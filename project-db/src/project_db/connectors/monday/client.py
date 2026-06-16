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
                "MONDAY_API_TOKEN not set. Get one at Monday > avatar > Admin > API."
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
        # Per-instance cache so we don't re-fetch board columns on every push.
        # Board columns change rarely (when someone edits a board) so caching
        # for the life of the client is safe; if you need a refresh, make a
        # new MondayClient or clear self._columns_cache.
        self._columns_cache: dict[int, list[dict[str, Any]]] = {}

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
        """Return every column definition for a board (cached per instance).

        Each dict: id, title, type, settings_str (JSON with label maps for
        status/dropdown columns).
        """
        if board_id in self._columns_cache:
            return self._columns_cache[board_id]
        gql = """
        query ($board_id: [ID!]!) {
          boards(ids: $board_id) {
            columns { id title type settings_str }
          }
        }
        """
        data = self.query(gql, {"board_id": [board_id]})
        boards = data.get("boards") or []
        cols = boards[0].get("columns") or [] if boards else []
        self._columns_cache[board_id] = cols
        return cols

    # ------------------------------------------------------------------
    # Items — full cursor pagination with delta sync support
    # ------------------------------------------------------------------

    def list_items(
        self,
        board_id: int,
        limit: int = PAGE_LIMIT,
        include_subitems: bool = False,
    ) -> list[dict[str, Any]]:
        """Fetch items on a board with their column values (+ subitems).

        IMPORTANT: Monday OMITS column_values for any column that has no
        value on a given item -- naming the column ids in ``ids:`` does NOT
        force empty columns to appear.  On portfolio/mirror boards the real
        per-task Status / Timeline are NOT stored on the task row at all;
        they live as mirror columns on a linked portfolio item.  See
        ``connector.apply_portfolio_mirror_overlay``, which backfills them
        onto every task AND subitem.

        This method always does a full board pull -- ``updated_after`` was
        removed from ``items_page`` in API-Version 2026-07.  For delta sync
        see ``list_activity_logs`` plus ``MondayConnector.sync(delta=True)``.
        """
        columns = self.list_board_columns(board_id)
        column_ids = [c["id"] for c in columns if c.get("id")]
        if not column_ids:
            logger.warning("list_items board=%s: no board columns returned", board_id)

        column_value_fields = """
                id type text value
                column { id title type }
                ... on StatusValue { label index is_done }
                ... on TimelineValue { from to visualization_type }
                ... on NumbersValue { number symbol }
                ... on PeopleValue { persons_and_teams { id kind } }
                ... on BoardRelationValue { display_value linked_item_ids }
                ... on DependencyValue { display_value linked_item_ids }
                ... on MirrorValue { display_value }
                ... on SubtasksValue { display_value subitems_ids }
        """

        # Do NOT filter subitem column_values by the parent board's column_ids.
        # Subitems can have their own hidden subitem-board schema, so parent ids
        # would incorrectly suppress subitem values.
        subitem_fields = ""
        if include_subitems:
            subitem_fields = """
                subitems {
                  id name state created_at updated_at
                  parent_item { id name }
                  column_values {
                    __COLUMN_VALUE_FIELDS__
                  }
                }
            """.replace("__COLUMN_VALUE_FIELDS__", column_value_fields)

        first_page_gql = """
        query ($board_id: [ID!]!, $limit: Int!, $column_ids: [String!]) {
          boards(ids: $board_id) {
            items_page(limit: $limit) {
              cursor
              items {
                id name state created_at updated_at
                group { id title }
                column_values(ids: $column_ids) {
                  __COLUMN_VALUE_FIELDS__
                }
                __SUBITEM_FIELDS__
              }
            }
          }
        }
        """.replace("__COLUMN_VALUE_FIELDS__", column_value_fields).replace(
            "__SUBITEM_FIELDS__", subitem_fields
        )
        next_page_gql = """
        query ($cursor: String!, $limit: Int!, $column_ids: [String!]) {
          next_items_page(cursor: $cursor, limit: $limit) {
            cursor
            items {
              id name state created_at updated_at
              group { id title }
              column_values(ids: $column_ids) {
                __COLUMN_VALUE_FIELDS__
              }
              __SUBITEM_FIELDS__
            }
          }
        }
        """.replace("__COLUMN_VALUE_FIELDS__", column_value_fields).replace(
            "__SUBITEM_FIELDS__", subitem_fields
        )

        variables = {"board_id": [board_id], "limit": limit, "column_ids": column_ids}
        data = self.query(first_page_gql, variables)
        boards = data.get("boards") or []
        if not boards:
            return []

        page = boards[0].get("items_page") or {}
        all_items: list[dict[str, Any]] = list(page.get("items") or [])
        cursor = page.get("cursor")

        while cursor:
            data = self.query(
                next_page_gql,
                {"cursor": cursor, "limit": limit, "column_ids": column_ids},
            )
            page = data.get("next_items_page") or {}
            batch = page.get("items") or []
            all_items.extend(batch)
            cursor = page.get("cursor")
            if not batch or len(batch) < limit:
                break

        logger.debug(
            "list_items board=%s -> %d items total; requested %d columns",
            board_id,
            len(all_items),
            len(column_ids),
        )
        return all_items

    # ------------------------------------------------------------------
    # Mirror-aware item fetch
    #
    # In a portfolio/sub-board setup, the task board exposes columns named
    # `project_status`, `project_timeline`, etc. but those columns are
    # EMPTY at the row level -- their values live on the linked portfolio
    # item as `mirror` columns containing per-task `mirrored_items`.
    #
    # `get_items_with_mirror_values` follows the link the other way: feed
    # in a list of portfolio item IDs and Monday returns each one's mirror
    # columns with the mirrored task values inline.
    # ------------------------------------------------------------------

    # Monday caps `items(ids: [...])` at 100 per request. Anything larger
    # has to be chunked.
    _ITEMS_BY_ID_CHUNK = 100

    def get_items_with_mirror_values(
        self,
        item_ids: list[int | str],
    ) -> list[dict[str, Any]]:
        """Fetch items by id, including MirrorValue.mirrored_items.

        Used to read mirror columns on a portfolio board where each mirror
        column proxies a real value from a linked task board. Automatically
        chunks the request to stay under Monday's 100-id cap on
        `items(ids: [...])`.
        """
        if not item_ids:
            return []

        column_value_fields = """
            id
            type
            text
            value
            column { id title type }

            ... on StatusValue   { label index is_done }
            ... on TimelineValue { from to visualization_type }
            ... on NumbersValue  { number symbol }
            ... on DateValue     { date time }

            ... on BoardRelationValue { display_value linked_item_ids }
            ... on DependencyValue   { display_value linked_item_ids }

            ... on MirrorValue {
              display_value
              mirrored_items {
                linked_item {
                  id
                  name
                  board { id name }
                }
                mirrored_value {
                  ... on StatusValue   { label index is_done }
                  ... on TimelineValue { from to visualization_type }
                  ... on NumbersValue  { number symbol }
                  ... on DateValue     { date time }
                  ... on BoardRelationValue { display_value linked_item_ids }
                  ... on MirrorValue       { display_value }
                }
              }
            }
        """

        gql = f"""
        query ($item_ids: [ID!]!) {{
          items(ids: $item_ids) {{
            id
            name
            board {{ id name }}
            group {{ id title }}
            column_values {{
              {column_value_fields}
            }}
          }}
        }}
        """

        all_ids = [str(i) for i in item_ids]
        chunks = [
            all_ids[i : i + self._ITEMS_BY_ID_CHUNK]
            for i in range(0, len(all_ids), self._ITEMS_BY_ID_CHUNK)
        ]
        out: list[dict[str, Any]] = []
        for chunk in chunks:
            data = self.query(gql, {"item_ids": chunk})
            out.extend(data.get("items") or [])
        return out

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
        mutation ($board_id: ID!, $item_id: ID!, $column_id: String!, $value: JSON!) {
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
        result = self.query(gql, variables)
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
        mutation ($board_id: ID!, $item_id: ID!, $values: JSON!) {
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
        result = self.query(gql, variables)
        logger.info(
            "Updated item %s on board %s: %d columns", item_id, board_id, len(column_values)
        )
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
        mutation ($board_id: ID!, $item_name: String!, $column_values: JSON, $group_id: String) {
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
        variables: dict[str, Any] = {
            "board_id": board_id,
            "item_name": item_name,
            "group_id": group_id,
        }
        if column_values:
            variables["column_values"] = json.dumps(column_values)

        result = self.query(gql, variables)
        item = result.get("create_item", {})
        logger.info("Created item '%s' on board %s: id=%s", item_name, board_id, item.get("id"))
        return item

    def create_subitem(
        self,
        parent_item_id: int,
        item_name: str,
        column_values: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Create a subitem under an existing parent item.

        Subitems live on their own auto-generated subitem board with their
        own column ids (distinct from the parent board), so we do NOT pass a
        board_id here -- Monday derives it from the parent.  ``column_values``
        keys, if supplied, must therefore be subitem-board column ids, not the
        parent board's.  For a bare title-only subitem (the common case) omit
        them.

        Returns the created subitem dict (id, name, and its board id so the
        caller can build an external_url).
        """
        gql = """
        mutation ($parent_item_id: ID!, $item_name: String!, $column_values: JSON) {
          create_subitem(
            parent_item_id: $parent_item_id,
            item_name: $item_name,
            column_values: $column_values
          ) {
            id
            name
            board { id }
            column_values { id type text value }
          }
        }
        """
        variables: dict[str, Any] = {
            "parent_item_id": parent_item_id,
            "item_name": item_name,
        }
        if column_values:
            variables["column_values"] = json.dumps(column_values)

        result = self.query(gql, variables)
        sub = result.get("create_subitem", {})
        logger.info(
            "Created subitem '%s' under parent %s: id=%s",
            item_name,
            parent_item_id,
            sub.get("id"),
        )
        return sub

    def delete_item(self, board_id: int, item_id: int) -> bool:
        """Delete an item from a board.

        Args:
            board_id: The board ID
            item_id: The item ID to delete

        Returns:
            True if successful
        """
        gql = """
        mutation ($board_id: ID!, $item_id: ID!) {
          delete_item(board_id: $board_id, item_id: $item_id) {
            id
          }
        }
        """
        result = self.query(gql, {"board_id": board_id, "item_id": item_id})
        deleted = result.get("delete_item")
        if deleted:
            logger.info("Deleted item %s from board %s", item_id, board_id)
            return True
        return False

    # ------------------------------------------------------------------
    # Activity logs (delta-sync gate)
    # ------------------------------------------------------------------

    def list_activity_logs(
        self,
        board_id: int,
        *,
        from_ts: datetime | None = None,
        to_ts: datetime | None = None,
        limit: int = 100,
        page: int = 1,
        max_pages: int = 20,
    ) -> list[dict[str, Any]]:
        """Return board activity-log events, newest first.

        Monday gives every Board a change feed.  We use it as the cheap
        delta-sync gate: ``MondayConnector.sync(delta=True)`` queries this
        with ``from_ts = last_sync_at`` and skips the board entirely when
        the result is empty.  Per-item delta -- refetching just the
        changed items -- is a future enhancement that would build on
        this same endpoint.

        Args:
          board_id:   Numeric board id.
          from_ts:    ISO-formatted via .isoformat() before sending.
                      Server interprets as UTC.
          to_ts:      Upper bound; usually omitted (= now).
          limit:      Events per page (max 1000 per Monday docs).
          page:       Start page; loops forward to ``max_pages``.
          max_pages:  Safety cap.  20 pages * 100/page = 2000 events
                      per board, plenty for skip-or-process decisions.

        Returns events with shape::

            {"id": "...", "created_at": "2026-05-16T12:34:56Z",
             "event": "update_column_value", "entity": "...",
             "user_id": "...", "data": "{...JSON blob...}"}

        ``data`` is a JSON string -- callers parse if they need item ids.
        """
        gql = """
        query ($board_id: [ID!]!, $from_ts: ISO8601DateTime,
               $to_ts: ISO8601DateTime, $limit: Int!, $page: Int!) {
          boards(ids: $board_id) {
            activity_logs(
              from: $from_ts
              to: $to_ts
              limit: $limit
              page: $page
            ) {
              id created_at event entity user_id data
            }
          }
        }
        """
        out: list[dict[str, Any]] = []
        current_page = page
        while current_page < page + max_pages:
            variables: dict[str, Any] = {
                "board_id": [board_id],
                "limit": limit,
                "page": current_page,
            }
            if from_ts is not None:
                variables["from_ts"] = from_ts.isoformat()
            if to_ts is not None:
                variables["to_ts"] = to_ts.isoformat()
            data = self.query(gql, variables)
            boards = data.get("boards") or []
            if not boards:
                break
            events = boards[0].get("activity_logs") or []
            out.extend(events)
            if len(events) < limit:
                break
            current_page += 1
        logger.debug(
            "list_activity_logs board=%s from=%s -> %d events",
            board_id,
            from_ts,
            len(out),
        )
        return out
