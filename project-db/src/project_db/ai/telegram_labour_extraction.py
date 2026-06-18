"""Telegram (and voice-transcript) free-text -> LabourClaim rows.

Worker/foreman messages are messy: "John 8h Mike 7.5 Alex 5 at Rockland demo",
"worked 7-4 half hour lunch basement framing". The LLM turns that into strict-
JSON claims; deterministic code resolves the worker/project, normalises
dates/times, computes hours, and writes LabourClaim rows (source_channel=
telegram) that flow into the same consolidation layer as the Gmail bridge.

Invariant (as everywhere in ALTA): the LLM extracts; code validates, computes,
and resolves. Raw names are never discarded; a wrong worker match is worse than
unresolved, so resolution is exact/alias only here.
"""

from __future__ import annotations

import json
import os
import uuid
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from project_db.ai.project_log_extraction import (
    _compute_hours,
    _normalize_date,
    _normalize_time,
    _to_decimal,
)
from project_db.db.models import LabourClaim, Project, Worker, WorkerAlias

PROMPT_VERSION = "telegram-labour-v1"

_CLAIM_TYPES = [
    "labour_time",
    "activity_only",
    "attendance_only",
    "correction",
    "absence",
    "unknown",
]

TELEGRAM_LABOUR_SCHEMA: dict[str, Any] = {
    "name": "telegram_labour_extraction",
    "strict": True,
    "schema": {
        "type": "object",
        "additionalProperties": False,
        "required": [
            "document_type",
            "classification_confidence",
            "reporter_role",
            "claims",
            "needs_followup",
            "followup_question",
        ],
        "properties": {
            "document_type": {"type": "string", "enum": ["labour_update", "other"]},
            "classification_confidence": {"type": "number"},
            "reporter_role": {
                "type": "string",
                "enum": ["self", "foreman", "supervisor", "unknown"],
            },
            "needs_followup": {"type": "boolean"},
            "followup_question": {"type": ["string", "null"]},
            "claims": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": [
                        "claim_type",
                        "employee_name",
                        "employee_phone",
                        "is_reporter_self",
                        "project_name",
                        "work_date",
                        "time_arrived",
                        "time_left",
                        "lunch_hours",
                        "total_hours_reported",
                        "activity_text",
                        "trade",
                        "unit",
                        "confidence",
                        "missing_fields",
                        "raw_excerpt",
                    ],
                    "properties": {
                        "claim_type": {"type": "string", "enum": _CLAIM_TYPES},
                        "employee_name": {"type": ["string", "null"]},
                        "employee_phone": {"type": ["string", "null"]},
                        "is_reporter_self": {"type": "boolean"},
                        "project_name": {"type": ["string", "null"]},
                        "work_date": {
                            "type": ["string", "null"],
                            "description": "YYYY-MM-DD; resolve 'today'/'yesterday' from the message timestamp.",
                        },
                        "time_arrived": {"type": ["string", "null"]},
                        "time_left": {"type": ["string", "null"]},
                        "lunch_hours": {"type": ["number", "null"]},
                        "total_hours_reported": {"type": ["number", "null"]},
                        "activity_text": {"type": ["string", "null"]},
                        "trade": {"type": ["string", "null"]},
                        "unit": {"type": ["string", "null"]},
                        "confidence": {"type": "number"},
                        "missing_fields": {"type": "array", "items": {"type": "string"}},
                        "raw_excerpt": {"type": "string"},
                    },
                },
            },
        },
    },
}


def _system_prompt(message_dt: datetime, reporter_name: str | None) -> str:
    return (
        "You read a Telegram message from a construction worker or foreman and "
        "extract LABOUR claims (who worked, where, when, how long, what they did).\n\n"
        f"MESSAGE SENT: {message_dt.strftime('%Y-%m-%d %H:%M')} "
        f"({message_dt.strftime('%A')}).\n"
        f"SENDER: {reporter_name or 'unknown'}.\n\n"
        "Rules:\n"
        "- One claim PER worker mentioned. A foreman listing several workers -> "
        "several claims.\n"
        "- is_reporter_self = true for a claim about the sender themselves "
        "('I worked 7-4'); then employee_name may be null.\n"
        "- Resolve 'today'/'yesterday' to YYYY-MM-DD using MESSAGE SENT.\n"
        "- Times as HH:MM (24h). Do NOT compute total hours -- our code does that. "
        "Only fill total_hours_reported if the message states a number ('8h').\n"
        "- 'actually Mike only did 6 not 8' -> claim_type=correction.\n"
        "- Activity-only updates ('finished the drywall') -> claim_type="
        "activity_only, no times/hours.\n"
        "- Leave project_name null if the message doesn't name a site (our code "
        "applies the sender's default project).\n"
        "- NEVER invent values; unknown fields are null and listed in "
        "missing_fields. raw_excerpt must be verbatim from the message.\n"
        "- If the message isn't a labour update at all, document_type='other' and "
        "claims=[]."
    )


class TelegramLabourExtractorError(RuntimeError):
    pass


class TelegramLabourExtractor(ABC):
    name = "abstract"

    @abstractmethod
    def extract(
        self, *, text: str, message_datetime: datetime, reporter_name: str | None
    ) -> dict[str, Any]:
        """Return a dict conforming to TELEGRAM_LABOUR_SCHEMA's schema."""
        raise NotImplementedError


class OpenAITelegramLabourExtractor(TelegramLabourExtractor):
    name = "openai-telegram-labour"

    def __init__(
        self,
        *,
        api_key: str | None = None,
        model: str | None = None,
        base_url: str = "https://api.openai.com/v1",
        timeout_seconds: float = 60.0,
    ) -> None:
        self.model = model or os.environ.get("OPENAI_EXTRACT_MODEL", "gpt-4o-mini")
        key = api_key or os.environ.get("OPENAI_API_KEY")
        if not key:
            raise TelegramLabourExtractorError("OPENAI_API_KEY is not set.")
        try:
            from openai import OpenAI
        except ImportError as exc:  # pragma: no cover
            raise TelegramLabourExtractorError("openai package not installed") from exc
        self._client = OpenAI(api_key=key, base_url=base_url, timeout=timeout_seconds)

    def extract(
        self, *, text: str, message_datetime: datetime, reporter_name: str | None
    ) -> dict[str, Any]:
        try:
            resp = self._client.chat.completions.create(
                model=self.model,
                temperature=0,
                messages=[
                    {"role": "system", "content": _system_prompt(message_datetime, reporter_name)},
                    {"role": "user", "content": text},
                ],
                response_format={"type": "json_schema", "json_schema": TELEGRAM_LABOUR_SCHEMA},
            )
        except Exception as exc:
            raise TelegramLabourExtractorError(f"OpenAI call failed: {exc}") from exc
        msg = resp.choices[0].message
        if getattr(msg, "refusal", None):
            raise TelegramLabourExtractorError(f"model refused: {msg.refusal}")
        try:
            return json.loads(msg.content)
        except (json.JSONDecodeError, TypeError) as exc:
            raise TelegramLabourExtractorError(f"bad JSON: {exc}") from exc


class MockTelegramLabourExtractor(TelegramLabourExtractor):
    """Deterministic test double: canned result, or per-text mapping."""

    name = "mock-telegram-labour"

    def __init__(
        self, result: dict[str, Any] | None = None, by_text: dict[str, dict[str, Any]] | None = None
    ) -> None:
        self._result = result
        self._by_text = by_text or {}
        self.calls: list[str] = []

    def extract(
        self, *, text: str, message_datetime: datetime, reporter_name: str | None
    ) -> dict[str, Any]:
        self.calls.append(text)
        if text in self._by_text:
            return self._by_text[text]
        if self._result is not None:
            return self._result
        return {
            "document_type": "other",
            "classification_confidence": 0.0,
            "reporter_role": "unknown",
            "claims": [],
            "needs_followup": False,
            "followup_question": None,
        }


# ---------------------------------------------------------------------------
# Deterministic resolution + claim building
# ---------------------------------------------------------------------------


def _resolve_worker(
    session: Session,
    *,
    is_self: bool,
    name: str | None,
    reporter_worker: Worker | None,
    allow_create: bool = False,
) -> tuple[Any, str, float | None]:
    """(worker_id, method, confidence).

    Order: self -> exact display_name -> alias. Then, when ``allow_create`` (a
    name reported by a BOUND reporter, e.g. a foreman listing crew), a genuinely
    new name auto-creates an UNVERIFIED Worker stub (method ``auto_created``) so
    the hours attach to someone reviewable -- rather than floating unresolved.
    We never fuzzy-merge: "Mike" gets its own stub even if "Michael" exists; the
    PM aliases/merges later (a wrong merge corrupts; a new stub is reversible).
    """
    if is_self and reporter_worker is not None:
        return reporter_worker.canonical_id, "telegram_identity", 1.0
    if not name or not name.strip():
        return None, "unresolved", None
    needle = " ".join(name.strip().lower().split())
    for w in session.query(Worker).all():
        if " ".join((w.display_name or "").lower().split()) == needle:
            return w.canonical_id, "exact", 1.0
    for a in session.query(WorkerAlias).all():
        if " ".join((a.alias_text or "").lower().split()) == needle:
            return a.worker_id, "alias", (a.confidence if a.confidence is not None else 0.9)
    if allow_create:
        stub = Worker(
            canonical_id=uuid.uuid4(),
            display_name=name.strip(),
            active=True,
            verified=False,  # flagged for the PM to confirm / merge
        )
        session.add(stub)
        session.flush()  # so a repeated name in the same message resolves to it
        return stub.canonical_id, "auto_created", 0.6
    return None, "unresolved", None


def _resolve_project(
    session: Session, *, name: str | None, default_project_id: Any
) -> tuple[Any, str, float | None]:
    if name and name.strip():
        frag = name.strip().lower()
        for p in session.query(Project).filter(Project.name.isnot(None)).all():
            pname = (p.name or "").lower()
            if frag in pname or pname in frag:
                return p.canonical_id, "text_llm", 0.8
    if default_project_id is not None:
        return default_project_id, "worker_default", 0.6
    return None, "unresolved", None


def ingest_telegram_labour_claims(
    session: Session,
    extractor: TelegramLabourExtractor,
    *,
    text: str,
    source_event_id: Any,
    message_datetime: datetime,
    reporter_worker: Worker | None = None,
    default_project_id: Any = None,
) -> list[LabourClaim]:
    """Extract a Telegram message into resolved LabourClaim rows. Flushes, not commits.

    The LLM extracts; this resolves worker/project (exact/alias only), normalises
    date/times, computes hours, and preserves raw values + uncertainty. Returns
    the created claims (possibly empty).
    """
    reporter_name = reporter_worker.display_name if reporter_worker else None
    raw = extractor.extract(
        text=text, message_datetime=message_datetime, reporter_name=reporter_name
    )

    if raw.get("document_type") != "labour_update":
        return []

    reporter_role = raw.get("reporter_role") or "unknown"
    # A BOUND reporter (e.g. foreman Andres) is trusted to name crew, so an
    # unknown name they report auto-creates a stub. An unbound message never
    # reaches here (it's quarantined), so this can't mint workers from strangers.
    allow_create = reporter_worker is not None
    out: list[LabourClaim] = []
    for c in raw.get("claims") or []:
        is_self = bool(c.get("is_reporter_self"))
        name = c.get("employee_name")
        wid, wmethod, wconf = _resolve_worker(
            session,
            is_self=is_self,
            name=name,
            reporter_worker=reporter_worker,
            allow_create=allow_create,
        )
        pid, pmethod, pconf = _resolve_project(
            session, name=c.get("project_name"), default_project_id=default_project_id
        )
        work_date = _normalize_date(c.get("work_date"))
        arrived = _normalize_time(c.get("time_arrived"))
        left = _normalize_time(c.get("time_left"))
        lunch = _to_decimal(c.get("lunch_hours"))
        reported = _to_decimal(c.get("total_hours_reported"))
        computed = _compute_hours(arrived, left, lunch)
        mismatch = reported is not None and computed is not None and abs(reported - computed) > 0.25
        try:
            cconf = max(0.0, min(1.0, float(c.get("confidence"))))
        except (TypeError, ValueError):
            cconf = 0.5

        claim_type = c.get("claim_type") or "unknown"
        # Resolve the reporter (the sender) when this claim is a self-report.
        reporter_worker_id = reporter_worker.canonical_id if reporter_worker else None

        claim = LabourClaim(
            canonical_id=uuid.uuid4(),
            source_event_id=source_event_id,
            source_channel="telegram",
            source_confidence=cconf,  # per-claim extraction confidence
            reporter_worker_id=reporter_worker_id,
            reporter_role=reporter_role
            if reporter_role in ("self", "foreman", "supervisor")
            else "unknown",
            reported_for_worker_id=wid,
            employee_name_raw=name if name else (reporter_name if is_self else None),
            employee_phone_raw=c.get("employee_phone"),
            employee_match_method=wmethod,
            employee_match_confidence=wconf,
            project_id=pid,
            project_name_raw=c.get("project_name"),
            project_match_method=pmethod,
            project_match_confidence=pconf,
            work_date=work_date,
            work_date_raw=c.get("work_date"),
            time_arrived=arrived,
            time_left=left,
            lunch_hours=lunch,
            total_hours_reported=reported,
            total_hours_computed=computed,
            hours_mismatch=bool(mismatch),
            activity_text=(c.get("activity_text") or None),
            trade=(c.get("trade") or None),
            unit=(c.get("unit") or None),
            claim_type=claim_type,
            extraction_method="text_llm",
            extractor_version=PROMPT_VERSION,
            missing_fields_json=json.dumps(c.get("missing_fields") or []),
            raw_extraction_json=json.dumps(c),
            review_status="pending",
        )
        session.add(claim)
        out.append(claim)
    session.flush()
    return out
