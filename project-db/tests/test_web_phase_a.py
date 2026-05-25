"""Phase A: dashboard renders, counts are live, no forbidden routes exist.

Two halves:
  - happy path: hit ``/``, expect 200 + key counts present in body
  - permission boundary: prove the routes we explicitly forbade in v1
    (sync, propose, edit) do NOT exist.  This is a regression net against
    future drift -- if someone adds /sync as a button, the test fails.
"""
from __future__ import annotations

import json
from datetime import date

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

# pytest will skip the entire module if fastapi isn't installed; that lets
# the suite stay green for anyone who hasn't installed the [ui] extra yet.
fastapi = pytest.importorskip("fastapi")
from fastapi.testclient import TestClient  # noqa: E402

from project_db.db.base import Base  # noqa: E402

from project_db.db.models import (  # noqa: E402
    Client,
    Document,
    Organization,
    Project,
    Proposal,
    Task,
)
from project_db.db.models.docs import DocumentText  # noqa: E402
from project_db.db.models.proposals import ProposalStatus  # noqa: E402
from project_db.db.models.work import ProjectStatus, TaskStatus  # noqa: E402


@pytest.fixture
def db_engine():
    """Override conftest's db_engine with a thread-safe in-memory SQLite.

    FastAPI's TestClient dispatches sync routes through a threadpool, so the
    request hits the DB from a different OS thread than the test body wrote
    on.  Default SQLite refuses that (``check_same_thread=True``).  We need
    StaticPool + check_same_thread=False so all threads share one connection
    on one in-memory DB.
    """
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
    """Bind session_scope() to the same in-memory DB the test fixture uses.

    Same pattern as ``tests/test_cli.py`` -- the web routes call
    ``session_scope`` via FastAPI's Depends(db), so we point the cached
    factory at the test engine.
    """
    from project_db.db import session as session_mod

    factory = sessionmaker(bind=db_engine, expire_on_commit=False)
    monkeypatch.setattr(session_mod, "_SessionLocal", factory)
    yield factory


@pytest.fixture
def client(patched_session_factory):
    from project_db.web.app import create_app

    return TestClient(create_app())


@pytest.fixture
def seeded(session, org: Organization):
    """Plant a project, a dated task, a dateless task, a doc with text,
    a doc without text, and one PENDING proposal so the dashboard has
    real numbers to render."""
    client = Client(name="Test Client", organization_id=org.canonical_id)
    session.add(client)
    session.flush()

    project = Project(
        name="Test Project",
        client_id=client.canonical_id,
        status=ProjectStatus.ACTIVE,
    )
    session.add(project)
    session.flush()

    dated = Task(
        project_id=project.canonical_id,
        title="Dated task",
        status=TaskStatus.TODO,
        start_date=date(2026, 6, 1),
        end_date=date(2026, 6, 10),
    )
    dateless = Task(
        project_id=project.canonical_id,
        title="Dateless task",
        status=TaskStatus.TODO,
    )
    session.add_all([dated, dateless])
    session.flush()

    doc_with = Document(
        project_id=project.canonical_id,
        name="contract.pdf",
        mime_type="application/pdf",
        url="drive://fake/contract.pdf",
        is_trashed=False,
    )
    doc_without = Document(
        project_id=project.canonical_id,
        name="photo.heic",
        mime_type="image/heic",
        url="drive://fake/photo.heic",
        is_trashed=False,
    )
    session.add_all([doc_with, doc_without])
    session.flush()

    session.add(DocumentText(
        document_id=doc_with.canonical_id,
        extracted_text="This is the contract text.",
        extraction_method="pdf",
        token_count=6,
    ))

    session.add(Proposal(
        entity_type="Task",
        entity_id=dateless.canonical_id,
        field_name="timeline",
        proposed_value=json.dumps({"start_date": "2026-07-01", "end_date": "2026-07-05"}),
        confidence=0.9,
        status=ProposalStatus.PENDING,
        prompt_version="test-v1",
    ))
    session.commit()
    return project


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


class TestDashboardRenders:
    def test_dashboard_returns_200(self, client, seeded):
        resp = client.get("/")
        assert resp.status_code == 200
        assert "Dashboard" in resp.text

    def test_dashboard_shows_project_count(self, client, seeded):
        resp = client.get("/")
        body = resp.text
        assert 'data-testid="projects-total"' in body
        # Sanity-check the project counter renders the seeded "1"
        import re
        m = re.search(
            r'data-testid="projects-total"[^>]*>\s*(\d+)\s*<', body
        )
        assert m is not None
        assert int(m.group(1)) == 1

    def test_dashboard_shows_dateless_task_count(self, client, seeded):
        resp = client.get("/")
        body = resp.text
        assert 'data-testid="tasks-dateless"' in body
        # 2 tasks total, 1 dateless
        assert 'data-testid="tasks-total"' in body

    def test_dashboard_shows_docs_with_text_count(self, client, seeded):
        resp = client.get("/")
        body = resp.text
        assert 'data-testid="docs-with-text"' in body
        assert 'data-testid="docs-total"' in body

    def test_dashboard_shows_pending_proposal_count(self, client, seeded):
        resp = client.get("/")
        body = resp.text
        assert 'data-testid="proposals-pending"' in body

    def test_dashboard_renders_with_empty_db(self, client):
        """No seed data -- dashboard must still 200, not crash on zero counts."""
        resp = client.get("/")
        assert resp.status_code == 200
        assert "Dashboard" in resp.text


class TestUiViewsService:
    """Direct tests on the service module so derived logic is exercised
    independently of FastAPI / templates."""

    def test_dashboard_summary_empty_db(self, session):
        from project_db.web.ui_views import dashboard_summary

        out = dashboard_summary(session)
        assert out["projects"]["total"] == 0
        assert out["tasks"]["total"] == 0
        assert out["tasks"]["without_dates"] == 0
        assert out["documents"]["total"] == 0
        assert out["documents"]["with_text"] == 0
        assert out["proposals"]["total"] == 0
        assert out["proposals"]["PENDING"] == 0

    def test_dashboard_summary_counts(self, session, seeded):
        from project_db.web.ui_views import dashboard_summary

        out = dashboard_summary(session)
        assert out["projects"]["total"] == 1
        assert out["projects"]["by_status"].get("ACTIVE") == 1
        assert out["tasks"]["total"] == 2
        assert out["tasks"]["without_dates"] == 1
        assert out["documents"]["total"] == 2
        assert out["documents"]["with_text"] == 1
        assert out["proposals"]["PENDING"] == 1
        assert out["proposals"]["total"] == 1

    def test_recent_pending_proposals_returns_only_pending(self, session, seeded):
        from project_db.web.ui_views import recent_pending_proposals

        out = recent_pending_proposals(session)
        assert len(out) == 1
        assert out[0]["status"] == "PENDING"
        assert out[0]["field_name"] == "timeline"


# ---------------------------------------------------------------------------
# Permission boundary -- the forbidden surface
# ---------------------------------------------------------------------------


class TestForbiddenRoutes:
    """v1 is read-mostly.  These routes must NOT exist.  If a future
    change adds one of them by accident, this test fails loud."""

    @pytest.mark.parametrize("path", [
        # No sync via the UI -- syncs are long-running CLI work
        "/sync",
        "/sync/monday",
        "/sync/GOOGLE_DRIVE",
        # No proposal generation in v1 -- LLM tokens must be deliberate
        "/propose",
        "/propose/timelines",
        "/propose/scope",
        # No direct entity edit endpoints
        "/projects/edit",
        "/projects/00000000-0000-0000-0000-000000000000/edit",
        "/tasks/edit",
        "/documents/edit",
        # No raw SQL exec endpoint
        "/db/exec",
        "/db/query",
    ])
    def test_route_does_not_exist(self, client, path):
        resp = client.get(path)
        assert resp.status_code == 404, (
            f"{path} returned {resp.status_code}; this route must not "
            f"exist in v1.  See M5 plan, section 9 (Things explicitly NOT in v1)."
        )

    @pytest.mark.parametrize("path", [
        "/sync", "/propose", "/projects/edit",
        "/proposals/00000000-0000-0000-0000-000000000000/accept",
        "/proposals/00000000-0000-0000-0000-000000000000/reject",
    ])
    def test_post_to_forbidden_or_phase_d_route(self, client, path):
        """Phase D adds accept/reject POST; until then everything mutating 404s
        or 405s.  405 is acceptable -- it means "no POST handler exists for
        this path", which is exactly the property we want to enforce.
        """
        resp = client.post(path)
        assert resp.status_code in (404, 405), (
            f"POST {path} returned {resp.status_code}; expected 404 (no route) "
            f"or 405 (no POST handler).  A mutation route must not exist in v1."
        )


class TestCorsAndHostBinding:
    def test_no_cors_headers_set(self, client):
        """No CORS middleware on purpose.  A cross-origin request should not
        get Access-Control-Allow-Origin back."""
        resp = client.get("/", headers={"Origin": "http://evil.example.com"})
        assert "access-control-allow-origin" not in {
            k.lower() for k in resp.headers.keys()
        }


class TestFooterAndChrome:
    def test_footer_shows_git_sha(self, client):
        resp = client.get("/")
        # git_sha helper returns either a short SHA or 'unknown' -- both fine.
        assert "git" in resp.text.lower()

    def test_nav_links_present(self, client):
        resp = client.get("/")
        for href in ("/projects", "/proposals", "/doctor"):
            assert f'href="{href}"' in resp.text


class TestDeps:
    def test_git_sha_never_raises(self):
        """Even in a non-git checkout, git_sha must return a string."""
        from project_db.web.deps import git_sha
        git_sha.cache_clear()
        sha = git_sha()
        assert isinstance(sha, str)
        assert sha  # non-empty

    def test_db_path_returns_string(self, monkeypatch):
        from project_db.web import deps

        deps.db_path.cache_clear()
        monkeypatch.setenv("PROJECT_DB_URL", "sqlite:///:memory:")
        assert deps.db_path() == "sqlite:///:memory:"
        deps.db_path.cache_clear()
