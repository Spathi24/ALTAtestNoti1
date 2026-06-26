"""Contract obligations -- the Money-at-Risk layer.

Dated/dollar COMMITMENTS extracted from contract documents: payment milestones,
retainage/holdbacks, penalty clauses, deposits, settlement payments,
insurance/permit expiry dates. The recurring, boring, cross-system items a human
lets slip -- the $8,000 due on key return, the 10% retainage, the milestone
done-but-not-billed.

Mirrors ``FinancialRecord`` deliberately: the LLM extracts the fact plus its
verbatim evidence; deterministic code (``report_commitments``) reconciles them
against invoices + Monday status + today. Schema-light -- classification columns
are plain strings validated against a known vocabulary (unknown values warn,
never crash), and the raw LLM item is kept in ``source_meta_json``.
"""

from __future__ import annotations

from sqlalchemy import (
    Boolean,
    Column,
    Date,
    Float,
    ForeignKey,
    Numeric,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import UUID

from project_db.db.base import Base, CanonicalMixin

# What the obligation is.  Validated at write time; unknown -> "other" + warn.
OBLIGATION_KINDS = {
    "payment_milestone",  # e.g. "25% on completion"
    "retainage",  # holdback / final retainage release
    "penalty",  # late-completion / liquidated-damages clause
    "deposit",  # an upfront deposit due
    "insurance_expiry",  # a certificate/coverage that expires
    "permit_deadline",  # a permit / filing deadline
    "settlement",  # a settlement / buyout payment (e.g. tenant key return)
    "other",
}
# Direction of the commitment, from OUR point of view:
#   owed_to_us  = the client owes us -> revenue to collect (money at risk if forgotten)
#   owed_by_us  = we owe someone     -> a payment/obligation to meet (penalty/deadline risk)
#   unknown     = not determinable (kept, not guessed)
OBLIGATION_DIRECTIONS = {"owed_to_us", "owed_by_us", "unknown"}


class ContractObligation(Base, CanonicalMixin):
    """One dated/dollar obligation extracted from one contract document."""

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

    kind = Column(String, nullable=False, default="other")
    direction = Column(String, nullable=False, default="unknown")
    description = Column(Text, nullable=True)  # what the obligation is

    amount = Column(Numeric(14, 2), nullable=True)  # null when it's a pure deadline
    currency = Column(String, nullable=True)
    # An explicit calendar date, when the contract gives one.
    due_date = Column(Date, nullable=True)
    # The condition in the contract's own words when there is no fixed date,
    # e.g. "upon key return", "on substantial completion".  Kept verbatim so the
    # reconciler can surface it even without a date.
    trigger = Column(String, nullable=True)
    counterparty = Column(String, nullable=True)  # client / sub / authority name

    # Verbatim evidence -- the exact clause text.  Ctrl-F-able against DocumentText.
    quoted_excerpt = Column(Text, nullable=True)
    confidence = Column(Float, nullable=True)
    # True when the amount's VALUE was found in the source text (value-based,
    # decimal-tolerant -- reuses the financial layer's verifier).  None = no
    # amount / not checked.
    amount_verified = Column(Boolean, nullable=True)

    prompt_version = Column(String, nullable=True)
    source_meta_json = Column(Text, nullable=True)  # raw LLM item -- keep everything

    # Evidence link (Slice 5) -- structured EvidenceSpan this clause was read
    # from, plus a denormalized locator. Nullable; one span per record (no
    # many-to-many). See FinancialRecord for full semantics.
    evidence_span_id = Column(
        UUID(as_uuid=True),
        ForeignKey("evidence_span.id", ondelete="SET NULL"),
        nullable=True,
    )
    evidence_locator_json = Column(Text, nullable=True)
