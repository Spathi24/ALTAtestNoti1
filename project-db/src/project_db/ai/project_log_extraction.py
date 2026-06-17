"""Project Log ingestion: classify a labour/time-sheet image and extract its rows.

Separate from field notes (``field_note_extraction.py``) and from financials.
See ``docs/PROJECT_LOG_INGESTION.md``.

Pipeline (mirrors the field-note extractor's shape):
  1. A single vision structured-output call classifies the attachment
     (``document_type`` = project_log | other) AND extracts the table rows.
  2. Deterministic code validates: normalise dates/times, compute hours from
     arrival/departure/lunch, compare to the reported total, flag mismatches,
     drop blank rows.  THE MODEL EXTRACTS; CODE VALIDATES AND COMPUTES.
  3. ``ingest_project_log`` resolves the site->project and each handwritten
     name->Worker (exact/alias only; never a forced match), then writes one
     ``ProjectLogSubmission`` + N ``ProjectLogEntry`` rows.

Design rules honoured (docs/PROJECT_LOG_INGESTION.md):
  - Canonical DB is the source of truth (write here; Drive mirror is separate).
  - employee_name_raw is NEVER discarded, even when unresolved.
  - reported hours are never silently overwritten; both reported+computed kept.
  - low-confidence classification -> quarantine, never silently field-noted.
  - idempotent on (source_email_message_id, source_attachment_hash).
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import date as _date_type
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Any

from sqlalchemy.orm import Session

from project_db.db.models import (
    Project,
    ProjectLogEntry,
    ProjectLogSubmission,
    Worker,
    WorkerAlias,
)

logger = logging.getLogger(__name__)

PROJECT_LOG_PROMPT_VERSION = "project-log-v1"
EXTRACTOR_VERSION = "project-log-v1"

# Classification confidence below this -> quarantine for human review.
_DEFAULT_CLASSIFY_THRESHOLD = 0.6
# Reported vs computed hours allowed to differ by this much (hours) before flag.
_HOURS_TOLERANCE = Decimal("0.25")  # 15 minutes


# ---------------------------------------------------------------------------
# Image helpers (the form IS the photo -- broader ext set than field notes)
# ---------------------------------------------------------------------------

_IMAGE_EXTS: frozenset[str] = frozenset(
    {".jpg", ".jpeg", ".png", ".webp", ".gif", ".jfif", ".bmp", ".tif", ".tiff", ".heic", ".heif"}
)
_MIME_BY_EXT: dict[str, str] = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".jfif": "image/jpeg",
    ".png": "image/png",
    ".webp": "image/webp",
    ".gif": "image/gif",
    ".bmp": "image/bmp",
    ".tif": "image/tiff",
    ".tiff": "image/tiff",
    ".heic": "image/heic",
    ".heif": "image/heif",
}
_MAX_IMAGE_BYTES = 20 * 1024 * 1024  # 20 MB -- a phone photo of a form


def _load_image_data_url(path: str) -> str | None:
    """Read an image and return a data-URL, or None if unsupported/oversized."""
    import base64 as _base64

    ext = os.path.splitext(path)[1].lower()
    if ext not in _IMAGE_EXTS:
        return None
    try:
        size = os.path.getsize(path)
    except OSError:
        return None
    if size > _MAX_IMAGE_BYTES or size == 0:
        return None
    try:
        with open(path, "rb") as fh:
            data = fh.read()
    except OSError:
        return None
    mime = _MIME_BY_EXT.get(ext, "image/jpeg")
    return f"data:{mime};base64,{_base64.b64encode(data).decode()}"


def _sha256_file(path: str) -> str | None:
    try:
        h = hashlib.sha256()
        with open(path, "rb") as fh:
            for chunk in iter(lambda: fh.read(65536), b""):
                h.update(chunk)
        return h.hexdigest()
    except OSError:
        return None


# ---------------------------------------------------------------------------
# Strict JSON schema for structured outputs
# ---------------------------------------------------------------------------

PROJECT_LOG_SCHEMA: dict[str, Any] = {
    "name": "project_log_extraction",
    "strict": True,
    "schema": {
        "type": "object",
        "additionalProperties": False,
        "required": ["document_type", "site_name", "classification_confidence", "rows"],
        "properties": {
            "document_type": {
                "type": "string",
                "enum": ["project_log", "other"],
                "description": (
                    "project_log if this image is an ALTA PROJECT LOG labour/time "
                    "sheet (title 'ALTA PROJECT LOG' and/or a table with columns "
                    "Date / Name / Time Arrived / Time Left / Lunch Hours / Total "
                    "Hours / Supervisor Signature). Otherwise 'other'."
                ),
            },
            "site_name": {
                "type": ["string", "null"],
                "description": "Verbatim text in the Site Name box at the top; null if blank.",
            },
            "classification_confidence": {
                "type": "number",
                "description": "Confidence in [0,1] that this is a project log.",
            },
            "rows": {
                "type": "array",
                "description": "One object per FILLED table row. Skip entirely-blank rows.",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": [
                        "row_index",
                        "date",
                        "name",
                        "time_arrived",
                        "time_left",
                        "lunch_hours",
                        "total_hours_reported",
                        "supervisor_signature_present",
                        "confidence",
                        "raw_notes",
                    ],
                    "properties": {
                        "row_index": {"type": "integer", "description": "1-based row number."},
                        "date": {
                            "type": ["string", "null"],
                            "description": "Work date as YYYY-MM-DD, or null if blank/illegible.",
                        },
                        "name": {
                            "type": ["string", "null"],
                            "description": "Worker name exactly as written; null if blank.",
                        },
                        "time_arrived": {
                            "type": ["string", "null"],
                            "description": "Arrival time as HH:MM (24h), or null.",
                        },
                        "time_left": {
                            "type": ["string", "null"],
                            "description": "Departure time as HH:MM (24h), or null.",
                        },
                        "lunch_hours": {
                            "type": ["number", "null"],
                            "description": "Lunch duration in hours (e.g. 0.5), or null.",
                        },
                        "total_hours_reported": {
                            "type": ["number", "null"],
                            "description": "Total Hours exactly as written on the form, or null.",
                        },
                        "supervisor_signature_present": {
                            "type": "boolean",
                            "description": "true if a signature/mark is present in that row.",
                        },
                        "confidence": {
                            "type": "number",
                            "description": "Confidence in [0,1] for this row's reading.",
                        },
                        "raw_notes": {
                            "type": ["string", "null"],
                            "description": "Anything ambiguous/illegible; null if clean.",
                        },
                    },
                },
            },
        },
    },
}


def _system_prompt() -> str:
    return (
        "You read photographed/scanned ALTA PROJECT LOG sheets -- standardized "
        "paper forms that record worker attendance/time on a construction site.\n\n"
        "The form has a 'Site Name' box at the top and a table with columns:\n"
        "Date | Name | Time Arrived | Time Left | Lunch Hours | Total Hours | "
        "Supervisor Signature.\n\n"
        "Your job:\n"
        "1. Decide document_type: 'project_log' only if this really is an ALTA "
        "PROJECT LOG (the title and/or that column layout). Otherwise 'other'.\n"
        "2. Read the Site Name box verbatim (null if blank).\n"
        "3. For EACH FILLED row, return its values. Skip rows that are entirely "
        "blank.\n\n"
        "STRICT RULES:\n"
        "- Never invent values. A blank or illegible cell is null (not a guess).\n"
        "- Dates as YYYY-MM-DD; times as HH:MM 24-hour. If you can read '7:30 am' "
        "write '07:30'; '4 pm' -> '16:00'.\n"
        "- total_hours_reported is what is WRITTEN in the Total Hours column -- do "
        "not compute it yourself (the system computes and cross-checks).\n"
        "- supervisor_signature_present is true only if a signature/mark is visibly "
        "present in that row.\n"
        "- Put anything uncertain in raw_notes and lower that row's confidence.\n"
        "- If the image is not a project log, return document_type='other', "
        "site_name=null, rows=[] and a low classification_confidence."
    )


# ---------------------------------------------------------------------------
# Extractor providers
# ---------------------------------------------------------------------------


class ProjectLogExtractorError(RuntimeError):
    pass


class ProjectLogExtractor(ABC):
    name = "abstract"

    @abstractmethod
    def extract(self, *, image_paths: list[str]) -> dict[str, Any]:
        """Return a dict conforming to PROJECT_LOG_SCHEMA's schema."""
        raise NotImplementedError


class OpenAIProjectLogExtractor(ProjectLogExtractor):
    """Real extractor via OpenAI vision + structured outputs (detail='high')."""

    name = "openai-project-log"

    def __init__(
        self,
        *,
        api_key: str | None = None,
        model: str | None = None,
        base_url: str = "https://api.openai.com/v1",
        timeout_seconds: float = 90.0,
    ) -> None:
        # gpt-4o reads handwriting better than -mini; allow override.
        self.model = model or os.environ.get("OPENAI_PROJECT_LOG_MODEL", "gpt-4o")
        key = api_key or os.environ.get("OPENAI_API_KEY")
        if not key:
            raise ProjectLogExtractorError(
                "OPENAI_API_KEY is not set (needed for project-log extraction)."
            )
        try:
            from openai import OpenAI
        except ImportError as exc:  # pragma: no cover
            raise ProjectLogExtractorError("openai package not installed") from exc
        self._client = OpenAI(api_key=key, base_url=base_url, timeout=timeout_seconds)

    def extract(self, *, image_paths: list[str]) -> dict[str, Any]:
        loaded = [u for u in (_load_image_data_url(p) for p in image_paths) if u]
        if not loaded:
            # Nothing readable -> not a project log we can claim.
            return {
                "document_type": "other",
                "site_name": None,
                "classification_confidence": 0.0,
                "rows": [],
            }
        content: list[dict[str, Any]] = [
            {"type": "text", "text": "Extract this ALTA PROJECT LOG sheet."}
        ]
        for url in loaded:
            # detail='high': a handwritten table grid needs the resolution.
            content.append({"type": "image_url", "image_url": {"url": url, "detail": "high"}})
        try:
            resp = self._client.chat.completions.create(
                model=self.model,
                temperature=0,
                messages=[
                    {"role": "system", "content": _system_prompt()},
                    {"role": "user", "content": content},
                ],
                response_format={"type": "json_schema", "json_schema": PROJECT_LOG_SCHEMA},
            )
        except Exception as exc:
            raise ProjectLogExtractorError(f"OpenAI vision call failed: {exc}") from exc
        msg = resp.choices[0].message
        if getattr(msg, "refusal", None):
            raise ProjectLogExtractorError(f"model refused: {msg.refusal}")
        try:
            return json.loads(msg.content)
        except (json.JSONDecodeError, TypeError) as exc:
            raise ProjectLogExtractorError(f"bad JSON despite strict schema: {exc}") from exc


class MockProjectLogExtractor(ProjectLogExtractor):
    """Deterministic extractor for tests: returns canned responses in order."""

    name = "mock-project-log"

    def __init__(self, responses: list[dict[str, Any]] | None = None) -> None:
        self._responses = list(responses or [])
        self._idx = 0
        self.calls: list[list[str]] = []

    def extract(self, *, image_paths: list[str]) -> dict[str, Any]:
        self.calls.append(list(image_paths))
        if self._idx < len(self._responses):
            r = self._responses[self._idx]
            self._idx += 1
            return r
        return {
            "document_type": "other",
            "site_name": None,
            "classification_confidence": 0.0,
            "rows": [],
        }


# ---------------------------------------------------------------------------
# Deterministic validation (the model extracts; code validates + computes)
# ---------------------------------------------------------------------------

_TIME_HM_RE = re.compile(r"^\s*(\d{1,2})\s*[:hH.]\s*(\d{2})\s*([ap])\.?\s*m\.?\s*$", re.I)
_TIME_HOUR_AMPM_RE = re.compile(r"^\s*(\d{1,2})\s*([ap])\.?\s*m\.?\s*$", re.I)
_TIME_HM_24_RE = re.compile(r"^\s*(\d{1,2})\s*[:hH.]\s*(\d{2})\s*$")
_TIME_COMPACT_RE = re.compile(r"^\s*(\d{3,4})\s*$")

_DATE_FORMATS = ("%Y-%m-%d", "%Y/%m/%d", "%m/%d/%Y", "%m/%d/%y", "%B %d, %Y", "%d %B %Y")


def _normalize_time(raw: Any) -> str | None:
    """Parse a messy time cell into 'HH:MM' (24h), or None.

    Handles '7:30', '07:30', '16:00', '7:30 AM', '4pm', '0730', '730'.
    Returns None for unparseable/out-of-range input (never guesses).
    """
    if raw is None:
        return None
    s = str(raw).strip()
    if not s:
        return None

    def _apply_ampm(h: int, ampm: str) -> int | None:
        ampm = ampm.lower()
        if not 1 <= h <= 12:
            return None
        if ampm == "a":
            return 0 if h == 12 else h
        return h if h == 12 else h + 12

    m = _TIME_HM_RE.match(s)
    if m:
        h = _apply_ampm(int(m.group(1)), m.group(3))
        minute = int(m.group(2))
        if h is None or minute > 59:
            return None
        return f"{h:02d}:{minute:02d}"

    m = _TIME_HOUR_AMPM_RE.match(s)
    if m:
        h = _apply_ampm(int(m.group(1)), m.group(2))
        if h is None:
            return None
        return f"{h:02d}:00"

    m = _TIME_HM_24_RE.match(s)
    if m:
        h, minute = int(m.group(1)), int(m.group(2))
        if h > 23 or minute > 59:
            return None
        return f"{h:02d}:{minute:02d}"

    m = _TIME_COMPACT_RE.match(s)
    if m:
        digits = m.group(1)
        h, minute = int(digits[:-2]), int(digits[-2:])
        if h > 23 or minute > 59:
            return None
        return f"{h:02d}:{minute:02d}"

    return None


def _time_to_minutes(hhmm: str) -> int:
    h, m = hhmm.split(":")
    return int(h) * 60 + int(m)


def _to_decimal(v: Any, *, allow_negative: bool = False) -> Decimal | None:
    """Coerce a number/string to a 2-dp Decimal, or None. Drops negatives unless allowed."""
    if v is None:
        return None
    try:
        d = Decimal(str(v).strip().replace(",", "."))
    except (InvalidOperation, ValueError, AttributeError):
        return None
    if not allow_negative and d < 0:
        return None
    return d.quantize(Decimal("0.01"))


def _compute_hours(arrived: str | None, left: str | None, lunch: Decimal | None) -> Decimal | None:
    """computed = (left - arrived) - lunch, in hours. None if not computable."""
    if not arrived or not left:
        return None
    a, lv = _time_to_minutes(arrived), _time_to_minutes(left)
    if lv < a:  # overnight is implausible for a day log -> can't trust it
        return None
    span = Decimal(lv - a) / Decimal(60)
    worked = span - (lunch or Decimal(0))
    if worked < 0:  # lunch longer than the on-site span -> invalid
        return None
    return worked.quantize(Decimal("0.01"))


def _normalize_date(raw: Any) -> _date_type | None:
    """Parse a date cell into a date. ISO first (the model emits ISO), then a
    few common North-American fallbacks. None if unparseable (never guesses)."""
    if raw is None:
        return None
    s = str(raw).strip()
    if not s:
        return None
    try:
        return _date_type.fromisoformat(s[:10])
    except ValueError:
        pass
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    return None


@dataclass
class ValidatedRow:
    row_index: int | None
    work_date: _date_type | None
    employee_name_raw: str | None
    time_arrived: str | None
    time_left: str | None
    lunch_hours: Decimal | None
    total_hours_reported: Decimal | None
    total_hours_computed: Decimal | None
    hours_mismatch: bool
    supervisor_signature_present: bool
    confidence: float | None
    missing_fields: list[str]
    raw_notes: str | None
    is_blank: bool


def _validate_row(row: dict[str, Any]) -> ValidatedRow:
    """Normalise + cross-check one extracted row. Pure; never raises."""
    work_date = _normalize_date(row.get("date"))
    name = (str(row.get("name")).strip() if row.get("name") is not None else "") or None
    arrived = _normalize_time(row.get("time_arrived"))
    left = _normalize_time(row.get("time_left"))
    lunch = _to_decimal(row.get("lunch_hours"))
    reported = _to_decimal(row.get("total_hours_reported"))
    computed = _compute_hours(arrived, left, lunch)

    mismatch = (
        reported is not None
        and computed is not None
        and abs(reported - computed) > _HOURS_TOLERANCE
    )

    missing = [
        f
        for f, v in (
            ("date", work_date),
            ("name", name),
            ("time_arrived", arrived),
            ("time_left", left),
        )
        if v is None
    ]
    if reported is None and computed is None:
        missing.append("total_hours")

    is_blank = (
        name is None
        and arrived is None
        and left is None
        and reported is None
        and work_date is None
        and lunch is None
    )

    try:
        conf = float(row.get("confidence")) if row.get("confidence") is not None else None
    except (TypeError, ValueError):
        conf = None

    raw_notes = (str(row.get("raw_notes")).strip() if row.get("raw_notes") else "") or None
    ri = row.get("row_index")
    try:
        ri = int(ri) if ri is not None else None
    except (TypeError, ValueError):
        ri = None

    return ValidatedRow(
        row_index=ri,
        work_date=work_date,
        employee_name_raw=name,
        time_arrived=arrived,
        time_left=left,
        lunch_hours=lunch,
        total_hours_reported=reported,
        total_hours_computed=computed,
        hours_mismatch=mismatch,
        supervisor_signature_present=bool(row.get("supervisor_signature_present")),
        confidence=conf,
        missing_fields=missing,
        raw_notes=raw_notes,
        is_blank=is_blank,
    )


# ---------------------------------------------------------------------------
# Resolution (site->project, name->Worker) -- conservative, never forced
# ---------------------------------------------------------------------------


def _resolve_site_project(
    session: Session, site_name_raw: str | None, project_hint: Any
) -> tuple[Any, str | None]:
    """Return (project_id, resolved_name). Site name wins; else the hint.

    Substring match (case-insensitive) over Project.name -- same simple rule the
    email-intake plus-address routing uses. Returns (None, None) if unresolved.
    """
    if site_name_raw and site_name_raw.strip():
        frag = site_name_raw.strip().lower()
        projects = session.query(Project).filter(Project.name.isnot(None)).all()
        for proj in projects:
            pname = (proj.name or "").lower()
            if frag in pname or pname in frag:
                return proj.canonical_id, proj.name
    if project_hint is not None:
        try:
            pid = uuid.UUID(str(project_hint))
        except (ValueError, TypeError):
            return None, None
        proj = session.query(Project).filter_by(canonical_id=pid).one_or_none()
        if proj is not None:
            return proj.canonical_id, proj.name
    return None, None


def _resolve_employee(session: Session, name_raw: str | None) -> tuple[Any, str, float | None]:
    """Return (worker_id, method, confidence). Exact + alias only (MVP).

    Fuzzy matching is deliberately NOT done here: a wrong employee link is worse
    than an unresolved row (docs/PROJECT_LOG_INGESTION.md). Unmatched -> unresolved.
    """
    if not name_raw or not name_raw.strip():
        return None, "unresolved", None
    needle = name_raw.strip().lower()

    for w in session.query(Worker).all():
        if (w.display_name or "").strip().lower() == needle:
            return w.canonical_id, "exact", 1.0

    alias = session.query(WorkerAlias).filter(WorkerAlias.alias_text.isnot(None)).all()
    for a in alias:
        if (a.alias_text or "").strip().lower() == needle:
            return a.worker_id, "alias", (a.confidence if a.confidence is not None else 0.9)

    return None, "unresolved", None


# ---------------------------------------------------------------------------
# Result containers
# ---------------------------------------------------------------------------


@dataclass
class ProjectLogResult:
    """Outcome of ingesting ONE attachment as a (possible) project log."""

    handled: bool = False  # True = claimed as a project log (do NOT field-note it)
    submission: ProjectLogSubmission | None = None
    entries: list[ProjectLogEntry] = field(default_factory=list)
    ingestion_status: str | None = None
    ingestion_reason: str | None = None
    duplicate: bool = False
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    @property
    def entry_count(self) -> int:
        return len(self.entries)


@dataclass
class ProjectLogEmailBatch:
    """Outcome of scanning one email's attachments for project logs."""

    results: list[ProjectLogResult] = field(default_factory=list)

    @property
    def any_project_log(self) -> bool:
        """True if ANY attachment was claimed as a project log (parsed OR
        quarantined-as-project-log) -- so the caller skips field-note extraction."""
        return any(r.handled for r in self.results)

    @property
    def total_entries(self) -> int:
        return sum(r.entry_count for r in self.results)


# ---------------------------------------------------------------------------
# Service: ingest one attachment / one email
# ---------------------------------------------------------------------------


def ingest_project_log(
    session: Session,
    extractor: ProjectLogExtractor,
    *,
    image_path: str | None = None,
    attachment_filename: str | None = None,
    attachment_hash: str | None = None,
    source_email_message_id: str | None = None,
    email_ingest_id: Any = None,
    received_at: datetime | None = None,
    project_hint: Any = None,
    classify_threshold: float = _DEFAULT_CLASSIFY_THRESHOLD,
) -> ProjectLogResult:
    """Classify one attachment; if it's a project log, write submission+entries.

    Flushes but does not commit (caller owns the transaction), matching
    ``ingest_field_note``. Idempotent on (source_email_message_id,
    attachment_hash): a re-sent attachment replaces the prior submission+entries.

    ``handled`` is True when we claim the attachment (parsed OR quarantined as a
    project log); the caller then skips the field-note path for that email.
    """
    result = ProjectLogResult()

    if attachment_hash is None and image_path:
        attachment_hash = _sha256_file(image_path)
    if attachment_filename is None and image_path:
        attachment_filename = os.path.basename(image_path)

    # --- classify + extract (one vision call) ---
    try:
        raw = extractor.extract(image_paths=[image_path] if image_path else [])
    except ProjectLogExtractorError as exc:
        result.errors.append(f"extraction failed: {exc}")
        return result  # handled stays False -> caller may field-note / skip

    doc_type = raw.get("document_type")
    if doc_type != "project_log":
        # Not a project log -> let the field-note path handle this email.
        return result

    # From here we CLAIM this attachment as a project log.
    result.handled = True
    confidence = _coerce_float(raw.get("classification_confidence"))

    # --- idempotent replace of any prior submission for this attachment ---
    _delete_prior_submission(session, source_email_message_id, attachment_hash, attachment_filename)

    site_name_raw = (raw.get("site_name") or "").strip() or None
    project_id, resolved_name = _resolve_site_project(session, site_name_raw, project_hint)
    eid = _uuid_or_none(email_ingest_id)
    now = datetime.utcnow()

    submission = ProjectLogSubmission(
        canonical_id=uuid.uuid4(),
        project_id=project_id,
        email_ingest_id=eid,
        site_name_raw=site_name_raw,
        site_name_resolved=resolved_name,
        source_email_message_id=source_email_message_id,
        source_attachment_filename=attachment_filename,
        source_attachment_hash=attachment_hash,
        source_image_uri=image_path,
        received_at=received_at,
        processed_at=now,
        document_type="project_log",
        classification_method="vision_llm",
        classification_confidence=confidence,
        extractor_version=EXTRACTOR_VERSION,
        raw_extraction_json=json.dumps(raw),
        ingestion_status="parsed",
    )

    # --- decide status: confidence gate, then content checks ---
    if confidence is not None and confidence < classify_threshold:
        submission.ingestion_status = "quarantined"
        submission.ingestion_reason = "low_confidence_project_log_classification"
        session.add(submission)
        session.flush()
        result.submission = submission
        result.ingestion_status = submission.ingestion_status
        result.ingestion_reason = submission.ingestion_reason
        result.warnings.append("classification confidence below threshold; quarantined")
        return result

    # Validate rows; drop blanks.
    validated = [_validate_row(r) for r in (raw.get("rows") or [])]
    filled = [v for v in validated if not v.is_blank]

    if not validated:
        submission.ingestion_status = "skipped"
        submission.ingestion_reason = "no_rows_detected"
    elif not filled:
        submission.ingestion_status = "skipped"
        submission.ingestion_reason = "empty_form"
    elif project_id is None:
        # Per spec: keep the raw extraction + rows, but quarantine for routing.
        submission.ingestion_status = "quarantined"
        submission.ingestion_reason = "unknown_site"

    session.add(submission)
    session.flush()
    result.submission = submission

    # Write entries even when quarantined for unknown_site (preserve raw data).
    if filled and submission.ingestion_reason != "empty_form":
        for v in filled:
            wid, method, match_conf = _resolve_employee(session, v.employee_name_raw)
            entry = ProjectLogEntry(
                canonical_id=uuid.uuid4(),
                submission_id=submission.canonical_id,
                project_id=project_id,
                site_name_raw=site_name_raw,
                site_name_resolved=resolved_name,
                work_date=v.work_date,
                employee_name_raw=v.employee_name_raw,
                employee_id=wid,
                employee_match_confidence=match_conf,
                employee_match_method=method,
                time_arrived=v.time_arrived,
                time_left=v.time_left,
                lunch_hours=v.lunch_hours,
                total_hours_reported=v.total_hours_reported,
                total_hours_computed=v.total_hours_computed,
                hours_mismatch=v.hours_mismatch,
                supervisor_signature_present=v.supervisor_signature_present,
                row_index=v.row_index,
                confidence=v.confidence,
                missing_fields_json=json.dumps(v.missing_fields) if v.missing_fields else None,
                source_meta_json=json.dumps({"raw_notes": v.raw_notes}) if v.raw_notes else None,
            )
            session.add(entry)
            result.entries.append(entry)
        session.flush()

    result.ingestion_status = submission.ingestion_status
    result.ingestion_reason = submission.ingestion_reason
    return result


def ingest_project_logs_from_email(
    session: Session,
    extractor: ProjectLogExtractor,
    image_paths: list[str],
    *,
    source_email_message_id: str | None = None,
    email_ingest_id: Any = None,
    received_at: datetime | None = None,
    project_hint: Any = None,
    classify_threshold: float = _DEFAULT_CLASSIFY_THRESHOLD,
) -> ProjectLogEmailBatch:
    """Scan an email's image attachments; ingest any that are project logs.

    Returns a batch whose ``any_project_log`` tells the caller whether to skip
    the field-note path for this email.
    """
    batch = ProjectLogEmailBatch()
    for path in image_paths or []:
        res = ingest_project_log(
            session,
            extractor,
            image_path=path,
            source_email_message_id=source_email_message_id,
            email_ingest_id=email_ingest_id,
            received_at=received_at,
            project_hint=project_hint,
            classify_threshold=classify_threshold,
        )
        batch.results.append(res)
    return batch


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------


def _delete_prior_submission(
    session: Session,
    message_id: str | None,
    attachment_hash: str | None,
    attachment_filename: str | None,
) -> None:
    """Idempotency: remove any prior submission (+entries) for THIS attachment.

    The dedup key is the attachment, not the email -- an email can carry several
    project-log sheets. Match on the content hash (+message_id when present); if
    no hash is available, fall back to (message_id AND filename). NEVER match on
    message_id alone, or a second attachment would delete its siblings.
    """
    q = session.query(ProjectLogSubmission)
    if attachment_hash:
        q = q.filter(ProjectLogSubmission.source_attachment_hash == attachment_hash)
        if message_id:
            q = q.filter(ProjectLogSubmission.source_email_message_id == message_id)
    elif message_id and attachment_filename:
        q = q.filter(
            ProjectLogSubmission.source_email_message_id == message_id,
            ProjectLogSubmission.source_attachment_filename == attachment_filename,
        )
    else:
        return  # not enough to safely identify a prior copy
    for prior in q.all():
        session.query(ProjectLogEntry).filter(
            ProjectLogEntry.submission_id == prior.canonical_id
        ).delete(synchronize_session="fetch")
        session.delete(prior)
    session.flush()


def _coerce_float(v: Any) -> float | None:
    try:
        return float(v) if v is not None else None
    except (TypeError, ValueError):
        return None


def _uuid_or_none(val: Any) -> Any:
    if val is None:
        return None
    try:
        return uuid.UUID(str(val))
    except (ValueError, TypeError):
        return None
