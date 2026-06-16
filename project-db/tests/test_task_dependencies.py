"""Task dependency graph: model, migration, and the sync-capture logic.

Covers the Phase-1 graph foundation from docs/MONDAY_AUDIT.md:
  - TaskDependency model round-trip + unique-edge constraint
  - ensure_sqlite_schema creates task_dependency on an existing DB file
  - resolve_dependency_predecessors: id-based, name fallback, dedup, ignore
    non-dependency columns, self-handling
  - rebuild_dependency_edges: builds edges, idempotent re-run, reflects
    REMOVED deps, skips self-links, excludes ambiguous titles
"""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from project_db.connectors.monday.connector import (
    rebuild_dependency_edges,
    resolve_dependency_predecessors,
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
    p = Project(name="923 Rockland", status=ProjectStatus.ACTIVE, client_id=cli.canonical_id)
    session.add(p)
    session.commit()
    return p


def _task(session, project, title):
    t = Task(title=title, status=TaskStatus.TODO, project_id=project.canonical_id)
    session.add(t)
    session.flush()
    return t


def _dep_col(*, display_value="", linked_item_ids=None):
    return {
        "id": "project_dependency",
        "title": "Dependent On",
        "type": "dependency",
        "display_value": display_value,
        "linked_item_ids": linked_item_ids or [],
    }


# ---------------------------------------------------------------------------
# Model + migration
# ---------------------------------------------------------------------------


class TestModel:
    def test_edge_round_trip(self, session, project):
        a = _task(session, project, "Plumbing")
        b = _task(session, project, "Drywall")
        session.add(
            TaskDependency(predecessor_task_id=a.canonical_id, successor_task_id=b.canonical_id)
        )
        session.commit()
        edge = session.query(TaskDependency).one()
        assert edge.predecessor_task_id == a.canonical_id
        assert edge.successor_task_id == b.canonical_id
        assert edge.source.value == "MONDAY"

    def test_unique_edge_constraint(self, session, project):
        a = _task(session, project, "Plumbing")
        b = _task(session, project, "Drywall")
        session.add(
            TaskDependency(predecessor_task_id=a.canonical_id, successor_task_id=b.canonical_id)
        )
        session.commit()
        session.add(
            TaskDependency(predecessor_task_id=a.canonical_id, successor_task_id=b.canonical_id)
        )
        with pytest.raises(Exception):
            session.commit()


def test_migration_creates_table_on_existing_db(tmp_path):
    """ensure_sqlite_schema adds task_dependency to a DB that predates it."""
    from sqlalchemy import inspect

    from project_db.db.migrations import ensure_sqlite_schema

    db = tmp_path / "old.sqlite"
    engine = create_engine(f"sqlite:///{db}", future=True)
    # Create just the 'task' table so the FK target exists, NOT task_dependency.
    Task.__table__.create(engine)
    assert "task_dependency" not in inspect(engine).get_table_names()
    ensure_sqlite_schema(engine)
    assert "task_dependency" in inspect(engine).get_table_names()
    engine.dispose()


# ---------------------------------------------------------------------------
# resolve_dependency_predecessors (pure)
# ---------------------------------------------------------------------------


class TestResolvePredecessors:
    def test_id_based(self):
        t1, t2 = uuid.uuid4(), uuid.uuid4()
        cols = [_dep_col(linked_item_ids=["111", "222"])]
        preds = resolve_dependency_predecessors(
            cols,
            task_id_by_monday_id={"111": t1, "222": t2},
            task_id_by_title={},
        )
        assert preds == [t1, t2]

    def test_name_fallback_when_no_ids(self):
        t1 = uuid.uuid4()
        cols = [_dep_col(display_value="Plumbing rough-in")]
        preds = resolve_dependency_predecessors(
            cols,
            task_id_by_monday_id={},
            task_id_by_title={"plumbing rough-in": t1},
        )
        assert preds == [t1]

    def test_name_fallback_multiple_comma_joined(self):
        t1, t2 = uuid.uuid4(), uuid.uuid4()
        cols = [_dep_col(display_value="Plumbing, Framing")]
        preds = resolve_dependency_predecessors(
            cols,
            task_id_by_monday_id={},
            task_id_by_title={"plumbing": t1, "framing": t2},
        )
        assert preds == [t1, t2]

    def test_ids_win_over_names(self):
        t_id, t_name = uuid.uuid4(), uuid.uuid4()
        cols = [_dep_col(display_value="By Name", linked_item_ids=["111"])]
        preds = resolve_dependency_predecessors(
            cols,
            task_id_by_monday_id={"111": t_id},
            task_id_by_title={"by name": t_name},
        )
        assert preds == [t_id]  # name fallback NOT used when an id resolved

    def test_unresolvable_name_skipped(self):
        cols = [_dep_col(display_value="Ghost task")]
        preds = resolve_dependency_predecessors(cols, task_id_by_monday_id={}, task_id_by_title={})
        assert preds == []

    def test_dedup(self):
        t1 = uuid.uuid4()
        cols = [_dep_col(linked_item_ids=["111", "111"])]
        preds = resolve_dependency_predecessors(
            cols, task_id_by_monday_id={"111": t1}, task_id_by_title={}
        )
        assert preds == [t1]

    def test_non_dependency_columns_ignored(self):
        cols = [
            {"type": "board_relation", "linked_item_ids": ["999"], "display_value": "Portfolio"},
            {"type": "status", "display_value": "Done"},
        ]
        preds = resolve_dependency_predecessors(
            cols, task_id_by_monday_id={"999": uuid.uuid4()}, task_id_by_title={}
        )
        assert preds == []


# ---------------------------------------------------------------------------
# rebuild_dependency_edges (the sync pass) — the Rockland scenario
# ---------------------------------------------------------------------------


class TestRebuildEdges:
    def test_name_fallback_builds_real_chain(self, session, project):
        """The live Rockland case: dependency columns carry NAMES (display_value),
        linked_item_ids empty -> resolve by in-project title."""
        plumb = _task(session, project, "Plumbing rough-in")
        drywall = _task(session, project, "Drywall installation")
        plaster = _task(session, project, "Plaster work")
        session.commit()
        synced = [
            ("1", plumb.canonical_id, "Plumbing rough-in", [_dep_col()]),
            (
                "2",
                drywall.canonical_id,
                "Drywall installation",
                [_dep_col(display_value="Plumbing rough-in")],
            ),
            (
                "3",
                plaster.canonical_id,
                "Plaster work",
                [_dep_col(display_value="Drywall installation")],
            ),
        ]
        n = rebuild_dependency_edges(session, synced)
        session.commit()
        assert n == 2
        edges = {
            (e.predecessor_task_id, e.successor_task_id)
            for e in session.query(TaskDependency).all()
        }
        assert (plumb.canonical_id, drywall.canonical_id) in edges
        assert (drywall.canonical_id, plaster.canonical_id) in edges

    def test_id_based_build(self, session, project):
        a = _task(session, project, "A")
        b = _task(session, project, "B")
        session.commit()
        synced = [
            ("100", a.canonical_id, "A", [_dep_col()]),
            ("200", b.canonical_id, "B", [_dep_col(linked_item_ids=["100"])]),
        ]
        n = rebuild_dependency_edges(session, synced)
        session.commit()
        assert n == 1
        e = session.query(TaskDependency).one()
        assert (e.predecessor_task_id, e.successor_task_id) == (a.canonical_id, b.canonical_id)

    def test_idempotent_rerun(self, session, project):
        a = _task(session, project, "A")
        b = _task(session, project, "B")
        session.commit()
        synced = [
            ("100", a.canonical_id, "A", [_dep_col()]),
            ("200", b.canonical_id, "B", [_dep_col(linked_item_ids=["100"])]),
        ]
        rebuild_dependency_edges(session, synced)
        session.commit()
        rebuild_dependency_edges(session, synced)
        session.commit()
        assert session.query(TaskDependency).count() == 1  # no duplicate

    def test_reflects_removed_dependency(self, session, project):
        a = _task(session, project, "A")
        b = _task(session, project, "B")
        session.commit()
        with_dep = [
            ("100", a.canonical_id, "A", [_dep_col()]),
            ("200", b.canonical_id, "B", [_dep_col(linked_item_ids=["100"])]),
        ]
        rebuild_dependency_edges(session, with_dep)
        session.commit()
        assert session.query(TaskDependency).count() == 1
        # Re-sync with the dependency cleared in Monday.
        without_dep = [
            ("100", a.canonical_id, "A", [_dep_col()]),
            ("200", b.canonical_id, "B", [_dep_col()]),
        ]
        rebuild_dependency_edges(session, without_dep)
        session.commit()
        assert session.query(TaskDependency).count() == 0

    def test_self_link_skipped(self, session, project):
        a = _task(session, project, "A")
        session.commit()
        synced = [("100", a.canonical_id, "A", [_dep_col(linked_item_ids=["100"])])]
        n = rebuild_dependency_edges(session, synced)
        session.commit()
        assert n == 0
        assert session.query(TaskDependency).count() == 0

    def test_ambiguous_title_not_matched(self, session, project):
        """Two tasks share a title -> name fallback must NOT guess one."""
        dup1 = _task(session, project, "Cleanup")
        dup2 = _task(session, project, "Cleanup")
        succ = _task(session, project, "Final")
        session.commit()
        synced = [
            ("1", dup1.canonical_id, "Cleanup", [_dep_col()]),
            ("2", dup2.canonical_id, "Cleanup", [_dep_col()]),
            ("3", succ.canonical_id, "Final", [_dep_col(display_value="Cleanup")]),
        ]
        n = rebuild_dependency_edges(session, synced)
        session.commit()
        assert n == 0  # ambiguous predecessor name dropped, not guessed
