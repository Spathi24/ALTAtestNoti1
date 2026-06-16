"""Canonical entities + the ExternalId mapping table.

ExternalId is the heart of the multi-source design. Every record we pull from
Monday, CompanyCam, QuickBooks, or Drive gets a row here pointing at the
canonical UUID it resolves to.

Composite uniqueness on (source, entity_type, external_key) means we can't
accidentally double-register the same source record.
"""

from __future__ import annotations

import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    Column,
    DateTime,
    String,
    UniqueConstraint,
)
from sqlalchemy import (
    Enum as SAEnum,
)
from sqlalchemy.dialects.postgresql import UUID

from project_db.db.base import Base, CanonicalMixin


class SourceSystem(str, enum.Enum):
    MONDAY = "MONDAY"
    COMPANYCAM = "COMPANYCAM"
    QUICKBOOKS = "QUICKBOOKS"
    GOOGLE_DRIVE = "GOOGLE_DRIVE"
    INTERNAL = "INTERNAL"


class Organization(Base, CanonicalMixin):
    """The top-level tenant. For a single-company deployment there's just one."""

    name = Column(String, nullable=False)
    legal_name = Column(String, nullable=True)
    default_currency = Column(String, nullable=True, default="CAD")


class ExternalId(Base):
    """Maps (source_system, external_key) → canonical entity UUID.

    `entity_type` records *which* canonical class this points at, e.g. "Project"
    or "Client". The (canonical_id, entity_type) pair is what you join on when
    you need to know "what's the Monday ID for this Project?"
    """

    __tablename__ = "external_id"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source = Column(SAEnum(SourceSystem), nullable=False)
    external_key = Column(String, nullable=False)
    external_url = Column(String, nullable=True)
    entity_type = Column(String, nullable=False)
    canonical_id = Column(UUID(as_uuid=True), nullable=False, index=True)

    last_synced_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    raw_payload_hash = Column(String, nullable=True)

    __table_args__ = (
        UniqueConstraint("source", "entity_type", "external_key", name="uq_external_id_lookup"),
    )

    def __repr__(self) -> str:
        return (
            f"<ExternalId {self.source.value}:{self.entity_type}:{self.external_key}"
            f" -> {self.canonical_id}>"
        )
