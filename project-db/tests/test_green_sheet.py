"""Phase 6: report_green_sheet -- the read-only budget/quoted/committed/actual
aggregator. Pure read; no ledger mutation, no LLM, no UI.
"""

from __future__ import annotations

import uuid
from decimal import Decimal

import pytest
from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from project_db.ai.green_sheet import report_green_sheet
from project_db.ai.views import report_division_margins
from project_db.db.base import Base
from project_db.db.migrations import ensure_sqlite_schema
from project_db.db.models import (
    BudgetSnapshot,
    BudgetSnapshotLine,
    Client,
    Document,
    FinancialLineItem,
    Organization,
    Project,
    SowPackage,
    SubcontractorQuote,
    Vendor,
)
from project_db.db.models.work import ProjectStatus

# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------


def _make_engine():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    ensure_sqlite_schema(engine)
    return engine


def _make_session(engine):
    return sessionmaker(bind=engine)()


def _project(session, *, name="923-927 Rockland", code="2026001"):
    org = Organization(canonical_id=uuid.uuid4(), name="Org")
    client = Client(canonical_id=uuid.uuid4(), name="Client", organization_id=org.canonical_id)
    session.add_all([org, client])
    session.flush()
    project = Project(
        canonical_id=uuid.uuid4(),
        name=name,
        code=code,
        client_id=client.canonical_id,
        status=ProjectStatus.ACTIVE,
    )
    session.add(project)
    session.flush()
    return project


def _cost_row(
    session,
    project,
    *,
    division_code,
    amount,
    cost_status,
    amount_type="material",
    document_id=None,
    subcontractor_quote_id=None,
):
    row = FinancialLineItem(
        canonical_id=uuid.uuid4(),
        project_id=project.canonical_id,
        document_id=document_id,
        division_code=division_code,
        side="cost",
        amount_type=amount_type,
        status="unknown",
        cost_status=cost_status,
        amount=Decimal(str(amount)),
        currency="CAD",
        source="grid",
        subcontractor_quote_id=subcontractor_quote_id,
    )
    session.add(row)
    return row


def _quote(session, project, *, division_code, status, amount=0):
    q = SubcontractorQuote(
        canonical_id=uuid.uuid4(),
        project_id=project.canonical_id,
        division_code=division_code,
        status=status,
        amount=Decimal(str(amount)),
        currency="CAD",
    )
    session.add(q)
    session.flush()
    return q


def _budget_snapshot(session, project, *, label="v1", lines, created_at=None):
    snap = BudgetSnapshot(canonical_id=uuid.uuid4(), project_id=project.canonical_id, label=label)
    if created_at is not None:
        snap.created_at = created_at
    session.add(snap)
    session.flush()
    for div_code, amount in lines.items():
        session.add(
            BudgetSnapshotLine(
                canonical_id=uuid.uuid4(),
                snapshot_id=snap.canonical_id,
                project_id=project.canonical_id,
                division_code=div_code,
                budget_amount=Decimal(str(amount)),
            )
        )
    session.flush()
    return snap


# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------


class TestSchema:
    def test_fresh_db_has_tables(self):
        engine = _make_engine()
        tables = set(inspect(engine).get_table_names())
        assert "budget_snapshot" in tables
        assert "budget_snapshot_line" in tables

    def test_existing_db_migration_adds_tables(self):
        engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        tables = [
            t
            for n, t in Base.metadata.tables.items()
            if n not in ("budget_snapshot", "budget_snapshot_line")
        ]
        Base.metadata.create_all(engine, tables=tables)
        assert "budget_snapshot" not in set(inspect(engine).get_table_names())

        ensure_sqlite_schema(engine)

        tables_after = set(inspect(engine).get_table_names())
        assert "budget_snapshot" in tables_after
        assert "budget_snapshot_line" in tables_after

    def test_duplicate_division_in_same_snapshot_rejected(self):
        engine = _make_engine()
        s = _make_session(engine)
        project = _project(s)
        snap = BudgetSnapshot(
            canonical_id=uuid.uuid4(), project_id=project.canonical_id, label="v1"
        )
        s.add(snap)
        s.flush()
        s.add(
            BudgetSnapshotLine(
                canonical_id=uuid.uuid4(),
                snapshot_id=snap.canonical_id,
                project_id=project.canonical_id,
                division_code="22",
                budget_amount=Decimal("1000"),
            )
        )
        s.flush()
        s.add(
            BudgetSnapshotLine(
                canonical_id=uuid.uuid4(),
                snapshot_id=snap.canonical_id,
                project_id=project.canonical_id,
                division_code="22",
                budget_amount=Decimal("2000"),
            )
        )
        with pytest.raises(Exception):  # IntegrityError
            s.flush()


# ---------------------------------------------------------------------------
# Core aggregation behavior
# ---------------------------------------------------------------------------


class TestAggregation:
    def test_no_data_returns_empty_divisions(self):
        engine = _make_engine()
        s = _make_session(engine)
        _project(s)
        result = report_green_sheet(s, "923-927 Rockland")
        assert result["divisions"] == []
        assert result["total_budget"] is None

    def test_bad_project_ref(self):
        engine = _make_engine()
        s = _make_session(engine)
        result = report_green_sheet(s, "nonexistent xyz")
        assert "error" in result

    def test_lifecycle_stages_kept_separate_never_summed(self):
        """The core Phase 6 invariant: quoted/committed/actual are separate
        columns, never added together into one 'cost' figure."""
        engine = _make_engine()
        s = _make_session(engine)
        project = _project(s)
        selected = _quote(s, project, division_code="22", status="selected")
        _cost_row(
            s,
            project,
            division_code="22",
            amount=800,
            cost_status="quoted",
            subcontractor_quote_id=selected.canonical_id,
        )
        _cost_row(s, project, division_code="22", amount=500, cost_status="committed")
        _cost_row(s, project, division_code="22", amount=300, cost_status="actual")
        s.flush()

        result = report_green_sheet(s, "923-927 Rockland")
        row = result["divisions"][0]
        assert row["quoted_cost"] == pytest.approx(800.0)
        assert row["committed_cost"] == pytest.approx(500.0)
        assert row["actual_cost"] == pytest.approx(300.0)

    def test_null_cost_status_counts_as_actual(self):
        """Legacy llm-v1 rows (cost_status never set) must still show up as
        actual spend, same allow-list as report_division_margins."""
        engine = _make_engine()
        s = _make_session(engine)
        project = _project(s)
        _cost_row(s, project, division_code="22", amount=1200, cost_status=None)
        s.flush()

        result = report_green_sheet(s, "923-927 Rockland")
        row = result["divisions"][0]
        assert row["actual_cost"] == pytest.approx(1200.0)

    def test_amount_type_total_still_counts_no_material_labour_filter(self):
        """The exact real-data finding: legacy llm-v1 cost rows are almost
        always amount_type='total' with no material/labour split. They must
        NOT be filtered out -- that would silently zero real spend."""
        engine = _make_engine()
        s = _make_session(engine)
        project = _project(s)
        _cost_row(
            s, project, division_code="22", amount=5000, cost_status=None, amount_type="total"
        )
        s.flush()

        result = report_green_sheet(s, "923-927 Rockland")
        row = result["divisions"][0]
        assert row["actual_cost"] == pytest.approx(5000.0)

    def test_unclassified_cost_status_flagged_not_dropped_not_summed(self):
        engine = _make_engine()
        s = _make_session(engine)
        project = _project(s)
        _cost_row(s, project, division_code="22", amount=150, cost_status="estimated")
        s.flush()

        result = report_green_sheet(s, "923-927 Rockland")
        row = result["divisions"][0]
        assert row["unclassified_cost"] == pytest.approx(150.0)
        assert row["actual_cost"] is None
        assert row["quoted_cost"] is None
        assert row["committed_cost"] is None
        assert any("unclassified" in w for w in row["warnings"])

    def test_budget_variance_computed_against_committed_and_actual_not_quoted(self):
        """Variance is budget minus real financial exposure (committed +
        actual). Quoted (pipeline, not yet a commitment) must NOT reduce it --
        that would treat an unselected quote as if it were already spent."""
        engine = _make_engine()
        s = _make_session(engine)
        project = _project(s)
        _budget_snapshot(s, project, lines={"22": 10000})
        selected = _quote(s, project, division_code="22", status="selected")
        _cost_row(
            s,
            project,
            division_code="22",
            amount=8000,
            cost_status="quoted",
            subcontractor_quote_id=selected.canonical_id,
        )
        _cost_row(s, project, division_code="22", amount=1000, cost_status="committed")
        s.flush()

        result = report_green_sheet(s, "923-927 Rockland")
        row = result["divisions"][0]
        assert row["budget_amount"] == pytest.approx(10000.0)
        assert row["quoted_cost"] == pytest.approx(8000.0)  # confirms it landed in the right bucket
        assert row["variance"] == pytest.approx(9000.0)  # 10000 - 1000, quoted excluded

    def test_no_budget_snapshot_leaves_budget_none(self):
        engine = _make_engine()
        s = _make_session(engine)
        project = _project(s)
        _cost_row(s, project, division_code="22", amount=500, cost_status="committed")
        s.flush()

        result = report_green_sheet(s, "923-927 Rockland")
        row = result["divisions"][0]
        assert row["budget_amount"] is None
        assert row["variance"] is None  # can't compute variance without a budget

    def test_most_recent_snapshot_used_by_default(self):
        """Explicit, guaranteed-distinct created_at -- NOT relying on real
        wall-clock timing between two flushes, which can tie on the exact
        same microsecond on a fast machine (reproduced directly; this test
        was flaky for that reason before the fix)."""
        from datetime import datetime

        engine = _make_engine()
        s = _make_session(engine)
        project = _project(s)
        _budget_snapshot(
            s,
            project,
            label="v1",
            lines={"22": 5000},
            created_at=datetime(2026, 1, 1),
        )
        snap2 = _budget_snapshot(
            s,
            project,
            label="v2",
            lines={"22": 7500},
            created_at=datetime(2026, 6, 1),
        )
        s.flush()

        result = report_green_sheet(s, "923-927 Rockland")
        assert result["budget_snapshot_label"] == "v2"
        assert result["budget_snapshot_id"] == str(snap2.canonical_id)

    def test_explicit_snapshot_id_overrides_most_recent(self):
        engine = _make_engine()
        s = _make_session(engine)
        project = _project(s)
        snap1 = _budget_snapshot(s, project, label="v1", lines={"22": 5000})
        s.flush()
        _budget_snapshot(s, project, label="v2", lines={"22": 7500})
        s.flush()

        result = report_green_sheet(s, "923-927 Rockland", snapshot_id=snap1.canonical_id)
        assert result["budget_snapshot_label"] == "v1"
        assert result["divisions"][0]["budget_amount"] == pytest.approx(5000.0)

    def test_package_and_quote_counts(self):
        engine = _make_engine()
        s = _make_session(engine)
        project = _project(s)
        org_vendor = Vendor(canonical_id=uuid.uuid4(), name="V", organization_id=uuid.uuid4())
        # Attach vendor to a real org to satisfy FK.
        org = s.query(Organization).first()
        org_vendor.organization_id = org.canonical_id
        s.add(org_vendor)
        s.flush()
        pkg = SowPackage(
            canonical_id=uuid.uuid4(),
            project_id=project.canonical_id,
            division_code="22",
            trade_name="Plumbing",
            title="22-Plumbing",
            status="draft",
        )
        s.add(pkg)
        s.flush()
        s.add(
            SubcontractorQuote(
                canonical_id=uuid.uuid4(),
                project_id=project.canonical_id,
                package_id=pkg.canonical_id,
                vendor_id=org_vendor.canonical_id,
                division_code="22",
                status="pending",
                amount=1000,
            )
        )
        s.add(
            SubcontractorQuote(
                canonical_id=uuid.uuid4(),
                project_id=project.canonical_id,
                package_id=pkg.canonical_id,
                vendor_id=org_vendor.canonical_id,
                division_code="22",
                status="selected",
                amount=1200,
            )
        )
        s.flush()

        result = report_green_sheet(s, "923-927 Rockland")
        row = result["divisions"][0]
        assert row["package_count"] == 1
        assert row["quote_count"] == 2
        assert row["selected_quote_count"] == 1

    def test_totals_sum_across_divisions(self):
        engine = _make_engine()
        s = _make_session(engine)
        project = _project(s)
        _budget_snapshot(s, project, lines={"09": 3000, "22": 5000})
        _cost_row(s, project, division_code="09", amount=1000, cost_status="committed")
        _cost_row(s, project, division_code="22", amount=2000, cost_status="committed")
        s.flush()

        result = report_green_sheet(s, "923-927 Rockland")
        assert result["total_budget"] == pytest.approx(8000.0)
        assert result["total_committed"] == pytest.approx(3000.0)
        assert result["total_variance"] == pytest.approx(5000.0)

    def test_no_ledger_mutation(self):
        """Pure read: calling the aggregator must not write anything."""
        engine = _make_engine()
        s = _make_session(engine)
        project = _project(s)
        _cost_row(s, project, division_code="22", amount=500, cost_status="quoted")
        s.commit()
        before = s.query(FinancialLineItem).count()

        report_green_sheet(s, "923-927 Rockland")
        report_green_sheet(s, "923-927 Rockland")  # call twice for good measure

        after = s.query(FinancialLineItem).count()
        assert after == before


# ---------------------------------------------------------------------------
# Competing bids: the exact bug the owner flagged. Ingestion writes
# cost_status="quoted" unconditionally for EVERY ingested quote document,
# regardless of that quote's own status -- so a naive sum over cost_status
# alone would silently add up every competing bid as if it were expected
# spend. quoted_cost must reflect the SELECTED quote only.
# ---------------------------------------------------------------------------


class TestCompetingBids:
    def test_three_bids_one_selected_quoted_cost_is_selected_only(self):
        """The exact scenario: 3 subs quote the same package. Only the
        selected one's amount may appear in quoted_cost."""
        engine = _make_engine()
        s = _make_session(engine)
        project = _project(s)
        q_a = _quote(s, project, division_code="22", status="pending", amount=9000)
        q_b = _quote(s, project, division_code="22", status="selected", amount=6800)
        q_c = _quote(s, project, division_code="22", status="recommended", amount=7500)
        _cost_row(
            s,
            project,
            division_code="22",
            amount=9000,
            cost_status="quoted",
            subcontractor_quote_id=q_a.canonical_id,
        )
        _cost_row(
            s,
            project,
            division_code="22",
            amount=6800,
            cost_status="quoted",
            subcontractor_quote_id=q_b.canonical_id,
        )
        _cost_row(
            s,
            project,
            division_code="22",
            amount=7500,
            cost_status="quoted",
            subcontractor_quote_id=q_c.canonical_id,
        )
        s.flush()

        result = report_green_sheet(s, "923-927 Rockland")
        row = result["divisions"][0]
        assert row["quoted_cost"] == pytest.approx(6800.0)  # NOT 9000+6800+7500=23300
        assert row["pending_bids_cost"] == pytest.approx(9000.0 + 7500.0)
        assert row["quote_count"] == 3
        assert row["selected_quote_count"] == 1
        assert any("excluded from quoted_cost" in w for w in row["warnings"])

    def test_rejected_bid_shown_as_count_only_no_dollar_figure(self):
        engine = _make_engine()
        s = _make_session(engine)
        project = _project(s)
        q_rejected = _quote(s, project, division_code="22", status="rejected", amount=15000)
        _cost_row(
            s,
            project,
            division_code="22",
            amount=15000,
            cost_status="quoted",
            subcontractor_quote_id=q_rejected.canonical_id,
        )
        s.flush()

        result = report_green_sheet(s, "923-927 Rockland")
        row = result["divisions"][0]
        assert row["quoted_cost"] is None
        assert row["pending_bids_cost"] is None
        assert row["unclassified_cost"] is None
        assert row["rejected_bid_count"] == 1
        # The 15000 must not surface as a dollar figure anywhere.
        assert 15000.0 not in (row["quoted_cost"], row["pending_bids_cost"], row["actual_cost"])

    def test_no_selected_quote_yet_quoted_cost_is_none_pending_holds_everything(self):
        """Before anyone has selected a quote, quoted_cost must be None (not
        0, not the sum of bids) -- there's no expected-spend figure yet."""
        engine = _make_engine()
        s = _make_session(engine)
        project = _project(s)
        q_a = _quote(s, project, division_code="22", status="pending", amount=9000)
        q_b = _quote(s, project, division_code="22", status="recommended", amount=8500)
        _cost_row(
            s,
            project,
            division_code="22",
            amount=9000,
            cost_status="quoted",
            subcontractor_quote_id=q_a.canonical_id,
        )
        _cost_row(
            s,
            project,
            division_code="22",
            amount=8500,
            cost_status="quoted",
            subcontractor_quote_id=q_b.canonical_id,
        )
        s.flush()

        result = report_green_sheet(s, "923-927 Rockland")
        row = result["divisions"][0]
        assert row["quoted_cost"] is None
        assert row["pending_bids_cost"] == pytest.approx(17500.0)

    def test_quoted_row_with_no_linked_quote_flagged_unclassified(self):
        """Defensive case: a cost_status='quoted' row with no resolvable
        subcontractor_quote_id must be flagged, not guessed into a bucket."""
        engine = _make_engine()
        s = _make_session(engine)
        project = _project(s)
        _cost_row(
            s,
            project,
            division_code="22",
            amount=400,
            cost_status="quoted",
            subcontractor_quote_id=None,
        )
        s.flush()

        result = report_green_sheet(s, "923-927 Rockland")
        row = result["divisions"][0]
        assert row["quoted_cost"] is None
        assert row["unclassified_cost"] == pytest.approx(400.0)
        assert any("unclassified" in w for w in row["warnings"])

    def test_quoted_row_linked_to_already_awarded_quote_flagged_not_guessed(self):
        """Defensive case: a row still cost_status='quoted' whose linked quote
        is already 'awarded' is an inconsistency (PO award should have
        flipped it to 'committed') -- flag it, don't silently count it as
        quoted OR committed."""
        engine = _make_engine()
        s = _make_session(engine)
        project = _project(s)
        q_awarded = _quote(s, project, division_code="22", status="awarded", amount=6800)
        _cost_row(
            s,
            project,
            division_code="22",
            amount=6800,
            cost_status="quoted",
            subcontractor_quote_id=q_awarded.canonical_id,
        )
        s.flush()

        result = report_green_sheet(s, "923-927 Rockland")
        row = result["divisions"][0]
        assert row["quoted_cost"] is None
        assert row["committed_cost"] is None
        assert row["unclassified_cost"] == pytest.approx(6800.0)
        assert any("unclassified" in w for w in row["warnings"])


# ---------------------------------------------------------------------------
# Cross-check against report_division_margins on the SAME synthetic data
# ---------------------------------------------------------------------------


class TestCrossCheckAgainstMargins:
    def test_actual_cost_matches_division_margins_actual_total_cost(self):
        """Both reports read the same allow-list rule. For a division with
        ONLY 'actual'-eligible cost rows (no quoted/committed), the two
        reports' actual-cost figures must agree -- if they diverge, one of
        them has drifted from the shared allow-list rule."""
        engine = _make_engine()
        s = _make_session(engine)
        project = _project(s)
        doc = Document(
            canonical_id=uuid.uuid4(),
            name="invoice.pdf",
            url="https://x",
            project_id=project.canonical_id,
        )
        s.add(doc)
        s.flush()
        _cost_row(
            s,
            project,
            division_code="22",
            amount=800,
            cost_status=None,
            amount_type="total",
            document_id=doc.canonical_id,
        )
        s.flush()

        gs = report_green_sheet(s, "923-927 Rockland")
        margins = report_division_margins(s, "923-927 Rockland")

        gs_actual = gs["divisions"][0]["actual_cost"]
        margins_actual = margins["divisions"][0]["actual_total_cost"]
        assert gs_actual == pytest.approx(margins_actual)
        assert gs_actual == pytest.approx(800.0)


# ---------------------------------------------------------------------------
# Real-DB smoke check (skips cleanly if the real DB isn't present)
# ---------------------------------------------------------------------------


class TestRealDbSmoke:
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

    def test_real_project_actual_cost_matches_margins_report(self, real_session):
        """Runs against a real project known to have only NULL-cost_status
        legacy rows (no Phase 4/5 quoted/committed data exists for it) --
        report_green_sheet's actual_cost total must equal
        report_division_margins' actual_total_cost total exactly."""
        name = "1455 Rue St. Mathieu"
        gs = report_green_sheet(real_session, name)
        margins = report_division_margins(real_session, name)
        if "error" in gs or "error" in margins:
            pytest.skip(f"{name} not resolvable in this checkout's DB")

        gs_total_actual = sum(
            d["actual_cost"] for d in gs["divisions"] if d["actual_cost"] is not None
        )
        margins_total_actual = sum(
            d["actual_total_cost"]
            for d in margins["divisions"]
            if d["actual_total_cost"] is not None
        )
        assert gs_total_actual == pytest.approx(margins_total_actual)
        assert gs_total_actual > 0

    def test_real_rockland_no_budget_snapshot_yet(self, real_session):
        """Rockland has SOW/packages (Phase 3) but no BudgetSnapshot yet --
        the aggregator must show budget_amount=None everywhere, not fabricate
        a number, and must not error."""
        result = report_green_sheet(real_session, "923-927 Rockland")
        assert "error" not in result
        assert result["total_budget"] is None
        for row in result["divisions"]:
            assert row["budget_amount"] is None
            assert row["variance"] is None
