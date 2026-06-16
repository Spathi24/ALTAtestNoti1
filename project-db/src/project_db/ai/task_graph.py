"""Deterministic task graph + schedule engine.

The single source of "full temporal and spatial awareness" for a project's
tasks. Loads the hierarchy (parent/child) AND the dependency edges
(predecessor/successor) AND the dates, then answers scheduling questions
*deterministically* -- no LLM, no guessing:

  - what does this task depend on, and are those predecessors finished?
  - is this task scheduled to start before a predecessor finishes? (conflict)
  - if this task's finish date moves, which downstream tasks must move, to
    what dates, and by how many days? (the cascade)

This is the engine the LLM is *handed facts from* -- it never asks the model to
infer the graph or do date math. That keeps the schedule reasoning consistent
and reliable (the #1 priority), and matches the project invariant: the LLM
reads prose and proposes; deterministic code computes numbers.

Pure once built: ``build_task_graph(session, project_id)`` does the only I/O;
every analysis method operates on the in-memory graph.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Any

from sqlalchemy.orm import Session

from project_db.db.models import Task, TaskDependency

# Status labels (Monday) and canonical values that mean "finished".
_DONE_LABELS: frozenset[str] = frozenset({"done", "complete", "completed", "finished"})


def _is_done(status_value: str | None, monday_label: str | None) -> bool:
    if monday_label and monday_label.strip().lower() in _DONE_LABELS:
        return True
    return (status_value or "").strip().upper() == "DONE"


@dataclass
class TaskNode:
    """One task with its hierarchy + dependency links + dates."""

    id: Any
    title: str
    status: str | None
    monday_label: str | None
    start_date: date | None
    end_date: date | None
    due_date: date | None
    duration_days: float | None
    is_subitem: bool
    parent_id: Any | None
    predecessor_ids: list[Any] = field(default_factory=list)  # tasks this waits on
    successor_ids: list[Any] = field(default_factory=list)  # tasks that wait on this
    child_ids: list[Any] = field(default_factory=list)

    @property
    def done(self) -> bool:
        return _is_done(self.status, self.monday_label)

    @property
    def effective_end(self) -> date | None:
        """Best available finish date: end_date, else due_date."""
        return self.end_date or self.due_date

    @property
    def span_days(self) -> int | None:
        """Duration in days from the dates, falling back to duration_days."""
        if self.start_date and self.effective_end:
            return max((self.effective_end - self.start_date).days, 0)
        if self.duration_days is not None:
            return max(round(self.duration_days), 0)
        return None


@dataclass
class CascadeImpact:
    """One downstream task that must move if an upstream finish date shifts."""

    task_id: Any
    title: str
    old_start: date | None
    old_end: date | None
    new_start: date
    new_end: date | None
    days_pushed: int


class TaskGraph:
    """In-memory hierarchy + dependency + schedule graph for one project."""

    def __init__(self, project_id: Any, nodes: dict[Any, TaskNode]) -> None:
        self.project_id = project_id
        self.nodes = nodes

    # ----- structural accessors -----

    def get(self, task_id: Any) -> TaskNode | None:
        return self.nodes.get(task_id)

    def predecessors(self, task_id: Any) -> list[TaskNode]:
        node = self.nodes.get(task_id)
        if node is None:
            return []
        return [self.nodes[p] for p in node.predecessor_ids if p in self.nodes]

    def successors(self, task_id: Any) -> list[TaskNode]:
        node = self.nodes.get(task_id)
        if node is None:
            return []
        return [self.nodes[s] for s in node.successor_ids if s in self.nodes]

    def parent(self, task_id: Any) -> TaskNode | None:
        node = self.nodes.get(task_id)
        if node is None or node.parent_id is None:
            return None
        return self.nodes.get(node.parent_id)

    def children(self, task_id: Any) -> list[TaskNode]:
        node = self.nodes.get(task_id)
        if node is None:
            return []
        return [self.nodes[c] for c in node.child_ids if c in self.nodes]

    def roots(self) -> list[TaskNode]:
        """Top-level tasks (not subitems), in date-then-title order."""
        tops = [n for n in self.nodes.values() if not n.is_subitem]
        return sorted(tops, key=_schedule_sort_key)

    # ----- schedule analysis (deterministic) -----

    def blocking_predecessors(self, task_id: Any) -> list[TaskNode]:
        """Predecessors that are NOT finished -- this task is waiting on them."""
        return [p for p in self.predecessors(task_id) if not p.done]

    def schedule_conflicts(self, task_id: Any) -> list[tuple[TaskNode, int]]:
        """Predecessors whose finish date is AFTER this task's start date.

        Returns (predecessor, days_of_overlap). A non-empty result means the
        task is scheduled to begin before something it depends on finishes --
        a real schedule error, computed not guessed.
        """
        node = self.nodes.get(task_id)
        if node is None or node.start_date is None:
            return []
        out: list[tuple[TaskNode, int]] = []
        for p in self.predecessors(task_id):
            pend = p.effective_end
            if pend and pend > node.start_date:
                out.append((p, (pend - node.start_date).days))
        return out

    def cascade_if_end_changes(self, task_id: Any, new_end: date) -> list[CascadeImpact]:
        """If ``task_id`` now finishes on ``new_end``, which downstream tasks
        must move, to what dates, and by how many days?

        Forward finish-to-start propagation: a successor cannot start before
        its predecessor finishes. Each affected task keeps its own duration and
        shifts forward; the push ripples through the chain. Cycle-safe.
        """
        impacts: dict[Any, CascadeImpact] = {}
        # The driving task's new finish.
        seed = self.nodes.get(task_id)
        if seed is None:
            return []
        # Queue carries (task_id, finish_date_of_this_task) for the UPSTREAM
        # task whose finish we just moved; we then push its successors.
        queue: deque[tuple[Any, date]] = deque([(task_id, new_end)])
        visited: set[Any] = set()
        while queue:
            upstream_id, upstream_end = queue.popleft()
            if upstream_id in visited:
                continue
            visited.add(upstream_id)
            for succ in self.successors(upstream_id):
                if succ.start_date is None:
                    # Undated successor: we can't compute a shift, but it is
                    # still downstream -- record it with no dates so the caller
                    # can surface "this also depends, dates unknown".
                    continue
                if upstream_end <= succ.start_date:
                    continue  # no conflict, this branch stops
                new_start = upstream_end
                push = (new_start - succ.start_date).days
                span = succ.span_days
                succ_new_end = new_start + timedelta(days=span) if span is not None else None
                prior = impacts.get(succ.id)
                # Keep the LARGEST push if reached via multiple paths.
                if prior is None or push > prior.days_pushed:
                    impacts[succ.id] = CascadeImpact(
                        task_id=succ.id,
                        title=succ.title,
                        old_start=succ.start_date,
                        old_end=succ.effective_end,
                        new_start=new_start,
                        new_end=succ_new_end,
                        days_pushed=push,
                    )
                if succ_new_end is not None:
                    queue.append((succ.id, succ_new_end))
        # Stable, readable order: soonest-moved first.
        return sorted(impacts.values(), key=lambda c: (c.new_start, c.title))


def _schedule_sort_key(node: TaskNode) -> tuple:
    # Dated tasks first (by start), then undated, then by title.
    return (0, node.start_date, node.title) if node.start_date else (1, date.max, node.title)


# ---------------------------------------------------------------------------
# Renderers -- the deterministic facts handed to the LLM
# ---------------------------------------------------------------------------


def _date_range(node: TaskNode) -> str:
    s = node.start_date.isoformat() if node.start_date else "?"
    e = node.effective_end.isoformat() if node.effective_end else "?"
    if s == "?" and e == "?":
        return "no dates"
    return f"{s} -> {e}"


def _status_tag(node: TaskNode) -> str:
    return node.monday_label or node.status or "?"


def describe_task_neighborhood(graph: TaskGraph, task_id: Any) -> str:
    """Full temporal + spatial awareness for ONE task: its dates, its place in
    the hierarchy, what it is blocked by (with finish dates + whether done),
    what it blocks, and any schedule conflict -- all computed, none guessed.

    This is what the LLM is handed when a note/question concerns a task, so it
    can reason about dependencies and cascades instead of inventing them.
    """
    node = graph.get(task_id)
    if node is None:
        return "(task not found in the project graph)"

    lines = [f"TASK: {node.title} [{_status_tag(node)}] ({_date_range(node)})"]
    parent = graph.parent(task_id)
    if parent:
        lines.append(f"  part of: {parent.title} [{_status_tag(parent)}]")
    kids = graph.children(task_id)
    if kids:
        lines.append(f"  has {len(kids)} sub-task(s): " + ", ".join(k.title for k in kids[:8]))

    preds = graph.predecessors(task_id)
    if preds:
        lines.append("  BLOCKED BY (these must finish first):")
        for p in sorted(preds, key=_schedule_sort_key):
            mark = "DONE" if p.done else "NOT DONE"
            lines.append(
                f"    - {p.title} [{_status_tag(p)}] (ends {p.effective_end or '?'}) {mark}"
            )
    succs = graph.successors(task_id)
    if succs:
        lines.append("  BLOCKS (these wait on this task):")
        for sc in sorted(succs, key=_schedule_sort_key):
            lines.append(f"    - {sc.title} [{_status_tag(sc)}] (starts {sc.start_date or '?'})")

    conflicts = graph.schedule_conflicts(task_id)
    if conflicts:
        lines.append("  SCHEDULE CONFLICT (starts before a predecessor finishes):")
        for p, days in conflicts:
            lines.append(
                f"    - {p.title} ends {p.effective_end} but this starts "
                f"{node.start_date} -- {days}d overlap"
            )
    elif preds or succs:
        lines.append("  SCHEDULE CONFLICT: none detected")
    return "\n".join(lines)


def render_cascade(impacts: list[CascadeImpact]) -> str:
    """Render a deterministic cascade ('if this moves, these must move')."""
    if not impacts:
        return "No downstream tasks are affected (no dependents with dates, or no conflict)."
    lines = ["Downstream tasks that must move (finish-to-start cascade):"]
    for c in impacts:
        end = c.new_end.isoformat() if c.new_end else "?"
        lines.append(
            f"  - {c.title}: {c.old_start} -> {c.old_end}  becomes  "
            f"{c.new_start.isoformat()} -> {end}  (+{c.days_pushed}d)"
        )
    return "\n".join(lines)


def render_project_tree(graph: TaskGraph, *, max_tasks: int = 250) -> str:
    """Whole-project hierarchy + dependency block for the LLM.

    Top-level tasks in schedule order, each with its sub-tasks indented, and
    every task annotated inline with what it is blocked by / blocks. Bounded by
    ``max_tasks`` so a huge board cannot blow the context budget.
    """
    if not graph.nodes:
        return "(no tasks for this project)"
    lines: list[str] = []
    count = 0

    def emit(node: TaskNode, indent: int) -> None:
        nonlocal count
        if count >= max_tasks:
            return
        pad = "    " * indent
        ann = ""
        preds = graph.predecessors(node.id)
        if preds:
            blockers = [p.title for p in preds if not p.done]
            if blockers:
                ann = "  <- blocked by: " + ", ".join(blockers[:4])
            else:
                ann = "  <- (deps satisfied)"
        lines.append(f"{pad}[{_status_tag(node)}] {node.title} ({_date_range(node)}){ann}")
        count += 1
        for child in sorted(graph.children(node.id), key=_schedule_sort_key):
            emit(child, indent + 1)

    lines.append("=== TASK TREE (hierarchy + dependencies, schedule order) ===")
    for root in graph.roots():
        emit(root, 0)
    if count >= max_tasks:
        lines.append(f"... (truncated at {max_tasks} tasks)")
    return "\n".join(lines)


def build_task_graph(session: Session, project_id: Any) -> TaskGraph:
    """Load a project's tasks + hierarchy + dependency edges into a TaskGraph."""
    tasks = session.query(Task).filter_by(project_id=project_id).all()
    nodes: dict[Any, TaskNode] = {}
    for t in tasks:
        nodes[t.canonical_id] = TaskNode(
            id=t.canonical_id,
            title=t.title or "(untitled)",
            status=t.status.value if hasattr(t.status, "value") else (t.status or None),
            monday_label=t.monday_status_label,
            start_date=t.start_date,
            end_date=t.end_date,
            due_date=t.due_date,
            duration_days=float(t.duration_days) if t.duration_days is not None else None,
            is_subitem=bool(t.is_subitem),
            parent_id=t.parent_task_id,
        )
    # Hierarchy child links.
    for node in nodes.values():
        if node.parent_id in nodes:
            nodes[node.parent_id].child_ids.append(node.id)
    # Dependency edges (predecessor -> successor) scoped to this project's tasks.
    task_ids = set(nodes)
    edges = (
        session.query(TaskDependency).filter(TaskDependency.successor_task_id.in_(task_ids)).all()
    )
    for e in edges:
        if e.predecessor_task_id in nodes and e.successor_task_id in nodes:
            nodes[e.successor_task_id].predecessor_ids.append(e.predecessor_task_id)
            nodes[e.predecessor_task_id].successor_ids.append(e.successor_task_id)
    return TaskGraph(project_id, nodes)
