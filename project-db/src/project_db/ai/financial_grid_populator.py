"""Phase 1b/1c-MVP of docs/FINANCIAL_REDESIGN: persister that maps grid-parsed
rows into FinancialLineItem records.

NO LLM. Reads the stored DocumentText for a project's financial sheets,
classifies each (quote → grid parser; extras → extras parser; everything else
→ skipped or quarantined), and writes FinancialLineItem rows.

Idempotent per document: existing rows for a document are deleted and replaced
on every call. Returns a ProjectLedgerResult with per-document outcomes.

Multi-sheet routing (Phase 1c hardening):
  For xlsx workbooks the extracted text contains '### SheetName' blocks for
  each worksheet.  populate_ledger_for_document splits on those markers and
  classifies each sheet independently, so a mixed workbook (e.g. Overview +
  Measurements + ESTIMATE) correctly skips non-financial sheets and parses
  only the ESTIMATE worksheet.  Deduplication rule: if multiple sheets in the
  same workbook have the same type (e.g. 'ESTIMATE' + 'Copy of ESTIMATE'),
  only the FIRST sheet of that type is parsed — subsequent sheets of the same
  type are skipped to prevent double-counting within a single document.

Phase 1c-MVP adds:
  - ingestion_status / ingestion_reason on DocLedgerResult
  - classification_method + source_doc_type on every written row
  - extras sheet routing → parse_extras_sheet + write side=revenue rows
  - job_cost / order_quantities / unknown → skipped (ingestion_status=skipped)
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from decimal import Decimal

from project_db.ai.financial_grid import (
    classify_financial_sheet,
    parse_financial_grid,
    split_workbook_sheets,
)
from project_db.db.models.docs import Document, DocumentText
from project_db.db.models.finance import FinancialLineItem

EXTRACTOR_VERSION_QUOTE = "grid-v1"
EXTRACTOR_VERSION_EXTRAS = "extras-v1"

# Ingestion status vocab (per-document outcome; not persisted on individual rows).
INGESTION_STATUSES = {"parsed", "skipped", "quarantined", "failed"}
INGESTION_REASONS = {
    "no_header",  # expected header row not found
    "unsupported_type",  # sheet type not yet supported (job_cost, order_quantities, unknown)
    "low_confidence",  # classifier confidence below threshold
    "validation_failed",  # schema validation failed
    "no_money",  # header found but no parseable amounts
    "ambiguous_amount_meaning",  # amounts present but meaning unclear (budget vs actual)
    "parse_error",  # unexpected exception during parsing
}

# ---------------------------------------------------------------------------
# Document-level helpers
# ---------------------------------------------------------------------------


def _extract_unit(name: str | None) -> str | None:
    """Infer the scope unit from the document filename.

    Examples:
      '923 ACCEPTED QUOTE'        -> '923'
      '_927 QUOTE  (NOT STARTED)' -> '927'  (leading underscore from Drive)
      'exterior quote'             -> 'exterior'
      '923-927 ACCEPTED QUOTE'    -> None   (multi-unit / whole-project doc)
    """
    if not name:
        return None
    if re.search(r"\b\d{3,4}-\d{3,4}\b", name):
        return None
    m = re.match(r"^[\s_]*(\d{3,4})\b", name)
    if m:
        return m.group(1)
    if re.search(r"\bexterior\b", name, re.I):
        return "exterior"
    return None


def _extract_status(name: str | None) -> str:
    """Infer proposal status from the filename marker.

    'NOT STARTED' / 'NOT ACCEPTED' -> 'proposed';
    'ACCEPTED' (alone)             -> 'accepted';
    else                           -> 'unknown'.
    """
    if not name:
        return "unknown"
    n = name.upper()
    if "NOT STARTED" in n or "NOT ACCEPTED" in n:
        return "proposed"
    if "ACCEPTED" in n:
        return "accepted"
    return "unknown"


def _extract_currency(text: str | None) -> str:
    """Detect the currency from the grid header. Defaults to CAD."""
    if not text:
        return "CAD"
    head = "\n".join(text.splitlines()[:20])
    if "USD" in head:
        return "USD"
    return "CAD"


# ---------------------------------------------------------------------------
# Result containers
# ---------------------------------------------------------------------------


@dataclass
class DocLedgerResult:
    doc_id: str
    doc_name: str
    sheet_type: str
    rows_written: int = 0
    reconcile_ok: bool | None = None  # None = no grand_total to compare
    grand_total: object = None
    division_total: object = None
    warnings: list[str] = field(default_factory=list)

    # Phase 1c-MVP: richer ingestion outcome
    ingestion_status: str = "parsed"  # parsed | skipped | quarantined | failed
    ingestion_reason: str | None = None  # why non-parsed (INGESTION_REASONS vocab)

    @property
    def skipped(self) -> bool:
        """Back-compat: True when ingestion_status != 'parsed'."""
        return self.ingestion_status != "parsed"


@dataclass
class ProjectLedgerResult:
    project_id: str
    docs: list[DocLedgerResult] = field(default_factory=list)

    @property
    def total_rows(self) -> int:
        return sum(d.rows_written for d in self.docs)

    @property
    def parsed_docs(self) -> list[DocLedgerResult]:
        return [d for d in self.docs if not d.skipped]

    def summary(self) -> str:
        parsed = self.parsed_docs
        reconciled = sum(1 for d in parsed if d.reconcile_ok is True)
        failed_rec = sum(1 for d in parsed if d.reconcile_ok is False)
        skipped = sum(1 for d in self.docs if d.skipped)
        lines = [
            f"Ledger populated: {self.total_rows} rows from {len(parsed)} sheet(s)",
            f"  Reconciled: {reconciled}  "
            f"Reconcile-fail: {failed_rec}  "
            f"Skipped/quarantined: {skipped}",
        ]
        for d in self.parsed_docs:
            flag = ""
            if d.reconcile_ok is False:
                flag = " [RECONCILE FAIL]"
            elif d.reconcile_ok is True:
                flag = " [OK]"
            lines.append(
                f"  {d.doc_name!r:<40}  sheet={d.sheet_type}"
                f"  rows={d.rows_written}"
                f"  div_total={d.division_total}"
                f"  grand_total={d.grand_total}{flag}"
            )
            for w in d.warnings:
                lines.append(f"    WARN: {w}")
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Per-sheet item collectors (return items; do NOT write to DB)
# ---------------------------------------------------------------------------


def _collect_quote_rows(
    document: Document,
    text: str,
    *,
    extractor_version: str,
) -> tuple[list[FinancialLineItem], DocLedgerResult]:
    """Parse a quote grid and return (items, result). No DB writes."""
    result = DocLedgerResult(
        doc_id=str(document.canonical_id),
        doc_name=document.name or "",
        sheet_type="quote",
        ingestion_status="skipped",
        ingestion_reason="no_header",
    )

    grid = parse_financial_grid(text)
    result.warnings.extend(grid.warnings)

    if not grid.header_found:
        return [], result

    unit = _extract_unit(document.name)
    status = _extract_status(document.name)
    currency = _extract_currency(text)
    doc_date = document.modified_at_source.date() if document.modified_at_source else None

    items = [
        FinancialLineItem(
            project_id=document.project_id,
            document_id=document.canonical_id,
            unit=unit,
            division_code=row.division_code,
            division_name=row.division_name,
            side="revenue",
            amount_type=row.amount_type,
            status=status,
            doc_role="quote",
            description=row.description,
            amount=row.amount,
            currency=currency,
            doc_date=doc_date,
            source="grid",
            quoted_excerpt=f"{row.description}: {row.amount}",
            amount_verified=True,
            confidence=1.0,
            extractor_version=extractor_version,
            classification_method="deterministic",
            classification_confidence=1.0,
            source_doc_type="quote",
            source_region=None,
            source_meta_json=json.dumps(
                {"kind": row.kind, "masterformat_hint": row.masterformat_hint}
            ),
        )
        for row in grid.rows
    ]

    result.rows_written = len(items)
    result.grand_total = grid.grand_total
    result.division_total = grid.division_total
    if grid.grand_total is not None:
        result.reconcile_ok = grid.division_total == grid.grand_total

    if items:
        result.ingestion_status = "parsed"
        result.ingestion_reason = None
    else:
        result.ingestion_status = "skipped"
        result.ingestion_reason = "no_money"

    return items, result


def _collect_extras_rows(
    document: Document,
    text: str,
    *,
    extractor_version: str,
) -> tuple[list[FinancialLineItem], DocLedgerResult]:
    """Parse an EXTRAS/change-order sheet and return (items, result). No DB writes.

    All extras rows are side=revenue (client-facing change orders).
    Rejected/cancelled rows are excluded by the parser.
    Proposed rows are written with status=proposed so they can be filtered
    at report time.
    """
    from project_db.ai.extras_grid import parse_extras_sheet

    result = DocLedgerResult(
        doc_id=str(document.canonical_id),
        doc_name=document.name or "",
        sheet_type="extras",
        ingestion_status="skipped",
        ingestion_reason="no_header",
    )

    extras = parse_extras_sheet(text)
    result.warnings.extend(extras.warnings)

    if not extras.header_found:
        return [], result

    if not extras.rows:
        result.ingestion_status = "skipped"
        result.ingestion_reason = "no_money"
        return [], result

    unit = _extract_unit(document.name)
    currency = _extract_currency(text)
    doc_date = document.modified_at_source.date() if document.modified_at_source else None

    items = [
        FinancialLineItem(
            project_id=document.project_id,
            document_id=document.canonical_id,
            unit=unit,
            division_code=row.division_code,
            division_name=row.division_name,
            side="revenue",
            amount_type="adjustment",
            status=row.status,
            doc_role="change_order",
            description=f"CO#{row.co_number}: {row.description}"
            if row.co_number
            else row.description,
            amount=row.total,
            currency=currency,
            doc_date=doc_date,
            source="grid/extras",
            quoted_excerpt=f"{row.description}: {row.total}",
            amount_verified=True,
            confidence=1.0,
            extractor_version=extractor_version,
            classification_method="deterministic",
            classification_confidence=1.0,
            source_doc_type="extras",
            source_region=None,
            source_meta_json=json.dumps(
                {
                    "co_number": row.co_number,
                    "extras_status": row.status,
                    "skipped_rows": extras.skipped_rows,
                }
            ),
        )
        for row in extras.rows
    ]

    result.rows_written = len(items)
    result.ingestion_status = "parsed"
    result.ingestion_reason = None
    result.grand_total = extras.accepted_total if extras.accepted_total else None
    result.division_total = sum((r.total for r in extras.rows), Decimal(0)) or None

    return items, result


# ---------------------------------------------------------------------------
# Main entry points
# ---------------------------------------------------------------------------


def populate_ledger_for_document(
    session,
    document: Document,
    doc_text: DocumentText,
    *,
    extractor_version: str = EXTRACTOR_VERSION_QUOTE,
) -> DocLedgerResult:
    """Parse one document and upsert its FinancialLineItem rows.

    Multi-sheet routing:
      For xlsx workbooks (extracted text contains '### SheetName' headers),
      each worksheet is classified independently.  Only the FIRST sheet of
      each parseable type (quote / extras) is processed — subsequent duplicate-
      type sheets are skipped to prevent double-counting within the document
      (e.g. 'ESTIMATE' + 'Copy of ESTIMATE' in the same workbook).

    Sheet type routing:
      quote            → deterministic grid parser (Phase 1b, stable)
      extras           → deterministic extras parser (Phase 1c-MVP)
      job_cost         → skipped (ingestion_status=skipped, reason=unsupported_type)
      order_quantities → skipped
      unknown          → skipped

    Idempotent: deletes existing rows for this document before writing new ones.
    One atomic delete+insert per document (all parseable sheets batched together).
    Never raises — unexpected exceptions are captured as ingestion_status=failed.
    """
    text = doc_text.extracted_text or ""

    # Split multi-sheet xlsx workbooks on '### SheetName' markers.
    # Single-sheet or non-xlsx documents return [(None, text)].
    raw_sheets = split_workbook_sheets(text)

    if len(raw_sheets) == 1 and raw_sheets[0][0] is None:
        # Non-xlsx document or true single sheet: classify by document name.
        classify_pairs: list[tuple[str | None, str]] = [(document.name, raw_sheets[0][1])]
    else:
        # Multi-sheet xlsx: classify each sheet by its own sheet name.
        classify_pairs = list(raw_sheets)

    # Classify each sheet; collect first-of-type for parseable types.
    seen_types: set[str] = set()
    canonical_sheets: list[tuple[str | None, str, str]] = []  # (name, type, text)
    all_sheet_types: list[str] = []

    for classify_name, sheet_text in classify_pairs:
        sheet_type = classify_financial_sheet(classify_name, sheet_text)
        all_sheet_types.append(sheet_type)
        if sheet_type in ("quote", "extras") and sheet_type not in seen_types:
            seen_types.add(sheet_type)
            canonical_sheets.append((classify_name, sheet_type, sheet_text))

    # Determine the primary reported sheet type for the DocLedgerResult.
    # If we found parseable sheets, use the first one; otherwise use the most
    # common non-unknown type in the workbook (for informative skipped reasons).
    if canonical_sheets:
        primary_type = canonical_sheets[0][1]
    else:
        counts: dict[str, int] = {}
        for t in all_sheet_types:
            counts[t] = counts.get(t, 0) + 1
        order = ["job_cost", "order_quantities", "extras", "quote", "unknown"]
        primary_type = next((t for t in order if t in counts), "unknown")

    result = DocLedgerResult(
        doc_id=str(document.canonical_id),
        doc_name=document.name or "",
        sheet_type=primary_type,
        ingestion_status="skipped",
        ingestion_reason="unsupported_type",
    )

    if not canonical_sheets:
        return result

    try:
        all_new_items: list[FinancialLineItem] = []

        for _sheet_name, sheet_type, sheet_text in canonical_sheets:
            if sheet_type == "quote":
                items, sheet_res = _collect_quote_rows(
                    document, sheet_text, extractor_version=extractor_version
                )
            elif sheet_type == "extras":
                items, sheet_res = _collect_extras_rows(
                    document, sheet_text, extractor_version=EXTRACTOR_VERSION_EXTRAS
                )
                # Fallback: if extras header not found, try the quote parser.
                # Handles documents named "EXTRAS+ROOF" / "EXTRAS ACCEPTED" that
                # are actually formatted as standard quote grids (no CO#/Status
                # columns). Only falls back when no quote sheet was already parsed
                # from this workbook.
                if (
                    sheet_res.ingestion_status == "skipped"
                    and sheet_res.ingestion_reason == "no_header"
                    and "quote" not in seen_types
                ):
                    items, sheet_res = _collect_quote_rows(
                        document, sheet_text, extractor_version=extractor_version
                    )
                    if not sheet_res.skipped:
                        result.sheet_type = "quote"
            else:
                continue

            result.warnings.extend(sheet_res.warnings)

            if not sheet_res.skipped:
                all_new_items.extend(items)
                result.rows_written += sheet_res.rows_written
                if result.ingestion_status != "parsed":
                    # Carry reconciliation info from the first successfully parsed sheet.
                    result.ingestion_status = "parsed"
                    result.ingestion_reason = None
                    result.grand_total = sheet_res.grand_total
                    result.division_total = sheet_res.division_total
                    result.reconcile_ok = sheet_res.reconcile_ok
            else:
                # Propagate skip reason only if nothing has succeeded yet.
                if result.ingestion_status != "parsed":
                    result.ingestion_status = sheet_res.ingestion_status
                    result.ingestion_reason = sheet_res.ingestion_reason

        # One atomic swap for all sheets of this document.
        session.query(FinancialLineItem).filter(
            FinancialLineItem.document_id == document.canonical_id
        ).delete(synchronize_session="fetch")
        if all_new_items:
            session.add_all(all_new_items)

    except Exception as exc:
        result.ingestion_status = "failed"
        result.ingestion_reason = "parse_error"
        result.warnings.append(f"Unexpected error: {exc}")

    return result


def populate_ledger_for_project(
    session,
    project_id,
) -> ProjectLedgerResult:
    """Populate FinancialLineItem rows for all financial docs in a project.

    Processes quote + extras sheets; skips job_cost / order_quantities / unknown
    (Phase 1c-MVP). Idempotent per document. Commits the session on success.
    """
    batch = ProjectLedgerResult(project_id=str(project_id))

    docs = (
        session.query(Document, DocumentText)
        .join(DocumentText, DocumentText.document_id == Document.canonical_id)
        .filter(
            Document.project_id == project_id,
            Document.is_trashed.is_(False),
            DocumentText.extracted_text.isnot(None),
        )
        .all()
    )

    for document, doc_text in docs:
        doc_result = populate_ledger_for_document(session, document, doc_text)
        batch.docs.append(doc_result)

    session.commit()
    return batch
