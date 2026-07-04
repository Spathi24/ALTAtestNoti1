"""Phase 5: award a PurchaseOrder by converting a `selected` SubcontractorQuote.

This is the ONE place that creates committed cost. Everything upstream of it
(Phase 4's subcontractor-quote ingest) only ever writes cost_status="quoted" --
by design, so a selected quote never silently becomes a financial commitment.

The award action:
  1. Requires the quote to be `status="selected"` (human intent already
     recorded) -- pending/recommended/rejected/already-awarded quotes are
     refused, not silently converted.
  2. Requires at least one FinancialLineItem with cost_status="quoted" linked
     to this quote (owner review 2026-07-02, "checkpoint" pass) -- refuses to
     create a PO/obligation backed by zero cost rows ("phantom money-at-risk":
     a recorded commitment with nothing in the ledger behind it).
  3. Creates ONE PurchaseOrder (auto po_number `{project.code}-{PPP}`), unique
     per quote -- a duplicate award raises (UniqueConstraint), it does not
     re-issue a second PO.
  4. Flips SubcontractorQuote.status -> "awarded" IN PLACE. The quote row is
     never deleted or rewritten -- award is a status transition, so quote
     history (coverage/exclusions/amount/evidence) survives.
  5. Flips cost_status "quoted" -> "committed" on exactly the FinancialLineItem
     rows this quote produced AND that are currently "quoted" (found via
     subcontractor_quote_id + cost_status='quoted', an UPDATE, never a
     delete+reinsert -- SOW linkage and amounts must not change). Scoping the
     UPDATE to cost_status='quoted' is defense-in-depth: no code path today
     produces a quote-linked row in any other cost_status, but the guard means
     a future one couldn't be silently overwritten by an award.
  6. Emits exactly one ContractObligation (owed_by_us, kind="po_commitment"),
     reusing the quote's evidence_span_id for traceability.

Deliberately narrow: no filename parsing, no vendor/package resolution (those
stay the caller's job -- see REFOUNDATION_BUILD_NOTES.md "Phase 5 design
decisions" #3), no budget/green-sheet interaction (Phase 6).
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import date

from sqlalchemy.exc import IntegrityError

from project_db.db.models.core import Vendor
from project_db.db.models.finance import FinancialLineItem, PurchaseOrder, SubcontractorQuote
from project_db.db.models.obligations import ContractObligation
from project_db.db.models.work import Project


class PurchaseOrderAwardError(ValueError):
    """A precondition for awarding a PO was not met (caller's bug or a stale
    quote reference) -- never raised for data-shape issues that can be flagged
    instead."""


@dataclass
class POAwardResult:
    po_id: str
    po_number: str
    obligation_id: str
    quote_id: str
    lines_committed: int = 0
    warnings: list[str] = field(default_factory=list)


def _next_po_number(session, project: Project) -> str:
    """Next sequential `{project.code}-{PPP}` PO number for this project."""
    if not project.code:
        raise PurchaseOrderAwardError(
            f"project {project.canonical_id} has no code -- cannot generate a PO number "
            "(Project.code IS project_code; see REFOUNDATION_BUILD_NOTES.md rule #3)"
        )
    prefix = f"{project.code}-"
    existing = (
        session.query(PurchaseOrder.po_number)
        .filter(PurchaseOrder.po_number.like(f"{prefix}%"))
        .all()
    )
    seqs = []
    for (num,) in existing:
        m = re.match(rf"^{re.escape(prefix)}(\d{{3}})$", num or "")
        if m:
            seqs.append(int(m.group(1)))
    next_seq = (max(seqs) + 1) if seqs else 1
    return f"{prefix}{next_seq:03d}"


def award_purchase_order(
    session,
    quote: SubcontractorQuote,
    *,
    awarded_date: date | None = None,
    contract_amount=None,
    terms: str | None = None,
) -> POAwardResult:
    """Award a PurchaseOrder for *quote*. See module docstring for the exact
    sequence of effects. Raises PurchaseOrderAwardError on an invalid quote
    state; raises IntegrityError (uncaught -- the caller's problem to handle)
    on a duplicate award attempt.
    """
    if quote.status != "selected":
        raise PurchaseOrderAwardError(
            f"SubcontractorQuote {quote.canonical_id} has status={quote.status!r}; "
            "only a 'selected' quote can be awarded a PO"
        )
    if quote.project_id is None:
        raise PurchaseOrderAwardError(
            f"SubcontractorQuote {quote.canonical_id} has no project_id -- cannot "
            "generate a PO number"
        )

    # Find the rows this award will commit BEFORE creating anything. A quote
    # with zero "quoted" cost rows (e.g. ingestion silently produced none)
    # must not become a PO/obligation with nothing backing it in the ledger.
    lines = (
        session.query(FinancialLineItem)
        .filter(
            FinancialLineItem.subcontractor_quote_id == quote.canonical_id,
            FinancialLineItem.cost_status == "quoted",
        )
        .all()
    )
    if not lines:
        raise PurchaseOrderAwardError(
            f"SubcontractorQuote {quote.canonical_id} has no FinancialLineItem rows "
            "with cost_status='quoted' -- refusing to award a PO backed by zero cost "
            "rows (would create an obligation with nothing in the ledger behind it)"
        )

    project = session.query(Project).filter_by(canonical_id=quote.project_id).one()
    po_number = _next_po_number(session, project)
    amount = contract_amount if contract_amount is not None else quote.amount

    po = PurchaseOrder(
        project_id=quote.project_id,
        package_id=quote.package_id,
        vendor_id=quote.vendor_id,
        subcontractor_quote_id=quote.canonical_id,
        po_number=po_number,
        division_code=quote.division_code,
        status="awarded",
        contract_amount=amount,
        currency=quote.currency,
        awarded_date=awarded_date,
        terms=terms,
        source_meta_json=json.dumps({"awarded_from_quote_id": str(quote.canonical_id)}),
    )
    session.add(po)
    try:
        session.flush()  # surfaces the UniqueConstraint on a duplicate award
    except IntegrityError:
        raise

    # Status transition IN PLACE -- never delete/rewrite the quote.
    quote.status = "awarded"

    # Commit exactly the "quoted" rows found above -- an UPDATE, not a
    # delete+reinsert. Re-querying here (rather than reusing `lines`) would
    # risk a race against concurrent writes between the guard check and this
    # point; iterating the already-fetched `lines` list keeps the guard and
    # the mutation looking at the exact same row set.
    for line in lines:
        line.cost_status = "committed"

    vendor_name = None
    if quote.vendor_id is not None:
        vendor = session.query(Vendor).filter_by(canonical_id=quote.vendor_id).one_or_none()
        vendor_name = vendor.name if vendor is not None else None
    obligation = ContractObligation(
        project_id=quote.project_id,
        document_id=quote.document_id,
        kind="po_commitment",
        direction="owed_by_us",
        description=f"PO {po_number} awarded" + (f" to {vendor_name}" if vendor_name else ""),
        amount=amount,
        currency=quote.currency,
        counterparty=vendor_name,
        evidence_span_id=quote.evidence_span_id,
        evidence_locator_json=quote.evidence_locator_json,
        source_meta_json=json.dumps(
            {
                "purchase_order_id": str(po.canonical_id),
                "subcontractor_quote_id": str(quote.canonical_id),
            }
        ),
    )
    session.add(obligation)
    session.flush()

    return POAwardResult(
        po_id=str(po.canonical_id),
        po_number=po_number,
        obligation_id=str(obligation.canonical_id),
        quote_id=str(quote.canonical_id),
        lines_committed=len(lines),
    )
