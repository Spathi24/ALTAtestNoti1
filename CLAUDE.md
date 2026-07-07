# CLAUDE.md — Operating Rules for ALTA / project_db

Read this first, every session, before touching code or docs. **This file
overrides every other doc.** If another file contradicts it, this wins — fix or
archive the other file.

---

## Session preflight (do this before ANY edit)

Run the `alta-preflight` skill, or manually:

1. `pwd` + branch check: real repo path, on `main`, **never** a
   `.claude/worktrees/...` path. `git status` clean of `.env`/`*.sqlite`/`*.pyc`.
2. Read in order: this file → `PROJECT_STATE.md` (root) → active slice doc if
   one is linked → `project-db/docs/HANDOFF.md` → top `CHANGELOG.md` entry.
3. Interpreter: `python --version` is 3.11 and
   `python -c "import project_db, openai, openpyxl"` works (rule 12).
4. Suite + lint green: `python -m pytest tests/ -q` (count matches the top
   CHANGELOG entry) and `python -m ruff check .` — run them as SEPARATE
   commands so exit codes mean something.
5. `python scripts/doctor.py` — read-only invariant sweep; report any FAIL to
   the user before starting.
6. **Anchor:** quote the active slice's Definition of Done + hard scope limits
   verbatim into your plan. Re-read them mid-slice. One slice per session; at
   any limitation, park it in HANDOFF and STOP.

---

## The one metric: time saved

ALTA exists to **save real people real hours.** That is the only success metric.
Not feature count. Not data completeness. Not "centralize Monday + Drive" — that
is a sync problem Zapier solves for $20/mo, and if that's all we're doing we
should stop.

The owner's words, kept verbatim because they are the north star:

> "The point is that the AI needs to advance automation and time saving... How
> much time can we save? We need to isolate what people spend most of their time
> on."

So before any work, the question is: **whose time does this save, on what task,
and how would we know?** If you can't answer concretely, don't build it.

**Leading value hypotheses** (to validate against real usage, NOT a mandate to
build a subsystem for each): the two biggest variable-cost leaks the owner wants
watched are (1) **Home Depot daily purchases** (Home Depot Pro account) and
(2) **hourly labour** — both overrunning project budget.

---

## The usage gate (definition of done)

Work is "done" when **a real person uses ALTA for a real task and comes back to
it** — not when the code is complete or the tests pass.

**Financial gate (settled 2026-06-30, pilot = 923 Rockland / project code `2026001`):**
For the pilot project, the owner/PM can open ALTA — not Drive — and accurately see:
budget vs committed cost vs actual spend; quoted vs actual by trade/package; selected
quotes; unresolved variable costs; current over/under status; forecasted cost exposure.
Success means ALTA becomes trusted as the financial source of truth and the owner/PM
comes back to it the following week without being prompted.

---

## BUILD FREEZE (the rule that breaks the loop)

This project has a documented failure mode: limitation found → new authoritative
doc → new subsystem → partial success → new limitation → repeat. Half-working
features pile onto a half-working product. **We are breaking that loop.**

- **No new features or subsystems** until the current visible spine meets the
  usage gate. The only allowed work is making the existing path *trustworthy*.
- **When you hit a limitation: note it in HANDOFF's "Parked" section and STOP.**
  A limitation is not a mandate to build. Ask: does the current user need this
  for the current task? Usually no.
- **Self-scrutiny (required after every change):** ask *"did this save someone
  time, or did I just make the code more complete?"* If the latter, you're in
  the loop — stop and say so out loud.
- **Visible delta or say so:** every slice ends with one command or URL the
  user can run to SEE the change (plus a coverage line — "works on N of 22
  projects"), or an explicit "nothing visible changed, here's why". Green
  tests are invisible to the owner; that gap caused the worst trust collapse
  on record (06-19).
- **No silent deferral:** anything the code deliberately skips (a doc type, a
  project, a side of the ledger) is recorded in PROJECT_STATE as "deliberately
  not ingested: X, because Y" the moment the decision is made.
- **Pilot examples are examples, not the target distribution.** The owner's
  standing words (06-19): *"just because I gave rockland projects as examples
  doesnt mean that OVERFITTING is the right answer."* Validate on the hardest
  real doc, not the friendliest fixture.
- Hidden features (`src/project_db/features.py`) stay hidden until a real user
  asks for one by name. Hiding is reversible (env var); it is not deletion.

---

## Documentation discipline (so docs stop steering us wrong)

The docs became a steering wheel: every entry declared itself "the new core / the
next build," and each session patched toward the latest one. Fixed by collapsing
to **four canonical files, present-tense only:**

| File | Role | Lifecycle |
|---|---|---|
| `CLAUDE.md` (this) | Rules + philosophy + the gate | Edit deliberately, rarely |
| `project-db/README.md` | What it is + how to set up & run | Update when setup changes |
| `project-db/docs/HANDOFF.md` | Current engineering state only | **Wiped & retyped every handoff** |
| `project-db/CHANGELOG.md` | Dated history, newest on top | **Never wiped — append only** |

**Durable working memory (owner-mandated 2026-06-25, repo root):**
`PROJECT_STATE.md` is the cross-session scratch/decision log (known bugs,
decisions, plans, risks, model observations) the four present-tense files don't
keep — read it at session start. A large multi-slice initiative gets ONE
dedicated plan+state doc (e.g. `EVIDENCE_REFACTOR.md`) with finishing
conditions, linked from `PROJECT_STATE.md`. These are working memory, not
"next build" authority docs — keep them honest and current, don't let them
ossify into mandates.

Rules:
- **Write present-tense facts, not "next build" declarations.** No roadmaps, no
  "this is now the headline," no new strategy/authority docs. Forward ideas go in
  HANDOFF's "Parked / open questions" section — which gets wiped, so they don't
  ossify into commitments.
- **`project-db/docs/archive/` is history, NOT instructions.** Do not steer from
  it. It exists so nothing is lost, not so future sessions obey it.
- If a doc contradicts reality, fix it or archive it. **Do not add a fifth
  canonical/strategy doc** to reconcile the other four. (The root working-memory
  docs above are the sanctioned exception — they record state, not authority.)
- **External-LLM pastes get distilled, not ingested.** When the user pastes a
  long plan authored with another model, distill it to <=10 bullet decisions in
  PROJECT_STATE.md (or the active slice doc) and work from those — re-reasoning
  over multi-page pastes burns context and accelerates compaction. If it
  contradicts an architecture invariant, say so instead of absorbing it.

### Document authority hierarchy (which wins when two disagree)

Highest to lowest. If two files conflict at different levels, **surface the
conflict before editing** — do NOT silently rewrite several docs "for
consistency" (a known failure mode with cheaper models).

1. `CLAUDE.md` — operational / repo invariants (this file).
2. `docs/MEETING_SYNTHESIS_financial_refoundation.md` — business/product authority.
3. `docs/REFOUNDATION_BUILD_NOTES.md` — implemented semantic rules, migration
   reality, permanent financial invariants.
4. `docs/architecture/FINANCIAL_SPINE_MAP.md` — target architecture/context map
   (living map, NOT a schema mandate).
5. active initiative plan (e.g. `docs/architecture/SCOPECONTEXT_TRANSITION_PLAN.md`)
   — current local execution/migration plan.
6. `docs/UI_REFOUNDATION.md` — UI initiative contract.
7. `PROJECT_STATE.md` — distilled current decisions/state.
8. `HANDOFF.md` — immediate completed/next execution state.
9. `docs/architecture/*.ump` — visualization only; never an authority alone.

An implementation discovery may update **HANDOFF, PROJECT_STATE, and the active
initiative plan.** It does **not** license broadly rewriting CLAUDE.md,
MEETING_SYNTHESIS, REFOUNDATION_BUILD_NOTES, or FINANCIAL_SPINE_MAP — change an
authority/architecture doc only when a *settled semantic decision actually
changed*, and say so.

### Financial-spine slice read pack + preflight (mandatory)

Assume NO implicit conversational context (a cheaper model may run the slice).
Continuity comes from reading files, not memory. Before EVERY financial-spine
implementation slice, read — in order: (1) `CLAUDE.md`, (2) `PROJECT_STATE.md`,
(3) `HANDOFF.md`, (4) the active initiative plan, (5) `FINANCIAL_SPINE_MAP.md`;
then the **relevant sections only** of (6) `MEETING_SYNTHESIS…`, (7)
`REFOUNDATION_BUILD_NOTES` (permanent rules + migration discipline + current
state); (8) `NAMING_CONVENTIONS.md` if Drive/filename/XLSX ingestion is touched;
(9) `UI_REFOUNDATION.md` if any visible surface / UI-facing report contract is
touched; then the slice-specific code: the models owning the touched entities,
their migration blocks, **every writer/ingester and every current
consumer/report/UI surface** found by grep (do not assume), the relevant targeted
tests, and the commits that established the previous slice. Then emit a compact
**PREFLIGHT** before editing: `FILES READ · CURRENT INVARIANTS ·
ENTITIES/WRITERS TOUCHED · CURRENT CONSUMERS · SLICE WRITES · MUST NOT TOUCH ·
KNOWN RISKS · TARGETED TESTS · REAL-DB VERIFICATION`. Only then implement. Do not
read the whole repo blindly; search for every affected entity/writer/consumer.
(The `alta-preflight` skill covers the generic session start; this is the
per-slice, financial-spine-specific read pack.)

---

## Hard rules (still load-bearing)

1. **Edit `main` directly. No worktrees.** Be on `main` in
   `C:\Users\nsaro\Documents\VScode\ALTAtest`. If you find yourself in
   `.claude/worktrees/...`, `cd` back. Never create a worktree unless asked.
   (A PreToolUse hook in `.claude/hooks/guard_bash.py` enforces this and the
   `git add -A` ban mechanically — do not remove it.)
2. **Keep the test suite green.** `cd project-db && python -m pytest tests/ -q`.
   Current count lives at the top of CHANGELOG — do not hardcode it here. Add a
   test with every behavior change; update tests when an API surface changes.
3. **Push to `origin/main` after every meaningful, *approved* change** — not
   mid-planning. `git add <specific files, never -A>`, then commit **via the
   Bash tool with a heredoc, or `git commit -F <scratch file>` — NEVER a
   multi-line `-m` in PowerShell** (its quoting shreds the message into
   pathspecs; ~10 recorded failures). `git push origin main`. If behind,
   `git fetch origin && git pull --ff-only origin main` first. (During a
   planning/freeze discussion, don't commit until told to.)
4. **Validate on the real system** — from the real repo path, against the real
   workspace. Don't just `pytest` and declare victory. Use the `alta-validate`
   skill: provenance (real data, not your own fixture), reconciliation (an
   independent path agrees, to the penny for money), downstream (smoke the
   nearest consumer). The CHANGELOG entry records the live evidence and the
   honest gaps.
5. **Windows console & shells:** stdout is UTF-8-hardened via
   `cli.force_utf8_output()`, but prefer ASCII (`->`, `OK:`, `FAIL:`, `-`,
   `...`) for clean rendering. One-off scripts you write must call
   `force_utf8_output()` themselves. Known artifacts: in PowerShell 5.1,
   piping a native CLI into `Select-Object -First N` (or similar) returns
   exit 255/1 with CORRECT output — don't chase it as a failure; and Unix-isms
   (`tail`, `head`, heredocs, `&&`) belong in the Bash tool, not PowerShell.
   One-off scripts >15 lines go to a scratchpad `.py` file, not an inline
   shell string; anything scanning the full corpus/DB runs in the background
   (foreground commands die at 120s).
6. **No redundant API calls.** If we synced it, we hold it — query the DB, not
   the source. (e.g. `board_id` is embedded in `ExternalId.external_url`;
   `MondayClient.list_board_columns` is cached per-instance.)
7. **Never commit secrets, `.env`, `*.pyc`, `*.sqlite`.** They're gitignored;
   if `git status` shows them, something is wrong.
8. **Every commit credits Claude:** end the body (via HEREDOC) with
   `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`.
9. **Lint gate:** `ruff check .` and `ruff format --check .` GREEN before
   moving to the next slice, not only at the end (formatter activated
   repo-wide 2026-07-04; the commit SHA is in `.git-blame-ignore-revs`).
   Ruff is **pinned** in `project-db/pyproject.toml` (`ruff==0.15.18`) —
   never "fix" code to satisfy an unpinned newer ruff; check the pin first,
   bump it deliberately in its own commit. Lint the files you touch as you
   go; never chain pytest+ruff in one command.
10. **Schema changes use the custom migration system, not Alembic.** Every new
    table/column needs BOTH the SQLAlchemy model AND a DDL/ALTER block in
    `db/migrations.py::ensure_sqlite_schema`, in FK-dependency order. Additive
    only during transitions; back up the real DB before anything destructive.
    Full checklist: `alta-migrations` skill.
11. **Model tiering (owner decision 2026-06-26):** certainty-requiring LLM
    calls (client-vs-vendor role, quote-vs-worksheet, side inversion, ambiguous
    lifecycle) run on the strong tier — never gpt-4o-mini. Pin model snapshots.
    Confirm credit balances with the owner before any live LLM run.
12. **One interpreter: `python` (3.11).** This machine also has `py -3.13`;
    mixing them caused phantom "missing package" failures and a user-facing
    CLI breakage. Use `python` / `python -m` for everything; if an import
    fails, suspect the interpreter before the code. Preflight asserts it.
13. **Credit discipline (owner mandate, repeated 06-01→07-04):** the owner
    works on a limited credit budget and work has HARD-STOPPED on empty
    balances at least five times. Therefore: (a) bulk/corpus AI work is NEVER
    Claude-subagent fan-out — write a one-shot OpenAI-API script (pattern:
    `scripts/reconcile_financials_llm.py`, Batch API when possible); (b) any
    background agent/workflow or batch LLM run needs a stated cost estimate
    and an explicit yes first; (c) dev/test paths default to the mock
    provider; (d) when the user signals low credits, switch to terse,
    single-pass execution — no exploratory loops; (e) before any operation
    that outlives a turn, commit + write state to disk first, so a mid-run
    credit death loses nothing.
14. **External-service automation needs a written go/no-go.** Any automation
    that logs into or scrapes a third-party service with real company
    credentials requires the risk stated and the user's explicit yes BEFORE
    building; ONE bot-detection signal (challenge, reset, captcha) = full
    stop, no retry. (Home Depot bot incident, 2026-06-23.)

---

## Architecture invariants (don't relitigate)

- **The schema is right** (13 entities + `ExternalId` bridge). Don't redesign it.
- **`Project` is the join nucleus.** Never merge a Monday item with a Drive file;
  link them by shared `project_id`. The Drive folder is the source of truth for
  *which project* a document belongs to.
- **The LLM is an advisor, never an actor.** Every AI suggestion goes to the
  `Proposal` table for human approval before any write-back. One source of truth
  per entity for writes (Monday → Tasks/Projects, Drive → Documents).
- **Stay relational / SQL + SQLite.** No graph DB, no vector DB service, no
  Postgres, no new tech until SQL actually limits us.

### Refoundation plan (owner+PM, 2026-06-29) — read before big finance/parser work

The financial spine is now the owner's **#1** ("financing → costing → receivables
is the first win"). Full plan: `docs/MEETING_SYNTHESIS_financial_refoundation.md`
(authoritative; kept in repo). Distilled invariants: `PROJECT_STATE.md` →
"REFOUNDATION PLAN". The load-bearing through-line: **structure & traceability
over prediction** — every cost traces SOW item → package → quote → PO → budget →
actual; the Alta-number estimator is **parked**. Direction shifts that bind future
work: the **deterministic grid parser is the primary path**; evidence/LLM tolerance
(Docling/LLM) is the **fallback for legacy/third-party docs** (keep, demote). The
product value is the **per-division line-item material/labour split, not aggregate
totals**. Do **not** over-invest in `folder_path` project attribution or quote-status
guessing — SOPs (`job_number`, one status vocabulary) will supersede both. New
entities (SowItem/SowPackage/SubcontractorQuote/PurchaseOrder/ChangeOrder,
`FinancialLineItem.purchase_type`/`cost_status`, `Project.job_number`) are **build-
later** — structure current work to fit them; don't pre-empt with large permanent
changes before conventions are settled with the owner.

---

## Layout & common commands

```
ALTAtest/
├── CLAUDE.md                     ← this file (rules + philosophy)
├── .claude/
│   ├── settings.json             ← hooks wiring (SessionStart + Bash guard)
│   ├── hooks/                    ← guard_bash.py, session_start.py
│   └── skills/                   ← alta-preflight, alta-validate, alta-migrations, alta-finance-domain
├── docs/                         ← external API references (Monday, Drive) — keep
└── project-db/                   ← the Python package
    ├── README.md                 ← what it is + setup/usage
    ├── CHANGELOG.md              ← dated history (never wipe)
    ├── pyproject.toml            ← deps + ruff/mypy config (ruff pinned)
    ├── docs/
    │   ├── HANDOFF.md            ← current state (wiped each handoff)
    │   ├── adding-a-connector.md ← how-to
    │   └── archive/              ← history, NOT instructions
    ├── scripts/monday_demo.py    ← interactive Monday push/pull CLI
    ├── scripts/doctor.py         ← read-only invariant sweep (preflight step 5)
    ├── scripts/db_probe.py       ← canonical read-only DB probe + import crib
    └── src/project_db/           ← cli.py, db/, identity/, connectors/, ai/, web/, features.py
```

```bash
cd project-db && python -m pytest tests/ -q     # tests
python scripts/doctor.py                         # invariant sweep (read-only)
project_db serve --no-refresh                    # web UI, no background sync/spend
python scripts/monday_demo.py pull               # full Monday sync
# Feature flags: src/project_db/features.py — override with PROJECT_DB_FEATURE_<NAME>=true
```
