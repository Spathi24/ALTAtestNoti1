"""Phase 5: PurchaseOrder award (converting a selected SubcontractorQuote).

Covers: schema (fresh + migrated), the award sequence (quote status flip,
FinancialLineItem cost_status flip, ContractObligation emission), auto
po_number generation, precondition guards (only 'selected' quotes may be
awarded, a duplicate award is rejected), quote history preserved in place
(no delete+reinsert), and that only THIS quote's line items are committed.
"""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from project_db.ai.purchase_order_award import (
    PurchaseOrderAwardError,
    award_purchase_order,
)
from project_db.db.base import Base
from project_db.db.migrations import ensure_sqlite_schema
from project_db.db.models import (
    Client,
    ContractObligation,
    FinancialLineItem,
    Organization,
    Project,
    PurchaseOrder,
    SowItem,
    SowPackage,
    SubcontractorQuote,
    Vendor,
)
from project_db.db.models.finance import PURCHASE_ORDER_STATUSES
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


def _project_pkg_vendor(session, *, code="2026001"):
    org = Organization(canonical_id=uuid.uuid4(), name="Org")
    client = Client(canonical_id=uuid.uuid4(), name="Client", organization_id=org.canonical_id)
    session.add_all([org, client])
    session.flush()
    project = Project(
        canonical_id=uuid.uuid4(), name="923-927 Rockland", code=code,
        client_id=client.canonical_id, status=ProjectStatus.ACTIVE,
    )
    session.add(project)
    session.flush()
    pkg = SowPackage(
        canonical_id=uuid.uuid4(), project_id=project.canonical_id,
        division_code="22", trade_name="Plumbing", title="22-Plumbing", status="draft",
    )
    session.add(pkg)
    session.flush()
    vendor = Vendor(canonical_id=uuid.uuid4(), name="Plombert Inc.", organization_id=org.canonical_id)
    session.add(vendor)
    session.flush()
    return project, pkg, vendor


def _selected_quote_with_lines(session, project, pkg, vendor, *, status="selected", amount=6800, code_prefix="SOW"):
    """A quote + 3 SowItems + 6 cost-side FinancialLineItem rows, mirroring
    Phase 4's real ingest output, without re-running the whole grid parser.
    ``code_prefix`` keeps item_code unique across multiple quotes in the same
    project (item_code uniqueness is project-scoped, per Phase 3)."""
    quote = SubcontractorQuote(
        canonical_id=uuid.uuid4(), project_id=project.canonical_id,
        package_id=pkg.canonical_id, vendor_id=vendor.canonical_id,
        division_code="22", status=status, amount=amount, currency="CAD",
        evidence_span_id=None, source="grid",
    )
    session.add(quote)
    session.flush()

    items = []
    for suffix, mat, lab in (("025", 800, 2400), ("026", 1600, 1200), ("027", 500, 300)):
        si = SowItem(
            canonical_id=uuid.uuid4(), project_id=project.canonical_id,
            package_id=pkg.canonical_id, item_code=f"{code_prefix}-{suffix}", division_code="22",
        )
        session.add(si)
        session.flush()
        for amount_type, amt in (("material", mat), ("labour", lab)):
            fli = FinancialLineItem(
                project_id=project.canonical_id, division_code="22", side="cost",
                amount_type=amount_type, status="unknown", cost_status="quoted",
                purchase_type="vendor", sow_item_id=si.canonical_id,
                subcontractor_quote_id=quote.canonical_id, amount=amt, currency="CAD",
            )
            session.add(fli)
            items.append(fli)
    session.flush()
    return quote, items


# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------

class TestSchema:
    def test_fresh_db_has_purchase_order_table(self):
        engine = _make_engine()
        insp = inspect(engine)
        assert "purchase_order" in set(insp.get_table_names())
        fli_cols = {c["name"] for c in insp.get_columns("financial_line_item")}
        assert "subcontractor_quote_id" in fli_cols

    def test_existing_db_migration_adds_table_and_column(self):
        engine = create_engine(
            "sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool,
        )
        tables = [t for n, t in Base.metadata.tables.items() if n != "purchase_order"]
        Base.metadata.create_all(engine, tables=tables)
        with engine.begin() as conn:
            try:
                conn.execute(text("ALTER TABLE financial_line_item DROP COLUMN subcontractor_quote_id"))
            except Exception:
                pass
        assert "purchase_order" not in set(inspect(engine).get_table_names())

        ensure_sqlite_schema(engine)

        insp = inspect(engine)
        assert "purchase_order" in set(insp.get_table_names())
        fli_cols = {c["name"] for c in insp.get_columns("financial_line_item")}
        assert "subcontractor_quote_id" in fli_cols


# ---------------------------------------------------------------------------
# Award sequence
# ---------------------------------------------------------------------------

class TestAward:
    @pytest.fixture
    def awarded(self):
        engine = _make_engine()
        s = _make_session(engine)
        project, pkg, vendor = _project_pkg_vendor(s)
        quote, items = _selected_quote_with_lines(s, project, pkg, vendor)
        res = award_purchase_order(s, quote)
        s.commit()
        return s, res, project, pkg, vendor, quote, items

    def test_po_created_with_auto_number(self, awarded):
        s, _res, _project, *_ = awarded
        po = s.query(PurchaseOrder).one()
        assert po.po_number == "2026001-001"
        assert po.status in PURCHASE_ORDER_STATUSES
        assert po.status == "awarded"
        assert po.subcontractor_quote_id is not None
        assert po.contract_amount == 6800

    def test_quote_status_flips_to_awarded_in_place(self, awarded):
        s, _res, _project, _pkg, _vendor, quote, _items = awarded
        refreshed = s.query(SubcontractorQuote).filter_by(canonical_id=quote.canonical_id).one()
        assert refreshed.status == "awarded"
        # Same row, not a new one -- quote history (amount/coverage/evidence) intact.
        assert refreshed.canonical_id == quote.canonical_id
        assert refreshed.amount == 6800
        assert s.query(SubcontractorQuote).count() == 1

    def test_cost_rows_committed_in_place_not_reinserted(self, awarded):
        s, res, _project, _pkg, _vendor, quote, items = awarded
        ids_before = {i.canonical_id for i in items}
        rows = s.query(FinancialLineItem).filter_by(subcontractor_quote_id=quote.canonical_id).all()
        assert {r.canonical_id for r in rows} == ids_before  # same rows, not replaced
        assert all(r.cost_status == "committed" for r in rows)
        assert res.lines_committed == 6

    def test_obligation_emitted(self, awarded):
        s, res, _project, _pkg, _vendor, _quote, _items = awarded
        obligations = s.query(ContractObligation).all()
        assert len(obligations) == 1
        ob = obligations[0]
        assert ob.kind == "po_commitment"
        assert ob.direction == "owed_by_us"
        assert ob.amount == 6800
        assert ob.counterparty == "Plombert Inc."
        assert str(ob.canonical_id) == res.obligation_id

    def test_sow_linkage_and_amounts_unchanged_by_award(self, awarded):
        s, _res, _project, _pkg, _vendor, quote, _items = awarded
        rows = s.query(FinancialLineItem).filter_by(subcontractor_quote_id=quote.canonical_id).all()
        amounts = sorted(float(r.amount) for r in rows)
        assert amounts == sorted([800.0, 2400.0, 1600.0, 1200.0, 500.0, 300.0])
        assert all(r.sow_item_id is not None for r in rows)


# ---------------------------------------------------------------------------
# Sequential PO numbering
# ---------------------------------------------------------------------------

class TestPoNumbering:
    def test_second_po_in_project_gets_next_sequence(self):
        engine = _make_engine()
        s = _make_session(engine)
        project, pkg, vendor = _project_pkg_vendor(s)
        q1, _ = _selected_quote_with_lines(s, project, pkg, vendor)
        award_purchase_order(s, q1)
        s.commit()

        pkg2 = SowPackage(
            canonical_id=uuid.uuid4(), project_id=project.canonical_id,
            division_code="09", trade_name="Finishes", title="09-Finishes", status="draft",
        )
        s.add(pkg2)
        s.flush()
        q2, _ = _selected_quote_with_lines(s, project, pkg2, vendor, amount=5000, code_prefix="FIN")
        res2 = award_purchase_order(s, q2)
        s.commit()

        assert res2.po_number == "2026001-002"

    def test_different_projects_do_not_share_sequence(self):
        engine = _make_engine()
        s = _make_session(engine)
        proj_a, pkg_a, vendor_a = _project_pkg_vendor(s, code="2026001")
        proj_b, pkg_b, vendor_b = _project_pkg_vendor(s, code="2026002")
        q_a, _ = _selected_quote_with_lines(s, proj_a, pkg_a, vendor_a)
        q_b, _ = _selected_quote_with_lines(s, proj_b, pkg_b, vendor_b)
        res_a = award_purchase_order(s, q_a)
        res_b = award_purchase_order(s, q_b)
        s.commit()
        assert res_a.po_number == "2026001-001"
        assert res_b.po_number == "2026002-001"


# ---------------------------------------------------------------------------
# Precondition guards
# ---------------------------------------------------------------------------

class TestGuards:
    def test_pending_quote_cannot_be_awarded(self):
        engine = _make_engine()
        s = _make_session(engine)
        project, pkg, vendor = _project_pkg_vendor(s)
        quote, _ = _selected_quote_with_lines(s, project, pkg, vendor, status="pending")
        with pytest.raises(PurchaseOrderAwardError):
            award_purchase_order(s, quote)
        assert s.query(PurchaseOrder).count() == 0

    def test_rejected_quote_cannot_be_awarded(self):
        engine = _make_engine()
        s = _make_session(engine)
        project, pkg, vendor = _project_pkg_vendor(s)
        quote, _ = _selected_quote_with_lines(s, project, pkg, vendor, status="rejected")
        with pytest.raises(PurchaseOrderAwardError):
            award_purchase_order(s, quote)

    def test_already_awarded_quote_cannot_be_re_awarded(self):
        engine = _make_engine()
        s = _make_session(engine)
        project, pkg, vendor = _project_pkg_vendor(s)
        quote, _ = _selected_quote_with_lines(s, project, pkg, vendor)
        award_purchase_order(s, quote)
        s.commit()
        with pytest.raises(PurchaseOrderAwardError):
            award_purchase_order(s, quote)

    def test_duplicate_po_for_same_quote_rejected_at_db_level(self):
        """Even bypassing the status guard, the unique constraint on
        subcontractor_quote_id prevents a second PO for the same quote."""
        engine = _make_engine()
        s = _make_session(engine)
        project, pkg, vendor = _project_pkg_vendor(s)
        quote, _ = _selected_quote_with_lines(s, project, pkg, vendor)
        award_purchase_order(s, quote)
        s.commit()
        quote.status = "selected"  # force back so the ValueError guard doesn't fire first
        s.flush()
        with pytest.raises(IntegrityError):
            award_purchase_order(s, quote)
            s.commit()


# ---------------------------------------------------------------------------
# Isolation: awarding one quote must not touch another quote's rows
# ---------------------------------------------------------------------------

class TestIsolation:
    def test_awarding_one_quote_does_not_commit_another_quotes_rows(self):
        engine = _make_engine()
        s = _make_session(engine)
        project, pkg, vendor = _project_pkg_vendor(s)
        pkg2 = SowPackage(
            canonical_id=uuid.uuid4(), project_id=project.canonical_id,
            division_code="09", trade_name="Finishes", title="09-Finishes", status="draft",
        )
        s.add(pkg2)
        s.flush()
        quote1, _items1 = _selected_quote_with_lines(s, project, pkg, vendor)
        quote2, _items2 = _selected_quote_with_lines(s, project, pkg2, vendor, amount=5000, code_prefix="FIN")

        award_purchase_order(s, quote1)
        s.commit()

        rows1 = s.query(FinancialLineItem).filter_by(subcontractor_quote_id=quote1.canonical_id).all()
        rows2 = s.query(FinancialLineItem).filter_by(subcontractor_quote_id=quote2.canonical_id).all()
        assert all(r.cost_status == "committed" for r in rows1)
        assert all(r.cost_status == "quoted" for r in rows2)  # untouched

        refreshed_q2 = s.query(SubcontractorQuote).filter_by(canonical_id=quote2.canonical_id).one()
        assert refreshed_q2.status == "selected"  # untouched
