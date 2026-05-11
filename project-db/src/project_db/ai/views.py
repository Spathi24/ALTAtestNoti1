"""Pre-built canned reports.

These are the safest entry point for the AI layer. The LLM doesn't write SQL;
it picks a named report by intent. Each report is a plain function that returns
a list of dicts ready to be summarized in natural language.

Add new reports here. The naming convention is `report_<topic>(...)`.
"""
from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from project_db.db.models import (
    Client,
    Deal,
    ExternalId,
    Invoice,
    InvoiceStatus,
    LeadStage,
    Project,
    ProjectStatus,
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


REPORT_REGISTRY: dict[str, Any] = {
    "active_projects": report_active_projects,
    "deal_pipeline_value": report_deal_pipeline_value,
    "ar_aging": report_ar_aging,
    "entity_external_ids": report_entity_external_ids,
}
