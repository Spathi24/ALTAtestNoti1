"""Project context assembler.

Pulls everything joinable for one Project into a structured block the
LLM can read.  The output of ``assemble_project_context`` is the single
input every Phase-3 prompt will receive -- timeline extraction, scope
reconciliation, anomaly detection all start here.

Design rules:
  - Pure ``(session, project_id) -> ProjectContext``.  No I/O, no LLM calls.
  - JSON-serializable everywhere (re-uses the ``_ser`` helper from views).
  - Size-bounded.  Documents come last in the prompt block because they
    eat the most tokens; we drop their bodies first if we exceed budget.
  - Trashed Documents are excluded; trashed Tasks/Projects are kept
    (canceled projects still need to be reasoned about).

The ``token_budget`` knob is in characters/4 by the same heuristic the
extractors use.  Default 150k tokens fits comfortably in Claude's 200k
context; tune up for newer models, down for fine-tuned 8k-context ones.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from sqlalchemy.orm import Session

from project_db.ai.views import _ser  # canonical JSON-friendly serializer
from project_db.db.models import (
    Client,
    DailyLog,
    Document,
    Invoice,
    Project,
    Task,
)
from project_db.db.models.docs import DocumentText

# ~4 chars/token, matches extractors.estimate_tokens.
_CHARS_PER_TOKEN = 4

# Per-document cap when fitting many docs into a context block: keep the
# first N chars of each, so we get a sample of every contract rather
# than the full text of one and zero of the others.
# 16k chars ≈ 4k tokens ≈ the first ~5 pages of a document -- enough to
# carry a contract's schedule/scope sections with their surrounding
# context, not just an out-of-context fragment.  The genuinely long
# (50+ page) contracts still get truncated; relevant-chunk retrieval
# (RAG) is the fix for those, now implemented (see CHANGELOG / ai/rag.py).
_PER_DOC_CHAR_CAP_DEFAULT = 16000


@dataclass
class ProjectContext:
    """Structured snapshot of a project for LLM consumption.

    Two views: ``to_dict()`` for JSON serialization / debugging, and
    ``to_prompt_block()`` for dropping straight into a prompt.
    """
    project: dict[str, Any]
    client: dict[str, Any] | None
    tasks: list[dict[str, Any]]
    documents: list[dict[str, Any]]          # metadata only
    document_texts: list[dict[str, Any]]     # name + mime + text excerpt
    invoices: list[dict[str, Any]]
    daily_logs: list[dict[str, Any]]
    truncated: dict[str, Any] = field(default_factory=dict)
    """Records what was cut to fit the budget, for transparency.
    Shape: {"document_bodies_truncated": int, "tasks_dropped": int, ...}
    """

    # ----- views -----

    def to_dict(self) -> dict[str, Any]:
        return {
            "project": self.project,
            "client": self.client,
            "tasks": self.tasks,
            "documents": self.documents,
            "document_texts": self.document_texts,
            "invoices": self.invoices,
            "daily_logs": self.daily_logs,
            "truncated": self.truncated,
        }

    def to_prompt_block(self) -> str:
        """Render as a structured text block.

        Sections are ordered by importance: project header → client →
        tasks → invoices → daily logs → documents metadata → document
        bodies.  Document bodies last because they're the biggest and
        will be the first thing the LLM skims; putting the structured
        canonical data on top keeps the model anchored on facts before
        free-form contract prose.
        """
        parts: list[str] = []
        parts.append("=== PROJECT ===")
        parts.append(_kv_block(self.project))

        if self.client:
            parts.append("\n=== CLIENT ===")
            parts.append(_kv_block(self.client))

        parts.append(f"\n=== TASKS ({len(self.tasks)}) ===")
        if self.tasks:
            for t in self.tasks:
                parts.append(_task_line(t))
        else:
            parts.append("(none)")

        parts.append(f"\n=== INVOICES ({len(self.invoices)}) ===")
        if self.invoices:
            for inv in self.invoices:
                parts.append(_invoice_line(inv))
        else:
            parts.append("(none)")

        if self.daily_logs:
            parts.append(f"\n=== DAILY LOGS ({len(self.daily_logs)}) ===")
            for d in self.daily_logs:
                parts.append(_log_line(d))

        parts.append(f"\n=== DOCUMENTS METADATA ({len(self.documents)}) ===")
        if self.documents:
            for d in self.documents:
                parts.append(_doc_meta_line(d))
        else:
            parts.append("(none)")

        if self.document_texts:
            parts.append(f"\n=== DOCUMENT BODIES ({len(self.document_texts)}) ===")
            for dt in self.document_texts:
                parts.append(f"\n--- {dt['name']} ({dt['mime_type']}) ---")
                parts.append(dt["text"])

        if self.truncated:
            parts.append(f"\n=== TRUNCATION NOTES ===")
            for k, v in self.truncated.items():
                parts.append(f"  {k}: {v}")

        return "\n".join(parts)


# ---------------------------------------------------------------------------
# Builder
# ---------------------------------------------------------------------------


def assemble_project_context(
    session: Session,
    project_id: Any,
    *,
    token_budget: int = 150_000,
    per_doc_char_cap: int = _PER_DOC_CHAR_CAP_DEFAULT,
    max_documents_with_text: int = 30,
) -> ProjectContext:
    """Build a ``ProjectContext`` for one project.

    Args:
      session:           SQLAlchemy session.
      project_id:        canonical_id of the Project.
      token_budget:      Soft cap on the resulting prompt block size.
                         If we exceed it, document bodies are dropped
                         oldest-first and recorded in ``truncated``.
      per_doc_char_cap:  Trim each document body to this many chars
                         BEFORE the global budget check.  Prevents one
                         giant contract from eating the whole budget.
      max_documents_with_text: Cap on how many DocumentTexts we attach.
                         Picks the most-recently-modified ones first.
    """
    project = session.query(Project).filter_by(canonical_id=project_id).one_or_none()
    if project is None:
        raise ValueError(f"No Project with canonical_id={project_id}")

    client = (
        session.query(Client).filter_by(canonical_id=project.client_id).one_or_none()
        if project.client_id else None
    )
    tasks = session.query(Task).filter_by(project_id=project_id).all()
    invoices = session.query(Invoice).filter_by(project_id=project_id).all()
    daily_logs = session.query(DailyLog).filter_by(project_id=project_id).all()

    # All non-trashed docs (metadata for ALL goes into the documents
    # list; the bodies are joined separately and we pick the most-recent
    # ones THAT ACTUALLY HAVE TEXT).
    docs_all = (
        session.query(Document)
        .filter(Document.project_id == project_id, Document.is_trashed.is_(False))
        .all()
    )

    # Pick the N most-recent docs with non-empty extracted text.  This is
    # subtly different from "N most-recent docs (and attach text if any)"
    # -- with that older logic, a fresh photo or HEIC would consume a
    # slot without contributing prose.  Users want N readable bodies.
    docs_with_text = (
        session.query(Document, DocumentText)
        .join(DocumentText, DocumentText.document_id == Document.canonical_id)
        .filter(
            Document.project_id == project_id,
            Document.is_trashed.is_(False),
            DocumentText.extracted_text.isnot(None),
        )
        .all()
    )
    docs_with_text.sort(
        key=lambda pair: pair[0].modified_at_source or pair[0].created_at,
        reverse=True,
    )

    document_texts: list[dict[str, Any]] = []
    for d, dt in docs_with_text[:max_documents_with_text]:
        body = (dt.extracted_text or "")[:per_doc_char_cap]
        document_texts.append({
            "document_id": _ser(d.canonical_id),
            "name": d.name,
            "mime_type": d.mime_type,
            "folder_path": d.folder_path,
            "text": body,
            "truncated": len(dt.extracted_text or "") > per_doc_char_cap,
        })

    # Build the context, then fit it to budget.
    ctx = ProjectContext(
        project=_project_to_dict(project),
        client=_client_to_dict(client) if client else None,
        tasks=[_task_to_dict(t) for t in tasks],
        documents=[_doc_to_dict(d) for d in docs_all],
        document_texts=document_texts,
        invoices=[_invoice_to_dict(inv) for inv in invoices],
        daily_logs=[_log_to_dict(d) for d in daily_logs],
    )
    _fit_to_budget(ctx, token_budget)
    return ctx


# ---------------------------------------------------------------------------
# Internal: entity → dict
# ---------------------------------------------------------------------------


def _project_to_dict(p: Project) -> dict[str, Any]:
    return {
        "canonical_id": _ser(p.canonical_id),
        "name": p.name,
        "code": p.code,
        "status": _ser(p.status),
        "start_date": _ser(p.start_date),
        "end_date": _ser(p.end_date),
        "budget_amount": _ser(p.budget_amount),
        "contract_amount": _ser(p.contract_amount),
    }


def _client_to_dict(c: Client) -> dict[str, Any]:
    return {
        "canonical_id": _ser(c.canonical_id),
        "name": c.name,
        "email": c.email,
        "phone": c.phone,
        "billing_address": c.billing_address,
    }


def _task_to_dict(t: Task) -> dict[str, Any]:
    return {
        "canonical_id": _ser(t.canonical_id),
        "title": t.title,
        "status": _ser(t.status),
        "monday_status_label": t.monday_status_label,
        "start_date": _ser(t.start_date),
        "end_date": _ser(t.end_date),
        "due_date": _ser(t.due_date),
        "duration_days": _ser(t.duration_days),
        "is_subitem": bool(t.is_subitem),
        "parent_task_id": _ser(t.parent_task_id),
        "group_title": t.group_title,
        "priority": t.priority,
    }


def _doc_to_dict(d: Document) -> dict[str, Any]:
    return {
        "canonical_id": _ser(d.canonical_id),
        "name": d.name,
        "mime_type": d.mime_type,
        "folder_path": d.folder_path,
        "size_bytes": d.size_bytes,
        "modified_at_source": _ser(d.modified_at_source),
    }


def _invoice_to_dict(inv: Invoice) -> dict[str, Any]:
    return {
        "canonical_id": _ser(inv.canonical_id),
        "number": inv.number,
        "amount": _ser(inv.amount),
        "status": _ser(inv.status),
        "issue_date": _ser(inv.issue_date),
        "due_date": _ser(inv.due_date),
    }


def _log_to_dict(d: DailyLog) -> dict[str, Any]:
    return {
        "canonical_id": _ser(d.canonical_id),
        "log_date": _ser(d.log_date),
        "summary": d.summary,
    }


# ---------------------------------------------------------------------------
# Internal: prompt-block helpers
# ---------------------------------------------------------------------------


def _kv_block(d: dict[str, Any]) -> str:
    lines = []
    for k, v in d.items():
        if v is None or v == "":
            continue
        lines.append(f"{k}: {v}")
    return "\n".join(lines)


def _task_line(t: dict[str, Any]) -> str:
    bits = [f"- [{t.get('status', '?')}] {t.get('title', '')}"]
    if t.get("start_date") or t.get("end_date") or t.get("due_date"):
        bits.append(
            f"(start={t.get('start_date') or '-'} end={t.get('end_date') or '-'} "
            f"due={t.get('due_date') or '-'})"
        )
    if t.get("monday_status_label"):
        bits.append(f"[Monday: {t['monday_status_label']}]")
    if t.get("is_subitem"):
        bits.append("[subitem]")
    return " ".join(bits)


def _invoice_line(inv: dict[str, Any]) -> str:
    return (
        f"- #{inv.get('number')}  ${inv.get('amount')}  "
        f"status={inv.get('status')}  issued={inv.get('issue_date') or '-'}"
    )


def _log_line(d: dict[str, Any]) -> str:
    return f"- {d.get('log_date')}: {d.get('summary') or '(no summary)'}"


def _doc_meta_line(d: dict[str, Any]) -> str:
    return (
        f"- {d.get('name')}  ({d.get('mime_type')}, "
        f"{d.get('size_bytes') or '?'} bytes, "
        f"modified={d.get('modified_at_source') or '-'}, "
        f"folder={d.get('folder_path') or '-'})"
    )


# ---------------------------------------------------------------------------
# Budget fitting
# ---------------------------------------------------------------------------


def _fit_to_budget(ctx: ProjectContext, token_budget: int) -> None:
    """Trim ``ctx`` in-place until ``to_prompt_block()`` fits the budget.

    Strategy: rendered length / 4 ≈ tokens.  If over budget, drop
    document bodies oldest-first.  Tasks/invoices/metadata stay --
    they're tiny and informative.  Record what was dropped in
    ``ctx.truncated``.
    """
    block = ctx.to_prompt_block()
    tokens = len(block) // _CHARS_PER_TOKEN
    if tokens <= token_budget:
        return

    dropped = 0
    # document_texts is already in newest-first order; pop from the end.
    while ctx.document_texts and tokens > token_budget:
        ctx.document_texts.pop()
        dropped += 1
        block = ctx.to_prompt_block()
        tokens = len(block) // _CHARS_PER_TOKEN

    if dropped:
        ctx.truncated["document_bodies_dropped"] = dropped
        ctx.truncated["final_estimated_tokens"] = tokens
