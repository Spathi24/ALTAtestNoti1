"""Pre-built canned reports.

These are the safest entry point for the AI layer. The LLM doesn't write SQL;
it picks a named report by intent. Each report is a plain function that returns
a list of dicts ready to be summarized in natural language.

Design rules for new reports (matters for the Phase-3 LLM tool layer too):
  - Pure: ``(session, **kwargs) -> data``. No print, no logging side-effects,
    no I/O. The same function is called from the CLI AND from prompt tooling.
  - Return JSON-serializable shapes (str / int / float / bool / list / dict).
    UUIDs become str; Decimals become float; dates ISO-stringified.
  - Never raise on "no data" -- return an empty list or an explicit
    ``{"error": "..."}`` dict so the dispatcher can render a useful message.
  - Cap result sizes (top-N, never SELECT *) so the LLM never blows context.

Add new reports here.  The naming convention is ``report_<topic>(...)``.
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any
from uuid import UUID as _UUID

from sqlalchemy.orm import Session

from project_db.db.models import (
    Client,
    DailyLog,
    Deal,
    Document,
    ExternalId,
    Invoice,
    InvoiceStatus,
    LeadStage,
    Project,
    ProjectStatus,
    Task,
    TaskStatus,
)
from project_db.db.models.docs import DocumentText


def _ser(value: Any) -> Any:
    """Best-effort JSON-serializable coercion.

    Enums must be checked BEFORE str/int because our status enums inherit
    from str (`class ProjectStatus(str, enum.Enum)`); without this, the
    isinstance(str) branch would yield "ProjectStatus.PROPOSED" instead of
    the desired "PROPOSED".
    """
    import enum as _enum
    if value is None:
        return None
    if isinstance(value, _enum.Enum):
        return value.value
    if isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, _UUID):
        return str(value)
    return str(value)


def _resolve_project(session: Session, ref: str) -> Project | None:
    """Resolve a project reference (UUID string OR a name substring) to a Project.

    Used by every per-project report so callers can be flexible about whether
    they pass an exact canonical_id or a friendly name fragment.
    """
    if not ref:
        return None
    try:
        cid = _UUID(ref)
        return session.query(Project).filter_by(canonical_id=cid).one_or_none()
    except (ValueError, AttributeError):
        pass
    # Substring match on name (case-insensitive)
    return (
        session.query(Project)
        .filter(Project.name.ilike(f"%{ref}%"))
        .first()
    )


def report_active_projects(session: Session) -> list[dict[str, Any]]:
    """List every project with status ACTIVE."""
    rows = session.query(Project).filter_by(status=ProjectStatus.ACTIVE).all()
    return [
        {
            "canonical_id": str(p.canonical_id),
            "name": p.name,
            "code": p.code,
            "start_date": p.start_date.isoformat() if p.start_date else None,
        }
        for p in rows
    ]


def report_deal_pipeline_value(session: Session) -> list[dict[str, Any]]:
    """Sum of open deal values, grouped by stage."""
    from sqlalchemy import func

    rows = (
        session.query(Deal.stage, func.sum(Deal.value), func.count(Deal.canonical_id))
        .filter(Deal.stage.notin_([LeadStage.WON, LeadStage.LOST]))
        .group_by(Deal.stage)
        .all()
    )
    return [
        {"stage": stage.value, "total_value": float(total or 0), "count": count}
        for stage, total, count in rows
    ]


def report_ar_aging(session: Session) -> list[dict[str, Any]]:
    """Outstanding invoices by status."""
    from sqlalchemy import func

    rows = (
        session.query(
            Invoice.status,
            func.sum(Invoice.amount),
            func.count(Invoice.canonical_id),
        )
        .filter(Invoice.status.in_([InvoiceStatus.SENT, InvoiceStatus.OVERDUE, InvoiceStatus.PARTIAL]))
        .group_by(Invoice.status)
        .all()
    )
    return [
        {"status": status.value, "total": float(total or 0), "count": count}
        for status, total, count in rows
    ]


def report_entity_external_ids(
    session: Session, entity_type: str, canonical_id: str
) -> list[dict[str, Any]]:
    """Show every source-system ID associated with one canonical entity.

    Useful for the AI to answer "where does Project X live in our systems?"
    """
    rows = (
        session.query(ExternalId)
        .filter_by(entity_type=entity_type, canonical_id=canonical_id)
        .all()
    )
    return [
        {
            "source": r.source.value,
            "external_key": r.external_key,
            "external_url": r.external_url,
            "last_synced_at": r.last_synced_at.isoformat() if r.last_synced_at else None,
        }
        for r in rows
    ]


def report_project_overview(session: Session, project_ref: str) -> dict[str, Any]:
    """One-screen snapshot of everything we know about one project.

    Touches Projects, Tasks, Documents, Invoices, DailyLogs, Client, and the
    ExternalId bridge.  Caps inner collections at top-N so an LLM reading
    this can fit it in context.

    Returns ``{"error": "..."}`` when the project_ref doesn't resolve.
    """
    project = _resolve_project(session, project_ref)
    if project is None:
        return {"error": f"No project matched ref={project_ref!r}"}

    pid = project.canonical_id
    client = (
        session.query(Client).filter_by(canonical_id=project.client_id).one_or_none()
        if project.client_id else None
    )

    tasks_all = session.query(Task).filter_by(project_id=pid).all()
    docs_all = session.query(Document).filter_by(project_id=pid, is_trashed=False).all()
    invoices_all = session.query(Invoice).filter_by(project_id=pid).all()
    daily_logs_all = session.query(DailyLog).filter_by(project_id=pid).all()

    tasks_no_dates = [
        t for t in tasks_all
        if t.start_date is None and t.end_date is None and t.due_date is None
    ]

    # Top 10 recent docs by source-side modified time.
    recent_docs = sorted(
        docs_all,
        key=lambda d: d.modified_at_source or d.created_at,
        reverse=True,
    )[:10]

    external_ids = (
        session.query(ExternalId)
        .filter_by(entity_type="Project", canonical_id=pid)
        .all()
    )

    return {
        "project": {
            "canonical_id": _ser(pid),
            "name": project.name,
            "code": project.code,
            "status": _ser(project.status),
            "start_date": _ser(project.start_date),
            "end_date": _ser(project.end_date),
            "budget_amount": _ser(project.budget_amount),
            "contract_amount": _ser(project.contract_amount),
        },
        "client": (
            {"canonical_id": _ser(client.canonical_id), "name": client.name}
            if client else None
        ),
        "stats": {
            "task_count": len(tasks_all),
            "tasks_without_dates": len(tasks_no_dates),
            "document_count": len(docs_all),
            "invoice_count": len(invoices_all),
            "invoice_total": float(sum((inv.amount or 0) for inv in invoices_all)),
            "daily_log_count": len(daily_logs_all),
        },
        "tasks": [
            {
                "title": t.title,
                "status": _ser(t.status),
                "start_date": _ser(t.start_date),
                "end_date": _ser(t.end_date),
                "due_date": _ser(t.due_date),
                "is_subitem": bool(t.is_subitem),
            }
            for t in tasks_all[:50]
        ],
        "recent_documents": [
            {
                "name": d.name,
                "mime_type": d.mime_type,
                "folder_path": d.folder_path,
                "size_bytes": d.size_bytes,
                "modified_at_source": _ser(d.modified_at_source),
                "url": d.url,
            }
            for d in recent_docs
        ],
        "invoices": [
            {
                "number": inv.number,
                "amount": _ser(inv.amount),
                "status": _ser(inv.status),
                "issue_date": _ser(inv.issue_date),
                "due_date": _ser(inv.due_date),
            }
            for inv in invoices_all
        ],
        "external_ids": [
            {
                "source": _ser(x.source),
                "external_key": x.external_key,
                "external_url": x.external_url,
            }
            for x in external_ids
        ],
    }


def report_docs_for_project(session: Session, project_ref: str) -> dict[str, Any]:
    """Every (non-trashed) Document for one project, ordered by folder then name."""
    project = _resolve_project(session, project_ref)
    if project is None:
        return {"error": f"No project matched ref={project_ref!r}"}

    docs = (
        session.query(Document)
        .filter_by(project_id=project.canonical_id, is_trashed=False)
        .order_by(Document.folder_path.is_(None), Document.folder_path, Document.name)
        .all()
    )
    return {
        "project": {"canonical_id": _ser(project.canonical_id), "name": project.name},
        "document_count": len(docs),
        "documents": [
            {
                "name": d.name,
                "mime_type": d.mime_type,
                "folder_path": d.folder_path,
                "size_bytes": d.size_bytes,
                "modified_at_source": _ser(d.modified_at_source),
                "url": d.url,
            }
            for d in docs
        ],
    }


def report_tasks_without_dates(
    session: Session, project_ref: str | None = None
) -> dict[str, Any]:
    """Tasks missing start/end/due dates -- the core "blind spot" problem.

    Per STRATEGY.md: only 11% of Monday tasks are dated.  This report surfaces
    the rest so the LLM in Phase 3 can target them for proposal generation.
    """
    q = session.query(Task).filter(
        Task.start_date.is_(None),
        Task.end_date.is_(None),
        Task.due_date.is_(None),
    )
    project = None
    if project_ref:
        project = _resolve_project(session, project_ref)
        if project is None:
            return {"error": f"No project matched ref={project_ref!r}"}
        q = q.filter(Task.project_id == project.canonical_id)

    tasks = q.all()
    # Pre-fetch projects + their docs counts so we can give folder_path context.
    project_ids = {t.project_id for t in tasks}
    projects = {
        p.canonical_id: p
        for p in session.query(Project).filter(Project.canonical_id.in_(project_ids)).all()
    } if project_ids else {}

    return {
        "scope": "single-project" if project else "all-projects",
        "task_count": len(tasks),
        "tasks": [
            {
                "title": t.title,
                "status": _ser(t.status),
                "project_name": projects.get(t.project_id).name
                    if projects.get(t.project_id) else None,
                "project_id": _ser(t.project_id),
                "is_subitem": bool(t.is_subitem),
                "monday_status_label": t.monday_status_label,
            }
            for t in tasks[:200]
        ],
    }


# Mime types that count as "this project has a contract on file."
_CONTRACT_MIMES = {
    "application/pdf",
    "application/vnd.google-apps.document",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}


def report_missing_documents(session: Session) -> dict[str, Any]:
    """Projects with zero contract-shaped Documents.

    A project with no PDF, Google Doc, or DOCX is suspicious -- the contract
    is probably somewhere outside Drive (or our folder match missed it).
    """
    from sqlalchemy import exists, and_

    contract_exists = exists().where(
        and_(
            Document.project_id == Project.canonical_id,
            Document.is_trashed.is_(False),
            Document.mime_type.in_(_CONTRACT_MIMES),
        )
    )
    projects = (
        session.query(Project)
        .filter(
            Project.status.in_([ProjectStatus.ACTIVE, ProjectStatus.PROPOSED]),
            ~contract_exists,
        )
        .all()
    )

    return {
        "missing_count": len(projects),
        "projects": [
            {
                "canonical_id": _ser(p.canonical_id),
                "name": p.name,
                "code": p.code,
                "status": _ser(p.status),
                "budget_amount": _ser(p.budget_amount),
            }
            for p in projects
        ],
    }


# Picks up "$123,456.78" / "$123,456" / "$123.45" (with optional decimals + commas).
import re as _re

_MONEY_RE = _re.compile(r"\$\s?([0-9]{1,3}(?:,[0-9]{3})+|[0-9]+)(?:\.[0-9]{1,2})?")


def _extract_money_amounts(text: str | None) -> list[float]:
    """Pull dollar amounts from prose.  Cheap regex, no NLP.

    Phase 3 will replace this with LLM extraction.  For Phase 2 this just
    gives us *something* to compare to the Monday budget.
    """
    if not text:
        return []
    out: list[float] = []
    for m in _MONEY_RE.finditer(text):
        try:
            out.append(float(m.group(0).lstrip("$").replace(",", "").strip()))
        except ValueError:
            pass
    return out


def report_budget_vs_contract(
    session: Session, project_ref: str, *, divergence_threshold: float = 0.15
) -> dict[str, Any]:
    """Compare Monday budget vs. largest dollar amount found in contract text.

    For each PDF / Google Doc / DOCX with extracted text under this project,
    regex out dollar amounts and surface the maximum (heuristic: the contract
    total is usually the biggest number).  Compare to Monday budget.  Flag if
    >threshold (default 15%) divergent.

    This is intentionally crude -- Phase 3 swaps the regex for a real LLM
    extraction prompt.  The structure of the report stays the same so
    downstream consumers don't have to change.
    """
    project = _resolve_project(session, project_ref)
    if project is None:
        return {"error": f"No project matched ref={project_ref!r}"}

    budget = float(project.budget_amount) if project.budget_amount is not None else None

    rows = (
        session.query(Document, DocumentText)
        .join(DocumentText, DocumentText.document_id == Document.canonical_id)
        .filter(
            Document.project_id == project.canonical_id,
            Document.is_trashed.is_(False),
            Document.mime_type.in_(_CONTRACT_MIMES),
            DocumentText.extracted_text.isnot(None),
        )
        .all()
    )

    per_doc: list[dict[str, Any]] = []
    for doc, txt in rows:
        amounts = _extract_money_amounts(txt.extracted_text)
        per_doc.append({
            "document_name": doc.name,
            "amounts_found": amounts,
            "max_amount": max(amounts) if amounts else None,
        })

    # Aggregate: the biggest number across all contract docs is our best guess.
    all_amounts = [a for d in per_doc for a in d["amounts_found"]]
    contract_estimate = max(all_amounts) if all_amounts else None

    divergence_pct = None
    flagged = False
    if budget and contract_estimate:
        divergence_pct = abs(contract_estimate - budget) / budget
        flagged = divergence_pct > divergence_threshold

    return {
        "project": {"canonical_id": _ser(project.canonical_id), "name": project.name},
        "monday_budget": budget,
        "contract_amount_estimate": contract_estimate,
        "divergence_pct": divergence_pct,
        "divergence_threshold": divergence_threshold,
        "flagged": flagged,
        "per_document": per_doc,
        "note": "Heuristic regex extraction; replaced by LLM in Phase 3.",
    }


REPORT_REGISTRY: dict[str, Any] = {
    "active_projects": report_active_projects,
    "deal_pipeline_value": report_deal_pipeline_value,
    "ar_aging": report_ar_aging,
    "entity_external_ids": report_entity_external_ids,
    "project_overview": report_project_overview,
    "docs_for_project": report_docs_for_project,
    "tasks_without_dates": report_tasks_without_dates,
    "missing_documents": report_missing_documents,
    "budget_vs_contract": report_budget_vs_contract,
}
