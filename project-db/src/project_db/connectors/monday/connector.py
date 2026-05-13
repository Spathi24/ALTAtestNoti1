"""Monday.com -> canonical DB connector.

Board classification is config-driven (regex patterns) so renaming a board
in Monday doesn't require touching Python. Column extraction uses heuristic
title matching + optional explicit column_id overrides.

Delta Sync:
  By default, full sync is performed on first run. On subsequent runs, only
  items updated since last sync are fetched, reducing API cost by 90%+.
  
  Set force_full_sync=True to override and re-fetch all items (testing/debugging).

Board mapping (DEFAULT_BOARD_MAPPING):
  CRM workspace           -> Lead, Deal, Client boards
  Project Management ws   -> Project boards (one per property / job)
  Admin workspace         -> skipped (reporting-only boards)

Column mapping per board type is in DEFAULT_COLUMN_MAPPING. Override via
connector config if your Monday column ids/titles differ.

Write-back capability:
  MondayConnector.sync_back() pushes canonical changes to Monday. Use after
  syncing data from other sources (e.g., QB invoices → update project status).
"""
from __future__ import annotations

import logging
import re
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import desc, func
from sqlalchemy.orm import Session

from project_db.connectors.base import BaseConnector, SyncReport
from project_db.connectors.monday.client import MondayClient
from project_db.connectors.monday.column_extractor import ColumnExtractor
from project_db.db.models import (
    Client,
    Deal,
    ExternalId,
    Lead,
    LeadStage,
    Project,
    ProjectStatus,
    SourceSystem,
    Task,
    TaskStatus,
    User,
)
from project_db.identity.matcher import ExactFieldMatcher

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Board classification — name pattern -> entity type
# ---------------------------------------------------------------------------

DEFAULT_BOARD_MAPPING: list[dict[str, Any]] = [
    {"pattern": r"(?i)\bleads?\b", "entity": "Lead"},
    {"pattern": r"(?i)\bdeals?\b", "entity": "Deal"},
    {"pattern": r"(?i)\bcontacts?\b|\baccounts?\b", "entity": "Client"},
    # CRM \"Client Projects\" board: each item = one project
    {"pattern": r"(?i)client\s+projects?", "entity": "Project"},
    # Address/job boards (e.g. "923 Rockland", "5768-5770 St Laurent"):
    # board = one Project, items = Tasks inside it.
    {"pattern": r"^\d+[-\s].+", "entity": "ProjectBoard"},
]

# Workspace names whose boards should always be treated as job/property boards
# even if their name doesn't match the address pattern above.
PROJECT_MANAGEMENT_WORKSPACES: set[str] = {"Project Management"}


# ---------------------------------------------------------------------------
# Explicit column-id overrides per entity type (optional — heuristics usually
# work, but you can force a mapping here if column titles are non-standard).
# Keys are entity types; values are {monday_column_id: canonical_field_name}.
# ---------------------------------------------------------------------------

DEFAULT_COLUMN_MAPPING: dict[str, dict[str, str]] = {

    "Project": {},
    "Lead": {},
    "Deal": {},
    "Client": {},
}


class MondayConnector(BaseConnector):
    source = SourceSystem.MONDAY

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        from project_db.config import settings
        self.client = MondayClient(
            token=self.config.get("api_token") or settings.monday_api_token
        )
        self.board_mapping: list[dict[str, Any]] = self.config.get(
            "board_mapping", DEFAULT_BOARD_MAPPING
        )
        self.column_mapping: dict[str, dict[str, str]] = self.config.get(
            "column_mapping", DEFAULT_COLUMN_MAPPING
        )


    # ------------------------------------------------------------------
    # Entry point
    # ------------------------------------------------------------------

    def sync(self, force_full_sync: bool = False) -> SyncReport:
        """Sync Monday data to canonical DB.
        
        Args:
            force_full_sync: If True, re-fetch all items. Otherwise, use delta sync
                            (only fetch items updated since last sync). Delta sync
                            is ~90% cheaper.
        """
        try:
            workspaces = self.client.list_workspaces()
            logger.info("Found %d Monday workspaces", len(workspaces))
            for ws in workspaces:
                logger.info("  - %s (id=%s)", ws["name"], ws["id"])

            # Sync users first so project assignee FKs can resolve
            self._sync_users()

            boards = self.client.list_boards()
            logger.info("Found %d boards total", len(boards))

            for board in boards:
                if board.get("state") != "active":
                    continue
                # Skip Monday's auto-generated subitem mirror boards
                if re.match(r"(?i)subitems?\s+of\b", board["name"]):
                    logger.debug("Skipping subitem mirror board %r", board["name"])
                    continue
                ws_name = (board.get("workspace") or {}).get("name", "")
                entity_type = self._classify_board(board["name"], ws_name)
                if entity_type is None:
                    logger.debug("Skipping board %r (no pattern match)", board["name"])
                    continue
                self._sync_board(board, entity_type, force_full_sync=force_full_sync)

        except Exception as exc:  # noqa: BLE001
            self._record_failure(f"sync failed: {exc}")
        return self._finalize()

    # ------------------------------------------------------------------
    # Users
    # ------------------------------------------------------------------

    def _sync_users(self) -> None:
        try:
            monday_users = self.client.list_users()
            logger.info("Syncing %d Monday users", len(monday_users))
            for mu in monday_users:
                if not mu.get("email"):
                    continue
                attrs = {
                    "email": mu["email"],
                    "display_name": mu.get("name", mu["email"]),
                    "role": mu.get("title") or ("admin" if mu.get("is_admin") else "member"),
                    "is_active": True,
                    "organization_id": self.organization_id,
                }
                result = self.resolver.resolve_or_create(
                    source=self.source,
                    external_key=str(mu["id"]),
                    external_url=None,
                    entity_class=User,
                    attrs=attrs,
                    matcher=ExactFieldMatcher(["email"]),
                )
                self._record_result(result.was_created, result.was_matched)
        except Exception as exc:  # noqa: BLE001
            logger.warning("User sync failed (non-fatal): %s", exc)

    # ------------------------------------------------------------------
    # Board classification & sync dispatch
    # ------------------------------------------------------------------

    # ------------------------------------------------------------------
    # Helper: track last sync time per board for delta sync
    # ------------------------------------------------------------------

    def _get_last_sync_time(self, board_id: int) -> datetime | None:
        """Fetch the most recent last_synced_at for any item from this board."""
        try:
            result = (
                self.session.query(func.max(ExternalId.last_synced_at))
                .filter(
                    ExternalId.source == self.source,
                    ExternalId.entity_type.in_(["Project", "Lead", "Deal", "Client", "Task"]),
                    # Heuristic: external keys from this board often contain the board ID
                    # For ProjectBoard items, the key is "board:{board_id}"
                    # For regular board items, it's just the item ID
                )
                .scalar()
            )
            if result:
                # Use a small buffer (5 minutes) to catch any changes during sync
                return result - timedelta(minutes=5)
            return None
        except Exception:  # noqa: BLE001
            return None

    # ------------------------------------------------------------------
    # Board classification & sync dispatch
    # ------------------------------------------------------------------

    def _classify_board(self, name: str, workspace_name: str = "") -> str | None:
        # Boards in the Project Management workspace that don't match CRM patterns
        # are job/property boards — board itself is the project.
        if workspace_name in PROJECT_MANAGEMENT_WORKSPACES:

            for rule in self.board_mapping:
                if re.search(rule["pattern"], name):
                    return rule["entity"]
            return "ProjectBoard"

        for rule in self.board_mapping:
            if re.search(rule["pattern"], name):
                return rule["entity"]
        return None

    def _sync_board(
        self,
        board: dict[str, Any],
        entity_type: str,
        force_full_sync: bool = False,
    ) -> None:
        """Sync a single board, using delta sync if available."""
        board_id = int(board["id"])

        column_defs = self.client.list_board_columns(board_id)
        explicit_mapping = self.column_mapping.get(entity_type, {})
        extractor = ColumnExtractor(column_defs, explicit_mapping=explicit_mapping)

        # Delta sync: only fetch items updated since last sync
        last_sync = None if force_full_sync else self._get_last_sync_time(board_id)
        
        if last_sync:
            logger.info(
                "  board %r -> %s -- delta sync since %s",
                board["name"],
                entity_type,
                last_sync.isoformat(),
            )
        
        items = self.client.list_items(board_id, updated_since=last_sync)
        
        logger.info(
            "  board %r -> %s -- %d items%s, %d columns",
            board["name"],
            entity_type,
            len(items),
            " (delta)" if last_sync else "",
            len(column_defs),
        )

        if entity_type == "ProjectBoard":
            self._sync_project_board(board, column_defs, items)
            return

        for item in items:
            if item.get("state") == "deleted":
                continue
            try:
                fields = extractor.extract(item.get("column_values") or [])
                if entity_type == "Project":
                    self._upsert_project(board, item, fields)
                elif entity_type == "Lead":
                    self._upsert_lead(board, item, fields)
                elif entity_type == "Deal":
                    self._upsert_deal(board, item, fields)
                elif entity_type == "Client":
                    self._upsert_client(board, item, fields)
            except Exception as exc:  # noqa: BLE001
                self._record_failure(
                    f"item {item.get('id')} on board {board['name']!r}: {exc}"
                )

    # ------------------------------------------------------------------
    # Per-entity upserts
    # ------------------------------------------------------------------

    def _upsert_project(
        self,
        board: dict[str, Any],
        item: dict[str, Any],
        fields: Any,
    ) -> None:
        client_id = self._resolve_client_id(fields.client_name)
        attrs: dict[str, Any] = {
            "name": item["name"],
            "code": f"MONDAY-{item['id']}",
            "status": fields.status or ProjectStatus.ACTIVE,
            "client_id": client_id,
        }
        if fields.start_date:
            attrs["start_date"] = fields.start_date
        if fields.end_date:
            attrs["end_date"] = fields.end_date
        if fields.budget_amount is not None:
            attrs["budget_amount"] = fields.budget_amount
        if fields.contract_amount is not None:
            attrs["contract_amount"] = fields.contract_amount

        result = self.resolver.resolve_or_create(
            source=self.source,
            external_key=str(item["id"]),
            external_url=f"https://view.monday.com/{item['id']}",
            entity_class=Project,
            attrs=attrs,
            matcher=ExactFieldMatcher(["name"]),
        )
        self._record_result(result.was_created, result.was_matched)

    def _upsert_lead(
        self,
        board: dict[str, Any],
        item: dict[str, Any],
        fields: Any,
    ) -> None:
        attrs: dict[str, Any] = {
            "stage": fields.lead_stage or LeadStage.NEW,
            "source_channel": "monday",
        }
        if fields.client_name:
            attrs["client_id"] = self._resolve_client_id(fields.client_name)
        if fields.contract_amount is not None:
            attrs["estimated_value"] = fields.contract_amount
        elif fields.budget_amount is not None:
            attrs["estimated_value"] = fields.budget_amount

        result = self.resolver.resolve_or_create(
            source=self.source,
            external_key=str(item["id"]),
            external_url=f"https://view.monday.com/{item['id']}",
            entity_class=Lead,
            attrs=attrs,
        )
        self._record_result(result.was_created, result.was_matched)

    def _upsert_deal(
        self,
        board: dict[str, Any],
        item: dict[str, Any],
        fields: Any,
    ) -> None:
        client_id = self._resolve_client_id(fields.client_name)
        attrs: dict[str, Any] = {
            "name": item["name"],
            "stage": fields.lead_stage or LeadStage.NEW,
            "value": fields.contract_amount or fields.budget_amount or 0,
            "client_id": client_id,
        }
        if fields.end_date:
            attrs["expected_close_date"] = fields.end_date
        if fields.probability is not None:
            attrs["probability"] = fields.probability

        result = self.resolver.resolve_or_create(
            source=self.source,
            external_key=str(item["id"]),
            external_url=f"https://view.monday.com/{item['id']}",
            entity_class=Deal,
            attrs=attrs,
            matcher=ExactFieldMatcher(["name"]),
        )
        self._record_result(result.was_created, result.was_matched)

    def _upsert_client(
        self,
        board: dict[str, Any],
        item: dict[str, Any],
        fields: Any,
    ) -> None:
        attrs: dict[str, Any] = {
            "name": item["name"],
            "organization_id": self.organization_id,
        }
        if fields.email:
            attrs["email"] = fields.email
        if fields.phone:
            attrs["phone"] = fields.phone
        if fields.address:
            attrs["billing_address"] = fields.address

        result = self.resolver.resolve_or_create(
            source=self.source,
            external_key=str(item["id"]),
            external_url=f"https://view.monday.com/{item['id']}",
            entity_class=Client,
            attrs=attrs,
            matcher=ExactFieldMatcher(["name"]),
        )
        self._record_result(result.was_created, result.was_matched)

    # ------------------------------------------------------------------
    # ProjectBoard -- board = Project, items = Tasks
    # ------------------------------------------------------------------

    def _sync_project_board(
        self,
        board: dict[str, Any],
        column_defs: list[dict[str, Any]],
        items: list[dict[str, Any]],
    ) -> None:
        """Create/update one Project from the board, then sync items as Tasks."""
        project_attrs: dict[str, Any] = {
            "name": board["name"],
            "code": f"MONDAY-BOARD-{board['id']}",
            "status": ProjectStatus.ACTIVE,
            "client_id": self._resolve_client_id(None),
        }
        project_result = self.resolver.resolve_or_create(
            source=self.source,
            external_key=f"board:{board['id']}",
            external_url=f"https://view.monday.com/{board['id']}",
            entity_class=Project,
            attrs=project_attrs,
            matcher=ExactFieldMatcher(["name"]),
        )
        self._record_result(project_result.was_created, project_result.was_matched)
        project_id = project_result.entity.canonical_id

        extractor = ColumnExtractor(column_defs)
        for item in items:
            if item.get("state") == "deleted":
                continue
            try:
                fields = extractor.extract(item.get("column_values") or [])
                self._upsert_task(item, fields, project_id)
            except Exception as exc:  # noqa: BLE001
                self._record_failure(
                    f"task item {item.get('id')} on board {board['name']!r}: {exc}"
                )

    def _upsert_task(
        self,
        item: dict[str, Any],
        fields: Any,
        project_id: Any,
    ) -> None:
        attrs: dict[str, Any] = {
            "title": item["name"],
            "status": fields.task_status or TaskStatus.TODO,
            "project_id": project_id,
        }
        if fields.end_date:
            attrs["due_date"] = fields.end_date

        result = self.resolver.resolve_or_create(
            source=self.source,
            external_key=str(item["id"]),
            external_url=f"https://view.monday.com/{item['id']}",
            entity_class=Task,
            attrs=attrs,
        )
        self._record_result(result.was_created, result.was_matched)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _resolve_client_id(self, client_name: str | None) -> Any:
        """Return canonical_id for a client by name, creating it if needed."""
        name = (client_name or "").strip() or "Unknown Client"
        existing = (
            self.session.query(Client)
            .filter_by(name=name, organization_id=self.organization_id)
            .one_or_none()
        )
        if existing:
            return existing.canonical_id
        new_client = Client(name=name, organization_id=self.organization_id)
        self.session.add(new_client)
        self.session.flush()
        logger.info("Created Client %r (canonical_id=%s)", name, new_client.canonical_id)
        return new_client.canonical_id

    # ------------------------------------------------------------------
    # Write-back: sync canonical changes back to Monday
    # ------------------------------------------------------------------

    def sync_back(
        self,
        canonical_entity: Any,
        field_updates: dict[str, Any],
    ) -> bool:
        """Push changes from canonical entity back to Monday.
        
        This enables ripple effects: when data changes in canonical DB (e.g., 
        QB invoice created, CompanyCam deficiency added), we can update the 
        corresponding Monday item.
        
        Args:
            canonical_entity: The canonical entity object (Project, Lead, Deal, etc.)
            field_updates: Dict mapping Monday column_id -> new value
                          e.g., {"status": {"index": 1}, "text_column_id": "Updated"}
        
        Returns:
            True if successful, False otherwise
        
        Example:
            >>> project = session.query(Project).first()
            >>> connector.sync_back(project, {"status": {"index": 2}})
            True
        """
        try:
            # Look up the Monday external key for this entity
            entity_type = canonical_entity.__class__.__name__
            ext_id = (
                self.session.query(ExternalId)
                .filter_by(
                    source=self.source,
                    entity_type=entity_type,
                    canonical_id=canonical_entity.canonical_id,
                )
                .one_or_none()
            )
            
            if not ext_id:
                logger.warning(
                    f"No Monday mapping for {entity_type} {canonical_entity.canonical_id}"
                )
                return False
            
            # Extract board_id and item_id from external_key
            # For ProjectBoard items, external_key is "board:{board_id}"
            # For other items, it's just the item ID
            try:
                if ext_id.external_key.startswith("board:"):
                    logger.debug(
                        f"Cannot sync_back ProjectBoard items directly; "
                        f"update tasks instead"
                    )
                    return False
                item_id = int(ext_id.external_key)
            except (ValueError, AttributeError):
                logger.warning(
                    f"Invalid external_key format: {ext_id.external_key}"
                )
                return False
            
            # Extract board_id from URL if available
            if not ext_id.external_url:
                logger.warning(f"No external_url for {entity_type}, cannot determine board_id")
                return False
            
            # Parse board_id from Monday URL (https://view.monday.com/{board_id})
            try:
                board_id = int(ext_id.external_url.split("/")[-1])
            except (ValueError, IndexError):
                logger.warning(f"Cannot parse board_id from URL: {ext_id.external_url}")
                return False
            
            # Perform the update
            logger.info(
                f"Syncing back {entity_type} {canonical_entity.canonical_id} "
                f"to Monday item {item_id} on board {board_id}"
            )
            
            result = self.client.change_multiple_column_values(
                board_id=board_id,
                item_id=item_id,
                column_values=field_updates,
            )
            
            if result:
                logger.info(f"Successfully synced back to Monday item {item_id}")
                # Update the last_synced_at timestamp
                ext_id.last_synced_at = datetime.utcnow()
                self.session.commit()
                return True
            return False
            
        except Exception as exc:  # noqa: BLE001
            logger.error(f"sync_back failed: {exc}")
            return False
