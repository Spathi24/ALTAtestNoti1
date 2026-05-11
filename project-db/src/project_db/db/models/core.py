"""Core domain entities: User, Client, Vendor, Property."""
from __future__ import annotations

from sqlalchemy import Boolean, Column, Float, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from project_db.db.base import Base, CanonicalMixin


class User(Base, CanonicalMixin):
    email = Column(String, nullable=False)
    display_name = Column(String, nullable=False)
    role = Column(String, nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)

    organization_id = Column(
        UUID(as_uuid=True),
        ForeignKey("organization.canonical_id"),
        nullable=False,
    )
    organization = relationship("Organization")


class Client(Base, CanonicalMixin):
    name = Column(String, nullable=False)
    email = Column(String, nullable=True)
    phone = Column(String, nullable=True)
    billing_address = Column(String, nullable=True)

    organization_id = Column(
        UUID(as_uuid=True),
        ForeignKey("organization.canonical_id"),
        nullable=False,
    )


class Vendor(Base, CanonicalMixin):
    name = Column(String, nullable=False)
    email = Column(String, nullable=True)
    phone = Column(String, nullable=True)
    tax_id = Column(String, nullable=True)
    payment_terms = Column(String, nullable=True)

    organization_id = Column(
        UUID(as_uuid=True),
        ForeignKey("organization.canonical_id"),
        nullable=False,
    )


class Property(Base, CanonicalMixin):
    address = Column(String, nullable=False)
    short_label = Column(String, nullable=True)
    city = Column(String, nullable=True)
    region = Column(String, nullable=True)
    postal_code = Column(String, nullable=True)
    country = Column(String, nullable=True, default="CA")
    property_type = Column(String, nullable=True)
    lot_size = Column(Float, nullable=True)
    year_built = Column(Integer, nullable=True)

    organization_id = Column(
        UUID(as_uuid=True),
        ForeignKey("organization.canonical_id"),
        nullable=False,
    )
