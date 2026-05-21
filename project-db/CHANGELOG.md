# ALTA / project_db — Work Log

A day-by-day journal of what was built, what works, and how the project's
capability grew. Newest entry on top. Lower-level "what changed" detail
is in commit messages; this is the human-readable version.

If you want **"what can this product do today?"** read the top entry.
If you want **"how did we get here?"** read top to bottom.

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
