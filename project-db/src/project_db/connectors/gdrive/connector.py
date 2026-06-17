"""Google Drive -> Canonical DB connector.

Syncs file metadata from Google Drive into the canonical Document table.
Content extraction (for LLM use) is a later phase -- this connector is
metadata-only until we have live credentials and a confirmed folder structure.

Linking strategy (deterministic -- folder ancestry, no name guessing):
  Drive's folder tree IS the project registry.  A folder sitting exactly at
  ``01. PROJECTS/<ACTIVE|INACTIVE|LEADS>/<name>`` is one canonical Project;
  the connector CREATES it (keyed by folder id -- two folders are never
  merged).  Every file beneath a project folder inherits that project_id by
  ancestry.  Files outside the projects tree (00. COMPANY, 02. REAL ESTATE,
  03. CONSTRUCTION, 05. INTELLIGENCE) get a `category` instead of a project.
  Monday boards later match INTO these Drive-defined projects -- see
  identity/matcher.py:ProjectMatcher.

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
from datetime import datetime
from typing import Any

from project_db.connectors.base import BaseConnector, SyncReport
from project_db.connectors.gdrive.client import GDriveClient
from project_db.connectors.gdrive.content_pipeline import extract_and_store
from project_db.db.models import ExternalId, Project, SourceSystem
from project_db.db.models.docs import Document
from project_db.db.models.work import ProjectStatus
from project_db.identity.matcher import ExactFieldMatcher, normalize_name

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


# --- Drive folder taxonomy -------------------------------------------------
#
# Project folders live exactly three levels deep:
#     01. PROJECTS / <bucket> / <project folder>
# Everything else is company knowledge, classified by its top-level area.

# Bucket folder name (under "01. PROJECTS") -> default ProjectStatus.
_PROJECT_BUCKETS: dict[str, ProjectStatus] = {
    "ACTIVE": ProjectStatus.ACTIVE,
    "INACTIVE": ProjectStatus.COMPLETED,
    "LEADS": ProjectStatus.PROPOSED,
}

# ALTA's own generated outputs live under this folder.  The Drive scanner must
# NEVER ingest them as source documents, or it creates a loop (a generated
# project-log CSV gets pulled back in as a new raw document).  See
# docs/PROJECT_LOG_INGESTION.md ("Generated Outputs").
_GENERATED_REPORTS_FOLDER = "alta generated reports"

# Keyword (in the normalized top-level folder name) -> document category.
_CATEGORY_KEYWORDS: list[tuple[str, str]] = [
    ("projects", "projects"),
    ("company", "company"),
    ("real estate", "real_estate"),
    ("construction", "construction"),
    ("intelligence", "intelligence"),
]


def _path_parts(folder_path: str | None) -> list[str]:
    """Split a folder breadcrumb into its non-empty segments."""
    return [p for p in (folder_path or "").split("/") if p]


def _project_bucket_for_path(folder_path: str | None) -> str | None:
    """Return the bucket name if ``folder_path`` IS a project folder, else None.

    A project folder sits exactly at  <projects-area>/<bucket>/<project>:
    three segments, the first containing "projects", the second one of
    ACTIVE / INACTIVE / LEADS.  Numeric folder prefixes ("01. ") are
    tolerated -- the first segment is matched on normalized text.
    """
    parts = _path_parts(folder_path)
    if len(parts) != 3:
        return None
    if "projects" not in normalize_name(parts[0]):
        return None
    bucket = parts[1].strip().upper()
    return bucket if bucket in _PROJECT_BUCKETS else None


def _category_for_path(folder_path: str | None) -> str | None:
    """Classify a document by its top-level Drive area.

    "01. PROJECTS/ACTIVE/923 Rockland/Contracts" -> "projects"
    "00. COMPANY/2. DOCUMENTS"                   -> "company"
    "02. REAL ESTATE/4. UNDERWRITING"            -> "real_estate"
    """
    parts = _path_parts(folder_path)
    if not parts:
        return None
    top = normalize_name(parts[0])
    for keyword, category in _CATEGORY_KEYWORDS:
        if keyword in top:
            return category
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

        self.root_folder: str = self.config.get("root_folder") or __import__("os").environ.get(
            "GDRIVE_ROOT_FOLDER", "root"
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
        except Exception as exc:
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
                doc.name,
                doc.storage_ref,
                doc.folder_path,
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

        A folder is a project folder iff its path is exactly
        ``01. PROJECTS/<bucket>/<name>`` (see ``_project_bucket_for_path``).
        Entering one creates/resolves its canonical Project; every file
        beneath it inherits that project_id by ancestry.  Folders elsewhere
        simply inherit their parent's project_id (None outside the projects
        tree) -- documents there are classified by ``category`` instead.
        """
        if depth > self._MAX_DEPTH:
            logger.warning("[GDRIVE] Max depth %d exceeded at %s", self._MAX_DEPTH, folder_path)
            return

        # Record visit BEFORE listing so reconcile knows we were here even if
        # the listing itself fails downstream.
        self._visited_folder_ids.add(folder_id)

        try:
            items = self.client.list_folder(folder_id)
        except Exception as exc:
            self._record_failure(f"list_folder({folder_id}, path={folder_path!r}): {exc}")
            return

        logger.debug("[GDRIVE] walk depth=%d path=%r -> %d items", depth, folder_path, len(items))

        for item in items:
            if item.get("mimeType") == _FOLDER_MIME:
                # Never descend into ALTA's own generated-output tree -- that
                # would re-ingest exported reports as source documents.
                if (item.get("name") or "").strip().lower() == _GENERATED_REPORTS_FOLDER:
                    logger.info("[GDRIVE] Skipping generated-reports folder under %r", folder_path)
                    continue
                child_path = f"{folder_path}/{item['name']}" if folder_path else item["name"]
                # A folder at  01. PROJECTS/<bucket>/<name>  IS a project --
                # create/resolve its canonical Project.  Any other folder
                # just inherits whatever project its parent resolved (None
                # outside the projects tree).
                bucket = _project_bucket_for_path(child_path)
                if bucket is not None:
                    child_project_id = self._resolve_project_folder(
                        item["id"],
                        item["name"],
                        bucket,
                    )
                else:
                    child_project_id = project_id
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
                parent_id = (file_data.get("parents") or [None])[0]
                # The delta path lacks the full tree, so it cannot resolve
                # folder ancestry.  project_id / folder_path / category are
                # passed as None -- and None never clobbers an existing
                # value (see _upsert_document) -- so a delta sync refreshes
                # file metadata while the next full sync / `rebuild` repairs
                # linkage.
                self._upsert_document(
                    file_data,
                    project_id=None,
                    folder_path=None,
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
        # Category is derived from the top-level Drive area.  Set only when
        # known (the full-sync path supplies folder_path); None is omitted so
        # a delta sync never wipes a category set by an earlier full sync.
        category = _category_for_path(folder_path)
        if category is not None:
            attrs["category"] = category

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
        except Exception as exc:
            self._record_failure(f"Document {file_id} ({name}): {exc}")
            return

        if self.extract_content and result.entity is not None:
            try:
                extract_and_store(
                    session=self.session,
                    client=self.client,
                    document=result.entity,
                )
            except Exception as exc:
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
        doc = self.session.query(Document).filter_by(canonical_id=ext.canonical_id).one_or_none()
        if doc is not None:
            doc.url = f"[removed] {doc.url}"
            self.session.flush()
            logger.info("[GDRIVE] Marked Document %s as removed", file_id)

    # ------------------------------------------------------------------
    # Project discovery -- a Drive project folder IS a canonical Project
    # ------------------------------------------------------------------

    def _resolve_project_folder(
        self,
        folder_id: str,
        folder_name: str,
        bucket: str,
    ) -> Any:
        """Return the canonical project_id for a Drive project folder.

        Each project folder maps to exactly ONE canonical Project, keyed by
        ``folder:<folder_id>``.  There is NO fuzzy matching between folders:
        two sibling folders are two distinct projects, full stop -- this is
        what makes linkage deterministic and is why "927 Rockland" can never
        again be confused with "923 Rockland".

        Idempotent: the folder's ExternalId is checked first, so a project's
        name / status are written once at creation and never churned on a
        later re-sync (Monday owns operational status from then on).
        """
        if folder_id in self._folder_project_cache:
            return self._folder_project_cache[folder_id]

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

        # New project folder -> create a canonical Project.  No matcher is
        # passed (resolver default = NoMatcher): folders never merge.
        result = self.resolver.resolve_or_create(
            source=self.source,
            external_key=f"folder:{folder_id}",
            external_url=f"https://drive.google.com/drive/folders/{folder_id}",
            entity_class=Project,
            attrs={
                "name": folder_name,
                "status": _PROJECT_BUCKETS[bucket],
                "client_id": self._unknown_client_id(),
            },
        )
        self._record_result(result.was_created, result.was_matched)
        self._folder_project_cache[folder_id] = result.entity.canonical_id
        logger.info(
            "[GDRIVE] project folder %r -> Project %s (%s)",
            folder_name,
            result.entity.canonical_id,
            bucket,
        )
        return result.entity.canonical_id

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
