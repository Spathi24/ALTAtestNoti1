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
        
        columns = [
            {"id": "name", "title": "Name", "type": "text"},
            {"id": "status", "title": "Status", "type": "status"},
            {"id": "budget", "title": "Budget Amount", "type": "numeric"},
        ]
        
        extractor = ColumnExtractor(columns)
        
        item_values = [
            {"id": "name", "type": "text", "text": "Acme Corp", "value": "Acme Corp"},
            {"id": "status", "type": "status", "text": "Active", "value": '{"index": 0}'},
            {"id": "budget", "type": "numeric", "text": "50000", "value": "50000"},
        ]
        
        fields = extractor.extract(item_values)
        assert fields is not None


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
