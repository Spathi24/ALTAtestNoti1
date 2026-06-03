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
                        doc_role="quote", amount_verified=True),
        # internal cost sheet -> rollup, excluded from totals
        FinancialRecord(project_id=p.canonical_id, document_id=d2.canonical_id,
                        direction="contractor_out", record_kind="total",
                        amount=Decimal("999"), is_rollup=True,
                        amount_verified=True),
    ])
    session.commit()
    return p


class TestMoneyClarity:
    def test_money_glossary_shape(self):
        from project_db.web.ui_views import money_glossary

        g = money_glossary()
        assert [s["authority"] for s in g["sources"]] == [
            "authoritative", "reference", "rough",
        ]
        assert all(s["blurb"].strip() for s in g["sources"])
        assert any(t["key"] == "contract_revenue" for t in g["money_types"])

    def test_financials_panel_marks_authoritative(self, client, fin_project):
        body = client.get(f"/projects/{fin_project.canonical_id}/financials").text
        assert "AUTHORITATIVE" in body
        assert 'data-testid="money-glossary"' in body
        assert "money picture to trust" in body

    def test_project_page_marks_reference_and_links_out(self, client, fin_project):
        body = client.get(f"/projects/{fin_project.canonical_id}").text
        assert "reference" in body
        assert 'data-testid="money-glossary"' in body
        assert f"/projects/{fin_project.canonical_id}/financials" in body


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
        # No mutation verb on the financials VIEW surface (the toggle lives on
        # the document, not the project financials page).
        url = f"/projects/{fin_project.canonical_id}/financials"
        assert client.post(url).status_code in (404, 405)
        assert client.delete(url).status_code in (404, 405)

    def test_confirmed_toggle_updates_total(self, client, fin_project, session):
        from project_db.db.models import Document
        geller = session.query(Document).filter_by(name="Geller Quote.xlsx").one()
        gid = str(geller.canonical_id)

        # By default a QUOTE is excluded: 0 of 1 primary docs counted.
        r0 = client.get(f"/projects/{fin_project.canonical_id}/financials")
        assert r0.status_code == 200
        assert "Confirmed total" in r0.text
        assert "0 of 1" in r0.text

        # Toggle it ON -> the route returns the body fragment, now 1 of 1.
        r1 = client.post(f"/documents/{gid}/financial-status",
                         data={"confirmed": "true"})
        assert r1.status_code == 200
        assert 'id="fin-body"' in r1.text     # body fragment for HTMX swap
        assert "1 of 1" in r1.text

        # Persisted: a fresh GET still shows it counted.
        r2 = client.get(f"/projects/{fin_project.canonical_id}/financials")
        assert "1 of 1" in r2.text

    def test_toggle_bad_document_404(self, client, fin_project):
        r = client.post("/documents/00000000-0000-0000-0000-000000000000/financial-status",
                        data={"confirmed": "true"})
        assert r.status_code == 404
