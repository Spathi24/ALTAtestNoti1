"""CRM pipeline entities: Lead → Deal → (Project)."""
from __future__ import annotations

import enum
from datetime import date

from sqlalchemy import Column, Date, Enum as SAEnum, Float, ForeignKey, Numeric, String
from sqlalchemy.dialects.postgresql import UUID

from project_db.db.base import Base, CanonicalMixin


class LeadStage(str, enum.Enum):
    NEW = "NEW"
    QUALIFIED = "QUALIFIED"
    PROPOSAL = "PROPOSAL"
    NEGOTIATION = "NEGOTIATION"
    WON = "WON"
    LOST = "LOST"


class Lead(Base, CanonicalMixin):
    source_channel = Column(String, nullable=True)
    stage = Column(SAEnum(LeadStage), nullable=False, default=LeadStage.NEW)
    estimated_value = Column(Numeric(12, 2), nullable=True)
    qualified_at = Column(Date, nullable=True)

    client_id = Column(
        UUID(as_uuid=True),
        ForeignKey("client.canonical_id"),
        nullable=True,
    )
    owner_id = Column(
        UUID(as_uuid=True),
        ForeignKey("user.canonical_id"),
        nullable=True,
    )
    property_id = Column(
        UUID(as_uuid=True),
        ForeignKey("property.canonical_id"),
        nullable=True,
    )


class Deal(Base, CanonicalMixin):
    name = Column(String, nullable=False)
    value = Column(Numeric(12, 2), nullable=False, default=0)
    stage = Column(SAEnum(LeadStage), nullable=False, default=LeadStage.NEW)
    expected_close_date = Column(Date, nullable=True)
    actual_close_date = Column(Date, nullable=True)
    probability = Column(Float, nullable=True)

    lead_id = Column(
        UUID(as_uuid=True),
        ForeignKey("lead.canonical_id"),
        nullable=True,
    )
    client_id = Column(
        UUID(as_uuid=True),
        ForeignKey("client.canonical_id"),
        nullable=False,
    )
    property_id = Column(
        UUID(as_uuid=True),
        ForeignKey("property.canonical_id"),
        nullable=True,
    )
    owner_id = Column(
        UUID(as_uuid=True),
        ForeignKey("user.canonical_id"),
        nullable=True,
    )
