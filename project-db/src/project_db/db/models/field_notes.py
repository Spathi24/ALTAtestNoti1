"""FieldNote: a sidecar for per-project field observations.

One FieldNote row = one extracted SIGNAL from a worker or PM note.  A single
note may yield multiple signals (e.g. task_progress + blocker + labor info),
each stored as a separate row sharing the same raw_text.

Design mirrors the Document -> DocumentText / FinancialRecord sidecar pattern.
Every actionable signal generates a Proposal row (via the existing Proposal
engine) so humans review and accept before anything touches Monday.
"""
from __future__ import annotations

import enum

from sqlalchemy import Column, DateTime, Enum as SAEnum, Float, ForeignKey, Numeric, String, Text
from sqlalchemy.dialects.postgresql import UUID

from project_db.db.base import Base, CanonicalMixin


class NoteChannel(str, enum.Enum):
    CLI = "cli"
    WEB = "web"
    EMAIL = "email"


class NoteClass(str, enum.Enum):
    TASK_DONE = "task_done"
    TASK_PROGRESS = "task_progress"
    BLOCKER = "blocker"
    NEW_TASK = "new_task"
    DATE_SHIFT = "date_shift"
    SCOPE_CHANGE = "scope_change"
    OTHER = "other"


class FieldNote(Base, CanonicalMixin):
    """One extracted signal from a field observation.

    ``raw_text`` is the original note as submitted.  ``classification`` and
    ``quoted_excerpt`` are set after LLM extraction.  ``matched_task_id`` is
    null when no task match was found (a declined match is not a failure -- it
    may indicate a new_task signal).
    """

    raw_text = Column(Text, nullable=False)
    received_at = Column(DateTime, nullable=False)
    channel = Column(SAEnum(NoteChannel), nullable=False, default=NoteChannel.CLI)
    sender_ref = Column(String, nullable=True)

    project_id = Column(
        UUID(as_uuid=True),
        ForeignKey("project.canonical_id"),
        nullable=False,
    )

    classification = Column(SAEnum(NoteClass), nullable=True)
    quoted_excerpt = Column(Text, nullable=True)
    workers = Column(String, nullable=True)      # comma-separated names
    hours_worked = Column(Numeric(8, 2), nullable=True)
    matched_task_id = Column(
        UUID(as_uuid=True),
        ForeignKey("task.canonical_id"),
        nullable=True,
    )
    confidence = Column(Float, nullable=True)
    # Nullable: only set when this note arrived via email (Win 2).
    email_ingest_id = Column(
        UUID(as_uuid=True),
        ForeignKey("email_ingest.canonical_id"),
        nullable=True,
    )
