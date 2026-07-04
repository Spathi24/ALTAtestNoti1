"""Phase 2: report_division_margins -- per-(unit, division) pivot over the
FinancialLineItem ledger.

Tests the double-count deduplication rule, the flag logic, and the output
shape. All fixtures are synthetic (no real client data).
"""

from __future__ import annotations

import uuid
from decimal import Decimal
from typing import ClassVar

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


def _add_row(
    session,
    project,
    doc,
    *,
    unit,
    div_code,
    side,
    amount_type,
    amount,
    status="accepted",
    cost_status=None,
):
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
        status=status,
        cost_status=cost_status,
        doc_role="quote",
        source="grid",
    )
    session.add(row)


class TestReportDivisionMarginsBasic:
    def test_no_rows_returns_empty(self, db_session):
        _project, _ = _setup(db_session)
        result = report_division_margins(db_session, "923 Test")
        assert result["divisions"] == []
        assert "fill-ledger" in result["coverage_note"]

    def test_bad_project_ref(self, db_session):
        result = report_division_margins(db_session, "nonexistent xyz")
        assert "error" in result

    def test_revenue_only_flag(self, db_session):
        project, doc = _setup(db_session)
        _add_row(
            db_session,
            project,
            doc,
            unit="923",
            div_code="02",
            side="revenue",
            amount_type="total",
            amount=1000,
        )
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
        _add_row(
            db_session,
            project,
            doc,
            unit="923",
            div_code="22",
            side="revenue",
            amount_type="total",
            amount=500,
        )
        _add_row(
            db_session,
            project,
            doc,
            unit="923",
            div_code="22",
            side="cost",
            amount_type="total",
            amount=300,
        )
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
        _add_row(
            db_session,
            project,
            doc,
            unit="923",
            div_code="26",
            side="cost",
            amount_type="total",
            amount=800,
        )
        db_session.flush()

        result = report_division_margins(db_session, "923 Test")
        row = result["divisions"][0]
        assert row["status_flag"] == "cost_only"
        assert row["quoted_revenue"] is None
        assert row["actual_total_cost"] == pytest.approx(800.0)

    def test_unknown_division_flag(self, db_session):
        project, doc = _setup(db_session)
        _add_row(
            db_session,
            project,
            doc,
            unit=None,
            div_code="99",
            side="revenue",
            amount_type="total",
            amount=200,
        )
        db_session.flush()

        result = report_division_margins(db_session, "923 Test")
        row = result["divisions"][0]
        assert row["status_flag"] == "unknown_division"


class TestDoubleCountRule:
    def test_total_wins_over_line_items(self, db_session):
        """If a division-total row exists, don't also sum the line items."""
        project, doc = _setup(db_session)
        # Section total
        _add_row(
            db_session,
            project,
            doc,
            unit="923",
            div_code="02",
            side="revenue",
            amount_type="total",
            amount=1000,
        )
        # Line items (should be IGNORED because the total row is present)
        _add_row(
            db_session,
            project,
            doc,
            unit="923",
            div_code="02",
            side="revenue",
            amount_type="material",
            amount=400,
        )
        _add_row(
            db_session,
            project,
            doc,
            unit="923",
            div_code="02",
            side="revenue",
            amount_type="labour",
            amount=600,
        )
        db_session.flush()

        result = report_division_margins(db_session, "923 Test")
        row = result["divisions"][0]
        # Must be 1000, NOT 1000 + 400 + 600 = 2000
        assert row["quoted_revenue"] == pytest.approx(1000.0)

    def test_line_items_used_when_no_total(self, db_session):
        project, doc = _setup(db_session)
        _add_row(
            db_session,
            project,
            doc,
            unit="923",
            div_code="09",
            side="revenue",
            amount_type="material",
            amount=300,
        )
        _add_row(
            db_session,
            project,
            doc,
            unit="923",
            div_code="09",
            side="revenue",
            amount_type="labour",
            amount=200,
        )
        db_session.flush()

        result = report_division_margins(db_session, "923 Test")
        row = result["divisions"][0]
        assert row["quoted_revenue"] == pytest.approx(500.0)

    def test_markup_always_counted(self, db_session):
        """Markup/contingency rows are standalone -- always included."""
        project, doc = _setup(db_session)
        # A section total
        _add_row(
            db_session,
            project,
            doc,
            unit="923",
            div_code="01",
            side="revenue",
            amount_type="markup",
            amount=500,
        )
        db_session.flush()

        result = report_division_margins(db_session, "923 Test")
        row = result["divisions"][0]
        assert row["quoted_revenue"] == pytest.approx(500.0)


class TestProjectTotals:
    def test_total_quoted_revenue(self, db_session):
        project, doc = _setup(db_session)
        _add_row(
            db_session,
            project,
            doc,
            unit="923",
            div_code="02",
            side="revenue",
            amount_type="total",
            amount=1000,
        )
        _add_row(
            db_session,
            project,
            doc,
            unit="923",
            div_code="22",
            side="revenue",
            amount_type="total",
            amount=500,
        )
        db_session.flush()

        result = report_division_margins(db_session, "923 Test")
        assert result["total_quoted_revenue"] == pytest.approx(1500.0)
        assert result["total_actual_cost"] is None  # no cost data
        assert result["gross_margin"] is None

    def test_gross_margin_when_both_sides(self, db_session):
        project, doc = _setup(db_session)
        _add_row(
            db_session,
            project,
            doc,
            unit="923",
            div_code="02",
            side="revenue",
            amount_type="total",
            amount=1000,
        )
        _add_row(
            db_session,
            project,
            doc,
            unit="923",
            div_code="02",
            side="cost",
            amount_type="total",
            amount=700,
        )
        db_session.flush()

        result = report_division_margins(db_session, "923 Test")
        assert result["gross_margin"] == pytest.approx(300.0)

    def test_source_docs_included(self, db_session):
        project, doc = _setup(db_session)
        _add_row(
            db_session,
            project,
            doc,
            unit="923",
            div_code="02",
            side="revenue",
            amount_type="total",
            amount=1000,
        )
        db_session.flush()

        result = report_division_margins(db_session, "923 Test")
        row = result["divisions"][0]
        assert "923 ACCEPTED QUOTE" in row["source_docs"]

    def test_coverage_note_mentions_revenue_only_count(self, db_session):
        project, doc = _setup(db_session)
        _add_row(
            db_session,
            project,
            doc,
            unit="923",
            div_code="02",
            side="revenue",
            amount_type="total",
            amount=1000,
        )
        db_session.flush()

        result = report_division_margins(db_session, "923 Test")
        assert "1 division" in result["coverage_note"]
        assert "revenue-only" in result["coverage_note"]


class TestRevenueStatusGating:
    """Revenue status gates whether a row counts as CONTRACTED money.

    A NOT-STARTED / speculative quote (status='proposed') is pipeline, not money
    actually sold, so it must stay OUT of the margin and be tracked separately.
    A 'superseded' quote was replaced by a newer version and must vanish
    entirely. 'accepted' / 'unknown' / 'actual' all count.  Regression: the LLM
    extractor populated $282k of NOT-STARTED quotes that inflated every margin.
    """

    def test_proposed_excluded_from_contracted_revenue(self, db_session):
        project, doc = _setup(db_session)
        _add_row(
            db_session,
            project,
            doc,
            unit="923",
            div_code="02",
            side="revenue",
            amount_type="total",
            amount=1000,
            status="accepted",
        )
        _add_row(
            db_session,
            project,
            doc,
            unit="927",
            div_code="02",
            side="revenue",
            amount_type="total",
            amount=5000,
            status="proposed",
        )
        db_session.flush()

        result = report_division_margins(db_session, "923 Test")
        # Contracted revenue is the accepted $1000 only -- NOT $6000.
        assert result["total_quoted_revenue"] == pytest.approx(1000.0)
        # Proposed is tracked separately.
        assert result["total_proposed_revenue"] == pytest.approx(5000.0)

    def test_proposed_only_division_flagged_and_kept_out_of_margin(self, db_session):
        project, doc = _setup(db_session)
        _add_row(
            db_session,
            project,
            doc,
            unit="927",
            div_code="09",
            side="revenue",
            amount_type="total",
            amount=4200,
            status="proposed",
        )
        db_session.flush()

        result = report_division_margins(db_session, "923 Test")
        row = result["divisions"][0]
        assert row["status_flag"] == "proposed_only"
        assert row["quoted_revenue"] is None
        assert row["proposed_revenue"] == pytest.approx(4200.0)
        assert result["total_quoted_revenue"] is None

    def test_superseded_excluded_entirely(self, db_session):
        project, doc = _setup(db_session)
        _add_row(
            db_session,
            project,
            doc,
            unit="923",
            div_code="22",
            side="revenue",
            amount_type="total",
            amount=900,
            status="superseded",
        )
        db_session.flush()

        result = report_division_margins(db_session, "923 Test")
        # Superseded row contributes nothing on either side -> no divisions.
        assert result["total_quoted_revenue"] is None
        assert result["total_proposed_revenue"] is None
        assert result["divisions"] == []

    def test_unknown_status_counts_as_revenue(self, db_session):
        """LLM-extracted rows carry status='unknown' -- treat as contracted."""
        project, doc = _setup(db_session)
        _add_row(
            db_session,
            project,
            doc,
            unit="923",
            div_code="22",
            side="revenue",
            amount_type="total",
            amount=750,
            status="unknown",
        )
        db_session.flush()

        result = report_division_margins(db_session, "923 Test")
        assert result["total_quoted_revenue"] == pytest.approx(750.0)
        assert result["total_proposed_revenue"] is None


class TestExtrasAdditiveToQuoteTotal:
    """An extras/change-order 'adjustment' row is scope agreed AFTER the base
    quote, so it must be ADDED to the quote's division total -- never suppressed
    by the total-vs-line-item dedup.  Regression: when the extras doc shared the
    quote's unit + division, the adjustment lost the dedup contest and the money
    silently vanished from the margin report (total showed $500 not $800)."""

    def test_adjustment_added_to_quote_total_same_division(self, db_session):
        project, doc = _setup(db_session)
        # Base quote: Plumbing division total $500.
        _add_row(
            db_session,
            project,
            doc,
            unit="923",
            div_code="22",
            side="revenue",
            amount_type="total",
            amount=500,
        )
        # Extras: a $300 plumbing-fixture adjustment, SAME unit + division.
        _add_row(
            db_session,
            project,
            doc,
            unit="923",
            div_code="22",
            side="revenue",
            amount_type="adjustment",
            amount=300,
        )
        db_session.flush()

        result = report_division_margins(db_session, "923 Test")
        assert len(result["divisions"]) == 1
        row = result["divisions"][0]
        # Must be 500 + 300 = 800, NOT 500 (extras dropped) or 1000 (line items
        # double-counted).
        assert row["quoted_revenue"] == pytest.approx(800.0)
        assert result["total_quoted_revenue"] == pytest.approx(800.0)

    def test_multiple_adjustments_all_counted(self, db_session):
        project, doc = _setup(db_session)
        _add_row(
            db_session,
            project,
            doc,
            unit="923",
            div_code="09",
            side="revenue",
            amount_type="total",
            amount=1000,
        )
        _add_row(
            db_session,
            project,
            doc,
            unit="923",
            div_code="09",
            side="revenue",
            amount_type="adjustment",
            amount=150,
        )
        _add_row(
            db_session,
            project,
            doc,
            unit="923",
            div_code="09",
            side="revenue",
            amount_type="adjustment",
            amount=250,
        )
        db_session.flush()

        result = report_division_margins(db_session, "923 Test")
        row = result["divisions"][0]
        assert row["quoted_revenue"] == pytest.approx(1400.0)

    def test_adjustment_without_quote_total_still_counted(self, db_session):
        project, doc = _setup(db_session)
        _add_row(
            db_session,
            project,
            doc,
            unit="923",
            div_code="26",
            side="revenue",
            amount_type="adjustment",
            amount=400,
        )
        db_session.flush()

        result = report_division_margins(db_session, "923 Test")
        row = result["divisions"][0]
        assert row["quoted_revenue"] == pytest.approx(400.0)


class TestCostStatusAllowList:
    """Checkpoint 2026-07-02: cost rows only count toward actual_*_cost when
    cost_status is NULL (pre-Phase-4/5 legacy) or "actual". quoted/committed/
    estimated/unknown must be excluded, never silently summed as spend."""

    def test_null_cost_status_counts_as_actual(self, db_session):
        """Legacy llm-v1 rows (cost_status never set) always represented real
        spend -- NULL must still count here, or every pre-existing project's
        margins page goes blank."""
        project, doc = _setup(db_session)
        _add_row(
            db_session,
            project,
            doc,
            unit="923",
            div_code="22",
            side="cost",
            amount_type="material",
            amount=800,
            cost_status=None,
        )
        db_session.flush()

        result = report_division_margins(db_session, "923 Test")
        row = result["divisions"][0]
        assert row["actual_material_cost"] == pytest.approx(800.0)
        assert row["pipeline_cost"] is None

    def test_actual_cost_status_counts(self, db_session):
        project, doc = _setup(db_session)
        _add_row(
            db_session,
            project,
            doc,
            unit="923",
            div_code="22",
            side="cost",
            amount_type="labour",
            amount=300,
            cost_status="actual",
        )
        db_session.flush()

        result = report_division_margins(db_session, "923 Test")
        row = result["divisions"][0]
        assert row["actual_labour_cost"] == pytest.approx(300.0)

    def test_quoted_cost_status_excluded_from_actual(self, db_session):
        """The exact bug this fix prevents: a Phase-4 'quoted' cost row must
        NOT show up as actual spend."""
        project, doc = _setup(db_session)
        _add_row(
            db_session,
            project,
            doc,
            unit="923",
            div_code="22",
            side="cost",
            amount_type="material",
            amount=800,
            cost_status="quoted",
        )
        db_session.flush()

        result = report_division_margins(db_session, "923 Test")
        row = result["divisions"][0]
        assert row["actual_material_cost"] is None
        assert row["actual_total_cost"] is None
        assert row["pipeline_cost"] == pytest.approx(800.0)
        assert row["status_flag"] != "ok"  # no actual cost recorded

    def test_committed_cost_status_excluded_from_actual(self, db_session):
        project, doc = _setup(db_session)
        _add_row(
            db_session,
            project,
            doc,
            unit="923",
            div_code="22",
            side="cost",
            amount_type="labour",
            amount=300,
            cost_status="committed",
        )
        db_session.flush()

        result = report_division_margins(db_session, "923 Test")
        row = result["divisions"][0]
        assert row["actual_labour_cost"] is None
        assert row["pipeline_cost"] == pytest.approx(300.0)

    def test_mixed_null_and_quoted_do_not_mix(self, db_session):
        """The exact scenario the audit flagged: a project with BOTH legacy
        NULL cost rows and Phase-4 quoted rows in the same division. Only the
        NULL row is actual; the quoted row is pipeline -- never summed
        together."""
        project, doc = _setup(db_session)
        _add_row(
            db_session,
            project,
            doc,
            unit="923",
            div_code="22",
            side="cost",
            amount_type="material",
            amount=500,
            cost_status=None,
        )
        _add_row(
            db_session,
            project,
            doc,
            unit="923",
            div_code="22",
            side="cost",
            amount_type="material",
            amount=800,
            cost_status="quoted",
        )
        db_session.flush()

        result = report_division_margins(db_session, "923 Test")
        row = result["divisions"][0]
        assert row["actual_material_cost"] == pytest.approx(500.0)  # not 1300
        assert row["pipeline_cost"] == pytest.approx(800.0)
        assert any("excluded" in w for w in row["warnings"])

    def test_unknown_cost_status_excluded(self, db_session):
        project, doc = _setup(db_session)
        _add_row(
            db_session,
            project,
            doc,
            unit="923",
            div_code="22",
            side="cost",
            amount_type="other",
            amount=150,
            cost_status="unknown",
        )
        db_session.flush()

        result = report_division_margins(db_session, "923 Test")
        row = result["divisions"][0]
        assert row["actual_total_cost"] is None
        assert row["pipeline_cost"] == pytest.approx(150.0)


class TestCostStatusRegressionRealProjects:
    """Pins today's REAL numbers for the 6 real projects that currently carry
    side='cost' rows, to prove the allow-list fix is inert today (no project
    yet mixes legacy-NULL and Phase-4/5-tagged cost rows) and only starts
    protecting once mixing would otherwise occur. Skips cleanly if the real
    project_db.sqlite isn't present (e.g. a clean checkout / CI)."""

    _EXPECTED: ClassVar[dict[str, int]] = {
        "1455 Rue St. Mathieu": 43,
        "5768 St-Laurent": 16,
        "6554 Rue Saint Hubert": 8,
        "14805 Notre-Dame Est. No.6": 6,
        "6305 Trans Island": 2,
        "3940 Cote des Neiges": 1,
    }

    @pytest.fixture
    def real_session(self):
        from pathlib import Path

        from project_db.db.session import get_engine

        db_path = Path(__file__).resolve().parents[1] / "project_db.sqlite"
        if not db_path.exists():
            pytest.skip("real project_db.sqlite not present in this checkout")
        engine = get_engine(f"sqlite:///{db_path.as_posix()}")
        SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)
        s = SessionLocal()
        yield s
        s.close()

    def test_all_cost_side_rows_today_are_null_cost_status(self, real_session):
        """Precondition the regression relies on: if this ever fails, a real
        project now has non-NULL cost_status rows and the two tests below stop
        proving what they claim to prove."""
        rows = real_session.query(FinancialLineItem).filter(FinancialLineItem.side == "cost").all()
        assert rows, "expected real side=cost rows in this checkout's DB"
        non_null = [r for r in rows if r.cost_status is not None]
        assert non_null == [], (
            f"{len(non_null)} real cost rows now have a non-NULL cost_status -- "
            "the allow-list fix may now be actively excluding real pipeline cost "
            "from these projects' margins; verify that's expected before trusting "
            "this regression pin."
        )

    def test_real_project_actual_costs_match_pinned_values(self, real_session):
        """actual_total_cost for each of the 6 known projects, pinned to what
        the ledger already summed to before this fix (all rows are NULL
        cost_status today, so the allow-list changes nothing for them)."""
        for name in self._EXPECTED:
            result = report_division_margins(real_session, name)
            assert "error" not in result, f"{name}: {result.get('error')}"
            total_cost = sum(
                d["actual_total_cost"]
                for d in result["divisions"]
                if d["actual_total_cost"] is not None
            )
            # No pin on the exact dollar value (real data, could legitimately
            # change between sessions) -- the invariant this test protects is
            # narrower and load-bearing: with every row still NULL cost_status,
            # NOTHING is excluded as pipeline_cost today.
            pipeline_total = sum(
                d["pipeline_cost"] for d in result["divisions"] if d["pipeline_cost"] is not None
            )
            assert pipeline_total == 0, (
                f"{name}: {pipeline_total} of cost unexpectedly excluded as "
                "pipeline -- expected 0 since all real cost rows are NULL "
                "cost_status today"
            )
            assert total_cost > 0, f"{name}: expected some actual cost, got 0"
