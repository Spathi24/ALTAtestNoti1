"""Deterministic parser for the two Home Depot Pro Excel exports.

The site emits two shapes, distinguished by their header row:

* **transactions** -- ``Sales Date | Transaction Number | Purchase Location |
  Job Name | Status | Purchaser | Subtotal | Total``
* **details** -- ``Sales Date | Transaction Number | Purchase Location |
  SKU Number | Product Name | Quantity | Unit Price | Subtotal``

Both are auto-detected from the header. Money is parsed defensively (``$``,
parentheses-negatives, trailing-minus, and either ``.`` or ``,`` as the decimal
mark -- Quebec exports have been seen both ways), dates are day-first
(``DD/MM/YYYY``), and every parsed row keeps its untouched values under
``_raw`` so nothing is lost. No arithmetic happens here.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

import openpyxl

# Normalized header label -> canonical field name. Header cells in the real
# exports carry leading spaces ("` Transaction Number`"), so we strip+lower
# before lookup.
_HEADER_MAP = {
    "sales date": "sales_date",
    "transaction number": "transaction_number",
    "purchase location": "purchase_location",
    "job name": "job_name",
    "status": "status",
    "purchaser": "purchaser",
    "subtotal": "subtotal",
    "total": "total",
    "sku number": "sku",
    "sku": "sku",
    "product name": "product_name",
    "quantity": "quantity",
    "unit price": "unit_price",
}

_TRANSACTION_FIELDS = {"job_name", "total", "status", "purchaser"}
_DETAIL_FIELDS = {"sku", "product_name", "quantity", "unit_price"}


class HomeDepotParseError(RuntimeError):
    """Raised when an Excel file is not a recognizable Home Depot export."""


@dataclass
class ParsedExport:
    """The result of parsing one export file."""

    kind: str  # "transactions" | "details"
    rows: list[dict[str, Any]] = field(default_factory=list)
    source_file: str | None = None

    def __len__(self) -> int:
        return len(self.rows)


def _normalize_header(value: Any) -> str:
    return str(value or "").strip().lower()


def parse_money(raw: Any) -> Decimal | None:
    """Parse a money cell to Decimal. Returns None for blank/unparseable.

    Handles ``$``, thin/non-breaking spaces, ``(123.45)`` and trailing-``-``
    negatives, and ``.``-or-``,`` decimal marks.
    """
    if raw is None:
        return None
    if isinstance(raw, bool):  # guard: bool is an int subclass
        return None
    if isinstance(raw, (int, float, Decimal)):
        return Decimal(str(raw))

    s = str(raw).strip()
    if not s:
        return None

    neg = False
    if s.startswith("(") and s.endswith(")"):
        neg = True
        s = s[1:-1]
    # Strip the currency symbol and any whitespace (regular, NBSP, narrow
    # NBSP, thin) that locale formatting injects as a thousands separator.
    s = re.sub(r"[\s$]", "", s)
    if s.endswith("-"):
        neg = True
        s = s[:-1]
    if s.startswith("-"):
        neg = True
        s = s[1:]
    if not s:
        return None

    if "," in s and "." in s:
        # The rightmost separator is the decimal mark.
        if s.rfind(",") > s.rfind("."):
            s = s.replace(".", "").replace(",", ".")
        else:
            s = s.replace(",", "")
    elif "," in s:
        intpart, _, frac = s.rpartition(",")
        # "1,50" -> decimal; "1,500" -> thousands.
        if len(frac) == 2 and intpart.replace(".", "").isdigit():
            s = f"{intpart}.{frac}"
        else:
            s = s.replace(",", "")

    try:
        value = Decimal(s)
    except InvalidOperation:
        return None
    return -value if neg else value


def parse_quantity(raw: Any) -> Decimal | None:
    """Parse a quantity cell (integer or fractional) to Decimal."""
    return parse_money(raw)  # same numeric tolerance, no currency symbol expected


def parse_date(raw: Any) -> date | None:
    """Parse a Home Depot date cell. Day-first (DD/MM/YYYY) for QC exports."""
    if raw is None:
        return None
    if isinstance(raw, datetime):
        return raw.date()
    if isinstance(raw, date):
        return raw
    s = str(raw).strip()
    if not s:
        return None
    for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%m/%d/%Y", "%d-%m-%Y"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    return None


def detect_format(headers: list[str]) -> str | None:
    """Return 'transactions' | 'details' | None from a header row."""
    mapped = {_HEADER_MAP[h] for h in (_normalize_header(x) for x in headers) if h in _HEADER_MAP}
    if _DETAIL_FIELDS & mapped:
        return "details"
    if _TRANSACTION_FIELDS & mapped:
        return "transactions"
    return None


def parse_export(path: str | Path) -> ParsedExport:
    """Parse a Home Depot Pro Excel export into a ``ParsedExport``.

    Raises ``HomeDepotParseError`` if the file has no recognizable header.
    """
    path = Path(path)
    wb = openpyxl.load_workbook(path, data_only=True, read_only=True)
    try:
        ws = wb.worksheets[0]
        rows_iter = ws.iter_rows(values_only=True)
        try:
            header_row = next(rows_iter)
        except StopIteration as exc:
            raise HomeDepotParseError(f"{path.name}: empty worksheet") from exc

        headers = [_normalize_header(c) for c in header_row]
        kind = detect_format(list(header_row))
        if kind is None:
            raise HomeDepotParseError(
                f"{path.name}: unrecognized export -- header was {list(header_row)!r}"
            )

        # Position -> canonical field. Unknown columns are dropped from the
        # typed view but preserved in _raw.
        col_field = {i: _HEADER_MAP[h] for i, h in enumerate(headers) if h in _HEADER_MAP}

        out: list[dict[str, Any]] = []
        for raw_row in rows_iter:
            if raw_row is None or all(c is None or str(c).strip() == "" for c in raw_row):
                continue
            record: dict[str, Any] = {"_raw": {}}
            for i, value in enumerate(raw_row):
                field_name = col_field.get(i)
                if field_name is None:
                    continue
                record["_raw"][field_name] = value
                if field_name in ("subtotal", "total", "unit_price"):
                    record[field_name] = parse_money(value)
                elif field_name == "quantity":
                    record[field_name] = parse_quantity(value)
                elif field_name == "sales_date":
                    record[field_name] = parse_date(value)
                else:
                    record[field_name] = str(value).strip() if value is not None else None

            # A row with no transaction number is unusable noise.
            if not record.get("transaction_number"):
                continue
            out.append(record)
    finally:
        wb.close()

    return ParsedExport(kind=kind, rows=out, source_file=path.name)
