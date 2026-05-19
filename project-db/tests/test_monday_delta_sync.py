"""Tests for Monday delta sync via Board.activity_logs.

The shape we're verifying:

  * list_activity_logs builds the right GraphQL request shape
  * sync(delta=True) skips boards with no activity since the cursor
  * sync(delta=True) does NOT skip boards on the first delta run
    (no cursor yet -> treat as changed)
  * Cursors are stored per-board as ExternalId rows with the right shape
  * sync(delta=True) saves a fresh cursor after a successful board sync
  * activity_logs probe errors are swallowed (board is treated as changed,
    not as a sync-blocker)
  * sync() without delta=True behaves identically to before this feature
    (no regression for the default path)
"""
from __future__ import annotations

from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest

from project_db.connectors.monday.client import MondayClient
from project_db.connectors.monday.connector import MondayConnector
from project_db.db.models import ExternalId, SourceSystem


# ---------------------------------------------------------------------------
# Client method
# ---------------------------------------------------------------------------


class TestListActivityLogs:
    def test_builds_correct_request(self):
        client = MondayClient(token="test")
        with patch.object(client, "query") as mock_query:
            mock_query.return_value = {
                "boards": [{
                    "activity_logs": [
                        {"id": "1", "created_at": "2026-05-16T10:00:00Z",
                         "event": "update_column_value", "entity": "pulse",
                         "user_id": "u1", "data": "{}"},
                    ]
                }]
            }
            ts = datetime(2026, 5, 15, 12, 0, 0)
            events = client.list_activity_logs(123, from_ts=ts, limit=50)

        assert len(events) == 1
        assert events[0]["event"] == "update_column_value"
        call_vars = mock_query.call_args[0][1]
        assert call_vars["board_id"] == [123]
        assert call_vars["from_ts"] == "2026-05-15T12:00:00"
        assert call_vars["limit"] == 50
        assert call_vars["page"] == 1

    def test_paginates_until_short_page(self):
        client = MondayClient(token="test")
        # Page 1: full (100 events), page 2: partial (5), stop.
        pages = [
            {"boards": [{"activity_logs": [{"id": str(i)} for i in range(100)]}]},
            {"boards": [{"activity_logs": [{"id": str(i)} for i in range(100, 105)]}]},
        ]
        with patch.object(client, "query", side_effect=pages):
            events = client.list_activity_logs(99, limit=100)
        assert len(events) == 105

    def test_empty_returns_empty_list(self):
        client = MondayClient(token="test")
        with patch.object(client, "query") as mock_query:
            mock_query.return_value = {"boards": [{"activity_logs": []}]}
            assert client.list_activity_logs(1) == []

    def test_no_board_returned_returns_empty(self):
        """If the board id doesn't resolve (deleted etc.), don't blow up."""
        client = MondayClient(token="test")
        with patch.object(client, "query", return_value={"boards": []}):
            assert client.list_activity_logs(999) == []

    def test_max_pages_safety_cap(self):
        """If the server kept returning full pages forever, we'd still stop."""
        client = MondayClient(token="test")
        full_page = {"boards": [{"activity_logs": [{"id": str(i)} for i in range(100)]}]}
        with patch.object(client, "query", return_value=full_page) as mock_query:
            client.list_activity_logs(1, limit=100, max_pages=3)
        # Should have stopped after 3 page calls, not run forever.
        assert mock_query.call_count == 3


# ---------------------------------------------------------------------------
# Connector cursor storage
# ---------------------------------------------------------------------------


class TestCursorStorage:
    def _make_connector(self, session, org, mock_monday_client):
        return MondayConnector(
            session=session,
            organization_id=org.canonical_id,
            config={"api_token": "test"},
        )

    def test_no_cursor_returns_none(self, session, org, mock_monday_client):
        # Bypass real auth -- inject the mock client directly.
        c = MondayConnector(session=session, organization_id=org.canonical_id, config={"api_token": "test"})
        c.client = mock_monday_client
        assert c._load_board_cursor(123) is None

    def test_save_and_load_roundtrip(self, session, org, mock_monday_client):
        c = MondayConnector(session=session, organization_id=org.canonical_id, config={"api_token": "test"})
        c.client = mock_monday_client
        ts = datetime(2026, 5, 16, 9, 30, 0)
        c._save_board_cursor(123, ts)
        loaded = c._load_board_cursor(123)
        assert loaded == ts

    def test_cursor_is_externalid_with_sync_state_type(self, session, org, mock_monday_client):
        c = MondayConnector(session=session, organization_id=org.canonical_id, config={"api_token": "test"})
        c.client = mock_monday_client
        c._save_board_cursor(456, datetime(2026, 5, 16))
        row = (
            session.query(ExternalId)
            .filter_by(
                source=SourceSystem.MONDAY,
                entity_type="SyncState",
                external_key="monday_board_cursor:456",
            )
            .one()
        )
        assert row.external_url.startswith("2026-05-16")

    def test_save_overwrites_existing_cursor(self, session, org, mock_monday_client):
        c = MondayConnector(session=session, organization_id=org.canonical_id, config={"api_token": "test"})
        c.client = mock_monday_client
        c._save_board_cursor(789, datetime(2026, 5, 15))
        c._save_board_cursor(789, datetime(2026, 5, 16))
        assert c._load_board_cursor(789) == datetime(2026, 5, 16)
        # Still exactly one row.
        n = (
            session.query(ExternalId)
            .filter_by(external_key="monday_board_cursor:789")
            .count()
        )
        assert n == 1

    def test_garbage_cursor_returns_none(self, session, org, mock_monday_client):
        c = MondayConnector(session=session, organization_id=org.canonical_id, config={"api_token": "test"})
        c.client = mock_monday_client
        ext = ExternalId(
            source=SourceSystem.MONDAY,
            entity_type="SyncState",
            external_key="monday_board_cursor:bad",
            external_url="not a timestamp",
            canonical_id=org.canonical_id,
        )
        session.add(ext); session.commit()
        assert c._load_board_cursor("bad") is None


# ---------------------------------------------------------------------------
# board_has_changes gate
# ---------------------------------------------------------------------------


class TestBoardHasChanges:
    def test_no_cursor_treats_as_changed(self, session, org, mock_monday_client):
        c = MondayConnector(session=session, organization_id=org.canonical_id, config={"api_token": "test"})
        c.client = mock_monday_client
        # No cursor saved for board 1 -- should return True without even calling activity_logs.
        mock_monday_client.list_activity_logs = MagicMock()
        assert c._board_has_changes(1) is True
        mock_monday_client.list_activity_logs.assert_not_called()

    def test_no_events_since_cursor_treats_as_unchanged(self, session, org, mock_monday_client):
        c = MondayConnector(session=session, organization_id=org.canonical_id, config={"api_token": "test"})
        c.client = mock_monday_client
        c._save_board_cursor(2, datetime(2026, 5, 15))
        mock_monday_client.list_activity_logs = MagicMock(return_value=[])
        assert c._board_has_changes(2) is False

    def test_events_since_cursor_treats_as_changed(self, session, org, mock_monday_client):
        c = MondayConnector(session=session, organization_id=org.canonical_id, config={"api_token": "test"})
        c.client = mock_monday_client
        c._save_board_cursor(3, datetime(2026, 5, 15))
        mock_monday_client.list_activity_logs = MagicMock(
            return_value=[{"id": "evt1", "event": "update_column_value"}]
        )
        assert c._board_has_changes(3) is True

    def test_probe_failure_treats_as_changed(self, session, org, mock_monday_client):
        """An activity_logs API failure must not block sync -- treat as changed."""
        c = MondayConnector(session=session, organization_id=org.canonical_id, config={"api_token": "test"})
        c.client = mock_monday_client
        c._save_board_cursor(4, datetime(2026, 5, 15))
        mock_monday_client.list_activity_logs = MagicMock(side_effect=RuntimeError("API down"))
        assert c._board_has_changes(4) is True


# ---------------------------------------------------------------------------
# sync(delta=True) end-to-end with mocked client
# ---------------------------------------------------------------------------


class TestSyncDeltaEndToEnd:
    def _build_connector(self, session, org):
        c = MondayConnector(
            session=session, organization_id=org.canonical_id,
            config={"api_token": "test"},
        )
        client = MagicMock()
        client.list_workspaces.return_value = []
        client.list_users.return_value = []
        client.list_boards.return_value = [
            {"id": "100", "name": "Active Projects", "state": "active",
             "workspace": {"name": "Construction"}},
            {"id": "200", "name": "Active Projects 2", "state": "active",
             "workspace": {"name": "Construction"}},
        ]
        # Make _classify_board return something so boards pass the filter.
        # We'll patch _sync_board to a no-op so we can measure WHICH boards get to it.
        c.client = client
        return c, client

    def test_first_delta_run_syncs_all_boards_and_saves_cursors(self, session, org):
        c, client = self._build_connector(session, org)
        client.list_activity_logs = MagicMock(return_value=[])  # would say "no changes"
        with patch.object(c, "_sync_board") as mock_sync, \
             patch.object(c, "_classify_board", return_value="Project"):
            c.sync(delta=True)
        # No cursor exists yet -> both boards processed.
        assert mock_sync.call_count == 2
        # Cursors now saved for both.
        assert c._load_board_cursor("100") is not None
        assert c._load_board_cursor("200") is not None

    def test_second_run_skips_unchanged_boards(self, session, org):
        c, client = self._build_connector(session, org)
        # Pre-seed cursors so this is treated as a re-run.
        c._save_board_cursor("100", datetime.utcnow() - timedelta(hours=1))
        c._save_board_cursor("200", datetime.utcnow() - timedelta(hours=1))
        # Board 100 has events, board 200 has none.
        client.list_activity_logs = MagicMock(
            side_effect=lambda bid, **_: (
                [{"id": "evt"}] if bid == 100 else []
            )
        )
        with patch.object(c, "_sync_board") as mock_sync, \
             patch.object(c, "_classify_board", return_value="Project"):
            c.sync(delta=True)
        # Only board 100 should have been synced.
        synced_board_ids = [call.args[0]["id"] for call in mock_sync.call_args_list]
        assert synced_board_ids == ["100"]

    def test_non_delta_sync_unchanged_behavior(self, session, org):
        """sync() without delta=True must still sync every board."""
        c, client = self._build_connector(session, org)
        # Even with a stored cursor and "no changes," non-delta sync ignores it.
        c._save_board_cursor("100", datetime.utcnow())
        client.list_activity_logs = MagicMock(return_value=[])
        with patch.object(c, "_sync_board") as mock_sync, \
             patch.object(c, "_classify_board", return_value="Project"):
            c.sync()  # default: delta=False
        assert mock_sync.call_count == 2
        client.list_activity_logs.assert_not_called()


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


class TestCLIParsing:
    def test_delta_flag_parses(self):
        from project_db.cli import build_parser
        ns = build_parser().parse_args(["sync", "monday", "--delta"])
        assert ns.cmd == "sync"
        assert ns.source == "monday"
        assert ns.delta is True

    def test_delta_default_false(self):
        from project_db.cli import build_parser
        ns = build_parser().parse_args(["sync", "monday"])
        assert ns.delta is False

    def test_llm_test_parser(self):
        from project_db.cli import build_parser
        ns = build_parser().parse_args(
            ["llm-test", "Rockland",
             "--token-budget", "5000",
             "--max-docs", "3",
             "--max-output-tokens", "100"]
        )
        assert ns.cmd == "llm-test"
        assert ns.project == "Rockland"
        assert ns.token_budget == 5000
        assert ns.max_docs == 3
        assert ns.max_output_tokens == 100

    def test_llm_test_parser_defaults(self):
        from project_db.cli import build_parser
        ns = build_parser().parse_args(["llm-test", "Rockland"])
        # Defaults are tuned for local CPU models -- small enough that
        # a fresh laptop+Ollama install doesn't time out on first try.
        assert ns.token_budget == 20_000
        assert ns.max_docs == 3
        assert ns.max_output_tokens == 300
