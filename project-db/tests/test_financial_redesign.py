"""Skeleton of the financial redesign (docs/FINANCIAL_REDESIGN.md):
the CSI division vocabulary/classifier + the FinancialLineItem ledger model.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from project_db.ai.financial_divisions import (
    ALL_DIVISION_CODES,
    UNCLASSIFIED,
    classify_division,
    division_by_code,
)
from project_db.db.base import Base
from project_db.db.models import (
    Client,
    FinancialLineItem,
    Organization,
    Project,
)
from project_db.db.models.work import ProjectStatus

# ---------------------------------------------------------------------------
# Division vocabulary + classifier
# ---------------------------------------------------------------------------


class TestClassifyDivision:
    @pytest.mark.parametrize(
        "text,expected",
        [
            ("Plumbing rough-in", "22"),
            ("Plomberie - salle de bain", "22"),
            ("Interior Painting", "09"),
            ("Flooring + sub-flooring", "09"),
            ("Windows and exterior doors", "08"),
            ("Selective Demolition", "02"),
            ("Overhead & Profit", "01"),
            ("Contingency (3%)", "01"),
            ("Electrical wiring", "26"),
            ("Thermopump and semi-split system", "23"),
            ("Carpentry + Millwork", "06"),
            ("Kitchen cabinetry + hardware", "10-12"),
            ("Load-bearing wall replacement", "05"),
        ],
    )
    def test_keyword_classification(self, text, expected):
        assert classify_division(text).code == expected

    def test_unknown_text_is_unclassified(self):
        assert classify_division("miscellaneous blah").code == "99"
        assert classify_division("").code == "99"
        assert classify_division(None).code == "99"

    def test_masterformat_hint_code_wins_over_text(self):
        # Text says plumbing, but the sheet's MasterFormat column says 26.
        d = classify_division("plumbing rough-in", masterformat_hint="26")
        assert d.code == "26"

    def test_hint_formats(self):
        assert classify_division("x", masterformat_hint="Division 22").code == "22"
        assert classify_division("x", masterformat_hint="09 90 00").code == "09"
        assert classify_division("x", masterformat_hint="230000").code == "23"

    def test_range_member_code_resolves(self):
        # CSI 10, 11, 12 all collapse to the 10-12 bucket.
        assert classify_division("x", masterformat_hint="11").code == "10-12"
        assert division_by_code("12").code == "10-12"

    def test_division_by_code_fallback(self):
        assert division_by_code("zzz") is UNCLASSIFIED
        assert division_by_code(None) is UNCLASSIFIED

    def test_all_codes_include_catchall(self):
        assert "99" in ALL_DIVISION_CODES
        assert "22" in ALL_DIVISION_CODES


# ---------------------------------------------------------------------------
# FinancialLineItem model + migration
# ---------------------------------------------------------------------------


@pytest.fixture
def session():
    engine = create_engine(
        "sqlite:///:memory:",
        future=True,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    s = sessionmaker(bind=engine, expire_on_commit=False)()
    yield s
    s.close()
    engine.dispose()


class TestFinancialLineItemModel:
    def test_round_trip(self, session):
        org = Organization(name="Co")
        session.add(org)
        session.flush()
        cli = Client(name="Tania", organization_id=org.canonical_id)
        session.add(cli)
        session.flush()
        proj = Project(
            name="923-927 Rockland", status=ProjectStatus.ACTIVE, client_id=cli.canonical_id
        )
        session.add(proj)
        session.flush()

        row = FinancialLineItem(
            project_id=proj.canonical_id,
            unit="923",
            division_code="22",
            division_name="Plumbing",
            side="revenue",
            amount_type="total",
            status="accepted",
            doc_role="quote",
            description="Plumbing",
            amount=Decimal("8100.00"),
            currency="CAD",
            doc_date=date(2026, 5, 28),
            source="grid",
            quoted_excerpt="Plumbing ... 8,100.00",
            confidence=1.0,
            amount_verified=True,
        )
        session.add(row)
        session.commit()

        got = session.query(FinancialLineItem).one()
        assert got.unit == "923"
        assert got.division_code == "22"
        assert got.side == "revenue"
        assert got.amount == Decimal("8100.00")
        assert got.status == "accepted"

    def test_defaults(self, session):
        row = FinancialLineItem(amount=Decimal("1"))
        session.add(row)
        session.commit()
        got = session.query(FinancialLineItem).one()
        assert got.division_code == "99"
        assert got.side == "unknown"
        assert got.amount_type == "total"
        assert got.status == "unknown"


def test_migration_creates_table_on_blank_db(tmp_path):
    """ensure_sqlite_schema creates financial_line_item on a DB that predates it."""
    from project_db.db.migrations import ensure_sqlite_schema

    db = tmp_path / "old.sqlite"
    engine = create_engine(f"sqlite:///{db}", future=True)
    assert "financial_line_item" not in inspect(engine).get_table_names()
    ensure_sqlite_schema(engine)
    assert "financial_line_item" in inspect(engine).get_table_names()
    engine.dispose()
