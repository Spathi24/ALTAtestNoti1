"""Web surface for the Financial Command Center (UI Slice U1).

Verifies /projects/{id}/finance renders the money lifecycle from
report_green_sheet, carries an honest provenance badge (mock/live/empty),
shows the tendering breakdown by quote status, states its fixed-cost scope,
honors the feature flag, and is linked from the project detail page.
"""

from __future__ import annotations

import uuid
from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

fastapi = pytest.importorskip("fastapi")
from fastapi.testclient import TestClient

from project_db.db.base import Base
from project_db.db.models import (
    BudgetSnapshot,
    BudgetSnapshotLine,
    Client,
    Organization,
    Project,
    SowItem,
    SowPackage,
    SubcontractorQuote,
    Vendor,
)
from project_db.db.models.finance import FinancialLineItem
from project_db.db.models.work import ProjectStatus


@pytest.fixture
def db_engine():
    engine = create_engine(
        "sqlite:///:memory:",
        future=True,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    yield engine
    engine.dispose()


@pytest.fixture
def patched_session_factory(db_engine, monkeypatch):
    from project_db.db import session as session_mod

    factory = sessionmaker(bind=db_engine, expire_on_commit=False)
    monkeypatch.setattr(session_mod, "_SessionLocal", factory)
    yield factory


@pytest.fixture
def client(patched_session_factory):
    from project_db.web.app import create_app

    return TestClient(create_app())


@pytest.fixture
def mock_project(session, org: Organization):
    """A project whose budget snapshot is flagged mock -> MOCK provenance."""
    c = Client(name="Acme", organization_id=org.canonical_id)
    session.add(c)
    session.flush()
    p = Project(
        name="923 Fin Test",
        code="2026001",
        client_id=c.canonical_id,
        status=ProjectStatus.ACTIVE,
        contract_amount=Decimal("66539.65"),
    )
    session.add(p)
    session.flush()

    snap = BudgetSnapshot(project_id=p.canonical_id, label="v1 (pilot mock)")
    session.add(snap)
    session.flush()
    session.add(
        BudgetSnapshotLine(
            snapshot_id=snap.canonical_id,
            project_id=p.canonical_id,
            division_code="22",
            division_name="Plumbing",
            budget_amount=Decimal("9500.00"),
        )
    )
    pkg = SowPackage(
        project_id=p.canonical_id,
        division_code="22",
        trade_name="Plumbing",
        title="22-Plumbing",
        status="draft",
    )
    session.add(pkg)
    vendor = Vendor(
        canonical_id=uuid.uuid4(), name="Plombert Inc.", organization_id=org.canonical_id
    )
    session.add(vendor)
    session.flush()

    # Real SOW items (covers the Scope-of-Work section render -- the path that
    # hit the Jinja dict-`.items` trap on real Rockland data).
    session.add(
        SowItem(
            project_id=p.canonical_id,
            package_id=pkg.canonical_id,
            item_code="SOW-003",
            description="Rough-in plumbing",
            division_code="22",
            included=True,
        )
    )
    session.add(
        SowItem(
            project_id=p.canonical_id,
            package_id=None,
            item_code="SOW-018",
            description="Permit fees",
            division_code="01",
            included=False,
        )
    )
    session.flush()

    selected = SubcontractorQuote(
        project_id=p.canonical_id,
        package_id=pkg.canonical_id,
        vendor_id=vendor.canonical_id,
        division_code="22",
        status="selected",
        amount=Decimal("6800.00"),
        currency="CAD",
    )
    session.add(selected)
    session.flush()
    session.add(
        FinancialLineItem(
            project_id=p.canonical_id,
            division_code="22",
            side="cost",
            amount_type="material",
            status="unknown",
            cost_status="quoted",
            subcontractor_quote_id=selected.canonical_id,
            amount=Decimal("6800.00"),
            currency="CAD",
            source="grid",
        )
    )
    session.commit()
    return p


@pytest.fixture
def live_project(session, org: Organization):
    """Real (non-mock) budget label -> LIVE provenance."""
    c = Client(name="Gamma", organization_id=org.canonical_id)
    session.add(c)
    session.flush()
    p = Project(
        name="Real Reno", code="2026002", client_id=c.canonical_id, status=ProjectStatus.ACTIVE
    )
    session.add(p)
    session.flush()
    snap = BudgetSnapshot(project_id=p.canonical_id, label="v1")
    session.add(snap)
    session.flush()
    session.add(
        BudgetSnapshotLine(
            snapshot_id=snap.canonical_id,
            project_id=p.canonical_id,
            division_code="22",
            division_name="Plumbing",
            budget_amount=Decimal("5000.00"),
        )
    )
    session.commit()
    return p


@pytest.fixture
def empty_project(session, org: Organization):
    c = Client(name="Beta", organization_id=org.canonical_id)
    session.add(c)
    session.flush()
    p = Project(name="Empty Reno", client_id=c.canonical_id, status=ProjectStatus.ACTIVE)
    session.add(p)
    session.commit()
    return p


class TestFinanceCommandCenter:
    def test_renders_lifecycle_and_mock_badge(self, client, mock_project):
        r = client.get(f"/projects/{mock_project.canonical_id}/finance")
        assert r.status_code == 200
        body = r.text
        assert "Financial Command Center" in body
        assert "MOCK / DEMO DATA" in body  # honest provenance
        assert "9,500" in body  # budget in the flow strip / table
        assert "6,800" in body  # selected quote -> quoted
        # Lifecycle stage labels present.
        for stage in ("Budget", "Quoted", "Committed", "Actual", "Variance"):
            assert stage in body

    def test_scope_of_work_section_renders_items(self, client, mock_project):
        """The Scope-of-Work card must render real SOW items (regression: the
        `row.items` -> dict.items() Jinja trap 500'd on real data)."""
        r = client.get(f"/projects/{mock_project.canonical_id}/finance")
        assert r.status_code == 200
        body = r.text
        assert "Scope of Work" in body
        assert "Rough-in plumbing" in body  # included item
        assert "Permit fees" in body  # excluded item
        assert "change order" in body  # the "outside scope = change order" note

    def test_signed_contract_line_is_honest(self, client, mock_project):
        """The contract figure renders, labelled as the signed contract value --
        NOT as a whole-project total (the project may hold several segments)."""
        r = client.get(f"/projects/{mock_project.canonical_id}/finance")
        assert r.status_code == 200
        body = r.text
        assert "66,539.65" in body
        assert "Signed contract on file" in body
        assert "not necessarily the whole-project total" in body

    def test_tendering_shows_selected_quote(self, client, mock_project):
        r = client.get(f"/projects/{mock_project.canonical_id}/finance")
        body = r.text
        assert "Tendering" in body
        assert "Plombert Inc." in body
        assert "Selected" in body

    def test_states_fixed_cost_scope(self, client, mock_project):
        r = client.get(f"/projects/{mock_project.canonical_id}/finance")
        assert "Fixed-cost side only" in r.text

    def test_live_provenance_when_budget_not_mock(self, client, live_project):
        r = client.get(f"/projects/{live_project.canonical_id}/finance")
        assert r.status_code == 200
        assert "LIVE DATA" in r.text
        assert "MOCK" not in r.text

    def test_empty_project_honest_empty_state(self, client, empty_project):
        r = client.get(f"/projects/{empty_project.canonical_id}/finance")
        assert r.status_code == 200
        body = r.text
        assert "NO FINANCIAL DATA YET" in body
        assert "Nothing to show yet" in body

    def test_404_unknown_project(self, client):
        r = client.get("/projects/00000000-0000-0000-0000-000000000000/finance")
        assert r.status_code == 404

    def test_disabled_when_feature_off(self, client, mock_project, monkeypatch):
        monkeypatch.setenv("PROJECT_DB_FEATURE_FINANCE_HOME", "false")
        r = client.get(f"/projects/{mock_project.canonical_id}/finance")
        assert r.status_code == 404


class TestNavLink:
    def test_project_detail_links_to_finance(self, client, mock_project):
        r = client.get(f"/projects/{mock_project.canonical_id}")
        assert r.status_code == 200
        assert f"/projects/{mock_project.canonical_id}/finance" in r.text
