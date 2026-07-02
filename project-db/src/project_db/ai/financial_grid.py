"""Deterministic parser for OUR structured financial sheets (Phase 1 of
docs/FINANCIAL_REDESIGN). NO LLM.

Reads the CSV/TSV cell grid of an own-authored quote/extras sheet, finds the
header row (a metadata block usually sits above it), maps the money columns by
role (Material / Labour / Total) plus the MasterFormat hint column, then walks
the data rows emitting:

  - ``division_total`` rows  -- a section subtotal (Total column filled, no
    material/labour; section name in col 0), tagged to a CSI division;
  - ``line_item`` rows       -- material and/or labour amounts, inheriting the
    current section's division.

Grand-total / summary rows (Pre-Tax / After-Tax: col-0 blank, label in another
column) are EXCLUDED from the rows and captured separately for cross-checking.

Grounded in the real 923 Rockland ACCEPTED QUOTE grid: the emitted
``division_total`` rows reconcile to the stated Pre-Tax total ($66,539.65) to
the penny. Fail-safe: an unrecognised layout yields ``header_found=False`` +
a warning (caller falls back to the LLM populator), never a crash.
"""

from __future__ import annotations

import csv
import io
import re
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation

from project_db.ai.financial_divisions import UNCLASSIFIED, classify_division

# Summary/grand-total labels (these rows are NOT divisions -- exclude them).
_PRETAX_RE = re.compile(r"pre.?tax|sub.?total|grand", re.I)
_AFTERTAX_RE = re.compile(r"after.?tax", re.I)
# amount_type detection for section rows.
_CONTINGENCY_RE = re.compile(r"conting", re.I)
_MARKUP_RE = re.compile(r"\b(ohp|overhead|profit|o&p|markup)\b", re.I)
_TAX_RE = re.compile(r"\b(tax|tps|tvq|gst|qst|hst)\b", re.I)
_MONEY_RE = re.compile(r"^-?\d+(\.\d+)?$")


# --- document-type routing (classify BEFORE you parse) ----------------------
# Checked in THIS order (a doc may carry several markers; the most specific
# layout wins). Markers are matched against the filename + the first few rows.
_EXTRAS_MARKERS = ("extras", "change order", "co #", "co#")
_JOBCOST_MARKERS = ("material spending", "job cost", "job costing", "costing", "spending")
_ORDER_MARKERS = ("order quantities", "qty per pack", "door order", "order sheet")
_QUOTE_MARKERS = ("accepted quote", "estimate", "quote")

# Document types this layer understands. Only ``quote`` routes to the grid
# parser today; the others have their own (future) extractors -- see
# docs/FINANCIAL_REDESIGN.md. ``unknown`` is left for the LLM populator.
FINANCIAL_SHEET_TYPES = {"quote", "extras", "job_cost", "order_quantities", "unknown"}

# Regex matching the '### SheetName' headers emitted by extract_xlsx.
_SHEET_BLOCK_RE = re.compile(r"^### (.+)$", re.MULTILINE)


def split_workbook_sheets(text: str) -> list[tuple[str | None, str]]:
    """Split xlsx-extracted text into (sheet_name, sheet_text) pairs.

    The xlsx extractor prefixes each worksheet block with '### SheetName'.
    If no such markers are found (PDF, DOCX, CSV, or true single-sheet xlsx),
    returns [(None, text)] so callers treat the whole text as one sheet.

    The '(further sheets omitted)' pseudo-header terminates the split — no
    content after that truncation marker is processed.
    """
    if not text:
        return [(None, "")]
    markers = list(_SHEET_BLOCK_RE.finditer(text))
    if not markers:
        return [(None, text)]

    sheets: list[tuple[str | None, str]] = []
    for i, m in enumerate(markers):
        sheet_name = m.group(1).strip()
        # Stop at the extractor's truncation pseudo-header
        # ("(further sheets omitted -- workbook too large)").  Match the marker
        # text, not a leading "(" -- a real worksheet may legitimately be named
        # "(2024) Budget" and must not be mistaken for the truncation sentinel.
        if "sheets omitted" in sheet_name.lower():
            break
        start = m.end()
        end = markers[i + 1].start() if i + 1 < len(markers) else len(text)
        sheet_text = text[start:end].strip()
        sheets.append((sheet_name, sheet_text))

    return sheets or [(None, text)]


def classify_financial_sheet(name: str | None, text: str | None) -> str:
    """Route a financial sheet to its layout type, deterministically.

    Uses the filename + the first rows (where the banner like "ESTIMATE" /
    "MATERIAL SPENDING" lives). More specific layouts are tested first so an
    "EXTRAS ACCEPTED" sheet routes to ``extras`` (not ``quote`` via "accepted").
    Returns one of ``FINANCIAL_SHEET_TYPES``; never raises.
    """
    name_l = (name or "").lower()
    head = "\n".join((text or "").splitlines()[:8]).lower()
    blob = f"{name_l} || {head}"
    if any(m in blob for m in _EXTRAS_MARKERS):
        return "extras"
    if any(m in blob for m in _JOBCOST_MARKERS):
        return "job_cost"
    if any(m in blob for m in _ORDER_MARKERS):
        return "order_quantities"
    if any(m in blob for m in _QUOTE_MARKERS):
        return "quote"
    return "unknown"


@dataclass
class ParsedGridRow:
    """One amount pulled from the grid, ready to become a FinancialLineItem."""

    kind: str  # "division_total" | "line_item"
    division_code: str
    division_name: str
    amount_type: str  # total | material | labour | markup | contingency | tax
    amount: Decimal
    description: str
    masterformat_hint: str = ""
    # Structural join key back to a SowItem (Quote_Lines.SOW_Item_Ref, e.g.
    # "SOW-025"). Empty when the sheet has no such column or the cell is blank.
    # Phase 4 resolves this to FinancialLineItem.sow_item_id; NEVER parsed from
    # free text.
    sow_item_ref: str = ""


@dataclass
class GridParseResult:
    rows: list[ParsedGridRow] = field(default_factory=list)
    grand_total: Decimal | None = None  # stated Pre-Tax total (cross-check)
    after_tax_total: Decimal | None = None
    header_found: bool = False
    warnings: list[str] = field(default_factory=list)

    @property
    def division_total(self) -> Decimal:
        """Sum of the section subtotals -- should equal ``grand_total``."""
        return sum((r.amount for r in self.rows if r.kind == "division_total"), Decimal(0))


def parse_money(cell: object) -> Decimal | None:
    """Locale-tolerant money cell -> Decimal, or None if not a number.

    Handles ``$1,000.00`` / ``1 000,00`` is NOT expected here (these are
    EN-format sheets), parentheses-negatives, $, commas, and nbsp.
    """
    if cell is None:
        return None
    s = str(cell).strip()
    if not s:
        return None
    neg = s.startswith("(") and s.endswith(")")
    s = s.strip("()").replace("$", "").replace(",", "")
    s = "".join(s.split())  # drop all whitespace incl. NBSP
    if not _MONEY_RE.match(s):
        return None
    try:
        val = Decimal(s)
    except InvalidOperation:
        return None
    return -val if neg else val


def _amount_type_for(description: str) -> str:
    if _CONTINGENCY_RE.search(description):
        return "contingency"
    if _MARKUP_RE.search(description):
        return "markup"
    if _TAX_RE.search(description):
        return "tax"
    return "total"


def _map_columns(header_cells: list[str]) -> dict[str, int]:
    """Map a detected header row to column roles by keyword."""
    col: dict[str, int] = {}
    for idx, raw in enumerate(header_cells):
        name = (raw or "").strip().lower()
        if not name:
            continue
        if "material" in name:
            col.setdefault("material", idx)
        elif "labour" in name or "labor" in name:
            col.setdefault("labour", idx)
        elif "total" in name:
            col.setdefault("total", idx)
        # SOW_Item_Ref MUST be tested before the description branch: its
        # lowercased name "sow_item_ref" contains "item", which would otherwise
        # be swallowed by the description rule.
        elif "sow" in name and ("ref" in name or "item" in name):
            col.setdefault("sow_item_ref", idx)
        elif "master format" in name or "masterformat" in name or name.startswith("notes"):
            col.setdefault("masterformat", idx)
        elif "description" in name or "item" in name or "phase" in name:
            col.setdefault("description", idx)
    return col


def _looks_like_header(cells: list[str]) -> bool:
    """True only for the QUOTE tri-amount header (a Material column AND a Total
    Amount column).

    Deliberately strict: job-cost / material-spending sheets carry "Material
    Budget" / "Cost" / "Labour budget" but NOT a "Total Amount" column, so this
    keeps them from false-matching (the JOB COSTING garbage-extraction bug).
    Routing is owned by ``classify_financial_sheet``; this is the parser's own
    safety net for when it is handed the wrong layout.
    """
    joined = " | ".join(c.strip().lower() for c in cells)
    return "material" in joined and "total amount" in joined


def _detect_delimiter(text: str) -> str:
    """Tab for xlsx (``extract_xlsx`` emits TSV) vs comma for CSV/Sheets export.

    They never mix in one document, so a simple tab-vs-comma count over the head
    of the text is reliable.
    """
    head = "\n".join(text.splitlines()[:40])
    return "\t" if head.count("\t") > head.count(",") else ","


def parse_financial_grid(text: str | None) -> GridParseResult:
    """Parse an own-authored Material/Labour/Total quote grid.

    Accepts either CSV (Google-Sheet export) or TSV (xlsx export) -- the
    delimiter is sniffed. Intended to be called only on sheets that
    ``classify_financial_sheet`` tagged ``quote``; the strict header check is a
    secondary guard so a mis-route degrades to ``header_found=False`` rather
    than emitting garbage rows.
    """
    result = GridParseResult()
    if not text or not text.strip():
        result.warnings.append("empty document text")
        return result

    rows = list(csv.reader(io.StringIO(text), delimiter=_detect_delimiter(text)))
    return parse_financial_grid_rows(rows)


def parse_financial_grid_rows(rows: list[list[str]]) -> GridParseResult:
    """Parse an already-split cell grid (rows of string cells).

    This is the core walker shared by ``parse_financial_grid`` (which splits CSV/
    TSV text first) and the evidence-backed path, which feeds the structured
    ``EvidenceSpan`` row grid directly -- so the grid ledger reads the same parsed
    cells as the rest of the evidence spine instead of re-parsing document text.
    """
    result = GridParseResult()
    if not rows:
        result.warnings.append("empty grid")
        return result

    header_idx = next((i for i, r in enumerate(rows) if _looks_like_header(r)), None)
    if header_idx is None:
        result.warnings.append("no Material/Labour/Total header row found")
        return result
    result.header_found = True

    col = _map_columns(rows[header_idx])
    col.setdefault("description", 0)
    desc_i = col["description"]
    mat_i, lab_i, tot_i, mf_i, sow_i = (
        col.get("material"),
        col.get("labour"),
        col.get("total"),
        col.get("masterformat"),
        col.get("sow_item_ref"),
    )

    def cell(row: list[str], i: int | None) -> str:
        return row[i].strip() if (i is not None and i < len(row)) else ""

    current = UNCLASSIFIED
    for row in rows[header_idx + 1 :]:
        if not any((c or "").strip() for c in row):
            continue
        desc = cell(row, desc_i)
        mf = cell(row, mf_i)
        sow_ref = cell(row, sow_i)
        material = parse_money(cell(row, mat_i))
        labour = parse_money(cell(row, lab_i))
        total = parse_money(cell(row, tot_i))

        # 1. Line item: carries material and/or labour. Inherit current section.
        if material is not None or labour is not None:
            line_desc = desc or mf  # continuation rows put the desc in col 1
            if material is not None:
                result.rows.append(
                    ParsedGridRow(
                        "line_item",
                        current.code,
                        current.name,
                        "material",
                        material,
                        line_desc,
                        mf,
                        sow_ref,
                    )
                )
            if labour is not None:
                result.rows.append(
                    ParsedGridRow(
                        "line_item",
                        current.code,
                        current.name,
                        "labour",
                        labour,
                        line_desc,
                        mf,
                        sow_ref,
                    )
                )
            continue

        # 2. A Total-only row.
        if total is not None:
            if not desc:
                # Grand-total / summary row (label sits in another column).
                joined = " ".join(c or "" for c in row)
                if _AFTERTAX_RE.search(joined):
                    result.after_tax_total = total
                elif _PRETAX_RE.search(joined):
                    result.grand_total = total
                continue  # never a division
            # Section subtotal -> a division total (or contingency / OHP / tax).
            div = classify_division(desc, masterformat_hint=mf)
            current = div
            result.rows.append(
                ParsedGridRow(
                    "division_total",
                    div.code,
                    div.name,
                    _amount_type_for(desc),
                    total,
                    desc,
                    mf,
                )
            )
            continue
        # 3. No money (blank row, or an unpriced material name) -> skip.

    return result
