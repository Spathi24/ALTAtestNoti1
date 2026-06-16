"""Structured financial extraction -- the intelligent, low-heuristic pipeline.

Why this exists (2026-06-04): the original extractor (``ai/financials.py``)
accumulated a pile of brittle regexes -- a keyword gate to pick documents, name
rules to spot roll-ups, content rules to spot projection/market-report sheets.
Every weird file added another regex.  Per current best practice (schema-based
structured outputs + LLM for *semantic understanding*, deterministic code for
*validation and arithmetic*), this module flips the design:

  - The LLM CLASSIFIES each document (quote / invoice / supplier bill / budget /
    acquisition model / market report / ...) and decides ``is_transactional`` --
    a reading-comprehension job it is good at -- and returns records via a
    STRICT JSON SCHEMA (OpenAI structured outputs: no malformed JSON, no
    hallucinated fields).
  - Deterministic code keeps doing what it must: verify each amount's value
    against the source text (the hard-won locale parser), decide primary vs
    cross-check from the LLM's ``is_transactional``, and SUM (never the LLM).

So there is no keyword gate, no model/projection/market-report regex -- the LLM
subsumes them.  The arithmetic stays deterministic (invariant N2).  This path
uses OpenAI (structured outputs are an OpenAI strength); the deterministic
report (``ai/views.report_project_financials``) is unchanged.
"""

from __future__ import annotations

import json
import os
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy.orm import Session

from project_db.ai.financials import (
    _amount_in_text,
    _as_uuid,
    _clamp_confidence,
    _clean_str,
    _company_name,
    _norm,
    _parse_amount,
)
from project_db.db.models import Document, FinancialRecord, Project
from project_db.db.models.docs import DocumentText

STRUCTURED_PROMPT_VERSION = "structured-v1"

# Document types the model classifies into.  Drives storage: the analysis types
# are NOT project transactions and are dropped; budgets are kept as a roll-up
# cross-check; the rest are primary transactions.
_DOC_TYPES = [
    "construction_quote",
    "construction_estimate",
    "client_invoice",
    "supplier_invoice",
    "receipt",
    "change_order",
    "purchase_order",
    "lease",
    "settlement",
    "budget_or_cost_tracker",
    "acquisition_or_proforma_model",
    "market_report_or_valuation",
    "other",
]
# Types whose figures are NOT this project's money -- skip entirely.
_SKIP_TYPES = {"acquisition_or_proforma_model", "market_report_or_valuation"}
# Direction logically ENTAILED by the document type (deterministic, not a
# guess): a quote/estimate/client-invoice we issue is revenue; a supplier
# invoice / PO is cost.  Used ONLY to resolve a record the LLM left 'unknown'
# (a typed estimate with no client named) -- never to override a confident
# client_in / contractor_out.  Ambiguous types (receipt / change_order / lease /
# settlement / budget) are left unknown.
_DIRECTION_BY_TYPE = {
    "construction_quote": "client_in",
    "construction_estimate": "client_in",
    "client_invoice": "client_in",
    "supplier_invoice": "contractor_out",
    "purchase_order": "contractor_out",
}
# Map document_type -> the doc_role the confirmed-vs-quoted default uses.
_DOC_ROLE_BY_TYPE = {
    "construction_quote": "quote",
    "construction_estimate": "estimate",
    "client_invoice": "invoice",
    "supplier_invoice": "invoice",
    "receipt": "receipt",
    "change_order": "change_order",
    "purchase_order": "quote",
    "lease": "other",
    "settlement": "other",
    "budget_or_cost_tracker": "other",
}

# Strict JSON schema -- structured outputs guarantee the model returns exactly
# this shape (no malformed JSON, no extra fields).  Nullable fields use a
# ["type","null"] union as strict mode requires every property in `required`.
EXTRACTION_SCHEMA: dict[str, Any] = {
    "name": "financial_document_extraction",
    "strict": True,
    "schema": {
        "type": "object",
        "additionalProperties": False,
        "required": ["document_type", "is_transactional", "summary", "records"],
        "properties": {
            "document_type": {"type": "string", "enum": _DOC_TYPES},
            "is_transactional": {
                "type": "boolean",
                "description": (
                    "true ONLY if this document records actual money quoted, "
                    "invoiced, paid, or owed on THIS construction project (a real "
                    "quote / estimate / invoice / receipt / change order / "
                    "settlement). false for internal budgets, cost trackers, "
                    "financial projections, acquisition / pro-forma models, "
                    "market reports, property valuations, feasibility studies."
                ),
            },
            "summary": {"type": "string"},
            "records": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": [
                        "amount",
                        "currency",
                        "direction",
                        "record_kind",
                        "description",
                        "quoted_excerpt",
                        "confidence",
                    ],
                    "properties": {
                        "amount": {"type": "number"},
                        "currency": {"type": ["string", "null"]},
                        "direction": {
                            "type": "string",
                            "enum": ["client_in", "contractor_out", "unknown"],
                        },
                        "record_kind": {
                            "type": "string",
                            "enum": ["total", "line_item", "tax", "deposit", "other"],
                        },
                        "description": {"type": "string"},
                        "quoted_excerpt": {"type": "string"},
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
        "financial document and return structured data about it.\n\n"
        f'OUR COMPANY is "{company_name}".\n\n'
        "FIRST classify the document (document_type) and decide is_transactional:\n"
        "- is_transactional = true only for a real quote/estimate/invoice/"
        "receipt/change-order/settlement that records money on THIS project.\n"
        "- is_transactional = false for internal budgets, cost trackers, "
        "financial projections, acquisition / pro-forma models, market reports, "
        "property valuations, feasibility studies -- these are analysis, not "
        "project transactions. Return is_transactional=false and NO records for "
        "them (do not extract their projected figures).\n\n"
        "THEN, for a transactional document, extract each monetary amount.\n"
        "DIRECTION is decided by WHO ISSUED the document:\n"
        f"- If {company_name} issued it (our letterhead) TO a client -> client_in "
        "(our revenue). An estimate/quote WE prepared for a client is client_in "
        "even though it lists our costs. Use document_type construction_quote / "
        "construction_estimate / client_invoice.\n"
        f"- If someone ELSE issued it and is billing {company_name} -- a "
        "subcontractor or supplier (an electrical / plumbing / material / "
        "'Inc.' / 'Electrique' company whose name is NOT "
        f"{company_name}) -> contractor_out (our cost), document_type "
        "supplier_invoice -- EVEN IF the document says 'Invoice'. The issuer/"
        "vendor/'from' name being a third party is the tell.\n"
        "- unknown only if the issuer is genuinely unclear.\n"
        "- record_kind: total / line_item / tax / deposit / other.\n"
        "- amount: the number only (no symbol or thousands separators).\n"
        "- quoted_excerpt: the verbatim text (<=30 words) that contains the "
        "amount. If you cannot quote it, do not emit the record.\n"
        "- NEVER invent an amount. NEVER do arithmetic (no summing, no margins). "
        "Report only amounts the document states.\n\n"
        "SPREADSHEETS: numbers under a header are a table -- use the header to "
        "tell money columns (price/cost/total/amount/$) from NON-money "
        "(quantities, counts, square footage, dimensions, hours, %, dates, IDs). "
        "Do NOT extract non-money cells as amounts. If a sheet shows several "
        "alternative scenarios/projections, they are not additive -- do not emit "
        "them all.\n\n"
        "Prefer the grand total, subtotals, deposits, and tax over enumerating "
        "every minor line; at most ~25 records."
    )


# ---------------------------------------------------------------------------
# Spreadsheet -> markdown (research: markdown tables beat TSV/CSV for LLMs)
# ---------------------------------------------------------------------------


def tsv_to_markdown(text: str) -> str:
    """Render our '### Sheet' + tab-separated extraction as markdown tables.

    Markdown tables are both more accurate and more token-efficient for LLMs
    than raw TSV/CSV.  Rows are padded/truncated to the header width so the
    table is well-formed; non-table lines pass through.
    """
    out: list[str] = []
    rows: list[list[str]] = []

    def _flush() -> None:
        if not rows:
            return
        width = max(len(r) for r in rows)
        header = rows[0] + [""] * (width - len(rows[0]))
        out.append("| " + " | ".join(c.replace("|", "/") for c in header) + " |")
        out.append("| " + " | ".join("---" for _ in range(width)) + " |")
        for r in rows[1:]:
            cells = (r + [""] * width)[:width]
            out.append("| " + " | ".join(c.replace("|", "/") for c in cells) + " |")
        rows.clear()

    for line in (text or "").split("\n"):
        if line.startswith("### "):
            _flush()
            out.append(f"\n**Sheet: {line[4:].strip()}**")
        elif "\t" in line:
            rows.append(line.split("\t"))
        else:
            _flush()
            if line.strip():
                out.append(line)
    _flush()
    return "\n".join(out)


# ---------------------------------------------------------------------------
# Extractor providers
# ---------------------------------------------------------------------------


class StructuredExtractorError(RuntimeError):
    pass


class StructuredExtractor(ABC):
    name = "abstract"

    @abstractmethod
    def extract(self, *, doc_name: str, doc_text: str, company_name: str) -> dict[str, Any]:
        """Return a dict conforming to EXTRACTION_SCHEMA's schema."""
        raise NotImplementedError


class OpenAIStructuredExtractor(StructuredExtractor):
    """Real extractor via OpenAI structured outputs (guaranteed-schema JSON)."""

    name = "openai-structured"

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
            raise StructuredExtractorError(
                "OPENAI_API_KEY is not set (needed for structured extraction)."
            )
        try:
            from openai import OpenAI
        except ImportError as exc:  # pragma: no cover
            raise StructuredExtractorError("openai package not installed") from exc
        self._client = OpenAI(api_key=key, base_url=base_url, timeout=timeout_seconds)

    def extract(self, *, doc_name: str, doc_text: str, company_name: str) -> dict[str, Any]:
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
                response_format={"type": "json_schema", "json_schema": EXTRACTION_SCHEMA},
            )
        except Exception as exc:
            raise StructuredExtractorError(f"OpenAI extraction call failed: {exc}") from exc
        msg = resp.choices[0].message
        if getattr(msg, "refusal", None):
            raise StructuredExtractorError(f"model refused: {msg.refusal}")
        try:
            return json.loads(msg.content)
        except (json.JSONDecodeError, TypeError) as exc:  # strict mode makes this rare
            raise StructuredExtractorError(f"bad JSON despite strict schema: {exc}") from exc


class MockStructuredExtractor(StructuredExtractor):
    """Deterministic extractor for tests: returns canned results keyed by name."""

    name = "mock-structured"

    def __init__(
        self,
        by_name: dict[str, dict[str, Any]] | None = None,
        default: dict[str, Any] | None = None,
    ) -> None:
        self._by_name = by_name or {}
        self._default = default or {
            "document_type": "other",
            "is_transactional": False,
            "summary": "mock",
            "records": [],
        }
        self.calls: list[str] = []

    def extract(self, *, doc_name: str, doc_text: str, company_name: str) -> dict[str, Any]:
        self.calls.append(doc_name)
        return self._by_name.get(doc_name, self._default)


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------


@dataclass
class StructuredBatch:
    project_id: str
    project_name: str
    prompt_version: str = STRUCTURED_PROMPT_VERSION
    records: list[FinancialRecord] = field(default_factory=list)
    documents_considered: int = 0
    documents_skipped_nontransactional: int = 0
    superseded_count: int = 0
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    skipped_reason: str | None = None
    classifications: list[tuple[str, str, bool]] = field(default_factory=list)

    @property
    def created_count(self) -> int:
        return len(self.records)

    def summary(self) -> str:
        if self.skipped_reason:
            return f"[structured] {self.project_name}: skipped -- {self.skipped_reason}"
        return (
            f"[structured] {self.project_name}: {self.created_count} record(s) from "
            f"{self.documents_considered} doc(s) "
            f"({self.documents_skipped_nontransactional} non-transactional skipped, "
            f"superseded {self.superseded_count})"
        )


# Mimes we will hand to the LLM (it does the rest of the judging).  Photos / CAD
# never carry money text.
_READABLE_MIMES = {
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "application/vnd.ms-excel",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/vnd.google-apps.document",
    "application/vnd.google-apps.spreadsheet",
    "text/csv",
    "text/plain",
}


def extract_financials_structured_for_project(
    session: Session,
    extractor: StructuredExtractor,
    project_id: Any,
    *,
    max_documents: int = 200,
) -> StructuredBatch:
    """Classify + extract every readable doc for a project via the LLM.

    No keyword gate, no roll-up/model regexes -- the LLM classifies each doc and
    sets is_transactional; non-transactional analysis docs (budgets, models,
    market reports) are skipped or kept only as roll-up cross-checks.  Amounts
    are still verified against the source text deterministically.  All-or-nothing
    snapshot, like the original extractor.
    """
    project_uuid = _as_uuid(project_id)
    project = (
        session.query(Project).filter_by(canonical_id=project_uuid).one_or_none()
        if project_uuid
        else None
    )
    batch = StructuredBatch(
        project_id=str(project_id),
        project_name=project.name if project is not None else str(project_id),
    )
    if project_uuid is None:
        batch.skipped_reason = "invalid project id"
        return batch
    company_name = _company_name()

    rows = (
        session.query(Document, DocumentText.extracted_text)
        .join(DocumentText, DocumentText.document_id == Document.canonical_id)
        .filter(
            Document.project_id == project_uuid,
            Document.is_trashed.is_(False),
            DocumentText.extracted_text.isnot(None),
        )
        .all()
    )
    candidates = [
        (doc, text)
        for doc, text in rows
        if (text or "").strip() and (doc.mime_type is None or doc.mime_type in _READABLE_MIMES)
    ][:max_documents]
    if not candidates:
        batch.skipped_reason = "no readable documents with extracted text"
        return batch
    batch.documents_considered = len(candidates)

    prior = session.query(FinancialRecord).filter(FinancialRecord.project_id == project_uuid).all()

    new_records: list[FinancialRecord] = []
    any_failed = False
    for doc, text in candidates:
        try:
            result = extractor.extract(
                doc_name=doc.name or "",
                doc_text=text,
                company_name=company_name,
            )
        except StructuredExtractorError as exc:
            batch.errors.append(f"{doc.name}: {exc}")
            any_failed = True
            continue

        dtype = str(result.get("document_type") or "other")
        is_txn = bool(result.get("is_transactional"))
        batch.classifications.append((doc.name or "", dtype, is_txn))

        if dtype in _SKIP_TYPES or (not is_txn and dtype not in ("budget_or_cost_tracker",)):
            # Analysis / projection / market report -> not this project's money.
            batch.documents_skipped_nontransactional += 1
            continue

        is_rollup = not is_txn  # budgets/trackers kept as cross-check only
        doc_role = _DOC_ROLE_BY_TYPE.get(dtype, "other")
        norm_text = _norm(text)
        for item in (result.get("records") or [])[:30]:
            amount = _parse_amount(item.get("amount"))
            if amount is None or amount == 0:
                continue
            direction = str(item.get("direction") or "unknown")
            if direction not in ("client_in", "contractor_out", "unknown"):
                direction = "unknown"
            # Resolve a hedged 'unknown' from the document type the LLM assigned
            # (a construction estimate IS our revenue side) -- deterministic.
            if direction == "unknown":
                direction = _DIRECTION_BY_TYPE.get(dtype, "unknown")
            new_records.append(
                FinancialRecord(
                    project_id=project_uuid,
                    document_id=doc.canonical_id,
                    direction=direction,
                    doc_role=doc_role,
                    record_kind=str(item.get("record_kind") or "other"),
                    description=_clean_str(item.get("description")),
                    amount=amount,
                    currency=_clean_str(item.get("currency")),
                    quoted_excerpt=_clean_str(item.get("quoted_excerpt")),
                    confidence=_clamp_confidence(item.get("confidence")),
                    amount_verified=_amount_in_text(amount, norm_text),
                    is_rollup=is_rollup,
                    prompt_version=STRUCTURED_PROMPT_VERSION,
                    source_meta_json=json.dumps(
                        {"document_type": dtype, "is_transactional": is_txn, "item": item},
                        default=str,
                    ),
                )
            )

    if any_failed:
        batch.records = []
        batch.skipped_reason = (
            "one or more documents failed to extract -- prior records kept, "
            "nothing changed. Re-run."
        )
        return batch

    for old in prior:
        session.delete(old)
    batch.superseded_count = len(prior)
    for rec in new_records:
        session.add(rec)
        batch.records.append(rec)
    session.flush()
    return batch
