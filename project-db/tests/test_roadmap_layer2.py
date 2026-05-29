"""Layer 2 of the roadmap integration: prompt injection + actor filter.

The two proposal bots (timeline, scope) now receive a roadmap snippet
containing ONLY contractor-relevant tasks (actor = CONTRACTOR or BOTH).
Pure architect tasks are filtered out before injection so contractor-side
boards don't get noise.

Tests cover:
  - RoadmapActor enum + nullable column on RoadmapTask
  - list_roadmap_tasks(actors=...) filter
  - _render_roadmap_for_prompt: contractor-relevant only, empty when
    no actors assigned (pre-classify state)
  - _build_scope_prompt: roadmap section present when block given,
    absent when empty; instruction asks for `source` field when
    roadmap is present
  - _build_timeline_prompt: same roadmap-conditional behavior
  - _persist_scope_items: captures `source` field, defaults to
    "contract" for backward compat, warns on unknown values
  - end-to-end via generate_scope_proposals with mock LLM: roadmap
    block reaches the LLM call args; the parsed source label lands
    in the Proposal row
"""
from __future__ import annotations

import json

import pytest

from project_db.ai.proposals import (
    SCOPE_PROMPT_VERSION,
    TIMELINE_PROMPT_VERSION,
    _build_scope_prompt,
    _build_timeline_prompt,
    generate_scope_proposals,
)
from project_db.ai.context import ProjectContext
from project_db.ai.providers.mock import MockLLMProvider
from project_db.ai.roadmap import import_roadmap_rows, list_roadmap_tasks
from project_db.db.models import (
    Client,
    Document,
    Organization,
    Project,
    Proposal,
    RoadmapActor,
    RoadmapPhase,
    RoadmapTask,
    Task,
)
from project_db.db.models.docs import DocumentText
from project_db.db.models.proposals import ProposalStatus
from project_db.db.models.work import ProjectStatus, TaskStatus


@pytest.fixture
def roadmap(session):
    """Seed a tiny roadmap (3 tasks, mixed actors) into the test DB."""
    rows = [
        # SD: one ARCHITECT (will be filtered out) + one BOTH
        {"phase": RoadmapPhase.SD, "ordinal": 1, "task_name": "Site Analysis",
         "sub_tasks": ["a"], "notes": None},
        {"phase": RoadmapPhase.SD, "ordinal": 2, "task_name": "Project Kickoff",
         "sub_tasks": ["a"], "notes": None},
        # CA: one CONTRACTOR
        {"phase": RoadmapPhase.CA, "ordinal": 1, "task_name": "Punch List",
         "sub_tasks": None, "notes": None},
    ]
    import_roadmap_rows(session, rows)

    # Apply actors manually so we don't have to call the LLM
    tasks = session.query(RoadmapTask).all()
    by_name = {t.task_name: t for t in tasks}
    by_name["Site Analysis"].actor = RoadmapActor.ARCHITECT
    by_name["Project Kickoff"].actor = RoadmapActor.BOTH
    by_name["Punch List"].actor = RoadmapActor.CONTRACTOR
    session.commit()
    return tasks


# ---------------------------------------------------------------------------
# Model + enum
# ---------------------------------------------------------------------------


class TestRoadmapActorColumn:
    def test_actor_is_nullable(self, session):
        """A row imported BEFORE classify-roadmap runs has actor=NULL.
        Verify NULL is allowed (the filter helper treats NULL as
        'pre-classify; do not inject')."""
        rt = RoadmapTask(
            phase=RoadmapPhase.SD, ordinal=99, task_name="t", actor=None,
        )
        session.add(rt)
        session.commit()
        fetched = session.query(RoadmapTask).filter_by(ordinal=99).one()
        assert fetched.actor is None

    def test_enum_values(self):
        assert [a.value for a in RoadmapActor] == [
            "ARCHITECT", "CONTRACTOR", "BOTH",
        ]


# ---------------------------------------------------------------------------
# list_roadmap_tasks filter
# ---------------------------------------------------------------------------


class TestListRoadmapTasksFilter:
    def test_no_filter_returns_all(self, session, roadmap):
        rows = list_roadmap_tasks(session)
        assert len(rows) == 3
        # actor field is in the dict now
        actors = {r["actor"] for r in rows}
        assert actors == {"ARCHITECT", "CONTRACTOR", "BOTH"}

    def test_contractor_plus_both(self, session, roadmap):
        rows = list_roadmap_tasks(
            session, actors=[RoadmapActor.CONTRACTOR, RoadmapActor.BOTH],
        )
        names = {r["task_name"] for r in rows}
        assert names == {"Project Kickoff", "Punch List"}  # no Site Analysis

    def test_architect_only(self, session, roadmap):
        rows = list_roadmap_tasks(session, actors=[RoadmapActor.ARCHITECT])
        names = {r["task_name"] for r in rows}
        assert names == {"Site Analysis"}


# ---------------------------------------------------------------------------
# Roadmap rendering helper
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Prompt builders -- roadmap injection REMOVED (2026-05-29)
#
# Layer-2 roadmap injection was stripped: it pushed an architect design-phase
# template into contractor-execution prompts, producing flags the PM had to
# second-guess.  list_roadmap_tasks + the RoadmapTask table stay (Layer 1);
# the proposal prompts no longer consult them.  These tests pin that the
# injection does NOT come back.
# ---------------------------------------------------------------------------


def _trivial_ctx() -> ProjectContext:
    """A minimal ProjectContext for prompt-builder unit tests."""
    return ProjectContext(
        project={"name": "P", "code": None, "status": "ACTIVE"},
        client=None,
        tasks=[],
        documents=[],
        document_texts=[
            {"name": "SOW.pdf", "folder_path": "p/", "mime_type": "application/pdf",
             "text": "Scope: install kitchen.", "truncated": False,
             "document_id": "abc"}
        ],
        invoices=[],
        daily_logs=[],
        truncated=False,
    )


class TestScopePromptHasNoRoadmap:
    def test_no_roadmap_section_or_source_field(self):
        ctx = _trivial_ctx()
        sys_p, user_p = _build_scope_prompt(ctx)
        assert "CANONICAL CONTRACTOR-RELEVANT ROADMAP" not in user_p
        assert '"source"' not in user_p
        assert "roadmap" not in user_p.lower()
        assert "MAY ALSO flag a roadmap-sourced gap" not in sys_p


class TestTimelinePromptHasNoRoadmap:
    def test_no_roadmap_section_or_ordering_clause(self):
        from datetime import date

        ctx = _trivial_ctx()
        sys_p, user_p = _build_timeline_prompt(
            ctx,
            dateless=[{"title": "T", "is_subitem": False}],
            dated=[],
            today=date(2026, 6, 1),
        )
        assert "CANONICAL CONTRACTOR-RELEVANT ROADMAP" not in user_p
        assert "ordering anchor" not in user_p.lower()
        assert "roadmap" not in user_p.lower()


# ---------------------------------------------------------------------------
# Prompt versions bumped
# ---------------------------------------------------------------------------


class TestPromptVersions:
    def test_versions_bumped_past_v1(self):
        """Prompt versions evolve: Layer 2 bumped to *-roadmap, then the
        2026-05-26 tightening bumped again to *-quoted.  This test
        guards that we DON'T regress to the original v1 / v2 strings.
        """
        for v in (TIMELINE_PROMPT_VERSION, SCOPE_PROMPT_VERSION):
            # Must NOT be the original (pre-Layer-2) versions
            assert v not in ("timeline-v2", "scope-v1")
            # Must have a recognized suffix from a post-Layer-1 milestone
            assert any(tag in v for tag in ("roadmap", "quoted")), (
                f"prompt version {v!r} doesn't carry a known milestone "
                f"tag -- update this assertion when a new milestone "
                f"bumps the prompt."
            )


# ---------------------------------------------------------------------------
# End-to-end: generate_scope_proposals with a mocked LLM that returns
# both a contract-sourced and a roadmap-sourced gap.
# ---------------------------------------------------------------------------


@pytest.fixture
def scope_world(session, org: Organization, roadmap):
    """One project + one document with extracted text, ready for a
    generate_scope_proposals call."""
    c = Client(name="Acme", organization_id=org.canonical_id)
    session.add(c)
    session.flush()
    project = Project(
        name="P", client_id=c.canonical_id, status=ProjectStatus.ACTIVE,
    )
    session.add(project)
    session.flush()
    # One Monday task so the prompt has tasks to compare against
    session.add(Task(
        project_id=project.canonical_id, title="Existing task",
        status=TaskStatus.TODO,
    ))
    session.flush()
    doc = Document(
        project_id=project.canonical_id,
        name="SOW.pdf", mime_type="application/pdf",
        url="drive://x", folder_path="01. PROJECTS/ACTIVE/P",
        is_trashed=False,
    )
    session.add(doc)
    session.flush()
    session.add(DocumentText(
        document_id=doc.canonical_id,
        extracted_text="Scope: install kitchen cabinets and complete punch list.",
        extraction_method="pdf",
        token_count=20,
    ))
    session.commit()
    return {"project": project, "doc": doc}


class TestGenerateScopeNoRoadmapInjection:
    def test_roadmap_not_injected_into_prompt(self, session, scope_world):
        """Even with classified roadmap tasks in the DB, the scope prompt
        must NOT carry the roadmap section (injection removed 2026-05-29)."""
        provider = MockLLMProvider(responses=[json.dumps({"scope_gaps": []})])
        generate_scope_proposals(
            session, provider, scope_world["project"].canonical_id,
        )
        assert provider.calls
        last_user = provider.calls[-1]["messages"][-1].content
        assert "CANONICAL CONTRACTOR-RELEVANT ROADMAP" not in last_user
        assert "Punch List" not in last_user  # roadmap content absent

    def test_source_label_still_persists_if_model_supplies_it(self, session, scope_world):
        """Backward compat: _persist_scope_items still records a `source`
        label the model happens to return, defaulting to 'contract'."""
        provider = MockLLMProvider(responses=[json.dumps({
            "scope_gaps": [{
                "scope_item": "Install kitchen cabinets",
                "suggested_task_title": "Install kitchen cabinets",
                "confidence": 0.9,
                "reasoning": "SOW.pdf states 'install kitchen'.",
                "source_document": "SOW.pdf",
            }]
        })])
        batch = generate_scope_proposals(
            session, provider, scope_world["project"].canonical_id,
        )
        assert batch.created_count == 1
        p = session.query(Proposal).filter_by(field_name="scope_gap").one()
        assert json.loads(p.proposed_value)["source"] == "contract"

    def test_backward_compat_when_model_omits_source(self, session, scope_world):
        """A model that doesn't return `source` (pre-Layer-2 behavior)
        should still work -- we default to 'contract'."""
        provider = MockLLMProvider(responses=[json.dumps({
            "scope_gaps": [{
                "scope_item": "X",
                "suggested_task_title": "X",
                "confidence": 0.9,
                "reasoning": "stated in SOW.pdf",
                "source_document": "SOW.pdf",
                # NO 'source' field
            }]
        })])
        batch = generate_scope_proposals(
            session, provider, scope_world["project"].canonical_id,
        )
        assert batch.created_count == 1
        p = session.query(Proposal).filter_by(field_name="scope_gap").one()
        pv = json.loads(p.proposed_value)
        assert pv["source"] == "contract"  # default

    def test_unknown_source_warns_and_defaults(self, session, scope_world):
        provider = MockLLMProvider(responses=[json.dumps({
            "scope_gaps": [{
                "scope_item": "X",
                "suggested_task_title": "X",
                "confidence": 0.9,
                "reasoning": "stated in SOW.pdf",
                "source_document": "SOW.pdf",
                "source": "BOGUS",
            }]
        })])
        batch = generate_scope_proposals(
            session, provider, scope_world["project"].canonical_id,
        )
        # Created but warned
        assert batch.created_count == 1
        assert any("BOGUS" in w or "source label" in w for w in batch.warnings)
        # Defaulted to contract
        p = session.query(Proposal).filter_by(field_name="scope_gap").one()
        pv = json.loads(p.proposed_value)
        assert pv["source"] == "contract"
