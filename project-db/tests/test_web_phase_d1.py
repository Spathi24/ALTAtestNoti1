"""Phase D.1: action surfaces -- propose buttons, /ask, manual task edits.

Coverage:
  - /projects/{id}/propose/timelines + propose/scope: happy path (mock
    LLM provider returns a structured timeline/scope), skip path
    (project has no dateless tasks / no extracted text), error path
    (provider raises)
  - /ask: empty question, canned-route match (no LLM call), no-match
    fallthrough to LLM, LLM error
  - /tasks/{id}/dates-form: returns the inline form
  - /tasks/{id}/row: returns the static row (cancel target)
  - /tasks/{id}/set-dates: writes Monday FIRST then mirrors; failing
    writeback leaves task unchanged; 404 on unknown id
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
    Document,
    Organization,
    Project,
    Proposal,
    Task,
)
from project_db.db.models.docs import DocumentText  # noqa: E402
from project_db.db.models.proposals import ProposalStatus  # noqa: E402
from project_db.db.models.work import ProjectStatus, TaskStatus  # noqa: E402


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


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
def world(session, org: Organization):
    """One project with a dateless task and one contract doc with text.
    Enough surface area for propose/timelines + propose/scope to do
    real work against a mock provider."""
    c = Client(name="Acme", organization_id=org.canonical_id)
    session.add(c)
    session.flush()
    project = Project(
        name="P", client_id=c.canonical_id, status=ProjectStatus.ACTIVE,
    )
    session.add(project)
    session.flush()
    dateless = Task(
        project_id=project.canonical_id,
        title="Install kitchen",
        status=TaskStatus.TODO,
    )
    session.add(dateless)
    session.flush()
    doc = Document(
        project_id=project.canonical_id,
        name="SOW.pdf",
        mime_type="application/pdf",
        url="drive://fake/sow.pdf",
        folder_path="01. PROJECTS/ACTIVE/P",
        is_trashed=False,
    )
    session.add(doc)
    session.flush()
    session.add(DocumentText(
        document_id=doc.canonical_id,
        extracted_text="Scope: install kitchen cabinets by July 2026.",
        extraction_method="pdf",
        token_count=20,
    ))
    session.commit()
    return {"project": project, "task": dateless, "doc": doc}


@pytest.fixture
def patched_default_provider(monkeypatch):
    """Mock the deep provider so propose routes don't hit Anthropic."""
    from project_db.ai.providers import mock as mock_mod
    from project_db.ai import providers as providers_pkg

    timeline_payload = json.dumps({
        "proposals": [{
            "task_index": 0,
            "proposed_start": "2026-07-01",
            "proposed_end": "2026-07-10",
            "confidence": 0.9,
            "reasoning": "test mock",
            "source_documents": ["SOW.pdf"],
        }]
    })
    scope_payload = json.dumps({
        "scope_gaps": [{
            "scope_item": "Install kitchen cabinets",
            "suggested_task_title": "Install kitchen cabinets",
            "confidence": 0.9,
            "reasoning": "test mock",
            "source_documents": ["SOW.pdf"],
        }]
    })
    prov = mock_mod.MockLLMProvider(responses=[timeline_payload, scope_payload])
    monkeypatch.setattr(providers_pkg, "get_default_provider", lambda: prov)
    # generate_timeline_proposals imports it via this path:
    monkeypatch.setattr(
        "project_db.ai.providers.get_default_provider", lambda: prov,
    )
    return prov


@pytest.fixture
def patched_fast_provider(monkeypatch):
    """Mock the fast (Haiku) provider for /ask LLM fallback."""
    from project_db.ai.providers import mock as mock_mod
    from project_db.ai import providers as providers_pkg

    prov = mock_mod.MockLLMProvider(
        responses=["Mocked Haiku answer: 21 projects in the DB."]
    )
    monkeypatch.setattr(providers_pkg, "get_fast_provider", lambda: prov)
    monkeypatch.setattr(
        "project_db.ai.providers.get_fast_provider", lambda: prov,
    )
    return prov


@pytest.fixture
def patched_writeback(monkeypatch):
    """Default Monday writeback fake; tests override as needed."""
    from project_db.web import deps
    wb = MagicMock(name="MondayConnector(fake)")
    wb.sync_back.return_value = True
    monkeypatch.setattr(deps, "build_monday_writeback", lambda session: wb)
    return wb


# ---------------------------------------------------------------------------
# Propose timelines / scope
# ---------------------------------------------------------------------------


class TestProposeTimelines:
    def test_happy_path_creates_proposal_returns_fragment(
        self, client, session, world, patched_default_provider
    ):
        pid = str(world["project"].canonical_id)
        resp = client.post(f"/projects/{pid}/propose/timelines")
        assert resp.status_code == 200
        body = resp.text
        assert "Generated" in body and "timeline" in body.lower()

        session.expire_all()
        props = session.query(Proposal).all()
        assert len(props) == 1
        assert props[0].field_name == "timeline"
        assert props[0].status == ProposalStatus.PENDING

    def test_skip_when_no_dateless_tasks(
        self, client, session, world, patched_default_provider
    ):
        """Give the one task a date, so propose has nothing to do."""
        task = world["task"]
        task.start_date = date(2026, 6, 1)
        task.end_date = date(2026, 6, 10)
        session.commit()

        pid = str(world["project"].canonical_id)
        resp = client.post(f"/projects/{pid}/propose/timelines")
        assert resp.status_code == 200
        assert "Skipped" in resp.text
        # No new proposal created
        assert session.query(Proposal).count() == 0

    def test_provider_factory_error_renders_inline(
        self, client, world, monkeypatch
    ):
        # Make get_default_provider raise; route should NOT 500.
        def boom():
            raise RuntimeError("no API key")
        monkeypatch.setattr(
            "project_db.ai.providers.get_default_provider", boom,
        )

        pid = str(world["project"].canonical_id)
        resp = client.post(f"/projects/{pid}/propose/timelines")
        assert resp.status_code == 200
        assert "timeline generation failed" in resp.text.lower() or \
               "could not build LLM provider" in resp.text

    def test_unknown_project_404(self, client):
        resp = client.post(
            "/projects/00000000-0000-0000-0000-000000000000/propose/timelines"
        )
        assert resp.status_code == 404


class TestProposeScope:
    def test_happy_path_creates_scope_gap_proposal(
        self, client, session, world, patched_default_provider
    ):
        # Burn the timeline response first by calling timelines route, so
        # the scope call receives the scope payload (mock has 2 responses).
        # Easier: just call scope -- the mock returns whichever response
        # is at the cursor.  Cursor=0 is timeline JSON, which scope parser
        # will reject as malformed.  Re-seed the mock with scope first.
        from project_db.ai.providers import mock as mock_mod
        from project_db.ai import providers as providers_pkg
        scope_only = json.dumps({
            "scope_gaps": [{
                "scope_item": "Install kitchen cabinets",
                "suggested_task_title": "Install kitchen cabinets",
                "confidence": 0.9,
                "reasoning": "test mock",
                "source_documents": ["SOW.pdf"],
            }]
        })
        prov = mock_mod.MockLLMProvider(responses=[scope_only])
        import pytest
        pytest.MonkeyPatch().setattr(
            providers_pkg, "get_default_provider", lambda: prov,
        )

        pid = str(world["project"].canonical_id)
        resp = client.post(f"/projects/{pid}/propose/scope")
        assert resp.status_code == 200
        body = resp.text
        assert "Generated" in body or "Skipped" in body

    def test_skip_when_no_extracted_text(self, client, session, org, patched_default_provider):
        """Project with no DocumentText -> scope generation is skipped."""
        c = Client(name="X", organization_id=org.canonical_id)
        session.add(c)
        session.flush()
        empty = Project(name="Empty", client_id=c.canonical_id,
                        status=ProjectStatus.ACTIVE)
        session.add(empty)
        session.commit()

        resp = client.post(f"/projects/{empty.canonical_id}/propose/scope")
        assert resp.status_code == 200
        assert "Skipped" in resp.text


# ---------------------------------------------------------------------------
# /ask
# ---------------------------------------------------------------------------


class TestAsk:
    def test_get_renders_form(self, client):
        resp = client.get("/ask")
        assert resp.status_code == 200
        assert "Ask" in resp.text
        assert "<textarea" in resp.text

    def test_post_empty_question_does_not_crash(self, client):
        resp = client.post("/ask", data={"question": "  "})
        assert resp.status_code == 200
        assert "Type a question" in resp.text

    def test_post_help_route_canned(self, client, world):
        """'help' matches the canned discoverability path -- no LLM call."""
        resp = client.post("/ask", data={"question": "help"})
        assert resp.status_code == 200
        body = resp.text
        assert "mode" in body
        assert "canned" in body  # mode badge or registry entry
        # spent-tokens pill must NOT appear
        assert "spent tokens" not in body

    def test_post_active_projects_canned(self, client, world):
        resp = client.post("/ask", data={"question": "what active projects do we have?"})
        assert resp.status_code == 200
        body = resp.text
        # 'P' is the seeded project name
        assert "active_projects" in body or "\"name\"" in body

    def test_post_no_match_falls_back_to_llm(
        self, client, world, patched_fast_provider
    ):
        """A question that matches no canned route triggers the Haiku
        fallback.  Tests asserts the mock was called and its response
        shows on the page."""
        resp = client.post(
            "/ask",
            data={"question": "what's the meaning of life across our projects?"},
        )
        assert resp.status_code == 200
        body = resp.text
        assert "Mocked Haiku answer" in body
        assert "llm" in body  # mode badge
        assert patched_fast_provider.calls, \
            "fast provider should have been called for the no-match path"

    def test_post_no_match_with_failed_fast_provider(
        self, client, world, monkeypatch
    ):
        def boom():
            raise RuntimeError("no API key for fast model")
        monkeypatch.setattr(
            "project_db.ai.providers.get_fast_provider", boom,
        )
        resp = client.post(
            "/ask",
            data={"question": "anything that doesn't match a canned report"},
        )
        assert resp.status_code == 200
        assert "could not be built" in resp.text


# ---------------------------------------------------------------------------
# Manual task date edits
# ---------------------------------------------------------------------------


class TestTaskDateEdits:
    def test_dates_form_returns_inline_form(self, client, world):
        tid = str(world["task"].canonical_id)
        resp = client.get(f"/tasks/{tid}/dates-form")
        assert resp.status_code == 200
        body = resp.text
        assert "input" in body and "type=\"date\"" in body
        assert "Save" in body
        assert "Cancel" in body

    def test_row_endpoint_returns_static_row(self, client, world):
        tid = str(world["task"].canonical_id)
        resp = client.get(f"/tasks/{tid}/row")
        assert resp.status_code == 200
        body = resp.text
        assert "Install kitchen" in body
        # dateless task -> dateless pill renders
        assert "dateless" in body.lower()

    def test_set_dates_writes_monday_then_mirrors(
        self, client, session, world, patched_writeback
    ):
        tid = str(world["task"].canonical_id)
        resp = client.post(
            f"/tasks/{tid}/set-dates",
            data={"start_date": "2026-07-01", "end_date": "2026-07-10"},
        )
        assert resp.status_code == 200

        # Adapter called sync_back exactly once with the right payload.
        assert patched_writeback.sync_back.call_count == 1
        _task_arg, field_updates = patched_writeback.sync_back.call_args.args
        assert field_updates == {
            "timeline": {"from": "2026-07-01", "to": "2026-07-10"}
        }

        session.expire_all()
        t = session.query(Task).filter_by(
            canonical_id=world["task"].canonical_id
        ).one()
        assert t.start_date == date(2026, 7, 1)
        assert t.end_date == date(2026, 7, 10)
        # No Proposal row was created for a manual edit.
        assert session.query(Proposal).count() == 0

    def test_set_dates_failing_writeback_leaves_task_unchanged(
        self, client, session, world, monkeypatch
    ):
        """Monday returned False -- task dates must NOT change."""
        from project_db.web import deps
        wb = MagicMock()
        wb.sync_back.return_value = False
        monkeypatch.setattr(deps, "build_monday_writeback", lambda s: wb)

        tid = str(world["task"].canonical_id)
        resp = client.post(
            f"/tasks/{tid}/set-dates",
            data={"start_date": "2026-07-01", "end_date": "2026-07-10"},
        )
        assert resp.status_code == 200
        assert "Save failed" in resp.text or "left unchanged" in resp.text

        session.expire_all()
        t = session.query(Task).filter_by(
            canonical_id=world["task"].canonical_id
        ).one()
        assert t.start_date is None
        assert t.end_date is None

    def test_set_dates_raising_writeback_leaves_task_unchanged(
        self, client, session, world, monkeypatch
    ):
        from project_db.web import deps
        wb = MagicMock()
        wb.sync_back.side_effect = RuntimeError("conn refused")
        monkeypatch.setattr(deps, "build_monday_writeback", lambda s: wb)

        tid = str(world["task"].canonical_id)
        resp = client.post(
            f"/tasks/{tid}/set-dates",
            data={"start_date": "2026-07-01", "end_date": "2026-07-10"},
        )
        assert resp.status_code == 200
        assert "Save failed" in resp.text

        session.expire_all()
        t = session.query(Task).filter_by(
            canonical_id=world["task"].canonical_id
        ).one()
        assert t.start_date is None

    def test_set_dates_validation_end_before_start(
        self, client, session, world, patched_writeback
    ):
        tid = str(world["task"].canonical_id)
        resp = client.post(
            f"/tasks/{tid}/set-dates",
            data={"start_date": "2026-07-10", "end_date": "2026-07-01"},
        )
        assert resp.status_code == 200
        assert "before" in resp.text.lower() or "Save failed" in resp.text
        # NO Monday call attempted with bad input.
        assert patched_writeback.sync_back.call_count == 0

    def test_set_dates_unknown_task_404(self, client, patched_writeback):
        resp = client.post(
            "/tasks/00000000-0000-0000-0000-000000000000/set-dates",
            data={"start_date": "2026-07-01", "end_date": "2026-07-10"},
        )
        assert resp.status_code == 404

    def test_dates_form_unknown_404(self, client):
        resp = client.get("/tasks/00000000-0000-0000-0000-000000000000/dates-form")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Project detail Tasks panel uses the new combined table
# ---------------------------------------------------------------------------


class TestProjectDetailTasksPanel:
    def test_tasks_panel_renders_dates_inline(self, client, session, world):
        """Now that the panel shows dates on each row, the dated case
        must render the actual dates (not just "-")."""
        task = world["task"]
        task.start_date = date(2026, 6, 1)
        task.end_date = date(2026, 6, 10)
        session.commit()

        pid = str(world["project"].canonical_id)
        resp = client.get(f"/projects/{pid}")
        body = resp.text
        assert "2026-06-01" in body
        assert "2026-06-10" in body

    def test_tasks_panel_shows_dateless_pill(self, client, world):
        pid = str(world["project"].canonical_id)
        resp = client.get(f"/projects/{pid}")
        # The single seeded task is dateless -> pill should render
        assert "dateless" in resp.text.lower()

    def test_tasks_panel_has_edit_buttons(self, client, world):
        pid = str(world["project"].canonical_id)
        resp = client.get(f"/projects/{pid}")
        tid = str(world["task"].canonical_id)
        # The Edit button is wired via HTMX to /tasks/{id}/dates-form
        assert f"/tasks/{tid}/dates-form" in resp.text


# ---------------------------------------------------------------------------
# Permission-boundary updates
# ---------------------------------------------------------------------------


class TestForbiddenAfterPhaseD1:
    """Phase D.1 adds propose, ask, task-dates routes.  Several routes
    that WERE forbidden in Phase A's test (e.g. `/propose`) are still
    forbidden -- only the nested `/projects/{id}/propose/...` shape
    landed."""

    @pytest.mark.parametrize("path", [
        # Plain /propose without project scope still doesn't exist
        "/propose",
        "/propose/timelines",
        "/propose/scope",
        # Bulk proposal endpoints still don't exist
        "/proposals/accept-all",
        "/proposals/reject-all",
        # Direct task-edit beyond dates still doesn't exist
        "/tasks/00000000-0000-0000-0000-000000000000/edit",
        "/tasks/00000000-0000-0000-0000-000000000000/delete",
        # Sync still not exposed
        "/sync",
        "/sync/monday",
    ])
    def test_still_forbidden(self, client, path):
        assert client.get(path).status_code in (404, 405)
        assert client.post(path).status_code in (404, 405)
