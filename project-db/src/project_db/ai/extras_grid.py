"""Deterministic parser for own-authored EXTRAS / change-order sheets (Phase 1c-MVP).

Layout target:
    CO # | Item | Cost/Unit | Applied | Total | Status

These are client-facing change orders — additional scope agreed with the
client AFTER the base quote was signed.  All valid rows are ``side=revenue``.
The parser NEVER touches FinancialRecord or the old financial layer.

Amount semantics:
  - Accepted extras → side=revenue, status=accepted, amount_type=adjustment
  - Proposed extras → side=revenue, status=proposed, amount_type=adjustment
  - Rejected / Not-Accepted / Cancelled rows → excluded (returned as skipped_rows)
  - Rows with no parseable Total → skipped silently

The parser is pure (no DB, no LLM, no side effects). The populator in
``financial_grid_populator.py`` calls it and writes FinancialLineItem rows.

Double-count safety: extras live in separate source documents from the base
quote, so the (unit, division_code, side) deduplication in
``report_division_margins`` treats each document's rows independently.  A
``division_total`` row from the base quote + an ``adjustment`` row from the extras
sheet for the same division are BOTH counted (they represent different scope
items, not the same number twice).
"""

from __future__ import annotations

import csv
import io
import re
import unicodedata
from dataclasses import dataclass, field
from decimal import Decimal

from project_db.ai.financial_divisions import classify_division
from project_db.ai.financial_grid import parse_money


def _strip_accents(s: str) -> str:
    """Fold diacritics so Quebec-French status/header cells match unaccented
    patterns ('Accepté' -> 'accepte', 'État' -> 'etat'). NFD-decompose, then
    drop combining marks. Idempotent on already-ASCII text (a no-op for EN)."""
    return "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")


# ---------------------------------------------------------------------------
# Status classification (bilingual EN/FR -- this is a Quebec dataset).
# Inputs are accent-folded before matching, so French patterns are written
# unaccented (e.g. 'accepte' matches 'accepté').  REJECTED is checked first so
# 'non accepté' is rejected even though it also contains the 'accepte' stem.
# ---------------------------------------------------------------------------

_ACCEPTED_RE = re.compile(
    r"\baccepted\b|\baccepte(e|s|es)?\b"  # accepted / accepté(e)(s)
    r"|\bapproved\b|\bapprouve(e|s|es)?\b"  # approved / approuvé(e)(s)
    r"|\bdone\b|\bcomplet\w*\b"  # done / complete(d) / complété(e)
    r"|\bfait\b|\brealise(e|s|es)?\b"  # fait / réalisé(e)
    r"|\btermine(e|s|es)?\b",  # terminé(e)(s) -- not EN 'terminated'
    re.I,
)
_PROPOSED_RE = re.compile(
    r"\bproposed?\b|\bpropose(e|s|es)?\b"  # proposed / proposé(e)(s)
    r"|\bnot\s+started\b|\bpending\b|\bin\s+progress\b"
    r"|\ben\s+cours\b|\ben\s+attente\b"  # in progress / pending (FR)
    r"|\bquoted\b|\bdevis\b|\bsoumis(e|es)?\b|\bopen\b",  # quoted / devis / soumis
    re.I,
)
_REJECTED_RE = re.compile(
    r"\bnot\s+accepted\b|\bnon\s+accepte(e|s|es)?\b"  # not accepted / non accepté
    r"|\brejected\b|\brejete(e|s|es)?\b|\brefus\w*\b"  # rejected / rejeté / refusé
    r"|\bcancell?ed\b|\bannul\w*\b"  # cancelled / annulé
    r"|\bvoided?\b|\babandonn\w*\b|\bn/?a\b",  # void / abandonné / n/a
    re.I,
)


def _classify_status(raw: str | None) -> str | None:
    """Return 'accepted', 'proposed', or None (= skip row) for an extras status cell."""
    s = _strip_accents((raw or "").strip())
    if not s:
        return "unknown"
    if _REJECTED_RE.search(s):
        return None  # caller should skip this row
    if _ACCEPTED_RE.search(s):
        return "accepted"
    if _PROPOSED_RE.search(s):
        return "proposed"
    return "unknown"


# ---------------------------------------------------------------------------
# Header detection
# ---------------------------------------------------------------------------

# Must find at least one of these to confirm it's an extras/CO sheet.
# Header cells are accent-folded + lowercased before matching (Quebec FR).
_CO_HEADER_MARKERS = ("co", "change order", "change #", "co #", "co#", "no co")
_TOTAL_HEADER_MARKERS = ("total",)
_STATUS_HEADER_MARKERS = ("status", "statut", "etat")


def _looks_like_extras_header(cells: list[str]) -> bool:
    joined = _strip_accents(" | ".join(c.strip().lower() for c in cells))
    has_co = any(m in joined for m in _CO_HEADER_MARKERS)
    has_total = any(m in joined for m in _TOTAL_HEADER_MARKERS)
    has_status = any(m in joined for m in _STATUS_HEADER_MARKERS)
    return has_co and has_total and has_status


def _map_extras_columns(header_cells: list[str]) -> dict[str, int]:
    col: dict[str, int] = {}
    for idx, raw in enumerate(header_cells):
        name = _strip_accents((raw or "").strip().lower())
        if not name:
            continue
        if "co" == name or "co #" in name or "co#" in name or "no co" in name or "change" in name:
            col.setdefault("co_number", idx)
        elif (
            "item" in name
            or "description" in name
            or "scope" in name
            or "work" in name
            or "travaux" in name  # FR: works
            or "designation" in name  # FR: désignation
        ):
            col.setdefault("description", idx)
        elif "total" in name and "cost" not in name:
            col.setdefault("total", idx)
        elif "cost" in name and "unit" in name:
            col.setdefault("cost_per_unit", idx)
        elif "status" in name or "statut" in name or "etat" in name:
            col.setdefault("status", idx)
        elif "applied" in name or "qty" in name or "quantity" in name:
            col.setdefault("applied", idx)
    return col


# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------


@dataclass
class ExtrasRow:
    """One accepted or proposed change-order line."""

    co_number: str  # CO identifier (string, may be "1", "CO-3", etc.)
    description: str  # Item description used for division classification
    total: Decimal  # Total amount for this CO (from Total column)
    status: str  # accepted | proposed | unknown
    division_code: str
    division_name: str


@dataclass
class ExtrasParseResult:
    rows: list[ExtrasRow] = field(default_factory=list)
    skipped_rows: int = 0  # rejected/cancelled/no-amount rows
    header_found: bool = False
    accepted_total: Decimal = Decimal(0)
    proposed_total: Decimal = Decimal(0)
    warnings: list[str] = field(default_factory=list)

    def accepted_rows(self) -> list[ExtrasRow]:
        return [r for r in self.rows if r.status == "accepted"]

    def proposed_rows(self) -> list[ExtrasRow]:
        return [r for r in self.rows if r.status == "proposed"]


# ---------------------------------------------------------------------------
# Parser
# ---------------------------------------------------------------------------

_HEADER_SEARCH_DEPTH = 10  # rows to scan before giving up on header


def _detect_delimiter(text: str) -> str:
    head = "\n".join(text.splitlines()[:20])
    return "\t" if head.count("\t") > head.count(",") else ","


def parse_extras_sheet(text: str | None) -> ExtrasParseResult:
    """Parse an EXTRAS/change-order sheet into a list of ExtrasRow objects.

    Accepts CSV (Google-Sheet export) or TSV (xlsx export).  Never raises —
    unrecognised layouts return ``header_found=False`` with a warning.

    The caller (``populate_ledger_for_document``) is responsible for filtering
    the sheet type via ``classify_financial_sheet`` BEFORE calling this function.
    This parser still validates the header as a second-line safety net.
    """
    result = ExtrasParseResult()
    if not text or not text.strip():
        result.warnings.append("empty document text")
        return result

    delimiter = _detect_delimiter(text)
    all_rows = list(csv.reader(io.StringIO(text), delimiter=delimiter))

    # Find the header row
    header_idx = None
    for i, row in enumerate(all_rows[:_HEADER_SEARCH_DEPTH]):
        if _looks_like_extras_header(row):
            header_idx = i
            break

    if header_idx is None:
        result.warnings.append(
            "no CO/Item/Total/Status header found — not an extras sheet or layout differs"
        )
        return result

    result.header_found = True
    col = _map_extras_columns(all_rows[header_idx])

    # Fallback column positions if header mapping is incomplete
    if "description" not in col:
        col["description"] = 1  # Item is usually col 1
    if "total" not in col:
        # Try to find the last numeric-looking column
        result.warnings.append("no clear Total column found; guessing from position")
        col["total"] = len(all_rows[header_idx]) - 2  # before status

    def _cell(row: list[str], key: str, default: int = 0) -> str:
        idx = col.get(key, default)
        return row[idx].strip() if idx < len(row) else ""

    for row_idx, row in enumerate(all_rows[header_idx + 1 :], start=header_idx + 1):
        if not any((c or "").strip() for c in row):
            continue  # blank row

        co_raw = _cell(row, "co_number", 0)
        desc = _cell(row, "description", 1)
        total_raw = _cell(row, "total", len(col) - 2 if len(col) > 1 else 4)
        status_raw = _cell(row, "status", len(col) - 1 if col else 5)

        total = parse_money(total_raw)
        if total is None or total == Decimal(0):
            result.skipped_rows += 1
            continue

        status = _classify_status(status_raw)
        if status is None:
            # Rejected / cancelled / not accepted — exclude
            result.skipped_rows += 1
            continue

        combined = f"{co_raw} {desc}".strip()
        div = classify_division(combined)

        extras_row = ExtrasRow(
            co_number=co_raw,
            description=desc or co_raw,
            total=total,
            status=status,
            division_code=div.code,
            division_name=div.name,
        )
        result.rows.append(extras_row)

        if status == "accepted":
            result.accepted_total += total
        elif status == "proposed":
            result.proposed_total += total

    if not result.rows and result.header_found:
        result.warnings.append("header found but no parseable money rows (empty or all rejected)")

    return result
