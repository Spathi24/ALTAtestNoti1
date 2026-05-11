"""Minimal Monday.com GraphQL client.

Just enough to fetch boards, items, and column values. In a fragmented-team
v0.1 the priority is "make calls succeed at all" — full pagination + rate
limiting come in v0.2.

API docs: https://developer.monday.com/api-reference/docs

Env vars used:
  MONDAY_API_TOKEN — personal API token (Monday > avatar > Admin > API)
"""
from __future__ import annotations

import logging
import os
from typing import Any

logger = logging.getLogger(__name__)

API_URL = "https://api.monday.com/v2"


class MondayClient:
    def __init__(self, token: str | None = None):
        self.token = token or os.environ.get("MONDAY_API_TOKEN")
        if not self.token:
            raise RuntimeError(
                "MONDAY_API_TOKEN not set. Get one at "
                "Monday > avatar > Admin > API."
            )

    def query(self, gql: str, variables: dict[str, Any] | None = None) -> dict[str, Any]:
        """Run a GraphQL query. Imported lazily so the package doesn't *require*
        httpx if you're not using Monday yet."""
        import httpx  # local import keeps optional deps optional

        resp = httpx.post(
            API_URL,
            headers={
                "Authorization": self.token,
                "Content-Type": "application/json",
                "API-Version": "2024-01",
            },
            json={"query": gql, "variables": variables or {}},
            timeout=30.0,
        )
        resp.raise_for_status()
        data = resp.json()
        if "errors" in data:
            raise RuntimeError(f"Monday API error: {data['errors']}")
        return data["data"]

    # ----- convenience methods -----

    def list_workspaces(self) -> list[dict[str, Any]]:
        gql = """
        query { workspaces { id name kind description } }
        """
        return self.query(gql)["workspaces"] or []

    def list_boards(self, workspace_ids: list[int] | None = None) -> list[dict[str, Any]]:
        gql = """
        query ($workspace_ids: [ID!]) {
          boards(workspace_ids: $workspace_ids, limit: 100) {
            id name workspace { id name } board_kind state
          }
        }
        """
        variables = {"workspace_ids": workspace_ids} if workspace_ids else {}
        return self.query(gql, variables)["boards"] or []

    def list_items(self, board_id: int, limit: int = 100) -> list[dict[str, Any]]:
        gql = """
        query ($board_id: [ID!], $limit: Int!) {
          boards(ids: $board_id) {
            items_page(limit: $limit) {
              items {
                id name state created_at updated_at
                column_values { id text value type }
              }
            }
          }
        }
        """
        data = self.query(gql, {"board_id": [board_id], "limit": limit})
        boards = data.get("boards") or []
        if not boards:
            return []
        return boards[0].get("items_page", {}).get("items", []) or []
