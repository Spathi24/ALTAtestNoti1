"""Web surface for the ScopeContext / Evidence Inspector (UI Slice U1.5).

Verifies /projects/{id}/scope-contexts renders contexts + their bound
documents, keeps UNRESOLVED (quarantine) visibly distinct from
LEGACY_UNSCOPED, honors the feature flag, and links from the Financial Command
Center. This is the visible-surface companion to SC-1/SC-2
(docs/UI_REFOUNDATION.md "VISIBLE-SURFACE GATE").
"""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

fastapi = pytest.importorskip("fastapi")
from fastapi.testclient import TestClient

from project_db.db.base import Base
from project_db.db.models import Client, Document, Organization, Project, ScopeContext
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
def pilot_like_project(session, org: Organization):
    """A project with 2 contexts (one bound doc each), an unresolved doc, and a
    legacy-unscoped doc -- mirrors the real pilot's SC-2 shape at small scale."""
    c = Client(name="Rockland Client", organization_id=org.canonical_id)
    session.add(c)
    session.flush()
    p = Project(
        name="923-927 Rockland",
        code="2026001",
        client_id=c.canonical_id,
        status=ProjectStatus.ACTIVE,
    )
    session.add(p)
    session.flush()

    ctx_a = ScopeContext(
        project_id=p.canonical_id,
        context_key="923_INTERIOR",
        label="923 Rockland -- Interior",
        kind="unit",
        unit_area="3rd floor",
    )
    ctx_b = ScopeContext(
        project_id=p.canonical_id,
        context_key="927_UNIT",
        label="927 Rockland -- Unit",
    )
    session.add_all([ctx_a, ctx_b])
    session.flush()

    session.add(
        Document(
            name="Final SOW.pdf",
            url="drive://sow",
            project_id=p.canonical_id,
            folder_path="923-927 Rockland/923 Rockland",
            scope_context_id=ctx_a.canonical_id,
            context_resolution_state="RESOLVED",
        )
    )
    session.add(
        Document(
            name="927 QUOTE.xlsx",
            url="drive://927quote",
            project_id=p.canonical_id,
            folder_path="923-927 Rockland/927 ROCKLAND",
            scope_context_id=ctx_b.canonical_id,
            context_resolution_state="RESOLVED",
        )
    )
    session.add(
        Document(
            name="mystery.pdf",
            url="drive://mystery",
            project_id=p.canonical_id,
            folder_path=None,
            context_resolution_state="UNRESOLVED",
        )
    )
    session.add(
        Document(
            name="old invoice.pdf",
            url="drive://old",
            project_id=p.canonical_id,
            context_resolution_state="LEGACY_UNSCOPED",
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


class TestScopeContextInspector:
    def test_renders_contexts_and_bound_documents(self, client, pilot_like_project):
        r = client.get(f"/projects/{pilot_like_project.canonical_id}/scope-contexts")
        assert r.status_code == 200
        body = r.text
        assert "Scope Contexts" in body
        assert "923 Rockland -- Interior" in body
        assert "927 Rockland -- Unit" in body
        assert "Final SOW.pdf" in body
        assert "927 QUOTE.xlsx" in body
        assert "LIVE DATA" in body

    def test_unresolved_distinct_from_legacy_unscoped(self, client, pilot_like_project):
        """The whole point of the two states: quarantine must be visibly
        different from harmless pre-migration legacy documents."""
        r = client.get(f"/projects/{pilot_like_project.canonical_id}/scope-contexts")
        body = r.text
        assert "mystery.pdf" in body  # shown in the Unresolved card
        assert "old invoice.pdf" not in body  # legacy-unscoped is a COUNT, not listed
        assert "Unresolved" in body
        assert "1 document" in body  # unresolved count
        assert "legacy-unscoped" in body.lower()

    def test_empty_project_honest_empty_state(self, client, empty_project):
        r = client.get(f"/projects/{empty_project.canonical_id}/scope-contexts")
        assert r.status_code == 200
        assert "NO SCOPE CONTEXTS YET" in r.text

    def test_404_unknown_project(self, client):
        r = client.get("/projects/00000000-0000-0000-0000-000000000000/scope-contexts")
        assert r.status_code == 404

    def test_disabled_when_feature_off(self, client, pilot_like_project, monkeypatch):
        monkeypatch.setenv("PROJECT_DB_FEATURE_SCOPE_CONTEXT_INSPECTOR", "false")
        r = client.get(f"/projects/{pilot_like_project.canonical_id}/scope-contexts")
        assert r.status_code == 404

    def test_linked_from_finance_page(self, client, pilot_like_project):
        r = client.get(f"/projects/{pilot_like_project.canonical_id}/finance")
        assert r.status_code == 200
        assert f"/projects/{pilot_like_project.canonical_id}/scope-contexts" in r.text
