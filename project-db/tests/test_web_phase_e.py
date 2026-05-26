"""Phase E -- DB inspector + raw JSON panels + footer polish + offline assets.

Coverage:
  - /db lists every Base.metadata table with row counts
  - /db/{table} shows top-N rows; 404 on unknown table
  - /db/{table}/edit, /db/exec, /db/query etc. must NOT exist
  - raw-JSON <details> panels render on project + document detail
  - vendored static assets are served from /static (no CDN dependency)
  - footer shows version + git SHA + uptime + db path
"""
from __future__ import annotations

from datetime import date

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
    Organization,
    Project,
    Task,
)
from project_db.db.models.work import ProjectStatus, TaskStatus  # noqa: E402


@pytest.fixture
def db_engine():
    engine = create_engine(
        "sqlite:///:memory:", future=True,
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
def seeded(session, org: Organization):
    """One project + task + doc so /db/project, /db/task, /db/document
    have something to display."""
    c = Client(name="Acme", organization_id=org.canonical_id)
    session.add(c)
    session.flush()
    project = Project(
        name="P", client_id=c.canonical_id, status=ProjectStatus.ACTIVE,
    )
    session.add(project)
    session.flush()
    task = Task(
        project_id=project.canonical_id,
        title="T",
        status=TaskStatus.TODO,
        start_date=date(2026, 6, 1),
    )
    doc = Document(
        project_id=project.canonical_id,
        name="d.pdf",
        mime_type="application/pdf",
        url="drive://x",
        is_trashed=False,
    )
    session.add_all([task, doc])
    session.commit()
    return {"project": project, "task": task, "doc": doc}


# ---------------------------------------------------------------------------
# DB inspector
# ---------------------------------------------------------------------------


class TestDbIndex:
    def test_renders(self, client, seeded):
        resp = client.get("/db")
        assert resp.status_code == 200
        body = resp.text
        assert "DB inspector" in body
        # Core tables must appear
        assert "project" in body
        assert "task" in body
        assert "document" in body
        # Each row carries the testid
        assert 'data-testid="db-row"' in body

    def test_each_row_has_a_count(self, client, seeded):
        from project_db.web.ui_views import db_table_index
        from project_db.db.base import Base
        from sqlalchemy.orm import Session as _S

        # The service function returns one row per registered table.
        # Pull a fresh session (the client fixture pinned the factory).
        from project_db.db import session_scope
        with session_scope() as s:
            rows = db_table_index(s)

        names = {r["name"] for r in rows}
        # Sanity: every table in the metadata is represented.
        assert names >= set(Base.metadata.tables.keys())
        # Counts are integers, not None / negative.
        for r in rows:
            assert isinstance(r["row_count"], int)
            assert r["row_count"] >= 0


class TestDbTable:
    def test_200_with_rows(self, client, seeded):
        resp = client.get("/db/project")
        assert resp.status_code == 200
        body = resp.text
        assert "<code>project</code>" in body
        # Seeded project name is shown
        assert ">P<" in body or "P</small>" in body

    def test_404_unknown_table(self, client):
        resp = client.get("/db/this_does_not_exist")
        assert resp.status_code == 404

    def test_empty_table_renders(self, client):
        """A table with zero rows must still 200, with a polite message."""
        resp = client.get("/db/invoice")
        assert resp.status_code == 200
        body = resp.text
        assert "empty" in body.lower() or "Table is empty" in body


class TestDbForbiddenSurfaces:
    """The DB inspector is read-only.  Any edit/exec/query/delete
    endpoint must NOT exist -- otherwise this becomes a second product
    surface (per M5 plan review #4)."""

    @pytest.mark.parametrize("path", [
        "/db/exec",
        "/db/query",
        "/db/sql",
        "/db/project/edit",
        "/db/project/delete",
        "/db/project/00000000-0000-0000-0000-000000000000/edit",
        "/db/project/00000000-0000-0000-0000-000000000000/delete",
        "/db/export",
    ])
    def test_forbidden(self, client, path):
        assert client.get(path).status_code in (404, 405)
        assert client.post(path).status_code in (404, 405)


# ---------------------------------------------------------------------------
# Raw JSON panels
# ---------------------------------------------------------------------------


class TestRawJsonPanels:
    def test_project_detail_has_raw_panel(self, client, seeded):
        pid = str(seeded["project"].canonical_id)
        resp = client.get(f"/projects/{pid}")
        assert resp.status_code == 200
        body = resp.text
        assert 'data-testid="raw-json-panel"' in body
        # The panel is collapsed by default -- it uses <details> with no
        # "open" attribute on the wrapper.
        assert "<summary>" in body

    def test_document_detail_has_raw_panel(self, client, seeded):
        did = str(seeded["doc"].canonical_id)
        resp = client.get(f"/documents/{did}")
        assert resp.status_code == 200
        body = resp.text
        assert 'data-testid="raw-json-panel"' in body


# ---------------------------------------------------------------------------
# Footer polish + offline asset serving
# ---------------------------------------------------------------------------


class TestFooter:
    def test_renders_version_git_uptime_db(self, client):
        resp = client.get("/")
        body = resp.text
        for tid in ("app-version", "git-sha", "uptime", "db-path"):
            assert f'data-testid="{tid}"' in body, (
                f"footer must carry data-testid={tid!r}"
            )

    def test_uptime_helper_ticks(self):
        """Sanity: uptime_str returns a non-empty string in human-readable form."""
        from project_db.web.deps import uptime_str
        s = uptime_str()
        assert isinstance(s, str)
        assert s
        # Format must contain a unit (s / m / h / d).
        assert any(u in s for u in ("s", "m", "h", "d"))

    def test_app_version_helper(self):
        from project_db.web.deps import app_version
        v = app_version()
        assert isinstance(v, str)
        assert v  # "0.1.0", or "dev" outside an installed package


class TestVendoredAssets:
    def test_pico_served_locally(self, client):
        resp = client.get("/static/pico.min.css")
        assert resp.status_code == 200
        # Pico's CSS is sizeable -- 80KB+ for v2.
        assert len(resp.content) > 5000

    def test_htmx_served_locally(self, client):
        resp = client.get("/static/htmx.min.js")
        assert resp.status_code == 200
        assert len(resp.content) > 5000
        # The file content contains the htmx export
        assert b"htmx" in resp.content.lower()

    def test_base_template_does_not_reference_cdn(self, client):
        """Per Phase E goal: no CDN dependency, the app must run offline."""
        resp = client.get("/")
        body = resp.text
        # Specifically check for the cdn hostnames that v1 used.
        assert "cdn.jsdelivr.net" not in body, (
            "base.html must not reference jsdelivr CDN -- vendor Pico locally"
        )
        assert "unpkg.com" not in body, (
            "base.html must not reference unpkg CDN -- vendor HTMX locally"
        )
