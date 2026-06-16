"""Phase 4: dependency write-back.

propose_dependency (producer) -> accept_proposal (writes Monday "Dependent On"
+ mirrors canonical edges) -> MondayConnector.set_task_dependencies (the write).
Monday is always mocked -- no test touches the real API.
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from project_db.ai.proposals import accept_proposal, propose_dependency
from project_db.db.base import Base
from project_db.db.models import (
    Client,
    ExternalId,
    Organization,
    Project,
    SourceSystem,
    Task,
    TaskDependency,
)
from project_db.db.models.proposals import ProposalStatus
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
def org(session):
    o = Organization(name="Co")
    session.add(o)
    session.commit()
    return o


@pytest.fixture
def project(session, org):
    cli = Client(name="Owner", organization_id=org.canonical_id)
    session.add(cli)
    session.flush()
    p = Project(name="Rockland", status=ProjectStatus.ACTIVE, client_id=cli.canonical_id)
    session.add(p)
    session.commit()
    return p


def _task(session, project, title):
    t = Task(title=title, status=TaskStatus.TODO, project_id=project.canonical_id)
    session.add(t)
    session.flush()
    return t


def _ext(session, task, item_id, board_id=999):
    session.add(
        ExternalId(
            source=SourceSystem.MONDAY,
            entity_type="Task",
            canonical_id=task.canonical_id,
            external_key=str(item_id),
            external_url=f"https://view.monday.com/boards/{board_id}/pulses/{item_id}",
        )
    )
    session.flush()


# ---------------------------------------------------------------------------
# propose_dependency (producer)
# ---------------------------------------------------------------------------


class TestProposeDependency:
    def test_creates_pending_proposal(self, session, project):
        succ = _task(session, project, "Drywall")
        pred = _task(session, project, "Plumbing")
        session.commit()
        p = propose_dependency(
            session,
            succ.canonical_id,
            [pred.canonical_id],
            evidence="can't drywall until plumbing done",
        )
        session.commit()
        assert p is not None
        assert p.field_name == "dependency"
        assert p.entity_id == succ.canonical_id
        assert p.status == ProposalStatus.PENDING
        pv = json.loads(p.proposed_value)
        assert pv["predecessor_task_ids"] == [str(pred.canonical_id)]
        assert "evidence" in pv

    def test_filters_self_and_cross_project(self, session, project, org):
        succ = _task(session, project, "Drywall")
        # other-project task
        cli2 = Client(name="X", organization_id=org.canonical_id)
        session.add(cli2)
        session.flush()
        other_proj = Project(name="Other", status=ProjectStatus.ACTIVE, client_id=cli2.canonical_id)
        session.add(other_proj)
        session.flush()
        foreign = Task(title="Foreign", status=TaskStatus.TODO, project_id=other_proj.canonical_id)
        session.add(foreign)
        session.commit()
        # self + cross-project -> nothing valid -> None
        p = propose_dependency(
            session, succ.canonical_id, [succ.canonical_id, foreign.canonical_id]
        )
        assert p is None

    def test_supersedes_prior(self, session, project):
        succ = _task(session, project, "Drywall")
        a = _task(session, project, "A")
        b = _task(session, project, "B")
        session.commit()
        p1 = propose_dependency(session, succ.canonical_id, [a.canonical_id])
        session.commit()
        p2 = propose_dependency(session, succ.canonical_id, [b.canonical_id])
        session.commit()
        session.refresh(p1)
        assert p1.status == ProposalStatus.SUPERSEDED
        assert p2.status == ProposalStatus.PENDING


# ---------------------------------------------------------------------------
# accept_proposal -> dependency
# ---------------------------------------------------------------------------


@pytest.fixture
def fake_wb():
    wb = MagicMock(name="MondayConnector(fake)")
    wb.set_task_dependencies.return_value = {"ok": True, "item_id": 1, "column": "dep"}
    return wb


class TestAcceptDependency:
    def _proposal(self, session, project):
        succ = _task(session, project, "Drywall")
        pred = _task(session, project, "Plumbing")
        session.commit()
        p = propose_dependency(session, succ.canonical_id, [pred.canonical_id])
        session.commit()
        return p, succ, pred

    def test_happy_path_writes_and_mirrors(self, session, project, fake_wb):
        p, succ, pred = self._proposal(session, project)
        res = accept_proposal(session, str(p.canonical_id), writeback=fake_wb, decided_by="ui:test")
        assert res["ok"], res
        # Monday write called once with the right tasks.
        assert fake_wb.set_task_dependencies.call_count == 1
        args = fake_wb.set_task_dependencies.call_args.args
        assert args[0].canonical_id == succ.canonical_id
        assert [t.canonical_id for t in args[1]] == [pred.canonical_id]
        # proposal flipped + canonical edge mirrored
        session.refresh(p)
        assert p.status == ProposalStatus.ACCEPTED
        edge = session.query(TaskDependency).one()
        assert edge.predecessor_task_id == pred.canonical_id
        assert edge.successor_task_id == succ.canonical_id

    def test_writeback_false_leaves_pending(self, session, project):
        p, _succ, _pred = self._proposal(session, project)
        wb = MagicMock()
        wb.set_task_dependencies.return_value = {"ok": False, "error": "no dep column"}
        res = accept_proposal(session, str(p.canonical_id), writeback=wb, decided_by="ui")
        assert not res["ok"]
        session.refresh(p)
        assert p.status == ProposalStatus.PENDING
        assert session.query(TaskDependency).count() == 0

    def test_writeback_raises_leaves_pending(self, session, project):
        p, _succ, _pred = self._proposal(session, project)
        wb = MagicMock()
        wb.set_task_dependencies.side_effect = RuntimeError("API down")
        res = accept_proposal(session, str(p.canonical_id), writeback=wb, decided_by="ui")
        assert not res["ok"]
        session.refresh(p)
        assert p.status == ProposalStatus.PENDING
        assert session.query(TaskDependency).count() == 0

    def test_dry_run_writes_nothing(self, session, project, fake_wb):
        p, _succ, _pred = self._proposal(session, project)
        res = accept_proposal(session, str(p.canonical_id), writeback=fake_wb, dry_run=True)
        assert res["ok"] and res["dry_run"]
        assert fake_wb.set_task_dependencies.call_count == 0
        session.refresh(p)
        assert p.status == ProposalStatus.PENDING
        assert session.query(TaskDependency).count() == 0


# ---------------------------------------------------------------------------
# MondayConnector.set_task_dependencies (the actual write)
# ---------------------------------------------------------------------------


class TestConnectorWrite:
    def _connector(self, session, org):
        from project_db.connectors.monday.connector import MondayConnector

        c = MondayConnector(
            session=session, organization_id=org.canonical_id, config={"api_token": "test"}
        )
        client = MagicMock()
        client.list_board_columns.return_value = [
            {"id": "project_dependency", "type": "dependency", "title": "Dependent On"},
            {"id": "status", "type": "status", "title": "Status"},
        ]
        client.change_column_value.return_value = {"id": "1"}
        c.client = client
        return c, client

    def test_writes_dependency_column(self, session, project, org):
        succ = _task(session, project, "Drywall")
        pred = _task(session, project, "Plumbing")
        _ext(session, succ, item_id=111, board_id=999)
        _ext(session, pred, item_id=222, board_id=999)
        session.commit()
        c, client = self._connector(session, org)
        res = c.set_task_dependencies(succ, [pred])
        assert res["ok"], res
        client.change_column_value.assert_called_once_with(
            999, 111, "project_dependency", {"item_ids": [222]}
        )

    def test_no_monday_mapping_returns_error(self, session, project, org):
        succ = _task(session, project, "Drywall")  # no ExternalId
        pred = _task(session, project, "Plumbing")
        session.commit()
        c, client = self._connector(session, org)
        res = c.set_task_dependencies(succ, [pred])
        assert not res["ok"]
        client.change_column_value.assert_not_called()

    def test_no_dependency_column_returns_error(self, session, project, org):
        succ = _task(session, project, "Drywall")
        pred = _task(session, project, "Plumbing")
        _ext(session, succ, item_id=111)
        _ext(session, pred, item_id=222)
        session.commit()
        c, client = self._connector(session, org)
        client.list_board_columns.return_value = [
            {"id": "status", "type": "status", "title": "Status"}
        ]
        res = c.set_task_dependencies(succ, [pred])
        assert not res["ok"]
        assert "dependency column" in res["error"]
