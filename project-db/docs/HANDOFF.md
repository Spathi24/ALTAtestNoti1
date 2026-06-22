# HANDOFF — current engineering state

**This file is wiped and retyped at every handoff.** It holds ONLY what is true
*right now*. History → `../CHANGELOG.md`. Rules & philosophy → `../../CLAUDE.md`
(read it first; it overrides everything).

Last retyped: 2026-06-22.

---

## Where things stand (the honest summary)

The project is in a **deliberate build-freeze + documentation reset** (see
CLAUDE.md). The chosen first build (it passes the time-saved gate: the bosses
review cross-project change weekly to make decisions) is the **weekly
per-project report**. Build #1 (the deterministic delta) is done; the narration
layer is next.

**Git:** on `main`, pushed to `origin/main`. The full, fully-exposed pre-reset
build is frozen on the **`full-exposed-build`** branch as the fallback. The doc
reset, the feature-flag quarantine, and weekly-report build #1 are committed.

**Tests:** see the top of CHANGELOG (1394 passing as last recorded).

**Active build — weekly report:** Both layers complete and tested.

`report_weekly_changes` (`ai/views.py`) — content-complete deterministic delta:
- Documents: `DocumentText.extracted_text` included (3 000-char cap per doc)
- Field notes: full `raw_text` (was truncated to 200 chars)
- Proposals: `proposed_value` parsed from JSON (the actual suggested value)
- Tasks: all schedule fields (start/end/due, group, subcontractor)
- `events`: all items merged into one chronological list per project
- `prior_window`: counts from the previous N days for trajectory context

`narrate_weekly_report` (`ai/views.py`) — LLM narration using the events list:
- Passes the chronological `events` list (not separate lists) to the provider
- Includes `prior_week` counts for trajectory narrative
- 2 000-token budget (was 300 -- that was a metadata stub, not a report)
- Zero-change projects get hard-coded text, no LLM call

CLI: `weekly-changes [project] [--days N] [--narrate] [--sync]`
- `--narrate`: calls fast provider (OpenAI currently, Anthropic when credits available)
- `--sync`: runs Drive + Monday connector sync first so data is current

Documented limits: financial rows excluded (ledger rebuilt on each fill-ledger
run → `created_at` is noisy); "newly filed but Drive-old" docs not caught
(only `modified_at_source` used, which is wipe-proof); prior-window counts for
proposals are approximate (polymorphic attribution at prior-window time).

---

## What's visible vs hidden right now

A feature-flag layer (`src/project_db/features.py`) decides what's reachable. It
is purely presentational — no schema, parser, or stored data was changed. Flip
any flag with `PROJECT_DB_FEATURE_<NAME>=true`.

- **Visible spine (default on):** core, `ask`, `search`, `proposals`, typed field
  notes, finance margins (`FinancialLineItem`), ledger health.
- **Hidden (default off, fully built, reversible):** email/photo field notes,
  legacy financials (`FinancialRecord`), obligations / money-at-risk,
  value-caught, project-logs, labour intake, Telegram intake, Monday Gantt,
  roadmap, LLM PDF finance, lead-gen, admin nav, batch proposal generation,
  manual task-date edit.

---

## Subsystem reality (present tense, no spin)

- **Financial / margins:** `FinancialLineItem` (division-keyed, per-unit) is the
  current ledger; a deterministic grid parser reconciles Rockland-style quote
  spreadsheets to the penny. **It is NOT portfolio-useful yet** — most other
  projects' money lives in PDFs / simple-estimate / job-cost sheets the grid
  parser doesn't read, and the **cost side is essentially absent**, so margins
  show `revenue_only`. Legacy `FinancialRecord` remains as a transition net.
- **Labour intake (Telegram/Gmail):** built and technically live, but **blocked
  on adoption** — nobody is reliably logging labour, so there is nothing to
  reconcile. Hidden.
- **Providers / budget:** LLM calls route through a fallback provider (Anthropic
  primary, OpenAI backup). **Confirm current credit balances with the owner
  before any live LLM run** — last recorded as very low. Develop on mocks.
- **Tier-1 reports + RAG + attention briefing:** built and working; the passive
  read/reconcile story.

---

## Parked / open questions (NOT a roadmap — do not build without the gate)

- **The usage-gate sentence** — owner is whiteboarding it. This unblocks
  everything. Settle it first.
- **Which product to be:** *passive truth layer* (reads docs that already exist —
  validatable by the owner alone, no adoption bet) vs *active operations layer*
  (labour, field-note → Monday — depends on other people changing habits).
  Current lean: passive first.
- **Financial re-architecture idea** (owner + ChatGPT; reference preserved in
  `archive/FINANCIAL_REDESIGN.md`): AI *classifies* documents/sheets first
  (structured output), deterministic code *validates & writes* second; emit a
  per-document audit ("what is this, can it be counted, why") BEFORE any
  margin/money-at-risk view. **Do not start building until the gate is set and
  this is the chosen lane.**
- **Home Depot purchases + hourly labour** as the two budget-overrun watch
  targets — leading value hypotheses, unvalidated.

---

## If you are a fresh Claude instance

1. Read `../../CLAUDE.md`. Honor the build freeze.
2. Read the top CHANGELOG entry for "what works today."
3. Do not resurrect anything in `archive/` as instructions.
4. Before building anything, answer: *whose time does this save, and how will we
   know?* If you can't, stop and ask.
