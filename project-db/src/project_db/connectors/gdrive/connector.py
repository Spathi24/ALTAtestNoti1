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

import logging
import re
import unicodedata
from typing import Any

from sqlalchemy.orm import Session

from project_db.connectors.base import BaseConnector, SyncReport
from project_db.connectors.gdrive.client import GDriveClient
from project_db.db.models import ExternalId, Project, SourceSystem
from project_db.db.models.docs import Document
from project_db.identity.matcher import ExactFieldMatcher

logger = logging.getLogger(__name__)

# ExternalId key used to persist the Drive changes cursor.
_CURSOR_KEY = "gdrive_changes_page_token"

# Folder mime type in Drive.
_FOLDER_MIME = "application/vnd.google-apps.folder"


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


def _match_project_by_name(
    session: Session,
    organization_id: Any,
    folder_name: str,
) -> Any | None:
    """Try to link a Drive folder to a canonical Project by name.

    Returns project.canonical_id or None.
    """
    needle = _normalize_name(folder_name)
    if not needle:
        return None

    for project in session.query(Project).all():
        haystack = _normalize_name(project.name or "")
        if haystack and (needle == haystack or needle in haystack or haystack in needle):
            logger.debug(
                "Folder '%s' matched Project '%s' (id=%s)",
                folder_name,
                project.name,
                project.canonical_id,
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

        # Cache: folder_id -> project_id (None = unrecognized)
        self._folder_project_cache: dict[str, Any | None] = {}

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

    def _full_sync(self) -> None:
        """Walk root folder one level deep (subfolders = projects), then files."""
        root_items = self.client.list_folder(self.root_folder)
        folders = [i for i in root_items if i.get("mimeType") == _FOLDER_MIME]
        files_at_root = [i for i in root_items if i.get("mimeType") != _FOLDER_MIME]

        # Files directly in root -- no project context
        for file in files_at_root:
            self._upsert_document(file, project_id=None, folder_name=None)

        # Walk each project subfolder
        for folder in folders:
            project_id = self._resolve_folder_to_project(folder["id"], folder["name"])
            sub_items = self.client.list_folder(folder["id"])
            for file in sub_items:
                if file.get("mimeType") == _FOLDER_MIME:
                    # Nested subfolder: recurse one more level (contracts, drawings, etc.)
                    nested = self.client.list_folder(file["id"])
                    for nf in nested:
                        if nf.get("mimeType") != _FOLDER_MIME:
                            self._upsert_document(nf, project_id=project_id, folder_name=folder["name"])
                else:
                    self._upsert_document(file, project_id=project_id, folder_name=folder["name"])

        # Save a fresh cursor so next run uses delta sync.
        try:
            new_cursor = self.client.get_start_page_token()
            self._save_cursor(new_cursor)
            logger.info("[GDRIVE] Saved new cursor for delta sync: %s", new_cursor)
        except Exception as exc:  # noqa: BLE001
            logger.warning("[GDRIVE] Could not save delta-sync cursor: %s", exc)

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
                self._upsert_document(file_data, project_id=project_id, folder_name=None)

        self._save_cursor(new_cursor)

    # ------------------------------------------------------------------
    # Document upsert
    # ------------------------------------------------------------------

    def _upsert_document(
        self,
        file: dict[str, Any],
        *,
        project_id: Any | None,
        folder_name: str | None,
    ) -> None:
        """Map a Drive file dict to a canonical Document row."""
        file_id = file.get("id", "")
        name = file.get("name", "Unnamed")
        mime_type = file.get("mimeType", "")
        url = file.get("webViewLink", f"https://drive.google.com/file/d/{file_id}")

        attrs: dict[str, Any] = {
            "name": name,
            "mime_type": mime_type,
            "url": url,
            "storage_ref": file_id,
        }
        if project_id is not None:
            attrs["project_id"] = project_id

        external_url = url

        try:
            result = self.resolver.resolve_or_create(
                source=self.source,
                external_key=file_id,
                external_url=external_url,
                entity_class=Document,
                attrs=attrs,
                matcher=ExactFieldMatcher(["storage_ref"]),
            )
            self._record_result(result.was_created, result.was_matched)
        except Exception as exc:  # noqa: BLE001
            self._record_failure(f"Document {file_id} ({name}): {exc}")

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
