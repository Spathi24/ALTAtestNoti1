"""SQLAlchemy declarative base and shared mixins.

All canonical entities inherit from `Base` (declarative base) plus the
`CanonicalMixin` which provides:
  - `canonical_id`: UUID primary key
  - `created_at` / `updated_at`: audit timestamps

This mirrors the Umple `CanonicalEntity` class.
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import Column, DateTime, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, declared_attr


class Base(DeclarativeBase):
    """Project-wide SQLAlchemy declarative base.

    `__allow_unmapped__` lets us keep 1.x-style `Column(...)` declarations
    without rewriting everything as `Mapped[...]`. Worth revisiting if/when
    the schema is stable and we want strict typing.
    """

    __allow_unmapped__ = True

    # Allow subclasses to override table names via `__tablename__`; default
    # to snake-cased class name.
    @declared_attr.directive
    def __tablename__(cls) -> str:  # type: ignore[override]
        import re

        return re.sub(r"(?<!^)(?=[A-Z])", "_", cls.__name__).lower()


class CanonicalMixin:
    """Adds canonical_id + timestamps to any entity that can appear in
    multiple source systems.
    """

    canonical_id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )
    notes = Column(String, nullable=True)
