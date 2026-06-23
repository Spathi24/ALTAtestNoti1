"""Home Depot Pro purchase ledger (variable-cost leak #1 in CLAUDE.md).

The owner's Home Depot *Pro* account exposes two manual Excel exports:

* the **transaction** export -- 24 months of purchase headers (sales date,
  transaction number, store, job name, status, purchaser, subtotal, total).
  This is the master index; it has NO line items.
* the **detail** export -- per-transaction line items (SKU, product name,
  quantity, unit price, line subtotal). The site only emits this one
  transaction at a time, behind ~5 clicks, which is why a backfill bot exists.

These two tables hold both, joined by ``transaction_number`` (the natural key
printed on every Home Depot receipt, e.g. ``7149-00007-62120-20260622``).

Discipline mirrors the rest of ALTA: raw values are preserved verbatim
(``job_name_raw``, ``product_name``), classification fields are
validated-with-fallback strings (unknown -> catch-all, never crash), and the
``source_meta_json`` keeps the untouched export row. No arithmetic is trusted
to the source -- the importer re-derives tax and reconciles the line-item sum
against the header subtotal so a mis-scanned receipt is *surfaced*, not hidden.

These are a self-contained ledger (like the labour-intake tables): standalone
entities keyed by their own natural key, NOT bridged through ``ExternalId``.
``Project`` stays the join nucleus -- a transaction's ``job_name`` is resolved
to a ``project_id`` so Home Depot spend rolls up per project, but the link is
kept (job_name_raw never discarded) and never guessed (unmatched -> unresolved).
"""

from __future__ import annotations

from sqlalchemy import (
    Boolean,
    Column,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID

from project_db.db.base import Base, CanonicalMixin

# --- Controlled vocabularies (validated-with-fallback strings, never DB enums) -

# Lifecycle of a transaction's line-item backfill. The transaction header lands
# first (from the bulk transaction export); the detail rows arrive later (manual
# detail export or the backfill bot), so each header tracks its own detail state.
HD_DETAIL_STATUSES = {
    "pending",  # header known, no line items yet -- the backfill queue
    "imported",  # line items present and reconciled against the subtotal
    "unbalanced",  # line items present but their sum != header subtotal (review)
    "no_items",  # detail page genuinely has no line items (e.g. a fee/adjustment)
    "skipped",  # operator chose not to backfill (e.g. tiny refund noise)
    "failed",  # the backfill bot tried and errored (see detail_last_error)
}

# How a transaction's job_name was resolved to a Project.
HD_PROJECT_MATCH_METHODS = {
    "job_name",  # job_name matched a project name/code substring or alias
    "manual",  # a human assigned it
    "unresolved",  # no confident match -- kept as raw text, never guessed
}


class HomeDepotTransaction(Base, CanonicalMixin):
    """One Home Depot Pro purchase header (one row of the transaction export).

    ``transaction_number`` is the natural key and is unique: re-importing the
    same export upserts in place rather than duplicating. Totals are stored as
    the export gives them; ``tax`` and ``is_refund`` are re-derived, never
    trusted to the source.
    """

    __table_args__ = (
        UniqueConstraint("transaction_number", name="uq_home_depot_transaction_number"),
    )

    # Natural key -- the receipt/transaction number, e.g. 7149-00007-62120-20260622.
    transaction_number = Column(String, nullable=False)

    sales_date = Column(Date, nullable=True)
    purchase_location = Column(String, nullable=True)  # store name, e.g. BEAUBIEN OUEST

    # Verbatim job/PO label off the receipt -- NEVER discarded, even once resolved.
    job_name_raw = Column(String, nullable=True)
    status = Column(String, nullable=True)  # Paid / Refunded / ...
    purchaser = Column(String, nullable=True)

    subtotal = Column(Numeric(14, 2), nullable=True)  # pre-tax, as exported
    total = Column(Numeric(14, 2), nullable=True)  # tax-in, as exported
    tax = Column(Numeric(14, 2), nullable=True)  # re-derived: total - subtotal
    currency = Column(String, nullable=True, default="CAD")
    is_refund = Column(Boolean, nullable=False, default=False)  # negative total

    # Project link -- job_name resolved to the join nucleus. Nullable + raw kept.
    project_id = Column(
        UUID(as_uuid=True),
        ForeignKey("project.canonical_id"),
        nullable=True,
    )
    project_match_method = Column(String, nullable=False, default="unresolved")
    project_match_confidence = Column(Float, nullable=True)

    # Line-item backfill state (the queue lives on the header, not a side table).
    detail_status = Column(String, nullable=False, default="pending")
    line_item_count = Column(Integer, nullable=False, default=0)
    line_items_subtotal = Column(Numeric(14, 2), nullable=True)  # sum of line subtotals
    reconciled = Column(Boolean, nullable=True)  # line sum ~= header subtotal
    reconcile_delta = Column(Numeric(14, 2), nullable=True)  # line sum - subtotal
    detail_attempts = Column(Integer, nullable=False, default=0)
    detail_last_error = Column(Text, nullable=True)
    detail_fetched_at = Column(DateTime, nullable=True)

    # Set when this row is a confirmed duplicate of another transaction -- e.g.
    # the online-order twin (`0641...`) of an in-store transaction (`7149-...`)
    # for the same amount/date/project, which Home Depot's export lists twice.
    # A flagged row is EXCLUDED from every total but kept intact (reversible,
    # evidence preserved) -- the dedupe twin of the financial reconcile gate.
    duplicate_of_id = Column(
        UUID(as_uuid=True),
        ForeignKey("home_depot_transaction.canonical_id"),
        nullable=True,
    )

    # Provenance.
    source_export_file = Column(String, nullable=True)
    source_meta_json = Column(Text, nullable=True)  # untouched export row


class HomeDepotLineItem(Base, CanonicalMixin):
    """One line item of one Home Depot transaction (a row of the detail export).

    Carries ``transaction_number`` denormalized so detail rows can be ingested
    and matched even if the header has not been imported yet. Re-importing a
    transaction's detail replaces its line items wholesale (fresh snapshot),
    mirroring the financial extractor's delete-and-rebuild discipline.
    """

    transaction_id = Column(
        UUID(as_uuid=True),
        ForeignKey("home_depot_transaction.canonical_id", ondelete="CASCADE"),
        nullable=True,
    )
    # Denormalized natural key of the parent -- matching anchor + human-readable.
    transaction_number = Column(String, nullable=False)
    line_number = Column(Integer, nullable=True)  # order within the receipt

    sku = Column(String, nullable=True)  # Home Depot SKU / internet number
    product_name = Column(Text, nullable=True)  # verbatim description
    quantity = Column(Numeric(12, 3), nullable=True)
    unit_price = Column(Numeric(14, 4), nullable=True)
    subtotal = Column(Numeric(14, 2), nullable=True)  # extended line price

    # Denormalized from the parent for cheap per-project / per-item querying.
    project_id = Column(
        UUID(as_uuid=True),
        ForeignKey("project.canonical_id"),
        nullable=True,
    )
    sales_date = Column(Date, nullable=True)
    purchase_location = Column(String, nullable=True)

    # Reserved for the (later) AI categoriser -- deterministic import leaves null.
    category_guess = Column(String, nullable=True)

    source_export_file = Column(String, nullable=True)
    source_meta_json = Column(Text, nullable=True)
