"""Deterministic project Gantt -- server-rendered SVG, no LLM, no JS, no build.

Renders a project's task graph (hierarchy + dates + dependency edges, from
``ai/task_graph``) as a single inline SVG: one indented row per task, a bar
positioned by its start/end dates, status colour, dependency connector arrows
between dated tasks, and a "today" marker. Undated tasks still get a row (so
the hierarchy is always visible) with a "no dates" marker -- which doubles as a
prompt to fill the schedule in.

Pure: ``render_project_gantt_svg(graph)`` is graph -> SVG string, so it is
fully testable without a browser. Colours use the page's CSS variables where
possible and fall back to fixed hexes, so it reads on light or dark themes.
"""

from __future__ import annotations

from datetime import date
from html import escape
from typing import Any

from project_db.ai.task_graph import TaskGraph, TaskNode

# ---- layout constants ------------------------------------------------------
_LABEL_W = 300  # left column for task names
_ROW_H = 26
_BAR_H = 14
_HEADER_H = 46
_PAD = 14
_MIN_PXPD = 6  # px per day floor
_MAX_PXPD = 26  # px per day ceiling
_TARGET_TIMELINE_W = 900
_INDENT = 16  # px per hierarchy level

# Status -> bar fill. Keys are lowercased Monday labels / canonical values.
_STATUS_FILL: dict[str, str] = {
    "done": "#2e7d32",
    "complete": "#2e7d32",
    "completed": "#2e7d32",
    "working on it": "#1565c0",
    "in progress": "#1565c0",
    "in_progress": "#1565c0",
    "stuck": "#c62828",
    "blocked": "#c62828",
    "on hold": "#ef6c00",
    "todo": "#78909c",
    "future steps": "#90a4ae",
}
_DEFAULT_FILL = "#607d8b"


def _fill(node: TaskNode) -> str:
    key = (node.monday_label or node.status or "").strip().lower()
    return _STATUS_FILL.get(key, _DEFAULT_FILL)


def _row_sort_key(node: TaskNode) -> tuple:
    return (0, node.start_date, node.title) if node.start_date else (1, date.max, node.title)


def _ordered_rows(graph: TaskGraph) -> list[tuple[TaskNode, int]]:
    """Tasks in tree order (root, then its sub-tasks), each with its depth."""
    rows: list[tuple[TaskNode, int]] = []
    seen: set[Any] = set()

    def walk(node: TaskNode, depth: int) -> None:
        if node.id in seen:
            return
        seen.add(node.id)
        rows.append((node, depth))
        for child in sorted(graph.children(node.id), key=_row_sort_key):
            walk(child, depth + 1)

    for root in graph.roots():
        walk(root, 0)
    # Defensive: include any orphan node not reached via roots (shouldn't happen).
    for node in graph.nodes.values():
        if node.id not in seen:
            rows.append((node, 0))
    return rows


def render_project_gantt_svg(graph: TaskGraph, *, today: date | None = None) -> str:
    """Render the project's task graph as an inline SVG string."""
    if today is None:
        today = date.today()
    rows = _ordered_rows(graph)
    if not rows:
        return (
            '<svg xmlns="http://www.w3.org/2000/svg" width="400" height="60" '
            'role="img"><text x="12" y="34" font-family="sans-serif" '
            'font-size="14">No tasks for this project.</text></svg>'
        )

    all_dates = [d for node, _ in rows for d in (node.start_date, node.effective_end) if d]
    has_timeline = bool(all_dates)
    if has_timeline:
        min_d, max_d = min(all_dates), max(all_dates)
        span = max((max_d - min_d).days, 1)
        pxpd = min(max(_TARGET_TIMELINE_W / span, _MIN_PXPD), _MAX_PXPD)
        timeline_w = int(span * pxpd) + 2 * _PAD
    else:
        min_d = max_d = today
        span, pxpd, timeline_w = 1, _MIN_PXPD, 240

    width = _LABEL_W + timeline_w + 24
    height = _HEADER_H + len(rows) * _ROW_H + _PAD

    def x_of(d: date) -> float:
        return _LABEL_W + _PAD + (d - min_d).days * pxpd

    def row_y(i: int) -> int:
        return _HEADER_H + i * _ROW_H

    row_index: dict[Any, int] = {node.id: i for i, (node, _) in enumerate(rows)}

    parts: list[str] = []
    parts.append(
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}" role="img" '
        f'font-family="system-ui, sans-serif" font-size="12">'
    )
    # Arrowhead marker for dependency connectors.
    parts.append(
        '<defs><marker id="dep-arrow" markerWidth="7" markerHeight="7" refX="6" '
        'refY="3" orient="auto"><path d="M0,0 L6,3 L0,6 Z" fill="#b08900"/>'
        "</marker></defs>"
    )
    # Background of the timeline area. currentColor + low opacity so it reads as
    # a faint shade on BOTH light and dark themes (the SVG inherits the page's
    # text color, which Pico flips per color-scheme).
    parts.append(
        f'<rect x="{_LABEL_W}" y="0" width="{width - _LABEL_W}" height="{height}" '
        'fill="currentColor" opacity="0.04"/>'
    )

    # ---- time axis: month gridlines + labels ----
    if has_timeline:
        cur = date(min_d.year, min_d.month, 1)
        while cur <= max_d:
            if cur >= min_d:
                gx = x_of(cur)
                parts.append(
                    f'<line x1="{gx:.1f}" y1="{_HEADER_H - 6}" x2="{gx:.1f}" '
                    f'y2="{height}" stroke="currentColor" stroke-opacity="0.12" '
                    'stroke-width="1"/>'
                )
                parts.append(
                    f'<text x="{gx + 3:.1f}" y="20" fill="currentColor" opacity="0.65" '
                    f'font-size="11">{cur.strftime("%b %Y")}</text>'
                )
            # advance one month
            cur = date(cur.year + (cur.month // 12), (cur.month % 12) + 1, 1)

        # "today" marker
        if min_d <= today <= max_d:
            tx = x_of(today)
            parts.append(
                f'<line x1="{tx:.1f}" y1="{_HEADER_H - 6}" x2="{tx:.1f}" y2="{height}" '
                'stroke="#c62828" stroke-width="1.5" stroke-dasharray="3,2"/>'
            )
            parts.append(
                f'<text x="{tx + 3:.1f}" y="{_HEADER_H - 8}" fill="#c62828" '
                'font-size="10">today</text>'
            )

    # ---- dependency connectors (drawn under the bars' labels, over the grid) ----
    for node, _ in rows:
        succ_i = row_index.get(node.id)
        if succ_i is None or node.start_date is None:
            continue
        sx = x_of(node.start_date)
        sy = row_y(succ_i) + _ROW_H // 2
        for pred in graph.predecessors(node.id):
            if pred.effective_end is None or pred.id not in row_index:
                continue
            px = x_of(pred.effective_end)
            py = row_y(row_index[pred.id]) + _ROW_H // 2
            midx = max(px, sx - 10)
            parts.append(
                f'<path d="M{px:.1f},{py} H{midx + 6:.1f} V{sy} H{sx - 2:.1f}" '
                'fill="none" stroke="#b08900" stroke-width="1.2" '
                'marker-end="url(#dep-arrow)" opacity="0.8"/>'
            )

    # ---- task rows: label + bar ----
    for i, (node, depth) in enumerate(rows):
        y = row_y(i)
        cy = y + _ROW_H // 2
        # zebra striping
        if i % 2 == 0:
            parts.append(
                f'<rect x="0" y="{y}" width="{width}" height="{_ROW_H}" '
                'fill="currentColor" opacity="0.035"/>'
            )
        label = escape(node.title[:46])
        indent = 6 + depth * _INDENT
        weight = "600" if depth == 0 else "400"
        parts.append(
            f'<text x="{indent}" y="{cy + 4}" font-weight="{weight}" fill="currentColor">'
            f"{label}</text>"
        )
        # bar (only when dated)
        if node.start_date and node.effective_end:
            bx = x_of(node.start_date)
            bw = max((node.effective_end - node.start_date).days * pxpd, 3)
            by = y + (_ROW_H - _BAR_H) // 2
            tip = escape(
                f"{node.title} | {node.start_date} -> {node.effective_end} "
                f"| {node.monday_label or node.status or '?'}"
            )
            parts.append(
                f'<rect x="{bx:.1f}" y="{by}" width="{bw:.1f}" height="{_BAR_H}" '
                f'rx="3" fill="{_fill(node)}"><title>{tip}</title></rect>'
            )
        elif has_timeline:
            parts.append(
                f'<text x="{_LABEL_W + _PAD}" y="{cy + 4}" fill="currentColor" '
                'opacity="0.5" font-size="11" font-style="italic">no dates</text>'
            )

    parts.append("</svg>")
    return "".join(parts)
