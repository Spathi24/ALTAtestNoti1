"""Project Log labour/time-sheet entities (separate from field notes & finance).

A daily ALTA Project Log sheet (photographed/scanned, emailed in) records who
worked on which site, when they arrived/left, lunch, total hours, and whether a
supervisor signed.  See ``docs/PROJECT_LOG_INGESTION.md``.

``ProjectLogSubmission``  one row per submitted form/image (provenance + status).
``ProjectLogEntry``       one row per filled worker/time row.
``WorkerAlias``           handwritten name variants -> a known ``Worker``.

Same validated-with-fallback discipline as ``finance.py``: classification fields
are plain strings checked against a known vocabulary at write time (unknown
values warn + coerce, never crash) so the schema survives form/handwriting drift.
The raw vision JSON is kept whole in ``raw_extraction_json``; nothing is lost.
"""

from __future__ import annotations

from sqlalchemy import (
    Boolean,
    Column,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import UUID

from project_db.db.base import Base, CanonicalMixin

# --- Controlled vocabularies (validated-with-fallback, never DB enums) -------

# Per-submission outcome.
PROJECT_LOG_INGESTION_STATUSES = {"parsed", "quarantined", "failed", "skipped"}
PROJECT_LOG_INGESTION_REASONS = {
    "low_confidence_project_log_classification",
    "unknown_site",
    "empty_form",
    "no_rows_detected",
    "unreadable_image",
    "validation_failed",
    "duplicate_attachment",
    "parse_error",
}
# How the form was recognised as a project log.
PROJECT_LOG_CLASSIFICATION_METHODS = {"deterministic", "vision_llm", "manual"}
# How a row's handwritten name was tied to a Worker.
EMPLOYEE_MATCH_METHODS = {"exact", "alias", "fuzzy", "manual", "unresolved"}
# Where an alias came from.
WORKER_ALIAS_SOURCES = {"manual", "project_log", "email_roster", "imported"}


class ProjectLogSubmission(Base, CanonicalMixin):
    """One submitted Project Log form (one image/PDF attachment).

    Dedup anchor: ``(source_email_message_id, source_attachment_hash)``.  A
    re-sent attachment replaces the prior submission + its entries idempotently.
    ``raw_extraction_json`` keeps the full vision payload for audit/replay.
    """

    project_id = Column(
        UUID(as_uuid=True),
        ForeignKey("project.canonical_id"),
        nullable=True,
    )
    # Link back to the email audit row (provenance); null for non-email sources.
    email_ingest_id = Column(
        UUID(as_uuid=True),
        ForeignKey("email_ingest.canonical_id"),
        nullable=True,
    )

    site_name_raw = Column(String, nullable=True)  # verbatim top-box text
    site_name_resolved = Column(String, nullable=True)  # matched project name

    # Provenance of the source attachment.
    source_email_message_id = Column(String, nullable=True)  # gmail message id
    source_attachment_filename = Column(String, nullable=True)
    source_attachment_hash = Column(String, nullable=True)  # sha256 of bytes
    source_image_uri = Column(String, nullable=True)  # local path / URI
    drive_file_id = Column(String, nullable=True)

    received_at = Column(DateTime, nullable=True)
    processed_at = Column(DateTime, nullable=True)

    document_type = Column(String, nullable=False, default="project_log")
    classification_method = Column(String, nullable=True)  # vision_llm / manual
    classification_confidence = Column(Float, nullable=True)

    ingestion_status = Column(String, nullable=False, default="parsed")
    ingestion_reason = Column(Text, nullable=True)
    extractor_version = Column(String, nullable=True)

    raw_extraction_json = Column(Text, nullable=True)


class ProjectLogEntry(Base, CanonicalMixin):
    """One filled worker/time row from a Project Log form.

    Raw values are always preserved (``employee_name_raw`` is NEVER discarded,
    even when unresolved).  Both reported and computed hours are stored; the
    reported value is never silently overwritten.
    """

    submission_id = Column(
        UUID(as_uuid=True),
        ForeignKey("project_log_submission.canonical_id", ondelete="CASCADE"),
        nullable=False,
    )
    project_id = Column(
        UUID(as_uuid=True),
        ForeignKey("project.canonical_id"),
        nullable=True,
    )

    site_name_raw = Column(String, nullable=True)
    site_name_resolved = Column(String, nullable=True)

    work_date = Column(Date, nullable=True)

    employee_name_raw = Column(String, nullable=True)  # NEVER discarded
    employee_id = Column(
        UUID(as_uuid=True),
        ForeignKey("worker.canonical_id"),
        nullable=True,
    )
    employee_match_confidence = Column(Float, nullable=True)
    employee_match_method = Column(String, nullable=False, default="unresolved")

    # Times stored as normalised "HH:MM" strings (locale-free, no tz games).
    time_arrived = Column(String, nullable=True)
    time_left = Column(String, nullable=True)
    lunch_hours = Column(Numeric(5, 2), nullable=True)
    total_hours_reported = Column(Numeric(6, 2), nullable=True)
    total_hours_computed = Column(Numeric(6, 2), nullable=True)
    hours_mismatch = Column(Boolean, nullable=False, default=False)

    supervisor_signature_present = Column(Boolean, nullable=False, default=False)

    row_index = Column(Integer, nullable=True)
    confidence = Column(Float, nullable=True)
    missing_fields_json = Column(Text, nullable=True)
    source_bbox_json = Column(Text, nullable=True)
    source_meta_json = Column(Text, nullable=True)


class WorkerAlias(Base, CanonicalMixin):
    """A handwritten/variant name that maps to a known ``Worker``.

    Lets 'Mike' / 'Michael' / 'M. Smith' / 'Michel' resolve to one worker.
    Stored separately so the resolver can grow without touching ``Worker``.
    """

    worker_id = Column(
        UUID(as_uuid=True),
        ForeignKey("worker.canonical_id", ondelete="CASCADE"),
        nullable=False,
    )
    alias_text = Column(String, nullable=False)
    source = Column(String, nullable=False, default="project_log")
    confidence = Column(Float, nullable=True)
