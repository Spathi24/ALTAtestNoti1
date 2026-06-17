"""Phase 2: report_division_margins -- per-(unit, division) pivot over the
FinancialLineItem ledger.

Tests the double-count deduplication rule, the flag logic, and the output
shape. All fixtures are synthetic (no real client data).
"""

from __future__ import annotations

import uuid
from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from project_db.ai.views import report_division_margins
from project_db.db.base import Base
from project_db.db.models import Client, Organization, Project
from project_db.db.models.docs import Document
from project_db.db.models.finance import FinancialLineItem
from project_db.db.models.work import ProjectStatus


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


def _setup(session):
    org = Organization(canonical_id=uuid.uuid4(), name="Test Org")
    client = Client(canonical_id=uuid.uuid4(), name="Test Client", organization_id=org.canonical_id)
    project = Project(
        canonical_id=uuid.uuid4(),
        name="923 Test",
        status=ProjectStatus.ACTIVE,
        client_id=client.canonical_id,
    )
    # Flush Org → Client → Project first (FK chain); Document references Project.
    session.add_all([org, client, project])
    session.flush()
    doc = Document(
        canonical_id=uuid.uuid4(),
        name="923 ACCEPTED QUOTE",
        url="https://example.com",
        is_trashed=False,
        project_id=project.canonical_id,
    )
    session.add(doc)
    session.flush()
    return project, doc


def _add_row(session, project, doc, *, unit, div_code, side, amount_type, amount):
    row = FinancialLineItem(
        canonical_id=uuid.uuid4(),
        project_id=project.canonical_id,
        document_id=doc.canonical_id,
        unit=unit,
        division_code=div_code,
        division_name=f"Div {div_code}",
        side=side,
        amount_type=amount_type,
        amount=Decimal(str(amount)),
        currency="CAD",
        status="accepted",
        doc_role="quote",
        source="grid",
    )
    session.add(row)


class TestReportDivisionMarginsBasic:
    def test_no_rows_returns_empty(self, db_session):
        project, _ = _setup(db_session)
        result = report_division_margins(db_session, "923 Test")
        assert result["divisions"] == []
        assert "fill-ledger" in result["coverage_note"]

    def test_bad_project_ref(self, db_session):
        result = report_division_margins(db_session, "nonexistent xyz")
        assert "error" in result

    def test_revenue_only_flag(self, db_session):
        project, doc = _setup(db_session)
        _add_row(db_session, project, doc, unit="923", div_code="02", side="revenue",
                 amount_type="total", amount=1000)
        db_session.flush()

        result = report_division_margins(db_session, "923 Test")
        assert len(result["divisions"]) == 1
        row = result["divisions"][0]
        assert row["status_flag"] == "revenue_only"
        assert row["quoted_revenue"] == pytest.approx(1000.0)
        assert row["actual_total_cost"] is None
        assert row["gross_margin"] is None

    def test_ok_flag_when_both_sides(self, db_session):
        project, doc = _setup(db_session)
        _add_row(db_session, project, doc, unit="923", div_code="22", side="revenue",
                 amount_type="total", amount=500)
        _add_row(db_session, project, doc, unit="923", div_code="22", side="cost",
                 amount_type="total", amount=300)
        db_session.flush()

        result = report_division_margins(db_session, "923 Test")
        row = result["divisions"][0]
        assert row["status_flag"] == "ok"
        assert row["quoted_revenue"] == pytest.approx(500.0)
        assert row["actual_total_cost"] == pytest.approx(300.0)
        assert row["gross_margin"] == pytest.approx(200.0)
        assert row["gross_margin_pct"] == pytest.approx(40.0)

    def test_cost_only_flag(self, db_session):
        project, doc = _setup(db_session)
        _add_row(db_session, project, doc, unit="923", div_code="26", side="cost",
                 amount_type="total", amount=800)
        db_session.flush()

        result = report_division_margins(db_session, "923 Test")
        row = result["divisions"][0]
        assert row["status_flag"] == "cost_only"
        assert row["quoted_revenue"] is None
        assert row["actual_total_cost"] == pytest.approx(800.0)

    def test_unknown_division_flag(self, db_session):
        project, doc = _setup(db_session)
        _add_row(db_session, project, doc, unit=None, div_code="99", side="revenue",
                 amount_type="total", amount=200)
        db_session.flush()

        result = report_division_margins(db_session, "923 Test")
        row = result["divisions"][0]
        assert row["status_flag"] == "unknown_division"


class TestDoubleCountRule:
    def test_total_wins_over_line_items(self, db_session):
        """If a division-total row exists, don't also sum the line items."""
        project, doc = _setup(db_session)
        # Section total
        _add_row(db_session, project, doc, unit="923", div_code="02", side="revenue",
                 amount_type="total", amount=1000)
        # Line items (should be IGNORED because the total row is present)
        _add_row(db_session, project, doc, unit="923", div_code="02", side="revenue",
                 amount_type="material", amount=400)
        _add_row(db_session, project, doc, unit="923", div_code="02", side="revenue",
                 amount_type="labour", amount=600)
        db_session.flush()

        result = report_division_margins(db_session, "923 Test")
        row = result["divisions"][0]
        # Must be 1000, NOT 1000 + 400 + 600 = 2000
        assert row["quoted_revenue"] == pytest.approx(1000.0)

    def test_line_items_used_when_no_total(self, db_session):
        project, doc = _setup(db_session)
        _add_row(db_session, project, doc, unit="923", div_code="09", side="revenue",
                 amount_type="material", amount=300)
        _add_row(db_session, project, doc, unit="923", div_code="09", side="revenue",
                 amount_type="labour", amount=200)
        db_session.flush()

        result = report_division_margins(db_session, "923 Test")
        row = result["divisions"][0]
        assert row["quoted_revenue"] == pytest.approx(500.0)

    def test_markup_always_counted(self, db_session):
        """Markup/contingency rows are standalone -- always included."""
        project, doc = _setup(db_session)
        # A section total
        _add_row(db_session, project, doc, unit="923", div_code="01", side="revenue",
                 amount_type="markup", amount=500)
        db_session.flush()

        result = report_division_margins(db_session, "923 Test")
        row = result["divisions"][0]
        assert row["quoted_revenue"] == pytest.approx(500.0)


class TestProjectTotals:
    def test_total_quoted_revenue(self, db_session):
        project, doc = _setup(db_session)
        _add_row(db_session, project, doc, unit="923", div_code="02", side="revenue",
                 amount_type="total", amount=1000)
        _add_row(db_session, project, doc, unit="923", div_code="22", side="revenue",
                 amount_type="total", amount=500)
        db_session.flush()

        result = report_division_margins(db_session, "923 Test")
        assert result["total_quoted_revenue"] == pytest.approx(1500.0)
        assert result["total_actual_cost"] is None  # no cost data
        assert result["gross_margin"] is None

    def test_gross_margin_when_both_sides(self, db_session):
        project, doc = _setup(db_session)
        _add_row(db_session, project, doc, unit="923", div_code="02", side="revenue",
                 amount_type="total", amount=1000)
        _add_row(db_session, project, doc, unit="923", div_code="02", side="cost",
                 amount_type="total", amount=700)
        db_session.flush()

        result = report_division_margins(db_session, "923 Test")
        assert result["gross_margin"] == pytest.approx(300.0)

    def test_source_docs_included(self, db_session):
        project, doc = _setup(db_session)
        _add_row(db_session, project, doc, unit="923", div_code="02", side="revenue",
                 amount_type="total", amount=1000)
        db_session.flush()

        result = report_division_margins(db_session, "923 Test")
        row = result["divisions"][0]
        assert "923 ACCEPTED QUOTE" in row["source_docs"]

    def test_coverage_note_mentions_revenue_only_count(self, db_session):
        project, doc = _setup(db_session)
        _add_row(db_session, project, doc, unit="923", div_code="02", side="revenue",
                 amount_type="total", amount=1000)
        db_session.flush()

        result = report_division_margins(db_session, "923 Test")
        assert "1 division" in result["coverage_note"]
        assert "revenue-only" in result["coverage_note"]
