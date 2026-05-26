# ALTA Roadmap

**Date:** 2026-05-14 (revised 2026-05-26)
**Authority:** [`STRATEGY.md`](STRATEGY.md). This roadmap is the execution
plan for the strategy; if they disagree, STRATEGY.md wins.

**Reading guide:** Phases are sequential. Don't start phase N+1 work until
phase N has produced visible value to a PM. Items inside a phase can be
parallelized.

---

## Current operating plan (2026-05-26)

M5 (local web UI) **closed**.  The full read+decision+action loop is in
the browser; the CLI surface stays intact.  578 tests passing.

**Shipped 2026-05-26 (Roadmap integration Layers 1+2):**
`RoadmapTask` table, `import-roadmap` CLI, `RoadmapActor` enum,
`classify-roadmap` Sonnet pass, and the actual prompt injection in
both proposal bots (`scope-v2-roadmap` and `timeline-v3-roadmap`).
**617 tests.**  Layer 3 (deterministic gap-finder) was DELIBERATELY
SKIPPED -- see the "Layer 3 skip rationale" subsection in the M5
retrospective.  Live validation on 5768 St-Laurent produced 6
contract-sourced + 4 roadmap-sourced gaps, with zero architect-noise
flags.

**Shipped 2026-05-26 (Quoted-excerpt reasoning):** Both proposal
prompts now demand direct QUOTED EXCERPTS for contract evidence and
explicit citations for schedule-sequence / roadmap evidence.  Lazy
reasoning REJECTED.  Live-verified on 5768 St-Laurent: every
contract-sourced gap now carries a literal contract quote with the
document name.  Versions: `timeline-v4-quoted`, `scope-v3-quoted`.
625 tests.

**Next sequence, in priority order:**

1. ~~**Tighten proposal reasoning prompts with quoted excerpts.**~~
   DONE.
2. **RAG over `DocumentText`.**  The biggest capability unlock.  See
   the [RAG plan](#rag-over-documenttext-detailed-plan) section below
   for the full breakdown.  ~4 sessions.  Both the askbot AND the
   proposal bots gain from this -- it's a context-quality upgrade for
   the whole AI layer.
3. **Structured financial extraction for invoices / contracts /
   change orders.**  See the
   [Financial extraction strategy](#financial-extraction-strategy)
   section below.  ~3-4 sessions.  Per the user's 2026-05-26 ask:
   "we need some kind of interaction or global awareness of financial
   continuity."  RAG (#2) and this (#3) are independent; do them in
   either order.
4. **Live QB integration.**  Pending real credentials.  Once the QB
   connector runs, invoice / payment data lands in `Invoice` table
   structured -- stop scraping PDFs that QB already has structured.
   ~1 session once credentials exist.
5. **One real Monday accept through the UI.**  Need explicit user
   sign-off (per the 2026-05-21 CLI accept precedent).  The code path
   is end-to-end verified against mocks; a real Monday write is the
   only thing pending.

**Deferred but considered, in case they come up:**

- **Intent classification + per-question context selection.**  ChatGPT
  recommended this on 2026-05-26.  Not urgent today (DB snapshot at 21
  projects is fine in one shot); add when DB size starts hurting Haiku
  recall.  ~1 session when needed.  Adds an LLM call to classify
  before answering, ~doubles latency on free-form questions.
- **Answer modes on `/ask`** (`brief / deep / risks / actions`).  The
  new assertive prompt already produces those sections implicitly; a
  mode dropdown would just bias toward one.  ~30 min when wanted.
- **Tailwind redesign.**  When you have a target look (Linear / Notion
  / Stripe Dashboard style).  Vendored Pico is 83 KB; vendored Tailwind
  via the CDN-built `tailwindcss.css` would be similar.  Templates
  don't change; just the `<link>` and class names.  ~2-4 sessions.
- **Bulk accept UI.**  Deliberately omitted from M5.  See "M5
  retrospective" below for the rationale.

**Older sequence (2026-05-22), kept for context but mostly superseded:**

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

## Phase 6 / M5 — Local Web UI **(CLOSED 2026-05-26)**

**Final status:** Shipped in five slices over two days.  A PM can do
the full daily loop from the browser; the CLI surface stays intact and
authoritative.

| Slice | Date | What landed |
|---|---|---|
| **A** -- skeleton + dashboard | 2026-05-25 | `project_db serve`, FastAPI factory, Pico+HTMX, dashboard with live counts + pending-proposal strip |
| **B+C** -- read-only browsing | 2026-05-25 | `/projects`, `/projects/{id}` (5 panels), `/documents/{id}` (metadata + full extracted text), `/proposals` (filterable queue), `/proposals/{id}` (5-panel review), `/doctor` |
| **D** -- HTMX accept/reject | 2026-05-25 | `POST /proposals/{id}/dry-run /accept /reject` with two-click confirm, stale-state guard, four decision partials, write-first/flip-second ordering preserved |
| **D.1** -- action surfaces | 2026-05-25 | `POST /projects/{id}/propose/timelines /scope` (Sonnet, hx-confirm), `/ask` (canned + Haiku fallback), inline task date editing via `set_task_timeline`; combined Tasks table with `dateless` pill |
| **D.1 fixes** -- bugs + UX | 2026-05-26 | `complete_json` bumps `max_tokens` on truncation; scope cap 3000→5000; HTMX `hx-indicator` loading spinners; dashboard alignment; Cancel-spinner inheritance fix; `/ask` markdown rendering; askbot **assertive inferential prompt** |
| **E** -- closeout | 2026-05-26 | `/db` raw-row inspector, raw-JSON debug panels on detail pages, vendored Pico+HTMX (offline-ready), footer polish (version + git SHA + uptime + DB path) |

**Final test count:** **578 / 578 passing** (+155 across the M5 build).

**Exit test (PASSED):** the read+decision+action loop is fully in the
browser.  A stakeholder can read a project overview, generate
proposals, dry-run, and accept without touching the terminal.  The
one real Monday accept executed through the UI is still owed (per the
precedent of the 2026-05-21 CLI accept), but the code path is
end-to-end verified against a mocked connector in tests.

### Architecture (anyone picking this up)

- **Stack:** FastAPI + Jinja2 + HTMX + Pico.css, single thin web
  framework per operating principle #8.  Vendored CSS/JS in
  `web/static/`.  HTMX powers in-place mutations (accept/reject,
  task date edits) without a build pipeline.
- **Code organization:**
  - `web/app.py` -- FastAPI factory, mounts static + page routers.
  - `web/deps.py` -- `db()` session dep, `git_sha`, `db_path`,
    `app_version`, `uptime_str`, `build_monday_writeback` (mockable
    by tests).
  - `web/ui_views.py` -- **service module**, the boundary the M5
    plan review #2 demanded.  Every derived dashboard / project /
    proposal / doctor value computed here, never in templates or
    routes.  Templates take dicts, present them.
  - `web/routes/` -- one file per logical group: `projects.py`,
    `proposals.py`, `tasks.py`, `ask.py`, `doctor.py`, `db.py`.
    Each route is a thin adapter: dep -> service call -> template.
  - `web/templates/` -- 23 templates; `_partials/` for HTMX-swappable
    fragments (decision_idle / dry_run / decided / stale,
    task_dates_row / task_dates_form, propose_buttons / propose_result).
- **Security model:** localhost-only (`127.0.0.1`), no auth, no CORS
  middleware, no `--host` flag.  Mutation routes deliberately limited
  to: `proposals/{id}/{accept,reject,dry-run}`, `tasks/{id}/set-dates`,
  `projects/{id}/propose/{timelines,scope}`.  Permission-boundary
  tests pin the forbidden surface.
- **Prompt-philosophy boundary (load-bearing):**
  - **Askbot (Haiku, `ai/query.py::answer_with_llm`):** assertive,
    inferential, recommends, labels inferences.  "Do not give up
    just because the question is imperfect."
  - **Proposal bots (Sonnet, `ai/proposals.py::generate_*`):**
    conservative, refuses on uncertainty, "returning fewer proposals
    or none is correct."  Write to Monday, so refusal-on-uncertainty
    is the desired behavior.
  - A regression test
    (`tests/test_askbot_assertive_prompt.py::TestProposalBotsStayConservative`)
    pins that the proposal prompts retain their conservative anchors.
    **Do not apply the assertive style to the proposal bots.**

---

## M5 retrospective -- worth revisiting

Closed != frozen.  These are things noticed during M5 that didn't
block closure but are worth re-opening if the right moment comes.

### What worked

- **Server-rendered + HTMX scaled further than expected.**  Inline
  editing, two-click confirmation flows, conditional disabling,
  stale-state handling, loading indicators -- all in plain HTML +
  one `<script>` tag.  Zero build pipeline.  The codebase is
  readable end-to-end by anyone who knows Python and HTML.
- **Service-module discipline held.**  Every derived value lives in
  `ui_views.py` or `ai/views.py`.  Templates don't compute anything.
  This is what makes the CLI and UI consume the same data shape:
  `cmd_doctor` and `/doctor` BOTH call `report_doctor(session)` and
  cannot drift.
- **Permission-boundary tests caught regressions.**  The "no
  `/projects/edit` route" check fires when a future feature
  accidentally adds an edit endpoint.  The "no Accept button in
  Phase B" check would catch a template-level leak.  Cheap insurance.
- **Two-click accept + `hx-confirm` + `hx-disabled-elt` + spinner**
  -- the combination makes accidental double-writes essentially
  impossible.  The stale-state guard is the third layer (re-read
  before mutating).
- **Write-first/flip-second ordering** carried through every
  mutation path: accept_proposal, set_task_timeline.  A failed
  Monday write never leaves canonical state ahead of Monday.

### Footguns the next maintainer should know about

1. **Starlette 1.x changed `TemplateResponse` signature.**  Old form
   `TemplateResponse(name, ctx_with_request)` is removed.  New form is
   `TemplateResponse(request, name, context)`.  Symptom of accidental
   regression: `TypeError: unhashable type: 'dict'` from Jinja's
   template cache lookup.  Every route in this codebase uses the new
   form.
2. **SQLite `:memory:` + FastAPI TestClient threadpool.**  Sync routes
   dispatch through a threadpool; SQLite's default `check_same_thread=True`
   refuses.  All web test files override `db_engine` with `StaticPool`
   + `check_same_thread=False`.  Don't remove that.
3. **`hx-indicator` inherits down the DOM.**  If you put it on a
   `<form>`, child buttons with their own `hx-*` (e.g. Cancel's
   `hx-get`) trigger the spinner too.  Put `hx-indicator` on the
   specific button you want to spin (e.g. Save), not the form.
   Regression test: `TestTaskDateEdits::test_cancel_button_has_no_spinner_inheritance`.
4. **`complete_json` MUST detect truncation.**  If `finish_reason ==
   "max_tokens"` (Anthropic) or `"length"` (OpenAI), the retry should
   bump `max_tokens` by 1.5x, not just repeat with the same cap.
   The 6554 Rue Saint Hubert bug burnt this lesson in.
5. **Background-task processes detached from the parent shell** stay
   alive when the parent dies.  When developing, kill the uvicorn
   process explicitly (`Stop-Process` on Windows; the test infra runs
   it in-process via `TestClient` so this only affects manual
   `project_db serve`).
6. **`markdown` library passes raw HTML through by default.**  The
   askbot pre-escapes input via `html.escape` BEFORE rendering, so
   embedded `<script>` becomes inert text.  Don't bypass that.
7. **Two consumers, two variable shapes for partials.**  E.g.
   `_partials/decision_idle.html` is rendered (a) inline from
   `proposal_detail.html` where the parent context has `p.proposal_id`,
   and (b) standalone by the `accept/reject/dry-run` routes where
   the context has `proposal_id` directly.  The page template uses
   `{% with proposal_id=p.proposal_id, ... %}` to alias.  If you
   change the partial's variable names, update both consumers.

### Ideas worth revisiting

These were considered during M5, weighed, and deferred.  None block
the next phase; all worth thinking about if the matching constraint
emerges.

- **Bulk accept / bulk reject in the UI.**  The CLI has `proposals
  accept all --yes` and `reject all --yes`.  The UI deliberately
  doesn't expose a bulk-accept button -- bulk accept is the worst
  combination of risk and value (a single bad proposal in a batch
  of 20 writes to Monday before anyone notices).  If we want it,
  it should still go through `accept_proposal` per row, with a
  progress UI, and a one-failure-stops-the-batch policy.
- **Sortable columns / client-side filtering on the project list
  + proposal queue.**  Vanilla JS, no library needed.  Skipped to
  keep Phase E tight; reasonable to add when the lists get big.
- **Project-level pending-proposal badge on the dashboard's
  pending strip.**  Currently the strip shows "Project X / timeline"
  per row; you have to click in to see which task.  Could render
  the task title inline.
- **Diff between dry-run preview and what actually got written.**
  Right now after a real Accept, the "wrote_to_monday" payload is
  shown.  No comparison to the dry-run.  Probably irrelevant in
  practice because the two are constructed from the same proposal
  data, but if Monday ever transforms inputs (timezone shift,
  date format quirks), a diff would catch it.
- **Markdown rendering for proposal reasoning blockquotes.**  Right
  now the proposal detail page renders `reasoning` as plain text in a
  `<blockquote>`.  Markdown rendering would help if the model emits
  multi-paragraph reasoning -- but it usually doesn't, and we want
  models to be terse, not chatty, in proposal output.
- **WebSockets for live updates.**  When the CLI accepts a proposal
  in another tab, the browser doesn't know.  Right now we rely on
  the stale-state guard (POST re-reads before mutating) + reload.
  Could add server-sent events for "proposal X just changed"
  pushes.  Real but bounded value.
- **A "show this LLM call's actual tokens used" debug panel.**  Helps
  spot when a question is hitting the Haiku context limit.  The
  data is already in `LLMResponse.usage`; we just don't surface it.
- **Anomaly detection prompt.**  Same engine shape as scope, different
  prompt.  Held until scope quality is validated by a PM at scale
  (M4 ongoing).
- **`project_db daily <project>` -- HTML version.**  The CLI command
  exists; the UI's project detail page covers ~70% of what it shows.
  Could be a dedicated `/projects/{id}/daily` page if PMs find the
  combined project page too noisy.

### Things that should NOT change

- The localhost-only / no-auth posture.  This stays a single-user
  internal tool.  Multi-user / hosting / auth is a fundamentally
  different product and would invalidate most of the architectural
  decisions here.
- The "no business logic in templates" rule.  Service module pattern
  + permission-boundary tests are what make this codebase reviewable.
- The write-first/flip-second ordering on Monday-touching paths.
  Reverse it once and you can ACCEPT a proposal that never reached
  Monday.
- **The prompt-philosophy boundary.**  Askbot stays assertive; proposal
  bots stay conservative.  Applying the assertive style to a proposal
  bot would cause hallucinated dates / scope items to flow into the
  Proposal table and eventually onto Monday.  The regression test
  `tests/test_askbot_assertive_prompt.py::TestProposalBotsStayConservative`
  is there to catch accidental drift.

---

## Forward-looking AI plans

The M5 retrospective above identifies what M5 deferred.  The two big
ones each have a structured plan -- these are written up so future
work doesn't re-derive them.

### Askbot vs proposal bot: the prompt-philosophy boundary

A discovery from the 2026-05-26 user feedback and ChatGPT analysis,
worth pinning explicitly:

| Role | Model | Prompt style | Why |
|---|---|---|---|
| Askbot (`answer_with_llm`) | Haiku | **Assertive, inferential**; "do not give up", "infer the closest useful answer, label as inference", recommends actions | A human is asking; refusing on uncertainty is annoying.  No external write happens; cost of being wrong is low. |
| Timeline proposals (`generate_timeline_proposals`) | Sonnet | **Conservative**; "returning fewer proposals or none is correct", "must cite specific evidence", refuses past-dated proposals outright | Output writes to Monday via accept.  Hallucinated date == real bad data in the company's source of truth. |
| Scope proposals (`generate_scope_proposals`) | Sonnet | **Conservative**; "flag ONLY scope items explicitly stated", "never invent scope", "returning few flags is correct" | Same risk as timeline; advisory-only today (no auto-write), but the proposals shape PM workflow. |

**The askbot's job is to be a smart analyst.  The proposal bots' job
is to be a careful extractor.**  They look similar in code (same
`LLMProvider` interface, same `complete_json` retry helper) but their
prompt philosophies must NOT converge.

When tempted to make a proposal bot "smarter" by giving it the
askbot's assertive style: don't.  The right answer to "smarter
proposals" is better evidence (RAG), better citation (quoted excerpts
in `reasoning`), or a better source-document selection -- never
loosening the anti-hallucination posture.

### RAG over DocumentText (detailed plan)

**Why this is the big unlock.**  Today the askbot reads
`report_database_overview` -- 21 projects + 154 tasks + 750 doc
*metadata*, but NO document text.  It can answer "which tasks are
dateless?" but it CANNOT answer "what does the standard payment-terms
clause say?" or "which specific scope items does the 923 Rockland
SOW commit us to?"  Those answers live in `DocumentText` (463 of
the 750 docs have non-empty extracted text), and the askbot is
currently blind to them.

The proposal bots already get document text via
`assemble_project_context` -- but they get the top-N documents by
recency, not by relevance to the specific question being asked.  RAG
fixes both: relevance-ranked chunks for the askbot, AND
relevance-ranked supplementary chunks for proposal bots.

**Decisions made in 2026-05-26 strategy discussion:**

| Decision | Choice | Why |
|---|---|---|
| Embedding model | OpenAI `text-embedding-3-small` | Cheap (~$0.02/M tokens; ~$0.05 to embed the entire current corpus), fast batch API, well-understood quality.  We already depend on remote APIs (Anthropic). |
| Vector store | `sqlite-vec` extension | Same SQLite file, no new infra.  Per operating principle #8, this is the moment "no new tech" gives way -- SQL limits genuinely bite when you need ANN search. |
| Chunking strategy | Paragraph- or sentence-boundary chunks, ~500 tokens with ~50-token overlap | Standard.  Preserves clause structure of contracts. |
| Where in the pipeline | New `DocumentChunk` table; populated by an `embed-documents` CLI command incremental on top of `extract-content` | Mirrors the existing `DocumentText` sidecar pattern.  `extract-content` runs first (text); `embed-documents` runs second (embeddings). |
| Retrieval API | New `retrieve_chunks(question, project_id=None, top_k=12)` in `ai/rag.py` | Returns chunks ordered by cosine similarity; optional project filter for per-project questions. |

**Four-session breakdown:**

| Session | Deliverable | Tests |
|---|---|---|
| 1 | `DocumentChunk` SQLAlchemy model + `ensure_sqlite_schema` migration.  Chunking pipeline (paragraph-aware).  `project_db embed-documents [--project] [--overwrite]` CLI -- batch-embeds via OpenAI API, stores chunks + vectors. | Chunk shape, idempotency, migration. |
| 2 | Integrate `embed-documents` invocation into `extract-content` (--with-embeddings flag).  Skip re-embedding when chunk text matches the existing hash.  `sqlite-vec` index build. | Hash-skip behavior, vector dimensions, index roundtrip. |
| 3 | `retrieve_chunks(question, project_id, top_k)` helper.  Wire into `answer_with_llm` -- when retrieval finds high-similarity chunks (>0.7 cosine), append them to the user prompt under a "RELEVANT DOCUMENT EXCERPTS" header BEFORE the question.  Same for `assemble_project_context` (replace top-N-by-recency with top-N-by-relevance when a question is supplied). | Mocked embeddings, retrieval ordering, prompt assembly. |
| 4 | UI: `/ask` shows "based on N document chunks" badge + collapsible list of cited chunks with `<a>` to source doc.  Proposal detail page shows "RAG-supplied chunks" as a separate panel from "source documents" the model chose to cite. | Template assertions, badge rendering, no UI regressions. |

**Open questions for when we get there:**

- How do we hold the embedding API key separate from the chat API
  key?  (`ANTHROPIC_API_KEY` vs `OPENAI_API_KEY` env vars; document
  in README.)
- Re-embedding policy: full rebuild on doc edit, or chunk-level
  diff?  Probably full rebuild per doc on text-hash change, given
  the small corpus.
- Cost monitoring: log per-call token usage, alert if a single
  question retrieves the same chunks 10x in a row (likely a loop).

**This applies to BOTH bots:**
- Askbot: questions like "what does the standard payment-terms
  clause say?" become answerable.  The assertive style + RAG-supplied
  chunks means the model has real evidence to be assertive about.
- Proposal bots: timeline / scope generation gets chunks selected
  for the project AND ranked by question relevance.  Quality lifts,
  particularly for scope where the relevant clauses are buried in
  long SOWs.  The conservative prompt style stays -- RAG is an input
  upgrade, not a behavior change.

### Financial extraction strategy

**The problem (user, 2026-05-26):**  "we need some kind of interaction
or global awareness of financial continuity, and bookkeeping" --
across SOWs (contracts), invoices, change orders, and eventually
QuickBooks-source AP/AR.  Today: `budget_vs_contract` uses regex to
find `$amounts` in contract text and picks the max.  Crude.

**Three options, ranked by cost / payoff:**

| Option | What | Effort | When |
|---|---|---|---|
| **A. Brute-force LLM extraction per doc-type** | One prompt + strict schema per document type (Invoice, ContractLineItem, ChangeOrder).  Store extracted records in new tables. | ~3-4 sessions | **Next.**  Works today, no new deps. |
| **B. Live QB integration** | Existing connector code; needs creds.  Stops scraping PDFs QB already has structured. | ~1 session once creds exist | **Concurrent with A.**  Solves the QB-shaped slice cleanly. |
| **C. Prebuilt construction-accounting integration** | Procore / Buildertrend / Sage / Accounting Seed | ~$200-2000/mo | **Reassess after A+B.**  Only if AP/AR workflows / payroll / multi-currency / vendor approval routing genuinely missing. |

**Option A in detail (the recommendation):**

Each new document type follows the same template:

1. **Schema** -- e.g. `InvoiceLineItem(invoice_id, sku, qty, unit_price, total, project_id)`.  Add the SQLAlchemy model + migration.
2. **Extractor prompt** -- "given this invoice text, return strict JSON matching this schema, NEVER invent line items not in the text."  Same conservative posture as the proposal bots.
3. **Validator** -- schema-check every returned item; bad items go to a per-doc errors list, never crash the run.
4. **CLI command** -- `project_db extract-financials [--doc-type invoice] [--project] [--limit]`.  Idempotent like `extract-content`.
5. **Surface in UI** -- new "Financials" panel on the project detail page (per-line-item table); aggregate billed / committed totals on the dashboard.

Build incrementally per doc type as the use case shows up.  Don't
build all five at once -- ship Invoice first, see if it's used, then
ContractLineItem, etc.

**Where the LLM is the WRONG tool:**  general arithmetic (sum line
items, compute margins) -- do that in SQL.  The LLM extracts;
canonical reports compute.  Same separation as the rest of the AI
layer.

**"Global awareness" -- how it emerges:**

Once structured line items exist keyed to projects, "is Project X
profitable right now?" becomes a SQL JOIN: contract amount vs sum of
invoiced line items vs Monday-tracked labor cost vs paid invoices
(QB).  No more LLM needed for the COMPUTATION; the LLM's role shifts
to NARRATION ("Project X is 12% over budget; the overrun is
concentrated in cabinetry...").  This is exactly the dual-model
pattern: cheap deterministic SQL for facts, expensive LLM for prose.

**Cross-category Drive content (intelligence / leads / company /
real_estate / construction folders):**  These are non-financial,
so they're a different question -- knowledge-base RAG, NOT
structured extraction.  Handle via the RAG plan above.  The folder
category becomes a retrieval filter ("only chunks from `category =
company`").

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
