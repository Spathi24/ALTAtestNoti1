"""Unified labour-intake / consolidation layer (source-agnostic).

The insight (per the Telegram-intake plan): Gmail Project Log sheets AND
Telegram worker/foreman messages should NOT be two buckets emptying into the
DB. They both feed ONE pre-canonical consolidation layer that decides whether
two source records describe the same real-world shift (reinforce), or disagree
(conflict).

Pipeline:
    LabourSourceEvent      one raw incoming item (email / telegram / manual)
      -> LabourClaim       one extracted claim about a worker's shift/activity
      -> LabourClaimCluster a group of claims that probably = the same shift
      -> canonical ProjectLogSubmission / ProjectLogEntry (existing tables)

Same discipline as the rest of ALTA: raw values preserved, uncertainty kept,
nothing collapsed prematurely; a CONFLICT cluster is surfaced for review, never
silently resolved (the labour twin of the financial reconcile gate). Reuses the
existing ``Worker`` / ``WorkerAlias`` -- no separate employee database.

v1 tables here; ``TelegramIdentity`` / ``WorkerContact`` /
``LabourReconciliationIssue`` / ``LabourActivityLink`` are added when their
phases land (Telegram transport, contact growth, reconciliation reports,
field-note linking).
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

# --- Controlled vocabularies (validated-with-fallback strings, never DB enums) -

SOURCE_CHANNELS = {"gmail", "telegram", "manual"}
SOURCE_KINDS = {
    "email_project_log",
    "telegram_text",
    "telegram_voice",
    "telegram_photo",
    "telegram_document",
    "telegram_callback",
    "manual",
}
SOURCE_EVENT_STATUSES = {
    "received",
    "extracted",
    "clustered",
    "canonicalized",
    "quarantined",
    "failed",
    "ignored",
}
CLAIM_TYPES = {
    "labour_time",
    "activity_only",
    "attendance_only",
    "correction",
    "absence",
    "unknown",
}
REPORTER_ROLES = {"self", "foreman", "supervisor", "unknown"}
CLAIM_EXTRACTION_METHODS = {
    "deterministic",
    "vision_llm",
    "text_llm",
    "voice_transcript_llm",
    "manual",
    "gmail_bridge",
}
EMPLOYEE_MATCH_METHODS_CLAIM = {
    "exact",
    "alias",
    "telegram_identity",
    "phone",
    "fuzzy",
    "manual",
    "unresolved",
}
PROJECT_MATCH_METHODS = {
    "explicit_selection",
    "site_name",
    "plus_address",
    "text_llm",
    "worker_default",
    "manual",
    "unresolved",
}
CLAIM_REVIEW_STATUSES = {"pending", "accepted", "rejected", "needs_review"}
CLUSTER_STATUSES = {"open", "canonicalized", "conflict", "needs_review", "ignored"}
CLUSTER_RESOLUTION_METHODS = {
    "auto_reinforced",
    "auto_single_source",
    "manual",
    "conflict_unresolved",
}
CLUSTER_MEMBER_RELATIONSHIPS = {
    "primary",
    "supporting",
    "conflicting",
    "duplicate",
    "correction",
}


class LabourSourceEvent(Base, CanonicalMixin):
    """One raw incoming source item, BEFORE interpretation. Source-agnostic.

    Dedup: Gmail by message id / attachment hash; Telegram by update id and
    (chat_id, message_id); attachments by sha256.
    """

    source_channel = Column(String, nullable=False, default="manual")
    source_kind = Column(String, nullable=False, default="manual")
    source_external_id = Column(String, nullable=True)  # gmail msg id / tg update id
    source_parent_id = Column(String, nullable=True)  # tg session / email thread
    source_sender_key = Column(String, nullable=True)  # email addr / tg user id
    source_chat_id = Column(String, nullable=True)
    source_message_id = Column(String, nullable=True)

    received_at = Column(DateTime, nullable=False)
    source_created_at = Column(DateTime, nullable=True)

    raw_text = Column(Text, nullable=True)  # body / message / caption / transcript
    raw_payload_json = Column(Text, nullable=True)
    attachment_paths_json = Column(Text, nullable=True)
    attachment_hashes_json = Column(Text, nullable=True)

    ingestion_status = Column(String, nullable=False, default="received")
    ingestion_reason = Column(Text, nullable=True)

    worker_id = Column(UUID(as_uuid=True), ForeignKey("worker.canonical_id"), nullable=True)
    project_id_hint = Column(UUID(as_uuid=True), ForeignKey("project.canonical_id"), nullable=True)


class LabourClaim(Base, CanonicalMixin):
    """One extracted claim about a worker's shift/activity. NOT yet canonical.

    A single source event can produce many claims (a foreman reporting several
    workers; a Gmail sheet with N rows). Raw values + uncertainty preserved.
    """

    source_event_id = Column(
        UUID(as_uuid=True),
        ForeignKey("labour_source_event.canonical_id", ondelete="CASCADE"),
        nullable=True,
    )
    source_channel = Column(String, nullable=False, default="manual")
    source_confidence = Column(Float, nullable=True)  # extraction confidence, not truth

    # Who submitted vs who the claim is about.
    reporter_worker_id = Column(
        UUID(as_uuid=True), ForeignKey("worker.canonical_id"), nullable=True
    )
    reporter_role = Column(String, nullable=False, default="unknown")
    reported_for_worker_id = Column(
        UUID(as_uuid=True), ForeignKey("worker.canonical_id"), nullable=True
    )
    employee_name_raw = Column(String, nullable=True)  # NEVER discarded
    employee_phone_raw = Column(String, nullable=True)
    employee_match_method = Column(String, nullable=False, default="unresolved")
    employee_match_confidence = Column(Float, nullable=True)

    project_id = Column(UUID(as_uuid=True), ForeignKey("project.canonical_id"), nullable=True)
    project_name_raw = Column(String, nullable=True)
    project_match_method = Column(String, nullable=False, default="unresolved")
    project_match_confidence = Column(Float, nullable=True)

    work_date = Column(Date, nullable=True)
    work_date_raw = Column(String, nullable=True)

    time_arrived = Column(String, nullable=True)  # normalised "HH:MM"
    time_left = Column(String, nullable=True)
    lunch_hours = Column(Numeric(5, 2), nullable=True)
    total_hours_reported = Column(Numeric(6, 2), nullable=True)
    total_hours_computed = Column(Numeric(6, 2), nullable=True)
    hours_mismatch = Column(Boolean, nullable=False, default=False)

    activity_text = Column(Text, nullable=True)
    trade = Column(String, nullable=True)
    unit = Column(String, nullable=True)
    notes = Column(Text, nullable=True)

    claim_type = Column(String, nullable=False, default="unknown")
    extraction_method = Column(String, nullable=False, default="manual")
    extractor_version = Column(String, nullable=True)

    missing_fields_json = Column(Text, nullable=True)
    raw_extraction_json = Column(Text, nullable=True)

    canonical_cluster_id = Column(
        UUID(as_uuid=True),
        ForeignKey("labour_claim_cluster.canonical_id"),
        nullable=True,
    )
    canonicalized = Column(Boolean, nullable=False, default=False)
    review_status = Column(String, nullable=False, default="pending")


class LabourClaimCluster(Base, CanonicalMixin):
    """A group of claims that probably refer to the same real-world shift.

    Gmail row + Telegram self-report + foreman report can all point to one shift.
    A CONFLICT status is surfaced for review, never silently collapsed.
    """

    worker_id = Column(UUID(as_uuid=True), ForeignKey("worker.canonical_id"), nullable=True)
    project_id = Column(UUID(as_uuid=True), ForeignKey("project.canonical_id"), nullable=True)
    work_date = Column(Date, nullable=True)

    cluster_key = Column(String, nullable=False)  # coarse worker/project/date key
    confidence = Column(Float, nullable=True)
    status = Column(String, nullable=False, default="open")

    chosen_time_arrived = Column(String, nullable=True)
    chosen_time_left = Column(String, nullable=True)
    chosen_lunch_hours = Column(Numeric(5, 2), nullable=True)
    chosen_total_hours = Column(Numeric(6, 2), nullable=True)

    evidence_count = Column(Integer, nullable=False, default=0)
    source_channels_json = Column(Text, nullable=True)  # ["gmail","telegram"]
    conflict_flags_json = Column(Text, nullable=True)
    resolution_method = Column(String, nullable=True)

    canonical_submission_id = Column(
        UUID(as_uuid=True),
        ForeignKey("project_log_submission.canonical_id"),
        nullable=True,
    )
    canonical_entry_id = Column(
        UUID(as_uuid=True),
        ForeignKey("project_log_entry.canonical_id"),
        nullable=True,
    )


class LabourClaimClusterMember(Base, CanonicalMixin):
    """Membership edge: which claim belongs to which cluster, and how."""

    cluster_id = Column(
        UUID(as_uuid=True),
        ForeignKey("labour_claim_cluster.canonical_id", ondelete="CASCADE"),
        nullable=False,
    )
    claim_id = Column(
        UUID(as_uuid=True),
        ForeignKey("labour_claim.canonical_id", ondelete="CASCADE"),
        nullable=False,
    )
    relationship = Column(String, nullable=False, default="supporting")
    similarity_score = Column(Float, nullable=True)
