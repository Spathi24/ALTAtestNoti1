# HANDOFF — current engineering state

**This file is wiped and retyped at every handoff.** It holds ONLY what is true
*right now*. History → `../CHANGELOG.md`. Rules & philosophy → `../../CLAUDE.md`
(read it first; it overrides everything).

Last retyped: 2026-06-26.

---

## Where things stand (the honest summary)

The **evidence-backed parsing refactor is COMPLETE (Slices 1–8) and the parser is
capped, hardened, and applied portfolio-wide.** This was the critical, delicate
part of the stack; it is now closed off deliberately.

The **next line of work is the refoundation plan** — a much larger front-of-spine
(SOW → package → quote → PO → budget → variance) from an owner+PM review. It is
**build-later, on hold** until the owner settles conventions (plan §12). Do NOT
start building it; structure-only understanding for now. Read:
- `../../docs/MEETING_SYNTHESIS_financial_refoundation.md` — the authoritative plan.
- `../../docs/REFOUNDATION_BUILD_NOTES.md` — entity→repo build map (what/where).
- `../../PROJECT_STATE.md` "REFOUNDATION PLAN" — distilled invariants/constraints.

**Build freeze still applies.** The plan reframes (not relitigates) the schema:
13-entity core + evidence spine are untouched; new entities sit on top.

## What the evidence spine does now (live)

`Document → DocumentParse → EvidenceSpan → DocumentText (compat)`. Parsers: CSV /
XLSX (openpyxl) / PDF (Docling primary, PyMuPDF fallback; Docling is a `[docling]`
extra, NOT in CI). Every parsed table/page is a citeable `EvidenceSpan`.

- **`ai/evidence_bundle.py`** — turns stored spans into LLM-ready labelled tables
  (`render_for_llm`), with `is_low_confidence()` (escalation gate) and
  `primary_span_id()/primary_locator()` (the link).
- **Financial extractors read the spine + link rows.** The deterministic **grid
  parser is primary** (reads `EvidenceSpan.rows_preview` via
  `financial_grid.parse_financial_grid_rows`); the **LLM path is fallback** (reads
  the bundle render; default model **gpt-4.1**, escalates low-confidence docs via
  `OPENAI_EXTRACT_STRONG_MODEL`). Every written row carries `evidence_span_id`.
- **Trust gates:** reconcile-to-stated-total + Slice-7 **evidence grounding** (the
  stated total must appear in the cited evidence, else quarantine).
- **Slice 8 `ReconciliationIssue`** (advisory) + `ai/reconciliation.py`
  deterministic `detect_duplicate_total_issues` — flags cross-doc double-counts
  (a SOW restating its accepted quote).

## Numbers right now

610 docs parsed, **0 parse failures**. Ledger across **10 projects = 241
`FinancialLineItem` rows** (158 llm + 83 grid), **169 evidence-linked**. Portfolio
LLM fill: 16 parsed / 10 quarantined / 33 correctly skipped. Reconciliation
detector flagged **2 real cross-doc double-counts** (Rockland SOW+quote $66,539.65;
a $4,973.56 pair). **Suite: 1556 green; ruff clean.**

## Known limitations (documented, NOT bugs — don't "fix" silently)

- **Scanned PDFs → empty bundles** (OCR is off by design; ~70 docs: surveys,
  certificates, plans). Re-enabling OCR is a deferred decision.
- **Multi-sheet workbooks aren't Material/Labour/Total grids** → the single-table
  grid gating loses no *grid* data; such docs are LLM-path or correctly skipped.
- **Layout-driven workbooks scramble (the XlsxParser limit).** Verified on the
  real ST-Laurent `JOB COSTING.xlsx`: simple single-table sheets (Order Quantities,
  EXTRAS, Order Qty) parse cleanly, but the rich `Material` sheet (3 horizontal
  zones A:F / H:L / P:U + ~11 stacked sub-tables + separator cols G/O) gets
  FLATTENED into one 21-col grid that interleaves unrelated tables per row (and
  falsely reports header_confidence=1.0). Our `openpyxl` one-header-per-sheet reader
  cannot infer spatial layout. ALSO: `rows_sample` shows FORMULAS not computed values
  (`=I5+I6+I7+I9`) — the `data_only` cached-value path isn't feeding rows_sample
  (a real, scoped fix worth doing). FORWARD PLAN (owner, plan §5): this is a legacy
  hand-built sheet = the *fallback* case, not a reason to over-engineer the cell
  reader. (1) Adopt its DATA MODEL (material-by-phase/supplier, labour-by-
  subcontractor, extras-with-status, proportional spending) as the SOP job-costing
  TEMPLATE but with ONE clean table per sheet / real headers / no side-by-side zones
  → deterministic parser then reads it perfectly AND keeps the richness. (2) Spike
  Docling-on-rendered-PDF (xlsx→PDF via LibreOffice headless) for legacy layout-
  driven sheets — visual segmentation + displayed values. (3) Fix formula→value in
  rows_sample regardless (helps every spreadsheet).
- **~72 llm rows are flat-text fallback** (their doc has no successful parse) so
  they're unlinked. Acceptable during migration.
- **Aggregate roll-ups are still wrong** portfolio-wide (e.g. a bogus $361k
  "contracted revenue") because quote-status is guessed and SOWs double-count —
  this is exactly what the plan's **status SOP + job_number** fix. The Slice-8
  detector *flags* these; it does not auto-sum them away. The per-document line
  items are correct; the **line-item material/labour split is the product**, not
  the aggregate total.

## How to run

```
cd project-db && python -m pytest tests/ -q                 # 1556 tests
project_db fill-ledger <project|--all>                       # grid (deterministic, free)
PROJECT_DB_FEATURE_LLM_PDF_FINANCE=true \
  project_db fill-ledger-llm <project>                       # LLM path (gpt-4.1, costs)
project_db division-margins <project>                        # the ledger view
scripts/revamp_corpus.py [--plan|--financial-only|--overwrite]  # re-parse corpus (Docling, slow)
```
Both fill paths are idempotent. `fill-ledger-llm --all` sends EVERY text doc to the
LLM (~746) — scope to financial docs instead (a scratch script did the ~59 needed).

## Parked / open questions (forward ideas — wiped, won't ossify)

- Faceted/tree retrieval (project→unit→trade) to fix askbot cross-project
  contamination — relational facet filter, post-ledger.
- Per-LINE span attribution (rows currently cite the doc's primary span).
- Enforce no-trusted-record-without-evidence once flat-text fallback is retired.
- Wire `scripts/reconcile_financials_llm.py` to persist via
  `reconciliation.record_llm_finding`.
- A `force_full` Drive sync to backfill the 189 NULL `folder_path`s (safe now that
  delta-sync containment is in place).
- The refoundation plan itself (the big next thing) — see the three docs above.
