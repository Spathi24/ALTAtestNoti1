"""Deterministic task graph + schedule engine (ai/task_graph.py).

Covers structural links (hierarchy + dependency), the schedule analysis
(blocking predecessors, conflicts, cascade), and the LLM-facing renderers.
The cascade math is the load-bearing part -- it must be exact and consistent.
"""

from __future__ import annotations

from datetime import date

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from project_db.ai.task_graph import (
    build_task_graph,
    describe_task_neighborhood,
    render_cascade,
    render_project_tree,
)
from project_db.db.base import Base
from project_db.db.models import (
    Client,
    Organization,
    Project,
    Task,
    TaskDependency,
)
from project_db.db.models.work import ProjectStatus, TaskStatus


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
    p = Project(name="P", status=ProjectStatus.ACTIVE, client_id=cli.canonical_id)
    session.add(p)
    session.commit()
    return p


def _task(
    session,
    project,
    title,
    *,
    status=TaskStatus.TODO,
    label=None,
    start=None,
    end=None,
    parent=None,
):
    t = Task(
        title=title,
        status=status,
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


def _dep(session, predecessor, successor):
    session.add(
        TaskDependency(
            predecessor_task_id=predecessor.canonical_id,
            successor_task_id=successor.canonical_id,
        )
    )


class TestStructure:
    def test_hierarchy_and_dependency_links(self, session, project):
        parent = _task(session, project, "Phase")
        child = _task(session, project, "Step", parent=parent)
        a = _task(session, project, "A")
        b = _task(session, project, "B")
        _dep(session, a, b)
        session.commit()

        g = build_task_graph(session, project.canonical_id)
        assert g.parent(child.canonical_id).title == "Phase"
        assert [c.title for c in g.children(parent.canonical_id)] == ["Step"]
        assert [p.title for p in g.predecessors(b.canonical_id)] == ["A"]
        assert [s.title for s in g.successors(a.canonical_id)] == ["B"]

    def test_roots_excludes_subitems(self, session, project):
        parent = _task(session, project, "Phase", start=date(2026, 6, 1))
        _task(session, project, "Step", parent=parent)
        session.commit()
        g = build_task_graph(session, project.canonical_id)
        assert [r.title for r in g.roots()] == ["Phase"]


class TestScheduleAnalysis:
    def test_blocking_predecessors_only_unfinished(self, session, project):
        done = _task(session, project, "Done dep", status=TaskStatus.DONE, label="Done")
        open_ = _task(
            session, project, "Open dep", status=TaskStatus.IN_PROGRESS, label="Working on it"
        )
        succ = _task(session, project, "S")
        _dep(session, done, succ)
        _dep(session, open_, succ)
        session.commit()
        g = build_task_graph(session, project.canonical_id)
        blocking = g.blocking_predecessors(succ.canonical_id)
        assert [b.title for b in blocking] == ["Open dep"]

    def test_schedule_conflict_detected(self, session, project):
        # Predecessor finishes 6/15 but successor starts 6/12 -> 3d overlap.
        p = _task(session, project, "P", end=date(2026, 6, 15))
        s = _task(session, project, "S", start=date(2026, 6, 12), end=date(2026, 6, 20))
        _dep(session, p, s)
        session.commit()
        g = build_task_graph(session, project.canonical_id)
        conflicts = g.schedule_conflicts(s.canonical_id)
        assert len(conflicts) == 1
        pred, days = conflicts[0]
        assert pred.title == "P" and days == 3

    def test_no_conflict_when_sequenced(self, session, project):
        p = _task(session, project, "P", end=date(2026, 6, 10))
        s = _task(session, project, "S", start=date(2026, 6, 11), end=date(2026, 6, 15))
        _dep(session, p, s)
        session.commit()
        g = build_task_graph(session, project.canonical_id)
        assert g.schedule_conflicts(s.canonical_id) == []


class TestCascade:
    def test_single_level_push(self, session, project):
        a = _task(session, project, "A", start=date(2026, 6, 1), end=date(2026, 6, 10))
        b = _task(session, project, "B", start=date(2026, 6, 11), end=date(2026, 6, 15))
        _dep(session, a, b)
        session.commit()
        g = build_task_graph(session, project.canonical_id)
        # A now finishes 6/14 (was 6/10). B (starts 6/11) must move to 6/14.
        impacts = g.cascade_if_end_changes(a.canonical_id, date(2026, 6, 14))
        assert len(impacts) == 1
        c = impacts[0]
        assert c.title == "B"
        assert c.new_start == date(2026, 6, 14)
        assert c.days_pushed == 3
        # B kept its 4-day span -> new end 6/18.
        assert c.new_end == date(2026, 6, 18)

    def test_multi_level_ripple(self, session, project):
        a = _task(session, project, "A", start=date(2026, 6, 1), end=date(2026, 6, 10))
        b = _task(session, project, "B", start=date(2026, 6, 11), end=date(2026, 6, 15))
        c = _task(session, project, "C", start=date(2026, 6, 16), end=date(2026, 6, 20))
        _dep(session, a, b)
        _dep(session, b, c)
        session.commit()
        g = build_task_graph(session, project.canonical_id)
        impacts = {i.title: i for i in g.cascade_if_end_changes(a.canonical_id, date(2026, 6, 14))}
        assert set(impacts) == {"B", "C"}
        assert impacts["B"].new_start == date(2026, 6, 14)  # +3
        # B new end 6/18 -> C (started 6/16) pushes to 6/18.
        assert impacts["C"].new_start == date(2026, 6, 18)

    def test_no_conflict_no_cascade(self, session, project):
        a = _task(session, project, "A", start=date(2026, 6, 1), end=date(2026, 6, 10))
        b = _task(session, project, "B", start=date(2026, 6, 20), end=date(2026, 6, 25))
        _dep(session, a, b)
        session.commit()
        g = build_task_graph(session, project.canonical_id)
        # A moves to 6/12, still well before B's 6/20 start -> no push.
        assert g.cascade_if_end_changes(a.canonical_id, date(2026, 6, 12)) == []

    def test_cycle_safe(self, session, project):
        a = _task(session, project, "A", start=date(2026, 6, 1), end=date(2026, 6, 10))
        b = _task(session, project, "B", start=date(2026, 6, 11), end=date(2026, 6, 15))
        _dep(session, a, b)
        _dep(session, b, a)  # pathological cycle
        session.commit()
        g = build_task_graph(session, project.canonical_id)
        # Must terminate, not hang.
        impacts = g.cascade_if_end_changes(a.canonical_id, date(2026, 6, 14))
        assert any(i.title == "B" for i in impacts)

    def test_undated_successor_skipped(self, session, project):
        a = _task(session, project, "A", start=date(2026, 6, 1), end=date(2026, 6, 10))
        b = _task(session, project, "B")  # no dates
        _dep(session, a, b)
        session.commit()
        g = build_task_graph(session, project.canonical_id)
        assert g.cascade_if_end_changes(a.canonical_id, date(2026, 6, 14)) == []


class TestRenderers:
    def test_describe_neighborhood(self, session, project):
        plumb = _task(
            session,
            project,
            "Plumbing",
            status=TaskStatus.DONE,
            label="Done",
            end=date(2026, 6, 13),
        )
        drywall = _task(
            session,
            project,
            "Drywall",
            label="Working on it",
            start=date(2026, 6, 14),
            end=date(2026, 6, 18),
        )
        plaster = _task(session, project, "Plaster", start=date(2026, 6, 19))
        _dep(session, plumb, drywall)
        _dep(session, drywall, plaster)
        session.commit()
        g = build_task_graph(session, project.canonical_id)
        text = describe_task_neighborhood(g, drywall.canonical_id)
        assert "TASK: Drywall" in text
        assert "BLOCKED BY" in text and "Plumbing" in text and "DONE" in text
        assert "BLOCKS" in text and "Plaster" in text

    def test_render_cascade(self, session, project):
        a = _task(session, project, "A", start=date(2026, 6, 1), end=date(2026, 6, 10))
        b = _task(session, project, "B", start=date(2026, 6, 11), end=date(2026, 6, 15))
        _dep(session, a, b)
        session.commit()
        g = build_task_graph(session, project.canonical_id)
        text = render_cascade(g.cascade_if_end_changes(a.canonical_id, date(2026, 6, 14)))
        assert "B" in text and "+3d" in text

    def test_render_project_tree_indents_subitems(self, session, project):
        parent = _task(session, project, "Phase", start=date(2026, 6, 1))
        _task(session, project, "Step", parent=parent)
        session.commit()
        g = build_task_graph(session, project.canonical_id)
        tree = render_project_tree(g)
        assert "Phase" in tree
        assert "    [" in tree  # the child is indented
