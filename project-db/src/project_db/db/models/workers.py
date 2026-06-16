"""Worker roster and email-ingest audit table for Win 2 email intake.

Worker
  Maps sender email / phone-gateway address to a person and a default project.
  Unknown senders (not in this table) are quarantined, never processed silently.

EmailIngest
  One row per Gmail message polled.  The dedup anchor (gmail_message_id) and
  the audit log: was this message processed, quarantined, duplicated, or failed?
  The mailbox itself is the durable queue; this table is the local mirror.

Both inherit from Base + CanonicalMixin (canonical_id UUID primary key).
"""

from __future__ import annotations

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID

from project_db.db.base import Base, CanonicalMixin


class Worker(Base, CanonicalMixin):
    """A field worker or PM whose emails ALTA should process.

    ``email`` is the primary sending address.  ``phone_gateway_email`` covers
    SMS-to-email relays (e.g. 5145550001@txt.att.net) so a text from the job
    site arrives via a different From address than the worker's Gmail.
    ``default_project_id`` is the fallback project when plus-address routing
    does not find a match.
    """

    display_name = Column(String, nullable=False)
    email = Column(String, nullable=True)
    phone_gateway_email = Column(String, nullable=True)
    default_project_id = Column(
        UUID(as_uuid=True),
        ForeignKey("project.canonical_id"),
        nullable=True,
    )
    active = Column(Boolean, nullable=False, default=True)
    # Categorization filled in by the PM after reviewing recurring senders.
    role = Column(String, nullable=True)  # PM / tradesman / crew / subcontractor
    tags = Column(String, nullable=True)  # comma-separated free-text labels
    # False = auto-created from first email; True = manually added / confirmed.
    verified = Column(Boolean, nullable=False, default=False)


class EmailIngest(Base, CanonicalMixin):
    """Audit + dedup record for one polled Gmail message.

    ``gmail_message_id``  -- Gmail's immutable message ID (dedup key).
    ``rfc_message_id``    -- RFC 2822 Message-ID header (secondary dedup).
    ``status`` values:
        pending       -- created but not yet processed (transient; should not persist)
        processed     -- ingest_field_note() ran successfully
        quarantined   -- sender not in Worker roster; no FieldNote created
        duplicate     -- gmail_message_id already seen; skipped
        failed        -- extraction or storage error; see failure_reason
    ``attachment_refs_json`` -- JSON list of local file paths for stored attachments.
    """

    gmail_message_id = Column(String, nullable=False)
    rfc_message_id = Column(String, nullable=True)
    thread_id = Column(String, nullable=True)
    sender_email = Column(String, nullable=True)
    subject = Column(String, nullable=True)
    received_at = Column(DateTime, nullable=False)
    processed_at = Column(DateTime, nullable=True)
    status = Column(String, nullable=False, default="pending")
    failure_reason = Column(Text, nullable=True)
    project_id = Column(
        UUID(as_uuid=True),
        ForeignKey("project.canonical_id"),
        nullable=True,
    )
    attachment_refs_json = Column(Text, nullable=True)
