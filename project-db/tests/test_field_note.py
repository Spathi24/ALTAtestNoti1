"""Tests for Win 1 and Win 3 of the field-note MVP.

Coverage:
  - FieldNote model creation + SQLite round-trip
  - MockFieldNoteExtractor deterministic behaviour
  - ingest_field_note: happy path (task_done / blocker / new_task / scope_change)
  - ingest_field_note: empty-note skip
  - ingest_field_note: multi-signal note yields multiple FieldNote + Proposal rows
  - ingest_field_note: A6 guard -- signal without quoted_excerpt is rejected
  - ingest_field_note: declined match (null task_index) for status signals
  - ingest_field_note: date_shift with parseable dates creates timeline Proposal
  - ingest_field_note: date_shift without dates creates no Proposal (error recorded)
  - ingest_field_note: other classification creates FieldNote but no Proposal
  - accept_proposal: task_status write-back (dry-run preview)
  - accept_proposal: task_status rejects unknown canonical status
  - accept_proposal: task_status mirrors onto task.status on success
  - _ACCEPTABLE_FIELDS now includes task_status
  - Win 3 photos: image_paths flows to extractor; photo-only notes proceed;
    _load_image_b64 size guard and extension filter
  - Strategy C task rendering: status grouping, temporal + semantic scoring,
    parent annotation, done trimming
"""

from __future__ import annotations

import json
import uuid
from datetime import date, datetime

import pytest

from project_db.ai.field_note_extraction import (
    _DONE_TRIM_K,
    _IMAGE_EXTS,
    MockFieldNoteExtractor,
    NoteClass,
    _load_image_b64,
    _render_task_block,
    ingest_field_note,
)
from project_db.ai.proposals import _ACCEPTABLE_FIELDS, accept_proposal
from project_db.db.models import (
    FieldNote,
    Project,
    Proposal,
    ProposalStatus,
    Task,
)
from project_db.db.models import (
    NoteChannel as DBNoteChannel,
)
from project_db.db.models import (
    NoteClass as DBNoteClass,
)
from project_db.db.models.work import ProjectStatus, TaskStatus

# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def project(session, client_factory):
    c = client_factory(name="Rockland Owner")
    p = Project(
        name="923-927 Rockland",
        code="R923",
        status=ProjectStatus.ACTIVE,
        client_id=c.canonical_id,
    )
    session.add(p)
    session.commit()
    return p


@pytest.fixture
def tasks(session, project):
    t1 = Task(
        title="Install silicone sealant", status=TaskStatus.TODO, project_id=project.canonical_id
    )
    t2 = Task(title="Adjust glass door", status=TaskStatus.TODO, project_id=project.canonical_id)
    t3 = Task(title="Drywall finishing", status=TaskStatus.TODO, project_id=project.canonical_id)
    session.add_all([t1, t2, t3])
    session.commit()
    return [t1, t2, t3]


def _mock_done(task_index: int = 0) -> MockFieldNoteExtractor:
    return MockFieldNoteExtractor(
        responses=[
            {
                "signals": [
                    {
                        "classification": "task_done",
                        "quoted_excerpt": "finished the silicone",
                        "task_index": task_index,
                        "proposed_status": "Done",
                        "proposed_start_date": None,
                        "proposed_end_date": None,
                        "new_task_title": None,
                        "workers": "Marco",
                        "hours_worked": 3.0,
                        "confidence": 0.95,
                    }
                ]
            }
        ]
    )


def _mock_multi() -> MockFieldNoteExtractor:
    """Two signals: task_progress + blocker.

    Note: "still working on the door, glass door still sticking"
    After Strategy-C rendering, t2 ("Adjust glass door") scores highest via
    keyword overlap ("door", "glass") and lands at index 0 in the UPCOMING
    group.  Both signals reference task_index=0 (t2).
    """
    return MockFieldNoteExtractor(
        responses=[
            {
                "signals": [
                    {
                        "classification": "task_progress",
                        "quoted_excerpt": "still working on the door",
                        "task_index": 0,
                        "proposed_status": "In Progress",
                        "proposed_start_date": None,
                        "proposed_end_date": None,
                        "new_task_title": None,
                        "workers": None,
                        "hours_worked": None,
                        "confidence": 0.80,
                    },
                    {
                        "classification": "blocker",
                        "quoted_excerpt": "glass door still sticking",
                        "task_index": 0,
                        "proposed_status": "Blocked",
                        "proposed_start_date": None,
                        "proposed_end_date": None,
                        "new_task_title": None,
                        "workers": None,
                        "hours_worked": None,
                        "confidence": 0.90,
                    },
                ]
            }
        ]
    )


# ---------------------------------------------------------------------------
# Model layer
# ---------------------------------------------------------------------------


class TestFieldNoteModel:
    def test_create_and_query(self, session, project, tasks):
        fn = FieldNote(
            raw_text="finished the silicone",
            received_at=datetime.utcnow(),
            channel=DBNoteChannel.CLI,
            project_id=project.canonical_id,
            classification=DBNoteClass.TASK_DONE,
            quoted_excerpt="finished the silicone",
            matched_task_id=tasks[0].canonical_id,
            confidence=0.95,
        )
        session.add(fn)
        session.commit()

        fetched = session.query(FieldNote).filter_by(canonical_id=fn.canonical_id).one()
        assert fetched.raw_text == "finished the silicone"
        assert fetched.classification == DBNoteClass.TASK_DONE
        assert fetched.matched_task_id == tasks[0].canonical_id
        assert fetched.project_id == project.canonical_id

    def test_nullable_fields(self, session, project):
        fn = FieldNote(
            raw_text="something happened",
            received_at=datetime.utcnow(),
            channel=DBNoteChannel.WEB,
            project_id=project.canonical_id,
        )
        session.add(fn)
        session.commit()
        fetched = session.query(FieldNote).filter_by(canonical_id=fn.canonical_id).one()
        assert fetched.classification is None
        assert fetched.matched_task_id is None
        assert fetched.sender_ref is None
        assert fetched.hours_worked is None


# ---------------------------------------------------------------------------
# ingest_field_note -- happy paths
# ---------------------------------------------------------------------------


class TestIngestHappyPath:
    def test_task_done_creates_field_note_and_proposal(self, session, project, tasks):
        ex = _mock_done(task_index=0)
        batch = ingest_field_note(
            session,
            ex,
            project.canonical_id,
            "finished the silicone in the bathroom",
        )
        session.commit()

        assert batch.skipped_reason is None
        assert len(batch.field_notes) == 1
        fn = batch.field_notes[0]
        assert fn.classification == NoteClass.TASK_DONE
        assert fn.matched_task_id == tasks[0].canonical_id
        assert "finished the silicone" in fn.quoted_excerpt
        assert fn.workers == "Marco"
        assert float(fn.hours_worked) == 3.0

        assert len(batch.proposals) == 1
        p = batch.proposals[0]
        assert p.field_name == "task_status"
        assert p.entity_type == "Task"
        assert p.entity_id == tasks[0].canonical_id
        assert p.status == ProposalStatus.PENDING
        pv = json.loads(p.proposed_value)
        assert pv["status"] == "DONE"
        assert pv["monday_label"] == "Done"

    def test_new_task_creates_advisory_proposal(self, session, project, tasks):
        ex = MockFieldNoteExtractor(
            responses=[
                {
                    "signals": [
                        {
                            "classification": "new_task",
                            "quoted_excerpt": "need to replace the threshold",
                            "task_index": None,
                            "proposed_status": None,
                            "proposed_start_date": None,
                            "proposed_end_date": None,
                            "new_task_title": "Replace door threshold",
                            "workers": None,
                            "hours_worked": None,
                            "confidence": 0.85,
                        }
                    ]
                }
            ]
        )
        batch = ingest_field_note(
            session, ex, project.canonical_id, "need to replace the threshold"
        )
        session.commit()

        assert len(batch.field_notes) == 1
        assert len(batch.proposals) == 1
        p = batch.proposals[0]
        assert p.field_name == "new_task"
        assert p.entity_type == "Project"
        pv = json.loads(p.proposed_value)
        assert pv["title"] == "Replace door threshold"

    def test_scope_change_creates_advisory_proposal(self, session, project, tasks):
        ex = MockFieldNoteExtractor(
            responses=[
                {
                    "signals": [
                        {
                            "classification": "scope_change",
                            "quoted_excerpt": "owner wants an extra coat of paint",
                            "task_index": None,
                            "proposed_status": None,
                            "proposed_start_date": None,
                            "proposed_end_date": None,
                            "new_task_title": None,
                            "workers": None,
                            "hours_worked": None,
                            "confidence": 0.75,
                        }
                    ]
                }
            ]
        )
        batch = ingest_field_note(session, ex, project.canonical_id, "owner wants extra paint")
        session.commit()

        assert len(batch.proposals) == 1
        p = batch.proposals[0]
        assert p.field_name == "scope_change"
        assert p.entity_type == "Project"

    def test_other_creates_field_note_but_no_proposal(self, session, project, tasks):
        ex = MockFieldNoteExtractor(
            responses=[
                {
                    "signals": [
                        {
                            "classification": "other",
                            "quoted_excerpt": "everything looks fine today",
                            "task_index": None,
                            "proposed_status": None,
                            "proposed_start_date": None,
                            "proposed_end_date": None,
                            "new_task_title": None,
                            "workers": None,
                            "hours_worked": None,
                            "confidence": 0.60,
                        }
                    ]
                }
            ]
        )
        batch = ingest_field_note(session, ex, project.canonical_id, "looks fine")
        session.commit()

        assert len(batch.field_notes) == 1
        assert len(batch.proposals) == 0

    def test_multi_signal_note(self, session, project, tasks):
        ex = _mock_multi()
        batch = ingest_field_note(
            session,
            ex,
            project.canonical_id,
            "still working on the door, glass door still sticking",
        )
        session.commit()

        assert len(batch.field_notes) == 2
        assert len(batch.proposals) == 2

        classes = {fn.classification for fn in batch.field_notes}
        assert NoteClass.TASK_PROGRESS in classes
        assert NoteClass.BLOCKER in classes

    def test_date_shift_with_dates_creates_timeline_proposal(self, session, project, tasks):
        # "drywall pushed to next week": t3 ("Drywall finishing") wins on
        # keyword overlap ("drywall") and is placed at index 0 in UPCOMING.
        ex = MockFieldNoteExtractor(
            responses=[
                {
                    "signals": [
                        {
                            "classification": "date_shift",
                            "quoted_excerpt": "drywall pushed to next week",
                            "task_index": 0,
                            "proposed_status": None,
                            "proposed_start_date": "2026-06-20",
                            "proposed_end_date": "2026-06-27",
                            "new_task_title": None,
                            "workers": None,
                            "hours_worked": None,
                            "confidence": 0.80,
                        }
                    ]
                }
            ]
        )
        batch = ingest_field_note(session, ex, project.canonical_id, "drywall pushed to next week")
        session.commit()

        assert len(batch.proposals) == 1
        p = batch.proposals[0]
        assert p.field_name == "timeline"
        pv = json.loads(p.proposed_value)
        assert pv["start_date"] == "2026-06-20"
        assert pv["end_date"] == "2026-06-27"


# ---------------------------------------------------------------------------
# ingest_field_note -- conservative / error cases
# ---------------------------------------------------------------------------


class TestIngestConservative:
    def test_empty_note_skipped(self, session, project, tasks):
        ex = MockFieldNoteExtractor()
        batch = ingest_field_note(session, ex, project.canonical_id, "   ")
        assert batch.skipped_reason is not None
        assert len(batch.field_notes) == 0
        assert len(ex.calls) == 0

    def test_no_signals_returned_skipped(self, session, project, tasks):
        ex = MockFieldNoteExtractor(responses=[{"signals": []}])
        batch = ingest_field_note(session, ex, project.canonical_id, "something")
        assert batch.skipped_reason is not None

    def test_missing_quoted_excerpt_rejected(self, session, project, tasks):
        ex = MockFieldNoteExtractor(
            responses=[
                {
                    "signals": [
                        {
                            "classification": "task_done",
                            "quoted_excerpt": "",
                            "task_index": 0,
                            "proposed_status": "Done",
                            "proposed_start_date": None,
                            "proposed_end_date": None,
                            "new_task_title": None,
                            "workers": None,
                            "hours_worked": None,
                            "confidence": 0.9,
                        }
                    ]
                }
            ]
        )
        batch = ingest_field_note(session, ex, project.canonical_id, "finished sealant")
        session.commit()

        assert len(batch.field_notes) == 0
        assert any("A6" in e for e in batch.errors)

    def test_declined_match_status_signal_no_proposal(self, session, project, tasks):
        ex = MockFieldNoteExtractor(
            responses=[
                {
                    "signals": [
                        {
                            "classification": "task_done",
                            "quoted_excerpt": "done with something",
                            "task_index": None,
                            "proposed_status": "Done",
                            "proposed_start_date": None,
                            "proposed_end_date": None,
                            "new_task_title": None,
                            "workers": None,
                            "hours_worked": None,
                            "confidence": 0.5,
                        }
                    ]
                }
            ]
        )
        batch = ingest_field_note(session, ex, project.canonical_id, "done with something")
        session.commit()

        assert len(batch.field_notes) == 1
        assert len(batch.proposals) == 0
        assert any("no matched task" in e for e in batch.errors)

    def test_date_shift_without_dates_no_proposal(self, session, project, tasks):
        ex = MockFieldNoteExtractor(
            responses=[
                {
                    "signals": [
                        {
                            "classification": "date_shift",
                            "quoted_excerpt": "pushed to later",
                            "task_index": 0,
                            "proposed_status": None,
                            "proposed_start_date": None,
                            "proposed_end_date": None,
                            "new_task_title": None,
                            "workers": None,
                            "hours_worked": None,
                            "confidence": 0.6,
                        }
                    ]
                }
            ]
        )
        batch = ingest_field_note(session, ex, project.canonical_id, "pushed to later")
        session.commit()

        assert len(batch.field_notes) == 1
        assert len(batch.proposals) == 0
        assert any("no parseable dates" in e for e in batch.errors)

    def test_project_not_found(self, session):
        ex = MockFieldNoteExtractor()
        fake_id = str(uuid.uuid4())
        batch = ingest_field_note(session, ex, fake_id, "something happened")
        assert batch.skipped_reason is not None
        assert "not found" in batch.skipped_reason

    def test_out_of_range_task_index_declined(self, session, project, tasks):
        ex = MockFieldNoteExtractor(
            responses=[
                {
                    "signals": [
                        {
                            "classification": "task_done",
                            "quoted_excerpt": "finished something",
                            "task_index": 999,
                            "proposed_status": "Done",
                            "proposed_start_date": None,
                            "proposed_end_date": None,
                            "new_task_title": None,
                            "workers": None,
                            "hours_worked": None,
                            "confidence": 0.9,
                        }
                    ]
                }
            ]
        )
        batch = ingest_field_note(session, ex, project.canonical_id, "finished something")
        session.commit()

        assert len(batch.field_notes) == 1
        assert len(batch.proposals) == 0
        assert any("out of range" in e for e in batch.errors)


# ---------------------------------------------------------------------------
# Proposal supersede: a new task_status proposal for the same task supersedes
# prior PENDING ones.
# ---------------------------------------------------------------------------


class TestSupersede:
    def test_new_status_proposal_supersedes_prior(self, session, project, tasks):
        ex1 = _mock_done(task_index=0)
        ingest_field_note(session, ex1, project.canonical_id, "first note")
        session.commit()

        # Second note for the same task -- should supersede the first.
        ex2 = MockFieldNoteExtractor(
            responses=[
                {
                    "signals": [
                        {
                            "classification": "blocker",
                            "quoted_excerpt": "actually stuck now",
                            "task_index": 0,
                            "proposed_status": "Stuck",
                            "proposed_start_date": None,
                            "proposed_end_date": None,
                            "new_task_title": None,
                            "workers": None,
                            "hours_worked": None,
                            "confidence": 0.88,
                        }
                    ]
                }
            ]
        )
        batch2 = ingest_field_note(session, ex2, project.canonical_id, "second note")
        session.commit()

        pending = (
            session.query(Proposal)
            .filter_by(
                entity_id=tasks[0].canonical_id,
                field_name="task_status",
                status=ProposalStatus.PENDING,
            )
            .all()
        )
        assert len(pending) == 1
        assert json.loads(pending[0].proposed_value)["monday_label"] == "Stuck"

        superseded = (
            session.query(Proposal)
            .filter_by(
                entity_id=tasks[0].canonical_id,
                field_name="task_status",
                status=ProposalStatus.SUPERSEDED,
            )
            .all()
        )
        assert len(superseded) == 1


# ---------------------------------------------------------------------------
# accept_proposal -- task_status branch
# ---------------------------------------------------------------------------


class FakeWriteback:
    """Minimal sync_back fake for tests."""

    def __init__(self, return_value: bool = True) -> None:
        self.calls: list[tuple] = []
        self._rv = return_value

    def sync_back(self, entity, field_updates):
        self.calls.append((entity, field_updates))
        return self._rv


def _make_task_status_proposal(
    session, task, monday_label="Done", canonical_status="DONE"
) -> Proposal:
    fn = FieldNote(
        raw_text="finished sealant",
        received_at=datetime.utcnow(),
        channel=DBNoteChannel.CLI,
        project_id=task.project_id,
        classification=DBNoteClass.TASK_DONE,
        quoted_excerpt="finished sealant",
    )
    session.add(fn)
    session.flush()
    p = Proposal(
        entity_type="Task",
        entity_id=task.canonical_id,
        field_name="task_status",
        proposed_value=json.dumps({"status": canonical_status, "monday_label": monday_label}),
        confidence=0.95,
        source_doc_ids=json.dumps([str(fn.canonical_id)]),
        prompt_version="field-note-v1",
        status=ProposalStatus.PENDING,
    )
    session.add(p)
    session.commit()
    return p


class TestAcceptTaskStatus:
    def test_task_status_in_acceptable_fields(self):
        assert "task_status" in _ACCEPTABLE_FIELDS

    def test_dry_run_preview(self, session, project, tasks):
        p = _make_task_status_proposal(session, tasks[0])
        result = accept_proposal(session, p.canonical_id, dry_run=True)
        assert result["ok"] is True
        assert result["dry_run"] is True
        assert "would_write" in result
        assert result["would_write"] == {"status": {"label": "Done"}}

    def test_real_accept_mirrors_status(self, session, project, tasks):
        p = _make_task_status_proposal(
            session, tasks[0], monday_label="Done", canonical_status="DONE"
        )
        wb = FakeWriteback(return_value=True)
        result = accept_proposal(session, p.canonical_id, writeback=wb, decided_by="test")
        assert result["ok"] is True
        assert result["new_status"] == "ACCEPTED"
        session.refresh(tasks[0])
        assert tasks[0].status == TaskStatus.DONE
        assert tasks[0].monday_status_label == "Done"

    def test_accept_blocked(self, session, project, tasks):
        p = _make_task_status_proposal(
            session, tasks[1], monday_label="Blocked", canonical_status="BLOCKED"
        )
        wb = FakeWriteback(return_value=True)
        result = accept_proposal(session, p.canonical_id, writeback=wb)
        assert result["ok"] is True
        session.refresh(tasks[1])
        assert tasks[1].status == TaskStatus.BLOCKED

    def test_accept_writeback_false_leaves_pending(self, session, project, tasks):
        p = _make_task_status_proposal(session, tasks[0])
        wb = FakeWriteback(return_value=False)
        result = accept_proposal(session, p.canonical_id, writeback=wb)
        assert result["ok"] is False
        session.refresh(p)
        assert p.status == ProposalStatus.PENDING

    def test_unknown_canonical_status_rejected(self, session, project, tasks):
        fn = FieldNote(
            raw_text="x",
            received_at=datetime.utcnow(),
            channel=DBNoteChannel.CLI,
            project_id=tasks[0].project_id,
        )
        session.add(fn)
        session.flush()
        bad_proposal = Proposal(
            entity_type="Task",
            entity_id=tasks[0].canonical_id,
            field_name="task_status",
            proposed_value=json.dumps({"status": "NOT_A_STATUS", "monday_label": "Bad"}),
            confidence=0.5,
            prompt_version="field-note-v1",
            status=ProposalStatus.PENDING,
        )
        session.add(bad_proposal)
        session.commit()
        result = accept_proposal(session, bad_proposal.canonical_id, dry_run=True)
        assert result["ok"] is False
        assert "unknown canonical status" in result["error"]


# ---------------------------------------------------------------------------
# Reasoning field + richer task context (Win 3 improvements)
# ---------------------------------------------------------------------------


class TestReasoningField:
    """reasoning in proposed_value propagated from extractor response."""

    def test_reasoning_stored_in_task_status_proposal(self, session, project, tasks):
        ext = MockFieldNoteExtractor(
            responses=[
                {
                    "signals": [
                        {
                            "classification": "task_done",
                            "quoted_excerpt": "silicone done",
                            "task_index": 0,
                            "proposed_status": "Done",
                            "proposed_start_date": None,
                            "proposed_end_date": None,
                            "new_task_title": None,
                            "workers": None,
                            "hours_worked": None,
                            "confidence": 0.9,
                            "reasoning": "Note says silicone done, matches task 0.",
                        }
                    ]
                }
            ]
        )
        batch = ingest_field_note(session, ext, project.canonical_id, "silicone done")
        assert batch.proposal_count == 1
        pv = json.loads(batch.proposals[0].proposed_value)
        assert pv.get("reasoning") == "Note says silicone done, matches task 0."

    def test_no_reasoning_omitted_from_proposed_value(self, session, project, tasks):
        """Extractor without reasoning key: proposal created without reasoning key."""
        batch = ingest_field_note(
            session, _mock_done(0), project.canonical_id, "finished the silicone"
        )
        assert batch.proposal_count == 1
        pv = json.loads(batch.proposals[0].proposed_value)
        assert "reasoning" not in pv

    def test_reasoning_in_new_task_proposal(self, session, project, tasks):
        ext = MockFieldNoteExtractor(
            responses=[
                {
                    "signals": [
                        {
                            "classification": "new_task",
                            "quoted_excerpt": "need to paint the door",
                            "task_index": None,
                            "proposed_status": None,
                            "proposed_start_date": None,
                            "proposed_end_date": None,
                            "new_task_title": "Paint the door",
                            "workers": None,
                            "hours_worked": None,
                            "confidence": 0.75,
                            "reasoning": "Painting not in existing task list; new_task is correct.",
                        }
                    ]
                }
            ]
        )
        batch = ingest_field_note(session, ext, project.canonical_id, "need to paint the door")
        assert batch.proposal_count == 1
        pv = json.loads(batch.proposals[0].proposed_value)
        assert pv.get("reasoning") == "Painting not in existing task list; new_task is correct."


class TestTaskContextLine:
    """_task_context_line produces richer lines with status + dates."""

    def test_includes_status_label_and_dates(self, session, project):
        from datetime import date as _date

        from project_db.ai.field_note_extraction import _task_context_line

        t = Task(
            title="Pour concrete",
            status=TaskStatus.TODO,
            monday_status_label="Working on it",
            start_date=_date(2026, 6, 1),
            end_date=_date(2026, 6, 15),
            project_id=project.canonical_id,
        )
        session.add(t)
        session.flush()
        line = _task_context_line(t)
        assert "Pour concrete" in line
        assert "Working on it" in line
        assert "2026-06-01" in line
        assert "2026-06-15" in line

    def test_no_dates_omitted(self, session, project):
        from project_db.ai.field_note_extraction import _task_context_line

        t = Task(
            title="Paint walls",
            status=TaskStatus.TODO,
            project_id=project.canonical_id,
        )
        session.add(t)
        session.flush()
        line = _task_context_line(t)
        assert "Paint walls" in line
        assert "start:" not in line
        assert "end:" not in line


class TestFieldNoteRag:
    """Field notes use the SAME RAG evidence base as generate-proposals."""

    def test_rag_excerpts_threaded_to_extractor(self, session, project, tasks, monkeypatch):
        """When an embedding provider is supplied, retrieved contract passages
        are passed to the extractor as context_excerpts."""
        import project_db.ai.proposals as proposals_mod

        monkeypatch.setattr(
            proposals_mod,
            "_retrieve_proposal_chunks",
            lambda *a, **k: [
                {
                    "text": "Contractor shall install custom shower glass in Unit 05.",
                    "document_name": "SOW.pdf",
                },
            ],
        )
        ex = MockFieldNoteExtractor(responses=[{"signals": []}])
        batch = ingest_field_note(
            session,
            ex,
            project.canonical_id,
            "the glass is installed",
            embedding_provider=object(),  # non-None triggers RAG
        )
        assert batch.rag_chunks_used == 1
        assert ex.context_calls, "extractor should have been called"
        assert any("custom shower glass" in e for e in ex.context_calls[0])

    def test_no_embedding_provider_means_no_rag(self, session, project, tasks):
        """No embedding provider -> byte-identical pre-RAG behaviour (no excerpts)."""
        ex = MockFieldNoteExtractor(responses=[{"signals": []}])
        batch = ingest_field_note(
            session,
            ex,
            project.canonical_id,
            "the glass is installed",
        )
        assert batch.rag_chunks_used == 0
        assert ex.context_calls == [[]]

    def test_rag_retrieval_failure_is_swallowed(self, session, project, tasks, monkeypatch):
        """A retrieval hiccup must not break ingest -- falls back to no excerpts."""
        import project_db.ai.proposals as proposals_mod

        def boom(*a, **k):
            raise RuntimeError("vector store down")

        monkeypatch.setattr(proposals_mod, "_retrieve_proposal_chunks", boom)

        ex = MockFieldNoteExtractor(responses=[{"signals": []}])
        batch = ingest_field_note(
            session,
            ex,
            project.canonical_id,
            "the glass is installed",
            embedding_provider=object(),
        )
        assert batch.rag_chunks_used == 0
        assert ex.context_calls == [[]]


class TestEmailTimestamp:
    """Email sent timestamp is threaded into the extractor + FieldNote.received_at."""

    def test_timestamp_passed_to_extractor(self, session, project, tasks):
        """received_at flows to note_timestamp on the extractor call so the LLM
        can resolve relative date references ('yesterday', 'next Friday')."""
        email_ts = datetime(2026, 6, 13, 9, 30, 0)
        ex = MockFieldNoteExtractor(responses=[{"signals": []}])
        ingest_field_note(
            session,
            ex,
            project.canonical_id,
            "finished the silicone",
            received_at=email_ts,
        )
        assert ex.timestamp_calls == [email_ts]

    def test_timestamp_sets_field_note_received_at(self, session, project, tasks):
        """FieldNote.received_at is the email's sent time, not ingest utcnow()."""
        email_ts = datetime(2026, 6, 13, 9, 30, 0)
        ex = _mock_done(task_index=0)
        batch = ingest_field_note(
            session,
            ex,
            project.canonical_id,
            "finished the silicone",
            received_at=email_ts,
        )
        session.commit()
        assert len(batch.field_notes) == 1
        assert batch.field_notes[0].received_at == email_ts

    def test_no_timestamp_falls_back_to_utcnow(self, session, project, tasks):
        """CLI path (no received_at) works; FieldNote.received_at is close to now."""
        before = datetime.utcnow()
        ex = _mock_done(task_index=0)
        batch = ingest_field_note(
            session,
            ex,
            project.canonical_id,
            "finished the silicone",
        )
        after = datetime.utcnow()
        session.commit()
        assert len(batch.field_notes) == 1
        fn_ts = batch.field_notes[0].received_at
        assert before <= fn_ts <= after

    def test_no_timestamp_extractor_still_receives_a_datetime(self, session, project, tasks):
        """Without received_at the extractor gets the fallback utcnow (not None)
        so the NOTE SENT block still appears in every prompt."""
        before = datetime.utcnow()
        ex = MockFieldNoteExtractor(responses=[{"signals": []}])
        ingest_field_note(session, ex, project.canonical_id, "something happened")
        after = datetime.utcnow()
        assert len(ex.timestamp_calls) == 1
        ts = ex.timestamp_calls[0]
        assert ts is not None
        assert before <= ts <= after


class TestNoteTimestampRendering:
    """_render_note_timestamp produces the expected header format."""

    def test_format_includes_day_name_and_dates(self):
        from project_db.ai.field_note_extraction import _render_note_timestamp

        ts = datetime(2026, 6, 13, 9, 30, 0)  # a Saturday
        block = _render_note_timestamp(ts)
        assert "NOTE SENT: 2026-06-13 09:30 UTC" in block
        assert "Saturday" in block
        assert "CURRENT DATE:" in block

    def test_format_ends_with_blank_line(self):
        """Block ends with double newline so it's cleanly separated from task list."""
        from project_db.ai.field_note_extraction import _render_note_timestamp

        block = _render_note_timestamp(datetime(2026, 6, 15, 8, 0, 0))
        assert block.endswith("\n\n")


class TestFieldNoteSubtaskWindow:
    """A date_shift on a SUBTASK is bounded loosely by its parent's window."""

    def _parent_and_subtask(self, session, project):
        parent = Task(
            title="Phase 1",
            status=TaskStatus.TODO,
            project_id=project.canonical_id,
            is_subitem=False,
            start_date=date(2026, 7, 1),
            end_date=date(2026, 7, 31),
        )
        session.add(parent)
        session.commit()
        sub = Task(
            title="Sub A",
            status=TaskStatus.TODO,
            project_id=project.canonical_id,
            is_subitem=True,
            parent_task_id=parent.canonical_id,
        )
        session.add(sub)
        session.commit()
        return parent, sub  # parent=index 0, subtask=index 1

    def _date_shift_mock(self, task_index, start, end):
        return MockFieldNoteExtractor(
            responses=[
                {
                    "signals": [
                        {
                            "classification": "date_shift",
                            "quoted_excerpt": "pushed to next month",
                            "task_index": task_index,
                            "proposed_status": None,
                            "proposed_start_date": start,
                            "proposed_end_date": end,
                            "new_task_title": None,
                            "workers": None,
                            "hours_worked": None,
                            "confidence": 0.8,
                            "reasoning": "note says so",
                        }
                    ]
                }
            ]
        )

    def test_date_shift_outside_parent_window_warns(self, session, project):
        self._parent_and_subtask(session, project)
        # "Sub A pushed to August": "Sub A" wins keyword overlap ("sub") -> index 0.
        # Parent "Phase 1" has temporal boost (dated Jul 1-31) but zero semantic -> index 1.
        ex = self._date_shift_mock(0, "2026-08-10", "2026-08-20")  # after Jul 31
        batch = ingest_field_note(session, ex, project.canonical_id, "Sub A pushed to August")
        # Proposal still created (A1: advise, don't block) but flagged.
        assert len(batch.proposals) == 1
        assert any("outside parent" in w for w in batch.warnings)

    def test_date_shift_within_parent_window_no_warning(self, session, project):
        self._parent_and_subtask(session, project)
        # "Sub A mid-July": same ordering -- sub at index 0.
        ex = self._date_shift_mock(0, "2026-07-10", "2026-07-20")  # within Jul 1-31
        batch = ingest_field_note(session, ex, project.canonical_id, "Sub A mid-July")
        assert len(batch.proposals) == 1
        assert not any("outside parent" in w for w in batch.warnings)


# ---------------------------------------------------------------------------
# Win 3 -- Photos through the same pipe
# ---------------------------------------------------------------------------


class TestPhotoIngestion:
    """image_paths param threads from ingest_field_note to the extractor (Win 3)."""

    def test_image_paths_passed_to_extractor(self, session, project, tasks):
        ex = MockFieldNoteExtractor(responses=[{"signals": []}])
        ingest_field_note(
            session,
            ex,
            project.canonical_id,
            "see attached photo",
            image_paths=["/fake/site_photo.jpg"],
        )
        assert ex.image_calls == [["/fake/site_photo.jpg"]]

    def test_multiple_image_paths_all_passed(self, session, project, tasks):
        ex = MockFieldNoteExtractor(responses=[{"signals": []}])
        paths = ["/fake/a.jpg", "/fake/b.png", "/fake/c.jpeg"]
        ingest_field_note(
            session,
            ex,
            project.canonical_id,
            "three photos",
            image_paths=paths,
        )
        assert ex.image_calls == [paths]

    def test_photo_only_note_proceeds_to_extractor(self, session, project, tasks):
        """empty text + image_paths -> extractor is called (not short-circuited)."""
        ex = MockFieldNoteExtractor(responses=[{"signals": []}])
        batch = ingest_field_note(
            session,
            ex,
            project.canonical_id,
            "",  # no text body
            image_paths=["/fake/photo.jpg"],
        )
        # extractor was called -- not skipped
        assert len(ex.calls) == 1
        assert batch.skipped_reason != "empty note"

    def test_empty_text_no_images_still_skips(self, session, project, tasks):
        """empty text with no images is still rejected (existing behaviour)."""
        ex = MockFieldNoteExtractor(responses=[{"signals": []}])
        batch = ingest_field_note(
            session,
            ex,
            project.canonical_id,
            "   ",
            image_paths=None,
        )
        assert batch.skipped_reason == "empty note"
        assert ex.calls == []

    def test_no_image_paths_extractor_gets_empty_list(self, session, project, tasks):
        """When image_paths is None, extractor.image_calls entry is an empty list."""
        ex = MockFieldNoteExtractor(responses=[{"signals": []}])
        ingest_field_note(session, ex, project.canonical_id, "some text")
        assert ex.image_calls == [[]]


class TestLoadImageB64:
    """Unit tests for the _load_image_b64 helper."""

    def test_unsupported_extension_returns_none(self):
        assert _load_image_b64("/tmp/document.pdf") is None

    def test_txt_extension_returns_none(self):
        assert _load_image_b64("/tmp/note.txt") is None

    def test_valid_jpeg_returns_data_url(self, tmp_path):
        img = tmp_path / "photo.jpg"
        img.write_bytes(b"\xff\xd8\xff\xe0" + b"\x00" * 10)  # minimal JPEG header bytes
        result = _load_image_b64(str(img))
        assert result is not None
        assert result.startswith("data:image/jpeg;base64,")

    def test_valid_png_returns_data_url(self, tmp_path):
        img = tmp_path / "shot.png"
        img.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 4)
        result = _load_image_b64(str(img))
        assert result is not None
        assert result.startswith("data:image/png;base64,")

    def test_size_too_large_returns_none(self, tmp_path, monkeypatch):
        img = tmp_path / "big.jpg"
        img.write_bytes(b"\xff\xd8\xff")
        import os

        monkeypatch.setattr(os.path, "getsize", lambda _: 11 * 1024 * 1024)
        assert _load_image_b64(str(img)) is None

    def test_missing_file_returns_none(self):
        assert _load_image_b64("/nonexistent/path/photo.jpg") is None

    def test_image_exts_constant_covers_common_formats(self):
        for ext in (".jpg", ".jpeg", ".png", ".webp", ".gif"):
            assert ext in _IMAGE_EXTS


# ---------------------------------------------------------------------------
# Strategy C -- _render_task_block: status grouping + scoring
# ---------------------------------------------------------------------------


class TestRenderTaskBlock:
    """Unit tests for the composite-score task block renderer."""

    def _make_task(
        self, title, status_label, *, is_subitem=False, parent_id=None, start=None, end=None
    ):
        """Build a minimal Task-like object without hitting the DB."""
        from unittest.mock import MagicMock

        t = MagicMock()
        t.title = title
        t.monday_status_label = status_label
        t.status = None
        t.is_subitem = is_subitem
        t.parent_task_id = parent_id
        t.canonical_id = uuid.uuid4()
        t.start_date = start
        t.end_date = end
        t.due_date = None  # prevent MagicMock from returning a truthy mock
        t.created_at = datetime.utcnow()
        return t

    def test_active_tasks_appear_before_upcoming_and_done(self):
        from datetime import date as _d

        active = self._make_task("Framing", "Working on it")
        upcoming = self._make_task("Paint", "Future steps")
        done = self._make_task("Demo", "Done")

        rendered, _ids = _render_task_block(
            [done, upcoming, active], "framing work", today=_d(2026, 6, 15)
        )
        lines = rendered.splitlines()
        active_hdr = next(i for i, line in enumerate(lines) if "ACTIVE" in line)
        upcoming_hdr = next(i for i, line in enumerate(lines) if "UPCOMING" in line)
        done_hdr = next(i for i, line in enumerate(lines) if "COMPLETED" in line)
        assert active_hdr < upcoming_hdr < done_hdr

    def test_indices_are_contiguous_and_match_task_ids(self):
        from datetime import date as _d

        tasks = [
            self._make_task("Task A", "Working on it"),
            self._make_task("Task B", "Future steps"),
            self._make_task("Task C", "Done"),
        ]
        rendered, ids = _render_task_block(tasks, "task note", today=_d(2026, 6, 15))
        assert len(ids) == 3
        # Every [N] in rendered maps to ids[N]
        import re as _re

        found_indices = [int(m) for m in _re.findall(r"\[(\d+)\]", rendered)]
        assert found_indices == list(range(len(ids)))

    def test_subitem_includes_parent_annotation(self, session, project):
        from datetime import date as _d

        parent = Task(
            title="Wall finishes",
            status=TaskStatus.TODO,
            monday_status_label="Working on it",
            project_id=project.canonical_id,
            is_subitem=False,
        )
        session.add(parent)
        session.flush()
        sub = Task(
            title="Drywall repair",
            status=TaskStatus.TODO,
            monday_status_label="Working on it",
            project_id=project.canonical_id,
            is_subitem=True,
            parent_task_id=parent.canonical_id,
        )
        session.add(sub)
        session.flush()

        rendered, _ids = _render_task_block([parent, sub], "drywall", today=_d(2026, 6, 15))
        assert "parent: Wall finishes" in rendered

    def test_done_section_trimmed_to_done_trim_k(self):
        from datetime import date as _d

        done_tasks = [self._make_task(f"Done task {i}", "Done") for i in range(_DONE_TRIM_K + 5)]
        rendered, ids = _render_task_block(done_tasks, "something", today=_d(2026, 6, 15))
        assert len(ids) == _DONE_TRIM_K
        assert f"top {_DONE_TRIM_K} of {_DONE_TRIM_K + 5}" in rendered

    def test_done_not_trimmed_when_under_limit(self):
        from datetime import date as _d

        done_tasks = [self._make_task(f"Done {i}", "Done") for i in range(5)]
        rendered, ids = _render_task_block(done_tasks, "something", today=_d(2026, 6, 15))
        assert len(ids) == 5
        assert "top" not in rendered

    def test_semantic_score_raises_matching_task(self):
        from datetime import date as _d

        # "drywall" in note: drywall task should score higher than glass task
        drywall = self._make_task("Drywall finishing", "Future steps")
        glass = self._make_task("Adjust glass door", "Future steps")
        rendered, _ids = _render_task_block(
            [glass, drywall], "drywall repair needed", today=_d(2026, 6, 15)
        )
        # drywall task should be first in UPCOMING (index 0)
        drywall_line = next(line for line in rendered.splitlines() if "Drywall" in line)
        assert "[0]" in drywall_line

    def test_temporal_proximity_boosts_within_group(self):
        from datetime import date as _d

        today = _d(2026, 6, 15)
        near = self._make_task(
            "Near task", "Future steps", start=_d(2026, 6, 20), end=_d(2026, 6, 25)
        )
        far = self._make_task(
            "Far task", "Future steps", start=_d(2026, 12, 1), end=_d(2026, 12, 31)
        )
        undated = self._make_task("Undated task", "Future steps")
        rendered, _ids = _render_task_block([far, undated, near], "general update", today=today)
        # near task wins temporal (1.0), undated is neutral (0.5), far is low (0.15)
        near_line = next(line for line in rendered.splitlines() if "Near task" in line)
        assert "[0]" in near_line

    def test_undated_task_not_buried_below_far_future(self):
        """Undated (0.5 temporal) beats far-future (0.15 temporal) in the ranking."""
        from datetime import date as _d

        today = _d(2026, 6, 15)
        far = self._make_task(
            "Far future task", "Future steps", start=_d(2027, 6, 1), end=_d(2027, 6, 30)
        )
        undated = self._make_task("Undated task", "Future steps")
        rendered, _ids = _render_task_block([far, undated], "general note", today=today)
        undated_line = next(line for line in rendered.splitlines() if "Undated" in line)
        assert "[0]" in undated_line

    def test_empty_task_list_returns_placeholder(self):
        rendered, ids = _render_task_block([], "anything")
        assert "no tasks" in rendered
        assert ids == []

    def test_block_calls_received_by_mock_extractor(self, session, project, tasks):
        """ingest_field_note passes the pre-rendered task_block to the extractor."""
        ex = MockFieldNoteExtractor(responses=[{"signals": []}])
        ingest_field_note(session, ex, project.canonical_id, "some note text")
        assert len(ex.block_calls) == 1
        assert ex.block_calls[0] is not None
        assert "-- UPCOMING" in ex.block_calls[0]


# ---------------------------------------------------------------------------
# parent_task_index resolution
# ---------------------------------------------------------------------------


class TestParentTaskIndex:
    """parent_task_index on new_task signals → parent_task_id in proposed_value."""

    def _new_task_signal(self, parent_task_index=None) -> dict:
        return {
            "classification": "new_task",
            "quoted_excerpt": "we also need to patch the ceiling",
            "task_index": None,
            "parent_task_index": parent_task_index,
            "proposed_status": None,
            "proposed_start_date": None,
            "proposed_end_date": None,
            "new_task_title": "Patch ceiling",
            "workers": None,
            "hours_worked": None,
            "confidence": 0.9,
        }

    def test_in_range_adds_parent_task_id(self, session, project):
        """parent_task_index=0 on a single-task project resolves to that task's UUID."""
        parent = Task(title="Drywall work", status=TaskStatus.TODO, project_id=project.canonical_id)
        session.add(parent)
        session.commit()

        ex = MockFieldNoteExtractor(
            responses=[{"signals": [self._new_task_signal(parent_task_index=0)]}]
        )
        batch = ingest_field_note(
            session, ex, project.canonical_id, "we also need to patch the ceiling"
        )
        session.commit()

        assert len(batch.proposals) == 1
        pv = json.loads(batch.proposals[0].proposed_value)
        assert "parent_task_id" in pv
        assert pv["parent_task_id"] == str(parent.canonical_id)

    def test_null_omits_parent_task_id(self, session, project):
        """parent_task_index=null → no parent_task_id key in proposed_value."""
        session.add(Task(title="Flooring", status=TaskStatus.TODO, project_id=project.canonical_id))
        session.commit()

        ex = MockFieldNoteExtractor(
            responses=[{"signals": [self._new_task_signal(parent_task_index=None)]}]
        )
        batch = ingest_field_note(
            session, ex, project.canonical_id, "we also need to patch the ceiling"
        )
        session.commit()

        assert len(batch.proposals) == 1
        pv = json.loads(batch.proposals[0].proposed_value)
        assert "parent_task_id" not in pv

    def test_out_of_range_silently_ignored(self, session, project):
        """Out-of-range parent_task_index is silently dropped (no error, no parent key)."""
        session.add(Task(title="Flooring", status=TaskStatus.TODO, project_id=project.canonical_id))
        session.commit()

        ex = MockFieldNoteExtractor(
            responses=[{"signals": [self._new_task_signal(parent_task_index=999)]}]
        )
        batch = ingest_field_note(session, ex, project.canonical_id, "patch the ceiling")
        session.commit()

        assert len(batch.proposals) == 1
        pv = json.loads(batch.proposals[0].proposed_value)
        assert "parent_task_id" not in pv
        assert len(batch.errors) == 0

    def test_negative_index_silently_ignored(self, session, project):
        """Negative parent_task_index is out-of-bounds and silently dropped."""
        session.add(Task(title="Flooring", status=TaskStatus.TODO, project_id=project.canonical_id))
        session.commit()

        ex = MockFieldNoteExtractor(
            responses=[{"signals": [self._new_task_signal(parent_task_index=-1)]}]
        )
        batch = ingest_field_note(session, ex, project.canonical_id, "patch the ceiling")
        session.commit()

        assert len(batch.proposals) == 1
        pv = json.loads(batch.proposals[0].proposed_value)
        assert "parent_task_id" not in pv

    def test_subitem_parent_climbs_to_top_level(self, session, project):
        """If the LLM picks a SUBITEM as parent (Monday forbids sub-subitems),
        the resolver climbs to the subitem's own parent so the new work still
        lands alongside the related step instead of failing at accept time."""
        top = Task(
            title="Drywall finishing",
            status=TaskStatus.IN_PROGRESS,
            project_id=project.canonical_id,
        )
        session.add(top)
        session.flush()
        sub = Task(
            title="Tape and mud",
            status=TaskStatus.IN_PROGRESS,
            project_id=project.canonical_id,
            is_subitem=True,
            parent_task_id=top.canonical_id,
        )
        session.add(sub)
        session.commit()

        # Tasks render Active-first; the subitem is index 1 (top is index 0).
        # Point the LLM at the SUBITEM and confirm it climbs to `top`.
        ex = MockFieldNoteExtractor(
            responses=[{"signals": [self._new_task_signal(parent_task_index=1)]}]
        )
        batch = ingest_field_note(session, ex, project.canonical_id, "patch the ceiling")
        session.commit()

        assert len(batch.proposals) == 1
        pv = json.loads(batch.proposals[0].proposed_value)
        assert pv["parent_task_id"] == str(top.canonical_id)

    def test_orphan_subitem_parent_falls_back_to_top_level(self, session, project):
        """A subitem with no resolvable parent (parent_task_id is None) cannot
        host a subitem; the resolver drops the parent rather than emit a
        proposal doomed to fail at accept time."""
        orphan_sub = Task(
            title="Loose subitem",
            status=TaskStatus.IN_PROGRESS,
            project_id=project.canonical_id,
            is_subitem=True,
            parent_task_id=None,
        )
        session.add(orphan_sub)
        session.commit()

        ex = MockFieldNoteExtractor(
            responses=[{"signals": [self._new_task_signal(parent_task_index=0)]}]
        )
        batch = ingest_field_note(session, ex, project.canonical_id, "patch the ceiling")
        session.commit()

        assert len(batch.proposals) == 1
        pv = json.loads(batch.proposals[0].proposed_value)
        assert "parent_task_id" not in pv
