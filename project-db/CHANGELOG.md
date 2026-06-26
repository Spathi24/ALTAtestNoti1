# ALTA / project_db — Work Log

A day-by-day journal of what was built, what works, and how the project's
capability grew. Newest entry on top. Lower-level "what changed" detail
is in commit messages; this is the human-readable version.

If you want **"what can this product do today?"** read the top entry.
If you want **"how did we get here?"** read top to bottom.

---

## 2026-06-26 -- Evidence-bundle reader: stored evidence -> AI-readable input (Slice 6a)

The READ side of the spine. `ai/evidence_bundle.py::build_evidence_bundle` loads
a document's latest successful `DocumentParse` + `EvidenceSpan` rows and assembles
them into an `EvidenceBundle`: structured tables (headers + sampled rows) tagged
with their sheet/page/range locator and `header_confidence`, plus PDF page text.
`render_for_llm()` emits labelled Markdown tables instead of a flat blob.

Why it matters (real proof, live DB): for "927 QUOTE", the bundle renders the
table starting at the TRUE header row (row 6, confidence 1.0) with clean columns
(Description / Material / Labour / Total) -- while the old flat `DocumentText`
dumps the ESTIMATE/address/`Estimate #`/`Valid Until` metadata rows first, the
exact noise that misleads the extractor about doc type and columns.

Pure: no LLM, no ledger writes, does not touch `DocumentText`. Returns `None` when
a doc has no successful parse (caller falls back to flat text -- additive). Also
exposes the Slice-6b hooks: `is_low_confidence()` (the deterministic -> LLM
escalation gate, threshold 0.5) and `primary_span_id()` (which span to cite as
`evidence_span_id`). 7 tests in `test_evidence_bundle.py`.

Slice 6b (next) wires this into `financial_llm_extractor.py`: read the bundle
instead of flat text, set the evidence link, and escalate low-confidence docs to
a stronger model (owner approved permanently upgrading off gpt-4o-mini).

## 2026-06-26 -- Evidence spine wired into sync + evidence links on the ledgers (Slice 5)

Two additive steps, both downstream-safe (no financial numbers move yet; that is
Slice 6's deliberate switch).

**Backfill wired into live sync.** `cmd_weekly_changes --sync` now calls
`_parse_recent_evidence` after the legacy content extraction: recently-changed
fast docs (CSV / XLSX / Google Sheets, ~0.05s each) are parsed into
`DocumentParse` + `EvidenceSpan` so the spine fills automatically on refresh.
It is idempotent (skips docs with a successful parse, no fetch) and uses
`write_text=False`, so the legacy `DocumentText` the reports read today is left
untouched. PDFs are gated OFF by default (Docling costs minutes/doc on CPU --
see runtime notes) behind `PROJECT_DB_PARSE_PDF_ON_SYNC=true`. 4 tests in
`test_sync_evidence.py`.

**Evidence links on the ledgers (Slice 5).** Added nullable `evidence_span_id`
(FK -> `evidence_span.id`, `ON DELETE SET NULL`) + `evidence_locator_json` to
`FinancialRecord`, `FinancialLineItem`, and `ContractObligation`. Additive: old
rows stay valid (link is null), one span per record (no many-to-many; extra
spans live in `source_meta_json` during transition). `SET NULL` means deleting a
span never deletes the financial fact -- it just drops the citation. Models +
migration DDL + ALTER columns wired into `ensure_sqlite_schema`; applied to the
real `project_db.sqlite` (columns confirmed present on all three tables). 5
tests in `test_document_parse.py`. Suite 1512.

The invariant "no NEW trusted record without an evidence link" is recorded but
NOT enforced yet -- enforcement waits until Slice 6 makes the extractor read
spans and set the link.

## 2026-06-25 -- Evidence-backed parsing: integration backfill + header confidence

Makes the new parsers actually USED on the real corpus. `scripts/parse_documents.py`
fetches each Drive document's bytes and runs the new parsers ->
``DocumentParse`` + ``EvidenceSpan`` + a synced ``DocumentText`` (the new
structure-preserving parse becomes canonical; ``DocumentText`` stays a
compatibility view). Idempotent (skips already-parsed; ``--overwrite`` re-does),
bounded (``--project`` / ``--limit`` / ``--all``), and it applies the SQLite
migration to the real DB itself. PDF pages are capped (60) so a 1000-page
building code can't dominate.

Ran on the real Rockland project: 9 documents -> 9 DocumentParse + 66
EvidenceSpan rows (39 page + 27 table regions); the window-spec PDF gave 16
tables, the estimates 3 each, the Google-Sheet estimates got their real headers
detected. Stale-data proof: the old extraction had Rockland JOB COST at $50.71;
the live sheet now totals $5,675.38 -- exactly why re-parsing matters.

RUNTIME reality (measured, this CPU): Docling PDFs ~220s avg, 728s max; Google
Sheets ~0.05s. The full ~452-PDF corpus is ~a day on this laptop -> local-model
work belongs on a dedicated server (ideally GPU), not each coworker's machine
(mitigations: financial-docs-only scope, pypdfium backend, or GPU).

Also: ``tableutil.detect_header`` now returns a confidence, carried on table
spans as ``header_confidence`` -- an uncertainty signal the Slice-6 extractor can
act on (re-derive the header via the LLM only when low), instead of calling the
LLM per file. NOT yet auto-wired into the live sync. Full suite 1504 passed;
ruff + format clean.

---

## 2026-06-25 -- Evidence-backed parsing: Docling PDF parser (Slice 4)

``PdfParser`` with two backends. When the optional ``[docling]`` extra is
installed, Docling (IBM's layout-analysis + TableFormer models) recovers each
table's structure with its page number and bounding box, including SPANNING
HEADERS and nested row/column hierarchy -- the "figure it out from row/column
labels" shape that flat PDF text destroys. Each table becomes a ``table_region``
EvidenceSpan (headers + structured rows_sample + page/bbox) and each page a
``page`` span; ``export_to_markdown`` is the DocumentText-compatible rendering.
When Docling is absent or a conversion errors, it falls back to the existing
PyMuPDF text path (page spans) -- it never raises.

Docling is a heavy, OPTIONAL dependency kept in a separate ``[docling]`` extra
that is deliberately NOT in CI (pulls torch + onnxruntime, ~500MB HuggingFace
models on first run). OCR is disabled (these are digital PDFs; the default
rapidocr model is broken in this build, and skipping OCR is faster) -- scanned
PDFs are a future option. Validated on real table-heavy PDFs: the 9-page Docling
paper's complex table was recovered with its multi-column spanning header
(``native backend.TTS`` / ``native backend.Pages/s``), each column traceable to
its full header path. (Real active-project estimate/invoice PDFs live in Drive,
not on disk; validate on fetched project PDFs once Drive access is wired.)

Registering the PDF parser correctly rippled into two earlier tests that used
"PDF" as their unsupported-type example -- now an image mime; the suite caught
it. 4 new tests (fallback forced for CI; Docling path gated on import). Full
suite 1503 passed; ruff + format clean. Next: Slice 5 -- nullable evidence links
on the financial records.

---

## 2026-06-25 -- Evidence-backed parsing: XLSX parser (Slice 3)

``XlsxParser`` (openpyxl) -- the structure-preserving spreadsheet parser, since
flattened workbooks were the worst troublemakers. Per sheet it emits one
``table_region`` EvidenceSpan with: a detected header row (skips a title/metadata
row sitting above it), a ``rows_sample`` of ``{header: value}`` dicts (values stay
bound to their column -- the 3940 lesson), a raw ``rows_preview`` safety net,
``merged_ranges``, and a compact ``cells`` map of FORMULA cells (formula +
number_format + cached value) so a ``=SUM`` total is citeable and not mistaken for
a line item. Bounded; ``.xls`` legacy (openpyxl can't read it) routes to a
skipped parse.

Validated on REAL data, not just synthetic: swept all 115 Home Depot ``.xlsx``
exports -- 0 failures, 0 anomalies, headers/values/sheet structure matched a
by-hand read. Honest downstream finding: feeding a reconstructed 3940 vendor-cost
worksheet to gpt-4o-mini as OLD flat text vs NEW structured evidence, BOTH were
classified ``cost`` correctly -- so flattening was not the sole cause of the
original 3940 mis-booking (that was the financial extractor's doc_type->side
logic, fixed earlier). The XlsxParser's payoff is robustness on harder shapes +
cell-level citation for the future evidence-bundle extractor, not a flat-text
classification win on simple single tables.

ADDITIVE: live ``extract_xlsx`` / ``extract_and_store`` untouched, seam not wired
into live sync, no extraction behavior changed. 7 new tests; full suite 1498
passed; ruff + format clean. Next: Slice 4 -- Docling PDF parser.

---

## 2026-06-25 -- Evidence-backed parsing: parser abstraction + CSV (Slice 2)

Proves the Slice-1 spine end to end with the first real parser. New
``src/project_db/parsing/`` package: a pure parser interface
(``ParsedDocument`` / ``ParsedEvidence`` / ``DocumentParser`` -- bytes in,
structured evidence out, no DB/network), MIME/extension routing with a one-line
``register_parser`` extension point, and a ``CsvParser`` that PRESERVES table
structure instead of flattening (header detection; comma/semicolon/tab/pipe
delimiter sniffing, so Quebec ``;`` CSVs parse correctly; a Markdown table for
DocumentText compatibility; and a ``table_region`` EvidenceSpan carrying headers
+ a structured row sample). ``parse_document_content`` persists the whole spine
(DocumentParse + EvidenceSpan + compat DocumentText); an unknown type records a
``skipped`` parse and a parser exception a ``failed`` parse -- it never raises.
``parse_documents`` is a batch pipeline helper for a future re-parse job.

ADDITIVE: the live Drive ``extract_and_store`` path is untouched and this seam is
not yet wired into the live sync (a later integration step), so no financial
extraction or ingestion behavior changed. 9 new tests; full suite 1491 passed;
ruff + format clean. Next: Slice 3 -- ``XlsxParser`` via openpyxl (the
highest-risk flattened format, the root of the 3940 worksheet confusion).

---

## 2026-06-25 -- Evidence-backed parsing: foundation (Slice 1)

First slice of the evidence refactor (full plan: `EVIDENCE_REFACTOR.md` at repo
root; durable working memory: `PROJECT_STATE.md`). The audit currently reads
flat `DocumentText` blobs, which destroy table/sheet/cell structure -- that is
why a vendor cost worksheet (3940's "Quotes") could read like a client quote.
The fix is a citeable evidence layer: ``Document -> DocumentParse ->
EvidenceSpan -> DocumentText (compatibility)``.

This slice adds only the foundation, changing NO financial-extraction behavior:
two models (``DocumentParse`` = one parse run per document; ``EvidenceSpan`` = a
citeable page/sheet/table/cell unit), their SQLite migration (cascade-delete with
the Document), and ``db/parse_compat.write_document_text_from_parse`` which keeps
the legacy ``DocumentText`` row in sync from a successful parse's rendering so all
existing reports/search/RAG keep working. Statuses/types are plain strings
(schema-light). No parser writes these yet (CSV/openpyxl/Docling are later
slices); no Cell table, no many-to-many, no automatic ledger mutation. 7 new
tests; full suite 1482 passed; ruff clean.

Also this session (advisory, no DB writes): an OpenAI cross-document
reconciliation auditor (`scripts/reconcile_financials_llm.py`, gpt-4.1) that
reads each project's documents together and flags duplicates / SOW restatements /
supplier-worksheet-as-revenue / side inversions for human approval.

---

## 2026-06-23 -- Home Depot: in-store/online duplicate flagging

Home Depot's export lists BODFS / online-pickup events twice -- once as an
in-store transaction number (``7149-...``) and once as an online order number
(``0641...`` / ``0616...``), same amount and date. New ``homedepot dedupe``
detects these pairs (equal ``|total|``, same refund sign, same project, sales
dates within 2 days, one dashed + one plain-digit number), previews them, and
with ``--apply`` flags the online twin via a new ``duplicate_of_id`` column so it
is EXCLUDED from every total -- the row is kept (reversible, evidence intact),
mirroring the dedupe philosophy of the financial reconcile gate. Standalone
online orders with no in-store twin are left untouched.

On the real ledger this caught 5 pairs (1 purchase $3,408.78 + 4 refunds),
correcting net spend $58,997.52 -> $57,188.31, gross -> $61,210.43, and
St-Laurent $27,437 -> $24,028. 4 new tests; full suite green.

---

## 2026-06-23 -- Home Depot: by-hand audit fixes a digit-fragment mis-link

A hand audit of the loaded ledger (after the owner backfilled 19 detail exports)
caught a real attribution bug. The job->project substring pass matched on raw
characters, so the register-default job ``"0"`` matched ``"3940 Cote des Neiges"``
via the ``0`` inside ``3940`` -- silently filing 49 untagged transactions
($13,689.39) under Cote-des-Neiges, which actually has NO identifiable Home Depot
spend. ``"00"`` likewise hit ``"...1001..."``.

Fix: ``link_job_to_project`` now matches on WHOLE-TOKEN boundaries
(``_phrase_in``), so a real street-number job (``"3940"``) still resolves but a
digit fragment never does. After re-link: 105/190 linked (was a false 155).
Honest portfolio picture now: St-Laurent $27,437 (the only well-covered
project), Rockland $2,088, St-Mathieu $1,555, and **$27,917 (47%) UNRESOLVED** --
dominated by ``"0"`` ($13.7k, no job entered) and online ``BODFS/ONLINE ORDER``
($16k). Per-project Home Depot costing is only as good as the job code typed at
the till; ~half of spend currently has none.

Also surfaced (not auto-changed -- needs owner judgement): (1) Home Depot's
detail export leaves ``Product Name`` blank for most rows -- we capture SKU + qty
+ price, not descriptions. (2) Suspected duplicate transaction pairs where one
in-store transaction number and one online order number (``0616.../0641...``)
carry the identical amount/date -- one purchase ($3,408.78) + several refunds,
~$4.7k+. Flagged for the owner; the ledger does not dedupe them automatically.

---

## 2026-06-23 -- Home Depot Pro purchase ledger: import spine (variable-cost leak #1)

The owner's #1 named cost leak gets its spine. The Home Depot Pro site exports
two Excel shapes: a **transaction** export (24 months of headers -- date, txn
number, store, job name, status, purchaser, subtotal, total; no line items) and
a per-transaction **detail** export (SKU, product name, qty, unit price, line
subtotal) that the site only emits one receipt at a time, behind ~5 clicks.
This change ingests both deterministically -- no browser, no LLM, no network.

**New ledger (`home_depot_transaction` + `home_depot_line_item`).** Standalone
tables keyed by `transaction_number` (the receipt's natural key), like the
labour-intake layer -- NOT bridged through `ExternalId`. Headers upsert in place
(re-importing the 24-month export is idempotent); a transaction's line items are
replaced wholesale on detail import (fresh snapshot, self-healing). Raw values
kept verbatim (`job_name_raw`, `product_name`, untouched row in
`source_meta_json`).

**Nothing trusted to the source.** `tax` is re-derived (`total - subtotal`);
refunds flagged by negative total; the line-item sum is reconciled against the
header subtotal, and a mismatch lands `detail_status='unbalanced'` for review
rather than being silently absorbed. The line-item backfill state lives on the
header (`detail_status`, `detail_attempts`, ...) -- the work-queue, no side table.

**Project attribution (`Project` stays the join nucleus).** `job_name` resolves
to a project in descending confidence: exact name/code, substring, then a
unique street-prefix pass for till abbreviations (`STL`/`STLAU`/`STL-GIFT-K` ->
`5768 St-Laurent`, `STMAT` -> `1455 Rue St. Mathieu`) -- only when it resolves to
exactly one project. Never guessed: `ONLINE ORDER` / `BODFS Order` / `TANIA` /
blank stay `unresolved`, raw label always kept. `homedepot relink` re-runs
linking after projects change.

**Validated on the real export.** 190 transactions, 17 refunds, **$64,619.21
gross / $58,997.52 net**; linking resolves 155/190 (unresolved $14.2k is the
genuinely project-less online/BODFS/blank rows). The one real detail export
(STL-GIFT-K) reconciles to the penny ($111.58 = 23.27 + 44.97 + 43.34).

**CLI** (behind the `homedepot` flag): `homedepot import <files|dirs>`,
`status` (spend + backfill coverage), `report [--by-item]` (spend by project /
top SKUs), `queue` (pending txns ranked by $ -- the manual-export work-list),
`relink`. 40 new tests; full suite green (1467).

**Line-item backfill = manual, by design (Phase-2 bot abandoned).** A logged-in
Playwright bot to auto-replay the per-receipt detail export was prototyped and
**dropped**: Home Depot's Akamai bot-protection reset/stalled the automated
browser at page load (ERR_HTTP2_PROTOCOL_ERROR / ERR_CONNECTION_RESET), and the
owner (rightly) would not risk the company Pro account on a scraper. The line
items the owner cares about are exported **by hand** -- `homedepot queue` ranks
which receipts are worth the clicks (top ~50 txns ≈ 80% of spend), and
`homedepot import <folder>` ingests the exported xlsx in bulk. No browser
automation in the product.

---

## 2026-06-23 -- Telegram general intake: anyone can text, into the weekly report

The owner's chosen value angle: the bosses ARE the Drive/Monday admins, so that
data is low-marginal-value; the untapped signal is field communications. The
Telegram bot was revamped from "labour hours only, invite-gated" to "anyone can
text any site update, and it flows into the weekly per-project report."

**Architecture (no new tables, no migration).** Every message is still recorded
as exactly one source-agnostic `LabourSourceEvent` (real send time, sender id,
raw text). Two paths fork off that single row: (A) the LABOUR path is unchanged
and still specialized -- a bound worker + the OpenAI extractor produce
LabourClaims; (B) a new GENERAL path keeps any sender's message as
`ingestion_status='received'` (reason `general_content`) with a deterministic
project attribution. The old behaviors (quarantine strangers / drop non-labour)
are preserved only when general intake is OFF.

**Deterministic project attribution** (`_attribute_project`, no LLM): explicit
site-name match in the text → bound worker's default project → recency-weighted
vote over the sender's last 14 days (7-day half-life, needs ≥60% dominance) →
otherwise unresolved. Constant site-switchers (PMs) never reach dominance and
fall to a project-less section rather than being mis-filed.

**Weekly report** gained a 5th event source: telegram `LabourSourceEvent` rows
(status in {received, extracted}) surface as "communications" in each project's
chronological events, timestamped by real send time; project-less messages go to
a new top-level `site_communications` section so nothing is dropped. Anonymous
senders show as a bound Worker name or `sender <id>` + unverified `@username`
hint; person-names inside a message stay free-text (never resolved to Workers).

**Feature flags (split, both default-off).** New `telegram_general_intake`
enables open intake; existing `telegram_intake` enables the labour path.
`poll-telegram` runs if EITHER is on, and the OpenAI labour extractor is now
OPTIONAL (no key → general intake still runs, LLM-free). Gating lives at the CLI
edge; `poll_telegram(..., general_intake=)` takes it as an explicit input so the
intake logic stays flag-free and unit-testable. Restore live with
`PROJECT_DB_FEATURE_TELEGRAM_GENERAL_INTAKE=true`.

**Deferred:** per-message LLM classifier (content_type/summary/mentions) -- the
report's narration already summarizes raw text; media (photo/voice) bytes;
spam/rate-limiting. Tests: new general-intake + attribution + report-comms
coverage; existing labour/gate contract preserved.

---

## 2026-06-22 -- Direction reset: docs canon, build freeze, weekly-report build #1

A deliberate course-correction after recognizing a "documentation-as-steering-
wheel" loop: every doc declared itself the next build, each session patched
toward the latest doc, and half-working features piled onto a half-working
product. What changed:

**Documentation reset to a four-file canon.** CLAUDE.md rewritten around ONE
metric -- time saved -- plus a BUILD FREEZE (no new subsystems until the visible
spine meets a usage gate) and doc discipline (present-tense facts only; no
roadmap/authority docs). HANDOFF.md = current state, wiped each handoff. This
CHANGELOG = history, never wiped. 9 forward-looking / point-in-time docs moved to
`docs/archive/` with a guard README ("history, not instructions"). README's two
navigation blocks repointed at the canon (its status-timeline body is stale and
still slated for rewrite).

**Safety branch.** The full, fully-exposed pre-reset build is frozen on the
`full-exposed-build` branch (commit 3323441) so `main` can evolve freely.

**Feature-flag quarantine committed.** `features.py` gates ~16 non-spine surfaces
off by default (reversible via `PROJECT_DB_FEATURE_<NAME>=true`); purely
presentational -- no schema/data change. Visible spine: core, ask, search,
proposals, typed field notes, finance margins, ledger health.

**Weekly report -- build #1 (foundation).** `report_weekly_changes(session,
project_ref=None, *, since_days=7, now=None)` in `ai/views.py` -- deterministic,
facts-only "what changed per project in the last N days": documents changed in
Drive (`modified_at_source`), field notes received, proposals opened/decided,
tasks completed. Proposals (no `project_id`) attributed via `entity_type`
Project/Task. `weekly-changes [project] [--days N]` CLI. Verified on live
Rockland data (7-day + 30-day). Known limitations, by design + documented:
`FinancialLineItem` excluded (ledger rebuilt via delete+insert, so its
`created_at` means "last parsed" -- noisy); "newly filed but Drive-old" docs not
caught (only `modified_at_source` used, because `Document.created_at` is reset by
a full DB wipe and would flood wide windows with false "new"); proposals shown
for all statuses; in-memory aggregation (fine at current scale). Next: LLM
narration layer (facts -> readable weekly summary + "what to act on"),
built/tested on the mock provider so development costs no tokens.

Tests: 1394 passing.

---

## 2026-06-17 -- Telegram labour intake: LIVE + closed up

Live end-to-end: a linked worker texts @ALTA_employeebot ("worked Rockland 7-4
half hour lunch") -> poll-telegram -> LLM extract -> consolidated shift in the DB
-> bot confirmation reply. Proven with a real message (Nicholas, 8h, Rockland).

Transport (committed earlier today): pyTelegramBotAPI (telebot) SYNC, one-shot
poll-telegram (offset cursor; no always-on server, no webhook -- poll >=daily,
like Gmail), /start <token> worker binding, unbound senders quarantined.

Closed up cleanly today with the deliberately-simple model:
- The LabourClaimCluster IS the canonical labour record (NO synthetic
  ProjectLogEntry write-back -- that was the convoluted part avoided).
- EXCEPTION-ONLY review: clean shifts auto-confirm; only conflict /
  needs_review are surfaced. The PM does not confirm every claim.
- report_labour() -> one function behind both `labour-claims` (CLI) and a new
  "Labour" tab on the project web page (shifts, hours-by-worker, the exceptions
  to review, unresolved names).
- labour-consolidate --all (Gmail bridge + consolidate every project) = the one
  daily-schedule command; no source required on any given day; two Project Log
  sheets for the same worker+day MERGE into one shift (tested).

Deferred (not blocking the text pilot): Telegram voice transcription, photo-of-
a-Project-Log via Telegram, activity-text -> field-note proposals, employee
alias-resolution UI. 1324 tests.

---

## 2026-06-17 -- Unified labour intake: consolidation spine + Telegram text extraction

Started the Telegram + Gmail labour-intake plan by building its architectural
core: Gmail Project Logs and (future) Telegram messages feed ONE consolidation
layer, not two silos.

Library decision (researched): the Telegram adapter will use **pyTelegramBotAPI
(telebot) in sync mode, NOT aiogram** -- this repo is fully synchronous (sync
SQLAlchemy, sync Gmail poller, sync CLI); aiogram and python-telegram-bot v20+
are async-only and would force event-loop bridging around sync DB calls for no
benefit at pilot scale. telebot 4.34 (June 2026) has first-class sync polling +
voice/photo downloads.

Built + mock-tested today (no bot token, no API spend):
- **4 models** (`db/models/labour_intake.py`): LabourSourceEvent (raw item),
  LabourClaim (one extracted shift/activity claim), LabourClaimCluster +
  Member. Reuses Worker/WorkerAlias -- no separate employee DB.
- **Gmail bridge** (`ai/labour_consolidation.py`): emits LabourClaims from the
  existing ProjectLogEntry rows, so the layer works on real data without
  touching Project Log ingestion.
- **Consolidation engine**: coarse (worker, project, date) clustering; agreeing
  sources REINFORCE, a single source is single-source, unresolved worker /
  missing date is needs-review, and materially different hours (>0.25h) is a
  CONFLICT surfaced for review -- never silently collapsed (the labour twin of
  the financial reconcile gate). Implements the plan's Examples 1-5.
- **Telegram text extraction** (`ai/telegram_labour_extraction.py`): LLM (strict
  JSON, ABC + OpenAI + Mock) turns "John 8h Mike 7.5 Alex 5 at Rockland" into
  one claim per worker; deterministic code resolves worker (self ->
  telegram_identity, else exact/alias only) + project (+ sender default) +
  date/times + computed hours. Raw names never discarded.
- End-to-end test: a Telegram self-report + a Gmail claim for the same
  worker/project/date consolidate into ONE auto_reinforced shift.

29 new tests across 2 files. 1308 tests total.

Remaining phases (next sessions): live telebot poller + /start worker binding +
TelegramIdentity [needs TELEGRAM_BOT_TOKEN + the pyTelegramBotAPI dep]; voice
transcription; reconciliation reports + web panel; field-note linking. No
public webhook needed (long polling, like the Gmail poller).

---

## 2026-06-17 -- LLM division extractor for PDF quotes (+ a trust gate the live run earned)

To take division margins beyond the one project with spreadsheet quotes, added
`ai/financial_llm_extractor.py`: the LLM reads a quote PDF's already-extracted
text and returns per-scope line items; deterministic code maps each to a CSI
division, verifies the amount against the source text, sums, and reconciles to
the document's stated total. CLI: `fill-ledger-llm <project|--all> [--limit]`.
12 mock tests; rows carry `source="llm"` and show in the same margins UI.

A small **live smoke run** (3 real 1455 St. Mathieu quotes, authorized) earned
its keep immediately:
- LYGC Quote 1: lines summed to $79,000 = stated $79,000 -> reconciled, written.
- Geller R1: $338,550 of lines vs $149,580 stated -> over-extraction.
- Geller House: $162,677 vs $306,498 stated -> under-extraction.

So the LLM over/under-extracts on complex multi-section quotes. Added a **trust
gate**: an LLM extraction is written to the ledger ONLY if it reconciles to the
document's own stated total (within 1% / $1); otherwise it's quarantined (no
rows) for review. Stricter than the deterministic grid path on purpose -- a
grid reconcile-fail is a small real doc discrepancy; an LLM one is an extraction
error that can be 2x off. Result: 1455's margins now shows a trustworthy $79,000
across 6 trades (Finishes $44k, Plumbing $10k, ...) from a PDF, while the two
unreliable Geller extractions are held back rather than inflating the number.

1290 tests. Next: the eval gold-set (Geller $159,120 etc.) + a tighter prompt to
raise the reconcile pass-rate, THEN the budgeted `fill-ledger-llm --all` run.

---

## 2026-06-17 -- Financial layer: SURFACED in the web UI (it was invisible)

The Phase 1a-1d engine was real but you couldn't see it in the browser, for
three concrete reasons we just fixed:

1. **The Margins page was orphaned.** `/projects/<id>/margins` rendered fine but
   NOTHING in the nav linked to it -- you'd have to type the URL. Added
   "Margins (by trade)" + "Ledger health" links to the project nav.
2. **The ledger was empty for 21 of 22 projects.** `fill-ledger` had only ever
   run on Rockland. Added `fill-ledger --all` (portfolio-wide) and ran it. The
   honest result: still only Rockland gets rows, because the deterministic
   parser reads own-authored quote *spreadsheets* (Material/Labour/Total grids)
   and every other project's quotes are PDFs or single-column estimates. The
   `--audit` view names exactly which doc needs which extractor (e.g. 1455 St.
   Mathieu: 14 docs, all unsupported_pdf_quote / simple_estimate, incl. the
   $159k Geller PDF).
3. **Phase 1d had no web page.** Added `/projects/<id>/ledger-health` +
   template -- the per-document audit (parsed / reconcile-fail / unsupported /
   safe-skip with recommended actions). This is the page that answers "why is
   this project's margin empty?" The margins empty-state links straight to it.

Live-verified: Rockland margins render $278,106 quoted revenue by division;
ledger-health shows the two clean quotes ($126,480.91 + $66,539.65, $0.00 diff),
two reconcile-fails, and the unsupported PDFs. 7 web tests (test_web_margins.py).
1278 tests total.

What this does NOT yet do: portfolio-wide margins. That needs PDF/LLM and
simple-estimate extraction feeding the division ledger (the schema already has
`source="llm"` for it) -- the next real build, and the clear unlock now that the
gap is visible.

---

## 2026-06-17 -- Project Log image ingestion (labour/time sheets) -- MVP

A new ingestion path, separate from field notes and financials: daily ALTA
PROJECT LOG sheets (photographed/scanned) emailed in, turned into structured,
queryable labour rows. Full spec: docs/PROJECT_LOG_INGESTION.md.

What it does today:
- **Classify, don't guess.** A fork in email_intake screens image attachments
  with a vision classify-extract call. An ALTA PROJECT LOG is handled by the
  project-log path and NOT field-noted; anything else falls through unchanged.
  Low-confidence -> quarantined (never silently misprocessed).
- **Model extracts, code validates.** The vision call returns strict JSON
  (document_type, site_name, rows); deterministic code normalises dates/times,
  computes hours (left-arrived-lunch), flags reported-vs-computed mismatches,
  and drops blank rows. Reported hours are never overwritten -- both kept.
- **Canonical DB is the source of truth.** ProjectLogSubmission (one per form) +
  ProjectLogEntry (one per worker/time row). Employee linkage reuses the Worker
  roster + a new WorkerAlias (exact/alias only -- a wrong match is worse than
  unresolved; raw handwritten names are never discarded). Idempotent on
  (message_id AND attachment_hash), sibling-safe so one email can carry several
  sheets.
- **Site/project resolution:** site name on the form wins, else the email's
  resolved project. Unresolved -> quarantined unknown_site, rows still kept.
- **Human-readable mirror.** `project-logs <project>` prints hours-by-employee
  (resolved + unresolved) and each sheet's status; `--export-dir` writes a CSV
  under `ALTA Generated Reports/Project Logs/<project>/`. The Drive scanner now
  SKIPS `ALTA Generated Reports/`, so a generated CSV is never re-ingested as a
  source document (the loop the spec forbids).
- CLI: `poll-mail` runs the route by default (`--no-project-logs` to disable);
  `project-logs <project> [--export-dir]` to view/export.

Reuse over rebuild: ~70% leaned on existing email_intake, the vision chain in
field_note_extraction, and Worker. New tables created via create_all +
ensure_sqlite_schema. ~120 new tests (test_project_log.py,
test_project_log_email.py, + the skip-rule test). 1271 tests total.

NOT yet done (deliberate): real-sheet run (needs OPENAI_API_KEY + gmail-auth --
the adoption step), PDF->image rendering, fuzzy employee matching, employee
profile UI, productivity analytics. No payroll logic.

---

## 2026-06-17 -- Financial Phase 1d: Ledger Health / Review Surface

The parser was safe and routing-correct, but a PM still couldn't *see* what it
did. Phase 1d adds the audit layer that answers "why is Project X showing only
$66k when I have four quote documents?"

- `report_ledger_health(session, project_ref)` (`ai/views.py`) + `fill-ledger
  --audit <project>`: a per-document table — classified_type, ingestion_status,
  ingestion_reason, rows_written, reconcile_ok, division_total, stated_total,
  difference, and a deterministic `recommended_action` (no LLM). Sorted
  attention-first (parse errors → reconcile-fails → unsupported → ok → safe
  skips) so the actionable rows are on top.
- recommended_action codes: `ok`, `review_reconcile_fail`, `review_parse_error`,
  `unsupported_pdf_quote`, `unsupported_simple_estimate`, `unsupported_job_cost`,
  `empty_extraction`, `safe_nonfinancial_skip`.
- Real-data accuracy fix found during validation: a photo with empty extracted
  text is `safe_nonfinancial_skip` (reason `non_textual_image`), NOT
  `empty_extraction` — "re-run extract-content" only makes sense for *textual*
  docs that came out empty. This kept 20 Rockland photos from being mislabeled.
- Validated live on Rockland (31 docs): 2 ok ($66,539.65 + $126,480.91, both
  reconcile to $0.00), 2 review_reconcile_fail (EXTERIOR +$1,000; EXTRAS
  -$1,250 — real source discrepancies), 2 unsupported_pdf_quote, 1
  unsupported_simple_estimate, 1 unsupported_job_cost, 23 safe skips.
- Idempotent: the audit re-runs the populator (delete+insert), so it also
  refreshes the ledger. 17 new tests (`tests/test_ledger_health.py`).

1202 tests (was 1185). Phase 1d closes the financial visibility gap; next up is
the queued **Project Log image ingestion** (`docs/PROJECT_LOG_INGESTION.md`).

---

## 2026-06-17 -- Financial layer: Phase 1a-1c walk-back audit + bug fixes

Reviewed the whole financial layer built today (Phase 1a grid parser → 1b
persister → 1c extras + multi-sheet routing) end to end and fixed every real
bug it surfaced. No new parsers (per the standing rule: nothing new before
Phase 1d + the eval harness).

Bugs found and fixed (each with a regression test):

- **Extras revenue silently dropped.** `report_division_margins` deduped each
  `(unit, division, side)` bucket with "total wins over line items", but an
  extras `adjustment` row fell into the line-item bucket -- so whenever an
  extras doc shared the base quote's unit + division (e.g. `923 EXTRAS` next to
  `923 ACCEPTED QUOTE`), the change-order money lost the dedup contest and
  vanished from the margin total. Reproduced: $500 quote + $300 extra reported
  as $500. Fix: `adjustment` is now STANDALONE (additive, never a re-statement),
  matching the `extras_grid.py` "BOTH counted" contract.
- **French extras not parsed (Quebec dataset).** The extras parser's status
  header markers and status classifier were English-only: a `Statut` column was
  not recognised (header → not-found → whole sheet skipped), and `Accepté` /
  `Non accepté` / `Refusé` all classified as `unknown` -- so a *rejected* French
  change order would have been counted as revenue. Fix: accent-fold all status/
  header cells and add bilingual EN/FR patterns (`accepté`, `non accepté`,
  `refusé`, `annulé`, `en cours`, `soumis`, ...), with `terminé` (done) kept
  distinct from English `terminated`.
- **Accented / plural divisions dropped to 99.** `classify_division` matched
  unaccented aliases against raw text, so `béton`/`fenêtre`/`électricité` missed
  their division; the alias list was also inconsistent about plurals, dropping
  `tuiles` (vs `tuile`). Fix: accent-fold the input and make the trailing `s`
  optional, so singular aliases also match their plural.
- **Workbook truncation sentinel over-matched.** `split_workbook_sheets` treated
  any sheet whose name started with `(` as the "(further sheets omitted...)"
  truncation marker, so a real worksheet named e.g. `(2024) Budget` would
  truncate the split. Fix: match the marker text (`sheets omitted`), not a
  leading paren.

Also: **CI was red on `main`.** Today's earlier financial commits landed after
the 2026-06-16 ruff sweep without running the (now-blocking) linter/formatter --
8 lint errors (unused imports, stale `# noqa`, unused unpacked vars) and 13
format-drifted files. Cleaned all of it; `ruff check .` and `ruff format
--check .` are green again.

1185 tests (was 1170): +15 net across extras (FR), divisions (accent/plural),
margins (extras additive), and workbook split.

---

## 2026-06-16 -- Financial redesign: division-keyed line-item ledger (skeleton)

Began re-architecting the financial layer after grounding the diagnosis in BOTH
the real Rockland documents (via Drive) and our actual code. The owner's boss
models profit per trade/division per unit; the current `FinancialRecord` layer
can only produce one project-wide net. Verified root cause (correcting an
external analysis that blamed text-flattening -- our XLSX/Sheets extraction
preserves the grid as TSV/CSV): granularity dies because (1) the extraction
prompt says "prefer the grand total over enumerating line items", (2) the
report collapses each (doc,direction) to one representative amount, (3) there's
no controlled division vocabulary, no `unit`, no material/labour split, no
proposed-vs-accepted status.

Design + intentions captured in **`docs/FINANCIAL_REDESIGN.md`** (authoritative).
Skeleton shipped:
- `ai/financial_divisions.py`: a controlled CSI-MasterFormat division vocabulary
  (residential subset, EN/FR aliases) + a deterministic, fail-safe classifier
  (explicit MasterFormat code/hint wins, else bilingual keyword, else
  `99 Unclassified`).
- `FinancialLineItem` model + migration + indexes: the normalized ledger row
  `(unit, division, side, amount_type, status, doc, date, evidence)`. Coexists
  with `FinancialRecord` -- no big-bang migration; cutover after parity.

Next: deterministic grid parser for our own quote/extras sheets (no LLM) →
`report_division_margins` (per-(unit,division), gross vs true margin, both-sides
guard) → LLM populator for unstructured supplier PDFs → status/date layering →
cutover. 1033 tests.

---

## 2026-06-16 -- The Monday task graph: dependencies, schedule engine, Gantt

A deep audit (`docs/MONDAY_AUDIT.md`) found the Monday integration was
discarding the task **dependency graph**: the connector fetched Monday's
"Dependent On" links and threw them away, the `Task` model had no field for
them, and the LLM `/ask` path got a flat, project-mixed task list with no
parents and no dependencies (which is why asking about a task gave poor
answers -- the model was blindfolded, not stupid). The hierarchy itself was
fine (129 subitems correctly parented). Fixed across four phases (1-3 shipped):

- **Phase 1 -- graph foundation.** New `TaskDependency` edge table + migration;
  the serializer keeps `linked_item_ids`; sync resolves dependencies by Monday
  id (fallback: in-project title match on the column's display names) and
  rebuilds edges idempotently. Verified live: Rockland's 11 "Dependent On"
  columns became 16 real predecessor->successor edges (bathroom -> plumbing ->
  drywall -> plaster).
- **Phase 2 -- the LLM sees the graph.** `ai/task_graph.py`: a deterministic
  schedule engine (predecessors/successors, blocking deps, schedule conflicts,
  and a finish-to-start **cascade** -- "if this slips 3 days, these downstream
  tasks must move to these dates"). The cascade is computed by code, never the
  LLM (consistency #1). `/ask` now injects the referenced project's real task
  tree; field-note date shifts surface the downstream cascade on the proposal.
- **Phase 3 -- visualize it.** `/projects/{id}/gantt`: a deterministic
  server-rendered SVG (no JS, no build) -- indented hierarchy, status-coloured
  bars by date, dependency arrows, today marker, theme-adaptive (light/dark).

Honest limit: cascades/arrows need dated dependents, and most Rockland subitems
are undated in Monday, so the engine maps the structure everywhere but does the
date math only where dates exist -- and now flags that gap. **Remaining:**
Phase 4 (dependency write-back). **1001 tests** (was 992).

---

## 2026-06-15 -- The field-note (active-adaptation) pipeline: notes -> proposals -> Monday

The big build the whole project was pointed at (STRATEGY's "active adaptation",
INTENTIONS §0, settled in `docs/FIELD_NOTES_BRIEF.md`). A field worker or PM
reports in plain language what happened on site; ALTA classifies it, matches it
against that project's Monday tasks, and emits **Proposals** a human reviews and
accepts -> Monday write-back. Advisor-not-actor throughout (A1): notes never
auto-apply. Pilot project is 923-927 Rockland. Built INSIDE the existing repo,
reusing the Proposal engine, the classify-then-extract structured pattern, RAG
context, and the existing review UI. All three Wins from the brief shipped, plus
a round of hardening:

- **Win 1 -- channel-agnostic core.** `FieldNote` sidecar table + migration;
  `ai/field_note_extraction.py` (OpenAI structured outputs, strict schema;
  classification vocab `task_done | task_progress | blocker | new_task |
  date_shift | scope_change | other`; one note -> many signals, each with a
  verbatim `quoted_excerpt`, A6). `ingest_field_note` is the shared service
  (A5) behind a `field-note <project> "text"` CLI and a project-page text box.
- **Win 2 -- email intake (N7-safe).** Gmail-API poller, OUTBOUND-only (no
  public endpoint -> localhost posture intact). Open sender roster auto-creates
  Worker stubs (role/tags/verified). Email content is treated as UNTRUSTED
  prompt-injection surface (A1): it produces Proposals only, never direct writes.
- **Win 3 -- photos through the same pipe.** Attachments pass through the
  vision-capable model with the SAME schema; photo + accompanying text are one
  combined signal. The email timestamp is threaded into the extractor so
  relative time ("yesterday", "last Friday") resolves to concrete ISO dates.
- **Proposal write-back symmetry.** Direct-accept now CREATES Monday items
  (scope_gap / new_task) and SUBITEMS, not just timeline edits; parent
  resolution is per-project-safe and refuses ambiguous/cross-project parents;
  subtask timeline proposals are bounded to the parent window; Monday API
  errors surface instead of failing silently; status labels normalise to the
  board's actual options.
- **RAG context wired in.** Field-note extraction pulls RELEVANT CONTRACT/SCOPE
  EXCERPTS from the embedded corpus as background to interpret a note (still
  quotes the NOTE for evidence, never the excerpts).

This session's hardening (the part that probed deepest):

- **Erik's-email failure class fixed.** A completed-work note that matched no
  existing task was classified `task_done` with a null match and then SILENTLY
  DROPPED. The prompt now prefers `new_task` over a dropped `task_done` when
  nothing matches confidently -- an actionable proposal instead of nothing.
- **Strategy C task block.** The flat 168-task list that confused matching is
  now status-stratified (Active -> Upcoming -> Done) and composite-scored
  (status 50% / keyword-semantic 30% / temporal 20%; undated tasks stay neutral
  so far-future and dateless work isn't buried). Done section trimmed to top-30
  by relevance; subitems annotated with parent context.
- **new_task accept uses the right title key + lands under a parent.**
  `parent_task_index` lets the LLM name the parent task; it resolves to a UUID
  stored in the proposal so accept creates a Monday SUBITEM instead of an orphan
  top-level item. If the LLM picks a subitem as the parent (Monday forbids
  sub-subitems), the resolver climbs to its top-level parent rather than emit a
  proposal doomed to fail at accept time.

Reuses, doesn't reinvent: storage mirrors the Document->DocumentText sidecar;
extraction mirrors `ai/doc_extraction.py`; proposals flow through the existing
engine and review queue. **958 tests passing** (was 829 at the last entry).

---

## 2026-06-10 -- External review integration: fix the cp1252 footgun once + strategy

An external review (Claude "Mythos") of the docs surfaced sharp points; acted on
the highest-value ones.

- **Fixed the cp1252/Unicode crash class ONCE (the overdue correctness fix).**
  `cli.force_utf8_output()` now reconfigures stdout/stderr to UTF-8 with
  `errors="replace"` (was: utf-8, no errors handler -> still crashed on edge
  chars). Called at every entry point (CLI + `monday_demo.py`). Accented FR data
  / em-dashes no longer hard-crash; worst case degrades to '?'. CLAUDE.md rule #5
  relaxed accordingly (stop being perpetually paranoid about every print()).
- **Strategy folded into INTENTIONS** (no new docs): named the two Honest
  Tensions (adoption is the unchecked box while building never stops; the project
  is a financial-truth tool wearing an active-adaptation mission -- both are
  owner decisions, now named not drifting); reframed §0's job-site questions to
  LEAD with the deployment/N7 contradiction (field workers texting = multi-user/
  networked, breaks the localhost posture -- the real hard part, not transcription
  accuracy); added §8 **extraction eval harness** (the highest-leverage missing
  infra -- production silently runs gpt-4o-mini but prompts were tuned on Sonnet
  and nothing measures regression; minimal ~5-doc gold set + scorer) and §9
  bootstrap-the-confirmed-default (correct a guess, not curate from scratch).
- Sequencing updated: eval harness gates extraction changes; financial trust
  (§6/§7/§9) reframed as gating the PM's first impression, not "after adoption".

Code change is the cp1252 fix only (cli.py + monday_demo.py). 829 tests passing.

---

## 2026-06-09 (later 5) -- $0-revenue audit: the missing acquisition money model

Hand-audited 6554 (57 docs, only 5 records, $0 revenue) to confirm the mirror
failure mode. Finding: the $0 is NOT dropped extraction -- the 5 records (small
plumbing supplier invoices) are correct, and the structured extractor correctly
declines to read the big docs (mechanical/electrical PLANS + a Purchase & Sale
Agreement) as construction revenue. The real defect: ALTA has **no money model
for acquisition/development deals**, so the `SIGNED PSA.pdf`'s stated
**$1,500,000 purchase price + $50,000 deposit** -- the biggest number on the
project -- is captured NOWHERE.

Subtle honesty hole found + corrected in the docs: the low-confidence guard did
NOT fire for 6554 (HANDOFF previously claimed it did). The guard only measures
money that reached the `other` bucket; the $1.5M was SKIPPED, so the guard sees a
"clean" $9k-cost project. **The guard can't flag money it never extracted.**
Captured as INTENTIONS §7 (+ a HANDOFF #14 correction). No code built.

Both failure modes are now understood: "huge number" = cross-document quote
duplication (§6); "$0" = unmodeled acquisition money + a guard blind to skipped
money (§7). Docs only. 829 tests unchanged.

---

## 2026-06-09 (later 4) -- Financial trust audit + the dedup strategy (no blind patch)

Hand-audited 1455's financials by reading the actual stored document text vs the
extracted records (free -- text is in the DB). Found the precise cause of the
"huge number" failure: the reported $931k revenue is ~3x inflated because the
Richard Geller job is counted across R1.pdf, R2.pdf, and a renamed "Penthouse"
copy, plus competing quotes summed. Per-document dedup works; the missing layer
is CROSS-document.

Researched the established solution rather than hand-rolling: this is **entity
resolution / record linkage + near-duplicate detection + MDM golden-record /
survivorship** (block -> match -> cluster -> survivorship -> human review;
MinHash/LSH/SimHash/Fellegi-Sunter; dedupe/Splink/recordlinkage/datasketch).
Key finding: ALTA already implements most of it -- `identity/resolver.py` IS a
record-linkage engine, `DocumentChunk` embeddings are the similarity signal, and
the confirmed/quoted toggle is golden-record survivorship with a human in the
loop. Captured as INTENTIONS §6 (extend, don't bolt on). No code built -- it's a
focused build of its own, and the money-line already declines to present the
inflated all-in number as truth, so this is an enhancement, not a fire.

Docs only. 829 tests unchanged.

---

## 2026-06-09 (later 3) -- Documentation consolidation (kill the sprawl)

The doc set had grown to 14 markdown files in project-db/docs/, each a partial
source of truth -- a handoff took too long and facts (the test count) drifted
across files. Consolidated to a lean set so a fresh instance ramps fast and
there's ONE home per kind of information.

- **Deleted 8 docs** (content folded into keepers or already there; all in git
  history): design-v0.1, OPTIMIZATION_v0.2, ROADMAP, GOOGLE_DRIVE_PLAN,
  ALTA_refocus_plan, EVALUATION, TRANSCRIPTION_FEATURE, docs/README (the index).
- **Folded:** EVALUATION's load-bearing ALWAYS/NEVER rules (A1-A9, N1-N8) +
  owner clarifications -> STRATEGY.md ("Standing Rules" + "Owner Clarifications").
  TRANSCRIPTION_FEATURE -> INTENTIONS.md "§0 Active adaptation" (the core
  purpose). refocus-plan's UX ideas -> INTENTIONS §3 backlog.
- **Lean core (6 prose docs):** STRATEGY (mission + rules), HANDOFF (engineering
  state + a new extraction-pipeline Mermaid diagram), INTENTIONS (forward
  roadmap), FEATURES (plain-language), CHANGELOG (history) + MONDAY_USAGE /
  adding-a-connector (reference). README points to them in read-order.
- **Single source for the test count: this CHANGELOG.** Other docs no longer
  hardcode a number (they drifted; now they point here).
- Updated all cross-references (README, HANDOFF, CLAUDE.md, adding-a-connector);
  no dangling doc links remain.

Docs only -- no code touched. **Test suite: 829 passing** (unchanged from the
money-line work earlier today).

---

## 2026-06-09 (later 2) -- Plain-English money one-liner (INTENTIONS #3)

A one-sentence per-project money summary: deterministic template over
report_project_financials + report_commitments, no LLM.

- `ai/views.py::report_project_money_line` + `_money_short` ($402 / $52k / $1.2M).
  CLI `money-line <project>`; a banner on the web project page (`ui_views.
  project_detail` -> `project_detail.html`), both from the same helper.
- **Honesty rework (the important part).** A naive "revenue | costs | margin"
  over the all-in totals LIED: 1455's all-in margin reads $809k because every
  unawarded quote in the folder is summed as revenue; its confirmed margin reads
  -$89k because the client docs are quotes (nothing confirmed). So the one-liner
  now headlines the CONFIRMED view (agreeing with the Financials panel = the
  money chokepoint): it prints a real margin ONLY when client revenue is actually
  confirmed; otherwise it leads with known costs and flags revenue as unconfirmed
  quotes, pointing at the panel (which is also the PM's confirm-the-awarded-quote
  workflow). Honest over confident-but-wrong. Low-confidence projects say so.
  - Live: "1455 Rue St. Mathieu: $88.7k in costs so far; client revenue not yet
    confirmed ($931k quoted on file -- confirm awarded quotes in Financials)".
- +7 tests (`test_money_line.py` + a project-page banner assertion). **829 passing.**

This surfaced a real adoption hook: per-project margins only become trustworthy
once a PM curates the confirmed/quoted toggle -- the one-liner now makes that gap
visible instead of hiding it behind a fake number.

---

## 2026-06-09 (later) -- Value-caught ROI tally (INTENTIONS #2)

The "pay-justification scoreboard" the owner's boss wants: one deterministic
number for "how much money has ALTA put in front of us?" Now that obligations are
extracted live, this aggregates them.

- `ai/views.py::report_value_caught` -- portfolio tally over ContractObligation,
  reusing `_obligation_status` (same status logic as report_commitments + the
  briefing, so the numbers agree). Buckets: revenue past due to collect
  (owed_to_us overdue), receivables due soon, obligations we owe (owed_by_us
  overdue); headline = collect-overdue + owe-overdue. A $0/null-amount obligation
  adds nothing and doesn't flag a project (it's a DOLLAR scoreboard). No LLM,
  free to recompute (N2).
- CLI `value-caught` (read-only renderer) + a headline card on the web `/`
  landing above the briefing (`web/ui_views.value_caught`, `dashboard.html`).
  Both read the same report, so CLI and web agree.
- Live (real DB): "$1,926 needing attention across 2 project(s)" -- 5768 owes
  $1,523 overdue, 2150 Tupper $402 to collect (the only projects with obligations
  extracted so far; the number grows as more are run).
- +7 tests (`test_value_caught.py` + 2 web card assertions). **822 passing.**

Scope note: v1 tallies COMMITMENTS dollars only (cleanest, non-double-counted).
Financial-risk flags (low-confidence margins, unconfirmed-quote piles) are a
softer signal left out of v1 to avoid double-counting -- a later extension.

---

## 2026-06-09 -- Obligations rebuilt on structured extraction + run live

Closed the last loose end in the "brain": the Money-at-Risk obligations layer was
built (2026-06-03) but had NEVER been run live and still used the old generic
ask-and-parse provider with a bilingual KEYWORD GATE -- the same design that
silently dropped real docs on the financial side. Re-did it with the
classify-then-extract structured pattern (`ai/doc_extraction.py` style).

- **`ai/obligation_extraction.py`** (OpenAI structured outputs, strict JSON
  schema): the LLM classifies each document + extracts obligations; deterministic
  code verifies amounts against the source text, enforces the dated-or-dollar
  rule, and snapshots all-or-nothing. NO keyword gate -- a MIME-level filter
  selects prose-carrying docs (a contract PDF is never dropped for its name).
  `MockObligationExtractor` for offline tests. CLI `extract-obligations
  --structured` (mirrors `extract-financials --structured`; legacy path kept).
- **Live-validated** (OpenAI gpt-4o-mini, ~$0.17 total): 2150 Tupper (smoke) +
  5768 St-Laurent. The canonical **"$8,000 due upon return of all keys"
  settlement surfaces, verified, with the verbatim clause**, alongside the
  other tenant buyouts (~$45k real owed-by-us exposure on the buyout project).
- Two general quality fixes from the live run (not per-project rules): treat
  `$0.00` as no-amount (template noise, mirrors the financial layer); prompt now
  excludes STANDARD/STATUTORY lease boilerplate (generic rent terms, C.c.Q.
  restatements) -- extract only non-standard project-specific commitments. False
  "overdue to collect" went $517 -> $0; overdue 22 -> 15. Prompt -> v2.
- **Known limits (documented, NOT forced -- match EVALUATION's 5768 notes):**
  cross-copy duplication (same tenant settlement counted across EN/FR/"Copy of"
  file copies inflates the per-project panel total; the briefing aggregates and
  excludes the no-date "conditional" ones, so the headline stays clean), and
  agency-buyout direction (2 of ~17 settlements came back owed_to_us; EVALUATION
  #12). Both are the financial layer's already-solved problem classes (dedup /
  direction-from-client-name) -- pick up only if/when a PM uses the layer.
- +9 tests (`test_obligation_extraction_structured.py`). **815 passing.**

DIRECTION FOR NEXT SESSION: structured is the recommended obligation path; the
legacy `ai/obligations.py` + the legacy `ai/financials.py` extractors can be
retired TOGETHER in one clean follow-up once structured is proven in use.

---

## 2026-06-04 (later 2) -- Anthropic primary, OpenAI automatic fallback

Owner's Anthropic credits hit $0, stranding ask/propose/extract. FallbackProvider
(`ai/providers/fallback.py`): Anthropic primary, OpenAI backup on any failure
(each backend's own retry runs fully on primary first). get_default/fast_provider
wire it when both keys exist; OpenAI used directly when no Anthropic key; explicit
LLM_PROVIDER respected; backup pinned to api.openai.com + OPENAI_FALLBACK_MODEL
(gpt-4o-mini). Live-verified: ask hit a "credit balance too low" 400 and answered
via OpenAI, no error surfaced. +8 tests. 806 passing.

---

## 2026-06-04 (later) -- Structured LLM extraction (retire the regex pile)

Owner pushback (correct): the heuristic pile (keyword gate + model/projection/
market-report regexes) was brittle whack-a-mole, and flattening docs to text
first was a lossy mistake. Re-architected per current best practice (schema-
based structured outputs; LLM for semantic understanding, deterministic code for
validation + arithmetic).

- `ai/doc_extraction.py` (OpenAI structured outputs): the LLM CLASSIFIES each
  document (quote / estimate / client-invoice / supplier-invoice / receipt /
  lease / settlement / budget / acquisition-model / market-report) + sets
  is_transactional, then extracts via a STRICT json schema (no malformed JSON,
  no hallucinated fields, no retry waste). Deterministic code still verifies
  every amount against the source text and sums (invariant N2). Spreadsheets ->
  markdown tables (+40% accuracy, fewer tokens than TSV). NO keyword/roll-up/
  model regexes -- the LLM subsumes them. CLI `extract-financials --structured`
  (gpt-4o-mini; OpenAI is the only thing with structured outputs + the owner's
  budget).
- Live-validated on the exact files that each needed a hand-coded rule, then a
  full-portfolio re-extraction: every project 100% classified or honestly empty,
  **0 unknown**, no low-confidence flags. 5768 $1M junk -> clean; 1364 $3.6B ->
  $0; 6554 dev deal -> clean. The supplier-vs-client direction (a long-standing
  hard problem) is correct after a prompt tweak; gpt-4o-mini == gpt-4o here.
- +7 tests. 797 passing.

DIRECTION FOR NEXT SESSION: the structured path (ai/doc_extraction.py) is now
the recommended extractor; the legacy regex path + its report-time rollup
recompute remain as a deterministic safety net but should fade. The same
classify-then-extract pattern should be applied to the obligations layer.

---

## 2026-06-04 -- Financial extraction overhaul (PM found it badly wrong)

A PM reviewing the app found financials missing/garbled. Investigated the whole
live DB; found four distinct bugs and fixed them all.

1. **Candidate selection silently dropped real docs.** The gate required a money
   keyword in the FILENAME -> 923 Rockland = 0 records ("Final SOW.pdf" /
   "preliminary quoting file.xlsx" all scored 0). EIGHT more projects were also
   silently empty. Fix: score the document TEXT; broaden keywords; read
   contract-shaped docs on content; skip photos/drawings.
2. **$71M of "unknown" junk.** Acquisition / pro-forma / projection / market-
   report spreadsheets were extracted as if their cells were transactions
   (6554 "Financial Breakdown" = $53M; 1364 lead "Market Report" = $2.5B). Fix:
   skip non-transactional analysis sheets by NAME and by CONTENT
   (content_is_rollup: projection/valuation/feasibility markers).
3. **XLSX extraction unbounded + structureless** (a 2.18M-char model dumped
   whole; wide tables flattened so dimensions/quantities read as money). Fix:
   header-aware, row/char capped, empty-sheet (uncomputed-formula) flagged.
4. **Roll-up status was frozen at extraction.** Fix: re-derive it at REPORT time
   (stored OR name OR content rule) + added budget/projection/job-costing -- so
   improving detection cleans already-extracted projects for FREE.

Result (verified live, mostly free recompute -- only ~$0.15 of Anthropic on the
candidate-selection victims): the portfolio went from a few-clean / lots-of-junk
state to **15 clean projects + 2 honestly low-confidence** (3940 small, 6554 a
real development deal). 923 Rockland 0 -> 27 recs (100%); 5768 (the PM's example)
18% -> 100%, $1.05M "other" -> $0; 1364 $3.6B -> $0. Prompt -> financials-v5.
+25 tests (test_extraction_fixes.py). 790 passing.

Note: the live REPORTS are now correct for every project (report-time recompute).
A full re-extraction (budgeted) would also scrub the stored junk records, but is
not required for correct numbers.

---

## 2026-06-03 (later 5) -- Money-at-Risk: contract obligations + commitments

INTENTIONS.md #1, the highest-ROI build: catch the recurring cross-system money
leaks (unbilled milestone, forgotten retainage, the $8k key-return settlement,
a missed insurance/penalty deadline) before they become losses.

- **ContractObligation** sidecar model + migration (mirrors FinancialRecord:
  schema-light validated vocab, quoted_excerpt evidence, amount_verified).
- **ai/obligations.py** `extract_obligations_for_project` -- LLM extracts dated/
  dollar obligations (payment_milestone / retainage / penalty / deposit /
  settlement / insurance_expiry / permit_deadline) with direction owed_to_us vs
  owed_by_us. Reuses the financial layer's helpers (amount verification, backoff,
  parsers); same all-or-nothing snapshot + conservative posture; STABLE system
  prompt (cache-friendly). CLI `extract-obligations <project>`.
- **report_commitments** -- deterministic chokepoint (no LLM): per-obligation
  status (overdue / due_soon / conditional / upcoming / open) from date/trigger
  + money-at-risk totals (owed_to_us overdue = revenue past due to collect;
  owed_by_us overdue = a payment/deadline we owe). CLI `commitments <project>`.
- **Briefing surface:** a new `commitments` category on the `/` landing --
  overdue receivables ("$X past due to collect", high), overdue obligations we
  owe (penalty/late exposure, high), due-soon (medium). So at-risk money shows
  up the moment obligations are extracted.
- Develop on mocks (done); a live `extract-obligations` run is a budgeted
  Anthropic action (not spent yet). +12 tests. 778 passing.

---

## 2026-06-03 (later 4) -- Money clarity in the UI

Keep all three money sources on screen but make it unmistakable which is
authoritative and what each means, in plain language. `ui_views.money_glossary()`
is the single source of the copy (template global, so the project page + the
Financials panel can't drift): reconciled picture = AUTHORITATIVE (green "trust
this"), Monday budget = reference, contract-text estimate = rough -- each with a
plain blurb on what it is and how they relate, plus a gloss of every money-type
bucket. Financials panel gets a green AUTHORITATIVE banner; the project page's
Budget-vs-Contract card gets a "reference" pill + a link to the reconciled
panel. +3 tests. 766 passing.

---

## 2026-06-03 (later 3) — Hybrid retrieval + documents search page

**Theme:** Maximum-accuracy retrieval. Pure cosine blurs exact tokens (invoice
numbers, civic addresses, proper names, "QST") — exactly what this corpus is
full of. The honest accuracy lever (not reranking/HyDE/larger-model treadmill).

- **Hybrid `retrieve_chunks`**: fuses the cosine ranking with a keyword
  (distinct-term coverage) ranking via reciprocal rank fusion. Exact
  identifiers surface even at lower semantic score. Free, local, deterministic,
  a GENERAL mechanism (no per-project tuning). `hybrid=True` default;
  `hybrid=False` = cosine-only. Results carry `similarity` / `keyword_score` /
  fused `score`. Sharpens ask + both proposal bots + search at once.
  Live proof: "estimate 25008" — pure cosine ranked TEMPLATE.xlsx (0.474) over
  the real estimate; hybrid put the "Estimate # 25008.0" chunk (0.461, kw 1.00)
  at #1.
- **`/search` page** (+ Search nav): read-only hybrid search over the corpus,
  optional project scope, doc links + match/sem/kw scores, graceful when
  nothing's embedded. No LLM tokens — just the tiny query embedding.
- **+10 tests** (4 hybrid, 6 search). **763 passing.**

---

## 2026-06-03 (later 2) — Proposal RAG + one-call refresh

**Theme:** Extend RAG to the proposal bots, and make staying current automatic.

### Proposal-bot RAG
- `generate_timeline_proposals` / `generate_scope_proposals` now pull the most
  on-topic document passages (project-scoped semantic search) into the prompt as
  ADDITIVE evidence — so a schedule milestone or scope clause buried deep in a
  long contract is seen even when `assemble_project_context`'s recency
  truncation cut it. Conservative anti-hallucination posture unchanged (pinned
  by `TestProposalBotsStayConservative`); no embeddings → byte-identical prompt.
  `ProposalBatch.rag_chunks_used` reports how many excerpts were injected. CLI
  `propose` + web propose routes pass the optional provider.
- Fix: `retrieve_chunks` excludes chunks whose Document was trashed in Drive.

### Refresh (sync + incremental re-embed)
- `connectors/refresh.py::run_refresh` — delta-syncs the live connectors
  (Monday now; Drive when live) then re-embeds ONLY documents whose text changed
  (idempotent via content_hash — unchanged docs cost $0). Every step guarded +
  reported; a connector without credentials is recorded, not fatal.
- CLI `project_db refresh [--full] [--no-embed]`.
- `serve` runs it in a daemon thread on startup (delta + re-embed) so the app
  opens on fresh data without blocking; opt out `--no-refresh`. Footer shows
  "data refreshed <time>". Background-only — never in `create_app`, so tests
  don't touch live APIs.
- **Answers "do we re-embed every Drive change?"** — no: only changed docs.

### Live-validated
`refresh` did a real Monday delta sync (135 processed, 8 boards skipped
unchanged, 18.8s), reported the expired Drive OAuth token as a non-fatal step
and continued, and the embed step skipped all 462 unchanged docs for **$0.0000**.

### Tests / state
- +11 tests (4 proposal-RAG/trashed in `test_rag.py`, 7 in `test_refresh.py`).
  **753 passing.** All offline.

---

## 2026-06-03 (later) — RAG: the askbot can read the contracts now

**Theme:** Give the AI eyes on the document TEXT, not just metadata. Until now
`ask` read a JSON snapshot (projects/tasks/counts) and was blind to what the
contracts actually say. RAG closes that. Strategy: BUY the commodity (OpenAI
`text-embedding-3-small`) and keep the domain logic (chunking, project-filtered
retrieval, idempotent storage, citing) ours.

### What shipped

- **`DocumentChunk`** sidecar table (mirrors the `DocumentText` pattern) +
  SQLite migration: chunk text + float32 embedding blob + content_hash +
  model/dims, `project_id` denormalised for cheap per-project filtering.
- **`ai/chunking.py`** — paragraph-aware ~500-token chunks with bounded
  overlap; tiktoken with a chars/4 offline fallback.
- **`ai/embeddings.py`** — `EmbeddingProvider` abstraction +
  `OpenAIEmbeddingProvider` (base_url pinned to api.openai.com so a stale
  `OPENAI_BASE_URL` can't hijack it) + deterministic `MockEmbeddingProvider`.
- **`ai/rag.py`** — `embed_documents_for` (idempotent via content_hash;
  unchanged docs skipped so re-runs don't re-charge; commits progress, survives
  Ctrl-C) and `retrieve_chunks` (brute-force numpy cosine — sub-10ms at this
  scale, no native vector extension; sqlite-vec is the upgrade path).
- **Askbot wiring** — `answer_with_llm` retrieves the most relevant excerpts
  and feeds them as quotable, citable hard facts; mode becomes `rag`, cited
  chunks return in `sources`. Best-effort: no key / nothing embedded -> falls
  back to the metadata snapshot, never breaks.
- **CLI** `embed-documents` (prints token + USD cost) + `rag-search`; `ask`
  and web `/ask` show "answered using N excerpts" + a `document-aware` badge
  with source links.

### Live-validated on the real DB (cost reported)

- Embedded the full corpus: **462/462 docs, 5590 chunks, 2.59M tokens =
  $0.0518** (idempotent re-runs skip unchanged docs).
- `ask "what scope does the 923 Rockland contract describe?"` -> **mode=rag**,
  a fully contract-grounded answer (contract value $66,539.65, 35-day duration,
  25/20/20/25/10 payment schedule, exclusions, change-order terms), **every
  line cited to Final SOW.pdf / SOW 923 Rockland.docx**, retrieval cosine ~0.55.
  The metadata-only askbot could not answer this at all.

### Env / deps

- New `[rag]` extra: `openai`, `tiktoken`, `numpy`. `OPENAI_API_KEY` in
  `.env` enables embeddings (the only OpenAI use — chat stays Anthropic).

### Tests / state

- **+26 tests** (`test_rag.py`): chunking, mock embeddings, embed idempotency /
  overwrite / stale-cleanup / project-filter, retrieve ordering / filter /
  model-mismatch, askbot RAG injection + fallbacks, migration. All offline
  (mock) — no API spend. **742 passing.**

---

## 2026-06-03 — The attention briefing (reveal, don't just generate)

**Theme:** Move the product's center of gravity from *showing the activity
ALTA generated* (a proposal queue) to *revealing the cross-system truths it
discovered* — the Monday-morning risk-and-money briefing EVALUATION.md §4–5
call the draw. Deterministic, free (no LLM / no API), built on already-stored
data.

### What shipped

- **`report_attention_briefing(session)` (`ai/views.py`)** — one pure,
  deterministic detector that composes the money / scope / schedule / document
  signals already in the canonical DB into a single severity-ranked list of
  attention items. No LLM call, no external API → safe to recompute on every
  request, never invents a number (invariant N2). Money items compose the
  `report_project_financials` chokepoint rather than re-summing rows.
- **Detectors:**
  - *money* — low-confidence reconciliation; confirmed costs exceeding
    confirmed revenue (guarded against the buyout no-revenue case); a pile of
    unconfirmed quote money (nudges the confirm/quote toggle).
  - *scope* — pending `scope_gap` proposals per project.
  - *schedule* — overdue tasks (past due, not done/cancelled), ranked.
  - *documents* — active/proposed projects with no contract on file.
- **`project_db briefing [--limit N]`** — ASCII CLI renderer.
- **Web `/` reframed to the briefing** — the ranked list now leads the landing
  as severity-pilled cards linking to evidence; the counts grid + pending strip
  are kept but demoted. Empty portfolio reads "All clear".
  `ui_views.attention_briefing` is a thin pass-through so CLI + web render
  identical data.

### Verified live (real 21-project DB)

`briefing` / `/` produce **15 ranked items across 7 projects (2 high / 9 medium
/ 4 low)** — 923 Rockland's 23 overdue tasks (HIGH), honest low-confidence
money flags on 3940/6554/5768, real scope gaps, and 1455's ~$367k
unconfirmed-quote pile. CLI and web outputs match exactly.

### Tests / state

- **+31 tests** (`test_attention_briefing.py` ×26, `test_web_briefing.py` ×5).
  **716 passing.**
- Pure-reveal, read-only: no write-back, no API budget consumed (honors A8 /
  N2 / N8). Next candidates: surface confirmed-loss once a PM confirms docs;
  optionally tune cross-category ranking; RAG (#4) remains the API-gated item.

---

## 2026-05-29 → 06-01 — The financial reconciliation layer (the "draw")

**Theme:** Build the thing that makes ALTA more than a sync tool — read the
MONEY out of the Drive documents and reconcile it per project. The biggest
capability jump since Drive sync. See `docs/HANDOFF.md` §2 for the architecture
and §4 for the worked-through problems; `docs/EVALUATION.md` for the strategic
framing that prompted it.

### What shipped

- **Extraction (`extract-financials`, `ai/financials.py`).** Reads a project's
  quotes / invoices / estimates / receipts (from `DocumentText`) and pulls every
  monetary amount with the verbatim `quoted_excerpt` that proves it, into a new
  `FinancialRecord` table. Batched across multiple LLM calls (full coverage, no
  truncation), all-or-nothing (a failed run never destroys prior records),
  conservative prompt (never invent an amount), `$0` noise skipped.
- **Two-sided ledger + reconciliation (`report_project_financials`).** The one
  chokepoint that computes money IN (client) vs OUT (contractor), margin, a
  per-document breakdown, and a flat record list. CLI prints it; the web
  Financials panel (`/projects/{id}/financials`) renders it.
- **Roll-up de-duplication (deterministic).** Internal cost/payment/tracking
  sheets are excluded from totals (shown as a cross-check) so they don't
  double-count the invoices they restate. Name-based rule, after an LLM
  classification proved unreliable (it once dropped a $549k client estimate,
  swinging the margin ~$200k).
- **Money-type buckets** (contract_revenue / supplier_cost / buyout_cost /
  lease_rental / deposit / tax / other) so different kinds of money aren't
  blindly netted.
- **Low-confidence guard.** When most of a project's money can't be classified
  (e.g. 6554 is a real-estate development deal — financing/acquisition/lease,
  not modeled), the reconciliation is flagged low-confidence instead of showing
  a misleading margin.
- **Confirmed-vs-quoted toggle.** They dump every quote into a project folder,
  including ones they didn't use. A human toggle (separate
  `document_financial_status` table that survives re-extraction) marks which
  documents count; the panel shows a live-recalculating "confirmed" total. Smart
  default: invoices in, quotes out.

### Locale / robustness (the hard part)

The value-verification guard was hardened over several real projects to handle
how Quebec/bilingual docs write numbers: English thousands (`1,234.56`), French
decimal commas (`923,44`), space thousands (`$1 080.00`), `k`-notation (`8k`),
negative signs, rounding, and the qty-vs-thousands ambiguity (`1 500,00`).
Direction classification needed a company-identity injection (`COMPANY_NAME`) to
stop reading our own client estimates as contractor costs.

### Validity verified across the whole portfolio

Extracted and audited 1455 (renovation, clean, 100% confidence), 5768
(tenant-buyout agency), 6554 (development — flagged), 6305, and the small
projects. Across all of them the system extracted real money, returned 0 for
genuinely non-financial docs (plans/reports — no hallucination), flagged garbled
or computed amounts, and flagged low-confidence where appropriate. No
confidently-wrong output anywhere.

### Also in this stretch

- **Removed the roadmap prompt injection** from the proposal bots (template
  noise; flagged as slop in EVALUATION §3). Table + CLIs kept.
- **New strategic docs:** `EVALUATION.md` (honest assessment + ALWAYS/NEVER
  rules) and `FEATURES.md` (plain-language feature overview).
- **UI polish** for readability + a PM demo: removed stale "Phase A" dashboard
  notes, "Overview" landing, brand tagline, the Confirmed-margin KPI card,
  Financials links on the project list.

### State at EOD (2026-06-01)

- **685 tests** passing.
- Financial layer complete for renovation + buyout projects; development-type
  and `unknown`-direction refinements are next steps (both need API budget —
  HANDOFF §5/§6).
- Owner is credit-constrained: develop on mocks, recompute financial logic over
  stored records for free, reserve API for direction work + new-project
  validation.

---

## 2026-05-26 (final EOD) — Tightening: quoted excerpts in proposal reasoning

**Theme:** The smallest possible prompt change with the largest
visible quality impact.  Both proposal bots' `reasoning` field spec
rewritten to demand direct evidence -- quoted excerpts for contract
sources, named neighbour tasks for schedule sequences, phase-ordinal
citations for roadmap entries.  Lazy reasoning ("the contract states
this", "per the schedule") is explicitly REJECTED.

### What changed
- `_build_timeline_prompt`: new EVIDENCE-CITATION REQUIREMENT block
  before the JSON schema.  Three evidence types named explicitly --
  DOCUMENT (quoted excerpt required), SCHEDULE SEQUENCE (named
  neighbours + dates), ROADMAP ENTRY (phase-ordinal+name).
- `_build_scope_prompt`: same block, with CONTRACT (quoted excerpt
  required) and ROADMAP (phase-ordinal+name) evidence types.
- Both prompts: "A reasoning that says only ... is REJECTED" guard.
- Prompt versions bumped: `timeline-v4-quoted`, `scope-v3-quoted`.

### Verification
- **+8 tests** (`tests/test_prompt_quoted_excerpts.py`).  Existing
  Layer-2 prompt-version test broadened to accept new milestone
  tags.  **625 / 625 total passing.**
- Tests pin: EVIDENCE-CITATION block present in both prompts, all
  evidence-source labels named, REJECTED guard present, anti-
  hallucination posture from earlier milestones preserved
  ("Never invent", "ANCHOR every proposed date", past-date guard).
- **Live re-run of `propose scope` on 5768 St-Laurent**: produced
  8 proposals (4 contract + 4 roadmap) with dramatically improved
  reasoning quality.

### Before / after on real output

Before this push, a typical contract-sourced reasoning read:

> "The contract mentions energy targets in section 4."

After, the same call produces:

> '"the LESSOR agrees to pay the amount of eight thousand dollars
> ($8000)... upon the LESSEE's departure and the return of all keys"
> (Majd 5768 English (2).pdf). No current task addresses this
> substantial financial settlement obligation.'

Every contract-sourced gap now carries the literal contract language
in double quotes, with the document name.  Works on French sources
too ('"le LOCATAIRE quittera les lieux loues au plus tard le 14 jour
du mois de Decembre 2025"').  Roadmap-sourced gaps use the
phase-ordinal citation format ('[CA-04] Punch List Coordination').

### Why this matters
- A PM reviewing a proposal can now validate the citation against the
  actual document in one click via `/documents/{id}`.
- Accept / reject decisions become evidence-based, not trust-based.
- The model's hallucination floor is much lower because it must
  produce verifiable text, not summarize.

### State at EOD
- **625 tests** passing.
- Day-of-work commits since this morning: 7 (Layer 1 -> Layer 2
  steps A through D -> tightening).  Today's net additions:
  - 44 canonical roadmap tasks live in DB
  - Actor classifications (20 contractor-relevant)
  - Layer 2 prompt injection working on both proposal bots
  - Source-labeled (contract vs roadmap) scope output
  - Quoted-excerpt reasoning on every contract gap

Pending: user evaluation review pass, then a final HANDOFF doc
update before session close.

---

## 2026-05-26 (post-M5) — Roadmap integration Layer 2: actor classification + prompt injection

**Theme:** Second of two layers shipped (Layer 3 was deliberately
SKIPPED -- see decision rationale below).  This is the layer that
delivers the user-visible value: scope proposals now flag two kinds
of gaps with explicit source labels.

### Decision: skip Layer 3, go straight to Layer 2

Earlier plan was Layer 1 (storage) -> Layer 3 (deterministic
gap-finder) -> Layer 2 (prompt injection).  After Layer 1 shipped,
honest evaluation showed Layer 3 (naive matching of all 44 roadmap
tasks against a project's Monday board) would produce **30-40
false-positive "missing" tasks per project** because:
- The roadmap is the architect/designer workflow (SD -> DD -> CD -> CA).
- Most Monday boards are construction execution (CA-phase + execution).
- A deterministic fuzzy matcher would flag every architect-side task
  as "missing" from contractor-side boards.

The user agreed: "a great program can do a little but very well."
Layer 3 was dropped.  Layer 2 with the LLM as a contextual filter
became the path -- the model decides which roadmap entries plausibly
apply to *this* project, not us assuming all 44 do.

### Step A: RoadmapActor enum + actor column

- New `RoadmapActor` enum: `ARCHITECT` / `CONTRACTOR` / `BOTH`.
- Nullable `actor` column on `RoadmapTask`.  NULL = "not classified
  yet"; the prompt-injection filter treats NULL as "do not inject."
- SQLite migration: new DDL includes the column; existing DBs get
  `ALTER TABLE roadmap_task ADD COLUMN actor VARCHAR` via the
  `SQLITE_ROADMAP_TASK_COLUMNS` map (mirrors the task / document
  back-compat pattern).

### Step B: `project_db classify-roadmap` CLI

- New `classify_roadmap_actors(session, provider)` -- single Sonnet
  call gets the 44 tasks + sub-tasks, returns strict JSON
  `{phase, ordinal, actor, reasoning}` per task.  Validated;
  bad items go to errors.  Updates roadmap_task rows in place.
- CLI command `project_db classify-roadmap` uses the deep provider.
  Re-runnable.
- **Live run on the 44 tasks: 24 ARCHITECT / 2 CONTRACTOR / 18 BOTH**.
  After filtering to CONTRACTOR + BOTH, 20 contractor-relevant tasks
  are available for prompt injection.

### Step C: Layer 2 -- the actual prompt injection

- New `_render_roadmap_for_prompt(session)` helper -- pulls
  CONTRACTOR + BOTH rows, formats as a compact text block grouped by
  phase.  Returns "" when no rows have an actor (pre-classify state),
  so the prompt behavior is exactly pre-Layer-2 in that case.
- Both `_build_timeline_prompt` and `_build_scope_prompt` now accept
  a `roadmap_block` parameter.  When non-empty:
  - Timeline: section + system rule that the canonical phase order
    is an additional ordering anchor.
  - Scope: section + system rule that the model MAY flag a
    roadmap-sourced gap when a roadmap entry plausibly applies but
    isn't on the Monday board.  Explicit warning: "do not flag SD/DD
    entries on a project whose tasks are all CA-phase execution."
- The scope output JSON gains a required `source` field
  (`"contract"` | `"roadmap"`) when roadmap is injected.  Backward
  compatible: missing field defaults to `"contract"`.
- `_persist_scope_items` captures and validates the `source` label;
  warns on unknown values.  Contract-sourced source-doc hallucination
  warnings only fire on `source == "contract"` (roadmap-sourced gaps
  legitimately have no source_document).
- Prompt versions bumped: `timeline-v3-roadmap`, `scope-v2-roadmap`.

### Step D: live validation against the real DB

Ran `propose scope` on **5768 St-Laurent** (pure-execution multi-unit
renovation, 16 tasks, 5 dateless, 143 documents).

**Result: 10 gaps total -- 6 contract-sourced + 4 roadmap-sourced.**

Contract-sourced (project-specific from SOW / settlement docs):
- Homologation of settlement agreements (Tribunal)
- Confidentiality between 5768 and 5770 buildings
- Settlement compensation payment
- Unit 5 vacate (Majd El-Merhebi)
- Unit 8 vacate (Kawtar Lahyane)
- Units 6-10 vacations per settlement agreements

Roadmap-sourced (canonical, contractor-relevant, plausibly applicable):
- **Cost Estimate + Schedule Alignment** (DD-12, CONTRACTOR)
- **Preliminary Cost + Feasibility Review** (SD-07, CONTRACTOR)
- **Submittal Review** (CA-01, BOTH)
- **Close-Out Documentation** (CA-05, BOTH)

What did NOT get flagged from the roadmap (the noise we were worried
about): Site Analysis, Energy Performance Criteria, Conceptual Design
Development, 3D Massing, Develop Envelope Assembly Details, etc.  The
actor filter (ARCHITECT-only excluded) + the prompt's "don't flag SD
items on execution projects" rule combined to produce exactly the
useful contractor-side template tasks, no architect noise.

### UI changes
- `propose_result.html` now shows a "By source: contract: N &middot;
  roadmap: M" breakdown for scope batches.  When roadmap entries
  appear, an explanatory note ("template-derived; review with
  'does this apply here?' in mind") renders.
- New Jinja `from_json` filter (`web/app.py`) so the template can
  parse `proposed_value` JSON strings for the source breakdown
  without forcing every service module to pre-parse them.

### Verification
- **+16 Layer-2 tests** (`tests/test_roadmap_layer2.py`),
  **617 / 617 total passing**.
- Tests pin: nullable actor column, list filter behavior,
  `_render_roadmap_for_prompt` empty/non-empty conditions, prompt
  builders conditional on roadmap_block presence, prompt versions
  bumped, `_persist_scope_items` source-label capture (including
  backward-compat default and unknown-value warning), end-to-end
  via mocked LLM with both contract + roadmap items in one batch.
- Live scope generate on 5768 St-Laurent produced the 6+4 result
  documented above.

### What's next (per the next-step list in ROADMAP)
1. Tighten proposal reasoning prompts with quoted excerpts
   (~1 session, high-value)
2. RAG over `DocumentText` (~4 sessions, biggest unlock)
3. Structured financial extraction (~3-4 sessions)
4. Live QB integration (pending creds)
5. One real Monday accept through the UI (pending sign-off)

### State at EOD
- **617 tests** passing.
- Roadmap integration complete: data ingested (Layer 1), actor-classified
  (Layer 2 step B), and live-injected into both proposal bots
  (Layer 2 step C).  Live validation confirms the contextual filter
  works -- pure-execution projects get useful roadmap flags without
  architect-side noise.

---

## 2026-05-26 (post-M5) — Roadmap integration Layer 1: storage + import CLI

**Theme:** First of three layers (per ROADMAP "Forward-looking AI
plans") to inject the user's canonical design-phase roadmap into the
AI proposal pipeline.  Layer 1 is the foundation -- a `RoadmapTask`
table populated from `docs/Project Roadmap.xlsx` via a new CLI command.
Layers 2 (prompt injection) and 3 (deterministic gap-finder) build on
this.

### What landed
- **New canonical entity `RoadmapTask`** (`db/models/roadmap.py`).
  Columns: `phase` (SD/DD/CD/CA enum), `ordinal` (int, 1-based within
  phase), `task_name`, `sub_tasks_json`, plus the CanonicalMixin
  fields.  Unique constraint on `(phase, ordinal)` so re-imports
  are stable.
- **`RoadmapPhase` enum** with explicit `ROADMAP_PHASE_ORDER` mapping
  (SD<DD<CD<CA) -- the AI layer uses this in Layer 2 as the
  "phase X cannot start before X-1 finishes" anchor.
- **SQLite migration** in `ensure_sqlite_schema` so existing local
  DB files pick up the new table automatically.
- **`ai/roadmap.py` parser** -- pure function
  `parse_roadmap_xlsx(path) -> list[dict]`.  Header-based column
  lookup (so editorial column reordering doesn't break the import),
  bounds-safe row access (openpyxl read-only mode returns shorter
  tuples for trailing-empty rows; first import of the live file
  caught this).  Skips editorial blank rows between phases.
  Splits sub-task bullets cleanly.
- **`import_roadmap_rows(session, parsed, overwrite=False)`** --
  idempotent persistence.  Refuses on second run without
  `--overwrite`; drops + re-inserts with `--overwrite`.
- **`list_roadmap_tasks(session)`** -- JSON-serializable read helper,
  sorted by phase order then ordinal.  Used by future Layer 2 / 3.
- **New CLI `project_db import-roadmap [path] [--overwrite]`** --
  defaults to `docs/Project Roadmap.xlsx`, also tries
  `../docs/Project Roadmap.xlsx` so it works from either
  `ALTAtest/` or `ALTAtest/project-db/`.

### Verification
- **+22 tests** (`tests/test_roadmap_layer1.py`), **601 / 601 total
  passing**.
- Tests cover: sub-task splitter (None / NaN / blank / dash / bullet
  / mixed cases), parser happy path, blank-row separators, unknown
  phase raises, missing required column raises, case-insensitive
  phase strings, notes column, **real-file integration test** (parses
  the actual `docs/Project Roadmap.xlsx` and asserts 44 tasks across
  the 4 phases), idempotency (refuse vs overwrite), `list_roadmap_tasks`
  sort order, CLI end-to-end + missing-file + re-import paths.
- **Live import**: `project_db import-roadmap` produced
  `OK -- imported 44 task(s): 15 SD / 13 DD / 11 CD / 5 CA` --
  exactly matching the spreadsheet phase breakdown.  Re-import
  without `--overwrite` correctly refused (`FAIL: roadmap_task
  already has 44 rows`); re-import with `--overwrite` replaced
  the 44 rows cleanly.
- Live UI: `/db` lists `roadmap_task` with row count 44;
  `/db/roadmap_task` renders all 44 task names with their sub-task
  JSON arrays.

### What's next (Layers 2 + 3 of the roadmap integration)
- **Layer 3 (next session): `roadmap-gaps` deterministic gap-finder.**
  CLI + UI route that compares a project's Monday tasks against the
  canonical roadmap using exact + fuzzy + LLM-tie-break matching.
  Zero tokens for the common case; LLM only for the 0.6-0.85 fuzzy
  middle.
- **Layer 2 (after Layer 3 ships):** inject the roadmap into
  `_build_timeline_prompt` and `_build_scope_prompt` as a reference
  section.  Both bots gain ordering / completeness anchors.

### State at EOD
- **601 tests** passing.
- Roadmap is canonical data now -- editable via re-import, queryable
  via `/db`, ready for Layers 2 + 3 to consume.

---

## 2026-05-26 — Phase 6 / M5 part E: closeout

**Theme:** Last UI slice -- the dev affordances + offline-readiness
that polish M5 to closure.

### What landed
- **`/db` raw-row inspector.** Lists every SQLAlchemy table with row
  counts; `/db/{table}` shows the top 100 rows.  Reflective via
  `Base.metadata.tables`, so new tables appear automatically.  Read-only
  by design -- no `/db/exec`, no `/db/query`, no edit, no export.  Per
  the M5 plan review #4: this is a dev affordance, NOT a second product
  surface.
- **Raw-JSON debug panels.** `<details>` (collapsed) at the bottom of
  the project detail and document detail pages, showing the full data
  dict the template was rendered from.  Proposal detail already had
  one; now everything does.  Eyeball what the service module returned
  without firing up DB Browser.
- **Vendored static assets.**  Pico.css (83 KB) and HTMX (48 KB) live
  in `web/static/` -- no jsdelivr / unpkg dependency.  The tool runs
  fully offline now (important for an internal company app on
  inconsistent connections).
- **Footer polish.**  Now carries app version, short git SHA, server
  uptime, and DB path.  Tiny but useful for spotting "wait, am I on
  the test DB?" mid-session.

### Verification
- **+21 tests** (`tests/test_web_phase_e.py`), **578 / 578 total
  passing** (+155 across the whole M5 build).
- Tests cover: `/db` index + table render, 404 on unknown table,
  empty table renders politely, every read-only forbidden surface
  (`/db/exec` / `/db/query` / `/db/sql` / `/db/{table}/edit` /
  `/db/{table}/delete` / `/db/export`) returns 404 or 405, raw-JSON
  panels render on project + document detail with the
  `data-testid="raw-json-panel"` marker, footer carries all four
  fields, pico.min.css + htmx.min.js are served from `/static`,
  base.html does NOT reference `cdn.jsdelivr.net` or `unpkg.com`.
- Live smoke against the real DB: `/db` lists all 14 canonical
  tables with live counts; `/db/project` and `/db/document` render
  top-100 rows; offline assets all 200 with the expected byte
  sizes; footer renders `v0.1.0`, git SHA `dac9218`, `10s` uptime,
  full DB path.

### M5 milestone closed
Phase 6 / M5 -- the local web UI -- shipped in five slices:
A skeleton + dashboard, B+C read-only browsing, D HTMX
accept/reject with two-click confirm + stale guard, D.1 action
surfaces (propose / ask / manual task date edit), E this closeout.

**Total scope of M5:** 14 routes, 23 templates, +155 tests, ~5500
LOC added.  The full read+decision+action loop is in the browser;
the CLI surface stays intact and authoritative.

The M5 RETROSPECTIVE writeup lived in the former `docs/ROADMAP.md` (removed in
the 2026-06-09 doc consolidation; recoverable from git history).

### State at EOD
- **578 tests** passing.
- M5 closed.  Next: tighten proposal reasoning prompts (high-value,
  small) OR RAG over DocumentText (high-value, large), per ROADMAP.

---

## 2026-05-26 — Askbot assertive prompt rewrite + markdown rendering

**Theme:** User report: the askbot was "annoying" -- gave up on broad
questions with "I cannot determine that from the snapshot."  Root
cause was the prompt literally instructing the model to bail.  Plus
three UI bugs from the same review.

### Askbot: assertive inferential prompt (commit `dac9218`)
- Rewrote `ai/query.py::answer_with_llm` system + user prompts.  New
  behavior: best-supported answer first, label inferences, identify
  missing data only AFTER giving the strongest reasonable answer.
- max_tokens 1024 -> 2048 (the assertive style produces longer answers
  with Hard Facts + Inference + Recommendation sections).
- Anti-hallucination rules preserved verbatim -- "never invent project
  names, clients, invoices, tasks, dates, document contents, contract
  terms, or dollar amounts" stays in place.
- **Scope discipline**: this assertive style is the askbot's ONLY.
  The timeline / scope proposal prompts (Sonnet) stay conservative --
  they extract facts that get written to Monday; refusal-on-uncertainty
  is desired behavior.  A regression test
  (`TestProposalBotsStayConservative`) pins this boundary.
- +8 tests (`tests/test_askbot_assertive_prompt.py`).
- Live: "What should we focus on this week?" produced a multi-project
  operational analysis with named tasks, real overdue dates, blockers,
  recommendations, and a data-gaps inference section at the end.
  Transformative vs. the previous "I cannot determine that" output.

### UI fixes (commit `cbb3ace`)
- **Dashboard counts alignment.**  Articles had inconsistent inner
  rhythm (CRM panel 1.5rem vs 2rem on others).  Added `.dash-card`
  flex column + `.dash-number` fixed-height row + `.dash-breakdown`
  pinned to the bottom via `margin-top: auto`.  CRM panel reformatted
  to show total deals+leads as the big number, breakdown below.
- **Task edit Cancel showed "Writing to Monday..." infinitely.**
  Cause: `hx-indicator` was on the `<form>` tag, so the Cancel
  button's `hx-get` inherited it.  Moved to the Save (submit) button
  only.  Regression test pins: form has no indicator, Cancel has
  no indicator, Save does.
- **/ask LLM responses rendered as plain text.**  Haiku's markdown
  was getting dumped one-line.  Added the `markdown` library to the
  [ui] extra; new `_render_markdown()` helper pre-escapes HTML (defense
  in depth) then runs markdown -> HTML5 with `sane_lists` + `nl2br` +
  `fenced_code`.  Template renders via `|safe`.  CSS tightens spacing
  for short answers.  +4 tests pin: bold / italic / lists survive,
  embedded `<script>` is escaped, canned dicts still go through JSON.

---

## 2026-05-25 (late night) — Phase D.1 fixes: truncation handling + UI spinners

**Theme:** Two concrete bugs the user hit immediately after Phase D.1
shipped, both fixed in one push.

### Bug 1: scope generation failed silently on 6554 Rue Saint Hubert
- Symptom: `POST /projects/{6554}/propose/scope` returned HTTP 200 but
  with the "Skipped: LLM call failed" panel.
- Cause: Sonnet's reply was cut off at the 3000-token cap mid-JSON,
  twice in a row (`complete_json` retried with the SAME cap, hit the
  same wall).  The 9000-char and 9700-char truncated payloads both
  failed parse.
- Root fix (`ai/providers/base.py::complete_json`): inspect
  `resp.finish_reason` after a failed parse.  When it equals
  `"max_tokens"` (Anthropic) or `"length"` (OpenAI-compatible), the
  output was truncated -- bump `max_tokens` by 1.5x for the retry (up
  to a 16k ceiling).  The follow-up user turn explicitly tells the
  model "your previous reply was cut off; be more concise."  When all
  retries truncate, the final `LLMProviderError` now names truncation
  so the UI can render a useful hint instead of a generic "bad JSON"
  message.
- Secondary fix: `generate_scope_proposals` default
  `max_output_tokens` raised 3000 -> 5000.  Scope replies tend to be
  longer than timeline replies (each gap carries scope_item +
  suggested_task_title + reasoning + source_document).
- Surface fix: `propose_result.html` now renders `batch.errors` even
  when `batch.skipped_reason` is set, so the user sees the real
  parse error.  When the joined errors mention "trunc", an extra
  hint paragraph explains that the next attempt will use a larger
  cap and to try again.
- **Live verified**: the same 6554 scope-generate that previously
  produced "Skipped: LLM call failed" now produces **20 scope
  proposals, 0 rejected, 0 warnings** in 66s.  Both `complete_json`
  attempts succeeded; the bumped cap was needed.

### Bug 2: no loading indicator on action buttons
- Symptom: clicking "Propose timelines" gave no feedback for 10-30s,
  so the user could click again (wasting tokens) or click "Propose
  scope" while the first call was still in flight.
- Fix: every action button now carries `hx-indicator` + `hx-disabled-elt`:
  - Propose timelines / scope: amber "Calling Sonnet... 10-30s.
    Don't click again." pill, both buttons disabled in the same
    `<fieldset>` during the request.
  - Dry-run / Accept: amber "Working..." / "Writing to Monday... do
    not click again" pill, button group disabled.
  - Reject: same.
  - Task date Save: amber "Writing to Monday..." pill.
  - Ask form: amber "Routing your question..." pill (plus a tiny inline
    JS submit listener since /ask is a regular POST, not HTMX).
- CSS in `web/static/app.css`: `.htmx-indicator` hides by default;
  the `htmx-request` class HTMX adds during the in-flight period
  reveals it.  `.working` is an amber pill with a CSS-only spinning
  border.

### Verification
- **+8 tests** (`tests/test_complete_json_truncation.py`),
  **544 / 544 total passing**.
- New tests pin: succeed-first-try, retry-after-prose keeps same cap,
  retry-after-truncation bumps the cap (Anthropic `max_tokens` AND
  OpenAI-compatible `length`), ceiling respected, exhausted retries
  on truncation surface a "truncation" hint, exhausted retries on
  non-truncation do NOT claim truncation, retry conversation appends
  a "be more concise" follow-up.
- Live: re-running scope generation on the previously-failed
  6554 Rue Saint Hubert produced 20 grounded proposals in one click.

### State at EOD
- **544 tests** passing.
- The two user-reported bugs are gone:
  1. Long LLM replies that exceed the token cap now succeed via the
     auto-bumping retry, and surface a useful hint when they don't.
  2. Every action button shows an amber spinner pill and disables
     its button group during the request.

---

## 2026-05-25 (night) — Phase 6 / M5 part D.1: action surfaces

**Theme:** The user observed that Phase D shipped an Accept button but
all 19 PENDING proposals were scope_gap (intentionally Accept-disabled),
so the loop wasn't observable end-to-end.  Fix: add the three action
surfaces that let a PM actually USE the system from the browser --
generate proposals, ask questions, edit task dates directly.

### Routes added
- `POST /projects/{id}/propose/timelines` -- spends Sonnet tokens to
  propose forward-looking start/end dates for dateless tasks.
  hx-confirm warning before each click.
- `POST /projects/{id}/propose/scope`     -- spends Sonnet tokens to
  flag scope items in contracts with no matching Monday task.
- `GET /ask`, `POST /ask` -- natural-language Q&A.  Keyword routes
  answer instantly via canned reports; no-match free-form questions
  fall through to the fast model (Haiku via `get_fast_provider`)
  reading a JSON snapshot of the whole DB.
- `GET /tasks/{id}/dates-form`   -- inline edit form for one task row
- `POST /tasks/{id}/set-dates`   -- writes the timeline to Monday FIRST,
  mirrors onto the canonical Task on success.  No Proposal row created
  (manual edits aren't AI suggestions; the audit lives in Monday's
  activity log).
- `GET /tasks/{id}/row`          -- static-row partial, used by the
  Cancel button on the edit form.

### Backend: set_task_timeline
- New function `ai.proposals.set_task_timeline(session, task_id, *,
  start_date, end_date, writeback, decided_by)`.
- Mirrors `accept_proposal`'s write-first/mirror-second ordering exactly.
- On any failure (validation, bad dates, end-before-start, missing
  connector, Monday returned False, connector raised) the DB is left
  untouched.

### Tasks panel reworked
The previous "dateless first, then a collapsed All tasks table" layout
hid the actual dates.  Now: ONE combined sortable table on the project
page with every task's title, status, Monday status, start, end, due,
a `dateless` pill when all three dates are NULL, and an Edit button
per row.  Edit swaps the row in place for an inline date-edit form
via HTMX; Save writes to Monday and renders the updated row;
Cancel swaps back without touching the DB.

### Generate panel
New section F on the project detail page: two buttons
`Propose timelines (LLM)` and `Propose scope gaps (LLM)`.  Each carries
an explicit hx-confirm dialog that names the token cost.  The result
fragment shows the batch summary (created / superseded / rejected /
warnings) with details collapsible.

### Discoverability
- New nav link `Ask` in the top bar.
- The /ask page lists every keyword pattern the dispatcher routes,
  so a non-technical user can see what's free and what spends tokens
  ahead of time.

### Verification
- **+32 tests** (`tests/test_web_phase_d1.py`), **536 / 536 total
  passing**.
- Tests cover: propose-timelines happy/skip/provider-error, scope happy
  path, /ask empty / canned / no-match LLM fallback / failed fast
  provider, manual task edit happy / failing writeback / raising
  writeback / end-before-start / 404, tasks panel renders dates +
  dateless pill + edit URLs.
- Phase D.1 forbidden-routes test class added: plain `/propose` and
  `/propose/timelines` (without project scope), `/proposals/accept-all`
  / `reject-all`, `/tasks/{id}/edit` and `/tasks/{id}/delete` (only
  `/set-dates` and `/dates-form` exist), `/sync` -- all still 404 or 405.
- **Live smoke against the real DB**:
  - `/ask "Which of our projects looks most at risk?"` -> mode=llm,
    `spent tokens` pill, real Haiku answer citing 923 Rockland.
  - `/ask "help"` and `/ask "what active projects do we have?"` ->
    mode=canned, `free` pill, instant response with structured data.
  - `POST /projects/{5768 St-Laurent}/propose/timelines` -> Sonnet
    call (~10s), batch result: 1 timeline created, 1 rejected as
    malformed (the past-date guard fired correctly on a 2026-05-10
    item -- exact behavior prompt-engineering review #4 mandates).
  - The newly-created timeline proposal renders the **idle fragment
    with Accept ENABLED** (no `disabled` attribute, no advisory-only
    copy), distinct from the scope_gap proposals whose Accept stays
    disabled.
  - `POST /proposals/{new timeline}/dry-run` -> yellow PREVIEW panel
    showing the actual Monday payload
    `{"timeline": {"from": "2026-06-20", "to": "2026-06-21"}}` for
    task "Unit 8".  Nothing written.
  - Tasks panel for 5768 St-Laurent shows 16 task rows with the
    dateless pill on 5 rows; every row carries a working
    `hx-get="/tasks/{id}/dates-form"` Edit button which renders the
    inline date inputs + Save/Cancel.

### What was NOT done
- A real Monday accept through the UI was deliberately NOT executed,
  same precedent as the 2026-05-21 CLI accept -- that needs explicit
  user sign-off.  The dry-run preview is fully verified; the actual
  Confirm-accept is one click away.

### State at EOD
- **536 tests** passing.
- A PM can now do the entire daily loop from the browser:
  1. Click "Ask" and ask anything (canned reports free, Haiku
     fallback for free-form).
  2. Open a project, click "Propose timelines" or "Propose scope gaps"
     to spend Sonnet tokens generating proposals.
  3. Click into a proposal, read the citations, dry-run the Monday
     payload, then Confirm to actually write -- or Reject with a
     reason.
  4. Or skip the AI entirely: click Edit on any dateless task row,
     type dates, Save -- written to Monday directly.
- Phase E (DB inspector + raw JSON panels) is the only UI slice left.

---

## 2026-05-25 (evening) — Phase 6 / M5 part D: accept / reject in the UI

**Theme:** The riskiest piece of the UI -- the one path that mutates a
live external system.  Built the same way the CLI accept was built in
Session 3b: write-back FIRST, status flip second, never the reverse.
The UI is a thin adapter; the CLI's existing `accept_proposal` /
`reject_proposal` keep their guarantees.

### Routes added
- `POST /proposals/{id}/dry-run`  -- preview the Monday payload; no DB
  change, no API call.  Renders a yellow PREVIEW fragment that is
  visually distinct from any accepted state (no green pill, no
  decided_at).
- `POST /proposals/{id}/accept`   -- write to Monday, flip status to
  ACCEPTED, mirror dates onto the canonical Task.  HTMX confirm prompt
  before the click takes effect, so a real Monday write needs two
  intentional interactions.
- `POST /proposals/{id}/reject`   -- pure DB.  Inline form takes an
  optional reason.
- `GET  /proposals/{id}/decision` -- re-render the decision panel;
  used as the Cancel target after a dry-run preview.

### Stale-state handling (review #5, load-bearing)
Every POST re-reads the proposal RIGHT BEFORE delegating.  If the
status is no longer PENDING (CLI decided it, or another browser tab,
or a bulk operation), the route returns a `decision_stale` fragment
explaining what happened and offering a reload link.  No 4xx, no
silent no-op, no double-write.  Pinned by
`tests/test_web_phase_d.py::TestAccept::test_accept_already_accepted_returns_stale_no_double_write`,
which asserts `sync_back.call_count == 0` on a stale POST.

### Dry-run / accept separation (review #6)
- Dry-run fragment uses yellow PREVIEW banner, "would_write" JSON
  prettily formatted, explicit "Nothing written yet" copy.
- Accept fragment uses the decided styling -- green for ACCEPTED,
  grey for REJECTED, with decided_at / decided_by / payload.  Cannot
  be confused with a preview.
- Confirm-accept button carries `hx-confirm` so the browser shows
  a native confirm dialog before the real Monday write.

### Thin-adapter discipline (review #14)
The route handlers do FOUR things and nothing else:
  1. Re-read proposal state (stale guard).
  2. Build connector via `deps.build_monday_writeback` (test-mockable).
  3. Delegate to `ai.proposals.accept_proposal` / `reject_proposal`.
  4. Render one of {idle, dry_run, decided, stale} partials.
No new business logic.  No proposal transformations.  No silent error
swallowing -- every backend `{"ok": False, "error": ...}` surfaces
inline in the idle fragment.

### Decision partials (all swappable via HTMX outerHTML)
- `_partials/decision_idle.html`    -- PENDING; Accept disabled when
  `field_name not in _ACCEPTABLE_FIELDS` (currently scope_gap).
- `_partials/decision_dry_run.html` -- yellow PREVIEW with payload +
  Confirm + Cancel.
- `_partials/decision_decided.html` -- ACCEPTED / REJECTED / SUPERSEDED.
- `_partials/decision_stale.html`   -- yellow warning + reload link.

### Verification
- **+20 tests** (`tests/test_web_phase_d.py`), **504 / 504 total
  passing** (+82 across Phases A-D combined).
- New tests cover: dry-run preview, dry-run does not change DB,
  scope_gap dry-run refused, accept happy path (mocked Monday,
  asserts sync_back called once with the right payload, status
  flipped, task dates mirrored), accept on already-accepted returns
  stale + `sync_back.call_count == 0`, accept with failing writeback
  leaves proposal PENDING, accept with raising writeback leaves
  proposal PENDING, scope_gap accept refused (sync_back never
  called), reject with reason, reject scope_gap works, reject on
  already-decided returns stale, GET /decision returns idle when
  PENDING / decided otherwise, connector-factory raising surfaces
  inline.
- Phase A / B forbidden-route tests updated: per-proposal accept /
  reject / dry-run now legitimately exist and are tested in Phase D;
  bulk endpoints (`/proposals/accept-all` etc.) remain forbidden.
- Live smoke: GET on a real PENDING scope_gap proposal renders the
  idle fragment with Accept disabled + "advisory-only" explanation.
  POST dry-run AND POST accept on the same scope_gap both render the
  idle fragment with "Action failed (scope_gap not acceptable)" and
  leave the proposal PENDING.  No real Monday writes were attempted
  -- those need explicit user sign-off (per the 2026-05-18 Session
  3b precedent).

### What is NOT in Phase D
- No bulk accept / reject in the UI (CLI's `accept all --yes` still
  works for that).
- No live Monday accept executed yet -- the code is exercised
  end-to-end against a mocked connector in tests; one real accept
  through the UI needs explicit user sign-off, same way the CLI
  accept did on 2026-05-21.

### State at EOD
- **504 tests** passing.
- The full read + decision loop is wired through the UI.  A PM can
  open a project, read its proposals with the source documents
  expanded, dry-run a timeline, confirm or reject it -- all from
  the browser.  Phase E (DB inspector + raw JSON panels) is the
  last UI slice.

---

## 2026-05-25 (later) — Phase 6 / M5 parts B+C: read-only browsing

**Theme:** The UI is actually usable now.  Phase A only had the
dashboard; every nav link 404'd.  This entry adds projects, documents,
proposals, and doctor -- all read-only, all wired to the existing
canned reports and proposal functions.  The dashboard's pending strip
finally goes somewhere.

### Routes added (all GET, all read-only)
- `/projects` -- every project with rolled-up counts and a
  pending-proposal tally
- `/projects/{id}` -- 5-panel detail (identity / overview /
  tasks / documents grouped by folder / proposals grouped by status)
- `/documents/{id}` -- metadata + full extracted text (scrollable
  `<pre>`) + every proposal citing this document
- `/proposals` -- filterable queue (status + kind via query params)
- `/proposals/{id}` -- 5-panel review page: target, proposed value
  (timeline / scope_gap parsed visually), citations + confidence,
  decision audit / "Phase D will add buttons" placeholder, supersede chain
- `/doctor` -- read-only audit; same data structure
  `project_db doctor` prints

### Service-module discipline
Per the M5 plan's #2 ("no business logic in the UI"), every derived
value lives in `web/ui_views.py`:
  - `project_list_rows`, `project_detail`, `document_detail`,
    `proposal_queue`, `proposal_detail`, `doctor_report`
  - Document grouping by folder, extraction-status badges, supersede
    chain, can_accept flag (mirroring `_ACCEPTABLE_FIELDS` from
    `ai.proposals`)
  - Templates do presentation only; calculations stay in Python

### cmd_doctor refactored
- New `report_doctor(session)` in `ai/views.py` returns the audit as a
  pure JSON-serializable dict.  `cmd_doctor` is now a thin renderer
  over it.  The `/doctor` route renders the same dict as HTML, so the
  two surfaces can never drift apart.
- Old inlined-in-cmd_doctor logic deleted (no dead code retained).

### Citation precision (per #7 in the plan review)
- Excerpt-offset metadata is NOT stored on `Proposal`; the proposal
  detail page is explicit about this -- it labels source documents as
  "this document supports the claim" rather than implying span-level
  precision, and links to `/documents/{id}` for the full text the
  model actually saw.
- When `source_documents` is empty, a prominent red article is rendered
  with "! No source documents are attached to this proposal."  Live
  verified on the 5768 St-Laurent "Quality Inspection & Punch List
  for Units 6-10" proposal which was flagged at creation time for an
  unsupported citation.

### Confidence is secondary (per #8)
- Confidence renders as a small pill colored green / amber / red, but
  the text right next to it says "(secondary signal -- citation
  evidence wins)" and the section header is "Citations & confidence",
  not "Confidence".

### Read-only is enforced by tests
- `tests/test_web_phase_b.py::TestPhaseDForbidden` covers all
  accept/reject/dry-run/bulk endpoints.  GET and POST must each
  return 404 or 405 until Phase D ships.
- `TestProjectDetail::test_no_accept_button_in_phase_b` asserts the
  project page doesn't even *render* an accept/reject button in v1
  (a UI-side regression net against accidental drift).
- 404 paths covered for unknown UUIDs AND malformed (non-UUID) ids on
  every detail route.

### Verification
- **+31 tests** (`tests/test_web_phase_b.py`), **484 / 484 total
  passing**.
- Live smoke against the real DB:
  - `/projects` lists all 21 projects with live counts
  - `/projects/{1455 St. Mathieu}` renders all 5 panels with real
    SOW proposals + 7 grouped document folders
  - `/documents/{first SOW}` opens with full extracted contract text
  - `/proposals?status=PENDING` -> 19 pending rows
  - `/proposals/{scope flagged proposal}` -> red "no source documents"
    warning shows; LLM reasoning shows in a blockquote
  - `/doctor` flags 1 issue (8 orphan documents) -- matches the CLI
  - All 7 sampled forbidden routes return 404 / 405 on live server

### Minor API extensions
- `report_project_overview.tasks[].canonical_id` added (was missing)
- `report_project_overview.recent_documents[].canonical_id` added
- `report_docs_for_project.documents[].canonical_id` added
- `report_tasks_without_dates.tasks[].canonical_id` added
- These are additive; the LLM-tool layer benefits too.

### State at EOD
- **484 tests** passing.
- Read-only UI complete.  Every nav link now resolves; dashboard's
  pending strip lands on a full review page.
- Phase D (the riskiest piece) is next: HTMX accept / reject with
  two-click confirm, stale-state handling, fresh-read-before-mutate.

---

## 2026-05-25 — Phase 6 / M5 part A: local web UI skeleton

**Theme:** Scope reconciliation output across 923 Rockland, 1455 St.
Mathieu, and 5768 St-Laurent was inspected (19 grounded gaps total, with
the hallucination guard correctly firing on 2 unsupported citations in
the 5768 run), and judged trustworthy enough to move M4 to "ongoing PM
review" and start M5 (local web UI).

Phase A is the first of five planned UI slices: skeleton + dashboard.

### What landed
- New `[ui]` extra in `pyproject.toml`: `fastapi`, `uvicorn[standard]`,
  `jinja2`, `python-multipart` (mirrored into `[dev]` so tests run
  without an extra install step).
- New `project_db.web` package:
  - `app.py` — FastAPI factory; localhost-only by construction (no CORS
    middleware, no `--host` flag).
  - `deps.py` — `db()` Session dependency over the existing
    `session_scope`; `git_sha()` and `db_path()` helpers used by the
    footer.  `git_sha` falls back to `"unknown"` outside a git checkout
    instead of crashing startup.
  - `ui_views.py` — service module.  All derived dashboard numbers are
    computed here, never in templates / routes, so the "no new business
    logic in the UI" rule is enforced by file boundaries.
- Templates: `base.html` (Pico.css + HTMX from CDN, nav, footer with
  git SHA + DB path) and `dashboard.html` (counts panels + pending
  proposals strip).
- `static/app.css` with the status-pill conventions used by later phases.
- CLI: `project_db serve [--port 8000]` binds hard to `127.0.0.1`.
  No `--host` flag.  Graceful error if the `[ui]` extra is not installed.

### Verification
- **+31 tests** (`tests/test_web_phase_a.py`), **453 / 453 total
  passing**.  New tests cover:
  - dashboard renders 200 on empty AND seeded DBs
  - service-module counts match seed data
  - footer carries the git SHA / DB path
  - **permission-boundary tests** prove `/sync`, `/sync/monday`,
    `/sync/GOOGLE_DRIVE`, `/propose`, `/propose/timelines`,
    `/propose/scope`, `/projects/edit`, `/tasks/edit`, `/documents/edit`,
    `/db/exec`, `/db/query` all return 404 (the routes we explicitly
    forbade in the M5 plan must not exist)
  - no CORS headers leak to a cross-origin `Origin` request
  - `git_sha` never raises (graceful fallback outside a git checkout)
- Test infra: this file overrides the conftest `db_engine` with a
  `StaticPool` + `check_same_thread=False` SQLite engine so FastAPI's
  TestClient (which dispatches sync routes through a threadpool) can
  share one in-memory DB across threads.
- Smoke run against the live DB: `project_db serve --port 8765` →
  dashboard rendered with real numbers — 83 dateless tasks, 461 docs
  with extracted text, 19 PENDING proposals, footer showing git SHA
  `f161188`.  Four forbidden routes all returned 404 against the live
  server as well.

### State at EOD
- **453 tests** passing.
- Phase A complete: skeleton + dashboard live.
- Next (Phase B): project list, project detail, document detail,
  doctor page — all read-only.  No mutation routes until Phase D.

---

## 2026-05-22 — Monday column fix, ask LLM fallback, bulk proposals, scope reconciliation

**Theme:** Closed the Monday "missing columns" gap, made `ask` answer
free-form questions, made proposal review usable in bulk, and shipped the
first scope-reconciliation prompt.

### Monday subitem mirror overlay
- `apply_portfolio_mirror_overlay` now walks subitems (recursive `_inject`)
  and collects link ids recursively (`_collect_linked_item_ids`). The
  per-task Status/Timeline that lives on linked portfolio items now
  reaches the DB for subitems too (was hitting top-level items only).
- 923 Rockland: status/timeline coverage went from ~5/118 to 93/118.

### `ask` LLM fallback (Haiku) + bulk proposal review
- `get_fast_provider()` resolves a small/cheap model (Haiku via
  `ANTHROPIC_MODEL_FAST`, default `claude-haiku-4-5`).
  `get_default_provider()` stays on Sonnet for analytical work.
- `report_database_overview(session)`: whole-DB snapshot — every
  project/task/deal/lead/client/invoice + doc-category breakdown
  (excludes document text by design).
- `AiAssistant.answer_with_llm(question, provider)`: feeds the snapshot
  to the fast LLM. Canned reports stay instant; only the no-match
  fallthrough spends a token.
- `proposals accept` / `reject` with no id → print the pending queue;
  `accept all --yes` / `reject all --yes` → bulk decide every pending
  proposal at once.
- `main()` forces UTF-8 stdout (Windows console fix for LLM em-dashes).

### Deal/project trust + daily review (earlier in the day, by user)
- Empty `Project - <deal>` placeholders with a matching `Deal` row are
  recognized as CRM deals, not failed projects — both `doctor` and
  `report_missing_documents` honor it.
- `project_db daily <project>`: one-screen read-only review; LLM strictly
  gated behind `--propose-timelines`.

### Timeline prompt v2
- Anchored to today + the project's already-dated tasks. Past-dated
  proposals are rejected at validation time. Guards the 2022-date bug.

### Scope reconciliation (`propose scope <project>`)
- `generate_scope_proposals`: Sonnet reads contract/SOW documents + the
  current Monday task list, flags documented scope items with no
  matching task.
- Guards: a suggested task that already exists is not flagged; cited
  source documents not supplied are warned as possible hallucination;
  re-running supersedes the prior scope batch (fresh snapshot semantics).
- `_enrich_target` extended for `entity_type="Project"` so scope
  proposals render correctly in `proposals list/show`.
- Advisory-only — `accept` refuses scope_gap proposals (a Monday
  create-task write-back is future work).

### Verification
- **422 tests** passing (+29: 6 `get_fast_provider`, 7 database overview +
  answer_with_llm, 4 bulk proposals parser, 5 CLI proposals behavior, 7
  scope reconciliation).
- Live: `ask "give me a short health summary..."` → grounded summary
  citing real numbers (21 projects, 153 tasks, 0 invoices, the deals).
- Live: `propose scope "923 Rockland"` → 7 grounded gaps citing
  `Final SOW.pdf Section 4 'RESPONSIBILITIES'`, source docs resolve.

### Docs
- New: `docs/HANDOFF.md` — developer handoff doc for the next Claude.
- README: command examples + env vars + What's New bullets.
- ROADMAP: scope reconciliation flipped to done; usability shipped note.

### State at EOD
- **422 tests** passing.
- Phase 3b expanded: timelines + scope advisory both live, advisory-only.
  Next: validate scope quality on more projects, then optionally anomaly
  detection, then minimal UI.

---

## 2026-05-21 — Phase 2.5: Foundation Correctness (project identity rebuilt)

**Theme:** A direct database audit found the canonical data was wrong at the
root -- project identity was unstable, so every report and every LLM proposal
was reasoning over garbage. Fixed the ingestion layer, not the AI.

### The disease
- 6 "projects" for ~3 real ones: "923 Rockland" split into two records;
  demo "deal" rows minted as projects.
- 60% of Drive documents (450 / 750) linked to no project at all.
- Mislinks: 18 documents from the "927 Rockland" folder were attached to a
  phantom "Rockland" project.
- Root cause: project identity came from "whatever Monday created", and Drive
  documents matched into it via a **substring** test -- "Rockland" matched
  "927 Rockland".

### The fix -- the Drive folder tree IS the project registry
- A folder at `01. PROJECTS/{ACTIVE,INACTIVE,LEADS}/<name>/` is one canonical
  Project, created keyed by folder id. Two folders never merge.
- Documents link to projects by **physical folder ancestry** -- fully
  deterministic. The `_match_project_by_name` substring matcher is deleted.
- `Document.category` -- every Drive file gets a home (a project, or a
  company-knowledge category: company / real_estate / construction /
  intelligence).
- `ProjectMatcher` (civic-number then exact-name, unique-hit-only, no
  fuzzy/substring) lets Monday boards match INTO Drive projects.
- `_classify_board` fails closed: a board matching no allowlisted rule is
  skipped + logged, never guessed into a Project (this kills the phantom
  "Rockland" and a stray "New Board").
- `resolve_or_create`: a matched (not newly-created) entity now also receives
  its attrs -- the path `rebuild` depends on. Without it, every preserved
  Document stayed unlinked (caught in live verification, then fixed).
- `create_only_attrs` -- Monday never renames a Drive-authoritative project.

### Tooling
- `project_db doctor` -- read-only trust instrument: project provenance,
  document/task counts, and mislink / orphan / duplicate-civic flags.
- `project_db rebuild` -- re-derive the canonical DB from the sources;
  preflight-checks every connector before wiping anything; preserves
  Document + DocumentText; exports Proposals to JSON first.

### Also today
- Anthropic provider wired live (`claude-haiku-4-5` for cost-efficient
  testing); added `ANTHROPIC_MODEL` env var and selective `.env` loading.

### Verification
- **388 tests** passing. Substring/civic matching tests replaced with
  deterministic folder-taxonomy + `ProjectMatcher` tests; added a regression
  test for the matched-path attrs bug.
- Live `rebuild` + `doctor`: 21 projects (19 real Drive folders + 2 demo
  Monday "deal" rows), **554 / 554 project documents linked, 0 mislinks**
  (was 300), all 750 documents categorized. "923 Rockland" and "927 Rockland"
  are correctly separate projects.

### State at EOD
- The foundation is correct and verifiable. Phase 3 scope/anomaly prompts and
  the Phase 6 frontend stay paused -- the brain now has a sound skeleton to
  build on.

---

## 2026-05-18 (later) — Session 3b (part 2b): accept + Monday write-back

**Theme:** The riskiest piece of Phase 3 -- the one path that mutates
a live external system.  Built carefully, staged, dry-runnable.

### accept_proposal -- the advisor->action closer
- `accept_proposal(session, proposal_id, writeback, dry_run, decided_by)`.
- **Ordering is load-bearing:** the Monday write happens FIRST; the
  proposal flips to ACCEPTED only on a True return.  A failed write
  leaves the proposal PENDING and the canonical Task untouched -- so we
  can never have an ACCEPTED proposal that didn't reach Monday.
- Writes a timeline proposal's `{start, end}` to Monday as a
  `{"timeline": {"from", "to"}}` column update via the existing,
  battle-tested `MondayConnector.sync_back`.
- On success, also mirrors the dates onto the canonical Task so
  `ask "tasks without dates"` reflects reality immediately (the next
  Monday sync re-confirms the same values -- idempotent).
- `--dry-run`: resolves + validates everything, prints exactly what
  WOULD be written, touches nothing.  No connector needed.
- Guards: bad UUID, not-found, PENDING-only, known field/entity only,
  unparseable dates, missing connector.  Every failure leaves the
  proposal PENDING.
- A raising connector is caught -> proposal stays PENDING.

### CLI
- `project_db proposals accept <id> [--dry-run] [--by]`.
- Dry-run never builds a Monday connector / never needs a token.

### Verification
- 16 new tests (367 total).  The load-bearing one
  (`test_write_back_false_leaves_proposal_pending`) proves a failed
  write does NOT flip status and does NOT mirror the task.
  Also: double-accept rejected, raising connector survived, dry-run
  touches nothing, exact sync_back payload asserted.
- Live: dry-run via the real CLI on a seeded proposal -- correct
  preview (`{"timeline": {"from": "2026-09-01", "to": "2026-09-12"}}`),
  proposal confirmed still PENDING, cleaned up.
- A REAL Monday write was deliberately NOT performed -- that mutates
  the user's live workspace and needs explicit sign-off.

### State at EOD
- **367 tests** passing.
- Approval loop CODE-complete: list / show / reject / accept all built.
- Outstanding before the loop is *proven* end-to-end: one real
  `accept` against Monday (user sign-off), and prompt-quality
  validation (needs the real model).

---

## 2026-05-18 — Session 3b (part 2a): reject + a security incident

**Theme:** Methodical, low-risk progress.  The safe half of the
approval loop, plus a real security finding caught during a routine
audit.

### SECURITY INCIDENT (commit 3f0cd5b)
Routine `.env.example` audit found two leaks on the PUBLIC GitHub repo,
live since 2026-05-11:
- `project-db/.env` (the real secrets file) was tracked in git --
  committed before `.gitignore` existed, and gitignore does nothing
  for already-tracked files.
- `.env.example` (the template) carried a live, write-scoped Monday
  API token.
Fixed: `.env` untracked (`git rm --cached`, local copy kept),
`.env.example` scrubbed + refreshed to current vars.  Code side is
closed.  **User rotated the exposed credentials** -- that's the real
remediation; untracking only stops future leakage.

### Proposal reject (the safe half of approval)
- `reject_proposal(session, proposal_id, reason, decided_by)` -- pure
  DB, no external system touched.  Flips PENDING -> REJECTED, stamps
  decided_at / decided_by / rejection_reason.
- Guards, all explicit errors (never silent no-ops): bad UUID,
  not-found, and -- critically -- only PENDING proposals can be
  rejected.  Rejecting an already ACCEPTED/REJECTED/SUPERSEDED
  proposal fails loudly and leaves status untouched.
- CLI: `project_db proposals reject <id> [--reason ...] [--by ...]`.
  `--by` defaults to the OS username for a real audit trail.
- 12 new tests (353 total).  Live-verified on the real DB: rejected a
  seeded proposal via the CLI, confirmed the double-reject guard
  fires, cleaned up.

### Deliberately NOT done yet -- `accept`
`accept` writes back to Monday (a real external mutation) -- the
single riskiest piece of Phase 3.  Held for its own focused session.
Groundwork done: studied `MondayConnector.sync_back` in full.  Key
finding for next session: sync_back commits its own session
internally, so `accept` must do the Monday write FIRST and flip the
proposal status only on a True return -- never the reverse.

### State at EOD
- **353 tests** passing.
- Approval loop: list / show / reject done; accept + write-back next.

---

## 2026-05-17 — Session 3b (part 1): the proposal engine

**Theme:** The LLM stops being a demo and starts producing
operationally useful output -- structured proposals in the Proposal
table, gated for human review.  Per STRATEGY.md: advisor, never actor.

### Proposal engine (`src/project_db/ai/proposals.py`)
- `generate_timeline_proposals(session, provider, project_id)` —
  assembles project context, builds the timeline prompt, calls the
  LLM, validates each returned item, writes `Proposal` rows (PENDING).
- **Timeline extraction prompt** — the flagship per STRATEGY.md
  (only ~11% of Monday tasks have dates; the contracts hold the real
  schedule).  Reads dateless tasks + contract text, proposes
  start/end dates with evidence-based reasoning.
- `ProposalBatch` result object — created / superseded / rejected
  counts, errors, skip reason.  `.summary()` for the CLI.
- Read side: `list_proposals()` (status/kind filters) and
  `get_proposal_detail()` (resolves polymorphic target + source docs).

### Design decisions
- **LLM references tasks by integer INDEX, never UUID.**  Models
  reliably miscopy 36-char UUIDs; we map index -> canonical Task.
- **Instruction at the TAIL** of the prompt (the 2026-05-16 lesson).
- **Every LLM item validated** before becoming a Proposal: index in
  range, dates parseable, end >= start, confidence clamped to [0,1].
  Bad items go to `ProposalBatch.errors`, never crash the batch.
- **Auto-supersede**: a new proposal for the same
  (entity_type, entity_id, field_name) flips prior PENDING ones to
  SUPERSEDED, so the reviewer only sees the latest.
- Skip paths: no dateless tasks, or no extracted document text to
  reason from -> clean no-op with a reason, not an error.

### CLI
- `project_db propose timelines <project>` — generate proposals.
- `project_db proposals list [--status] [--kind]` — newest-first.
- `project_db proposals show <proposal_id>` — full detail incl.
  parsed value, source documents, decision audit fields.

### Verification
- 32 new tests (343 total), all against MockLLMProvider -- offline,
  deterministic.  Covers happy path, every skip/error path, supersede,
  validation, read side, CLI parsing.
- Live: ran the engine against 923 Rockland (115 dateless tasks,
  3 docs with extracted text) with a mock provider -- created a real
  Proposal row, read it back via list + show, then cleaned up.
- Live: CLI `propose` + `proposals list` plumbing exercised.

### NOT done (Session 3b part 2)
- `proposals accept / reject` -- the accept path writes back to
  Monday via `sync_back`, deserves its own focused session.
- `scope` and `anomaly` prompts -- same engine shape, more of it.
- Prompt-quality tuning -- needs a real model (Claude API / Mac mini);
  the engine is built and tested, quality is a later pass.

### State at EOD
- **343 tests** passing.
- Phase 3b half complete: proposals generate + view.  Approval
  actions + remaining prompts are the next session.

---

## 2026-05-16 (afternoon) — Session 3a close-out: delta sync + LLM smoke

**Theme:** Wrap up 3a with the deferred Monday delta-sync work and a
real end-to-end LLM smoke test against a local model.  Ship the
prompt-design lessons learned along the way.

### Monday delta sync via `Board.activity_logs` (commit ea09770)
- `MondayClient.list_activity_logs(board_id, from_ts, ...)` — paginated
  GraphQL against the live API.  20-page safety cap.
- `MondayConnector.sync(delta=True)` smart-skip: queries the change
  feed per board, skips boards with zero activity since their stored
  cursor.  Cursor pattern mirrors Drive's `changes.list` cursor —
  per-board ExternalId rows with ISO8601 timestamps in `external_url`.
- Conservative on failure: if probing activity_logs errors, treat the
  board as changed (better wasted pull than missed update).
- CLI: `project_db sync monday --delta`
- **Live result on real DB:** full sync 38.1s → delta sync 6.4s,
  11 of 12 boards skipped (only users + 1 changed board re-pulled).
  6× speedup on a quiet day.
- 19 new tests.

### `project_db llm-test <project>` (commit f881076 + iterations)
- End-to-end smoke command: picks the configured provider, assembles
  real project context, sends a "give me a status update" prompt,
  prints the response.  Does NOT write Proposal rows.
- Knobs: `--token-budget`, `--max-docs`, `--max-output-tokens`,
  `--verbose`.  Defaults tuned for local CPU reality.
- Reports tokens/sec and elapsed time on every run.

### Local model setup (Ollama smoke run)
- User installed Ollama + pulled llama3.2:3b then qwen2.5:3b.
- `LLM_PROVIDER=openai-compatible`, `OPENAI_BASE_URL=http://localhost:11434/v1`,
  `OPENAI_MODEL=qwen2.5:3b`.
- Live result on Rockland (small project): coherent status update,
  225s on CPU at 0.3 tok/s.  Wires fully proven.

### Iterations forced by the smoke test (each its own lesson)
**Iteration 1 (commit 7f96321):** First call timed out.  Cold-start +
CPU inference + 600 max-output blew through the 120s default timeout.
Fixed: default 600s, OPENAI_TIMEOUT env var, smaller defaults on
llm-test (20k budget, 3 docs, 300 output tokens).

**Iteration 2 (commit 67fc3f3):** Added `--verbose` flag for prompt
dumping + per-call timing.  Also captured the dual-model future
architecture + RAG vision in ROADMAP.

**Iteration 3 (commit b74a4de):** Bigger smoke test (5768-5770,
11k tokens) produced a FRENCH LEASE REWRITE instead of a status
update.  Diagnosed: Ollama silently truncated to 4096 tokens from
the FRONT, so the head-loaded instruction got cut and the model
only saw lease boilerplate at the tail.  Fixed:
  1. Instruction moved to TAIL of user message (chat templates
     preserve the tail of the last user turn under truncation).
  2. System prompt restated as backup.
  3. Warning printed when estimated prompt size > 3500 tokens.
- This is a **general prompt-engineering lesson** that informs every
  Phase-3b proposal prompt: instruction LAST, context FIRST.
- Post-fix retry: same project, same model — model now correctly
  responds to "give a status update" using the truncated context it
  has.  Coherent on-topic English vs the previous French lease.

### State at EOD
- **311 tests** passing (+24 today).
- 8 commits since yesterday's EOD wrap.
- Phase 3a fully complete (provider abstraction + context assembler
  + delta sync + LLM smoke + prompt-engineering lessons baked in).
- Local model proven, slow on laptop, blocked from real use by
  hardware -- Mac mini / Claude API will fix.
- Phase 3b ready to start: real timeline / scope / anomaly prompts,
  Proposal table writes, approval CLI.

---

## 2026-05-16 — Session 3a: LLM provider abstraction + project-context assembler

**Theme:** Start Phase 3 by building the model-agnostic plumbing.  No
real model touched.  Designed so swapping Anthropic-for-now → local
Qwen-on-Mac-mini → fine-tuned Qwen is a config change, not a refactor.

### Provider layer (`src/project_db/ai/providers/`)
- **`base.py`** — `LLMProvider` ABC with one required method (`complete`)
  and one convenience (`complete_json` with retry-on-bad-JSON).
  Canonical message shape mirrors OpenAI Chat Completions because
  every local server speaks it.  Errors normalized as `LLMProviderError`.
- **`mock.py`** — `MockLLMProvider` for tests.  Sequential responses
  or callback; captures every call for assertions.
- **`anthropic_provider.py`** — translates to Anthropic Messages API.
  Lifts system-role turns to the `system` field correctly.  SDK
  errors wrapped, not raw.
- **`openai_compatible.py`** — works with Ollama, vLLM, llama.cpp,
  LM Studio, TGI, OpenAI itself.  Zero new code when Mac mini lands —
  flip `OPENAI_BASE_URL` env var.
- **`get_default_provider()`** — env-driven resolver
  (`LLM_PROVIDER=mock|anthropic|openai-compatible`).

### Project context assembler (`src/project_db/ai/context.py`)
- `assemble_project_context(session, project_id, token_budget, ...)`
  pulls Project + Client + Tasks + Documents + DocumentTexts +
  Invoices + DailyLogs into one structured `ProjectContext`.
- `to_dict()` for JSON; `to_prompt_block()` for direct prompt insertion.
- Three knobs: `max_documents_with_text` (top-N newest *with text*),
  `per_doc_char_cap` (per-body clip), `token_budget` (global, evicts
  bodies oldest-first when over).
- Live test on 5768-5770 St Laurent: 16 tasks, 143 docs metadata,
  5 contract bodies, ~14k token output block.

### Bug caught by tests before commit
- First implementation picked the N most-recent Documents and *then*
  looked up text — but the newest doc on Rockland was a HEIC photo
  with no DocumentText, so `max_documents_with_text=1` returned 0
  bodies.  Fixed: now joins through DocumentText first, then takes
  top-N by recency.  Semantic is "N readable bodies," not "N doc
  slots that might or might not have text."

### Decisions baked in unilaterally (push back if wrong)
1. OpenAI Chat Completions wire shape as canonical (every local
   server speaks it; Anthropic adapts via thin translator).
2. Structured output: retry-on-bad-JSON in base class; native
   `response_format=json_object` as opt-in HTTP hint where supported.
3. Anthropic plays prototyping role until Mac mini lands.
4. Three providers from day one (mock + anthropic + openai-compatible)
   so the local swap costs zero code later.

### Tests
- **287 total** (+41 today).
- 22 new in `test_ai_providers.py` covering interface contract,
  three concrete providers, JSON retry, env resolver.
- 19 new in `test_ai_context.py` covering assembly, trash exclusion,
  doc-budget eviction, prompt-block formatting, JSON serialization.

### What Session 3a did NOT do (next session)
- No prompts written (timeline / scope / anomaly — Session 3b).
- No proposals CLI (Session 3b).
- Monday `activity_logs` delta sync deferred to start of Session 3b.
- No real Anthropic API call yet — every test is mocked.

---

## 2026-05-15 (evening) — System audit + corrected Monday-delta-sync position

**Theme:** Honest audit of the whole system. Discovered I had been
asserting "Monday has no delta sync" for two days based on incomplete
reading of the API. Corrected the record across four docs.

### Audit findings (no code changes needed)
- **Empty tables triage:** `Invoice` and `DailyLog` empty by design
  (deferred connectors). `Vendor` and `Property` are coverage gaps with
  no current source. `Proposal` empty by design (Phase 3 hasn't started).
- **Connector coverage:** Monday + Drive both honor "keep everything"
  via JSON blobs (`source_columns_json`, `source_meta_json`); no silent
  data loss. QB code complete but never run.
- **Doc hygiene:** added missing `list-sources` and `list-external` to
  the README's daily-use list (commit b26ef1c).

### Correction: Monday delta sync framing
User caught me parroting "delta sync withdrawn" without verifying.
Re-read `docs/monday-graphql-schema.json`. Two viable paths exist that
I had ignored:
- `Board.activity_logs(from, to, ...)` — timestamped change feed,
  poll-based, no hosting needed.
- `create_webhook(board_id, url, event)` — scriptable mutation, 20+
  event types. Real blocker is hosting a public HTTPS endpoint, NOT
  API support.
Fixed framing in CLAUDE.md, README.md, ROADMAP.md, and the historical
OPTIMIZATION_v0.2.md (commit b57ccfb).

### Phase 3 plan, refined
- Recommendation: fold `activity_logs`-based delta sync into Phase 3a
  alongside the LLM provider abstraction + project-context assembler.
  The "re-propose when something changed" use case ties them naturally.
- Webhooks stay deferred until hosting exists (Mac mini scenario
  unblocks this).
- Four design decisions still pending from user before Session 3a:
  provider API shape (OpenAI-compatible recommended), structured-output
  strategy, role of Anthropic during local-model setup, fine-tuning
  corpus scope.

### State at EOD
- 246 tests passing.
- 750 Documents / 462 with extracted text / 2.19M indexed tokens.
- All Phase 0 / 1 / 2 exit tests passed; Phase 3 ready to start.
- 8 routed `ask` reports + `help` discoverability.
- Mission still pointed correctly per STRATEGY.md.

---

## 2026-05-15 (afternoon) — Phase 1 + Phase 2 close-out

**Theme:** Exit tests passed. Both phases officially done.

### Phase 1 exit test (PASSED)
Ran `project_db extract-content` over the full Drive tree.
- 742 documents processed (5 were already done)
- **457 with non-empty extracted text** (target was ≥200)
- 255 properly skipped as unsupported mime (HEIC, JPG, .wav, etc.)
- 12 skipped as too big (>10 MB)
- 1 actual failure (download error)
- 17 no-op (parsed cleanly but produced empty text — image-only PDFs)
- Every successful extraction carries a token_count

Total DocumentText rows in live DB: **751** (every Document has a status row).
Spot-check confirmed real readable text from contracts, leases, estimates,
DOCX scopes of work.

### Phase 2 exit test (PASSED)
All five reports verified live:
- `tasks_without_dates` → 137 dateless tasks
- `missing_documents` → 1 PROPOSED project flagged
- `project_overview` → Rockland: 1 task, 18 docs, 0 invoices
- `docs_for_project` → Rockland: 18 docs with folder_path context
- `budget_vs_contract` → 5768-5770 St Laurent contracts produced
  real $ extractions (rents, lease months, line items). Honestly
  returns `divergence_pct=null` when Monday budget is unset.

### New: discoverability for non-technical users
`project_db ask "help"` (or `?`, `what can you do`, `list reports`, etc.)
now returns the full list of routed patterns. Closes the gap where a
non-technical user had no way to discover phrases like
"budget vs contract for project X" without reading code.

### Doc hygiene
- CLAUDE.md: stale "113 tests" / "131-test suite" → current numbers
  and a pointer to CHANGELOG for the precise count.
- ROADMAP.md: Phase 1 + Phase 2 checkboxes flipped to `[x]`, exit-test
  results recorded inline.
- README.md: test count updated, `ask "help"` added to daily-use list.

### Tests
- **246 total** (+1 today for the help route).



**Theme:** Stop building plumbing, start building the brain.

### Schema
- New `DocumentText` table: 1:1 sidecar to `Document`, stores extracted text
  + extraction_method + token_count.
- New `Proposal` table: polymorphic LLM-output table gated by human
  approval. Carries entity ref, field name, JSON value, confidence,
  source doc ids, prompt version, decision audit.
- Migration helper (`ensure_sqlite_schema`) now creates both tables on
  legacy SQLite files. Idempotent.
- SQLite foreign-key enforcement turned on (`PRAGMA foreign_keys=ON`
  per connection) — without it the new CASCADE FK was decorative.

### Drive content extraction (`[content]` optional deps)
- `extractors.py` — pure bytes→text functions per mime:
  PDF (PyMuPDF), DOCX (python-docx), XLSX (openpyxl),
  Google Docs (`text/plain` export), Google Sheets (`text/csv` export).
- `content_pipeline.py` — orchestrator with skip-mime, skip-size (10 MB cap),
  skip-trashed, failed-* error labels. Never raises.
- New CLI: **`project_db extract-content [--project UUID] [--overwrite] [--limit N]`**.
  Idempotent; periodic commits every 25 docs; handles Ctrl-C cleanly.
- Live smoke test: 3 Google Docs + 1 XLSX extracted with real text
  (~2000 tokens each).

### Drive sync reconciliation
- Full sync now soft-marks Documents that vanished from Drive since
  the last walk (was an insert-only sync before — orphans linger forever).
- Conservative guardrails: only acts on visited folders, skips if any
  listing failed, leaves legacy null-parent rows alone. Per
  STRATEGY.md "keep everything" — soft delete, never hard.

### Phase 2 reports (Tier-1, zero LLM)
- 5 new canned reports in `ai/views.py`:
  - `project_overview` — one-screen snapshot (tasks, docs, invoices, logs)
  - `docs_for_project` — every doc for a project ordered by folder
  - `tasks_without_dates` — surfaces the 11%-dated-tasks problem
  - `missing_documents` — projects with no contract-shaped doc
  - `budget_vs_contract` — regex `$amounts` vs Monday budget, flags >15% divergence
- Dispatcher in `ai/query.py` now extracts a project ref from natural
  language (UUID anywhere OR text after the word `project`).
- Per-project reports return helpful `{"error": ...}` dicts when no
  project ref is parseable.

### Bugs caught by live smoke testing
- `_ser(ProjectStatus.ACTIVE)` returned `"ProjectStatus.ACTIVE"` (wrong)
  because enum check ran *after* `isinstance(str)` — but the enum
  inherits from str. Enum check moved first. Regression test added.
- CASCADE delete didn't fire (covered above).

### Tests
- **245 total** (up from 151 yesterday). +94 across Phase 1 and Phase 2.
- All green.

### Commands available today
| Command | Phase | Status |
|---|---|---|
| `project_db init-db` | Setup | Works |
| `project_db sync monday` | v0.1 | Works |
| `project_db sync GOOGLE_DRIVE` | v0.2.5 | Works (OAuth) |
| `project_db gdrive-auth` | v0.2.5 | Works (one-time) |
| `project_db list-boards` | v0.1 | Works |
| `project_db inspect-board <id>` | v0.1 | Works |
| `project_db list-sources` | v0.1 | Works |
| `project_db list-external <type> <uuid>` | v0.1 | Works |
| `project_db ask "..."` | v0.1 + Phase 2 | 8 canned reports |
| **`project_db extract-content`** | **Phase 1** | **Works (Drive→DocumentText)** |

### `ask` patterns that work today
| Phrase | Routes to |
|---|---|
| "active projects" / "open projects" | `active_projects` |
| "pipeline" / "deal value" | `deal_pipeline_value` |
| "ar aging" / "outstanding invoices" | `ar_aging` |
| "overview of project X" | `project_overview` |
| "docs for project X" / "files for project X" | `docs_for_project` |
| "tasks without dates" [`for project X`] | `tasks_without_dates` |
| "which projects are missing documents" | `missing_documents` |
| "budget vs contract for project X" | `budget_vs_contract` |

---

## 2026-05-14 — Google Drive live + strategic refocus

**Theme:** Drive sync working at scale; STRATEGY.md written; ROADMAP.md
established; +20 tests; cleanup.

### Drive connector live
- 750 documents synced with full metadata (folder_path, modified_time,
  size, md5, owner, etc.).
- 300 of 750 linked to canonical Projects via civic-number + name match.
- Recursive walk (depth-20 cap) replaced the old 3-level walk that
  silently dropped deep files.
- Delta sync via `changes.list` cursor stored in synthetic ExternalId row.
- OAuth Desktop credential flow (`gdrive-auth`) for personal/non-Workspace
  Google accounts. Auto-detects service-account vs OAuth Desktop from
  the JSON file.
- Folder→Project matching: civic number first (`923 Rockland` beats
  generic `Rockland`), then substring fallback.

### Infra
- Two `.sqlite` files consolidated into one (absolute path in `.env`).
- `Document` model expanded with 10 new columns
  (created_at_source, modified_at_source, size_bytes, md5_checksum,
   drive_id, parent_folder_id, folder_path, owner_email, is_trashed,
   source_meta_json).

### Strategy
- **STRATEGY.md** written — the canonical decision manifesto.
  Reframes ALTA from "sync tool" (commodity) to "LLM operations brain"
  (genuinely novel). 10 operating principles distilled.
- **ROADMAP.md** written — Phase 0 (done) through Phase 5 (adoption).
- CLAUDE.md updated with the strategic direction so future sessions
  can't drift.

### Tests
- 131 total (up from 111). Civic-number matching, RFC3339 parsing,
  Drive document field population, recursion depth, migration helper.

### Bugs fixed
- `gdrive-auth` was reading `GOOGLE_CREDENTIALS_PATH` (settings.py) but
  `.env` was using `GDRIVE_SA_KEY_PATH` — read switched to the env var
  directly.
- `python-dotenv` wasn't loading in `cmd_gdrive_auth` because
  `from project_db.config import settings` had been removed; restored
  via module-level `from project_db import config as _config`.
- `getStartPageToken` rejected `includeItemsFromAllDrives` (only valid
  on `changes.list`); param removed.

---

## 2026-05-13 — Monday push/pull/fuzzy/optimizer/mirror-columns

**Theme:** Monday became fully operational. Tests, fuzzy matching,
column caching, mirror columns, and the inspect tool all landed.

### Monday
- `change_multiple_column_values` write-back works end-to-end —
  `sync_back` parses board_id from the ExternalId URL so it doesn't
  re-query Monday for it.
- Mirror-column overlay: pulls status/timeline from linked portfolio
  items (so tasks proxying portfolio rows display the right value).
- Column metadata cached per `MondayClient` instance (1 fetch / board
  / run instead of N).
- `inspect-board` CLI shows columns + heuristic field assignments +
  sample items.
- `add-item` works for creating Monday items from the canonical side.
- Project optimizer analysis script added.

### Identity
- `FuzzyFieldMatcher` for approximate dedup
  (email-normalized, name-fuzzy, address-fuzzy).

### Cleanup
- Stale files culled. Compiled `.pyc` and SQLite removed from tracking.
- Test suite expanded to ~110 tests.

### Bug fixes
- Removed invalid `updated_after` argument from Monday `items_page`
  query (Monday API-Version 2026-07 dropped it).
- Corrected several GraphQL mutation signatures discovered against
  the live API.

---

## 2026-05-12 — Monday connector real implementation + QB skeleton

**Theme:** Monday went from architectural sketch to real working
connector. QuickBooks connector scaffolded.

### Monday
- Real column extraction with `ColumnExtractor`: maps Monday column
  types (status, timeline, numbers, people, date, ...) to canonical
  fields via title-based heuristics.
- ProjectBoard classification: distinguishes CRM boards from
  property/job boards.
- Per-board sync workflow: boards become Projects, items become Tasks.
- `.env` loading via `python-dotenv` so credentials don't leak into
  version control.

### QuickBooks
- Client + connector code complete (REST + Query Language).
- Mapping for customers, invoices, estimates.
- Live test pending real credentials.

### Docs
- README rewritten with full project scope, current usage, roadmap.

---

## 2026-05-11 — Genesis

**Theme:** Repo created. Architecture sketched in Umple UML. Monday
API reference docs scraped for offline reading.

- Initial schema design: 13 canonical entities + ExternalId bridge.
- Umple UML model compiled to Java; 0 compile errors but logical work
  in progress.
- Monday.com API reference fully documented (42 pages of GraphQL
  schema + examples cached locally).
- First-pass connector skeleton.

---

## How to read this log

- **Newest on top** so the top entry is "today's product state."
- **Each entry has a theme** so you can scan to find when something was
  built without reading every commit message.
- **Commands available today** in the latest entry is the live cheat
  sheet — if a command isn't listed there, assume it's planned but
  not built.
