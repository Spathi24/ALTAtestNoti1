# ALTA Roadmap

**Date:** 2026-05-14
**Authority:** [`STRATEGY.md`](STRATEGY.md). This roadmap is the execution
plan for the strategy; if they disagree, STRATEGY.md wins.

**Reading guide:** Phases are sequential. Don't start phase N+1 work until
phase N has produced visible value to a PM. Items inside a phase can be
parallelized.

---

## Phase 0 — Foundation (DONE, do not redo)

The plumbing is built. Do not redesign it. Document it if confused; do not
rewrite.

- [x] Canonical schema: 13 entities + ExternalId bridge
- [x] Identity resolver: exact + fuzzy match, NoMatcher default
- [x] Monday connector: full board/item read, column extraction, write-back via `sync_back`
- [x] Monday mirror-column overlay: pulls task status/timeline from linked portfolio items
- [x] Google Drive connector: 750 documents, full metadata, recursive walk to depth 20
- [x] Folder→Project linking via civic-number + substring match (300 of 750 docs linked)
- [x] Drive delta sync via `changes.list` cursor
- [x] OAuth Desktop auth flow (`project_db gdrive-auth`)
- [x] One consolidated SQLite location, absolute path in `.env`
- [x] 131-test suite

---

## Phase 1 — The Brain Foundation (NEXT, single focus)

Goal: every Drive document with parseable content has indexed text tied to
its canonical Project, and there is a place to store LLM proposals without
mutating canonical fields.

- [ ] Create `DocumentText` SQLAlchemy model: `document_id` (FK), `extracted_text` (TEXT), `extraction_method` (VARCHAR — 'pdf-pymupdf', 'gdoc-export', 'docx-python', 'xlsx-openpyxl', 'skipped-size', 'skipped-mime'), `extracted_at` (DATETIME), `token_count` (INT, nullable)
- [ ] Add `ensure_sqlite_schema` migration for `DocumentText`
- [ ] Add `pymupdf`, `python-docx`, `openpyxl` to `pyproject.toml` under a new `[content]` optional dependency group
- [ ] Implement `gdrive/extractors.py` with one function per mime type, returning `(text, method)` or `(None, 'skipped-*')`
- [ ] Wire extractors into `GDriveConnector` — content extraction runs after metadata upsert; cap at 10 MB per file; skip HEIC, DWG, ZIP, audio
- [ ] Add `project_db extract-content [--project <id>] [--missing-only]` CLI command for re-running extraction without a full Drive sync
- [ ] Create `Proposal` SQLAlchemy model: `entity_type` (VARCHAR), `entity_id` (UUID), `field_name` (VARCHAR), `proposed_value` (TEXT — JSON-encoded), `confidence` (FLOAT), `source_doc_ids` (TEXT — JSON list of Document UUIDs), `prompt_version` (VARCHAR), `status` (ENUM: pending/accepted/rejected/superseded), `created_at`, `decided_at`, `decided_by`
- [ ] Add tests: extractor coverage per mime type, Proposal model CRUD, DocumentText constraints

**Phase 1 exit test:** running `project_db extract-content` populates
`DocumentText` rows for at least 200 documents from the live Drive sync,
with non-empty text and a `token_count` set. Manual spot-check confirms
the text looks readable.

---

## Phase 2 — Tier-1 AI (deterministic reports, no LLM)

Goal: PMs have at least three queries they hit daily that they couldn't
run before, with zero AI involved. This builds trust before introducing
probabilistic outputs.

- [ ] Report: `project_overview <project_id>` — one screen showing tasks, recent documents, invoices, daily logs, linked clients/vendors
- [ ] Report: `docs_for_project <project_id>` — every Document with folder_path, size, modified date, ordered by folder
- [ ] Report: `tasks_without_dates [--project <id>]` — Monday tasks missing start/end/due dates, with project + folder_path context
- [ ] Report: `missing_documents` — projects with zero documents of mime type 'application/pdf' or 'application/vnd.google-apps.document' (likely missing a contract)
- [ ] Report: `budget_vs_contract <project_id>` — extract numeric values from contract text, compare to Monday budget column, flag divergences > 15%
- [ ] Wire all reports through existing `project_db ask "..."` so the canned mode picks them up
- [ ] Add tests for each report's SQL against a populated fixture DB

**Phase 2 exit test:** a non-technical person can run any of the five
reports above against the live DB and get a useful, correctly-formatted
result.

---

## Phase 3 — Tier-2 AI (LLM proposals)

Goal: the LLM reads a project's contract text plus its current Monday
state and produces structured suggestions that land in the `Proposal`
table. Nothing is auto-written to Monday.

- [ ] Add Anthropic client wrapper in `ai/llm_client.py` — model selection via env var, prompt-caching headers set, token tracking
- [ ] Build a "project context" SQL view: project + tasks + extracted document text + invoices + clients, capped at ~150k tokens
- [ ] Prompt: timeline extraction — input is project context, output is a JSON list of `{task_canonical_id, proposed_start, proposed_end, confidence, source_doc_id, reasoning}`
- [ ] Prompt: scope reconciliation — input is contract text + Monday task list, output is JSON list of `{scope_item, in_monday: bool, suggested_task_title, confidence}`
- [ ] Prompt: anomaly detection — input is full project context, output is JSON list of `{anomaly_type, description, severity}` (e.g., "Status=Done but no invoice sent", "30% budget remaining but 80% complete")
- [ ] CLI: `project_db propose timelines <project_id>` — runs the timeline prompt, writes proposals
- [ ] CLI: `project_db propose scope <project_id>` — runs scope reconciliation
- [ ] CLI: `project_db propose all <project_id>` — runs all three
- [ ] Add tests with mocked LLM responses for each prompt; verify Proposal rows are well-formed

**Phase 3 exit test:** running `project_db propose all <project_id>` on
the 923 Rockland project produces at least one timeline proposal and one
scope flag that survives human review.

---

## Phase 4 — Approval Workflow

Goal: there is a clean human-in-the-loop pipeline from "LLM proposed X" to
"X is now reflected in Monday." This is what turns the LLM from a toy into
operational tooling.

- [ ] CLI: `project_db proposals list [--status pending] [--project <id>]` — table view of open proposals
- [ ] CLI: `project_db proposals show <proposal_id>` — full proposal detail incl. source document excerpts
- [ ] CLI: `project_db proposals accept <proposal_id>` — flips status to accepted, triggers Monday write-back via existing `sync_back`
- [ ] CLI: `project_db proposals reject <proposal_id> [--reason "..."]`
- [ ] Auto-supersede: if a new proposal lands for the same `(entity_id, field_name)`, mark the old pending one as `superseded`
- [ ] Audit log: every accept/reject writes to a `ProposalDecision` table (or extend Proposal with `decided_*` columns — already in schema above)
- [ ] Add tests: accept-flow writes back to Monday (mocked client), reject-flow doesn't, superseded handling, idempotency on double-accept

**Phase 4 exit test:** accept a real timeline proposal on a real project,
verify the Monday item gets the proposed dates without any manual
intervention.

---

## Phase 5 — Adoption

Goal: get the system into a PM's hands and verify it changes how they
work. This is where success or failure is determined.

- [ ] Pick one PM, one project. Run the full pipeline daily for two weeks.
- [ ] `project_db daily <project_id>` — single command that runs sync + content extraction + proposals + prints any new flags
- [ ] Optional Slack / email digest of new proposals (only if PM asks for it)
- [ ] Iterate on prompt quality based on actual rejection rate
- [ ] Decision point at 4-6 weeks: is it being used? Continue if yes. Stop or pivot if no.

**Phase 5 exit test:** the PM is opening ALTA before opening Monday at
least three times a week. If not, see STRATEGY.md §7.

---

## Deferred (per STRATEGY.md — explicitly NOT next)

These are real items but they are plumbing-not-brain. Do not pick them up
until Phase 5 is in a known-good state.

- [ ] CompanyCam connector (photos)
- [ ] QuickBooks live test + invoice sync
- [ ] Webhook receivers (replaces polling on Monday)
- [ ] Postgres + Alembic migrations
- [ ] `pgvector` for semantic document search
- [ ] Text-to-SQL natural language layer
- [ ] Multi-tenant / multi-org support
- [ ] Resource / crew scheduling

---

## How to use this roadmap

When tempted to start work on something, check it against three rules:

1. Is it in the current phase? If no, postpone.
2. Does it directly serve the Phase exit test? If no, drop scope.
3. Does it contradict an operating principle in STRATEGY.md? If yes, stop.

The roadmap is a contract with the strategy, not a wishlist.
