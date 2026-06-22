# HANDOFF — current engineering state

**This file is wiped and retyped at every handoff.** It holds ONLY what is true
*right now*. History → `../CHANGELOG.md`. Rules & philosophy → `../../CLAUDE.md`
(read it first; it overrides everything).

Last retyped: 2026-06-22.

---

## Where things stand (the honest summary)

The project is in a **deliberate build-freeze + documentation reset** (see
CLAUDE.md). We are NOT adding features. The active work is:
1. Collapse the docs to the four-file canon (this reset). **Done this session.**
2. Settle the *time-saved* usage gate with the owner (whiteboard in progress).
3. Decide which built-but-hidden features earn re-exposure — driven by real use,
   not by completeness.

**Git:** on `main`, level with `origin/main`. The feature-flag quarantine + this
doc reset are **uncommitted working-tree changes** — GitHub still holds the full,
fully-exposed build as the fallback. Nothing is lost.

**Tests:** see the top of CHANGELOG (~1324 passing as last recorded).

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
