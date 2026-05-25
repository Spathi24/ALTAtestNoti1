# ALTA Roadmap

**Date:** 2026-05-14
**Authority:** [`STRATEGY.md`](STRATEGY.md). This roadmap is the execution
plan for the strategy; if they disagree, STRATEGY.md wins.

**Reading guide:** Phases are sequential. Don't start phase N+1 work until
phase N has produced visible value to a PM. Items inside a phase can be
parallelized.

**Current operating plan (2026-05-22):** the foundation is sound enough to
resume product work, but only if the next changes reduce PM friction. The
next sequence is:

1. Clean the trust surface: treat Google/Amazon as deals, not construction
   projects, and keep those records out of `doctor` project warnings unless
   they get real Drive project folders.
2. Make proposal generation less brittle: keep manual proposal commands, but
   add better pre-filtering and context selection so the model spends tokens
   only on tasks/documents that can plausibly produce useful future-facing
   proposals.
3. Add `project_db daily <project>`: one command for sync, extraction, report
   summary, proposal generation, and review pointers.
4. Build scope reconciliation, then anomaly detection. Timeline gaps remain
   first, but "no proposal" is a valid model answer; the product must surface
   "still dateless after review" separately from "LLM found a date."
5. Pull the minimal local UI forward once the daily command has a stable
   shape. The UI is not decorative; it is necessary because the CLI is already
   too hard to navigate for daily use.

**Shipped 2026-05-22 (usability slice):** `proposals accept` / `reject` with
no id now print the pending queue so the user can choose; `accept all` /
`reject all --yes` decide every pending proposal at once. `ask` routes any
question that matches no canned report to a fast Haiku model that reads a
whole-database snapshot (`report_database_overview`) — canned reports stay
instant and deterministic, and the deep (Sonnet) model stays reserved for
`propose`.

Small fixes should be accepted only when they serve one of those outcomes:
trustworthy data, fewer decisions for the user, better proposal quality, or
clearer review/adoption. Avoid polishing connector breadth, schema elegance,
or speculative AI features until one PM can use the Monday+Drive loop daily.

**Near-term milestones:**

- **M1: Clean doctor output.** `doctor` should end with no scary warnings for
  expected CRM-only deals. If Google/Amazon are in the `deal` table with their
  values/stages/source IDs, they should not appear as failed project records.
  First implementation slice is done: reports and `doctor` now recognize empty
  `Project - <deal>` placeholders as CRM deals when matching `Deal` rows exist.
- **M2: Targeted timeline runs.** Proposal generation should rank dateless
  tasks by project priority and evidence likelihood, then explain unresolved
  blanks instead of silently leaving them invisible.
- **M3: Daily command.** One command should tell the user: what changed, what
  needs review, what remains unresolved, and which command or UI screen opens
  the detail. First implementation slice is done: `project_db daily <project>`
  gives a read-only review by default and only calls the LLM when
  `--propose-timelines` is passed.
- **M4: Scope reconciliation.** Once timeline review is understandable, add
  contract/SOW scope comparison against Monday tasks.
- **M5: Minimal UI.** Build a local web review surface over existing reports
  and proposal actions; no new business logic should live in the UI.

---

## Phase 0 — Foundation (DONE, do not redo)

The plumbing is built. Do not redesign it. Document it if confused; do not
rewrite.

- [x] Canonical schema: 13 entities + ExternalId bridge
- [x] Identity resolver: exact + fuzzy match, NoMatcher default
- [x] Monday connector: full board/item read, column extraction, write-back via `sync_back`
- [x] Monday mirror-column overlay: pulls task status/timeline from linked portfolio items
- [x] Google Drive connector: 750 documents, full metadata, recursive walk to depth 20
- [x] Initial folder-to-project linking existed here, but the substring/civic
      matcher was later replaced by deterministic Drive-folder ancestry in
      Phase 2.5.
- [x] Drive delta sync via `changes.list` cursor
- [x] OAuth Desktop auth flow (`project_db gdrive-auth`)
- [x] One consolidated SQLite location, absolute path in `.env`
- [x] Test suite (390 passing as of 2026-05-22)

---

## Phase 1 — The Brain Foundation (DONE 2026-05-15)

Goal: every Drive document with parseable content has indexed text tied to
its canonical Project, and there is a place to store LLM proposals without
mutating canonical fields.

- [x] `DocumentText` SQLAlchemy model: `document_id` (FK), `extracted_text` (TEXT), `extraction_method`, `extracted_at`, `token_count`
- [x] `ensure_sqlite_schema` migration for both `DocumentText` and `Proposal`
- [x] `pymupdf`, `python-docx`, `openpyxl` added under `[content]` optional deps
- [x] `gdrive/extractors.py` with one function per mime type (PDF / DOCX / XLSX / Google Docs / Google Sheets); lazy imports so the codebase loads without the libs
- [x] Wired extractors into `GDriveConnector` (`extract_content` flag, default off — CLI is primary entry). 10 MB cap. Trashed docs skipped. Unsupported mime auto-`skipped-mime`.
- [x] `project_db extract-content [--project] [--overwrite] [--limit]` CLI; idempotent; periodic commits; Ctrl-C handling
- [x] `Proposal` SQLAlchemy model with all fields + ProposalStatus enum
- [x] **Bonus:** Drive sync reconciliation soft-marks vanished files (was insert-only before)
- [x] **Bonus:** SQLite FK enforcement turned on (`PRAGMA foreign_keys=ON`); CASCADE now actually works
- [x] Tests: 60+ across the three new files (`test_phase1_models`, `test_gdrive_extractors`, partial coverage in `test_gdrive_enhancements`)

**Phase 1 exit test — PASSED:** ran `project_db extract-content` over the
full 750-doc tree. **457 documents** with non-empty text, every one with
a token_count. Spot-check on real contract text (Petro.docx, Tony Estimate.pdf,
Alta Construction Group - contract.pdf) confirms readable output.

---

## Phase 2 — Tier-1 AI (deterministic reports, no LLM) — DONE 2026-05-15

Goal: PMs have at least three queries they hit daily that they couldn't
run before, with zero AI involved. This builds trust before introducing
probabilistic outputs.

- [x] `project_overview` — one-screen snapshot (tasks, docs, invoices, logs, client, external IDs)
- [x] `docs_for_project` — every Document with folder_path, size, modified date, ordered by folder
- [x] `tasks_without_dates [--project]` — Monday tasks missing start/end/due dates
- [x] `missing_documents` — projects with zero contract-shaped docs (PDF / Google Doc / DOCX)
- [x] `budget_vs_contract` — regex `$amounts` from extracted contract text vs Monday budget; flags >15% divergence. Regex swaps for LLM extraction in Phase 3 (same output shape).
- [x] All wired through `project_db ask "..."` with natural-language project-ref extraction (UUID or "project <name>")
- [x] `ask "help"` lists every routed pattern for non-technical users
- [x] 46 new tests; reports importable from `project_db.ai.views` for Phase-3 LLM tool layer

**Phase 2 exit test — PASSED:** all 5 reports verified against the live DB.
- `tasks_without_dates` → 137 dateless tasks surfaced
- `missing_documents` → 1 PROPOSED project flagged
- `project_overview` → real Project (Rockland: 1 task, 18 docs, 0 invoices)
- `docs_for_project` → 18 docs for Rockland with folder_path context
- `budget_vs_contract` → 5768-5770 St Laurent contracts produced real $ extractions; the report honestly returns `divergence_pct=null` when Monday budget is unset rather than fabricating

**Current live snapshot (2026-05-22):** 83 dateless tasks remain across
923 Rockland, 1455 Rue St. Mathieu, and 5768 St-Laurent. `missing_documents`
now flags only the Amazon deal row, which is a deal/project boundary problem
rather than proof that a real construction project lacks documents.

---

## Phase 2.5 — Foundation Correctness (2026-05-21)

**Why this exists.** A direct DB audit found the canonical data was wrong at
the root: 6 "projects" for ~3 real ones (923 Rockland split in two; demo
"deal" rows minted as projects), 60% of Drive documents linked to nothing,
and mislinks (927 Rockland's files attached to a phantom "Rockland" project).
Root cause: project identity came from "whatever Monday created", and Drive
documents matched into it via a **substring** test — `"Rockland"` matched
`"927 Rockland"`. Every report and every LLM proposal was reasoning over a
broken skeleton. Building more AI on that is the "running in circles" loop.

**Governing principle.** *This phase does not add intelligence. It only makes
identity, provenance, and linkage deterministic. Any uncertainty must surface
in `doctor`, not be guessed in code.*

- [x] Drive folder tree (`01. PROJECTS/{ACTIVE,INACTIVE,LEADS}/<name>/`) becomes
      the project registry — each project folder IS one canonical Project,
      created keyed by folder id (two folders never merge).
- [x] Documents link to projects by **physical folder ancestry** — deterministic.
      `_match_project_by_name` substring matcher **deleted**.
- [x] `Document.category` — every Drive file gets a home (project, or a
      company-knowledge category: company / real_estate / construction /
      intelligence).
- [x] `ProjectMatcher` (civic-number then exact-name, unique-hit-only, no
      fuzzy/substring) — used by Monday to match boards INTO Drive projects.
- [x] `_classify_board` fails closed: a board matching no allowlisted rule is
      skipped, never guessed into a Project.
- [x] `project_db doctor` — read-only trust instrument (provenance, doc/task
      counts, mislink/orphan/duplicate flags).
- [x] `project_db rebuild` — re-derive the canonical DB from the sources;
      preflight-checks connectors before wiping; preserves Document +
      DocumentText; exports Proposals to JSON first.
- [x] 387 tests green (substring/civic matching tests replaced with
      deterministic folder-taxonomy + ProjectMatcher tests).
- [x] **Exit test — PASSED (2026-05-21):** `project_db rebuild --yes` then
      `project_db doctor`. 21 projects = 19 real Drive folders + 2 Monday
      deal-derived rows that should be represented as Deals, not trusted as
      construction Projects.
      **554 / 554 project documents linked, 0 mislinks** (was 300).
      All 750 documents categorized: projects 554 / real_estate 84 /
      intelligence 47 / company 43 / construction 14 / 8 with no folder
      path. "923 Rockland (3rd Floor unit)" and "927 Rockland (Ground
      Floor unit)" are correctly separate projects; the phantom "Rockland"
      is gone (its Monday portfolio board is skipped by fail-closed
      classification).

**Remaining cleanup:** `doctor` now distinguishes empty CRM deal placeholders
from real projects missing provenance. The remaining live data hygiene warning
is 8 Drive documents with no project/category, usually files with no
`folder_path`.

---

## Phase 3 — Tier-2 AI (LLM proposals)

Goal: the LLM reads a project's contract text plus its current Monday
state and produces structured suggestions that land in the `Proposal`
table. Nothing is auto-written to Monday.

**Refined plan (2026-05-15):** target architecture is a local model
(Qwen / DeepSeek / MiniMax tier) on dedicated hardware (Mac mini),
with optional Anthropic provider for prototyping while the box is
being set up.  Build provider-agnostic infrastructure FIRST.

**Session 3a — Provider abstraction + context assembler (DONE 2026-05-16)**
- [x] `LLMProvider` interface in `ai/providers/base.py`.  OpenAI Chat
      Completions shape canonical; `complete_json` retry helper on base.
- [x] `MockLLMProvider` (deterministic, for tests)
- [x] `AnthropicProvider` (real, for prototyping pre-hardware)
- [x] `OpenAICompatibleProvider` (Ollama/vLLM/llama.cpp — zero new code
      when local hardware arrives)
- [x] `get_default_provider()` env-var resolver
- [x] `assemble_project_context(session, project_id)` — full join,
      configurable token budget, evicts doc bodies oldest-first
- [x] 41 new tests
- [x] Monday `activity_logs(from, to)` delta-sync — shipped and available
      through `project_db sync monday --delta`

**Session 3b part 1 — Proposal engine (DONE 2026-05-17)**
- [x] `generate_timeline_proposals()` — context → LLM → validated `Proposal` rows
- [x] Timeline-extraction prompt (instruction-at-tail; LLM references tasks by integer index, never UUID)
- [x] Per-item validation: index range, date parse, end≥start, confidence clamp; bad items recorded not raised
- [x] Auto-supersede prior PENDING proposals for the same `(entity_type, entity_id, field_name)`
- [x] `list_proposals()` / `get_proposal_detail()` read side
- [x] CLI: `propose timelines`, `proposals list`, `proposals show`
- [x] 32 tests on MockLLMProvider; live-verified on 923 Rockland
- [x] ~~Monday delta sync~~ — already shipped in Session 3a (`sync monday --delta`)

**Session 3b part 2 — Approval actions + remaining prompts**
- [x] CLI: `proposals reject <id> [--reason] [--by]` — pure DB, PENDING-only guard (DONE 2026-05-18)
- [x] CLI: `proposals accept <id> [--dry-run] [--by]` — Monday write-back via `sync_back`; write-first/flip-second ordering; mirrors dates onto canonical Task (DONE 2026-05-18)
- [ ] Proposal targeting pass — pre-select the highest-value dateless tasks,
      attach only likely schedule/source documents, and separately report
      tasks that remain dateless because the model found no future-facing
      evidence. Do not pressure the LLM to invent dates or accept dates before
      today just to fill blanks.
- [x] Prompt: scope reconciliation — `generate_scope_proposals` ships
      `propose scope <project>`; flags documented scope items with no
      matching Monday task. Advisory-only (`accept` refuses scope_gap;
      Monday create-task write-back is future work). 2026-05-22.
- [ ] Prompt: anomaly detection — `{anomaly_type, description, severity}`
- [ ] CLI: `propose scope / anomalies / all <project>`

**Before the loop is *proven* (not just built):**
- [x] One real `accept` against the live Monday workspace (DONE 2026-05-21
      — proposal `8a39b20c` accepted by nsaro; `project_timeline` on
      Monday item 11941695903 went null → 2026-05-10, confirmed in
      Monday's activity log)
- [x] Provider wired to a real model (DONE 2026-05-21 — Anthropic API,
      `claude-haiku-4-5` for cost-efficient testing; `ANTHROPIC_MODEL`
      env var added; live-verified on 1455 Saint Mathieu + 923 Rockland)
- [ ] Full prompt-quality validation pass — first real-model runs look
      sound (evidence-cited, honest confidence), but rejection-rate
      tuning over many projects is still owed

**Session 3b note:** "no proposal" is a valid model output when the documents
do not support a future date. The product gap is not that the model refuses to
guess; it is that the user needs a clear review list of unresolved dateless
tasks, source documents considered, and why no proposal was produced.

**Session 3c — Fine-tuning corpus + personality + local backend**
- [ ] `project_db export-corpus` — DocumentText + Monday data dumped as
      JSONL suitable for continued pretraining / fine-tuning
- [ ] `prompts/personality.yaml` — tone/style variables injected into the
      system prompt at runtime (formal / casual / verbose etc.)
- [ ] `LocalProvider` (OpenAI-compat HTTP) — plugs in when hardware ready;
      single config-line swap to flip from Anthropic → local

**Resolved design decisions:**
1. Provider API shape: OpenAI Chat Completions style internally, with Anthropic
   and OpenAI-compatible adapters.
2. Structured-output strategy: ask-and-parse JSON with validation/retry helpers.
3. Real-provider bridge: Anthropic is usable while local hardware is pending;
   OpenAI-compatible local backends can swap in by config.

**Remaining design decision:** fine-tuning/export corpus scope. Recommended:
contracts + Monday task history + folder structures + civic mappings, because
the model needs ALTA's operational language and project identity conventions,
not just contract prose.

**Phase 3 exit test:** running `project_db propose all <project_id>` on
the 923 Rockland project produces at least one timeline proposal and one
scope flag that survives human review.

---

## Phase 4 — Approval Workflow

Goal: there is a clean human-in-the-loop pipeline from "LLM proposed X" to
"X is now reflected in Monday." This is what turns the LLM from a toy into
operational tooling.

- [x] CLI: `project_db proposals list [--status pending]` — table view of open proposals
- [x] CLI: `project_db proposals show <proposal_id>` — full proposal detail incl. source document excerpts
- [x] CLI: `project_db proposals accept <proposal_id>` — flips status to accepted, triggers Monday write-back via existing `sync_back`
- [x] CLI: `project_db proposals reject <proposal_id> [--reason "..."]`
- [x] Auto-supersede: if a new proposal lands for the same `(entity_id, field_name)`, mark the old pending one as `superseded`
- [x] Audit data stored on `Proposal` (`decided_at`, `decided_by`, `rejection_reason`); separate `ProposalDecision` table is unnecessary until we need multi-decision history.
- [x] Tests: accept-flow writes back to Monday (mocked client), reject-flow doesn't, superseded handling, idempotency on double-accept
- [x] CLI: `proposals accept` / `reject` with no id print the pending queue;
      `accept all` / `reject all --yes` decide every pending proposal at once
- [ ] Add project/status filters to proposal listing if the CLI review surface remains noisy.

**Phase 4 exit test — PASSED 2026-05-21:** accepted a real timeline proposal
on a real project and verified Monday received the proposed dates. The ongoing
work is usability and quality, not the existence of the approval loop.

---

## Phase 5 — Adoption

Goal: get the system into a PM's hands and verify it changes how they
work. This is where success or failure is determined.

- [ ] Pick one PM, one project. Run the full pipeline daily for two weeks.
- [x] `project_db daily <project_id>` — first slice: read-only deterministic
      review by default, optional `--propose-timelines` to create pending
      timeline proposals. It distinguishes:
      - proposed changes awaiting review
      - dateless tasks where no supported future date was found
      - project/document trust warnings from `doctor`
- [ ] Add optional sync/extract steps once the read-only review shape proves
      useful. Keep them explicit or clearly labeled because they hit live APIs
      and mutate the local DB.
- [ ] Optional Slack / email digest of new proposals (only if PM asks for it)
- [ ] Iterate on prompt quality based on actual rejection rate
- [ ] Decision point at 4-6 weeks: is it being used? Continue if yes. Stop or pivot if no.

**Phase 5 exit test:** the PM is opening ALTA before opening Monday at
least three times a week. If not, see STRATEGY.md §7.

---

## Phase 6 — Minimal UI (read-only window)

**Status (2026-05-25):** Phase A of the five-phase build landed.
`project_db serve` boots a localhost-only FastAPI app rendering a live
dashboard (counts + pending-proposal strip).  Test suite is 453 green
(+31 from this phase) including permission-boundary tests that pin the
forbidden surface.  Phases B-E still ahead: project/document pages,
proposal queue + detail, accept/reject through the existing functions,
then DB inspector + raw-JSON panels.



Goal: a thin, *visible* interface so non-CLI stakeholders — the PM, and
the people they report to — can SEE what ALTA produces without opening
a terminal. This is a demo / visibility layer, not a new product
surface.

**Strategy guardrails (per STRATEGY.md).** This does NOT add a new backend
paradigm, touch the schema, or add connectors. It is a read-mostly view over
reports and proposals that already exist and are already tested. The UI may be
pulled forward before Phase 5 completes because discoverability is now a real
adoption blocker: even the developer has trouble remembering the CLI surface.
Operating principle #8 ("no new tech") is respected: a single thin web
framework, nothing more.

- [ ] Thin local web app (FastAPI or Flask) serving the existing
      `ai.views` reports — `project_overview`, `docs_for_project`,
      `tasks_without_dates` — as HTML pages. No new business logic; the
      routes call functions that already exist.
- [ ] Proposal review screen: list PENDING proposals, open one with its
      reasoning + source-document evidence, and Accept / Reject buttons
      that call the SAME `accept_proposal` / `reject_proposal` the CLI
      uses (so the human-in-the-loop guarantees are identical).
- [ ] `project_db serve` — runs on localhost; no hosting, no auth, no
      multi-user. Single-machine, single-user, exactly like the CLI.
- [ ] Can be pulled forward if superiors need a demo before Phase 5
      finishes — it has no dependency on Phase 5's outcome.

**Phase 6 exit test:** a non-technical stakeholder opens the local URL,
reads a project overview, and accepts or rejects a proposal without
ever touching a terminal.

---

## Future architecture notes (post-Phase-5)

These are user-articulated directions worth preserving so future
sessions don't re-derive them.  Not committed work; not next; not now.

**Dual-model architecture.**  Two configured providers running in
parallel:

  - **Fast** (small local model / Haiku tier): conversational
    layer for `ask`, query routing, simple Q&A.
  - **Deep** (big local model / Opus tier): proposal generation,
    contract-vs-Monday reconciliation, anomaly detection.

They share state through the canonical DB (`ProjectContext`,
`Proposal` table), not through token windows.  Already enabled by
the `LLMProvider` interface -- just instantiate two providers and
config-switch which one a given call uses.  Likely env-var pattern:
`LLM_PROVIDER_FAST` + `LLM_PROVIDER_DEEP`.

**Company-wide Drive content (beyond per-project folders).**  Drive
holds far more than the project folders.  There are subfolders for
company-level concerns — HR, document templates, insurance
certificates, vendor master files, estimating standards, safety docs,
and more.  Today the pipeline only extracts and reasons over documents
that link to a Project; that non-project corpus is untouched.  It is a
real future input for: (a) a company-knowledge `ask` mode — "what is
our standard payment-terms clause?", "which insurance certificate
expires next?"; (b) template-vs-actual comparison — does a project's
contract follow the company's standard contract template; (c) the
fine-tuning corpus.  It needs its own lightweight classifier
(folder → category) rather than the civic-number project linker, and a
home in the schema that is NOT the `Project` FK.  Not next; noted so a
future session does not re-derive it.

**RAG layer.**  Vector embeddings over `DocumentText` for
similarity-based retrieval.  Complements `assemble_project_context`
rather than replacing it: the assembler grabs structured canonical
spine (tasks / invoices / dates), RAG grabs fuzzy text chunks
("the deadline clause" in a 100-page contract).  Both feed the
same prompt.  Will need `pgvector` (= Postgres migration) or
`sqlite-vec` extension first.

**Domain-pretrained / fine-tuned local model.**  Continued
pretraining on the company corpus (DocumentText + Monday history
+ folder structures + civic mappings) so the model speaks our
internal language out of the box.  The exporter is Session 3c;
the actual fine-tuning happens on the dedicated hardware
(Mac mini / dedicated GPU box) and is not a code task in this
repo.

---

## Deferred (per STRATEGY.md — explicitly NOT next)

These are real items but they are plumbing-not-brain. Do not pick them up
until Phase 5 is in a known-good state.

- [ ] CompanyCam connector (photos)
- [ ] QuickBooks live test + invoice sync
- [ ] Webhook receivers (replaces polling on Monday) — note: `create_webhook` is a scriptable mutation in the live Monday API; the actual blocker is hosting a public HTTPS endpoint
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
