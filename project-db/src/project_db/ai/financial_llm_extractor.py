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

from project_db.ai.financial_divisions import (
    DIVISIONS,
    UNCLASSIFIED,
    classify_division,
    division_by_code,
)
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

# Document types the model classifies into. The authoritative router is
# ``ledger_side`` (revenue / cost / skip), not the type -- the type only refines
# the doc_role label. BOTH sides become ledger rows now: revenue from quotes WE
# issued, cost from supplier invoices + actual-spend trackers billed to / paid by
# us. Future-money documents (a subcontractor's quote, a budget) are skipped --
# only money actually invoiced or spent counts as cost.
_LLM_DOC_TYPES = [
    # revenue -- documents WE issue to a client
    "construction_quote",
    "construction_estimate",
    "change_order",
    # cost -- money actually billed to / spent by us
    "supplier_invoice",
    "expense_tracker",  # job-cost / material-spending actual-spend sheet
    # neither (skipped): future money or non-financial
    "subcontractor_quote",  # a sub's price to us, NOT yet paid -> skip
    "budget",  # planned, NOT yet spent -> skip
    "other",
]
_REVENUE_DOC_TYPES = {"construction_quote", "construction_estimate", "change_order"}
_COST_DOC_TYPES = {"supplier_invoice", "expense_tracker"}
_DOC_ROLE_BY_TYPE = {
    "construction_quote": "quote",
    "construction_estimate": "estimate",
    "change_order": "change_order",
    "supplier_invoice": "invoice",
    "expense_tracker": "expense",
}

# Reconcile tolerance: lines must sum to the stated total within the greater of
# $1 or 1% (PDF extraction loses cents; a 1% gap still flags real omissions).
_RECONCILE_ABS = Decimal("1.00")
_RECONCILE_PCT = Decimal("0.01")

# The controlled division vocabulary, exposed to the LLM so it assigns the CSI
# division DIRECTLY using full-document context (the supplier's trade, the scope
# described) instead of us keyword-matching a terse line afterwards -- the latter
# dumped most invoice lines into 99 Unclassified. ``classify_division`` stays as
# a deterministic backstop only when the model returns 99.
_DIVISION_CHOICES: tuple[tuple[str, str], ...] = tuple(
    [(d.code, d.name) for d in DIVISIONS] + [(UNCLASSIFIED.code, UNCLASSIFIED.name)]
)
_DIVISION_CODE_ENUM: list[str] = [c for c, _ in _DIVISION_CHOICES]
_DIVISION_GUIDE: str = "\n".join(f"   {c} = {n}" for c, n in _DIVISION_CHOICES)


FINANCIAL_LINE_SCHEMA: dict[str, Any] = {
    "name": "financial_line_extraction",
    "strict": True,
    "schema": {
        "type": "object",
        "additionalProperties": False,
        "required": [
            "document_type",
            "ledger_side",
            "unit",
            "currency",
            "stated_total",
            "is_summary_rollup",
            "line_items",
        ],
        "properties": {
            "document_type": {"type": "string", "enum": _LLM_DOC_TYPES},
            "is_summary_rollup": {
                "type": "boolean",
                "description": (
                    "true if this document is a SUMMARY / ROLLUP that restates "
                    "money priced in DETAIL elsewhere -- e.g. a one-line "
                    "'Statement of Work' lump total, a recap/cover page, or scope "
                    "quoted 'as per the accepted quote'. false for an itemized "
                    "quote or invoice that prices its own scope. This flags "
                    "probable double-counts for human reconciliation; it does NOT "
                    "change what you extract."
                ),
            },
            "ledger_side": {
                "type": "string",
                "enum": ["revenue", "cost", "skip"],
                "description": (
                    "revenue = a quote/estimate/change-order WE issued to a "
                    "client (our income). cost = an invoice a supplier/"
                    "subcontractor billed TO us, OR a record of money we "
                    "ACTUALLY paid/spent (an actual-spend tracker). skip = "
                    "anything else: a subcontractor's quote/estimate not yet "
                    "paid, a budget/forecast, a schedule, or a non-financial "
                    "document. When unsure, choose skip."
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
                    "The document's stated PRE-TAX total that the line items sum "
                    "to, for cross-check ONLY (never also a line item). For an "
                    "invoice use the pre-tax sub-total (exclude GST/QST/TPS/TVQ/"
                    "freight). For an actual-spend sheet, use its stated total of "
                    "money ACTUALLY spent if one is printed; null if none is."
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
                        "division_code",
                        "masterformat_hint",
                        "amount",
                        "amount_type",
                        "quoted_excerpt",
                        "confidence",
                    ],
                    "properties": {
                        "description": {"type": "string"},
                        "division_code": {
                            "type": "string",
                            "enum": _DIVISION_CODE_ENUM,
                            "description": (
                                "The CSI MasterFormat division THIS line belongs "
                                "to. Decide using the WHOLE document's context -- "
                                "the supplier's trade, the scope described, the "
                                "materials named -- not only this line's words. "
                                "E.g. a line that says only 'materials' or "
                                "'labour' on a plumber's invoice is 22; a tile "
                                "purchase is 09. Use '99' ONLY when the line is "
                                "genuinely unclassifiable.\nThe codes:\n"
                                + _DIVISION_GUIDE
                            ),
                        },
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
        "You are a meticulous construction-company bookkeeper. You read ONE "
        "financial document (already extracted to text) and return its priced "
        "lines, tagging which side of the ledger it belongs to.\n\n"
        f'OUR COMPANY is "{company_name}".\n\n'
        "1. ledger_side -- the single most important decision:\n"
        "   * revenue: a quote / estimate / change-order WE issued to a CLIENT "
        "(money coming IN to us).\n"
        "   * cost: an invoice a supplier or subcontractor billed TO us, OR a "
        "sheet recording money we have ACTUALLY spent/paid (real supplier names, "
        "dates, amounts already incurred).\n"
        "   * skip: ANYTHING else -- a subcontractor's quote/estimate we have not "
        "paid yet, a budget or forecast, a price list, a schedule (WBS) with no "
        "dollars, or a non-financial document. When in doubt, skip.\n"
        "   If skip, return an empty line_items array.\n"
        "2. document_type: pick the closest type.\n"
        "3. unit: if the document is for a specific sub-scope (a civic number "
        "like 923/927, or 'exterior'), put it; else null.\n"
        "4. stated_total: the pre-tax total the line items sum to, for "
        "CROSS-CHECK ONLY. Never also emit it as a line item.\n"
        "5. line_items: one per priced line. Give the description, any "
        "MasterFormat/trade hint the doc names, the amount (number only), and "
        "amount_type (total for a normal line; material/labour only if the doc "
        "splits them; markup/contingency/tax for those).\n"
        "6. division_code (per line): assign each line to ONE CSI division using "
        "the WHOLE document -- the supplier's trade, the scope, the materials. A "
        "plumbing supplier's invoice line is 22 even if it only says 'materials'; "
        "a flooring/tile purchase is 09; a kitchen-cabinet line is 10-12. Use the "
        "controlled codes:\n" + _DIVISION_GUIDE + "\n"
        "Use 99 only when a line is genuinely unclassifiable. This 'split by "
        "trade' is the whole point of the report -- do NOT default to 99.\n"
        "7. is_summary_rollup: set true when the WHOLE document just restates "
        "money detailed elsewhere (a lump 'Statement of Work' total, a recap "
        "page, 'as per accepted quote') so we don't double-count it; false for an "
        "itemized quote/invoice.\n\n"
        "ITEMIZE: when the document breaks its price into trades/sections, return "
        "EACH as its own line with its own division_code. Only return a single "
        "lump line when the document itself gives one price for everything.\n\n"
        "COST RULE (critical): on a cost document, include ONLY money ACTUALLY "
        "spent or invoiced. A single sheet often mixes real spend with planning "
        "numbers -- you must EXCLUDE every budget column, estimate column, and "
        "any figure labelled receivable, target, projection, prediction, "
        "'quoted (N units)', forecast, or a per-unit number extrapolated to many "
        "units. Return only the rows that are real, incurred costs.\n\n"
        "TAX RULE: never emit sales tax (GST/QST/TPS/TVQ/HST), freight/shipping, "
        "or a 'deposit'/'balance due' line as a line_item. Costs and revenue are "
        "tracked PRE-TAX. stated_total is the pre-tax sub-total the line items "
        "sum to.\n\n"
        "RULES: NEVER invent an amount. NEVER do arithmetic (no summing, no "
        "margins) -- our code sums and reconciles. quoted_excerpt must be "
        "verbatim from the document; if you cannot quote it, omit the line. "
        "Prefer the real lines over restating subtotals."
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
            "ledger_side": "skip",
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
    """LLM-extract one financial doc into FinancialLineItem rows. Flushes, not commits.

    Handles BOTH sides of the ledger: revenue (quotes we issued) and cost
    (supplier invoices / actual-spend trackers). The LLM tags ``ledger_side``;
    a ``skip`` doc (future money, budget, schedule, non-financial) writes nothing.
    Idempotent on this document's ``source='llm'`` rows (re-run replaces them);
    never touches ``source='grid'`` rows. The same trust gate applies to both
    sides: rows are written only if they reconcile to a stated pre-tax total,
    else they are quarantined for review.
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
    ledger_side = (raw.get("ledger_side") or "skip").strip().lower()
    if ledger_side not in ("revenue", "cost"):
        result.ingestion_reason = "not_financial"
        return result
    result.sheet_type = doc_type

    raw_lines = raw.get("line_items") or []
    if not raw_lines:
        result.ingestion_reason = "no_money"
        return result

    norm_text = _norm(text)
    unit = (raw.get("unit") or "").strip() or _extract_unit(document.name)
    currency = (raw.get("currency") or "").strip() or _extract_currency(text)
    doc_date = document.modified_at_source.date() if document.modified_at_source else None
    # Advisory flag: a summary/rollup doc likely restates money priced elsewhere.
    # Stored on every row so the cross-document reconciliation pass (and a human)
    # can spot probable double-counts; it does NOT gate writing here.
    is_rollup = bool(raw.get("is_summary_rollup"))
    if ledger_side == "cost":
        # Costs that reach this layer are money already incurred -> status=actual.
        status = "actual"
        doc_role = _DOC_ROLE_BY_TYPE.get(doc_type, "invoice")
    else:
        status = _extract_status(document.name)
        doc_role = _DOC_ROLE_BY_TYPE.get(doc_type, "quote")

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
        # Costs are tracked PRE-TAX (revenue is too). Defensively drop any tax
        # line the model emitted despite the prompt, so recoverable sales tax
        # never inflates a project's actual cost.
        if ledger_side == "cost" and amount_type == "tax":
            continue
        # Division: TRUST THE LLM FIRST. It read the whole document, so it knows
        # the trade for a terse line ('materials' on a plumber's invoice -> 22).
        # Keyword-matching the line text only kicks in when the model abstains
        # (returns 99 / nothing) -- a backstop, not the primary signal. This is
        # the fix for everything landing in 99 Unclassified.
        llm_code = (line.get("division_code") or "").strip()
        div = division_by_code(llm_code) if llm_code else UNCLASSIFIED
        div_source = "llm" if div.code != "99" else None
        if div.code == "99":
            fallback = classify_division(desc, masterformat_hint=hint)
            if fallback.code != "99":
                div = fallback
                div_source = "fallback"
            else:
                div_source = "unclassified"
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
                side=ledger_side,
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
                source_meta_json=json.dumps(
                    {
                        "masterformat_hint": hint,
                        "llm_division_code": llm_code or None,
                        "division_source": div_source,
                        "is_summary_rollup": is_rollup,
                    }
                ),
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
