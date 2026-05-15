"""Tests for Phase-1 schema additions: DocumentText and Proposal.

Phase 1 of ROADMAP.md introduces the storage layer for the AI loop:
  - DocumentText: extracted content sidecar (1:1 with Document)
  - Proposal:     LLM suggestions awaiting human review

These tests cover model contracts only -- extractors and LLM logic come
in later phases. If these break, the whole brain breaks.
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime

import pytest
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import IntegrityError

from project_db.db.base import Base
from project_db.db.models import (
    Client,
    Document,
    DocumentText,
    Project,
    Proposal,
    ProposalStatus,
)
from project_db.db.models.work import ProjectStatus


# ---------------------------------------------------------------------------
# DocumentText: 1:1 sidecar to Document
# ---------------------------------------------------------------------------


class TestDocumentText:
    def _make_doc(self, session, org, client_factory) -> Document:
        c = client_factory(name="C")
        p = Project(
            name="P", code="P1", status=ProjectStatus.ACTIVE,
            client_id=c.canonical_id,
        )
        session.add(p)
        session.commit()
        doc = Document(
            name="Contract.pdf",
            url="https://drive/x",
            mime_type="application/pdf",
            storage_ref="file42",
            project_id=p.canonical_id,
        )
        session.add(doc)
        session.commit()
        return doc

    def test_insert_basic_row(self, session, org, client_factory):
        doc = self._make_doc(session, org, client_factory)
        dt = DocumentText(
            document_id=doc.canonical_id,
            extracted_text="hello world",
            extraction_method="pdf-pymupdf",
            token_count=2,
        )
        session.add(dt)
        session.commit()

        loaded = session.query(DocumentText).filter_by(document_id=doc.canonical_id).one()
        assert loaded.extracted_text == "hello world"
        assert loaded.extraction_method == "pdf-pymupdf"
        assert loaded.token_count == 2
        assert isinstance(loaded.extracted_at, datetime)

    def test_extracted_at_defaults_to_now(self, session, org, client_factory):
        doc = self._make_doc(session, org, client_factory)
        before = datetime.utcnow()
        dt = DocumentText(
            document_id=doc.canonical_id,
            extracted_text="x",
            extraction_method="pdf-pymupdf",
        )
        session.add(dt)
        session.commit()
        assert dt.extracted_at >= before

    def test_skipped_row_has_no_text(self, session, org, client_factory):
        """A 'skipped' row records the decision without storing text."""
        doc = self._make_doc(session, org, client_factory)
        dt = DocumentText(
            document_id=doc.canonical_id,
            extracted_text=None,
            extraction_method="skipped-mime",
            token_count=None,
        )
        session.add(dt)
        session.commit()
        loaded = session.query(DocumentText).filter_by(document_id=doc.canonical_id).one()
        assert loaded.extracted_text is None
        assert loaded.extraction_method == "skipped-mime"

    def test_one_row_per_document(self, session, org, client_factory):
        """Document PK on the FK enforces 1:1."""
        doc = self._make_doc(session, org, client_factory)
        session.add(DocumentText(
            document_id=doc.canonical_id, extracted_text="a",
            extraction_method="pdf-pymupdf",
        ))
        session.commit()
        session.add(DocumentText(
            document_id=doc.canonical_id, extracted_text="b",
            extraction_method="pdf-pymupdf",
        ))
        with pytest.raises(IntegrityError):
            session.commit()

    def test_extraction_method_required(self, session, org, client_factory):
        doc = self._make_doc(session, org, client_factory)
        session.add(DocumentText(
            document_id=doc.canonical_id, extracted_text="x", extraction_method=None,
        ))
        with pytest.raises(IntegrityError):
            session.commit()


# ---------------------------------------------------------------------------
# Proposal: LLM advisor output, gated by human approval
# ---------------------------------------------------------------------------


class TestProposal:
    def test_minimal_pending_proposal(self, session):
        p = Proposal(
            entity_type="Task",
            entity_id=uuid.uuid4(),
            field_name="start_date",
            proposed_value=json.dumps("2026-06-01"),
        )
        session.add(p)
        session.commit()

        loaded = session.query(Proposal).filter_by(canonical_id=p.canonical_id).one()
        assert loaded.status == ProposalStatus.PENDING
        assert loaded.field_name == "start_date"
        assert json.loads(loaded.proposed_value) == "2026-06-01"
        assert loaded.decided_at is None
        assert loaded.decided_by is None

    def test_proposal_records_source_docs_and_confidence(self, session):
        doc_ids = [str(uuid.uuid4()), str(uuid.uuid4())]
        p = Proposal(
            entity_type="Task",
            entity_id=uuid.uuid4(),
            field_name="end_date",
            proposed_value=json.dumps({"date": "2026-07-15"}),
            confidence=0.83,
            source_doc_ids=json.dumps(doc_ids),
            prompt_version="timeline-v1",
        )
        session.add(p)
        session.commit()
        loaded = session.query(Proposal).filter_by(canonical_id=p.canonical_id).one()
        assert loaded.confidence == 0.83
        assert json.loads(loaded.source_doc_ids) == doc_ids
        assert loaded.prompt_version == "timeline-v1"

    def test_status_transitions_pending_to_accepted(self, session):
        p = Proposal(
            entity_type="Task", entity_id=uuid.uuid4(),
            field_name="start_date", proposed_value=json.dumps("2026-06-01"),
        )
        session.add(p)
        session.commit()

        p.status = ProposalStatus.ACCEPTED
        p.decided_at = datetime.utcnow()
        p.decided_by = "alice@company.com"
        session.commit()

        loaded = session.query(Proposal).filter_by(canonical_id=p.canonical_id).one()
        assert loaded.status == ProposalStatus.ACCEPTED
        assert loaded.decided_by == "alice@company.com"

    def test_rejection_carries_reason(self, session):
        p = Proposal(
            entity_type="Task", entity_id=uuid.uuid4(),
            field_name="start_date", proposed_value=json.dumps("2026-06-01"),
        )
        session.add(p)
        session.commit()

        p.status = ProposalStatus.REJECTED
        p.decided_at = datetime.utcnow()
        p.decided_by = "alice@company.com"
        p.rejection_reason = "Contract revision invalidated this date"
        session.commit()

        loaded = session.query(Proposal).filter_by(canonical_id=p.canonical_id).one()
        assert loaded.status == ProposalStatus.REJECTED
        assert loaded.rejection_reason.startswith("Contract")

    def test_required_fields_enforced(self, session):
        """entity_type, entity_id, field_name, proposed_value must be present."""
        session.add(Proposal(
            entity_type=None, entity_id=uuid.uuid4(),
            field_name="x", proposed_value="null",
        ))
        with pytest.raises(IntegrityError):
            session.commit()

    def test_supersede_old_proposal_for_same_field(self, session):
        """Same (entity_id, field_name) gets a new proposal -- old marked SUPERSEDED."""
        ent = uuid.uuid4()
        old = Proposal(
            entity_type="Task", entity_id=ent, field_name="start_date",
            proposed_value=json.dumps("2026-06-01"),
        )
        session.add(old)
        session.commit()

        new = Proposal(
            entity_type="Task", entity_id=ent, field_name="start_date",
            proposed_value=json.dumps("2026-06-05"),
        )
        session.add(new)
        old.status = ProposalStatus.SUPERSEDED
        session.commit()

        pending = session.query(Proposal).filter_by(
            entity_id=ent, field_name="start_date", status=ProposalStatus.PENDING,
        ).all()
        assert len(pending) == 1
        assert pending[0].canonical_id == new.canonical_id


# ---------------------------------------------------------------------------
# Migration helper: legacy SQLite files get the new tables on the fly
# ---------------------------------------------------------------------------


class TestPhase1Migration:
    def test_creates_document_text_table(self):
        from project_db.db.migrations import ensure_sqlite_schema

        engine = create_engine("sqlite:///:memory:", future=True)
        # Pre-existing schema with task + document but no document_text yet.
        with engine.begin() as conn:
            conn.execute(text("CREATE TABLE task (canonical_id TEXT PRIMARY KEY)"))
            conn.execute(text("CREATE TABLE document (canonical_id TEXT PRIMARY KEY, name TEXT, url TEXT, created_at DATETIME, updated_at DATETIME)"))

        ensure_sqlite_schema(engine)
        cols = {c["name"] for c in inspect(engine).get_columns("document_text")}
        assert {"document_id", "extracted_text", "extraction_method", "extracted_at", "token_count"} <= cols

    def test_creates_proposal_table(self):
        from project_db.db.migrations import ensure_sqlite_schema

        engine = create_engine("sqlite:///:memory:", future=True)
        with engine.begin() as conn:
            conn.execute(text("CREATE TABLE task (canonical_id TEXT PRIMARY KEY)"))

        ensure_sqlite_schema(engine)
        cols = {c["name"] for c in inspect(engine).get_columns("proposal")}
        for required in {
            "canonical_id", "entity_type", "entity_id", "field_name",
            "proposed_value", "confidence", "source_doc_ids", "prompt_version",
            "status", "decided_at", "decided_by", "rejection_reason",
        }:
            assert required in cols, f"proposal table missing {required!r}"

    def test_migration_is_idempotent_for_new_tables(self):
        """Two runs must not raise 'table already exists'."""
        from project_db.db.migrations import ensure_sqlite_schema

        engine = create_engine("sqlite:///:memory:", future=True)
        with engine.begin() as conn:
            conn.execute(text("CREATE TABLE task (canonical_id TEXT PRIMARY KEY)"))

        ensure_sqlite_schema(engine)
        ensure_sqlite_schema(engine)

    def test_full_create_all_works_on_fresh_db(self):
        """A fresh DB built via Base.metadata.create_all gets both new tables."""
        engine = create_engine("sqlite:///:memory:", future=True)
        Base.metadata.create_all(engine)
        names = set(inspect(engine).get_table_names())
        assert "document_text" in names
        assert "proposal" in names
