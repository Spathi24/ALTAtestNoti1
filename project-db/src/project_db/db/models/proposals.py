"""LLM-generated suggestions awaiting human review.

This is the gate between the AI layer and the canonical store: per
STRATEGY.md, "the LLM is an advisor, never an actor." Every AI-produced
field change lands here first. A human reviews via the approval CLI and
explicit acceptance is what triggers write-back to the source system.

Polymorphic by design:
  - `entity_type` + `entity_id` identifies the target row in any canonical
    table (Task, Project, Invoice, ...). Kept as plain strings instead of a
    real polymorphic relationship because the target is dynamic and the
    proposal layer has no business JOIN-ing into every entity table.
  - `proposed_value` is JSON so we can carry scalars, dates, lists, or
    structured payloads uniformly. Readers parse based on `field_name`
    semantics.
"""

from __future__ import annotations

import enum

from sqlalchemy import Column, DateTime, Float, String, Text
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import UUID

from project_db.db.base import Base, CanonicalMixin


class ProposalStatus(str, enum.Enum):
    PENDING = "PENDING"
    ACCEPTED = "ACCEPTED"
    REJECTED = "REJECTED"
    SUPERSEDED = "SUPERSEDED"


class Proposal(Base, CanonicalMixin):
    entity_type = Column(String, nullable=False)
    entity_id = Column(UUID(as_uuid=True), nullable=False)
    field_name = Column(String, nullable=False)
    proposed_value = Column(Text, nullable=False)
    confidence = Column(Float, nullable=True)
    source_doc_ids = Column(Text, nullable=True)
    prompt_version = Column(String, nullable=True)
    status = Column(
        SAEnum(ProposalStatus),
        nullable=False,
        default=ProposalStatus.PENDING,
    )
    decided_at = Column(DateTime, nullable=True)
    decided_by = Column(String, nullable=True)
    rejection_reason = Column(Text, nullable=True)
