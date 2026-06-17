"""End-to-end integration test: extract-content → fill-ledger → division-margins.

Verifies the full pipeline from raw DocumentText through the deterministic
grid parser into the FinancialLineItem ledger, then through report_division_margins.

Uses an in-memory SQLite DB with synthetic fixtures. The quote text matches
the real 923 Rockland shape so the divisions and totals are meaningful.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from project_db.ai.financial_grid_populator import populate_ledger_for_document
from project_db.ai.views import report_division_margins
from project_db.db.base import Base
from project_db.db.models import Client, Organization, Project
from project_db.db.models.docs import Document, DocumentText
from project_db.db.models.finance import FinancialLineItem
from project_db.db.models.work import ProjectStatus

# ---------------------------------------------------------------------------
# Realistic quote fixture matching the 923 Rockland structure.
# Pre-tax total = $9,650.00; divisions: Demolition $1,000, Plumbing $500,
# Carpentry $7,000, General (OHP) $1,150.
# ---------------------------------------------------------------------------
_QUOTE_CSV = """\
,ESTIMATE,,,,
923 Test Ave,,Date,1/1/2026,,
TestCity QC,,Estimate #,T-923,,
,,Client ID,Test Client,,
,,Valid Until,2/28/2026,,
,,,,,
Description,Notes/ Master Format values,, Material Amount (CAD),Labour Amount (CAD),Total Amount (CAD)
,,,,,
Demolition,Div. 02,,,,"$1,000.00"
    Demo scope,02 41 00,,$400.00,$600.00,
Plumbing,Div. 22,,,,"$500.00"
    Rough-in,22 11 16,,$500.00,,
Carpentry,Div. 06,,,,"$7,000.00"
    Framing,06 10 00,,$3,500.00,$3,500.00,
OHP,,,,,"$1,150.00"
,,,,Pre-Tax total,"$9,650.00"
,,,,After-Tax Total,"$11,097.50"
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


def _seed(session):
    """Create org → client → project → document → document_text."""
    org = Organization(canonical_id=uuid.uuid4(), name="Test Org")
    client = Client(canonical_id=uuid.uuid4(), name="Test Client", organization_id=org.canonical_id)
    project = Project(
        canonical_id=uuid.uuid4(),
        name="923 Rockland E2E",
        status=ProjectStatus.ACTIVE,
        client_id=client.canonical_id,
    )
    session.add_all([org, client, project])
    session.flush()

    doc = Document(
        canonical_id=uuid.uuid4(),
        name="923 ACCEPTED QUOTE",
        url="https://example.com/923-quote",
        is_trashed=False,
        project_id=project.canonical_id,
        modified_at_source=datetime(2026, 1, 15),
    )
    session.add(doc)
    session.flush()

    dt = DocumentText(
        document_id=doc.canonical_id,
        extracted_text=_QUOTE_CSV,
        extraction_method="csv",
        extracted_at=datetime(2026, 1, 16),
    )
    session.add(dt)
    session.flush()
    return project, doc, dt


class TestE2EFinancialPipeline:
    def test_fill_ledger_then_division_margins(self, db_session):
        """Full pipeline: DocumentText → ledger rows → margin report."""
        _project, doc, dt = _seed(db_session)

        # Step 1: fill-ledger (populate_ledger_for_document = the inner engine)
        result = populate_ledger_for_document(db_session, doc, dt)

        assert not result.skipped, f"expected quote, got: {result.sheet_type}"
        assert result.sheet_type == "quote"
        assert result.rows_written > 0
        assert result.reconcile_ok is True

        # Pre-tax total in our fixture = $9,650.00
        assert result.grand_total == Decimal("9650.00")

        # Step 2: report_division_margins reads from the ledger
        margins = report_division_margins(db_session, "923 Rockland E2E")

        assert "error" not in margins, margins.get("error")
        assert margins["project"] == "923 Rockland E2E"

        # Total quoted revenue must match the grid pre-tax total (no double-count)
        assert margins["total_quoted_revenue"] == pytest.approx(9650.0, rel=1e-3)
        assert margins["total_actual_cost"] is None  # cost side not yet populated
        assert margins["gross_margin"] is None

        divs = {r["division_code"]: r for r in margins["divisions"]}

        # Demolition (02): $1,000 total row present — line items suppressed
        assert "02" in divs
        assert divs["02"]["quoted_revenue"] == pytest.approx(1000.0)
        assert divs["02"]["status_flag"] == "revenue_only"

        # Plumbing (22): $500
        assert "22" in divs
        assert divs["22"]["quoted_revenue"] == pytest.approx(500.0)

        # Carpentry (06): $7,000
        assert "06" in divs
        assert divs["06"]["quoted_revenue"] == pytest.approx(7000.0)

        # General (01) includes OHP ($1,150) — standalone type, always counted
        assert "01" in divs
        assert divs["01"]["quoted_revenue"] == pytest.approx(1150.0)

        # Source doc name is present on each row
        for row in margins["divisions"]:
            assert "923 ACCEPTED QUOTE" in row["source_docs"]

    def test_idempotent_pipeline(self, db_session):
        """Running fill-ledger twice produces the same margin report."""
        project, doc, dt = _seed(db_session)

        populate_ledger_for_document(db_session, doc, dt)
        db_session.flush()
        populate_ledger_for_document(db_session, doc, dt)  # second run
        db_session.flush()

        # Idempotent: only one set of rows in the DB
        count = (
            db_session.query(FinancialLineItem)
            .filter(FinancialLineItem.project_id == project.canonical_id)
            .count()
        )
        assert count > 0

        margins = report_division_margins(db_session, "923 Rockland E2E")
        # Total must not be doubled
        assert margins["total_quoted_revenue"] == pytest.approx(9650.0, rel=1e-3)

    def test_proposed_doc_contributes_to_ledger(self, db_session):
        """A NOT STARTED quote still lands in the ledger (status=proposed)."""
        org = Organization(canonical_id=uuid.uuid4(), name="Test Org 2")
        client = Client(
            canonical_id=uuid.uuid4(), name="Test Client 2", organization_id=org.canonical_id
        )
        project = Project(
            canonical_id=uuid.uuid4(),
            name="927 Rockland E2E",
            status=ProjectStatus.ACTIVE,
            client_id=client.canonical_id,
        )
        db_session.add_all([org, client, project])
        db_session.flush()

        doc = Document(
            canonical_id=uuid.uuid4(),
            name="_927 QUOTE (NOT STARTED)",
            url="https://example.com/927-quote",
            is_trashed=False,
            project_id=project.canonical_id,
        )
        db_session.add(doc)
        db_session.flush()

        dt = DocumentText(
            document_id=doc.canonical_id,
            extracted_text=_QUOTE_CSV,
            extraction_method="csv",
            extracted_at=datetime(2026, 1, 16),
        )
        db_session.add(dt)
        db_session.flush()

        result = populate_ledger_for_document(db_session, doc, dt)
        assert not result.skipped
        assert result.rows_written > 0

        rows = (
            db_session.query(FinancialLineItem)
            .filter(FinancialLineItem.project_id == project.canonical_id)
            .all()
        )
        assert all(r.status == "proposed" for r in rows)
        assert all(r.unit == "927" for r in rows)

        # Proposed docs still appear in margins (no filter by status at report layer)
        margins = report_division_margins(db_session, "927 Rockland E2E")
        assert "error" not in margins
        assert margins["total_quoted_revenue"] == pytest.approx(9650.0, rel=1e-3)

    def test_trashed_doc_excluded(self, db_session):
        """A trashed document's ledger rows are not written by the project populator."""
        from project_db.ai.financial_grid_populator import populate_ledger_for_project

        org = Organization(canonical_id=uuid.uuid4(), name="Test Org 3")
        client = Client(
            canonical_id=uuid.uuid4(), name="Test Client 3", organization_id=org.canonical_id
        )
        project = Project(
            canonical_id=uuid.uuid4(),
            name="Trashed Doc Project",
            status=ProjectStatus.ACTIVE,
            client_id=client.canonical_id,
        )
        db_session.add_all([org, client, project])
        db_session.flush()

        doc = Document(
            canonical_id=uuid.uuid4(),
            name="923 ACCEPTED QUOTE",
            url="https://example.com/trashed",
            is_trashed=True,  # trashed
            project_id=project.canonical_id,
        )
        db_session.add(doc)
        db_session.flush()

        dt = DocumentText(
            document_id=doc.canonical_id,
            extracted_text=_QUOTE_CSV,
            extraction_method="csv",
            extracted_at=datetime(2026, 1, 16),
        )
        db_session.add(dt)
        db_session.flush()

        batch = populate_ledger_for_project(db_session, project.canonical_id)
        assert batch.total_rows == 0

        margins = report_division_margins(db_session, "Trashed Doc Project")
        assert margins["divisions"] == []
        assert "fill-ledger" in margins["coverage_note"]

    def test_coverage_note_format(self, db_session):
        """Coverage note counts revenue-only divisions correctly."""
        _project, doc, dt = _seed(db_session)
        populate_ledger_for_document(db_session, doc, dt)

        margins = report_division_margins(db_session, "923 Rockland E2E")
        note = margins["coverage_note"]
        # All divisions are revenue-only at this stage
        assert "revenue-only" in note
        assert "division" in note
