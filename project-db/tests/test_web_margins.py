"""Web surface for the division-keyed financial layer: Margins + Ledger Health.

Verifies the two pages render (they were built but never linked into the nav),
that the project detail page now links to both, and that an empty project shows
the "why is this empty" explanation pointing at ledger health.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

fastapi = pytest.importorskip("fastapi")
from fastapi.testclient import TestClient

from project_db.db.base import Base
from project_db.db.models import (
    Client,
    Document,
    Organization,
    Project,
)
from project_db.db.models.docs import DocumentText
from project_db.db.models.finance import FinancialLineItem
from project_db.db.models.work import ProjectStatus

_QUOTE_GRID = """\
,ESTIMATE,,,,
Description,Notes,, Material Amount (CAD),Labour Amount (CAD),Total Amount (CAD)
Plumbing,Div. 22,,,,"$500.00"
    Rough-in,22 11 16,,$500.00,,
,,,,Pre-Tax total,"$500.00"
"""


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
def margin_project(session, org: Organization):
    """A project with one division-ledger revenue row + one parseable quote doc."""
    c = Client(name="Acme", organization_id=org.canonical_id)
    session.add(c)
    session.flush()
    p = Project(name="923 Margins Test", client_id=c.canonical_id, status=ProjectStatus.ACTIVE)
    session.add(p)
    session.flush()

    # Division-ledger revenue row (what the margins page reads).
    session.add(
        FinancialLineItem(
            project_id=p.canonical_id,
            unit="923",
            division_code="22",
            division_name="Plumbing",
            side="revenue",
            amount_type="total",
            amount=Decimal("500.00"),
            status="accepted",
            doc_role="quote",
            source="grid",
        )
    )
    # A parseable quote doc (what ledger-health re-parses and reports).
    doc = Document(
        name="923 ACCEPTED QUOTE",
        url="x://q",
        mime_type="text/csv",
        project_id=p.canonical_id,
        is_trashed=False,
        modified_at_source=datetime(2026, 1, 15),
    )
    session.add(doc)
    session.flush()
    session.add(
        DocumentText(
            document_id=doc.canonical_id,
            extracted_text=_QUOTE_GRID,
            extraction_method="csv",
            extracted_at=datetime(2026, 1, 16),
        )
    )
    session.commit()
    return p


@pytest.fixture
def empty_project(session, org: Organization):
    """A project with no division ledger rows (the common portfolio case)."""
    c = Client(name="Beta", organization_id=org.canonical_id)
    session.add(c)
    session.flush()
    p = Project(name="Empty Reno", client_id=c.canonical_id, status=ProjectStatus.ACTIVE)
    session.add(p)
    session.commit()
    return p


class TestMarginsPage:
    def test_renders_division_revenue(self, client, margin_project):
        r = client.get(f"/projects/{margin_project.canonical_id}/margins")
        assert r.status_code == 200
        body = r.text
        assert "Division Margins" in body
        assert "Plumbing" in body
        assert "500.00" in body
        assert "rev-only" in body  # revenue present, no cost yet

    def test_404_unknown_project(self, client):
        r = client.get("/projects/00000000-0000-0000-0000-000000000000/margins")
        assert r.status_code == 404

    def test_empty_project_explains_why_and_links_to_ledger_health(self, client, empty_project):
        r = client.get(f"/projects/{empty_project.canonical_id}/margins")
        assert r.status_code == 200
        body = r.text
        assert "No division ledger" in body
        assert f"/projects/{empty_project.canonical_id}/ledger-health" in body


class TestLedgerHealthPage:
    def test_renders_audit_for_parsed_quote(self, client, margin_project):
        r = client.get(f"/projects/{margin_project.canonical_id}/ledger-health")
        assert r.status_code == 200
        body = r.text
        assert "Ledger Health" in body
        assert "923 ACCEPTED QUOTE" in body
        assert "parsed" in body  # the quote doc parsed

    def test_404_unknown_project(self, client):
        r = client.get("/projects/00000000-0000-0000-0000-000000000000/ledger-health")
        assert r.status_code == 404

    def test_empty_project_renders(self, client, empty_project):
        r = client.get(f"/projects/{empty_project.canonical_id}/ledger-health")
        assert r.status_code == 200
        assert "Ledger Health" in r.text


class TestNavLinks:
    def test_project_detail_links_to_margins_and_ledger_health(self, client, margin_project):
        r = client.get(f"/projects/{margin_project.canonical_id}")
        assert r.status_code == 200
        body = r.text
        assert f"/projects/{margin_project.canonical_id}/margins" in body
        assert f"/projects/{margin_project.canonical_id}/ledger-health" in body
