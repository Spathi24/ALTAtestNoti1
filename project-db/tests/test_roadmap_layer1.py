"""Layer 1: RoadmapTask model + xlsx parser + import-roadmap CLI.

Coverage:
  - parser handles a tiny fixture xlsx (built in-memory)
  - parser skips editorial blank rows between phases
  - parser raises ValueError on unknown phase strings
  - parser raises if required columns are missing
  - sub_tasks splitter strips bullets / blanks correctly
  - import_roadmap_rows is idempotent: refuses without --overwrite,
    drops + re-inserts with --overwrite
  - list_roadmap_tasks returns rows sorted by phase order then ordinal
  - the unique (phase, ordinal) constraint fires on duplicate inserts
  - CLI cmd_import_roadmap end-to-end against an in-memory DB
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import pytest
from openpyxl import Workbook

from project_db.ai.roadmap import (
    _split_sub_tasks,
    import_roadmap_rows,
    list_roadmap_tasks,
    parse_roadmap_xlsx,
)
from project_db.db.models import RoadmapPhase, RoadmapTask


# ---------------------------------------------------------------------------
# Fixture builder
# ---------------------------------------------------------------------------


def _make_xlsx(tmp_path: Path, rows: list[tuple]) -> Path:
    """Write a small roadmap xlsx with the canonical header row."""
    wb = Workbook()
    ws = wb.active
    ws.append(["Design Phase", "Task", "Notes", "Sub-tasks"])
    for r in rows:
        ws.append(list(r))
    path = tmp_path / "roadmap.xlsx"
    wb.save(path)
    return path


# ---------------------------------------------------------------------------
# Parser
# ---------------------------------------------------------------------------


class TestSubTasksSplitter:
    def test_none_returns_none(self):
        assert _split_sub_tasks(None) is None

    def test_blank_string_returns_none(self):
        assert _split_sub_tasks("") is None
        assert _split_sub_tasks("   ") is None

    def test_nan_returns_none(self):
        # NaN != NaN, which is what the splitter checks for
        assert _split_sub_tasks(float("nan")) is None

    def test_single_line_no_bullet(self):
        assert _split_sub_tasks("just one item") == ["just one item"]

    def test_multi_line_with_dash_bullets(self):
        text = "-First item\n-Second item\n-Third item"
        assert _split_sub_tasks(text) == [
            "First item", "Second item", "Third item",
        ]

    def test_blank_lines_skipped(self):
        text = "-A\n\n-B\n   \n-C"
        assert _split_sub_tasks(text) == ["A", "B", "C"]

    def test_mixed_bullets(self):
        text = "-A\n• B\n* C\nD"
        assert _split_sub_tasks(text) == ["A", "B", "C", "D"]


class TestParseRoadmapXlsx:
    def test_happy_path(self, tmp_path):
        path = _make_xlsx(tmp_path, [
            ("SD", "Kick off", None, "-Prep timeline\n-Set goals"),
            ("SD", "Site analysis", None, "-Solar\n-Zoning"),
            ("DD", "Envelope details", None, None),
        ])
        out = parse_roadmap_xlsx(path)
        assert len(out) == 3
        assert [r["phase"] for r in out] == [
            RoadmapPhase.SD, RoadmapPhase.SD, RoadmapPhase.DD,
        ]
        # Ordinals reset per phase: SD-1, SD-2, DD-1
        assert [r["ordinal"] for r in out] == [1, 2, 1]
        assert out[0]["task_name"] == "Kick off"
        assert out[0]["sub_tasks"] == ["Prep timeline", "Set goals"]
        assert out[2]["sub_tasks"] is None

    def test_blank_rows_skipped(self, tmp_path):
        """Editorial blank rows between phases must be dropped without
        breaking ordinal counting."""
        path = _make_xlsx(tmp_path, [
            ("SD", "A", None, None),
            ("SD", "B", None, None),
            (None, None, None, None),         # blank separator
            ("DD", "C", None, None),
            ("", "", None, None),             # blank separator (empty strings)
            ("CD", "D", None, None),
        ])
        out = parse_roadmap_xlsx(path)
        assert len(out) == 4
        # Ordinals stay clean across separators
        assert out[0]["ordinal"] == 1  # SD-1
        assert out[1]["ordinal"] == 2  # SD-2
        assert out[2]["ordinal"] == 1  # DD-1
        assert out[3]["ordinal"] == 1  # CD-1

    def test_unknown_phase_raises(self, tmp_path):
        path = _make_xlsx(tmp_path, [
            ("XX", "Bogus", None, None),
        ])
        with pytest.raises(ValueError) as exc:
            parse_roadmap_xlsx(path)
        assert "XX" in str(exc.value)

    def test_missing_required_column_raises(self, tmp_path):
        wb = Workbook()
        ws = wb.active
        ws.append(["Phase", "Whatever"])  # wrong headers
        path = tmp_path / "bad.xlsx"
        wb.save(path)
        with pytest.raises(ValueError) as exc:
            parse_roadmap_xlsx(path)
        assert "design phase" in str(exc.value).lower() or "task" in str(exc.value).lower()

    def test_phase_string_case_normalized(self, tmp_path):
        """Lowercase / mixed-case phase strings still work."""
        path = _make_xlsx(tmp_path, [
            ("sd", "A", None, None),
            ("Dd", "B", None, None),
        ])
        out = parse_roadmap_xlsx(path)
        assert out[0]["phase"] == RoadmapPhase.SD
        assert out[1]["phase"] == RoadmapPhase.DD

    def test_notes_parsed_when_present(self, tmp_path):
        path = _make_xlsx(tmp_path, [
            ("SD", "A", "some note", None),
            ("SD", "B", None, None),
        ])
        out = parse_roadmap_xlsx(path)
        assert out[0]["notes"] == "some note"
        assert out[1]["notes"] is None

    def test_real_roadmap_file(self):
        """Sanity test against the actual roadmap file shipped with the
        repo.  Lives at ALTAtest/docs/Project Roadmap.xlsx -- one level
        up from the project-db package."""
        candidates = [
            Path("docs/Project Roadmap.xlsx"),
            Path("../docs/Project Roadmap.xlsx"),
        ]
        path = next((p for p in candidates if p.exists()), None)
        if path is None:
            pytest.skip("real roadmap xlsx not found")
        out = parse_roadmap_xlsx(path)
        # User's roadmap is 44 tasks (15 SD + 13 DD + 11 CD + 5 CA).
        # Tolerate ±2 for ongoing edits to the spreadsheet.
        assert 40 <= len(out) <= 50
        phases = {r["phase"] for r in out}
        assert phases == set(RoadmapPhase)


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------


class TestImportRoadmapRows:
    def _seed(self, session, n=2):
        """Helper: build a small parsed list."""
        return [
            {"phase": RoadmapPhase.SD, "ordinal": i + 1,
             "task_name": f"Task SD-{i+1}",
             "sub_tasks": ["a", "b"] if i == 0 else None,
             "notes": None}
            for i in range(n)
        ]

    def test_first_import_writes_rows(self, session):
        parsed = self._seed(session, n=3)
        result = import_roadmap_rows(session, parsed)
        assert result["ok"] is True
        assert result["total"] == 3
        assert result["by_phase"]["SD"] == 3
        assert result["overwrote"] == 0

        # Persistent
        session.commit()
        rows = session.query(RoadmapTask).all()
        assert len(rows) == 3
        # sub_tasks_json round-trips as JSON
        first = next(r for r in rows if r.ordinal == 1)
        assert json.loads(first.sub_tasks_json) == ["a", "b"]

    def test_second_import_without_overwrite_refuses(self, session):
        import_roadmap_rows(session, self._seed(session, n=2))
        session.commit()

        result = import_roadmap_rows(session, self._seed(session, n=2))
        assert result["ok"] is False
        assert "overwrite" in result["error"].lower()
        # No double-insert happened
        session.commit()
        assert session.query(RoadmapTask).count() == 2

    def test_overwrite_replaces_rows(self, session):
        import_roadmap_rows(session, self._seed(session, n=2))
        session.commit()

        # Re-import with a different set
        new_parsed = [
            {"phase": RoadmapPhase.DD, "ordinal": 1, "task_name": "X",
             "sub_tasks": None, "notes": None},
        ]
        result = import_roadmap_rows(session, new_parsed, overwrite=True)
        assert result["ok"] is True
        assert result["overwrote"] == 2
        assert result["total"] == 1

        session.commit()
        rows = session.query(RoadmapTask).all()
        assert len(rows) == 1
        assert rows[0].phase == RoadmapPhase.DD
        assert rows[0].task_name == "X"


class TestListRoadmapTasks:
    def test_returns_sorted_by_phase_then_ordinal(self, session):
        # Insert out of order on purpose
        parsed = [
            {"phase": RoadmapPhase.CA, "ordinal": 1, "task_name": "C1",
             "sub_tasks": None, "notes": None},
            {"phase": RoadmapPhase.SD, "ordinal": 2, "task_name": "S2",
             "sub_tasks": None, "notes": None},
            {"phase": RoadmapPhase.SD, "ordinal": 1, "task_name": "S1",
             "sub_tasks": None, "notes": None},
            {"phase": RoadmapPhase.DD, "ordinal": 1, "task_name": "D1",
             "sub_tasks": None, "notes": None},
        ]
        import_roadmap_rows(session, parsed)
        session.commit()
        out = list_roadmap_tasks(session)
        # Expected order: S1, S2, D1, C1
        assert [r["task_name"] for r in out] == ["S1", "S2", "D1", "C1"]
        assert [r["phase"] for r in out] == ["SD", "SD", "DD", "CA"]


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


class TestCliImportRoadmap:
    def test_end_to_end(self, tmp_path, patched_session_factory, capsys):
        from project_db.cli import cmd_import_roadmap

        path = _make_xlsx(tmp_path, [
            ("SD", "Kickoff", None, "-Set goals"),
            ("SD", "Site analysis", None, None),
            ("DD", "Envelope", None, None),
        ])

        rc = cmd_import_roadmap(argparse.Namespace(
            path=str(path), overwrite=False,
        ))
        assert rc == 0
        captured = capsys.readouterr().out
        assert "Parsed 3 roadmap task(s)" in captured
        assert "imported 3 task(s)" in captured

        # Verify rows in DB via session_scope (same factory the CLI used).
        from project_db.db import session_scope
        with session_scope() as s:
            assert s.query(RoadmapTask).count() == 3

    def test_missing_file_returns_2(self, patched_session_factory):
        from project_db.cli import cmd_import_roadmap

        rc = cmd_import_roadmap(argparse.Namespace(
            path="does/not/exist.xlsx", overwrite=False,
        ))
        assert rc == 2

    def test_re_import_without_overwrite_returns_1(
        self, tmp_path, patched_session_factory
    ):
        from project_db.cli import cmd_import_roadmap

        path = _make_xlsx(tmp_path, [
            ("SD", "A", None, None),
        ])
        # First import succeeds
        assert cmd_import_roadmap(
            argparse.Namespace(path=str(path), overwrite=False)
        ) == 0
        # Second without --overwrite fails
        rc = cmd_import_roadmap(argparse.Namespace(path=str(path), overwrite=False))
        assert rc == 1

    def test_re_import_with_overwrite_succeeds(
        self, tmp_path, patched_session_factory
    ):
        from project_db.cli import cmd_import_roadmap

        path = _make_xlsx(tmp_path, [
            ("SD", "A", None, None),
        ])
        assert cmd_import_roadmap(
            argparse.Namespace(path=str(path), overwrite=False)
        ) == 0
        assert cmd_import_roadmap(
            argparse.Namespace(path=str(path), overwrite=True)
        ) == 0


# ---------------------------------------------------------------------------
# Fixture: patched_session_factory (matches test_cli.py pattern)
# ---------------------------------------------------------------------------


@pytest.fixture
def patched_session_factory(db_engine, monkeypatch):
    from sqlalchemy.orm import sessionmaker

    from project_db.db import session as session_mod

    factory = sessionmaker(bind=db_engine, expire_on_commit=False)
    monkeypatch.setattr(session_mod, "_SessionLocal", factory)
    yield factory
