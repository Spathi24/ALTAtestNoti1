"""Finance entities. v0.1 is intentionally minimal — Invoice only.

The full model adds PurchaseOrder, Payment, Expense, Quote, Contract.
"""
from __future__ import annotations

import enum

from sqlalchemy import Column, Date, Enum as SAEnum, ForeignKey, Numeric, String
from sqlalchemy.dialects.postgresql import UUID

from project_db.db.base import Base, CanonicalMixin


class InvoiceStatus(str, enum.Enum):
    DRAFT = "DRAFT"
    SENT = "SENT"
    PARTIAL = "PARTIAL"
    PAID = "PAID"
    OVERDUE = "OVERDUE"
    VOID = "VOID"


class Invoice(Base, CanonicalMixin):
    number = Column(String, nullable=False)
    amount = Column(Numeric(12, 2), nullable=False, default=0)
    issue_date = Column(Date, nullable=False)
    due_date = Column(Date, nullable=True)
    status = Column(
        SAEnum(InvoiceStatus), nullable=False, default=InvoiceStatus.DRAFT
    )

    project_id = Column(
        UUID(as_uuid=True),
        ForeignKey("project.canonical_id"),
        nullable=False,
    )
    client_id = Column(
        UUID(as_uuid=True),
        ForeignKey("client.canonical_id"),
        nullable=False,
    )
