# ALTA / project_db — Developer Handoff

For the next Claude instance picking this up. Everything here is information
that ISN'T in README/ROADMAP/CHANGELOG/STRATEGY — invariants, subtle design
decisions, and footguns that bit us. Read those four first; this fills the
gaps.

---

## 1. Repo layout (one-line orientation)

The git repo root is **`ALTAtest/`** (not `project-db/`). `project-db/` is a
subdirectory holding the actual Python package. There is also a git worktree
at `ALTAtest/.claude/worktrees/<name>/` used for Claude Code sessions —
**ignore the worktree; all real work lives in `project-db/`**. Always edit
under `project-db/...` with absolute paths.

```
project-db/
  src/project_db/
    ai/          context.py, proposals.py, query.py, views.py, providers/
    connectors/  monday/, gdrive/, quickbooks/   (companycam stubbed)
    db/          base.py, models/, migrations.py, session.py
    identity/    resolver.py, matcher.py
    cli.py       single entry point
    config.py    selective .env loader
  tests/         pytest; conftest.py has all fixtures + env stubs
  docs/          STRATEGY.md, ROADMAP.md, HANDOFF.md (this file)
```

---

## 2. The four governing invariants (do not break)

1. **The LLM is an advisor, never an actor.** Any AI-produced field change
   lands in the `Proposal` table as PENDING. A human accepts/rejects.
   `accept` is the only path that mutates an external system, and it writes
   to Monday FIRST and flips the proposal status only on success — never
   the reverse.
2. **Identity is deterministic; uncertainty surfaces in `doctor`, not in
   code.** No substring matching, no fuzzy guessing inside connectors.
   Project identity comes from Drive folder ancestry; Monday boards match
   INTO Drive projects via `ProjectMatcher` (civic-number then exact-name,
   unique-hit-only). A board that matches no allowlisted classification
   rule is SKIPPED, not guessed.
3. **Connectors extract source facts. Resolvers reconcile identity. The DB
   stores a canonical projection. The AI layer only reads canonical state.**
   No connector performs fuzzy cross-source business logic.
4. **Documents are the system of record for content; Monday is the system
   of record for status.** Drive folders define which Project a document
   belongs to (by physical ancestry). Monday columns drive task state.

---

## 3. Architecture you need to know

### ExternalId bridge
Every canonical entity (Project, Task, Client, ...) can have multiple
`ExternalId` rows linking it to source systems. `(source, external_key)` is
unique. The resolver pattern: `resolve_or_create(source, entity_class,
external_key, matcher, create_only_attrs, **attrs)`. A matched path applies
attrs (a regression bug — the original didn't, and `rebuild` left every doc
unlinked). `create_only_attrs` prevents Monday from renaming Drive-authoritative
projects.

### Drive as the project source
- `01. PROJECTS/{ACTIVE,INACTIVE,LEADS}/<project name>/` — each immediate
  child of a bucket is one canonical Project, keyed by **folder id**. Two
  folders never merge.
- All files under a project folder inherit `project_id` by ancestry. Files
  under `00. COMPANY`, `02. REAL ESTATE`, `03. CONSTRUCTION`,
  `05. INTELLIGENCE` get `Document.category = ...` and `project_id = NULL`.
- The substring matcher `_match_project_by_name` is **deleted**. Do not
  reinstate it; it produced the "Rockland matches 927 Rockland" bug.

### Monday connector + the mirror overlay (this one is subtle)
- `column_values` in the GraphQL response **omits empty columns** —
  listing column ids does NOT force absent columns to appear.
- Task boards often have empty per-task Status/Timeline; the real value
  lives on a **portfolio item** linked via a `board_relation` or
  `dependency` column.
- `apply_portfolio_mirror_overlay` walks each item AND its subitems
  (recursive `_inject`), collects every `board_relation` / `dependency`
  target id (recursive `_collect_linked_item_ids`), fetches those portfolio
  items with `MirrorValue.mirrored_items`, and **enriches** the original
  column_values from `MIRROR_COLUMN_MAP`. Native values always win over
  mirror values. This is what made 923 Rockland's 118 subitem tasks
  actually get status/timeline (was ~5/118; now 93/118).
- `_classify_board` fails closed. No "default to ProjectBoard" fallback.

### Resolver matchers
- `ExactFieldMatcher(fields)` — equality on named columns.
- `FuzzyFieldMatcher` — for clients/people only (email-normalized,
  name-fuzzy). Never used for projects.
- `ProjectMatcher` — civic-number (`923 == 923`, `927 ≠ 923`) THEN exact
  normalized-name. Ambiguous or zero hits → no match (resolver creates;
  `doctor` flags). No substring.

---

## 4. AI layer

### Dual-model providers
- `get_default_provider()` → "deep" model (Sonnet via `ANTHROPIC_MODEL`).
  Used by `propose timelines` / `propose scope` — analytical work.
- `get_fast_provider()` → "fast" model (Haiku via `ANTHROPIC_MODEL_FAST`,
  default `claude-haiku-4-5`). Used by `ask` non-canned fallback —
  summarization-grade.
- Both resolve the same backend via `_resolve_provider_name()`
  (LLM_PROVIDER → anthropic-if-key → mock). `_build_provider(name, fast=)`
  is the shared constructor; openai-compatible respects `OPENAI_MODEL_FAST`.

### Context assembler (`ai/context.py`)
- `assemble_project_context(session, project_id, token_budget, ...)` pulls
  Project+Client+Tasks+Documents+DocumentTexts+Invoices+DailyLogs into a
  `ProjectContext`. Budget evicts doc bodies **oldest-first**.
- Bug fixed long ago that still matters: the assembler joins through
  `DocumentText` FIRST, then takes top-N by recency. "N readable bodies,"
  not "N doc slots that might be empty."

### Database snapshot for `ask` (`ai/views.py`)
- `report_database_overview(session, max_tasks=600)` is the JSON snapshot
  fed to the fast LLM for non-canned `ask` questions. Includes every
  project (with rolled-up counts), every task, deals, leads, clients,
  invoices, doc-category breakdown. **Excludes document text** — too big
  for a cheap per-question call.
- NOT registered in `REPORT_REGISTRY` (it's infrastructure for the LLM
  fallback, not a keyword-routed report).

### Proposal lifecycle
- `Proposal` is polymorphic: `entity_type` + `entity_id` + `field_name` +
  `proposed_value` (JSON). Status: PENDING → ACCEPTED | REJECTED | SUPERSEDED.
- **Timeline auto-supersede** keys by `(entity_type=Task, entity_id=task,
  field_name=timeline)`. One proposal per task at a time.
- **Scope auto-supersede** treats each `propose scope` run as a fresh
  snapshot — supersedes ALL prior PENDING `scope_gap` proposals for the
  project at the start of the run.
- `_ACCEPTABLE_FIELDS = {"timeline"}`. `accept_proposal` only writes
  timelines to Monday. Scope/anomaly proposals are advisory — `accept`
  refuses with a clean error; reviewer uses `reject` or acts manually.

### accept_proposal — the load-bearing ordering
Monday write FIRST → on True return, flip status + mirror dates onto the
canonical Task. On False or exception, proposal stays PENDING, Task
untouched. The test `test_write_back_false_leaves_proposal_pending` exists
to lock this in.

---

## 5. Prompt-engineering lessons (baked into every prompt)

1. **Instruction at the TAIL of the user message.** When a prompt overflows
   the context window, most backends (Ollama, many gateways) truncate from
   the FRONT. A front-loaded instruction gets cut; the model responds to
   the document body at the bottom instead. We learned this when a 5768
   prompt produced a French lease rewrite. EVERY prompt: context first,
   instruction last.
2. **Models reference items by integer INDEX, not UUID.** Models miscopy
   36-char UUIDs reliably; an index they cannot subtly wrong. We map
   index → canonical entity on the server side.
3. **Validate every LLM item before persisting.** Bad items go to
   `ProposalBatch.errors`, never crash the batch. One malformed row must
   not sink everything.
4. **Anti-hallucination: warn, don't reject (unless it's clearly wrong).**
   - Cited `source_document` that matches NO doc we supplied → warning
     (possible hallucination, still create the proposal).
   - Missing `reasoning` → warning.
   - Past-dated timeline (`end < today`) → REJECT outright. Timelines are
     forward-looking; a past timeline means the task is done. This guards
     the 2022-date bug.
5. **`{"proposals": []}` / `{"scope_gaps": []}` is a VALID answer.** "No
   evidence" beats invention. Tell the model this explicitly.

---

## 6. CLI command map

| Command | What it does |
|---|---|
| `init-db` | Create tables + seed default Organization. Idempotent. |
| `sync monday [--delta]` | Pull Monday; `--delta` uses activity_logs cursor. |
| `sync GOOGLE_DRIVE` | Pull Drive (uses `changes.list` cursor). |
| `gdrive-auth` | One-time OAuth Desktop browser flow. |
| `list-boards`, `inspect-board <id>` | Live Monday board exploration. |
| `extract-content [--project] [--overwrite] [--limit]` | Run text extractors over Documents. Idempotent. Commits every 25 docs. |
| `ask "..."` | Canned reports (8 patterns + `help`) → fast LLM fallback for anything else. |
| `daily <project> [--propose-timelines]` | One-screen read-only review (LLM strictly gated). |
| `propose timelines <project>` | Sonnet timeline proposals → PENDING. |
| `propose scope <project>` | Sonnet scope-gap proposals → PENDING (advisory). |
| `proposals list [--status] [--kind]` | Newest-first, filterable. |
| `proposals show <id>` | Full detail + source documents. |
| `proposals accept [<id>\|all] [--dry-run] [--yes] [--by]` | Empty → list; `all --yes` → bulk Monday write. |
| `proposals reject [<id>\|all] [--reason] [--yes] [--by]` | Empty → list; `all --yes` → bulk reject. |
| `llm-test <project>` | LLM smoke (no Proposal written). |
| `doctor` | Read-only data audit (provenance, mislinks, orphans, duplicate civics). |
| `rebuild --yes` | Re-derive canonical DB. Preserves Document+DocumentText; exports Proposals to JSON first. |
| `list-sources`, `list-external <type> <uuid>` | Plumbing introspection. |

Exit codes: 0 ok, 1 caller-facing failure (e.g. proposal validation),
2 configuration / not-found / missing prerequisite.

---

## 7. Testing patterns (read before writing new tests)

- **`conftest.py` stubs env vars BEFORE importing app modules** (lines
  24-31). Tests think `LLM_PROVIDER=anthropic` + `ANTHROPIC_API_KEY=test_anthropic_key`
  because `.env` is selective-loaded into `os.environ`. Any test that
  triggers a real provider call → mock the provider or monkeypatch the
  resolver. Never let a test hit `.complete()` for real.
- **`MockLLMProvider`**: pass `responses=[...]` for sequential answers
  (sticks on last), or `on_call=lambda **kw: ...` for dynamic. Every call
  captured in `.calls` for assertions.
- **`patched_session_factory` fixture** binds `session_scope()` to the
  test engine. CLI tests use this so `cmd_*` functions hit the same
  in-memory DB the test sees via the `session` fixture.
- **Cross-session staleness**: when a CLI command commits via its own
  `session_scope()`, the outer `session` fixture's identity map has stale
  attributes (`expire_on_commit=False`). Call `session.expire_all()`
  before re-querying to verify post-CLI state. See `TestCliProposals`.
- **SQLite `:memory:` shares one connection per thread** (SQLAlchemy
  default pool), so all sessions on the test thread hit the same DB.
- **Patching the `ask` LLM provider**: `monkeypatch.setattr(
  "project_db.ai.get_fast_provider", lambda: MockLLMProvider(...))` — the
  CLI's `from project_db.ai import get_fast_provider` inside the function
  re-fetches at call time, so the patch takes effect.

---

## 8. Footguns that have bitten us

- **`column_values` omits empty columns** (Monday). Don't assume a missing
  column means "no value"; it means "no value OR not populated yet."
  Check mirror columns.
- **`expire_on_commit=False` + cross-session writes** → stale reads. Use
  `expire_all()` or open a fresh session.
- **`get_default_provider` will silently build an AnthropicProvider** if
  `ANTHROPIC_API_KEY` is set + `LLM_PROVIDER` unset. In tests, conftest
  sets the key. Always inject mocks for tests that call `.complete()`.
- **Windows console encoding mangles LLM em-dashes.** `main()` calls
  `sys.stdout.reconfigure(encoding="utf-8")` to fix it. Don't remove that.
- **`.env` selective load** (`config.py`): a non-empty env var WINS over
  `.env` (so CI/Docker secrets stay authoritative), but an empty/missing
  env var picks up the `.env` value. This was added because a shell
  profile had `ANTHROPIC_API_KEY=` (empty), and the real key in `.env`
  was being shadowed. Plain `override=True` would have broken CI.
- **`rebuild` is destructive**. Preflight builds every connector BEFORE
  wiping anything — a dead OAuth token aborts cleanly with the DB
  untouched. Don't reorder.
- **The egg-info directory** (`src/project_db.egg-info/`) is tracked but
  should NOT be committed when only its contents changed via `pip install -e`.
  Stage source/test/doc files explicitly; never `git add -A`.
- **`.env.example` is gitignored** by a `.env*` rule. The README is the
  authoritative config doc; `.env.example` is best-effort.

---

## 9. What is deliberately deferred and why

- **CompanyCam, QuickBooks live sync, Webhooks, Postgres + Alembic,
  pgvector, text-to-SQL, multi-tenant, scheduling** — plumbing-not-brain.
  Per STRATEGY.md, don't pick these up until a PM is using the daily
  Monday+Drive loop.
- **Anomaly detection prompt** — same engine shape as scope; held until
  scope quality is validated by a PM.
- **Auto-creating Monday tasks from accepted scope proposals** — would
  require a write-back action for `field_name="scope_gap"`. Not built;
  scope is advisory-only for now. The natural place to add it: a new
  branch in `accept_proposal` (or a sibling function) that calls a
  `MondayConnector.create_item_for_scope_gap`.
- **RAG over DocumentText / fine-tuning corpus / minimal UI** — see
  ROADMAP "Future architecture notes" and Phase 6. Not next.

---

## 10. How to continue (per the operating plan)

The roadmap's near-term milestones are M1-M5; M1-M3 are done. Next:

- **M4 — Scope reconciliation quality validation.** `propose scope` ships,
  but a PM hasn't reviewed enough output to tune the prompt. The next
  reasonable step is to run it on 3-5 projects, look at the rejection
  rate, and iterate the prompt. Don't add more LLM features until scope
  output is trusted.
- **M5 — Minimal UI.** Thin FastAPI/Flask over `ai/views.py` reports +
  the existing `accept_proposal` / `reject_proposal`. No new business
  logic in the UI. Pull this forward if discoverability is the blocker.
- If anomaly detection is requested, mirror `generate_scope_proposals`:
  new prompt version, new `field_name`, supersede-by-project pattern.

If the next session is about a bug or a small feature, **read CHANGELOG's
top entry first** for the live snapshot of what works.

---

## 11. Tracking conventions

- Test count in README is hand-maintained. Update it when you add tests.
- CHANGELOG is newest-on-top. Each entry has a date + theme + what shipped
  + tests + state at EOD.
- ROADMAP `[ ]` → `[x]` when a phase item ships.
- Commit messages: imperative, group by concern, mention test count.
- Co-author trailer on Claude commits: `Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>`.
