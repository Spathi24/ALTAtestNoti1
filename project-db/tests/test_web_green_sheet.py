"""Web surface for the green sheet (Phase 7 UI slice).

Verifies the /projects/{id}/green-sheet page renders the budget vs quoted vs
committed vs actual pivot from report_green_sheet, keeps competing bids out of
the quoted column, states its fixed-cost-only scope, honors the feature flag,
and is linked from the project detail page.
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
def green_project(session, org: Organization):
    """Rockland-shaped pilot: budget + package + selected & pending quotes +
    committed cost rows -- every green-sheet column lights up."""
    c = Client(name="Acme", organization_id=org.canonical_id)
    session.add(c)
    session.flush()
    p = Project(
        name="923 Green Test", code="2026001", client_id=c.canonical_id, status=ProjectStatus.ACTIVE
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

    selected = SubcontractorQuote(
        project_id=p.canonical_id,
        package_id=pkg.canonical_id,
        vendor_id=vendor.canonical_id,
        division_code="22",
        status="selected",
        amount=Decimal("6800.00"),
        currency="CAD",
    )
    competing = SubcontractorQuote(
        project_id=p.canonical_id,
        package_id=pkg.canonical_id,
        vendor_id=vendor.canonical_id,
        division_code="22",
        status="pending",
        amount=Decimal("9111.00"),
        currency="CAD",
    )
    session.add_all([selected, competing])
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
    session.add(
        FinancialLineItem(
            project_id=p.canonical_id,
            division_code="22",
            side="cost",
            amount_type="material",
            status="unknown",
            cost_status="quoted",
            subcontractor_quote_id=competing.canonical_id,
            amount=Decimal("9111.00"),
            currency="CAD",
            source="grid",
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


class TestGreenSheetPage:
    def test_renders_budget_quoted_and_pending_separately(self, client, green_project):
        r = client.get(f"/projects/{green_project.canonical_id}/green-sheet")
        assert r.status_code == 200
        body = r.text
        assert "Green Sheet" in body
        assert "Plumbing" in body
        assert "9,500.00" in body  # budget line
        assert "6,800.00" in body  # selected quote -> quoted column
        assert "9,111.00" in body  # competing bid -> pending column, visible
        # The competing bid is flagged as excluded from quoted_cost, not summed in.
        assert "excluded from quoted_cost" in body

    def test_states_fixed_cost_scope(self, client, green_project):
        r = client.get(f"/projects/{green_project.canonical_id}/green-sheet")
        assert "Fixed-cost side only" in r.text

    def test_404_unknown_project(self, client):
        r = client.get("/projects/00000000-0000-0000-0000-000000000000/green-sheet")
        assert r.status_code == 404

    def test_empty_project_renders_honest_empty_state(self, client, empty_project):
        r = client.get(f"/projects/{empty_project.canonical_id}/green-sheet")
        assert r.status_code == 200
        body = r.text
        assert "No green-sheet data" in body
        assert "no budget baseline" in body

    def test_disabled_when_feature_off(self, client, green_project, monkeypatch):
        monkeypatch.setenv("PROJECT_DB_FEATURE_GREEN_SHEET", "false")
        r = client.get(f"/projects/{green_project.canonical_id}/green-sheet")
        assert r.status_code == 404


class TestNavLink:
    def test_project_detail_links_to_green_sheet(self, client, green_project):
        r = client.get(f"/projects/{green_project.canonical_id}")
        assert r.status_code == 200
        assert f"/projects/{green_project.canonical_id}/green-sheet" in r.text
