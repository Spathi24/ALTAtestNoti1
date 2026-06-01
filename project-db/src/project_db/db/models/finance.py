"""Finance entities.

`Invoice` is the structured, QuickBooks-shaped record (still unused in dev
until QB credentials exist).

`FinancialRecord` is the Drive-document-derived money layer: every monetary
amount the LLM extracts from a quote / estimate / invoice / receipt / change
order, with the verbatim excerpt that proves it.  Per the owner (2026-05-29),
Google Drive — not QuickBooks — is the canonical and most complete financial
source, so this is where the money picture actually comes from.  It is
deliberately SCHEMA-LIGHT: classification fields are plain strings validated
against a known vocabulary (unknown values warn, never crash) so the model
survives the file-convention drift the owner flagged, and the raw LLM item is
kept in `source_meta_json`.
"""
from __future__ import annotations

import enum

from datetime import datetime

from sqlalchemy import (
    Boolean,
    Column,
    Date,
    DateTime,
    Enum as SAEnum,
    Float,
    ForeignKey,
    Numeric,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import UUID

from project_db.db.base import Base, CanonicalMixin


# --- FinancialRecord vocabularies -------------------------------------------
# Plain string sets, NOT DB enums: the owner asked us not to hardcode a rigid
# model to today's conventions.  The extractor validates against these and
# falls back to the catch-all value with a warning on anything unexpected,
# so a new document shape never crashes a run.

# Which side of the two-sided ledger a record belongs to.  The upcharge is the
# spread between client_in and contractor_out -- that margin is the business.
FINANCIAL_DIRECTIONS = {"client_in", "contractor_out", "unknown"}
# What kind of financial document the amount came from.
FINANCIAL_DOC_ROLES = {
    "quote", "estimate", "invoice", "receipt", "change_order", "other",
}
# What the individual amount represents within its document.  Used by the
# reconciliation report to avoid double-counting a line item AND its total.
FINANCIAL_RECORD_KINDS = {"total", "line_item", "tax", "deposit", "other"}


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


class FinancialRecord(Base, CanonicalMixin):
    """One monetary amount extracted from one Drive financial document.

    The LLM extracts; this row stores the fact plus its evidence.  No
    arithmetic happens here -- the reconciliation report computes
    client-in / contractor-out / margin from these rows in plain SQL/Python.

    Classification columns (`direction`, `doc_role`, `record_kind`) are
    free-form strings constrained at write time to the FINANCIAL_* sets
    above; an unrecognised value is coerced to the catch-all and warned,
    never rejected -- the schema must outlive today's document conventions.
    """

    # Provenance -- which project + which source document this came from.
    # project_id is nullable because a financial document may not (yet) be
    # linked to a project; document_id is the evidence anchor.
    project_id = Column(
        UUID(as_uuid=True),
        ForeignKey("project.canonical_id"),
        nullable=True,
    )
    document_id = Column(
        UUID(as_uuid=True),
        ForeignKey("document.canonical_id", ondelete="CASCADE"),
        nullable=True,
    )

    # The two-sided ledger.  client_in = money we invoice the client;
    # contractor_out = money contractors/suppliers quote/invoice us;
    # unknown = the model could not determine direction (kept, not guessed).
    direction = Column(String, nullable=False, default="unknown")
    # quote / estimate / invoice / receipt / change_order / other.
    doc_role = Column(String, nullable=True)
    # total / line_item / tax / deposit / other -- lets the reconciliation
    # report prefer a document's total over re-summing its line items.
    record_kind = Column(String, nullable=True)

    counterparty = Column(String, nullable=True)   # client or contractor name
    description = Column(Text, nullable=True)        # what the amount is for
    phase = Column(String, nullable=True)            # phase label, if phased

    amount = Column(Numeric(14, 2), nullable=True)
    currency = Column(String, nullable=True)         # e.g. CAD, USD
    doc_date = Column(Date, nullable=True)           # date on the document

    # Verbatim evidence -- the exact text from the document containing the
    # amount.  A reviewer can Ctrl-F this against the extracted DocumentText.
    quoted_excerpt = Column(Text, nullable=True)
    confidence = Column(Float, nullable=True)
    # True when the amount's value was found in the source document text (value-
    # based, decimal-tolerant).  False = the model may have computed it, or
    # expanded notation/words ("8k", "eight thousand"); surfaced for review and
    # so the future dashboard can badge unverified figures.  None = not checked.
    amount_verified = Column(Boolean, nullable=True)
    # True when the SOURCE DOCUMENT is an internal roll-up / tracking sheet
    # (a cost tracker, job-costing sheet, payment tracker) that restates amounts
    # from other documents, rather than a primary transaction (one invoice /
    # quote / contract).  Roll-up records are EXCLUDED from reconciliation
    # totals (to avoid double-counting the invoices they summarize) and shown
    # only as a cross-check.  Per-document property, denormalized onto each row.
    # None / False = primary transaction document (counted in totals).
    is_rollup = Column(Boolean, nullable=True)

    # Which extraction prompt produced this (mirrors Proposal.prompt_version).
    prompt_version = Column(String, nullable=True)
    # Raw LLM item -- keep everything; promote to columns only what we query.
    source_meta_json = Column(Text, nullable=True)


class DocumentFinancialStatus(Base):
    """A human's decision: does this document's money COUNT toward the
    confirmed total, or is it a quote they didn't go with?

    CRITICAL design point: this lives in its OWN table keyed by document, NOT
    on FinancialRecord -- because every ``extract-financials`` run deletes and
    rebuilds the FinancialRecord rows (fresh snapshot), which would otherwise
    WIPE the human's confirmations.  Keyed by document id, it survives
    re-extraction.

    Only documents a human has EXPLICITLY toggled get a row here.  Absence of a
    row means "use the smart default" (invoices/receipts confirmed; quotes /
    estimates unconfirmed) -- computed in ``report_project_financials``.
    """

    document_id = Column(
        UUID(as_uuid=True),
        ForeignKey("document.canonical_id", ondelete="CASCADE"),
        primary_key=True,
    )
    confirmed = Column(Boolean, nullable=False)
    decided_by = Column(String, nullable=True)
    decided_at = Column(DateTime, nullable=False, default=datetime.utcnow)
