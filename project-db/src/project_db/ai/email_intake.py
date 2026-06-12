"""Gmail API email intake for field notes (Win 2).

Architecture contract:
  - N7: outbound-only poller; nothing listens on the public internet.
  - A1: email content is untrusted; produces Proposals only, never direct writes.
  - Unknown HUMAN senders: auto-create an unverified Worker stub, then process
    normally.  The PM reviews recurring senders via the roster and assigns
    role/tags (PM / tradesman / crew).
  - System / noreply senders: quarantined immediately, no processing.
  - Message-ID dedup: gmail_message_id is the unique key; repeated runs are idempotent.
  - Plus-addressing routing: fieldnotes+rockland@company.com -> fuzzy-match project names.
    Fallback: GMAIL_DEFAULT_PROJECT_ID env var (name fragment or UUID).
  - Attachments are stored raw (path list in attachment_refs_json) for Win 3 (photos).

Auth:
  - GDRIVE_SA_KEY_PATH           -- OAuth client_secret JSON (same file as Drive auth).
  - GMAIL_TOKEN_PATH             -- Gmail OAuth token file (default: secrets/gmail_token.json).
  - GMAIL_MAILBOX_ADDRESS        -- address to filter messages to (optional).
  - GMAIL_DEFAULT_PROJECT_ID     -- fallback project (name fragment or UUID) when no
                                    plus-address tag and no worker default_project_id.
  - Run `project_db gmail-auth` once for the one-time browser consent.

Gmail labels applied server-side:
  - ALTA/Processed   -- ingest ran; Proposals created or note too vague.
  - ALTA/Quarantine  -- system/noreply sender; not processed.
  - ALTA/Failed      -- extraction or DB error.
"""
from __future__ import annotations

import base64
import email as _stdlib_email
import json
import logging
import os
import re
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from project_db.ai.field_note_extraction import (
    FieldNoteBatch,
    ingest_field_note,
)
from project_db.db.models import EmailIngest, NoteChannel, Project, Worker

logger = logging.getLogger(__name__)

GMAIL_SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.modify",
]

# Gmail label names ALTA creates / manages.
_LABEL_PROCESSED = "ALTA/Processed"
_LABEL_QUARANTINE = "ALTA/Quarantine"
_LABEL_FAILED = "ALTA/Failed"

# How many messages to retrieve per poll (max 500 per Gmail API page).
_BATCH_SIZE = 100

# Senders that are definitively non-human (Google welcome emails, bounce
# notifications, automated alerts).  These are quarantined without processing.
_SYSTEM_SENDER_RE = re.compile(
    r"^(no[-_.]?reply|noreply|mailer-daemon|postmaster|do-not-reply|donotreply"
    r"|bounce|alert|notification|automated)@",
    re.IGNORECASE,
)


# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------


@dataclass
class EmailPollBatch:
    """Summary of one poll-mailbox run."""

    total_seen: int = 0
    processed: int = 0
    quarantined: int = 0
    duplicate: int = 0
    failed: int = 0
    field_note_batches: list[FieldNoteBatch] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return self.failed == 0


# ---------------------------------------------------------------------------
# Poller ABC
# ---------------------------------------------------------------------------


class BaseGmailPoller(ABC):
    """Interface for Gmail message polling.

    Concrete implementations: GmailPoller (real API) and MockGmailPoller (tests).
    """

    @abstractmethod
    def list_unprocessed(self) -> list[dict[str, Any]]:
        """Return a list of raw Gmail message metadata dicts (id, threadId).

        Implementations should filter by -label:ALTA/Processed so already-
        handled messages don't re-appear.  The list order is newest-first
        (Gmail default).
        """

    @abstractmethod
    def get_message(self, message_id: str) -> dict[str, Any]:
        """Fetch full message payload for *message_id*."""

    @abstractmethod
    def apply_label(self, message_id: str, label: str, *, add: bool = True) -> None:
        """Add or remove *label* on a Gmail message.  No-ops if already applied."""

    @abstractmethod
    def ensure_labels(self) -> None:
        """Create the ALTA/* labels if they don't exist yet (idempotent)."""


# ---------------------------------------------------------------------------
# Real Gmail API poller
# ---------------------------------------------------------------------------


class GmailPoller(BaseGmailPoller):
    """Gmail REST API v1 poller using the same OAuth flow as GDriveClient.

    Parameters
    ----------
    mailbox_address
        The address of the mailbox to poll (e.g. ``fieldnotes@company.com``).
        Only messages TO this address are processed.
    client_secret_path
        Path to the OAuth client_secret JSON.  Defaults to GDRIVE_SA_KEY_PATH.
    token_path
        Path to the saved Gmail OAuth token.  Defaults to GMAIL_TOKEN_PATH or
        ``secrets/gmail_token.json`` next to the client_secret file.
    service
        Inject a pre-built googleapiclient resource for testing.
    """

    def __init__(
        self,
        mailbox_address: str | None = None,
        *,
        client_secret_path: str | None = None,
        token_path: str | None = None,
        service: Any = None,
    ) -> None:
        self._mailbox = mailbox_address or os.environ.get("GMAIL_MAILBOX_ADDRESS", "")
        self._svc = service or self._build_service(client_secret_path, token_path)
        self._label_cache: dict[str, str] = {}  # name -> id

    # ------------------------------------------------------------------
    # Auth
    # ------------------------------------------------------------------

    @staticmethod
    def _build_service(
        client_secret_path: str | None,
        token_path: str | None,
    ) -> Any:
        try:
            from googleapiclient.discovery import build
        except ImportError as exc:
            raise RuntimeError(
                "google-api-python-client and google-auth are required.\n"
                "Run: pip install google-api-python-client google-auth google-auth-oauthlib"
            ) from exc

        key_path = client_secret_path or os.environ.get("GDRIVE_SA_KEY_PATH")
        if not key_path:
            raise RuntimeError(
                "GDRIVE_SA_KEY_PATH is not set.  "
                "Point it at your OAuth client_secret JSON and run `project_db gmail-auth`."
            )

        resolved_token = token_path or os.environ.get("GMAIL_TOKEN_PATH") or os.path.join(
            os.path.dirname(os.path.abspath(key_path)), "gmail_token.json"
        )
        creds = GmailPoller._load_or_refresh(key_path, resolved_token)
        return build("gmail", "v1", credentials=creds, cache_discovery=False)

    @staticmethod
    def _load_or_refresh(client_secret_path: str, token_path: str) -> Any:
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials

        creds = None
        if os.path.exists(token_path):
            creds = Credentials.from_authorized_user_file(token_path, GMAIL_SCOPES)

        if creds and creds.valid:
            return creds

        if creds and creds.expired and creds.refresh_token:
            logger.info("[GMAIL] Refreshing expired OAuth token...")
            creds.refresh(Request())
            with open(token_path, "w") as fh:
                fh.write(creds.to_json())
            return creds

        raise RuntimeError(
            f"No valid Gmail token at:\n  {token_path}\n\n"
            "Run once to authenticate:\n"
            "  project_db gmail-auth\n\n"
            "A browser window will open for Gmail consent."
        )

    # ------------------------------------------------------------------
    # Label management
    # ------------------------------------------------------------------

    def ensure_labels(self) -> None:
        """Create ALTA/* labels if missing.  Caches label IDs."""
        result = self._svc.users().labels().list(userId="me").execute()
        existing = {lb["name"]: lb["id"] for lb in result.get("labels", [])}
        for name in (_LABEL_PROCESSED, _LABEL_QUARANTINE, _LABEL_FAILED):
            if name in existing:
                self._label_cache[name] = existing[name]
            else:
                body = {"name": name, "labelListVisibility": "labelShow",
                        "messageListVisibility": "show"}
                created = self._svc.users().labels().create(userId="me", body=body).execute()
                self._label_cache[name] = created["id"]
                logger.info("[GMAIL] Created label: %s", name)

    def _label_id(self, name: str) -> str:
        if name not in self._label_cache:
            self.ensure_labels()
        return self._label_cache[name]

    def apply_label(self, message_id: str, label: str, *, add: bool = True) -> None:
        body: dict[str, Any] = {"addLabelIds": [], "removeLabelIds": []}
        lid = self._label_id(label)
        if add:
            body["addLabelIds"] = [lid]
        else:
            body["removeLabelIds"] = [lid]
        self._svc.users().messages().modify(
            userId="me", id=message_id, body=body
        ).execute()

    # ------------------------------------------------------------------
    # Listing + fetch
    # ------------------------------------------------------------------

    def list_unprocessed(self) -> list[dict[str, Any]]:
        """List messages not yet labeled ALTA/Processed.

        Uses server-side label filter as a fast pre-filter; EmailIngest.gmail_message_id
        is the authoritative local dedup guard.
        """
        query = "-label:ALTA/Processed"
        if self._mailbox:
            query += f" to:{self._mailbox}"

        results: list[dict[str, Any]] = []
        page_token: str | None = None
        while True:
            kwargs: dict[str, Any] = {
                "userId": "me",
                "q": query,
                "maxResults": _BATCH_SIZE,
            }
            if page_token:
                kwargs["pageToken"] = page_token
            resp = self._svc.users().messages().list(**kwargs).execute()
            results.extend(resp.get("messages", []))
            page_token = resp.get("nextPageToken")
            if not page_token:
                break
        return results

    def get_message(self, message_id: str) -> dict[str, Any]:
        return self._svc.users().messages().get(
            userId="me", id=message_id, format="full"
        ).execute()


# ---------------------------------------------------------------------------
# Mock poller (for tests -- no real API calls)
# ---------------------------------------------------------------------------


class MockGmailPoller(BaseGmailPoller):
    """In-memory test double.

    Populate ``messages`` with dicts shaped like Gmail API full-message objects.
    ``applied_labels`` collects (message_id, label, add) tuples for assertions.
    ``labels_ensured`` is set to True when ensure_labels() is called.
    """

    def __init__(self, messages: list[dict[str, Any]] | None = None) -> None:
        self.messages: dict[str, dict[str, Any]] = {
            m["id"]: m for m in (messages or [])
        }
        self.applied_labels: list[tuple[str, str, bool]] = []
        self.labels_ensured: bool = False

    def list_unprocessed(self) -> list[dict[str, Any]]:
        return [{"id": mid, "threadId": m.get("threadId", "t1")}
                for mid, m in self.messages.items()]

    def get_message(self, message_id: str) -> dict[str, Any]:
        return self.messages[message_id]

    def apply_label(self, message_id: str, label: str, *, add: bool = True) -> None:
        self.applied_labels.append((message_id, label, add))

    def ensure_labels(self) -> None:
        self.labels_ensured = True


# ---------------------------------------------------------------------------
# Message parsing helpers
# ---------------------------------------------------------------------------


def _parse_headers(headers: list[dict[str, str]]) -> dict[str, str]:
    return {h["name"].lower(): h["value"] for h in headers}


def _extract_body_text(payload: dict[str, Any]) -> str:
    """Walk the MIME tree and return the first plaintext body part."""
    mime = payload.get("mimeType", "")
    if mime == "text/plain":
        data = payload.get("body", {}).get("data", "")
        if data:
            return base64.urlsafe_b64decode(data + "==").decode("utf-8", errors="replace")

    for part in payload.get("parts", []):
        text = _extract_body_text(part)
        if text:
            return text
    return ""


def _parse_plus_tag(to_address: str) -> str | None:
    """Extract the plus-tag from `fieldnotes+rockland@company.com`.

    Returns the tag string (e.g. ``"rockland"``), or None if no tag.
    """
    match = re.search(r"\+([^@+]+)@", to_address)
    if match:
        return match.group(1).lower()
    return None


def _fuzzy_match_project(session: Session, tag: str) -> str | None:
    """Return canonical_id of the first Project whose name contains *tag*.

    Simple substring match (case-insensitive).  Sufficient for the pilot
    (923 Rockland is the only project).  Extend with difflib if quality drops.
    """
    tag_lower = tag.lower()
    projects = session.query(Project).filter(Project.name.isnot(None)).all()
    for proj in projects:
        if tag_lower in (proj.name or "").lower():
            return str(proj.canonical_id)
    return None


def _find_worker(session: Session, sender_email: str) -> Worker | None:
    """Look up a Worker by primary email or phone_gateway_email."""
    email_lower = sender_email.lower().strip()
    worker = (
        session.query(Worker)
        .filter(Worker.active.is_(True))
        .filter(Worker.email == email_lower)
        .one_or_none()
    )
    if worker:
        return worker
    return (
        session.query(Worker)
        .filter(Worker.active.is_(True))
        .filter(Worker.phone_gateway_email == email_lower)
        .one_or_none()
    )


def _is_system_sender(email: str) -> bool:
    """Return True for noreply/bounce/automated senders that should be quarantined."""
    return bool(_SYSTEM_SENDER_RE.match(email.strip()))


def _auto_create_worker_stub(session: Session, sender_email: str) -> "Worker":
    """Create an unverified Worker stub for a first-time human sender.

    The PM reviews recurring senders in the Worker roster and fills in
    display_name, role, and tags at their leisure.  Processing is NOT blocked
    on verification -- all output still goes through Proposals (A1).
    """
    w = Worker(
        display_name=sender_email,   # placeholder; PM can rename later
        email=sender_email.lower().strip(),
        verified=False,
        active=True,
    )
    session.add(w)
    session.flush()
    logger.info("[GMAIL] Auto-created unverified Worker stub for: %s", sender_email)
    return w


def _resolve_project_id(
    session: Session,
    *,
    to_address: str,
    worker: "Worker | None",
) -> str | None:
    """Determine project_id: plus-tag first, then worker default, then env fallback.

    GMAIL_DEFAULT_PROJECT_ID (env) can be a canonical UUID or a project name
    fragment.  Set it when most emails arrive without plus-addressing.
    """
    tag = _parse_plus_tag(to_address)
    if tag:
        project_id = _fuzzy_match_project(session, tag)
        if project_id:
            return project_id
    if worker and worker.default_project_id:
        return str(worker.default_project_id)
    # Last resort: system-wide default from environment.
    default_ref = os.environ.get("GMAIL_DEFAULT_PROJECT_ID", "").strip()
    if default_ref:
        try:
            uid = uuid.UUID(default_ref)
            proj = session.query(Project).filter_by(canonical_id=uid).one_or_none()
            if proj:
                return str(proj.canonical_id)
        except ValueError:
            pass
        # Treat as name fragment.
        return _fuzzy_match_project(session, default_ref)
    return None


def _store_attachment(
    msg_payload: dict[str, Any],
    ingest_id: str,
    attachment_dir: str,
) -> list[str]:
    """Save raw attachment bytes to disk; return list of saved paths.

    Only stores if the part has a filename (skips inline body parts).
    Directory is created on first use.
    """
    saved: list[str] = []
    for part in msg_payload.get("parts", []):
        filename = part.get("filename", "")
        if not filename:
            continue
        data = part.get("body", {}).get("data", "")
        if not data:
            continue
        os.makedirs(attachment_dir, exist_ok=True)
        safe_name = re.sub(r"[^\w.\-]", "_", filename)
        path = os.path.join(attachment_dir, f"{ingest_id}_{safe_name}")
        with open(path, "wb") as fh:
            fh.write(base64.urlsafe_b64decode(data + "=="))
        saved.append(path)
        logger.debug("[GMAIL] Saved attachment %s", path)
    return saved


# ---------------------------------------------------------------------------
# Core service function (A5: same path for CLI + cron)
# ---------------------------------------------------------------------------


def poll_mailbox(
    session: Session,
    extractor: Any,  # BaseFieldNoteExtractor subclass
    poller: BaseGmailPoller,
    *,
    attachment_dir: str | None = None,
) -> EmailPollBatch:
    """Poll the Gmail mailbox and ingest any new field notes.

    Contract:
    - Unknown senders -> EmailIngest(status="quarantined"), label ALTA/Quarantine.
    - Duplicate message_id -> EmailIngest(status="duplicate"), no FieldNote.
    - Extraction error -> EmailIngest(status="failed"), label ALTA/Failed.
    - Happy path -> EmailIngest(status="processed"), FieldNote rows, ALTA/Processed.
    - All EmailIngest rows are committed BEFORE field_note_extraction runs so a
      crash mid-extraction doesn't re-process the same message.
    """
    batch = EmailPollBatch()
    attach_base = attachment_dir or os.environ.get(
        "GMAIL_ATTACHMENT_DIR",
        os.path.join(os.getcwd(), "gmail_attachments"),
    )

    poller.ensure_labels()
    unprocessed = poller.list_unprocessed()
    batch.total_seen = len(unprocessed)

    for msg_meta in unprocessed:
        gmail_id = msg_meta["id"]
        try:
            _process_one(
                session=session,
                extractor=extractor,
                poller=poller,
                gmail_id=gmail_id,
                batch=batch,
                attachment_dir=attach_base,
            )
        except Exception as exc:  # noqa: BLE001
            logger.exception("[GMAIL] Unexpected error processing %s", gmail_id)
            batch.failed += 1
            batch.errors.append(f"{gmail_id}: {exc}")
            _mark_ingest_failed(session, gmail_id, str(exc))
            try:
                poller.apply_label(gmail_id, _LABEL_FAILED)
            except Exception:
                pass

    return batch


def _process_one(
    *,
    session: Session,
    extractor: Any,
    poller: BaseGmailPoller,
    gmail_id: str,
    batch: EmailPollBatch,
    attachment_dir: str,
) -> None:
    """Process a single Gmail message.  All side-effects happen here."""
    # ----- Dedup check -----
    existing = (
        session.query(EmailIngest)
        .filter_by(gmail_message_id=gmail_id)
        .one_or_none()
    )
    if existing:
        batch.duplicate += 1
        # Apply ALTA/Processed so it stops appearing in list_unprocessed.
        try:
            poller.apply_label(gmail_id, _LABEL_PROCESSED)
        except Exception:
            pass
        return

    # ----- Fetch full message -----
    msg = poller.get_message(gmail_id)
    payload = msg.get("payload", {})
    headers = _parse_headers(payload.get("headers", []))

    sender_raw = headers.get("from", "")
    # Extract just the email from "Display Name <email@example.com>".
    sender_email_match = re.search(r"<([^>]+)>", sender_raw)
    sender_email = (sender_email_match.group(1) if sender_email_match else sender_raw).lower().strip()

    to_raw = headers.get("to", "")
    rfc_msg_id = headers.get("message-id")
    subject = headers.get("subject", "")

    # Parse internalDate (milliseconds epoch) -> aware UTC datetime.
    internal_ms = int(msg.get("internalDate", 0))
    received_at = datetime.fromtimestamp(internal_ms / 1000.0, tz=timezone.utc).replace(tzinfo=None)

    # ----- Worker lookup -----
    worker = _find_worker(session, sender_email)

    # ----- Create EmailIngest row (commits here so dedup is durable) -----
    ingest = EmailIngest(
        canonical_id=uuid.uuid4(),
        gmail_message_id=gmail_id,
        rfc_message_id=rfc_msg_id,
        thread_id=msg.get("threadId"),
        sender_email=sender_email,
        subject=subject,
        received_at=received_at,
        status="pending",
    )
    session.add(ingest)
    session.flush()  # persist so canonical_id is real; not yet committed

    if worker is None:
        if _is_system_sender(sender_email):
            # noreply / bounce / automated: quarantine without processing.
            ingest.status = "quarantined"
            ingest.failure_reason = "system/noreply sender"
            session.flush()
            session.commit()
            batch.quarantined += 1
            poller.apply_label(gmail_id, _LABEL_QUARANTINE)
            logger.info("[GMAIL] Quarantined system sender: %s", sender_email)
            return
        # Unknown human: auto-create an unverified Worker stub so the PM can
        # review and tag them later.  Content still goes through Proposals (A1).
        worker = _auto_create_worker_stub(session, sender_email)

    # ----- Project resolution -----
    project_id = _resolve_project_id(session, to_address=to_raw, worker=worker)
    ingest.project_id = _uuid_or_none(project_id)

    # ----- Attachments (Win 3 prep) -----
    attachment_paths = _store_attachment(payload, str(ingest.canonical_id), attachment_dir)
    if attachment_paths:
        ingest.attachment_refs_json = json.dumps(attachment_paths)

    # Commit the ingest row with known sender BEFORE extraction so crash is idempotent.
    session.flush()
    session.commit()

    # ----- Body extraction -----
    body_text = _extract_body_text(payload).strip()
    if not body_text:
        ingest.status = "failed"
        ingest.failure_reason = "empty body"
        ingest.processed_at = datetime.utcnow()
        session.flush()
        session.commit()
        batch.failed += 1
        poller.apply_label(gmail_id, _LABEL_FAILED)
        return

    # ----- Field note extraction (A1: Proposals only) -----
    if project_id is None:
        ingest.status = "failed"
        ingest.failure_reason = "no project resolved from plus-address or worker default"
        ingest.processed_at = datetime.utcnow()
        session.flush()
        session.commit()
        batch.failed += 1
        poller.apply_label(gmail_id, _LABEL_FAILED)
        return

    fn_batch = ingest_field_note(
        session,
        extractor,
        project_id,
        body_text,
        channel=NoteChannel.EMAIL,
        sender_ref=sender_email,
        email_ingest_id=str(ingest.canonical_id),
    )
    batch.field_note_batches.append(fn_batch)

    ingest.status = "processed"
    ingest.processed_at = datetime.utcnow()
    session.flush()
    session.commit()
    batch.processed += 1

    poller.apply_label(gmail_id, _LABEL_PROCESSED)
    logger.info(
        "[GMAIL] Processed msg %s from %s -> %d signals, %d proposals",
        gmail_id,
        sender_email,
        len(fn_batch.field_notes),
        len(fn_batch.proposals),
    )


def _mark_ingest_failed(session: Session, gmail_id: str, reason: str) -> None:
    """Best-effort: create or update an EmailIngest row as failed."""
    try:
        row = (
            session.query(EmailIngest)
            .filter_by(gmail_message_id=gmail_id)
            .one_or_none()
        )
        if row:
            row.status = "failed"
            row.failure_reason = reason
            row.processed_at = datetime.utcnow()
        else:
            row = EmailIngest(
                canonical_id=uuid.uuid4(),
                gmail_message_id=gmail_id,
                received_at=datetime.utcnow(),
                status="failed",
                failure_reason=reason,
            )
            session.add(row)
        session.flush()
        session.commit()
    except Exception:
        session.rollback()


def retry_quarantined(session: Session) -> int:
    """Delete quarantined EmailIngest rows so poll-mail reprocesses them.

    The underlying Gmail messages still exist (they have ALTA/Quarantine but
    NOT ALTA/Processed), so the next poll-mail run picks them up fresh.
    Returns the number of rows deleted.

    Use after upgrading to the auto-create-worker-stub behaviour so previously
    quarantined human-sender messages get a second chance.
    """
    rows = session.query(EmailIngest).filter_by(status="quarantined").all()
    count = len(rows)
    for row in rows:
        session.delete(row)
    session.commit()
    logger.info("[GMAIL] Cleared %d quarantined EmailIngest row(s) for retry", count)
    return count


def _uuid_or_none(val: str | None) -> Any:
    if val is None:
        return None
    try:
        return uuid.UUID(val)
    except ValueError:
        return None
