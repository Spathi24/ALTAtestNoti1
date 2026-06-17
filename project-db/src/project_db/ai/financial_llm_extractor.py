"""LLM extraction of division-keyed line items from unstructured quotes.

The deterministic grid parser (``financial_grid.py``) only reads own-authored
quote SPREADSHEETS (Material/Labour/Total grids). Most projects keep their
quotes as PDFs or single-column estimates -- already extracted to text in
``DocumentText`` but not grid-shaped. This module fills that gap so division
margins can go portfolio-wide.

Design (mirrors ``doc_extraction.py``: LLM for reading-comprehension, code for
arithmetic + trust):
  - The LLM reads a quote's extracted text and returns, via a STRICT JSON
    schema, the document_type, whether it's a revenue quote WE issued, an
    optional unit, a stated grand total (for cross-check only), and the
    per-scope line items with any MasterFormat hint.
  - Deterministic code maps each line to a CSI division (``classify_division``),
    verifies each amount's value against the source text (``_amount_in_text``),
    sums the lines, reconciles against the stated total, and writes
    ``FinancialLineItem`` rows with ``source="llm"`` /
    ``classification_method="llm_assisted"``. NEVER the LLM doing arithmetic.

The stated grand total is a cross-check ONLY -- it is never written as a row
(that would double-count the line items). Rows coexist with the grid path's
``source="grid"`` rows; ``report_division_margins`` reads both.
"""

from __future__ import annotations

import json
import os
from abc import ABC, abstractmethod
from decimal import Decimal
from typing import Any

from sqlalchemy.orm import Session

from project_db.ai.financial_divisions import classify_division
from project_db.ai.financial_grid_populator import (
    DocLedgerResult,
    ProjectLedgerResult,
    _extract_currency,
    _extract_status,
    _extract_unit,
)
from project_db.ai.financials import _amount_in_text, _norm, _parse_amount
from project_db.db.models import Document, FinancialLineItem
from project_db.db.models.docs import DocumentText
from project_db.db.models.finance import LINE_ITEM_AMOUNT_TYPES

FINANCIAL_LINE_PROMPT_VERSION = "fin-line-llm-v1"
EXTRACTOR_VERSION_LLM = "llm-v1"

# Document types the model classifies into. Only revenue quotes/estimates/change
# orders WE issued become ledger rows; everything else is skipped here (the old
# FinancialRecord layer still captures supplier invoices etc. on the cost side).
_LLM_DOC_TYPES = [
    "construction_quote",
    "construction_estimate",
    "change_order",
    "supplier_invoice",
    "other",
]
_REVENUE_DOC_TYPES = {"construction_quote", "construction_estimate", "change_order"}
_DOC_ROLE_BY_TYPE = {
    "construction_quote": "quote",
    "construction_estimate": "estimate",
    "change_order": "change_order",
}

# Reconcile tolerance: lines must sum to the stated total within the greater of
# $1 or 1% (PDF extraction loses cents; a 1% gap still flags real omissions).
_RECONCILE_ABS = Decimal("1.00")
_RECONCILE_PCT = Decimal("0.01")


FINANCIAL_LINE_SCHEMA: dict[str, Any] = {
    "name": "financial_line_extraction",
    "strict": True,
    "schema": {
        "type": "object",
        "additionalProperties": False,
        "required": [
            "document_type",
            "is_revenue_quote",
            "unit",
            "currency",
            "stated_total",
            "line_items",
        ],
        "properties": {
            "document_type": {"type": "string", "enum": _LLM_DOC_TYPES},
            "is_revenue_quote": {
                "type": "boolean",
                "description": (
                    "true ONLY if this is a quote/estimate/change-order WE issued "
                    "to a client (our revenue). false for supplier invoices, "
                    "budgets, or anything else."
                ),
            },
            "unit": {
                "type": ["string", "null"],
                "description": (
                    "Sub-scope this doc is for, if any: a civic number like '923' "
                    "or '927', or 'exterior'. null if the doc covers the whole "
                    "project or no unit is identifiable."
                ),
            },
            "currency": {"type": ["string", "null"]},
            "stated_total": {
                "type": ["number", "null"],
                "description": (
                    "The document's stated grand/pre-tax total, for cross-check "
                    "ONLY. Do NOT also list it as a line item."
                ),
            },
            "line_items": {
                "type": "array",
                "description": "One object per priced scope line. Skip the grand total.",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": [
                        "description",
                        "masterformat_hint",
                        "amount",
                        "amount_type",
                        "quoted_excerpt",
                        "confidence",
                    ],
                    "properties": {
                        "description": {"type": "string"},
                        "masterformat_hint": {
                            "type": ["string", "null"],
                            "description": (
                                "Any CSI/MasterFormat code or trade the doc names "
                                "for this line (e.g. 'Division 22', 'Plumbing', "
                                "'09 - Finishes'); null if none."
                            ),
                        },
                        "amount": {
                            "type": "number",
                            "description": "The line's amount, number only (no symbol/separators).",
                        },
                        "amount_type": {
                            "type": "string",
                            "enum": [
                                "total",
                                "material",
                                "labour",
                                "markup",
                                "contingency",
                                "tax",
                                "adjustment",
                                "other",
                            ],
                        },
                        "quoted_excerpt": {
                            "type": "string",
                            "description": "Verbatim text (<=30 words) containing the amount.",
                        },
                        "confidence": {"type": "number"},
                    },
                },
            },
        },
    },
}


def _system_prompt(company_name: str) -> str:
    return (
        "You are a meticulous construction-company estimator. You read ONE quote "
        "document (already extracted to text) and return its priced scope lines.\n\n"
        f'OUR COMPANY is "{company_name}".\n\n'
        "1. Classify document_type and set is_revenue_quote = true ONLY for a "
        "quote/estimate/change-order WE issued to a client (our revenue). For a "
        "supplier invoice or anything else, set is_revenue_quote = false and "
        "return an empty line_items array.\n"
        "2. unit: if the document is for a specific sub-scope (a civic number "
        "like 923/927, or 'exterior'), put it; else null.\n"
        "3. stated_total: the document's grand/pre-tax total, for CROSS-CHECK "
        "ONLY. Never also emit it as a line item.\n"
        "4. line_items: one per priced scope line. For each, give the "
        "description, any MasterFormat/trade hint the doc names, the amount "
        "(number only), and amount_type (total for a normal scope line; markup/"
        "contingency/tax for those; material/labour only if the doc splits "
        "them).\n\n"
        "RULES: NEVER invent an amount. NEVER do arithmetic (no summing, no "
        "margins) -- our code sums and reconciles. quoted_excerpt must be "
        "verbatim from the document; if you cannot quote it, omit the line. "
        "Prefer the real scope lines over restating subtotals."
    )


# ---------------------------------------------------------------------------
# Extractor providers
# ---------------------------------------------------------------------------


class FinancialLineExtractorError(RuntimeError):
    pass


class FinancialLineExtractor(ABC):
    name = "abstract"

    @abstractmethod
    def extract(self, *, doc_name: str, doc_text: str, company_name: str) -> dict[str, Any]:
        """Return a dict conforming to FINANCIAL_LINE_SCHEMA's schema."""
        raise NotImplementedError


class OpenAIFinancialLineExtractor(FinancialLineExtractor):
    """Real extractor via OpenAI structured outputs (guaranteed-schema JSON)."""

    name = "openai-financial-line"

    def __init__(
        self,
        *,
        api_key: str | None = None,
        model: str | None = None,
        base_url: str = "https://api.openai.com/v1",
        max_chars: int = 16_000,
        timeout_seconds: float = 90.0,
    ) -> None:
        self.model = model or os.environ.get("OPENAI_EXTRACT_MODEL", "gpt-4o-mini")
        self._max_chars = max_chars
        key = api_key or os.environ.get("OPENAI_API_KEY")
        if not key:
            raise FinancialLineExtractorError(
                "OPENAI_API_KEY is not set (needed for LLM financial extraction)."
            )
        try:
            from openai import OpenAI
        except ImportError as exc:  # pragma: no cover
            raise FinancialLineExtractorError("openai package not installed") from exc
        self._client = OpenAI(api_key=key, base_url=base_url, timeout=timeout_seconds)

    def extract(self, *, doc_name: str, doc_text: str, company_name: str) -> dict[str, Any]:
        from project_db.ai.doc_extraction import tsv_to_markdown

        body = tsv_to_markdown(doc_text)[: self._max_chars]
        user = f"DOCUMENT NAME: {doc_name}\n\nDOCUMENT CONTENT:\n{body}"
        try:
            resp = self._client.chat.completions.create(
                model=self.model,
                temperature=0,
                messages=[
                    {"role": "system", "content": _system_prompt(company_name)},
                    {"role": "user", "content": user},
                ],
                response_format={"type": "json_schema", "json_schema": FINANCIAL_LINE_SCHEMA},
            )
        except Exception as exc:
            raise FinancialLineExtractorError(f"OpenAI extraction call failed: {exc}") from exc
        msg = resp.choices[0].message
        if getattr(msg, "refusal", None):
            raise FinancialLineExtractorError(f"model refused: {msg.refusal}")
        try:
            return json.loads(msg.content)
        except (json.JSONDecodeError, TypeError) as exc:
            raise FinancialLineExtractorError(f"bad JSON despite strict schema: {exc}") from exc


class MockFinancialLineExtractor(FinancialLineExtractor):
    """Deterministic extractor for tests: canned results keyed by doc name."""

    name = "mock-financial-line"

    def __init__(
        self,
        by_name: dict[str, dict[str, Any]] | None = None,
        default: dict[str, Any] | None = None,
    ) -> None:
        self._by_name = by_name or {}
        self._default = default or {
            "document_type": "other",
            "is_revenue_quote": False,
            "unit": None,
            "currency": None,
            "stated_total": None,
            "line_items": [],
        }
        self.calls: list[str] = []

    def extract(self, *, doc_name: str, doc_text: str, company_name: str) -> dict[str, Any]:
        self.calls.append(doc_name)
        return self._by_name.get(doc_name, self._default)


# ---------------------------------------------------------------------------
# Deterministic populator (LLM extracts; code validates + sums + writes)
# ---------------------------------------------------------------------------


def populate_ledger_llm_for_document(
    session: Session,
    document: Document,
    doc_text: DocumentText,
    extractor: FinancialLineExtractor,
    *,
    company_name: str | None = None,
) -> DocLedgerResult:
    """LLM-extract one quote doc into FinancialLineItem rows. Flushes, not commits.

    Idempotent on this document's ``source='llm'`` rows (re-run replaces them);
    never touches ``source='grid'`` rows. A non-revenue doc is skipped.
    """
    from project_db.ai.financials import _company_name

    company = company_name or _company_name()
    result = DocLedgerResult(
        doc_id=str(document.canonical_id),
        doc_name=document.name or "",
        sheet_type="quote",
        ingestion_status="skipped",
        ingestion_reason="unsupported_type",
    )

    text = doc_text.extracted_text or ""
    if not text.strip():
        result.ingestion_reason = "empty_extraction"
        return result

    try:
        raw = extractor.extract(doc_name=document.name or "", doc_text=text, company_name=company)
    except FinancialLineExtractorError as exc:
        result.ingestion_status = "failed"
        result.ingestion_reason = "parse_error"
        result.warnings.append(f"LLM extraction failed: {exc}")
        return result

    doc_type = raw.get("document_type", "other")
    if not raw.get("is_revenue_quote") or doc_type not in _REVENUE_DOC_TYPES:
        result.ingestion_reason = "not_revenue_quote"
        return result

    raw_lines = raw.get("line_items") or []
    if not raw_lines:
        result.ingestion_reason = "no_money"
        return result

    norm_text = _norm(text)
    unit = (raw.get("unit") or "").strip() or _extract_unit(document.name)
    status = _extract_status(document.name)
    currency = (raw.get("currency") or "").strip() or _extract_currency(text)
    doc_role = _DOC_ROLE_BY_TYPE.get(doc_type, "quote")
    doc_date = document.modified_at_source.date() if document.modified_at_source else None

    items: list[FinancialLineItem] = []
    div_total = Decimal(0)
    for line in raw_lines:
        amount = _parse_amount(line.get("amount"))
        if amount is None:
            continue
        desc = (line.get("description") or "").strip()
        hint = (line.get("masterformat_hint") or "").strip() or None
        amount_type = line.get("amount_type") or "total"
        if amount_type not in LINE_ITEM_AMOUNT_TYPES:
            amount_type = "total"
        div = classify_division(desc, masterformat_hint=hint)
        verified = _amount_in_text(amount, norm_text)
        try:
            conf = max(0.0, min(1.0, float(line.get("confidence"))))
        except (TypeError, ValueError):
            conf = 0.5
        div_total += amount
        items.append(
            FinancialLineItem(
                project_id=document.project_id,
                document_id=document.canonical_id,
                unit=unit,
                division_code=div.code,
                division_name=div.name,
                side="revenue",
                amount_type=amount_type,
                status=status,
                doc_role=doc_role,
                description=desc,
                amount=amount,
                currency=currency,
                doc_date=doc_date,
                source="llm",
                quoted_excerpt=(line.get("quoted_excerpt") or "")[:500] or None,
                amount_verified=verified,
                confidence=conf,
                extractor_version=EXTRACTOR_VERSION_LLM,
                classification_method="llm_assisted",
                classification_confidence=conf,
                source_doc_type=doc_type,
                source_meta_json=json.dumps({"masterformat_hint": hint}),
            )
        )

    if not items:
        result.ingestion_reason = "no_money"
        return result

    stated = _parse_amount(raw.get("stated_total"))
    result.grand_total = stated
    result.division_total = div_total
    if stated is not None:
        tol = max(_RECONCILE_ABS, (abs(stated) * _RECONCILE_PCT))
        result.reconcile_ok = abs(div_total - stated) <= tol

    # Always clear this document's prior LLM rows first (idempotent + cleans up
    # a previous bad extraction).
    session.query(FinancialLineItem).filter(
        FinancialLineItem.document_id == document.canonical_id,
        FinancialLineItem.source == "llm",
    ).delete(synchronize_session="fetch")

    # TRUST GATE: commit LLM rows ONLY when they reconcile to the document's own
    # stated total. LLM over/under-extraction on complex quotes is real -- a live
    # smoke run had a quote extract $338,550 of lines against a $149,580 stated
    # total. So an unreconciled (or unverifiable, no-stated-total) extraction is
    # QUARANTINED for human review (surfaced in ledger-health), never written as
    # "truth" into the margins. This is stricter than the deterministic grid path
    # on purpose: the grid's reconcile-fails are small real doc discrepancies; an
    # LLM's are extraction errors that could be 2x off.
    if result.reconcile_ok is True:
        session.add_all(items)
        result.rows_written = len(items)
        result.ingestion_status = "parsed"
        result.ingestion_reason = None
    else:
        result.rows_written = 0
        result.ingestion_status = "quarantined"
        result.ingestion_reason = "reconcile_fail" if stated is not None else "no_stated_total"
        result.warnings.append(
            f"extracted lines sum to {div_total} vs stated {stated}; "
            "quarantined (not written to ledger)"
        )
    return result


def populate_ledger_llm_for_project(
    session: Session,
    extractor: FinancialLineExtractor,
    project_id: Any,
    *,
    company_name: str | None = None,
    limit: int | None = None,
) -> ProjectLedgerResult:
    """LLM-extract revenue quotes for a project that the grid parser couldn't read.

    Processes text-bearing, non-trashed documents that do NOT already have
    deterministic ``source='grid'`` rows (those are handled by ``fill-ledger``).
    ``limit`` caps how many documents are sent to the LLM (cost control).
    Commits on success.
    """
    batch = ProjectLedgerResult(project_id=str(project_id))

    # Documents already covered by the deterministic grid parser -- skip them.
    grid_doc_ids = {
        row[0]
        for row in session.query(FinancialLineItem.document_id)
        .filter(
            FinancialLineItem.project_id == project_id,
            FinancialLineItem.source == "grid",
        )
        .distinct()
        .all()
    }

    pairs = (
        session.query(Document, DocumentText)
        .join(DocumentText, DocumentText.document_id == Document.canonical_id)
        .filter(
            Document.project_id == project_id,
            Document.is_trashed.is_(False),
            DocumentText.extracted_text.isnot(None),
        )
        .all()
    )

    processed = 0
    for document, doc_text in pairs:
        if document.canonical_id in grid_doc_ids:
            continue
        if limit is not None and processed >= limit:
            break
        processed += 1
        doc_result = populate_ledger_llm_for_document(
            session, document, doc_text, extractor, company_name=company_name
        )
        batch.docs.append(doc_result)

    session.commit()
    return batch
