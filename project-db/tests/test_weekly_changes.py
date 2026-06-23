"""Tests for report_weekly_changes -- the deterministic weekly delta.

Facts only, no LLM. This is the foundation the weekly per-project report is
built on: documents touched in Drive, field notes received, proposals
opened/decided, tasks completed -- all within a look-back window.

`now` is pinned so the window is deterministic and timezone-free.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta

import pytest

from project_db.ai.views import report_weekly_changes
from project_db.db.models import Document, Project, Task, TaskStatus
from project_db.db.models.field_notes import FieldNote, NoteChannel, NoteClass
from project_db.db.models.proposals import Proposal, ProposalStatus
from project_db.db.models.work import ProjectStatus

NOW = datetime(2026, 6, 22, 12, 0, 0)


@pytest.fixture
def seeded(session, client_factory):
    """Three projects: Alpha (docs/notes/tasks), Bravo (proposals), Charlie (nothing)."""
    client = client_factory(name="Acme Co")
    cid = client.canonical_id
    alpha = Project(name="Alpha Tower", code="ALP", status=ProjectStatus.ACTIVE, client_id=cid)
    bravo = Project(name="Bravo House", code="BRV", status=ProjectStatus.ACTIVE, client_id=cid)
    charlie = Project(name="Charlie Shed", code="CHR", status=ProjectStatus.ACTIVE, client_id=cid)
    session.add_all([alpha, bravo, charlie])
    session.commit()

    # Alpha: 1 in-window doc, 1 stale doc, 1 trashed doc, 1 note, 2 tasks (1 stale)
    session.add_all(
        [
            Document(
                name="Quote A.xlsx",
                url="u1",
                mime_type="application/vnd.ms-excel",
                project_id=alpha.canonical_id,
                modified_at_source=NOW - timedelta(days=2),
            ),
            Document(
                name="Old Contract.pdf",
                url="u2",
                mime_type="application/pdf",
                project_id=alpha.canonical_id,
                modified_at_source=NOW - timedelta(days=30),
            ),
            Document(
                name="Trashed.pdf",
                url="u3",
                mime_type="application/pdf",
                project_id=alpha.canonical_id,
                is_trashed=True,
                modified_at_source=NOW - timedelta(days=1),
            ),
        ]
    )
    session.add(
        FieldNote(
            raw_text="Framing done on the second floor",
            received_at=NOW - timedelta(days=1),
            channel=NoteChannel.WEB,
            classification=NoteClass.TASK_PROGRESS,
            project_id=alpha.canonical_id,
        )
    )
    session.add_all(
        [
            Task(
                title="Pour slab",
                status=TaskStatus.DONE,
                project_id=alpha.canonical_id,
                completed_at=(NOW - timedelta(days=3)).date(),
            ),
            Task(
                title="Old task",
                status=TaskStatus.DONE,
                project_id=alpha.canonical_id,
                completed_at=(NOW - timedelta(days=20)).date(),
            ),
        ]
    )
    session.commit()

    # Bravo: a Task-targeted proposal opened in window + a Project-targeted
    # proposal decided in window (opened earlier, outside the window).
    btask = Task(title="Install windows", status=TaskStatus.TODO, project_id=bravo.canonical_id)
    session.add(btask)
    session.commit()
    session.add_all(
        [
            Proposal(
                entity_type="Task",
                entity_id=btask.canonical_id,
                field_name="end_date",
                proposed_value='"2026-07-01"',
                status=ProposalStatus.PENDING,
                created_at=NOW - timedelta(days=1),
            ),
            Proposal(
                entity_type="Project",
                entity_id=bravo.canonical_id,
                field_name="budget_amount",
                proposed_value='"200000"',
                status=ProposalStatus.ACCEPTED,
                created_at=NOW - timedelta(days=10),
                decided_at=NOW - timedelta(days=2),
            ),
        ]
    )
    session.commit()
    return {"alpha": alpha, "bravo": bravo, "charlie": charlie}


def test_all_projects_only_shows_changed(session, seeded):
    data = report_weekly_changes(session, now=NOW, since_days=7)
    names = {p["name"] for p in data["projects"]}
    assert names == {"Alpha Tower", "Bravo House"}  # Charlie excluded (no changes)
    assert data["project_count"] == 2
    assert data["total_changes"] == 5  # alpha 3 + bravo 2


def test_alpha_window_and_trash_filtering(session, seeded):
    data = report_weekly_changes(session, "Alpha", now=NOW, since_days=7)
    assert data["project_count"] == 1
    alpha = data["projects"][0]
    assert len(alpha["documents"]) == 1  # stale + trashed excluded
    assert alpha["documents"][0]["name"] == "Quote A.xlsx"
    assert len(alpha["field_notes"]) == 1
    assert len(alpha["tasks_completed"]) == 1
    assert alpha["tasks_completed"][0]["title"] == "Pour slab"
    assert alpha["change_count"] == 3


def test_proposal_attribution_task_and_project(session, seeded):
    data = report_weekly_changes(session, "Bravo", now=NOW, since_days=7)
    bravo = data["projects"][0]
    assert len(bravo["proposals_opened"]) == 1
    assert bravo["proposals_opened"][0]["entity_type"] == "Task"
    assert len(bravo["proposals_decided"]) == 1
    assert bravo["proposals_decided"][0]["status"] == "ACCEPTED"


def test_requested_project_shown_even_with_no_changes(session, seeded):
    data = report_weekly_changes(session, "Charlie", now=NOW, since_days=7)
    assert data["project_count"] == 1
    assert data["projects"][0]["change_count"] == 0


def test_unknown_project_returns_error(session, seeded):
    data = report_weekly_changes(session, "Nonexistent", now=NOW)
    assert "error" in data


def test_result_is_json_serializable(session, seeded):
    data = report_weekly_changes(session, now=NOW, since_days=7)
    json.dumps(data)  # must not raise


def test_narrow_window_excludes_older_changes(session, seeded):
    # 1-day window: Alpha's doc (2d) and task (3d) drop out; the note (1d) stays.
    data = report_weekly_changes(session, "Alpha", now=NOW, since_days=1)
    alpha = data["projects"][0]
    assert len(alpha["documents"]) == 0
    assert len(alpha["tasks_completed"]) == 0
    assert len(alpha["field_notes"]) == 1


def test_telegram_communications_surface_per_project_and_site_section(session, seeded):
    """Telegram messages (LabourSourceEvent) reach the report: project-attributed
    ones into the project's communications + events; project-less ones into the
    top-level site_communications; quarantined/ignored excluded."""
    from project_db.db.models import LabourSourceEvent

    alpha = seeded["alpha"]
    session.add_all(
        [
            LabourSourceEvent(
                source_channel="telegram",
                source_kind="telegram_text",
                ingestion_status="received",
                received_at=NOW - timedelta(days=1),
                source_created_at=NOW - timedelta(days=1),
                source_sender_key="111",
                raw_text="Concrete delivered to the north side, all good.",
                project_id_hint=alpha.canonical_id,
            ),
            LabourSourceEvent(
                source_channel="telegram",
                source_kind="telegram_text",
                ingestion_status="received",
                received_at=NOW - timedelta(days=1),
                source_created_at=NOW - timedelta(days=1),
                source_sender_key="222",
                raw_text="Who has the key to the gate?",
                project_id_hint=None,
            ),
            LabourSourceEvent(
                source_channel="telegram",
                source_kind="telegram_text",
                ingestion_status="quarantined",
                received_at=NOW - timedelta(days=1),
                source_created_at=NOW - timedelta(days=1),
                source_sender_key="333",
                raw_text="QUARANTINEDSPAM",
                project_id_hint=alpha.canonical_id,
            ),
        ]
    )
    session.commit()

    data = report_weekly_changes(session, now=NOW, since_days=7)
    alpha_out = next(p for p in data["projects"] if p["name"] == "Alpha Tower")
    assert len(alpha_out["communications"]) == 1
    assert "Concrete delivered" in alpha_out["communications"][0]["text"]
    assert any(e["type"] == "communication" for e in alpha_out["events"])

    assert len(data["site_communications"]) == 1
    assert "key to the gate" in data["site_communications"][0]["text"]

    # quarantined messages never leak into the report
    assert "QUARANTINEDSPAM" not in json.dumps(data)


def test_telegram_comm_effective_ts_falls_back_to_received_at(session, seeded):
    from project_db.db.models import LabourSourceEvent

    alpha = seeded["alpha"]
    session.add(
        LabourSourceEvent(
            source_channel="telegram",
            source_kind="telegram_text",
            ingestion_status="received",
            received_at=NOW - timedelta(days=2),
            source_created_at=None,  # no send time -> fall back to received_at
            source_sender_key="444",
            raw_text="No send time on this one.",
            project_id_hint=alpha.canonical_id,
        )
    )
    session.commit()
    data = report_weekly_changes(session, "Alpha", now=NOW, since_days=7)
    comms = data["projects"][0]["communications"]
    assert len(comms) == 1
    assert comms[0]["received_at"].startswith("2026-06-20")  # NOW - 2 days


def test_window_start_is_day_granular(session, seeded):
    # Regression: a field note timestamped ~7 days ago at an EARLIER clock time
    # than `now` must still appear in a 7-day report.  Before the day-granular
    # fix, the minute-precise boundary silently dropped it -- the report's best
    # content flickered in/out depending on the time of day it was run.
    late_now = datetime(2026, 6, 22, 19, 46, 0)
    boundary_ts = datetime(2026, 6, 15, 18, 17, 0)  # 7d ago, but earlier in the day
    session.add(
        FieldNote(
            raw_text="Boundary note -- must not be dropped",
            received_at=boundary_ts,
            channel=NoteChannel.WEB,
            classification=NoteClass.TASK_PROGRESS,
            project_id=seeded["alpha"].canonical_id,
        )
    )
    session.commit()
    data = report_weekly_changes(session, "Alpha", now=late_now, since_days=7)
    texts = [n["text"] for n in data["projects"][0]["field_notes"]]
    assert any("Boundary note" in t for t in texts)
