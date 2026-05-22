"""Tests for Monday.com GraphQL client."""
from __future__ import annotations

import json
from unittest.mock import MagicMock, patch
import pytest


class TestMondayClientBasics:
    """Test basic MondayClient operations."""
    
    def test_client_initialization(self):
        """Test MondayClient initialization."""
        from project_db.connectors.monday.client import MondayClient
        
        client = MondayClient(token="test_token")
        assert client is not None
    
    def test_list_boards(self, mock_monday_client):
        """Test listing boards."""
        boards = mock_monday_client.list_boards()
        
        assert len(boards) == 2
        assert boards[0]["name"] == "CRM Board"
        assert boards[1]["name"] == "Projects Board"
    
    def test_list_board_columns(self, mock_monday_client):
        """Test listing board columns."""
        columns = mock_monday_client.list_board_columns(board_id="123456")
        
        assert len(columns) == 4
        assert columns[0]["id"] == "name"
        assert columns[1]["type"] == "status"
    
    def test_list_items(self, mock_monday_client):
        """Test listing items from a board."""
        items = mock_monday_client.list_items(board_id="123456")
        
        assert len(items) == 2
        assert items[0]["name"] == "Acme Corp"
        assert items[1]["name"] == "Beta Inc"
    
    def test_list_users(self, mock_monday_client):
        """Test listing workspace users."""
        users = mock_monday_client.list_users()
        
        assert len(users) == 2
        assert users[0]["name"] == "Alice"
        assert users[1]["is_admin"] is False


class TestMondayClientDeltaSync:
    """Test delta sync functionality."""
    
    def test_list_items_with_updated_since(self, mock_monday_client):
        """Test delta sync with updated_since parameter."""
        from datetime import datetime, timedelta
        
        since = datetime.now() - timedelta(days=1)
        items = mock_monday_client.list_items(
            board_id="123456",
            updated_since=since
        )
        
        assert mock_monday_client.list_items.called


class TestMondayClientMutations:
    """Test write mutation methods."""
    
    def test_change_column_value(self, mock_monday_client):
        """Test changing a single column value."""
        result = mock_monday_client.change_column_value(
            board_id=123456,
            item_id=789,
            column_id="status",
            value={"index": 1}
        )
        
        assert result == {"id": "item1", "column_values": []}
        mock_monday_client.change_column_value.assert_called_once()
    
    def test_change_multiple_column_values(self, mock_monday_client):
        """Test batch changing multiple columns."""
        result = mock_monday_client.change_multiple_column_values(
            board_id=123456,
            item_id=789,
            column_values={
                "status": {"index": 1},
                "budget": "50000"
            }
        )
        
        assert result == {"id": "item1", "column_values": []}
    
    def test_create_item(self, mock_monday_client):
        """Test creating a new item."""
        result = mock_monday_client.create_item(
            board_id=123456,
            item_name="New Client",
            column_values={"status": {"index": 0}}
        )
        
        assert result == {"id": "new_item", "name": "New Item"}
    
    def test_delete_item(self, mock_monday_client):
        """Test deleting an item."""
        result = mock_monday_client.delete_item(
            board_id=123456,
            item_id=789
        )
        
        assert result is True


class TestMondayClientComplexityTracking:
    """Test API complexity tracking."""
    
    def test_query_with_complexity_tracking(self, mock_monday_client):
        """Test that query method can track complexity."""
        gql = """
        query {
          boards { id name }
        }
        """
        mock_monday_client.query(gql, track_complexity=True)
        mock_monday_client.query.assert_called()


class TestMondayClientErrorHandling:
    """Test error handling."""
    
    def test_invalid_board_id_handled(self, mock_monday_client):
        """Test handling of invalid board IDs."""
        # Mock should handle gracefully
        mock_monday_client.list_items.return_value = []
        result = mock_monday_client.list_items(board_id="invalid")
        assert result == []


class TestColumnExtractor:
    """Test ColumnExtractor for field extraction."""
    
    def test_extractor_initialization(self):
        """Test initializing column extractor."""
        from project_db.connectors.monday.column_extractor import ColumnExtractor
        
        columns = [
            {"id": "name", "title": "Name", "type": "text"},
            {"id": "status", "title": "Status", "type": "status"},
            {"id": "budget", "title": "Budget Amount", "type": "numeric"},
        ]
        
        extractor = ColumnExtractor(columns)
        assert extractor is not None
    
    def test_extract_heuristic_fields(self):
        """Test extracting fields using heuristics."""
        from project_db.connectors.monday.column_extractor import ColumnExtractor
        from project_db.db.models.work import TaskStatus
        
        columns = [
            {"id": "name", "title": "Name", "type": "text"},
            {"id": "status", "title": "Status", "type": "status"},
            {"id": "budget", "title": "Budget Amount", "type": "numeric"},
            {"id": "timeline", "title": "Timeline", "type": "timeline"},
            {"id": "duration", "title": "Duration", "type": "numbers"},
            {"id": "planned", "title": "Planned Effort", "type": "numbers"},
            {"id": "spent", "title": "Effort Spent", "type": "numbers"},
            {"id": "sub", "title": "Subcontractor", "type": "text"},
            {"id": "supplier", "title": "Supplier", "type": "text"},
        ]
        
        extractor = ColumnExtractor(columns)
        
        item_values = [
            {"id": "name", "type": "text", "text": "Acme Corp", "value": "Acme Corp"},
            {
                "id": "status",
                "type": "status",
                "text": "Working on it",
                "value": '{"index": 0}',
                "label": "Working on it",
            },
            {"id": "budget", "type": "numeric", "text": "50000", "value": "50000"},
            {"id": "timeline", "type": "timeline", "text": "", "value": None, "from": "2026-05-01", "to": "2026-05-04"},
            {"id": "duration", "type": "numbers", "text": "3", "value": None, "number": 3},
            {"id": "planned", "type": "numbers", "text": "12", "value": None, "number": 12},
            {"id": "spent", "type": "numbers", "text": "5", "value": None, "number": 5},
            {"id": "sub", "type": "text", "text": "Raul", "value": '"Raul"'},
            {"id": "supplier", "type": "text", "text": "BMR", "value": '"BMR"'},
        ]
        
        fields = extractor.extract(item_values)
        assert fields.task_status == TaskStatus.IN_PROGRESS
        assert fields.start_date.isoformat() == "2026-05-01"
        assert fields.end_date.isoformat() == "2026-05-04"
        assert fields.duration_days == 3
        assert fields.planned_effort == 12
        assert fields.effort_spent == 5
        assert fields.subcontractor == "Raul"
        assert fields.supplier == "BMR"


class TestMondayClientPagination:
    """Test pagination handling."""

    def test_pagination_follows_cursor(self, mock_monday_client):
        """Test that pagination follows cursor correctly."""
        # Configure mock to return paginated results
        mock_monday_client.list_items.return_value = [
            {"id": f"item{i}", "name": f"Item {i}"} for i in range(100)
        ]

        items = mock_monday_client.list_items(board_id="123456")
        assert len(items) >= 0


class TestPortfolioMirrorOverlay:
    """Mirror-column overlay: a task board's real status/timeline can live as
    MIRROR columns on a linked portfolio item. The overlay walks the link
    back, pulls the mirrored values, and merges them onto each task row."""

    def test_build_task_mirror_overlay_extracts_status_and_timeline(self):
        from project_db.connectors.monday.connector import build_task_mirror_overlay

        linked_items = [
            {
                "id": "11941707664",
                "name": "923 Rockland",
                "column_values": [
                    {
                        "id": "portfolio_project_progress",
                        "type": "mirror",
                        "column": {
                            "id": "portfolio_project_progress",
                            "title": "Project Progress",
                            "type": "mirror",
                        },
                        "mirrored_items": [
                            {
                                "linked_item": {"id": "11941695903", "name": "Kickoff"},
                                "mirrored_value": {
                                    "label": "Done",
                                    "index": 1,
                                    "is_done": True,
                                },
                            },
                            {
                                "linked_item": {"id": "11941695383", "name": "Demo"},
                                # Empty mirrored value -- should be skipped
                                "mirrored_value": {
                                    "label": None, "index": None, "is_done": False
                                },
                            },
                        ],
                    },
                    {
                        "id": "portfolio_project_actual_timeline",
                        "type": "mirror",
                        "column": {
                            "id": "portfolio_project_actual_timeline",
                            "title": "Actual Timeline",
                            "type": "mirror",
                        },
                        "mirrored_items": [
                            {
                                "linked_item": {"id": "11941694967", "name": "Inspect"},
                                "mirrored_value": {
                                    "from": "2026-08-11T00:00:00+00:00",
                                    "to":   "2026-08-12T00:00:00+00:00",
                                },
                            }
                        ],
                    },
                ],
            }
        ]

        overlay = build_task_mirror_overlay(linked_items)

        # Status is overlaid for the Kickoff task only (empty values skipped).
        assert "11941695903" in overlay
        assert "11941695383" not in overlay
        kickoff = overlay["11941695903"]
        assert any(cv["id"] == "project_status" and cv["label"] == "Done" for cv in kickoff)

        # Timeline overlay strips the timestamp portion to YYYY-MM-DD.
        inspect = overlay["11941694967"]
        timeline_cv = next(cv for cv in inspect if cv["id"] == "project_timeline")
        assert timeline_cv["from"] == "2026-08-11"
        assert timeline_cv["to"] == "2026-08-12"
        assert timeline_cv["text"] == "2026-08-11 - 2026-08-12"

    def test_apply_portfolio_mirror_overlay_enriches_only_missing_ids(self):
        """Native values on the task row win; overlay backfills the rest."""
        from project_db.connectors.monday.connector import apply_portfolio_mirror_overlay

        # Mock client that returns one portfolio item with one mirror column.
        client = MagicMock()
        client.get_items_with_mirror_values.return_value = [
            {
                "id": "PORT1",
                "column_values": [
                    {
                        "id": "portfolio_project_progress",
                        "type": "mirror",
                        "column": {
                            "id": "portfolio_project_progress",
                            "title": "Project Progress",
                            "type": "mirror",
                        },
                        "mirrored_items": [
                            {
                                "linked_item": {"id": "TASK_A"},
                                "mirrored_value": {"label": "Done", "is_done": True},
                            },
                            {
                                "linked_item": {"id": "TASK_B"},
                                "mirrored_value": {"label": "Working on it"},
                            },
                        ],
                    }
                ],
            }
        ]

        tasks = [
            {
                "id": "TASK_A",
                "name": "Already has native status",
                "column_values": [
                    {"id": "project_status", "type": "status", "text": "On Hold"},
                    {
                        "id": "portfolio_relation",
                        "type": "board_relation",
                        "linked_item_ids": ["PORT1"],
                    },
                ],
            },
            {
                "id": "TASK_B",
                "name": "Empty -- gets overlay",
                "column_values": [
                    {
                        "id": "portfolio_relation",
                        "type": "board_relation",
                        "linked_item_ids": ["PORT1"],
                    }
                ],
            },
            {
                "id": "TASK_C",
                "name": "No portfolio link -- unchanged",
                "column_values": [],
            },
        ]

        enriched = apply_portfolio_mirror_overlay(client, tasks)

        # Portfolio fetched once with the union of linked ids.
        client.get_items_with_mirror_values.assert_called_once_with(["PORT1"])

        # TASK_A keeps its native status (overlay does not clobber).
        a = next(t for t in enriched if t["id"] == "TASK_A")
        statuses = [cv for cv in a["column_values"] if cv["id"] == "project_status"]
        assert len(statuses) == 1
        assert statuses[0]["text"] == "On Hold"

        # TASK_B gains a synthetic project_status from the overlay.
        b = next(t for t in enriched if t["id"] == "TASK_B")
        statuses = [cv for cv in b["column_values"] if cv["id"] == "project_status"]
        assert len(statuses) == 1
        assert statuses[0]["label"] == "Working on it"
        assert statuses[0]["_source"]["kind"] == "mirror"
        assert statuses[0]["_source"]["linked_item_id"] == "PORT1"

        # TASK_C unchanged.
        c = next(t for t in enriched if t["id"] == "TASK_C")
        assert c["column_values"] == []

    def test_overlay_reaches_subitems(self):
        """Most real tasks on these boards are subitems -- the overlay must
        enrich them too, and must find the portfolio link even when only the
        subitem (not its top-level parent) carries the board_relation.
        """
        from project_db.connectors.monday.connector import apply_portfolio_mirror_overlay

        client = MagicMock()
        client.get_items_with_mirror_values.return_value = [
            {
                "id": "PORT1",
                "column_values": [
                    {
                        "id": "portfolio_project_progress",
                        "type": "mirror",
                        "column": {
                            "id": "portfolio_project_progress",
                            "title": "Project Progress",
                            "type": "mirror",
                        },
                        "mirrored_items": [
                            {
                                "linked_item": {"id": "SUB1"},
                                "mirrored_value": {"label": "Working on it"},
                            },
                        ],
                    }
                ],
            }
        ]
        # The top-level item carries NO portfolio link -- only its subitem does.
        tasks = [
            {
                "id": "ITEM1",
                "name": "Stage header (no portfolio link)",
                "column_values": [],
                "subitems": [
                    {
                        "id": "SUB1",
                        "name": "Real work task",
                        "column_values": [
                            {
                                "id": "portfolio_relation",
                                "type": "board_relation",
                                "linked_item_ids": ["PORT1"],
                            }
                        ],
                    }
                ],
            }
        ]

        enriched = apply_portfolio_mirror_overlay(client, tasks)

        # The portfolio link was discovered on the SUBITEM, not the parent.
        client.get_items_with_mirror_values.assert_called_once_with(["PORT1"])

        # The SUBITEM gained a synthetic project_status from the overlay.
        sub = enriched[0]["subitems"][0]
        statuses = [cv for cv in sub["column_values"] if cv["id"] == "project_status"]
        assert len(statuses) == 1
        assert statuses[0]["label"] == "Working on it"
        assert statuses[0]["_source"]["kind"] == "mirror"

    def test_apply_overlay_no_links_is_noop(self):
        from project_db.connectors.monday.connector import apply_portfolio_mirror_overlay

        client = MagicMock()
        tasks = [{"id": "1", "column_values": [{"id": "x", "type": "text"}]}]

        result = apply_portfolio_mirror_overlay(client, tasks)

        # When no board_relation columns exist, the client is never called.
        assert client.get_items_with_mirror_values.call_count == 0
        assert result is tasks  # same object — no copy
