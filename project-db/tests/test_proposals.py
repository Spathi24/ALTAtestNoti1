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
    _match_source_document,
    _parse_date,
    accept_proposal,
    generate_scope_proposals,
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


@pytest.fixture(autouse=True)
def _freeze_today(monkeypatch):
    """Pin the proposal engine's notion of "today" to a fixed date.

    These tests hardcode future proposed dates like 2026-06-01.  The timeline
    bot's past-date guard rejects proposed_start < today, so once the real clock
    passes those dates every test produces 0 proposals (a time-bomb).  Freezing
    today keeps the hardcoded dates safely in the future, deterministically.
    """
    class _Fixed(date):
        @classmethod
        def today(cls):
            return date(2026, 5, 15)

    monkeypatch.setattr("project_db.ai.proposals.date", _Fixed)


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


def _scope_mock(gaps_json: list[dict]) -> MockLLMProvider:
    """MockLLMProvider that returns a well-formed scope_gaps envelope."""
    return MockLLMProvider(responses=[json.dumps({"scope_gaps": gaps_json})])


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


class TestMatchSourceDocument:
    """Source-document matching is an anti-hallucination gate: a cited
    document that matches NOTHING we supplied is a hallucination signal."""

    _DOCS = {
        "Alta Construction Group - contract.pdf": "id-1",
        "Tony Estimate.pdf": "id-2",
    }

    def test_exact_match(self):
        assert _match_source_document(
            "Tony Estimate.pdf", self._DOCS) == "id-2"

    def test_case_insensitive_match(self):
        assert _match_source_document(
            "tony estimate.pdf", self._DOCS) == "id-2"

    def test_unambiguous_substring_match(self):
        # The model abbreviates -- "the contract" -> the contract doc.
        assert _match_source_document("contract", self._DOCS) == "id-1"

    def test_ambiguous_substring_returns_none(self):
        # ".pdf" is in both names -- we will not guess which.
        assert _match_source_document(".pdf", self._DOCS) is None

    def test_no_match_returns_none(self):
        # A document we never supplied -- the hallucination case.
        assert _match_source_document(
            "Fabricated Contract.pdf", self._DOCS) is None

    def test_none_and_nonstring(self):
        assert _match_source_document(None, self._DOCS) is None
        assert _match_source_document(123, self._DOCS) is None
        assert _match_source_document("", self._DOCS) is None


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

    def test_hallucinated_source_flagged_as_warning(self, session, timeline_fixture):
        """A cited source document we never supplied -> proposal still
        created (a human may know the dates), but flagged in
        batch.warnings as a possible hallucination -- NOT an error."""
        provider = _mock([
            {"task_index": 0, "proposed_start": "2026-06-01",
             "proposed_end": "2026-06-07", "confidence": 0.8,
             "reasoning": "the schedule says so",
             "source_document": "A Document We Never Gave The Model.pdf"},
        ])
        batch = generate_timeline_proposals(session, provider, timeline_fixture.canonical_id)
        session.commit()
        assert batch.created_count == 1          # still created
        assert not batch.errors                  # not rejected
        assert any("hallucination" in w for w in batch.warnings)

    def test_missing_reasoning_flagged_as_warning(self, session, timeline_fixture):
        """No reasoning violates the evidence-citation rule -> flagged."""
        provider = _mock([
            {"task_index": 0, "proposed_start": "2026-06-01",
             "proposed_end": "2026-06-07", "confidence": 0.8,
             "reasoning": "", "source_document": "Contract.pdf"},
        ])
        batch = generate_timeline_proposals(session, provider, timeline_fixture.canonical_id)
        session.commit()
        assert batch.created_count == 1
        assert any("no reasoning" in w for w in batch.warnings)

    def test_well_evidenced_proposal_has_no_warnings(self, session, timeline_fixture):
        """Happy path: matched source + reasoning present -> zero warnings."""
        provider = _mock([
            {"task_index": 0, "proposed_start": "2026-06-01",
             "proposed_end": "2026-06-07", "confidence": 0.9,
             "reasoning": "Contract says demo runs June 1-7.",
             "source_document": "Contract.pdf"},
        ])
        batch = generate_timeline_proposals(session, provider, timeline_fixture.canonical_id)
        session.commit()
        assert batch.created_count == 1
        assert not batch.warnings

    def test_past_dated_proposal_rejected(self, session, timeline_fixture):
        """A timeline entirely in the past is rejected -- proposals are
        forward-looking, so a past end date means the task is already done.
        This guards the bug where invoice/lease dates produced 2022 'schedules'.
        """
        provider = _mock([
            {"task_index": 0, "proposed_start": "2020-01-01",
             "proposed_end": "2020-02-01", "confidence": 0.9,
             "reasoning": "Invoice dated 2020.", "source_document": "Contract.pdf"},
        ])
        batch = generate_timeline_proposals(session, provider, timeline_fixture.canonical_id)
        session.commit()
        assert batch.created_count == 0
        assert len(batch.errors) == 1
        assert "past" in batch.errors[0].lower()

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
# generate_scope_proposals
# ---------------------------------------------------------------------------


class TestGenerateScopeProposals:
    def test_happy_path_creates_scope_proposals(self, session, timeline_fixture):
        provider = _scope_mock([
            {"scope_item": "Install fire-rated drywall in stairwell",
             "suggested_task_title": "Fire-rated drywall - stairwell",
             "confidence": 0.8, "reasoning": "Contract section 4 requires it.",
             "source_document": "Contract.pdf"},
        ])
        batch = generate_scope_proposals(session, provider, timeline_fixture.canonical_id)
        session.commit()

        assert batch.skipped_reason is None
        assert batch.created_count == 1
        p = batch.proposals[0]
        assert p.entity_type == "Project"
        assert p.entity_id == timeline_fixture.canonical_id
        assert p.field_name == "scope_gap"
        assert p.status == ProposalStatus.PENDING
        val = json.loads(p.proposed_value)
        assert "fire-rated drywall" in val["scope_item"].lower()
        assert val["suggested_task_title"] == "Fire-rated drywall - stairwell"

    def test_skips_when_no_document_text(self, session, client_factory):
        c = client_factory(name="C")
        p = Project(name="No Docs", code="ND", status=ProjectStatus.ACTIVE,
                    client_id=c.canonical_id)
        session.add(p)
        session.commit()
        session.add(Task(title="t", status=TaskStatus.TODO,
                         project_id=p.canonical_id))
        session.commit()

        batch = generate_scope_proposals(session, _scope_mock([]), p.canonical_id)
        assert batch.skipped_reason is not None
        assert "extracted text" in batch.skipped_reason
        assert batch.created_count == 0

    def test_empty_scope_gaps_is_valid(self, session, timeline_fixture):
        """{"scope_gaps": []} is a legitimate 'task list already covers it'."""
        batch = generate_scope_proposals(
            session, _scope_mock([]), timeline_fixture.canonical_id)
        assert batch.skipped_reason is None
        assert batch.created_count == 0

    def test_existing_task_is_not_flagged_as_gap(self, session, timeline_fixture):
        """A suggested task that already exists on the board is not a gap."""
        provider = _scope_mock([
            {"scope_item": "demolition of interior walls",
             "suggested_task_title": "Demolition",  # already a task in the fixture
             "confidence": 0.7, "reasoning": "x", "source_document": "Contract.pdf"},
        ])
        batch = generate_scope_proposals(session, provider, timeline_fixture.canonical_id)
        session.commit()
        assert batch.created_count == 0
        assert len(batch.errors) == 1
        assert "already exists" in batch.errors[0]

    def test_malformed_item_recorded_not_raised(self, session, timeline_fixture):
        provider = MockLLMProvider(
            responses=[json.dumps({"scope_gaps": ["just a string"]})])
        batch = generate_scope_proposals(session, provider, timeline_fixture.canonical_id)
        assert batch.created_count == 0
        assert len(batch.errors) == 1

    def test_rerun_supersedes_prior_scope_proposals(self, session, timeline_fixture):
        gap = [{"scope_item": "Roof flashing", "suggested_task_title": "Roof flashing install",
                "confidence": 0.8, "reasoning": "spec 7", "source_document": "Contract.pdf"}]
        b1 = generate_scope_proposals(session, _scope_mock(gap), timeline_fixture.canonical_id)
        session.commit()
        first_id = b1.proposals[0].canonical_id

        b2 = generate_scope_proposals(session, _scope_mock(gap), timeline_fixture.canonical_id)
        session.commit()
        assert b2.superseded_count == 1
        old = session.query(Proposal).filter_by(canonical_id=first_id).one()
        assert old.status == ProposalStatus.SUPERSEDED
        pending = session.query(Proposal).filter_by(
            field_name="scope_gap", status=ProposalStatus.PENDING).all()
        assert len(pending) == 1


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


class _FakeConnector:
    """Stand-in for MondayConnector in accept tests.

    Records every sync_back call so tests can assert the exact
    field_updates payload, and can be configured to return False or
    raise -- the two failure modes accept_proposal must survive.
    """
    def __init__(self, *, returns: bool = True, raises: bool = False):
        self.calls: list[dict] = []
        self._returns = returns
        self._raises = raises

    def sync_back(self, entity, field_updates):
        self.calls.append({"entity": entity, "field_updates": field_updates})
        if self._raises:
            raise RuntimeError("simulated Monday API failure")
        return self._returns


class TestAcceptProposal:
    """The risky half -- writes to Monday.  Ordering is load-bearing:
    the external write happens FIRST; status flips only on success."""

    def _one_pending(self, session, timeline_fixture) -> Proposal:
        provider = _mock([
            {"task_index": 0, "proposed_start": "2026-06-01",
             "proposed_end": "2026-06-07", "confidence": 0.9,
             "reasoning": "x", "source_document": "Contract.pdf"},
        ])
        batch = generate_timeline_proposals(session, provider, timeline_fixture.canonical_id)
        session.commit()
        return batch.proposals[0]

    def test_happy_path_writes_and_accepts(self, session, timeline_fixture):
        p = self._one_pending(session, timeline_fixture)
        conn = _FakeConnector(returns=True)
        result = accept_proposal(session, p.canonical_id, writeback=conn, decided_by="alice")
        session.commit()

        assert result["ok"] is True
        assert result["new_status"] == "ACCEPTED"
        reloaded = session.query(Proposal).filter_by(canonical_id=p.canonical_id).one()
        assert reloaded.status == ProposalStatus.ACCEPTED
        assert reloaded.decided_by == "alice"
        assert reloaded.decided_at is not None

    def test_sync_back_receives_timeline_payload(self, session, timeline_fixture):
        p = self._one_pending(session, timeline_fixture)
        conn = _FakeConnector(returns=True)
        accept_proposal(session, p.canonical_id, writeback=conn)
        session.commit()
        assert len(conn.calls) == 1
        fu = conn.calls[0]["field_updates"]
        assert fu == {"timeline": {"from": "2026-06-01", "to": "2026-06-07"}}

    def test_canonical_task_mirrored_on_accept(self, session, timeline_fixture):
        """After a successful accept the canonical Task carries the dates."""
        p = self._one_pending(session, timeline_fixture)
        task_id = p.entity_id
        conn = _FakeConnector(returns=True)
        accept_proposal(session, p.canonical_id, writeback=conn)
        session.commit()
        task = session.query(Task).filter_by(canonical_id=task_id).one()
        assert task.start_date == date(2026, 6, 1)
        assert task.end_date == date(2026, 6, 7)

    def test_write_back_false_leaves_proposal_pending(self, session, timeline_fixture):
        """LOAD-BEARING: a failed Monday write must NOT flip the status."""
        p = self._one_pending(session, timeline_fixture)
        task_id = p.entity_id
        conn = _FakeConnector(returns=False)
        result = accept_proposal(session, p.canonical_id, writeback=conn)
        session.commit()

        assert result["ok"] is False
        assert "returned False" in result["error"]
        reloaded = session.query(Proposal).filter_by(canonical_id=p.canonical_id).one()
        assert reloaded.status == ProposalStatus.PENDING, "status must NOT change on write failure"
        # And the canonical task must NOT have been mirrored.
        task = session.query(Task).filter_by(canonical_id=task_id).one()
        assert task.start_date is None
        assert task.end_date is None

    def test_write_back_raises_leaves_proposal_pending(self, session, timeline_fixture):
        """A raising connector is caught; proposal stays PENDING."""
        p = self._one_pending(session, timeline_fixture)
        conn = _FakeConnector(raises=True)
        result = accept_proposal(session, p.canonical_id, writeback=conn)
        session.commit()
        assert result["ok"] is False
        assert "raised" in result["error"]
        reloaded = session.query(Proposal).filter_by(canonical_id=p.canonical_id).one()
        assert reloaded.status == ProposalStatus.PENDING

    def test_dry_run_touches_nothing(self, session, timeline_fixture):
        p = self._one_pending(session, timeline_fixture)
        task_id = p.entity_id
        conn = _FakeConnector(returns=True)
        result = accept_proposal(session, p.canonical_id, writeback=conn, dry_run=True)
        session.commit()

        assert result["ok"] is True
        assert result["dry_run"] is True
        assert result["would_write"] == {"timeline": {"from": "2026-06-01", "to": "2026-06-07"}}
        # Nothing called, nothing changed.
        assert conn.calls == []
        reloaded = session.query(Proposal).filter_by(canonical_id=p.canonical_id).one()
        assert reloaded.status == ProposalStatus.PENDING
        task = session.query(Task).filter_by(canonical_id=task_id).one()
        assert task.start_date is None

    def test_dry_run_needs_no_connector(self, session, timeline_fixture):
        p = self._one_pending(session, timeline_fixture)
        result = accept_proposal(session, p.canonical_id, dry_run=True)  # writeback=None
        assert result["ok"] is True
        assert result["dry_run"] is True

    def test_real_accept_without_connector_fails(self, session, timeline_fixture):
        p = self._one_pending(session, timeline_fixture)
        result = accept_proposal(session, p.canonical_id)  # no writeback, not dry-run
        assert result["ok"] is False
        assert "no writeback" in result["error"]
        reloaded = session.query(Proposal).filter_by(canonical_id=p.canonical_id).one()
        assert reloaded.status == ProposalStatus.PENDING

    def test_cannot_accept_non_pending(self, session, timeline_fixture):
        p = self._one_pending(session, timeline_fixture)
        p.status = ProposalStatus.REJECTED
        session.commit()
        conn = _FakeConnector(returns=True)
        result = accept_proposal(session, p.canonical_id, writeback=conn)
        assert result["ok"] is False
        assert "not PENDING" in result["error"]
        assert conn.calls == [], "must not write to Monday for a non-PENDING proposal"

    def test_double_accept_is_rejected(self, session, timeline_fixture):
        p = self._one_pending(session, timeline_fixture)
        conn = _FakeConnector(returns=True)
        first = accept_proposal(session, p.canonical_id, writeback=conn)
        session.commit()
        assert first["ok"] is True
        # Second accept must fail -- proposal is already ACCEPTED.
        second = accept_proposal(session, p.canonical_id, writeback=conn)
        assert second["ok"] is False
        assert "not PENDING" in second["error"]
        assert len(conn.calls) == 1, "second accept must not re-write to Monday"

    def test_nonexistent_id(self, session):
        result = accept_proposal(session, str(uuid.uuid4()), writeback=_FakeConnector())
        assert result["ok"] is False
        assert "no proposal" in result["error"]

    def test_garbage_id(self, session):
        result = accept_proposal(session, "not-a-uuid", writeback=_FakeConnector())
        assert result["ok"] is False
        assert "valid UUID" in result["error"]


class TestProposalCLIParsing:
    def test_propose_parser(self):
        from project_db.cli import build_parser
        ns = build_parser().parse_args(["propose", "timelines", "Rockland"])
        assert ns.cmd == "propose"
        assert ns.kind == "timelines"
        assert ns.project == "Rockland"

    def test_propose_scope_parser(self):
        from project_db.cli import build_parser
        ns = build_parser().parse_args(["propose", "scope", "Rockland"])
        assert ns.cmd == "propose"
        assert ns.kind == "scope"
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

    def test_proposals_accept_parser(self):
        from project_db.cli import build_parser
        ns = build_parser().parse_args([
            "proposals", "accept", "some-uuid", "--dry-run", "--by", "alice",
        ])
        assert ns.proposals_action == "accept"
        assert ns.proposal_id == "some-uuid"
        assert ns.dry_run is True
        assert ns.by == "alice"

    def test_proposals_accept_parser_defaults(self):
        from project_db.cli import build_parser
        ns = build_parser().parse_args(["proposals", "accept", "some-uuid"])
        assert ns.proposals_action == "accept"
        assert ns.dry_run is False
        assert ns.by is None

    def test_proposals_accept_parser_no_id(self):
        """`proposals accept` with no id is valid -- it lists pending proposals."""
        from project_db.cli import build_parser
        ns = build_parser().parse_args(["proposals", "accept"])
        assert ns.proposals_action == "accept"
        assert ns.proposal_id is None
        assert ns.yes is False

    def test_proposals_accept_all_parser(self):
        from project_db.cli import build_parser
        ns = build_parser().parse_args(["proposals", "accept", "all", "--yes"])
        assert ns.proposals_action == "accept"
        assert ns.proposal_id == "all"
        assert ns.yes is True

    def test_proposals_reject_parser_no_id(self):
        """`proposals reject` with no id is valid -- it lists pending proposals."""
        from project_db.cli import build_parser
        ns = build_parser().parse_args(["proposals", "reject"])
        assert ns.proposals_action == "reject"
        assert ns.proposal_id is None
        assert ns.yes is False

    def test_proposals_reject_all_parser(self):
        from project_db.cli import build_parser
        ns = build_parser().parse_args(["proposals", "reject", "all", "--yes"])
        assert ns.proposals_action == "reject"
        assert ns.proposal_id == "all"
        assert ns.yes is True


# ---------------------------------------------------------------------------
# bulk_dismiss_stale
# ---------------------------------------------------------------------------


class TestBulkDismissStale:
    """bulk_dismiss_stale: reject PENDING proposals older than N days."""

    def _old_proposal(self, session, project, task, *, days: int = 31) -> Proposal:
        from datetime import datetime, timedelta
        p = Proposal(
            entity_type="Task",
            entity_id=task.canonical_id,
            field_name="task_status",
            proposed_value=json.dumps({"status": "DONE", "monday_label": "Done"}),
            confidence=0.8,
            prompt_version="field-note-v1",
            status=ProposalStatus.PENDING,
        )
        p.created_at = datetime.utcnow() - timedelta(days=days)
        p.updated_at = p.created_at
        session.add(p)
        session.commit()
        return p

    def test_dismisses_old_pending(self, session, timeline_fixture):
        from project_db.ai.proposals import bulk_dismiss_stale
        task = session.query(Task).filter_by(project_id=timeline_fixture.canonical_id).first()
        old_p = self._old_proposal(session, timeline_fixture, task, days=31)

        count = bulk_dismiss_stale(session, timeline_fixture.canonical_id, days_old=30)
        session.commit()

        assert count == 1
        session.refresh(old_p)
        assert old_p.status == ProposalStatus.REJECTED
        assert "stale" in old_p.rejection_reason

    def test_skips_fresh_proposals(self, session, timeline_fixture):
        from project_db.ai.proposals import bulk_dismiss_stale
        task = session.query(Task).filter_by(project_id=timeline_fixture.canonical_id).first()
        fresh_p = Proposal(
            entity_type="Task",
            entity_id=task.canonical_id,
            field_name="task_status",
            proposed_value=json.dumps({"status": "DONE", "monday_label": "Done"}),
            confidence=0.8,
            prompt_version="field-note-v1",
            status=ProposalStatus.PENDING,
        )
        session.add(fresh_p)
        session.commit()

        count = bulk_dismiss_stale(session, timeline_fixture.canonical_id, days_old=30)
        assert count == 0
        session.refresh(fresh_p)
        assert fresh_p.status == ProposalStatus.PENDING

    def test_skips_non_pending(self, session, timeline_fixture):
        from datetime import datetime, timedelta
        from project_db.ai.proposals import bulk_dismiss_stale
        task = session.query(Task).filter_by(project_id=timeline_fixture.canonical_id).first()
        accepted_p = Proposal(
            entity_type="Task",
            entity_id=task.canonical_id,
            field_name="task_status",
            proposed_value=json.dumps({"status": "DONE", "monday_label": "Done"}),
            confidence=0.8,
            prompt_version="field-note-v1",
            status=ProposalStatus.ACCEPTED,
        )
        accepted_p.created_at = datetime.utcnow() - timedelta(days=60)
        accepted_p.updated_at = accepted_p.created_at
        session.add(accepted_p)
        session.commit()

        count = bulk_dismiss_stale(session, timeline_fixture.canonical_id, days_old=30)
        assert count == 0

    def test_project_level_proposals_dismissed(self, session, timeline_fixture):
        from datetime import datetime, timedelta
        from project_db.ai.proposals import bulk_dismiss_stale
        old_p = Proposal(
            entity_type="Project",
            entity_id=timeline_fixture.canonical_id,
            field_name="new_task",
            proposed_value=json.dumps({"title": "Old task", "evidence": "old note"}),
            confidence=0.7,
            prompt_version="field-note-v1",
            status=ProposalStatus.PENDING,
        )
        old_p.created_at = datetime.utcnow() - timedelta(days=45)
        old_p.updated_at = old_p.created_at
        session.add(old_p)
        session.commit()

        count = bulk_dismiss_stale(session, timeline_fixture.canonical_id, days_old=30)
        assert count >= 1
        session.refresh(old_p)
        assert old_p.status == ProposalStatus.REJECTED

    def test_empty_project_returns_zero(self, session, timeline_fixture):
        from project_db.ai.proposals import bulk_dismiss_stale
        count = bulk_dismiss_stale(session, timeline_fixture.canonical_id, days_old=30)
        assert count == 0

    def test_bad_project_id_returns_zero(self, session):
        from project_db.ai.proposals import bulk_dismiss_stale
        count = bulk_dismiss_stale(session, "not-a-uuid", days_old=30)
        assert count == 0
