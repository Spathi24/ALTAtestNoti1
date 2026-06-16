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

Task list rendering (Strategy C):
  Tasks are grouped by operational status (Active → Upcoming → Done) and
  sorted within each group by a composite relevance score:
    50% status weight  (Active tasks surface first regardless of other factors)
    30% keyword-semantic overlap  (note text vs task title, no API call)
    20% temporal proximity  (date distance from today; 0.5 neutral for undated)
  The Done section is trimmed to ``_DONE_TRIM_K`` entries by relevance when
  large.  Sub-tasks carry a parent annotation so the model understands
  hierarchy without the parent needing to appear adjacent.
"""

from __future__ import annotations

import json
import logging
import os
import re
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import date as _date_type
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

FIELD_NOTE_PROMPT_VERSION = "field-note-v3"

# ---------------------------------------------------------------------------
# Image helpers (Win 3 -- photos through the same pipe)
# ---------------------------------------------------------------------------

_IMAGE_EXTS: frozenset[str] = frozenset({".jpg", ".jpeg", ".png", ".webp", ".gif"})
_MIME_BY_EXT: dict[str, str] = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".webp": "image/webp",
    ".gif": "image/gif",
}
_MAX_IMAGE_BYTES = 10 * 1024 * 1024  # 10 MB


def _load_image_b64(path: str) -> str | None:
    """Read an image file and return a data-URL string, or None if unsupported/oversized."""
    import base64 as _base64

    ext = os.path.splitext(path)[1].lower()
    if ext not in _IMAGE_EXTS:
        logger.debug("[field-note] %s is not a supported image type -- skipped", path)
        return None
    try:
        size = os.path.getsize(path)
    except OSError:
        logger.warning("[field-note] cannot stat image %s -- skipped", path)
        return None
    if size > _MAX_IMAGE_BYTES:
        logger.warning(
            "[field-note] image %s (%d bytes) exceeds 10 MB limit -- skipped", path, size
        )
        return None
    try:
        with open(path, "rb") as fh:
            data = fh.read()
        mime = _MIME_BY_EXT.get(ext, "image/jpeg")
        return f"data:{mime};base64,{_base64.b64encode(data).decode()}"
    except OSError as exc:
        logger.warning("[field-note] cannot read image %s: %s -- skipped", path, exc)
        return None


# ---------------------------------------------------------------------------
# Task-block scoring: status x semantic x temporal composite
# ---------------------------------------------------------------------------

_STOPWORDS: frozenset[str] = frozenset(
    {
        "the",
        "a",
        "an",
        "and",
        "or",
        "of",
        "to",
        "in",
        "for",
        "on",
        "at",
        "is",
        "was",
        "be",
        "been",
        "have",
        "has",
        "do",
        "did",
        "will",
        "with",
        "this",
        "that",
        "it",
        "its",
        "by",
        "from",
        "are",
        "not",
        "no",
        "as",
        "we",
        "they",
        "he",
        "she",
        "my",
        "our",
        "so",
        "if",
        "but",
        "up",
    }
)

_ACTIVE_LABELS: frozenset[str] = frozenset(
    {"working on it", "in progress", "in_progress", "stuck", "blocked"}
)
_DONE_LABELS: frozenset[str] = frozenset({"done", "complete", "completed"})

_STATUS_SCORES: dict[str, float] = {
    "Working on it": 1.00,
    "In Progress": 1.00,
    "Stuck": 0.95,
    "Blocked": 0.95,
    "TODO": 0.55,
    "On Hold": 0.45,
    "Future steps": 0.40,
    "Done": 0.10,
}

_DONE_TRIM_K = 30


def _keyword_tokens(text: str) -> frozenset[str]:
    return frozenset(
        w for w in re.findall(r"[a-z]+", (text or "").lower()) if w not in _STOPWORDS and len(w) > 2
    )


def _task_status_label(task: Task) -> str:
    return task.monday_status_label or (
        task.status.value if hasattr(task.status, "value") else str(task.status or "TODO")
    )


def _task_status_score(task: Task) -> float:
    label = _task_status_label(task)
    # Canonical enum values ("IN_PROGRESS", "DONE", "BLOCKED") map via aliases.
    _aliases = {"IN_PROGRESS": "Working on it", "DONE": "Done", "BLOCKED": "Stuck", "TODO": "TODO"}
    resolved = _aliases.get(label, label)
    return _STATUS_SCORES.get(resolved, 0.30)


def _task_temporal_score(task: Task, today: _date_type) -> float:
    """Proximity of the task's dates to today.  0.5 for undated (neutral)."""
    dates = [d for d in [task.start_date, task.end_date] if d]
    if hasattr(task, "due_date") and task.due_date:
        dates.append(task.due_date)
    if not dates:
        return 0.5
    min_days = min(abs((d - today).days) for d in dates)
    if min_days <= 7:
        return 1.00
    if min_days <= 14:
        return 0.85
    if min_days <= 30:
        return 0.65
    if min_days <= 60:
        return 0.45
    if min_days <= 90:
        return 0.30
    return 0.15


def _task_semantic_score(task: Task, note_tokens: frozenset[str]) -> float:
    """Keyword recall: fraction of task-title tokens present in the note."""
    task_tokens = _keyword_tokens(task.title or "")
    if not task_tokens or not note_tokens:
        return 0.0
    return len(task_tokens & note_tokens) / len(task_tokens)


def _task_composite(task: Task, note_tokens: frozenset[str], today: _date_type) -> float:
    return (
        0.50 * _task_status_score(task)
        + 0.30 * _task_semantic_score(task, note_tokens)
        + 0.20 * _task_temporal_score(task, today)
    )


def _task_bucket(task: Task) -> str:
    label = _task_status_label(task).lower()
    if label in _ACTIVE_LABELS:
        return "active"
    if label in _DONE_LABELS:
        return "done"
    # Canonical enum fallback
    if task.status is not None:
        val = (task.status.value if hasattr(task.status, "value") else str(task.status)).upper()
        if val in ("IN_PROGRESS", "BLOCKED"):
            return "active"
        if val == "DONE":
            return "done"
    return "upcoming"


def _render_task_block(
    tasks: list[Task],
    note_text: str,
    *,
    today: _date_type | None = None,
    done_trim_k: int = _DONE_TRIM_K,
) -> tuple[str, list]:
    """Build a status-stratified, relevance-sorted task block for the LLM prompt.

    Groups: Active (Working on it / Stuck) → Upcoming (TODO / Future steps /
    On Hold) → Completed (Done, trimmed to done_trim_k by composite score).
    Within each group, ordered by composite score (status 50%, keyword-semantic
    30%, temporal 20%).  Subitems annotated with parent name + status for
    disambiguation.  Indices are 0-based and contiguous across all sections.

    Returns (rendered_str, task_ids) where task_ids[i] is the canonical_id of
    the task at index i.  Section header lines are not indexed.
    """
    if not tasks:
        return "(no tasks found for this project)", []

    if today is None:
        today = _date_type.today()

    note_tokens = _keyword_tokens(note_text)
    by_id = {t.canonical_id: t for t in tasks}

    active: list[Task] = []
    upcoming: list[Task] = []
    done: list[Task] = []
    for t in tasks:
        b = _task_bucket(t)
        if b == "active":
            active.append(t)
        elif b == "done":
            done.append(t)
        else:
            upcoming.append(t)

    def sort_key(t: Task) -> tuple:
        return (-_task_composite(t, note_tokens, today), str(t.created_at or ""))

    active.sort(key=sort_key)
    upcoming.sort(key=sort_key)
    done.sort(key=sort_key)

    trimmed = 0
    if len(done) > done_trim_k:
        trimmed = len(done) - done_trim_k
        done = done[:done_trim_k]

    def parent_note(t: Task) -> str:
        if not t.is_subitem or t.parent_task_id is None:
            return ""
        parent = by_id.get(t.parent_task_id)
        if parent is None:
            return ""
        return f"  (parent: {parent.title or '?'} [{_task_status_label(parent)}])"

    lines: list[str] = []
    task_ids: list = []

    done_header = "COMPLETED — Done"
    if trimmed:
        done_header += f" (top {done_trim_k} of {done_trim_k + trimmed} by relevance)"

    sections = [
        ("ACTIVE — Working on it / Stuck", active),
        ("UPCOMING — TODO / Future steps / On Hold", upcoming),
        (done_header, done),
    ]
    for header, group in sections:
        if not group:
            continue
        lines.append(f"-- {header} --")
        for t in group:
            idx = len(task_ids)
            lines.append(f"[{idx}] {_task_context_line(t)}{parent_note(t)}")
            task_ids.append(t.canonical_id)

    return "\n".join(lines), task_ids


# ---------------------------------------------------------------------------
# Strict JSON schema for structured outputs
# ---------------------------------------------------------------------------

_CLASSIFICATION_VOCAB = [
    "task_done",
    "task_progress",
    "blocker",
    "new_task",
    "date_shift",
    "scope_change",
    "other",
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
                        "classification",
                        "quoted_excerpt",
                        "task_index",
                        "parent_task_index",
                        "proposed_status",
                        "proposed_start_date",
                        "proposed_end_date",
                        "new_task_title",
                        "workers",
                        "hours_worked",
                        "confidence",
                        "reasoning",
                    ],
                    "properties": {
                        "reasoning": {
                            "type": "string",
                            "description": (
                                "1-2 sentences explaining WHY you chose this "
                                "classification and which task you matched (if any). "
                                "Be specific about what words in the note drove the decision."
                            ),
                        },
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
                        "parent_task_index": {
                            "type": ["integer", "null"],
                            "description": (
                                "For new_task signals only: the 0-based index of the "
                                "existing task this new work should be created under as "
                                "a sub-step.  null if the new task is genuinely "
                                "top-level work, or if classification is not new_task."
                            ),
                        },
                        "proposed_status": {
                            "type": ["string", "null"],
                            "description": (
                                "Monday status label to set when classification is "
                                "task_done / task_progress / blocker.  "
                                "You MUST use one of the VALID STATUS LABELS listed in "
                                "the user message -- do not invent a label.  "
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


def _system_prompt(*, has_images: bool = False) -> str:
    base = (
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
        "classification is new_task / scope_change / other.  The list is "
        "grouped (Active first, Completed last) -- indices are consecutive "
        "across all sections.  Sub-tasks include a parent annotation.\n"
        "   - proposed_status: use EXACTLY one of the VALID STATUS LABELS listed "
        "in the user message for status signals; null otherwise.\n"
        "   - proposed_start_date / proposed_end_date: ISO dates only if the "
        "note implies a schedule change; null otherwise.\n"
        "   - new_task_title: a short imperative title only for new_task; null "
        "otherwise.\n"
        "   - parent_task_index: for new_task signals only -- set to the 0-based "
        "index of the existing task this new work belongs under as a sub-step "
        "(e.g. a repair step inside a larger 'Flooring' task).  null when the "
        "new task is genuinely top-level work with no clear parent in the list, "
        "or when classification is not new_task.\n"
        "   - workers / hours_worked: fill only when the note mentions them.\n"
        "   - confidence: your confidence in this signal [0.0, 1.0].\n"
        "   - reasoning: 1-2 sentences explaining WHY you chose this classification "
        "and which task you matched (cite the specific words from the note and the "
        "task title/status that drove your decision).\n\n"
        "CONSERVATIVE RULES:\n"
        "- Return no signals (empty array) if the note is too vague to classify.\n"
        "- A declined task match (null task_index) is fine -- do not guess.\n"
        "- IMPORTANT: If a signal describes work that was COMPLETED but no task in "
        "the TASK LIST is a confident match (either because the work was unplanned, "
        "the closest task is already Done for a different scope, or the list is long "
        "and no item clearly corresponds), prefer classifying as `new_task` rather "
        "than `task_done` with null task_index.  A `new_task` proposal with a "
        "descriptive title (e.g. 'Ceiling hole repair - second floor') is actionable; "
        "a `task_done` with no matched task is silently dropped and produces nothing.  "
        "Use `new_task` whenever completed work cannot be confidently tied to an "
        "existing task in the list.\n"
        "- Never invent information not present in the note.\n"
        "- Every signal MUST have a non-empty quoted_excerpt.\n"
        "- The user message may include RELEVANT CONTRACT/SCOPE EXCERPTS.  Use "
        "them only as BACKGROUND to interpret the note (e.g. to recognise that "
        "a mentioned item is contracted scope, or to gauge whether something is "
        "a new_task vs. an existing obligation).  The quoted_excerpt must still "
        "come from the NOTE, never from the excerpts.\n"
        "- When NOTE SENT and CURRENT DATE appear at the top of the user message, "
        "use NOTE SENT as the reference point for all relative time expressions "
        "('yesterday', 'last Friday', 'next week', etc.) to produce concrete ISO "
        "dates in proposed_start_date / proposed_end_date.  CURRENT DATE is today "
        "at processing time -- use it to judge how recent the note is and whether "
        "a mentioned date is in the past or future."
    )
    if has_images:
        base += (
            "\n- SITE PHOTOS: One or more job-site photos are attached alongside "
            "the text note.  Treat the photo(s) as visual evidence of the SAME "
            "field report -- analyse them together with the text to understand "
            "what work was done, what materials are present, and the state of the "
            "site.  Visible completed work supports task_done; visible materials "
            "or ongoing activity supports task_progress.  If the FIELD NOTE is "
            "empty, derive signals from the photo(s) alone.  For the quoted_excerpt "
            "field, use a brief plain-English description of what the photo shows "
            "(e.g. 'photo: silicone joint completed along window frame') -- this "
            "is the only case where quoted_excerpt does not come from text.  "
            "Never claim to see something not visible in the photo."
        )
    return base


def _render_note_timestamp(ts: datetime) -> str:
    """Header block giving the LLM temporal context for relative-date resolution.

    Placed at the top of the user message so 'yesterday', 'next Monday', etc.
    can be converted to concrete ISO dates.  CURRENT DATE is ingest time in UTC.
    """
    day_name = ts.strftime("%A")
    current_date = datetime.utcnow().strftime("%Y-%m-%d")
    return (
        f"NOTE SENT: {ts.strftime('%Y-%m-%d %H:%M')} UTC ({day_name})\n"
        f"CURRENT DATE: {current_date}\n\n"
    )


def _render_context_excerpts(excerpts: list[str]) -> str:
    """A RELEVANT CONTRACT/SCOPE EXCERPTS block for the user message.

    Empty string when there are no excerpts -- so the prompt is byte-identical
    to the pre-RAG prompt when no embedding provider is available.
    """
    cleaned = [" ".join((e or "").split()) for e in excerpts if (e or "").strip()]
    if not cleaned:
        return ""
    lines = [
        "RELEVANT CONTRACT/SCOPE EXCERPTS (semantic search -- background only, "
        "do NOT quote these as the signal's quoted_excerpt):"
    ]
    for body in cleaned:
        lines.append(f"- {body}")
    return "\n".join(lines) + "\n\n"


# ---------------------------------------------------------------------------
# Extractor providers
# ---------------------------------------------------------------------------


class FieldNoteExtractorError(RuntimeError):
    pass


class FieldNoteExtractor(ABC):
    name = "abstract"

    @abstractmethod
    def extract(
        self,
        *,
        note_text: str,
        task_lines: list[str] = (),
        task_block: str | None = None,
        status_labels: list[str] = (),
        context_excerpts: list[str] = (),
        note_timestamp: datetime | None = None,
        image_paths: list[str] | None = None,
    ) -> dict[str, Any]:
        """Return a dict conforming to FIELD_NOTE_SCHEMA's schema.

        ``task_block`` is a pre-rendered task list string (status-stratified,
        relevance-sorted, parent-annotated) produced by ``_render_task_block``.
        When provided it is used directly in the user message.  ``task_lines``
        is the legacy flat-list fallback used by tests and callers that build
        the block themselves; it is ignored when ``task_block`` is given.

        ``context_excerpts`` are RAG-retrieved document passages (contract /
        scope text) relevant to the note.

        ``note_timestamp`` is the email's sent time (or CLI call time if no
        email).  When provided it is rendered as a NOTE SENT header in the
        user message so the model can resolve relative date expressions
        ('yesterday', 'next Friday') into concrete ISO dates.

        ``image_paths`` are local file paths to job-site photos attached to
        the same field report.  When provided the extractor passes them as
        base64 image_url blocks alongside the text (Win 3).  The same
        FIELD_NOTE_SCHEMA is used; for photo-only notes the model derives
        signals from the images and uses a photo description as quoted_excerpt.
        """
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

    def extract(
        self,
        *,
        note_text: str,
        task_lines: list[str] = (),
        task_block: str | None = None,
        status_labels: list[str] = (),
        context_excerpts: list[str] = (),
        note_timestamp: datetime | None = None,
        image_paths: list[str] | None = None,
    ) -> dict[str, Any]:
        # task_block (pre-rendered) takes priority over legacy task_lines.
        rendered_tasks = (
            task_block
            if task_block is not None
            else (
                "\n".join(f"[{i}] {title}" for i, title in enumerate(task_lines))
                if task_lines
                else "(no tasks found for this project)"
            )
        )
        labels_block = (
            "\n".join(f"- {lbl}" for lbl in status_labels)
            if status_labels
            else "- Working on it\n- Done\n- Stuck\n- Future steps\n- On Hold"
        )
        excerpt_block = _render_context_excerpts(context_excerpts)
        timestamp_block = _render_note_timestamp(note_timestamp) if note_timestamp else ""
        user_text = (
            f"{timestamp_block}"
            f"TASK LIST (0-based index, grouped by status — active first, "
            f"completed last; sub-tasks show parent in parentheses):\n"
            f"{rendered_tasks}\n\n"
            f"VALID STATUS LABELS (use one of these EXACTLY for proposed_status):\n"
            f"{labels_block}\n\n"
            f"{excerpt_block}"
            f"FIELD NOTE:\n{note_text}"
        )

        # Build multimodal content when photos are attached (Win 3).
        loaded_images: list[str] = []
        if image_paths:
            for p in image_paths:
                url = _load_image_b64(p)
                if url:
                    loaded_images.append(url)

        if loaded_images:
            user_content: Any = [{"type": "text", "text": user_text}]
            for url in loaded_images:
                # detail="low" uses ~85 tokens/image -- budget-aware.
                user_content.append(
                    {"type": "image_url", "image_url": {"url": url, "detail": "low"}}
                )
        else:
            user_content = user_text

        try:
            resp = self._client.chat.completions.create(
                model=self.model,
                temperature=0,
                messages=[
                    {"role": "system", "content": _system_prompt(has_images=bool(loaded_images))},
                    {"role": "user", "content": user_content},
                ],
                response_format={"type": "json_schema", "json_schema": FIELD_NOTE_SCHEMA},
            )
        except Exception as exc:
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
        # Records the context_excerpts each call received.
        self.context_calls: list[list[str]] = []
        # Records the note_timestamp each call received, for timestamp threading tests.
        self.timestamp_calls: list[datetime | None] = []
        # Records the image_paths each call received, for Win 3 photo tests.
        self.image_calls: list[list[str]] = []
        # Records the pre-rendered task_block each call received (None when not passed).
        self.block_calls: list[str | None] = []

    def extract(
        self,
        *,
        note_text: str,
        task_lines: list[str] = (),
        task_block: str | None = None,
        status_labels: list[str] = (),
        context_excerpts: list[str] = (),
        note_timestamp: datetime | None = None,
        image_paths: list[str] | None = None,
    ) -> dict[str, Any]:
        self.calls.append((note_text, list(task_lines)))
        self.context_calls.append(list(context_excerpts))
        self.timestamp_calls.append(note_timestamp)
        self.image_calls.append(list(image_paths or []))
        self.block_calls.append(task_block)
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
    warnings: list[str] = field(default_factory=list)
    skipped_reason: str | None = None
    rag_chunks_used: int = 0

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


def _task_context_line(t: Task) -> str:
    """One-line task description for the LLM prompt: title + status + dates."""
    status_label = t.monday_status_label or (
        t.status.value if hasattr(t.status, "value") else str(t.status)
    )
    parts = [t.title or "(untitled)", f"[{status_label}]"]
    if t.start_date:
        parts.append(f"start:{t.start_date.isoformat()}")
    if t.end_date:
        parts.append(f"end:{t.end_date.isoformat()}")
    return " ".join(parts)


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
    email_ingest_id: str | None = None,
    received_at: datetime | None = None,
    image_paths: list[str] | None = None,
    embedding_provider: Any | None = None,
    rag_top_k: int = 6,
    rag_min_similarity: float = 0.25,
) -> FieldNoteBatch:
    """Classify a field note, persist signals + proposals.  The entry point for
    CLI and web (A5).  Flushes but does not commit -- caller owns the transaction.

    When ``embedding_provider`` is supplied, the note is enriched with
    RAG-retrieved contract/scope excerpts (the same evidence base the
    generate-proposals path uses) so the model can interpret the note against
    the contract -- not the task list alone.  Retrieval never raises; a hiccup
    just yields the pre-RAG behaviour.

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

    if (not raw_text or not raw_text.strip()) and not image_paths:
        batch.skipped_reason = "empty note"
        return batch

    # Fetch task list for this project (for task matching by index).
    tasks: list[Task] = (
        session.query(Task).filter_by(project_id=pid).order_by(Task.created_at).all()
    )
    # Build a status-stratified, relevance-sorted block (Strategy C).
    # task_ids mirrors the rendered order so task_index N -> task_ids[N].
    task_block, task_ids = _render_task_block(tasks, raw_text.strip())

    # Collect unique Monday status labels from synced tasks so the model
    # uses labels that actually exist on this board.
    known_labels: list[str] = sorted(
        {t.monday_status_label for t in tasks if t.monday_status_label}
    )

    # RAG: pull contract/scope passages relevant to THIS note, so the model
    # can cross-check the note against the contract (same evidence base as the
    # generate-proposals path).  Best-effort -- never breaks ingest.
    context_excerpts: list[str] = []
    if embedding_provider is not None:
        try:
            from project_db.ai.proposals import _retrieve_proposal_chunks

            chunks = _retrieve_proposal_chunks(
                session,
                embedding_provider,
                pid,
                raw_text.strip(),
                top_k=rag_top_k,
                min_similarity=rag_min_similarity,
            )
            context_excerpts = [c.get("text") or "" for c in chunks]
            batch.rag_chunks_used = len(context_excerpts)
        except Exception:
            context_excerpts = []

    # Resolve the note's timestamp: email send time if provided, ingest time otherwise.
    # Used both for FieldNote.received_at and as temporal context for the LLM.
    note_received_at = received_at or datetime.utcnow()

    # One structured-output call: classify + match tasks (+ photos when provided).
    try:
        result = extractor.extract(
            note_text=raw_text.strip(),
            task_block=task_block,
            status_labels=known_labels,
            context_excerpts=context_excerpts,
            note_timestamp=note_received_at,
            image_paths=image_paths or None,
        )
    except FieldNoteExtractorError as exc:
        batch.errors.append(f"extraction failed: {exc}")
        return batch

    signals = result.get("signals") or []
    if not signals:
        batch.skipped_reason = "extractor returned no signals (note too vague)"
        return batch

    eid: Any = None
    if email_ingest_id:
        try:
            eid = uuid.UUID(str(email_ingest_id))
        except (ValueError, TypeError):
            eid = None

    for sig in signals:
        try:
            _process_signal(
                session,
                batch,
                sig,
                pid,
                raw_text,
                channel,
                sender_ref,
                note_received_at,
                task_ids,
                eid,
                known_labels=known_labels,
            )
        except Exception as exc:
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
    email_ingest_id: Any = None,
    *,
    known_labels: list[str] = (),
) -> None:
    """Persist one signal as a FieldNote row and (if actionable) a Proposal."""
    raw_class = sig.get("classification", "other")
    try:
        note_class = NoteClass(raw_class)
    except ValueError:
        note_class = NoteClass.OTHER

    quoted = (sig.get("quoted_excerpt") or "").strip()
    if not quoted:
        batch.errors.append(f"signal {raw_class!r} has no quoted_excerpt -- skipped (A6)")
        return

    conf = _clamp_conf(sig.get("confidence", 0.5))
    reasoning = (sig.get("reasoning") or "").strip()

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
                    f"task_index {idx} out of range (0..{len(task_ids) - 1}) -- match declined"
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
        email_ingest_id=email_ingest_id,
    )
    session.add(fn)
    batch.field_notes.append(fn)

    # Create Proposal rows for actionable signals.
    _maybe_create_proposal(
        session,
        batch,
        sig,
        note_class,
        fn,
        project_id,
        matched_task_id,
        task_ids,
        conf,
        quoted,
        reasoning,
        known_labels=list(known_labels),
    )


# Alias map: lower-case keys -> canonical Monday label.
# Used as a safety net when the model produces a common synonym despite
# being given the real label list in the prompt.
_STATUS_ALIASES: dict[str, str] = {
    "blocked": "Stuck",
    "in progress": "Working on it",
    "in_progress": "Working on it",
    "working on it": "Working on it",
    "done": "Done",
    "complete": "Done",
    "completed": "Done",
    "on hold": "On Hold",
    "future": "Future steps",
    "future steps": "Future steps",
    "stuck": "Stuck",
}

# Monday label -> canonical TaskStatus value.
_LABEL_TO_CANONICAL: dict[str, str] = {
    "Done": "DONE",
    "Working on it": "IN_PROGRESS",
    "In Progress": "IN_PROGRESS",
    "Stuck": "BLOCKED",
    "Blocked": "BLOCKED",
    "Future steps": "TODO",
    "On Hold": "TODO",
}


def _normalize_status_label(proposed: str, known_labels: list[str]) -> str:
    """Map a proposed Monday status label to one the board will accept.

    Priority: exact in known_labels > case-insensitive in known_labels > alias map > original.
    """
    if proposed in known_labels:
        return proposed
    lower_map = {lbl.lower(): lbl for lbl in known_labels}
    if proposed.lower() in lower_map:
        return lower_map[proposed.lower()]
    aliased = _STATUS_ALIASES.get(proposed.lower())
    if aliased:
        if not known_labels or aliased in known_labels:
            return aliased
    return proposed


def _subtask_window_note(session: Session, task_id: Any, start: Any, end: Any) -> str | None:
    """Advisory string when a subtask's proposed dates fall outside its parent's
    window, else None.  Loose bound -- the caller warns, never blocks (A1)."""
    task = session.query(Task).filter_by(canonical_id=task_id).one_or_none()
    if task is None or not task.is_subitem or task.parent_task_id is None:
        return None
    parent = session.query(Task).filter_by(canonical_id=task.parent_task_id).one_or_none()
    if parent is None:
        return None
    ps, pe = parent.start_date, parent.end_date or parent.due_date
    if ps is None and pe is None:
        return None
    outside = (ps is not None and start is not None and start < ps) or (
        pe is not None and end is not None and end > pe
    )
    if not outside:
        return None
    return (
        f"subtask {task.title!r} proposed dates "
        f"{start or '?'}..{end or '?'} fall outside parent {parent.title!r} "
        f"window {ps or '?'}..{pe or '?'} -- verify before accepting"
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
    conf: float,
    quoted: str,
    reasoning: str = "",
    *,
    known_labels: list[str] = (),
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
            _default = {"task_done": "Done", "task_progress": "Working on it", "blocker": "Stuck"}
            proposed_status = _default.get(note_class.value, "Working on it")

        # Normalise the label against the board's actual options.
        proposed_status = _normalize_status_label(proposed_status, list(known_labels))

        # Canonical TaskStatus mirror for the proposed_value.
        canonical_status = _LABEL_TO_CANONICAL.get(proposed_status, "IN_PROGRESS")

        pv: dict[str, Any] = {
            "status": canonical_status,
            "monday_label": proposed_status,
        }
        if reasoning:
            pv["reasoning"] = reasoning
        proposed_value = json.dumps(pv)

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

        pv_dates: dict[str, Any] = {
            "start_date": start.isoformat() if start else None,
            "end_date": end.isoformat() if end else None,
            "evidence": quoted,
        }
        if reasoning:
            pv_dates["reasoning"] = reasoning
        # Loose parent-window bound for a subtask date_shift: warn (don't block)
        # when the proposed dates spill outside the parent task's window.
        bound_note = _subtask_window_note(session, matched_task_id, start, end)
        if bound_note:
            pv_dates["parent_window_warning"] = bound_note
            batch.warnings.append(bound_note)
        proposed_value = json.dumps(pv_dates)
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
        pv_new: dict[str, Any] = {"title": title, "evidence": quoted}
        if reasoning:
            pv_new["reasoning"] = reasoning
        # Resolve parent_task_index → UUID (same bounds-check as task_index).
        pti = sig.get("parent_task_index")
        if isinstance(pti, int) and 0 <= pti < len(task_ids):
            parent_uuid = task_ids[pti]
            # The task block indexes subitems too, so the LLM can pick one as a
            # parent.  Monday forbids sub-subitems, so a subitem parent would be
            # rejected at accept time.  Climb to the subitem's own parent (the
            # real top-level task) so the new work still lands alongside the
            # related step; if the subitem has no resolvable parent, fall back
            # to a top-level task (no parent) rather than emit a doomed proposal.
            parent_obj = session.query(Task).filter_by(canonical_id=parent_uuid).one_or_none()
            if parent_obj is not None and parent_obj.is_subitem:
                parent_uuid = parent_obj.parent_task_id
            if parent_uuid is not None:
                pv_new["parent_task_id"] = str(parent_uuid)
        proposed_value = json.dumps(pv_new)
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
        pv_scope: dict[str, Any] = {"description": quoted}
        if reasoning:
            pv_scope["reasoning"] = reasoning
        proposed_value = json.dumps(pv_scope)
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
