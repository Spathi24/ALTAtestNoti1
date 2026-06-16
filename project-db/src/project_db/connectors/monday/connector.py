"""Monday.com -> canonical DB connector.

Board classification is config-driven (regex patterns) so renaming a board
in Monday doesn't require touching Python. Column extraction uses heuristic
title matching + optional explicit column_id overrides.

Sync model: every run is a full board pull. Monday's API-Version 2026-07
removed `updated_after` from items_page, so true delta sync only works via
webhooks (not yet implemented). One full sync against the live workspace
is ~30s and a few hundred items, which is fine for nightly cadence.

Board mapping (DEFAULT_BOARD_MAPPING):
  CRM workspace           -> Lead, Deal, Client boards
  Project Management ws   -> Project boards (one per property / job)
  Admin workspace         -> skipped (reporting-only boards)

Column mapping per board type is in DEFAULT_COLUMN_MAPPING. Override via
connector config if your Monday column ids/titles differ.

Write-back capability:
  MondayConnector.sync_back() pushes canonical changes to Monday. Use after
  syncing data from other sources (e.g., QB invoices -> update project status).
"""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime
from decimal import Decimal
from typing import Any

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
    TaskDependency,
    TaskStatus,
    User,
)
from project_db.identity.matcher import ExactFieldMatcher, ProjectMatcher

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

# NOTE: board classification is allowlist-only (see _classify_board).  A board
# that matches no rule above is skipped, never guessed into a Project.


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


# ---------------------------------------------------------------------------
# Portfolio mirror overlay
#
# Construction-side task boards (e.g. "923 Rockland") often store the real
# status / timeline for each task as MIRROR columns on a separate PORTFOLIO
# item that the task is linked to via a board_relation column. Those mirror
# columns contain `mirrored_items` keyed by task id.
#
# `apply_portfolio_mirror_overlay` walks the link in reverse, fetches the
# portfolio items, and merges their mirrored values back into each source
# task as synthetic column_values so the existing ColumnExtractor sees them
# the same way it sees native columns.
# ---------------------------------------------------------------------------

# portfolio column id -> (synthetic task-board column id, title, type)
MIRROR_COLUMN_MAP: dict[str, tuple[str, str, str]] = {
    "portfolio_project_progress": ("project_status", "Status", "status"),
    "portfolio_project_actual_timeline": ("project_timeline", "Timeline", "timeline"),
}
# Fallback when column ids differ across portfolios.
MIRROR_TITLE_MAP: dict[str, tuple[str, str, str]] = {
    "project progress": ("project_status", "Status", "status"),
    "progress": ("project_status", "Status", "status"),
    "actual timeline": ("project_timeline", "Timeline", "timeline"),
}


def _collect_linked_item_ids(items: list[dict[str, Any]]) -> list[str]:
    """De-duplicated, ordered list of board_relation linked_item_ids.

    Recurses into subitems -- on these boards a subitem carries its own
    board_relation link to the portfolio, and most real tasks ARE subitems,
    so a top-level-only scan misses the link for the bulk of the board.
    """
    seen: set[str] = set()
    ordered: list[str] = []

    def _scan(item: dict[str, Any]) -> None:
        for cv in item.get("column_values") or []:
            if cv.get("type") not in ("board_relation", "dependency"):
                continue
            for raw_id in cv.get("linked_item_ids") or []:
                sid = str(raw_id)
                if sid not in seen:
                    seen.add(sid)
                    ordered.append(sid)
        for sub in item.get("subitems") or []:
            _scan(sub)

    for item in items:
        _scan(item)
    return ordered


def _synthetic_column_value(
    *,
    synthetic_id: str,
    synthetic_title: str,
    synthetic_type: str,
    mirrored_value: dict[str, Any],
    portfolio_item_id: Any,
    portfolio_column_id: str,
) -> dict[str, Any] | None:
    """Shape a mirrored value into a normal Monday column_value dict."""
    source = {
        "kind": "mirror",
        "linked_item_id": portfolio_item_id,
        "mirror_column_id": portfolio_column_id,
    }

    if synthetic_type == "status":
        label = mirrored_value.get("label")
        if not label:
            return None
        return {
            "id": synthetic_id,
            "type": "status",
            "text": label,
            "value": None,
            "column": {"id": synthetic_id, "title": synthetic_title, "type": "status"},
            "label": label,
            "index": mirrored_value.get("index"),
            "is_done": mirrored_value.get("is_done"),
            "_source": source,
        }

    if synthetic_type == "timeline":
        start = mirrored_value.get("from")
        end = mirrored_value.get("to")
        if not start and not end:
            return None
        start_date = (start or "")[:10] or None
        end_date = (end or "")[:10] or None
        if start_date and end_date:
            text = f"{start_date} - {end_date}"
        else:
            text = start_date or end_date or ""
        return {
            "id": synthetic_id,
            "type": "timeline",
            "text": text,
            "value": None,
            "column": {"id": synthetic_id, "title": synthetic_title, "type": "timeline"},
            "from": start_date,
            "to": end_date,
            "visualization_type": mirrored_value.get("visualization_type"),
            "_source": source,
        }

    return None


def build_task_mirror_overlay(
    linked_items: list[dict[str, Any]],
) -> dict[str, list[dict[str, Any]]]:
    """Return {task_item_id: [synthetic column_values]} from mirror columns."""
    overlay: dict[str, list[dict[str, Any]]] = {}

    for linked_item in linked_items:
        linked_id = linked_item.get("id")
        for cv in linked_item.get("column_values") or []:
            if cv.get("type") != "mirror":
                continue
            col_id = cv.get("id") or ""
            column_meta = cv.get("column") or {}
            title = (column_meta.get("title") or "").strip().lower()

            mapping = MIRROR_COLUMN_MAP.get(col_id) or MIRROR_TITLE_MAP.get(title)
            if mapping is None:
                continue
            synthetic_id, synthetic_title, synthetic_type = mapping

            for mirrored in cv.get("mirrored_items") or []:
                task = mirrored.get("linked_item") or {}
                task_id = str(task.get("id") or "")
                if not task_id:
                    continue
                synthetic = _synthetic_column_value(
                    synthetic_id=synthetic_id,
                    synthetic_title=synthetic_title,
                    synthetic_type=synthetic_type,
                    mirrored_value=mirrored.get("mirrored_value") or {},
                    portfolio_item_id=linked_id,
                    portfolio_column_id=col_id,
                )
                if synthetic is None:
                    continue
                overlay.setdefault(task_id, []).append(synthetic)

    return overlay


def apply_portfolio_mirror_overlay(
    client: MondayClient,
    items: list[dict[str, Any]],
    *,
    board: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Enrich task items with mirror-column values from linked portfolio items.

    For each task, follow its board_relation links, fetch those portfolio
    items, and append synthetic column_values (status, timeline, etc.) for
    each mirror column on the portfolio item that points back to this task.

    Returns a NEW list. Original items are not mutated. If no tasks link
    anywhere, returns the input list unchanged.
    """
    linked_ids = _collect_linked_item_ids(items)
    if not linked_ids:
        return items

    try:
        linked_items = client.get_items_with_mirror_values(linked_ids)
    except Exception as exc:
        board_label = (board or {}).get("name") or (board or {}).get("id")
        logger.warning(
            "Mirror overlay fetch failed (board=%s): %s -- continuing without",
            board_label,
            exc,
        )
        return items

    overlay = build_task_mirror_overlay(linked_items)
    if not overlay:
        return items

    def _inject(item: dict[str, Any]) -> tuple[dict[str, Any], int]:
        """Add synthetic mirror column_values to an item, RECURSING into its
        subitems.  Most real tasks on these boards are subitems, so a
        top-level-only pass leaves the bulk of the board unenriched.

        Native column_values always win -- a synthetic value is added only
        for a column id the row does not already populate.  Returns
        (item_or_copy, number_of_tasks_enriched).
        """
        count = 0
        result = item
        extra = overlay.get(str(item.get("id") or "")) or []
        if extra:
            existing_cvs = list(item.get("column_values") or [])
            existing_ids = {cv.get("id") for cv in existing_cvs}
            additions = [cv for cv in extra if cv.get("id") not in existing_ids]
            if additions:
                result = dict(item)
                result["column_values"] = existing_cvs + additions
                count += 1
        subitems = item.get("subitems")
        if subitems:
            new_subitems: list[dict[str, Any]] = []
            for sub in subitems:
                new_sub, sub_count = _inject(sub)
                new_subitems.append(new_sub)
                count += sub_count
            if result is item:
                result = dict(item)
            result["subitems"] = new_subitems
        return result, count

    enriched: list[dict[str, Any]] = []
    injected = 0
    for item in items:
        new_item, count = _inject(item)
        enriched.append(new_item)
        injected += count

    if injected:
        board_label = (board or {}).get("name") or (board or {}).get("id") or "<unknown>"
        logger.info(
            "Mirror overlay: enriched %d task(s) (items + subitems) on board "
            "%r from %d portfolio item(s)",
            injected,
            board_label,
            len(linked_items),
        )
    return enriched


def _column_values_json(column_values: list[dict[str, Any]]) -> str:
    """Compact JSON snapshot of Monday column values for diagnostics."""
    keep: list[dict[str, Any]] = []
    for cv in column_values:
        column = cv.get("column") or {}
        keep.append(
            {
                "id": cv.get("id"),
                "title": column.get("title"),
                "type": cv.get("type"),
                "text": cv.get("text"),
                "value": cv.get("value"),
                "label": cv.get("label"),
                "number": cv.get("number"),
                "from": cv.get("from"),
                "to": cv.get("to"),
                "display_value": cv.get("display_value"),
                # Graph edges (dependency / board_relation). Previously dropped,
                # which discarded the task dependency graph -- keep them so the
                # dependency-capture pass can resolve predecessors by id.
                "linked_item_ids": cv.get("linked_item_ids") or [],
            }
        )
    return json.dumps(keep, default=str, separators=(",", ":"))


def resolve_dependency_predecessors(
    column_values: list[dict[str, Any]],
    *,
    task_id_by_monday_id: dict[str, Any],
    task_id_by_title: dict[str, Any],
) -> list[Any]:
    """Resolve the predecessor canonical task ids from an item's dependency
    column(s).

    Monday's "Dependent On" column on the current item lists the tasks it waits
    on (its predecessors). We resolve each, preferring the structured
    ``linked_item_ids`` (Monday item id -> canonical task via
    ``task_id_by_monday_id``) and falling back to matching the comma-joined
    ``display_value`` names against in-project task titles
    (``task_id_by_title``; ambiguous titles are excluded by the caller).

    Pure + order-preserving + de-duplicated. Returns canonical task ids.
    """
    preds: list[Any] = []
    seen: set[Any] = set()
    for cv in column_values or []:
        if cv.get("type") != "dependency":
            continue
        resolved_any = False
        for mid in cv.get("linked_item_ids") or []:
            tid = task_id_by_monday_id.get(str(mid))
            if tid is not None and tid not in seen:
                preds.append(tid)
                seen.add(tid)
                resolved_any = True
        # Fall back to names only when ids were absent or none resolved.
        if not resolved_any:
            disp = (cv.get("display_value") or "").strip()
            if not disp:
                continue
            for name in (n.strip() for n in disp.split(",")):
                tid = task_id_by_title.get(name.lower()) if name else None
                if tid is not None and tid not in seen:
                    preds.append(tid)
                    seen.add(tid)
    return preds


def rebuild_dependency_edges(
    session: Any,
    synced: list[tuple[str, Any, str, list[dict[str, Any]]]],
) -> int:
    """Idempotently rebuild the MONDAY dependency edges for synced tasks.

    ``synced`` is a list of ``(monday_id, canonical_task_id, title,
    column_values)`` for every task on a board/project. Clears the existing
    MONDAY inbound edges for those tasks, then inserts the current predecessor
    set -- so a dependency added OR removed in Monday is reflected on re-sync.
    Returns the number of edges inserted.
    """
    if not synced:
        return 0
    task_id_by_monday_id = {mid: tid for mid, tid, _title, _cvs in synced}
    # Title map for the name fallback; drop ambiguous (duplicate) titles so we
    # never guess the wrong predecessor.
    title_counts: dict[str, int] = {}
    for _mid, _tid, title, _cvs in synced:
        key = title.strip().lower()
        title_counts[key] = title_counts.get(key, 0) + 1
    task_id_by_title = {
        title.strip().lower(): tid
        for _mid, tid, title, _cvs in synced
        if title.strip() and title_counts[title.strip().lower()] == 1
    }

    synced_task_ids = [tid for _mid, tid, _title, _cvs in synced]
    session.query(TaskDependency).filter(
        TaskDependency.successor_task_id.in_(synced_task_ids),
        TaskDependency.source == SourceSystem.MONDAY,
    ).delete(synchronize_session=False)

    seen_edges: set[tuple[Any, Any]] = set()
    inserted = 0
    for _mid, successor_id, _title, column_values in synced:
        predecessors = resolve_dependency_predecessors(
            column_values,
            task_id_by_monday_id=task_id_by_monday_id,
            task_id_by_title=task_id_by_title,
        )
        for predecessor_id in predecessors:
            if predecessor_id == successor_id:
                continue  # never self-link
            edge = (predecessor_id, successor_id)
            if edge in seen_edges:
                continue
            seen_edges.add(edge)
            session.add(
                TaskDependency(
                    predecessor_task_id=predecessor_id,
                    successor_task_id=successor_id,
                    source=SourceSystem.MONDAY,
                )
            )
            inserted += 1
    return inserted


class MondayConnector(BaseConnector):
    source = SourceSystem.MONDAY

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        from project_db.config import settings

        self.client = MondayClient(token=self.config.get("api_token") or settings.monday_api_token)
        self.board_mapping: list[dict[str, Any]] = self.config.get(
            "board_mapping", DEFAULT_BOARD_MAPPING
        )
        self.column_mapping: dict[str, dict[str, str]] = self.config.get(
            "column_mapping", DEFAULT_COLUMN_MAPPING
        )

    # ------------------------------------------------------------------
    # Entry point
    # ------------------------------------------------------------------

    # Cursor storage: each board has its own activity-log cursor (ISO8601
    # timestamp stored as the external_url of a synthetic ExternalId row).
    # Pattern mirrors what GDriveConnector does for changes.list.
    _CURSOR_PREFIX = "monday_board_cursor:"

    def sync(self, *, delta: bool = False) -> SyncReport:
        """Sync Monday data to canonical DB.

        Args:
          delta: If True, query ``Board.activity_logs`` for each board and
                 SKIP boards that have had zero activity since the cursor
                 stored from the last run.  At small scale this saves the
                 cost of a full board pull on quiet boards.  Per-item
                 delta -- refetching only changed items rather than the
                 whole board -- is a future enhancement built on the same
                 endpoint.  Default False (full pull on every board).
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

            sync_started_at = datetime.utcnow()
            skipped_unchanged = 0
            for board in boards:
                if board.get("state") != "active":
                    continue
                # Skip Monday's auto-generated subitem mirror boards
                if re.match(r"(?i)subitems?\s+of\b", board["name"]):
                    logger.debug("Skipping subitem mirror board %r", board["name"])
                    continue
                entity_type = self._classify_board(board["name"])
                if entity_type is None:
                    logger.info(
                        "[MONDAY] skipped board %r -- no board_mapping rule "
                        "matched (add a rule to ingest it)",
                        board["name"],
                    )
                    continue

                if delta and not self._board_has_changes(board["id"]):
                    skipped_unchanged += 1
                    logger.info(
                        "[MONDAY] delta: skipping board %r (no activity since cursor)",
                        board["name"],
                    )
                    continue

                self._sync_board(board, entity_type)
                # Advance the per-board cursor only after a successful sync.
                self._save_board_cursor(board["id"], sync_started_at)

            if delta:
                logger.info(
                    "[MONDAY] delta sync: %d board(s) skipped as unchanged",
                    skipped_unchanged,
                )

        except Exception as exc:
            self._record_failure(f"sync failed: {exc}")
        return self._finalize()

    # ------------------------------------------------------------------
    # Activity-log cursor storage
    # ------------------------------------------------------------------

    def _board_has_changes(self, board_id: Any) -> bool:
        """True iff the board has at least one activity-log event since
        the stored cursor.  No cursor yet (= first delta run) returns
        True so the board gets synced and a cursor saved for next time.
        """
        cursor_ts = self._load_board_cursor(board_id)
        if cursor_ts is None:
            return True
        try:
            events = self.client.list_activity_logs(
                int(board_id),
                from_ts=cursor_ts,
                limit=1,
                max_pages=1,
            )
        except Exception as exc:
            logger.warning(
                "[MONDAY] activity_logs probe failed on board=%s: %s "
                "(treating as changed to be safe)",
                board_id,
                exc,
            )
            return True
        return bool(events)

    def _load_board_cursor(self, board_id: Any) -> datetime | None:
        ext = (
            self.session.query(ExternalId)
            .filter_by(
                source=self.source,
                entity_type="SyncState",
                external_key=f"{self._CURSOR_PREFIX}{board_id}",
            )
            .one_or_none()
        )
        if ext is None or not ext.external_url:
            return None
        try:
            return datetime.fromisoformat(ext.external_url)
        except (TypeError, ValueError):
            return None

    def _save_board_cursor(self, board_id: Any, ts: datetime) -> None:
        ext = (
            self.session.query(ExternalId)
            .filter_by(
                source=self.source,
                entity_type="SyncState",
                external_key=f"{self._CURSOR_PREFIX}{board_id}",
            )
            .one_or_none()
        )
        if ext is None:
            ext = ExternalId(
                source=self.source,
                entity_type="SyncState",
                external_key=f"{self._CURSOR_PREFIX}{board_id}",
                canonical_id=self.organization_id,  # stable anchor
            )
            self.session.add(ext)
        ext.external_url = ts.isoformat()
        self.session.flush()

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
        except Exception as exc:
            logger.warning("User sync failed (non-fatal): %s", exc)

    # ------------------------------------------------------------------
    # Board classification & sync dispatch
    # ------------------------------------------------------------------

    # ------------------------------------------------------------------
    # Board classification & sync dispatch
    # ------------------------------------------------------------------

    def _classify_board(self, name: str) -> str | None:
        """Classify a board to an entity type via the board_mapping allowlist.

        Fail closed: a board matching NO rule returns None and is skipped.
        Only an explicit allowlisted rule may cause a board to mint or
        attach project / CRM entities -- this stops a future board (a stray
        portfolio board, a "New Deal - Construction" board) from silently
        polluting the canonical projects.  The sync logs every skipped
        board so the gap is visible and a rule can be added deliberately.
        """
        for rule in self.board_mapping:
            if re.search(rule["pattern"], name):
                return rule["entity"]
        return None

    def _sync_board(self, board: dict[str, Any], entity_type: str) -> None:
        """Sync a single board (full pull -- no delta sync)."""
        board_id = int(board["id"])

        column_defs = self.client.list_board_columns(board_id)
        explicit_mapping = self.column_mapping.get(entity_type, {})
        extractor = ColumnExtractor(column_defs, explicit_mapping=explicit_mapping)

        items = self.client.list_items(
            board_id,
            include_subitems=(entity_type == "ProjectBoard"),
        )

        logger.info(
            "  board %r -> %s -- %d items, %d columns",
            board["name"],
            entity_type,
            len(items),
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
            except Exception as exc:
                self._record_failure(f"item {item.get('id')} on board {board['name']!r}: {exc}")

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
            external_url=f"https://view.monday.com/boards/{board['id']}/pulses/{item['id']}",
            entity_class=Project,
            attrs=attrs,
            # Attach to the Drive-defined Project (civic / exact name).
            # create_only_attrs keeps the Drive folder name authoritative.
            matcher=ProjectMatcher(),
            create_only_attrs={"name"},
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
            external_url=f"https://view.monday.com/boards/{board['id']}/pulses/{item['id']}",
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
            external_url=f"https://view.monday.com/boards/{board['id']}/pulses/{item['id']}",
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
            external_url=f"https://view.monday.com/boards/{board['id']}/pulses/{item['id']}",
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
        """Create/update one Project from the board, then sync items as Tasks.

        Many tasks on these boards have their real status/timeline stored
        as mirror columns on a linked PORTFOLIO item (typically on a parent
        "portfolio" board like Rockland). Before extracting fields, we
        follow each task's board_relation links, fetch those portfolio
        items, and overlay the mirrored values back onto the source tasks.
        """
        project_attrs: dict[str, Any] = {
            "name": board["name"],
            "code": f"MONDAY-BOARD-{board['id']}",
            "status": ProjectStatus.ACTIVE,
            "client_id": self._resolve_client_id(None),
        }
        project_result = self.resolver.resolve_or_create(
            source=self.source,
            external_key=f"board:{board['id']}",
            external_url=f"https://view.monday.com/boards/{board['id']}",
            entity_class=Project,
            attrs=project_attrs,
            # ProjectMatcher attaches this board to the Drive-defined Project
            # (civic / exact name).  create_only_attrs keeps the Drive folder
            # name authoritative -- Monday never renames a matched project.
            matcher=ProjectMatcher(),
            create_only_attrs={"name"},
        )
        self._record_result(project_result.was_created, project_result.was_matched)
        project_id = project_result.entity.canonical_id

        # Overlay mirror-column values from any linked portfolio items.
        items = self._apply_portfolio_mirror_overlay(board, items)

        extractor = ColumnExtractor(column_defs)
        # (monday_id, canonical_task_id, title, column_values) for every task
        # synced on this board -- the dependency pass needs the full set so it
        # can resolve predecessors (which may be subitems) by id or by title.
        synced: list[tuple[str, Any, str, list[dict[str, Any]]]] = []
        for item in items:
            if item.get("state") == "deleted":
                continue
            try:
                fields = extractor.extract(item.get("column_values") or [])
                parent_task_id = self._upsert_task(board, item, fields, project_id)
                synced.append(
                    (
                        str(item["id"]),
                        parent_task_id,
                        item.get("name") or "",
                        item.get("column_values") or [],
                    )
                )
                for subitem in item.get("subitems") or []:
                    if subitem.get("state") == "deleted":
                        continue
                    sub_fields = extractor.extract(subitem.get("column_values") or [])
                    sub_task_id = self._upsert_task(
                        board,
                        subitem,
                        sub_fields,
                        project_id,
                        parent_task_id=parent_task_id,
                        parent_group_title=(item.get("group") or {}).get("title", ""),
                    )
                    synced.append(
                        (
                            str(subitem["id"]),
                            sub_task_id,
                            subitem.get("name") or "",
                            subitem.get("column_values") or [],
                        )
                    )
            except Exception as exc:
                self._record_failure(
                    f"task item {item.get('id')} on board {board['name']!r}: {exc}"
                )

        try:
            self._sync_task_dependencies(synced)
        except Exception as exc:
            self._record_failure(f"dependency sync on board {board['name']!r}: {exc}")

    def _sync_task_dependencies(
        self,
        synced: list[tuple[str, Any, str, list[dict[str, Any]]]],
    ) -> None:
        """Rebuild the Monday dependency edges for the tasks just synced."""
        n = rebuild_dependency_edges(self.session, synced)
        if n:
            logger.info("Synced %d task dependency edge(s)", n)

    # ------------------------------------------------------------------
    # Portfolio mirror overlay (thin wrappers around module-level helpers
    # so the optimizer / debug scripts can reuse the logic without going
    # through a connector instance + DB session).
    # ------------------------------------------------------------------

    def _apply_portfolio_mirror_overlay(
        self,
        board: dict[str, Any],
        items: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        return apply_portfolio_mirror_overlay(self.client, items, board=board)

    def _upsert_task(
        self,
        board: dict[str, Any],
        item: dict[str, Any],
        fields: Any,
        project_id: Any,
        parent_task_id: Any | None = None,
        parent_group_title: str | None = None,
    ) -> Any:
        group_title = (item.get("group") or {}).get("title") or parent_group_title
        attrs: dict[str, Any] = {
            "title": item["name"],
            "status": fields.task_status or TaskStatus.TODO,
            "project_id": project_id,
            "group_title": group_title,
            "is_subitem": parent_task_id is not None,
            "parent_task_id": parent_task_id,
            "source_columns_json": _column_values_json(item.get("column_values") or []),
        }
        if fields.status_label:
            attrs["monday_status_label"] = fields.status_label
        if fields.priority:
            attrs["priority"] = fields.priority
        if fields.start_date:
            attrs["start_date"] = fields.start_date
        if fields.end_date:
            attrs["end_date"] = fields.end_date
        if fields.end_date:
            attrs["due_date"] = fields.end_date
        duration_days = fields.duration_days
        if duration_days is None and fields.start_date and fields.end_date:
            duration_days = float((fields.end_date - fields.start_date).days) or 1.0
        if duration_days is not None:
            attrs["duration_days"] = Decimal(str(duration_days))
        if fields.planned_effort is not None:
            attrs["planned_effort"] = Decimal(str(fields.planned_effort))
        if fields.effort_spent is not None:
            attrs["effort_spent"] = Decimal(str(fields.effort_spent))
        if fields.subcontractor:
            attrs["subcontractor"] = fields.subcontractor
        if fields.supplier:
            attrs["supplier"] = fields.supplier

        result = self.resolver.resolve_or_create(
            source=self.source,
            external_key=str(item["id"]),
            external_url=f"https://view.monday.com/boards/{board['id']}/pulses/{item['id']}",
            entity_class=Task,
            attrs=attrs,
        )
        self._record_result(result.was_created, result.was_matched)
        return result.entity.canonical_id

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    # Strings we will refuse to treat as real client names when they leak in
    # from heuristic column extraction (group titles, action labels, etc.).
    _NON_CLIENT_NAME_RE = re.compile(
        r"^(move\s+to|todo|n/?a|none|tbd|unknown|new\s+\w+\s+stage|--+)$",
        re.IGNORECASE,
    )

    def _resolve_client_id(self, client_name: str | None) -> Any:
        """Return a canonical client_id for a given name.

        Looks for an existing Client by exact name match. If none is found,
        falls back to the per-org "Unknown Client" placeholder rather than
        auto-creating an arbitrary Client from heuristic extraction. Real
        new Clients should only enter via `_upsert_client` from an actual
        Monday Clients board sync.
        """
        name = (client_name or "").strip()
        if name and not self._NON_CLIENT_NAME_RE.match(name):
            existing = (
                self.session.query(Client)
                .filter_by(name=name, organization_id=self.organization_id)
                .first()
            )
            if existing:
                return existing.canonical_id

        # Fall back to the per-org placeholder. Create it once if missing.
        placeholder = (
            self.session.query(Client)
            .filter_by(name="Unknown Client", organization_id=self.organization_id)
            .first()
        )
        if placeholder is None:
            placeholder = Client(name="Unknown Client", organization_id=self.organization_id)
            self.session.add(placeholder)
            self.session.flush()
            logger.info(
                "Created 'Unknown Client' placeholder (canonical_id=%s)",
                placeholder.canonical_id,
            )
        return placeholder.canonical_id

    # ------------------------------------------------------------------
    # Write-back: sync canonical changes back to Monday
    # ------------------------------------------------------------------

    _URL_BOARD_RE = re.compile(r"/boards/(\d+)")

    def _board_id_from_url(self, url: str | None) -> int | None:
        """Extract board_id from a stored external_url. No API call."""
        if not url:
            return None
        m = self._URL_BOARD_RE.search(url)
        return int(m.group(1)) if m else None

    def _resolve_column_id(self, board_id: int, logical_name: str) -> str | None:
        """Map a logical field name like 'status' to the real Monday column id
        for this specific board (cached in MondayClient).

        Rules:
          - If a real column with this exact id exists, use it as-is.
          - Otherwise look for a column whose type/title hints at the role:
              status   -> first column of type 'status' whose title contains 'status'
              priority -> first column of type 'status' whose title contains 'priority'
              date / due_date / timeline -> matching column types
              budget   -> first 'numbers' column whose title contains 'budget'
        """
        cols = self.client.list_board_columns(board_id)  # cached
        by_id = {c["id"]: c for c in cols}
        if logical_name in by_id:
            return logical_name

        wanted = logical_name.lower()

        def find(col_type: str, title_hint: str | None = None) -> str | None:
            for c in cols:
                if c.get("type") != col_type:
                    continue
                if title_hint and title_hint not in (c.get("title") or "").lower():
                    continue
                return c["id"]
            return None

        if wanted == "status":
            return find("status", "status") or find("status")
        if wanted == "priority":
            return find("status", "priority")
        if wanted in ("date", "due_date"):
            return find("date")
        if wanted == "timeline":
            return find("timeline")
        if wanted == "budget":
            return find("numbers", "budget") or find("numbers")
        if wanted == "name":
            # 'name' isn't a column_value in Monday — caller should use a name mutation
            return None
        return None

    def sync_back(
        self,
        canonical_entity: Any,
        field_updates: dict[str, Any],
    ) -> bool:
        """Push changes from canonical entity back to Monday.

        ``field_updates`` keys may be EITHER real Monday column ids
        (``project_status``) OR logical names (``status``, ``priority``,
        ``budget``, ``date``, ``timeline``). Logical names get resolved to
        the real per-board column id automatically.

        Reads board_id from the stored ExternalId.external_url — no extra
        Monday API call to find which board an item lives on.
        """
        # --- setup phase: return False on lookup/parsing failures -----------
        # The API call below is intentionally outside this try so that Monday
        # API errors (e.g. invalid status label) propagate to the caller and
        # can be surfaced to the user rather than being swallowed here.
        try:
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
                    "No Monday mapping for %s %s", entity_type, canonical_entity.canonical_id
                )
                return False

            # Parse item_id from external_key
            if (ext_id.external_key or "").startswith("board:"):
                logger.warning(
                    "Cannot sync_back a ProjectBoard wrapper item; update its tasks instead"
                )
                return False
            try:
                item_id = int(ext_id.external_key)
            except (ValueError, TypeError):
                logger.warning("Invalid external_key format: %r", ext_id.external_key)
                return False

            # Parse board_id from URL (no API call!) — fallback to API only if
            # we have a legacy row from before we embedded board_id in URL.
            board_id = self._board_id_from_url(ext_id.external_url)
            if board_id is None:
                logger.info(
                    "external_url has no board_id for item %s — falling back to API lookup. "
                    "Re-run sync to update the URL.",
                    item_id,
                )
                gql = "query ($ids: [ID!]!) { items(ids: $ids) { board { id } } }"
                try:
                    data = self.client.query(gql, {"ids": [item_id]})
                    items = data.get("items") or []
                    if items:
                        board_id = int(items[0]["board"]["id"])
                except Exception as exc:
                    logger.warning("API fallback to find board_id failed: %s", exc)
                if board_id is None:
                    return False

            # Resolve logical column names to real per-board column ids.
            resolved: dict[str, Any] = {}
            for key, value in field_updates.items():
                col_id = self._resolve_column_id(board_id, key)
                if col_id is None:
                    logger.warning("Cannot resolve column %r on board %s — skipping", key, board_id)
                    continue
                resolved[col_id] = value

            if not resolved:
                logger.warning("sync_back: no resolvable column updates for item %s", item_id)
                return False

        except Exception as exc:
            logger.error("sync_back setup failed: %s", exc)
            return False

        # --- API call: let exceptions propagate so callers see the real error
        logger.info(
            "Syncing back %s %s -> Monday item %s on board %s: %s",
            entity_type,
            canonical_entity.canonical_id,
            item_id,
            board_id,
            list(resolved.keys()),
        )
        result = self.client.change_multiple_column_values(
            board_id=board_id,
            item_id=item_id,
            column_values=resolved,
        )
        if result:
            ext_id.last_synced_at = datetime.utcnow()
            self.session.commit()
            return True
        return False

    def create_task(
        self, project: Any, title: str, parent_task: Any | None = None
    ) -> dict[str, Any]:
        """Create a new Monday item (or subitem) and return the created dict.

        When ``parent_task`` is given, the new task is created as a SUBITEM of
        that parent's Monday item (preserving the board hierarchy that the
        read side already mirrors via ``is_subitem`` / ``parent_task_id``).
        Otherwise a top-level item is created on the project's board.

        Raises RuntimeError if the required Monday mapping is missing or if the
        Monday API returns an error.
        """
        # --- subitem path: needs the PARENT's Monday item id ---------------
        if parent_task is not None:
            parent_ext = (
                self.session.query(ExternalId)
                .filter(
                    ExternalId.source == self.source,
                    ExternalId.entity_type == "Task",
                    ExternalId.canonical_id == parent_task.canonical_id,
                )
                .one_or_none()
            )
            if not parent_ext or (parent_ext.external_key or "").startswith("board:"):
                raise RuntimeError(
                    f"Cannot create subitem: parent Task {parent_task.canonical_id} "
                    f"({getattr(parent_task, 'title', '?')!r}) has no Monday item "
                    f"mapping -- run a Monday sync first"
                )
            try:
                parent_item_id = int(parent_ext.external_key)
            except (ValueError, TypeError) as exc:
                raise RuntimeError(
                    f"Parent Task has a non-numeric Monday key {parent_ext.external_key!r}"
                ) from exc
            return self.client.create_subitem(parent_item_id=parent_item_id, item_name=title)

        # --- top-level path: needs the PROJECT's board id ------------------
        ext_id = (
            self.session.query(ExternalId)
            .filter(
                ExternalId.source == self.source,
                ExternalId.entity_type == "Project",
                ExternalId.canonical_id == project.canonical_id,
                ExternalId.external_key.like("board:%"),
            )
            .one_or_none()
        )
        if not ext_id:
            raise RuntimeError(
                f"No Monday board mapping for Project {project.canonical_id} "
                f"({project.name!r}) -- run a Monday sync first"
            )
        board_id = int(ext_id.external_key.split(":", 1)[1])
        return self.client.create_item(board_id=board_id, item_name=title)
