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
    Lead,
    LeadStage,
    Project,
    ProjectStatus,
    Task,
    TaskStatus,
)
from project_db.db.models.docs import DocumentText
from project_db.identity.matcher import normalize_name


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


def _crm_deal_for_project_placeholder(session: Session, project: Project) -> Deal | None:
    """Return the matching Deal for a CRM-only project placeholder, if any.

    Monday's "Client Projects" board can contain rows named like
    "Project - Amazon deal". Those are sales-pipeline placeholders, not
    construction projects, when they have no tasks/docs and a real Deal row
    exists for "Amazon deal". Reports should not treat them as failed project
    records.
    """
    import re

    name = project.name or ""
    match = re.match(r"^\s*project\s*-+\s*(.+?)\s*$", name, flags=re.I)
    if not match:
        return None

    deal_name = match.group(1)
    if "deal" not in deal_name.lower():
        return None

    wanted = normalize_name(deal_name)
    if not wanted:
        return None

    for deal in session.query(Deal).all():
        if normalize_name(deal.name or "") == wanted:
            return deal
    return None


def _is_crm_deal_placeholder_project(session: Session, project: Project) -> bool:
    """True when a Project row is really an empty CRM deal placeholder."""
    if _crm_deal_for_project_placeholder(session, project) is None:
        return False

    task_count = session.query(Task).filter(Task.project_id == project.canonical_id).count()
    if task_count:
        return False

    doc_count = (
        session.query(Document)
        .filter(
            Document.project_id == project.canonical_id,
            Document.is_trashed.is_(False),
        )
        .count()
    )
    return doc_count == 0


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
                "canonical_id": _ser(t.canonical_id),
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
                "canonical_id": _ser(d.canonical_id),
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
                "canonical_id": _ser(d.canonical_id),
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
                "canonical_id": _ser(t.canonical_id),
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

    projects = [
        p for p in projects
        if not _is_crm_deal_placeholder_project(session, p)
    ]

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


def report_database_overview(
    session: Session, *, max_tasks: int = 600
) -> dict[str, Any]:
    """Whole-database canonical snapshot -- the context for the LLM `ask` fallback.

    Every structured operational fact ALTA holds: projects (with rolled-up
    counts), tasks, deals, leads, clients, invoices, and a document-category
    breakdown.  Document *text* is deliberately excluded -- it is large, and
    per-project document reasoning is what `daily` / `propose` are for.

    Collections are capped (``max_tasks``) so the snapshot stays inside a
    small model's context window.  Pure + JSON-serializable, like every
    report in this module.
    """
    from sqlalchemy import func

    clients = {c.canonical_id: c for c in session.query(Client).all()}
    projects = session.query(Project).order_by(Project.name).all()
    all_tasks = session.query(Task).all()
    invoices = session.query(Invoice).all()
    deals = session.query(Deal).order_by(Deal.name).all()
    leads = session.query(Lead).all()

    # Roll up per-project counts -- one pass / one grouped query each, no N+1.
    tasks_by_project: dict[Any, list[Task]] = {}
    for t in all_tasks:
        tasks_by_project.setdefault(t.project_id, []).append(t)
    docs_by_project: dict[Any, int] = dict(
        session.query(Document.project_id, func.count(Document.canonical_id))
        .filter(Document.is_trashed.is_(False))
        .group_by(Document.project_id)
        .all()
    )
    invoices_by_project: dict[Any, int] = {}
    for inv in invoices:
        invoices_by_project[inv.project_id] = (
            invoices_by_project.get(inv.project_id, 0) + 1
        )

    project_name_by_id = {p.canonical_id: p.name for p in projects}

    project_rows: list[dict[str, Any]] = []
    for p in projects:
        ptasks = tasks_by_project.get(p.canonical_id, [])
        dateless = sum(
            1 for t in ptasks
            if not t.start_date and not t.end_date and not t.due_date
        )
        client = clients.get(p.client_id)
        project_rows.append({
            "name": p.name,
            "status": _ser(p.status),
            "start_date": _ser(p.start_date),
            "end_date": _ser(p.end_date),
            "budget_amount": _ser(p.budget_amount),
            "contract_amount": _ser(p.contract_amount),
            "client": client.name if client else None,
            "task_count": len(ptasks),
            "tasks_without_dates": dateless,
            "document_count": docs_by_project.get(p.canonical_id, 0),
            "invoice_count": invoices_by_project.get(p.canonical_id, 0),
        })

    task_rows = [
        {
            "title": t.title,
            "project": project_name_by_id.get(t.project_id),
            "status": _ser(t.status),
            "monday_status_label": t.monday_status_label,
            "priority": t.priority,
            "start_date": _ser(t.start_date),
            "end_date": _ser(t.end_date),
            "due_date": _ser(t.due_date),
            "is_subitem": bool(t.is_subitem),
        }
        for t in all_tasks[:max_tasks]
    ]

    deal_rows = [
        {
            "name": d.name,
            "stage": _ser(d.stage),
            "value": _ser(d.value),
            "expected_close_date": _ser(d.expected_close_date),
            "client": clients[d.client_id].name if d.client_id in clients else None,
        }
        for d in deals
    ]

    lead_rows = [
        {
            "stage": _ser(ld.stage),
            "source_channel": ld.source_channel,
            "estimated_value": _ser(ld.estimated_value),
            "client": clients[ld.client_id].name if ld.client_id in clients else None,
        }
        for ld in leads
    ]

    invoice_rows = [
        {
            "number": inv.number,
            "amount": _ser(inv.amount),
            "status": _ser(inv.status),
            "issue_date": _ser(inv.issue_date),
            "due_date": _ser(inv.due_date),
            "project": project_name_by_id.get(inv.project_id),
        }
        for inv in invoices
    ]

    doc_categories = dict(
        session.query(Document.category, func.count(Document.canonical_id))
        .filter(Document.is_trashed.is_(False))
        .group_by(Document.category)
        .all()
    )
    total_docs = (
        session.query(Document).filter(Document.is_trashed.is_(False)).count()
    )

    return {
        "generated_on": date.today().isoformat(),
        "totals": {
            "projects": len(projects),
            "tasks": len(all_tasks),
            "deals": len(deals),
            "leads": len(leads),
            "clients": len(clients),
            "invoices": len(invoices),
            "documents": total_docs,
        },
        "projects": project_rows,
        "tasks": task_rows,
        "tasks_truncated": len(all_tasks) > max_tasks,
        "deals": deal_rows,
        "leads": lead_rows,
        "clients": sorted(c.name for c in clients.values() if c.name),
        "invoices": invoice_rows,
        "documents_by_category": {
            (str(k) if k is not None else "uncategorized"): v
            for k, v in doc_categories.items()
        },
    }


def report_doctor(session: Session) -> dict[str, Any]:
    """Data behind `project_db doctor` -- audit project / document integrity.

    Pure, JSON-serializable, no I/O.  Both the CLI ``cmd_doctor`` renderer
    AND the web UI ``/doctor`` page consume this; if you change a check,
    change it here and both surfaces update.
    """
    from sqlalchemy import func

    from project_db.db.models import ExternalId, SourceSystem
    from project_db.identity.matcher import extract_civic_numbers

    flags: list[str] = []
    projects = session.query(Project).order_by(Project.name).all()

    civic_seen: dict[str, list[str]] = {}
    proj_by_id: dict[Any, Project] = {}
    project_rows: list[dict[str, Any]] = []
    for p in projects:
        proj_by_id[p.canonical_id] = p
        exts = (
            session.query(ExternalId)
            .filter(ExternalId.canonical_id == p.canonical_id)
            .all()
        )
        drive = [
            e for e in exts
            if e.source == SourceSystem.GOOGLE_DRIVE
            and (e.external_key or "").startswith("folder:")
        ]
        monday = [e for e in exts if e.source == SourceSystem.MONDAY]
        ndoc = (
            session.query(Document)
            .filter(
                Document.project_id == p.canonical_id,
                Document.is_trashed.is_(False),
            )
            .count()
        )
        ntask = session.query(Task).filter(Task.project_id == p.canonical_id).count()
        crm_deal = _crm_deal_for_project_placeholder(session, p)
        is_crm_deal_placeholder = bool(crm_deal and ndoc == 0 and ntask == 0)

        sources: list[str] = []
        if drive:
            sources.append(f"Drive x{len(drive)}")
        if monday:
            sources.append(f"Monday x{len(monday)}")
        if is_crm_deal_placeholder:
            sources.append(f"CRM deal: {crm_deal.name}")

        per_project_flags: list[str] = []
        if not drive and not is_crm_deal_placeholder:
            msg = (
                f"{p.name!r}: no Drive folder -- Monday-only. If it is a "
                f"real project, give it a folder under 01. PROJECTS/"
                f"<ACTIVE|INACTIVE|LEADS>/; otherwise it is a stray board "
                f"to remove in Monday."
            )
            flags.append(msg)
            per_project_flags.append("no-drive-folder")
        if ndoc == 0 and ntask == 0 and not is_crm_deal_placeholder:
            flags.append(f"{p.name!r}: 0 documents and 0 tasks -- empty record")
            per_project_flags.append("empty-record")

        for civic in extract_civic_numbers(p.name or ""):
            civic_seen.setdefault(civic, []).append(p.name)

        project_rows.append({
            "canonical_id": str(p.canonical_id),
            "name": p.name,
            "status": _ser(p.status),
            "drive_count": len(drive),
            "monday_count": len(monday),
            "doc_count": ndoc,
            "task_count": ntask,
            "is_crm_deal_placeholder": is_crm_deal_placeholder,
            "crm_deal_name": crm_deal.name if crm_deal else None,
            "sources_label": ", ".join(sources) or "NONE",
            "flags": per_project_flags,
        })

    civic_duplicates: list[dict[str, Any]] = []
    for civic, names in sorted(civic_seen.items()):
        if len(names) > 1:
            civic_duplicates.append({"civic": civic, "names": names})
            flags.append(
                f"civic number {civic} shared by {len(names)} projects: {names}"
            )

    mislinked_rows: list[dict[str, Any]] = []
    for d in (
        session.query(Document)
        .filter(Document.project_id.isnot(None), Document.is_trashed.is_(False))
        .all()
    ):
        p = proj_by_id.get(d.project_id)
        if p is None or not d.folder_path:
            continue
        if p.name not in [seg.strip() for seg in d.folder_path.split("/")]:
            mislinked_rows.append({
                "document_id": str(d.canonical_id),
                "document_name": d.name,
                "folder_path": d.folder_path,
                "linked_project_id": str(p.canonical_id),
                "linked_project_name": p.name,
            })
    if mislinked_rows:
        flags.append(
            f"{len(mislinked_rows)} document(s) linked to a project that is "
            f"NOT their Drive-folder ancestor (mislink)"
        )

    total = session.query(Document).filter(Document.is_trashed.is_(False)).count()
    linked = (
        session.query(Document)
        .filter(Document.project_id.isnot(None), Document.is_trashed.is_(False))
        .count()
    )
    category_rows = (
        session.query(Document.category, func.count(Document.canonical_id))
        .filter(Document.is_trashed.is_(False))
        .group_by(Document.category)
        .all()
    )
    by_category = {
        (cat or "(none)"): int(n)
        for cat, n in sorted(category_rows, key=lambda r: -(r[1] or 0))
    }
    orphans = (
        session.query(Document)
        .filter(
            Document.project_id.is_(None),
            Document.category.is_(None),
            Document.is_trashed.is_(False),
        )
        .count()
    )
    if orphans:
        flags.append(
            f"{orphans} document(s) with neither a project nor a category "
            f"(orphans -- usually files with no folder_path)"
        )

    return {
        "projects": project_rows,
        "civic_duplicates": civic_duplicates,
        "documents": {
            "total": int(total),
            "linked": int(linked),
            "orphans": int(orphans),
            "by_category": by_category,
        },
        "mislinked": mislinked_rows,
        "flags": flags,
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
