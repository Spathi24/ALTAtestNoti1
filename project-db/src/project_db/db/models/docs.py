"""Document references — actual files stay in Drive / CompanyCam / etc."""
from __future__ import annotations

from sqlalchemy import Column, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID

from project_db.db.base import Base, CanonicalMixin


class Document(Base, CanonicalMixin):
    name = Column(String, nullable=False)
    mime_type = Column(String, nullable=True)
    url = Column(String, nullable=False)
    storage_ref = Column(String, nullable=True)

    project_id = Column(
        UUID(as_uuid=True),
        ForeignKey("project.canonical_id"),
        nullable=True,
    )
    deal_id = Column(
        UUID(as_uuid=True),
        ForeignKey("deal.canonical_id"),
        nullable=True,
    )
    client_id = Column(
        UUID(as_uuid=True),
        ForeignKey("client.canonical_id"),
        nullable=True,
    )
