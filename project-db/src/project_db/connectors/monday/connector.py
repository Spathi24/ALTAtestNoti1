"""Monday.com → canonical DB connector.

v0.1 scope:
  - Discover workspaces & boards (logged for visibility, not yet persisted as
    Workspace entities — that's a full-model concept).
  - For boards whose names match configured patterns, pull items and map to
    canonical Projects, Leads, or Deals.

The board-name → entity-type mapping is intentionally config-driven so you
don't have to keep editing Python every time the team renames a board. See
`DEFAULT_BOARD_MAPPING` for the starting layout reflecting the workspace
structure described:

  CRM workspace          → Leads, Deals, Contacts (as Clients), Activities
  Project Management ws  → Projects (one board per property — e.g. "923 Rockland")
  Admin workspace        → Dashboard (skipped — reporting only)
"""
from __future__ import annotations

import logging
import re
from typing import Any

from project_db.connectors.base import BaseConnector, SyncReport
from project_db.connectors.monday.client import MondayClient
from project_db.db.models import (
    Client,
    Deal,
    Lead,
    LeadStage,
    Project,
    ProjectStatus,
    SourceSystem,
)
from project_db.identity.matcher import DEFAULT_MATCHERS, ExactFieldMatcher

logger = logging.getLogger(__name__)


# Board-name patterns → (canonical_entity, role)
# Roles tell the connector what mapping logic to apply.
DEFAULT_BOARD_MAPPING: list[dict[str, Any]] = [
    {"pattern": r"(?i)leads?", "entity": "Lead"},
    {"pattern": r"(?i)deals?", "entity": "Deal"},
    {"pattern": r"(?i)contacts?|accounts?", "entity": "Client"},
    {"pattern": r"(?i)client projects?", "entity": "Project"},
    # Property boards: match anything that looks like an address. The
    # Project Management workspace has one board per property.
    {"pattern": r"^\d+[-\s].+", "entity": "Project"},
]


class MondayConnector(BaseConnector):
    source = SourceSystem.MONDAY

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.client = MondayClient(token=self.config.get("api_token"))
        self.board_mapping: list[dict[str, Any]] = self.config.get(
            "board_mapping", DEFAULT_BOARD_MAPPING
        )

    def sync(self) -> SyncReport:
        try:
            workspaces = self.client.list_workspaces()
            logger.info("Found %d Monday workspaces", len(workspaces))
            for ws in workspaces:
                logger.info("  - %s (id=%s, kind=%s)", ws["name"], ws["id"], ws.get("kind"))

            boards = self.client.list_boards()
            logger.info("Found %d boards across all workspaces", len(boards))

            for board in boards:
                entity_type = self._classify_board(board["name"])
                if entity_type is None:
                    logger.debug("Skipping board %r (no mapping)", board["name"])
                    continue
                self._sync_board(board, entity_type)
        except Exception as exc:  # noqa: BLE001
            self._record_failure(f"sync failed: {exc}")
        return self._finalize()

    # ----- board classification -----

    def _classify_board(self, name: str) -> str | None:
        for rule in self.board_mapping:
            if re.search(rule["pattern"], name):
                return rule["entity"]
        return None

    # ----- per-entity sync logic -----

    def _sync_board(self, board: dict[str, Any], entity_type: str) -> None:
        items = self.client.list_items(int(board["id"]))
        logger.info(
            "  syncing board %r as %s — %d items",
            board["name"],
            entity_type,
            len(items),
        )
        for item in items:
            try:
                if entity_type == "Project":
                    self._upsert_project(board, item)
                elif entity_type == "Lead":
                    self._upsert_lead(board, item)
                elif entity_type == "Deal":
                    self._upsert_deal(board, item)
                elif entity_type == "Client":
                    self._upsert_client(board, item)
            except Exception as exc:  # noqa: BLE001
                self._record_failure(
                    f"item {item.get('id')} on board {board['name']!r}: {exc}"
                )

    def _upsert_project(self, board: dict[str, Any], item: dict[str, Any]) -> None:
        # Default: project from a property board; assumes client UNKNOWN
        # until we wire Client resolution from column values.
        attrs = {
            "name": item["name"],
            "status": ProjectStatus.ACTIVE,
            "code": f"MONDAY-{item['id']}",
        }
        # Project requires client_id — for v0.1 we attach a placeholder
        # "Unknown Client" per org. Real mapping reads from column_values.
        attrs["client_id"] = self._get_or_create_placeholder_client_id()
        result = self.resolver.resolve_or_create(
            source=self.source,
            external_key=str(item["id"]),
            external_url=f"https://view.monday.com/{item['id']}",
            entity_class=Project,
            attrs=attrs,
            matcher=DEFAULT_MATCHERS.get("Project"),
        )
        self._record_result(result.was_created, result.was_matched)

    def _upsert_lead(self, board: dict[str, Any], item: dict[str, Any]) -> None:
        attrs = {"stage": LeadStage.NEW, "source_channel": "monday-import"}
        result = self.resolver.resolve_or_create(
            source=self.source,
            external_key=str(item["id"]),
            external_url=f"https://view.monday.com/{item['id']}",
            entity_class=Lead,
            attrs=attrs,
        )
        self._record_result(result.was_created, result.was_matched)

    def _upsert_deal(self, board: dict[str, Any], item: dict[str, Any]) -> None:
        attrs = {
            "name": item["name"],
            "value": 0.0,
            "stage": LeadStage.NEW,
            "client_id": self._get_or_create_placeholder_client_id(),
        }
        result = self.resolver.resolve_or_create(
            source=self.source,
            external_key=str(item["id"]),
            external_url=f"https://view.monday.com/{item['id']}",
            entity_class=Deal,
            attrs=attrs,
        )
        self._record_result(result.was_created, result.was_matched)

    def _upsert_client(self, board: dict[str, Any], item: dict[str, Any]) -> None:
        attrs = {"name": item["name"], "organization_id": self.organization_id}
        result = self.resolver.resolve_or_create(
            source=self.source,
            external_key=str(item["id"]),
            external_url=f"https://view.monday.com/{item['id']}",
            entity_class=Client,
            attrs=attrs,
            matcher=ExactFieldMatcher(["name"]),
        )
        self._record_result(result.was_created, result.was_matched)

    # ----- helpers -----

    _placeholder_client_id: Any = None

    def _get_or_create_placeholder_client_id(self) -> Any:
        """v0.1 — Projects need a client. Until we map Monday client columns
        we attach everything to a single 'Unknown Client' so the FK is valid.
        Replace this once column-value extraction is implemented.
        """
        if self._placeholder_client_id is not None:
            return self._placeholder_client_id
        placeholder = (
            self.session.query(Client)
            .filter_by(name="Unknown Client", organization_id=self.organization_id)
            .one_or_none()
        )
        if placeholder is None:
            placeholder = Client(
                name="Unknown Client",
                organization_id=self.organization_id,
            )
            self.session.add(placeholder)
            self.session.flush()
        self._placeholder_client_id = placeholder.canonical_id
        return self._placeholder_client_id
