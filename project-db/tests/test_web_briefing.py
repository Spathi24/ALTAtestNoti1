"""The attention-briefing landing page (`/`).

The dashboard now leads with the ranked briefing (the truths ALTA discovered)
instead of a counts grid (the activity it generated).  These tests pin that the
briefing renders, that items carry their severity + link, that an empty
portfolio reads "All clear", and that the demoted counts grid is still present
(so the Phase-A count assertions keep holding).
"""
from __future__ import annotations

from datetime import date, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

fastapi = pytest.importorskip("fastapi")
from fastapi.testclient import TestClient  # noqa: E402

from project_db.db.base import Base  # noqa: E402
from project_db.db.models.work import TaskStatus  # noqa: E402


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


class TestBriefingLanding:
    def test_empty_portfolio_reads_all_clear(self, client):
        r = client.get("/")
        assert r.status_code == 200
        assert "Dashboard" in r.text            # title block preserved
        assert "Today's briefing" in r.text
        assert "All clear" in r.text
        assert 'data-testid="briefing-item"' not in r.text

    def test_overdue_task_surfaces_as_briefing_item(
        self, client, session, project_factory, task_factory
    ):
        p = project_factory(name="Briefing Reno")
        task_factory(project=p, title="Hang doors", status=TaskStatus.TODO,
                     due_date=date.today() - timedelta(days=10))

        r = client.get("/")
        assert r.status_code == 200
        body = r.text
        assert 'data-testid="briefing-item"' in body
        assert "task(s) overdue" in body
        assert "Briefing Reno" in body
        # Severity pill + a click-through link to the project.
        assert "pill-medium" in body
        assert f"/projects/{p.canonical_id}" in body

    def test_counts_grid_still_present(self, client, session, project_factory):
        """Demoted, but the Phase-A count testids must survive."""
        project_factory(name="Count Proj")
        body = client.get("/").text
        for testid in (
            "projects-total", "tasks-total", "tasks-dateless",
            "docs-total", "docs-with-text", "proposals-total",
            "proposals-pending",
        ):
            assert f'data-testid="{testid}"' in body

    def test_briefing_count_matches_items(
        self, client, session, project_factory, task_factory
    ):
        p = project_factory(name="Multi Proj")
        # 5 overdue -> a single HIGH schedule item.
        for i in range(5):
            task_factory(project=p, title=f"t{i}", status=TaskStatus.TODO,
                         due_date=date.today() - timedelta(days=3))
        body = client.get("/").text
        assert "pill-high" in body
        assert 'data-testid="briefing-count"' in body


class TestUiViewsBriefing:
    def test_attention_briefing_passthrough_shape(self, session, project_factory):
        from project_db.web.ui_views import attention_briefing

        project_factory(name="Shape Proj")
        out = attention_briefing(session)
        # Same shape report_attention_briefing returns.
        assert set(out) >= {
            "generated_on", "item_count", "project_count", "shown_count",
            "truncated", "by_category", "by_severity", "items",
        }
        assert isinstance(out["items"], list)
