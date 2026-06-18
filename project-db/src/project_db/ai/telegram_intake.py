"""Telegram intake orchestration (sync, one-shot poll -- mirrors Gmail intake).

poll_telegram pulls new updates (getUpdates with an offset cursor derived from
stored events), and for each message:
  - /start <token>  -> bind this Telegram user to the invited Worker
  - /help | /status -> reply with guidance / today's logged hours
  - free text       -> LabourSourceEvent + LLM-extracted LabourClaims (only for
                       a bound worker) + consolidation, then a parsed-summary reply

No always-on server and no webhook: Telegram retains unacknowledged updates ~24h,
so polling at least daily (or on a short schedule) captures everything, with the
message's own send time. Unbound senders are quarantined, never silently
processed (A1 posture). The LLM extracts; deterministic code resolves + computes.
"""

from __future__ import annotations

import logging
import secrets
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from project_db.ai.labour_consolidation import consolidate_claims
from project_db.ai.telegram_labour_extraction import (
    TelegramLabourExtractor,
    ingest_telegram_labour_claims,
)
from project_db.connectors.telegram.client import BaseTelegramClient
from project_db.db.models import LabourSourceEvent, TelegramIdentity, Worker

logger = logging.getLogger(__name__)

_HELP = (
    "ALTA labour bot. Log your hours in plain language, e.g.:\n"
    "  worked Rockland 7-4, half hour lunch, basement framing\n"
    "A foreman can list several workers in one message.\n\n"
    "Commands: /start <token> to link your account, /status for today, /help."
)


# ---------------------------------------------------------------------------
# Invite (PM-side): pre-create a pending binding + deep link
# ---------------------------------------------------------------------------


def generate_invite(
    session: Session, client: BaseTelegramClient, worker_ref: str
) -> dict[str, Any]:
    """Create a pending TelegramIdentity for a Worker and return its deep link.

    ``worker_ref`` is a display-name (exact, case-insensitive) or canonical UUID.
    An unknown name creates an unverified Worker stub (low-friction onboarding).
    Commits.
    """
    worker = None
    try:
        wid = uuid.UUID(str(worker_ref))
        worker = session.query(Worker).filter_by(canonical_id=wid).one_or_none()
    except (ValueError, TypeError):
        worker = None
    if worker is None:
        needle = " ".join(worker_ref.strip().lower().split())
        for w in session.query(Worker).all():
            if " ".join((w.display_name or "").lower().split()) == needle:
                worker = w
                break
    if worker is None:
        worker = Worker(
            canonical_id=uuid.uuid4(), display_name=worker_ref.strip(), active=True, verified=False
        )
        session.add(worker)
        session.flush()

    token = secrets.token_urlsafe(8)
    identity = TelegramIdentity(
        canonical_id=uuid.uuid4(),
        worker_id=worker.canonical_id,
        invite_token=token,
        verified=False,
        first_seen_at=datetime.utcnow(),
    )
    session.add(identity)
    session.commit()

    me = client.get_me()
    link = f"https://t.me/{me.get('username')}?start={token}"
    return {
        "worker": worker.display_name,
        "worker_id": str(worker.canonical_id),
        "token": token,
        "deep_link": link,
    }


# ---------------------------------------------------------------------------
# Poll
# ---------------------------------------------------------------------------


@dataclass
class TelegramPollBatch:
    total_seen: int = 0
    processed: int = 0
    bound: int = 0
    quarantined: int = 0
    ignored: int = 0
    duplicate: int = 0
    claims_created: int = 0
    errors: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors

    def summary(self) -> str:
        return (
            f"[poll-telegram] {self.total_seen} update(s): {self.processed} message(s) logged "
            f"({self.claims_created} claim(s)), {self.bound} binding(s), "
            f"{self.quarantined} unbound, {self.ignored} ignored, {self.duplicate} duplicate"
        )


def _next_offset(session: Session) -> int | None:
    """getUpdates offset = max stored telegram update_id + 1 (None on first poll)."""
    rows = (
        session.query(LabourSourceEvent.source_external_id)
        .filter(LabourSourceEvent.source_channel == "telegram")
        .all()
    )
    seen = [int(r[0]) for r in rows if r[0] and str(r[0]).isdigit()]
    return (max(seen) + 1) if seen else None


def _find_identity(session: Session, user_id: Any) -> TelegramIdentity | None:
    if user_id is None:
        return None
    return (
        session.query(TelegramIdentity)
        .filter(
            TelegramIdentity.telegram_user_id == str(user_id),
            TelegramIdentity.verified.is_(True),
        )
        .one_or_none()
    )


def poll_telegram(
    session: Session,
    client: BaseTelegramClient,
    extractor: TelegramLabourExtractor,
) -> TelegramPollBatch:
    """One-shot poll: fetch new updates and process each. Mirrors poll_mailbox."""
    batch = TelegramPollBatch()
    offset = _next_offset(session)
    updates = client.get_updates(offset=offset)
    batch.total_seen = len(updates)

    for upd in updates:
        try:
            _process_update(session, client, extractor, upd, batch)
        except Exception as exc:
            logger.exception("[TELEGRAM] error processing update %s", upd.get("update_id"))
            batch.errors.append(f"{upd.get('update_id')}: {exc}")
            session.rollback()
    return batch


def _process_update(
    session: Session,
    client: BaseTelegramClient,
    extractor: TelegramLabourExtractor,
    upd: dict[str, Any],
    batch: TelegramPollBatch,
) -> None:
    update_id = upd.get("update_id")
    msg = upd.get("message")
    if msg is None or update_id is None:
        batch.ignored += 1
        return

    # Dedup: an update we already turned into an event is skipped.
    existing = (
        session.query(LabourSourceEvent)
        .filter(
            LabourSourceEvent.source_channel == "telegram",
            LabourSourceEvent.source_external_id == str(update_id),
        )
        .one_or_none()
    )
    if existing is not None:
        batch.duplicate += 1
        return

    text = (msg.get("text") or "").strip()
    chat_id = msg.get("chat_id")
    user_id = msg.get("from_id")
    received_at = (
        datetime.fromtimestamp(msg["date"], tz=timezone.utc).replace(tzinfo=None)
        if msg.get("date")
        else datetime.utcnow()
    )

    # ----- Commands -----
    if text.startswith("/start"):
        _handle_start(session, client, text, msg, batch)
        _record_event(session, update_id, msg, text, "ignored", "command_start")
        session.commit()
        return
    if text.startswith(("/help", "/cancel")):
        client.send_message(chat_id, _HELP)
        _record_event(session, update_id, msg, text, "ignored", "command_help")
        session.commit()
        batch.ignored += 1
        return
    if text.startswith("/status"):
        client.send_message(chat_id, _status_text(session, user_id))
        _record_event(session, update_id, msg, text, "ignored", "command_status")
        session.commit()
        batch.ignored += 1
        return

    # ----- Free text -----
    identity = _find_identity(session, user_id)
    if identity is None:
        _record_event(session, update_id, msg, text, "quarantined", "unbound_sender")
        session.commit()
        batch.quarantined += 1
        client.send_message(
            chat_id,
            "You're not linked yet. Ask your PM for an invite link, then tap it "
            "(or send /start <token>) before logging hours.",
        )
        return

    if not text:
        _record_event(session, update_id, msg, text, "ignored", "empty")
        session.commit()
        batch.ignored += 1
        return

    worker = session.query(Worker).filter_by(canonical_id=identity.worker_id).one()
    identity.last_seen_at = received_at
    event = _record_event(
        session, update_id, msg, text, "extracted", None, worker_id=worker.canonical_id
    )
    session.flush()

    claims = ingest_telegram_labour_claims(
        session,
        extractor,
        text=text,
        source_event_id=event.canonical_id,
        message_datetime=received_at,
        reporter_worker=worker,
        default_project_id=worker.default_project_id,
    )
    if not claims:
        event.ingestion_status = "ignored"
        event.ingestion_reason = "not_labour"
        session.commit()
        batch.ignored += 1
        client.send_message(chat_id, "Got it — nothing to log from that message.")
        return

    # Consolidate every project these new claims touched.
    project_ids = {c.project_id for c in claims if c.project_id}
    session.commit()
    for pid in project_ids:
        consolidate_claims(session, pid)

    batch.processed += 1
    batch.claims_created += len(claims)
    client.send_message(chat_id, _summarize_claims(claims))


def _handle_start(
    session: Session,
    client: BaseTelegramClient,
    text: str,
    msg: dict[str, Any],
    batch: TelegramPollBatch,
) -> None:
    parts = text.split(maxsplit=1)
    token = parts[1].strip() if len(parts) > 1 else ""
    chat_id = msg.get("chat_id")
    if not token:
        client.send_message(
            chat_id, "Send /start <invite token>, or ask your PM for an invite link."
        )
        return
    identity = (
        session.query(TelegramIdentity).filter(TelegramIdentity.invite_token == token).one_or_none()
    )
    if identity is None:
        client.send_message(
            chat_id, "That invite link is invalid or already used. Ask your PM for a new one."
        )
        return
    identity.telegram_user_id = str(msg.get("from_id"))
    identity.telegram_chat_id = str(chat_id)
    identity.telegram_username = msg.get("from_username")
    identity.telegram_first_name = msg.get("from_first_name")
    identity.telegram_last_name = msg.get("from_last_name")
    identity.verified = True
    identity.verified_method = "invite_token"
    identity.invite_token = None  # consume it
    identity.last_seen_at = datetime.utcnow()
    worker = session.query(Worker).filter_by(canonical_id=identity.worker_id).one()
    batch.bound += 1
    client.send_message(
        chat_id,
        f"You're linked as {worker.display_name}. Log hours like:\n"
        "  worked Rockland 7-4, half hour lunch, basement framing",
    )


def _record_event(
    session: Session,
    update_id: Any,
    msg: dict[str, Any],
    text: str,
    status: str,
    reason: str | None,
    *,
    worker_id: Any = None,
) -> LabourSourceEvent:
    ev = LabourSourceEvent(
        canonical_id=uuid.uuid4(),
        source_channel="telegram",
        source_kind="telegram_text",
        source_external_id=str(update_id),
        source_sender_key=str(msg.get("from_id")) if msg.get("from_id") is not None else None,
        source_chat_id=str(msg.get("chat_id")) if msg.get("chat_id") is not None else None,
        source_message_id=str(msg.get("message_id")) if msg.get("message_id") is not None else None,
        received_at=datetime.fromtimestamp(msg["date"], tz=timezone.utc).replace(tzinfo=None)
        if msg.get("date")
        else datetime.utcnow(),
        raw_text=text or None,
        ingestion_status=status,
        ingestion_reason=reason,
        worker_id=worker_id,
    )
    session.add(ev)
    return ev


def _summarize_claims(claims: list) -> str:
    lines = [f"Logged {len(claims)} claim(s):"]
    for c in claims[:10]:
        who = c.employee_name_raw or "(you)"
        when = c.work_date.isoformat() if c.work_date else "?"
        hrs = (
            c.total_hours_reported if c.total_hours_reported is not None else c.total_hours_computed
        )
        hrs_s = f"{hrs}h" if hrs is not None else "no hours"
        extra = f" — {c.activity_text}" if c.activity_text else ""
        flag = " (HOURS MISMATCH — check)" if c.hours_mismatch else ""
        lines.append(f"  {who}: {when}, {hrs_s}{extra}{flag}")
    lines.append("Your PM reviews these in ALTA.")
    return "\n".join(lines)


def _status_text(session: Session, user_id: Any) -> str:
    from datetime import date as _date

    from project_db.db.models import LabourClaim

    identity = _find_identity(session, user_id)
    if identity is None:
        return "You're not linked yet. Ask your PM for an invite link."
    today = _date.today()
    claims = (
        session.query(LabourClaim)
        .filter(
            LabourClaim.reported_for_worker_id == identity.worker_id,
            LabourClaim.work_date == today,
        )
        .all()
    )
    if not claims:
        return "Nothing logged for you today yet."
    total = sum(float(c.total_hours_reported or c.total_hours_computed or 0) for c in claims)
    return f"Today: {len(claims)} entr(y/ies), {total:g}h logged."
