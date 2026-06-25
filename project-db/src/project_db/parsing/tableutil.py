"""Shared table heuristics for the parsers (CSV, XLSX, and later).

Real estimates do NOT put the header in row 1: they open with a title row,
company address, estimate number, and blank rows, THEN the real column header
(``Description | Notes | Material | Labour | Total``), THEN section rows and
indented sub-items. Picking row 1 as the header yields garbage. These helpers
find the real header row so values stay bound to their columns.

Header detection is a heuristic, not perfect (multi-table sheets and nested
subtotals still need richer modelling -- see EVIDENCE_REFACTOR "Struggles"), so
parsers also keep a raw ``rows_preview`` as a safety net.
"""

from __future__ import annotations


def is_formula(value: object) -> bool:
    return isinstance(value, str) and value.startswith("=")


def looks_numeric(x: object) -> bool:
    if isinstance(x, (int, float)):
        return True
    if not isinstance(x, str):
        return False
    s = x.strip().lstrip("$").replace(" ", "").replace(",", "").replace("%", "")
    if not s:
        return False
    try:
        float(s)
        return True
    except ValueError:
        return False


def looks_like_header(row: list) -> bool:
    """A header row has >=2 non-empty cells, mostly non-numeric text (column
    titles), and no formulas -- so we skip title/metadata rows above it."""
    nonempty = [c for c in row if c not in (None, "")]
    if len(nonempty) < 2 or any(is_formula(c) for c in nonempty):
        return False
    text = [c for c in nonempty if isinstance(c, str) and not looks_numeric(c)]
    return len(text) >= max(2, (len(nonempty) + 1) // 2)


def _nonempty_count(row: list) -> int:
    return sum(1 for c in row if c not in (None, ""))


def detect_header_index(rows: list[list], *, scan: int = 15) -> int:
    """Index of the most likely header row among the first *scan* rows.

    Among header-like rows we pick the one with the MOST filled cells (a real
    column header labels every column, while metadata rows like "address | Date |
    5/5/2026" fill only a few), earliest on a tie. Falls back to 0 when nothing
    looks like a header (e.g. a bare data table)."""
    best_idx, best_score = 0, -1
    for i, row in enumerate(rows[:scan]):
        if looks_like_header(row):
            score = _nonempty_count(row)
            if score > best_score:
                best_idx, best_score = i, score
    return best_idx
