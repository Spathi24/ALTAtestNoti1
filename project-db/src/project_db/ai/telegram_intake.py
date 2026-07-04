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

import json
import logging
import re
import secrets
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy.orm import Session

from project_db.ai.labour_consolidation import consolidate_claims
from project_db.ai.telegram_labour_extraction import (
    TelegramLabourExtractor,
    ingest_telegram_labour_claims,
)
from project_db.connectors.telegram.client import BaseTelegramClient
from project_db.db.models import LabourSourceEvent, Project, TelegramIdentity, Worker

logger = logging.getLogger(__name__)

_HELP = (
    "ALTA site bot. Text any site update in plain language -- progress, issues,\n"
    "deliveries, questions -- and it's logged for the team's weekly report.\n"
    "Mention the site/address so it files under the right project.\n\n"
    "Invited workers can also log hours, e.g.:\n"
    "  worked Rockland 7-4, half hour lunch, basement framing\n\n"
    "Commands: /start <token> to link your account, /status for today, /help."
)

# Acknowledgement for a general (non-labour) message.
_GENERAL_ACK = "Got it -- logged for the team's weekly report. Thanks for the update."

# Recency-weighted project attribution (deterministic, no LLM). A sender's
# recent project-attributed messages vote, weighted by recency; the top project
# must dominate (>= _ATTRIB_DOMINANCE of total weight) or the message is left
# unattributed (PMs who switch sites constantly -> project-less Site comms).
_ATTRIB_HALF_LIFE_DAYS = 7.0
_ATTRIB_WINDOW_DAYS = 14
_ATTRIB_DOMINANCE = 0.6

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
    general: int = 0
    errors: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors

    def summary(self) -> str:
        return (
            f"[poll-telegram] {self.total_seen} update(s): {self.processed} labour message(s) "
            f"({self.claims_created} claim(s)), {self.general} general message(s), "
            f"{self.bound} binding(s), {self.quarantined} unbound, "
            f"{self.ignored} ignored, {self.duplicate} duplicate"
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


def _attribute_project(
    session: Session,
    user_id: Any,
    text: str,
    *,
    worker: Worker | None = None,
    now: datetime | None = None,
) -> tuple[Any, str, float]:
    """Deterministically attribute a general message to a project (no LLM).

    Returns ``(project_id | None, method, confidence)``, first hit wins:
      1. text_match  -- an active project's name appears in the message text.
      2. worker_default -- a bound sender's Worker.default_project_id.
      3. sender_recency -- recency-weighted vote over this sender's recent
         project-attributed messages; the top project must reach
         ``_ATTRIB_DOMINANCE`` of total weight, else it's treated as ambiguous.
      4. unresolved  -- (None) -> the message lands in the project-less
         "Site communications" section for human routing.
    """
    now = now or datetime.utcnow()

    # 1) Explicit site/project name in the message text.
    if text:
        frag = text.lower()
        for p in session.query(Project).filter(Project.name.isnot(None)).all():
            pname = (p.name or "").lower().strip()
            if not pname:
                continue
            # Full name match (highest confidence).
            if pname in frag:
                return p.canonical_id, "text_match", 0.9
            # Word-token match: e.g. "Rockland" from "923-927 Rockland" (address-format names).
            for token in re.split(r"[\s\-/]+", pname):
                token = token.strip(".,:()")
                if len(token) >= 4 and re.search(r"\b" + re.escape(token) + r"\b", frag):
                    return p.canonical_id, "text_match_word", 0.75

    # 2) Bound worker's default project.
    if worker is not None and getattr(worker, "default_project_id", None):
        return worker.default_project_id, "worker_default", 0.6

    # 3) Recency-weighted sender history.
    if user_id is not None:
        cutoff = now - timedelta(days=_ATTRIB_WINDOW_DAYS)
        rows = (
            session.query(LabourSourceEvent)
            .filter(
                LabourSourceEvent.source_channel == "telegram",
                LabourSourceEvent.source_sender_key == str(user_id),
                LabourSourceEvent.project_id_hint.isnot(None),
                LabourSourceEvent.received_at >= cutoff,
            )
            .all()
        )
        weights: dict[Any, float] = {}
        total = 0.0
        for r in rows:
            ts = r.source_created_at or r.received_at
            if ts is None:
                continue
            age_days = max(0.0, (now - ts).total_seconds() / 86400.0)
            w = 0.5 ** (age_days / _ATTRIB_HALF_LIFE_DAYS)
            weights[r.project_id_hint] = weights.get(r.project_id_hint, 0.0) + w
            total += w
        if total > 0:
            top_pid, top_w = max(weights.items(), key=lambda kv: kv[1])
            if top_w / total >= _ATTRIB_DOMINANCE:
                return top_pid, "sender_recency", 0.5

    return None, "unresolved", 0.0


def poll_telegram(
    session: Session,
    client: BaseTelegramClient,
    extractor: TelegramLabourExtractor | None = None,
    *,
    general_intake: bool = True,
) -> TelegramPollBatch:
    """One-shot poll: fetch new updates and process each. Mirrors poll_mailbox.

    Feature gating lives at the CLI edge, passed in here as explicit inputs:
      - ``extractor`` present  -> the labour path is available (bound workers).
      - ``general_intake=True`` -> anyone's message is accepted as general
        content (attributed + surfaced in the weekly report). When False, the
        legacy labour-only contract holds (strangers quarantined).
    """
    batch = TelegramPollBatch()
    offset = _next_offset(session)
    updates = client.get_updates(offset=offset)
    batch.total_seen = len(updates)

    for upd in updates:
        try:
            _process_update(session, client, extractor, upd, batch, general_intake=general_intake)
        except Exception as exc:
            logger.exception("[TELEGRAM] error processing update %s", upd.get("update_id"))
            batch.errors.append(f"{upd.get('update_id')}: {exc}")
            session.rollback()
            _record_failed_update(session, upd, exc)
    return batch


def _nested(d: dict[str, Any] | None, key: str) -> Any:
    return d.get(key) if isinstance(d, dict) else None


def _msg_chat_id(msg: dict[str, Any] | None) -> Any:
    return _nested(msg, "chat_id") or _nested(_nested(msg, "chat"), "id")


def _msg_from(msg: dict[str, Any] | None) -> dict[str, Any] | None:
    frm = _nested(msg, "from")
    return frm if isinstance(frm, dict) else None


def _msg_from_id(msg: dict[str, Any] | None) -> Any:
    return _nested(msg, "from_id") or _nested(_msg_from(msg), "id")


def _msg_from_field(msg: dict[str, Any] | None, field: str) -> Any:
    flat = _nested(msg, f"from_{field}")
    if flat is not None:
        return flat
    return _nested(_msg_from(msg), field)


def _msg_message_id(msg: dict[str, Any] | None) -> Any:
    return _nested(msg, "message_id")


def _msg_text(msg: dict[str, Any] | None) -> str:
    return str(_nested(msg, "text") or _nested(msg, "caption") or "").strip()


def _source_created_at(msg: dict[str, Any] | None) -> datetime | None:
    date_value = _nested(msg, "date")
    if date_value is None:
        return None
    try:
        return datetime.fromtimestamp(date_value, tz=timezone.utc).replace(tzinfo=None)
    except (OSError, TypeError, ValueError):
        return None


def _serialisable_payload(upd: dict[str, Any]) -> str:
    payload = upd.get("raw_update") if isinstance(upd.get("raw_update"), dict) else upd
    try:
        return json.dumps(payload, default=str, sort_keys=True)
    except TypeError:
        return json.dumps({"update_id": upd.get("update_id")}, sort_keys=True)


def _event_exists(session: Session, update_id: Any) -> bool:
    if update_id is None:
        return False
    return (
        session.query(LabourSourceEvent)
        .filter(
            LabourSourceEvent.source_channel == "telegram",
            LabourSourceEvent.source_external_id == str(update_id),
        )
        .one_or_none()
        is not None
    )


def _record_failed_update(session: Session, upd: dict[str, Any], exc: Exception) -> None:
    update_id = upd.get("update_id")
    if update_id is None or _event_exists(session, update_id):
        return
    try:
        _record_event(
            session,
            update_id,
            upd.get("message"),
            None,
            "failed",
            f"exception:{type(exc).__name__}",
            raw_payload=upd,
            source_kind="telegram_update",
        )
        session.commit()
    except Exception:
        logger.exception("[TELEGRAM] could not preserve failed update %s", update_id)
        session.rollback()


def _process_update(
    session: Session,
    client: BaseTelegramClient,
    extractor: TelegramLabourExtractor | None,
    upd: dict[str, Any],
    batch: TelegramPollBatch,
    *,
    general_intake: bool = False,
) -> None:
    update_id = upd.get("update_id")
    msg = upd.get("message")
    callback = upd.get("callback_query") if isinstance(upd.get("callback_query"), dict) else None
    if update_id is None:
        batch.ignored += 1
        _record_event(
            session,
            None,
            msg,
            None,
            "failed",
            "missing_update_id",
            raw_payload=upd,
            source_kind="telegram_update",
        )
        session.commit()
        return

    # Dedup: an update we already turned into an event is skipped.
    if _event_exists(session, update_id):
        batch.duplicate += 1
        return

    if msg is None:
        if callback is not None:
            cb_msg = callback.get("message") if isinstance(callback.get("message"), dict) else None
            _record_event(
                session,
                update_id,
                cb_msg,
                str(callback.get("data") or "") or None,
                "ignored",
                "callback_query",
                raw_payload=upd,
                source_kind="telegram_callback",
                sender_key=callback.get("from", {}).get("id")
                if isinstance(callback.get("from"), dict)
                else None,
            )
        else:
            _record_event(
                session,
                update_id,
                None,
                None,
                "ignored",
                "non_message_update",
                raw_payload=upd,
                source_kind="telegram_update",
            )
        session.commit()
        batch.ignored += 1
        return

    text = _msg_text(msg)
    chat_id = _msg_chat_id(msg)
    user_id = _msg_from_id(msg)
    source_created_at = _source_created_at(msg)
    message_datetime = source_created_at or datetime.utcnow()

    # ----- Commands -----
    if text.startswith("/start"):
        _handle_start(session, client, text, msg, batch)
        _record_event(session, update_id, msg, text, "ignored", "command_start", raw_payload=upd)
        session.commit()
        return
    if text.startswith(("/help", "/cancel")):
        client.send_message(chat_id, _HELP)
        _record_event(session, update_id, msg, text, "ignored", "command_help", raw_payload=upd)
        session.commit()
        batch.ignored += 1
        return
    if text.startswith("/status"):
        client.send_message(chat_id, _status_text(session, user_id))
        _record_event(session, update_id, msg, text, "ignored", "command_status", raw_payload=upd)
        session.commit()
        batch.ignored += 1
        return

    # ----- Free text -----
    if not text:
        _record_event(session, update_id, msg, text, "ignored", "empty", raw_payload=upd)
        session.commit()
        batch.ignored += 1
        return

    identity = _find_identity(session, user_id)
    worker = (
        session.query(Worker).filter_by(canonical_id=identity.worker_id).one()
        if identity is not None
        else None
    )
    if identity is not None:
        identity.last_seen_at = source_created_at or datetime.utcnow()

    # Record EXACTLY ONE source event per update (preserves the offset cursor /
    # dedup invariant). Its status is refined below once we know the content type.
    event = _record_event(
        session,
        update_id,
        msg,
        text,
        "received",
        None,
        worker_id=worker.canonical_id if worker else None,
        raw_payload=upd,
    )
    session.flush()

    # ----- Labour path (specialized): a bound worker + an available extractor.
    # The LLM classifies; if it yields claims, this is a labour update. -----
    claims: list = []
    if worker is not None and extractor is not None:
        try:
            # SAVEPOINT: a labour-extraction failure rolls back only the partial
            # claims, leaving the already-recorded event intact to fall through
            # to the general path.
            with session.begin_nested():
                claims = ingest_telegram_labour_claims(
                    session,
                    extractor,
                    text=text,
                    source_event_id=event.canonical_id,
                    message_datetime=message_datetime,
                    reporter_worker=worker,
                    default_project_id=worker.default_project_id,
                )
        except Exception:
            logger.exception("[TELEGRAM] labour extraction failed; routing as general content")
            claims = []

    if claims:
        event.ingestion_status = "extracted"
        project_ids = {c.project_id for c in claims if c.project_id}
        session.commit()
        for pid in project_ids:
            consolidate_claims(session, pid)
        batch.processed += 1
        batch.claims_created += len(claims)
        client.send_message(chat_id, _summarize_claims(claims))
        return

    # ----- General content path: anyone, any message. Keep the event as an
    # accepted communication, attribute a project deterministically, surface it
    # in the weekly report. Only active when general intake is enabled. -----
    if general_intake:
        event.ingestion_status = "received"
        event.ingestion_reason = "general_content"
        pid, _method, _conf = _attribute_project(session, user_id, text, worker=worker)
        if pid is not None:
            event.project_id_hint = pid
        session.commit()
        batch.general += 1
        client.send_message(chat_id, _GENERAL_ACK)
        return

    # ----- General intake OFF: preserve the legacy labour-only contract. -----
    if worker is None:
        event.ingestion_status = "quarantined"
        event.ingestion_reason = "unbound_sender"
        session.commit()
        batch.quarantined += 1
        client.send_message(
            chat_id,
            "You're not linked yet. Ask your PM for an invite link, then tap it "
            "(or send /start <token>) before logging hours.",
        )
        return
    event.ingestion_status = "ignored"
    event.ingestion_reason = "not_labour"
    session.commit()
    batch.ignored += 1
    client.send_message(chat_id, "Got it — nothing to log from that message.")


def _handle_start(
    session: Session,
    client: BaseTelegramClient,
    text: str,
    msg: dict[str, Any],
    batch: TelegramPollBatch,
) -> None:
    parts = text.split(maxsplit=1)
    token = parts[1].strip() if len(parts) > 1 else ""
    chat_id = _msg_chat_id(msg)
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
    from_id = _msg_from_id(msg)
    existing = (
        session.query(TelegramIdentity)
        .filter(
            TelegramIdentity.telegram_user_id == str(from_id),
            TelegramIdentity.verified.is_(True),
        )
        .one_or_none()
    )
    if existing is not None:
        existing_worker = (
            session.query(Worker).filter_by(canonical_id=existing.worker_id).one_or_none()
        )
        name = existing_worker.display_name if existing_worker else "an existing worker"
        client.send_message(
            chat_id,
            f"Your account is already linked as {name}. Ask your PM if you need to re-link.",
        )
        return
    identity.telegram_user_id = str(from_id)
    identity.telegram_chat_id = str(chat_id)
    identity.telegram_username = _msg_from_field(msg, "username")
    identity.telegram_first_name = _msg_from_field(msg, "first_name")
    identity.telegram_last_name = _msg_from_field(msg, "last_name")
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
    raw_payload: dict[str, Any] | None = None,
    source_kind: str = "telegram_text",
    sender_key: Any = None,
) -> LabourSourceEvent:
    source_created_at = _source_created_at(msg)
    ev = LabourSourceEvent(
        canonical_id=uuid.uuid4(),
        source_channel="telegram",
        source_kind=source_kind,
        source_external_id=str(update_id) if update_id is not None else None,
        source_sender_key=str(sender_key if sender_key is not None else _msg_from_id(msg))
        if (sender_key is not None or _msg_from_id(msg) is not None)
        else None,
        source_chat_id=str(_msg_chat_id(msg)) if _msg_chat_id(msg) is not None else None,
        source_message_id=str(_msg_message_id(msg)) if _msg_message_id(msg) is not None else None,
        received_at=datetime.utcnow(),
        source_created_at=source_created_at,
        raw_text=text or None,
        raw_payload_json=_serialisable_payload(raw_payload or {"update_id": update_id}),
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
