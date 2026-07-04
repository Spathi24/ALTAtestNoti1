---
name: alta-finance-domain
description: Controlled vocabulary + trap list for ALTA's financial spine. Use BEFORE touching anything that reads or writes money — FinancialLineItem, SubcontractorQuote, SowItem/SowPackage, PurchaseOrder, BudgetSnapshot, the grid parser, division margins, green-sheet, or any extraction/report of amounts. Triggers include "quote", "ledger", "division", "margin", "cost_status", "budget", "markup", "revenue vs cost", or parsing financial documents.
---

# ALTA Financial Domain — vocabulary & traps

Every trap below caused a real shipped bug. Re-deriving this per session is how
they recur. Settled conventions: §12 of
`docs/MEETING_SYNTHESIS_financial_refoundation.md` (2026-06-30) — do not reopen.

## Controlled vocabularies (exact strings, no synonyms)

- **Quote status** (`SUBCONTRACTOR_QUOTE_STATUSES`):
  `pending -> recommended -> selected / rejected -> awarded`.
  `selected` = human INTENT only, cost stays "quoted". `awarded` is set at PO
  conversion only. AI recommends via the Proposal gate; a human approves.
- **Cost lifecycle** (`COST_STATUSES`, on `FinancialLineItem.cost_status`):
  `estimated -> quoted -> committed -> actual` (+ `unknown`). Only a
  PurchaseOrder award moves quoted -> committed.
  **Trap:** legacy llm-v1 rows have `side='cost', cost_status NULL` — every
  aggregate must ALLOW-LIST cost_status values, never exclude-NULL or sum all.
- **Division codes:** canonical form is the DB form — two digits (`"09"`,
  `"22"`) or dash range (`"10-12"`, `"31-32"`); `"99"` = unclassified.
  FILENAMES spell ranges dashless (`1012`) because a dash collides with the
  naming-convention separators. **Always fold external spellings through
  `financial_divisions.canonical_division_code()`** — an exact-match on a raw
  `"1012"` silently never hits a canonical `"10-12"` package (real bug, fixed
  2026-07-04).
- **Identity formats:** `project_code=^\d{7}$` (e.g. `2026001`),
  `po_number=^\d{7}-\d{3}$`. `Project.canonical_id` is the join key — models
  have NO `.id` attribute. Pilot: 923 Rockland = `2026001`.

## Side & role (the $123k / $361k class of bug)

- `side` is revenue XOR cost from **Alta's** point of view (COMPANY_NAME =
  "Alta Construction Group" decides direction). A vendor doc BILLED TO Alta is
  a COST even if titled "quote"/"estimate" — read the BILL TO / issuer lines.
- A sheet organizing rows BY VENDOR (Company/Fournisseur column, per-row phone
  numbers) is Alta's COST build-up worksheet, not client revenue.
- **Selected-vs-competing trap:** revenue/committed aggregates must count the
  SELECTED quote only. Summing every competing bid produced the $361,007.98
  phantom revenue the PM rejected (fixed in commit `e365183`). When
  aggregating quotes, always filter by status.
- Sales taxes (TPS/TVQ/GST/QST) are pass-through — never revenue or cost.

## Parsing traps

- Quebec-French numerals: `1 234,50` (space thousands — often NBSP/narrow-NBSP
  U+00A0/U+202F — comma decimal). The NBSP handling in
  `audit_financial_extraction.py` is INTENTIONAL (noqa'd) — don't "fix" it.
- Grid documents: the deterministic grid parser
  (`ai/financial_grid.py::parse_financial_grid_rows`) is the PRIMARY path;
  Docling/LLM is the fallback for legacy/third-party docs. `division_total`
  and `grand_total` rows are RECONCILIATION CHECKS, not line items.
- Header rows: Rockland-style estimates carry metadata rows above the true
  header (row 6, not the `,ESTIMATE,,,,` row). Verify header detection on the
  real doc, not a fixture.
- Reconcile to the penny: line-item sum == stated pre-tax total, or the parse
  is wrong. The mock-drive gold number is $66,539.65.

## Markup (client-facing vs internal)

Two layers: line client price = internal cost x `line_markup_factor`; final
client price = subtotal x 1.15 global. Internal cost/margin NEVER reaches
client-facing output (green-sheet is display-only, `Ingest=N`).

## Model tiering (owner decision 2026-06-26 — CLAUDE.md rule 11)

Certainty-requiring judgments (client-vs-vendor role, quote-vs-worksheet, side
inversion, ambiguous lifecycle) run on the strong tier — never gpt-4o-mini.
Pin model snapshots. Confirm credit balance with the owner before live runs.

## Structure invariants (refoundation north star)

Every cost traces SOW item -> package -> quote -> PO -> budget line -> actual.
Outside-SOW work = tracked ChangeOrder. Ambiguous = FLAG, never silently sort
(Home Depot linker discipline: a wrong link is worse than none). The product
value is the per-division material/labour split, not aggregate totals.
