"""Tests for the Phase-3b proposal engine.

Everything runs against MockLLMProvider -- no API key, no network,
deterministic.  Coverage:

  * generate_timeline_proposals happy path -> Proposal rows
  * skip paths (no dateless tasks / no document text)
  * malformed LLM items recorded as errors, not crashes
  * auto-supersede of prior PENDING proposals
  * confidence clamping, date validation, end-before-start rejection
  * LLM provider failure handled gracefully
  * pure helpers: _parse_date, _clamp_confidence, _coerce_item_list
  * read side: list_proposals, get_proposal_detail
  * CLI parsing for propose / proposals list / proposals show
"""
from __future__ import annotations

import json
import uuid
from datetime import date

import pytest

from project_db.ai.proposals import (
    _clamp_confidence,
    _coerce_item_list,
    _parse_date,
    generate_timeline_proposals,
    get_proposal_detail,
    list_proposals,
    reject_proposal,
)
from project_db.ai.providers import MockLLMProvider
from project_db.db.models import (
    Document,
    DocumentText,
    Project,
    Proposal,
    ProposalStatus,
    Task,
)
from project_db.db.models.work import ProjectStatus, TaskStatus


# ---------------------------------------------------------------------------
# Fixture: a project with dateless tasks + a contract with extracted text
# ---------------------------------------------------------------------------


@pytest.fixture
def timeline_fixture(session, client_factory):
    """One project, 2 dateless tasks, 1 dated task, 1 contract w/ text."""
    c = client_factory(name="Acme")
    p = Project(
        name="923 Rockland", code="R923", status=ProjectStatus.ACTIVE,
        client_id=c.canonical_id,
    )
    session.add(p)
    session.commit()

    session.add_all([
        Task(title="Demolition", status=TaskStatus.TODO, project_id=p.canonical_id),
        Task(title="Framing", status=TaskStatus.TODO, project_id=p.canonical_id),
        Task(title="Already scheduled", status=TaskStatus.TODO,
             start_date=date(2026, 4, 1), end_date=date(2026, 4, 10),
             project_id=p.canonical_id),
    ])
    contract = Document(
        name="Contract.pdf", url="https://drive/c",
        mime_type="application/pdf", storage_ref="c1",
        folder_path="Active/923 Rockland",
        project_id=p.canonical_id,
    )
    session.add(contract)
    session.commit()
    session.add(DocumentText(
        document_id=contract.canonical_id,
        extracted_text=(
            "SCHEDULE: Demolition runs June 1-7, 2026.  Framing follows, "
            "June 8-22, 2026."
        ),
        extraction_method="pdf-pymupdf",
        token_count=20,
    ))
    session.commit()
    return p


def _mock(proposals_json: list[dict]) -> MockLLMProvider:
    """MockLLMProvider that returns a well-formed proposals envelope."""
    return MockLLMProvider(responses=[json.dumps({"proposals": proposals_json})])


# ---------------------------------------------------------------------------
# Pure helpers
# ---------------------------------------------------------------------------


class TestParseDate:
    def test_iso_date(self):
        assert _parse_date("2026-06-01") == date(2026, 6, 1)

    def test_iso_datetime(self):
        assert _parse_date("2026-06-01T12:00:00") == date(2026, 6, 1)

    def test_none_and_garbage(self):
        assert _parse_date(None) is None
        assert _parse_date("") is None
        assert _parse_date("not a date") is None
        assert _parse_date(12345) is None


class TestClampConfidence:
    def test_in_range(self):
        assert _clamp_confidence(0.7) == 0.7

    def test_clamps_high_and_low(self):
        assert _clamp_confidence(1.5) == 1.0
        assert _clamp_confidence(-0.2) == 0.0

    def test_none_and_garbage(self):
        assert _clamp_confidence(None) is None
        assert _clamp_confidence("high") is None

    def test_string_number_coerced(self):
        assert _clamp_confidence("0.5") == 0.5


class TestCoerceItemList:
    def test_envelope_shape(self):
        assert _coerce_item_list({"proposals": [1, 2]}) == [1, 2]

    def test_bare_list(self):
        assert _coerce_item_list([1, 2, 3]) == [1, 2, 3]

    def test_missing_key(self):
        assert _coerce_item_list({"other": 1}) == []

    def test_garbage(self):
        assert _coerce_item_list("nope") == []
        assert _coerce_item_list(None) == []


# ---------------------------------------------------------------------------
# generate_timeline_proposals
# ---------------------------------------------------------------------------


class TestGenerateTimelineProposals:
    def test_happy_path_creates_proposals(self, session, timeline_fixture):
        provider = _mock([
            {"task_index": 0, "proposed_start": "2026-06-01",
             "proposed_end": "2026-06-07", "confidence": 0.9,
             "reasoning": "Contract says demo runs June 1-7.",
             "source_document": "Contract.pdf"},
        ])
        batch = generate_timeline_proposals(session, provider, timeline_fixture.canonical_id)
        session.commit()

        assert batch.skipped_reason is None
        assert batch.created_count == 1
        assert batch.llm_raw_item_count == 1
        assert not batch.errors

        rows = session.query(Proposal).all()
        assert len(rows) == 1
        p = rows[0]
        assert p.entity_type == "Task"
        assert p.field_name == "timeline"
        assert p.status == ProposalStatus.PENDING
        assert p.confidence == 0.9
        val = json.loads(p.proposed_value)
        assert val["start_date"] == "2026-06-01"
        assert val["end_date"] == "2026-06-07"

    def test_proposal_targets_correct_task(self, session, timeline_fixture):
        """The integer index must map to the right canonical Task."""
        provider = _mock([
            {"task_index": 0, "proposed_start": "2026-06-01",
             "proposed_end": "2026-06-07", "confidence": 0.8,
             "reasoning": "x", "source_document": "Contract.pdf"},
        ])
        batch = generate_timeline_proposals(session, provider, timeline_fixture.canonical_id)
        session.commit()
        # The proposal's entity_id must be a real dateless Task on this project.
        p = batch.proposals[0]
        task = session.query(Task).filter_by(canonical_id=p.entity_id).one()
        assert task.title in ("Demolition", "Framing")
        assert task.start_date is None  # was dateless

    def test_skips_when_no_dateless_tasks(self, session, client_factory):
        c = client_factory(name="C")
        p = Project(name="All Dated", code="AD", status=ProjectStatus.ACTIVE,
                    client_id=c.canonical_id)
        session.add(p)
        session.commit()
        session.add(Task(
            title="Done deal", status=TaskStatus.TODO,
            start_date=date(2026, 1, 1), end_date=date(2026, 1, 2),
            project_id=p.canonical_id,
        ))
        session.commit()

        provider = _mock([])
        batch = generate_timeline_proposals(session, provider, p.canonical_id)
        assert batch.skipped_reason is not None
        assert "missing dates" in batch.skipped_reason
        assert batch.created_count == 0

    def test_skips_when_no_document_text(self, session, client_factory):
        c = client_factory(name="C")
        p = Project(name="No Docs", code="ND", status=ProjectStatus.ACTIVE,
                    client_id=c.canonical_id)
        session.add(p)
        session.commit()
        session.add(Task(title="Orphan task", status=TaskStatus.TODO,
                         project_id=p.canonical_id))
        session.commit()

        provider = _mock([])
        batch = generate_timeline_proposals(session, provider, p.canonical_id)
        assert batch.skipped_reason is not None
        assert "no extracted document text" in batch.skipped_reason

    def test_empty_proposals_list_is_valid(self, session, timeline_fixture):
        """LLM returning {"proposals": []} is a legitimate 'no evidence' answer."""
        provider = _mock([])
        batch = generate_timeline_proposals(session, provider, timeline_fixture.canonical_id)
        assert batch.skipped_reason is None
        assert batch.created_count == 0
        assert batch.llm_raw_item_count == 0

    def test_malformed_items_recorded_not_raised(self, session, timeline_fixture):
        provider = _mock([
            {"task_index": 99, "proposed_start": "2026-06-01",  # index OOR
             "proposed_end": "2026-06-07", "confidence": 0.5, "reasoning": "x"},
            {"task_index": 0, "proposed_start": "garbage",       # bad date
             "proposed_end": "2026-06-07", "confidence": 0.5, "reasoning": "x"},
            {"task_index": 1, "proposed_start": "2026-06-20",    # end < start
             "proposed_end": "2026-06-01", "confidence": 0.5, "reasoning": "x"},
        ])
        batch = generate_timeline_proposals(session, provider, timeline_fixture.canonical_id)
        session.commit()
        assert batch.created_count == 0
        assert len(batch.errors) == 3
        assert session.query(Proposal).count() == 0

    def test_non_dict_item_recorded(self, session, timeline_fixture):
        provider = MockLLMProvider(responses=[json.dumps({"proposals": ["just a string"]})])
        batch = generate_timeline_proposals(session, provider, timeline_fixture.canonical_id)
        assert batch.created_count == 0
        assert len(batch.errors) == 1

    def test_confidence_clamped_on_persist(self, session, timeline_fixture):
        provider = _mock([
            {"task_index": 0, "proposed_start": "2026-06-01",
             "proposed_end": "2026-06-07", "confidence": 4.7,  # out of range
             "reasoning": "x", "source_document": "Contract.pdf"},
        ])
        batch = generate_timeline_proposals(session, provider, timeline_fixture.canonical_id)
        session.commit()
        assert batch.proposals[0].confidence == 1.0

    def test_auto_supersede_prior_pending(self, session, timeline_fixture):
        """Second run for the same task supersedes the first proposal.

        Within one session the Task query order is deterministic
        (insertion / rowid order), so task_index 0 resolves to the same
        canonical Task on both runs -- we can assert directly.
        """
        prov1 = _mock([
            {"task_index": 0, "proposed_start": "2026-06-01",
             "proposed_end": "2026-06-07", "confidence": 0.8,
             "reasoning": "first", "source_document": "Contract.pdf"},
        ])
        batch1 = generate_timeline_proposals(session, prov1, timeline_fixture.canonical_id)
        session.commit()
        first_id = batch1.proposals[0].canonical_id
        first_task = batch1.proposals[0].entity_id

        # Second run proposes for the SAME task (index 0 again).
        prov2 = _mock([
            {"task_index": 0, "proposed_start": "2026-06-02",
             "proposed_end": "2026-06-09", "confidence": 0.95,
             "reasoning": "revised", "source_document": "Contract.pdf"},
        ])
        batch2 = generate_timeline_proposals(session, prov2, timeline_fixture.canonical_id)
        session.commit()

        # Index 0 must resolve to the same task -- the precondition of
        # the supersede behaviour we're verifying.
        assert batch2.proposals[0].entity_id == first_task, (
            "task query order not deterministic -- test precondition broken"
        )
        assert batch2.superseded_count == 1
        old = session.query(Proposal).filter_by(canonical_id=first_id).one()
        assert old.status == ProposalStatus.SUPERSEDED
        pending = session.query(Proposal).filter_by(
            entity_id=first_task, status=ProposalStatus.PENDING,
        ).all()
        assert len(pending) == 1
        assert pending[0].canonical_id == batch2.proposals[0].canonical_id

    def test_llm_failure_handled_gracefully(self, session, timeline_fixture):
        """A provider that always returns junk -> complete_json raises -> graceful skip."""
        bad = MockLLMProvider(responses=["not json at all"])
        batch = generate_timeline_proposals(session, bad, timeline_fixture.canonical_id)
        # complete_json exhausts retries and raises LLMProviderError, caught.
        assert batch.skipped_reason == "LLM call failed"
        assert batch.created_count == 0
        assert batch.errors


# ---------------------------------------------------------------------------
# Read side
# ---------------------------------------------------------------------------


class TestListProposals:
    def test_lists_created_proposals(self, session, timeline_fixture):
        provider = _mock([
            {"task_index": 0, "proposed_start": "2026-06-01",
             "proposed_end": "2026-06-07", "confidence": 0.9,
             "reasoning": "x", "source_document": "Contract.pdf"},
        ])
        generate_timeline_proposals(session, provider, timeline_fixture.canonical_id)
        session.commit()

        rows = list_proposals(session)
        assert len(rows) == 1
        r = rows[0]
        assert r["field_name"] == "timeline"
        assert r["status"] == "PENDING"
        assert r["entity_type"] == "Task"
        assert r["entity_label"] in ("Demolition", "Framing")
        assert r["project_name"] == "923 Rockland"

    def test_status_filter(self, session, timeline_fixture):
        provider = _mock([
            {"task_index": 0, "proposed_start": "2026-06-01",
             "proposed_end": "2026-06-07", "confidence": 0.9,
             "reasoning": "x", "source_document": "Contract.pdf"},
        ])
        generate_timeline_proposals(session, provider, timeline_fixture.canonical_id)
        session.commit()

        assert len(list_proposals(session, status=ProposalStatus.PENDING)) == 1
        assert len(list_proposals(session, status=ProposalStatus.ACCEPTED)) == 0

    def test_kind_filter(self, session, timeline_fixture):
        provider = _mock([
            {"task_index": 0, "proposed_start": "2026-06-01",
             "proposed_end": "2026-06-07", "confidence": 0.9,
             "reasoning": "x", "source_document": "Contract.pdf"},
        ])
        generate_timeline_proposals(session, provider, timeline_fixture.canonical_id)
        session.commit()
        assert len(list_proposals(session, kind="timeline")) == 1
        assert len(list_proposals(session, kind="scope")) == 0

    def test_empty_when_none(self, session):
        assert list_proposals(session) == []


class TestGetProposalDetail:
    def test_full_detail(self, session, timeline_fixture):
        provider = _mock([
            {"task_index": 0, "proposed_start": "2026-06-01",
             "proposed_end": "2026-06-07", "confidence": 0.9,
             "reasoning": "Contract evidence here.", "source_document": "Contract.pdf"},
        ])
        batch = generate_timeline_proposals(session, provider, timeline_fixture.canonical_id)
        session.commit()
        pid = batch.proposals[0].canonical_id

        detail = get_proposal_detail(session, str(pid))
        assert detail is not None
        assert detail["proposal_id"] == str(pid)
        assert detail["field_name"] == "timeline"
        assert detail["proposed_value"]["reasoning"] == "Contract evidence here."
        # source_document mapped to a real Document.
        assert len(detail["source_documents"]) == 1
        assert detail["source_documents"][0]["name"] == "Contract.pdf"

    def test_unknown_id_returns_none(self, session):
        assert get_proposal_detail(session, str(uuid.uuid4())) is None

    def test_garbage_id_returns_none(self, session):
        assert get_proposal_detail(session, "not-a-uuid") is None


# ---------------------------------------------------------------------------
# CLI parsing
# ---------------------------------------------------------------------------


class TestRejectProposal:
    """The safe half of the approval loop -- pure DB, no external write."""

    def _one_pending(self, session, timeline_fixture) -> Proposal:
        provider = _mock([
            {"task_index": 0, "proposed_start": "2026-06-01",
             "proposed_end": "2026-06-07", "confidence": 0.9,
             "reasoning": "x", "source_document": "Contract.pdf"},
        ])
        batch = generate_timeline_proposals(session, provider, timeline_fixture.canonical_id)
        session.commit()
        return batch.proposals[0]

    def test_reject_pending_proposal(self, session, timeline_fixture):
        p = self._one_pending(session, timeline_fixture)
        result = reject_proposal(session, p.canonical_id, decided_by="alice")
        session.commit()

        assert result["ok"] is True
        assert result["new_status"] == "REJECTED"
        reloaded = session.query(Proposal).filter_by(canonical_id=p.canonical_id).one()
        assert reloaded.status == ProposalStatus.REJECTED
        assert reloaded.decided_by == "alice"
        assert reloaded.decided_at is not None

    def test_reject_stores_reason(self, session, timeline_fixture):
        p = self._one_pending(session, timeline_fixture)
        reject_proposal(session, p.canonical_id, reason="contract was revised", decided_by="bob")
        session.commit()
        reloaded = session.query(Proposal).filter_by(canonical_id=p.canonical_id).one()
        assert reloaded.rejection_reason == "contract was revised"

    def test_reject_nonexistent_id(self, session):
        result = reject_proposal(session, str(uuid.uuid4()))
        assert result["ok"] is False
        assert "no proposal" in result["error"]

    def test_reject_garbage_id(self, session):
        result = reject_proposal(session, "not-a-uuid")
        assert result["ok"] is False
        assert "valid UUID" in result["error"]

    def test_cannot_reject_already_rejected(self, session, timeline_fixture):
        p = self._one_pending(session, timeline_fixture)
        reject_proposal(session, p.canonical_id, decided_by="alice")
        session.commit()
        # Second reject must fail explicitly.
        result = reject_proposal(session, p.canonical_id, decided_by="alice")
        assert result["ok"] is False
        assert "not PENDING" in result["error"]

    def test_cannot_reject_accepted_proposal(self, session, timeline_fixture):
        """A proposal already moved to ACCEPTED cannot be rejected."""
        p = self._one_pending(session, timeline_fixture)
        p.status = ProposalStatus.ACCEPTED  # simulate a prior accept
        session.commit()
        result = reject_proposal(session, p.canonical_id)
        assert result["ok"] is False
        assert "ACCEPTED" in result["error"]
        # Status must be untouched.
        reloaded = session.query(Proposal).filter_by(canonical_id=p.canonical_id).one()
        assert reloaded.status == ProposalStatus.ACCEPTED

    def test_cannot_reject_superseded_proposal(self, session, timeline_fixture):
        p = self._one_pending(session, timeline_fixture)
        p.status = ProposalStatus.SUPERSEDED
        session.commit()
        result = reject_proposal(session, p.canonical_id)
        assert result["ok"] is False

    def test_reject_default_decided_by_is_none_at_function_level(self, session, timeline_fixture):
        """The function itself doesn't invent a user; the CLI supplies one."""
        p = self._one_pending(session, timeline_fixture)
        reject_proposal(session, p.canonical_id)  # no decided_by
        session.commit()
        reloaded = session.query(Proposal).filter_by(canonical_id=p.canonical_id).one()
        assert reloaded.decided_by is None
        assert reloaded.status == ProposalStatus.REJECTED


class TestProposalCLIParsing:
    def test_propose_parser(self):
        from project_db.cli import build_parser
        ns = build_parser().parse_args(["propose", "timelines", "Rockland"])
        assert ns.cmd == "propose"
        assert ns.kind == "timelines"
        assert ns.project == "Rockland"

    def test_proposals_list_parser(self):
        from project_db.cli import build_parser
        ns = build_parser().parse_args(["proposals", "list", "--status", "pending"])
        assert ns.cmd == "proposals"
        assert ns.proposals_action == "list"
        assert ns.status == "pending"

    def test_proposals_list_no_filters(self):
        from project_db.cli import build_parser
        ns = build_parser().parse_args(["proposals", "list"])
        assert ns.proposals_action == "list"
        assert ns.status is None
        assert ns.kind is None

    def test_proposals_show_parser(self):
        from project_db.cli import build_parser
        ns = build_parser().parse_args(["proposals", "show", "some-uuid"])
        assert ns.proposals_action == "show"
        assert ns.proposal_id == "some-uuid"

    def test_proposals_reject_parser(self):
        from project_db.cli import build_parser
        ns = build_parser().parse_args([
            "proposals", "reject", "some-uuid",
            "--reason", "stale", "--by", "alice",
        ])
        assert ns.proposals_action == "reject"
        assert ns.proposal_id == "some-uuid"
        assert ns.reason == "stale"
        assert ns.by == "alice"

    def test_proposals_reject_parser_minimal(self):
        from project_db.cli import build_parser
        ns = build_parser().parse_args(["proposals", "reject", "some-uuid"])
        assert ns.proposals_action == "reject"
        assert ns.reason is None
        assert ns.by is None
