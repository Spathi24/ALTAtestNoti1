#!/usr/bin/env python3
"""project_optimizer.py -- PERT/CPM Analysis on Monday.com project board data.

Commands
--------
  demo
      Run a built-in sample project so you can see the optimizer output
      without a Monday API token.

  list-boards
      List all project boards that have timeline or date columns.

  export-deps <board_id> [--output FILE]
      Pull all tasks from a board and write a starter deps JSON you can fill in.
      Default output: deps_<board_id>.json

  analyze <board_id> --deps FILE [--analysis MODE] [--target DAYS]
      Run PERT/CPM using a dependency file you filled in from export-deps.

  analyze <board_id> --auto-deps [--analysis MODE] [--target DAYS]
      Auto-generate linear dependencies within each board group (group items
      form a chain: task1 -> task2 -> task3 ...).

  analyze <board_id> --no-deps [--analysis MODE] [--target DAYS]
      Treat all tasks as independent (all start at t=0, no dependencies).
      Shows PERT estimates and duration stats but no critical path.

Analysis modes  (--analysis, default=all)
  critical-path   Critical path tasks + project duration
  slack           Total float and free float per task
  drag            Critical path drag -- how much each critical task delays the project
  fast-track      Fast-tracking: which critical tasks can be parallelised
  crash           Crash analysis: which critical tasks to shorten first
  probability     PERT probability of finishing by a target date
  all             Run all of the above (default)

PERT 3-point estimates in the deps file
  By default the task's calendar duration is used as all three estimates
  (optimistic = most_likely = pessimistic = calendar days).
  To get proper PERT uncertainty modelling, add per-task overrides in the deps
  JSON (see export-deps output for the exact format):

    "pert": {"optimistic": 2, "most_likely": 5, "pessimistic": 10}

Windows note: all output is ASCII-only (no arrows, box chars, or ellipsis).
"""
from __future__ import annotations

import argparse
import json
import math
import os
import re
import sys
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Any

import httpx

# ---------------------------------------------------------------------------
# Make the package importable when run from the repo root or from scripts/
# ---------------------------------------------------------------------------
_HERE = Path(__file__).resolve().parent
_SRC = _HERE.parent / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from project_db.config import settings
from project_db.connectors.monday.client import MondayClient
from project_db.connectors.monday.column_extractor import ColumnExtractor
from project_db.connectors.monday.connector import apply_portfolio_mirror_overlay

PROJECT_WORKSPACE_NAMES = {"Project Management"}
NON_PROJECT_WORKSPACE_NAMES = {"CRM"}
NON_PROJECT_BOARD_KEYWORDS = (
    "lead", "deal", "contact", "account", "client", "crm", "pipeline",
    "quote", "invoice", "activity", "activities", "task sheet", "subitems",
)


# ===========================================================================
# Data model
# ===========================================================================

@dataclass
class Activity:
    """One project task, enriched with PERT/CPM computed fields."""

    # From Monday
    id: str
    name: str
    group: str
    status: str
    start_date: date | None
    end_date: date | None
    duration: float             # calendar days (from timeline or date columns)

    # PERT 3-point estimates (days)
    optimistic: float = 0.0
    most_likely: float = 0.0
    pessimistic: float = 0.0

    # Derived PERT values
    expected: float = 0.0       # te = (o + 4m + p) / 6
    std_dev: float = 0.0        # sdte = (p - o) / 6
    variance: float = 0.0       # sdte^2

    # Network
    predecessors: list[str] = field(default_factory=list)
    successors: list[str] = field(default_factory=list)

    # CPM forward/backward pass
    es: float = 0.0             # Early Start
    ef: float = 0.0             # Early Finish
    ls: float = 0.0             # Late Start
    lf: float = 0.0             # Late Finish
    total_float: float = 0.0    # LF - EF  (or LS - ES)
    free_float: float = 0.0     # min(ES of successors) - EF
    is_critical: bool = False
    drag: float = 0.0           # drag on the critical path

    def apply_pert(self) -> None:
        """Compute expected time, std_dev, variance from 3-point estimates."""
        self.expected = (self.optimistic + 4 * self.most_likely + self.pessimistic) / 6
        self.std_dev = (self.pessimistic - self.optimistic) / 6
        self.variance = self.std_dev ** 2


# ===========================================================================
# Monday data fetch
# ===========================================================================

def fetch_board_tasks(client: MondayClient, board_id: int) -> list[dict[str, Any]]:
    """Pull items from a board (with mirror-column overlay) and return raw dicts.

    Many construction-side task boards store the real status/timeline as MIRROR
    columns on a linked portfolio item, not on the task row itself. We follow
    those links and merge the mirrored values back onto each task before
    extracting fields -- see connector.apply_portfolio_mirror_overlay.
    """
    cols = client.list_board_columns(board_id)
    items = client.list_items(board_id)
    items = apply_portfolio_mirror_overlay(
        client, items, board={"id": board_id, "name": f"board:{board_id}"}
    )
    extractor = ColumnExtractor(cols)
    result = []
    for item in items:
        if item.get("state") != "active":
            continue
        cv = item.get("column_values") or []
        fields = extractor.extract(cv)
        group = (item.get("group") or {}).get("title", "")

        # Determine duration in days: prefer the explicit Duration column,
        # then fall back to (end - start) on the timeline, then 1 day.
        start = fields.start_date
        end = fields.end_date
        if fields.duration_days is not None and fields.duration_days > 0:
            duration = float(fields.duration_days)
        elif start and end and end >= start:
            duration = float((end - start).days) or 1.0
        else:
            duration = 1.0

        # Prefer the heuristic-extracted status label; fall back to the raw
        # column text (matches both native status columns and the mirror
        # overlay's synthetic "label" field).
        status_raw = fields.status_label or ""
        if not status_raw:
            for v in cv:
                if v.get("type") == "status" and (v.get("text") or v.get("label")):
                    status_raw = v.get("text") or v.get("label") or ""
                    break

        result.append({
            "id": item["id"],
            "name": item["name"],
            "group": group,
            "status": status_raw,
            "start_date": str(start) if start else None,
            "end_date": str(end) if end else None,
            "duration": duration,
        })
    return result


def list_project_boards(client: MondayClient) -> list[dict[str, Any]]:
    """Return boards that look like project/job boards (not CRM boards)."""
    boards = client.list_boards(limit=200)
    project_boards = []
    for b in boards:
        if not _looks_like_project_board(b):
            continue
        if b.get("board_kind") == "private":
            continue
        try:
            board_id = int(b["id"])
        except (TypeError, ValueError):
            continue

        cols = client.list_board_columns(board_id)
        has_dates = any(
            (c.get("type") in ("timeline", "date"))
            for c in cols
        )
        if not has_dates:
            continue
        project_boards.append(b)
    return project_boards


def _looks_like_project_board(board: dict[str, Any]) -> bool:
    """Cheap prefilter before spending an API call on board columns."""
    name = board.get("name") or ""
    name_lower = name.lower()
    workspace_name = ((board.get("workspace") or {}).get("name") or "").strip()

    if workspace_name in NON_PROJECT_WORKSPACE_NAMES:
        return False
    if any(keyword in name_lower for keyword in NON_PROJECT_BOARD_KEYWORDS):
        return False
    if workspace_name in PROJECT_WORKSPACE_NAMES:
        return True
    # Address-like boards outside the Project Management workspace.
    return bool(re.search(r"^\d+[-\s].+", name))


# ===========================================================================
# Dependency helpers
# ===========================================================================

def auto_deps_sequential(tasks: list[dict]) -> dict[str, list[str]]:
    """Within each group, each task depends on the previous one (chain)."""
    from collections import defaultdict
    by_group: dict[str, list[str]] = defaultdict(list)
    for t in tasks:
        by_group[t["group"]].append(t["id"])
    deps: dict[str, list[str]] = {t["id"]: [] for t in tasks}
    for group_tasks in by_group.values():
        for i in range(1, len(group_tasks)):
            deps[group_tasks[i]].append(group_tasks[i - 1])
    return deps


def load_deps_file(path: str, task_ids: set[str]) -> dict[str, list[str]]:
    """Load deps JSON file; ignore any IDs not in the current board."""
    with open(path) as fh:
        raw = json.load(fh)
    deps = {}
    for tid in task_ids:
        raw_preds = raw.get(tid, {})
        if isinstance(raw_preds, dict):
            preds = raw_preds.get("predecessors", [])
        else:
            preds = raw_preds  # legacy flat format
        deps[tid] = [p for p in preds if p in task_ids]
    return deps


# ===========================================================================
# PERT/CPM engine
# ===========================================================================

def build_activities(
    tasks: list[dict],
    deps: dict[str, list[str]],
    pert_overrides: dict[str, dict],   # task_id -> {optimistic, most_likely, pessimistic}
) -> dict[str, Activity]:
    """Construct Activity objects with PERT estimates applied."""
    activities: dict[str, Activity] = {}
    for t in tasks:
        tid = t["id"]
        dur = t["duration"]
        ov = pert_overrides.get(tid, {})
        o = float(ov.get("optimistic", dur))
        m = float(ov.get("most_likely", dur))
        p = float(ov.get("pessimistic", dur))
        if o < 0 or m < 0 or p < 0:
            raise ValueError(f"PERT estimates must be non-negative for task {tid}")
        if not (o <= m <= p):
            raise ValueError(
                f"PERT estimates must satisfy optimistic <= most_likely <= "
                f"pessimistic for task {tid}"
            )
        act = Activity(
            id=tid,
            name=t["name"],
            group=t.get("group", ""),
            status=t.get("status", ""),
            start_date=_parse_date(t.get("start_date")),
            end_date=_parse_date(t.get("end_date")),
            duration=dur,
            optimistic=o,
            most_likely=m,
            pessimistic=p,
            predecessors=deps.get(tid, []),
        )
        act.apply_pert()
        activities[tid] = act

    # Build successor lists
    for act in activities.values():
        for pred_id in act.predecessors:
            if pred_id in activities:
                activities[pred_id].successors.append(act.id)

    return activities


def analyze_network(
    tasks: list[dict],
    deps: dict[str, list[str]],
    pert_overrides: dict[str, dict] | None = None,
) -> dict[str, Activity]:
    """Build and calculate a PERT/CPM network from task dictionaries."""
    activities = build_activities(tasks, deps, pert_overrides or {})
    cpm_forward_pass(activities)
    cpm_backward_pass(activities)
    compute_free_float(activities)
    compute_drag(activities)
    return activities


def _parse_date(s: str | None) -> date | None:
    if not s:
        return None
    try:
        return datetime.strptime(s, "%Y-%m-%d").date()
    except ValueError:
        return None


def cpm_forward_pass(activities: dict[str, Activity]) -> None:
    """Compute ES and EF for all activities using topological ordering."""
    ordered = _topological_sort(activities)
    for act_id in ordered:
        act = activities[act_id]
        if not act.predecessors:
            act.es = 0.0
        else:
            act.es = max(
                activities[p].ef
                for p in act.predecessors
                if p in activities
            )
        act.ef = act.es + act.expected


def cpm_backward_pass(activities: dict[str, Activity]) -> None:
    """Compute LS and LF for all activities. Forward pass must run first."""
    ordered = _topological_sort(activities)
    project_ef = max(a.ef for a in activities.values()) if activities else 0.0

    for act_id in reversed(ordered):
        act = activities[act_id]
        if not act.successors:
            act.lf = project_ef
        else:
            act.lf = min(
                activities[s].ls
                for s in act.successors
                if s in activities
            )
        act.ls = act.lf - act.expected
        act.total_float = round(act.lf - act.ef, 4)
        act.is_critical = abs(act.total_float) < 0.001


def compute_free_float(activities: dict[str, Activity]) -> None:
    """Free float = min(ES of successors) - EF. Requires forward pass."""
    for act in activities.values():
        if not act.successors:
            act.free_float = act.total_float
        else:
            min_succ_es = min(
                activities[s].es
                for s in act.successors
                if s in activities
            )
            act.free_float = round(min_succ_es - act.ef, 4)


def compute_drag(activities: dict[str, Activity]) -> None:
    """Critical path drag for each critical activity.

    If nothing runs in parallel with a critical activity:
        drag = activity duration (expected time)
    If other activities run in parallel:
        drag = min(activity duration, min total_float of all parallel activities)
    A parallel activity is any NON-critical activity whose ES < critical.EF
    and EF > critical.ES (i.e. time ranges overlap).
    """
    non_critical = [a for a in activities.values() if not a.is_critical]
    for act in activities.values():
        if not act.is_critical:
            act.drag = 0.0
            continue
        # Find parallel non-critical activities
        parallel_floats = [
            nc.total_float
            for nc in non_critical
            if nc.es < act.ef and nc.ef > act.es
        ]
        if not parallel_floats:
            act.drag = act.expected
        else:
            act.drag = min(act.expected, min(parallel_floats))
        act.drag = round(act.drag, 2)


def _topological_sort(activities: dict[str, Activity]) -> list[str]:
    """Kahn's algorithm. Raises on cycles."""
    in_degree = {tid: 0 for tid in activities}
    for act in activities.values():
        for p in act.predecessors:
            if p in in_degree:
                in_degree[act.id] += 1

    queue = [tid for tid, deg in in_degree.items() if deg == 0]
    order = []
    while queue:
        tid = queue.pop(0)
        order.append(tid)
        for succ_id in activities[tid].successors:
            if succ_id in in_degree:
                in_degree[succ_id] -= 1
                if in_degree[succ_id] == 0:
                    queue.append(succ_id)

    if len(order) != len(activities):
        raise ValueError(
            "Dependency cycle detected! Check your deps file. "
            "Activities not ordered: " + str(set(activities) - set(order))
        )
    return order


def get_critical_path(activities: dict[str, Activity]) -> list[Activity]:
    """Return critical activities sorted by ES."""
    crits = [a for a in activities.values() if a.is_critical]
    return sorted(crits, key=lambda a: a.es)


def get_all_paths(activities: dict[str, Activity]) -> list[tuple[list[str], float]]:
    """Enumerate all source-to-sink paths and their total expected durations.
    Returns list of (path_ids, total_te) sorted descending by duration.
    Only practical for small networks (<= 30 tasks).
    """
    sources = [a.id for a in activities.values() if not a.predecessors]
    sinks = [a.id for a in activities.values() if not a.successors]
    paths: list[tuple[list[str], float]] = []

    def dfs(current: str, path: list[str], total: float) -> None:
        path = path + [current]
        total = total + activities[current].expected
        if current in sinks:
            paths.append((path, round(total, 2)))
            return
        for succ in activities[current].successors:
            dfs(succ, path, total)

    for src in sources:
        dfs(src, [], 0.0)

    return sorted(paths, key=lambda x: x[1], reverse=True)


def get_probability_path(activities: dict[str, Activity]) -> list[Activity]:
    """Return one longest source-to-sink path for PERT probability.

    CPM can have multiple parallel critical paths. For a single probability
    estimate, use one complete path rather than summing every zero-float task.
    If paths tie on expected duration, use the path with higher variance.
    """
    if not activities:
        return []

    ordered = _topological_sort(activities)
    best: dict[str, tuple[float, float, list[str]]] = {}

    for act_id in ordered:
        act = activities[act_id]
        if not act.predecessors:
            best[act_id] = (act.expected, act.variance, [act_id])
            continue

        pred_scores = [
            best[pred_id]
            for pred_id in act.predecessors
            if pred_id in best
        ]
        if not pred_scores:
            best[act_id] = (act.expected, act.variance, [act_id])
            continue

        pred_duration, pred_variance, pred_path = max(
            pred_scores,
            key=lambda score: (round(score[0], 6), round(score[1], 6)),
        )
        best[act_id] = (
            pred_duration + act.expected,
            pred_variance + act.variance,
            pred_path + [act_id],
        )

    sink_ids = [a.id for a in activities.values() if not a.successors]
    if not sink_ids:
        return []
    _, _, path_ids = max(
        (best[sink_id] for sink_id in sink_ids if sink_id in best),
        key=lambda score: (round(score[0], 6), round(score[1], 6)),
    )
    return [activities[act_id] for act_id in path_ids]


# ===========================================================================
# PERT probability
# ===========================================================================

def pert_probability(
    activities: dict[str, Activity],
    target_days: float,
) -> dict[str, float]:
    """Probability of completing the critical path by target_days (PERT stats).

    Uses the central limit theorem: sum of critical-path expected times is
    approximately normal with mean = sum(te) and variance = sum(variance).
    Returns dict with mean, std_dev, target, z_score, probability.
    """
    probability_path = get_probability_path(activities)
    if not probability_path:
        return {}

    te_total = sum(a.expected for a in probability_path)
    var_total = sum(a.variance for a in probability_path)
    sigma_total = math.sqrt(var_total) if var_total > 0 else 0.0

    if sigma_total == 0:
        prob = 1.0 if target_days >= te_total else 0.0
        z = float("inf") if target_days >= te_total else float("-inf")
    else:
        z = (target_days - te_total) / sigma_total
        prob = _normal_cdf(z)

    return {
        "critical_path_mean_days": round(te_total, 2),
        "critical_path_std_dev": round(sigma_total, 2),
        "target_days": target_days,
        "z_score": round(z, 3),
        "probability_pct": round(prob * 100, 1),
    }


def _normal_cdf(z: float) -> float:
    """Approximation of the standard normal CDF using math.erfc."""
    return 0.5 * math.erfc(-z / math.sqrt(2))


# ===========================================================================
# Output / reporting
# ===========================================================================

LINE = "-" * 72


def _fmt(value: float) -> str:
    return f"{value:.2f}"


def print_critical_path(activities: dict[str, Activity]) -> None:
    print()
    print("=" * 72)
    print("  CRITICAL PATH ANALYSIS")
    print("=" * 72)
    crits = get_critical_path(activities)
    if not crits:
        print("  No critical path found -- are all tasks independent?")
        return

    project_duration = max(a.ef for a in activities.values())
    print(f"  Project duration (expected):   {_fmt(project_duration)} days")
    print(f"  Critical tasks:                {len(crits)}")
    print()
    print(f"  {'Task':<35} {'Group':<20} {'te':>6} {'ES':>6} {'EF':>6}  Status")
    print(f"  {'-'*35} {'-'*20} {'-'*6} {'-'*6} {'-'*6}  {'-'*12}")
    for a in crits:
        name = a.name[:34]
        grp = a.group[:19]
        print(f"  {name:<35} {grp:<20} {_fmt(a.expected):>6} {_fmt(a.es):>6} {_fmt(a.ef):>6}  {a.status}")

    # All paths if network is small enough
    if len(activities) <= 30:
        print()
        print("  All paths (longest first):")
        print(f"  {'Duration':>8}  Path")
        print(f"  {'-'*8}  {'-'*50}")
        paths = get_all_paths(activities)
        for path_ids, dur in paths[:10]:
            names = [activities[pid].name[:12] for pid in path_ids]
            print(f"  {_fmt(dur):>8}  {' -> '.join(names)}")
        if len(paths) > 10:
            print(f"  ... and {len(paths) - 10} more paths")


def print_slack(activities: dict[str, Activity]) -> None:
    print()
    print("=" * 72)
    print("  FLOAT / SLACK ANALYSIS")
    print("=" * 72)
    print(f"  {'Task':<35} {'Group':<18} {'te':>5} {'TF':>7} {'FF':>7}  Critical")
    print(f"  {'-'*35} {'-'*18} {'-'*5} {'-'*7} {'-'*7}  {'-'*8}")
    sorted_acts = sorted(activities.values(), key=lambda a: a.total_float)
    for a in sorted_acts:
        crit = "YES (*)" if a.is_critical else ""
        name = a.name[:34]
        grp = a.group[:17]
        print(
            f"  {name:<35} {grp:<18} {_fmt(a.expected):>5} "
            f"{_fmt(a.total_float):>7} {_fmt(a.free_float):>7}  {crit}"
        )
    print()
    print("  TF = Total Float (days project can slip without delay)")
    print("  FF = Free Float (days task can slip without delaying successors)")


def print_drag(activities: dict[str, Activity]) -> None:
    print()
    print("=" * 72)
    print("  CRITICAL PATH DRAG ANALYSIS")
    print("=" * 72)
    print("  Drag = how many days each critical task is extending the project.")
    print("  Reducing a task's duration by X reduces the project by min(X, drag).")
    print()
    crits = get_critical_path(activities)
    if not crits:
        print("  No critical tasks found.")
        return
    crits_by_drag = sorted(crits, key=lambda a: a.drag, reverse=True)
    print(f"  {'Task':<35} {'Group':<18} {'te':>5} {'Drag':>6}  Parallel?")
    print(f"  {'-'*35} {'-'*18} {'-'*5} {'-'*6}  {'-'*10}")
    non_crit = [a for a in activities.values() if not a.is_critical]
    for a in crits_by_drag:
        has_parallel = any(
            nc.es < a.ef and nc.ef > a.es for nc in non_crit
        )
        par_str = "yes" if has_parallel else "no (drag=te)"
        name = a.name[:34]
        grp = a.group[:17]
        print(f"  {name:<35} {grp:<18} {_fmt(a.expected):>5} {_fmt(a.drag):>6}  {par_str}")

    total_drag = sum(a.drag for a in crits_by_drag)
    print()
    print(f"  Total drag (sum over critical tasks): {_fmt(total_drag)} days")
    print("  Note: drag values are not simply additive -- reducing one task")
    print("  may shift what is critical. Re-run after each change.")


def print_fast_track(activities: dict[str, Activity]) -> None:
    print()
    print("=" * 72)
    print("  FAST-TRACKING RECOMMENDATIONS")
    print("=" * 72)
    print("  Fast-tracking = running critical tasks in parallel to shorten the path.")
    print("  Candidates: critical tasks with sequential predecessors that could")
    print("  potentially overlap (at the cost of rework risk).")
    print()
    crits = get_critical_path(activities)
    if not crits:
        print("  No critical tasks found.")
        return

    candidates = []
    for a in crits:
        critical_preds = [
            pid for pid in a.predecessors
            if pid in activities and activities[pid].is_critical
        ]
        if critical_preds:
            candidates.append((a, critical_preds))

    if not candidates:
        print("  No sequential critical-to-critical dependencies found.")
        print("  All critical tasks may already be running in parallel.")
        return

    print(f"  {'Task':<35} {'Depends on (critical)':<35}  Potential saving")
    print(f"  {'-'*35} {'-'*35}  {'-'*15}")
    for act, preds in candidates:
        pred_names = ", ".join(activities[p].name[:15] for p in preds)
        # Max saving if we run them fully in parallel
        max_save = max(activities[p].expected for p in preds)
        name = act.name[:34]
        print(f"  {name:<35} {pred_names:<35}  up to {_fmt(max_save)} days")

    print()
    print("  WARNING: Fast-tracking introduces rework risk. Evaluate carefully.")


def print_crash(activities: dict[str, Activity]) -> None:
    print()
    print("=" * 72)
    print("  CRASHING RECOMMENDATIONS")
    print("=" * 72)
    print("  Crashing = adding resources to shorten critical tasks.")
    print("  Prioritize tasks with the HIGHEST drag (biggest impact per dollar).")
    print()
    crits = get_critical_path(activities)
    if not crits:
        print("  No critical tasks found.")
        return
    crits_by_drag = sorted(crits, key=lambda a: a.drag, reverse=True)

    print(f"  Priority  {'Task':<35} {'te':>5} {'Drag':>6}  Action")
    print(f"  {'-'*8}  {'-'*35} {'-'*5} {'-'*6}  {'-'*30}")
    for rank, a in enumerate(crits_by_drag, 1):
        if a.drag < 0.5:
            action = "Low priority (drag < 0.5 day)"
        elif a.drag < 2:
            action = "Minor crash -- 1 extra resource"
        elif a.drag < 5:
            action = "Moderate crash -- consider overtime / subcontract"
        else:
            action = "HIGH IMPACT -- crash first"
        name = a.name[:34]
        print(f"  {rank:<8}  {name:<35} {_fmt(a.expected):>5} {_fmt(a.drag):>6}  {action}")

    total_save = sum(a.drag for a in crits_by_drag)
    print()
    print(f"  If all critical tasks are crashed to zero drag, theoretical")
    print(f"  project reduction: up to {_fmt(total_save)} days")
    print("  (Actual saving is limited by the next longest non-critical path.)")


def print_probability(activities: dict[str, Activity], target_days: float) -> None:
    print()
    print("=" * 72)
    print("  PERT PROBABILITY ANALYSIS")
    print("=" * 72)
    result = pert_probability(activities, target_days)
    if not result:
        print("  Could not compute -- no critical path or no activities.")
        return

    print(f"  Critical path expected duration:  {result['critical_path_mean_days']} days")
    print(f"  Critical path std deviation:      {result['critical_path_std_dev']} days")
    print(f"  Target completion:                {result['target_days']} days")
    print(f"  Z-score:                          {result['z_score']}")
    print(f"  Probability of on-time delivery:  {result['probability_pct']}%")
    print()

    # Print a small probability table
    mean = result["critical_path_mean_days"]
    sigma = result["critical_path_std_dev"]
    print("  Completion probability table:")
    print(f"  {'Target (days)':>14}  {'Probability':>12}")
    print(f"  {'-'*14}  {'-'*12}")
    if sigma > 0:
        for z, label in [(-2, "-2 sigma"), (-1, "-1 sigma"), (0, "mean"),
                          (1, "+1 sigma"), (2, "+2 sigma")]:
            t = mean + z * sigma
            p = _normal_cdf(z) * 100
            marker = " <-- target" if abs(t - target_days) < sigma * 0.5 else ""
            print(f"  {_fmt(t):>14}  {p:>11.1f}%{marker}")
    else:
        print(f"  {_fmt(mean):>14}  {'deterministic':>12} (no uncertainty -- all te=o=p)")

    if sigma == 0:
        print()
        print("  NOTE: To get meaningful PERT probabilities, add 'pert' overrides")
        print("  to your deps JSON file (optimistic / pessimistic per task).")


def print_summary(activities: dict[str, Activity]) -> None:
    """One-line summary of the network."""
    project_duration = max(a.ef for a in activities.values()) if activities else 0.0
    n_critical = sum(1 for a in activities.values() if a.is_critical)
    n_total = len(activities)
    print()
    print(LINE)
    print(f"  Tasks: {n_total}   Critical: {n_critical}   "
          f"Project duration: {_fmt(project_duration)} days")
    print(LINE)


# ===========================================================================
# Deps JSON format
# ===========================================================================

def build_deps_skeleton(tasks: list[dict]) -> dict:
    """Create a skeleton deps JSON the user can fill in."""
    skeleton: dict = {"_instructions": (
        "Fill in 'predecessors' for each task with the IDs of tasks that must "
        "complete before this one starts. Add 'pert' block for 3-point estimates "
        "(days). Leave predecessors empty [] for tasks with no dependencies."
    )}
    for t in tasks:
        skeleton[t["id"]] = {
            "name": t["name"],
            "group": t.get("group", ""),
            "duration_days": t["duration"],
            "status": t.get("status", ""),
            "start_date": t.get("start_date"),
            "end_date": t.get("end_date"),
            "predecessors": [],
            "pert": {
                "optimistic": t["duration"],
                "most_likely": t["duration"],
                "pessimistic": t["duration"],
                "_note": "Edit these values to model uncertainty. Keep most_likely = calendar duration."
            }
        }
    return skeleton


def load_pert_overrides(deps_raw: dict, task_ids: set[str]) -> dict[str, dict]:
    """Extract pert overrides from loaded deps JSON."""
    overrides = {}
    for tid in task_ids:
        entry = deps_raw.get(tid, {})
        if isinstance(entry, dict) and "pert" in entry:
            overrides[tid] = entry["pert"]
    return overrides


# ===========================================================================
# CLI commands
# ===========================================================================

def cmd_list_boards(args: argparse.Namespace) -> int:
    client = MondayClient(token=settings.monday_api_token)
    boards = list_project_boards(client)
    if not boards:
        print("No project boards found.")
        return 0

    print(f"\n{'ID':<16} {'Workspace':<25} Name")
    print(LINE)
    for b in boards:
        ws = (b.get("workspace") or {}).get("name", "-")
        print(f"{b['id']:<16} {ws:<25} {b['name']}")
    print()
    print(f"Found {len(boards)} project board(s).")
    print("Use 'export-deps <board_id>' to start building a dependency map.")
    return 0


def cmd_export_deps(args: argparse.Namespace) -> int:
    board_id = int(args.board_id)
    output_path = args.output or f"deps_{board_id}.json"

    print(f"Fetching tasks from board {board_id} ...")
    client = MondayClient(token=settings.monday_api_token)
    tasks = fetch_board_tasks(client, board_id)

    if not tasks:
        print("No active tasks found on this board.")
        return 1

    skeleton = build_deps_skeleton(tasks)
    with open(output_path, "w") as fh:
        json.dump(skeleton, fh, indent=2, default=str)

    print(f"Exported {len(tasks)} tasks to: {output_path}")
    print()
    print("Next steps:")
    print("  1. Open the JSON file and fill in 'predecessors' for each task")
    print("  2. Optionally adjust 'pert.optimistic' and 'pert.pessimistic' values")
    print(f"  3. Run: python scripts/project_optimizer.py analyze {board_id} --deps {output_path}")
    return 0


def cmd_analyze(args: argparse.Namespace) -> int:
    board_id = int(args.board_id)
    analysis = args.analysis.lower()

    print(f"\nFetching tasks from board {board_id} ...")
    client = MondayClient(token=settings.monday_api_token)
    tasks = fetch_board_tasks(client, board_id)

    if not tasks:
        print("No active tasks found on this board.")
        return 1

    task_ids = {t["id"] for t in tasks}
    print(f"Loaded {len(tasks)} active tasks.")

    # -- Dependencies --
    pert_overrides: dict[str, dict] = {}

    if args.deps:
        print(f"Loading dependency map from: {args.deps}")
        with open(args.deps) as fh:
            deps_raw = json.load(fh)
        deps = load_deps_file(args.deps, task_ids)
        pert_overrides = load_pert_overrides(deps_raw, task_ids)
    elif args.auto_deps:
        print("Auto-generating sequential dependencies within each group ...")
        deps = auto_deps_sequential(tasks)
    else:
        # no-deps: all tasks are independent
        print("No dependencies specified -- treating all tasks as independent.")
        deps = {t["id"]: [] for t in tasks}

    # -- Build network --
    print("Running PERT/CPM calculations ...")
    try:
        activities = analyze_network(tasks, deps, pert_overrides)
    except ValueError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 2

    print_selected_analysis(activities, analysis, args.target)

    print()
    return 0


def cmd_demo(args: argparse.Namespace) -> int:
    print("\nRunning built-in sample project ...")
    tasks, deps, pert_overrides = demo_project()
    try:
        activities = analyze_network(tasks, deps, pert_overrides)
    except ValueError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 2
    print(f"Loaded {len(tasks)} sample tasks.")
    print_selected_analysis(activities, args.analysis.lower(), args.target)
    print()
    return 0


def print_selected_analysis(
    activities: dict[str, Activity],
    analysis: str,
    target: float | None,
) -> None:
    """Print one or more analysis sections."""
    print_summary(activities)
    run_all = (analysis == "all")

    if run_all or analysis == "critical-path":
        print_critical_path(activities)

    if run_all or analysis == "slack":
        print_slack(activities)

    if run_all or analysis == "drag":
        print_drag(activities)

    if run_all or analysis == "fast-track":
        print_fast_track(activities)

    if run_all or analysis == "crash":
        print_crash(activities)

    if run_all or analysis == "probability":
        if target is None:
            crits = get_critical_path(activities)
            if crits:
                mean = sum(a.expected for a in crits)
                target = round(mean * 1.1, 1)  # default: 10% buffer
                print(f"\n  (Using target = {target} days -- mean + 10% buffer)")
        if target is not None:
            print_probability(activities, float(target))
        else:
            print("\n  Use --target DAYS to run probability analysis.")


def demo_project() -> tuple[list[dict], dict[str, list[str]], dict[str, dict]]:
    """Return a realistic renovation schedule with parallel paths."""
    tasks = [
        _demo_task("A", "Site survey", "Planning", 2),
        _demo_task("B", "Permit submission", "Planning", 5),
        _demo_task("C", "Procure long-lead fixtures", "Procurement", 8),
        _demo_task("D", "Demolition", "Field", 4),
        _demo_task("E", "Rough plumbing", "Field", 6),
        _demo_task("F", "Rough electrical", "Field", 5),
        _demo_task("G", "Framing repairs", "Field", 3),
        _demo_task("H", "Inspection", "Field", 2),
        _demo_task("I", "Drywall and mudding", "Finishes", 5),
        _demo_task("J", "Tile installation", "Finishes", 7),
        _demo_task("K", "Cabinet install", "Finishes", 4),
        _demo_task("L", "Final plumbing trim", "Finishes", 3),
        _demo_task("M", "Final electrical trim", "Finishes", 2),
        _demo_task("N", "Punch list", "Closeout", 2),
        _demo_task("O", "Client walkthrough", "Closeout", 1),
    ]
    deps = {
        "A": [],
        "B": ["A"],
        "C": ["A"],
        "D": ["B"],
        "E": ["D"],
        "F": ["D"],
        "G": ["D"],
        "H": ["E", "F", "G"],
        "I": ["H"],
        "J": ["I", "C"],
        "K": ["I", "C"],
        "L": ["J", "K"],
        "M": ["J", "K"],
        "N": ["L", "M"],
        "O": ["N"],
    }
    pert = {
        "A": {"optimistic": 1, "most_likely": 2, "pessimistic": 3},
        "B": {"optimistic": 3, "most_likely": 5, "pessimistic": 9},
        "C": {"optimistic": 5, "most_likely": 8, "pessimistic": 16},
        "D": {"optimistic": 3, "most_likely": 4, "pessimistic": 6},
        "E": {"optimistic": 4, "most_likely": 6, "pessimistic": 9},
        "F": {"optimistic": 3, "most_likely": 5, "pessimistic": 7},
        "G": {"optimistic": 2, "most_likely": 3, "pessimistic": 5},
        "H": {"optimistic": 1, "most_likely": 2, "pessimistic": 5},
        "I": {"optimistic": 4, "most_likely": 5, "pessimistic": 8},
        "J": {"optimistic": 5, "most_likely": 7, "pessimistic": 11},
        "K": {"optimistic": 3, "most_likely": 4, "pessimistic": 6},
        "L": {"optimistic": 2, "most_likely": 3, "pessimistic": 5},
        "M": {"optimistic": 1, "most_likely": 2, "pessimistic": 4},
        "N": {"optimistic": 1, "most_likely": 2, "pessimistic": 4},
        "O": {"optimistic": 1, "most_likely": 1, "pessimistic": 2},
    }
    return tasks, deps, pert


def _demo_task(task_id: str, name: str, group: str, duration: float) -> dict[str, Any]:
    return {
        "id": task_id,
        "name": name,
        "group": group,
        "status": "Working on it",
        "start_date": None,
        "end_date": None,
        "duration": float(duration),
    }


# ===========================================================================
# Entry point
# ===========================================================================

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="project_optimizer",
        description="PERT/CPM project analysis on Monday.com task boards",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    sub = p.add_subparsers(dest="cmd", required=True)

    demo = sub.add_parser("demo", help="Run a built-in sample project")
    demo.add_argument(
        "--analysis",
        choices=["all", "critical-path", "slack", "drag", "fast-track", "crash", "probability"],
        default="all",
        help="Which analysis to run (default: all)",
    )
    demo.add_argument(
        "--target", type=float, metavar="DAYS",
        help="Target project duration in days for probability analysis",
    )
    demo.set_defaults(func=cmd_demo)

    sub.add_parser("list-boards", help="List project boards").set_defaults(
        func=cmd_list_boards
    )

    exp = sub.add_parser(
        "export-deps",
        help="Export tasks + blank deps JSON template for a board",
    )
    exp.add_argument("board_id", help="Monday board ID")
    exp.add_argument(
        "--output", "-o",
        help="Output file path (default: deps_<board_id>.json)",
    )
    exp.set_defaults(func=cmd_export_deps)

    an = sub.add_parser("analyze", help="Run PERT/CPM analysis on a board")
    an.add_argument("board_id", help="Monday board ID")

    dep_group = an.add_mutually_exclusive_group()
    dep_group.add_argument(
        "--deps", metavar="FILE",
        help="JSON dependency file created by export-deps (fill in predecessors)",
    )
    dep_group.add_argument(
        "--auto-deps", action="store_true",
        help="Auto-chain tasks sequentially within each board group",
    )
    dep_group.add_argument(
        "--no-deps", action="store_true",
        help="Treat all tasks as independent (no dependencies)",
    )

    an.add_argument(
        "--analysis",
        choices=["all", "critical-path", "slack", "drag", "fast-track", "crash", "probability"],
        default="all",
        help="Which analysis to run (default: all)",
    )
    an.add_argument(
        "--target", type=float, metavar="DAYS",
        help="Target project duration in days for probability analysis",
    )
    an.set_defaults(func=cmd_analyze)

    return p


def main(argv: list[str] | None = None) -> int:
    import logging
    logging.basicConfig(level=logging.WARNING)
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except httpx.RequestError as e:
        print(f"ERROR: Could not reach Monday API: {e}", file=sys.stderr)
        return 3
    except RuntimeError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 3


if __name__ == "__main__":
    sys.exit(main())
