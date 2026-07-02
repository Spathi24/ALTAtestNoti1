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
    Float,
    ForeignKey,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy import (
    Enum as SAEnum,
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
    "quote",
    "estimate",
    "invoice",
    "receipt",
    "change_order",
    "other",
}
# What the individual amount represents within its document.  Used by the
# reconciliation report to avoid double-counting a line item AND its total.
FINANCIAL_RECORD_KINDS = {"total", "line_item", "tax", "deposit", "other"}

# --- FinancialLineItem vocabularies (the division-keyed redesign) -----------
# See docs/FINANCIAL_REDESIGN.md.  Same validated-with-fallback discipline:
# unknown values coerce to the catch-all + warn, never crash.
# Which side of the margin equation a row sits on.
LINE_ITEM_SIDES = {"revenue", "cost", "budget", "quantity", "unknown"}
# What the amount represents -- captures Material/Labour/Total columns of a
# client quote, markup rows, and change-order/extras totals.
LINE_ITEM_AMOUNT_TYPES = {
    "material",
    "labour",
    "total",
    "markup",
    "contingency",
    "tax",
    "deposit",
    "adjustment",  # extras / change-order line item
    "other",
}
# Lifecycle status, promoted from the filename marker + modifiedTime tiebreak.
LINE_ITEM_STATUSES = {"accepted", "proposed", "actual", "superseded", "unknown"}
# Which populator produced the row: deterministic grid parse vs LLM extraction.
LINE_ITEM_SOURCES = {"grid", "llm", "grid/extras"}
# How the row's document was classified before ingestion.
LINE_ITEM_CLASSIFICATION_METHODS = {
    "deterministic",  # exact header/marker match
    "fuzzy",  # normalised keyword match
    "llm_assisted",  # LLM returned a bounded classification JSON
    "manual",  # human-overridden
    "unknown",  # classification was not attempted / not stored
}
# Source document type (matches classify_financial_sheet output).
LINE_ITEM_SOURCE_DOC_TYPES = {"quote", "extras", "job_cost", "order_quantities", "unknown"}

# --- Phase 4 vocabularies (subcontractor quotes + cost lifecycle) -----------
# SubcontractorQuote lifecycle (the ONE quote status vocabulary, settled §12):
#   pending    -- collected, not yet evaluated
#   recommended-- AI-proposed via the Proposal gate, awaiting human decision
#   selected   -- human INTENT to use it (NOT a commitment; cost stays "quoted")
#   rejected   -- not chosen
#   awarded    -- a PO has been issued for it (set at PO conversion, Phase 5 -- NOT here)
SUBCONTRACTOR_QUOTE_STATUSES = {"pending", "recommended", "selected", "rejected", "awarded"}

# FinancialLineItem.cost_status -- the COST lifecycle axis. Distinct from the
# existing `status` column (accepted/proposed/... = revenue recognition). A
# subcontractor quote line is cost_status="quoted"; only a PO (Phase 5) moves it
# to "committed"; an invoice/receipt moves it to "actual".
COST_STATUSES = {"estimated", "quoted", "committed", "actual", "unknown"}

# FinancialLineItem.purchase_type -- what kind of spend the cost row is.
PURCHASE_TYPES = {
    "vendor",  # a subcontractor trade quote/invoice
    "supplier",  # a material supplier
    "home_depot",  # Home Depot Pro purchases (type 3)
    "hourly",  # hourly labour (type 4)
    "transportation",  # delivery / transport
    "other",
}

# --- Phase 5 vocabulary (PurchaseOrder lifecycle) ----------------------------
# A PurchaseOrder row is created BY the award action (see
# ai/purchase_order_award.award_purchase_order) -- there is no "draft PO" state
# in this model. "cancelled" exists for a PO that is voided after issuance
# (e.g. the sub falls through); cancelling a PO does not delete it or its
# ContractObligation -- that is a future reconciliation concern, not Phase 5.
PURCHASE_ORDER_STATUSES = {"awarded", "cancelled"}


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
    status = Column(SAEnum(InvoiceStatus), nullable=False, default=InvoiceStatus.DRAFT)

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

    counterparty = Column(String, nullable=True)  # client or contractor name
    description = Column(Text, nullable=True)  # what the amount is for
    phase = Column(String, nullable=True)  # phase label, if phased

    amount = Column(Numeric(14, 2), nullable=True)
    currency = Column(String, nullable=True)  # e.g. CAD, USD
    doc_date = Column(Date, nullable=True)  # date on the document

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

    # Evidence link (Slice 5) -- the structured EvidenceSpan this amount was read
    # from, plus a denormalized locator (page/sheet/cell range) for citation
    # without a join. Nullable: pre-refactor rows and rows extracted from flat
    # text have neither. One span per record (no many-to-many); any extra spans
    # live in source_meta_json during transition. Invariant enforced by a later
    # slice: no NEW trusted record without an evidence link.
    evidence_span_id = Column(
        UUID(as_uuid=True),
        ForeignKey("evidence_span.id", ondelete="SET NULL"),
        nullable=True,
    )
    evidence_locator_json = Column(Text, nullable=True)


class FinancialLineItem(Base, CanonicalMixin):
    """One amount on the division-keyed line-item ledger (the redesign).

    Differs from ``FinancialRecord`` in shape, not philosophy: it keeps
    LINE ITEMS (not collapsed totals), tags each to a controlled CSI
    ``division_code`` and a ``unit`` (923 / 921 / 927 / exterior), splits
    material vs labour vs markup via ``amount_type``, and carries a
    proposed-vs-accepted ``status``.  Reconciliation pivots by
    ``(unit, division_code)``: margin = revenue rows - cost rows.

    Coexists with ``FinancialRecord`` during transition (see
    docs/FINANCIAL_REDESIGN.md §3); the legacy aggregate-net report is retired
    only once this ledger reaches parity on Rockland.  Classification columns
    are validated-with-fallback strings (unknown -> catch-all + warn), never
    rejected -- the schema must outlive document-convention drift.
    """

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

    # Sub-scope within the project (923 / 921 / 927 / exterior); None = whole.
    unit = Column(String, nullable=True)

    # Controlled CSI division (ai/financial_divisions.py); denormalized name.
    division_code = Column(String, nullable=False, default="99")
    division_name = Column(String, nullable=True)

    side = Column(String, nullable=False, default="unknown")  # revenue/cost/unknown
    amount_type = Column(String, nullable=False, default="total")  # material/labour/...
    status = Column(String, nullable=False, default="unknown")  # accepted/proposed/...

    doc_role = Column(String, nullable=True)  # quote/estimate/invoice/change_order
    description = Column(Text, nullable=True)

    amount = Column(Numeric(14, 2), nullable=True)
    currency = Column(String, nullable=True)
    doc_date = Column(Date, nullable=True)
    quote_expiry = Column(Date, nullable=True)  # "Valid Until" -- re-price if past

    source = Column(String, nullable=True)  # grid / llm / grid/extras -- which populator
    quoted_excerpt = Column(Text, nullable=True)
    confidence = Column(Float, nullable=True)
    amount_verified = Column(Boolean, nullable=True)
    extractor_version = Column(String, nullable=True)
    source_meta_json = Column(Text, nullable=True)

    # Classification provenance (Phase 1c-MVP) --------------------------------
    # How was this document classified before ingestion?
    classification_method = Column(String, nullable=True)  # deterministic | fuzzy | ...
    # Classifier confidence [0, 1]. None = not computed (pre-MVP rows).
    classification_confidence = Column(Float, nullable=True)
    # Which document type the classifier assigned (matches classify_financial_sheet).
    source_doc_type = Column(String, nullable=True)  # quote | extras | job_cost | ...

    # Evidence link (Slice 5) -- structured EvidenceSpan this line was read from,
    # plus a denormalized locator. See FinancialRecord above; same semantics.
    evidence_span_id = Column(
        UUID(as_uuid=True),
        ForeignKey("evidence_span.id", ondelete="SET NULL"),
        nullable=True,
    )
    evidence_locator_json = Column(Text, nullable=True)
    # Sub-region within a multi-block document (e.g. "material_spending_block").
    source_region = Column(String, nullable=True)

    # --- Phase 4 additions (cost lifecycle + SOW traceability) --------------
    # What kind of spend this cost row is (PURCHASE_TYPES). None on pre-Phase-4
    # rows and on revenue rows.
    purchase_type = Column(String, nullable=True)
    # The COST lifecycle (COST_STATUSES): estimated -> quoted -> committed ->
    # actual. SEPARATE from `status` (which is revenue recognition). A
    # subcontractor quote line is "quoted"; a *selected* quote stays "quoted"
    # (selection is intent) -- only a PO (Phase 5) makes it "committed".
    cost_status = Column(String, nullable=True)
    # The scope item this cost prices, resolved from the quote's SOW_Item_Ref
    # against SowItem.item_code (project-scoped). Nullable: unresolved refs are
    # flagged, never silently assigned. One SowItem may back many line items.
    sow_item_id = Column(
        UUID(as_uuid=True),
        ForeignKey("sow_item.canonical_id", ondelete="SET NULL"),
        nullable=True,
    )
    # Client-price multiplier applied at REPORT time (presentation only); the
    # ledger amount stays the internal cost. Default 1.0 = no markup stored.
    line_markup_factor = Column(Float, nullable=True)
    # Which SubcontractorQuote priced this cost row (Phase 5). Set at ingest
    # time by subcontractor_quote_ingest; read by the PO-award conversion to
    # find which rows flip cost_status quoted -> committed. Do NOT add a
    # redundant purchase_order_id here -- PurchaseOrder.subcontractor_quote_id
    # is the other end of that join.
    subcontractor_quote_id = Column(
        UUID(as_uuid=True),
        ForeignKey("subcontractor_quote.canonical_id", ondelete="SET NULL"),
        nullable=True,
    )


class SubcontractorQuote(Base, CanonicalMixin):
    """One subcontractor/vendor quote for one SowPackage (trade).

    Phase 4 of the refoundation. The quote is the priced response to a tendering
    package: a vendor's amount to do a trade's scope, with the coverage /
    exclusions / assumptions that determine whether the price actually covers the
    whole SOW (the owner's "compare coverage, not just price" rule).

    Status is the ONE settled quote vocabulary (SUBCONTRACTOR_QUOTE_STATUSES):
    pending -> recommended -> selected/rejected -> awarded. ``selected`` is human
    INTENT only -- it does NOT create committed cost. ``awarded`` is set later at
    PO conversion (Phase 5); this model never issues a PO or emits a
    ContractObligation.

    Evidence-linked like the rest of the ledger: ``evidence_span_id`` cites the
    parsed table region the amount was read from. Cost line items derived from
    this quote live in ``FinancialLineItem`` (side=cost, cost_status=quoted),
    associated by shared ``document_id``.
    """

    project_id = Column(
        UUID(as_uuid=True),
        ForeignKey("project.canonical_id"),
        nullable=True,
    )
    package_id = Column(
        UUID(as_uuid=True),
        ForeignKey("sow_package.canonical_id"),
        nullable=True,
    )
    vendor_id = Column(
        UUID(as_uuid=True),
        ForeignKey("vendor.canonical_id"),
        nullable=True,
    )
    document_id = Column(
        UUID(as_uuid=True),
        ForeignKey("document.canonical_id", ondelete="CASCADE"),
        nullable=True,
    )

    division_code = Column(String, nullable=True)  # CSI code of the package/trade
    status = Column(String, nullable=False, default="pending")  # SUBCONTRACTOR_QUOTE_STATUSES

    amount = Column(Numeric(14, 2), nullable=True)  # pre-tax quote total (grand_total)
    currency = Column(String, nullable=True)
    quote_date = Column(Date, nullable=True)

    # Coverage evidence -- how the quote maps against the SOW. Free text /
    # concatenated cell values; the structured line-level linkage lives on the
    # derived FinancialLineItem rows via sow_item_id.
    coverage = Column(Text, nullable=True)  # what it covers / Coverage_Y_N summary
    exclusions = Column(Text, nullable=True)  # concatenated Exclusions cells
    assumptions = Column(Text, nullable=True)
    materials_included = Column(Text, nullable=True)  # Mat_Incl summary

    # Evidence + provenance (same pattern as FinancialLineItem/FinancialRecord).
    evidence_span_id = Column(
        UUID(as_uuid=True),
        ForeignKey("evidence_span.id", ondelete="SET NULL"),
        nullable=True,
    )
    evidence_locator_json = Column(Text, nullable=True)
    source = Column(String, nullable=True)  # "grid" -- which populator produced it
    source_meta_json = Column(Text, nullable=True)


class PurchaseOrder(Base, CanonicalMixin):
    """One Purchase Order: the operational artifact created by AWARDING a
    ``selected`` SubcontractorQuote (Phase 5). A PurchaseOrder is always
    created BY the award action (``ai/purchase_order_award.award_purchase_order``)
    -- there is no separate "create a draft PO" path, so ``subcontractor_quote_id``
    is required (one PO per quote; a duplicate award attempt is rejected by the
    unique constraint below, not silently re-issued).

    The PO is the OPERATIONAL fact ("we ordered this"); the ``ContractObligation``
    it emits is the LEGAL/FINANCIAL consequence ("we now owe this money"). Awarding
    a PO does not delete or rewrite the originating quote or its cost line items --
    it flips their lifecycle fields in place (SubcontractorQuote.status ->
    "awarded", the linked FinancialLineItem rows' cost_status -> "committed") so
    quote history and SOW linkage survive the conversion.
    """

    project_id = Column(
        UUID(as_uuid=True),
        ForeignKey("project.canonical_id"),
        nullable=True,
    )
    package_id = Column(
        UUID(as_uuid=True),
        ForeignKey("sow_package.canonical_id"),
        nullable=True,
    )
    vendor_id = Column(
        UUID(as_uuid=True),
        ForeignKey("vendor.canonical_id"),
        nullable=True,
    )
    # The quote this PO converts. Required + unique: exactly one PO per quote.
    subcontractor_quote_id = Column(
        UUID(as_uuid=True),
        ForeignKey("subcontractor_quote.canonical_id"),
        nullable=False,
    )

    po_number = Column(String, nullable=False)  # YYYYNNN-PPP, auto-generated
    division_code = Column(String, nullable=True)
    status = Column(String, nullable=False, default="awarded")  # PURCHASE_ORDER_STATUSES

    contract_amount = Column(Numeric(14, 2), nullable=True)
    currency = Column(String, nullable=True)
    awarded_date = Column(Date, nullable=True)
    terms = Column(Text, nullable=True)

    source_meta_json = Column(Text, nullable=True)

    __table_args__ = (
        UniqueConstraint("po_number", name="uq_purchase_order_po_number"),
        UniqueConstraint(
            "subcontractor_quote_id", name="uq_purchase_order_subcontractor_quote_id"
        ),
    )


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


# Slice 8: cross-document reconciliation findings (advisory, human-reviewed).
RECONCILIATION_ISSUE_TYPES = {
    "rollup_double_count",  # a summary/SOW doc restates money priced in another doc
    "duplicate_total",  # two docs with the same total (likely the same money twice)
    "side_error",  # a doc sided revenue/cost against its issuer/BILL-TO evidence
    "restatement",  # a later doc restates/supersedes an earlier one
    "unreconciled",  # an extraction whose lines don't sum to its stated total
    "missing_evidence",  # a trusted record with no evidence link
    "other",
}
RECONCILIATION_SEVERITIES = {"high", "medium", "low"}
# open -> a human acknowledges / resolves / dismisses it (advisory, never auto-acts).
RECONCILIATION_STATUSES = {"open", "acknowledged", "resolved", "dismissed"}
RECONCILIATION_SOURCES = {"deterministic", "llm"}


class ReconciliationIssue(Base, CanonicalMixin):
    """One cross-document reconciliation finding (Slice 8).

    Advisory only -- like ``Proposal``, a human acknowledges/resolves/dismisses it;
    nothing here mutates the ledger automatically. Stores the issue type, severity,
    a human-readable description, the dollar delta it represents, and an
    ``evidence_json`` blob naming the documents / records / EvidenceSpans involved
    so a reviewer can trace it. Produced by the deterministic detector and/or the
    LLM cross-doc auditor (``source``).
    """

    project_id = Column(
        UUID(as_uuid=True),
        ForeignKey("project.canonical_id"),
        nullable=True,
        index=True,
    )
    issue_type = Column(String, nullable=False)  # one of RECONCILIATION_ISSUE_TYPES
    severity = Column(String, nullable=False, default="medium")
    status = Column(String, nullable=False, default="open")
    source = Column(String, nullable=False, default="deterministic")
    description = Column(Text, nullable=True)
    # The money this issue represents (e.g. the double-counted amount). Signed or
    # absolute by convention of the detector; kept for ranking by impact.
    delta_amount = Column(Numeric(14, 2), nullable=True)
    currency = Column(String, nullable=True)
    # JSON: {documents: [...], records: [...], evidence_span_ids: [...], amounts: {...}}
    evidence_json = Column(Text, nullable=True)
    # A stable key so the same finding isn't stored twice across re-runs.
    dedupe_key = Column(String, nullable=True, index=True)
    prompt_version = Column(String, nullable=True)  # set when source='llm'
    decided_by = Column(String, nullable=True)
    decided_at = Column(DateTime, nullable=True)
