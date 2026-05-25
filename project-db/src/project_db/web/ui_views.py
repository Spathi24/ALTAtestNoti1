"""Service module for the UI.

Every derived value rendered by the UI is computed here, *not* in templates
and *not* inline in routes.  Templates receive plain dicts / lists; routes
just glue request -> service -> template.

Rule of thumb: if you find yourself writing ``{% if proposals|length > 0 %}``
followed by a calculation in a template, the calculation belongs here.
"""
from __future__ import annotations

from typing import Any

from sqlalchemy import func
from sqlalchemy.orm import Session

from project_db.ai.proposals import list_proposals
from project_db.db.models import (
    Deal,
    Document,
    Lead,
    Project,
    Proposal,
    Task,
)
from project_db.db.models.docs import DocumentText
from project_db.db.models.proposals import ProposalStatus
from project_db.db.models.work import ProjectStatus


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
