"""Build 2.3: read-only Financials web panel.

Renders report_project_financials in the browser -- money-type buckets,
two-sided totals, roll-up cross-check, per-document, records with badges.
No mutation routes; pure render of stored data (no API).
"""
from __future__ import annotations

from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

fastapi = pytest.importorskip("fastapi")
from fastapi.testclient import TestClient  # noqa: E402

from project_db.db.base import Base  # noqa: E402
from project_db.db.models import (  # noqa: E402
    Client,
    Document,
    FinancialRecord,
    Organization,
    Project,
)
from project_db.db.models.work import ProjectStatus  # noqa: E402


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
def fin_project(session, org: Organization):
    c = Client(name="Acme", organization_id=org.canonical_id)
    session.add(c)
    session.flush()
    p = Project(name="Test Reno", client_id=c.canonical_id,
                status=ProjectStatus.ACTIVE)
    session.add(p)
    session.flush()
    d1 = Document(name="Geller Quote.xlsx", url="x://1",
                  mime_type="application/pdf", project_id=p.canonical_id)
    d2 = Document(name="Costs.xlsx", url="x://2",
                  mime_type="application/pdf", project_id=p.canonical_id)
    session.add_all([d1, d2])
    session.flush()
    session.add_all([
        FinancialRecord(project_id=p.canonical_id, document_id=d1.canonical_id,
                        direction="client_in", record_kind="total",
                        amount=Decimal("250"), is_rollup=False,
                        amount_verified=True),
        # internal cost sheet -> rollup, excluded from totals
        FinancialRecord(project_id=p.canonical_id, document_id=d2.canonical_id,
                        direction="contractor_out", record_kind="total",
                        amount=Decimal("999"), is_rollup=True,
                        amount_verified=True),
    ])
    session.commit()
    return p


class TestFinancialsPanel:
    def test_renders_buckets_and_excludes_rollup(self, client, fin_project):
        r = client.get(f"/projects/{fin_project.canonical_id}/financials")
        assert r.status_code == 200
        body = r.text
        assert "Financials" in body
        assert "contract_revenue" in body          # money-type bucket
        assert "Roll-up cross-check" in body        # rollup surfaced separately
        # primary client_in total is 250 (Geller); the rollup 999 is excluded.
        assert "250.00" in body

    def test_404_unknown_project(self, client):
        r = client.get("/projects/00000000-0000-0000-0000-000000000000/financials")
        assert r.status_code == 404

    def test_project_detail_links_to_financials(self, client, fin_project):
        r = client.get(f"/projects/{fin_project.canonical_id}")
        assert r.status_code == 200
        assert f"/projects/{fin_project.canonical_id}/financials" in r.text

    def test_panel_is_read_only(self, client, fin_project):
        # No mutation verb on the financials surface.
        url = f"/projects/{fin_project.canonical_id}/financials"
        assert client.post(url).status_code in (404, 405)
        assert client.delete(url).status_code in (404, 405)
