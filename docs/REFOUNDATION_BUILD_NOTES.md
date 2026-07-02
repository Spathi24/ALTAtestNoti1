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

**Phase 3 — SowItem + SowPackage models** ✓ COMPLETE 2026-07-02
New `db/models/sow.py`: `SowPackage` (per-trade tendering package) + `SowItem` (one
scope line; deliberately coarser than `FinancialLineItem` — Phase 4 links many
line items back to one SowItem via `sow_item_id`, not built yet). Migration DDL
in FK order (`sow_package` before `sow_item`) wired into `ensure_sqlite_schema`.
Exported from `db/models/__init__.py`. 13 tests (schema creation, ALTER-TABLE
path, project/package linkage, included/excluded scope, material_spec JSON
persistence, item_code uniqueness scoped to project+package (not global), no
ledger mutation). `SowItem.package_id` is nullable — division 01 (General
Requirements) items are GC overhead with no subcontractor package, a real state
surfaced while populating real data, not an oversight.
Mock-drive `Quote_Lines` regenerated with a structural `SOW_Item_Ref` column
(e.g. `SOW-025`) replacing the old "per SOW-025" text buried in `Notes` —
`verify_template_drive.py` still passes both QUOTE files.
Manually verified against the real DB: Rockland (`code=2026001`) populated from
the same already-approved mock `SOW_ITEMS` list (not new/fabricated data) — 11
packages, 31 items, 3 correctly package-less General Requirements items, all
division codes match the trade table. No `FinancialLineItem` row created —
Phase 3 touches no ledger table. Full suite 1581 passed.
**Uniqueness correction (2026-07-02, post-review):** `SowItem.item_code` uniqueness
changed from `(project_id, package_id, item_code)` to a project-scoped **partial
unique index** `uq_sow_item_project_item_code ON sow_item (project_id, item_code)
WHERE item_code IS NOT NULL` — in the model `__table_args__` (so `create_all`
produces it for tests, which use `create_all` without the migration) **and** the
migration DDL (for existing DBs). Reason: `SOW_Item_Ref` on a quote line carries
only `SOW-025` with no package context, so the code must resolve to exactly one
scope item per project; and the nullable `package_id` (div-01) made the old
package-scoped constraint leak (NULLs compare distinct). Tests updated: same code
in two packages of one project now REJECTED; same code across two projects allowed;
duplicate null-package code rejected. Suite 1583.

**Phase 4 — SubcontractorQuote + FinancialLineItem extensions** ✓ COMPLETE 2026-07-02
`SubcontractorQuote` in `db/models/finance.py` (project/package/vendor/document/
evidence_span links; status pending/recommended/selected/rejected/awarded;
amount/coverage/exclusions/assumptions/materials_included/quote_date). Extended
`FinancialLineItem`: +purchase_type +cost_status +sow_item_id(FK) +line_markup_factor.
New `ai/subcontractor_quote_ingest.py` — a SEPARATE cost-quote path (did NOT bend
`_collect_quote_rows`, which stays revenue-only). Reuses the spine:
build_evidence_bundle → picks the quote grid table by money-column signature
(ignores the Parser_Contract metadata sheet — a real gap the single-span test
missed, caught by running the real 2-sheet file) → parse_financial_grid_rows →
resolves SOW_Item_Ref against SowItem.item_code (project-scoped). Cost rows are
`side=cost`, `cost_status=quoted`, `purchase_type=vendor`; division_total rows are
NOT written (grand_total is a reconcile cross-check only) so the material/labour
split is preserved and nothing double-counts. Unresolved/missing SOW refs are
FLAGGED (warnings + source_meta), never silently assigned. Parser gap fixed:
`_map_columns`+`ParsedGridRow` now carry `sow_item_ref` (tested before the
description branch so "item" in "sow_item_ref" isn't swallowed). Migration: new
table + 4 `_add_missing_columns` on financial_line_item; fresh + existing DB both
work. 17 tests. Manually verified on the REAL Rockland DB by parsing the actual
mock Plumbing xlsx through the real XlsxParser: 1 SubcontractorQuote (Plombert,
div 22, selected, $6800, evidence-linked), 6 cost rows → SOW-025/026/027,
sum=$6800=grand_total (no 2x), 0 total rows, 0 committed. **NO PurchaseOrder, NO
ContractObligation, NO BudgetSnapshot, NO green-sheet built; selected quote stays
`cost_status=quoted` — commitment is Phase 5.** Full suite 1600.
Known small gaps (recorded, not blocking): FinancialLineItem has no
`subcontractor_quote_id` FK (spec listed only 4 columns) — quote↔line association
is via shared `document_id`; quote-level coverage/assumptions columns exist but are
only best-effort populated (exclusions/materials_included from cells); package/
vendor resolution is caller-supplied, not yet auto-resolved from the filename.

**Owner review 2026-07-02 (post-Phase-4): reuse verdict = accepted, not spaghetti.**
The core distinction to keep enforcing: reusing *generic* structures (EvidenceSpan,
DocumentParse, FinancialLineItem, Vendor, ReconciliationIssue, Proposal, the
deterministic grid parser) is correct and intended by the plan. Reusing/bending
*revenue-specific* logic (`_collect_quote_rows`, the `total`-wins-over-`items`
dedup in `report_project_financials`, the old accepted/proposed status meaning)
is NOT — Phase 4 correctly built a separate cost-side path instead. **The
spaghetti failure mode to actively prevent:** `financial_grid.py` starting to do
SOW DB lookups, `financial_grid_populator.py` special-casing vendor quotes,
`views.py` "correcting" ingestion mistakes, `docs.py` deciding selected/awarded
semantics, or the same entity being created from multiple unrelated code paths.
One ingestion path per entity; identity/resolution logic stays out of parsers.

**Recorded design decisions for Phase 5 (answered before implementation, per
owner request — not yet coded):**
1. **`FinancialLineItem.subcontractor_quote_id` FK:** not added in Phase 4 (spec
   listed exactly 4 columns). Add it in Phase 5 alongside `PurchaseOrder` — by
   then there are three things a cost row can trace to (quote / PO / actual) and
   a direct FK is worth the schema churn once, not twice.
2. **Idempotent delete scope (documented hardening, not urgent):**
   `subcontractor_quote_ingest.ingest_subcontractor_quote` currently deletes ALL
   `FinancialLineItem` rows for the `document_id` before re-inserting. Fine while
   one document → one extractor. Narrow to
   `filter_by(document_id=..., extractor_version="subquote-v1")` before any
   second extractor (e.g. a future LLM fallback) can touch the same document —
   otherwise one extractor's re-run could silently delete another's rows.
3. **Filename → package/vendor resolution:** stays OUT of the ingester (which
   only takes `project_id`/`package_id`/`vendor_id` as caller-supplied args —
   correct, keep it that way). Phase 5 adds a small resolver/router *above* the
   ingester — parses `{YYYYNNN}_QUOTE_{DD}-{TradeName}_{VendorSlug}_{status}.xlsx`
   per `NAMING_CONVENTIONS.md`, looks up `SowPackage` by `division_code` and
   `Vendor` by name (reuse `ExactFieldMatcher`-style matching, do not invent a
   new fuzzy matcher). Lives in its own small module, not inside
   `financial_grid.py` or `subcontractor_quote_ingest.py`.
4. **PO award → committed conversion:** Phase 5's `PurchaseOrder` model gets
   awarded from a `selected` `SubcontractorQuote` by an explicit human/Proposal-
   gated action, never automatically. On award: (a) `SubcontractorQuote.status`
   → `awarded` (the quote row itself is never deleted or rewritten — award is a
   status transition, quote history stays intact); (b) the cost `FinancialLineItem`
   rows already linked to that quote's `document_id` get `cost_status` →
   `committed` (an UPDATE, not a delete+reinsert — the SOW linkage and amounts
   must not change, only the lifecycle field); (c) a new `ContractObligation` row
   is emitted per PO. This must NOT be built inside
   `subcontractor_quote_ingest.py` — it belongs in a Phase 5 PO-conversion
   function that reads `SubcontractorQuote` + writes `PurchaseOrder` +
   `ContractObligation`, one direction only.

**Phase 5 — PurchaseOrder → ContractObligation** ✓ COMPLETE 2026-07-02
`PurchaseOrder` in `db/models/finance.py`: `subcontractor_quote_id` (NOT NULL,
UNIQUE — one PO per quote, a re-award attempt fails at the DB level, not
silently re-issued), `po_number` auto-generated `{project.code}-{PPP}`
sequential per project, `project_id`/`package_id`/`vendor_id` denormalized from
the quote, `status` (`awarded`/`cancelled`), `contract_amount`/`currency`/
`awarded_date`/`terms`. Added `FinancialLineItem.subcontractor_quote_id` FK
(per the recorded Phase-5 decision #1) so a cost row traces to the quote that
priced it — Phase 4's ingester now stamps it at creation.
New `ai/purchase_order_award.award_purchase_order(session, quote, ...)` — the
ONE place that creates committed cost. Refuses to award anything but a
`status="selected"` quote (`PurchaseOrderAwardError`, not a silent no-op).
Effects, all in place, never delete+reinsert: (a) `SubcontractorQuote.status`
→ `awarded` on the same row — quote history/coverage/evidence survives; (b)
every `FinancialLineItem` row linked via `subcontractor_quote_id` gets
`cost_status` → `committed` by UPDATE, isolated to exactly this quote's rows
(verified: awarding one quote never touches another quote's rows, even in the
same project); (c) exactly one `ContractObligation` emitted
(`kind="po_commitment"` — added to `OBLIGATION_KINDS`, `direction="owed_by_us"`),
citing the quote's `evidence_span_id`. 14 tests: schema (fresh + migrated),
the full award sequence, sequential PO numbering (per-project, not global),
guards (pending/rejected/already-awarded quotes rejected; duplicate award
rejected at the DB unique-constraint level even if the status guard is
bypassed), isolation between quotes. Full suite 1614.
Manually verified on the REAL Rockland DB, chained onto Phase 4's real parse:
ingested the actual mock Plumbing quote, then awarded it — `po_number
2026001-001`, quote flipped to `awarded` in place (same `canonical_id`, amount
unchanged), 6 cost rows flipped `quoted`→`committed` with sum still `$6800`
(no drift/duplication), 1 `ContractObligation` (`po_commitment`, owed_by_us,
`$6800`, counterparty "Plombert Inc."), 0 committed rows outside this quote.
Rolled back — real DB unchanged.
Deliberately NOT built: filename→package/vendor auto-resolution (Phase-5
decision #3, still open — `award_purchase_order` takes an already-resolved
`SubcontractorQuote` object, no filename parsing here); BudgetSnapshot;
green-sheet report/UI (both Phase 6).

**Checkpoint 2026-07-02: freeze-and-map audit + 2 hardening guards.**
Read-only audit of the full chain (`Project → SowPackage → SowItem →
SubcontractorQuote → FinancialLineItem → PurchaseOrder → ContractObligation`)
before Phase 6, confirmed against the live DB (all 7 tables exist; the FKs,
unique indexes, and `code`→PO-prefix link all verified by `PRAGMA` inspection).
Two findings from the audit:
- **FK enforcement:** globally ON via `session.py`'s `event.listens_for(Engine,
  "connect")` (`PRAGMA foreign_keys=ON`), for prod and test connections alike.
  BUT `financial_line_item.sow_item_id`/`subcontractor_quote_id` are not
  *declared* FKs on the real DB (added via bare `ALTER TABLE ADD COLUMN`, no
  `REFERENCES`) — so referential integrity there is application-level only,
  even though fresh test DBs (via `create_all`) get the real constraint. A
  false-confidence gap: tests can pass against a constraint production doesn't
  enforce.
- **A pre-existing, separate cost-side ledger exists**: 79 real
  `financial_line_item` rows with `side='cost', cost_status=NULL` from an
  older LLM extractor (`source='llm', extractor_version='llm-v1'`,
  `doc_role` in estimate/expense/**invoice** — 68 of the 79 are invoices).
  This predates the Phase 4/5 `cost_status` lifecycle entirely. **Binding
  rule for any future green-sheet/aggregator: filter cost rows with an
  explicit `cost_status IN ('quoted','committed','actual')` ALLOW-list, never
  an exclusion pattern** (`cost_status != 'actual'` would wrongly pull in all
  79 of these). Also: Phase 6's "actuals ingestion" isn't starting from a
  blank page — an LLM invoice-extraction path already exists.
  **DECIDED (2026-07-02): keep it separate from the deterministic PO-actuals
  path, do not unify.** Follows the plan's own settled rule
  ("deterministic-first... LLM is the FALLBACK for legacy/third-party docs").
  A future PO-actuals matcher should structurally match invoices to a known
  PO (number/vendor/amount) and flip *that* PO's linked rows to `actual`;
  `llm-v1` rows stay `cost_status=NULL` (not auto-promoted to `actual`)
  unless/until positively matched to a PO. This is why the allow-list
  treats `NULL` as actual for now — it's covering the legacy extractor's
  output, not blessing it as the permanent actuals mechanism.

Two guards added to `ai/purchase_order_award.py` as a result (owner-approved,
scoped hardening only, no new feature surface):
1. `award_purchase_order` now refuses to award a quote with zero
   `FinancialLineItem` rows at `cost_status='quoted'` (raises
   `PurchaseOrderAwardError` before creating anything) — prevents a PO +
   `ContractObligation` recording real dollars with nothing backing them in
   the ledger.
2. The commit-to-`committed` UPDATE is now scoped to `cost_status='quoted'`
   rows only (was: every row linked via `subcontractor_quote_id`,
   unconditionally). Defense-in-depth — no path today produces a
   quote-linked row in any other state, but a future one can no longer be
   silently overwritten by an award.
2 new tests (`test_zero_quoted_lines_refused`,
`test_only_quoted_status_lines_are_committed`) + the existing DB-uniqueness
test reworked to bypass both guards deliberately (proving the DB constraint
is still a real backstop, not just a duplicate of the application guard).
Full suite 1616. Real-DB verification re-run after the change — identical
clean result to the original Phase 5 verification, confirming the guards
don't affect the correct happy path.
Not fixed (still recorded, not urgent): the idempotent-delete scope in
`subcontractor_quote_ingest.py` (Phase 4 known gap); `ContractObligation` has
no FK to `PurchaseOrder` (link lives in `source_meta_json` only); PO
numbering (`_next_po_number`) is a read-then-increment, not
concurrency-safe.

**Checkpoint follow-up 2026-07-02: `report_division_margins` cost_status
allow-list.** The checkpoint's live-report grep found this pre-existing
function (wired to `/projects/{id}/margins`, a CLI command, and the askbot's
`REPORT_REGISTRY` — genuinely live, on 6 real projects with `side='cost'`
data today) summed `side='cost'` rows into `actual_*_cost` with **zero**
`cost_status` awareness — its own comment said *"Cost rows are always
actuals, so status does not gate them,"* a pre-Phase-4/5 assumption now
false. Fixed with the same allow-list rule already recorded (`cost_status`
NULL or `"actual"` counts; `quoted`/`committed`/`estimated`/`unknown` is
excluded from `actual_*_cost` and surfaced separately as a new `pipeline_cost`
field + a per-division warning — never silently dropped, never silently
summed in). 8 new tests: 6 synthetic (NULL counts, `actual` counts,
`quoted`/`committed`/`unknown` excluded, and the exact bug scenario — NULL
and `quoted` rows in the same division must not sum together) + 2 against the
**real** `project_db.sqlite` (a precondition check that all real `side='cost'`
rows are still NULL today, and a regression pin proving `pipeline_cost==0`
and `actual_total_cost` unchanged for all 6 real affected projects).
Confirmed by literally reverting the fix and re-running against the real DB:
`actual_total_cost` byte-identical before/after for all 6 projects
(87079.45 / 5792.00 / 1181.00 / 960.45 / 694.00 / 1133.18) — the fix is
provably inert today and only changes behavior once a project actually mixes
lifecycle stages. Full suite 1624.

**Phase 6 — BudgetSnapshot + green-sheet aggregator** ✓ COMPLETE 2026-07-02
`BudgetSnapshot`(header) + `BudgetSnapshotLine`(per-division) in
`db/models/finance.py`. IMMUTABLE by convention (no update code path; a
re-baseline is a new snapshot with a new `label`, never an edit). New
`ai/green_sheet.py::report_green_sheet(session, project_ref, snapshot_id=None)`
— PURE READ, no LLM, no ledger mutation, no UI (owner-set scope boundary).
Per division: `budget_amount`, `quoted_cost`, `committed_cost`, `actual_cost`,
`unclassified_cost` — kept as **separate columns, never summed** — plus
`variance = budget - (committed + actual)` (quoted deliberately excluded from
variance: an unselected/unawarded quote is pipeline, not exposure). Reads the
most-recent `BudgetSnapshot` by default; `snapshot_id` overrides.
**Real-data-shape finding that changed the design before any code was
committed:** the old "aggregate only `amount_type IN (material, labour)`"
rule (written pre-Phase-4/5) does NOT apply here — checked the real DB first
and found 78 of the 79 legacy `llm-v1` cost rows are `amount_type='total'`
with no material/labour split; applying that filter would have silently
zeroed real spend for every pre-Phase-4/5 project. The actual invariant it
protects (never sum a division-total row against its own line items) is
already satisfied structurally — `subcontractor_quote_ingest.py` only ever
persists `kind="line_item"` cost rows, never `division_total`. So the
aggregator sums all cost `amount_type`s per `cost_status` bucket, matching
`report_division_margins`'s existing (now allow-list-correct) behavior —
cross-checked directly: both reports agree exactly on a real project's
`actual_cost` total (test + real-DB verification).
19 tests: schema (fresh + migrated + duplicate-division-per-snapshot
rejected), lifecycle stages never summed, NULL/`amount_type='total'`
counted as actual, `estimated`/`unknown` flagged not dropped, variance
excludes quoted, most-recent-snapshot default + explicit override,
package/quote/selected-quote counts, no-mutation check, a cross-check against
`report_division_margins` on identical synthetic data, and 2 tests against
the real DB (actual-cost parity with margins on "1455 Rue St. Mathieu";
Rockland's no-snapshot-yet case renders `None` everywhere, never fabricates).
Full suite 1643.
**Manually verified end-to-end on the REAL Rockland DB**, chaining Phases
4→5→6 in one run: seeded a real `BudgetSnapshot` from the already-approved
mock `BUDGET_v1.xlsx` (12 divisions, not fabricated), re-ran Phase 4's real
parse + ingest of the mock Plumbing quote, awarded its PO (Phase 5), then ran
the aggregator. Result: Plumbing (div 22) — `budget=$6800`,
`committed=$6800`, `variance=$0`, exactly right; all 11 other divisions show
full budget with `variance = budget` (no quoted/committed/actual anywhere
else, correctly). `selected_quote_count=0` for Plumbing post-award (the quote
correctly reads as `awarded`, not `selected`, once flipped by Phase 5) — the
counts reflect live state, not stale. Rolled back, real DB unchanged.
**New pre-existing gap found by this verification** (not caused by Phase 6,
recorded not fixed): division `"1012"` (Fixtures, the SOW/template
convention — see `NAMING_CONVENTIONS.md`, "`10-12` becomes `1012`") renders
as "Unclassified" because `ai/financial_divisions.py`'s canonical vocab uses
`"10-12"` (with a hyphen) for the same trade. A code-format mismatch between
two parts of the codebase, not missing data — affects any report calling
`division_by_code("1012")`, not just this one.
Deliberately NOT built: variable-cost tolerance flags (Home Depot/hourly —
still not unified into `FinancialLineItem`, see checkpoint above); any UI —
that is its own explicit later gate per the owner's Phase 6 scope.

---

## Phase 4 wiring map — existing mechanisms (READ BEFORE BUILDING)

Recorded 2026-07-02 after a full codebase read of the parse/evidence/financial
spine. These are present-tense facts about what already exists. The parsing
system built last week is the **chokepoint for nearly all data this layer uses** —
Phase 4 wires into it, it does not replace it. Reuse everything here; rebuild
nothing.

**1. The parse → evidence → ledger spine (the chokepoint).**
`Document → DocumentParse (status='success') → EvidenceSpan (evidence_type
'table_region', content_json = {headers, rows_sample, rows_preview,
header_confidence}) → ai/evidence_bundle.build_evidence_bundle() → EvidenceBundle`.
The grid ledger populator (`ai/financial_grid_populator.populate_ledger_for_document`)
already: builds the bundle, and for a single-table sheet parses the **structured
span grid** (`bundle.tables[0].rows_preview`) instead of re-splitting flat text,
linking each written row to `evidence_span_id` + a denormalized
`evidence_locator_json`. `evidence_span_id` FK columns already exist on
`FinancialRecord`, `FinancialLineItem`, and `ContractObligation`. **Phase 4
`SubcontractorQuote` must carry `evidence_span_id` too** (plan says so) and get it
the same way — from the bundle. This spine is built but under-exercised; it is the
intended path for all new structured ingestion.

**2. The deterministic grid parser (`ai/financial_grid.py`).**
`parse_financial_grid_rows(rows)` → `GridParseResult` with `ParsedGridRow`s
(`kind` = division_total | line_item; `amount_type` = material/labour/total/…;
`division_code`; `amount`; `description`; `masterformat_hint`). It captures
`grand_total` (Pre-Tax) separately as a cross-check; `GridParseResult.division_total`
= Σ of section subtotals. **Gap for Phase 4:** `_map_columns` maps only
material/labour/total/masterformat/description by keyword — it does **NOT** capture
`SOW_Item_Ref`, and `ParsedGridRow` has no field for it. To set
`FinancialLineItem.sow_item_id`, Phase 4 must extend `_map_columns` +
`ParsedGridRow` (or read the column off the evidence bundle's `headers`/`rows`
by name) and resolve `SOW_Item_Ref` → `SowItem.canonical_id` via the project-scoped
`item_code` (now unique — that's why the gate above mattered).

**3. The populator hardcodes `side="revenue"` — WRONG for subcontractor quotes.**
`_collect_quote_rows` was built for *client* quotes (`923 ACCEPTED QUOTE` →
revenue). A subcontractor QUOTE (`2026001_QUOTE_22-Plumbing_PlombertInc_selected`)
is `side="cost"` (contractor_out). `classify_financial_sheet` routes on
filename/first-row markers and `_QUOTE_MARKERS` includes "quote", so the new files
classify as `quote` — but the classifier does NOT distinguish client-vs-subcontractor.
Phase 4 needs a cost-quote path (own populator branch or a new collector) that sets
`side="cost"`, `cost_status="quoted"`, `purchase_type` per trade, and links
`sow_item_id`. Do NOT bend `_collect_quote_rows`'s revenue assumption.

**4. `cost_status` is a NEW axis — do not conflate with existing `status`.**
`FinancialLineItem.status` already exists (accepted/proposed/actual/superseded/
unknown) and gates *revenue recognition* (proposed = pipeline, kept out of margin).
Phase 4's `cost_status` (estimated → quoted → committed → actual) is a *separate*
cost-lifecycle axis. A subcontractor quote line = `side=cost`, `cost_status=quoted`,
`status` irrelevant. Selected quote stays `cost_status=quoted` (intent); only a PO
(Phase 5) moves it to `committed`. See Permanent semantic rule #1.

**5. The division_total double-count trap — the existing guard CONFLICTS with the
material/labour-split goal.** `report_project_financials` (views.py ~L2547) dedups
per `(unit, division_code, side)` bucket by letting `total` rows **win over**
`items`. For a client quote that's fine. For a subcontractor COST quote it is
actively harmful: preferring the `division_total` row drops the material/labour
line items — and the per-division material/labour split IS the product value
(Working practice #6). Resolution for Phase 4 (matches the reviewer's rule):
`division_total` rows are **check/context rows, never aggregated**; `line_item`
(material/labour) rows are the aggregatable cost facts; `grand_total` is a
reconciliation cross-check. Phase 4 cost aggregation must sum material/labour line
items and use division_total only to verify the sum — NOT reuse the "total-wins"
suppression. (This is why Permanent rule #2 says aggregate only
`amount_type IN (material, labour)`.)

**6. Reuse, don't rebuild.** `Vendor` exists (name/email/payment_terms/
organization_id) → `SubcontractorQuote.vendor_id`; resolve from the QUOTE
filename's VendorSlug via the identity resolver (ExactFieldMatcher-style — there is
no vendor matcher yet, a small Phase 4 wiring task). `ReconciliationIssue` (Slice 8:
duplicate_total / rollup_double_count / unreconciled / missing_evidence) and
`DocumentFinancialStatus` (human confirm survives re-extraction) are the advisory
surfaces — new quote anomalies flag through them. The `Proposal` gate owns quote
*selection* (human marks selected; never auto-mutate). The populator is idempotent
per document (delete+insert) — keep that.

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
