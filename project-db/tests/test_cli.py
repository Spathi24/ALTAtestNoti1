"""Tests for CLI subcommands.

The CLI lazily imports MondayClient / ColumnExtractor inside each command
function, so patches target the import source, not the cli module.
"""
from __future__ import annotations

import argparse
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy.orm import Session, sessionmaker

from project_db.db.models import Organization


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


class TestCliListExternal:
    def test_list_external_invalid_uuid_returns_2(self):
        from project_db.cli import cmd_list_external

        result = cmd_list_external(
            argparse.Namespace(entity_type="Client", canonical_id="not-a-uuid")
        )
        assert result == 2
