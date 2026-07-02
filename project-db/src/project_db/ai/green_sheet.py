"""Phase 6: the green-sheet aggregator -- one read-only pivot over the
financial spine, per division: budget vs quoted vs committed vs actual.

PURE READ. This module writes nothing -- it queries `SowPackage`,
`SubcontractorQuote`, `FinancialLineItem`, `PurchaseOrder`, `BudgetSnapshot`/
`BudgetSnapshotLine`, and returns a dict. No LLM call, no ledger mutation, no
UI. That is Phase 6's deliberate scope boundary (owner review 2026-07-02):
BudgetSnapshot model -> this one aggregator -> UI is its own later gate.

Cost-status buckets are kept SEPARATE, never summed:
  quoted_cost     -- FinancialLineItem.cost_status == "quoted" (pipeline, not
                     yet a commitment -- a *selected* quote is still "quoted").
  committed_cost  -- cost_status == "committed" (a PO has been awarded).
  actual_cost     -- cost_status is NULL (legacy llm-v1 extractor -- those
                     rows always represented real spend, see
                     REFOUNDATION_BUILD_NOTES.md checkpoint 2026-07-02) or
                     "actual" (a future PO-actuals matcher's output).
  unclassified_cost -- cost_status in ("estimated", "unknown"): nothing
                     writes these today, but if something ever does, they are
                     flagged here rather than silently dropped or silently
                     folded into "actual".
This is the SAME allow-list rule already applied to `report_division_margins`
(views.py) -- an explicit per-bucket match, never an exclusion pattern.

amount_type is NOT filtered to material/labour here. The reason a filter like
that exists elsewhere (division-total rows must not be summed against their
own material+labour line items) does not apply to the persisted data today:
`ai/subcontractor_quote_ingest.py` only ever writes `kind="line_item"` rows
for cost data -- division-total rows are never persisted for cost at all, so
there is nothing to double-count against. The legacy llm-v1 extractor's cost
rows are almost entirely `amount_type="total"` (no material/labour split);
filtering them out would silently zero real spend for every project that
predates Phase 4/5. Sum by amount_type into material/labour/other, same as
`report_division_margins` already does, with no exclusion.

Budget: reads the MOST RECENT `BudgetSnapshot` for the project (by
created_at) unless `snapshot_id` is given. No snapshot -> `budget_amount` is
None for every division (never fabricated).
"""

from __future__ import annotations

from collections import defaultdict
from decimal import Decimal
from typing import Any

from sqlalchemy.orm import Session

# Cost rows counting as "actual" spend for this aggregator (allow-list, not
# an exclusion pattern -- see module docstring and the identical rule already
# applied in ai/views.py::report_division_margins).
_ACTUAL_COST_STATUSES = (None, "actual")
_QUOTED_STATUS = "quoted"
_COMMITTED_STATUS = "committed"


def report_green_sheet(
    session: Session, project_ref: str, *, snapshot_id: Any | None = None
) -> dict[str, Any]:
    """Per-division budget vs quoted vs committed vs actual for one project.

    Returns ``{"error": "..."}`` when the project doesn't resolve.

    Output shape::

        {
          "project": "<name>",
          "project_id": "<uuid>",
          "budget_snapshot_id": "<uuid>|None",
          "budget_snapshot_label": "<str>|None",
          "total_budget":    <float|None>,
          "total_quoted":    <float|None>,
          "total_committed": <float|None>,
          "total_actual":    <float|None>,
          "total_variance":  <float|None>,   # budget - (committed + actual)
          "divisions": [
            {
              "division_code":     "<str>",
              "division_name":     "<str>",
              "budget_amount":     <float|None>,
              "quoted_cost":       <float|None>,  # pipeline -- not yet a commitment
              "committed_cost":    <float|None>,  # PO awarded
              "actual_cost":       <float|None>,  # real spend
              "unclassified_cost": <float|None>,  # flagged, not dropped
              "variance":          <float|None>,  # budget - (committed + actual)
              "package_count":     <int>,
              "quote_count":       <int>,
              "selected_quote_count": <int>,
              "warnings":          [<str>, ...],
            },
            ...
          ],
        }
    """
    from project_db.ai.views import _resolve_project
    from project_db.db.models.finance import BudgetSnapshot as _BudgetSnapshot
    from project_db.db.models.finance import BudgetSnapshotLine as _BudgetSnapshotLine
    from project_db.db.models.finance import FinancialLineItem
    from project_db.db.models.finance import SubcontractorQuote as _SubcontractorQuote
    from project_db.db.models.sow import SowPackage as _SowPackage

    project = _resolve_project(session, project_ref)
    if project is None:
        return {"error": f"No project matched ref={project_ref!r}"}

    _zero = Decimal(0)

    # --- resolve the budget snapshot (most recent, unless a specific one is given) ---
    if snapshot_id is not None:
        snapshot = (
            session.query(_BudgetSnapshot)
            .filter(_BudgetSnapshot.canonical_id == snapshot_id)
            .one_or_none()
        )
    else:
        snapshot = (
            session.query(_BudgetSnapshot)
            .filter(_BudgetSnapshot.project_id == project.canonical_id)
            .order_by(_BudgetSnapshot.created_at.desc())
            .first()
        )
    budget_by_division: dict[str, Decimal] = {}
    if snapshot is not None:
        for line in (
            session.query(_BudgetSnapshotLine)
            .filter(_BudgetSnapshotLine.snapshot_id == snapshot.canonical_id)
            .all()
        ):
            if line.budget_amount is not None:
                budget_by_division[line.division_code] = Decimal(str(line.budget_amount))

    # --- pivot: cost rows by (division_code, cost_status bucket) ---
    pivot: dict = defaultdict(
        lambda: {
            "quoted": _zero,
            "committed": _zero,
            "actual": _zero,
            "unclassified": _zero,
            "unclassified_statuses_seen": set(),
        }
    )
    cost_rows = (
        session.query(FinancialLineItem)
        .filter(
            FinancialLineItem.project_id == project.canonical_id,
            FinancialLineItem.side == "cost",
        )
        .all()
    )
    for r in cost_rows:
        amount = Decimal(str(r.amount or 0))
        bucket = pivot[r.division_code]
        if r.cost_status in _ACTUAL_COST_STATUSES:
            bucket["actual"] += amount
        elif r.cost_status == _QUOTED_STATUS:
            bucket["quoted"] += amount
        elif r.cost_status == _COMMITTED_STATUS:
            bucket["committed"] += amount
        else:
            bucket["unclassified"] += amount
            bucket["unclassified_statuses_seen"].add(r.cost_status or "NULL")

    # --- package/quote counts per division (scope + tendering visibility) ---
    pkg_count: dict[str, int] = defaultdict(int)
    quote_count: dict[str, int] = defaultdict(int)
    selected_count: dict[str, int] = defaultdict(int)
    for pkg in (
        session.query(_SowPackage).filter(_SowPackage.project_id == project.canonical_id).all()
    ):
        pkg_count[pkg.division_code] += 1
    for q in (
        session.query(_SubcontractorQuote)
        .filter(_SubcontractorQuote.project_id == project.canonical_id)
        .all()
    ):
        div = q.division_code or "99"
        quote_count[div] += 1
        if q.status == "selected":
            selected_count[div] += 1

    # --- build output rows ---------------------------------------------------
    from project_db.ai.financial_divisions import division_by_code

    all_divisions = set(budget_by_division) | set(pivot) | set(pkg_count) | set(quote_count)
    division_rows: list[dict] = []
    for div_code in sorted(all_divisions):
        div = division_by_code(div_code)
        bucket = pivot.get(div_code, {})
        budget_amount = budget_by_division.get(div_code)
        quoted = bucket.get("quoted") or None
        committed = bucket.get("committed") or None
        actual = bucket.get("actual") or None
        unclassified = bucket.get("unclassified") or None

        warnings: list[str] = []
        if unclassified:
            seen = sorted(bucket.get("unclassified_statuses_seen", ()))
            warnings.append(
                f"{float(unclassified):.2f} of cost-side amount has an unclassified "
                f"cost_status {seen} -- not counted in quoted/committed/actual"
            )

        variance = None
        if budget_amount is not None:
            exposure = (committed or _zero) + (actual or _zero)
            variance = budget_amount - exposure

        division_rows.append(
            {
                "division_code": div_code,
                "division_name": div.name,
                "budget_amount": float(budget_amount) if budget_amount is not None else None,
                "quoted_cost": float(quoted) if quoted is not None else None,
                "committed_cost": float(committed) if committed is not None else None,
                "actual_cost": float(actual) if actual is not None else None,
                "unclassified_cost": float(unclassified) if unclassified is not None else None,
                "variance": float(variance) if variance is not None else None,
                "package_count": pkg_count.get(div_code, 0),
                "quote_count": quote_count.get(div_code, 0),
                "selected_quote_count": selected_count.get(div_code, 0),
                "warnings": warnings,
            }
        )

    def _total(key: str) -> float | None:
        vals = [r[key] for r in division_rows if r[key] is not None]
        return sum(vals) if vals else None

    total_budget = _total("budget_amount")
    total_quoted = _total("quoted_cost")
    total_committed = _total("committed_cost")
    total_actual = _total("actual_cost")
    total_variance = (
        total_budget - ((total_committed or 0.0) + (total_actual or 0.0))
        if total_budget is not None
        else None
    )

    return {
        "project": project.name,
        "project_id": str(project.canonical_id),
        "budget_snapshot_id": str(snapshot.canonical_id) if snapshot is not None else None,
        "budget_snapshot_label": snapshot.label if snapshot is not None else None,
        "total_budget": total_budget,
        "total_quoted": total_quoted,
        "total_committed": total_committed,
        "total_actual": total_actual,
        "total_variance": total_variance,
        "divisions": division_rows,
    }
