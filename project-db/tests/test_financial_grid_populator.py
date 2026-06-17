"""Phase 1b: financial_grid_populator -- persists parsed quote rows as
FinancialLineItem records.

Uses an in-memory SQLite DB with the canonical schema. Synthetic fixtures only
(no real client data); the real-data reconciliation ($66,539.65) is verified
out-of-band.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from project_db.ai.financial_grid_populator import (
    DocLedgerResult,
    ProjectLedgerResult,
    _extract_currency,
    _extract_status,
    _extract_unit,
    populate_ledger_for_document,
    populate_ledger_for_project,
)
from project_db.db.base import Base
from project_db.db.models import Client, Organization, Project
from project_db.db.models.docs import Document, DocumentText
from project_db.db.models.finance import FinancialLineItem
from project_db.db.models.work import ProjectStatus

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

_QUOTE_TEXT = """\
,ESTIMATE,,,,
100 Test Ave,,Date,1/1/2026,,
TestCity QC,,Estimate #,T-001,,
,,Client ID,Test Client,,
,,Valid Until,2/1/2026,,
,,,,,
Description,Notes/ Master Format values,, Material Amount (CAD),Labour Amount (CAD),Total Amount (CAD)
,,,,,
Demolition,Div. 02,,,,"$1,000.00"
    Demo scope,02 41 00,,$400.00,$600.00,
Plumbing,Div. 22,,,,$500.00
    Rough-in,22 11 16,,$500.00,,
OHP,,,,,$150.00
,,,,Pre-Tax total,"$1,650.00"
,,,,After-Tax Total,"$1,897.50"
"""

_JOBCOST_TEXT = """\
MATERIAL SPENDING,,,,
Phase,Item Description, Cost ,Supplier,Date
Finishing,Floor," $ 500.00 ",Supplier A,01/01
"""

_EMPTY_TEXT = ""


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


def _make_project(session) -> Project:
    org = Organization(canonical_id=uuid.uuid4(), name="Test Org")
    client = Client(canonical_id=uuid.uuid4(), name="Test Client", organization_id=org.canonical_id)
    project = Project(
        canonical_id=uuid.uuid4(),
        name="923 Test St.",
        status=ProjectStatus.ACTIVE,
        client_id=client.canonical_id,
    )
    session.add_all([org, client, project])
    session.flush()
    return project


def _make_doc(session, project, name: str, text: str) -> tuple[Document, DocumentText]:
    doc = Document(
        canonical_id=uuid.uuid4(),
        name=name,
        url=f"https://drive.google.com/file/{uuid.uuid4()}",
        is_trashed=False,
        project_id=project.canonical_id,
        modified_at_source=datetime(2026, 1, 15),
    )
    dt = DocumentText(
        document_id=doc.canonical_id,
        extracted_text=text,
        extraction_method="csv",
        extracted_at=datetime(2026, 1, 16),
    )
    session.add_all([doc, dt])
    session.flush()
    return doc, dt


# ---------------------------------------------------------------------------
# Unit / status / currency helpers
# ---------------------------------------------------------------------------


class TestExtractUnit:
    def test_leading_civic(self):
        assert _extract_unit("923 ACCEPTED QUOTE") == "923"
        assert _extract_unit("921 QUOTE") == "921"

    def test_exterior_keyword(self):
        assert _extract_unit("exterior quote") == "exterior"
        assert _extract_unit("Exterior ACCEPTED QUOTE") == "exterior"

    def test_range_means_whole_project(self):
        assert _extract_unit("923-927 ACCEPTED QUOTE") is None

    def test_no_unit_cue(self):
        assert _extract_unit("ACCEPTED QUOTE") is None
        assert _extract_unit(None) is None

    def test_four_digit_civic(self):
        assert _extract_unit("5768 ACCEPTED QUOTE") == "5768"


class TestExtractStatus:
    def test_accepted(self):
        assert _extract_status("923 ACCEPTED QUOTE") == "accepted"
        assert _extract_status("EXTRAS ACCEPTED") == "accepted"

    def test_not_started_is_proposed(self):
        assert _extract_status("927 QUOTE (NOT STARTED)") == "proposed"

    def test_not_accepted_is_proposed(self):
        assert _extract_status("Quote NOT ACCEPTED") == "proposed"

    def test_plain_quote_is_unknown(self):
        assert _extract_status("923 QUOTE") == "unknown"
        assert _extract_status(None) == "unknown"


class TestExtractCurrency:
    def test_cad_default(self):
        assert _extract_currency("Material Amount (CAD)") == "CAD"
        assert _extract_currency("") == "CAD"
        assert _extract_currency(None) == "CAD"

    def test_usd_detected(self):
        assert _extract_currency("Material Amount (USD)\nsome content") == "USD"


# ---------------------------------------------------------------------------
# populate_ledger_for_document
# ---------------------------------------------------------------------------


class TestPopulateLedgerForDocument:
    def test_quote_sheet_writes_rows(self, db_session):
        project = _make_project(db_session)
        doc, dt = _make_doc(db_session, project, "923 ACCEPTED QUOTE", _QUOTE_TEXT)

        result = populate_ledger_for_document(db_session, doc, dt)

        assert not result.skipped
        assert result.sheet_type == "quote"
        assert result.rows_written > 0
        assert result.reconcile_ok is True
        assert result.grand_total == Decimal("1650.00")
        assert result.division_total == result.grand_total

        rows = db_session.query(FinancialLineItem).filter(
            FinancialLineItem.document_id == doc.canonical_id
        ).all()
        assert len(rows) == result.rows_written

    def test_rows_carry_correct_metadata(self, db_session):
        project = _make_project(db_session)
        doc, dt = _make_doc(db_session, project, "923 ACCEPTED QUOTE", _QUOTE_TEXT)
        populate_ledger_for_document(db_session, doc, dt)

        rows = db_session.query(FinancialLineItem).filter(
            FinancialLineItem.document_id == doc.canonical_id
        ).all()
        for row in rows:
            assert row.project_id == project.canonical_id
            assert row.side == "revenue"
            assert row.doc_role == "quote"
            assert row.source == "grid"
            assert row.amount_verified is True
            assert row.confidence == 1.0
            assert row.currency == "CAD"
            assert row.status == "accepted"  # "923 ACCEPTED QUOTE"
            assert row.unit == "923"

    def test_division_codes_correct(self, db_session):
        project = _make_project(db_session)
        doc, dt = _make_doc(db_session, project, "923 ACCEPTED QUOTE", _QUOTE_TEXT)
        populate_ledger_for_document(db_session, doc, dt)

        rows = db_session.query(FinancialLineItem).filter(
            FinancialLineItem.document_id == doc.canonical_id
        ).all()
        codes = {row.division_code for row in rows}
        assert "02" in codes  # Demolition section
        assert "22" in codes  # Plumbing section
        assert "01" in codes  # OHP -> General Requirements

    def test_not_started_status(self, db_session):
        project = _make_project(db_session)
        doc, dt = _make_doc(db_session, project, "927 QUOTE (NOT STARTED)", _QUOTE_TEXT)
        populate_ledger_for_document(db_session, doc, dt)

        rows = db_session.query(FinancialLineItem).filter(
            FinancialLineItem.document_id == doc.canonical_id
        ).all()
        assert all(r.status == "proposed" for r in rows)

    def test_non_quote_sheet_skipped(self, db_session):
        project = _make_project(db_session)
        doc, dt = _make_doc(db_session, project, "JOB COSTING", _JOBCOST_TEXT)

        result = populate_ledger_for_document(db_session, doc, dt)

        assert result.skipped
        assert result.sheet_type == "job_cost"
        assert result.rows_written == 0
        count = db_session.query(FinancialLineItem).filter(
            FinancialLineItem.document_id == doc.canonical_id
        ).count()
        assert count == 0

    def test_idempotent_double_run(self, db_session):
        project = _make_project(db_session)
        doc, dt = _make_doc(db_session, project, "923 ACCEPTED QUOTE", _QUOTE_TEXT)

        r1 = populate_ledger_for_document(db_session, doc, dt)
        db_session.flush()
        r2 = populate_ledger_for_document(db_session, doc, dt)
        db_session.flush()

        assert r1.rows_written == r2.rows_written
        # Only one set of rows in the DB (no duplicates).
        count = db_session.query(FinancialLineItem).filter(
            FinancialLineItem.document_id == doc.canonical_id
        ).count()
        assert count == r1.rows_written

    def test_no_grand_total_reconcile_is_none(self, db_session):
        project = _make_project(db_session)
        # A quote grid with no "Pre-Tax total" row
        text = (
            "Description,Notes/ Master Format,, Material Amount (CAD),"
            "Labour Amount (CAD),Total Amount (CAD)\n"
            "Demolition,Div. 02,,,,$500.00\n"
        )
        doc, dt = _make_doc(db_session, project, "923 ACCEPTED QUOTE", text)
        result = populate_ledger_for_document(db_session, doc, dt)

        assert not result.skipped
        assert result.reconcile_ok is None  # nothing to compare against


# ---------------------------------------------------------------------------
# populate_ledger_for_project
# ---------------------------------------------------------------------------


class TestPopulateLedgerForProject:
    def test_project_with_mixed_docs(self, db_session):
        project = _make_project(db_session)
        _make_doc(db_session, project, "923 ACCEPTED QUOTE", _QUOTE_TEXT)
        _make_doc(db_session, project, "JOB COSTING", _JOBCOST_TEXT)

        batch = populate_ledger_for_project(db_session, project.canonical_id)

        assert isinstance(batch, ProjectLedgerResult)
        assert len(batch.docs) == 2
        assert len(batch.parsed_docs) == 1  # only the quote
        assert batch.total_rows > 0

        skipped = [d for d in batch.docs if d.skipped]
        assert len(skipped) == 1
        assert skipped[0].sheet_type == "job_cost"

    def test_empty_project(self, db_session):
        project = _make_project(db_session)
        batch = populate_ledger_for_project(db_session, project.canonical_id)
        assert batch.total_rows == 0
        assert batch.docs == []

    def test_trashed_docs_excluded(self, db_session):
        project = _make_project(db_session)
        doc = Document(
            canonical_id=uuid.uuid4(),
            name="923 ACCEPTED QUOTE",
            url="https://example.com",
            is_trashed=True,
            project_id=project.canonical_id,
        )
        dt = DocumentText(
            document_id=doc.canonical_id,
            extracted_text=_QUOTE_TEXT,
            extraction_method="csv",
            extracted_at=datetime(2026, 1, 16),
        )
        db_session.add_all([doc, dt])
        db_session.flush()

        batch = populate_ledger_for_project(db_session, project.canonical_id)
        assert batch.total_rows == 0

    def test_summary_string_is_readable(self, db_session):
        project = _make_project(db_session)
        _make_doc(db_session, project, "923 ACCEPTED QUOTE", _QUOTE_TEXT)
        batch = populate_ledger_for_project(db_session, project.canonical_id)
        summary = batch.summary()
        assert "Ledger populated" in summary
        assert "923 ACCEPTED QUOTE" in summary
        assert "OK" in summary
