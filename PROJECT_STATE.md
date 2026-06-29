# Project State

> Durable working memory for ALTA / project_db. Known bugs, architectural
> decisions, active and deferred plans, risks, model observations — anything a
> human or a coding agent noticed that must NOT be lost between sessions.
>
> Relationship to the other docs (see `CLAUDE.md` → "Documentation discipline"):
> `CLAUDE.md` = rules/philosophy (root). `project-db/README.md` = setup.
> `project-db/CHANGELOG.md` = dated append-only history.
> `project-db/docs/HANDOFF.md` = current engineering state (wiped each handoff).
> **This file** is the cross-session scratch/decision log that the four
> present-tense canonical files deliberately don't keep. Detailed plans for a
> specific large initiative live in their own doc (e.g.
> `EVIDENCE_REFACTOR.md`) and are linked from here.

## Current Focus

**Evidence-backed document parsing refactor.** Spine `Document -> DocumentParse ->
EvidenceSpan -> DocumentText (compat)` so parsers and the financial audit can cite
*where* a number came from instead of reading one flat blob. Full plan + checklist +
finishing conditions: **[EVIDENCE_REFACTOR.md](EVIDENCE_REFACTOR.md)**.

- Slice 1 (foundation: models + migration + compat write-back) — **DONE 2026-06-25**.
- Slice 2 (parser abstraction + MIME routing + CSV parser) — **DONE 2026-06-25**. Spine proven
  end-to-end; forward-compat groundwork (skipped path, batch pipeline, registry seam).
- Slice 3 (`XlsxParser` via openpyxl) — **DONE 2026-06-25**. Structure-preserving: sheets,
  header-below-title detection, formulas/merged/number-formats, `rows_sample` + raw
  `rows_preview`. Validated on 115 real HD files (0 failures). NO extraction behavior changed.
- Slice 3.1 (shared header detection) — **DONE 2026-06-25**. `parsing/tableutil.py` fixes the
  row-1-header bug on real estimates (Rockland); used by CSV + XLSX.
- Slice 4 (Docling PDF parser + PyMuPDF fallback) — **DONE 2026-06-25**. `PdfParser`: Docling
  (TableFormer) recovers tables w/ page+bbox+spanning headers; PyMuPDF fallback. Docling in a
  SEPARATE `[docling]` extra (NOT in CI), OCR off. Validated on real table-heavy PDFs.
- Slice 4.5 (integration backfill) — **DONE 2026-06-25**. `scripts/parse_documents.py` runs the new
  parsers over real Drive docs -> `DocumentParse`+`EvidenceSpan`+`DocumentText` (idempotent; applies
  the migration). Ran on Rockland: 9 docs -> 66 spans (27 table regions). The new parsers are now
  USED/runnable on the corpus, but NOT yet auto-wired into the live sync.
- Slice 4.6 (backfill wired into sync) — **DONE 2026-06-26**. `cmd_weekly_changes --sync` ->
  `_parse_recent_evidence`: recently-changed fast docs (CSV/XLSX/gsheet) parse into the spine on
  refresh, `write_text=False` (DocumentText untouched -> downstream-safe), idempotent. PDFs gated by
  `PROJECT_DB_PARSE_PDF_ON_SYNC=true` (Docling cost). 4 tests (test_sync_evidence.py).
- Slice 5 (evidence links on the ledgers) — **DONE 2026-06-26**. Nullable `evidence_span_id`
  (FK->evidence_span.id, ON DELETE SET NULL) + `evidence_locator_json` on FinancialRecord /
  FinancialLineItem / ContractObligation. Additive (old rows null; one span per record, no
  many-to-many). Migration applied to real DB; cols confirmed on all three. 5 tests
  (test_document_parse.py). Suite 1512. Invariant "no NEW trusted record without evidence" is
  recorded but NOT enforced yet — Slice 6 owns enforcement.
- Slice 6a (evidence-bundle reader) — **DONE 2026-06-26**. `ai/evidence_bundle.py::
  build_evidence_bundle` turns stored spans into an `EvidenceBundle` (labelled tables + locator +
  header_confidence + page text; `render_for_llm()`). Pure — no LLM/ledger/DocumentText. Hooks:
  `is_low_confidence()` (thr 0.5), `primary_span_id()`. Real proof on "927 QUOTE": renders from the
  true header row vs old flat text leading with ESTIMATE/metadata noise. 7 tests.
- Slice 6b (extractor reads structured evidence) — **DONE 2026-06-26**.
  `populate_ledger_llm_for_document` builds the bundle and feeds `render_for_llm()` to the LLM when a
  parse exists (else flat `DocumentText`); every `FinancialLineItem` stamped with
  `evidence_span_id`/`evidence_locator_json`; amounts verified vs flat+evidence; reconcile TRUST GATE
  unchanged. Low header-confidence (<0.5) + `strong_extractor` -> stronger model (CLI:
  `OPENAI_EXTRACT_STRONG_MODEL`). Default model bumped gpt-4o-mini -> gpt-4.1 (owner-approved). 4
  tests (test_financial_evidence.py).
- 6b LIVE-VALIDATED 2026-06-26 on real Rockland (gpt-4.1 A/B). Fixed a truncation bug (table caps
  25->300 rows; bundle/extractor char caps ->60k) so whole quote tables render -- "927 QUOTE" now
  reconciles exactly ($191,843.68). vs flat+gpt-4o-mini baseline: clearly better (flat drove ~1.9x
  double-counting; gpt-4o-mini mis-read the SOW; both fixed on most docs). Re-parse overwrote these
  docs' DocumentText with the new rendering (intended "replace old flat" migration).
- **TWO REAL RESIDUAL ISSUES (model-side, the actual next work):**
  1. DOUBLE-COUNTING: the extractor still sometimes sums a division TOTAL row PLUS its material/labour
     sub-rows (ACCEPTED QUOTE 63 lines $124k ~= 2x stated $66k; near-identical 927 QUOTE correct at 17
     lines). FIX = prompt refinement: when a section has a Total row AND component (material/labour)
     rows, extract the components OR the total, never both. Re-validate on Rockland after.
  2. UNVERIFIED TOTALS: model's stated_total not trustworthy alone (927 swung $126k->$191k run to run).
     FIX = Slice 7 deterministic verification: the stated_total / line sums must match a number that
     actually appears in the cited EvidenceSpan; flag mismatches; only then enforce
     no-trusted-record-without-evidence.
- DOUBLE-COUNTING FIXED 2026-06-26 (prompt v2): rule that a TOTAL-column row already sums its
  material/labour sub-rows -> extract section totals OR components, never both. Re-validated:
  ACCEPTED QUOTE 63 lines $124k (2x) -> 13 lines $66,539.65 EXACT; 927 QUOTE stays exact. SOW (multi-
  table PDF) now under-counts and EXTRAS slightly over -> both correctly QUARANTINED by the gate.
- SLICE 7 DONE 2026-06-26: `ai/evidence_verify.py` deterministic grounding; gate quarantines a
  reconcile whose stated_total is NOT in the cited evidence (`total_not_in_evidence`) -- catches
  hallucinated totals. Tests added.
- GRID->EVIDENCE MIGRATION DONE 2026-06-26 (owner-chosen). `parse_financial_grid_rows(rows)` factored
  out; `financial_grid_populator` reads `EvidenceSpan.rows_preview` for single-table docs + stamps
  evidence_span_id on grid rows. Fixes a latent regression: the corpus re-parse rewrote DocumentText
  to MARKDOWN, which the CSV grid parser couldn't read (927 -> 0 rows). ACCEPTED QUOTE now parses from
  evidence + reconciles $66,539.65. KEY ARCH FINDING: grid parser handles only Material/Labour/Total
  grids; current 927 QUOTE is Description+Total (sums $191,843.68 = the LLM number, CORRECT); the 56
  old grid rows ($233k) were STALE. Grid (M/L/T) + LLM (Desc+Total/unstructured) are COMPLEMENTARY.
  TODO: multi-sheet workbook tables still use text path; re-run fill-ledger + fill-ledger-llm to
  refresh real rows (clears 927's stale grid rows so the LLM path owns it).
- **Next: refresh real ledger + Slice 8.** (1) Run production `fill-ledger-llm` on real Rockland
  with gpt-4.1 + v2 prompt + Slice-7 gate; confirm the docs that pass write evidence-linked rows with
  correct totals and the rest quarantine; eyeball division margins vs reality. (2) Slice 8 =
  ReconciliationIssue storage + wire reconcile_financials_llm to evidence. Still pending: SOW multi-
  table PDF accuracy, per-LINE span attribution, enforce no-trusted-record-without-evidence,
  full-sync to backfill the 189 NULL folder_paths.

## REFOUNDATION PLAN (READ 2026-06-29) — `docs/MEETING_SYNTHESIS_financial_refoundation.md`
Authoritative plan (owner+PM) kept in repo. Read it before big parser/ledger changes. Full distilled
invariants in memory [[project-refoundation-plan]]. The parser/ledger/DB-relevant constraints:
- NORTH STAR: STRUCTURE & TRACEABILITY over prediction. Every cost traces SOW item -> package -> quote
  -> PO -> budget line -> actual. Alta-number estimator (§11) PARKED until ~20-50 clean projects.
- LEAVE ALONE (§9): 13-entity core + ExternalId; Project=join nucleus; LLM-advisor->Proposal gate;
  SQL/SQLite; **evidence spine (DocumentParse/EvidenceSpan) keep as-is**; CSI vocab; HD + labour spines.
- PARSING (§9): deterministic GRID parser becomes the MAIN path under templated SOP inputs; evidence/
  LLM tolerance (Docling/XlsxParser/LLM) DEMOTED to FALLBACK for legacy + third-party docs. My grid->
  evidence migration is aligned. The VALUE is the per-division LINE-ITEM material/labour split, NOT the
  aggregate total (PM confirmed). => the $361k "contracted revenue" is a WRONG aggregation, not a target.
- DON'T OVER-INVEST IN (SOPs supersede): folder_path/category project attribution (-> `job_number` on
  Project); quote-status GUESSING (accepted/verified/1/2/3 -> deterministic status-label read; this
  guessing IS the $361k bug: 927 mis-counted as contracted); forcing HD/hourly to line items (tolerance
  buckets vs job#, not precision).
- INVARIANTS: outside-SOW -> tracked ChangeOrder never silent; flag never silently sort; material spec
  drives material/labour; client never sees internal numbers; takeoff(quantities) vs site-visit
  (conditions) kept separate; cross-doc rollups must not double-count (the $361k = ACCEPTED QUOTE
  $66,539.65 + its SOW $66,539.65 same money + 927 mis-classified).
- NEW entities (build LATER): SowItem, SowPackage, SubcontractorQuote (has evidence_span_id <- my
  spine), BudgetSnapshot, PurchaseOrder (emits ContractObligation), ChangeOrder (generalize
  extras_grid). EXTEND FinancialLineItem +purchase_type +cost_status(estimated->quoted->committed->
  actual); EXTEND Project +job_number.
- ACTION: do NOT start building this yet (owner: settle conventions first, doc §10 step 1 + §12 Qs).
  HOLD Slice 8. Structure current work to fit; don't pre-empt with large permanent parser changes.

### PRIVACY FIX 2026-06-26 (delta sync leaked files outside the team root) — RESOLVED
- Symptom: corpus revamp processed private personal files NOT under the configured root.
- Cause: `_delta_sync` ingested every `changes.list` result (corpora="allDrives", not folder-scoped);
  impersonated account is a personal Gmail and the root is a My-Drive folder, so any edited file
  anywhere leaked in. Full crawl was fine; only delta lacked containment.
- Fix: `_delta_sync` now verifies each changed file is a descendant of `root_folder` (memoised
  parent-chain walk); unverifiable ancestry -> skip (privacy-safe). Tests in test_gdrive_connector.py.
- Cleanup: authoritative Drive walk of the root (1188 files, 0 failures) -> purged 374 foreign docs
  + all derived rows; verified 0 orphans, deleted set confirmed under_root=False, 0 shortcuts. 1187
  team docs kept. DB backed up (project_db.sqlite.bak_foreignpurge_*). One-off script lived in
  scratchpad (not committed — destructive remediation, not a feature).
- FOLLOW-UP 2026-06-26: delta sync also ingested FOLDERS as Document rows (full crawl skips them).
  Found 9 team project/bucket folders (e.g. "923-927 Rockland", "655 Victoria") as junk Documents --
  NOT private (team-owned), no derived rows. Fixed: `_delta_sync` now skips `mimeType==folder` before
  the containment check. Purged the 9 (one-off). Live documents now = 1189 (all files under root).
- NOTE for future: any time delta sync or impersonation config changes, re-check containment.

### STORAGE MODEL (answer to "where does parsed data live / does it replace the old?")
- `DocumentParse` (one row per parse run: rendered_text + structured_json + status) and
  `EvidenceSpan` (citeable page/sheet/table/cell units) ARE the new canonical storage. NOT a new
  system beyond these two tables. `DocumentText` is kept as a compatibility VIEW (written from a
  successful parse), so old reports/search keep working.
- `FinancialRecord`/`FinancialLineItem`/`ContractObligation` are NOT replaced yet. Slices 5-7 add
  evidence links and switch the financial extractor to read the structured `EvidenceSpan`s instead
  of flat text; old rows stay valid through the transition.
- Sync: `parse_documents.py` is the manual backfill today. Wiring it into the live refresh (so a
  sync re-parses changed docs via md5) is the integration step after the parsers are proven.
- RUNTIME/DEPLOYMENT (measured): Docling PDF parsing is ~220s avg / 728s max per PDF on this CPU ->
  the 452-PDF corpus is ~a day on this laptop. Local-model work (Docling, embeddings) + always-on
  services (refresh, gmail/telegram ingestion) belong on a dedicated server (ideally GPU), NOT on
  each coworker's machine. Mitigations: financial-docs-only scope, pypdfium backend (faster, lower
  table quality), or GPU.

## Known Bugs

- [ ] Bug: Spreadsheet (XLSX/CSV) content is flattened to one text blob in `DocumentText`.
  - Evidence: 3940 Côte-des-Neiges "Quotes" — a vendor cost worksheet (a "Company"
    column listing JCPerault / NouvelAir / Boutin Conteneur…) reads like a client
    quote once linearized, so $123,393.83 of supplier cost was booked as revenue.
    Multi-sheet workbooks and side-by-side tables lose their boundaries.
  - Suspected cause: `DocumentText` stores a single flat string; no sheet / table /
    cell-range structure survives extraction.
  - Next action: openpyxl parser writing `EvidenceSpan` table/cell regions (later
    slice — NOT slice 1). Slice 1 only lays the table foundation.

- [ ] Bug: CI ruff likely RED from version drift, NOT from any recent code change.
  - Evidence: `python -m ruff check .` (local ruff 0.15.18) reports 9 errors in three files
    untouched since the 2026-06-16 sweep: `src/project_db/ai/views.py` (UP037 + F821
    `datetime` undefined-name in string annotations, lines ~457/917/919),
    `src/project_db/ai/telegram_intake.py:518` (RUF059 unused unpacked `method`), and
    `tests/test_weekly_narration.py:18` (F401 unused FieldNote/NoteChannel/NoteClass imports).
  - Suspected cause: `pyproject` pins `ruff>=0.5` (unpinned floor); CI installs the latest
    ruff, whose newer rule behavior flags code that was clean in June. The `datetime` F821
    pair may be a latent real bug (string annotation referencing an unimported name).
  - Next action: pin ruff to a known-good version OR clear the 9 (mostly trivial: drop unused
    imports, de-quote annotations + import `datetime`, rename unused unpack to `_`). Out of
    Slice-1 scope — flagged as a separate task. Slice-1 files are ruff-clean.

- [ ] Bug: Financial reconciliation reads `DocumentText` flat blobs, not the structured
    cost/trade ledger and not via the RAG retrieval layer (`DocumentChunk` embeddings).
  - Evidence: `scripts/reconcile_financials_llm.py` consumes flat per-doc text excerpts
    exported by `scripts/export_financial_bundles.py`.
  - Suspected cause: no citeable evidence layer existed; bundles are flat text.
  - Next action: once `EvidenceSpan` exists and parsers populate it, reconciliation can
    consume evidence spans instead of flat bundles (later slice).

## Architectural Decisions

- Decision: Target architecture is `Document -> DocumentParse -> EvidenceSpan -> existing
  DocumentText compatibility layer -> later FinancialRecord / FinancialLineItem /
  ContractObligation evidence links`.
  - Date: 2026-06-25
  - Reason: Auditing needs provenance ("which doc / parser / page / sheet / range / model
    run produced this number, and was the amount verified?"). A flat text blob destroys
    layout, table boundaries, cell addresses, and formulas.
  - Consequence: `DocumentText` becomes a *compatibility output* of parsing, not the
    canonical source. Existing reports/search keep working unchanged.

- Decision: `DocumentText` stays as a compatibility layer; do NOT delete its logic.
  - Date: 2026-06-25
  - Reason: Existing reports, search, RAG embedding, and the financial extractors all read
    it. Breaking it would break the whole app.
  - Consequence: After every successful `DocumentParse`, write-through to `DocumentText`.

- Decision: Markdown is a *report view*, never the source of truth. Structured data
  (`DocumentParse.structured_json`, `EvidenceSpan`, ledger rows linked to evidence) is
  canonical; reports are generated FROM it.
  - Date: 2026-06-25
  - Reason: The earlier Claude-agent reconciliation pattern (agents emit markdown, another
    merges markdown, system treats final markdown as truth) is unauditable.
  - Consequence: The system should be auditable by construction.

- Decision (POLICY, not yet implemented — see Open Questions): for judgment-heavy LLM
  calls that require certainty (client-vs-vendor role, quote-vs-supplier-worksheet,
  SOW-vs-duplicate, side inversion, ambiguous lifecycle), prefer the stronger model
  (`gpt-4.1` or better), reserving cheap models for simple parsing / ingestion
  comprehension. Pin model snapshots; a single error the cheap model makes is a priority
  bug.
  - Date: 2026-06-25
  - Reason: Live audit run showed `gpt-4o-mini` invents false errors AND misses real ones;
    `gpt-4o` misses subtle cross-doc patterns; `gpt-4.1` got all of them right.
  - Consequence: drains more credits; acceptable given correctness is the priority. NOT
    applied in slice 1 (slice 1 touches no extraction logic).

## Current Plan

Active: **Slice 1** of the evidence refactor (Tasks 1–6 in
[EVIDENCE_REFACTOR.md](EVIDENCE_REFACTOR.md)):

1. `PROJECT_STATE.md` (this file) + `EVIDENCE_REFACTOR.md` reference doc.
2. Add `DocumentParse` + `EvidenceSpan` models.
3. Add SQLite migration for both tables.
4. Add `DocumentText` compatibility write-back helper.
5. Add tests (create, link, cascade-delete, write-back, suite stays green).
6. Update this file with results + deferred next step.

## Deferred Plans

Valid, but explicitly NOT in slice 1 (do not build until their slice):

- App-owned artifact store (raw files stay in Drive/CompanyCam; never giant SQL blobs).
- Docling PDF parser (use the Docling library, not raw HF `AutoModel`).
- openpyxl XLSX/XLS parser (highest-risk flattened format — do this parser FIRST among parsers).
- Parser abstraction + MIME routing (`ParsedDocument`/`ParsedEvidence`).
- Evidence-bundle financial extraction (extractor reads latest `DocumentParse` + `EvidenceSpan`,
  not only `DocumentText`); structured-output schema with evidence index + role/lifecycle classifiers.
- Nullable `evidence_span_id` / `evidence_locator_json` on FinancialRecord / FinancialLineItem /
  ContractObligation; invariant: no new *trusted* record without evidence.
- `ReconciliationIssue` storage (issue_type / severity / status / deltas / evidence_json); keep
  `reconcile_financials_llm.py` read-only/advisory until then.
- Deterministic verification (amount exists in cited evidence, span/doc IDs resolve, hash matches);
  an evidence-grounded LLM verifier later (refute only on concrete contradiction; never silently erase).
- Snapshot export/import.
- Apply the stronger-model policy across certainty-requiring calls; Batch API for nightly audits.
- **Faceted / hierarchical retrieval (owner idea 2026-06-26).** Askbot RAG currently pulls
  same-worded evidence from UNRELATED projects (flat global cosine pool -> cross-project
  contamination). Owner wants tree/faceted fetch: `project -> unit -> trade` (or `side
  (income/expense) -> ...`) so an agent filters-then-ranks down the relevant branch. The evidence
  layer makes the facets available: every `EvidenceSpan`/`DocumentChunk` already carries
  `project_id`; add `unit` / `division_code` / `side` facets and filter retrieval by them. This is a
  RETRIEVAL refactor — do it AFTER the evidence layer feeds the ledger (post Slice 6/7), not now
  (build freeze, one slice at a time). Stay relational (SQL filter + existing hybrid RRF); no
  graph/vector service. Keep it CLEAN, not "everything everywhere" — the owner's own caveat.

## Decisions (2026-06-26)
- **Model upgrade approved (owner):** permanently move the financial/certainty-requiring LLM calls
  OFF `gpt-4o-mini` to a stronger model if it delivers better results (gpt-4o-mini/4o proved
  unreliable on the audit). Apply in Slice 6b at the extractor call (env `OPENAI_EXTRACT_MODEL`
  default bump + low-confidence escalation to an even stronger tier). Validate the win on real docs
  before locking the default.

## Risks / Drift Warnings

- Do NOT rewrite the app, rename existing models, or change financial extraction logic in slice 1.
- Do NOT create a per-cell spreadsheet `Cell` table, many-to-many evidence joins, GraphRAG,
  multi-agent swarms, adversarial-verifier frameworks, or automatic ledger mutation.
- Reconciliation must stay advisory: it proposes corrections; humans approve before any ledger change.
- `DocumentText` write-back must be additive — never delete the existing extract path.
- The migration system is custom (`db/migrations.py::ensure_sqlite_schema`), NOT Alembic. Every new
  table needs BOTH a SQLAlchemy model (for `create_all` / fresh DBs) AND a DDL block wired into
  `ensure_sqlite_schema` (for existing local SQLite files). Keep FK-dependency creation order correct.
- Avoid scope creep: each slice has a Definition of Done; close it before starting the next.
- **Lint gate (owner, 2026-06-25):** run ruff (`ruff check .` + `format --check`) and keep it
  GREEN *before* continuing to the next feature/slice — not only at the end. Don't stack work on
  an un-linted base. (CI ruff is blocking and `ruff>=0.5` is unpinned, so drift happens.)
- **Re-anchor each step (owner, 2026-06-25):** before and during any slice, re-read its Definition
  of Done + hard scope limits and quote them back to yourself, so the plan stays rock-steady and
  you don't overflow/drift.
- **Basal/upstream caution (owner, 2026-06-25):** the parse/ingestion spine is foundational —
  changing a shared/upstream object (models, the parse layer, `DocumentText`) can ripple across
  many files/functions. Think twice, enumerate downstream consumers first, prefer additive/
  backward-compatible changes, and update all affected call sites + tests in the same pass.

## Completed Since Last Update

- 2026-06-25: **Slice 1 (foundation) COMPLETE.** Added the evidence-parsing spine with no
  change to financial extraction behavior.
  - Implemented: `DocumentParse` + `EvidenceSpan` SQLAlchemy models (plain-string
    `PARSE_STATUSES` / `EVIDENCE_TYPES`, no DB enums); SQLite migration wired into
    `ensure_sqlite_schema` (document_parse before evidence_span for FK order, with indexes);
    `db/parse_compat.py::write_document_text_from_parse` compatibility write-back
    (upserts `DocumentText` from a successful parse's `rendered_text`; skips non-success).
  - Files changed: `src/project_db/db/models/docs.py`,
    `src/project_db/db/models/__init__.py`, `src/project_db/db/migrations.py`,
    `src/project_db/db/parse_compat.py` (new), `tests/test_document_parse.py` (new),
    plus docs `PROJECT_STATE.md` + `EVIDENCE_REFACTOR.md` (new).
  - Tests: 7 new in `test_document_parse.py` (create parse; link evidence; cascade-delete;
    write-back create/update/skip; migration on blank DB). Full suite **1482 passed**;
    ruff clean.
  - Deferred next step (Slice 2): parser abstraction + MIME routing + a CSV parser to prove
    the spine end-to-end (DocumentParse + EvidenceSpan + DocumentText written by a real
    parser). Then openpyxl (Slice 3), then Docling (Slice 4). NO extraction-logic changes
    until Slice 5+. See [EVIDENCE_REFACTOR.md](EVIDENCE_REFACTOR.md).

- 2026-06-25: **Slice 2 (parser abstraction + MIME routing + CSV parser) COMPLETE**, plus the
  authorized forward-compat groundwork. New `src/project_db/parsing/` package: `base.py`
  (`ParsedDocument`/`ParsedEvidence`/`DocumentParser`), `csv_parser.py` (`CsvParser` v1 —
  header + delimiter sniffing incl. Quebec `;`, Markdown render, `table_region` EvidenceSpan
  with structured sample), `router.py` (`get_parser_for`/`register_parser` seam), `service.py`
  (`parse_document_content` persists the full spine; `skipped`/`failed` handled, never raises;
  `parse_documents` batch pipeline). ADDITIVE — live `extract_and_store` untouched, not wired
  into live sync. 9 tests in `test_parsing.py`; full suite **1491 passed**; ruff + format clean.
  Deferred next: Slice 3 `XlsxParser` (openpyxl).

- 2026-06-25: **Slice 3 (`XlsxParser` via openpyxl) COMPLETE.** New `parsing/xlsx_parser.py`
  (registered): per-sheet `table_region` EvidenceSpan with detected header (skips title rows),
  `rows_sample` {header:value} + raw `rows_preview`, `merged_ranges`, and a compact `cells` map
  of formula cells (formula + number_format + cached value). Bounded; `.xls` → skipped; ADDITIVE
  (live `extract_xlsx` untouched). **Correctness validated on real data per owner's directive**:
  swept all 115 Home Depot `.xlsx` (0 failures/anomalies; headers/values matched a manual read);
  synthetic workbooks cover formulas/merged/title-rows/multi-sheet. **Downstream check (honest):**
  gpt-4o-mini classified a reconstructed 3940 vendor sheet as `cost` from BOTH old-flat and
  new-structured input — flattening wasn't the sole cause of the original error; XlsxParser's win
  is robustness + cell citation for Slice 6, not flat-text classification. 7 tests in
  `test_xlsx_parsing.py`; full suite **1498 passed**; ruff + format clean. Deferred next: Slice 4
  Docling PDF.

- 2026-06-25: **Slice 3.1 + Slice 4 COMPLETE.**
  - 3.1 (header detection): real Rockland estimate exposed that CSV took row 1 (`,ESTIMATE,,,,`) as
    the header. Shared `parsing/tableutil.py::detect_header_index` (header-like row with the MOST
    filled cells) used by CSV + XLSX; raw `rows_preview` safety net. Rockland header now row 6;
    115 HD xlsx still row 1. Recorded KNOWN GAPS (multi-table-per-sheet; nested subtotals).
  - 4 (PDF): `parsing/pdf_parser.py` `PdfParser` (registered). Docling (layout + TableFormer) →
    `table_region` spans with page+bbox+spanning-header recovery + `page` spans; PyMuPDF fallback.
    Docling = SEPARATE `[docling]` extra (NOT CI; `pip install -e ".[docling]"`; torch+onnx, models
    in `~/.cache/huggingface`); OCR off (digital PDFs; rapidocr default model is broken). Validated
    on real table-heavy PDFs (spanning header `native backend.TTS` recovered). Adding PdfParser
    rippled into 2 Slice-2 tests (used PDF as "unsupported" example) — fixed to an image mime.
    4 tests in `test_pdf_parsing.py`; full suite **1503 passed**; ruff + format clean. Next: Slice 5.

## Open Questions

- Stronger-model policy (gpt-4.1+ for certainty-requiring calls): flip the global default now, or
  introduce a separate `OPENAI_RECONCILE_MODEL` / per-call tiering and migrate gradually? (Out of
  slice-1 scope; needs a deliberate change to extraction config + a cost check.)
- `PROJECT_STATE.md` / `EVIDENCE_REFACTOR.md` live at repo root for discoverability; the four
  canonical docs live in `project-db/`. Confirm this placement is what you want, or move them under
  `project-db/`.
