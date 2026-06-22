"""Tests for narrate_weekly_report -- the LLM narration layer on top of the
deterministic weekly delta.

All tests use MockLLMProvider -- zero API calls, zero token cost.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta

import pytest

from project_db.ai.providers.mock import MockLLMProvider
from project_db.ai.views import narrate_weekly_report, report_weekly_changes
from project_db.db.models import Document, Project, Task, TaskStatus
from project_db.db.models.docs import DocumentText
from project_db.db.models.field_notes import FieldNote, NoteChannel, NoteClass
from project_db.db.models.work import ProjectStatus

NOW = datetime(2026, 6, 22, 12, 0, 0)
_MOCK_NARRATIVE = (
    "Alpha Tower saw active progress this week. "
    "Quote A.xlsx was updated in Drive and the slab pour task was completed. "
    "No pending proposals require a decision."
)


@pytest.fixture
def seeded(session, client_factory):
    """Alpha: in-window doc + task (has changes). Charlie: nothing (zero changes)."""
    client = client_factory(name="Acme Co")
    cid = client.canonical_id
    alpha = Project(name="Alpha Tower", code="ALP", status=ProjectStatus.ACTIVE, client_id=cid)
    charlie = Project(name="Charlie Shed", code="CHR", status=ProjectStatus.ACTIVE, client_id=cid)
    session.add_all([alpha, charlie])
    session.commit()

    doc = Document(
        name="Quote A.xlsx",
        url="u1",
        mime_type="application/vnd.ms-excel",
        project_id=alpha.canonical_id,
        modified_at_source=NOW - timedelta(days=2),
    )
    session.add(doc)
    session.commit()

    # Attach extracted text so content enrichment is exercised.
    session.add(
        DocumentText(
            document_id=doc.canonical_id,
            extracted_text="Scope: supply and install slab for Unit A. Price: $45,000.",
            extraction_method="gdrive-export",
        )
    )
    session.add(
        Task(
            title="Pour slab",
            status=TaskStatus.DONE,
            project_id=alpha.canonical_id,
            completed_at=(NOW - timedelta(days=3)).date(),
        )
    )
    session.commit()
    return {"alpha": alpha, "charlie": charlie}


# --- narrate_weekly_report tests ---

def test_narrate_adds_narrative_key(session, seeded):
    provider = MockLLMProvider(responses=[_MOCK_NARRATIVE])
    data = narrate_weekly_report(session, "Alpha", provider=provider, now=NOW, since_days=7)
    assert "error" not in data
    proj = data["projects"][0]
    assert "narrative" in proj
    assert proj["narrative"] == _MOCK_NARRATIVE


def test_narrate_zero_changes_skips_llm(session, seeded):
    provider = MockLLMProvider(responses=[_MOCK_NARRATIVE])
    data = narrate_weekly_report(session, "Charlie", provider=provider, now=NOW, since_days=7)
    charlie = data["projects"][0]
    assert charlie["change_count"] == 0
    assert "narrative" in charlie
    assert "Charlie Shed" in charlie["narrative"]
    assert len(provider.calls) == 0  # no LLM call for zero-change project


def test_narrate_calls_provider_once_per_changed_project(session, seeded):
    # All-projects view: only Alpha has changes; Charlie has none.
    provider = MockLLMProvider(responses=[_MOCK_NARRATIVE])
    data = narrate_weekly_report(session, provider=provider, now=NOW, since_days=7)
    changed = [p for p in data["projects"] if p["change_count"] > 0]
    assert len(changed) == 1
    assert len(provider.calls) == 1


def test_narrate_prompt_uses_events_list(session, seeded):
    """The prompt must use the chronological events list with full content."""
    provider = MockLLMProvider(responses=[_MOCK_NARRATIVE])
    narrate_weekly_report(session, "Alpha", provider=provider, now=NOW, since_days=7)
    assert len(provider.calls) == 1
    user_content = provider.calls[0]["messages"][0].content
    payload = json.loads(user_content)

    assert payload["project"] == "Alpha Tower"
    assert "events" in payload  # chronological list, not separate lists

    # Event content must appear in the payload.
    all_text = json.dumps(payload)
    assert "Quote A.xlsx" in all_text
    assert "Pour slab" in all_text
    # Extracted doc text must be present (not just the filename).
    assert "slab for Unit A" in all_text


def test_narrate_prompt_includes_prior_window(session, seeded):
    provider = MockLLMProvider(responses=[_MOCK_NARRATIVE])
    narrate_weekly_report(session, "Alpha", provider=provider, now=NOW, since_days=7)
    payload = json.loads(provider.calls[0]["messages"][0].content)
    assert "prior_week" in payload


def test_narrate_system_prompt_construction_context(session, seeded):
    provider = MockLLMProvider(responses=[_MOCK_NARRATIVE])
    narrate_weekly_report(session, "Alpha", provider=provider, now=NOW, since_days=7)
    system = provider.calls[0]["system"]
    assert system is not None
    assert "construction" in system.lower()


def test_narrate_max_tokens_generous(session, seeded):
    """Narration should use at least 1000 tokens -- not the old 300-token stub."""
    provider = MockLLMProvider(responses=[_MOCK_NARRATIVE])
    narrate_weekly_report(session, "Alpha", provider=provider, now=NOW, since_days=7)
    assert provider.calls[0]["max_tokens"] >= 1000


def test_narrate_error_passthrough(session, seeded):
    provider = MockLLMProvider(responses=[_MOCK_NARRATIVE])
    data = narrate_weekly_report(session, "Nonexistent XYZ", provider=provider, now=NOW)
    assert "error" in data
    assert len(provider.calls) == 0


def test_narrate_result_is_json_serializable(session, seeded):
    provider = MockLLMProvider(responses=[_MOCK_NARRATIVE])
    data = narrate_weekly_report(session, provider=provider, now=NOW, since_days=7)
    json.dumps(data)  # must not raise


# --- report_weekly_changes enrichment tests (content, events, prior_window) ---

def test_delta_document_includes_extracted_content(session, seeded):
    data = report_weekly_changes(session, "Alpha", now=NOW, since_days=7)
    doc = data["projects"][0]["documents"][0]
    assert doc["content_available"] is True
    assert "slab for Unit A" in (doc["content"] or "")


def test_delta_events_are_chronological(session, seeded):
    data = report_weekly_changes(session, "Alpha", now=NOW, since_days=7)
    events = data["projects"][0]["events"]
    assert len(events) >= 2
    timestamps = [e["timestamp"] for e in events]
    assert timestamps == sorted(timestamps)


def test_delta_events_include_all_types(session, seeded):
    data = report_weekly_changes(session, "Alpha", now=NOW, since_days=7)
    types = {e["type"] for e in data["projects"][0]["events"]}
    assert "document_updated" in types
    assert "task_completed" in types


def test_delta_prior_window_key_present(session, seeded):
    data = report_weekly_changes(session, "Alpha", now=NOW, since_days=7)
    proj = data["projects"][0]
    assert "prior_window" in proj
    pw = proj["prior_window"]
    assert "docs" in pw
    assert "tasks_completed" in pw


def test_delta_task_includes_schedule_fields(session, seeded):
    data = report_weekly_changes(session, "Alpha", now=NOW, since_days=7)
    task = data["projects"][0]["tasks_completed"][0]
    assert task["title"] == "Pour slab"
    assert "start_date" in task
    assert "end_date" in task
    assert "status" in task
