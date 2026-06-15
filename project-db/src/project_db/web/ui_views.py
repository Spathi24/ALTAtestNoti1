"""Service module for the UI.

Every derived value rendered by the UI is computed here, *not* in templates
and *not* inline in routes.  Templates receive plain dicts / lists; routes
just glue request -> service -> template.

Rule of thumb: if you find yourself writing ``{% if proposals|length > 0 %}``
followed by a calculation in a template, the calculation belongs here.
"""
from __future__ import annotations

import json
from typing import Any

from sqlalchemy import func
from sqlalchemy.orm import Session

from uuid import UUID

from project_db.ai.proposals import get_proposal_detail, list_proposals
from project_db.ai.views import report_project_financials
from project_db.db.models import (
    Client,
    Deal,
    Document,
    ExternalId,
    Lead,
    Project,
    Proposal,
    Task,
)
from project_db.db.models.docs import DocumentText
from project_db.db.models.proposals import ProposalStatus
from project_db.db.models.work import ProjectStatus


def project_financials(session: Session, project_id: str) -> dict[str, Any] | None:
    """Financial reconciliation for one project (read-only).

    Thin pass-through to the canonical ``report_project_financials`` so the CLI
    and the web panel render the exact same numbers.  Returns None when the
    project doesn't resolve (route renders a 404).
    """
    rep = report_project_financials(session, project_id)
    if isinstance(rep, dict) and rep.get("error"):
        return None
    return rep


def attention_briefing(session: Session, *, limit: int = 25) -> dict[str, Any]:
    """Portfolio attention briefing for the landing page.

    Thin pass-through to ``ai.views.report_attention_briefing`` so the web `/`
    landing and the ``project_db briefing`` CLI render identical data.  Pure
    read, deterministic, no LLM -- safe to recompute on every request.
    """
    from project_db.ai.views import report_attention_briefing

    return report_attention_briefing(session, limit=limit)


def submit_field_note(
    session: Session,
    project_id: str,
    note_text: str,
) -> dict[str, Any]:
    """Ingest a field note from the web UI (A5: same service path as the CLI).

    Returns a dict with keys:
      ok         bool
      summary    one-line result string
      proposals  list of {field_name, entity_type, proposal_id} for created proposals
      errors     list of warning strings
    """
    from project_db.ai.field_note_extraction import (
        FieldNoteExtractorError,
        NoteChannel,
        OpenAIFieldNoteExtractor,
        ingest_field_note,
    )

    if not note_text or not note_text.strip():
        return {"ok": False, "summary": "Empty note -- nothing to process.", "proposals": [], "errors": []}

    try:
        extractor = OpenAIFieldNoteExtractor()
    except FieldNoteExtractorError as exc:
        return {"ok": False, "summary": f"Extractor unavailable: {exc}", "proposals": [], "errors": [str(exc)]}

    # Same RAG evidence base the generate-proposals path uses (optional --
    # None if no embedding provider is configured).
    try:
        from project_db.ai.embeddings import get_optional_embedding_provider
        embed_provider = get_optional_embedding_provider()
    except Exception:  # noqa: BLE001
        embed_provider = None

    batch = ingest_field_note(
        session, extractor, project_id, note_text.strip(),
        channel=NoteChannel.WEB,
        embedding_provider=embed_provider,
    )

    proposals_out = [
        {"field_name": p.field_name, "entity_type": p.entity_type,
         "proposal_id": str(p.canonical_id)}
        for p in batch.proposals
    ]
    return {
        "ok": True,
        "summary": batch.summary(),
        "proposals": proposals_out,
        "errors": batch.errors,
    }


def value_caught(session: Session) -> dict[str, Any]:
    """ROI scoreboard for the landing page (INTENTIONS #2).

    Thin pass-through to ``ai.views.report_value_caught`` so the web `/` card and
    the ``project_db value-caught`` CLI render identical numbers.  Pure read,
    deterministic, no LLM -- safe to recompute on every request.
    """
    from project_db.ai.views import report_value_caught

    return report_value_caught(session)


def money_glossary() -> dict[str, Any]:
    """Plain-language explanation of the project's money numbers.

    The single source of this copy (rendered by the project page AND the
    Financials panel) so the story can't drift. ``authority`` drives the visual
    weight: ``authoritative`` is the one to trust; ``reference`` and ``rough``
    are weaker cross-checks we keep on screen, clearly labelled, rather than
    hide. Pure -- no DB, no I/O.
    """
    return {
        "sources": [
            {
                "label": "Reconciled money picture (this Financials panel)",
                "authority": "authoritative",
                "blurb": (
                    "Built from the project's ACTUAL quotes, invoices, and "
                    "receipts in Drive. It separates money coming IN from the "
                    "client from money going OUT to suppliers and subs, and "
                    "shows the margin between them. This is the number to "
                    "trust -- it comes from the real documents, flags how "
                    "confident it is, and leaves out duplicate tracking sheets."
                ),
            },
            {
                "label": "Monday budget / contract value",
                "authority": "reference",
                "blurb": (
                    "A single figure a person typed into the Monday board's "
                    "Budget/Contract column. It is a planning target, only as "
                    "current as the last time someone updated it by hand -- it "
                    "is NOT read from the documents. Use it as a sanity check: "
                    "if it disagrees with the reconciled picture, the board is "
                    "probably stale or the job is drifting from its budget."
                ),
            },
            {
                "label": "Contract-text estimate",
                "authority": "rough",
                "blurb": (
                    "The largest dollar amount a simple text scan found in the "
                    "contract files. A crude first-pass guess from before the "
                    "document-reading layer existed, kept only as a loose "
                    "cross-reference. If it disagrees with the reconciled "
                    "picture, trust the reconciled picture."
                ),
            },
        ],
        # The money-type buckets inside the reconciled picture, in plain words.
        "money_types": [
            {"key": "contract_revenue",
             "blurb": "Money the client pays you -- what you invoice or quote them."},
            {"key": "supplier_cost",
             "blurb": "Money you pay suppliers and subcontractors (materials, labour)."},
            {"key": "buyout_cost",
             "blurb": "What you pay to buy out / relocate a tenant (agency projects)."},
            {"key": "lease_rental",
             "blurb": "Rent or lease payments."},
            {"key": "deposit",
             "blurb": "An upfront deposit."},
            {"key": "tax",
             "blurb": "Sales tax (GST/QST/TPS/TVQ), kept separate so it isn't double-counted."},
            {"key": "other",
             "blurb": "Money that couldn't be confidently sorted. A lot here means the "
                      "picture is low-confidence -- treat the margin with caution."},
        ],
    }


def search_documents(
    session: Session,
    query: str,
    *,
    project_ref: str | None = None,
    top_k: int = 20,
) -> dict[str, Any]:
    """Hybrid (semantic + keyword) search over embedded document chunks.

    Read-only -- no LLM, just retrieval -- so it's the cheapest way to find
    the exact clause/number/name across the corpus. Degrades gracefully: an
    empty query, an un-embedded corpus, or a missing key each return a clear
    ``error`` rather than raising.
    """
    from project_db.ai.rag import embedding_coverage

    query = (query or "").strip()
    out: dict[str, Any] = {
        "query": query, "results": [], "error": None, "project": None,
        "coverage": embedding_coverage(session),
    }
    out["embedded"] = out["coverage"]["chunks"] > 0

    if not query:
        return out
    if not out["embedded"]:
        out["error"] = ("No documents are embedded yet. Run "
                        "`project_db embed-documents` first.")
        return out

    from project_db.ai.embeddings import get_optional_embedding_provider

    provider = get_optional_embedding_provider()
    if provider is None:
        out["error"] = "No embedding provider configured (set OPENAI_API_KEY)."
        return out

    project_id = None
    if project_ref:
        from project_db.ai.views import _resolve_project

        proj = _resolve_project(session, project_ref)
        if proj is not None:
            project_id = proj.canonical_id
            out["project"] = {"canonical_id": str(proj.canonical_id), "name": proj.name}

    from project_db.ai.rag import retrieve_chunks

    try:
        out["results"] = retrieve_chunks(
            session, provider, query, project_id=project_id, top_k=top_k,
        )
    except Exception as exc:  # noqa: BLE001 -- surface, don't 500
        out["error"] = f"Search failed: {exc}"
    return out


def dashboard_summary(session: Session) -> dict[str, Any]:
    """Counts and recent activity for the dashboard.

    Pure read.  Cheap aggregation queries -- no per-row Python loops; the
    DB does the grouping.  Returns JSON-serializable values throughout
    (Enum -> .value, no SQLAlchemy ORM objects).
    """
    project_status_counts = dict(
        session.query(Project.status, func.count(Project.canonical_id))
        .group_by(Project.status)
        .all()
    )
    projects_total = session.query(func.count(Project.canonical_id)).scalar() or 0
    projects = {
        "total": int(projects_total),
        "by_status": {
            (k.value if hasattr(k, "value") else str(k)): int(v)
            for k, v in project_status_counts.items()
            if k is not None
        },
    }

    total_tasks = session.query(func.count(Task.canonical_id)).scalar() or 0
    dateless_tasks = (
        session.query(func.count(Task.canonical_id))
        .filter(Task.start_date.is_(None))
        .filter(Task.end_date.is_(None))
        .filter(Task.due_date.is_(None))
        .scalar()
        or 0
    )
    tasks = {
        "total": int(total_tasks),
        "without_dates": int(dateless_tasks),
    }

    total_docs = (
        session.query(func.count(Document.canonical_id))
        .filter(Document.is_trashed.is_(False))
        .scalar()
        or 0
    )
    docs_with_text = (
        session.query(func.count(DocumentText.document_id))
        .join(Document, DocumentText.document_id == Document.canonical_id)
        .filter(Document.is_trashed.is_(False))
        .filter(DocumentText.extracted_text.isnot(None))
        .filter(func.length(DocumentText.extracted_text) > 0)
        .scalar()
        or 0
    )
    documents = {
        "total": int(total_docs),
        "with_text": int(docs_with_text),
    }

    proposal_status_counts = dict(
        session.query(Proposal.status, func.count(Proposal.canonical_id))
        .group_by(Proposal.status)
        .all()
    )
    proposals = {
        s.value: int(proposal_status_counts.get(s, 0)) for s in ProposalStatus
    }
    proposals["total"] = sum(proposals.values())

    deals_total = session.query(func.count(Deal.canonical_id)).scalar() or 0
    leads_total = session.query(func.count(Lead.canonical_id)).scalar() or 0

    return {
        "projects": projects,
        "tasks": tasks,
        "documents": documents,
        "proposals": proposals,
        "deals": int(deals_total),
        "leads": int(leads_total),
    }


def recent_pending_proposals(
    session: Session, *, limit: int = 10
) -> list[dict[str, Any]]:
    """Top N newest PENDING proposals for the dashboard strip.

    Delegates to ``ai.proposals.list_proposals`` so the UI sees exactly what
    ``project_db proposals list`` sees.  No re-derivation.
    """
    return list_proposals(session, status=ProposalStatus.PENDING, limit=limit)


def _status_active_set() -> set[ProjectStatus]:
    """Statuses we treat as 'live' for the project list default filter."""
    return {ProjectStatus.PROPOSED, ProjectStatus.ACTIVE, ProjectStatus.ON_HOLD}


# ---------------------------------------------------------------------------
# Project list -- /projects
# ---------------------------------------------------------------------------


def project_list_rows(session: Session) -> list[dict[str, Any]]:
    """Every project, with rolled-up counts and a pending-proposal tally.

    One row per project, ordered by name.  No N+1 -- counts are grouped
    queries.
    """
    projects = session.query(Project).order_by(Project.name).all()

    tasks_by_project: dict[Any, int] = dict(
        session.query(Task.project_id, func.count(Task.canonical_id))
        .group_by(Task.project_id)
        .all()
    )
    docs_by_project: dict[Any, int] = dict(
        session.query(Document.project_id, func.count(Document.canonical_id))
        .filter(Document.is_trashed.is_(False))
        .group_by(Document.project_id)
        .all()
    )
    dateless_by_project: dict[Any, int] = dict(
        session.query(Task.project_id, func.count(Task.canonical_id))
        .filter(
            Task.start_date.is_(None),
            Task.end_date.is_(None),
            Task.due_date.is_(None),
        )
        .group_by(Task.project_id)
        .all()
    )

    clients = {c.canonical_id: c.name for c in session.query(Client).all()}

    out: list[dict[str, Any]] = []
    for p in projects:
        pending = (
            session.query(func.count(Proposal.canonical_id))
            .join(Task, Task.canonical_id == Proposal.entity_id)
            .filter(
                Proposal.entity_type == "Task",
                Proposal.status == ProposalStatus.PENDING,
                Task.project_id == p.canonical_id,
            )
            .scalar()
            or 0
        )
        out.append({
            "canonical_id": str(p.canonical_id),
            "name": p.name,
            "status": p.status.value if hasattr(p.status, "value") else str(p.status),
            "client": clients.get(p.client_id),
            "task_count": int(tasks_by_project.get(p.canonical_id, 0)),
            "tasks_dateless": int(dateless_by_project.get(p.canonical_id, 0)),
            "doc_count": int(docs_by_project.get(p.canonical_id, 0)),
            "pending_proposals": int(pending),
        })
    return out


# ---------------------------------------------------------------------------
# Project detail -- /projects/{id}
# ---------------------------------------------------------------------------


def _coerce_uuid(value: str) -> UUID | None:
    try:
        return UUID(value)
    except (ValueError, AttributeError, TypeError):
        return None


def project_detail(session: Session, project_id: str) -> dict[str, Any] | None:
    """Assemble the data the project-detail template renders.

    Returns ``None`` when the project_id doesn't resolve, so the route
    can return a 404 cleanly.

    Delegates to existing canned reports for every panel; the only new
    work is gathering them in one place + adding the proposals strip.
    """
    from project_db.ai.views import (
        report_budget_vs_contract,
        report_docs_for_project,
        report_project_money_line,
        report_project_overview,
        report_tasks_without_dates,
    )

    pid = _coerce_uuid(project_id)
    if pid is None:
        return None
    project = session.query(Project).filter_by(canonical_id=pid).one_or_none()
    if project is None:
        return None

    ref = str(pid)
    overview = report_project_overview(session, ref)
    docs = report_docs_for_project(session, ref)
    dateless = report_tasks_without_dates(session, ref)
    budget = report_budget_vs_contract(session, ref)
    money_line = report_project_money_line(session, ref)

    # Combined task list with EVERY date column populated, so the project
    # page can show "what's dated, what isn't, what dates were set" in one
    # table.  The reason this is here and not in report_project_overview:
    # that report caps tasks at 50 + omits monday_status_label; this list
    # is uncapped and dateless-first-sorted for the UI's edit-in-place flow.
    from project_db.db.models.work import Task as _Task  # local: avoid shadowing
    all_tasks_q = (
        session.query(_Task)
        .filter(_Task.project_id == pid)
        .order_by(_Task.title)
        .all()
    )
    def _row(t: _Task) -> dict[str, Any]:
        is_dateless = (
            t.start_date is None and t.end_date is None and t.due_date is None
        )
        return {
            "canonical_id": str(t.canonical_id),
            "title": t.title,
            "status": t.status.value if hasattr(t.status, "value") else str(t.status),
            "monday_status_label": t.monday_status_label,
            "start_date": t.start_date.isoformat() if t.start_date else None,
            "end_date": t.end_date.isoformat() if t.end_date else None,
            "due_date": t.due_date.isoformat() if t.due_date else None,
            "is_subitem": bool(t.is_subitem),
            "is_dateless": is_dateless,
        }
    # Dateless first (so they don't get lost), then by title.  The user
    # explicitly asked for visibility of which tasks are dateless and
    # what dates the dated ones have.
    all_tasks_full = sorted(
        (_row(t) for t in all_tasks_q),
        key=lambda r: (not r["is_dateless"], r["title"] or ""),
    )

    # Proposals scoped to this project's tasks.  Same data shape as
    # /proposals -- list_proposals returns enrichment via _enrich_target.
    task_ids = {
        row[0] for row in
        session.query(Task.canonical_id).filter(Task.project_id == pid).all()
    }
    proposals_for_project: list[dict[str, Any]] = []
    for p in list_proposals(session, limit=500):
        try:
            if UUID(p["entity_label"]) in task_ids:
                proposals_for_project.append(p)
                continue
        except (ValueError, AttributeError, TypeError):
            pass
        if p.get("project_name") == project.name:
            proposals_for_project.append(p)

    by_status: dict[str, list[dict[str, Any]]] = {
        s.value: [] for s in ProposalStatus
    }
    for p in proposals_for_project:
        by_status.setdefault(p["status"], []).append(p)

    # Group docs by folder_path for the documents panel.  Pure presentation
    # grouping over what report_docs_for_project already returned.
    by_folder: dict[str, list[dict[str, Any]]] = {}
    for d in docs.get("documents", []):
        by_folder.setdefault(d.get("folder_path") or "(no folder)", []).append(d)

    # Attach extraction status per doc by joining DocumentText.
    if docs.get("documents"):
        doc_ids = [UUID(d["canonical_id"]) for d in docs["documents"]]
        text_rows = dict(
            session.query(
                DocumentText.document_id,
                func.length(DocumentText.extracted_text),
            )
            .filter(DocumentText.document_id.in_(doc_ids))
            .all()
        )
        for d in docs["documents"]:
            text_len = text_rows.get(UUID(d["canonical_id"]))
            d["extraction_status"] = (
                "text" if (text_len or 0) > 0 else
                ("empty" if text_len == 0 else "none")
            )
            d["text_chars"] = int(text_len or 0)

    return {
        "project": overview.get("project") or {
            "canonical_id": str(pid),
            "name": project.name,
        },
        "client": overview.get("client"),
        "stats": overview.get("stats", {}),
        "external_ids": overview.get("external_ids", []),
        # `tasks_full` is the combined dated+dateless table the UI renders.
        # The legacy `tasks` / `dateless_tasks` keys stay for any consumer
        # that still uses them.
        "tasks_full": all_tasks_full,
        "tasks": overview.get("tasks", []),
        "dateless_tasks": dateless.get("tasks", []),
        "dateless_count": dateless.get("task_count", 0),
        "documents_by_folder": by_folder,
        "documents_total": docs.get("document_count", 0),
        "budget": budget,
        "money_line": money_line,
        "proposals_by_status": by_status,
        "proposals_total": len(proposals_for_project),
    }


# ---------------------------------------------------------------------------
# Document detail -- /documents/{id}
# ---------------------------------------------------------------------------


def document_detail(session: Session, document_id: str) -> dict[str, Any] | None:
    """Document metadata + extracted text + proposals that cite it."""
    did = _coerce_uuid(document_id)
    if did is None:
        return None
    doc = session.query(Document).filter_by(canonical_id=did).one_or_none()
    if doc is None:
        return None

    text_row = (
        session.query(DocumentText)
        .filter(DocumentText.document_id == did)
        .one_or_none()
    )

    project = None
    if doc.project_id:
        p = session.query(Project).filter_by(canonical_id=doc.project_id).one_or_none()
        if p:
            project = {"canonical_id": str(p.canonical_id), "name": p.name}

    # Proposals that cite this document in source_doc_ids.  Stored as a
    # JSON string on Proposal; cheap to scan because there are not many.
    citing: list[dict[str, Any]] = []
    for prop in (
        session.query(Proposal)
        .order_by(Proposal.created_at.desc())
        .limit(500)
        .all()
    ):
        if not prop.source_doc_ids:
            continue
        try:
            ids = json.loads(prop.source_doc_ids)
        except (json.JSONDecodeError, TypeError):
            continue
        if not isinstance(ids, list):
            continue
        if str(did) in [str(x) for x in ids]:
            citing.append({
                "proposal_id": str(prop.canonical_id),
                "field_name": prop.field_name,
                "status": prop.status.value if hasattr(prop.status, "value") else str(prop.status),
                "created_at": prop.created_at.isoformat() if prop.created_at else None,
                "confidence": prop.confidence,
            })

    return {
        "document": {
            "canonical_id": str(doc.canonical_id),
            "name": doc.name,
            "mime_type": doc.mime_type,
            "url": doc.url,
            "folder_path": doc.folder_path,
            "size_bytes": doc.size_bytes,
            "modified_at_source": doc.modified_at_source.isoformat()
                if doc.modified_at_source else None,
            "owner_email": doc.owner_email,
            "is_trashed": bool(doc.is_trashed),
            "category": doc.category,
            "drive_id": doc.drive_id,
            "md5_checksum": doc.md5_checksum,
        },
        "project": project,
        "text": {
            "method": getattr(text_row, "extraction_method", None) if text_row else None,
            "token_count": getattr(text_row, "token_count", None) if text_row else None,
            "extracted_at": text_row.extracted_at.isoformat()
                if text_row and text_row.extracted_at else None,
            "char_count": len(text_row.extracted_text or "") if text_row else 0,
            "body": (text_row.extracted_text or "") if text_row else "",
        } if text_row else None,
        "citing_proposals": citing,
    }


# ---------------------------------------------------------------------------
# Proposal queue + detail -- /proposals and /proposals/{id}
# ---------------------------------------------------------------------------


def proposal_queue(
    session: Session,
    *,
    status: str | None = None,
    kind: str | None = None,
    limit: int = 200,
) -> dict[str, Any]:
    """Filtered proposal list for /proposals.

    Thin wrapper over ai.proposals.list_proposals so the UI sees the same
    data the CLI sees.  Validates status filter input here so a malformed
    status from a URL query just produces an empty result and a hint,
    rather than a 500.
    """
    status_enum: ProposalStatus | None = None
    if status:
        try:
            status_enum = ProposalStatus(status.upper())
        except ValueError:
            return {
                "error": f"Unknown status {status!r}. "
                         f"Valid: {[s.value for s in ProposalStatus]}",
                "rows": [],
                "filters": {"status": status, "kind": kind},
            }
    rows = list_proposals(session, status=status_enum, kind=kind, limit=limit)
    return {
        "error": None,
        "rows": rows,
        "filters": {
            "status": status_enum.value if status_enum else None,
            "kind": kind,
        },
        "total": len(rows),
    }


def proposal_detail(session: Session, proposal_id: str) -> dict[str, Any] | None:
    """Full proposal detail for /proposals/{id}.

    Delegates to ``ai.proposals.get_proposal_detail`` so the page renders
    exactly what the CLI's ``proposals show`` renders.  Returns None when
    the id doesn't resolve so the route can 404 cleanly.

    Adds presentation-only fields:
      - ``can_accept``: False for scope_gap (not in _ACCEPTABLE_FIELDS) --
        the route still lets reject through, but disables the Accept
        button in the template.  Source of truth is the backend's
        _ACCEPTABLE_FIELDS set; UI just mirrors it.
      - ``supersede_chain``: prior proposals for the same
        (entity_type, entity_id, field_name).
    """
    pid = _coerce_uuid(proposal_id)
    if pid is None:
        return None

    detail = get_proposal_detail(session, pid)
    if detail is None or detail.get("error"):
        return None

    proposal = session.query(Proposal).filter_by(canonical_id=pid).one_or_none()
    if proposal is None:
        return None

    from project_db.ai.proposals import _ACCEPTABLE_FIELDS  # noqa: PLC2701
    detail["can_accept"] = proposal.field_name in _ACCEPTABLE_FIELDS

    chain_rows = (
        session.query(Proposal)
        .filter(
            Proposal.entity_type == proposal.entity_type,
            Proposal.entity_id == proposal.entity_id,
            Proposal.field_name == proposal.field_name,
            Proposal.canonical_id != proposal.canonical_id,
        )
        .order_by(Proposal.created_at.desc())
        .limit(20)
        .all()
    )
    detail["supersede_chain"] = [
        {
            "proposal_id": str(r.canonical_id),
            "status": r.status.value if hasattr(r.status, "value") else str(r.status),
            "created_at": r.created_at.isoformat() if r.created_at else None,
            "confidence": r.confidence,
        }
        for r in chain_rows
    ]
    return detail


# ---------------------------------------------------------------------------
# Doctor -- /doctor
# ---------------------------------------------------------------------------


def doctor_report(session: Session) -> dict[str, Any]:
    """Thin pass-through to ai.views.report_doctor.

    Lives here so the route only imports from ``ui_views`` -- one rule
    for everywhere.
    """
    from project_db.ai.views import report_doctor
    return report_doctor(session)


# ---------------------------------------------------------------------------
# DB inspector -- /db and /db/{table}
# ---------------------------------------------------------------------------


def db_table_index(session: Session) -> list[dict[str, Any]]:
    """List every SQLAlchemy table with a row count.

    Reflective: walks ``Base.metadata.tables`` so new tables added
    later show up automatically without a code change here.  Tables
    are sorted alphabetically for predictability.
    """
    from project_db.db.base import Base

    rows: list[dict[str, Any]] = []
    for name in sorted(Base.metadata.tables.keys()):
        table = Base.metadata.tables[name]
        try:
            count = session.execute(table.count()).scalar() or 0
        except Exception:  # noqa: BLE001
            # SQLAlchemy 2.x: table.count() may not exist; fall back
            # to a raw COUNT(*).
            from sqlalchemy import func, select
            try:
                count = session.execute(
                    select(func.count()).select_from(table)
                ).scalar() or 0
            except Exception:  # noqa: BLE001
                count = -1
        rows.append({"name": name, "row_count": int(count)})
    return rows


def db_table_rows(
    session: Session,
    table_name: str,
    *,
    limit: int = 100,
) -> dict[str, Any] | None:
    """Top-N rows for one table, JSON-serializable.

    Returns ``None`` when the table doesn't exist so the route can 404.

    Read-only by design.  This is a dev affordance -- DB Browser for
    SQLite covers any "I need to query / edit" use case.  Per the M5
    plan review #4, this endpoint stays small and ugly.
    """
    from project_db.db.base import Base

    if table_name not in Base.metadata.tables:
        return None

    table = Base.metadata.tables[table_name]
    columns = [c.name for c in table.columns]

    from sqlalchemy import select
    result = session.execute(select(table).limit(limit)).fetchall()

    rows: list[dict[str, Any]] = []
    for r in result:
        row: dict[str, Any] = {}
        for col, val in zip(columns, r):
            # Coerce to JSON-friendly shapes.
            if val is None:
                row[col] = None
            elif isinstance(val, (str, int, float, bool)):
                row[col] = val
            else:
                row[col] = str(val)
        rows.append(row)

    # True (possibly larger) total -- so the page can say "showing 100 of 750".
    from sqlalchemy import func
    total = (
        session.execute(select(func.count()).select_from(table)).scalar() or 0
    )

    return {
        "table": table_name,
        "columns": columns,
        "rows": rows,
        "displayed": len(rows),
        "total": int(total),
        "limit": limit,
    }
