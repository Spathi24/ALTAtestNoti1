"""Tests for CLI subcommands.

The CLI lazily imports MondayClient / ColumnExtractor inside each command
function, so patches target the import source, not the cli module.
"""
from __future__ import annotations

import argparse
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy.orm import Session, sessionmaker

from project_db.db.models import (
    Deal,
    Document,
    DocumentText,
    LeadStage,
    Organization,
    Project,
    ProjectStatus,
    Proposal,
    ProposalStatus,
    Task,
    TaskStatus,
)


@pytest.fixture
def patched_session_factory(db_engine, monkeypatch):
    """Bind session_scope() to the test engine for CLI tests that hit the DB."""
    from project_db.db import session as session_mod

    factory = sessionmaker(bind=db_engine, expire_on_commit=False)
    monkeypatch.setattr(session_mod, "_SessionLocal", factory)
    yield factory


class TestCliInitDb:
    def test_init_db_returns_zero(self, patched_session_factory):
        from project_db.cli import cmd_init_db

        result = cmd_init_db(argparse.Namespace())
        assert result == 0

    def test_init_db_seeds_organization(self, patched_session_factory):
        from project_db.cli import cmd_init_db
        from project_db.db import session_scope

        cmd_init_db(argparse.Namespace())

        with session_scope() as s:
            assert s.query(Organization).count() > 0


class TestCliListBoards:
    @patch("project_db.connectors.monday.client.MondayClient")
    def test_list_boards_shows_boards(self, mock_class, capsys):
        from project_db.cli import cmd_list_boards

        mock_client = MagicMock()
        mock_class.return_value = mock_client
        mock_client.list_boards.return_value = [
            {
                "id": "123",
                "name": "CRM Board",
                "workspace": {"name": "Workspace 1"},
                "state": "active",
            }
        ]

        result = cmd_list_boards(argparse.Namespace())
        assert result == 0
        assert "CRM Board" in capsys.readouterr().out

    @patch("project_db.connectors.monday.client.MondayClient")
    def test_list_boards_empty(self, mock_class, capsys):
        from project_db.cli import cmd_list_boards

        mock_client = MagicMock()
        mock_class.return_value = mock_client
        mock_client.list_boards.return_value = []

        result = cmd_list_boards(argparse.Namespace())
        assert result == 0
        assert "No boards" in capsys.readouterr().out


class TestCliInspectBoard:
    @patch("project_db.connectors.monday.client.MondayClient")
    def test_inspect_board_shows_columns(self, mock_class, capsys):
        from project_db.cli import cmd_inspect_board

        mock_client = MagicMock()
        mock_class.return_value = mock_client
        mock_client.list_board_columns.return_value = [
            {"id": "name", "title": "Name", "type": "text"}
        ]
        mock_client.list_items.return_value = [
            {
                "id": "item1",
                "name": "Test Item",
                "group": {"title": "Group 1"},
                "column_values": [],
            }
        ]

        result = cmd_inspect_board(argparse.Namespace(board_id="123"))
        assert result == 0

    @patch("project_db.connectors.monday.client.MondayClient")
    def test_inspect_board_no_columns_returns_1(self, mock_class):
        from project_db.cli import cmd_inspect_board

        mock_client = MagicMock()
        mock_class.return_value = mock_client
        mock_client.list_board_columns.return_value = []

        result = cmd_inspect_board(argparse.Namespace(board_id="123"))
        assert result == 1


class TestCliSync:
    def test_sync_unknown_source_returns_2(self):
        from project_db.cli import cmd_sync

        result = cmd_sync(argparse.Namespace(source="not_a_real_source"))
        assert result == 2


class TestCliListSources:
    def test_available_sources_includes_monday_and_qb(self):
        from project_db.connectors import available_sources

        sources = available_sources()
        names = {s.value.lower() for s in sources}
        assert "monday" in names
        assert "quickbooks" in names


class TestCliAsk:
    def test_ask_runs_against_seeded_db(self, patched_session_factory):
        from project_db.cli import cmd_ask, cmd_init_db

        cmd_init_db(argparse.Namespace())
        result = cmd_ask(argparse.Namespace(question=["what", "active", "projects"]))
        assert result == 0

    def test_ask_non_canned_question_routes_to_llm(
        self, patched_session_factory, monkeypatch, capsys
    ):
        """A question matching no canned report escalates to the fast LLM."""
        from project_db.ai.providers import MockLLMProvider
        from project_db.cli import cmd_ask

        # Patch the fast provider so the test never touches the network.
        monkeypatch.setattr(
            "project_db.ai.get_fast_provider",
            lambda: MockLLMProvider(responses=["Here is the situation."]),
        )
        result = cmd_ask(argparse.Namespace(
            question=["what", "should", "i", "worry", "about"],
        ))
        out = capsys.readouterr().out
        assert result == 0
        assert "mode=llm" in out
        assert "Here is the situation." in out


class TestCliDaily:
    def test_daily_review_is_read_only_summary(
        self, patched_session_factory, session, client_factory, capsys
    ):
        from project_db.cli import cmd_daily

        client = client_factory(name="Daily Client")
        project = Project(
            name="923 Rockland",
            code="R923",
            status=ProjectStatus.ACTIVE,
            client_id=client.canonical_id,
        )
        session.add(project)
        session.commit()
        session.add(Task(
            title="Frame addition",
            status=TaskStatus.TODO,
            project_id=project.canonical_id,
        ))
        doc = Document(
            name="Contract.pdf",
            mime_type="application/pdf",
            url="https://drive/contract",
            storage_ref="doc-1",
            project_id=project.canonical_id,
        )
        session.add(doc)
        session.commit()
        session.add(DocumentText(
            document_id=doc.canonical_id,
            extracted_text="Total contract price: $12,000.00",
            extraction_method="pdf-pymupdf",
            token_count=6,
        ))
        session.commit()

        result = cmd_daily(argparse.Namespace(
            project=["923", "Rockland"],
            propose_timelines=False,
            limit=5,
            token_budget=20_000,
            max_docs=30,
            max_output_tokens=3000,
        ))
        out = capsys.readouterr().out

        assert result == 0
        assert "=== DAILY REVIEW ===" in out
        assert "Project: 923 Rockland" in out
        assert "Unresolved Dateless Tasks" in out
        assert "Frame addition" in out
        assert "--propose-timelines" in out


class TestCliListExternal:
    def test_list_external_invalid_uuid_returns_2(self):
        from project_db.cli import cmd_list_external

        result = cmd_list_external(
            argparse.Namespace(entity_type="Client", canonical_id="not-a-uuid")
        )
        assert result == 2


class TestCliDoctor:
    def test_crm_deal_placeholder_is_not_project_health_flag(
        self, patched_session_factory, session, client_factory, capsys
    ):
        from project_db.cli import cmd_doctor

        client = client_factory(name="CRM Client")
        session.add(
            Deal(
                name="Amazon deal",
                value=Decimal("55000.00"),
                stage=LeadStage.WON,
                client_id=client.canonical_id,
            )
        )
        session.add(
            Project(
                name="Project - Amazon deal",
                code="MONDAY-123",
                status=ProjectStatus.PROPOSED,
                client_id=client.canonical_id,
            )
        )
        session.commit()

        result = cmd_doctor(argparse.Namespace())
        out = capsys.readouterr().out

        assert result == 0
        assert "CRM deal: Amazon deal" in out
        assert "Project - Amazon deal': no Drive folder" not in out
        assert "Project - Amazon deal': 0 documents and 0 tasks" not in out


class TestCliProposals:
    """`proposals accept/reject` with no id list the pending queue; with the
    literal 'all' they act on every pending proposal (gated behind --yes)."""

    def _seed_pending_proposal(self, session, client_factory) -> Proposal:
        """One project + task + a PENDING timeline proposal; returns the proposal."""
        import json as _json

        client = client_factory(name="Prop Client")
        project = Project(
            name="Prop Project", code="PP",
            status=ProjectStatus.ACTIVE, client_id=client.canonical_id,
        )
        session.add(project)
        session.commit()
        task = Task(
            title="Pour slab", status=TaskStatus.TODO,
            project_id=project.canonical_id,
        )
        session.add(task)
        session.commit()
        proposal = Proposal(
            entity_type="Task",
            entity_id=task.canonical_id,
            field_name="timeline",
            proposed_value=_json.dumps({
                "start_date": "2026-06-01", "end_date": "2026-06-07",
                "task_title": "Pour slab", "reasoning": "contract milestone",
            }),
            confidence=0.9,
            status=ProposalStatus.PENDING,
        )
        session.add(proposal)
        session.commit()
        return proposal

    def test_accept_with_no_id_lists_pending(
        self, patched_session_factory, session, client_factory, capsys
    ):
        from project_db.cli import cmd_proposals

        proposal = self._seed_pending_proposal(session, client_factory)
        result = cmd_proposals(argparse.Namespace(
            proposals_action="accept", proposal_id=None,
            dry_run=False, by=None, yes=False,
        ))
        out = capsys.readouterr().out
        assert result == 0
        assert "1 pending proposal(s)" in out
        assert str(proposal.canonical_id) in out

    def test_accept_with_no_id_and_no_proposals(
        self, patched_session_factory, capsys
    ):
        from project_db.cli import cmd_proposals

        result = cmd_proposals(argparse.Namespace(
            proposals_action="accept", proposal_id=None,
            dry_run=False, by=None, yes=False,
        ))
        out = capsys.readouterr().out
        assert result == 0
        assert "No pending proposals" in out

    def test_accept_all_without_yes_changes_nothing(
        self, patched_session_factory, session, client_factory, capsys
    ):
        from project_db.cli import cmd_proposals

        proposal = self._seed_pending_proposal(session, client_factory)
        result = cmd_proposals(argparse.Namespace(
            proposals_action="accept", proposal_id="all",
            dry_run=False, by=None, yes=False,
        ))
        out = capsys.readouterr().out
        assert result == 1            # refused -- a real bulk write needs --yes
        assert "--yes" in out
        session.expire_all()
        reloaded = session.query(Proposal).filter_by(
            canonical_id=proposal.canonical_id).one()
        assert reloaded.status == ProposalStatus.PENDING

    def test_reject_all_with_yes_rejects_every_pending(
        self, patched_session_factory, session, client_factory, capsys
    ):
        from project_db.cli import cmd_proposals

        proposal = self._seed_pending_proposal(session, client_factory)
        result = cmd_proposals(argparse.Namespace(
            proposals_action="reject", proposal_id="all",
            reason="bulk cleanup", by="tester", yes=True,
        ))
        out = capsys.readouterr().out
        assert result == 0
        assert "rejected 1" in out
        session.expire_all()
        reloaded = session.query(Proposal).filter_by(
            canonical_id=proposal.canonical_id).one()
        assert reloaded.status == ProposalStatus.REJECTED
        assert reloaded.rejection_reason == "bulk cleanup"
