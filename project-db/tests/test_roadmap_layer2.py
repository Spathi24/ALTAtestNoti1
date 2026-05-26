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
    _render_roadmap_for_prompt,
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


class TestRenderRoadmapForPrompt:
    def test_empty_when_no_actors_assigned(self, session):
        """Pre-classify state: roadmap_task rows exist but no actor on
        any.  Helper returns '' so the prompt behaves as pre-Layer-2."""
        rt = RoadmapTask(
            phase=RoadmapPhase.SD, ordinal=1, task_name="x", actor=None,
        )
        session.add(rt)
        session.commit()
        assert _render_roadmap_for_prompt(session) == ""

    def test_filters_to_contractor_and_both(self, session, roadmap):
        block = _render_roadmap_for_prompt(session)
        assert block  # non-empty
        # Contractor-relevant tasks are in the block
        assert "Project Kickoff" in block
        assert "Punch List" in block
        # ARCHITECT-only tasks are filtered out
        assert "Site Analysis" not in block
        # Header is present
        assert "CANONICAL CONTRACTOR-RELEVANT ROADMAP" in block

    def test_groups_by_phase(self, session, roadmap):
        block = _render_roadmap_for_prompt(session)
        # Phase headers appear
        assert "-- SD phase --" in block
        assert "-- CA phase --" in block


# ---------------------------------------------------------------------------
# Prompt builders -- roadmap conditional behavior
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


class TestScopePromptRoadmapConditional:
    def test_without_roadmap_no_source_field(self):
        ctx = _trivial_ctx()
        sys_p, user_p = _build_scope_prompt(ctx, roadmap_block="")
        # No roadmap section
        assert "CANONICAL CONTRACTOR-RELEVANT ROADMAP" not in user_p
        # No source field in the JSON schema
        assert '"source"' not in user_p
        # No roadmap rule in system prompt
        assert "MAY ALSO flag a roadmap-sourced gap" not in sys_p

    def test_with_roadmap_includes_section_and_source_field(self):
        ctx = _trivial_ctx()
        block = (
            "=== CANONICAL CONTRACTOR-RELEVANT ROADMAP ===\n"
            "-- CA phase --\n  [CA-01] (BOTH) Punch List"
        )
        sys_p, user_p = _build_scope_prompt(ctx, roadmap_block=block)
        # Roadmap section reaches the prompt
        assert "CANONICAL CONTRACTOR-RELEVANT ROADMAP" in user_p
        assert "Punch List" in user_p
        # Source field required in output JSON
        assert '"source"' in user_p
        assert '"contract"' in user_p and '"roadmap"' in user_p
        # System rule is present
        assert "MAY ALSO flag a roadmap-sourced gap" in sys_p


class TestTimelinePromptRoadmapConditional:
    def test_without_roadmap_no_phase_clause(self):
        from datetime import date

        ctx = _trivial_ctx()
        sys_p, user_p = _build_timeline_prompt(
            ctx,
            dateless=[{"title": "T", "is_subitem": False}],
            dated=[],
            today=date(2026, 6, 1),
            roadmap_block="",
        )
        assert "CANONICAL CONTRACTOR-RELEVANT ROADMAP" not in user_p
        assert "ordering anchor" not in user_p.lower()

    def test_with_roadmap_includes_section_and_ordering_clause(self):
        from datetime import date

        ctx = _trivial_ctx()
        block = (
            "=== CANONICAL CONTRACTOR-RELEVANT ROADMAP ===\n"
            "-- CA phase --\n  [CA-01] (BOTH) Punch List"
        )
        sys_p, user_p = _build_timeline_prompt(
            ctx,
            dateless=[{"title": "T", "is_subitem": False}],
            dated=[],
            today=date(2026, 6, 1),
            roadmap_block=block,
        )
        assert "CANONICAL CONTRACTOR-RELEVANT ROADMAP" in user_p
        # Instruction asks model to use it as an ordering anchor
        assert "ordering anchor" in user_p.lower()


# ---------------------------------------------------------------------------
# Prompt versions bumped
# ---------------------------------------------------------------------------


class TestPromptVersions:
    def test_versions_signal_roadmap_layer(self):
        assert "roadmap" in TIMELINE_PROMPT_VERSION
        assert "roadmap" in SCOPE_PROMPT_VERSION


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


class TestGenerateScopeWithRoadmap:
    def test_persists_source_labels(self, session, scope_world):
        """Mock the LLM to return one contract gap + one roadmap gap.
        Verify the source label lands on the Proposal row."""
        provider = MockLLMProvider(responses=[json.dumps({
            "scope_gaps": [
                {
                    "scope_item": "Install kitchen cabinets",
                    "suggested_task_title": "Install kitchen cabinets",
                    "confidence": 0.9,
                    "reasoning": "SOW.pdf states 'install kitchen'.",
                    "source_document": "SOW.pdf",
                    "source": "contract",
                },
                {
                    "scope_item": "Punch list coordination",
                    "suggested_task_title": "Coordinate punch list",
                    "confidence": 0.8,
                    "reasoning": "Roadmap entry CA-01 'Punch List' applies; "
                                 "no task covers it.",
                    "source_document": "",
                    "source": "roadmap",
                },
            ]
        })])

        batch = generate_scope_proposals(
            session, provider, scope_world["project"].canonical_id,
        )
        assert batch.created_count == 2

        # Confirm the prompt the mock saw INCLUDED the roadmap section
        assert provider.calls
        # The user message is the last (only) message; the roadmap
        # block should be embedded somewhere in it.
        last_user = provider.calls[-1]["messages"][-1].content
        assert "CANONICAL CONTRACTOR-RELEVANT ROADMAP" in last_user
        # The actor filter worked: Site Analysis (ARCHITECT) is NOT in
        # the prompt; Punch List (CONTRACTOR) is.
        assert "Site Analysis" not in last_user
        assert "Punch List" in last_user

        # Check the persisted proposals
        proposals = session.query(Proposal).filter_by(
            entity_type="Project", field_name="scope_gap",
        ).all()
        assert len(proposals) == 2
        sources = []
        for p in proposals:
            pv = json.loads(p.proposed_value)
            sources.append(pv["source"])
        assert sorted(sources) == ["contract", "roadmap"]

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
