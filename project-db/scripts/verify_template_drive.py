"""Verify that every QUOTE file in the mock template Drive parses correctly.

Run from repo root:
  python project-db/scripts/verify_template_drive.py

Checks per QUOTE file:
  - XlsxParser finds at least one span classified as 'quote' or with Quote_Lines sheet
  - parse_financial_grid_rows: header_found=True
  - grand_total is not None
  - At least one line item with division != 99
  - All line items belong to the correct trade division

Exit 0 = all checks pass. Exit 1 = at least one failure.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

try:
    from project_db.cli import force_utf8_output

    force_utf8_output()
except Exception:
    pass

from project_db.ai.financial_grid import parse_financial_grid_rows
from project_db.parsing.xlsx_parser import XlsxParser

REPO_ROOT = Path(__file__).parent.parent.parent
MOCK_DRIVE = REPO_ROOT / "docs" / "templates" / "mock_drive"
PROJECT_DIR = MOCK_DRIVE / "2026001 — Rockland"
QUOTE_DIR = PROJECT_DIR / "quotes"

EXPECTED = {
    "2026001_QUOTE_22-Plumbing_PlombertInc_selected.xlsx": {
        "division": "22",
        "grand_total": 6800.0,
        "min_line_items": 3,
    },
    "2026001_QUOTE_09-Finishes_ABCTile_pending.xlsx": {
        "division": "09",
        "grand_total": 21500.0,
        "min_line_items": 4,
    },
}

parser = XlsxParser()
failures = []

for p in sorted(QUOTE_DIR.glob("*.xlsx")):
    exp = EXPECTED.get(p.name)
    doc = parser.parse(
        p.read_bytes(),
        doc_name=p.name,
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )

    quote_spans = [
        s
        for s in doc.evidence_spans
        if isinstance(s.locator, dict) and s.locator.get("sheet") == "Quote_Lines"
    ]

    if not quote_spans:
        failures.append(f"FAIL {p.name}: no Quote_Lines span found")
        continue

    span = quote_spans[0]
    rows_prev = span.content_json.get("rows_preview", [])
    headers = span.content_json.get("headers", [])
    coerced = [["" if c is None else str(c) for c in r] for r in rows_prev]
    result = parse_financial_grid_rows(coerced)

    file_ok = True

    if not result.header_found:
        failures.append(f"FAIL {p.name}: header_found=False  headers={headers}")
        file_ok = False

    if result.grand_total is None:
        failures.append(f"FAIL {p.name}: grand_total=None (Pre-Tax Total row not captured)")
        file_ok = False
    elif exp and abs(float(result.grand_total) - exp["grand_total"]) > 0.01:
        failures.append(
            f"FAIL {p.name}: grand_total={result.grand_total} expected {exp['grand_total']}"
        )
        file_ok = False

    line_items = [r for r in result.rows if r.kind == "line_item"]
    if exp and len(line_items) < exp["min_line_items"]:
        failures.append(
            f"FAIL {p.name}: only {len(line_items)} line items (expected >= {exp['min_line_items']})"
        )
        file_ok = False

    if exp:
        wrong_div = [r for r in line_items if r.division_code != exp["division"]]
        if wrong_div:
            failures.append(
                f"FAIL {p.name}: {len(wrong_div)} line items in wrong division "
                f"(expected all [{exp['division']}]): "
                + ", ".join(f"[{r.division_code}] {r.description}" for r in wrong_div[:3])
            )
            file_ok = False

    status = "OK  " if file_ok else "FAIL"
    print(
        f"{status} {p.name}"
        f"  header={result.header_found}"
        f"  grand_total={result.grand_total}"
        f"  line_items={len(line_items)}"
        f"  divisions={sorted({r.division_code for r in line_items})}"
    )

if failures:
    print()
    for f in failures:
        print(f)
    sys.exit(1)

print(f"\nAll {len(EXPECTED)} QUOTE files passed.")
sys.exit(0)
