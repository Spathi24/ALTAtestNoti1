# ALTA / project_db — Work Log

A day-by-day journal of what was built, what works, and how the project's
capability grew. Newest entry on top. Lower-level "what changed" detail
is in commit messages; this is the human-readable version.

If you want **"what can this product do today?"** read the top entry.
If you want **"how did we get here?"** read top to bottom.

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

See **[docs/ROADMAP.md M5 RETROSPECTIVE](docs/ROADMAP.md)** for the
extended writeup: what worked, footguns to know about, ideas
revisited later, and the path forward.

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
