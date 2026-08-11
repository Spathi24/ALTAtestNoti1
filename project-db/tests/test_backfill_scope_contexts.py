"""SC-2: deterministic pilot ScopeContext backfill (Documents only).

Covers the pure registered-mapping resolver and the backfill: correct bindings,
UNRESOLVED (not LEGACY_UNSCOPED) for unmatched paths, idempotency, and that it
never touches another project's documents or any SowItem/quote/budget rows.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

from project_db.db.models import Client, Document, Organization, Project, ScopeContext
from project_db.db.models.work import ProjectStatus

_SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "backfill_scope_contexts.py"
_spec = importlib.util.spec_from_file_location("backfill_scope_contexts", _SCRIPT)
backfill = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(backfill)

_BASE = "01. PROJECTS/ACTIVE/923-927 Rockland"


class TestResolver:
    @pytest.mark.parametrize(
        "path,expected",
        [
            (f"{_BASE}/923 Rockland/SPECS", "923_INTERIOR"),
            (f"{_BASE}/923 Rockland", "923_INTERIOR"),
            (f"{_BASE}/927 ROCKLAND/SITE PHOTOS", "927_UNIT"),
            (f"{_BASE}/EXTERIOR/Landscape", "EXTERIOR"),
            (f"{_BASE}/EXTERIOR", "EXTERIOR"),
            (None, None),
            ("", None),
            (_BASE, None),  # stops at the project folder -> no context segment
            (f"{_BASE}/SOW/packages", None),  # organizational folder, NOT a context
            ("some/unrelated/path", None),  # project folder absent
        ],
    )
    def test_resolve_context_key(self, path, expected):
        assert backfill.resolve_context_key(path) == expected


@pytest.fixture
def pilot(session, org: Organization):
    c = Client(name="Rockland Client", organization_id=org.canonical_id)
    session.add(c)
    session.flush()
    p = Project(
        name="923-927 Rockland",
        code="2026001",
        client_id=c.canonical_id,
        status=ProjectStatus.ACTIVE,
    )
    session.add(p)
    session.flush()
    docs = [
        ("interior spec", f"{_BASE}/923 Rockland/SPECS"),
        ("927 quote", f"{_BASE}/927 ROCKLAND/SITE PHOTOS"),
        ("exterior landscape", f"{_BASE}/EXTERIOR/Landscape"),
        ("no path doc", None),
        ("root only doc", _BASE),
    ]
    for name, fp in docs:
        session.add(
            Document(name=name, url=f"drive://{name}", folder_path=fp, project_id=p.canonical_id)
        )
    session.commit()
    return p


class TestBackfill:
    def test_binds_documents_and_quarantines_the_rest(self, session, pilot):
        summary = backfill.backfill_pilot_scope_contexts(session)
        session.commit()
        assert summary["contexts_created"] == 3
        assert summary["documents_resolved"] == 3
        assert summary["documents_unresolved"] == 2
        assert summary["per_context"] == {"923_INTERIOR": 1, "927_UNIT": 1, "EXTERIOR": 1}

        # Resolved docs point at a real context; unmatched docs are UNRESOLVED
        # (quarantine), NOT LEGACY_UNSCOPED, and stay unbound.
        by_name = {d.name: d for d in session.query(Document).all()}
        assert by_name["interior spec"].context_resolution_state == "RESOLVED"
        assert by_name["interior spec"].scope_context_id is not None
        assert by_name["no path doc"].context_resolution_state == "UNRESOLVED"
        assert by_name["no path doc"].scope_context_id is None
        assert by_name["root only doc"].context_resolution_state == "UNRESOLVED"

    def test_idempotent(self, session, pilot):
        backfill.backfill_pilot_scope_contexts(session)
        session.commit()
        again = backfill.backfill_pilot_scope_contexts(session)
        session.commit()
        assert again["contexts_created"] == 0  # no duplicate contexts
        assert again["documents_resolved"] == 3
        assert session.query(ScopeContext).count() == 3

    def test_does_not_touch_other_projects(self, session, org, pilot):
        c = Client(name="Other", organization_id=org.canonical_id)
        session.add(c)
        session.flush()
        p2 = Project(
            name="Other",
            code="2026002",
            client_id=c.canonical_id,
            status=ProjectStatus.ACTIVE,
        )
        session.add(p2)
        session.flush()
        session.add(
            Document(
                name="other doc",
                url="drive://other",
                folder_path="01. PROJECTS/ACTIVE/Other/923 Rockland/x",  # same segment name!
                project_id=p2.canonical_id,
            )
        )
        session.commit()

        backfill.backfill_pilot_scope_contexts(session)
        session.commit()

        other = session.query(Document).filter_by(name="other doc").one()
        assert other.context_resolution_state == "LEGACY_UNSCOPED"  # untouched
        assert other.scope_context_id is None
        # No context rows were created under the other project.
        assert session.query(ScopeContext).filter_by(project_id=p2.canonical_id).count() == 0
