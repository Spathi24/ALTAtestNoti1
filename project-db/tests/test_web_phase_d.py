"""Phase D: HTMX accept / reject decision actions.

Coverage:
  - accept happy path: write-back called once, status flips, task dates
    mirror, decided fragment rendered
  - accept on already-ACCEPTED: stale fragment, NO double-write
  - accept with failing writeback (returns False or raises): proposal
    stays PENDING, idle fragment with error rendered
  - scope_gap accept: creates Monday item, proposal flips to ACCEPTED
  - reject happy path: REJECTED with reason, decided fragment rendered
  - reject scope_gap: works (advisory-only proposals can be rejected)
  - reject on already-decided: stale fragment
  - GET /decision: returns idle for PENDING, decided for else
  - missing connector: idle + error, no DB change
  - 404 for unknown ids on every mutation route
"""
from __future__ import annotations

import json
from datetime import date
from unittest.mock import MagicMock

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

fastapi = pytest.importorskip("fastapi")
from fastapi.testclient import TestClient  # noqa: E402

from project_db.db.base import Base  # noqa: E402
from project_db.db.models import (  # noqa: E402
    Client,
    Organization,
    Project,
    Proposal,
    Task,
)
from project_db.db.models.proposals import ProposalStatus  # noqa: E402
from project_db.db.models.work import ProjectStatus, TaskStatus  # noqa: E402


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


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
def fake_writeback():
    """Default fake: sync_back returns True (write succeeded).
    create_task returns a minimal Monday item dict.
    Tests that need other behaviors override methods themselves."""
    wb = MagicMock(name="MondayConnector(fake)")
    wb.sync_back.return_value = True
    wb.create_task.return_value = {"id": "9999999", "name": "New task"}
    wb.source = "MONDAY"
    return wb


@pytest.fixture
def patched_writeback(monkeypatch, fake_writeback):
    """Replace deps.build_monday_writeback with one that returns the fake.

    Per the review's #14: the accept route is a thin adapter; the test
    verifies the adapter calls sync_back exactly once with the right
    payload, without ever touching the real Monday API.
    """
    from project_db.web import deps
    monkeypatch.setattr(deps, "build_monday_writeback", lambda session: fake_writeback)
    return fake_writeback


@pytest.fixture
def client(patched_session_factory):
    from project_db.web.app import create_app
    return TestClient(create_app())


@pytest.fixture
def timeline_proposal(session, org: Organization):
    """A PENDING timeline proposal on a real Task -- the happy path."""
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
        title="Dateless task",
        status=TaskStatus.TODO,
    )
    session.add(task)
    session.flush()

    proposal = Proposal(
        entity_type="Task",
        entity_id=task.canonical_id,
        field_name="timeline",
        proposed_value=json.dumps({
            "start_date": "2026-07-01",
            "end_date":   "2026-07-05",
            "reasoning":  "test fixture",
        }),
        confidence=0.85,
        status=ProposalStatus.PENDING,
        prompt_version="test-v1",
    )
    session.add(proposal)
    session.commit()
    return {"proposal": proposal, "task": task, "project": project}


@pytest.fixture
def scope_proposal(session, org: Organization):
    """A PENDING scope_gap proposal targeting the Project entity.

    scope_gap is in _ACCEPTABLE_FIELDS, so accept creates a Monday item
    and flips the proposal to ACCEPTED.
    """
    c = Client(name="Acme", organization_id=org.canonical_id)
    session.add(c)
    session.flush()
    project = Project(
        name="P2", client_id=c.canonical_id, status=ProjectStatus.ACTIVE,
    )
    session.add(project)
    session.flush()

    proposal = Proposal(
        entity_type="Project",
        entity_id=project.canonical_id,
        field_name="scope_gap",
        proposed_value=json.dumps({
            "gap_description": "Missing kitchen demo line item",
            "suggested_task_title": "Demo kitchen",
            "reasoning": "test fixture",
        }),
        confidence=0.7,
        status=ProposalStatus.PENDING,
        prompt_version="scope-v1",
    )
    session.add(proposal)
    session.commit()
    return {"proposal": proposal, "project": project}


# ---------------------------------------------------------------------------
# Accept
# ---------------------------------------------------------------------------


class TestAccept:
    def test_accept_writes_to_monday_and_flips_status(
        self, client, session, timeline_proposal, patched_writeback
    ):
        pid = str(timeline_proposal["proposal"].canonical_id)
        resp = client.post(f"/proposals/{pid}/accept")
        assert resp.status_code == 200

        # Adapter called sync_back EXACTLY once with the right payload.
        assert patched_writeback.sync_back.call_count == 1
        call_args = patched_writeback.sync_back.call_args
        task_arg, field_updates = call_args.args
        assert field_updates == {
            "timeline": {"from": "2026-07-01", "to": "2026-07-05"}
        }

        body = resp.text
        assert "ACCEPTED" in body
        assert "Wrote to Monday" in body

        session.expire_all()
        p = session.query(Proposal).filter_by(
            canonical_id=timeline_proposal["proposal"].canonical_id
        ).one()
        assert p.status == ProposalStatus.ACCEPTED
        assert p.decided_by and p.decided_by.startswith("ui:")

        # task dates mirrored
        t = session.query(Task).filter_by(
            canonical_id=timeline_proposal["task"].canonical_id
        ).one()
        assert t.start_date == date(2026, 7, 1)
        assert t.end_date == date(2026, 7, 5)

    def test_accept_already_accepted_returns_stale_no_double_write(
        self, client, session, timeline_proposal, patched_writeback
    ):
        """Two browser tabs case: tab A accepts, tab B clicks Accept on
        a stale page.  Tab B's click must NOT trigger a second sync_back
        call.  This is the load-bearing review #5 invariant."""
        proposal_id = timeline_proposal["proposal"].canonical_id
        # Pre-decide the proposal directly so the route sees stale state.
        p = session.query(Proposal).filter_by(canonical_id=proposal_id).one()
        p.status = ProposalStatus.ACCEPTED
        session.commit()

        resp = client.post(f"/proposals/{proposal_id}/accept")
        assert resp.status_code == 200
        body = resp.text
        assert "stale" in body.lower() or "no longer PENDING" in body

        # CRITICAL: writeback must NOT have been called at all.
        assert patched_writeback.sync_back.call_count == 0

    def test_accept_with_failing_writeback_leaves_proposal_pending(
        self, client, session, timeline_proposal, monkeypatch
    ):
        """Monday returned False -- proposal stays PENDING, idle fragment
        with error is rendered.  No status flip, no task date mirror."""
        from project_db.web import deps

        failing = MagicMock()
        failing.sync_back.return_value = False
        monkeypatch.setattr(deps, "build_monday_writeback", lambda s: failing)

        pid = str(timeline_proposal["proposal"].canonical_id)
        resp = client.post(f"/proposals/{pid}/accept")
        assert resp.status_code == 200
        body = resp.text
        assert "Action failed" in body
        assert "PENDING" in body  # idle fragment

        session.expire_all()
        p = session.query(Proposal).filter_by(
            canonical_id=timeline_proposal["proposal"].canonical_id
        ).one()
        assert p.status == ProposalStatus.PENDING
        t = session.query(Task).filter_by(
            canonical_id=timeline_proposal["task"].canonical_id
        ).one()
        assert t.start_date is None

    def test_accept_with_raising_writeback_leaves_proposal_pending(
        self, client, session, timeline_proposal, monkeypatch
    ):
        from project_db.web import deps

        raising = MagicMock()
        raising.sync_back.side_effect = RuntimeError("connection refused")
        monkeypatch.setattr(deps, "build_monday_writeback", lambda s: raising)

        pid = str(timeline_proposal["proposal"].canonical_id)
        resp = client.post(f"/proposals/{pid}/accept")
        assert resp.status_code == 200
        assert "Action failed" in resp.text

        session.expire_all()
        p = session.query(Proposal).filter_by(
            canonical_id=timeline_proposal["proposal"].canonical_id
        ).one()
        assert p.status == ProposalStatus.PENDING

    def test_accept_scope_gap_creates_monday_item(self, client, session, scope_proposal, patched_writeback):
        """scope_gap proposals now create a new Monday item (not advisory-only).
        create_task is called once; sync_back is NOT called (different path)."""
        pid = str(scope_proposal["proposal"].canonical_id)
        resp = client.post(f"/proposals/{pid}/accept")
        assert resp.status_code == 200
        body = resp.text
        assert "Action failed" not in body
        assert "ACCEPTED" in body

        # create_task called once; sync_back never called (different code path).
        assert patched_writeback.create_task.call_count == 1
        assert patched_writeback.sync_back.call_count == 0

        session.expire_all()
        p = session.query(Proposal).filter_by(
            canonical_id=scope_proposal["proposal"].canonical_id
        ).one()
        assert p.status == ProposalStatus.ACCEPTED

        # A new Task should exist in the DB mirroring the Monday item.
        new_tasks = (
            session.query(Task)
            .filter_by(project_id=scope_proposal["project"].canonical_id)
            .all()
        )
        assert any(t.title == "Demo kitchen" for t in new_tasks)

    def test_accept_unknown_id_404(self, client):
        resp = client.post("/proposals/00000000-0000-0000-0000-000000000000/accept")
        assert resp.status_code == 404

    def test_accept_when_connector_factory_raises(
        self, client, timeline_proposal, monkeypatch
    ):
        """Missing MONDAY_API_TOKEN etc. -- factory raises, route shows
        the error inline, proposal stays PENDING."""
        from project_db.web import deps

        def factory(_s):
            raise RuntimeError("MONDAY_API_TOKEN not set")
        monkeypatch.setattr(deps, "build_monday_writeback", factory)

        pid = str(timeline_proposal["proposal"].canonical_id)
        resp = client.post(f"/proposals/{pid}/accept")
        assert resp.status_code == 200
        assert "could not build Monday connector" in resp.text


# ---------------------------------------------------------------------------
# Reject
# ---------------------------------------------------------------------------


class TestReject:
    def test_reject_with_reason(self, client, session, timeline_proposal):
        pid = str(timeline_proposal["proposal"].canonical_id)
        resp = client.post(
            f"/proposals/{pid}/reject",
            data={"reason": "dates conflict with permit window"},
        )
        assert resp.status_code == 200
        body = resp.text
        assert "REJECTED" in body
        assert "dates conflict with permit window" in body

        session.expire_all()
        p = session.query(Proposal).filter_by(
            canonical_id=timeline_proposal["proposal"].canonical_id
        ).one()
        assert p.status == ProposalStatus.REJECTED
        assert p.rejection_reason == "dates conflict with permit window"

    def test_reject_scope_gap_works(self, client, session, scope_proposal):
        """Advisory-only proposals can still be rejected."""
        pid = str(scope_proposal["proposal"].canonical_id)
        resp = client.post(f"/proposals/{pid}/reject", data={"reason": "not in budget"})
        assert resp.status_code == 200
        assert "REJECTED" in resp.text

        session.expire_all()
        p = session.query(Proposal).filter_by(
            canonical_id=scope_proposal["proposal"].canonical_id
        ).one()
        assert p.status == ProposalStatus.REJECTED

    def test_reject_already_rejected_returns_stale(
        self, client, session, timeline_proposal
    ):
        proposal_id = timeline_proposal["proposal"].canonical_id
        p = session.query(Proposal).filter_by(canonical_id=proposal_id).one()
        p.status = ProposalStatus.REJECTED
        session.commit()

        resp = client.post(f"/proposals/{proposal_id}/reject", data={"reason": "x"})
        assert resp.status_code == 200
        assert "stale" in resp.text.lower() or "no longer PENDING" in resp.text

    def test_reject_unknown_id_404(self, client):
        resp = client.post(
            "/proposals/00000000-0000-0000-0000-000000000000/reject",
            data={"reason": ""},
        )
        assert resp.status_code == 404

    def test_reject_with_no_reason(self, client, session, timeline_proposal):
        """Empty reason is allowed -- some rejects are obvious enough not to
        warrant prose.  Backend stores NULL in that case."""
        pid = str(timeline_proposal["proposal"].canonical_id)
        resp = client.post(f"/proposals/{pid}/reject", data={"reason": ""})
        assert resp.status_code == 200
        assert "REJECTED" in resp.text


# ---------------------------------------------------------------------------
# GET /decision (cancel target + refresh)
# ---------------------------------------------------------------------------


class TestDecisionGet:
    def test_get_pending_returns_idle(self, client, timeline_proposal):
        pid = str(timeline_proposal["proposal"].canonical_id)
        resp = client.get(f"/proposals/{pid}/decision")
        assert resp.status_code == 200
        body = resp.text
        # Idle fragment has the Accept button + Reject form
        assert "Accept" in body
        assert "Reject" in body

    def test_get_decided_returns_decided(self, client, session, timeline_proposal):
        proposal_id = timeline_proposal["proposal"].canonical_id
        p = session.query(Proposal).filter_by(canonical_id=proposal_id).one()
        p.status = ProposalStatus.ACCEPTED
        session.commit()

        resp = client.get(f"/proposals/{proposal_id}/decision")
        assert resp.status_code == 200
        body = resp.text
        assert "Preview Monday write" not in body  # no idle controls
        assert "ACCEPTED" in body

    def test_get_unknown_404(self, client):
        resp = client.get("/proposals/00000000-0000-0000-0000-000000000000/decision")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Detail-page initial render still works
# ---------------------------------------------------------------------------


class TestProposalDetailPageRender:
    def test_pending_renders_idle_fragment_inline(self, client, timeline_proposal):
        """The first time you visit /proposals/{id}, the decision panel is
        the idle fragment (not the Phase-B placeholder text)."""
        pid = str(timeline_proposal["proposal"].canonical_id)
        resp = client.get(f"/proposals/{pid}")
        assert resp.status_code == 200
        body = resp.text
        assert "Accept" in body
        # Old Phase-B placeholder text MUST be gone
        assert "Phase D will add" not in body

    def test_scope_gap_idle_enables_accept(self, client, scope_proposal):
        """scope_gap proposals are now actionable -- Accept button is enabled."""
        pid = str(scope_proposal["proposal"].canonical_id)
        resp = client.get(f"/proposals/{pid}")
        assert resp.status_code == 200
        body = resp.text
        # Accept button should NOT be disabled
        assert "advisory-only" not in body
        assert "Accept" in body
        assert "Reject" in body
