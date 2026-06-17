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

import re as _re
from datetime import date, timedelta
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
    FinancialRecord,
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
    return session.query(Project).filter(Project.name.ilike(f"%{ref}%")).first()


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
        .filter(
            Invoice.status.in_([InvoiceStatus.SENT, InvoiceStatus.OVERDUE, InvoiceStatus.PARTIAL])
        )
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
        if project.client_id
        else None
    )

    tasks_all = session.query(Task).filter_by(project_id=pid).all()
    docs_all = session.query(Document).filter_by(project_id=pid, is_trashed=False).all()
    invoices_all = session.query(Invoice).filter_by(project_id=pid).all()
    daily_logs_all = session.query(DailyLog).filter_by(project_id=pid).all()

    tasks_no_dates = [
        t for t in tasks_all if t.start_date is None and t.end_date is None and t.due_date is None
    ]

    # Top 10 recent docs by source-side modified time.
    recent_docs = sorted(
        docs_all,
        key=lambda d: d.modified_at_source or d.created_at,
        reverse=True,
    )[:10]

    external_ids = (
        session.query(ExternalId).filter_by(entity_type="Project", canonical_id=pid).all()
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
            {"canonical_id": _ser(client.canonical_id), "name": client.name} if client else None
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


def report_tasks_without_dates(session: Session, project_ref: str | None = None) -> dict[str, Any]:
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
    projects = (
        {
            p.canonical_id: p
            for p in session.query(Project).filter(Project.canonical_id.in_(project_ids)).all()
        }
        if project_ids
        else {}
    )

    return {
        "scope": "single-project" if project else "all-projects",
        "task_count": len(tasks),
        "tasks": [
            {
                "canonical_id": _ser(t.canonical_id),
                "title": t.title,
                "status": _ser(t.status),
                "project_name": projects.get(t.project_id).name
                if projects.get(t.project_id)
                else None,
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
    from sqlalchemy import and_, exists

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

    projects = [p for p in projects if not _is_crm_deal_placeholder_project(session, p)]

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
        per_doc.append(
            {
                "document_name": doc.name,
                "amounts_found": amounts,
                "max_amount": max(amounts) if amounts else None,
            }
        )

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


def _representative_amount(records: list[FinancialRecord]) -> Decimal:
    """Collapse a (document, direction) group to one non-double-counted amount.

    A single financial document often lists line items AND a grand total;
    naively summing every row would count the money twice.  Rule, in order:
      1. If the group has any 'total' record, use the largest total (a doc may
         carry subtotals + a grand total; the grand total is the largest).
      2. Else sum the 'line_item' records.
      3. Else sum whatever remains (deposit/other), excluding 'tax' so we do
         not stack tax on top of a base amount we couldn't classify.

    Returns a Decimal so the caller controls float coercion at the edge.
    """
    totals = [r.amount for r in records if r.record_kind == "total" and r.amount is not None]
    if totals:
        return max(totals)
    line_items = [
        r.amount for r in records if r.record_kind == "line_item" and r.amount is not None
    ]
    if line_items:
        return sum(line_items, Decimal(0))
    rest = [r.amount for r in records if r.record_kind != "tax" and r.amount is not None]
    return sum(rest, Decimal(0))


def report_project_financials(session: Session, project_ref: str) -> dict[str, Any]:
    """Two-sided money-flow reconciliation for one project, from FinancialRecord.

    Computes -- in plain Python, never via the LLM -- the project's:
      - ``client_in_total``: money we invoice/quote the client (revenue)
      - ``contractor_out_total``: money contractors/suppliers bill us (cost)
      - ``margin``: client_in - contractor_out (the upcharge spread)
      - ``unknown_total``: amounts the extractor could not assign a side

    Each (document, direction) group is collapsed via ``_representative_amount``
    so a line item and its document total are not both counted.  Returns the
    per-document breakdown and a capped flat record list for drill-down.

    Returns ``{"error": "..."}`` when the project_ref doesn't resolve.  When
    the project has no extracted financial records, returns zeros with a
    ``note`` pointing at ``extract-financials`` rather than an error.
    """
    project = _resolve_project(session, project_ref)
    if project is None:
        return {"error": f"No project matched ref={project_ref!r}"}

    records = (
        session.query(FinancialRecord)
        .filter(FinancialRecord.project_id == project.canonical_id)
        .all()
    )
    _docs = session.query(Document).filter(Document.project_id == project.canonical_id).all()
    doc_names = {d.canonical_id: d.name for d in _docs}
    doc_folders = {d.canonical_id: d.folder_path for d in _docs}

    # Split: PRIMARY transaction docs drive the totals; ROLL-UP / tracking
    # sheets are excluded (they restate the invoices, so summing both would
    # double-count) and surfaced separately as a cross-check.  Decision: the
    # individual invoices/quotes/contracts are authoritative.
    # Effective roll-up = stored value OR the CURRENT name rule OR the CONTENT
    # rule (a projection/model sheet whose name hides it).  Re-deriving here
    # means improving the rules cleans up already-extracted projects for FREE,
    # with no re-extraction -- the same free-recompute discipline as money_type.
    from project_db.ai.financials import (
        _name_is_rollup as _is_rollup_name,
    )
    from project_db.ai.financials import (
        content_is_rollup as _is_rollup_content,
    )

    _rec_doc_ids = {r.document_id for r in records if r.document_id}
    doc_texts = (
        {
            row[0]: row[1]
            for row in session.query(DocumentText.document_id, DocumentText.extracted_text)
            .filter(DocumentText.document_id.in_(_rec_doc_ids))
            .all()
        }
        if _rec_doc_ids
        else {}
    )

    def _eff_rollup(r: FinancialRecord) -> bool:
        return (
            bool(r.is_rollup)
            or _is_rollup_name(doc_names.get(r.document_id))
            or _is_rollup_content(doc_texts.get(r.document_id))
        )

    primary = [r for r in records if not _eff_rollup(r)]
    rollup = [r for r in records if _eff_rollup(r)]

    # --- Confirmed-vs-quoted -------------------------------------------------
    # They dump every quote into a project, including ones they didn't go with.
    # Explicit human decisions live in document_financial_status (separate table
    # -> survives re-extraction).  Absent => smart default: a doc with an
    # invoice/receipt role is confirmed (work happened); pure quotes/estimates
    # are not.  Confirmed totals are computed ALONGSIDE the all-in totals so the
    # panel shows both and can live-toggle.
    from project_db.ai.financials import default_confirmed
    from project_db.db.models import DocumentFinancialStatus

    primary_doc_ids = {r.document_id for r in primary}
    doc_roles_by_id: dict[Any, set[str]] = {}
    for r in primary:
        doc_roles_by_id.setdefault(r.document_id, set()).add(r.doc_role or "other")
    explicit_status = (
        {
            s.document_id: bool(s.confirmed)
            for s in session.query(DocumentFinancialStatus)
            .filter(DocumentFinancialStatus.document_id.in_(primary_doc_ids))
            .all()
        }
        if primary_doc_ids
        else {}
    )

    def _doc_confirmed(doc_id: Any) -> bool:
        if doc_id in explicit_status:
            return explicit_status[doc_id]
        return default_confirmed(doc_roles_by_id.get(doc_id, set()))

    confirmed_doc_ids = {d for d in primary_doc_ids if _doc_confirmed(d)}
    confirmed_primary = [r for r in primary if r.document_id in confirmed_doc_ids]

    def _rollup_by_dir(recs: list[FinancialRecord]) -> dict[str, Any]:
        """Per-(document,direction) representative-amount aggregation."""
        groups: dict[tuple[Any, str], list[FinancialRecord]] = {}
        for r in recs:
            groups.setdefault((r.document_id, r.direction or "unknown"), []).append(r)
        dir_totals: dict[str, Decimal] = {
            "client_in": Decimal(0),
            "contractor_out": Decimal(0),
            "unknown": Decimal(0),
        }
        per_doc: dict[Any, dict[str, Any]] = {}
        for (doc_id, direction), grp in groups.items():
            rep = _representative_amount(grp)
            dir_totals[direction] = dir_totals.get(direction, Decimal(0)) + rep
            entry = per_doc.setdefault(
                doc_id,
                {
                    "document_id": _ser(doc_id),
                    "document_name": doc_names.get(doc_id, "(unknown document)"),
                    "client_in": Decimal(0),
                    "contractor_out": Decimal(0),
                    "unknown": Decimal(0),
                    "record_count": 0,
                },
            )
            entry[direction] = entry.get(direction, Decimal(0)) + rep
            entry["record_count"] += len(grp)
        return {"dir_totals": dir_totals, "per_doc": per_doc}

    agg = _rollup_by_dir(primary)
    direction_totals = agg["dir_totals"]
    per_document = agg["per_doc"]

    client_in = direction_totals.get("client_in", Decimal(0))
    contractor_out = direction_totals.get("contractor_out", Decimal(0))
    unknown_total = direction_totals.get("unknown", Decimal(0))
    margin = client_in - contractor_out

    # Confirmed-only direction totals (same logic, confirmed primary docs only).
    c_agg = _rollup_by_dir(confirmed_primary)["dir_totals"]
    c_client_in = c_agg.get("client_in", Decimal(0))
    c_contractor_out = c_agg.get("contractor_out", Decimal(0))
    confirmed_totals = {
        "client_in": float(c_client_in),
        "contractor_out": float(c_contractor_out),
        "unknown": float(c_agg.get("unknown", Decimal(0))),
        "margin": float(c_client_in - c_contractor_out),
    }

    per_document_rows = []
    for doc_id, entry in per_document.items():
        per_document_rows.append(
            {
                "document_id": entry["document_id"],
                "document_name": entry["document_name"],
                "client_in": float(entry.get("client_in", Decimal(0))),
                "contractor_out": float(entry.get("contractor_out", Decimal(0))),
                "unknown": float(entry.get("unknown", Decimal(0))),
                "record_count": entry["record_count"],
                "confirmed": doc_id in confirmed_doc_ids,
                "confirmed_source": "explicit" if doc_id in explicit_status else "default",
            }
        )
    per_document_rows.sort(
        key=lambda r: r["client_in"] + r["contractor_out"] + r["unknown"],
        reverse=True,
    )

    # Roll-up cross-check: what the internal summary sheets say, NOT added to
    # the totals.  A big gap between this and the primary totals is a signal
    # the invoices or the tracker are out of sync.
    rollup_agg = _rollup_by_dir(rollup)
    rollup_crosscheck = {
        "document_count": len({r.document_id for r in rollup}),
        "client_in": float(rollup_agg["dir_totals"].get("client_in", Decimal(0))),
        "contractor_out": float(rollup_agg["dir_totals"].get("contractor_out", Decimal(0))),
        "unknown": float(rollup_agg["dir_totals"].get("unknown", Decimal(0))),
        "documents": [
            {
                "document_id": e["document_id"],
                "document_name": e["document_name"],
                "client_in": float(e.get("client_in", Decimal(0))),
                "contractor_out": float(e.get("contractor_out", Decimal(0))),
                "unknown": float(e.get("unknown", Decimal(0))),
                "record_count": e["record_count"],
            }
            for e in rollup_agg["per_doc"].values()
        ],
    }

    # Money-type breakdown (deterministic) over PRIMARY records.  Separates
    # incompatible kinds of money -- contract revenue, supplier cost, tenant
    # buyout cost, lease/rental, deposit, tax -- so the report doesn't net a
    # buyout against a renovation.  Grouped by (doc, money_type) with the same
    # representative-amount dedup as the direction totals.
    from project_db.ai.financials import classify_money_type

    def _mt(r: FinancialRecord) -> str:
        return classify_money_type(
            r.direction,
            r.record_kind,
            doc_names.get(r.document_id),
            doc_folders.get(r.document_id),
        )

    def _money_by_type(recs: list[FinancialRecord]) -> dict[str, float]:
        groups: dict[tuple[Any, str], list[FinancialRecord]] = {}
        for r in recs:
            groups.setdefault((r.document_id, _mt(r)), []).append(r)
        dec: dict[str, Decimal] = {}
        for (_doc, mtype), grp in groups.items():
            dec[mtype] = dec.get(mtype, Decimal(0)) + _representative_amount(grp)
        return {k: float(v) for k, v in sorted(dec.items())}

    by_money_type = _money_by_type(primary)
    confirmed_by_money_type = _money_by_type(confirmed_primary)

    contract_rev = by_money_type.get("contract_revenue", 0.0)
    supplier_cost = by_money_type.get("supplier_cost", 0.0)
    buyout_cost = by_money_type.get("buyout_cost", 0.0)
    other_amt = by_money_type.get("other", 0.0)
    confirmed_construction_margin = confirmed_by_money_type.get(
        "contract_revenue", 0.0
    ) - confirmed_by_money_type.get("supplier_cost", 0.0)

    # Coverage / confidence: how much of the project's money landed in an
    # INTERPRETABLE bucket vs 'other' (direction unknown / a project type the
    # model doesn't handle).  A low ratio means the reconciliation -- and the
    # margin -- should not be trusted at face value.  Surfaced loudly so an
    # unmodeled project (e.g. the 6554 real-estate development deal: asking
    # price, loan, lease income) does NOT masquerade as a confident margin.
    interpretable = sum(v for k, v in by_money_type.items() if k != "other")
    total_primary_money = interpretable + other_amt
    classified_ratio = interpretable / total_primary_money if total_primary_money else None
    low_confidence = classified_ratio is not None and classified_ratio < 0.5

    money_summary = {
        # Renovation profitability -- the figure that nets cleanly.
        "construction_margin": contract_rev - supplier_cost,
        "buyout_cost_to_date": buyout_cost,
        # Buyout margin needs the client-agreed price (agency model); per the
        # owner that figure is typically NOT in the documents, so we do NOT
        # invent it -- it must be supplied to compute buyout margin.
        "buyout_margin": None,
        "buyout_note": (
            "Agency buyout: margin = client-agreed budget minus actual buyout "
            "cost. The agreed budget was not found in the documents; supply it "
            "to compute buyout margin."
            if buyout_cost
            else None
        ),
        "classified_ratio": classified_ratio,
        "low_confidence": low_confidence,
        "confidence_note": (
            "LOW CONFIDENCE: most of this project's money could not be "
            "classified as revenue or cost. This is usually a project type the "
            "model does not yet handle (e.g. a real-estate development / "
            "investment deal -- asking price, financing, lease income). Treat "
            "the margin with caution; see the 'other' bucket."
            if low_confidence
            else None
        ),
    }

    unverified_count = sum(1 for r in records if r.amount_verified is False)

    return {
        "project": {"canonical_id": _ser(project.canonical_id), "name": project.name},
        "record_count": len(records),
        "primary_record_count": len(primary),
        "rollup_record_count": len(rollup),
        "unverified_count": unverified_count,
        "totals": {
            "client_in": float(client_in),
            "contractor_out": float(contractor_out),
            "unknown": float(unknown_total),
            "margin": float(margin),
        },
        "by_money_type": by_money_type,
        "money_summary": money_summary,
        # Confirmed-vs-quoted: the human-controlled view.  Totals over confirmed
        # primary docs only; the all-in totals above stay for reference.
        "confirmed_totals": confirmed_totals,
        "confirmed_by_money_type": confirmed_by_money_type,
        "confirmed_construction_margin": confirmed_construction_margin,
        "confirmation": {
            "confirmed_docs": len(confirmed_doc_ids),
            "total_primary_docs": len(primary_doc_ids),
            "explicit_decisions": len(explicit_status),
        },
        "per_document": per_document_rows,
        "rollup_crosscheck": rollup_crosscheck,
        "records": [
            {
                "canonical_id": _ser(r.canonical_id),
                "document_id": _ser(r.document_id),
                "document_name": doc_names.get(r.document_id),
                "direction": r.direction,
                "doc_role": r.doc_role,
                "record_kind": r.record_kind,
                "counterparty": r.counterparty,
                "description": r.description,
                "phase": r.phase,
                "amount": _ser(r.amount),
                "currency": r.currency,
                "doc_date": _ser(r.doc_date),
                "quoted_excerpt": r.quoted_excerpt,
                "confidence": r.confidence,
                "amount_verified": r.amount_verified,
                "is_rollup": _eff_rollup(r),
                "money_type": _mt(r),
                "confirmed": r.document_id in confirmed_doc_ids,
            }
            for r in records[:200]
        ],
        "note": (
            "Totals sum PRIMARY transaction documents only; internal roll-up / "
            "tracking sheets are excluded and shown under rollup_crosscheck to "
            "avoid double-counting. Run extract-financials to (re)populate."
            if records
            else "No financial records yet. Run: project_db extract-financials "
            f"--project {project.canonical_id}"
        ),
    }


def report_database_overview(session: Session, *, max_tasks: int = 600) -> dict[str, Any]:
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
        invoices_by_project[inv.project_id] = invoices_by_project.get(inv.project_id, 0) + 1

    project_name_by_id = {p.canonical_id: p.name for p in projects}

    project_rows: list[dict[str, Any]] = []
    for p in projects:
        ptasks = tasks_by_project.get(p.canonical_id, [])
        dateless = sum(1 for t in ptasks if not t.start_date and not t.end_date and not t.due_date)
        client = clients.get(p.client_id)
        project_rows.append(
            {
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
            }
        )

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
    total_docs = session.query(Document).filter(Document.is_trashed.is_(False)).count()

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
            (str(k) if k is not None else "uncategorized"): v for k, v in doc_categories.items()
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
        exts = session.query(ExternalId).filter(ExternalId.canonical_id == p.canonical_id).all()
        drive = [
            e
            for e in exts
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

        project_rows.append(
            {
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
            }
        )

    civic_duplicates: list[dict[str, Any]] = []
    for civic, names in sorted(civic_seen.items()):
        if len(names) > 1:
            civic_duplicates.append({"civic": civic, "names": names})
            flags.append(f"civic number {civic} shared by {len(names)} projects: {names}")

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
            mislinked_rows.append(
                {
                    "document_id": str(d.canonical_id),
                    "document_name": d.name,
                    "folder_path": d.folder_path,
                    "linked_project_id": str(p.canonical_id),
                    "linked_project_name": p.name,
                }
            )
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
        (cat or "(none)"): int(n) for cat, n in sorted(category_rows, key=lambda r: -(r[1] or 0))
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


# ---------------------------------------------------------------------------
# Commitments / Money-at-Risk -- deterministic reconciliation of obligations
# ---------------------------------------------------------------------------
#
# The chokepoint for ContractObligation, mirroring report_project_financials for
# money. The LLM extracted the obligations (with evidence); here we compute --
# deterministically, no LLM (invariant N2) -- which ones are overdue, due soon,
# or conditional, and how much money is at risk on each side.

_OBLIGATION_DUE_SOON_DAYS = 30
_OBLIGATION_STATUS_RANK = {
    "overdue": 4,
    "due_soon": 3,
    "conditional": 2,
    "upcoming": 1,
    "open": 0,
}


def _obligation_status(ob: Any, today: date, due_soon_days: int) -> str:
    """Deterministic status for one obligation from its date / trigger."""
    if ob.due_date is not None:
        if ob.due_date < today:
            return "overdue"
        if ob.due_date <= today + timedelta(days=due_soon_days):
            return "due_soon"
        return "upcoming"
    if ob.trigger:
        return "conditional"  # depends on a condition, no fixed date
    return "open"


def report_commitments(
    session: Session,
    project_ref: str,
    *,
    today: date | None = None,
    due_soon_days: int = _OBLIGATION_DUE_SOON_DAYS,
) -> dict[str, Any]:
    """Per-project obligations with deterministic status + money-at-risk totals.

    Returns ``{"error": ...}`` on an unresolved ref; zeros + a ``note`` when the
    project has no extracted obligations (pointing at ``extract-obligations``).
    Pure / JSON-serializable. ``owed_to_us`` overdue = revenue past due to
    collect; ``owed_by_us`` overdue = a payment/deadline we've missed.
    """
    from project_db.db.models import ContractObligation

    project = _resolve_project(session, project_ref)
    if project is None:
        return {"error": f"No project matched ref={project_ref!r}"}
    today = today or date.today()

    obs = (
        session.query(ContractObligation)
        .filter(ContractObligation.project_id == project.canonical_id)
        .all()
    )
    doc_names = {
        d.canonical_id: d.name
        for d in session.query(Document).filter(Document.project_id == project.canonical_id).all()
    }

    rows: list[dict[str, Any]] = []
    counts: dict[str, int] = {}
    money = {
        "owed_to_us_overdue": Decimal(0),
        "owed_to_us_total": Decimal(0),
        "owed_by_us_overdue": Decimal(0),
        "owed_by_us_total": Decimal(0),
    }
    for ob in obs:
        status = _obligation_status(ob, today, due_soon_days)
        counts[status] = counts.get(status, 0) + 1
        amt = ob.amount if ob.amount is not None else Decimal(0)
        if ob.direction == "owed_to_us":
            money["owed_to_us_total"] += amt
            if status == "overdue":
                money["owed_to_us_overdue"] += amt
        elif ob.direction == "owed_by_us":
            money["owed_by_us_total"] += amt
            if status == "overdue":
                money["owed_by_us_overdue"] += amt
        rows.append(
            {
                "canonical_id": _ser(ob.canonical_id),
                "kind": ob.kind,
                "direction": ob.direction,
                "status": status,
                "amount": _ser(ob.amount),
                "currency": ob.currency,
                "due_date": _ser(ob.due_date),
                "trigger": ob.trigger,
                "description": ob.description,
                "counterparty": ob.counterparty,
                "quoted_excerpt": ob.quoted_excerpt,
                "confidence": ob.confidence,
                "amount_verified": ob.amount_verified,
                "document_id": _ser(ob.document_id),
                "document_name": doc_names.get(ob.document_id),
            }
        )

    # Most urgent first (status rank, then larger amounts).
    rows.sort(
        key=lambda r: (
            _OBLIGATION_STATUS_RANK.get(r["status"], 0),
            float(r["amount"] or 0),
        ),
        reverse=True,
    )

    return {
        "project": {"canonical_id": _ser(project.canonical_id), "name": project.name},
        "generated_on": today.isoformat(),
        "obligation_count": len(obs),
        "counts": counts,
        "money_at_risk": {k: float(v) for k, v in money.items()},
        "obligations": rows,
        "note": (
            None
            if obs
            else f"No obligations extracted yet. Run: project_db extract-obligations {project.name}"
        ),
    }


# ---------------------------------------------------------------------------
# Value caught -- the ROI scoreboard (INTENTIONS #2)
# ---------------------------------------------------------------------------
#
# A single deterministic number (no LLM, free to recompute over stored rows)
# answering the owner's boss: "how much money has ALTA put in front of us?"
# Aggregates the COMMITMENTS money-at-risk across the whole portfolio -- the
# cleanest, non-double-counted exposure. Financial-risk flags (low-confidence
# margins, unconfirmed-quote piles) are deliberately NOT tallied here: a softer,
# different signal that would risk double-counting (a later extension).


def report_value_caught(
    session: Session,
    *,
    today: date | None = None,
    due_soon_days: int = _OBLIGATION_DUE_SOON_DAYS,
) -> dict[str, Any]:
    """Portfolio tally of the money ALTA has surfaced as needing action.

    Buckets (all deterministic, from ``ContractObligation`` via
    ``_obligation_status`` -- the same status logic ``report_commitments`` and
    the briefing use, so the numbers agree):

      - ``receivables_overdue``  : ``owed_to_us`` overdue  -> revenue past due to COLLECT
      - ``receivables_due_soon`` : ``owed_to_us`` due soon
      - ``obligations_overdue``  : ``owed_by_us`` overdue   -> penalty / late exposure we owe

    ``headline_total = receivables_overdue + obligations_overdue`` (the
    boss-facing "money ALTA flagged"). Pure / JSON-serializable; zeros + a note
    when nothing is surfaced yet.
    """
    from project_db.db.models import ContractObligation

    today = today or date.today()
    proj_names = {p.canonical_id: p.name for p in session.query(Project).all()}

    money = {
        "receivables_overdue": Decimal(0),
        "receivables_due_soon": Decimal(0),
        "obligations_overdue": Decimal(0),
    }
    status_counts: dict[str, int] = {}
    per_project: dict[Any, dict[str, Any]] = {}

    obs = session.query(ContractObligation).filter(ContractObligation.project_id.isnot(None)).all()
    for ob in obs:
        status = _obligation_status(ob, today, due_soon_days)
        status_counts[status] = status_counts.get(status, 0) + 1
        amt = ob.amount if ob.amount is not None else Decimal(0)
        pp = per_project.setdefault(
            ob.project_id,
            {
                "project_id": _ser(ob.project_id),
                "project_name": proj_names.get(ob.project_id) or "(unknown project)",
                "receivables_overdue": Decimal(0),
                "receivables_due_soon": Decimal(0),
                "obligations_overdue": Decimal(0),
                "flagged_count": 0,
            },
        )
        # A scoreboard of DOLLARS: only a positive-amount obligation flags a
        # project (a null/$0 overdue item adds nothing and shouldn't show as "$0").
        contributed = Decimal(0)
        if ob.direction == "owed_to_us":
            if status == "overdue":
                money["receivables_overdue"] += amt
                pp["receivables_overdue"] += amt
                contributed = amt
            elif status == "due_soon":
                money["receivables_due_soon"] += amt
                pp["receivables_due_soon"] += amt
                contributed = amt
        elif ob.direction == "owed_by_us" and status == "overdue":
            money["obligations_overdue"] += amt
            pp["obligations_overdue"] += amt
            contributed = amt
        if contributed > 0:
            pp["flagged_count"] += 1

    headline_total = money["receivables_overdue"] + money["obligations_overdue"]

    breakdown = [
        {
            **pp,
            "receivables_overdue": float(pp["receivables_overdue"]),
            "receivables_due_soon": float(pp["receivables_due_soon"]),
            "obligations_overdue": float(pp["obligations_overdue"]),
        }
        for pp in per_project.values()
        if pp["flagged_count"] > 0
    ]
    breakdown.sort(
        key=lambda r: r["receivables_overdue"] + r["obligations_overdue"],
        reverse=True,
    )

    return {
        "generated_on": today.isoformat(),
        "headline_total": float(headline_total),
        "money": {k: float(v) for k, v in money.items()},
        "obligation_count": len(obs),
        "status_counts": status_counts,
        "flagged_project_count": len(breakdown),
        "projects": breakdown,
        "note": (
            None
            if breakdown
            else "No money-at-risk surfaced yet -- run extract-obligations on "
            "projects to populate the tally."
        ),
    }


# ---------------------------------------------------------------------------
# Money one-liner -- the whole financial state of a project in one sentence
# ---------------------------------------------------------------------------
#
# INTENTIONS #3: a deterministic template over report_project_financials +
# report_commitments (no LLM). Honest -- when the picture is low-confidence it
# says so instead of printing a confident margin. ASCII output (cp1252-safe for
# the CLI). Used by the CLI and the project page.


def _money_short(value: Any) -> str:
    """Compact money string: $402, $52k, $1.2M. ASCII-only."""
    x = float(value or 0)
    sign = "-" if x < 0 else ""
    a = abs(x)
    if a >= 1e6:
        return f"{sign}${(f'{a / 1e6:.1f}M').replace('.0M', 'M')}"
    if a >= 1e3:
        return f"{sign}${(f'{a / 1e3:.1f}k').replace('.0k', 'k')}"
    return f"{sign}${a:.0f}"


def report_project_money_line(
    session: Session,
    project_ref: str,
    *,
    today: date | None = None,
) -> dict[str, Any]:
    """One plain-English sentence summarizing a project's money state.

    Returns ``{project, line, low_confidence, has_records}`` (or ``{error}`` on an
    unresolved ref). ``line`` is the headline sentence -- revenue / costs / margin
    for a clean renovation, a LOW-CONFIDENCE note for an unmodeled project type,
    or a "nothing extracted yet" hint -- with a commitments tail when obligations
    are overdue. Pure / deterministic.
    """
    fin = report_project_financials(session, project_ref)
    if fin.get("error"):
        return {"error": fin["error"]}
    name = fin["project"]["name"]
    com = report_commitments(session, project_ref, today=today)

    # Shared tail: overdue obligations / money past due to collect.
    tail = ""
    if not com.get("error") and com.get("obligation_count"):
        overdue = com.get("counts", {}).get("overdue", 0)
        to_collect = com.get("money_at_risk", {}).get("owed_to_us_overdue", 0)
        if overdue:
            tail = f" | {overdue} obligation(s) overdue"
            if to_collect:
                tail += f" ({_money_short(to_collect)} to collect)"

    ms = fin.get("money_summary", {})
    has_records = fin.get("record_count", 0) > 0
    low_conf = bool(ms.get("low_confidence"))

    if not has_records:
        line = f"{name}: no financial records extracted yet (run extract-financials)."
        return {
            "project": fin["project"],
            "line": line,
            "low_confidence": False,
            "has_records": False,
        }

    if low_conf:
        line = (
            f"{name}: money picture LOW CONFIDENCE -- unusual project type; "
            f"{fin['record_count']} record(s), see Financials.{tail}"
        )
        return {
            "project": fin["project"],
            "line": line,
            "low_confidence": True,
            "has_records": True,
        }

    # Headline the CONFIRMED view so the one-liner AGREES with the Financials
    # panel (the money chokepoint). A real margin is shown ONLY when client
    # revenue is actually confirmed; otherwise the revenue side is a pile of
    # unconfirmed quotes (the "we dump every quote in the folder" problem) and a
    # single margin would be misleading -- so we lead with known costs and flag
    # that revenue is unconfirmed, pointing at the panel (which is also the PM's
    # confirm-the-awarded-quote workflow). Honest over confident-but-wrong.
    cbmt = fin.get("confirmed_by_money_type", {})
    conf_rev = cbmt.get("contract_revenue", 0.0)
    conf_cost = cbmt.get("supplier_cost", 0.0)
    totals = fin.get("totals", {})
    if conf_rev > 0:
        margin = fin.get("confirmed_construction_margin", conf_rev - conf_cost)
        line = (
            f"{name}: revenue {_money_short(conf_rev)} | "
            f"costs {_money_short(conf_cost)} | "
            f"margin ~{_money_short(margin)} (confirmed){tail}"
        )
    else:
        cost_known = conf_cost or totals.get("contractor_out", 0.0)
        quoted = totals.get("client_in", 0.0)
        line = (
            f"{name}: {_money_short(cost_known)} in costs so far; client revenue not yet confirmed"
        )
        if quoted:
            line += (
                f" ({_money_short(quoted)} quoted on file -- confirm awarded quotes in Financials)"
            )
        line += tail
    return {"project": fin["project"], "line": line, "low_confidence": False, "has_records": True}


# ---------------------------------------------------------------------------
# Attention briefing -- the Monday-morning risk-and-money surface
# ---------------------------------------------------------------------------
#
# This is the deterministic detector layer the strategy (STRATEGY.md, rule A8)
# calls the "draw": instead of showing the PM activity ALTA *generated* (a
# proposal queue), it surfaces cross-system *truths* ALTA discovered that a PM
# cannot see by opening Monday and Drive in two tabs -- ranked by how much they
# need attention.
#
# Everything here is computed in plain Python/SQL over already-stored canonical
# data (FinancialRecord, Task, Proposal, Document).  No LLM call, no external
# API -- so it is free to run, safe to recompute on every page load, and never
# invents a number (invariant N2: the LLM extracts; deterministic code computes).
# Money items compose ``report_project_financials`` (the one money chokepoint)
# rather than re-summing FinancialRecord rows.

_SEVERITY_RANK = {"high": 3, "medium": 2, "low": 1}

# Tunables for the money/schedule detectors.  Named here so they are auditable
# and a future session can tighten them without spelunking the logic.
_OVERDUE_HIGH_COUNT = 5  # >= this many overdue tasks on one project -> high
_OVERDUE_HIGH_DAYS = 30  # any task overdue by >= this many days -> high
_UNCONFIRMED_PILE_MIN = 20000.0  # unconfirmed quote money >= this -> surface it
_UNCONFIRMED_PILE_MIN_DOCS = 2  # ...and at least this many unconfirmed docs


def report_attention_briefing(
    session: Session, *, limit: int = 25, today: date | None = None
) -> dict[str, Any]:
    """Portfolio-wide ranked list of cross-system truths needing attention.

    Deterministic and free: composes the money / scope / schedule / document
    signals already stored in the canonical DB.  No LLM, no external call, so it
    is safe to recompute on every request.

    Each item is a JSON-serializable dict::

        {"project_id", "project_name", "category", "severity",
         "severity_rank", "weight", "headline", "detail", "link"}

    ``category`` is one of ``money`` / ``scope`` / ``schedule`` / ``documents``;
    ``severity`` is ``high`` / ``medium`` / ``low``.  Items are ranked
    severity-desc, then weight-desc (magnitude within a severity), then project
    name asc.  The returned ``items`` list is capped at ``limit``; the
    ``by_category`` / ``by_severity`` counts describe ALL detected items, not
    just the shown slice.
    """
    today = today or date.today()
    items: list[dict[str, Any]] = []

    proj_by_id: dict[Any, Project] = {p.canonical_id: p for p in session.query(Project).all()}

    def _name(pid: Any) -> str:
        p = proj_by_id.get(pid)
        return p.name if p and p.name else "(unknown project)"

    def _add(
        project_id: Any,
        project_name: str,
        category: str,
        severity: str,
        *,
        weight: float,
        headline: str,
        detail: str,
        link: str,
    ) -> None:
        items.append(
            {
                "project_id": _ser(project_id) if project_id is not None else None,
                "project_name": project_name,
                "category": category,
                "severity": severity,
                "severity_rank": _SEVERITY_RANK[severity],
                "weight": float(weight),
                "headline": headline,
                "detail": detail,
                "link": link,
            }
        )

    # --- MONEY ---------------------------------------------------------------
    # Only projects that actually have extracted financial records; for each we
    # call the money chokepoint once and read its already-computed summary.
    fin_pids = [
        row[0]
        for row in session.query(FinancialRecord.project_id)
        .filter(FinancialRecord.project_id.isnot(None))
        .group_by(FinancialRecord.project_id)
        .all()
    ]
    for pid in fin_pids:
        if pid not in proj_by_id:
            continue
        rep = report_project_financials(session, str(pid))
        if rep.get("error"):
            continue
        name = _name(pid)
        link = f"/projects/{_ser(pid)}/financials"
        ms = rep.get("money_summary", {})
        conf = rep.get("confirmation", {})
        cbmt = rep.get("confirmed_by_money_type", {})
        totals = rep.get("totals", {})
        ctotals = rep.get("confirmed_totals", {})

        if ms.get("low_confidence"):
            # A. Low-confidence reconciliation -- most money couldn't be
            #    classified.  Honest "don't trust this margin" flag.
            ratio = ms.get("classified_ratio")
            pct = f"{ratio * 100:.0f}%" if ratio is not None else "an unknown share"
            _add(
                pid,
                name,
                "money",
                "medium",
                weight=10000 + (1 - (ratio or 0)) * 1000,
                headline=f"{name}: money picture is low-confidence",
                detail=(
                    f"Only {pct} of this project's money sorted into "
                    f"revenue/cost buckets, so the margin is unreliable. "
                    f"Usually a project type the model does not yet model."
                ),
                link=link,
            )
        else:
            # B. Confirmed costs exceed confirmed revenue -- a real loss signal.
            #    Guarded: only when confidence is OK AND there is confirmed
            #    revenue to compare.  A buyout/agency project legitimately has no
            #    revenue in its docs, so we must not cry "loss" there.
            rev = float(cbmt.get("contract_revenue", 0.0) or 0.0)
            cost = float(cbmt.get("supplier_cost", 0.0) or 0.0)
            if rev > 0 and cost > rev:
                gap = cost - rev
                _add(
                    pid,
                    name,
                    "money",
                    "high",
                    weight=gap,
                    headline=(f"{name}: confirmed costs exceed confirmed revenue by {gap:,.0f}"),
                    detail=(
                        f"Confirmed supplier cost {cost:,.0f} vs confirmed "
                        f"contract revenue {rev:,.0f}. Possible loss, an "
                        f"un-filed revenue document, or unbilled work."
                    ),
                    link=link,
                )

        # C. A pile of unconfirmed quote money -- nudge the confirm/quote toggle.
        unconfirmed_in = float(totals.get("client_in", 0.0) or 0.0) - float(
            ctotals.get("client_in", 0.0) or 0.0
        )
        unconfirmed_out = float(totals.get("contractor_out", 0.0) or 0.0) - float(
            ctotals.get("contractor_out", 0.0) or 0.0
        )
        pile = max(unconfirmed_in, unconfirmed_out)
        unconfirmed_docs = int(conf.get("total_primary_docs", 0)) - int(
            conf.get("confirmed_docs", 0)
        )
        if pile >= _UNCONFIRMED_PILE_MIN and unconfirmed_docs >= _UNCONFIRMED_PILE_MIN_DOCS:
            _add(
                pid,
                name,
                "money",
                "low",
                weight=pile,
                headline=f"{name}: {pile:,.0f} in unconfirmed quotes",
                detail=(
                    f"{unconfirmed_docs} financial document(s) are quotes "
                    f"not yet marked confirmed. Confirm which ones count so "
                    f"the margin reflects money that actually moved."
                ),
                link=link,
            )

    # --- SCOPE ---------------------------------------------------------------
    # Pending scope-gap proposals: contract scope items with no matching task.
    from project_db.db.models import Proposal as _Proposal
    from project_db.db.models.proposals import ProposalStatus as _PS

    scope_by_proj: dict[Any, int] = {}
    for pr in (
        session.query(_Proposal)
        .filter(_Proposal.field_name == "scope_gap", _Proposal.status == _PS.PENDING)
        .all()
    ):
        scope_by_proj[pr.entity_id] = scope_by_proj.get(pr.entity_id, 0) + 1
    for pid, n in scope_by_proj.items():
        name = _name(pid)
        _add(
            pid,
            name,
            "scope",
            "medium",
            weight=n,
            headline=f"{name}: {n} contract scope item(s) with no task",
            detail=(
                "Work the contract commits to that is not tracked on the "
                "Monday board. Each flagged item carries a quoted excerpt; "
                "review and add a task or dismiss."
            ),
            link=f"/projects/{_ser(pid)}",
        )

    # --- SCHEDULE ------------------------------------------------------------
    # Overdue tasks: a past due date with a not-done, not-cancelled status.
    # This cross-cuts the whole portfolio in one place -- Monday shows it
    # per-board, never ranked across jobs.
    overdue_by_proj: dict[Any, list[Task]] = {}
    for t in (
        session.query(Task)
        .filter(
            Task.due_date.isnot(None),
            Task.due_date < today,
            Task.status.notin_([TaskStatus.DONE, TaskStatus.CANCELLED]),
            Task.project_id.isnot(None),
        )
        .all()
    ):
        overdue_by_proj.setdefault(t.project_id, []).append(t)
    for pid, tasks in overdue_by_proj.items():
        if pid not in proj_by_id:
            continue
        name = _name(pid)
        earliest = min(t.due_date for t in tasks)
        days_over = (today - earliest).days
        n = len(tasks)
        severity = (
            "high" if (n >= _OVERDUE_HIGH_COUNT or days_over >= _OVERDUE_HIGH_DAYS) else "medium"
        )
        example = next((t.title for t in tasks if t.title), None)
        ex = f' e.g. "{example}"' if example else ""
        _add(
            pid,
            name,
            "schedule",
            severity,
            weight=n * 100 + days_over,
            headline=f"{name}: {n} task(s) overdue",
            detail=(
                f"Earliest due {earliest.isoformat()} ({days_over} day(s) "
                f"ago), not marked done.{ex}"
            ),
            link=f"/projects/{_ser(pid)}",
        )

    # --- DOCUMENTS -----------------------------------------------------------
    # Active/proposed projects with no contract-shaped document on file.
    for p in report_missing_documents(session).get("projects", []):
        status = (p.get("status") or "").upper()
        severity = "medium" if status == "ACTIVE" else "low"
        name = p.get("name") or "(unknown project)"
        _add(
            p.get("canonical_id"),
            name,
            "documents",
            severity,
            weight=1.0,
            headline=f"{name}: no contract document on file",
            detail=(
                "No PDF / Google Doc / DOCX is filed under this project in "
                "Drive. The contract may be elsewhere, or the folder match "
                "missed it."
            ),
            link=f"/projects/{p.get('canonical_id')}",
        )

    # --- COMMITMENTS (Money-at-Risk) -----------------------------------------
    # Overdue / due-soon contract obligations: revenue past due to collect, or a
    # payment/deadline we owe. Same deterministic status as report_commitments.
    from project_db.db.models import ContractObligation as _Oblig

    oblig_by_proj: dict[Any, list[Any]] = {}
    for ob in session.query(_Oblig).filter(_Oblig.project_id.isnot(None)).all():
        oblig_by_proj.setdefault(ob.project_id, []).append(ob)

    def _ex(o: Any) -> str:
        return (o.description or o.kind or "obligation").strip()

    for pid, obs in oblig_by_proj.items():
        if pid not in proj_by_id:
            continue
        name = _name(pid)
        link = f"/projects/{_ser(pid)}"
        statuses = [(o, _obligation_status(o, today, _OBLIGATION_DUE_SOON_DAYS)) for o in obs]
        overdue_in = [o for o, s in statuses if s == "overdue" and o.direction == "owed_to_us"]
        overdue_out = [o for o, s in statuses if s == "overdue" and o.direction == "owed_by_us"]
        due_soon = [o for o, s in statuses if s == "due_soon"]

        if overdue_in:
            amt = float(sum((o.amount or 0) for o in overdue_in))
            _add(
                pid,
                name,
                "commitments",
                "high",
                weight=amt or len(overdue_in) * 100,
                headline=(
                    f"{name}: {amt:,.0f} past due to collect"
                    if amt
                    else f"{name}: {len(overdue_in)} overdue receivable(s)"
                ),
                detail=(
                    f"{len(overdue_in)} obligation(s) the client owes us are past "
                    f'due (e.g. "{_ex(overdue_in[0])}"). Revenue at risk if not '
                    f"chased."
                ),
                link=link,
            )
        if overdue_out:
            amt = float(sum((o.amount or 0) for o in overdue_out))
            _add(
                pid,
                name,
                "commitments",
                "high",
                weight=amt or len(overdue_out) * 100,
                headline=f"{name}: {len(overdue_out)} obligation(s) overdue",
                detail=(
                    f"{len(overdue_out)} payment/deadline obligation(s) we owe are "
                    f'past due (e.g. "{_ex(overdue_out[0])}"). Penalty / late '
                    f"exposure."
                ),
                link=link,
            )
        if due_soon:
            amt = float(sum((o.amount or 0) for o in due_soon))
            _add(
                pid,
                name,
                "commitments",
                "medium",
                weight=amt or len(due_soon) * 10,
                headline=f"{name}: {len(due_soon)} obligation(s) due soon",
                detail=(
                    f'Due within {_OBLIGATION_DUE_SOON_DAYS} days (e.g. "{_ex(due_soon[0])}").'
                ),
                link=link,
            )

    # --- RANK + CAP ----------------------------------------------------------
    # Stable two-pass sort: name asc first, then (severity, weight) desc on top,
    # so equal-priority items read alphabetically.
    items.sort(key=lambda it: ((it["project_name"] or "").lower(), it["headline"]))
    items.sort(key=lambda it: (it["severity_rank"], it["weight"]), reverse=True)

    by_category: dict[str, int] = {}
    by_severity: dict[str, int] = {}
    for it in items:
        by_category[it["category"]] = by_category.get(it["category"], 0) + 1
        by_severity[it["severity"]] = by_severity.get(it["severity"], 0) + 1

    shown = items[:limit] if (limit and limit > 0) else items
    project_ids = {it["project_id"] for it in items if it["project_id"]}

    return {
        "generated_on": today.isoformat(),
        "item_count": len(items),
        "project_count": len(project_ids),
        "shown_count": len(shown),
        "truncated": len(items) > len(shown),
        "by_category": by_category,
        "by_severity": by_severity,
        "items": shown,
    }


def report_division_margins(session: Session, project_ref: str) -> dict[str, Any]:
    """Per-(unit, division) margin pivot from the FinancialLineItem ledger.

    Revenue side = own-authored quote rows populated by ``fill-ledger``.
    Cost side    = actual-spend rows (future LLM/job-cost extractor).

    Where only one side is populated the flag column says so explicitly —
    this is by design; the ledger is sparse until cost data arrives.

    Double-count rule: for each ``(unit, division_code, side)`` group,
    the division-total row wins over re-summing its material+labour line items;
    markup/contingency/tax are always included (they are not duplicates).

    Returns ``{"error": "..."}`` when the project_ref doesn't resolve.

    Output shape::

        {
          "project": "<name>",
          "project_id": "<uuid>",
          "total_quoted_revenue": <float|None>,
          "total_actual_cost":    <float|None>,
          "gross_margin":         <float|None>,
          "coverage_note":        "<str>",
          "divisions": [
            {
              "unit":                "<str|None>",
              "division_code":       "<str>",
              "division_name":       "<str>",
              "quoted_revenue":      <float|None>,
              "actual_material_cost":<float|None>,
              "actual_labour_cost":  <float|None>,
              "actual_total_cost":   <float|None>,
              "gross_margin":        <float|None>,
              "gross_margin_pct":    <float|None>,
              "status_flag":         "<flag>",
              "source_docs":         [<str>, ...],
              "warnings":            [<str>, ...],
            },
            ...
          ],
        }

    ``status_flag`` values:
        ``ok``               both sides present
        ``revenue_only``     quote exists, no cost data yet
        ``cost_only``        cost exists, no revenue (unexpected at this stage)
        ``unknown_division`` division_code == '99'
    """
    from collections import defaultdict

    from project_db.db.models.finance import FinancialLineItem

    project = _resolve_project(session, project_ref)
    if project is None:
        return {"error": f"No project matched ref={project_ref!r}"}

    rows: list[FinancialLineItem] = (
        session.query(FinancialLineItem)
        .filter(FinancialLineItem.project_id == project.canonical_id)
        .all()
    )
    if not rows:
        return {
            "project": project.name,
            "project_id": str(project.canonical_id),
            "total_quoted_revenue": None,
            "total_actual_cost": None,
            "gross_margin": None,
            "coverage_note": ("No ledger rows — run 'fill-ledger' to populate quote data."),
            "divisions": [],
        }

    # --- document name lookup for source_docs ---
    _doc_ids = {r.document_id for r in rows if r.document_id}
    doc_names: dict = {}
    if _doc_ids:
        for d in session.query(Document).filter(Document.canonical_id.in_(_doc_ids)).all():
            doc_names[d.canonical_id] = d.name or str(d.canonical_id)

    # --- double-count deduplication per (unit, division_code, side) ----------
    # Standalone amount types are included unconditionally; total rows win over
    # line items within the same (unit, division_code, side) bucket.
    #
    # ``adjustment`` (extras / change-order) is STANDALONE on purpose: an extra
    # is scope agreed AFTER the base quote, so its amount is ADDITIVE to the
    # quote's division total -- it is never a re-statement of the same money.
    # Treating it as a line item would let a quote division-total suppress the
    # extra (it lost the total-vs-items contest), silently dropping real revenue
    # whenever the extras doc shared the quote's unit + division. See
    # ai/extras_grid.py module docstring ("BOTH counted").
    _STANDALONE = {"markup", "contingency", "tax", "deposit", "adjustment", "other"}
    _buckets: dict = defaultdict(lambda: {"total": [], "items": [], "standalone": []})
    for r in rows:
        key = (r.unit, r.division_code, r.side)
        if r.amount_type in _STANDALONE:
            _buckets[key]["standalone"].append(r)
        elif r.amount_type == "total":
            _buckets[key]["total"].append(r)
        else:
            _buckets[key]["items"].append(r)

    effective: list[FinancialLineItem] = []
    for g in _buckets.values():
        effective.extend(g["total"] if g["total"] else g["items"])
        effective.extend(g["standalone"])

    # --- pivot by (unit, division_code) --------------------------------------
    _Decimal = Decimal
    _zero = _Decimal(0)

    pivot: dict = defaultdict(
        lambda: {
            "revenue_rows": [],
            "cost_material": _zero,
            "cost_labour": _zero,
            "cost_other": _zero,
            "doc_ids": set(),
            "warnings": [],
        }
    )
    for r in effective:
        key = (r.unit, r.division_code)
        bucket = pivot[key]
        bucket["doc_ids"].add(r.document_id)
        amount = _Decimal(str(r.amount or 0))
        if r.side == "revenue":
            bucket["revenue_rows"].append(amount)
        elif r.side == "cost":
            if r.amount_type == "material":
                bucket["cost_material"] += amount
            elif r.amount_type == "labour":
                bucket["cost_labour"] += amount
            else:
                bucket["cost_other"] += amount

    # --- build output rows ---------------------------------------------------
    from project_db.ai.financial_divisions import division_by_code

    division_rows: list[dict] = []
    for (unit, div_code), bucket in sorted(
        pivot.items(), key=lambda kv: (kv[0][0] or "", kv[0][1])
    ):
        div = division_by_code(div_code)
        rev_amounts: list[_Decimal] = bucket["revenue_rows"]
        quoted_revenue: _Decimal | None = sum(rev_amounts, _zero) if rev_amounts else None
        mat = bucket["cost_material"] or None
        lab = bucket["cost_labour"] or None
        oth = bucket["cost_other"] or None
        actual_cost: _Decimal | None = None
        if mat is not None or lab is not None or oth is not None:
            actual_cost = (mat or _zero) + (lab or _zero) + (oth or _zero)

        # Gross margin: only when both sides are present.
        gross_margin: _Decimal | None = None
        gross_margin_pct: float | None = None
        if quoted_revenue is not None and actual_cost is not None:
            gross_margin = quoted_revenue - actual_cost
            if quoted_revenue != _zero:
                gross_margin_pct = round(float(gross_margin / quoted_revenue * 100), 1)

        # Status flag.
        if div_code == "99":
            flag = "unknown_division"
        elif quoted_revenue is not None and actual_cost is not None:
            flag = "ok"
        elif quoted_revenue is not None:
            flag = "revenue_only"
        elif actual_cost is not None:
            flag = "cost_only"
        else:
            flag = "unknown_division"

        source_docs = sorted(
            {doc_names.get(did, str(did)) for did in bucket["doc_ids"] if did},
        )

        division_rows.append(
            {
                "unit": unit,
                "division_code": div_code,
                "division_name": div.name,
                "quoted_revenue": float(quoted_revenue) if quoted_revenue is not None else None,
                "actual_material_cost": float(mat) if mat is not None else None,
                "actual_labour_cost": float(lab) if lab is not None else None,
                "actual_total_cost": float(actual_cost) if actual_cost is not None else None,
                "gross_margin": float(gross_margin) if gross_margin is not None else None,
                "gross_margin_pct": gross_margin_pct,
                "status_flag": flag,
                "source_docs": source_docs,
                "warnings": bucket["warnings"],
            }
        )

    total_revenue = (
        sum(
            (r["quoted_revenue"] for r in division_rows if r["quoted_revenue"] is not None),
            0.0,
        )
        or None
    )
    total_cost = (
        sum(
            (r["actual_total_cost"] for r in division_rows if r["actual_total_cost"] is not None),
            0.0,
        )
        or None
    )
    gross_total = (
        (total_revenue or 0.0) - (total_cost or 0.0)
        if total_revenue is not None and total_cost is not None
        else None
    )

    revenue_only_count = sum(1 for r in division_rows if r["status_flag"] == "revenue_only")
    coverage_note = (
        f"{revenue_only_count} division(s) have revenue-only data — "
        "cost data pending job-cost extractor (Phase 1c)."
        if revenue_only_count
        else "Both sides populated."
    )

    return {
        "project": project.name,
        "project_id": str(project.canonical_id),
        "total_quoted_revenue": total_revenue,
        "total_actual_cost": total_cost,
        "gross_margin": gross_total,
        "coverage_note": coverage_note,
        "divisions": division_rows,
    }


# Document extensions that imply an unstructured (non-grid) financial doc -- a
# quote/extras-named file with no parseable Material/Total grid is a PDF/Word
# quote (needs the future LLM extractor), not a single-column simple estimate.
_PDF_LIKE_EXTS = {".pdf", ".doc", ".docx"}

# Non-textual image formats: empty extracted_text is EXPECTED (a photo), so the
# action is "safe skip", NOT "re-run extract-content".
_PHOTO_EXTS = {
    ".jpg",
    ".jpeg",
    ".png",
    ".webp",
    ".gif",
    ".jfif",
    ".heic",
    ".heif",
    ".bmp",
    ".tif",
    ".tiff",
}


def _recommended_action(doc_name: str, result, *, has_text: bool) -> str:
    """Deterministic Phase-1d action code for one document. NO LLM.

    Maps a ``DocLedgerResult`` (plus whether the document had extracted text and
    its file extension) to one of the recommended_action codes in
    ``docs/FINANCIAL_REDESIGN.md §9``. Pure function; never raises.
    """
    import os

    if not has_text:
        return "empty_extraction"

    status = result.ingestion_status
    if status == "parsed":
        return "review_reconcile_fail" if result.reconcile_ok is False else "ok"
    if status == "failed":
        return "review_parse_error"

    # status == "skipped" / "quarantined"
    ctype = result.sheet_type
    reason = result.ingestion_reason
    ext = os.path.splitext(doc_name or "")[1].lower()

    if ctype in ("quote", "extras") and reason == "no_header":
        # Financial-looking, but no Material/Total grid was found.
        return "unsupported_pdf_quote" if ext in _PDF_LIKE_EXTS else "unsupported_simple_estimate"
    if ctype == "job_cost":
        return "unsupported_job_cost"
    # order_quantities, unknown, no_money, or anything else correctly set aside.
    return "safe_nonfinancial_skip"


def report_ledger_health(session: Session, project_ref: str) -> dict[str, Any]:
    """Phase 1d audit: per-document explanation of what fill-ledger did and why.

    Answers "why is Project X showing only $66k when I have four quote docs?" by
    replaying the populator over every text-bearing document in the project and
    reporting, per document: how it was classified, whether rows landed, whether
    it reconciled, and a deterministic ``recommended_action`` (no LLM).

    Side effect: this re-runs ``populate_ledger_for_document`` (idempotent
    delete+insert), so it also refreshes the ledger exactly like ``fill-ledger``.
    Documents whose ``DocumentText.extracted_text`` is empty are reported as
    ``empty_extraction`` without being parsed.

    Returns ``{"error": "..."}`` when the project_ref doesn't resolve.
    """
    from project_db.ai.financial_grid_populator import populate_ledger_for_document
    from project_db.db.models.docs import DocumentText
    from project_db.db.models.finance import FinancialLineItem  # noqa: F401 (parity import)

    project = _resolve_project(session, project_ref)
    if project is None:
        return {"error": f"No project matched ref={project_ref!r}"}

    pairs = (
        session.query(Document, DocumentText)
        .join(DocumentText, DocumentText.document_id == Document.canonical_id)
        .filter(
            Document.project_id == project.canonical_id,
            Document.is_trashed.is_(False),
        )
        .all()
    )

    documents: list[dict[str, Any]] = []
    for document, doc_text in pairs:
        has_text = bool((doc_text.extracted_text or "").strip())

        if not has_text:
            import os

            ext = os.path.splitext(document.name or "")[1].lower()
            # A photo with no text is expected (safe skip); a textual doc with
            # no text means extract-content didn't run / failed (re-run it).
            if ext in _PHOTO_EXTS:
                reason, action = "non_textual_image", "safe_nonfinancial_skip"
            else:
                reason, action = "empty_extraction", "empty_extraction"
            documents.append(
                {
                    "document": document.name or str(document.canonical_id),
                    "classified_type": "unknown",
                    "ingestion_status": "skipped",
                    "ingestion_reason": reason,
                    "rows_written": 0,
                    "reconcile_ok": None,
                    "division_total": None,
                    "stated_total": None,
                    "difference": None,
                    "recommended_action": action,
                }
            )
            continue

        result = populate_ledger_for_document(session, document, doc_text)
        stated = result.grand_total
        divtot = result.division_total
        difference = None
        if stated is not None and divtot is not None:
            difference = float(Decimal(str(stated)) - Decimal(str(divtot)))

        documents.append(
            {
                "document": document.name or str(document.canonical_id),
                "classified_type": result.sheet_type,
                "ingestion_status": result.ingestion_status,
                "ingestion_reason": result.ingestion_reason,
                "rows_written": result.rows_written,
                "reconcile_ok": result.reconcile_ok,
                "division_total": float(divtot) if divtot is not None else None,
                "stated_total": float(stated) if stated is not None else None,
                "difference": difference,
                "recommended_action": _recommended_action(
                    document.name or "", result, has_text=True
                ),
            }
        )

    session.commit()

    # Sort: things needing attention first, then OK, then safe skips -- so a PM
    # reads the actionable rows at the top.
    _ACTION_RANK = {
        "review_parse_error": 0,
        "review_reconcile_fail": 1,
        "unsupported_pdf_quote": 2,
        "unsupported_simple_estimate": 3,
        "unsupported_job_cost": 4,
        "empty_extraction": 5,
        "ok": 6,
        "safe_nonfinancial_skip": 7,
    }
    documents.sort(
        key=lambda d: (_ACTION_RANK.get(d["recommended_action"], 9), d["document"].lower())
    )

    counts: dict[str, int] = {}
    for d in documents:
        counts[d["recommended_action"]] = counts.get(d["recommended_action"], 0) + 1

    total_rows = sum(d["rows_written"] for d in documents)
    parsed = sum(1 for d in documents if d["ingestion_status"] == "parsed")
    needs_review = sum(
        1
        for d in documents
        if d["recommended_action"] in ("review_parse_error", "review_reconcile_fail")
    )
    unsupported = sum(1 for d in documents if d["recommended_action"].startswith("unsupported_"))

    return {
        "project": project.name,
        "project_id": str(project.canonical_id),
        "document_count": len(documents),
        "parsed_count": parsed,
        "rows_written": total_rows,
        "needs_review_count": needs_review,
        "unsupported_count": unsupported,
        "action_counts": counts,
        "documents": documents,
    }


def report_project_log_hours(session: Session, project_ref: str) -> dict[str, Any]:
    """Deterministic labour rollup from ProjectLogEntry rows (no LLM).

    Groups hours by employee -- resolved Workers are grouped by worker; unresolved
    handwritten names are grouped by their raw text (so the report is useful both
    before and after name resolution). Also lists each submission's status so a
    PM can see what was parsed/quarantined/skipped.

    Returns ``{"error": "..."}`` when the project_ref doesn't resolve.
    """
    from collections import defaultdict

    from project_db.db.models.project_log import ProjectLogEntry, ProjectLogSubmission

    project = _resolve_project(session, project_ref)
    if project is None:
        return {"error": f"No project matched ref={project_ref!r}"}

    entries: list[ProjectLogEntry] = (
        session.query(ProjectLogEntry)
        .filter(ProjectLogEntry.project_id == project.canonical_id)
        .all()
    )
    submissions: list[ProjectLogSubmission] = (
        session.query(ProjectLogSubmission)
        .filter(ProjectLogSubmission.project_id == project.canonical_id)
        .all()
    )

    _zero = Decimal(0)
    groups: dict[tuple, dict[str, Any]] = defaultdict(
        lambda: {
            "employee_id": None,
            "name": None,
            "resolved": False,
            "entries": 0,
            "dates": set(),
            "reported": _zero,
            "has_reported": False,
            "computed": _zero,
            "has_computed": False,
            "mismatches": 0,
        }
    )

    total_reported = _zero
    total_computed = _zero
    mismatch_count = 0
    unresolved_entries = 0

    for e in entries:
        if e.employee_id is not None:
            key = ("worker", str(e.employee_id))
        else:
            key = ("raw", (e.employee_name_raw or "(unnamed)").strip().lower())
        g = groups[key]
        g["entries"] += 1
        if e.employee_id is not None:
            g["employee_id"] = str(e.employee_id)
            g["resolved"] = True
        if g["name"] is None:
            g["name"] = e.employee_name_raw or "(unnamed)"
        if e.work_date is not None:
            g["dates"].add(e.work_date)
        if e.total_hours_reported is not None:
            amt = Decimal(str(e.total_hours_reported))
            g["reported"] += amt
            g["has_reported"] = True
            total_reported += amt
        if e.total_hours_computed is not None:
            amt = Decimal(str(e.total_hours_computed))
            g["computed"] += amt
            g["has_computed"] = True
            total_computed += amt
        if e.hours_mismatch:
            g["mismatches"] += 1
            mismatch_count += 1
        if e.employee_id is None:
            unresolved_entries += 1

    employees: list[dict[str, Any]] = []
    for g in groups.values():
        dates = sorted(g["dates"])
        employees.append(
            {
                "employee_id": g["employee_id"],
                "name": g["name"],
                "resolved": g["resolved"],
                "entries": g["entries"],
                "days": len(dates),
                "reported_hours": float(g["reported"]) if g["has_reported"] else None,
                "computed_hours": float(g["computed"]) if g["has_computed"] else None,
                "mismatches": g["mismatches"],
                "first_seen": dates[0].isoformat() if dates else None,
                "last_seen": dates[-1].isoformat() if dates else None,
            }
        )
    # Most hours first; unresolved/None hours sink to the bottom.
    employees.sort(key=lambda r: (r["reported_hours"] is None, -(r["reported_hours"] or 0.0)))

    submission_rows = sorted(
        (
            {
                "document": s.source_attachment_filename or str(s.canonical_id),
                "status": s.ingestion_status,
                "reason": s.ingestion_reason,
                "site_raw": s.site_name_raw,
                "site_resolved": s.site_name_resolved,
                "received_at": s.received_at.isoformat() if s.received_at else None,
                "classification_confidence": s.classification_confidence,
            }
            for s in submissions
        ),
        key=lambda d: d["received_at"] or "",
    )

    return {
        "project": project.name,
        "project_id": str(project.canonical_id),
        "submission_count": len(submissions),
        "entry_count": len(entries),
        "total_reported_hours": float(total_reported) if entries else None,
        "total_computed_hours": float(total_computed) if entries else None,
        "mismatch_count": mismatch_count,
        "unresolved_entry_count": unresolved_entries,
        "employees": employees,
        "submissions": submission_rows,
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
    "project_financials": report_project_financials,
    "division_margins": report_division_margins,
}
