# Financial System Redesign — division-keyed line-item ledger

**Date:** 2026-06-16. **Last updated:** 2026-06-17. **Status:** Phase 1c +
hardening DONE; Phase 1d (Ledger Health / Review Surface) is next. This is the
intentions doc for the financial rework — future sessions should read it before
touching the financial layer, alongside `HANDOFF.md §2` (the *current* layer it
replaces) and `MONDAY_AUDIT.md` (the task-graph rework it parallels).

---

## Financial Data Contract (canonical source declaration)

**Decided 2026-06-17 after the Phase 2 checkpoint.**

| Consumer | Reads from | Status |
|---|---|---|
| `report_project_financials` | `FinancialRecord` (LLM-extracted) | Transition — kept until Phase 5 cutover |
| `/projects/{id}/financials` web panel + HTMX toggle | `FinancialRecord` via `report_project_financials` | Transition |
| `report_project_money_line` | `FinancialRecord` via `report_project_financials` | Transition |
| Attention briefing money section | `FinancialRecord` | Transition |
| `extract_financials_for_project` (ai/financials.py) | Writes `FinancialRecord` | Transition writer |
| **`report_division_margins`** | **`FinancialLineItem`** | **Canonical new source** |
| **`/projects/{id}/margins` web panel** | **`FinancialLineItem` via `report_division_margins`** | **Canonical new source** |
| **`fill-ledger` CLI** | Writes `FinancialLineItem` | **Canonical new source writer** |
| `report_budget_vs_contract` | `DocumentText` only | Independent (regex heuristic) |

**`FinancialLineItem` is canonical for division-keyed margin analysis.**
`FinancialRecord` is the compatibility/transition layer — it stays until
`report_division_margins` covers all use cases that `report_project_financials`
currently covers (confirmed toggle, per-document breakdown, cross-check view).
That cutover is Phase 5. No consumer currently reads from both tables.

**`unit=None` semantics:** a `None` unit means the document had no unit prefix
(e.g. "ACCEPTED QUOTE" with no civic number). It does NOT mean "covers all
units." Display as `"unknown_unit"` in all UIs, never as `"(all)"`.

---

## 0. Why (the problem, verified against real code)

The owner's boss models profit **per trade/division per unit** (Plumbing
revenue − Plumbing cost, for unit 923), not as one project-wide net. The
current layer cannot produce that, for four verified reasons:

1. **Extraction discards line items by instruction.** `ai/doc_extraction.py`
   (~line 194): *"Prefer the grand total, subtotals … over enumerating every
   minor line; at most ~25 records."* We tell the LLM to keep totals, not lines.
2. **The report aggregate-nets.** `ai/views.py::_representative_amount` collapses
   each `(document, direction)` group to ONE amount; `report_project_financials`
   sums those into a single `client_in − contractor_out` margin. Per-division
   margin is unreconstructable from this.
3. **No controlled division vocabulary.** `FinancialRecord.phase` is a free
   string, rarely populated; "Plumbing" / "plomberie" / a Home-Depot PEX run
   never collapse to one bucket.
4. **No `unit`, no material/labour split, no proposed-vs-accepted `status`.**
   923 / 921 / 927 / exterior are separate scopes inside one canonical Project;
   client quotes carry Material + Labour + Total columns; filenames carry
   "ACCEPTED" vs "NOT STARTED".

**Correction to the originating analysis:** it blamed *text flattening severing
numbers from labels*. That is NOT our pipeline — `connectors/gdrive/
extractors.py::extract_xlsx` emits each row as **TSV in column order** (header
kept), and Google Sheets export as **CSV**; both preserve the grid. That
observation came from a different Drive-reading tool. The fix below stands; only
the justification changes (deterministic parsing wins because the LLM is *told*
to skip lines and because column-role parsing of a known sheet is free + exact,
not because the text is mangled).

## 1. The shape we want

A normalized **line-item ledger**: one row per
`(unit, division, side, amount_type, source_doc, doc_date, status, amount)`,
with evidence. Reconciliation pivots by `(unit, division)`:
`margin = revenue rows − cost rows`. Two margins are reported:

- **gross** — client line (incl. OHP + contingency) − cost
- **true**  — after pulling OHP / contingency out to their own Div-01 rows

Reconciliation key is `(unit, division)`, never project-wide division (the
windows *cost* belongs to `exterior`; the interior 923 quote has no Openings
division — naive whole-project matching would mismatch them).

## 2. The controlled axis — CSI MasterFormat divisions

A fixed ~16-entry list (`ai/financial_divisions.py`). Every amount maps to
exactly ONE division via: (a) the sheet's own "Master Format" hint column when
present, else (b) deterministic EN/FR keyword match, else (c) `99 Unclassified`
(never crash — same fail-safe posture as the rest of the codebase). Divisions
(residential-renovation pragmatic subset of CSI):

`01 General` (delivery, supervision, materials, **OHP, contingency**),
`02 Demolition`, `03 Concrete`, `05 Structural`, `06 Carpentry/Millwork`,
`07 Roofing/Insulation`, `08 Openings (doors/windows)`, `09 Finishes
(drywall/flooring/paint/tile)`, `10-12 Fixtures/Hardware/Casework`,
`22 Plumbing`, `23 HVAC/Mechanical`, `26 Electrical`, `31-32 Site/Landscape`,
`99 Unclassified`.

## 3. The model — `FinancialLineItem` (new table, coexists with FinancialRecord)

A NEW sidecar, not an overload of `FinancialRecord`. Rationale: the new shape
(unit + controlled division + material/labour split + status + line-item-first)
is different enough that overloading the existing schema — and its
`_representative_amount`-collapsing report — would be messier than a clean
table. The legacy `FinancialRecord` path stays during transition (it is already
the deprecated-but-kept safety net), and we cut the UI/report over once the new
ledger is proven on Rockland. **No big-bang migration.**

Fields: `project_id`, `document_id`, `unit`, `division_code`, `division_name`,
`side` (`revenue`|`cost`|`unknown`), `amount_type`
(`material`|`labour`|`total`|`markup`|`contingency`|`tax`|`deposit`|`other`),
`amount`, `currency`, `description`, `status`
(`accepted`|`proposed`|`actual`|`superseded`|`unknown`), `doc_role`, `doc_date`,
`quote_expiry`, `source` (`grid`|`llm`), `quoted_excerpt`, `confidence`,
`amount_verified`, `extractor_version`, `source_meta_json`. Vocab fields are
validated-with-fallback strings (never crash), exactly like `FinancialRecord`.

**Double-count rule (per `(unit, division, side)`):** prefer the division-total
row when present; else sum material+labour line items; never both. (Same idea as
`_representative_amount`, but scoped per-division instead of per-document.)

## 4. Classify → route → extract → one ledger

**There is NOT one parser.** The corpus has structurally different documents —
verified against the real St-Laurent / Rockland data:

| Type | Real example | Layout | Extractor |
|---|---|---|---|
| `quote` | 923 ACCEPTED QUOTE, 927 QUOTE | `Description | MasterFormat | Material | Labour | Total`, ESTIMATE banner | **grid parser (built, grid-v1)** |
| `extras` | EXTRAS ACCEPTED, JOB COSTING→EXTRAS sheet | change-order table (`CO# | Item | Cost/Unit | Applied | Total | Status`) | **extras parser (built, extras-v1)** |
| `simple_estimate` | Common Area ESTIMATE | single-column `Description | Notes | Total Amount` (no Material/Labour split) | future — `simple_estimate_grid.py`; safely skips as `no_header` until built |
| `job_cost` | JOB COSTING (5768), JOB COST.xlsx | "MATERIAL SPENDING" `Phase | Cost | Supplier`, + budget/prediction/**receivable** side-blocks | future (hard — see §8); intentionally deferred |
| `order_quantities` | Door Order sheet, Order Quantities sheet | procurement qty table, no money | skip/ignore (correct) |
| `unknown` | PDFs, photos, meeting notes, mixed | unstructured or unrecognised layout | skip; future: LLM populator behind eval harness |

So routing is mandatory and comes FIRST: `classify_financial_sheet(name, text)`
(deterministic — filename + the top-of-sheet banner) picks the type; only
`quote` is handed to the grid parser today. **This is load-bearing**: applying
the quote parser blindly to JOB COSTING scraped 22 garbage rows (it pulled a
`$322,500 "Receivable total"` projection as a line item). The grid parser now
also self-guards (its header check requires the quote's `Total Amount` column),
so a mis-route degrades to "no rows", never garbage.

- **Deterministic grid parser** (`ai/financial_grid.py`, NO LLM): reads the
  CSV **or TSV** cell grid (delimiter sniffed — Google-Sheet export is comma,
  xlsx export via `extract_xlsx` is tab), finds the header below the metadata
  block, reads amounts by **column position**, classifies each row
  `division_total` (section subtotal) vs `line_item` (material/labour, inherits
  its section's division), maps the MasterFormat column to a CSI division.
  Reconciles the real 923 quote to **$66,539.65** to the penny.
- **LLM classify-then-extract** (extend `ai/doc_extraction.py`) ONLY for
  unstructured third-party PDFs (supplier quotes/invoices, e.g. Superior
  Windows) and `unknown` sheets: classify division(s), side, doc_role, line
  total, with an evidence quote (N2). Reuses the existing structured-output
  discipline.
- The `extras` and `job_cost` layouts get their own deterministic extractors
  later (own column maps), all writing the SAME `FinancialLineItem` ledger.

### Tooling stance (deliberate)

The architecture above (classify → route → canonical schema → validate) is the
right one. But we **keep it in-house** and add NO new dependencies — per
STRATEGY's "no new tech until SQL limits bite", and because we already have the
equivalents: **SQLite** (consolidated store — not DuckDB), **openpyxl** (xlsx —
covers all 26 in the corpus; not calamine/pyxlsb/pandas), **pymupdf** (PDF),
the **string-vocab-with-fallback + pytest + the one report chokepoint**
(validation — not Great Expectations / dbt / Pydantic), and
**`FuzzyFieldMatcher`** (supplier dedup — not rapidfuzz). Azure Document
Intelligence is a new paid cloud connector, explicitly deferred.

## 5. Reconciliation — `report_division_margins`

A new chokepoint report: group ledger rows by `(unit, division)`, sum each side,
emit `revenue / cost / gross_margin / true_margin / has_both_sides`. Where only
one side exists, flag `cost data pending` (reuse the confidence-guard idea) —
never invent the missing side. The confirmed/quoted toggle
(`DocumentFinancialStatus`) and the report-chokepoint discipline carry over.

## 6. Status & dates (proposed vs current)

1. **Filename status** → first-class `status`: "ACCEPTED"/"EXTRAS ACCEPTED" →
   `accepted`; "(NOT STARTED)" → `proposed` (excluded from actuals by default,
   shown in a separate pipeline view).
2. **`Valid Until` in-doc date** → `quote_expiry` (a `cost` quote past expiry
   needs re-pricing).
3. **Drive `modifiedTime`** breaks ties: newest accepted doc for a
   `(unit, division)` wins; older becomes `superseded`, never double-counted.

## 7. Phased plan

- **Phase 0 — skeleton. ✅ DONE.** `financial_divisions.py` (CSI vocab +
  classifier) + `FinancialLineItem` model + migration + tests.
- **Phase 1a — sheet classifier + quote grid parser. ✅ DONE.**
  `financial_grid.py`: `classify_financial_sheet` (quote/extras/job_cost/
  order_quantities/unknown) + the delimiter-sniffing quote parser. Verified on
  real data — 923 quote reconciles to $66,539.65; JOB COSTING routes to
  `job_cost` and the parser declines it (no garbage). Pure (text → rows); NOT
  yet wired to a persister.
- **Phase 1b — persister + CLI. ✅ DONE.**
  `ai/financial_grid_populator.py`: unit/status/currency extracted from filename;
  rows written as `FinancialLineItem` (side=revenue, source=grid, amount_verified=True);
  `fill-ledger <project>` CLI. Idempotent per document. Verified on real Rockland
  data: 923 ACCEPTED QUOTE -> 63 rows, reconciles to $66,539.65; 927 NOT STARTED
  -> 56 rows, reconciles to $126,480.91; EXTERIOR NOT STARTED -> 2 rows,
  reconcile fail ($49k vs $50k, correctly flagged). 22 new tests.
- **Phase 1c — extras parser + classification metadata. ✅ DONE (2026-06-17).**
  `ai/extras_grid.py` (extras-v1): deterministic CO/change-order parser
  (`CO# | Item | Cost/Unit | Applied | Total | Status` layout). All CO rows are
  side=revenue; accepted/proposed written; rejected/cancelled skipped. Extras→
  quote fallback: if a doc named "EXTRAS" has no CO header, tries the quote
  parser (catches "EXTRAS+ROOF" style mislabeled documents).
  Classification metadata added to all rows: `classification_method`,
  `classification_confidence`, `source_doc_type`, `source_region`.
  `ingestion_status` / `ingestion_reason` on `DocLedgerResult`.
  Verified on Rockland corpus: EXTRAS ACCEPTED now parses 12 rows (was 0);
  reconcile fail correctly flagged ($36,085 line items vs $34,835 stated — real
  discrepancy in source doc). 43 new tests (test_extras_grid.py,
  test_phase1c_mvp.py, test_e2e_financial_pipeline.py). 1170 total tests.
- **Phase 1c-hardening — multi-sheet workbook routing. ✅ DONE (2026-06-17).**
  `split_workbook_sheets(text)` in `financial_grid.py` splits the
  `### SheetName\n...` blocks emitted by `extract_xlsx`. Populator now classifies
  each sheet independently and deduplicates by type (first quote/extras sheet
  wins; "Copy of ESTIMATE" skipped to prevent double-counting). One atomic
  delete+insert per document across all sheets. Single-sheet/non-xlsx documents
  fall through unchanged. Verified against real-file patterns:
  - Common Area.xlsx: 10 sheets (Overview/Measurements/Specs/etc.) — non-financial
    sheets skip; ESTIMATE sheet (single-column format) safely returns no_header;
    Copy of ESTIMATE and Est. Minus Sections deduped
  - 5770 St-Laurent.xlsx: Sheet1 has "Quote #" in header → classifies as quote
    → no financial grid found → no_header (correct)
  - JOB COSTING.xlsx: EXTRAS sheet parsed, Material/Labour/Order Quantities skipped
  31 new tests (test_workbook_routing.py). 1170 total tests.
- **Phase 1d — Ledger Health / Review Surface. NEXT.**
  A PM-facing audit layer that answers: what did fill-ledger parse? what did it
  skip and why? what failed reconciliation? what is likely financial but
  unsupported? This is the bridge between "the parser is safe" and "the PM can
  trust the numbers." See §9 for full spec.
- **Phase 2 — `report_division_margins`. ✅ DONE.**
  `ai/views.py::report_division_margins`: pivots the ledger by `(unit, division_code)`,
  applies the double-count rule (section-total wins over line-item sum), flags
  `revenue_only | cost_only | ok | unknown_division` per row, carries `source_docs`
  and `gross_margin_pct`. `division-margins <project>` CLI and
  `/projects/{id}/margins` web panel — **both are live and functional.**
  Verified on Rockland after Phase 1c: $278,105.56 total quoted revenue (4
  parsed docs), 19 divisions flagged `revenue_only`. 13+ new tests.
- **Phase 3 — LLM populator** for unstructured supplier PDFs + `unknown` sheets.
  Gated on eval harness (see §8 / INTENTIONS.md §8). Do NOT build until a gold
  set exists.
- **Phase 4 — status/date layering** (filename status, expiry, modifiedTime
  supersession) + the pipeline-vs-actuals split. Proposed-vs-accepted filter on
  `report_division_margins`. See §6.
- **Phase 5 — cutover:** point the UI/briefing money story at the new report;
  retire the `FinancialRecord` aggregate-net path once parity is proven.

## 8. Known limitations as of 2026-06-17 (features, not bugs)

These are stable properties of the current system. Do not attempt to "fix" them
without a clear business trigger and a specific design decision.

**Cost-side margin is structurally missing.** All current ledger rows are
revenue-side (quoted revenue + extras). The cost side barely exists in Drive
(JOB COST sheets have scattered actual spend, but no canonical format). The
margin report correctly shows `revenue_only` for all 19 Rockland divisions.
This is not a bug — it is an honest reflection of what the Drive corpus contains.
The report is "quoted revenue by unit/division + extras" not "profit truth."

**Simple estimates are not supported.** Common Area.xlsx uses a single-column
format (`Description | Notes/MasterFormat | Total Amount`) without
Material/Labour split. The grid parser requires both `material` AND
`total amount` in the header, so this safely returns `no_header`. A future
`simple_estimate_grid.py` would handle this layout. Do not build it until those
sheets matter to a PM.

**Sheet-type deduplication is a safety heuristic, not survivorship logic.**
"First sheet wins" prevents double-counting but ignores semantics. The eventual
correct order is: `accepted > proposed`, `explicit ESTIMATE > Copy of ESTIMATE`,
`newer modifiedTime > older`, `human-confirmed > inferred`. Do not build
survivorship logic until it is needed for financial trust.

**Reconciliation failures are surfaced, not resolved.** EXTRAS ACCEPTED
reports reconcile fail ($36,085 line items vs $34,835 stated pre-tax). The
difference appears to be a line-item counting issue in the source document — the
OHP or an interior-doors line may be included in the division total but excluded
from the stated pre-tax. Do not "fix" this in code without identifying the real
business rule. It belongs in a human review queue.

**No durable audit trail for skipped documents.** Skipped/quarantined documents
exist only in `DocLedgerResult` (in-memory, per fill-ledger run). The database
does not record "document X was classified as quote, parser rejected it,
reason=no_header." When a PM asks "why is this quote missing?", the answer is
only available by re-running fill-ledger. A future `FinancialDocumentIngestion`
table (see §9) would make skips visible in the UI.

**PDF and Word financial extraction is not solved.** The system skips
unstructured PDFs (subcontractor invoices, supplier quotes, etc.) with
`unknown/unsupported_type`. These are real documents with real dollars. The
correct approach is LLM-classify-then-extract with a deterministic validation
layer, gated behind an eval harness. Do not build it without eval.

**French document-NAME classification is deferred (deliberately, not missed).**
`classify_financial_sheet` matches English doc-type markers
(`quote`/`estimate`/`extras`/...). The live corpus confirms French-named
financial docs exist — e.g. `2025-03-25 - Soumission - 5770 Boul St Laurent`
(soumission = quote/bid) and several `Facture #…` (facture = invoice). They are
**not** currently lost revenue, because every one of them is a PDF or an
invoice: the grid parser only reads CSV/TSV grids today, and invoice/PDF
ingestion is itself deferred (above). Adding French *name* markers now would be
untested code that changes no real outcome. **When PDF/invoice ingestion is
built (Phase 4-5), revisit `classify_financial_sheet` with French naming
(`soumission`, `devis`, `avenant`, `facture`) as part of that work** — the
CELL-CONTENT side is already bilingual (status values + division keywords are
accent-folded EN/FR as of 2026-06-17).

## 9. Phase 1d — Ledger Health / Review Surface

**Goal.** The parser is now safe, but a PM still cannot trust the numbers
because they cannot see what was counted, what was skipped, and why.
Phase 1d builds the audit/review layer that closes this gap.

**The question it answers:** "Why is Project X showing only $66k revenue when
I have four quote documents?"

**Minimum output (`fill-ledger --audit` or `report_ledger_health`):**

| Field | Description |
|---|---|
| `project` | Project name |
| `document` | Document name |
| `sheet` | Sheet name (or "whole doc" for single-sheet) |
| `classified_type` | quote / extras / job_cost / order_quantities / unknown |
| `ingestion_status` | parsed / skipped / quarantined / failed |
| `ingestion_reason` | no_header / unsupported_type / no_money / parse_error / … |
| `rows_written` | integer; 0 = nothing landed in ledger |
| `reconcile_ok` | true / false / null (no grand total to compare) |
| `division_total` | sum of section rows |
| `stated_total` | pre-tax total declared in the document |
| `difference` | stated_total − division_total |
| `recommended_action` | (see below) |

**Recommended actions (deterministic, not LLM):**

| Code | Meaning |
|---|---|
| `review_reconcile_fail` | Parsed, but division total ≠ stated total — human should check source doc |
| `unsupported_simple_estimate` | Quote layout but no Material column — future `simple_estimate_grid.py` |
| `unsupported_job_cost` | Job-cost sheet — intentionally deferred |
| `unsupported_pdf_quote` | PDF/Word quote from a subcontractor — needs LLM extractor |
| `empty_extraction` | DocumentText exists but extracted_text is empty — re-run `extract-content` |
| `safe_nonfinancial_skip` | Photo, meeting notes, spec sheet — correctly skipped |
| `ok` | Parsed, rows written, reconcile passed |

**Implementation path:**
- `report_ledger_health(session, project_id) -> list[dict]` in `ai/views.py` —
  re-runs `populate_ledger_for_document` in read-only mode (or replays from
  `DocLedgerResult` if cached) for all documents in the project, classifies
  each result, assigns recommended_action.
- `fill-ledger --audit <project>` CLI command that calls this and prints a table.
- Optionally: a `FinancialDocumentIngestion` sidecar table to persist per-doc
  outcomes (makes skips queryable from the web UI). Fields: `document_id`,
  `project_id`, `classified_sheet_type`, `ingestion_status`, `ingestion_reason`,
  `rows_written`, `reconcile_ok`, `division_total`, `stated_total`,
  `recommended_action`, `extractor_version`, `updated_at`.

**What NOT to do in Phase 1d:** do not build more parsers. Do not write to
`FinancialRecord`. Do not add status/date layering. Phase 1d's deliverable is
visibility, not more extraction.

**Build trigger:** when a PM asks "why is this document not counted?"

## 10. Honest cautions (original §8 — preserved)

- The cost side **barely exists in Drive yet** (the JOB COST sheet has ~$529 of
  Home-Depot runs; most sub invoices aren't filed). Correct behavior: reconcile
  only where both sides exist, flag the rest. Margin coverage grows as docs land.
- gross vs true margin is a real decision — report **both**, don't pick silently.
- Per-unit, not per-project, division keying is load-bearing (windows cost ⇒
  exterior).
- **`job_cost` / "MATERIAL SPENDING" sheets are genuinely hard** and must not be
  parsed naively. JOB COSTING (5768) interleaves actual spend (`Phase | Cost |
  Supplier`) with budget columns, per-unit predictions, and **receivables**
  ($322k "Receivable total", $78k–$117k "Jair quoted") — these are projections,
  NOT costs. A correct extractor reads ONLY the actual-spend block; until that's
  built, these route to `job_cost` and are left for a dedicated extractor /
  human, never scraped. (This is exactly the regression that justified
  classify-first.)
