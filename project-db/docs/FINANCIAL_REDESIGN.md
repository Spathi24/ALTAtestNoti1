# Financial System Redesign — division-keyed line-item ledger

**Date:** 2026-06-16. **Status:** design AGREED + skeleton in progress. This is
the intentions doc for the financial rework — future sessions should read it
before touching the financial layer, alongside `HANDOFF.md §2` (the *current*
layer it replaces) and `MONDAY_AUDIT.md` (the task-graph rework it parallels).

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

## 4. Two populators, one ledger

- **Deterministic grid parser** (`ai/financial_grid.py`, NO LLM) for OUR
  structured sheets (ACCEPTED QUOTE / EXTRAS / JOB COST): read the CSV/TSV cell
  grid, detect the header (`Description | Material | Labour | Total`), read
  amounts by **column position**, classify each row `division_header` (subtotal
  in Total) vs `line_item` (material/labour), map the Master-Format column to a
  division. This is the highest-value, highest-certainty path.
- **LLM classify-then-extract** (extend `ai/doc_extraction.py`) ONLY for
  unstructured third-party PDFs (supplier quotes/invoices, e.g. Superior
  Windows): one job — classify division(s), side, doc_role, line total, with an
  evidence quote (N2). Reuses the existing structured-output discipline.

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

- **Phase 0 — skeleton (IN PROGRESS):** `financial_divisions.py` (vocab +
  classifier) + `FinancialLineItem` model + migration + tests. ← here
- **Phase 1 — deterministic grid parser** for our own quote/extras/job-cost
  sheets → ledger rows; tested on the real 923 quote ($66,539.65 to the penny).
- **Phase 2 — `report_division_margins`** (pivot, gross/true, both-sides guard)
  + a CLI + a web panel.
- **Phase 3 — LLM populator** for unstructured supplier PDFs (Superior Windows).
- **Phase 4 — status/date layering** (filename status, expiry, modifiedTime
  supersession) + the pipeline-vs-actuals split.
- **Phase 5 — cutover:** point the UI/briefing money story at the new report;
  retire the `FinancialRecord` aggregate-net path once parity is proven.

## 8. Honest cautions (features, not bugs)

- The cost side **barely exists in Drive yet** (the JOB COST sheet has ~$529 of
  Home-Depot runs; most sub invoices aren't filed). Correct behavior: reconcile
  only where both sides exist, flag the rest. Margin coverage grows as docs land.
- gross vs true margin is a real decision — report **both**, don't pick silently.
- Per-unit, not per-project, division keying is load-bearing (windows cost ⇒
  exterior).
