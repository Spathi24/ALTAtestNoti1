"""Phase 1b/1c-MVP of docs/FINANCIAL_REDESIGN: persister that maps grid-parsed
rows into FinancialLineItem records.

NO LLM. Reads the stored DocumentText for a project's financial sheets,
classifies each (quote → grid parser; extras → extras parser; everything else
→ skipped or quarantined), and writes FinancialLineItem rows.

Idempotent per document: existing rows for a document are deleted and replaced
on every call. Returns a ProjectLedgerResult with per-document outcomes.

Phase 1c-MVP adds:
  - ingestion_status / ingestion_reason on DocLedgerResult
  - classification_method + source_doc_type on every written row
  - extras sheet routing → parse_extras_sheet + write side=revenue rows
  - job_cost / order_quantities / unknown → skipped (ingestion_status="skipped")
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from decimal import Decimal

from project_db.ai.financial_grid import classify_financial_sheet, parse_financial_grid
from project_db.db.models.docs import Document, DocumentText
from project_db.db.models.finance import FinancialLineItem

EXTRACTOR_VERSION_QUOTE = "grid-v1"
EXTRACTOR_VERSION_EXTRAS = "extras-v1"

# Ingestion status vocab (per-document outcome; not persisted on individual rows).
INGESTION_STATUSES = {"parsed", "skipped", "quarantined", "failed"}
INGESTION_REASONS = {
    "no_header",           # expected header row not found
    "unsupported_type",    # sheet type not yet supported (job_cost, order_quantities, unknown)
    "low_confidence",      # classifier confidence below threshold
    "validation_failed",   # schema validation failed
    "no_money",            # header found but no parseable amounts
    "ambiguous_amount_meaning",  # amounts present but meaning unclear (budget vs actual)
    "parse_error",         # unexpected exception during parsing
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
    ingestion_status: str = "parsed"   # parsed | skipped | quarantined | failed
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
            f"Ledger populated: {self.total_rows} rows "
            f"from {len(parsed)} sheet(s)",
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
# Quote-sheet persister (stable, Phase 1b)
# ---------------------------------------------------------------------------


def _write_quote_rows(
    session,
    document: Document,
    text: str,
    *,
    extractor_version: str,
    result: DocLedgerResult,
) -> None:
    """Parse a quote grid and write FinancialLineItem rows. Mutates ``result``."""
    from project_db.ai.financial_grid import parse_financial_grid

    grid = parse_financial_grid(text)
    result.warnings.extend(grid.warnings)

    if not grid.header_found:
        result.ingestion_status = "skipped"
        result.ingestion_reason = "no_header"
        return

    unit = _extract_unit(document.name)
    status = _extract_status(document.name)
    currency = _extract_currency(text)
    doc_date = (
        document.modified_at_source.date() if document.modified_at_source else None
    )

    new_items = [
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
            # Phase 1c-MVP classification provenance
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

    # Atomic swap: parse first, then delete, then insert.
    session.query(FinancialLineItem).filter(
        FinancialLineItem.document_id == document.canonical_id
    ).delete(synchronize_session="fetch")
    session.add_all(new_items)

    result.rows_written = len(new_items)
    result.grand_total = grid.grand_total
    result.division_total = grid.division_total
    if grid.grand_total is not None:
        result.reconcile_ok = grid.division_total == grid.grand_total

    if result.rows_written == 0:
        result.ingestion_status = "skipped"
        result.ingestion_reason = "no_money"
    else:
        result.ingestion_status = "parsed"


# ---------------------------------------------------------------------------
# Extras-sheet persister (Phase 1c-MVP)
# ---------------------------------------------------------------------------


def _write_extras_rows(
    session,
    document: Document,
    text: str,
    *,
    extractor_version: str,
    result: DocLedgerResult,
) -> None:
    """Parse an EXTRAS/change-order sheet and write FinancialLineItem rows.

    All extras rows are side=revenue (client-facing change orders).
    Rejected/cancelled rows are excluded by the parser.
    Proposed rows are written with status=proposed so they can be filtered
    at report time.
    """
    from project_db.ai.extras_grid import parse_extras_sheet

    extras = parse_extras_sheet(text)
    result.warnings.extend(extras.warnings)

    if not extras.header_found:
        result.ingestion_status = "skipped"
        result.ingestion_reason = "no_header"
        return

    if not extras.rows:
        result.ingestion_status = "skipped"
        result.ingestion_reason = "no_money"
        return

    unit = _extract_unit(document.name)
    currency = _extract_currency(text)
    doc_date = (
        document.modified_at_source.date() if document.modified_at_source else None
    )

    new_items = [
        FinancialLineItem(
            project_id=document.project_id,
            document_id=document.canonical_id,
            unit=unit,
            division_code=row.division_code,
            division_name=row.division_name,
            side="revenue",
            amount_type="adjustment",
            status=row.status,  # accepted | proposed | unknown
            doc_role="change_order",
            description=f"CO#{row.co_number}: {row.description}" if row.co_number else row.description,
            amount=row.total,
            currency=currency,
            doc_date=doc_date,
            source="grid/extras",
            quoted_excerpt=f"{row.description}: {row.total}",
            amount_verified=True,
            confidence=1.0,
            extractor_version=extractor_version,
            # Phase 1c-MVP classification provenance
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

    session.query(FinancialLineItem).filter(
        FinancialLineItem.document_id == document.canonical_id
    ).delete(synchronize_session="fetch")
    session.add_all(new_items)

    result.rows_written = len(new_items)
    result.ingestion_status = "parsed"
    # For extras, grand_total = accepted_total (the client-confirmed scope delta)
    result.grand_total = extras.accepted_total if extras.accepted_total else None
    result.division_total = sum((r.total for r in extras.rows), Decimal(0)) or None
    # No pre-tax / after-tax reconciliation line in extras sheets → reconcile_ok stays None


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

    Routes by sheet type (classify_financial_sheet):
      quote            → deterministic grid parser (Phase 1b, stable)
      extras           → deterministic extras parser (Phase 1c-MVP)
      job_cost         → skipped (ingestion_status=skipped, reason=unsupported_type)
      order_quantities → skipped
      unknown          → skipped

    Idempotent: deletes existing rows for this document before writing new ones.
    Never raises — unexpected exceptions are captured and returned as
    ingestion_status=failed.
    """
    text = doc_text.extracted_text or ""
    sheet_type = classify_financial_sheet(document.name, text)

    result = DocLedgerResult(
        doc_id=str(document.canonical_id),
        doc_name=document.name or "",
        sheet_type=sheet_type,
        ingestion_status="skipped",
        ingestion_reason="unsupported_type",
    )

    try:
        if sheet_type == "quote":
            _write_quote_rows(
                session,
                document,
                text,
                extractor_version=extractor_version,
                result=result,
            )
        elif sheet_type == "extras":
            _write_extras_rows(
                session,
                document,
                text,
                extractor_version=EXTRACTOR_VERSION_EXTRAS,
                result=result,
            )
        # job_cost, order_quantities, unknown → remain skipped/unsupported_type
    except Exception as exc:  # noqa: BLE001
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
