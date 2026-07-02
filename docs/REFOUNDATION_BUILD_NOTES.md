# Refoundation — Build Blueprint (preliminary context for the next instance)

Companion to `docs/MEETING_SYNTHESIS_financial_refoundation.md` (the plan; READ IT
FIRST). This maps the plan's new entities onto **exactly where and how** they slot
into the current repo, so a fresh instance with less context can execute precisely
**once the conventions in plan §12 are settled with the owner**. This is a map, not
code — nothing here is built yet, by design (the working practices / SOP conventions
come before heavy implementation).

> Status 2026-06-26: evidence refactor Slices 1–8 COMPLETE, parser capped.
> **§12 conventions SETTLED 2026-06-30. Phase 1 mock Drive COMPLETE + owner-approved 2026-07-02.**
> Build phases below. Follow in order. One slice per prompt.

---

## Permanent semantic rules (do not violate in any phase)

These are not preferences — they are correctness invariants. Getting them wrong
destroys trust in the financial output.

**1. cost_status lifecycle (the most important rule):**
```
QUOTE file ingested                → FinancialLineItem.cost_status = "quoted"
Quote marked selected (human)      → SubcontractorQuote.status = "selected"
                                     FinancialLineItem.cost_status stays "quoted"
PO issued / awarded                → FinancialLineItem.cost_status = "committed"
                                     ContractObligation emitted
Invoice / receipt posted           → FinancialLineItem.cost_status = "actual"
```
Selected quote = *intent*. PO = *legal/financial commitment*. Never skip this chain.

**2. Division-total rows are control rows, not aggregatable cost rows:**
`division_total` rows (amount_type="total") are stored in FinancialLineItem but routed
to a separate "total" bucket in views.py — NEVER summed with material/labour amounts.
This is already correct in code. Any new aggregation (BudgetSnapshot, green-sheet report,
variance view) must apply the same filter: aggregate ONLY `amount_type IN ("material",
"labour")` for actual money; use "total" rows only as cross-checks/reconciliation.
Storing both section totals and line items is intentional; the filter is the guard.

**3. Project.code IS the project_code — no separate column needed (LOCKED 2026-07-02):**
`docs/MEETING_SYNTHESIS_financial_refoundation.md` names the settled concept
`project_code` (format `YYYYNNN`). The implementation field for that concept is
the existing `Project.code` column (nullable String, already present before
Phase 2) — this is a deliberate, accepted naming deviation, not an oversight:

```
Spec name:      project_code
Actual column:  project.code
Meaning:        the same concept — the human-assigned YYYYNNN job code
```

This binds every phase from here on:
- `Project.code` is read/written everywhere the plan says `project_code`
  (resolver, QuickBooks matching, PO numbering in Phase 5, reports, UI).
- **No second `project_code` column is ever added** unless there is an
  explicit, intentional migration/rename decision recorded here first.
- Any future code (including Phase 3+) that needs "the operational project
  code" reads `Project.code` — do not reintroduce ambiguity by naming a new
  field, parameter, or JSON key `project_code` that isn't literally `.code`.

**4. Phase 2 does NOT solve Drive attribution:**
Attribution remains folder-ancestry-based (ExternalId `folder:{folder_id}`) until
filename-first routing is explicitly implemented. After Phase 2, the statement
"project attribution is reliable" is STILL FALSE for files with ambiguous folder paths.
Only after filename/code extraction is wired into the Drive connector will it be true.

**5. Markup is presentation-layer, never storage-layer:**
`FinancialLineItem.amount` = internal cost only. `line_markup_factor` and the global
1.15 are applied at report-render time for client-facing outputs. Never store
already-inflated amounts as ledger values.

**6. SOW_Item_Ref must be a structural column, not a Notes substring:**
Quote_Lines needs a `SOW_Item_Ref` column (to be added in Phase 3 template regeneration).
`Notes` containing "per SOW-025" is human-readable, not a machine join key. The
`sow_item_id` FK on FinancialLineItem must be set from a proper column, not NLP parsing.

**7. GreenSheet is a computed report, never a table:**
No `GreenSheet` or `GreenSheetLine` model. The green-sheet is a view/report function
that queries BudgetSnapshot, SubcontractorQuote, PurchaseOrder, ContractObligation, and
FinancialLineItem with the correct `cost_status` and `amount_type` filters.

---

---

## Build phases (ordered — do not skip ahead)

**Phase 1 — Mock template Drive** `docs/templates/mock_drive/` ← **CURRENT, patched 2026-06-30**
Files + naming convention + template .xlsx (SOW, PKG, QUOTE, GREENSHEET, PO, BUDGET,
JOBCOST). No schema/model/migration code. Owner must approve templates before Phase 2.
Verify: XlsxParser reads every data sheet → clean table, correct headers, real values.
Gold standard to mirror: `docs/JOB_COST_TEMPLATE_structured.xlsx` (owner-built).
**The mock `2026001_JOBCOST.xlsx` is a pilot-scale demo, NOT a replacement for the gold
standard** — see `docs/templates/NAMING_CONVENTIONS.md` "JOBCOST: gold-standard template
is canonical" section. Production rule: copy `JOB_COST_TEMPLATE_structured.xlsx` per
project as `{project_code}_JOBCOST.xlsx`, use its own `Parser_Contract`.
Patches applied 2026-06-30: fixed BUDGET README `#NAME?` formula-text cells; renamed
plumbing QUOTE to `_selected` (was inconsistent with its `awarded` PO); fixed Greensheet
plumbing status to `awarded` to match; documented Quote_Lines control rows (section-total
+ Pre-Tax Total) explicitly in each file's Parser_Contract Notes.

**Phase 2 — Project code migration** (additive, no rename of existing id/hash) ← **CURRENT**
`Project.code` already exists (nullable String). Phase 2 POPULATES it with YYYYNNN format.
Do NOT add a column named `project_code` — `code` IS the project code.
New columns only: +display_name +legacy_job_number +aliases (JSON Text).
Wire via `_add_missing_columns` for "project" table. Add partial unique index on code.
Extend `_resolve_project` in views.py: match by code exact + aliases JSON-contains.
Assign code='2026001', display_name='2026001 — Rockland', legacy_job_number='923',
aliases='["Rockland","Tanya","923 Rockland","923-927 Rockland"]' to pilot project
(query by name, never by hardcoded UUID). Tests. Manual DB verify. Commit.

**Phase 3 — SowItem + SowPackage models**
New `db/models/sow.py`. Migration in FK order (SowPackage before SowItem). Tests. Commit.

**Phase 4 — SubcontractorQuote + FinancialLineItem extensions**
SubcontractorQuote model in `db/models/finance.py`; status vocab pending/recommended/
selected/rejected/awarded; evidence_span_id FK reused. Extend FinancialLineItem:
+purchase_type +cost_status +sow_item_id +line_markup_factor. Tests. Commit.

**Phase 5 — PurchaseOrder → ContractObligation**
PurchaseOrder in `db/models/finance.py`; auto po_number (YYYYNNN-PPP); emits
ContractObligation on award. Tests. Commit.

**Phase 6 — BudgetSnapshot + green-sheet report + variance view**
BudgetSnapshot model; green sheet report fn in `ai/`; variable-cost tolerance flags
wired into ledger-health. Tests. Commit. Demo: owner sees real-vs-quoted on pilot.

---

---

## Working practices (how we build this — agreed posture)

1. **Structure & traceability over prediction.** Every cost traces SOW item →
   package → quote → PO → budget line → actual. The Alta-number estimator (plan §11)
   is parked until ~20–50 clean projects produce takeoff-quantity inputs + actuals.
2. **Additive, slice-by-slice, on the pilot (923 Rockland).** Each step ships
   something usable; keep the suite green; lint before continuing; one dedicated
   plan+state doc per initiative (this file + the meeting doc).
3. **LLM is an advisor → `Proposal` gate.** Quote selection, side classification,
   anomaly flags are AI-advisory; a human decides. Never auto-mutate the ledger.
4. **Flag, never silently sort.** Anything the system can't place → surfaces for a
   human (reuse `Proposal` + `ReconciliationIssue` + ledger-health). Already the
   pattern of Slice 8.
5. **Deterministic-first.** With templated SOP inputs the deterministic grid parser
   is the PRIMARY path; the evidence/LLM tolerance (Docling/XlsxParser/LLM) is the
   FALLBACK for legacy + third-party/supplier docs. Don't expand tolerance as primary.
6. **The value is the line-item material/labour split**, not aggregate totals
   (totals already live in the sheets; the per-trade breakdown feeds the pipeline).

---

## Invariants that bind any new code (do not violate)

- **SOW = contract boundary.** Inside SOW → original contract price. Outside SOW →
  a tracked `ChangeOrder` (what/why/trade/added cost/added time/approval). Never
  silently absorbed into the budget.
- **Material spec is part of scope** (drives material+labour assumption); store it
  on the SOW item.
- **Client never sees internal numbers.** Client estimate = budget + markup; the
  real numbers never leak. Two number sets.
- **Takeoff (quantities) vs site-visit (conditions/risk) stay SEPARATE.** Takeoff →
  estimator inputs; site-visit → exclusions/contingency, not clean quantities.
- **Cross-doc rollups must not double-count.** A SOW restating its accepted quote is
  the SAME money (the Rockland $66,539.65 × 2 = the bogus $361k). Slice 8's
  `detect_duplicate_total_issues` already flags this; new aggregation must respect it.
- **One status vocabulary** (pending/selected/rejected/awarded …) — a deterministic
  read, never guessed. The "accepted/verified/1/2/3" guessing is retired by SOP.

---

## Entity → repo mapping (build order follows plan §10)

Legend: **NEW** model · **EXTEND** existing · **VIEW** (computed, no table) · **REUSE**.

§12 conventions settled 2026-06-30 — blocking questions are now resolved. See
`docs/MEETING_SYNTHESIS_financial_refoundation.md §12` for full detail.

| Entity | Action | Where | Key fields | FK / reuse | §12 status |
|---|---|---|---|---|---|
| `Project.project_code` | EXTEND | `db/models/work.py` + migration `_add_missing_columns` | `project_code` YYYYNNN, `display_name`, `legacy_job_number`, `aliases` (JSON) | internal hash/id unchanged; Drive attribution updates to project_code | ✓ format settled (#7) |
| `SowItem` | NEW | `db/models/` new `sow.py` | description, `division_code` (CSI), `included` bool, `material_spec` (JSON), `package_id`, optional `sow_item_id` FK on FinancialLineItem | → Project, → SowPackage; CSI vocab in `ai/financial_divisions.py` | ✓ granularity settled (#5): SowItem coarser than FinancialLineItem |
| `SowPackage` | NEW | `db/models/sow.py` | trade/`division_code`, drawings/notes refs, status | → Project; has many SowItem | ✓ |
| `SubcontractorQuote` | NEW | `db/models/finance.py` (near ledger) | vendor_id, package_id, amount, coverage, exclusions, assumptions, materials_incl, quote_date, `status` (pending/recommended/selected/rejected/awarded), **`evidence_span_id`** | → SowPackage, → Vendor, **→ EvidenceSpan (already built)** | ✓ status vocab + selection rule settled (#3) |
| Green sheet | VIEW | `ai/` report fn | per trade-line: Alta vs quotes vs selected vs actual | computed over FinancialLineItem + SubcontractorQuote | ✓ |
| `BudgetSnapshot` (+lines) | NEW | `db/models/finance.py` | frozen targets per line/unit; immutable; carries markup metadata | → Project, → FinancialLineItem | ✓ markup model settled (#2): line factor × 1.15 global |
| `PurchaseOrder` | NEW | `db/models/finance.py` | `project_code`, `po_number` (YYYYNNN-PPP, auto), package_id, vendor_id, `trade_type`, `purchase_type`, `contract_amount`, terms, budget_line_id, status | → SowPackage, → Vendor; **emits ContractObligation** | ✓ PO↔obligation settled (#4) |
| `ChangeOrder` | NEW | generalize `ai/extras_grid.py` → `db/models/` | what changed, why-not-original, trade/package, added_cost, added_time, client_approval_status | → Project, → SowItem/package | ✓ |
| `FinancialLineItem.purchase_type` | EXTEND | `db/models/finance.py` + migration | enum: vendor/supplier/home_depot/hourly/transportation | — | ✓ |
| `FinancialLineItem.cost_status` | EXTEND | `db/models/finance.py` + migration | enum: estimated/quoted/committed/actual | — | ✓ |
| `FinancialLineItem.sow_item_id` | EXTEND | `db/models/finance.py` + migration | nullable FK → SowItem | — | ✓ |
| `FinancialLineItem.line_markup_factor` | EXTEND | `db/models/finance.py` + migration | float, default 1.0; client price = internal × factor; subtotal × 1.15 = final | — | ✓ markup model (#2) |
| Variable cost tolerance flags | LOGIC | `ai/` or ledger-health | warn > 3% / > 1 wk; hard > 5% / > 2 wk; mandatory job code on HD/labour | reuse ledger-health surface | ✓ thresholds settled (#6) |
| Quote-vs-actual variance | VIEW | `ai/` report fn | diffs across cost_status columns per line | computed | ✓ |
| Alta-number estimator | PARKED | `ai/` (later) | regularized least squares (plan §11) | inputs = takeoff quantities (NEW capture); targets = actuals via POs/variance | needs §11 data (~20–50 clean projects) |

**Reuse as-is (do not rebuild):** 13-entity core + `ExternalId`; `Project` join
nucleus; evidence spine `DocumentParse`/`EvidenceSpan` (+ `evidence_span_id` already
on FinancialLineItem / grid rows / obligations) — this is the provenance layer for
`SubcontractorQuote`; CSI vocab `ai/financial_divisions.py`; deterministic grid
parser (`financial_grid.parse_financial_grid_rows`) + populator; `homedepot` spine
(purchase type 3); Telegram/labour intake (type 4); `Proposal` gate;
`ReconciliationIssue` (Slice 8) for flagging; `Vendor.payment_terms`.

---

## Migration discipline reminder (so the next instance doesn't trip)

Every new table needs BOTH a SQLAlchemy model (for `create_all`) AND a DDL block
wired into `db/migrations.py::ensure_sqlite_schema` in FK-dependency order; export
it from `db/models/__init__.py` (`__all__` is RUF022-sorted). New nullable columns
on an existing table → add to the model AND the table's `_add_missing_columns`
dict AND (for consistency) the CREATE DDL. Apply to the real DB by invoking
`ensure_sqlite_schema(get_engine())`. The real `project_db.sqlite` only gets new
tables when the migration is invoked.

## First build step when unblocked (plan §10.3, pilot 923 Rockland)

SOW → packages → SubcontractorQuote on the pilot: read the templated SOW + per-trade
quotes into `SowItem` / `SowPackage` / `SubcontractorQuote` (+ `FinancialLineItem`),
compare by **coverage not just price**, mark one `selected`, freeze a `BudgetSnapshot`.
Reuse the grid parser + CSI vocab + the evidence links already in place. Gate of done:
owner/PM opens ALTA (not Drive) to see real-vs-quoted per trade + spend vs budget on
the pilot, it's right, and they come back next week unprompted.

---

## PARKED — Drive Write Capability (gated, NOT started, no automatic mutation)

Recorded 2026-06-30 as a future option, not a commitment. Only relevant if the owner
decides ALTA should construct/reorganize the real project Drive automatically from
parsed project data, instead of the team manually copying templates into folders.
**This requires an explicit owner decision before any code is written.** Do not start
on this without that decision, and do not let it block or distract from Phases 2–6.

If undertaken, build in this strict order — each step is a hard gate on the next:

1. **Read-only Drive audit** — scan real Drive folders/filenames, report against
   `NAMING_CONVENTIONS.md`. No writes.
2. **Proposed folder/filename migration plan** — a diff-style plan (current → proposed
   path), surfaced for human review. No writes.
3. **Dry-run output** — simulate the plan, log what would happen, byte-for-byte
   preview of new files where applicable. No writes.
4. **Human approval** — explicit per-project or per-batch sign-off before anything
   touches the real Drive. Reuse the `Proposal` gate pattern already in place.
5. **Copy-first write mode** — new/reorganized files are written as copies; existing
   files are never moved or deleted in this phase.
6. **Operation log and rollback manifest** — every write logged with enough detail
   to reverse it; no destructive operation without a corresponding rollback path.

No direct Drive mutation happens before step 4 (human approval) on every run, every
time — this is not a one-time approval that unlocks future autonomous writes.
