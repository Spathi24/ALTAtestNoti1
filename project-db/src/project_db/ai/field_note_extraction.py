"""Field-note extraction: classify a plain-language site note into structured signals.

Pipeline (all in one call, A5 -- logic lives here, consumed by CLI + web):

  1. Caller supplies the raw note text + the project's task list (fetched by
     the service function).
  2. A single structured-output LLM call returns an array of signals.  Each
     signal carries: classification vocab, verbatim quoted_excerpt (A6),
     task_index (0-based into the supplied list; null if no match), optional
     proposed_status / proposed dates / new_task_title, optional labor capture,
     confidence.
  3. ``ingest_field_note`` persists each signal as a FieldNote row then emits
     Proposal rows for actionable signals:
       task_done / task_progress / blocker  ->  field_name="task_status"
       date_shift (with dates)              ->  field_name="timeline"
       new_task                             ->  field_name="new_task" (advisory)
       scope_change                         ->  field_name="scope_change" (advisory)
       other                                ->  no Proposal

Conservative posture (A7/N1): the model must cite verbatim evidence (A6).
A note that cannot be confidently classified yields NoteClass.OTHER with no
Proposal.  A declined task match is correct behavior (not a failure) -- it
signals a potential new_task.  No auto-apply under any circumstances (A1).

Task indexing mirrors proposals.py: tasks are passed by INTEGER INDEX so the
model cannot subtly miscopy a 36-char UUID.  The service maps index -> id.
"""
from __future__ import annotations

import json
import logging
import os
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from project_db.db.models import (
    FieldNote,
    NoteChannel,
    NoteClass,
    Proposal,
    ProposalStatus,
    Task,
)

logger = logging.getLogger(__name__)

FIELD_NOTE_PROMPT_VERSION = "field-note-v1"

# ---------------------------------------------------------------------------
# Strict JSON schema for structured outputs
# ---------------------------------------------------------------------------

_CLASSIFICATION_VOCAB = [
    "task_done", "task_progress", "blocker",
    "new_task", "date_shift", "scope_change", "other",
]

FIELD_NOTE_SCHEMA: dict[str, Any] = {
    "name": "field_note_extraction",
    "strict": True,
    "schema": {
        "type": "object",
        "additionalProperties": False,
        "required": ["signals"],
        "properties": {
            "signals": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": [
                        "classification", "quoted_excerpt", "task_index",
                        "proposed_status", "proposed_start_date",
                        "proposed_end_date", "new_task_title",
                        "workers", "hours_worked", "confidence",
                    ],
                    "properties": {
                        "classification": {
                            "type": "string",
                            "enum": _CLASSIFICATION_VOCAB,
                            "description": (
                                "task_done: a task was completed.  "
                                "task_progress: work is ongoing.  "
                                "blocker: something is stuck or blocked.  "
                                "new_task: work not in the plan was mentioned.  "
                                "date_shift: a schedule change is implied.  "
                                "scope_change: a scope addition or change.  "
                                "other: does not fit any category."
                            ),
                        },
                        "quoted_excerpt": {
                            "type": "string",
                            "description": "Verbatim phrase from the note that supports this classification (A6).",
                        },
                        "task_index": {
                            "type": ["integer", "null"],
                            "description": (
                                "0-based index into the supplied TASK LIST.  "
                                "null if no specific task matches (e.g. new_task, "
                                "scope_change, or genuinely ambiguous)."
                            ),
                        },
                        "proposed_status": {
                            "type": ["string", "null"],
                            "description": (
                                "Monday status label to set when classification is "
                                "task_done / task_progress / blocker.  "
                                "Use 'Done', 'In Progress', or 'Blocked'.  "
                                "null for all other classifications."
                            ),
                        },
                        "proposed_start_date": {
                            "type": ["string", "null"],
                            "description": "ISO date yyyy-mm-dd for a new start date; null if not mentioned.",
                        },
                        "proposed_end_date": {
                            "type": ["string", "null"],
                            "description": "ISO date yyyy-mm-dd for a new end date; null if not mentioned.",
                        },
                        "new_task_title": {
                            "type": ["string", "null"],
                            "description": "Brief title for a new task; only set when classification=new_task.",
                        },
                        "workers": {
                            "type": ["string", "null"],
                            "description": "Comma-separated worker names mentioned in the note; null if none.",
                        },
                        "hours_worked": {
                            "type": ["number", "null"],
                            "description": "Total hours mentioned; null if not stated.",
                        },
                        "confidence": {
                            "type": "number",
                            "description": "Extraction confidence in [0, 1].",
                        },
                    },
                },
            },
        },
    },
}


def _system_prompt() -> str:
    return (
        "You are a construction-site note analyst.  A field worker or PM sends "
        "a short plain-language report of what happened on site.  Your job:\n\n"
        "1. Read the note carefully.\n"
        "2. Split it into discrete SIGNALS -- each signal is one event or "
        "observation (one note often contains several).\n"
        "3. For each signal, fill the structured schema:\n"
        "   - classification: one of the vocab values.\n"
        "   - quoted_excerpt: copy the EXACT words from the note that prove "
        "the classification (do not paraphrase).\n"
        "   - task_index: the 0-based index of the BEST matching task from "
        "the provided TASK LIST, or null if no task matches or if "
        "classification is new_task / scope_change / other.\n"
        "   - proposed_status: 'Done', 'In Progress', or 'Blocked' for status "
        "signals; null otherwise.\n"
        "   - proposed_start_date / proposed_end_date: ISO dates only if the "
        "note implies a schedule change; null otherwise.\n"
        "   - new_task_title: a short imperative title only for new_task; null "
        "otherwise.\n"
        "   - workers / hours_worked: fill only when the note mentions them.\n"
        "   - confidence: your confidence in this signal [0.0, 1.0].\n\n"
        "CONSERVATIVE RULES:\n"
        "- Return no signals (empty array) if the note is too vague to classify.\n"
        "- A declined task match (null task_index) is fine -- do not guess.\n"
        "- Never invent information not present in the note.\n"
        "- Every signal MUST have a non-empty quoted_excerpt."
    )


# ---------------------------------------------------------------------------
# Extractor providers
# ---------------------------------------------------------------------------


class FieldNoteExtractorError(RuntimeError):
    pass


class FieldNoteExtractor(ABC):
    name = "abstract"

    @abstractmethod
    def extract(self, *, note_text: str, task_lines: list[str]) -> dict[str, Any]:
        """Return a dict conforming to FIELD_NOTE_SCHEMA's schema."""
        raise NotImplementedError


class OpenAIFieldNoteExtractor(FieldNoteExtractor):
    """Real extractor via OpenAI structured outputs."""

    name = "openai-field-note"

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
            raise FieldNoteExtractorError(
                "OPENAI_API_KEY is not set (needed for field-note extraction)."
            )
        try:
            from openai import OpenAI
        except ImportError as exc:  # pragma: no cover
            raise FieldNoteExtractorError("openai package not installed") from exc
        self._client = OpenAI(api_key=key, base_url=base_url, timeout=timeout_seconds)

    def extract(self, *, note_text: str, task_lines: list[str]) -> dict[str, Any]:
        task_block = "\n".join(
            f"[{i}] {title}" for i, title in enumerate(task_lines)
        ) if task_lines else "(no tasks found for this project)"
        user = (
            f"TASK LIST (0-based index):\n{task_block}\n\n"
            f"FIELD NOTE:\n{note_text}"
        )
        try:
            resp = self._client.chat.completions.create(
                model=self.model,
                temperature=0,
                messages=[
                    {"role": "system", "content": _system_prompt()},
                    {"role": "user", "content": user},
                ],
                response_format={"type": "json_schema", "json_schema": FIELD_NOTE_SCHEMA},
            )
        except Exception as exc:  # noqa: BLE001
            raise FieldNoteExtractorError(f"OpenAI extraction call failed: {exc}") from exc
        msg = resp.choices[0].message
        if getattr(msg, "refusal", None):
            raise FieldNoteExtractorError(f"model refused: {msg.refusal}")
        try:
            return json.loads(msg.content)
        except (json.JSONDecodeError, TypeError) as exc:
            raise FieldNoteExtractorError(f"bad JSON despite strict schema: {exc}") from exc


class MockFieldNoteExtractor(FieldNoteExtractor):
    """Deterministic extractor for tests: returns canned responses in order."""

    name = "mock-field-note"

    def __init__(self, responses: list[dict[str, Any]] | None = None) -> None:
        self._responses = list(responses or [])
        self._idx = 0
        self.calls: list[tuple[str, list[str]]] = []

    def extract(self, *, note_text: str, task_lines: list[str]) -> dict[str, Any]:
        self.calls.append((note_text, task_lines))
        if self._idx < len(self._responses):
            r = self._responses[self._idx]
            self._idx += 1
            return r
        return {"signals": []}


# ---------------------------------------------------------------------------
# Service function (A5: logic here, consumed by CLI + web identically)
# ---------------------------------------------------------------------------


@dataclass
class FieldNoteBatch:
    """Outcome of one field-note ingest run."""
    project_id: str
    raw_text: str
    field_notes: list[FieldNote] = field(default_factory=list)
    proposals: list[Proposal] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    skipped_reason: str | None = None

    @property
    def signal_count(self) -> int:
        return len(self.field_notes)

    @property
    def proposal_count(self) -> int:
        return len(self.proposals)

    def summary(self) -> str:
        if self.skipped_reason:
            return f"[field-note] skipped -- {self.skipped_reason}"
        return (
            f"[field-note] {self.signal_count} signal(s) extracted, "
            f"{self.proposal_count} proposal(s) created"
            + (f", {len(self.errors)} error(s)" if self.errors else "")
        )


def _clamp_conf(v: Any) -> float:
    try:
        return max(0.0, min(1.0, float(v)))
    except (TypeError, ValueError):
        return 0.5


def _parse_date_str(v: Any):
    """Return a date from an ISO string, or None."""
    if not v or not isinstance(v, str):
        return None
    try:
        from datetime import date
        return date.fromisoformat(v[:10])
    except (ValueError, AttributeError):
        return None


def _supersede_prior(session: Session, entity_type: str, entity_id: Any, field_name: str) -> int:
    """Mark prior PENDING proposals for the same target as SUPERSEDED."""
    count = 0
    prior = (
        session.query(Proposal)
        .filter_by(
            entity_type=entity_type,
            entity_id=entity_id,
            field_name=field_name,
            status=ProposalStatus.PENDING,
        )
        .all()
    )
    for p in prior:
        p.status = ProposalStatus.SUPERSEDED
        count += 1
    return count


def ingest_field_note(
    session: Session,
    extractor: FieldNoteExtractor,
    project_id: Any,
    raw_text: str,
    *,
    channel: NoteChannel = NoteChannel.CLI,
    sender_ref: str | None = None,
) -> FieldNoteBatch:
    """Classify a field note, persist signals + proposals.  The entry point for
    CLI and web (A5).  Flushes but does not commit -- caller owns the transaction.

    Returns a FieldNoteBatch with the created FieldNote and Proposal rows.
    """
    from project_db.db.models import Project

    pid: Any
    try:
        pid = uuid.UUID(str(project_id))
    except (ValueError, TypeError):
        pid = project_id

    batch = FieldNoteBatch(project_id=str(pid), raw_text=raw_text)

    project = session.query(Project).filter_by(canonical_id=pid).one_or_none()
    if project is None:
        batch.skipped_reason = f"project {pid} not found"
        return batch

    if not raw_text or not raw_text.strip():
        batch.skipped_reason = "empty note"
        return batch

    # Fetch task list for this project (for task matching by index).
    tasks: list[Task] = (
        session.query(Task)
        .filter_by(project_id=pid)
        .order_by(Task.created_at)
        .all()
    )
    task_lines = [t.title for t in tasks]
    task_ids = [t.canonical_id for t in tasks]

    # One structured-output call: classify + match tasks.
    try:
        result = extractor.extract(note_text=raw_text.strip(), task_lines=task_lines)
    except FieldNoteExtractorError as exc:
        batch.errors.append(f"extraction failed: {exc}")
        return batch

    signals = result.get("signals") or []
    if not signals:
        batch.skipped_reason = "extractor returned no signals (note too vague)"
        return batch

    received_at = datetime.utcnow()

    for sig in signals:
        try:
            _process_signal(
                session, batch, sig, pid, raw_text,
                channel, sender_ref, received_at,
                task_ids, task_lines,
            )
        except Exception as exc:  # noqa: BLE001
            batch.errors.append(f"signal processing error: {exc}")

    session.flush()
    return batch


def _process_signal(
    session: Session,
    batch: FieldNoteBatch,
    sig: dict[str, Any],
    project_id: Any,
    raw_text: str,
    channel: NoteChannel,
    sender_ref: str | None,
    received_at: datetime,
    task_ids: list,
    task_lines: list[str],
) -> None:
    """Persist one signal as a FieldNote row and (if actionable) a Proposal."""
    raw_class = sig.get("classification", "other")
    try:
        note_class = NoteClass(raw_class)
    except ValueError:
        note_class = NoteClass.OTHER

    quoted = (sig.get("quoted_excerpt") or "").strip()
    if not quoted:
        batch.errors.append(
            f"signal {raw_class!r} has no quoted_excerpt -- skipped (A6)"
        )
        return

    conf = _clamp_conf(sig.get("confidence", 0.5))

    # Resolve task_index -> canonical Task id.
    task_idx = sig.get("task_index")
    matched_task_id = None
    if task_idx is not None:
        try:
            idx = int(task_idx)
            if 0 <= idx < len(task_ids):
                matched_task_id = task_ids[idx]
            else:
                batch.errors.append(
                    f"task_index {idx} out of range (0..{len(task_ids)-1}) -- match declined"
                )
        except (TypeError, ValueError):
            batch.errors.append(f"invalid task_index {task_idx!r} -- match declined")

    workers_raw = sig.get("workers")
    hours_raw = sig.get("hours_worked")
    try:
        hours = float(hours_raw) if hours_raw is not None else None
    except (TypeError, ValueError):
        hours = None

    fn = FieldNote(
        raw_text=raw_text,
        received_at=received_at,
        channel=channel,
        sender_ref=sender_ref,
        project_id=project_id,
        classification=note_class,
        quoted_excerpt=quoted,
        workers=(str(workers_raw).strip() if workers_raw else None),
        hours_worked=hours,
        matched_task_id=matched_task_id,
        confidence=conf,
    )
    session.add(fn)
    batch.field_notes.append(fn)

    # Create Proposal rows for actionable signals.
    _maybe_create_proposal(
        session, batch, sig, note_class, fn, project_id, matched_task_id,
        task_ids, task_lines, conf, quoted,
    )


def _maybe_create_proposal(
    session: Session,
    batch: FieldNoteBatch,
    sig: dict[str, Any],
    note_class: NoteClass,
    fn: FieldNote,
    project_id: Any,
    matched_task_id: Any,
    task_ids: list,
    task_lines: list[str],
    conf: float,
    quoted: str,
) -> None:
    """Emit a Proposal for actionable signals (A1: always PENDING, never auto-apply)."""

    source_ref = json.dumps([str(fn.canonical_id)])

    if note_class in (NoteClass.TASK_DONE, NoteClass.TASK_PROGRESS, NoteClass.BLOCKER):
        if matched_task_id is None:
            batch.errors.append(
                f"{note_class.value} signal has no matched task -- no Proposal created "
                f"(hint: submit again naming the task explicitly)"
            )
            return
        proposed_status = (sig.get("proposed_status") or "").strip() or None
        if not proposed_status:
            _default = {"task_done": "Done", "task_progress": "In Progress", "blocker": "Blocked"}
            proposed_status = _default.get(note_class.value, "In Progress")

        # Canonical TaskStatus mirror for the proposed_value.
        _status_map = {"Done": "DONE", "In Progress": "IN_PROGRESS", "Blocked": "BLOCKED"}
        canonical_status = _status_map.get(proposed_status, "IN_PROGRESS")

        proposed_value = json.dumps({
            "status": canonical_status,
            "monday_label": proposed_status,
        })

        # A2/A3: supersede prior PENDING task_status proposals for same target.
        _supersede_prior(session, "Task", matched_task_id, "task_status")

        p = Proposal(
            entity_type="Task",
            entity_id=matched_task_id,
            field_name="task_status",
            proposed_value=proposed_value,
            confidence=conf,
            source_doc_ids=source_ref,
            prompt_version=FIELD_NOTE_PROMPT_VERSION,
            status=ProposalStatus.PENDING,
        )
        session.add(p)
        batch.proposals.append(p)

    elif note_class == NoteClass.DATE_SHIFT:
        start = _parse_date_str(sig.get("proposed_start_date"))
        end = _parse_date_str(sig.get("proposed_end_date"))
        if start is None and end is None:
            batch.errors.append(
                "date_shift signal has no parseable dates -- no timeline Proposal created"
            )
            return
        if matched_task_id is None:
            batch.errors.append(
                "date_shift signal has no matched task -- no timeline Proposal created"
            )
            return

        proposed_value = json.dumps({
            "start_date": start.isoformat() if start else None,
            "end_date": end.isoformat() if end else None,
            "evidence": quoted,
        })
        _supersede_prior(session, "Task", matched_task_id, "timeline")
        p = Proposal(
            entity_type="Task",
            entity_id=matched_task_id,
            field_name="timeline",
            proposed_value=proposed_value,
            confidence=conf,
            source_doc_ids=source_ref,
            prompt_version=FIELD_NOTE_PROMPT_VERSION,
            status=ProposalStatus.PENDING,
        )
        session.add(p)
        batch.proposals.append(p)

    elif note_class == NoteClass.NEW_TASK:
        title = (sig.get("new_task_title") or "").strip() or "(untitled new task)"
        proposed_value = json.dumps({
            "title": title,
            "evidence": quoted,
        })
        p = Proposal(
            entity_type="Project",
            entity_id=project_id,
            field_name="new_task",
            proposed_value=proposed_value,
            confidence=conf,
            source_doc_ids=source_ref,
            prompt_version=FIELD_NOTE_PROMPT_VERSION,
            status=ProposalStatus.PENDING,
        )
        session.add(p)
        batch.proposals.append(p)

    elif note_class == NoteClass.SCOPE_CHANGE:
        proposed_value = json.dumps({"description": quoted})
        p = Proposal(
            entity_type="Project",
            entity_id=project_id,
            field_name="scope_change",
            proposed_value=proposed_value,
            confidence=conf,
            source_doc_ids=source_ref,
            prompt_version=FIELD_NOTE_PROMPT_VERSION,
            status=ProposalStatus.PENDING,
        )
        session.add(p)
        batch.proposals.append(p)

    # NoteClass.OTHER produces no Proposal -- the note is logged but not actioned.
