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


def detect_header(rows: list[list], *, scan: int = 15) -> tuple[int, float]:
    """Best header-row index + a CONFIDENCE in [0,1].

    Among header-like rows we pick the one with the MOST filled cells (a real
    column header labels every column, while metadata rows like "address | Date |
    5/5/2026" fill only a few), earliest on a tie.

    The confidence is a cheap, deterministic UNCERTAINTY SIGNAL -- it is NOT a
    second guess. It is meant to be carried on the table_region span so the
    downstream extractor (Slice 6, where the LLM already runs) can RE-DERIVE the
    header from `rows_preview` when confidence is low, instead of calling the LLM
    per-file inside parsing. For PDFs this is moot -- Docling/TableFormer detects
    headers directly.
      1.0  clear winner, >=3 labelled columns, strictly beats the runner-up
      0.8  >=2 labelled columns, strictly beats the runner-up
      0.5  a tie (two rows equally header-like) -- genuinely ambiguous
      0.3  nothing looked like a header (fell back to row 0)
    """
    scored = [
        (i, _nonempty_count(row)) for i, row in enumerate(rows[:scan]) if looks_like_header(row)
    ]
    if not scored:
        return 0, 0.3
    scored.sort(key=lambda x: (-x[1], x[0]))
    best_idx, best_score = scored[0]
    runner_up = scored[1][1] if len(scored) > 1 else 0
    if best_score <= runner_up:
        conf = 0.5
    elif best_score >= 3:
        conf = 1.0
    else:
        conf = 0.8
    return best_idx, conf


def detect_header_index(rows: list[list], *, scan: int = 15) -> int:
    """Back-compat: the header index only (see `detect_header` for confidence)."""
    return detect_header(rows, scan=scan)[0]
