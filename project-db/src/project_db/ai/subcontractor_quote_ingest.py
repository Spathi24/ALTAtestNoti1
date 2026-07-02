"""Phase 4: ingest a subcontractor QUOTE document into one SubcontractorQuote +
its cost-side FinancialLineItem rows.

Deliberately SEPARATE from ``financial_grid_populator._collect_quote_rows``,
which is built for CLIENT quotes (side=revenue). A subcontractor quote is
COST-side: the vendor's price to do a trade's scope.

Reuses the existing spine -- ``build_evidence_bundle`` (DocumentParse +
EvidenceSpan) for the structured table + citation, and
``parse_financial_grid_rows`` for the deterministic Material/Labour/Total walk.
NO new parser, NO LLM, NO broad ingestion subsystem.

Invariants enforced here (owner review 2026-07-02):
  * cost line rows are side="cost", cost_status="quoted", purchase_type set;
  * a *selected* quote stays cost_status="quoted" -- selection is INTENT, not a
    commitment (commitment starts at PO award, Phase 5, not here);
  * the division_total / grand_total are RECONCILIATION CHECKS only -- they are
    NOT written as cost rows, so the material/labour split is preserved and no
    section total is double-counted with its line items;
  * SOW_Item_Ref resolves to SowItem.item_code scoped to the project; an
    unresolved/missing ref is FLAGGED (warning + source_meta), never silently
    assigned to a wrong item;
  * this module never creates a PurchaseOrder, ContractObligation, or
    BudgetSnapshot, and never marks anything committed.

Idempotent per document: existing SubcontractorQuote + FinancialLineItem rows
for the document are deleted and replaced on each call.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from decimal import Decimal

from project_db.ai.evidence_bundle import build_evidence_bundle
from project_db.ai.financial_grid import _looks_like_header, parse_financial_grid_rows
from project_db.db.models.finance import FinancialLineItem, SubcontractorQuote
from project_db.db.models.sow import SowItem

EXTRACTOR_VERSION = "subquote-v1"

# Quote status tokens that may appear in the filename (SUBCONTRACTOR_QUOTE_STATUSES
# minus "awarded", which is set at PO conversion, not read off a quote file).
_STATUS_TOKENS = ("pending", "recommended", "selected", "rejected")


@dataclass
class SubQuoteResult:
    document_id: str
    quote_id: str | None = None
    status: str = "pending"
    rows_written: int = 0
    grand_total: object = None  # stated Pre-Tax total (cross-check)
    division_total: object = None  # Σ section subtotals (cross-check)
    line_item_sum: object = None  # Σ material+labour cost rows actually written
    reconcile_ok: bool | None = None  # line_item_sum == grand_total (or div total)
    resolved_refs: int = 0
    unresolved_refs: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def _status_from_name(name: str | None) -> str:
    """Deterministic quote status from the filename marker; default 'pending'."""
    n = (name or "").lower()
    for tok in _STATUS_TOKENS:
        if re.search(rf"[_\-\s]{tok}\b", n):
            return tok
    return "pending"


def _select_quote_table(bundle):
    """Pick the one structured table that is a quote grid.

    A real QUOTE workbook carries more than one table_region span (Quote_Lines
    plus the Parser_Contract metadata sheet), so we cannot assume a single table.
    Select by the money-column header signature (Material + Total Amount) -- the
    same deterministic check the grid parser uses -- so the Parser_Contract sheet
    (no money columns) is never chosen. Returns the BundleTable or None.
    """
    if bundle is None:
        return None
    candidates = [t for t in bundle.tables if _looks_like_header([str(h) for h in t.headers])]
    if not candidates:
        return None
    # If more than one financial-looking table, take the one with the most rows.
    return max(candidates, key=lambda t: len(t.rows_preview))


def _extract_coverage_fields(table) -> dict[str, str | None]:
    """Best-effort quote-level coverage text from the chosen table's own columns.

    Populates ``exclusions`` (concatenated non-empty Exclusions cells) and
    ``materials_included`` (concatenated non-empty Mat_Incl cells). ``coverage``
    and ``assumptions`` are left None unless the sheet clearly carries them --
    the structured, per-line SOW linkage lives on the FinancialLineItem rows via
    sow_item_id, so these quote-level text fields are supplementary, not the
    source of truth. Never raises.
    """
    out: dict[str, str | None] = {
        "coverage": None,
        "exclusions": None,
        "assumptions": None,
        "materials_included": None,
    }
    try:
        rows = (table.rows if table is not None else None) or []
        excl = [str(r.get("Exclusions")).strip() for r in rows if str(r.get("Exclusions") or "").strip()]
        mats = [str(r.get("Mat_Incl")).strip() for r in rows if str(r.get("Mat_Incl") or "").strip()]
        if excl:
            out["exclusions"] = "; ".join(excl)
        if mats:
            out["materials_included"] = "; ".join(sorted(set(mats)))
    except Exception:
        pass
    return out


def ingest_subcontractor_quote(
    session,
    document,
    *,
    project_id,
    package_id=None,
    vendor_id=None,
    division_code: str | None = None,
    status: str | None = None,
) -> SubQuoteResult:
    """Parse one subcontractor QUOTE document into a SubcontractorQuote + cost rows.

    ``project_id`` is required (SOW resolution is project-scoped). ``package_id``,
    ``vendor_id`` and ``division_code`` are resolved by the caller (kept out of
    this function so it stays a narrow, testable populator, not a routing/identity
    subsystem). ``status`` defaults to the filename marker.
    """
    result = SubQuoteResult(document_id=str(document.canonical_id))
    status = (status or _status_from_name(document.name)).lower()
    result.status = status

    bundle = build_evidence_bundle(session, document)
    qtable = _select_quote_table(bundle)
    if qtable is None:
        result.warnings.append(
            "no quote grid table found (document not parsed, or no Material/Total "
            "Amount table) -- subcontractor-quote ingest needs a Quote_Lines table"
        )
        return result

    grid_rows = [["" if c is None else str(c) for c in r] for r in qtable.rows_preview]
    grid = parse_financial_grid_rows(grid_rows)
    result.warnings.extend(grid.warnings)
    if not grid.header_found:
        result.warnings.append("Material/Labour/Total header row not found")
        return result

    # Cite the exact table we parsed (not just the bundle's primary).
    ev_span_id = qtable.span_id
    ev_loc = json.dumps(qtable.locator) if qtable.locator else None
    doc_date = document.modified_at_source.date() if document.modified_at_source else None

    # Resolve every SOW_Item_Ref seen on line items to a SowItem (project-scoped).
    line_rows = [r for r in grid.rows if r.kind == "line_item"]
    refs = {r.sow_item_ref for r in line_rows if r.sow_item_ref}
    ref_to_id: dict[str, object] = {}
    for ref in refs:
        hit = (
            session.query(SowItem)
            .filter(SowItem.project_id == project_id, SowItem.item_code == ref)
            .one_or_none()
        )
        if hit is not None:
            ref_to_id[ref] = hit.canonical_id
        else:
            result.unresolved_refs.append(ref)
            result.warnings.append(
                f"SOW_Item_Ref {ref!r} not found in project -- cost row left unlinked (flagged, not assigned)"
            )
    result.resolved_refs = len(ref_to_id)

    # Build the cost line items: material/labour ONLY. division_total rows are
    # NOT written (they are section checks); grand_total is a reconciliation
    # cross-check. This preserves the material/labour split and prevents any
    # section-total-vs-line-item double count.
    items: list[FinancialLineItem] = []
    line_sum = Decimal(0)
    for row in line_rows:
        ref = row.sow_item_ref or ""
        sow_item_id = ref_to_id.get(ref) if ref else None
        if not ref:
            result.warnings.append(
                f"line {row.description!r} has no SOW_Item_Ref -- cost row left unlinked (flagged)"
            )
        line_sum += row.amount
        items.append(
            FinancialLineItem(
                project_id=project_id,
                document_id=document.canonical_id,
                division_code=row.division_code,
                division_name=row.division_name,
                side="cost",
                amount_type=row.amount_type,  # material | labour
                status="unknown",  # revenue-recognition axis: N/A for cost rows
                cost_status="quoted",  # COST lifecycle: quoted (selected stays quoted)
                purchase_type="vendor",  # subcontractor trade quote
                sow_item_id=sow_item_id,
                line_markup_factor=1.0,
                doc_role="quote",
                description=row.description,
                amount=row.amount,
                currency="CAD",
                doc_date=doc_date,
                source="grid",
                quoted_excerpt=f"{row.description}: {row.amount}",
                amount_verified=True,
                confidence=1.0,
                extractor_version=EXTRACTOR_VERSION,
                classification_method="deterministic",
                classification_confidence=1.0,
                source_doc_type="quote",
                evidence_span_id=ev_span_id,
                evidence_locator_json=ev_loc,
                source_meta_json=json.dumps(
                    {
                        "kind": row.kind,
                        "masterformat_hint": row.masterformat_hint,
                        "sow_item_ref": ref,
                        "sow_item_resolved": sow_item_id is not None,
                    }
                ),
            )
        )

    result.grand_total = grid.grand_total
    result.division_total = grid.division_total
    result.line_item_sum = line_sum
    check = grid.grand_total if grid.grand_total is not None else (grid.division_total or None)
    if check is not None:
        result.reconcile_ok = line_sum == check
        if not result.reconcile_ok:
            result.warnings.append(
                f"line-item sum {line_sum} != stated total {check} (reconcile flag)"
            )

    cov = _extract_coverage_fields(qtable)
    quote = SubcontractorQuote(
        project_id=project_id,
        package_id=package_id,
        vendor_id=vendor_id,
        document_id=document.canonical_id,
        division_code=division_code or (line_rows[0].division_code if line_rows else None),
        status=status,
        amount=grid.grand_total if grid.grand_total is not None else (grid.division_total or None),
        currency="CAD",
        quote_date=doc_date,
        coverage=cov["coverage"],
        exclusions=cov["exclusions"],
        assumptions=cov["assumptions"],
        materials_included=cov["materials_included"],
        evidence_span_id=ev_span_id,
        evidence_locator_json=ev_loc,
        source="grid",
        source_meta_json=json.dumps(
            {
                "unresolved_sow_refs": result.unresolved_refs,
                "line_item_count": len(items),
            }
        ),
    )

    # Idempotent per document: replace this document's quote + cost rows.
    # FUTURE HARDENING (recorded 2026-07-02, not yet needed): this deletes ALL
    # FinancialLineItem rows for the document_id, not just the ones THIS
    # extractor wrote. Fine while one document has exactly one extractor. If a
    # second extractor (e.g. an LLM fallback) can ever touch the same
    # document_id, narrow this to
    # filter_by(document_id=..., extractor_version=EXTRACTOR_VERSION) so one
    # extractor's re-run can't silently delete another extractor's rows.
    session.query(SubcontractorQuote).filter(
        SubcontractorQuote.document_id == document.canonical_id
    ).delete(synchronize_session="fetch")
    session.query(FinancialLineItem).filter(
        FinancialLineItem.document_id == document.canonical_id
    ).delete(synchronize_session="fetch")

    session.add(quote)
    session.flush()  # populate quote.canonical_id
    session.add_all(items)

    result.quote_id = str(quote.canonical_id)
    result.rows_written = len(items)
    return result
