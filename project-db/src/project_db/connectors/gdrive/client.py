"""Google Drive REST v3 API client.

Two auth modes are supported, auto-detected from the credential file type:

1. OAuth Desktop App (personal Gmail / no Workspace domain)
   - GDRIVE_SA_KEY_PATH points to the OAuth client_secret JSON you downloaded
     from Google Cloud Console (contains "installed": {...}).
   - Run `project_db gdrive-auth` ONCE to open the browser consent screen.
   - A token is saved to GDRIVE_TOKEN_PATH (default: secrets/gdrive_token.json).
   - Subsequent syncs refresh the token silently from the saved file.

2. Service Account with Domain-Wide Delegation (Google Workspace orgs only)
   - GDRIVE_SA_KEY_PATH points to a service account JSON (contains
     "type": "service_account" and a private key).
   - Set GDRIVE_IMPERSONATE to a Workspace user email to impersonate.
   - No browser flow needed -- pure headless auth.

Scope: drive.readonly  --  read metadata + content; no writes.

Delta sync: call get_start_page_token() once, persist the token, then call
list_changes(token) on subsequent runs.

Env vars:
  GDRIVE_SA_KEY_PATH  -- path to credential JSON (client secret OR service account)
  GDRIVE_TOKEN_PATH   -- where to save OAuth tokens (default: secrets/gdrive_token.json)
  GDRIVE_IMPERSONATE  -- only used for service-account mode (Workspace domains only)
  GDRIVE_ROOT_FOLDER  -- Drive folder ID to crawl (defaults to 'root')
"""
from __future__ import annotations

import json
import logging
import os
from typing import Any

logger = logging.getLogger(__name__)

SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]

# Files larger than this skip content fetch (metadata-only).
MAX_CONTENT_BYTES = 25 * 1024 * 1024  # 25 MB

# mimeTypes we will fetch content for (everything else: metadata only).
FETCHABLE_MIME_TYPES = {
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/vnd.google-apps.document",
    "application/vnd.google-apps.spreadsheet",
}

# Fields requested on every files.list / changes.list call.
# Kept narrow to reduce payload and quota units.
_FILE_FIELDS = (
    "id,name,mimeType,modifiedTime,size,md5Checksum,"
    "parents,driveId,webViewLink,trashed"
)
_LIST_FIELDS = f"nextPageToken,files({_FILE_FIELDS})"
_CHANGE_FILE_FIELDS = f"nextPageToken,newStartPageToken,changes(removed,fileId,file({_FILE_FIELDS}))"


class GDriveClient:
    """Thin wrapper around Google Drive REST v3.

    Pass ``service`` to inject a pre-built googleapiclient discovery service
    (useful for tests).  If ``service`` is omitted, the client builds one from
    GDRIVE_SA_KEY_PATH and GDRIVE_IMPERSONATE.
    """

    def __init__(
        self,
        *,
        sa_key_path: str | None = None,
        impersonate: str | None = None,
        service: Any = None,  # googleapiclient resource (injected in tests)
    ) -> None:
        self._svc = service or self._build_service(sa_key_path, impersonate)

    # ------------------------------------------------------------------
    # Auth
    # ------------------------------------------------------------------

    @staticmethod
    def _build_service(
        sa_key_path: str | None,
        impersonate: str | None,
    ) -> Any:
        """Build and return a googleapiclient Drive v3 resource.

        Auto-detects credential type from the JSON file:
          - {"type": "service_account", ...}  -> service account flow
          - {"installed": {...}}               -> OAuth Desktop app flow
        """
        try:
            from googleapiclient.discovery import build
        except ImportError as exc:
            raise RuntimeError(
                "google-api-python-client and google-auth are required for the "
                "Google Drive connector.  Run: pip install google-api-python-client google-auth google-auth-oauthlib"
            ) from exc

        key_path = sa_key_path or os.environ.get("GDRIVE_SA_KEY_PATH")
        if not key_path:
            raise RuntimeError(
                "GDRIVE_SA_KEY_PATH is not set.  "
                "Point it at your credential JSON (OAuth client secret or service account)."
            )

        # Detect which credential type we have.
        with open(key_path) as fh:
            cred_data = json.load(fh)

        if cred_data.get("type") == "service_account":
            creds = GDriveClient._service_account_creds(key_path, impersonate)
        elif "installed" in cred_data or "web" in cred_data:
            creds = GDriveClient._oauth_user_creds(key_path)
        else:
            raise RuntimeError(
                f"Unrecognized credential format in {key_path}.  "
                "Expected a service-account JSON or an OAuth client-secret JSON."
            )

        return build("drive", "v3", credentials=creds, cache_discovery=False)

    @staticmethod
    def _service_account_creds(key_path: str, impersonate: str | None) -> Any:
        """Build service-account credentials (Google Workspace domains only)."""
        from google.oauth2 import service_account

        creds = service_account.Credentials.from_service_account_file(
            key_path, scopes=SCOPES
        )
        subject = impersonate or os.environ.get("GDRIVE_IMPERSONATE")
        if subject:
            creds = creds.with_subject(subject)
        else:
            logger.warning(
                "GDRIVE_IMPERSONATE not set -- shared-drive items may be invisible. "
                "Set it to a Workspace user who is a member of every project drive."
            )
        return creds

    @staticmethod
    def _oauth_user_creds(client_secret_path: str) -> Any:
        """Load saved OAuth user credentials, refreshing if expired.

        Raises RuntimeError if no token file exists yet -- caller should run
        `project_db gdrive-auth` to complete the one-time browser consent.
        """
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials

        token_path = os.environ.get("GDRIVE_TOKEN_PATH") or os.path.join(
            os.path.dirname(os.path.abspath(client_secret_path)), "gdrive_token.json"
        )

        creds = None
        if os.path.exists(token_path):
            creds = Credentials.from_authorized_user_file(token_path, SCOPES)

        if creds and creds.valid:
            return creds

        if creds and creds.expired and creds.refresh_token:
            logger.info("[GDRIVE] Refreshing expired OAuth token...")
            creds.refresh(Request())
            # Persist the refreshed token.
            with open(token_path, "w") as fh:
                fh.write(creds.to_json())
            return creds

        raise RuntimeError(
            f"No valid Google Drive token found at:\n  {token_path}\n\n"
            "Run this once to authenticate:\n"
            "  project_db gdrive-auth\n\n"
            "A browser window will open asking you to sign in with your Google account."
        )

    # ------------------------------------------------------------------
    # Folder listing
    # ------------------------------------------------------------------

    def list_folder(self, folder_id: str = "root") -> list[dict[str, Any]]:
        """Return all non-trashed items directly inside *folder_id*.

        Does NOT recurse -- call list_folder() on subfolders yourself if you
        need a full tree walk.  Handles pagination automatically.

        Always passes supportsAllDrives + includeItemsFromAllDrives so shared-
        drive items are not silently excluded.
        """
        out: list[dict] = []
        token: str | None = None

        while True:
            resp = (
                self._svc.files()
                .list(
                    q=f"'{folder_id}' in parents and trashed=false",
                    fields=_LIST_FIELDS,
                    pageSize=1000,
                    pageToken=token,
                    supportsAllDrives=True,
                    includeItemsFromAllDrives=True,
                    corpora="allDrives",
                )
                .execute()
            )
            out.extend(resp.get("files", []))
            token = resp.get("nextPageToken")
            if not token:
                break

        logger.debug("list_folder(%s) -> %d items", folder_id, len(out))
        return out

    def list_folder_recursive(
        self, root_id: str = "root", max_depth: int = 5
    ) -> list[dict[str, Any]]:
        """Depth-first recursive folder walk.

        Stops at *max_depth* to avoid runaway traversal on deeply nested
        drives.  Returns all files (not folders) encountered.
        """
        files: list[dict] = []
        self._walk(root_id, files, depth=0, max_depth=max_depth)
        return files

    def _walk(
        self,
        folder_id: str,
        accumulator: list[dict],
        depth: int,
        max_depth: int,
    ) -> None:
        if depth > max_depth:
            return
        items = self.list_folder(folder_id)
        for item in items:
            if item.get("mimeType") == "application/vnd.google-apps.folder":
                self._walk(item["id"], accumulator, depth + 1, max_depth)
            else:
                accumulator.append(item)

    # ------------------------------------------------------------------
    # Delta sync  (changes.list)
    # ------------------------------------------------------------------

    def get_start_page_token(self) -> str:
        """Get the current changes page token.

        Call this ONCE before the first sync and persist the returned string.
        On subsequent syncs pass it to list_changes() to get only what changed.
        """
        resp = (
            self._svc.changes()
            .getStartPageToken(
                supportsAllDrives=True,
                includeItemsFromAllDrives=True,
            )
            .execute()
        )
        return resp["startPageToken"]

    def list_changes(self, page_token: str) -> tuple[list[dict[str, Any]], str]:
        """Return (changed_items, new_page_token) since *page_token*.

        Each change dict has shape::

            {
              "removed": bool,          # True if file was deleted/trashed
              "fileId": "abc123",
              "file": { ...file fields... }  # absent when removed=True
            }

        Persist *new_page_token* as the cursor for the next call.
        """
        changes: list[dict] = []
        token = page_token

        while True:
            resp = (
                self._svc.changes()
                .list(
                    pageToken=token,
                    fields=_CHANGE_FILE_FIELDS,
                    supportsAllDrives=True,
                    includeItemsFromAllDrives=True,
                    includeRemoved=True,
                    pageSize=1000,
                )
                .execute()
            )
            changes.extend(resp.get("changes", []))
            token = resp.get("nextPageToken") or resp.get("newStartPageToken", page_token)
            if not resp.get("nextPageToken"):
                break

        new_cursor = resp.get("newStartPageToken", page_token)
        logger.debug("list_changes -> %d changes, new_cursor=%s", len(changes), new_cursor)
        return changes, new_cursor

    # ------------------------------------------------------------------
    # File metadata / content
    # ------------------------------------------------------------------

    def get_file_metadata(self, file_id: str) -> dict[str, Any]:
        """Fetch metadata for a single file."""
        return (
            self._svc.files()
            .get(
                fileId=file_id,
                fields=_FILE_FIELDS,
                supportsAllDrives=True,
            )
            .execute()
        )

    def export_google_doc(self, file_id: str, mime_type: str = "text/plain") -> bytes:
        """Export a Google-native doc (Docs, Sheets) to *mime_type*.

        The API hard-limits exports to 10 MB.  Use text/plain for LLM ingestion
        (much smaller than PDF for large documents).
        """
        return (
            self._svc.files()
            .export(fileId=file_id, mimeType=mime_type)
            .execute()
        )

    def download_file(self, file_id: str) -> bytes:
        """Download binary file content (PDF, DOCX, etc.).

        Caller should check file size before calling -- files over MAX_CONTENT_BYTES
        should be skipped (metadata-only).
        """
        import io
        from googleapiclient.http import MediaIoBaseDownload

        request = self._svc.files().get_media(fileId=file_id, supportsAllDrives=True)
        buffer = io.BytesIO()
        downloader = MediaIoBaseDownload(buffer, request)
        done = False
        while not done:
            _, done = downloader.next_chunk()
        return buffer.getvalue()
