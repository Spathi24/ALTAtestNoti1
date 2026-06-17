"""Phase 1d: report_ledger_health -- per-document audit/review surface.

Verifies the deterministic recommended_action mapping, the summary counts, the
attention-first sort order, idempotency, and the empty-extraction path. All
fixtures are synthetic (no real client data); no LLM.
"""

from __future__ import annotations

import uuid
from datetime import datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from project_db.ai.views import report_ledger_health
from project_db.db.base import Base
from project_db.db.models import Client, Organization, Project
from project_db.db.models.docs import Document, DocumentText
from project_db.db.models.finance import FinancialLineItem
from project_db.db.models.work import ProjectStatus

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

_QUOTE_OK = """\
,ESTIMATE,,,,
Description,Notes/ Master Format values,, Material Amount (CAD),Labour Amount (CAD),Total Amount (CAD)
Demolition,Div. 02,,,,"$1,000.00"
    Demo scope,02 41 00,,$400.00,$600.00,
Plumbing,Div. 22,,,,"$500.00"
    Rough-in,22 11 16,,$500.00,,
,,,,Pre-Tax total,"$1,500.00"
"""

_QUOTE_RECON_FAIL = """\
,ESTIMATE,,,,
Description,Notes/ Master Format values,, Material Amount (CAD),Labour Amount (CAD),Total Amount (CAD)
Demolition,Div. 02,,,,"$1,000.00"
Plumbing,Div. 22,,,,"$500.00"
,,,,Pre-Tax total,"$2,000.00"
"""

_JOBCOST = """\
MATERIAL SPENDING,,,,
Phase,Item Description, Cost ,Supplier,Date
Plumbing,PEX," $ 250.00 ",Home Depot,01/15
"""

_ORDER_QTY = """\
Door Order Sheet,,,,
Item,Width,Height,QTY,Unit
Interior door,32,80,3,EA
"""

# Quote-classified ("estimate" banner) but only Description|Notes|Total -- no
# Material column, so parse_financial_grid returns no_header.
_SIMPLE_ESTIMATE = """\
,ESTIMATE,,
Description,Notes,Total Amount (CAD)
Demolition,Div 02,"$1,000.00"
"""

# Non-grid body; classified quote via the ".pdf"-named doc carrying "quote".
_PDF_QUOTE_BODY = "Quote for renovation services\nScope: kitchen\nTotal: $5,000\n"

# A genuinely non-financial doc (meeting notes) -> unknown -> safe skip.
_MEETING_NOTES = "Meeting notes\nDiscussed schedule and next steps.\nNo numbers here.\n"


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


def _seed_project(session) -> Project:
    org = Organization(canonical_id=uuid.uuid4(), name="Test Org")
    client = Client(canonical_id=uuid.uuid4(), name="Test Client", organization_id=org.canonical_id)
    project = Project(
        canonical_id=uuid.uuid4(),
        name="923 Test Project",
        status=ProjectStatus.ACTIVE,
        client_id=client.canonical_id,
    )
    session.add_all([org, client, project])
    session.flush()
    return project


def _make_doc(session, project, name: str, text: str | None) -> Document:
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
    return doc


def _by_name(report: dict, fragment: str) -> dict:
    for d in report["documents"]:
        if fragment.lower() in d["document"].lower():
            return d
    raise AssertionError(f"no audit row for {fragment!r}")


# ---------------------------------------------------------------------------
# Basic resolution
# ---------------------------------------------------------------------------


class TestBasics:
    def test_bad_project_ref(self, db_session):
        result = report_ledger_health(db_session, "nonexistent xyz")
        assert "error" in result

    def test_empty_project_has_no_docs(self, db_session):
        _seed_project(db_session)
        result = report_ledger_health(db_session, "923 Test Project")
        assert result["documents"] == []
        assert result["document_count"] == 0
        assert result["rows_written"] == 0


# ---------------------------------------------------------------------------
# recommended_action mapping
# ---------------------------------------------------------------------------


class TestRecommendedAction:
    def test_ok_quote(self, db_session):
        project = _seed_project(db_session)
        _make_doc(db_session, project, "923 ACCEPTED QUOTE", _QUOTE_OK)
        report = report_ledger_health(db_session, "923 Test Project")
        row = _by_name(report, "ACCEPTED QUOTE")
        assert row["recommended_action"] == "ok"
        assert row["ingestion_status"] == "parsed"
        assert row["rows_written"] > 0
        assert row["reconcile_ok"] is True

    def test_reconcile_fail(self, db_session):
        project = _seed_project(db_session)
        _make_doc(db_session, project, "923 QUOTE", _QUOTE_RECON_FAIL)
        report = report_ledger_health(db_session, "923 Test Project")
        row = _by_name(report, "923 QUOTE")
        assert row["recommended_action"] == "review_reconcile_fail"
        assert row["reconcile_ok"] is False
        # stated 2000, div 1500, diff 500
        assert row["stated_total"] == pytest.approx(2000.0)
        assert row["division_total"] == pytest.approx(1500.0)
        assert row["difference"] == pytest.approx(500.0)

    def test_job_cost_unsupported(self, db_session):
        project = _seed_project(db_session)
        _make_doc(db_session, project, "JOB COSTING", _JOBCOST)
        report = report_ledger_health(db_session, "923 Test Project")
        row = _by_name(report, "JOB COSTING")
        assert row["recommended_action"] == "unsupported_job_cost"
        assert row["rows_written"] == 0

    def test_order_quantities_safe_skip(self, db_session):
        project = _seed_project(db_session)
        _make_doc(db_session, project, "Door Order Sheet", _ORDER_QTY)
        report = report_ledger_health(db_session, "923 Test Project")
        row = _by_name(report, "Door Order")
        assert row["recommended_action"] == "safe_nonfinancial_skip"

    def test_meeting_notes_safe_skip(self, db_session):
        project = _seed_project(db_session)
        _make_doc(db_session, project, "Site Meeting Notes", _MEETING_NOTES)
        report = report_ledger_health(db_session, "923 Test Project")
        row = _by_name(report, "Meeting Notes")
        assert row["recommended_action"] == "safe_nonfinancial_skip"
        assert row["classified_type"] == "unknown"

    def test_simple_estimate_unsupported(self, db_session):
        project = _seed_project(db_session)
        # No file extension -> single-column simple estimate.
        _make_doc(db_session, project, "Simple Estimate", _SIMPLE_ESTIMATE)
        report = report_ledger_health(db_session, "923 Test Project")
        row = _by_name(report, "Simple Estimate")
        assert row["recommended_action"] == "unsupported_simple_estimate"
        assert row["classified_type"] == "quote"
        assert row["ingestion_reason"] == "no_header"

    def test_pdf_quote_unsupported(self, db_session):
        project = _seed_project(db_session)
        _make_doc(db_session, project, "Subcontractor Quote.pdf", _PDF_QUOTE_BODY)
        report = report_ledger_health(db_session, "923 Test Project")
        row = _by_name(report, "Subcontractor Quote")
        assert row["recommended_action"] == "unsupported_pdf_quote"

    def test_empty_extraction(self, db_session):
        project = _seed_project(db_session)
        _make_doc(db_session, project, "923 QUOTE (empty).pdf", "")
        report = report_ledger_health(db_session, "923 Test Project")
        row = _by_name(report, "empty")
        # A TEXTUAL doc with no extracted text -> re-run extract-content.
        assert row["recommended_action"] == "empty_extraction"
        assert row["ingestion_reason"] == "empty_extraction"
        assert row["rows_written"] == 0

    def test_empty_photo_is_safe_skip_not_empty_extraction(self, db_session):
        project = _seed_project(db_session)
        # A photo with no text is EXPECTED -- must not say "re-run extract-content".
        _make_doc(db_session, project, "IMG_0473.jpeg", "")
        _make_doc(db_session, project, "Screenshot.jfif", "")
        report = report_ledger_health(db_session, "923 Test Project")
        for frag in ("IMG_0473", "Screenshot"):
            row = _by_name(report, frag)
            assert row["recommended_action"] == "safe_nonfinancial_skip"
            assert row["ingestion_reason"] == "non_textual_image"


# ---------------------------------------------------------------------------
# Summary + ordering + idempotency
# ---------------------------------------------------------------------------


class TestSummaryAndOrdering:
    def _seed_mixed(self, db_session):
        project = _seed_project(db_session)
        _make_doc(db_session, project, "923 ACCEPTED QUOTE", _QUOTE_OK)
        _make_doc(db_session, project, "923 QUOTE (recon fail)", _QUOTE_RECON_FAIL)
        _make_doc(db_session, project, "JOB COSTING", _JOBCOST)
        _make_doc(db_session, project, "Site Meeting Notes", _MEETING_NOTES)
        return project

    def test_counts(self, db_session):
        self._seed_mixed(db_session)
        report = report_ledger_health(db_session, "923 Test Project")
        assert report["document_count"] == 4
        assert report["parsed_count"] == 2  # both quotes parse
        assert report["needs_review_count"] == 1  # the recon-fail
        assert report["unsupported_count"] == 1  # job cost
        assert report["rows_written"] > 0

    def test_attention_first_ordering(self, db_session):
        self._seed_mixed(db_session)
        report = report_ledger_health(db_session, "923 Test Project")
        actions = [d["recommended_action"] for d in report["documents"]]
        # review_reconcile_fail must come before ok, which comes before safe skip.
        assert actions.index("review_reconcile_fail") < actions.index("ok")
        assert actions.index("ok") < actions.index("safe_nonfinancial_skip")

    def test_action_counts_total_matches_doc_count(self, db_session):
        self._seed_mixed(db_session)
        report = report_ledger_health(db_session, "923 Test Project")
        assert sum(report["action_counts"].values()) == report["document_count"]

    def test_idempotent(self, db_session):
        project = self._seed_mixed(db_session)
        r1 = report_ledger_health(db_session, "923 Test Project")
        r2 = report_ledger_health(db_session, "923 Test Project")
        assert r1["rows_written"] == r2["rows_written"]
        # No duplicate ledger rows from running the audit twice.
        total = (
            db_session.query(FinancialLineItem)
            .filter(FinancialLineItem.project_id == project.canonical_id)
            .count()
        )
        assert total == r1["rows_written"]

    def test_audit_refreshes_ledger(self, db_session):
        """report_ledger_health populates the ledger as a side effect."""
        project = _seed_project(db_session)
        _make_doc(db_session, project, "923 ACCEPTED QUOTE", _QUOTE_OK)
        # Ledger empty before.
        before = (
            db_session.query(FinancialLineItem)
            .filter(FinancialLineItem.project_id == project.canonical_id)
            .count()
        )
        assert before == 0
        report_ledger_health(db_session, "923 Test Project")
        after = (
            db_session.query(FinancialLineItem)
            .filter(FinancialLineItem.project_id == project.canonical_id)
            .count()
        )
        assert after > 0

    def test_trashed_docs_excluded(self, db_session):
        project = _seed_project(db_session)
        doc = Document(
            canonical_id=uuid.uuid4(),
            name="923 ACCEPTED QUOTE",
            url="https://example.com",
            is_trashed=True,
            project_id=project.canonical_id,
        )
        dt = DocumentText(
            document_id=doc.canonical_id,
            extracted_text=_QUOTE_OK,
            extraction_method="csv",
            extracted_at=datetime(2026, 1, 21),
        )
        db_session.add_all([doc, dt])
        db_session.flush()
        report = report_ledger_health(db_session, "923 Test Project")
        assert report["document_count"] == 0
