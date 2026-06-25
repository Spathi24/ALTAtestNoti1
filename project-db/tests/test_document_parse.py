"""Slice 1 of the evidence refactor: DocumentParse + EvidenceSpan models,
migration, and the DocumentText compatibility write-back helper.

Self-contained: builds its own FK-enforcing in-memory engine (SQLite ignores
ON DELETE CASCADE unless `PRAGMA foreign_keys=ON` per connection), so the
cascade-delete test is reliable in isolation as well as in the full suite.
"""

from __future__ import annotations

import json

import pytest
from sqlalchemy import create_engine, event, inspect
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from project_db.db.base import Base
from project_db.db.models import (
    EVIDENCE_TYPES,
    PARSE_STATUSES,
    Document,
    DocumentParse,
    DocumentText,
    EvidenceSpan,
)
from project_db.db.parse_compat import write_document_text_from_parse


@pytest.fixture
def fk_session():
    """In-memory SQLite with foreign keys ON and a single shared connection."""
    engine = create_engine(
        "sqlite:///:memory:",
        future=True,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(engine, "connect")
    def _fk(dbapi_connection, _record):  # pragma: no cover - trivial
        cur = dbapi_connection.cursor()
        cur.execute("PRAGMA foreign_keys=ON")
        cur.close()

    Base.metadata.create_all(engine)
    s = sessionmaker(bind=engine, expire_on_commit=False)()
    yield s
    s.close()
    engine.dispose()


def _document(session, name="Quote.pdf", mime="application/pdf") -> Document:
    doc = Document(name=name, url=f"https://drive/{name}", mime_type=mime)
    session.add(doc)
    session.flush()
    return doc


def _parse(session, doc, *, status="success", rendered="hello world", **kw) -> DocumentParse:
    p = DocumentParse(
        document_id=doc.canonical_id,
        parser_name=kw.pop("parser_name", "docling"),
        status=status,
        rendered_text=rendered,
        **kw,
    )
    session.add(p)
    session.flush()
    return p


# --------------------------------------------------------------------------- #
# Models
# --------------------------------------------------------------------------- #


def test_document_parse_can_be_created(fk_session):
    doc = _document(fk_session)
    p = _parse(
        fk_session,
        doc,
        parser_version="2.1",
        source_hash="abc123",
        structured_json=json.dumps({"pages": 2}),
        token_count=3,
    )
    fk_session.commit()

    got = fk_session.query(DocumentParse).one()
    assert got.document_id == doc.canonical_id
    assert got.parser_name == "docling"
    assert got.parser_version == "2.1"
    assert got.status == "success" and got.status in PARSE_STATUSES
    assert got.rendered_text == "hello world"
    assert json.loads(got.structured_json) == {"pages": 2}
    assert got.created_at is not None  # default fired
    assert got.id is not None


def test_evidence_spans_point_to_parse(fk_session):
    doc = _document(fk_session)
    p = _parse(fk_session, doc)
    span_a = EvidenceSpan(
        document_id=doc.canonical_id,
        parse_id=p.id,
        evidence_type="table_region",
        locator_json=json.dumps({"sheet": "Quote", "range": "B4:F29"}),
        content_json=json.dumps({"cells": {"F29": {"raw_value": 123393.83}}}),
        confidence=0.9,
    )
    span_b = EvidenceSpan(
        document_id=doc.canonical_id,
        parse_id=p.id,
        evidence_type="page",
        content_text="page 1 text",
    )
    fk_session.add_all([span_a, span_b])
    fk_session.commit()

    spans = fk_session.query(EvidenceSpan).filter_by(parse_id=p.id).all()
    assert len(spans) == 2
    assert {s.evidence_type for s in spans} == {"table_region", "page"}
    assert all(s.evidence_type in EVIDENCE_TYPES for s in spans)
    assert all(s.document_id == doc.canonical_id for s in spans)


def test_deleting_document_cascades_parse_and_evidence(fk_session):
    doc = _document(fk_session)
    p = _parse(fk_session, doc)
    fk_session.add(
        EvidenceSpan(document_id=doc.canonical_id, parse_id=p.id, evidence_type="page")
    )
    fk_session.commit()
    assert fk_session.query(DocumentParse).count() == 1
    assert fk_session.query(EvidenceSpan).count() == 1

    fk_session.delete(doc)
    fk_session.commit()

    assert fk_session.query(DocumentParse).count() == 0
    assert fk_session.query(EvidenceSpan).count() == 0


# --------------------------------------------------------------------------- #
# DocumentText compatibility write-back
# --------------------------------------------------------------------------- #


def test_writeback_creates_document_text(fk_session):
    doc = _document(fk_session)
    p = _parse(fk_session, doc, parser_version="2.1", rendered="extracted body text")
    fk_session.commit()

    row = write_document_text_from_parse(fk_session, p)
    fk_session.commit()

    assert row is not None
    dt = fk_session.query(DocumentText).filter_by(document_id=doc.canonical_id).one()
    assert dt.extracted_text == "extracted body text"
    assert dt.extraction_method == "docling/2.1"  # parser_name + version
    assert dt.token_count is not None
    assert dt.extracted_at is not None


def test_writeback_updates_existing_document_text(fk_session):
    doc = _document(fk_session)
    fk_session.add(
        DocumentText(
            document_id=doc.canonical_id,
            extracted_text="OLD",
            extraction_method="legacy",
            token_count=1,
        )
    )
    fk_session.commit()

    p = _parse(fk_session, doc, rendered="NEW body")
    fk_session.commit()
    write_document_text_from_parse(fk_session, p)
    fk_session.commit()

    rows = fk_session.query(DocumentText).filter_by(document_id=doc.canonical_id).all()
    assert len(rows) == 1  # upsert, not insert
    assert rows[0].extracted_text == "NEW body"
    assert rows[0].extraction_method == "docling"


def test_writeback_skips_non_success_parse(fk_session):
    doc = _document(fk_session)
    p = _parse(fk_session, doc, status="failed", rendered=None)
    fk_session.commit()

    row = write_document_text_from_parse(fk_session, p)
    assert row is None
    assert (
        fk_session.query(DocumentText).filter_by(document_id=doc.canonical_id).count() == 0
    )


# --------------------------------------------------------------------------- #
# Migration on a pre-existing DB
# --------------------------------------------------------------------------- #


def test_migration_creates_parse_and_evidence_tables_on_blank_db(tmp_path):
    from project_db.db.migrations import ensure_sqlite_schema

    db = tmp_path / "old.sqlite"
    engine = create_engine(f"sqlite:///{db}", future=True)
    names = set(inspect(engine).get_table_names())
    assert "document_parse" not in names
    assert "evidence_span" not in names

    ensure_sqlite_schema(engine)

    names = set(inspect(engine).get_table_names())
    assert "document_parse" in names
    assert "evidence_span" in names
    engine.dispose()
