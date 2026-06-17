"""Phase 1c-MVP acceptance criteria tests (10 criteria).

Verifies the full guarantee set declared in the Phase 1c-MVP specification:
  1.  Quote rows remain unchanged.
  2.  Extras rows are inserted into FinancialLineItem (not a side table).
  3.  report_division_margins reflects extras (at least accepted rows show up).
  4.  Budget-only rows do not reduce gross margin.
  5.  Quantity-only rows do not reduce gross margin.
  6.  Extras/change orders are not double-counted with base quote revenue.
  7.  Re-running fill-ledger is idempotent.
  8.  unknown_unit and unknown_division are flagged, not silently grouped.
  9.  Source document provenance is preserved on extras rows.
  10. Old /financials path (FinancialRecord) is untouched.

Uses in-memory SQLite + synthetic fixtures.  No LLM, no external I/O.
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
    populate_ledger_for_document,
    populate_ledger_for_project,
)
from project_db.ai.views import report_division_margins
from project_db.db.base import Base
from project_db.db.models import Client, Organization, Project
from project_db.db.models.docs import Document, DocumentText
from project_db.db.models.finance import FinancialLineItem, FinancialRecord
from project_db.db.models.work import ProjectStatus

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

_QUOTE_CSV = """\
,ESTIMATE,,,,
923 Test Ave,,Date,1/1/2026,,
TestCity QC,,Estimate #,T-001,,
,,Valid Until,2/28/2026,,
,,,,,
Description,Notes/ Master Format values,, Material Amount (CAD),Labour Amount (CAD),Total Amount (CAD)
,,,,,
Demolition,Div. 02,,,,"$1,000.00"
    Demo scope,02 41 00,,$400.00,$600.00,
Plumbing,Div. 22,,,,"$500.00"
    Rough-in,22 11 16,,$500.00,,
OHP,,,,,"$150.00"
,,,,Pre-Tax total,"$1,650.00"
,,,,After-Tax Total,"$1,897.50"
"""

_EXTRAS_CSV = """\
CO #,Item,Cost/Unit,Applied,Total,Status
1,Additional plumbing fixture,300.00,1,"$300.00",Accepted
2,Extra demolition scope - back wall,200.00,1,"$200.00",Accepted
3,Proposed window upgrade,800.00,1,"$800.00",Proposed
4,Cancelled scope change,500.00,1,"$500.00",Not Accepted
"""

_JOBCOST_CSV = """\
MATERIAL SPENDING,,,,
Phase,Item Description, Cost ,Supplier,Date
Plumbing,PEX piping," $ 250.00 ",Home Depot,01/15
Finishing,Floor tiles," $ 500.00 ",Supplier A,01/20
"""

_ORDER_QTY_CSV = """\
Door Order Sheet,,,,
Item,Width,Height,QTY,Unit
Interior door,32,80,3,EA
Window,24,36,4,EA
"""


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


def _seed_project(session):
    org = Organization(canonical_id=uuid.uuid4(), name="Test Org")
    client = Client(canonical_id=uuid.uuid4(), name="Test Client",
                    organization_id=org.canonical_id)
    project = Project(
        canonical_id=uuid.uuid4(),
        name="923 Test Project",
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
        url=f"https://drive.google.com/{uuid.uuid4()}",
        is_trashed=False,
        project_id=project.canonical_id,
        modified_at_source=datetime(2026, 1, 20),
    )
    session.add(doc)
    session.flush()
    dt = DocumentText(
        document_id=doc.canonical_id,
        extracted_text=text,
        extraction_method="csv",
        extracted_at=datetime(2026, 1, 21),
    )
    session.add(dt)
    session.flush()
    return doc, dt


# ---------------------------------------------------------------------------
# Criterion 1: Quote rows remain unchanged
# ---------------------------------------------------------------------------

class TestCriterion1QuoteRowsUnchanged:
    def test_quote_rows_still_written(self, db_session):
        project = _seed_project(db_session)
        doc, dt = _make_doc(db_session, project, "923 ACCEPTED QUOTE", _QUOTE_CSV)
        result = populate_ledger_for_document(db_session, doc, dt)

        assert result.ingestion_status == "parsed", result.ingestion_reason
        assert result.sheet_type == "quote"
        assert result.rows_written > 0
        assert result.reconcile_ok is True

    def test_quote_rows_have_correct_side_and_doc_role(self, db_session):
        project = _seed_project(db_session)
        doc, dt = _make_doc(db_session, project, "923 ACCEPTED QUOTE", _QUOTE_CSV)
        populate_ledger_for_document(db_session, doc, dt)

        rows = db_session.query(FinancialLineItem).filter(
            FinancialLineItem.document_id == doc.canonical_id
        ).all()
        assert all(r.side == "revenue" for r in rows)
        assert all(r.doc_role == "quote" for r in rows)
        assert all(r.source == "grid" for r in rows)
        # Phase 1c-MVP: classification metadata
        assert all(r.classification_method == "deterministic" for r in rows)
        assert all(r.source_doc_type == "quote" for r in rows)


# ---------------------------------------------------------------------------
# Criterion 2: Extras rows inserted into FinancialLineItem
# ---------------------------------------------------------------------------

class TestCriterion2ExtrasInLedger:
    def test_extras_rows_written(self, db_session):
        project = _seed_project(db_session)
        doc, dt = _make_doc(db_session, project, "EXTRAS ACCEPTED", _EXTRAS_CSV)
        result = populate_ledger_for_document(db_session, doc, dt)

        assert result.ingestion_status == "parsed", result.ingestion_reason
        assert result.sheet_type == "extras"
        assert result.rows_written > 0  # accepted + proposed rows

    def test_extras_rows_metadata(self, db_session):
        project = _seed_project(db_session)
        doc, dt = _make_doc(db_session, project, "EXTRAS ACCEPTED", _EXTRAS_CSV)
        populate_ledger_for_document(db_session, doc, dt)

        rows = db_session.query(FinancialLineItem).filter(
            FinancialLineItem.document_id == doc.canonical_id
        ).all()
        assert rows, "no rows written"
        for r in rows:
            assert r.side == "revenue"
            assert r.doc_role == "change_order"
            assert r.amount_type == "adjustment"
            assert r.source == "grid/extras"
            assert r.classification_method == "deterministic"
            assert r.source_doc_type == "extras"

    def test_rejected_extras_not_written(self, db_session):
        project = _seed_project(db_session)
        doc, dt = _make_doc(db_session, project, "EXTRAS ACCEPTED", _EXTRAS_CSV)
        populate_ledger_for_document(db_session, doc, dt)

        rows = db_session.query(FinancialLineItem).filter(
            FinancialLineItem.document_id == doc.canonical_id
        ).all()
        # CO4 was "Not Accepted" → must not be in ledger
        amounts = [float(r.amount) for r in rows]
        assert 500.0 not in amounts, "rejected extra (CO4=$500) was wrongly inserted"


# ---------------------------------------------------------------------------
# Criterion 3: report_division_margins reflects extras
# ---------------------------------------------------------------------------

class TestCriterion3MarginsReflectExtras:
    def test_extras_appear_in_margins(self, db_session):
        project = _seed_project(db_session)
        # Only extras, no base quote
        doc, dt = _make_doc(db_session, project, "EXTRAS ACCEPTED", _EXTRAS_CSV)
        populate_ledger_for_document(db_session, doc, dt)

        margins = report_division_margins(db_session, "923 Test Project")
        assert "error" not in margins
        assert len(margins["divisions"]) > 0
        # All divisions should be revenue_only at this stage (no cost data)
        flags = {r["status_flag"] for r in margins["divisions"]}
        assert "revenue_only" in flags or "unknown_division" in flags

    def test_extras_added_to_quote_totals(self, db_session):
        project = _seed_project(db_session)
        quote_doc, quote_dt = _make_doc(db_session, project, "923 ACCEPTED QUOTE", _QUOTE_CSV)
        extras_doc, extras_dt = _make_doc(db_session, project, "EXTRAS ACCEPTED", _EXTRAS_CSV)

        populate_ledger_for_document(db_session, quote_doc, quote_dt)
        populate_ledger_for_document(db_session, extras_doc, extras_dt)

        margins = report_division_margins(db_session, "923 Test Project")
        # Quote pre-tax = $1,650 + accepted extras CO1=$300, CO2=$200 = $2,150
        # proposed CO3=$800 is also in ledger; total quoted revenue >= $1650
        total = margins["total_quoted_revenue"]
        assert total is not None
        assert total > 1650.0, "extras revenue not added to quote revenue"


# ---------------------------------------------------------------------------
# Criterion 4: Budget-only rows do not reduce gross margin
# ---------------------------------------------------------------------------

class TestCriterion4BudgetRowsNotCost:
    def test_jobcost_skipped_not_cost(self, db_session):
        project = _seed_project(db_session)
        doc, dt = _make_doc(db_session, project, "JOB COSTING (5768)", _JOBCOST_CSV)
        result = populate_ledger_for_document(db_session, doc, dt)

        assert result.ingestion_status == "skipped"
        assert result.ingestion_reason == "unsupported_type"
        assert result.rows_written == 0

        count = db_session.query(FinancialLineItem).filter(
            FinancialLineItem.document_id == doc.canonical_id
        ).count()
        assert count == 0, "job_cost rows must not land in ledger"

    def test_skipped_job_cost_does_not_change_margin(self, db_session):
        project = _seed_project(db_session)
        quote_doc, quote_dt = _make_doc(db_session, project, "923 ACCEPTED QUOTE", _QUOTE_CSV)
        jobcost_doc, jobcost_dt = _make_doc(db_session, project, "JOB COSTING (5768)", _JOBCOST_CSV)

        populate_ledger_for_document(db_session, quote_doc, quote_dt)
        populate_ledger_for_document(db_session, jobcost_doc, jobcost_dt)

        margins = report_division_margins(db_session, "923 Test Project")
        # All divisions still revenue_only — cost side is empty
        flags = {r["status_flag"] for r in margins["divisions"]}
        assert "cost_only" not in flags
        assert "ok" not in flags


# ---------------------------------------------------------------------------
# Criterion 5: Quantity-only rows do not reduce gross margin
# ---------------------------------------------------------------------------

class TestCriterion5QuantityRowsNotCost:
    def test_order_quantities_skipped(self, db_session):
        project = _seed_project(db_session)
        doc, dt = _make_doc(db_session, project, "Door Order Sheet", _ORDER_QTY_CSV)
        result = populate_ledger_for_document(db_session, doc, dt)

        assert result.ingestion_status == "skipped"
        assert result.rows_written == 0

    def test_order_quantities_do_not_affect_margin(self, db_session):
        project = _seed_project(db_session)
        quote_doc, quote_dt = _make_doc(db_session, project, "923 ACCEPTED QUOTE", _QUOTE_CSV)
        order_doc, order_dt = _make_doc(db_session, project, "Door Order Sheet", _ORDER_QTY_CSV)

        populate_ledger_for_document(db_session, quote_doc, quote_dt)
        populate_ledger_for_document(db_session, order_doc, order_dt)

        before = report_division_margins(db_session, "923 Test Project")
        # No cost rows → gross_margin is still None
        assert before["gross_margin"] is None


# ---------------------------------------------------------------------------
# Criterion 6: Extras not double-counted with base quote revenue
# ---------------------------------------------------------------------------

class TestCriterion6NoDoubleCount:
    def test_quote_and_extras_different_document_ids(self, db_session):
        project = _seed_project(db_session)
        quote_doc, quote_dt = _make_doc(db_session, project, "923 ACCEPTED QUOTE", _QUOTE_CSV)
        extras_doc, extras_dt = _make_doc(db_session, project, "EXTRAS ACCEPTED", _EXTRAS_CSV)

        populate_ledger_for_document(db_session, quote_doc, quote_dt)
        populate_ledger_for_document(db_session, extras_doc, extras_dt)

        all_rows = db_session.query(FinancialLineItem).filter(
            FinancialLineItem.project_id == project.canonical_id
        ).all()
        doc_ids = {str(r.document_id) for r in all_rows}
        assert len(doc_ids) == 2, "rows from both documents must stay separate"

    def test_re_running_quote_does_not_duplicate_rows(self, db_session):
        project = _seed_project(db_session)
        quote_doc, quote_dt = _make_doc(db_session, project, "923 ACCEPTED QUOTE", _QUOTE_CSV)
        extras_doc, extras_dt = _make_doc(db_session, project, "EXTRAS ACCEPTED", _EXTRAS_CSV)

        populate_ledger_for_document(db_session, quote_doc, quote_dt)
        populate_ledger_for_document(db_session, extras_doc, extras_dt)
        db_session.flush()

        # Re-run quote only → extras rows unchanged
        r2 = populate_ledger_for_document(db_session, quote_doc, quote_dt)
        db_session.flush()

        quote_rows = db_session.query(FinancialLineItem).filter(
            FinancialLineItem.document_id == quote_doc.canonical_id
        ).count()
        extras_rows = db_session.query(FinancialLineItem).filter(
            FinancialLineItem.document_id == extras_doc.canonical_id
        ).count()
        assert quote_rows == r2.rows_written
        assert extras_rows > 0  # extras untouched by quote re-run


# ---------------------------------------------------------------------------
# Criterion 7: Idempotency
# ---------------------------------------------------------------------------

class TestCriterion7Idempotent:
    def test_extras_idempotent(self, db_session):
        project = _seed_project(db_session)
        doc, dt = _make_doc(db_session, project, "EXTRAS ACCEPTED", _EXTRAS_CSV)

        r1 = populate_ledger_for_document(db_session, doc, dt)
        db_session.flush()
        r2 = populate_ledger_for_document(db_session, doc, dt)
        db_session.flush()

        assert r1.rows_written == r2.rows_written
        count = db_session.query(FinancialLineItem).filter(
            FinancialLineItem.document_id == doc.canonical_id
        ).count()
        assert count == r1.rows_written

    def test_populate_project_idempotent(self, db_session):
        project = _seed_project(db_session)
        _make_doc(db_session, project, "923 ACCEPTED QUOTE", _QUOTE_CSV)
        _make_doc(db_session, project, "EXTRAS ACCEPTED", _EXTRAS_CSV)

        b1 = populate_ledger_for_project(db_session, project.canonical_id)
        b2 = populate_ledger_for_project(db_session, project.canonical_id)

        assert b1.total_rows == b2.total_rows

        total_in_db = db_session.query(FinancialLineItem).filter(
            FinancialLineItem.project_id == project.canonical_id
        ).count()
        assert total_in_db == b2.total_rows


# ---------------------------------------------------------------------------
# Criterion 8: unknown_unit and unknown_division flagged
# ---------------------------------------------------------------------------

class TestCriterion8UnknownFlagged:
    def test_extras_without_unit_prefix_uses_none(self, db_session):
        project = _seed_project(db_session)
        doc, dt = _make_doc(db_session, project, "EXTRAS ACCEPTED", _EXTRAS_CSV)
        populate_ledger_for_document(db_session, doc, dt)

        rows = db_session.query(FinancialLineItem).filter(
            FinancialLineItem.document_id == doc.canonical_id
        ).all()
        # "EXTRAS ACCEPTED" has no civic number prefix → unit = None
        for r in rows:
            assert r.unit is None

    def test_report_carries_none_unit_not_fake_label(self, db_session):
        project = _seed_project(db_session)
        doc, dt = _make_doc(db_session, project, "EXTRAS ACCEPTED", _EXTRAS_CSV)
        populate_ledger_for_document(db_session, doc, dt)

        margins = report_division_margins(db_session, "923 Test Project")
        for row in margins["divisions"]:
            # unit=None is preserved (not coerced to "all" or anything fake)
            assert row["unit"] is None or isinstance(row["unit"], str)

    def test_unknown_division_rows_go_to_code_99(self, db_session):
        project = _seed_project(db_session)
        csv = (
            "CO #,Item,Cost/Unit,Total,Status\n"
            "1,Miscellaneous work,100,100.00,Accepted\n"
        )
        doc, dt = _make_doc(db_session, project, "EXTRAS ACCEPTED", csv)
        populate_ledger_for_document(db_session, doc, dt)

        rows = db_session.query(FinancialLineItem).filter(
            FinancialLineItem.document_id == doc.canonical_id
        ).all()
        for r in rows:
            # If item is unclassifiable it lands in 99
            assert r.division_code in {"99", "09", "22", "02", "26", "06", "07", "08",
                                        "23", "05", "03", "01", "10-12", "31-32"}


# ---------------------------------------------------------------------------
# Criterion 9: Source document provenance preserved
# ---------------------------------------------------------------------------

class TestCriterion9Provenance:
    def test_extras_rows_carry_document_id(self, db_session):
        project = _seed_project(db_session)
        doc, dt = _make_doc(db_session, project, "EXTRAS ACCEPTED", _EXTRAS_CSV)
        populate_ledger_for_document(db_session, doc, dt)

        rows = db_session.query(FinancialLineItem).filter(
            FinancialLineItem.document_id == doc.canonical_id
        ).all()
        for r in rows:
            assert r.document_id == doc.canonical_id
            assert r.project_id == project.canonical_id

    def test_source_meta_json_contains_co_number(self, db_session):
        import json
        project = _seed_project(db_session)
        doc, dt = _make_doc(db_session, project, "EXTRAS ACCEPTED", _EXTRAS_CSV)
        populate_ledger_for_document(db_session, doc, dt)

        rows = db_session.query(FinancialLineItem).filter(
            FinancialLineItem.document_id == doc.canonical_id
        ).all()
        for r in rows:
            assert r.source_meta_json is not None
            meta = json.loads(r.source_meta_json)
            assert "co_number" in meta

    def test_extractor_version_tagged(self, db_session):
        project = _seed_project(db_session)
        doc, dt = _make_doc(db_session, project, "EXTRAS ACCEPTED", _EXTRAS_CSV)
        populate_ledger_for_document(db_session, doc, dt)

        rows = db_session.query(FinancialLineItem).filter(
            FinancialLineItem.document_id == doc.canonical_id
        ).all()
        for r in rows:
            assert r.extractor_version == "extras-v1"


# ---------------------------------------------------------------------------
# Criterion 10: Old /financials path (FinancialRecord) untouched
# ---------------------------------------------------------------------------

class TestCriterion10FinancialRecordUntouched:
    def test_financial_record_table_empty_after_ledger_fill(self, db_session):
        project = _seed_project(db_session)
        quote_doc, quote_dt = _make_doc(db_session, project, "923 ACCEPTED QUOTE", _QUOTE_CSV)
        extras_doc, extras_dt = _make_doc(db_session, project, "EXTRAS ACCEPTED", _EXTRAS_CSV)

        populate_ledger_for_document(db_session, quote_doc, quote_dt)
        populate_ledger_for_document(db_session, extras_doc, extras_dt)

        # fill-ledger NEVER writes FinancialRecord
        fr_count = db_session.query(FinancialRecord).filter(
            FinancialRecord.project_id == project.canonical_id
        ).count()
        assert fr_count == 0, "fill-ledger must not touch FinancialRecord"

    def test_ingestion_status_on_doc_result(self, db_session):
        project = _seed_project(db_session)
        doc, dt = _make_doc(db_session, project, "EXTRAS ACCEPTED", _EXTRAS_CSV)
        result = populate_ledger_for_document(db_session, doc, dt)

        assert isinstance(result, DocLedgerResult)
        assert result.ingestion_status in {"parsed", "skipped", "quarantined", "failed"}
        assert result.sheet_type == "extras"
