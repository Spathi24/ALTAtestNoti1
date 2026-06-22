"""Tests for narrate_weekly_report -- the LLM narration layer on top of the
deterministic weekly delta.

All tests use MockLLMProvider -- zero API calls, zero token cost.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta

import pytest

from project_db.ai.providers.mock import MockLLMProvider
from project_db.ai.views import narrate_weekly_report
from project_db.db.models import Document, Project, Task, TaskStatus
from project_db.db.models.field_notes import FieldNote, NoteChannel, NoteClass
from project_db.db.models.work import ProjectStatus

NOW = datetime(2026, 6, 22, 12, 0, 0)
_MOCK_NARRATIVE = "Alpha Tower had one document updated and a slab poured this week. The slab completion closes out the foundation phase -- no further action required."


@pytest.fixture
def seeded(session, client_factory):
    """Alpha: in-window doc + task (has changes). Charlie: nothing (zero changes)."""
    client = client_factory(name="Acme Co")
    cid = client.canonical_id
    alpha = Project(name="Alpha Tower", code="ALP", status=ProjectStatus.ACTIVE, client_id=cid)
    charlie = Project(name="Charlie Shed", code="CHR", status=ProjectStatus.ACTIVE, client_id=cid)
    session.add_all([alpha, charlie])
    session.commit()

    session.add(
        Document(
            name="Quote A.xlsx",
            url="u1",
            mime_type="application/vnd.ms-excel",
            project_id=alpha.canonical_id,
            modified_at_source=NOW - timedelta(days=2),
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
    # Both Alpha (2 changes) and Charlie (0) in scope; only Alpha triggers an LLM call.
    provider = MockLLMProvider(responses=[_MOCK_NARRATIVE])
    data = narrate_weekly_report(session, provider=provider, now=NOW, since_days=7)
    # Only Alpha has changes in the all-projects view.
    changed = [p for p in data["projects"] if p["change_count"] > 0]
    assert len(changed) == 1
    assert len(provider.calls) == 1


def test_narrate_prompt_contains_project_name_and_facts(session, seeded):
    provider = MockLLMProvider(responses=[_MOCK_NARRATIVE])
    narrate_weekly_report(session, "Alpha", provider=provider, now=NOW, since_days=7)
    assert len(provider.calls) == 1
    call = provider.calls[0]
    user_content = call["messages"][0].content
    payload = json.loads(user_content)
    assert payload["project"] == "Alpha Tower"
    # Document title present in the facts payload
    doc_names = [d["name"] for d in payload["documents_changed"]]
    assert "Quote A.xlsx" in doc_names
    # Task title present
    task_titles = [t["title"] for t in payload["tasks_completed"]]
    assert "Pour slab" in task_titles


def test_narrate_system_prompt_sent(session, seeded):
    provider = MockLLMProvider(responses=[_MOCK_NARRATIVE])
    narrate_weekly_report(session, "Alpha", provider=provider, now=NOW, since_days=7)
    call = provider.calls[0]
    assert call["system"] is not None
    assert "construction" in call["system"].lower()


def test_narrate_error_passthrough(session, seeded):
    provider = MockLLMProvider(responses=[_MOCK_NARRATIVE])
    data = narrate_weekly_report(session, "Nonexistent XYZ", provider=provider, now=NOW)
    assert "error" in data
    assert len(provider.calls) == 0  # no LLM call when report errors


def test_narrate_result_is_json_serializable(session, seeded):
    provider = MockLLMProvider(responses=[_MOCK_NARRATIVE])
    data = narrate_weekly_report(session, provider=provider, now=NOW, since_days=7)
    json.dumps(data)  # must not raise
