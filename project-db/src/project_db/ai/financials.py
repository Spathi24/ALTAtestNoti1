"""Financial extraction -- read money out of Drive documents.

Per the owner (2026-05-29): Google Drive, not QuickBooks, is the canonical
and most complete financial source.  Quotes and invoices arrive by email and
are filed into Drive, scattered across PDFs / spreadsheets / Word docs.  This
module reads them so a human doesn't have to.

The shape mirrors ``ai/proposals.py`` deliberately -- assemble candidate
documents, build a conservative quoted-excerpt prompt (instruction at the
TAIL, documents referenced by INTEGER INDEX), call ``complete_json``, validate
every returned item, and persist the good ones.  The difference is the
destination: extracted facts land in the ``FinancialRecord`` canonical
sidecar, NOT the ``Proposal`` table.  Extraction enriches our own DB and
writes to no external system, so it needs no human-approval gate -- the
quoted excerpt (verified against the source text) is what makes each record
trustworthy.

Two-sided ledger (the load-bearing concept): every project has money coming
IN (what we invoice the client) and money going OUT (what contractors and
suppliers quote/invoice us).  The upcharge is the spread between the two.
The model classifies each amount's ``direction``; the reconciliation report
(``ai.views.report_project_financials``) sums each side and computes the
margin -- in plain SQL/Python, never in the LLM.

Design rules carried over from the proposal engine:
  - Documents are referenced by INTEGER INDEX, never name/UUID (models
    miscopy long strings).
  - Instruction sits at the TAIL of the user message (front-loaded
    instructions get truncated away on small context windows).
  - Every item is validated before it becomes a row; bad items are recorded
    in ``errors``, never raised -- one malformed row must not sink the batch.
  - The model extracts; it never does arithmetic.  Sums/margins are the
    reconciliation report's job.
"""
from __future__ import annotations

import json
import logging
import os
import re
import uuid
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any

from sqlalchemy.orm import Session

from project_db.ai.providers.base import LLMMessage, LLMProvider, LLMProviderError
from project_db.db.models import (
    FINANCIAL_DIRECTIONS,
    FINANCIAL_DOC_ROLES,
    FINANCIAL_RECORD_KINDS,
    Document,
    FinancialRecord,
)
from project_db.db.models.docs import DocumentText

logger = logging.getLogger(__name__)

# Bump when the prompt text or output schema changes.
FINANCIAL_PROMPT_VERSION = "financials-v2-direction"

# Who "we" are -- the signal the model needs to tell client-facing revenue
# (a quote/estimate/invoice WE issue) from contractor cost (a bill issued TO
# us).  Without this, a detailed cost-itemized estimate on our own letterhead
# was misread as contractor_out, inverting the whole money picture.  Config,
# not schema: override with COMPANY_NAME in .env if the entity changes.
DEFAULT_COMPANY_NAME = "Alta Construction Group"


def _company_name() -> str:
    return (os.environ.get("COMPANY_NAME") or DEFAULT_COMPANY_NAME).strip()

# Bilingual (EN/FR) keyword priors used to pick which of a project's many
# documents are worth sending to the model.  This is ONLY a cheap pre-filter
# to keep the prompt small and focused -- the model still reads the content
# and decides.  Folder/name signal is a hint, never authoritative (5768's
# "Invoices" folder held a quote), so a generous prior is fine.
_FINANCIAL_KEYWORDS = (
    "invoice", "facture", "quote", "soumission", "devis", "estimate",
    "estimat", "receipt", "quittance", "payment", "paiement", "deposit",
    "acompte", "contract", "contrat", "change order", "purchase", "bon de",
    "sales", "billing", "cost", "budget", "financ", "material", "materiel",
    "contractor", "entrepreneur", "sub quote", "order",
)

# Mime types worth reading for money.  Image-only / CAD / archive files never
# carry extractable monetary text.
_FINANCIAL_MIMES = {
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "application/vnd.ms-excel",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/vnd.google-apps.document",
    "application/vnd.google-apps.spreadsheet",
    "text/csv",
    "text/plain",
}


@dataclass
class FinancialExtractionBatch:
    """Outcome of one extraction run -- everything the CLI needs to report."""
    project_id: str
    project_name: str
    prompt_version: str
    records: list[FinancialRecord] = field(default_factory=list)
    documents_considered: int = 0
    superseded_count: int = 0          # prior rows deleted on a fresh run
    llm_raw_item_count: int = 0
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    skipped_reason: str | None = None

    @property
    def created_count(self) -> int:
        return len(self.records)

    def summary(self) -> str:
        if self.skipped_reason:
            return f"[financials] {self.project_name}: skipped -- {self.skipped_reason}"
        line = (
            f"[financials] {self.project_name}: "
            f"{self.created_count} record(s) extracted from "
            f"{self.documents_considered} document(s), "
            f"{self.superseded_count} prior record(s) replaced, "
            f"{len(self.errors)} item(s) rejected as malformed "
            f"(LLM returned {self.llm_raw_item_count})"
        )
        if self.warnings:
            line += f", {len(self.warnings)} flagged for review"
        return line


def extract_financials_for_project(
    session: Session,
    provider: LLMProvider,
    project_id: Any,
    *,
    max_documents: int = 12,
    per_doc_char_cap: int = 8000,
    total_char_budget: int = 48_000,
    # Bounded by the prompt's "prefer totals, don't enumerate every line of a
    # big itemized list" rule.  Without that rule a materials spreadsheet alone
    # produced >16k tokens of JSON and truncated even after complete_json's
    # 1.5x retry bumps -- see the 2026-05-29 first-smoke lesson.
    max_output_tokens: int = 6000,
) -> FinancialExtractionBatch:
    """Extract monetary records from a project's financial documents.

    A run is a fresh snapshot: prior ``FinancialRecord`` rows for this project
    are deleted before new ones are written, so re-running re-reads the
    current documents without accumulating duplicates.

    Records are flushed to the session but NOT committed -- the caller owns
    the transaction.

    A run is a no-op (``skipped_reason`` set) when the project has no
    financial-looking documents with extracted text.
    """
    from project_db.db.models import Project

    project = (
        session.query(Project)
        .filter_by(canonical_id=_as_uuid(project_id))
        .one_or_none()
        if _as_uuid(project_id) else None
    )
    project_name = project.name if project is not None else str(project_id)
    batch = FinancialExtractionBatch(
        project_id=str(project_id),
        project_name=project_name,
        prompt_version=FINANCIAL_PROMPT_VERSION,
    )

    candidates = _select_financial_documents(
        session, project_id,
        max_documents=max_documents,
        per_doc_char_cap=per_doc_char_cap,
        total_char_budget=total_char_budget,
    )
    if not candidates:
        batch.skipped_reason = (
            "no financial-looking documents with extracted text "
            "(run extract-content first, or this project has no quotes/"
            "invoices/estimates on file)"
        )
        return batch

    batch.documents_considered = len(candidates)
    system, user = _build_financial_prompt(candidates, company_name=_company_name())
    try:
        raw = provider.complete_json(
            messages=[LLMMessage(role="user", content=user)],
            system=system,
            max_tokens=max_output_tokens,
        )
    except LLMProviderError as exc:
        batch.errors.append(f"LLM call failed: {exc}")
        batch.skipped_reason = "LLM call failed"
        return batch

    items = _coerce_item_list(raw, key="records")
    batch.llm_raw_item_count = len(items)
    _persist_financial_records(session, batch, items, candidates, project_id)
    return batch


# ---------------------------------------------------------------------------
# Document selection
# ---------------------------------------------------------------------------


@dataclass
class _Candidate:
    """A financial-candidate document plus the (clipped) text shown to the LLM."""
    document: Document
    text: str            # clipped to per_doc_char_cap
    full_text: str       # full extracted text, for excerpt verification
    truncated: bool


def _financial_score(name: str, folder_path: str) -> int:
    """Count financial-keyword hits across a document's name + folder path."""
    hay = f"{name or ''} {folder_path or ''}".lower()
    return sum(1 for kw in _FINANCIAL_KEYWORDS if kw in hay)


def _select_financial_documents(
    session: Session,
    project_id: Any,
    *,
    max_documents: int,
    per_doc_char_cap: int,
    total_char_budget: int,
) -> list[_Candidate]:
    """Pick the financial-candidate documents to send to the model.

    Joins Document -> DocumentText, keeps non-trashed readable financial-mime
    docs with a keyword hit, ranks by keyword score then recency, and fills up
    to the document-count and character budgets.
    """
    pid = _as_uuid(project_id)
    if pid is None:
        return []

    rows = (
        session.query(Document, DocumentText)
        .join(DocumentText, DocumentText.document_id == Document.canonical_id)
        .filter(
            Document.project_id == pid,
            Document.is_trashed.is_(False),
            DocumentText.extracted_text.isnot(None),
        )
        .all()
    )

    scored: list[tuple[int, Any, Document, DocumentText]] = []
    for doc, txt in rows:
        if not (txt.extracted_text or "").strip():
            continue
        # Mime gate: only document types that carry extractable money text.
        if doc.mime_type and doc.mime_type not in _FINANCIAL_MIMES:
            continue
        score = _financial_score(doc.name, doc.folder_path or "")
        if score == 0:
            continue
        scored.append((score, doc.modified_at_source or doc.created_at, doc, txt))

    # Highest keyword score first, then most-recently modified.
    scored.sort(key=lambda r: (r[0], r[1] or datetime.min), reverse=True)

    out: list[_Candidate] = []
    budget = total_char_budget
    for _score, _ts, doc, txt in scored:
        if len(out) >= max_documents or budget <= 0:
            break
        full = txt.extracted_text or ""
        clipped = full[:per_doc_char_cap]
        truncated = len(full) > per_doc_char_cap
        if len(clipped) > budget:
            clipped = clipped[:budget]
            truncated = True
        budget -= len(clipped)
        out.append(
            _Candidate(
                document=doc,
                text=clipped,
                full_text=full,
                truncated=truncated,
            )
        )
    return out


# ---------------------------------------------------------------------------
# Prompt
# ---------------------------------------------------------------------------


def _build_financial_prompt(
    candidates: list[_Candidate], *, company_name: str = DEFAULT_COMPANY_NAME,
) -> tuple[str, str]:
    """Construct (system, user) for financial extraction.

    Documents are enumerated with integer indices; the model references those
    indices in its output, never the document name.  Instruction at the TAIL.
    """
    system = (
        "You are a meticulous bookkeeping assistant for a construction / real-"
        "estate company.  You read financial documents and extract every "
        "monetary amount EXACTLY as written.  Documents may be in English or "
        "French.\n\n"
        f"OUR COMPANY is \"{company_name}\".  Deciding the DIRECTION of money "
        "hinges on who ISSUED a document and who it is ADDRESSED to:\n"
        "- MONEY IN (direction='client_in'): the document is issued BY us and "
        "addressed to a CLIENT/tenant -- our revenue.  Tells: our name on the "
        "letterhead/issuer, or a 'Client', 'Client ID', 'Bill To', or "
        "'Soumis a' field naming someone else.  An ESTIMATE or QUOTE we "
        "prepared for a client is client_in EVEN THOUGH it itemizes our "
        "material/labour COSTS -- it is what we are charging the client.\n"
        "- MONEY OUT (direction='contractor_out'): the document is issued BY "
        "an external contractor, subcontractor, or supplier and billed TO us.  "
        "Tells: someone else's name/letterhead as issuer, and OUR company in "
        "the 'Bill To'/'Sold To'/'Deliver To' field.\n"
        "- If the issuer and recipient are genuinely unclear, use "
        "direction='unknown'.  Do NOT guess.\n\n"
        "Hard rules:\n"
        "- Extract ONLY amounts that actually appear in the document text.  "
        "Never invent or infer a number that is not written.\n"
        "- Every record MUST include 'quoted_excerpt': the verbatim text "
        "(copied exactly, max ~30 words) that contains the amount.  If you "
        "cannot quote it, do not emit the record.\n"
        "- Do NOT do arithmetic.  Do not sum line items, do not compute "
        "totals, do not compute margins.  Only report amounts the document "
        "states.\n"
        "- Mark each amount's record_kind: 'total' for a document/section "
        "grand total, 'line_item' for an individual line, 'tax' for "
        "GST/QST/HST/TPS/TVQ, 'deposit' for a deposit/down-payment, else "
        "'other'.\n"
        "- PREFER the amounts that matter for tracking money in vs out: the "
        "document grand total, section subtotals, deposits, and the tax.  For "
        "a long itemized list (e.g. a materials spreadsheet with many rows), "
        "do NOT emit every individual line -- capture the total and the "
        "handful of largest or most significant line items.  Emit at most "
        "~20 records per document.\n"
        "- Returning few records, or none, is correct when the document has "
        "no clear monetary amounts.\n"
        "- Output STRICT JSON only.  No prose, no markdown fences."
    )

    lines: list[str] = []
    lines.append(
        f"=== FINANCIAL DOCUMENTS ({len(candidates)}) -- "
        f"reference each by its [index] ==="
    )
    for i, cand in enumerate(candidates):
        d = cand.document
        header = f"\n--- DOCUMENT [{i}]: {d.name}"
        if d.folder_path:
            header += f"  |  Drive folder: {d.folder_path}"
        if d.mime_type:
            header += f"  |  type: {d.mime_type}"
        header += " ---"
        lines.append(header)
        if cand.truncated:
            lines.append(
                f"(NOTE: only the first {len(cand.text)} characters are shown; "
                f"the document continues beyond this point.)"
            )
        lines.append(cand.text)

    context_block = "\n".join(lines)

    user = (
        f"{context_block}\n\n"
        "---\n\n"
        "INSTRUCTION: Extract every monetary amount stated in the documents "
        "above.  For each amount, decide direction by WHO issued the document "
        "and who it is addressed to (see the rules above): MONEY IN from the "
        "client ('client_in') when WE issued it to a client, MONEY OUT "
        "('contractor_out') when an external party billed it to us, or "
        "'unknown' if the issuer/recipient is unclear.  Copy the exact "
        "text containing the amount into 'quoted_excerpt'.  Reference each "
        "document by its integer index.  Do not do any arithmetic -- report "
        "only amounts the documents state.  Prefer totals, subtotals, "
        "deposits and tax over enumerating every minor line; emit at most "
        "~20 records per document.\n\n"
        "Return strict JSON:\n\n"
        "{\n"
        '  "records": [\n'
        "    {\n"
        '      "doc_index": <int>,\n'
        '      "direction": "client_in" | "contractor_out" | "unknown",\n'
        '      "doc_role": "quote" | "estimate" | "invoice" | "receipt" '
        '| "change_order" | "other",\n'
        '      "record_kind": "total" | "line_item" | "tax" | "deposit" '
        '| "other",\n'
        '      "counterparty": "<client or contractor/supplier name, or '
        'empty>",\n'
        '      "description": "<what this amount is for>",\n'
        '      "phase": "<phase/section label if the document is phased, '
        'else empty>",\n'
        '      "amount": <number, no currency symbol or thousands '
        'separators>,\n'
        '      "currency": "<e.g. CAD, USD; empty if unstated>",\n'
        '      "doc_date": "YYYY-MM-DD or empty",\n'
        '      "quoted_excerpt": "<verbatim text containing the amount, '
        'max ~30 words>",\n'
        '      "confidence": <float 0.0-1.0>\n'
        "    }\n"
        "  ]\n"
        "}\n\n"
        'If no document contains a clear monetary amount, return '
        '{"records": []}.'
    )
    return system, user


# ---------------------------------------------------------------------------
# Persistence + validation
# ---------------------------------------------------------------------------


def _persist_financial_records(
    session: Session,
    batch: FinancialExtractionBatch,
    items: list[Any],
    candidates: list[_Candidate],
    project_id: Any,
) -> None:
    """Validate each LLM item and turn the good ones into FinancialRecord rows.

    Fresh-snapshot semantics: every prior FinancialRecord for this project is
    deleted first, so a re-run reflects the current documents exactly.
    """
    project_uuid = _as_uuid(project_id)
    if project_uuid is None:
        batch.errors.append(f"bad project id {project_id!r}")
        return

    # Fresh snapshot -- drop the project's prior extracted records.
    prior = (
        session.query(FinancialRecord)
        .filter(FinancialRecord.project_id == project_uuid)
        .all()
    )
    for old in prior:
        session.delete(old)
    batch.superseded_count = len(prior)

    # Normalized full text per doc index, for excerpt verification.
    norm_text_by_index = {i: _norm(c.full_text) for i, c in enumerate(candidates)}

    for raw_item in items:
        if not isinstance(raw_item, dict):
            batch.errors.append(f"item is not an object: {raw_item!r}")
            continue

        idx = raw_item.get("doc_index")
        if not isinstance(idx, int) or not (0 <= idx < len(candidates)):
            batch.errors.append(f"doc_index out of range or non-int: {idx!r}")
            continue

        amount = _parse_amount(raw_item.get("amount"))
        if amount is None:
            batch.errors.append(
                f"doc_index={idx}: unparseable amount {raw_item.get('amount')!r}"
            )
            continue

        direction = _coerce_vocab(
            raw_item.get("direction"), FINANCIAL_DIRECTIONS, "unknown",
            batch, f"doc_index={idx} direction",
        )
        doc_role = _coerce_vocab(
            raw_item.get("doc_role"), FINANCIAL_DOC_ROLES, "other",
            batch, f"doc_index={idx} doc_role", allow_empty=True,
        )
        record_kind = _coerce_vocab(
            raw_item.get("record_kind"), FINANCIAL_RECORD_KINDS, "other",
            batch, f"doc_index={idx} record_kind", allow_empty=True,
        )

        excerpt = str(raw_item.get("quoted_excerpt") or "").strip()
        # Anti-hallucination guard (warn, don't reject -- a human verifies).
        # The load-bearing check is whether the AMOUNT actually appears in the
        # source text: that catches both invented numbers and amounts the
        # model computed itself (e.g. qty x price), which it is told not to do.
        # An earlier verbatim-EXCERPT check was dropped -- PDF text reflow made
        # the model join non-contiguous fragments, flagging correct amounts
        # (3,600 in a real soumission) as false positives.  The excerpt is
        # still stored as human-verifiable evidence; we just don't gate on it.
        if not excerpt:
            batch.warnings.append(
                f"doc_index={idx}: amount {amount} has no quoted_excerpt -- "
                f"evidence is required, verify before trusting"
            )
        amount_verified = _amount_in_text(amount, norm_text_by_index.get(idx, ""))
        if not amount_verified:
            batch.warnings.append(
                f"doc_index={idx}: amount {amount} does not appear in the "
                f"document text -- possible hallucination or a value the model "
                f"computed/expanded itself, verify before trusting"
            )

        cand = candidates[idx]
        record = FinancialRecord(
            project_id=project_uuid,
            document_id=cand.document.canonical_id,
            direction=direction,
            doc_role=doc_role,
            record_kind=record_kind,
            counterparty=_clean_str(raw_item.get("counterparty")),
            description=_clean_str(raw_item.get("description")),
            phase=_clean_str(raw_item.get("phase")),
            amount=amount,
            currency=_clean_str(raw_item.get("currency")),
            doc_date=_parse_date(raw_item.get("doc_date")),
            quoted_excerpt=excerpt or None,
            confidence=_clamp_confidence(raw_item.get("confidence")),
            amount_verified=amount_verified,
            prompt_version=batch.prompt_version,
            source_meta_json=json.dumps(raw_item, ensure_ascii=False),
        )
        session.add(record)
        batch.records.append(record)

    session.flush()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _coerce_item_list(raw: Any, *, key: str = "records") -> list[Any]:
    """Pull the item list out of whatever shape the LLM returned."""
    if isinstance(raw, dict):
        inner = raw.get(key)
        return inner if isinstance(inner, list) else []
    if isinstance(raw, list):
        return raw
    return []


def _coerce_vocab(
    value: Any,
    vocab: set[str],
    default: str,
    batch: FinancialExtractionBatch,
    where: str,
    *,
    allow_empty: bool = False,
) -> str:
    """Constrain a free-form classification string to a known vocabulary.

    Unknown non-empty values warn and fall back to ``default`` -- the schema
    must survive document-convention drift, so we never crash on a label we
    didn't anticipate.  When ``allow_empty`` and the value is blank, return the
    default silently (a missing optional label is not worth a warning).
    """
    s = str(value or "").strip().lower()
    if not s:
        return default
    if s in vocab:
        return s
    if not allow_empty or s:
        batch.warnings.append(
            f"{where}: unknown value {s!r} -- expected one of "
            f"{sorted(vocab)}; using {default!r}"
        )
    return default


def _norm(text: str | None) -> str:
    """Lowercase + collapse whitespace, for forgiving text containment."""
    if not text:
        return ""
    return re.sub(r"\s+", " ", text).strip().lower()


# Maximal digit/separator runs in the text.  Each run is then interpreted
# under BOTH English (comma=thousands, dot=decimal) and French/Quebec
# (comma=decimal) conventions -- this dataset is bilingual and invoices write
# "923,44 $" where English writes "923.44".  We add every plausible reading to
# the value set, because this is a presence check: a real amount must match at
# least one reading.
_DOC_NUMBER_RE = re.compile(r"\d[\d.,]*\d|\d")


def _number_interpretations(token: str) -> set[Decimal]:
    """Plausible Decimal values for one number-ish token (2-dp), both locales."""
    tok = token.strip(".,")
    if not tok:
        return set()
    has_c, has_d = "," in tok, "." in tok
    cands: list[str] = []
    if has_c and has_d:
        # Both present: the rightmost separator is the decimal point.
        if tok.rfind(",") > tok.rfind("."):
            cands.append(tok.replace(".", "").replace(",", "."))  # European 1.234,56
        else:
            cands.append(tok.replace(",", ""))                    # English 1,234.56
    elif has_c:
        cands.append(tok.replace(",", ""))                        # comma = thousands
        # A single comma with 1-2 trailing digits is a French decimal (923,44).
        if tok.count(",") == 1 and 1 <= len(tok.rsplit(",", 1)[1]) <= 2:
            cands.append(tok.replace(",", "."))
    else:
        cands.append(tok)
    out: set[Decimal] = set()
    for cc in cands:
        try:
            out.add(_round2(Decimal(cc)))
        except (InvalidOperation, ValueError):
            continue
    return out


def _document_amounts(norm_text: str) -> set[Decimal]:
    """All numeric values in the text (every locale reading), rounded to 2 dp."""
    out: set[Decimal] = set()
    for m in _DOC_NUMBER_RE.finditer(norm_text):
        out |= _number_interpretations(m.group(0))
    return out


def _round2(d: Decimal) -> Decimal:
    return d.quantize(Decimal("0.01"))


def _amount_in_text(amount: Decimal | None, norm_text: str) -> bool:
    """True if the amount's VALUE appears in the document text (2-dp tolerance).

    Value-based, not string-based: the source may write the same money many
    ways (12.50 / 12.5, 3,600.00 / 3600, 549241.8481 rounding to 549241.85).
    Comparing rounded Decimal values clears those false positives while still
    flagging amounts that are genuinely absent -- a sum the model computed
    itself, or notation/words it expanded ("8k", "eight thousand").
    """
    if amount is None:
        return False
    return _round2(amount) in _document_amounts(norm_text)


def _clean_str(value: Any) -> str | None:
    """Trim a string field; empty -> None."""
    if value is None:
        return None
    s = str(value).strip()
    return s or None


def _parse_amount(value: Any) -> Decimal | None:
    """Parse a monetary amount into a Decimal.  None / unparseable -> None.

    Tolerates a stray currency symbol or thousands separators in case the
    model ignores the 'no symbol/separator' instruction.
    """
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        try:
            return Decimal(str(value))
        except (InvalidOperation, ValueError):
            return None
    if isinstance(value, str):
        cleaned = value.strip().replace(",", "").replace("$", "")
        cleaned = re.sub(r"[A-Za-z]", "", cleaned).strip()
        if not cleaned:
            return None
        try:
            return Decimal(cleaned)
        except (InvalidOperation, ValueError):
            return None
    return None


def _parse_date(value: Any) -> date | None:
    """Parse an ISO date string.  None / unparseable -> None (never raises)."""
    if not value or not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value.strip()).date()
    except (ValueError, TypeError):
        return None


def _clamp_confidence(value: Any) -> float | None:
    """Coerce a confidence into [0, 1].  None / non-numeric -> None."""
    if value is None:
        return None
    try:
        f = float(value)
    except (ValueError, TypeError):
        return None
    return max(0.0, min(1.0, f))


def _as_uuid(value: Any) -> uuid.UUID | None:
    """Best-effort UUID coercion; None when not a UUID."""
    if isinstance(value, uuid.UUID):
        return value
    try:
        return uuid.UUID(str(value))
    except (ValueError, TypeError):
        return None
