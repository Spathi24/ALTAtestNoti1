"""Contract-obligation extraction -- the Money-at-Risk layer.

Reads a project's contract / SOW / settlement / lease documents and pulls every
dated/dollar OBLIGATION (payment milestone, retainage, penalty, deposit,
settlement, insurance/permit deadline) into ``ContractObligation`` rows, each
with the verbatim clause that proves it.  Deterministic code
(``report_commitments``) then reconciles them against invoices + Monday status +
today; this module only EXTRACTS (invariant N2).

Deliberately mirrors ``ai/financials.py`` and reuses its hard-won helpers
(amount verification, transient-error backoff, locale-tolerant parsers).  Same
postures: candidate pre-filter, batched calls, ALL-OR-NOTHING snapshot (a failed
batch keeps prior rows and writes nothing), validate-don't-crash, conservative
prompt.  The system prompt is STABLE across docs so prompt caching applies.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy.orm import Session

from project_db.ai.financials import (
    _amount_in_text,
    _as_uuid,
    _clamp_confidence,
    _clean_str,
    _coerce_item_list,
    _company_name,
    _complete_with_backoff,
    _norm,
    _parse_amount,
    _parse_date,
)
from project_db.ai.providers import LLMProviderError
from project_db.db.models import (
    OBLIGATION_DIRECTIONS,
    OBLIGATION_KINDS,
    ContractObligation,
    Document,
    Project,
)
from project_db.db.models.docs import DocumentText

OBLIGATION_PROMPT_VERSION = "obligations-v1"

# Mimes that carry obligations (contracts / SOWs / settlements as documents).
_CONTRACT_MIMES = {
    "application/pdf",
    "application/vnd.google-apps.document",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}

# Bilingual keyword prior -- a doc is a candidate if its name/folder OR its text
# hints at an obligation.  Cheap pre-filter; the LLM still reads the content.
_OBLIGATION_KEYWORDS = (
    "payment", "milestone", "deposit", "retainage", "holdback", "retenue",
    "penalt", "liquidated", "damages", "insurance", "assurance", "permit",
    "permis", "deadline", "settlement", "quittance", "completion", "achevement",
    "balance", "final payment", "echeance", "due", "contract", "contrat",
    "agreement", "entente", "sow", "scope of work", "lease", "bail",
)


@dataclass
class ObligationBatch:
    """Outcome of one extraction run -- everything the CLI needs to report."""
    project_id: str
    project_name: str
    prompt_version: str
    obligations: list[ContractObligation] = field(default_factory=list)
    documents_considered: int = 0
    llm_raw_item_count: int = 0
    superseded_count: int = 0
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    skipped_reason: str | None = None

    @property
    def created_count(self) -> int:
        return len(self.obligations)

    def summary(self) -> str:
        if self.skipped_reason:
            return f"[obligations] {self.project_name}: skipped -- {self.skipped_reason}"
        return (
            f"[obligations] {self.project_name}: {self.created_count} obligation(s) "
            f"from {self.documents_considered} document(s) "
            f"(superseded {self.superseded_count})"
        )


@dataclass
class _Candidate:
    document: Document
    text: str
    score: int


def _coerce_vocab(value: Any, vocab: set[str], default: str,
                  batch: ObligationBatch, where: str) -> str:
    s = str(value or "").strip().lower()
    if not s:
        return default
    if s in vocab:
        return s
    batch.warnings.append(
        f"{where}: unknown value {s!r} -- expected one of {sorted(vocab)}; "
        f"using {default!r}"
    )
    return default


def _select_obligation_documents(
    session: Session, project_id: Any, *, max_documents: int, per_doc_char_cap: int,
) -> list[_Candidate]:
    """Contract-shaped docs with text, scored by obligation keywords."""
    rows = (
        session.query(Document, DocumentText.extracted_text)
        .join(DocumentText, DocumentText.document_id == Document.canonical_id)
        .filter(
            Document.project_id == project_id,
            Document.is_trashed.is_(False),
            DocumentText.extracted_text.isnot(None),
        )
        .all()
    )
    cands: list[_Candidate] = []
    for doc, text in rows:
        if not text or not text.strip():
            continue
        hay = f"{doc.name or ''} {doc.folder_path or ''} {text[:4000]}".lower()
        score = sum(1 for kw in _OBLIGATION_KEYWORDS if kw in hay)
        if doc.mime_type in _CONTRACT_MIMES:
            score += 2
        if score <= 0:
            continue
        cands.append(_Candidate(document=doc, text=text[:per_doc_char_cap], score=score))
    cands.sort(key=lambda c: c.score, reverse=True)
    return cands[:max_documents]


def _chunk_candidates(
    candidates: list[_Candidate], char_budget: int, max_docs: int,
) -> list[list[_Candidate]]:
    batches: list[list[_Candidate]] = []
    cur: list[_Candidate] = []
    cur_chars = 0
    for cand in candidates:
        clen = len(cand.text)
        if cur and (len(cur) >= max_docs or cur_chars + clen > char_budget):
            batches.append(cur)
            cur, cur_chars = [], 0
        cur.append(cand)
        cur_chars += clen
    if cur:
        batches.append(cur)
    return batches


def _build_obligation_prompt(chunk: list[_Candidate], company_name: str) -> tuple[str, str]:
    """(system, user).  System is STABLE (cache-friendly); user holds the docs."""
    system = (
        "You are a construction-contract analyst. You read contract / "
        "scope-of-work / settlement / lease documents and extract OBLIGATIONS -- "
        "commitments that carry a DATE and/or a DOLLAR AMOUNT.\n\n"
        "Kinds to extract:\n"
        "- payment_milestone: a scheduled payment (e.g. '25% on completion').\n"
        "- retainage: a holdback / retainage release.\n"
        "- penalty: a late-completion / liquidated-damages / penalty clause.\n"
        "- deposit: an upfront deposit due.\n"
        "- settlement: a settlement / buyout payment (e.g. a tenant on key return).\n"
        "- insurance_expiry: an insurance certificate / coverage that expires.\n"
        "- permit_deadline: a permit or filing deadline.\n\n"
        f"The company you work for is \"{company_name}\". Set direction:\n"
        f"- owed_to_us : the CLIENT owes {company_name} (money for us to collect).\n"
        f"- owed_by_us : {company_name} owes someone (a sub, tenant, authority).\n"
        "- unknown    : you cannot tell.\n\n"
        "For each obligation return: document (the NUMBER of the document it came "
        "from), kind, direction, description, amount (a number, no currency symbol "
        "or separators; null if there is no amount), currency, due_date (ISO "
        "yyyy-mm-dd ONLY if the document gives an explicit calendar date, else "
        "null), trigger (the triggering CONDITION in the document's own words when "
        "there is no fixed date, e.g. 'upon key return'; null if a date is given), "
        "counterparty, quoted_excerpt (the verbatim sentence/clause that proves "
        "it), confidence (0-1).\n\n"
        "Hard rules:\n"
        "- Extract ONLY obligations explicitly stated. NEVER invent an amount, a "
        "date, or a clause.\n"
        "- If an item has NO amount AND NO date AND NO clear trigger, skip it.\n"
        "- Returning few or none is correct.\n"
        "- Output STRICT JSON only: {\"obligations\": [ ... ]}. No prose, no markdown."
    )
    lines: list[str] = ["DOCUMENTS:"]
    for i, cand in enumerate(chunk, 1):
        doc = cand.document
        header = f"\n--- DOCUMENT {i}: {doc.name}"
        if doc.folder_path:
            header += f"  |  folder: {doc.folder_path}"
        header += " ---"
        lines.append(header)
        lines.append(cand.text)
    lines.append(
        "\n\n---\nINSTRUCTION: Extract every obligation from the documents above "
        "as STRICT JSON {\"obligations\": [...]}. Reference each by its document "
        "number, and quote the verbatim clause in quoted_excerpt."
    )
    return system, "\n".join(lines)


def _build_obligations_for_batch(
    batch: ObligationBatch, items: list[Any], chunk: list[_Candidate], project_uuid: Any,
) -> list[ContractObligation]:
    norm_texts = [_norm(c.text) for c in chunk]
    out: list[ContractObligation] = []
    for i, item in enumerate(items):
        if not isinstance(item, dict):
            batch.errors.append(f"obligation {i}: not an object")
            continue
        amount = _parse_amount(item.get("amount"))
        due = _parse_date(item.get("due_date"))
        trigger = _clean_str(item.get("trigger"))
        # Server-side enforcement of the "must be dated or dollar" rule.
        if amount is None and due is None and not trigger:
            batch.warnings.append(
                f"obligation {i}: no amount, date, or trigger -- skipped"
            )
            continue

        kind = _coerce_vocab(item.get("kind"), OBLIGATION_KINDS, "other",
                             batch, f"obligation {i} kind")
        direction = _coerce_vocab(item.get("direction"), OBLIGATION_DIRECTIONS,
                                  "unknown", batch, f"obligation {i} direction")

        # Resolve the source document by 1-based index (single-doc batch: attribute
        # to that doc).  Verify the amount's value against THAT document's text.
        doc_id = None
        verified = None
        idx = None
        try:
            idx = int(item.get("document")) - 1
        except (TypeError, ValueError):
            idx = 0 if len(chunk) == 1 else None
        if idx is not None and 0 <= idx < len(chunk):
            doc_id = chunk[idx].document.canonical_id
            if amount is not None:
                verified = _amount_in_text(amount, norm_texts[idx])

        out.append(ContractObligation(
            project_id=project_uuid,
            document_id=doc_id,
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
            amount_verified=verified,
            prompt_version=OBLIGATION_PROMPT_VERSION,
            source_meta_json=json.dumps(item, default=str),
        ))
    return out


def extract_obligations_for_project(
    session: Session,
    provider: Any,
    project_id: Any,
    *,
    max_documents: int = 200,
    per_doc_char_cap: int = 8000,
    batch_char_budget: int = 14_000,
    batch_max_docs: int = 5,
    max_output_tokens: int = 6000,
) -> ObligationBatch:
    """Extract obligations from ALL of a project's contract documents.

    Fresh snapshot, all-or-nothing: prior rows are kept until a FULL success,
    then swapped.  A failed batch (transient rate limit) keeps the prior set and
    writes nothing.  Flushes; the caller owns the commit.  No-op
    (``skipped_reason``) when no contract-looking docs with text exist.
    """
    project_uuid = _as_uuid(project_id)
    project = (
        session.query(Project).filter_by(canonical_id=project_uuid).one_or_none()
        if project_uuid else None
    )
    batch = ObligationBatch(
        project_id=str(project_id),
        project_name=project.name if project is not None else str(project_id),
        prompt_version=OBLIGATION_PROMPT_VERSION,
    )
    if project_uuid is None:
        batch.errors.append(f"bad project id {project_id!r}")
        batch.skipped_reason = "invalid project id"
        return batch

    candidates = _select_obligation_documents(
        session, project_uuid,
        max_documents=max_documents, per_doc_char_cap=per_doc_char_cap,
    )
    if not candidates:
        batch.skipped_reason = (
            "no contract-looking documents with extracted text "
            "(run extract-content first)"
        )
        return batch
    batch.documents_considered = len(candidates)

    prior = (
        session.query(ContractObligation)
        .filter(ContractObligation.project_id == project_uuid)
        .all()
    )

    new_obligations: list[ContractObligation] = []
    any_batch_failed = False
    for chunk in _chunk_candidates(candidates, batch_char_budget, batch_max_docs):
        system, user = _build_obligation_prompt(chunk, _company_name())
        try:
            raw = _complete_with_backoff(provider, system, user, max_output_tokens)
        except LLMProviderError as exc:
            names = ", ".join(c.document.name or "?" for c in chunk)
            batch.errors.append(f"LLM call failed for batch [{names[:120]}]: {exc}")
            any_batch_failed = True
            continue
        items = _coerce_item_list(raw, key="obligations")
        batch.llm_raw_item_count += len(items)
        new_obligations.extend(
            _build_obligations_for_batch(batch, items, chunk, project_uuid)
        )

    if any_batch_failed:
        batch.obligations = []
        batch.superseded_count = 0
        batch.skipped_reason = (
            "one or more document batches failed (often a transient API rate "
            "limit) -- prior obligations were kept and NOTHING was changed. Re-run."
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
