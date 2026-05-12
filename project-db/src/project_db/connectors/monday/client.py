"""Monday.com GraphQL client.

Handles auth, versioned API headers, full cursor-based pagination, and
basic error detection. All callers get plain Python dicts — no SDK objects.

Env vars:
  MONDAY_API_TOKEN — personal or service-account API token
                     (Monday > avatar > Admin > API)
"""
from __future__ import annotations

import logging
import os
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

    # ------------------------------------------------------------------
    # Low-level runner
    # ------------------------------------------------------------------

    def query(
        self,
        gql: str,
        variables: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Execute a GraphQL operation. Returns data dict. Raises on errors."""
        resp = self._http.post(
            "",
            json={"query": gql, "variables": variables or {}},
        )
        resp.raise_for_status()
        payload = resp.json()
        if "errors" in payload:
            raise RuntimeError(f"Monday API error: {payload['errors']}")
        return payload["data"]

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
    # Items — full cursor pagination
    # ------------------------------------------------------------------

    def list_items(
        self,
        board_id: int,
        limit: int = PAGE_LIMIT,
    ) -> list[dict[str, Any]]:
        """Fetch ALL items on a board, following cursor pages automatically."""
        first_page_gql = """
        query ($board_id: [ID!]!, $limit: Int!) {
          boards(ids: $board_id) {
            items_page(limit: $limit) {
              cursor
              items {
                id name state created_at updated_at
                group { id title }
                column_values { id type text value }
              }
            }
          }
        }
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

        logger.debug("list_items board=%s → %d items total", board_id, len(all_items))
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
