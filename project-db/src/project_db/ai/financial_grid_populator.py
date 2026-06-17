"""Phase 1b of docs/FINANCIAL_REDESIGN: persister that maps grid-parsed rows
into FinancialLineItem records.

NO LLM. Reads the stored DocumentText for a project's quote sheets, classifies
each, parses the deterministic grid, and writes FinancialLineItem rows.

Idempotent per document: existing rows for a document are deleted and replaced
on every call. Returns a ProjectLedgerResult with per-document outcomes and a
cross-check flag (division_total == stated grand_total).
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field

from project_db.ai.financial_grid import classify_financial_sheet, parse_financial_grid
from project_db.db.models.docs import Document, DocumentText
from project_db.db.models.finance import FinancialLineItem

EXTRACTOR_VERSION = "grid-v1"

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
    # A range like "923-927" means the doc covers the whole project.
    if re.search(r"\b\d{3,4}-\d{3,4}\b", name):
        return None
    # Strip leading underscores and whitespace (Drive sometimes prefixes filenames).
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
    skipped: bool = False  # True when sheet_type != 'quote' or no header found


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
        failed = sum(1 for d in parsed if d.reconcile_ok is False)
        skipped = sum(1 for d in self.docs if d.skipped)
        lines = [
            f"Ledger populated: {self.total_rows} rows from {len(parsed)} quote sheet(s)",
            f"  Reconciled: {reconciled}  Reconcile-fail: {failed}"
            f"  Skipped (non-quote / no header): {skipped}",
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
# Core persister
# ---------------------------------------------------------------------------


def populate_ledger_for_document(
    session,
    document: Document,
    doc_text: DocumentText,
    *,
    extractor_version: str = EXTRACTOR_VERSION,
) -> DocLedgerResult:
    """Parse one document and upsert its FinancialLineItem rows.

    Idempotent: deletes existing rows for this document before writing new ones.
    Only acts on sheets classified as 'quote'; everything else is returned as
    skipped so the caller knows why, but is not an error.
    """
    result = DocLedgerResult(
        doc_id=str(document.canonical_id),
        doc_name=document.name or "",
        sheet_type="",
    )

    text = doc_text.extracted_text

    # 1. Classify — route BEFORE parsing (the critical lesson from Phase 1a).
    sheet_type = classify_financial_sheet(document.name, text)
    result.sheet_type = sheet_type
    if sheet_type != "quote":
        result.skipped = True
        return result

    # 2. Parse
    grid = parse_financial_grid(text)
    result.warnings.extend(grid.warnings)
    if not grid.header_found:
        result.skipped = True
        return result

    # 3. Doc-level context derived from the file name / metadata.
    unit = _extract_unit(document.name)
    status = _extract_status(document.name)
    currency = _extract_currency(text)
    doc_date = (
        document.modified_at_source.date() if document.modified_at_source else None
    )

    # 4. Build new item objects BEFORE touching the DB.
    #    This explicit ordering means: if building fails, no rows are deleted.
    #    Own-authored quote sheets are ALWAYS revenue (our client quote).
    #    Supplier cost data arrives via the LLM populator (Phase 3).
    #
    #    amount_verified=True: the amount VALUE is present in the extracted
    #    source text (consistent with FinancialRecord semantics in HANDOFF §2.4).
    #    It does NOT mean the amount is financially validated in the real world —
    #    that judgement lives in the reconcile_ok cross-check + human review.
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
            source_meta_json=json.dumps(
                {"kind": row.kind, "masterformat_hint": row.masterformat_hint}
            ),
        )
        for row in grid.rows
    ]

    # 5. Atomic swap: delete old rows, add new ones.
    #    Parse succeeded before we reach here, so this is safe.
    session.query(FinancialLineItem).filter(
        FinancialLineItem.document_id == document.canonical_id
    ).delete(synchronize_session="fetch")
    session.add_all(new_items)

    # 6. Cross-check: section subtotals should equal the stated Pre-Tax total.
    result.rows_written = len(new_items)
    result.grand_total = grid.grand_total
    result.division_total = grid.division_total
    if grid.grand_total is not None:
        result.reconcile_ok = grid.division_total == grid.grand_total

    return result


def populate_ledger_for_project(
    session,
    project_id,
) -> ProjectLedgerResult:
    """Populate FinancialLineItem rows for all quote docs in a project.

    Queries all documents with extracted text, classifies each sheet, and runs
    the grid parser on quote sheets. Idempotent per document. Commits at the
    end so the caller gets a clean result even if they have no surrounding
    transaction.
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
