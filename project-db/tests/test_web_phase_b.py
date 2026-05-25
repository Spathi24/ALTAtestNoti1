"""Phase B+C: read-only browsing -- projects, documents, proposals, doctor.

Tests cover:
  - happy path: each route renders 200 with key data present
  - service module: ui_views functions return shapes the templates expect
  - 404 for unknown / malformed IDs
  - Phase-D forbidden surface: accept/reject endpoints must NOT exist yet
"""
from __future__ import annotations

import json
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
    ExternalId,
    Organization,
    Project,
    Proposal,
    SourceSystem,
    Task,
)
from project_db.db.models.docs import DocumentText  # noqa: E402
from project_db.db.models.proposals import ProposalStatus  # noqa: E402
from project_db.db.models.work import ProjectStatus, TaskStatus  # noqa: E402


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
def world(session, org: Organization):
    """One full slice of canonical data: client, project with one Drive folder
    ExternalId, two tasks (dated + dateless), one document with extracted text,
    one document without, one PENDING timeline proposal citing the doc."""
    c = Client(name="Acme", organization_id=org.canonical_id)
    session.add(c)
    session.flush()

    project = Project(
        name="923 Rockland",
        client_id=c.canonical_id,
        status=ProjectStatus.ACTIVE,
    )
    session.add(project)
    session.flush()

    session.add(ExternalId(
        entity_type="Project",
        canonical_id=project.canonical_id,
        source=SourceSystem.GOOGLE_DRIVE,
        external_key="folder:abc123",
        external_url="https://drive.google.com/drive/folders/abc123",
    ))

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
        name="Final SOW.pdf",
        mime_type="application/pdf",
        url="drive://fake/sow.pdf",
        folder_path="01. PROJECTS/ACTIVE/923 Rockland",
        is_trashed=False,
    )
    doc_without = Document(
        project_id=project.canonical_id,
        name="site_photo.heic",
        mime_type="image/heic",
        url="drive://fake/photo.heic",
        folder_path="01. PROJECTS/ACTIVE/923 Rockland/photos",
        is_trashed=False,
    )
    session.add_all([doc_with, doc_without])
    session.flush()

    session.add(DocumentText(
        document_id=doc_with.canonical_id,
        extracted_text="Scope of work: install temporary structural support.",
        extraction_method="pdf",
        token_count=12,
    ))

    proposal = Proposal(
        entity_type="Task",
        entity_id=dateless.canonical_id,
        field_name="timeline",
        proposed_value=json.dumps({
            "start_date": "2026-07-01",
            "end_date": "2026-07-05",
            "reasoning": "Inferred from Final SOW.pdf section 4.",
        }),
        confidence=0.85,
        status=ProposalStatus.PENDING,
        prompt_version="timelines-v2",
        source_doc_ids=json.dumps([str(doc_with.canonical_id)]),
    )
    session.add(proposal)
    session.commit()
    return {
        "project": project,
        "dated_task": dated,
        "dateless_task": dateless,
        "doc_with_text": doc_with,
        "doc_without_text": doc_without,
        "proposal": proposal,
    }


# ===========================================================================
# Project list + detail
# ===========================================================================


class TestProjectList:
    def test_index_200(self, client, world):
        resp = client.get("/projects")
        assert resp.status_code == 200
        assert "923 Rockland" in resp.text
        assert 'data-testid="project-row"' in resp.text

    def test_empty_db(self, client):
        resp = client.get("/projects")
        assert resp.status_code == 200
        assert "No projects" in resp.text


class TestProjectDetail:
    def test_200(self, client, world):
        pid = str(world["project"].canonical_id)
        resp = client.get(f"/projects/{pid}")
        assert resp.status_code == 200
        body = resp.text
        assert "923 Rockland" in body
        # Identity panel shows the Drive ExternalId
        assert "GOOGLE_DRIVE" in body
        # Tasks panel surfaces the dateless task
        assert "Dateless task" in body
        # Documents panel lists the SOW
        assert "Final SOW.pdf" in body
        # Proposals panel shows the pending one
        assert "PENDING" in body
        assert "timelines-v2" not in body  # prompt version on detail page, not project

    def test_404_for_unknown_uuid(self, client, world):
        resp = client.get("/projects/00000000-0000-0000-0000-000000000000")
        assert resp.status_code == 404

    def test_404_for_malformed_id(self, client, world):
        resp = client.get("/projects/not-a-uuid")
        assert resp.status_code == 404

    def test_no_accept_button_on_project_detail_in_any_phase(self, client, world):
        """The project-detail page lists proposals as Review links, never
        as inline accept/reject buttons.  Mutation UI lives on the
        proposal detail page; this is intentional, so a PM doesn't
        click Accept without seeing the citations.

        Phase D adds accept/reject on /proposals/{id}.  This test pins
        that they do NOT bleed into the project page."""
        pid = str(world["project"].canonical_id)
        resp = client.get(f"/projects/{pid}")
        assert resp.status_code == 200
        body = resp.text.lower()
        # 'Review' link to the proposal is fine; an inline Accept button
        # right on the project page would be the smell.
        assert ">accept<" not in body
        # 'reject' as a word may appear in proposal status text; only flag
        # an actual button.
        assert "<button" not in body or "accept" not in body.split("<button", 1)[1].split("</button>", 1)[0].lower()


# ===========================================================================
# Document detail
# ===========================================================================


class TestDocumentDetail:
    def test_200_with_text(self, client, world):
        did = str(world["doc_with_text"].canonical_id)
        resp = client.get(f"/documents/{did}")
        assert resp.status_code == 200
        body = resp.text
        assert "Final SOW.pdf" in body
        # extracted text appears (inside the <pre>)
        assert "temporary structural support" in body
        # The proposal citing this doc is listed
        assert ">timeline<" in body or "timeline" in body

    def test_200_without_text(self, client, world):
        did = str(world["doc_without_text"].canonical_id)
        resp = client.get(f"/documents/{did}")
        assert resp.status_code == 200
        body = resp.text
        assert "site_photo.heic" in body
        assert "No DocumentText" in body

    def test_404_unknown(self, client, world):
        resp = client.get("/documents/00000000-0000-0000-0000-000000000000")
        assert resp.status_code == 404

    def test_404_malformed(self, client):
        resp = client.get("/documents/garbage")
        assert resp.status_code == 404


# ===========================================================================
# Proposal queue + detail
# ===========================================================================


class TestProposalQueue:
    def test_200(self, client, world):
        resp = client.get("/proposals")
        assert resp.status_code == 200
        body = resp.text
        assert "923 Rockland" in body
        assert 'data-testid="proposal-row"' in body
        assert "timeline" in body

    def test_status_filter_invalid_renders_hint(self, client, world):
        resp = client.get("/proposals?status=GARBAGE")
        assert resp.status_code == 200
        assert "Unknown status" in resp.text or "Valid" in resp.text

    def test_status_filter_pending(self, client, world):
        resp = client.get("/proposals?status=PENDING")
        assert resp.status_code == 200
        assert 'data-testid="proposal-row"' in resp.text

    def test_status_filter_accepted_empty(self, client, world):
        resp = client.get("/proposals?status=ACCEPTED")
        assert resp.status_code == 200
        assert "No proposals match" in resp.text


class TestProposalDetail:
    def test_200(self, client, world):
        pid = str(world["proposal"].canonical_id)
        resp = client.get(f"/proposals/{pid}")
        assert resp.status_code == 200
        body = resp.text
        assert "PENDING" in body
        assert "Final SOW.pdf" in body  # source document listed
        assert "2026-07-01" in body  # proposed start date
        # Phase D landed: the idle decision fragment is rendered inline.
        # The Phase-B placeholder text is gone.
        assert "Preview Monday write" in body
        assert "Phase D will add Accept" not in body

    def test_404_unknown(self, client, world):
        resp = client.get("/proposals/00000000-0000-0000-0000-000000000000")
        assert resp.status_code == 404


# ===========================================================================
# Doctor
# ===========================================================================


class TestDoctor:
    def test_200_clean_data(self, client, world):
        resp = client.get("/doctor")
        assert resp.status_code == 200
        body = resp.text
        assert "Doctor" in body
        assert "923 Rockland" in body

    def test_200_empty_db(self, client):
        resp = client.get("/doctor")
        assert resp.status_code == 200
        assert "Doctor" in resp.text


# ===========================================================================
# Service module
# ===========================================================================


class TestServiceFunctions:
    def test_project_list_rows(self, session, world):
        from project_db.web.ui_views import project_list_rows
        rows = project_list_rows(session)
        assert len(rows) == 1
        row = rows[0]
        assert row["name"] == "923 Rockland"
        assert row["task_count"] == 2
        assert row["tasks_dateless"] == 1
        assert row["doc_count"] == 2
        assert row["pending_proposals"] == 1

    def test_project_detail_resolves_uuid(self, session, world):
        from project_db.web.ui_views import project_detail
        pid = str(world["project"].canonical_id)
        d = project_detail(session, pid)
        assert d is not None
        assert d["project"]["name"] == "923 Rockland"
        assert d["dateless_count"] == 1
        assert d["documents_total"] == 2
        # Documents are grouped by folder
        assert "01. PROJECTS/ACTIVE/923 Rockland" in d["documents_by_folder"]

    def test_project_detail_none_for_unknown(self, session, world):
        from project_db.web.ui_views import project_detail
        assert project_detail(session, "00000000-0000-0000-0000-000000000000") is None
        assert project_detail(session, "not-a-uuid") is None

    def test_document_detail_includes_extraction(self, session, world):
        from project_db.web.ui_views import document_detail
        did = str(world["doc_with_text"].canonical_id)
        d = document_detail(session, did)
        assert d is not None
        assert d["document"]["name"] == "Final SOW.pdf"
        assert d["text"] is not None
        assert "structural support" in d["text"]["body"]
        # the citing proposal is found
        assert len(d["citing_proposals"]) == 1

    def test_document_detail_none_text_row(self, session, world):
        from project_db.web.ui_views import document_detail
        did = str(world["doc_without_text"].canonical_id)
        d = document_detail(session, did)
        assert d is not None
        assert d["text"] is None

    def test_proposal_queue_filter(self, session, world):
        from project_db.web.ui_views import proposal_queue
        data = proposal_queue(session, status="PENDING")
        assert data["error"] is None
        assert data["total"] == 1
        bad = proposal_queue(session, status="GARBAGE")
        assert bad["error"] is not None
        assert bad["rows"] == []

    def test_proposal_detail_includes_can_accept(self, session, world):
        from project_db.web.ui_views import proposal_detail
        pid = str(world["proposal"].canonical_id)
        d = proposal_detail(session, pid)
        assert d is not None
        assert d["status"] == "PENDING"
        # timeline IS acceptable
        assert d["can_accept"] is True
        # No prior proposal exists for the same target -- chain is empty
        assert d["supersede_chain"] == []

    def test_doctor_report_uses_service(self, session, world):
        from project_db.web.ui_views import doctor_report
        d = doctor_report(session)
        assert isinstance(d["projects"], list)
        assert d["documents"]["total"] >= 2


# ===========================================================================
# Routes that should still NOT exist after Phase D
#
# Phase D added per-proposal /accept /reject /dry-run.  These are tested
# in test_web_phase_d.py.  Bulk endpoints + cross-entity edits are still
# out of scope.
# ===========================================================================


class TestStillForbiddenAfterPhaseD:
    """Bulk-accept / bulk-reject and direct entity edits are NOT in v1."""

    @pytest.mark.parametrize("path", [
        "/proposals/accept-all",
        "/proposals/reject-all",
        "/proposals/all/accept",
        "/proposals/all/reject",
        # Per-proposal mutations that were never planned:
        "/proposals/00000000-0000-0000-0000-000000000000/delete",
        "/proposals/00000000-0000-0000-0000-000000000000/edit",
    ])
    def test_no_bulk_or_edit_routes(self, client, path):
        # GET
        assert client.get(path).status_code in (404, 405)
        # POST
        assert client.post(path).status_code in (404, 405)
