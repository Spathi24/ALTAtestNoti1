"""Read-only rollups over the Home Depot ledger (no writes, no network).

These power the ``homedepot status`` / ``homedepot report`` CLI and answer the
only question that matters: where is the money going, and how much of it do we
actually have at line-item resolution yet.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from sqlalchemy import func
from sqlalchemy.orm import Session

from project_db.db.models import HomeDepotLineItem, HomeDepotTransaction, Project

_ZERO = Decimal("0")


def _d(value: Any) -> Decimal:
    return Decimal(str(value)) if value is not None else _ZERO


def _active_txns(session: Session) -> list[HomeDepotTransaction]:
    """All transactions EXCEPT those flagged as duplicates (excluded from totals)."""
    return (
        session.query(HomeDepotTransaction)
        .filter(HomeDepotTransaction.duplicate_of_id.is_(None))
        .all()
    )


def coverage_summary(session: Session) -> dict[str, Any]:
    """Counts, spend, and line-item backfill coverage across all transactions."""
    txns = _active_txns(session)
    dup_rows = (
        session.query(HomeDepotTransaction)
        .filter(HomeDepotTransaction.duplicate_of_id.isnot(None))
        .all()
    )
    purchases = [t for t in txns if not t.is_refund]
    refunds = [t for t in txns if t.is_refund]

    gross = sum((_d(t.total) for t in purchases), _ZERO)
    refunded = sum((_d(t.total) for t in refunds), _ZERO)
    net = gross + refunded  # refund totals are negative

    by_status: dict[str, int] = {}
    for t in txns:
        by_status[t.detail_status] = by_status.get(t.detail_status, 0) + 1

    # "Backfilled" = has line items imported (imported or unbalanced).
    backfilled = [t for t in txns if t.line_item_count]
    backfilled_spend = sum((_d(t.total) for t in backfilled if not t.is_refund), _ZERO)

    line_item_total = session.query(func.count(HomeDepotLineItem.canonical_id)).scalar() or 0

    return {
        "transactions": len(txns),
        "purchases": len(purchases),
        "refunds": len(refunds),
        "gross_spend": gross,
        "refunded": refunded,
        "net_spend": net,
        "by_detail_status": by_status,
        "linked": sum(1 for t in txns if t.project_id is not None),
        "unresolved": sum(1 for t in txns if t.project_id is None),
        "backfilled_count": len(backfilled),
        "backfilled_spend": backfilled_spend,
        "backfilled_spend_pct": (float(backfilled_spend / gross * 100) if gross else 0.0),
        "unbalanced": by_status.get("unbalanced", 0),
        "line_items": int(line_item_total),
        "duplicates_excluded": len(dup_rows),
        "duplicates_amount": sum((_d(t.total) for t in dup_rows), _ZERO),
    }


def spend_by_project(session: Session) -> list[dict[str, Any]]:
    """Net spend per resolved project (plus an 'unresolved' bucket), ranked."""
    projects = {p.canonical_id: p for p in session.query(Project).all()}
    buckets: dict[Any, dict[str, Any]] = {}
    for t in _active_txns(session):
        key = t.project_id
        b = buckets.setdefault(
            key,
            {"project_id": key, "label": None, "transactions": 0, "net_spend": _ZERO},
        )
        b["transactions"] += 1
        b["net_spend"] += _d(t.total)
    for b in buckets.values():
        if b["project_id"] is None:
            b["label"] = "(unresolved)"
        else:
            proj = projects.get(b["project_id"])
            b["label"] = proj.name if proj else str(b["project_id"])
    return sorted(buckets.values(), key=lambda b: b["net_spend"], reverse=True)


def top_items(session: Session, *, limit: int = 25, project_id: Any | None = None) -> list[dict[str, Any]]:
    """Aggregate line items by SKU -- total quantity and spend, ranked by spend."""
    q = session.query(HomeDepotLineItem)
    if project_id is not None:
        q = q.filter(HomeDepotLineItem.project_id == project_id)
    agg: dict[str, dict[str, Any]] = {}
    for li in q.all():
        key = li.sku or (li.product_name or "?")
        a = agg.setdefault(
            key,
            {"sku": li.sku, "product_name": li.product_name, "quantity": _ZERO, "spend": _ZERO, "lines": 0},
        )
        a["quantity"] += _d(li.quantity)
        a["spend"] += _d(li.subtotal)
        a["lines"] += 1
        if not a["product_name"] and li.product_name:
            a["product_name"] = li.product_name
    ranked = sorted(agg.values(), key=lambda a: a["spend"], reverse=True)
    return ranked[:limit] if limit else ranked


def backfill_queue(
    session: Session, *, limit: int = 50, include_refunds: bool = False
) -> list[HomeDepotTransaction]:
    """Pending (no line items) transactions ranked by absolute total descending.

    This is the work-list: chase the biggest dollars first. Per the spend curve,
    the top ~50 transactions are ~80% of gross spend.
    """
    q = session.query(HomeDepotTransaction).filter(
        HomeDepotTransaction.detail_status == "pending",
        HomeDepotTransaction.duplicate_of_id.is_(None),
    )
    if not include_refunds:
        q = q.filter(HomeDepotTransaction.is_refund.is_(False))
    txns = q.all()
    txns.sort(key=lambda t: abs(_d(t.total)), reverse=True)
    return txns[:limit] if limit else txns
