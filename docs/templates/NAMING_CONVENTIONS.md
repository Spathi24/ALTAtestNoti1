# ALTA File Naming Conventions — Project Drive

Settled 2026-06-30. These rules are machine-parseable: every token is positional
and deterministic. ALTA extracts project code, doc type, trade, vendor, and status
from the filename with zero guessing.

---

## Filename patterns

### General documents (SOW, PKG, QUOTE, GREENSHEET, BUDGET, JOBCOST, CHANGE)

```
{YYYYNNN}_{DOCTYPE}[_{DD}-{TradeName}][_{VendorSlug}][_{status}].xlsx
```

### Purchase Orders (carry the full PO number, not just project code)

```
{YYYYNNN}-{PPP}_{DOCTYPE}[_{DD}-{TradeName}][_{VendorSlug}][_{status}].xlsx
```

### Token rules

| Token | Format | Examples | Notes |
|---|---|---|---|
| `YYYYNNN` | 7 digits (year + 3-digit sequence) | `2026001` | Project code; first token always |
| `PPP` | 3 digits | `001`, `015` | PO sequence within the project |
| `DOCTYPE` | UPPERCASE abbreviation | `SOW` `PKG` `QUOTE` `GREENSHEET` `PO` `BUDGET` `JOBCOST` `CHANGE` | Always second token |
| `DD` | 2-digit CSI code (range → concatenated) | `09` `22` `1012` | `10-12` becomes `1012` |
| `TradeName` | PascalCase, no spaces | `Finishes` `Plumbing` `DoorsWindows` `Fixtures` | Always follows DD with a hyphen: `09-Finishes` |
| `VendorSlug` | CamelCase, ≤12 chars | `ABCTile` `PlombertInc` | Short recognisable abbreviation |
| `status` | lowercase | `pending` `recommended` `selected` `rejected` `awarded` `v1` `snapshot` | Version tag for SOW/BUDGET |

### Parser regex anchors

```
Project code:  ^\d{7}
PO number:     ^\d{7}-\d{3}
DOCTYPE:       _(SOW|PKG|QUOTE|GREENSHEET|PO|BUDGET|JOBCOST|CHANGE)
Trade block:   _(\d{2,4})-([A-Za-z]+)        e.g. _22-Plumbing
Vendor:        _([A-Z][A-Za-z]{1,11})_        e.g. _PlombertInc_
Status:        _(pending|recommended|selected|rejected|awarded|v\d+|snapshot)\.
```

---

## Examples

| File | Meaning |
|---|---|
| `2026001_SOW_v1.xlsx` | Scope of Work, whole project, version 1 |
| `2026001_PKG_22-Plumbing.xlsx` | Tendering package for division 22 Plumbing |
| `2026001_QUOTE_22-Plumbing_PlombertInc_pending.xlsx` | Plombert Inc. quote for plumbing, not yet evaluated |
| `2026001_QUOTE_09-Finishes_ABCTile_selected.xlsx` | ABC Tile quote for finishes, human-selected |
| `2026001_GREENSHEET.xlsx` | Green sheet (trade-comparison summary) |
| `2026001-001_PO_22-Plumbing_PlombertInc_awarded.xlsx` | PO #001, plumbing, PlombertInc, awarded |
| `2026001_BUDGET_v1.xlsx` | Budget snapshot, version 1 |
| `2026001_JOBCOST.xlsx` | Job-cost ledger (actuals + forecast) |
| `2026001_CHANGE_06-Carpentry_v1.xlsx` | Change order, carpentry trade |

---

## Normalised aliases accepted for lookup

The system also recognises and normalises legacy/informal references:

| Input | Resolves to |
|---|---|
| `2026001` / `2026-001` / `2026 001` / `Job 2026001` | project code `2026001` |
| `923 Rockland` / `Rockland` / `Tanya` / `923` | project code `2026001` |
| `2026001-001` / `2026001 001` / `PO-2026001-001` | PO number `2026001-001` |

Aliases are accepted for lookup only; they are **not** canonical. Files in Drive
must use the canonical filename pattern above so ALTA can parse them without ambiguity.

---

## Folder structure

```
{YYYYNNN} — {DisplayName}/
├── JOBCOST/
│   └── {YYYYNNN}_JOBCOST.xlsx                    cost ledger (actuals + forecast)
├── SOW/
│   ├── {YYYYNNN}_SOW_v1.xlsx                     full scope of work
│   └── packages/
│       └── {YYYYNNN}_PKG_{DD}-{TradeName}.xlsx   one per subcontractor trade
├── quotes/
│   └── {YYYYNNN}_QUOTE_{DD}-{TradeName}_{VendorSlug}_{status}.xlsx
├── green-sheet/
│   └── {YYYYNNN}_GREENSHEET.xlsx                 trade-comparison dashboard (display only)
├── POs/
│   └── {YYYYNNN}-{PPP}_PO_{DD}-{TradeName}_{VendorSlug}_awarded.xlsx
├── budget/
│   └── {YYYYNNN}_BUDGET_v1.xlsx                  frozen snapshot
└── actuals/
    └── (receipts, invoices, labour logs — filed here by PM or ALTA)
```

---

## Column-shape rules (what ALTA parses)

| DOCTYPE | Sheet to ingest | Key columns | Parser path |
|---|---|---|---|
| `QUOTE` / `PKG` | `Quote_Lines` / `Package_Lines` | `Description`, `Masterformat`, `Material Amount`, `Labour Amount`, `Total Amount` | Deterministic grid parser (primary) |
| `SOW` | `SOW_Items` | `Item_ID`, `CSI_Div_Code`, `Trade`, `Description`, `Included`, `Material_Spec` | XlsxParser → scope ingestion (Phase 3) |
| `JOBCOST` | `Cost_Ledger`, `Scope_Budget`, `Change_Orders`, `Order_Quantities` | See `Parser_Contract` sheet inside each file | XlsxParser → Cost_Ledger shape |
| `BUDGET` | `Budget_Lines` | `Line_ID`, `CSI_Div_Code`, `Trade`, `Budget_Amount`, `Line_Markup_Factor`, `Client_Price` | XlsxParser → budget ingestion (Phase 6) |
| `GREENSHEET` | — | All sheets marked Ingest=N | Display only; computed by ALTA report |
| `PO` | `PO_Header`, `PO_Lines` | `PO_Number`, `Vendor`, `Contract_Amount`, `Status`; lines have M/L/T | XlsxParser → PO ingestion (Phase 5) |

**Every file must contain a `Parser_Contract` sheet** listing which sheets ALTA
ingests (Ingest=Y) vs skips (Ingest=N). This makes every file self-describing.

### QUOTE / PO_Lines column layout rules

Column order matters — the deterministic grid parser uses first-match for each role:

```
Description | Masterformat | Material Amount | Labour Amount | Total Amount | Item_ID | Coverage_Y_N | Mat_Incl | Exclusions | Notes
```

- `Description` must be **first** (col A) — the parser maps the first "description"/"item"/"phase" hit.
- `Masterformat` (not `CSI_Div_Code`) — the parser recognises "masterformat" substring only.
- `Material Amount` must appear **before** any other column containing "material" in its name.
  Use `Mat_Incl` (not `Materials_Included`) for the Y/N flag column.
- Money columns (`Material Amount`, `Labour Amount`, `Total Amount`) must come **before** the
  auxiliary columns (`Item_ID`, `Coverage_Y_N`, etc.).

**Row structure:**

| Row | Description col | Masterformat col | Material Amount | Labour Amount | Total Amount |
|---|---|---|---|---|---|
| Section-total | Trade name (e.g. "Plumbing") | CSI code (e.g. "22") | empty | empty | trade total |
| Line items | Item description | empty or CSI code | material $ | labour $ | empty |
| Pre-Tax Total | **empty** | empty | empty | empty | grand total |

The Pre-Tax Total row **must** have an empty Description column so the grid parser routes it
to the `grand_total` field (it scans the full row for the "Pre-Tax Total" / "sous-total" label
in whichever column it appears).

---

## Status vocabulary (one everywhere)

`pending` → `recommended` → `selected` / `rejected` → `awarded`

- `pending`: collected, not yet evaluated
- `recommended`: AI-proposed via Proposal gate, awaiting human decision
- `selected`: human-approved (not yet converted to PO)
- `rejected`: not chosen
- `awarded`: PO issued

For SOW / BUDGET versioning: `v1`, `v2`, `snapshot` are allowed as the status token.
