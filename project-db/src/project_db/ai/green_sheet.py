"""Phase 6: the green-sheet aggregator -- one read-only pivot over the
financial spine, per division: budget vs quoted vs committed vs actual.

PURE READ. This module writes nothing -- it queries `SowPackage`,
`SubcontractorQuote`, `FinancialLineItem`, `PurchaseOrder`, `BudgetSnapshot`/
`BudgetSnapshotLine`, and returns a dict. No LLM call, no ledger mutation, no
UI. That is Phase 6's deliberate scope boundary (owner review 2026-07-02):
BudgetSnapshot model -> this one aggregator -> UI is its own later gate.

Cost-status buckets are kept SEPARATE, never summed:
  quoted_cost     -- the SELECTED quote's cost_status="quoted" rows only (the
                     quote we've chosen, pending PO award). NOT every quote
                     ingested for the division.
  pending_bids_cost -- cost_status="quoted" rows belonging to quotes that are
                     NOT yet selected (status pending/recommended) -- i.e.
                     competing bids still under consideration. Kept fully
                     SEPARATE from quoted_cost: summing every received quote
                     into one figure would read as "expected cost" when it is
                     actually the sum of everyone's asking price (owner
                     review 2026-07-02 -- this is the exact bug this split
                     fixes; ingestion writes cost_status="quoted"
                     unconditionally for EVERY ingested quote document,
                     regardless of that quote's own status, so a naive sum
                     over cost_status alone silently triple-counts when
                     multiple subs bid the same package).
  rejected_bid_count -- a count only, no dollar figure. A rejected bid's
                     asking price is dead information; showing it as a
                     dollar amount risks being read as live exposure.
  committed_cost  -- cost_status == "committed" (a PO has been awarded).
  actual_cost     -- cost_status is NULL (legacy llm-v1 extractor -- those
                     rows always represented real spend, see
                     REFOUNDATION_BUILD_NOTES.md checkpoint 2026-07-02) or
                     "actual" (a future PO-actuals matcher's output).
  unclassified_cost -- cost_status in ("estimated", "unknown"), OR a
                     cost_status="quoted" row with no resolvable linked
                     quote, OR one linked to a quote already "awarded" (that
                     row should have been flipped to "committed" by the PO
                     award -- seeing "quoted" here means something is
                     inconsistent, so it is flagged rather than guessed at).
                     Nothing writes the first case today, but all three are
                     routed here rather than silently dropped or folded into
                     a bucket that would misrepresent them.
This is the SAME allow-list discipline already applied to
`report_division_margins` (views.py) -- an explicit per-bucket match, never
an exclusion pattern.

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
          "total_budget":       <float|None>,
          "total_quoted":       <float|None>,  # selected quote(s) only
          "total_pending_bids": <float|None>,  # competing, not-yet-selected bids
          "total_committed":    <float|None>,
          "total_actual":       <float|None>,
          "total_variance":     <float|None>,   # budget - (committed + actual)
          "divisions": [
            {
              "division_code":       "<str>",
              "division_name":       "<str>",
              "budget_amount":       <float|None>,
              "quoted_cost":         <float|None>,  # SELECTED quote only, not a commitment yet
              "pending_bids_cost":   <float|None>,  # OTHER (unselected) competing bids
              "rejected_bid_count":  <int>,          # count only, no dollar figure
              "committed_cost":      <float|None>,  # PO awarded
              "actual_cost":         <float|None>,  # real spend
              "unclassified_cost":   <float|None>,  # flagged, not dropped
              "variance":            <float|None>,  # budget - (committed + actual)
              "package_count":       <int>,
              "quote_count":         <int>,
              "selected_quote_count": <int>,
              "warnings":            [<str>, ...],
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
        # Tiebreak on canonical_id after created_at: two snapshots created in
        # quick succession can land on the EXACT same microsecond
        # (datetime.utcnow() resolution, confirmed by direct reproduction --
        # not hypothetical), which made "most recent" nondeterministic
        # without a secondary sort key. In a genuine tie the two are
        # indistinguishable in time anyway; this only guarantees the same
        # snapshot is picked consistently, not that ties reflect true
        # insertion order.
        snapshot = (
            session.query(_BudgetSnapshot)
            .filter(_BudgetSnapshot.project_id == project.canonical_id)
            .order_by(_BudgetSnapshot.created_at.desc(), _BudgetSnapshot.canonical_id.desc())
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

    # --- quotes for this project: fetched FIRST so cost rows can be
    # categorized by their linked quote's status, not just cost_status alone
    # (see module docstring -- cost_status="quoted" is written unconditionally
    # for every ingested quote, so distinguishing selected vs competing bids
    # requires this join). Also feeds the package/quote counts below.
    quote_status_by_id: dict[Any, str] = {}
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
        quote_status_by_id[q.canonical_id] = q.status
        div = q.division_code or "99"
        quote_count[div] += 1
        if q.status == "selected":
            selected_count[div] += 1

    # --- pivot: cost rows by (division_code, bucket) ---
    pivot: dict = defaultdict(
        lambda: {
            "quoted": _zero,  # SELECTED quote's rows only
            "pending_bids": _zero,  # other (unselected) competing bids
            "rejected_bid_quote_ids": set(),
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
            q_status = quote_status_by_id.get(r.subcontractor_quote_id)
            if q_status == "selected":
                bucket["quoted"] += amount
            elif q_status in ("pending", "recommended"):
                bucket["pending_bids"] += amount
            elif q_status == "rejected":
                # Count only -- a rejected bid's asking price is dead
                # information; showing it as a dollar figure risks being
                # read as live exposure.
                bucket["rejected_bid_quote_ids"].add(r.subcontractor_quote_id)
            else:
                # Unresolvable link, or the linked quote is already
                # "awarded" -- this row should have been flipped to
                # cost_status="committed" by the PO award. Flag rather than
                # guess which bucket it belongs in.
                bucket["unclassified"] += amount
                bucket["unclassified_statuses_seen"].add(f"quoted-row/quote_status={q_status!r}")
        elif r.cost_status == _COMMITTED_STATUS:
            bucket["committed"] += amount
        else:
            bucket["unclassified"] += amount
            bucket["unclassified_statuses_seen"].add(r.cost_status or "NULL")

    # --- build output rows ---------------------------------------------------
    from project_db.ai.financial_divisions import division_by_code

    all_divisions = set(budget_by_division) | set(pivot) | set(pkg_count) | set(quote_count)
    division_rows: list[dict] = []
    for div_code in sorted(all_divisions):
        div = division_by_code(div_code)
        bucket = pivot.get(div_code, {})
        budget_amount = budget_by_division.get(div_code)
        quoted = bucket.get("quoted") or None
        pending_bids = bucket.get("pending_bids") or None
        rejected_bid_count = len(bucket.get("rejected_bid_quote_ids", ()))
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
        if pending_bids:
            warnings.append(
                f"{float(pending_bids):.2f} of competing (not-yet-selected) bids "
                "excluded from quoted_cost -- not expected spend, just asking prices"
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
                "pending_bids_cost": float(pending_bids) if pending_bids is not None else None,
                "rejected_bid_count": rejected_bid_count,
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
    total_pending_bids = _total("pending_bids_cost")
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
        "total_pending_bids": total_pending_bids,
        "total_committed": total_committed,
        "total_actual": total_actual,
        "total_variance": total_variance,
        "divisions": division_rows,
    }
