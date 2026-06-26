# Evidence-Backed Document Parsing & Financial Audit Refactor

> Dedicated plan + state doc for one large initiative. The general cross-session
> log is [PROJECT_STATE.md](PROJECT_STATE.md); this file holds the full reference
> architecture (preserved near-verbatim from the owner's brief so nothing is
> lost), the step-by-step checklist, current status, struggles/bugs, future
> work, and — importantly — **finishing conditions**, so this does not sprawl
> into endless phases.

## Why this exists (owner's diagnosis, kept verbatim in spirit)

The cost/trade-separation ledger we built for financial docs is **not** what the
audit reads — the audit reads flat PDF/text. Revenue is usually one *quote*
while expenses are spread over many invoices, which is where side-confusion
occurs. The RAG layer (`DocumentChunk` embeddings) is not used by the audit
either. CSV/XLSX files are in the DB but **flattened**: multi-sheet files and
side-by-side tables get linearized, so a single "row read" spans multiple
fields and even concepts. The audit must become extremely reliable and
auditable by construction. Better evidence and structure — not a bigger model
everywhere — is the biggest reliability lever (though for judgment-heavy calls,
use the stronger model).

## Finishing conditions (READ THIS — how we know we're DONE, per slice and overall)

This initiative is a fixed, ordered set of slices. **Do not invent new phases.**
When the overall Definition of Done (bottom of this file) is met, the initiative
is COMPLETE and this doc is archived. Each slice has its own Definition of Done;
close it (tests green, committed) before starting the next. If a limitation is
found mid-slice, record it under "Struggles / Bugs / Parked" and either fold it
into an existing slice's checklist or the explicit "Future Work" list — **a
limitation is not a license to add a phase.**

---

## Slice checklist (top-level)

- [x] **Slice 1 — Foundation (models + migration + compat write-back).** DONE 2026-06-25.
- [x] **Slice 2 — Parser abstraction + MIME routing + CSV parser.** DONE 2026-06-25. Spine proven
  end-to-end; forward-compat groundwork added (graceful `skipped` for unimplemented types, a
  `parse_documents` batch pipeline, one-line `register_parser` seam).
- [x] **Slice 3 — openpyxl XLSX parser.** DONE 2026-06-25. `XlsxParser` (sheets, header
      detection above title rows, formulas/merged/number-formats, `rows_sample` + raw
      `rows_preview`). Validated on 115 real HD files (0 failures). `.xls` legacy not handled
      (routes to skipped).
- [x] **Slice 4 — Docling PDF parser (+ PyMuPDF fallback).** DONE 2026-06-25. `PdfParser`:
      Docling (layout + TableFormer) recovers tables with page + bbox + spanning headers; falls
      back to PyMuPDF when Docling absent/fails. Docling is a SEPARATE `[docling]` extra, NOT in
      CI; OCR disabled (digital PDFs). Validated on real table-heavy PDFs.
- [x] **Slice 4.5 — Integration backfill (make it USED).** DONE 2026-06-25.
      `scripts/parse_documents.py` fetches real Drive bytes and runs the new parsers ->
      `DocumentParse` + `EvidenceSpan` + synced `DocumentText`, idempotent. Applies the migration
      to the real DB. Ran on Rockland (9 docs -> 66 spans, 27 table regions). NOT yet auto-wired
      into the live sync (next). RUNTIME: PDFs ~220s avg / 728s max on this CPU (Docling) -> the
      full 452-PDF corpus is ~a day on this laptop; needs a server/GPU or financial-docs-only scope.
- [x] **Slice 4.6 — Backfill wired into live sync.** DONE 2026-06-26. `cmd_weekly_changes --sync`
      calls `_parse_recent_evidence` after legacy extraction: recently-changed fast docs (CSV/XLSX/
      gsheet) parse into the spine, `write_text=False` (DocumentText untouched), idempotent. PDFs
      gated off by `PROJECT_DB_PARSE_PDF_ON_SYNC=true` (Docling cost). 4 tests (test_sync_evidence.py).
- [x] **Slice 5 — Nullable evidence links on the ledgers.** DONE 2026-06-26. `evidence_span_id`
      (FK -> evidence_span.id, ON DELETE SET NULL) + `evidence_locator_json` on FinancialRecord /
      FinancialLineItem / ContractObligation. Additive (old rows null; one span per record, no
      many-to-many). Models + migration DDL + ALTER cols; applied to real DB. 5 tests
      (test_document_parse.py). Invariant "no NEW trusted record without evidence" recorded, NOT
      enforced yet (Slice 6 owns enforcement). Suite 1512.
- [ ] Slice 6 — One structured extraction path consumes evidence bundles; sets the evidence link;
      refuses trusted records without evidence; low header_confidence -> LLM escalation. ← NEXT
- [ ] Slice 7 — Deterministic verification (amount-in-evidence, IDs resolve, hash matches).
- [ ] Slice 8 — `ReconciliationIssue` storage; wire `reconcile_financials_llm.py` to consume evidence spans.

### Slice 1 — Foundation (DONE 2026-06-25) — task checklist

- [x] Task 1: `PROJECT_STATE.md` at repo root + this `EVIDENCE_REFACTOR.md`.
- [x] Task 2: `DocumentParse` + `EvidenceSpan` models (plain-string statuses/types, schema-light style).
- [x] Task 3: SQLite migration for both tables wired into `ensure_sqlite_schema`.
- [x] Task 4: compatibility write-back helper (`DocumentParse.rendered_text` → upsert `DocumentText`).
- [x] Task 5: tests (create parse; link evidence; cascade-delete; write-back; suite stays green — 1482 passed).
- [x] Task 6: update `PROJECT_STATE.md` + this file with results + deferred next step.

**Slice 1 Definition of Done:** `PROJECT_STATE.md` exists; `DocumentParse` model exists;
`EvidenceSpan` model exists; migration exists; compat write-back helper exists; tests pass;
**no financial extraction behavior changed; no parser-specific implementation added yet.**

### Slice 1 — hard scope limits (do NOT cross in slice 1)

Do not rewrite the app · do not rename existing models unless absolutely required · do not
modify financial extraction logic · do not add Docling · do not add openpyxl parser · do not
add artifact storage · do not add reconciliation issue storage · do not create GraphRAG,
agents, verifiers, many-to-many evidence joins, or a spreadsheet Cell table · preserve
existing reports and tests.

---

## Current Status / Behavior / Results

- **Slice 1: DONE (2026-06-25).** Tables `document_parse` + `evidence_span` exist (models +
  migration); `db/parse_compat.py::write_document_text_from_parse` bridges a successful parse
  back to `DocumentText`. NO financial extraction behavior changed.
- **Slice 2: DONE (2026-06-25).** New `src/project_db/parsing/` package proves the spine
  end-to-end with a real parser:
  - `base.py` — `ParsedDocument` / `ParsedEvidence` dataclasses + `DocumentParser` Protocol
    (pure: bytes → ParsedDocument; no DB/network).
  - `csv_parser.py` — `CsvParser` (v1): header detection, comma/semicolon/tab/pipe delimiter
    sniffing (handles Quebec `;` CSVs), Markdown table for compatibility, and a `table_region`
    `EvidenceSpan` carrying headers + a structured row sample (preserves table structure,
    does NOT flatten).
  - `router.py` — `get_parser_for(mime, filename)` registry; `register_parser(...)` is the
    one-line extension point for Slice 3/4. Unhandled types → `None`.
  - `service.py` — `parse_document_content(...)` persists the spine (`DocumentParse` +
    `EvidenceSpan` + compat `DocumentText`); unknown type → `status='skipped'`, parser
    exception → `status='failed'` (never raises). `parse_documents(...)` is a batch pipeline
    helper. ADDITIVE: the live Drive `extract_and_store` path is untouched; this seam is not
    wired into live sync yet (a later integration step).
  - 9 tests in `test_parsing.py`. Full suite **1491 passed**; ruff + format clean.
- **Slice 3: DONE (2026-06-25).** `src/project_db/parsing/xlsx_parser.py` (`XlsxParser` v1,
  registered) via openpyxl. Per sheet, one `table_region` EvidenceSpan with: detected header
  (skips a title/metadata row above it), `rows_sample` of `{header: value}` dicts, a raw
  `rows_preview` safety net, `merged_ranges`, and a compact `cells` map of FORMULA cells
  (formula + number_format + cached value when the file carries one). Bounded; `.xls` legacy →
  skipped. ADDITIVE (live `extract_xlsx`/`extract_and_store` untouched; not wired into live sync).
  - **Correctness validated on REAL data** (per owner's testing directive): swept all **115**
    Home Depot `.xlsx` files — 0 failures, 0 anomalies; headers/values/sheet structure matched a
    manual read. Synthetic workbooks cover formulas/merged/title-rows/multi-sheet. 7 tests in
    `test_xlsx_parsing.py`; full suite **1498 passed**; ruff+format clean.
  - **Downstream check (honest finding):** fed a reconstructed 3940 vendor-cost worksheet to
    `gpt-4o-mini` (the model that failed on 3940) as OLD flat text vs NEW structured evidence —
    BOTH classified it `cost` correctly. So flattening was NOT the sole cause of the original
    3940 error (that was the financial extractor's doc_type→side logic on the CSV path, fixed
    earlier). XlsxParser's real payoff is robustness on harder shapes (title rows, formula-vs-
    total, multi-sheet) + cell-level CITATION for the future evidence-bundle extractor
    (Slice 6) — NOT a dramatic flat-text classification win on simple single tables. Do not
    overclaim it.
- **Slice 4: DONE (2026-06-25).** `parsing/pdf_parser.py` `PdfParser` (registered). Docling backend
  (layout analysis + TableFormer) emits a `table_region` EvidenceSpan per table with page + bbox +
  structured `rows_sample`, and a `page` span per page of text; `export_to_markdown` is the compat
  rendering. Falls back to PyMuPDF (`page` spans) when Docling is absent or a conversion errors —
  never raises. Backend recorded in `structured_json`.
  - **Docling specifics:** heavy optional dep in a SEPARATE `[docling]` extra (NOT in `dev`/CI;
    `pip install -e ".[docling]"`; pulls torch + onnxruntime; models cached under
    `~/.cache/huggingface`). OCR is DISABLED (`do_ocr=False`) — these are digital PDFs, and the
    default rapidocr model (`torch.PP-OCRv6.det.small`) is broken in this build anyway; scanned-PDF
    OCR is a future option. Tested with docling 2.107.0.
  - **Correctness validated on real table-heavy PDFs** (owner's directive): the OpenAI structured-
    outputs PDF (table on p2, headers + rows bound, bbox captured) and the 9-page Docling paper
    (3 tables; TableFormer correctly recovered a SPANNING header — `native backend.TTS` /
    `native backend.Pages/s` / `pypdfium backend.TTS` — so each column traces to its full header
    path). This spanning-header / nested-hierarchy recovery is exactly the "multiple sums" structure
    flat text destroys — the real Docling win. (Real ACTIVE-project estimate/invoice PDFs live in
    Drive, not on disk, so on-disk validation used these table-heavy PDFs; validate on fetched
    project PDFs when Drive access is wired.)
  - 4 tests in `test_pdf_parsing.py` (fallback forced for CI; Docling path gated on import). Adding
    PdfParser to the registry rippled into 2 Slice-2 tests that used PDF as their "unsupported type"
    example — fixed to use an image mime (the registry-ripple the owner warned about, caught by the
    suite). Full suite **1503 passed**; ruff+format clean.
- Next: Slice 5 — nullable `evidence_span_id` / `evidence_locator_json` on FinancialRecord /
  FinancialLineItem / ContractObligation (additive; old rows stay valid).
- Everything below ("Reference architecture") is **background, not a command to implement now.**

## Struggles / Bugs / Parked

- **(FIXED 2026-06-25) CSV/XLSX took row 1 as the header.** Real active-project estimates open
  with a title + company + estimate-# + blank rows, then the real header
  (`Description | Notes | Material | Labour | Total`). On Rockland's ACCEPTED QUOTE the CSV parser
  produced headers `['', 'ESTIMATE', ...]` (garbage). Fixed: shared `parsing/tableutil.py`
  `detect_header_index` (pick the header-like row with the MOST filled cells, so a metadata row
  like `address | Date | 5/5/2026` loses to the real 5-column header), used by both parsers; a raw
  `rows_preview` is always kept as a safety net. Re-validated: Rockland header now row 6 with
  `Demolition → Total $1,000.00` bound correctly; all 115 HD xlsx still detect row 1.
- **KNOWN GAP (not yet addressed) — multi-table-per-sheet.** A sheet/CSV can hold several tables
  (side by side or stacked). v1 treats each sheet as ONE table_region, so a second table's columns
  bleed into the first's. Needs region detection (blank-row/blank-col splitting, or layout from
  Docling for PDFs). Owner flagged this explicitly. Target: a hardening pass before/within Slice 6
  (evidence-bundle extraction), since that is where region granularity actually matters.
- **KNOWN GAP (not yet addressed) — nested subtotals / "multiple sums".** Estimate columns are not
  one grand total: a section row carries a subtotal that sums only its indented sub-items
  (Material+Labour), with structure encoded by row labels/indentation. v1 captures all rows with
  correct headers (data preserved) but does NOT model the section→subtotal hierarchy. The future
  evidence-bundle extractor must reconstruct it from row labels rather than blindly summing a
  column. Owner flagged this explicitly.
- **TESTING NOTE (owner directive).** Validate parsers on REAL, preferably ACTIVE/current projects
  (open finances matter more than closed ones like 3940), across MANY differently-formatted sheets
  — not just the simple single-table Home Depot exports. Read files yourself, check in/out pairs,
  and trace downstream (does the API agent get the right answer on cleaner data?).

## Future Work (explicitly out of the slice list above, revisit later)

- Apply stronger-model policy (gpt-4.1+) to all certainty-requiring calls; pin model snapshots; build evals.
- OpenAI Batch API (50% cheaper, async) for nightly project audits, embedding refreshes, full rechecks.
- Snapshot export/import; W3C-PROV-style provenance (entity/activity/agent/derivation) on derived totals.
- Evidence-grounded LLM verifier (only refute on a concrete cited contradiction; never silently erase).

---

# Reference architecture (BACKGROUND ONLY — do not implement all phases now)

> Preserved near-verbatim from the owner's brief. The immediate work is Slice 1
> above. Later slices map onto the phases below.

**Papers / articles** (stored in `docs/AcademicPapers/` where provided — Docling report + two
OpenAI guides on JSON/Structured-Outputs and Batch API; the rest are external references):

- *Document parsing & table structure:* Docling Technical Report (messy docs → structured
  representations via layout analysis + table-structure recognition); LayoutLMv3 (visually rich
  document understanding where position/layout matter); TableFormer + table-recognition surveys
  (invoices/quotes are table-heavy; table structure is not recoverable from plain text).
- *RAG & retrieval reliability ("don't just stuff all docs into context"):* RAGAS (context
  precision/relevance, faithfulness, answer relevance); ARES (automated RAG eval with lightweight
  judges); Corrective RAG / CRAG (retrieval evaluator before generation — detect the wrong bundle);
  GraphRAG (project-level/private-data reasoning over a graph/hierarchy of extracted entities).
- *Agent design & cost control:* ReAct (interleave reasoning + tool use, kept bounded); Reflexion
  (store feedback from failed attempts — only if grounded in test failures / human corrections);
  LLMCompiler (plan independent calls, execute in parallel, consolidate — fits large file audits).
- *Verification & hallucination control:* Chain-of-Verification (independent verification questions);
  Chain-of-NLI (check generated claims are supported by source context); "LLMs Cannot Self-Correct
  Reasoning Yet" (self-review without external evidence is NOT enough).
- *Provenance & auditability:* W3C PROV (entity/activity/agent/derivation); "Provenance in Databases:
  Why, How, and Where"; Provenance Semirings (mathematically traceable derived totals).
- *API/prompting practices:* Use **Structured Outputs** (schema-enforced), not plain JSON mode or
  markdown parsing, for extraction / issue objects / verifier outputs / model-run records. Use the
  **Batch API** for non-urgent large audits (50% cheaper, async). **Pin model snapshots** and build
  evals — the audit run already showed `gpt-4o-mini`, `gpt-4o`, `gpt-4.1` behaving materially
  differently.

**Target architecture (full):**

```
raw source file reference
-> parser-specific structured artifact
-> evidence spans / table regions / cell ranges
-> extracted financial claims
-> reconciliation issues
-> Markdown/JSON reports as views only
-> optional human approval
-> ledger changes only after approval
```

**Immediate (smaller) target:** `Document -> DocumentParse -> EvidenceSpan -> FinancialRecord /
FinancialLineItem / ContractObligation`. Do NOT jump to GraphRAG, multi-agent systems, adversarial
verifier frameworks, full spreadsheet cell databases, or automatic ledger mutation yet.

**Existing situation.** `Document` is mostly correct (source metadata + references) — keep it; raw
files stay in their source system / object storage (never giant SQL blobs); store reference, MIME,
path/URL/storage ref, source metadata, timestamps, checksum, owner, project/client/deal links.
`DocumentText` is the weak point: one flat blob per doc destroys layout, sheet structure, table
boundaries, cell addresses, formulas, page regions, provenance — keep it TEMPORARILY as a
compatibility layer, not the canonical source. `FinancialRecord` / `FinancialLineItem` /
`ContractObligation` are fine — keep them; `quoted_excerpt` is too weak as the only evidence anchor.
`financials.py` hardening (all-or-nothing replacement, batching, transient retry, amount verification,
`DocumentFinancialStatus`, careful warnings) — keep those ideas. `doc_extraction.py` is closer to the
future (strict structured extraction, doc classification, deterministic amount verification, no LLM
arithmetic) — move the future extraction path toward this style.

**Phase 1 — parser/evidence DB models** (this is Slice 1). `DocumentParse` = one parse run for one
document (id; document_id FK→Document.canonical_id cascade; parser_name req; parser_version;
source_hash; status req success|failed|skipped; rendered_text; structured_json; error; created_at;
token_count). `EvidenceSpan` = one citeable unit of evidence (id; document_id FK cascade; parse_id
FK→DocumentParse.id cascade; evidence_type req text_block|table_region|cell_range|paragraph|page|sheet;
locator_json; content_text; content_json; bbox_json; confidence; created_at). Plain strings, not DB
enums (schema-light style). No relational `Cell` table; no one-SQL-row-per-cell.

**Phase 2 — keep `DocumentText` as compatibility output.** After every successful parse, upsert
`DocumentText`: extracted_text = DocumentParse.rendered_text; extraction_method = parser_name (+ version);
extracted_at = now; token_count = approx tokens. Do not delete old logic — make it downstream of parsing.

**Phase 3 — parser abstraction.** Small internal interface `ParsedDocument(rendered_text, structured,
evidence_spans)` / `ParsedEvidence(evidence_type, locator, content_text, content_json, bbox, confidence)`.
Route by MIME/extension: PDF→Docling (fallback to existing text parser); XLSX/XLS→openpyxl; CSV→CSV
parser; DOCX→current path for now; unknown→skipped DocumentParse. Each parse produces a DocumentParse
row + EvidenceSpan rows + DocumentText compat row.

**Phase 4 — PDF parser via Docling** (the Docling library, not raw HF `AutoModel`). Store Docling JSON
in `structured_json`, Docling markdown/text in `rendered_text`; EvidenceSpan rows for page text blocks,
detected table regions, useful table content, page-level spans when fine-grained regions are
unavailable; preserve page number / block id / bbox / locator in `locator_json` + `bbox_json`. Docling
markdown is a rendering, NOT canonical — canonical is structured JSON + citeable evidence spans.

**Phase 5 — XLSX/XLS parser via openpyxl.** Preserve workbook structure; do not flatten. Extract
workbook filename/hash, sheet names, used ranges, merged cells, formulas, displayed + raw values,
number formats, hidden rows/cols when accessible, table regions, detected headers, important cell
addresses. Workbook-level metadata → `structured_json`. EvidenceSpan per meaningful sheet range /
table-like region (sheet name, cell range, headers, important formulas/totals, compact cell map, merged
ranges, number formats). Example `content_json`:

```json
{ "sheet": "Quote", "range": "B4:F29",
  "headers": ["Item","Qty","Unit","Price","Total"],
  "merged_ranges": ["B4:C4"],
  "cells": { "F29": { "raw_value": 123393.83, "displayed_value": "$123,393.83",
                      "formula": "=SUM(F4:F28)", "number_format": "$#,##0.00" } } }
```

`rendered_text` may be a markdown-ish readable version for compatibility, but financial extraction
should eventually use evidence bundles, not this flat text.

**Phase 6 — link financial records to evidence.** Nullable `evidence_span_id` FK +
`evidence_locator_json` on FinancialRecord / FinancialLineItem / ContractObligation (old records stay
valid). No many-to-many yet; one primary `evidence_span_id` suffices (extra IDs in `source_meta_json`
during transition). Invariant for the new path: **no new trusted record without `evidence_span_id` or
`evidence_locator_json`.**

**Phase 7 — change financial extraction input.** The structured path reads the latest successful
`DocumentParse` + its `EvidenceSpan` rows (not only `DocumentText`). Build compact evidence bundles
(`[EVIDENCE n] document_id / evidence_span_id / type / locator / content`). The structured-output schema
makes each claim include: evidence_index or evidence_span_id; amount; currency; issuer; recipient;
counterparty_role; document_role; side_candidate revenue|cost|neutral|unknown; lifecycle_status
proposed|accepted|invoiced|paid|cancelled|superseded|unknown; confidence; uncertainty_reason. LLM
extracts + classifies roles; it does NOT do final arithmetic or mutate totals.

**Phase 8 — preserve hardening.** Keep amount parsing, locale-aware amount verification, confidence
clamping, all-or-nothing replacement, transient retry/backoff, `DocumentFinancialStatus`, structured
schemas, deterministic amount verification, partial/ambiguous warnings. Do NOT keep as primary
architecture: large keyword gates, regex-heavy rollup/projection filtering, flat-text batching as main
path, giant-blob-only prompts, quoted_excerpt-only evidence (these may remain as secondary hints).

**Phase 9 — minimal `ReconciliationIssue` storage.** Keep `reconcile_financials_llm.py` read-only/
advisory. It showed project errors are often cross-document (duplicate estimate / PDF export; SOW
restating itemized quotes; supplier worksheet as client revenue; vendor bill on wrong side;
quote/invoice/status confusion). Add `ReconciliationIssue` (id; project_id; issue_type duplicate|
restatement|side_inversion|tax_error|status_error|ambiguous|other; severity; status candidate|verified|
refuted|approved|applied|ignored; amount_delta_revenue; amount_delta_cost; confidence; reason;
evidence_json; created_by_model_run; created_at; approved_at; approved_by) only if not too disruptive;
otherwise defer and keep markdown/JSON output — but design `DocumentParse`+`EvidenceSpan` so
reconciliation can later consume spans directly. Reconciliation never mutates totals automatically —
proposed corrections only.

**Phase 10 — model-use policy.** Cheap/deterministic for: MIME routing, hashing, basic parsing, obvious
date/vendor/invoice-number extraction, amount verification, formula detection, table-region creation,
token counting, compatibility text rendering. Stronger model only for judgment-heavy extraction: client
vs vendor role; quote vs supplier worksheet; SOW vs original scope vs duplicate restatement;
cross-document duplicate; side inversion; ambiguous lifecycle. Biggest reliability win is better
evidence/structure, not a bigger model everywhere.

**Phase 11 — verification policy.** Deterministic only for now: amount exists in cited evidence;
evidence_span_id exists; document_id matches; amount parses; record not partially written; source hash
matches latest parse when possible. A later LLM verifier must be evidence-grounded and may refute ONLY
when it cites a concrete contradiction. A verifier must never silently erase findings — refuted/uncertain
stay visible as candidates with status + reason.

**Phase 12 — Definition of Done (overall initiative).**

```
Existing reports still work through DocumentText.
New parser runs create DocumentParse and EvidenceSpan.
PDF parsing uses Docling when available.
XLSX parsing uses openpyxl.
CSV parsing creates structured parse/evidence output.
DOCX still works through existing path or simple parser path.
DocumentText is updated from DocumentParse.rendered_text after successful parse.
At least one financial extraction path can create records linked to evidence_span_id or evidence_locator_json.
The new trusted extraction path refuses to create trusted records without evidence.
Old records remain valid.
Tests pass.
No raw binary files are stored as giant SQL blobs.
No spreadsheet Cell table is created.
No many-to-many evidence system is created.
No GraphRAG is created.
No automatic ledger mutation is created.
```

**Design principle.** Markdown is a report view, not the source of truth. Good: structured_json +
EvidenceSpan + records linked to evidence + ReconciliationIssue rows + markdown generated from
structured data. Bad: agents each write markdown and the final merged markdown is treated as truth.
Every extracted number should answer: which document? which parser? which page/sheet/range? which
evidence span? which model run (if any)? was the amount deterministically verified? was it approved or
merely proposed?

**Implementation order (overall):** 1) models+migration; 2) parse service abstraction; 3) DocumentText
write-back; 4) openpyxl parser FIRST (spreadsheets are highest-risk flattened format); 5) Docling PDF
parser; 6) nullable evidence fields; 7) one structured extraction path consumes evidence bundles;
8) require evidence ID/locator for new trusted records; 9) preserve all reports; 10) run tests; 11) only
after stable, wire reconciliation to consume evidence spans. Do not expand scope beyond the current slice.
