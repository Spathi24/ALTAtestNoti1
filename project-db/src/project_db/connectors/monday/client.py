"""Monday.com GraphQL client.

Handles auth, versioned API headers, full cursor-based pagination, complexity
tracking, and write mutations. All callers get plain Python dicts — no SDK objects.

Env vars:
  MONDAY_API_TOKEN — personal or service-account API token
                     (Monday > avatar > Admin > API)

Complexity & Limits:
  - Personal tokens: 10M complexity points/min combined (read+write)
  - Pro tier: 2,500 queries/min, 5M complexity/min
  - Enterprise: 5,000 queries/min, 5M complexity/min
  - Daily limit: Pro=10k calls, Enterprise=25k calls

Delta Sync:
  Use list_items_updated_since() to fetch only changed items (cheaper than full resync).
  Store last_synced_at per board and pass to subsequent syncs.

Write Operations:
  - change_column_value() — update single item field
  - change_multiple_column_values() — batch update (preferred, 150x cheaper)
  - create_item() — create new item
  - delete_item() — delete item
"""
from __future__ import annotations

import json
import logging
import os
from datetime import datetime
from typing import Any

import httpx

logger = logging.getLogger(__name__)

API_URL = "https://api.monday.com/v2"
API_VERSION = "2026-07"
PAGE_LIMIT = 200  # items per cursor page (max 500, 200 keeps complexity low)


class MondayClient:
    def __init__(self, token: str | None = None):
        self.token = token or os.environ.get("MONDAY_API_TOKEN")
        if not self.token:
            raise RuntimeError(
                "MONDAY_API_TOKEN not set. "
                "Get one at Monday > avatar > Admin > API."
            )
        self._http = httpx.Client(
            base_url=API_URL,
            headers={
                "Authorization": self.token,
                "Content-Type": "application/json",
                "API-Version": API_VERSION,
            },
            timeout=30.0,
        )
        self.complexity_before: int | None = None
        self.complexity_after: int | None = None

    # ------------------------------------------------------------------
    # Low-level runner with complexity tracking
    # ------------------------------------------------------------------

    def query(
        self,
        gql: str,
        variables: dict[str, Any] | None = None,
        track_complexity: bool = False,
    ) -> dict[str, Any]:
        """Execute a GraphQL operation. Returns data dict. Raises on errors.
        
        If track_complexity=True, embeds complexity tracking and logs result.
        """
        if track_complexity:
            # Wrap query to include complexity information
            gql = f"""
            {{
              complexity {{ before after query }}
              result: {gql.strip()}
            }}
            """
        
        resp = self._http.post(
            "",
            json={"query": gql, "variables": variables or {}},
        )
        resp.raise_for_status()
        payload = resp.json()
        if "errors" in payload:
            raise RuntimeError(f"Monday API error: {payload['errors']}")
        
        data = payload["data"]
        
        # Extract and log complexity if present
        if track_complexity and "complexity" in data:
            complexity = data.pop("complexity")
            self.complexity_before = complexity.get("before")
            self.complexity_after = complexity.get("after")
            query_cost = complexity.get("query", 0)
            logger.info(
                f"API Complexity — cost={query_cost}, before={self.complexity_before}, "
                f"after={self.complexity_after}"
            )
        
        return data

    # ------------------------------------------------------------------
    # Workspaces & boards
    # ------------------------------------------------------------------

    def list_workspaces(self) -> list[dict[str, Any]]:
        data = self.query("query { workspaces { id name kind description } }")
        return data.get("workspaces") or []

    def list_boards(
        self,
        workspace_ids: list[int] | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        gql = """
        query ($workspace_ids: [ID], $limit: Int!) {
          boards(workspace_ids: $workspace_ids, limit: $limit, order_by: created_at) {
            id name board_kind state
            workspace { id name }
          }
        }
        """
        variables: dict[str, Any] = {"limit": limit}
        if workspace_ids:
            variables["workspace_ids"] = workspace_ids
        return self.query(gql, variables).get("boards") or []

    # ------------------------------------------------------------------
    # Board columns — call once per board to get the schema
    # ------------------------------------------------------------------

    def list_board_columns(self, board_id: int) -> list[dict[str, Any]]:
        """Return every column definition for a board.

        Each dict: id, title, type, settings_str (JSON with label maps for
        status/dropdown columns).
        """
        gql = """
        query ($board_id: [ID!]!) {
          boards(ids: $board_id) {
            columns { id title type settings_str }
          }
        }
        """
        data = self.query(gql, {"board_id": [board_id]})
        boards = data.get("boards") or []
        return boards[0].get("columns") or [] if boards else []

    # ------------------------------------------------------------------
    # Items — full cursor pagination with delta sync support
    # ------------------------------------------------------------------

    def list_items(
        self,
        board_id: int,
        limit: int = PAGE_LIMIT,
        updated_since: datetime | None = None,
    ) -> list[dict[str, Any]]:
        """Fetch items on a board, optionally filtering by updated_at timestamp.
        
        If updated_since is provided, only returns items updated after that time
        (delta sync). This dramatically reduces API cost for large boards.
        
        Always follows cursor pages automatically.
        """
        where_clause = ""
        if updated_since:
            # Filter for items updated after the given timestamp
            # Monday's API uses ISO-8601 format
            iso_time = updated_since.isoformat()
            where_clause = f', updated_after: "{iso_time}"'
            logger.debug(
                f"Delta sync for board {board_id}: fetching items updated since {iso_time}"
            )
        
        first_page_gql = f"""
        query ($board_id: [ID!]!, $limit: Int!) {{
          boards(ids: $board_id) {{
            items_page(limit: $limit{where_clause}) {{
              cursor
              items {{
                id name state created_at updated_at
                group {{ id title }}
                column_values {{ id type text value }}
              }}
            }}
          }}
        }}
        """
        next_page_gql = """
        query ($cursor: String!, $limit: Int!) {
          next_items_page(cursor: $cursor, limit: $limit) {
            cursor
            items {
              id name state created_at updated_at
              group { id title }
              column_values { id type text value }
            }
          }
        }
        """
        data = self.query(first_page_gql, {"board_id": [board_id], "limit": limit})
        boards = data.get("boards") or []
        if not boards:
            return []

        page = boards[0].get("items_page") or {}
        all_items: list[dict[str, Any]] = list(page.get("items") or [])
        cursor = page.get("cursor")

        while cursor:
            data = self.query(next_page_gql, {"cursor": cursor, "limit": limit})
            page = data.get("next_items_page") or {}
            batch = page.get("items") or []
            all_items.extend(batch)
            cursor = page.get("cursor")
            if not batch or len(batch) < limit:
                break

        logger.debug(
            "list_items board=%s%s -> %d items total",
            board_id,
            " (delta)" if updated_since else "",
            len(all_items),
        )
        return all_items

    # ------------------------------------------------------------------
    # Users
    # ------------------------------------------------------------------

    def list_users(self, kind: str = "non_guests") -> list[dict[str, Any]]:
        """Return workspace members. kind: 'all' | 'non_guests' | 'guests'."""
        gql = """
        query ($kind: UserKind!) {
          users(kind: $kind, limit: 1000) {
            id name email title is_admin is_guest
          }
        }
        """
        return self.query(gql, {"kind": kind}).get("users") or []

    # ------------------------------------------------------------------
    # Write mutations — sync canonical changes back to Monday
    # ------------------------------------------------------------------

    def change_column_value(
        self,
        board_id: int,
        item_id: int,
        column_id: str,
        value: Any,
    ) -> dict[str, Any]:
        """Update a single column value on an item.
        
        Args:
            board_id: The board ID
            item_id: The item ID to update
            column_id: The column ID (e.g., "status", "date123")
            value: The new value (format depends on column type)
                  - Status: {"index": 0} or {"label": "Done"}
                  - Date: "2026-05-12"
                  - Person: {"id": 123}
                  - Number: 42
        
        Returns:
            Item dict with id and updated column_values
        """
        gql = """
        mutation change_column_value($value: JSON!) {
          change_column_value(
            board_id: $board_id,
            item_id: $item_id,
            column_id: $column_id,
            value: $value
          ) {
            id
            column_values { id type text value }
          }
        }
        """
        variables = {
            "board_id": board_id,
            "item_id": item_id,
            "column_id": column_id,
            "value": value if isinstance(value, str) else json.dumps(value),
        }
        result = self.query(gql, variables, track_complexity=True)
        return result.get("change_column_value", {})

    def change_multiple_column_values(
        self,
        board_id: int,
        item_id: int,
        column_values: dict[str, Any],
    ) -> dict[str, Any]:
        """Batch update multiple columns on a single item (preferred over single updates).
        
        ~150x cheaper than calling change_column_value() multiple times because
        it's counted as one API call instead of N calls.
        
        Args:
            board_id: The board ID
            item_id: The item ID to update
            column_values: Dict of {column_id: value} to update
                          e.g., {"status": {"index": 1}, "date123": "2026-05-12"}
        
        Returns:
            Item dict with id and updated column_values
        """
        gql = """
        mutation change_multiple_column_values($values: JSON!) {
          change_multiple_column_values(
            board_id: $board_id,
            item_id: $item_id,
            column_values: $values
          ) {
            id
            name
            column_values { id type text value }
          }
        }
        """
        variables = {
            "board_id": board_id,
            "item_id": item_id,
            "values": json.dumps(column_values),
        }
        result = self.query(gql, variables, track_complexity=True)
        logger.info(f"Updated item {item_id} on board {board_id}: {len(column_values)} columns")
        return result.get("change_multiple_column_values", {})

    def create_item(
        self,
        board_id: int,
        item_name: str,
        column_values: dict[str, Any] | None = None,
        group_id: str | None = None,
    ) -> dict[str, Any]:
        """Create a new item on a board.
        
        Args:
            board_id: The board ID
            item_name: The name/title of the new item
            column_values: Optional initial column values {column_id: value}
            group_id: Optional group/lane to add item to
        
        Returns:
            Created item dict with id, name, and column_values
        """
        gql = """
        mutation create_item($column_values: JSON) {
          create_item(
            board_id: $board_id,
            item_name: $item_name,
            column_values: $column_values,
            group_id: $group_id
          ) {
            id
            name
            group { id title }
            column_values { id type text value }
          }
        }
        """
        variables = {
            "board_id": board_id,
            "item_name": item_name,
            "group_id": group_id,
        }
        if column_values:
            variables["column_values"] = json.dumps(column_values)
        
        result = self.query(gql, variables, track_complexity=True)
        item = result.get("create_item", {})
        logger.info(f"Created item '{item_name}' on board {board_id}: id={item.get('id')}")
        return item

    def delete_item(self, board_id: int, item_id: int) -> bool:
        """Delete an item from a board.
        
        Args:
            board_id: The board ID
            item_id: The item ID to delete
        
        Returns:
            True if successful
        """
        gql = """
        mutation delete_item {
          delete_item(board_id: $board_id, item_id: $item_id) {
            id
          }
        }
        """
        result = self.query(gql, {"board_id": board_id, "item_id": item_id}, track_complexity=True)
        deleted = result.get("delete_item")
        if deleted:
            logger.info(f"Deleted item {item_id} from board {board_id}")
            return True
        return False

