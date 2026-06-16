"""Structured contract-obligation extraction -- the Money-at-Risk layer, rebuilt.

Why this exists (2026-06-09): the original obligation extractor
(``ai/obligations.py``) used the generic ask-and-parse-JSON provider with a
bilingual KEYWORD GATE to pick candidate documents -- the same design that, on
the financial side, silently dropped real documents ("Final SOW.pdf" scored 0
on filename keywords -> 0 records).  This module applies the same
classify-then-extract pattern the financial layer was rebuilt on
(``ai/doc_extraction.py``): the LLM CLASSIFIES each document and extracts
obligations via a STRICT JSON SCHEMA (OpenAI structured outputs -- no malformed
JSON, no hallucinated fields), and deterministic code does the rest (verify each
amount against the source text, enforce the dated-or-dollar rule, reconcile in
``report_commitments``).

Two deliberate departures from ``ai/doc_extraction.py``, both because obligations
are prose commitments, not money figures:
  - Document scope is a MIME-level filter (PDF / DOCX / Google Doc / text) -- the
    prose-carrying formats where dated/dollar clauses live.  This is NOT the
    filename keyword gate that caused the silent-drop bug; a contract is a PDF
    regardless of what it is named, so it is never dropped.  Spreadsheets carry
    money figures (the financial layer's job), not obligation clauses.
  - The classification is informational (recorded, surfaced) rather than a hard
    skip: a document with no binding clause simply yields an empty obligations
    array, which is the correct, conservative answer.

The arithmetic / reconciliation stays deterministic (invariant N2): this module
only EXTRACTS evidence-backed facts.  Like the financial structured path it uses
OpenAI (structured outputs are an OpenAI strength) and an all-or-nothing snapshot
(a failed document keeps the prior rows and writes nothing).
"""

from __future__ import annotations

import json
import os
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy.orm import Session

from project_db.ai.doc_extraction import tsv_to_markdown
from project_db.ai.financials import (
    _amount_in_text,
    _as_uuid,
    _clamp_confidence,
    _clean_str,
    _company_name,
    _norm,
    _parse_amount,
    _parse_date,
)
from project_db.db.models import (
    OBLIGATION_DIRECTIONS,
    OBLIGATION_KINDS,
    ContractObligation,
    Document,
    Project,
)
from project_db.db.models.docs import DocumentText

OBLIGATION_STRUCTURED_PROMPT_VERSION = "obligations-structured-v2"

# Document types the model classifies into.  Informational -- recorded and shown,
# not used to drop documents (an "other" doc just yields no obligations).
_DOC_TYPES = [
    "contract",
    "scope_of_work",
    "settlement",
    "lease",
    "change_order_or_amendment",
    "invoice",
    "other",
]

# Prose-carrying mimes where obligation clauses live.  A MIME filter, not a
# keyword gate -- a contract PDF is never dropped for being mis-named.
_OBLIGATION_MIMES = {
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/vnd.google-apps.document",
    "text/plain",
}

# Strict JSON schema -- structured outputs guarantee exactly this shape.  Strict
# mode requires every property in `required`; nullable fields use a
# ["type","null"] union (an obligation can be a pure deadline with no amount, or
# a triggered payment with no calendar date).
OBLIGATION_EXTRACTION_SCHEMA: dict[str, Any] = {
    "name": "contract_obligation_extraction",
    "strict": True,
    "schema": {
        "type": "object",
        "additionalProperties": False,
        "required": ["document_type", "is_contractual", "summary", "obligations"],
        "properties": {
            "document_type": {"type": "string", "enum": _DOC_TYPES},
            "is_contractual": {
                "type": "boolean",
                "description": (
                    "true if this document states binding commitments that carry "
                    "a DATE and/or a DOLLAR AMOUNT (a contract, scope of work, "
                    "settlement, lease, change order). false for photos, drawings, "
                    "reports, correspondence, or anything with no such clause."
                ),
            },
            "summary": {"type": "string"},
            "obligations": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": [
                        "kind",
                        "direction",
                        "description",
                        "amount",
                        "currency",
                        "due_date",
                        "trigger",
                        "counterparty",
                        "quoted_excerpt",
                        "confidence",
                    ],
                    "properties": {
                        "kind": {"type": "string", "enum": sorted(OBLIGATION_KINDS)},
                        "direction": {
                            "type": "string",
                            "enum": sorted(OBLIGATION_DIRECTIONS),
                        },
                        "description": {"type": ["string", "null"]},
                        "amount": {"type": ["number", "null"]},
                        "currency": {"type": ["string", "null"]},
                        "due_date": {
                            "type": ["string", "null"],
                            "description": "ISO yyyy-mm-dd ONLY if the document "
                            "gives an explicit calendar date; else null.",
                        },
                        "trigger": {
                            "type": ["string", "null"],
                            "description": "The triggering CONDITION in the "
                            "document's own words when there is no fixed date "
                            "(e.g. 'upon key return'); else null.",
                        },
                        "counterparty": {"type": ["string", "null"]},
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
        "You are a construction-contract analyst. You read ONE document and "
        "extract OBLIGATIONS -- binding commitments that carry a DATE and/or a "
        "DOLLAR AMOUNT.\n\n"
        "FIRST classify the document (document_type) and set is_contractual:\n"
        "- is_contractual = true for a contract / scope of work / settlement / "
        "lease / change order that states such commitments.\n"
        "- is_contractual = false for photos, drawings, reports, generic "
        "correspondence -- return is_contractual=false and an EMPTY obligations "
        "array.\n\n"
        "THEN extract each obligation. Kinds:\n"
        "- payment_milestone: a scheduled payment (e.g. '25% on completion').\n"
        "- retainage: a holdback / retainage release.\n"
        "- penalty: a late-completion / liquidated-damages / penalty clause.\n"
        "- deposit: an upfront deposit due.\n"
        "- settlement: a settlement / buyout payment (e.g. a tenant on key return).\n"
        "- insurance_expiry: an insurance certificate / coverage that expires.\n"
        "- permit_deadline: a permit or filing deadline.\n"
        "- other: a dated/dollar obligation that fits none of the above.\n\n"
        f'OUR COMPANY is "{company_name}". Set direction from whom the '
        "obligation runs:\n"
        f"- owed_to_us : the CLIENT owes {company_name} (revenue for us to collect).\n"
        f"- owed_by_us : {company_name} owes someone (a sub, tenant, authority).\n"
        "- unknown    : you cannot tell.\n\n"
        "For each obligation: amount (the number only -- no currency symbol or "
        "thousands separators; null when it is a pure deadline), currency, "
        "due_date (ISO yyyy-mm-dd ONLY for an explicit calendar date, else null), "
        "trigger (the condition in the document's own words when there is no fixed "
        "date, else null), counterparty, quoted_excerpt (the verbatim "
        "sentence/clause, <=40 words, that proves it), confidence (0-1).\n\n"
        "Hard rules:\n"
        "- Extract ONLY obligations the document explicitly states. NEVER invent "
        "an amount, a date, or a clause.\n"
        "- If an obligation has NO amount AND NO date AND NO clear trigger, omit it.\n"
        "- If you cannot quote the clause verbatim, omit the obligation.\n"
        "- Do NOT extract STANDARD or STATUTORY boilerplate -- generic rent-payment "
        "terms ('rent is payable on the first of each term'), the duty to deliver a "
        "copy of the lease, civil-code (C.c.Q.) article restatements, or any clause "
        "that appears unchanged in every standard lease/contract. Extract only "
        "NON-STANDARD, project-specific commitments: a negotiated settlement/buyout "
        "payment, a specific deposit, a penalty, a retainage, a payment milestone, "
        "or a dated permit/insurance deadline.\n"
        "- NEVER do arithmetic. Report only what the document states.\n"
        "- Returning few or none is correct."
    )


class ObligationExtractorError(RuntimeError):
    pass


class ObligationExtractor(ABC):
    name = "abstract"

    @abstractmethod
    def extract(self, *, doc_name: str, doc_text: str, company_name: str) -> dict[str, Any]:
        """Return a dict conforming to OBLIGATION_EXTRACTION_SCHEMA's schema."""
        raise NotImplementedError


class OpenAIObligationExtractor(ObligationExtractor):
    """Real extractor via OpenAI structured outputs (guaranteed-schema JSON)."""

    name = "openai-obligations"

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
            raise ObligationExtractorError(
                "OPENAI_API_KEY is not set (needed for structured extraction)."
            )
        try:
            from openai import OpenAI
        except ImportError as exc:  # pragma: no cover
            raise ObligationExtractorError("openai package not installed") from exc
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
                response_format={
                    "type": "json_schema",
                    "json_schema": OBLIGATION_EXTRACTION_SCHEMA,
                },
            )
        except Exception as exc:
            raise ObligationExtractorError(f"OpenAI extraction call failed: {exc}") from exc
        msg = resp.choices[0].message
        if getattr(msg, "refusal", None):
            raise ObligationExtractorError(f"model refused: {msg.refusal}")
        try:
            return json.loads(msg.content)
        except (json.JSONDecodeError, TypeError) as exc:  # strict mode makes this rare
            raise ObligationExtractorError(f"bad JSON despite strict schema: {exc}") from exc


class MockObligationExtractor(ObligationExtractor):
    """Deterministic extractor for tests: returns canned results keyed by name."""

    name = "mock-obligations"

    def __init__(
        self,
        by_name: dict[str, dict[str, Any]] | None = None,
        default: dict[str, Any] | None = None,
    ) -> None:
        self._by_name = by_name or {}
        self._default = default or {
            "document_type": "other",
            "is_contractual": False,
            "summary": "mock",
            "obligations": [],
        }
        self.calls: list[str] = []

    def extract(self, *, doc_name: str, doc_text: str, company_name: str) -> dict[str, Any]:
        self.calls.append(doc_name)
        return self._by_name.get(doc_name, self._default)


@dataclass
class ObligationStructuredBatch:
    """Outcome of one structured extraction run -- everything the CLI reports."""

    project_id: str
    project_name: str
    prompt_version: str = OBLIGATION_STRUCTURED_PROMPT_VERSION
    obligations: list[ContractObligation] = field(default_factory=list)
    documents_considered: int = 0
    superseded_count: int = 0
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    skipped_reason: str | None = None
    classifications: list[tuple[str, str, bool]] = field(default_factory=list)

    @property
    def created_count(self) -> int:
        return len(self.obligations)

    def summary(self) -> str:
        if self.skipped_reason:
            return f"[obligations/structured] {self.project_name}: skipped -- {self.skipped_reason}"
        return (
            f"[obligations/structured] {self.project_name}: {self.created_count} "
            f"obligation(s) from {self.documents_considered} document(s) "
            f"(superseded {self.superseded_count})"
        )


def _coerce_vocab(value: Any, vocab: set[str], default: str) -> str:
    """Defensive vocab coercion. The schema enum already constrains the real
    path; this protects against a mock / non-strict backend returning junk."""
    s = str(value or "").strip().lower()
    return s if s in vocab else default


def extract_obligations_structured_for_project(
    session: Session,
    extractor: ObligationExtractor,
    project_id: Any,
    *,
    max_documents: int = 200,
) -> ObligationStructuredBatch:
    """Classify + extract obligations from every prose document of a project.

    No keyword gate -- a MIME filter selects prose-carrying documents and the LLM
    classifies each; a non-contractual doc simply yields no obligations.  Amounts
    are verified against the source text deterministically, and the dated-or-
    dollar rule is enforced server-side.  All-or-nothing snapshot: a failed
    document keeps the prior obligations and writes nothing.  Flushes; the caller
    owns the commit.
    """
    project_uuid = _as_uuid(project_id)
    project = (
        session.query(Project).filter_by(canonical_id=project_uuid).one_or_none()
        if project_uuid
        else None
    )
    batch = ObligationStructuredBatch(
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
        if (text or "").strip() and (doc.mime_type is None or doc.mime_type in _OBLIGATION_MIMES)
    ][:max_documents]
    if not candidates:
        batch.skipped_reason = (
            "no contract-looking documents with extracted text (run extract-content first)"
        )
        return batch
    batch.documents_considered = len(candidates)

    prior = (
        session.query(ContractObligation)
        .filter(ContractObligation.project_id == project_uuid)
        .all()
    )

    new_obligations: list[ContractObligation] = []
    any_failed = False
    for doc, text in candidates:
        try:
            result = extractor.extract(
                doc_name=doc.name or "",
                doc_text=text,
                company_name=company_name,
            )
        except ObligationExtractorError as exc:
            batch.errors.append(f"{doc.name}: {exc}")
            any_failed = True
            continue

        dtype = str(result.get("document_type") or "other")
        is_contractual = bool(result.get("is_contractual"))
        batch.classifications.append((doc.name or "", dtype, is_contractual))

        norm_text = _norm(text)
        for item in result.get("obligations") or []:
            if not isinstance(item, dict):
                batch.errors.append(f"{doc.name}: obligation is not an object")
                continue
            amount = _parse_amount(item.get("amount"))
            if amount is not None and amount == 0:
                amount = None  # $0 is template noise, not a dollar obligation
            due = _parse_date(item.get("due_date"))
            trigger = _clean_str(item.get("trigger"))
            # Server-side enforcement of the dated-or-dollar rule.
            if amount is None and due is None and not trigger:
                batch.warnings.append(
                    f"{doc.name}: obligation with no amount, date, or trigger -- skipped"
                )
                continue
            kind = _coerce_vocab(item.get("kind"), OBLIGATION_KINDS, "other")
            direction = _coerce_vocab(item.get("direction"), OBLIGATION_DIRECTIONS, "unknown")
            new_obligations.append(
                ContractObligation(
                    project_id=project_uuid,
                    document_id=doc.canonical_id,
                    kind=kind,
                    direction=direction,
                    description=_clean_str(item.get("description")),
                    amount=amount,
                    currency=_clean_str(item.get("currency")),
                    due_date=due,
                    trigger=trigger,
                    counterparty=_clean_str(item.get("counterparty")),
                    quoted_excerpt=_clean_str(item.get("quoted_excerpt")),
                    confidence=_clamp_confidence(item.get("confidence")),
                    amount_verified=(
                        None if amount is None else _amount_in_text(amount, norm_text)
                    ),
                    prompt_version=OBLIGATION_STRUCTURED_PROMPT_VERSION,
                    source_meta_json=json.dumps(
                        {"document_type": dtype, "is_contractual": is_contractual, "item": item},
                        default=str,
                    ),
                )
            )

    if any_failed:
        batch.obligations = []
        batch.skipped_reason = (
            "one or more documents failed to extract -- prior obligations kept, "
            "nothing changed. Re-run."
        )
        return batch

    for old in prior:
        session.delete(old)
    batch.superseded_count = len(prior)
    for ob in new_obligations:
        session.add(ob)
        batch.obligations.append(ob)
    session.flush()
    return batch
