"""Deterministic Gantt SVG (web/gantt.py) + the /projects/{id}/gantt route."""

from __future__ import annotations

from datetime import date

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from project_db.ai.task_graph import build_task_graph
from project_db.db.base import Base
from project_db.db.models import (
    Client,
    Organization,
    Project,
    Task,
    TaskDependency,
)
from project_db.db.models.work import ProjectStatus, TaskStatus
from project_db.web.gantt import render_project_gantt_svg


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


@pytest.fixture
def project(session):
    org = Organization(name="Co")
    session.add(org)
    session.flush()
    cli = Client(name="Owner", organization_id=org.canonical_id)
    session.add(cli)
    session.flush()
    p = Project(name="Rockland", status=ProjectStatus.ACTIVE, client_id=cli.canonical_id)
    session.add(p)
    session.commit()
    return p


def _task(session, project, title, *, label=None, start=None, end=None, parent=None):
    t = Task(
        title=title,
        status=TaskStatus.TODO,
        project_id=project.canonical_id,
        start_date=start,
        end_date=end,
        is_subitem=parent is not None,
        parent_task_id=parent.canonical_id if parent else None,
    )
    t.monday_status_label = label
    session.add(t)
    session.flush()
    return t


class TestGanttSvg:
    def test_empty_project(self, session, project):
        g = build_task_graph(session, project.canonical_id)
        svg = render_project_gantt_svg(g)
        assert svg.startswith("<svg")
        assert "No tasks" in svg

    def test_dated_task_gets_a_bar(self, session, project):
        _task(session, project, "Demo", label="Done", start=date(2026, 6, 1), end=date(2026, 6, 10))
        session.commit()
        g = build_task_graph(session, project.canonical_id)
        svg = render_project_gantt_svg(g, today=date(2026, 6, 5))
        assert svg.startswith("<svg")
        assert "Demo" in svg
        assert "<rect" in svg  # a bar was drawn
        assert "<title>" in svg  # bar tooltip
        # today is in range -> today marker present
        assert "today" in svg

    def test_dependency_draws_connector(self, session, project):
        a = _task(
            session,
            project,
            "Plumbing",
            label="Done",
            start=date(2026, 6, 1),
            end=date(2026, 6, 10),
        )
        b = _task(
            session,
            project,
            "Drywall",
            label="Working on it",
            start=date(2026, 6, 11),
            end=date(2026, 6, 18),
        )
        session.add(
            TaskDependency(predecessor_task_id=a.canonical_id, successor_task_id=b.canonical_id)
        )
        session.commit()
        g = build_task_graph(session, project.canonical_id)
        svg = render_project_gantt_svg(g)
        # The dependency connector uses the arrow marker.
        assert "dep-arrow" in svg
        assert 'marker-end="url(#dep-arrow)"' in svg

    def test_subitem_is_indented(self, session, project):
        parent = _task(session, project, "Phase", start=date(2026, 6, 1), end=date(2026, 6, 20))
        _task(session, project, "Step", parent=parent, start=date(2026, 6, 2), end=date(2026, 6, 5))
        session.commit()
        g = build_task_graph(session, project.canonical_id)
        svg = render_project_gantt_svg(g)
        assert "Phase" in svg and "Step" in svg

    def test_undated_task_marked(self, session, project):
        _task(session, project, "Dated", start=date(2026, 6, 1), end=date(2026, 6, 5))
        _task(session, project, "Undated")  # no dates
        session.commit()
        g = build_task_graph(session, project.canonical_id)
        svg = render_project_gantt_svg(g)
        assert "no dates" in svg

    def test_title_is_escaped(self, session, project):
        _task(session, project, "A & B <x>", start=date(2026, 6, 1), end=date(2026, 6, 5))
        session.commit()
        g = build_task_graph(session, project.canonical_id)
        svg = render_project_gantt_svg(g)
        assert "&amp;" in svg
        assert "<x>" not in svg  # angle brackets escaped, not injected

    def test_text_is_theme_adaptive(self, session, project):
        """Labels/axis use currentColor so they read on light AND dark themes
        (regression guard: a hardcoded dark fill is invisible on Pico dark)."""
        _task(session, project, "Demo", start=date(2026, 6, 1), end=date(2026, 6, 5))
        session.commit()
        g = build_task_graph(session, project.canonical_id)
        svg = render_project_gantt_svg(g)
        assert "currentColor" in svg
        # No near-black text fill that would vanish on a dark background.
        assert 'fill="#222"' not in svg and 'fill="#555"' not in svg


# ---------------------------------------------------------------------------
# Route
# ---------------------------------------------------------------------------

fastapi = pytest.importorskip("fastapi")
from fastapi.testclient import TestClient


@pytest.fixture
def web_engine():
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
def web_client(web_engine, monkeypatch):
    from project_db.db import session as session_mod

    factory = sessionmaker(bind=web_engine, expire_on_commit=False)
    monkeypatch.setattr(session_mod, "_SessionLocal", factory)
    from project_db.web.app import create_app

    return TestClient(create_app()), factory


class TestGanttRoute:
    def test_gantt_page_renders(self, web_client):
        client, factory = web_client
        s = factory()
        org = Organization(name="Co")
        s.add(org)
        s.flush()
        cli = Client(name="Owner", organization_id=org.canonical_id)
        s.add(cli)
        s.flush()
        p = Project(name="Rockland", status=ProjectStatus.ACTIVE, client_id=cli.canonical_id)
        s.add(p)
        s.flush()
        t = Task(
            title="Demo",
            status=TaskStatus.TODO,
            project_id=p.canonical_id,
            start_date=date(2026, 6, 1),
            end_date=date(2026, 6, 10),
        )
        s.add(t)
        s.commit()
        pid = str(p.canonical_id)
        s.close()

        resp = client.get(f"/projects/{pid}/gantt")
        assert resp.status_code == 200
        assert "Timeline" in resp.text
        assert "<svg" in resp.text
        assert "Demo" in resp.text

    def test_gantt_unknown_id_404(self, web_client):
        client, _ = web_client
        resp = client.get("/projects/00000000-0000-0000-0000-000000000000/gantt")
        assert resp.status_code == 404
