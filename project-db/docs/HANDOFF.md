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

### Roadmap integration (post-M5, 2026-05-26)

The canonical design-phase roadmap (SD/DD/CD/CA, 44 tasks) is imported
from `docs/Project Roadmap.xlsx` into the `roadmap_task` table and
filter-injected into both proposal prompts.

**Two-layer architecture (Layer 3 was deliberately skipped):**
- **Layer 1 -- storage.** `RoadmapTask` model, `import-roadmap` CLI.
  The xlsx itself is tracked in git so fresh clones can re-import.
- **Layer 2 -- prompt injection.**  `RoadmapActor` enum
  (ARCHITECT/CONTRACTOR/BOTH) on each row.  `classify-roadmap` CLI
  does a one-shot Sonnet pass to populate.  `_render_roadmap_for_prompt`
  filters to CONTRACTOR + BOTH (ARCHITECT-only is noise on contractor
  boards) and injects into both `_build_timeline_prompt` and
  `_build_scope_prompt`.  Scope output gains a `source` field
  (`"contract"` | `"roadmap"`) so the UI can break flags down by
  origin.  Pre-classify state (no actor) -> empty inject block ->
  prompts behave as pre-Layer-2.

**Layer 3 skip rationale:** the original plan was a deterministic
`roadmap-gaps` CLI doing fuzzy match between Monday tasks and the 44
roadmap entries.  On evaluation: the roadmap is architect-side work,
the Monday boards are contractor execution.  A naive matcher would
flag 30-40 "missing" architect tasks per project -- pure noise.  The
LLM-driven Layer 2 with actor filter does the same job contextually,
producing zero architect-noise on the live 5768 St-Laurent test (4
roadmap flags, all legitimately contractor-relevant).  The user
approved skipping Layer 3.

**Live verified (2026-05-26):** `propose scope` on 5768 St-Laurent
produced 6 contract-sourced + 4 roadmap-sourced gaps, all useful.

**Behavior observation worth knowing:** the prompt asks the model to
cite roadmap entries by `[phase-ordinal]+name` (e.g. `[CA-04]`).
In practice the model OFTEN cites by **pattern parallelism** instead
when the project's own task list provides better evidence (e.g.
"Phase 1 has X but Phase 2 doesn't").  This isn't a prompt failure
-- it's the model choosing project-specific evidence over generic
template evidence, which is generally better.  If you want strict
`[CA-XX]` citation in all cases, tighten the prompt or post-filter.

### Quoted-excerpt reasoning (2026-05-26)

Both proposal bots' `reasoning` field is now required to contain
verifiable evidence, not summaries:

| Evidence type | Required citation |
|---|---|
| Contract / document | Direct QUOTED EXCERPT in double quotes (~30 words max), + document name |
| Schedule sequence (timeline only) | Named neighbour tasks + dates (e.g. "between Demolition (2026-06-01 to 06-10) and Final Inspection (2026-08-12)") |
| Roadmap entry | `[phase-ordinal]+name` citation (when used; see observation above) |

Lazy reasoning ("the contract states this", "per the schedule") is
explicitly REJECTED in the prompt.

The proposal detail UI shows the reasoning in a `<blockquote>` and
the source documents below with an `open` link to `/documents/{id}`,
where the user can Ctrl-F to verify the quote against the full
extracted text.  Excerpt offsets are NOT stored on Proposal -- the
disclaimer "this document supports the claim, not necessarily this
exact span" is rendered explicitly per the M5 plan review #7.

**Prompt versions:** `timeline-v4-quoted`, `scope-v3-quoted`.
A regression test (`tests/test_prompt_quoted_excerpts.py`) pins the
EVIDENCE-CITATION REQUIREMENT block in both prompts so a future
"clean up the prompt" edit can't accidentally drop it.

### Web UI (M5)
- **Stack**: FastAPI + Jinja2 + HTMX + Pico.css.  Vendored static in
  `web/static/`.  No build pipeline, no JS toolchain.
- **Service-module discipline** (`web/ui_views.py`): EVERY derived
  value the templates render is computed there, not in templates or
  routes.  Mirrors the `ai/views.py` pattern for the CLI.  The same
  data shape (`report_doctor`, `dashboard_summary`, `project_detail`,
  etc.) drives both surfaces.
- **Route boundary**: routes are thin adapters (dep → service →
  template).  Mutation routes (accept / reject / set-dates) are
  pinned to four steps: re-read state, build connector, delegate to
  the existing service function, render one of {idle / dry_run /
  decided / stale} partials.
- **HTMX patterns**:
  - `hx-confirm` on every Sonnet-spending button (proposals
    generation, confirm-accept).
  - `hx-indicator` + `hx-disabled-elt` on every action button (spinner
    + button-group disable during in-flight request).
  - `outerHTML` swap on `<section id="decision">` for the four-state
    decision partial machine (idle ↔ dry_run → decided; any →
    stale on cross-tab race).
  - Stale-state guard: every mutation POST re-reads the proposal
    BEFORE delegating; non-PENDING → render `decision_stale`
    fragment, not a 4xx.
- **Localhost only**: hard-bound to `127.0.0.1`, no `--host` flag,
  no CORS middleware, no auth.  Multi-user is a different product.

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
| **`serve [--port 8000]`** | **Launch the local web UI on 127.0.0.1 (M5).** No auth, single-user, localhost-only. |
| **`import-roadmap [path] [--overwrite]`** | Import the canonical design-phase roadmap from xlsx into `roadmap_task` table.  Default path: `docs/Project Roadmap.xlsx` (also tries `../docs/Project Roadmap.xlsx`).  Idempotent; `--overwrite` drops + re-inserts. |
| **`classify-roadmap`** | Single-call Sonnet pass to classify every `roadmap_task` row by actor (ARCHITECT/CONTRACTOR/BOTH).  Re-runnable; overwrites previous values.  Required for Layer 2 prompt injection -- proposal prompts only see CONTRACTOR + BOTH rows. |

Exit codes: 0 ok, 1 caller-facing failure (e.g. proposal validation),
2 configuration / not-found / missing prerequisite.

### Web UI route map (M5)

| Route | Method | Purpose |
|---|---|---|
| `/` | GET | Dashboard (live counts + pending-proposal strip) |
| `/projects` | GET | All projects table |
| `/projects/{id}` | GET | 5-panel project detail + Generate panel + raw JSON |
| `/projects/{id}/propose/timelines` | POST | Generate timeline proposals (Sonnet, hx-confirm) |
| `/projects/{id}/propose/scope` | POST | Generate scope proposals (Sonnet, hx-confirm) |
| `/documents/{id}` | GET | Document metadata + full extracted text + citing proposals |
| `/proposals` | GET | Filterable proposal queue |
| `/proposals/{id}` | GET | 5-panel review page |
| `/proposals/{id}/decision` | GET | Re-render idle fragment (used as dry-run Cancel target) |
| `/proposals/{id}/dry-run` | POST | Preview Monday payload; no DB / API change |
| `/proposals/{id}/accept` | POST | Write to Monday, flip status (write-first/mirror-second) |
| `/proposals/{id}/reject` | POST | Pure DB; optional reason via Form |
| `/tasks/{id}/dates-form` | GET | Inline edit form |
| `/tasks/{id}/row` | GET | Static row (Cancel target) |
| `/tasks/{id}/set-dates` | POST | Manual date edit; write Monday + mirror |
| `/ask` | GET, POST | Canned dispatcher + Haiku LLM fallback |
| `/doctor` | GET | Data integrity audit (HTML render of `report_doctor()`) |
| `/db` | GET | Table index (dev affordance) |
| `/db/{table}` | GET | Top-100 rows of one table (dev affordance) |
| `/static/*` | GET | Vendored Pico, HTMX, app.css |
| `/docs` | GET | FastAPI auto Swagger (free debugging surface) |

### M5 prompt-philosophy boundary (load-bearing)

| Role | Function | Style |
|---|---|---|
| Askbot | `ai/query.py::answer_with_llm` | **Assertive, inferential**.  Recommends; labels inferences; "Never end at a dead end." |
| Timeline proposals | `ai/proposals.py::generate_timeline_proposals` | **Conservative**.  "Returning fewer proposals, or none, is correct."  Past-dated proposals rejected outright. |
| Scope proposals | `ai/proposals.py::generate_scope_proposals` | **Conservative**.  "Flag ONLY scope items explicitly stated."  Advisory-only -- can't be accepted via `accept_proposal`. |

Regression test pinning the boundary:
`tests/test_askbot_assertive_prompt.py::TestProposalBotsStayConservative`.
**Do not apply the askbot's assertive style to a proposal bot.**

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

### M5-era web footguns (read before touching `web/`)

- **Starlette 1.x changed `TemplateResponse` signature.**  Old form
  `TemplateResponse(name, {"request": req, ...})` is removed.  New
  form is `TemplateResponse(request, name, {...})`.  Symptom of
  accidental regression: `TypeError: unhashable type: 'dict'` from
  Jinja's template cache.  Every route in `web/routes/` uses the new
  form; don't revert.
- **SQLite `:memory:` + FastAPI TestClient threadpool.**  Sync routes
  dispatch through a threadpool; SQLite's default `check_same_thread=True`
  refuses cross-thread access.  Every web test file overrides
  `db_engine` with a `StaticPool` + `check_same_thread=False` engine.
  Don't remove that fixture override.
- **`hx-indicator` inherits down the DOM.**  If on a `<form>`, child
  buttons with their own `hx-*` (e.g. Cancel's `hx-get`) trigger the
  spinner too.  Put `hx-indicator` on the specific button that should
  spin (e.g. Save), not the form.  Pinned by
  `tests/test_web_phase_d1.py::TestTaskDateEdits::test_cancel_button_has_no_spinner_inheritance`.
- **`complete_json` must detect truncation.**  If `finish_reason ==
  "max_tokens"` (Anthropic) or `"length"` (OpenAI), the retry bumps
  `max_tokens` by 1.5x.  Same cap on retry == same wall.  Pinned by
  `tests/test_complete_json_truncation.py`.
- **`markdown` library passes raw HTML through by default.**  The
  askbot pre-escapes input via `html.escape()` BEFORE rendering, so
  embedded `<script>` becomes inert text.  See
  `web/routes/ask.py::_render_markdown`.  Don't bypass the pre-escape.
- **Partial templates serve two consumers, two variable shapes.**
  E.g. `_partials/decision_idle.html` is rendered (a) inline from
  `proposal_detail.html` where the parent context has `p.proposal_id`,
  and (b) standalone by the accept/reject routes where the context
  has `proposal_id` directly.  The page template uses `{% with %}`
  to alias.  If you change the partial's variable names, update both
  consumers.
- **Vendored Pico + HTMX in `web/static/`** -- 130 KB total.  Bumping
  versions: replace the files in place; comments in `base.html` link
  to the original URLs.  Do NOT re-introduce CDN links;
  `tests/test_web_phase_e.py::TestVendoredAssets::test_base_template_does_not_reference_cdn`
  fails loud if you do.
- **Background processes (uvicorn) detach from the parent shell on
  Windows.**  When testing manually, kill the port with
  `Get-NetTCPConnection -LocalPort 8000 | ForEach-Object {
  Stop-Process -Id $_.OwningProcess -Force }`.  `TestClient` runs
  in-process so this only affects manual `project_db serve`.

### Post-M5 roadmap-integration footguns (2026-05-26)

- **`hx-disabled-elt` on a `<form>` inherits to child buttons with
  hx-* attrs.**  This was the 2025-05-26 v2 Cancel-doesn't-close bug:
  HTMX form-level attrs inherit, AND HTMX serializes form data on any
  request inside a `<form>`, so Cancel's `hx-get` was hitting
  `/tasks/X/row?start_date=&end_date=` with an inherited disable
  rule -- the swap silently failed in some browsers.  Pattern: keep
  hx-* attrs on the SPECIFIC buttons that should have them, never on
  the wrapping `<form>`.  Add `hx-params="none"` to buttons that
  shouldn't ship form data.  Two regression tests pin this in
  `tests/test_web_phase_d1.py::TestTaskDateEdits`.
- **The roadmap xlsx is the editorial source of truth, not the DB.**
  Edit `docs/Project Roadmap.xlsx` if the canonical roadmap changes;
  re-run `project_db import-roadmap --overwrite`.  Then re-run
  `project_db classify-roadmap` to repopulate actors.  The DB rows
  are a *projection*; never edit them directly.
- **Pre-classify state is silent: empty roadmap_block in prompts.**
  If `classify-roadmap` has never run on a fresh DB, every
  `roadmap_task` row has `actor=NULL` and `_render_roadmap_for_prompt`
  returns `""`.  The proposal prompts then behave as pre-Layer-2.
  This is intentional (don't inject unclassified data), but it can
  surprise: "I imported the roadmap; why aren't my scope proposals
  using it?"  Answer: run `classify-roadmap`.
- **Roadmap source label defaults to "contract" silently.**  If the
  model returns a scope_gap without a `source` field, we default to
  "contract" for back-compat with pre-Layer-2 outputs.  When
  debugging "why does this look like a contract gap when I thought
  it was roadmap?", check the model's actual JSON output (raw panel
  on the proposal page) before assuming the persistence layer is
  wrong.
- **The model has discretion on roadmap citation style.**  The
  prompt asks for `[phase-ordinal]+name` for roadmap entries, but
  the model legitimately substitutes project-specific parallelism
  reasoning when that's more evidence-grounded (see "Behavior
  observation" in Section 3 / Roadmap integration above).  Both
  styles are acceptable; if you need strict `[CA-XX]` citation,
  tighten the prompt and add a parse-side check.

---

## 9. What is deliberately deferred and why

- **CompanyCam, Webhooks, Postgres + Alembic, pgvector, text-to-SQL,
  multi-tenant, scheduling** — plumbing-not-brain.  Per STRATEGY.md,
  don't pick these up until a PM is using the daily Monday+Drive loop
  AND the brain (RAG + financial extraction) has shipped.
- **QuickBooks live sync** -- still pending real credentials.  Code
  is ready; ~1 session once creds exist.  Per ROADMAP's current
  operating plan, this happens concurrent with structured financial
  extraction (option A there).
- **Anomaly detection prompt** — same engine shape as scope; held
  until scope quality is validated by a PM at scale (M4 ongoing).
- **Auto-creating Monday tasks from accepted scope proposals** —
  would require a write-back action for `field_name="scope_gap"`.
  Not built; scope is advisory-only for now.  The natural place to
  add it: a new branch in `accept_proposal` (or a sibling function)
  that calls a `MondayConnector.create_item_for_scope_gap`.
- **Intent classification + per-question context selection** in the
  askbot.  ChatGPT recommended this on 2026-05-26.  Not urgent at
  21 projects; reasonable to add when DB size hurts Haiku recall.
  See ROADMAP "Deferred but considered" section.
- **Bulk accept / bulk reject in the UI.**  CLI has it; UI doesn't.
  Deliberately omitted to keep the failure mode bounded -- one bad
  proposal in a batch of 20 writes to Monday before anyone notices.
  See M5 retrospective in ROADMAP for the full rationale.
- **Multi-user / hosting / auth.**  The current architecture assumes
  single-machine single-user.  Adding multi-user is a fundamentally
  different product and would invalidate most of the M5 decisions
  (no CORS, no `--host` flag, no session auth, no rate limiting).
  If this comes up, it's a separate project, not a feature.

---

## 10. How to continue (per the current operating plan)

**M5 closed (2026-05-26).**  The local web UI is shipped; the full
read+decision+action loop is in the browser.  **Post-M5 work today:**
roadmap integration Layers 1+2 (Layer 3 deliberately skipped) and
quoted-excerpt reasoning in both proposal bots.  **625 tests passing.**

The ROADMAP's "Current operating plan (2026-05-26)" is the
authoritative next-step list.  In priority order:

1. ~~**Tighten proposal reasoning prompts with quoted excerpts**~~
   **DONE** (commit `68c1904`).  Both prompts now demand QUOTED
   EXCERPTS for contract evidence; lazy reasoning REJECTED.
   Verified live on 5768 St-Laurent.
2. **RAG over `DocumentText`** -- the biggest capability unlock.
   ~4 sessions.  Detailed plan in ROADMAP "RAG over DocumentText
   (detailed plan)" section.  Both askbot and proposal bots gain.
   **This is now the highest-leverage next move.**
3. **Structured financial extraction** -- per-doc-type LLM extractor
   into new tables (Invoice line items, ContractLineItem,
   ChangeOrder).  ~3-4 sessions.  Detailed plan in ROADMAP
   "Financial extraction strategy" section.  Concurrent with #2 OK.
4. **Live QB integration** -- pending real creds.  ~1 session.
5. **One real Monday accept through the UI** -- needs user sign-off.

**If the next session is a bug or small feature**, read CHANGELOG's
top entry first for the live snapshot of what works.

**If anomaly detection comes up**, mirror `generate_scope_proposals`:
new prompt version, new `field_name`, supersede-by-project pattern.

---

## 11. Tracking conventions

- Test count in README + ROADMAP is hand-maintained. Update when you
  add tests.
- CHANGELOG is newest-on-top. Each entry has a date + theme + what
  shipped + tests + state at EOD.
- ROADMAP `[ ]` → `[x]` when a phase item ships.  Closed milestones
  get a one-line summary table + a "retrospective" subsection if
  there are footguns / deferred ideas worth preserving.
- Commit messages: imperative, group by concern, mention test count.
- Co-author trailer on Claude commits: `Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>`.
