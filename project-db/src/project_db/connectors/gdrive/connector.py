"""Google Drive -> Canonical DB connector.

Syncs file metadata from Google Drive into the canonical Document table.
Content extraction (for LLM use) is a later phase -- this connector is
metadata-only until we have live credentials and a confirmed folder structure.

Linking strategy (two stages):
  1. Folder-name match (primary).  The root folder contains one subfolder per
     project.  Normalize the subfolder name and match against Project.name.
     Cache the (folder_id -> project_id) mapping in ExternalId once resolved.
  2. Content fallback.  Files under unrecognized folders are stored without a
     project link and flagged for manual review via storage_ref.

Delta sync:
  On the first sync, we store a Drive changes-page-token in a one-row
  "connector state" in ExternalId (source=GOOGLE_DRIVE, entity_type="SyncState",
  external_key="page_token").  Subsequent syncs call list_changes() rather than
  crawling the full tree.  Call sync(force_full=True) to re-crawl from root.

Env vars (passed via config dict or picked up from environment):
  GDRIVE_SA_KEY_PATH   -- service-account JSON key path
  GDRIVE_IMPERSONATE   -- Workspace user to impersonate
  GDRIVE_ROOT_FOLDER   -- Drive folder ID to crawl (default: root)
"""
from __future__ import annotations

import json
import logging
import re
import unicodedata
from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from project_db.connectors.base import BaseConnector, SyncReport
from project_db.connectors.gdrive.client import GDriveClient
from project_db.connectors.gdrive.content_pipeline import extract_and_store
from project_db.db.models import ExternalId, Project, SourceSystem
from project_db.db.models.docs import Document
from project_db.identity.matcher import ExactFieldMatcher

logger = logging.getLogger(__name__)

# ExternalId key used to persist the Drive changes cursor.
_CURSOR_KEY = "gdrive_changes_page_token"

# Folder mime type in Drive.
_FOLDER_MIME = "application/vnd.google-apps.folder"


def _parse_rfc3339(value: str | None) -> datetime | None:
    """Parse RFC 3339 timestamps Drive returns (e.g. '2026-05-14T12:34:56.789Z').

    Returns None on missing or unparseable input -- never raises.
    """
    if not value:
        return None
    try:
        # Python 3.11+ handles 'Z' suffix natively; for safety strip and parse.
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None


def _normalize_name(name: str) -> str:
    """Lowercase, strip punctuation, collapse whitespace.

    '5768-5770 St. Laurent (Reno)' -> '5768 5770 st laurent reno'
    """
    # Normalize unicode -> ASCII approximation
    name = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    name = name.lower()
    name = re.sub(r"[^\w\s]", " ", name)  # strip punctuation
    name = re.sub(r"\s+", " ", name).strip()
    return name


# Civic numbers in our portfolio are always 3-5 digits.  Requiring 3+ avoids
# false matches on section-header folders like "01. PROJECTS", "05. INTELLIGENCE".
_CIVIC_NUMBER_RE = re.compile(r"^\s*(\d{3,5})(?:[-\s]+(\d{3,5}))?\b")


def _extract_civic_numbers(name: str) -> set[str]:
    """Pull leading civic number(s) from an address-like name.

    '1455 Rue St. Mathieu'        -> {'1455'}
    '5768-5770 St Laurent'        -> {'5768', '5770'}
    '923 Rockland (Ground Floor)' -> {'923'}
    'Active Projects'             -> set()  (no leading number)
    """
    m = _CIVIC_NUMBER_RE.match(name or "")
    if not m:
        return set()
    nums = {m.group(1)}
    if m.group(2):
        nums.add(m.group(2))
    return nums


def _match_project_by_name(
    session: Session,
    organization_id: Any,
    folder_name: str,
) -> Any | None:
    """Try to link a Drive folder to a canonical Project.

    Two strategies, tried in order (civic FIRST -- it's the more specific
    signal for address-style folders):
      1. Leading civic-number match -- "923 Rockland" beats generic "Rockland"
         because "923" is a hard match.  Handles renderings like
         "1455 Rue St. Mathieu" -> project "1455 Saint Mathieu".
      2. Normalized substring match -- fallback for non-address folder names
         and projects without civic numbers.

    Returns project.canonical_id or None.
    """
    needle = _normalize_name(folder_name)
    if not needle:
        return None

    folder_civics = _extract_civic_numbers(folder_name)
    projects = session.query(Project).all()

    # Pass 1: civic-number match (tight when both sides have a civic).
    if folder_civics:
        for project in projects:
            project_civics = _extract_civic_numbers(project.name or "")
            if project_civics and (folder_civics & project_civics):
                logger.info(
                    "[GDRIVE] folder %r -> Project %r (civic match: %s)",
                    folder_name, project.name, folder_civics & project_civics,
                )
                return project.canonical_id

    # Pass 2: normalized substring match (looser fallback).
    for project in projects:
        haystack = _normalize_name(project.name or "")
        if haystack and (needle == haystack or needle in haystack or haystack in needle):
            logger.info(
                "[GDRIVE] folder %r -> Project %r (name match)",
                folder_name, project.name,
            )
            return project.canonical_id

    return None


class GDriveConnector(BaseConnector):
    """Google Drive connector -- syncs Document metadata to canonical DB."""

    source = SourceSystem.GOOGLE_DRIVE

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        from project_db.config import settings

        sa_key_path = self.config.get("sa_key_path") or settings.google_credentials_path
        impersonate = self.config.get("impersonate") or None

        # Allow injecting a pre-built GDriveClient (for tests).
        injected = self.config.get("_client")
        if injected is not None:
            self.client: GDriveClient = injected
        else:
            self.client = GDriveClient(
                sa_key_path=sa_key_path,
                impersonate=impersonate,
            )

        self.root_folder: str = (
            self.config.get("root_folder")
            or __import__("os").environ.get("GDRIVE_ROOT_FOLDER", "root")
        )

        # Off by default: every sync would otherwise issue one Drive download per
        # file (up to 750 in our portfolio).  The `extract-content` CLI is the
        # primary way to populate DocumentText.  Set extract_content=True in
        # config to opt into in-line extraction during sync.
        self.extract_content: bool = bool(self.config.get("extract_content", False))

        # Cache: folder_id -> project_id (None = unrecognized)
        self._folder_project_cache: dict[str, Any | None] = {}

        # Drive-state reconciliation: track everything the current walk visits
        # so we can soft-mark vanished files at the end.  See _reconcile_removed.
        self._seen_file_ids: set[str] = set()
        self._visited_folder_ids: set[str] = set()

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------

    def sync(self, *, force_full: bool = False) -> SyncReport:
        """Sync Drive files to canonical Document rows.

        On first run (no saved cursor), does a full folder crawl.
        On subsequent runs, uses the changes.list cursor unless force_full=True.
        """
        cursor = self._load_cursor()

        if cursor is None or force_full:
            logger.info(
                "[GDRIVE] Full crawl from root=%s (cursor=%s, force=%s)",
                self.root_folder,
                cursor,
                force_full,
            )
            self._full_sync()
        else:
            logger.info("[GDRIVE] Delta sync from cursor %s", cursor)
            self._delta_sync(cursor)

        return self._finalize()

    # ------------------------------------------------------------------
    # Full crawl
    # ------------------------------------------------------------------

    # Hard cap on recursion depth -- Drive itself caps at 100 levels of nesting,
    # but a 20-deep tree is already pathological for our use case.
    _MAX_DEPTH = 20

    def _full_sync(self) -> None:
        """Walk root folder fully recursively, tracking folder paths.

        At each top-level subfolder we attempt to resolve a canonical Project
        via folder-name match; files nested anywhere under that subfolder
        inherit the project_id and the human-readable folder path.
        """
        self._walk(
            folder_id=self.root_folder,
            folder_path="",
            project_id=None,
            parent_folder_id=None,
            depth=0,
        )

        # Reconcile DB state against current Drive state -- soft-mark vanished
        # files as trashed.  Only safe if the walk completed without listing
        # failures; otherwise a transient permission/network blip could
        # incorrectly trash a swathe of real files.
        self._reconcile_removed()

        # Save a fresh cursor so the next run uses delta sync.
        try:
            new_cursor = self.client.get_start_page_token()
            self._save_cursor(new_cursor)
            logger.info("[GDRIVE] Saved new cursor for delta sync: %s", new_cursor)
        except Exception as exc:  # noqa: BLE001
            logger.warning("[GDRIVE] Could not save delta-sync cursor: %s", exc)

    def _reconcile_removed(self) -> None:
        """Soft-mark Documents that vanished from Drive since the last full sync.

        Scope rules (deliberately conservative -- we'd rather leave a stale row
        than mark a real file trashed by mistake):

          1. If the walk had any listing failures, SKIP.  A transient permission
             error in one folder shouldn't trigger mass-trashing of its files.
          2. Only consider Documents whose parent_folder_id was actually visited
             this run.  This means a sync rooted at a subfolder won't touch
             docs in other parts of the tree, and legacy rows with no
             parent_folder_id (e.g. delta-synced before folder_path existed)
             stay untouched.
          3. Already-trashed rows are skipped (no double-counting in the report).
          4. Per STRATEGY.md "keep everything" -- this is soft delete only.
             The row stays; only is_trashed flips.  If the file reappears
             later, _upsert_document will set is_trashed back to False from
             Drive's `trashed` flag.
        """
        if self.report.records_failed > 0:
            logger.warning(
                "[GDRIVE] Skipping reconciliation: %d listing failure(s) -- "
                "stale rows preserved to avoid wrong-marking real files.",
                self.report.records_failed,
            )
            return

        if not self._visited_folder_ids:
            logger.info("[GDRIVE] Skipping reconciliation: no folders visited.")
            return

        # All non-trashed Documents whose parent_folder_id was in our scope.
        candidates = (
            self.session.query(Document)
            .filter(
                Document.parent_folder_id.in_(self._visited_folder_ids),
                Document.is_trashed.is_(False),
            )
            .all()
        )

        removed = 0
        for doc in candidates:
            if doc.storage_ref in self._seen_file_ids:
                continue
            doc.is_trashed = True
            removed += 1
            logger.info(
                "[GDRIVE] Marked removed: %s (storage_ref=%s, folder_path=%s)",
                doc.name, doc.storage_ref, doc.folder_path,
            )

        if removed:
            self.session.flush()
            self.report.records_removed = removed
            logger.info("[GDRIVE] Reconciliation: %d Documents soft-marked trashed.", removed)
        else:
            logger.info("[GDRIVE] Reconciliation: 0 vanished files (DB matches Drive).")

    def _walk(
        self,
        *,
        folder_id: str,
        folder_path: str,
        project_id: Any | None,
        parent_folder_id: str | None,
        depth: int,
    ) -> None:
        """Recursive folder traversal.

        Tries to resolve every folder name to a canonical Project (cached so
        each folder is checked once per run).  Project folders can sit at any
        depth -- e.g. "01. PROJECTS/ACTIVE/5768 St-Laurent" only matches at
        depth 3.  Once a folder resolves, every file below it inherits that
        project_id.  Inner folders that themselves match (e.g. a sub-project
        nested under a parent project) override the parent's resolution for
        their own subtree.
        """
        if depth > self._MAX_DEPTH:
            logger.warning("[GDRIVE] Max depth %d exceeded at %s", self._MAX_DEPTH, folder_path)
            return

        # Record visit BEFORE listing so reconcile knows we were here even if
        # the listing itself fails downstream.
        self._visited_folder_ids.add(folder_id)

        try:
            items = self.client.list_folder(folder_id)
        except Exception as exc:  # noqa: BLE001
            self._record_failure(f"list_folder({folder_id}, path={folder_path!r}): {exc}")
            return

        logger.debug("[GDRIVE] walk depth=%d path=%r -> %d items", depth, folder_path, len(items))

        for item in items:
            if item.get("mimeType") == _FOLDER_MIME:
                # Try to resolve this folder name to a canonical Project.
                # If it doesn't match, inherit the parent's project_id (which
                # itself may have matched higher up the tree).
                matched = self._resolve_folder_to_project(item["id"], item["name"])
                child_project_id = matched if matched is not None else project_id
                child_path = f"{folder_path}/{item['name']}" if folder_path else item["name"]
                self._walk(
                    folder_id=item["id"],
                    folder_path=child_path,
                    project_id=child_project_id,
                    parent_folder_id=folder_id,
                    depth=depth + 1,
                )
            else:
                self._upsert_document(
                    item,
                    project_id=project_id,
                    folder_path=folder_path,
                    parent_folder_id=folder_id,
                )

    # ------------------------------------------------------------------
    # Delta sync
    # ------------------------------------------------------------------

    def _delta_sync(self, cursor: str) -> None:
        """Process only files that changed since cursor."""
        try:
            changes, new_cursor = self.client.list_changes(cursor)
        except Exception as exc:
            self._record_failure(f"list_changes failed: {exc}")
            return

        logger.info("[GDRIVE] %d changes to process", len(changes))
        for change in changes:
            file_id = change.get("fileId")
            removed = change.get("removed", False)
            file_data = change.get("file")

            if removed or (file_data and file_data.get("trashed")):
                # Mark the Document url as trashed (soft-delete).
                self._handle_removal(file_id)
                continue

            if file_data:
                project_id = self._resolve_folder_to_project_from_file(file_data)
                parent_id = (file_data.get("parents") or [None])[0]
                self._upsert_document(
                    file_data,
                    project_id=project_id,
                    folder_path=None,  # unknown in delta path; next full sync repairs
                    parent_folder_id=parent_id,
                )

        self._save_cursor(new_cursor)

    # ------------------------------------------------------------------
    # Document upsert
    # ------------------------------------------------------------------

    def _upsert_document(
        self,
        file: dict[str, Any],
        *,
        project_id: Any | None,
        folder_path: str | None,
        parent_folder_id: str | None,
    ) -> None:
        """Map a Drive file dict to a canonical Document row.

        Populates every Drive-metadata column we promoted in the model, and
        stashes the rest of the payload in source_meta_json.
        """
        file_id = file.get("id", "")
        name = file.get("name", "Unnamed")
        if file_id:
            self._seen_file_ids.add(file_id)
        mime_type = file.get("mimeType", "")
        url = file.get("webViewLink") or f"https://drive.google.com/file/d/{file_id}"

        # Owner: first owner if multiple (most files have one).
        owners = file.get("owners") or []
        owner_email = owners[0].get("emailAddress") if owners else None

        # Size comes back as a string from Drive -- coerce to int.
        size_str = file.get("size")
        try:
            size_bytes = int(size_str) if size_str is not None else None
        except (TypeError, ValueError):
            size_bytes = None

        attrs: dict[str, Any] = {
            "name": name,
            "mime_type": mime_type,
            "url": url,
            "storage_ref": file_id,
            "created_at_source": _parse_rfc3339(file.get("createdTime")),
            "modified_at_source": _parse_rfc3339(file.get("modifiedTime")),
            "size_bytes": size_bytes,
            "md5_checksum": file.get("md5Checksum"),
            "drive_id": file.get("driveId"),
            "parent_folder_id": parent_folder_id,
            "folder_path": folder_path,
            "owner_email": owner_email,
            "is_trashed": bool(file.get("trashed", False)),
            "source_meta_json": json.dumps(
                {
                    "webContentLink": file.get("webContentLink"),
                    "iconLink": file.get("iconLink"),
                    "shared": file.get("shared"),
                    "starred": file.get("starred"),
                    "owners": owners,
                    "lastModifyingUser": file.get("lastModifyingUser"),
                    "capabilities": file.get("capabilities"),
                    "parents": file.get("parents"),
                },
                default=str,
            ),
        }
        if project_id is not None:
            attrs["project_id"] = project_id

        try:
            result = self.resolver.resolve_or_create(
                source=self.source,
                external_key=file_id,
                external_url=url,
                entity_class=Document,
                attrs=attrs,
                matcher=ExactFieldMatcher(["storage_ref"]),
            )
            self._record_result(result.was_created, result.was_matched)
        except Exception as exc:  # noqa: BLE001
            self._record_failure(f"Document {file_id} ({name}): {exc}")
            return

        if self.extract_content and result.entity is not None:
            try:
                extract_and_store(
                    session=self.session,
                    client=self.client,
                    document=result.entity,
                )
            except Exception as exc:  # noqa: BLE001
                # Never let extraction failure abort the sync.
                self._record_failure(f"extract_content {file_id} ({name}): {exc}")

    def _handle_removal(self, file_id: str) -> None:
        """Soft-delete: mark the document URL as [removed] so we know it's gone."""
        ext = (
            self.session.query(ExternalId)
            .filter_by(
                source=self.source,
                entity_type="Document",
                external_key=file_id,
            )
            .one_or_none()
        )
        if ext is None:
            return  # never saw this file -- nothing to do
        doc = (
            self.session.query(Document)
            .filter_by(canonical_id=ext.canonical_id)
            .one_or_none()
        )
        if doc is not None:
            doc.url = f"[removed] {doc.url}"
            self.session.flush()
            logger.info("[GDRIVE] Marked Document %s as removed", file_id)

    # ------------------------------------------------------------------
    # Project linking
    # ------------------------------------------------------------------

    def _resolve_folder_to_project(self, folder_id: str, folder_name: str) -> Any | None:
        """Return canonical project_id for a Drive subfolder, or None."""
        if folder_id in self._folder_project_cache:
            return self._folder_project_cache[folder_id]

        # Check if we already registered this folder->project mapping.
        ext = (
            self.session.query(ExternalId)
            .filter_by(
                source=self.source,
                entity_type="Project",
                external_key=f"folder:{folder_id}",
            )
            .one_or_none()
        )
        if ext is not None:
            self._folder_project_cache[folder_id] = ext.canonical_id
            return ext.canonical_id

        # Try folder-name match.
        project_id = _match_project_by_name(
            self.session, self.organization_id, folder_name
        )
        if project_id is not None:
            # Persist the mapping so future syncs skip the name match.
            link = ExternalId(
                source=self.source,
                entity_type="Project",
                external_key=f"folder:{folder_id}",
                external_url=None,
                canonical_id=project_id,
            )
            self.session.add(link)
            self.session.flush()

        self._folder_project_cache[folder_id] = project_id
        return project_id

    def _resolve_folder_to_project_from_file(self, file: dict[str, Any]) -> Any | None:
        """Resolve project_id from a file's parents list (delta sync path)."""
        parents = file.get("parents") or []
        for parent_id in parents:
            if parent_id in self._folder_project_cache:
                return self._folder_project_cache[parent_id]
            # Can't resolve without the folder name -- return None and let it
            # be an unlinked document.  The next full sync will repair linkage.
        return None

    # ------------------------------------------------------------------
    # Cursor persistence  (stored as a synthetic ExternalId row)
    # ------------------------------------------------------------------

    def _load_cursor(self) -> str | None:
        """Load the persisted Drive changes page token, or None."""
        ext = (
            self.session.query(ExternalId)
            .filter_by(
                source=self.source,
                entity_type="SyncState",
                external_key=_CURSOR_KEY,
            )
            .one_or_none()
        )
        return ext.external_url if ext is not None else None

    def _save_cursor(self, token: str) -> None:
        """Persist the Drive changes page token for the next run."""
        ext = (
            self.session.query(ExternalId)
            .filter_by(
                source=self.source,
                entity_type="SyncState",
                external_key=_CURSOR_KEY,
            )
            .one_or_none()
        )
        if ext is None:
            ext = ExternalId(
                source=self.source,
                entity_type="SyncState",
                external_key=_CURSOR_KEY,
                canonical_id=self.organization_id,  # any stable UUID as anchor
            )
            self.session.add(ext)
        ext.external_url = token  # reuse this column as the token store
        self.session.flush()
