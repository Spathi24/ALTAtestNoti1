"""LLM division extractor -- engine tests with a MockFinancialLineExtractor.

Validates the deterministic half (division mapping, amount verification,
reconcile, idempotency, grid-row coexistence). No API calls.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from project_db.ai.financial_llm_extractor import (
    MockFinancialLineExtractor,
    populate_ledger_llm_for_document,
    populate_ledger_llm_for_project,
)
from project_db.db.base import Base
from project_db.db.models import Client, Organization, Project
from project_db.db.models.docs import Document, DocumentText
from project_db.db.models.finance import FinancialLineItem
from project_db.db.models.work import ProjectStatus

_QUOTE_TEXT = (
    "RENOVATION QUOTE\nClient: Geller\n"
    "Plumbing rough-in .......... $5,000.00\n"
    "Electrical panel upgrade .... $3,000.00\n"
    "Finishes - flooring ......... $2,000.00\n"
    "Pre-Tax Total .............. $10,000.00\n"
)


def _quote_response(
    unit=None, stated=10000.0, lines=None, doc_type="construction_quote", revenue=True
):
    if lines is None:
        lines = [
            {
                "description": "Plumbing rough-in",
                "masterformat_hint": "Division 22",
                "amount": 5000.0,
                "amount_type": "total",
                "quoted_excerpt": "Plumbing rough-in $5,000.00",
                "confidence": 0.95,
            },
            {
                "description": "Electrical panel upgrade",
                "masterformat_hint": None,
                "amount": 3000.0,
                "amount_type": "total",
                "quoted_excerpt": "Electrical panel upgrade $3,000.00",
                "confidence": 0.9,
            },
            {
                "description": "Finishes - flooring",
                "masterformat_hint": None,
                "amount": 2000.0,
                "amount_type": "total",
                "quoted_excerpt": "Finishes - flooring $2,000.00",
                "confidence": 0.9,
            },
        ]
    return {
        "document_type": doc_type,
        "is_revenue_quote": revenue,
        "unit": unit,
        "currency": "CAD",
        "stated_total": stated,
        "line_items": lines,
    }


@pytest.fixture
def db_session():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)
    s = SessionLocal()
    yield s
    s.rollback()
    s.close()


def _seed_project(session, name="1455 Rue St. Mathieu"):
    org = Organization(canonical_id=uuid.uuid4(), name="Test Org")
    client = Client(canonical_id=uuid.uuid4(), name="Client", organization_id=org.canonical_id)
    project = Project(
        canonical_id=uuid.uuid4(),
        name=name,
        status=ProjectStatus.ACTIVE,
        client_id=client.canonical_id,
    )
    session.add_all([org, client, project])
    session.flush()
    return project


def _make_doc(session, project, name, text):
    doc = Document(
        canonical_id=uuid.uuid4(),
        name=name,
        url=f"x://{uuid.uuid4()}",
        is_trashed=False,
        project_id=project.canonical_id,
        modified_at_source=datetime(2026, 1, 15),
    )
    session.add(doc)
    session.flush()
    dt = DocumentText(
        document_id=doc.canonical_id,
        extracted_text=text,
        extraction_method="pdf",
        extracted_at=datetime(2026, 1, 16),
    )
    session.add(dt)
    session.flush()
    return doc, dt


class TestPopulateLLMDocument:
    def test_revenue_quote_writes_division_rows(self, db_session):
        project = _seed_project(db_session)
        doc, dt = _make_doc(db_session, project, "Richard Geller Home - R1.pdf", _QUOTE_TEXT)
        ex = MockFinancialLineExtractor({doc.name: _quote_response()})

        res = populate_ledger_llm_for_document(db_session, doc, dt, ex, company_name="Alta")
        assert res.ingestion_status == "parsed"
        assert res.rows_written == 3

        rows = (
            db_session.query(FinancialLineItem)
            .filter(FinancialLineItem.document_id == doc.canonical_id)
            .all()
        )
        codes = {r.division_code for r in rows}
        assert "22" in codes  # plumbing (via masterformat_hint Division 22)
        assert "26" in codes  # electrical (via description)
        assert "09" in codes  # finishes/flooring
        for r in rows:
            assert r.source == "llm"
            assert r.side == "revenue"
            assert r.classification_method == "llm_assisted"

    def test_amount_verified_against_text(self, db_session):
        project = _seed_project(db_session)
        doc, dt = _make_doc(db_session, project, "Quote.pdf", _QUOTE_TEXT)
        # One real line ($5,000 in text) + one fabricated ($9,999 not in text).
        lines = [
            {
                "description": "Plumbing",
                "masterformat_hint": "Division 22",
                "amount": 5000.0,
                "amount_type": "total",
                "quoted_excerpt": "Plumbing rough-in $5,000.00",
                "confidence": 0.9,
            },
            {
                "description": "Mystery",
                "masterformat_hint": None,
                "amount": 9999.0,
                "amount_type": "total",
                "quoted_excerpt": "n/a",
                "confidence": 0.4,
            },
        ]
        ex = MockFinancialLineExtractor({doc.name: _quote_response(stated=14999.0, lines=lines)})
        populate_ledger_llm_for_document(db_session, doc, dt, ex, company_name="Alta")
        rows = {
            r.description: r
            for r in db_session.query(FinancialLineItem).filter(
                FinancialLineItem.document_id == doc.canonical_id
            )
        }
        assert rows["Plumbing"].amount_verified is True
        assert rows["Mystery"].amount_verified is False

    def test_reconcile_ok_and_fail(self, db_session):
        project = _seed_project(db_session)
        doc, dt = _make_doc(db_session, project, "Q.pdf", _QUOTE_TEXT)
        ex = MockFinancialLineExtractor({doc.name: _quote_response(stated=10000.0)})
        res = populate_ledger_llm_for_document(db_session, doc, dt, ex, company_name="Alta")
        assert res.reconcile_ok is True  # 5000+3000+2000 == 10000

        doc2, dt2 = _make_doc(db_session, project, "Q2.pdf", _QUOTE_TEXT)
        ex2 = MockFinancialLineExtractor({doc2.name: _quote_response(stated=12000.0)})
        res2 = populate_ledger_llm_for_document(db_session, doc2, dt2, ex2, company_name="Alta")
        assert res2.reconcile_ok is False  # lines sum 10000, stated 12000

    def test_non_revenue_skipped(self, db_session):
        project = _seed_project(db_session)
        doc, dt = _make_doc(db_session, project, "Supplier Invoice.pdf", _QUOTE_TEXT)
        ex = MockFinancialLineExtractor(
            {doc.name: _quote_response(doc_type="supplier_invoice", revenue=False)}
        )
        res = populate_ledger_llm_for_document(db_session, doc, dt, ex, company_name="Alta")
        assert res.ingestion_status == "skipped"
        assert res.ingestion_reason == "not_revenue_quote"
        assert (
            db_session.query(FinancialLineItem)
            .filter(FinancialLineItem.document_id == doc.canonical_id)
            .count()
            == 0
        )

    def test_empty_text_skipped(self, db_session):
        project = _seed_project(db_session)
        doc, dt = _make_doc(db_session, project, "Blank.pdf", "")
        ex = MockFinancialLineExtractor()
        res = populate_ledger_llm_for_document(db_session, doc, dt, ex, company_name="Alta")
        assert res.ingestion_reason == "empty_extraction"
        assert ex.calls == []  # never called the LLM on empty text

    def test_unit_from_llm_else_filename(self, db_session):
        project = _seed_project(db_session)
        doc, dt = _make_doc(db_session, project, "927 Quote.pdf", _QUOTE_TEXT)
        # LLM gives no unit -> fall back to filename "927".
        ex = MockFinancialLineExtractor({doc.name: _quote_response(unit=None)})
        populate_ledger_llm_for_document(db_session, doc, dt, ex, company_name="Alta")
        rows = db_session.query(FinancialLineItem).filter(
            FinancialLineItem.document_id == doc.canonical_id
        )
        assert all(r.unit == "927" for r in rows)

    def test_idempotent_replaces_only_llm_rows(self, db_session):
        project = _seed_project(db_session)
        doc, dt = _make_doc(db_session, project, "Q.pdf", _QUOTE_TEXT)
        ex = MockFinancialLineExtractor({doc.name: _quote_response()})
        populate_ledger_llm_for_document(db_session, doc, dt, ex, company_name="Alta")
        populate_ledger_llm_for_document(db_session, doc, dt, ex, company_name="Alta")
        assert (
            db_session.query(FinancialLineItem)
            .filter(FinancialLineItem.document_id == doc.canonical_id)
            .count()
            == 3
        )


class TestPopulateLLMProject:
    def test_skips_grid_parsed_docs(self, db_session):
        project = _seed_project(db_session)
        grid_doc, _grid_dt = _make_doc(db_session, project, "923 ACCEPTED QUOTE", _QUOTE_TEXT)
        # Simulate the grid parser already having produced a row for this doc.
        db_session.add(
            FinancialLineItem(
                project_id=project.canonical_id,
                document_id=grid_doc.canonical_id,
                division_code="22",
                side="revenue",
                amount_type="total",
                amount=Decimal("500"),
                source="grid",
                status="accepted",
            )
        )
        _pdf_doc, _pdf_dt = _make_doc(db_session, project, "Geller.pdf", _QUOTE_TEXT)
        db_session.flush()

        ex = MockFinancialLineExtractor(
            {
                "923 ACCEPTED QUOTE": _quote_response(),
                "Geller.pdf": _quote_response(),
            }
        )
        batch = populate_ledger_llm_for_project(
            db_session, ex, project.canonical_id, company_name="Alta"
        )
        # The grid-parsed doc must NOT have been sent to the LLM.
        assert "923 ACCEPTED QUOTE" not in ex.calls
        assert "Geller.pdf" in ex.calls
        # grid row preserved; llm rows added for the PDF only.
        assert (
            db_session.query(FinancialLineItem).filter(FinancialLineItem.source == "grid").count()
            == 1
        )
        assert (
            db_session.query(FinancialLineItem).filter(FinancialLineItem.source == "llm").count()
            == 3
        )

    def test_limit_caps_llm_calls(self, db_session):
        project = _seed_project(db_session)
        for i in range(4):
            _make_doc(db_session, project, f"Quote {i}.pdf", _QUOTE_TEXT)
        ex = MockFinancialLineExtractor(default=_quote_response())
        populate_ledger_llm_for_project(
            db_session, ex, project.canonical_id, company_name="Alta", limit=2
        )
        assert len(ex.calls) == 2
