# HANDOFF — current engineering state

**This file is wiped and retyped at every handoff.** It holds ONLY what is true
*right now*. History → `../CHANGELOG.md`. Rules & philosophy → `../../CLAUDE.md`
(read it first; it overrides everything).

Last retyped: 2026-07-04.

---

## Where things stand (the honest summary)

The **financial refoundation front-of-spine is BUILT end-to-end** (2026-07-02 →
07-04): Phases 1–6 + the filename resolver + the green-sheet UI + a demo
harness. The full chain works through the front door on the pilot:

```
filename → resolve_quote_document → ingest_subcontractor_quote →
(human selects) → award_purchase_order → committed cost + ContractObligation →
report_green_sheet → /projects/{id}/green-sheet
```

**What is NOT true yet (do not let a rendered page imply otherwise):**
- Every dollar that has flowed through the new chain is **mock template data**
  (Rockland pilot seed). No real budget, no real subcontractor quote has gone
  through it. The circularity is documented, not hidden.
- **Zero real Drive files follow the naming convention** and only Rockland has
  SOW structure — operational adoption (a human task) is the blocker, not
  code. The exact team checklist lives at the bottom of
  `../../docs/templates/NAMING_CONVENTIONS.md`.
- The **actual** lifecycle stage has no writer (nothing sets
  `cost_status='actual'`); invoices/receipts are not yet matched to POs.
- **Home Depot + hourly labour are invisible to the green-sheet** (no
  `purchase_type` unification) — the page says "fixed-cost side only" out loud.

## The new spine (Phases 1–6, all shipped + tested)

- **Phase 1** mock template Drive (`docs/templates/mock_drive/`, owner-approved)
  + `NAMING_CONVENTIONS.md` (now includes the team adoption checklist).
- **Phase 2** `Project.code` IS the YYYYNNN project_code (LOCKED decision);
  +display_name/legacy_job_number/aliases; `_resolve_project` matches
  code/legacy#/alias/name; Monday connector no longer clobbers `code`.
- **Phase 3** `SowPackage`/`SowItem` (scope only; `package_id` nullable for
  div-01 GC overhead; `item_code` unique PER PROJECT — partial index).
- **Phase 4** `SubcontractorQuote` + FinancialLineItem `purchase_type` /
  `cost_status` / `sow_item_id` / `subcontractor_quote_id` /
  `line_markup_factor`; `ai/subcontractor_quote_ingest.py` (cost-side path,
  SEPARATE from the revenue `_collect_quote_rows`; division-total rows never
  persisted as cost; SOW_Item_Ref resolved per-project or flagged).
- **Phase 5** `PurchaseOrder` (one per quote, DB-enforced; po_number
  `{code}-{PPP}`) + `ai/purchase_order_award.py` — the ONE writer of committed
  cost (guards: only `selected` quotes; refuses zero quoted rows; commits only
  `cost_status='quoted'` rows; obligation kind `po_commitment`).
- **Phase 5 item #3** `ai/quote_document_resolver.py` — deterministic
  filename → project/package/vendor (Home Depot linker discipline: unique
  match or unresolved, never guess; `canonical_division_code` folds `1012` →
  `10-12` at the parse boundary).
- **Phase 6** `BudgetSnapshot`/`BudgetSnapshotLine` (immutable baselines) +
  `ai/green_sheet.py::report_green_sheet` — per division: budget / quoted
  (SELECTED quote only) / pending_bids (competing, never summed) /
  committed / actual (allow-list: NULL-legacy or 'actual') / unclassified
  (flagged) / variance = budget − (committed+actual).
- **UI green-sheet (2026-07-04)** `/projects/{id}/green-sheet` (flag
  `green_sheet`; template `project_green_sheet.html`). Now effectively a
  subset of the Command Center below; kept until UI slice U3 retires it.
- **UI Financial Command Center (2026-07-04, NEW ground-up UI — slice U1 of
  `../../docs/UI_REFOUNDATION.md`)** `/projects/{id}/finance` (flag
  `finance_home`; new self-contained design language `web/static/finance.css`;
  template `project_finance.html`; service `ui_views.project_finance_home`).
  The whole money lifecycle on one screen + tendering + honest
  MOCK/LIVE/EMPTY provenance badge. Read-only; all numbers from
  `report_green_sheet` verbatim. This is the shell the rest gets mounted onto
  (rules in UI_REFOUNDATION.md: no new tech stack, no old-page rehab now).
- **Demo harness (2026-07-04)** `scripts/demo_rockland.py` — copies the real
  DB to `project_db.demo.sqlite` (canonical DB never touched), seeds the
  pilot THROUGH the real pipeline, serves on :8123. `.claude/launch.json` has
  `alta-web` (fixed to `python`; was wrongly `py -3.13`) + `alta-demo`.

## Numbers right now

Suite **1698 green** (SOW ingest + a Scope-of-Work-render regression test).
The Financial Command Center now shows a **Scope of Work** card (real SOW
items grouped by division, included vs excluded, expandable) — verified LIVE
on the real DB: Rockland shows "REAL SCOPE INGESTED — 111 SOW items". `doctor.py`
0 fail / 1 known warn (79 legacy NULL cost_status rows, allow-listed
downstream). **RUFF NOT RE-RUN THIS SESSION** — the ruff native binary is
blocked by a Windows Application Control policy on this machine (`WinError
4551`), an environment issue, not a code issue; new code was hand-kept to the
100-char line limit + isort order. Re-run `python -m ruff check .` +
`format --check .` once the policy allows it before the next slice.
Real DB: Rockland `code=2026001`. **REAL SOW INGESTED 2026-07-05** — the
owner's `2026001_SOW_v1_consolidated.xlsx` (the mock template shape, filled
with real Rockland scope) ingested via the new `ai/sow_ingest.py`: **111 real
SowItems (86 included / 25 explicit exclusions) across 13 SowPackages**,
replacing the 31 mock items (0 mock rows remain). Real DB backed up first
(`project_db.sqlite.bak_presowingest_*`). Still 0 SubcontractorQuote /
PurchaseOrder / BudgetSnapshot in the real DB (those ingesters don't exist
yet). NOTE: CSI div `28` (Fire Detection) has no entry in
`ai/financial_divisions.py` so it renders as name "Unclassified" (code `28`
is preserved, not lost) — a small vocab gap to add, not a data problem.

## How to run the demo

```
python scripts/demo_rockland.py           # seed the isolated demo DB
python scripts/demo_rockland.py serve     # http://127.0.0.1:8123
# the seed prints the exact green-sheet URL; --reseed for a fresh copy
```

## Session-local artifacts (things a cold instance would miss)

- `project_db.demo.sqlite` (gitignored) — disposable, rebuilt by the seed.
- A preview server may be running on :8123 from the 07-04 session.
- The gold job-cost template is `docs/JOB_COST_TEMPLATE_structured.xlsx`
  (owner-built, canonical); the mock drive under `docs/templates/mock_drive/`
  is the template SOURCE the team copies files up to Google Drive from.

## Parked / open questions (forward ideas — wiped, won't ossify)

- **THE DRIVE GO-LIVE WORKSTREAM (the actual next real-data build).**
  1. **SOW-file ingester — ✅ BUILT 2026-07-05** (`ai/sow_ingest.py`,
     7 tests, run on real Rockland SOW → 111 items / 13 packages). Reads the
     `SOW_Items` sheet → `SowPackage`/`SowItem`, div-01 = GC overhead
     (no package), canonicalizes division codes, idempotent replace.
  2. **BUDGET-file ingester — NOT built.** `{code}_BUDGET_v1.xlsx`
     (`Budget_Lines`) → `BudgetSnapshot`/`BudgetSnapshotLine` (the demo does
     this inline; extract into a reusable ingester, same shape as #1).
  3. **QUOTE path — NOT built as a loop.** The per-file
     `ingest_subcontractor_quote` + `resolve_quote_document` exist; still need
     the derive-quotes-from-real-estimates step (the DB already has parsed
     `927 QUOTE` / `ACCEPTED QUOTE` / `Estimate_*.pdf` with evidence spans) and
     an `ingest-quotes` loop over synced convention-named Documents.
  4. **`ingest-project-financials <project>` CLI** wrapping #1–#3, idempotent.
  Owner's fuller vision (2026-07-05, reconcile before building — see below):
  the pipeline should GENERATE downstream files from the SOW (SOW → packages →
  quotes → budget), organize by PHASES (subfolders per phase, changes
  propagate downward), and eventually WRITE back to Google Drive. Those are
  bigger, partly-gated builds; see PROJECT_STATE "Current Focus" for the
  reconciliation with the meeting doc + the phased plan.
- Actuals stage: deterministic invoice→PO matcher writing
  `cost_status='actual'` (llm-v1 rows stay NULL, never auto-promoted).
- HD/hourly unification into the green-sheet (variable-cost tolerance flags).
- LLM-advisory slices (quote coverage-comparison vs SOW; owner explicitly
  encourages LLM use where deterministic is impractical — Proposal-gated,
  never a ledger writer).
- FK-declaration gap: `financial_line_item.sow_item_id` /
  `subcontractor_quote_id` are app-level-only on the real DB (bare ALTER);
  `ContractObligation`↔PO link lives in source_meta_json; PO numbering is
  read-then-increment (fine single-user).
- Remote/live-trial deployment: the UI is 127.0.0.1-only by design (no auth).
  A PM trial = run it on the owner's machine (or screen-share). Anything
  network-exposed needs auth first — do not just tunnel it.
