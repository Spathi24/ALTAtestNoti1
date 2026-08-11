# HANDOFF — current engineering state

**This file is wiped and retyped at every handoff.** It holds ONLY what is true
*right now*. History → `../CHANGELOG.md`. Rules & philosophy → `../../CLAUDE.md`
(read it first; it overrides everything).

Last retyped: 2026-08-11 (first session after a 4-week gap; previous work ended
2026-07-07).

---

## Base state (verified this session, not inherited from docs)

| Gate | State |
|---|---|
| Branch / worktree | `main`, real repo path, clean of tracked changes |
| Interpreter | `python` 3.11.9; `project_db, openai, openpyxl, anthropic` import OK |
| Suite | **1726 passed** |
| `ruff check` | GREEN |
| `ruff format --check` | GREEN (230 files) |
| `doctor.py` | 0 fail / 1 known warn (79 legacy NULL `cost_status` cost rows, allow-listed downstream) / 1 info |

**The AppControl block on ruff is GONE.** The 07-04→07-07 sessions could not run
the ruff binary (WinError 4551) and hand-kept code to the line limit instead;
that left 3 real lint errors + 11 unformatted files, now fixed. Do not repeat
the "ruff is blocked, skip the gate" note without re-testing it.

---

## Where things stand (the honest summary)

**The structure is built. The money is empty.** This is the single most
important fact for whoever picks this up, and it was not written down anywhere
before 2026-08-11.

On the **canonical** DB, `report_green_sheet('2026001')` returns `None` for
every money field — budget / quoted / pending bids / committed / actual — across
all 13 divisions. The Financial Command Center therefore renders provenance
`scoped`: real scope, zero dollars. **Every dollar ever seen on that page came
from `project_db.demo.sqlite`** (the mock template seed), never from the real DB.

```
Pilot 2026001 (923-927 Rockland), REAL DB:
  SowItem              111    REAL  (owner's consolidated SOW xlsx)
  SowPackage            13    REAL
  ScopeContext           3    REAL  (923_INTERIOR=2 / 927_UNIT=18 / EXTERIOR=4 docs; 7 UNRESOLVED)
  Document              31
  contract_amount  $66,539.65 REAL  (923 signed segment only)
  ContractObligation    12
  FinancialLineItem    101    REAL but ALL revenue-side (see below)

  SubcontractorQuote     0
  PurchaseOrder          0
  BudgetSnapshot         0
  cost-side ledger rows  0
```

**The two halves never meet.** The pilot's 101 ledger rows are all
`side=revenue` (client prices extracted from `927 QUOTE` + `ACCEPTED QUOTE`,
evidence-linked, good data — 61 grid rows + 40 llm rows). `report_green_sheet`
reports only the **cost** side. So real extraction exists and the flagship page
shows nothing.

**Real money already in the DB that reaches no financial surface:**

```
Home Depot: 192 transactions / 1288 line items / $59,337.48 total
  5768 St-Laurent     68 txns   $27,512.93   linked (job_name)
  923-927 Rockland    19 txns    $2,352.54   linked (job_name)
  1455 St. Mathieu    20 txns    $1,555.39   linked (job_name)
  UNRESOLVED          85 txns   $27,916.62   <- 47% attributed to NO project
  detail_status: 160 imported / 32 pending
Labour: 1 LabourClaim, 1 cluster.  FieldNote: 7.  ReconciliationIssue: 2.
```

The Command Center says "fixed-cost side only" out loud, so this is disclosed,
not hidden — but it means the biggest real number in the system is invisible.

**The blocker on the front-of-spine is still OPERATIONAL, not code** (unchanged
since 2026-07-04): zero real Drive files follow the naming convention, and only
Rockland has SOW structure. Team checklist: bottom of
`../../docs/templates/NAMING_CONVENTIONS.md`.

## What is built (and works)

- **Evidence spine** `Document → DocumentParse → EvidenceSpan → DocumentText`
  (compat). 610 docs parsed, 0 failures. Grid (M/L/T) + LLM (Desc+Total) paths
  are complementary; Slice-7 deterministic grounding gate quarantines
  hallucinated totals.
- **Refoundation front-of-spine, Phases 1–6:** `Project.code` = the YYYYNNN
  project code (LOCKED); `SowPackage`/`SowItem`; `SubcontractorQuote` +
  FinancialLineItem `purchase_type`/`cost_status`/`sow_item_id`;
  `PurchaseOrder` + `ai/purchase_order_award.py` (the ONE writer of committed
  cost); `BudgetSnapshot` + `ai/green_sheet.py::report_green_sheet`;
  `ai/quote_document_resolver.py` (deterministic filename → project/package/
  vendor; `canonical_division_code` folds `1012` → `10-12`).
- **`ai/sow_ingest.py`** — real SOW-file ingester, deterministic, no LLM. Ran on
  the owner's real file → 111 SowItems (86 included / 25 explicit exclusions) /
  13 SowPackages. **NOTE: it has no CLI entry point** — the real ingest was a
  one-off. `python -m project_db.cli --help` has no `ingest-*` command.
- **ScopeContext (SC-0.5 / SC-1 / SC-2)** + **U1.5 inspector**
  `/projects/{id}/scope-contexts`. See the 2026-07-07 CHANGELOG entry.
- **UI:** `/projects/{id}/finance` (flag `finance_home`) — the Financial Command
  Center, self-contained `web/static/finance.css`, numbers verbatim from
  `report_green_sheet`. `/projects/{id}/green-sheet` (subset, kept until U3).
  Both 127.0.0.1-only, no auth.
- **Streams:** Home Depot import, Gmail/Telegram labour intake, field notes,
  project logs, RAG/askbot, attention briefing.

## What is NOT built

- **Budget-file ingester.** The logic exists *inline* in
  `scripts/demo_rockland.py` (lines ~97–138: reads `Budget_Lines` →
  `BudgetSnapshot`/`BudgetSnapshotLine`). Extracting it into
  `ai/budget_ingest.py` is a half-day and is the closest thing to "almost
  done" in the repo — but there is **no real BUDGET xlsx** to run it on.
- **Quote ingest loop.** Per-file `ingest_subcontractor_quote` +
  `resolve_quote_document` exist; no loop over synced Documents, and no
  derive-quotes-from-real-estimates step.
- **`ingest-project-financials <project>` CLI** wrapping SOW + budget + quotes.
- **Actuals stage.** Nothing writes `cost_status='actual'`; no invoice/receipt →
  PO matcher.
- **HD + hourly labour unification** into the green sheet (no `purchase_type`
  bridge).
- Everything after SC-2 on the ScopeContext ladder (SC-3 generalized resolver →
  SC-4 authority → SC-5 SowVersion/scope axes → SC-6 consumers → SC-7 finance
  surfaces → SC-8 retire project-level contract), then `WorkRequirement`,
  `CostEvent`/`CostAllocation`, forecast-to-complete, Drive write-back.

## Known small gap (recorded, deliberately not fixed)

CSI division `28` (Fire Detection) has no entry in `ai/financial_divisions.py`,
so it renders as name "Unclassified" on the pilot's scope card. The code `28` is
preserved, not lost. One-line vocab add; left alone because base repair was
scoped to hygiene only.

## Session-local artifacts (things a cold instance would miss)

**Real owner-supplied files live in `C:\Users\nsaro\Downloads\`, NOT in the
repo** — the repo only contains the *mock* template drive:
- `2026001_SOW_v1_consolidated.xlsx` (2026-07-06) — the real 111-item SOW that
  was ingested. Also `2026001_SOW_v1.xlsx`.
- `SOW 923 Rockland.docx`, `SOW - EXTERIOR.docx`, `Final SOW.pdf` (2026-07-06).
- `ACCEPTED QUOTE.xlsx`, `_927 QUOTE.xlsx` (last edited **2026-07-07 11:09**),
  `_927 QUOTE  (NOT STARTED).xlsx`.
- `ProjectInfo1_merged.pdf` (64pp) + `EstimatorDocumentation.pdf` (23pp) — the
  two design reports behind the 2026-07-07 architecture reconciliation.
- There is **no real BUDGET, PO, or JOBCOST file** anywhere — those exist only
  as mock templates under `../../docs/templates/mock_drive/`.

Other:
- `project_db.demo.sqlite` (gitignored) — disposable mock demo DB, rebuilt by
  `scripts/demo_rockland.py`. **Do not confuse its numbers with real ones.**
- Untracked data dirs, all pre-vacation: `docs/HomedepotData/` (the HD exports),
  `docs/AcademicPapers/`, `project-db/docs/templates/JOB_COSTING_TEMPLATE.xlsx`,
  6 `project_db.sqlite.bak_*` backups, 2 `*_run.log` files.

## How to run

```
project_db serve --no-refresh              # real DB, http://127.0.0.1:8000
python scripts/demo_rockland.py            # seed the isolated MOCK demo DB
python scripts/demo_rockland.py serve      # http://127.0.0.1:8123
python scripts/db_probe.py 2026001         # read-only DB snapshot (import crib)
```

## Parked / open questions (forward ideas — wiped, won't ossify)

- **The direction decision is OPEN.** As of 2026-08-11 the owner has ~2–3 weeks
  left at this job and no working MVP in 3 months. Three candidate arcs were put
  to them; they chose "fix the base first, then decide". The candidates:
  1. **Home Depot money MVP** — surface the already-imported HD spend + labour on
     the project financial surface, plus an operator queue to attribute the 85
     unresolved transactions ($27,916). Needs no new file from the owner; the
     data is real today; HD is CLAUDE.md's variable-cost leak #1.
  2. **Close the cost-side loop** — budget ingester + `ingest-project-financials`
     CLI so the green sheet lights up. Needs the owner to produce a real
     convention-named BUDGET xlsx first; fixed-cost side only.
  3. **Continue the ScopeContext ladder** (SC-3, SC-5). Architecturally correct;
     6+ slices from anything a PM can open.
- Actuals stage: deterministic invoice→PO matcher writing `cost_status='actual'`
  (llm-v1 rows stay NULL, never auto-promoted).
- LLM-advisory slices (quote coverage vs SOW), Proposal-gated, never a ledger
  writer.
- FK-declaration gap: `financial_line_item.sow_item_id` /
  `subcontractor_quote_id` are app-level-only on the real DB (bare ALTER);
  `ContractObligation`↔PO link lives in `source_meta_json`; PO numbering is
  read-then-increment (fine single-user).
- Remote/live-trial deployment: the UI is 127.0.0.1-only by design (no auth). A
  PM trial = run it on the owner's machine or screen-share. Anything
  network-exposed needs auth first — do not just tunnel it.
- Owner's fuller pipeline vision (2026-07-05): generate downstream files from the
  SOW (SOW → packages → quotes → budget), organize by PHASES with downward
  propagation, and eventually WRITE back to Drive under a reserved `ALTA/`
  folder. Gated (CLAUDE.md rule 14); design with the owner before building.
