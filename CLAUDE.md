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
3. Suite + lint green: `pytest -q` (count matches the top CHANGELOG entry) and
   `ruff check .`. Note: whole-repo `ruff format --check .` is NOT green yet —
   formatter activation is a deliberate one-commit ratchet (pyproject +
   CONTRIBUTING). Keep files you *edit* format-clean; do not piecemeal-reformat
   untouched files.
4. `python scripts/doctor.py` — read-only invariant sweep; report any FAIL to
   the user before starting.
5. **Anchor:** quote the active slice's Definition of Done + hard scope limits
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
   mid-planning. `git add <specific files, never -A>`, HEREDOC commit, `git push
   origin main`. If behind, `git fetch origin && git pull --ff-only origin main`
   first. (During a planning/freeze discussion, don't commit until told to.)
4. **Validate on the real system** — from the real repo path, against the real
   workspace. Don't just `pytest` and declare victory. Use the `alta-validate`
   skill: provenance (real data, not your own fixture), reconciliation (an
   independent path agrees, to the penny for money), downstream (smoke the
   nearest consumer). The CHANGELOG entry records the live evidence and the
   honest gaps.
5. **Windows console:** stdout is UTF-8-hardened via `cli.force_utf8_output()`,
   but prefer ASCII (`->`, `OK:`, `FAIL:`, `-`, `...`) for clean rendering.
   One-off scripts you write must call `force_utf8_output()` themselves.
6. **No redundant API calls.** If we synced it, we hold it — query the DB, not
   the source. (e.g. `board_id` is embedded in `ExternalId.external_url`;
   `MondayClient.list_board_columns` is cached per-instance.)
7. **Never commit secrets, `.env`, `*.pyc`, `*.sqlite`.** They're gitignored;
   if `git status` shows them, something is wrong.
8. **Every commit credits Claude:** end the body (via HEREDOC) with
   `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`.
9. **Lint gate:** `ruff check .` GREEN before moving to the next slice, not only
   at the end. Ruff is **pinned** in `project-db/pyproject.toml` (`ruff==0.15.18`)
   — never "fix" code to satisfy an unpinned newer ruff; check the pin first, bump
   it deliberately in its own commit. (Whole-repo `ruff format` is a separate,
   not-yet-activated ratchet — keep edited files format-clean, don't reformat
   untouched ones.)
10. **Schema changes use the custom migration system, not Alembic.** Every new
    table/column needs BOTH the SQLAlchemy model AND a DDL/ALTER block in
    `db/migrations.py::ensure_sqlite_schema`, in FK-dependency order. Additive
    only during transitions; back up the real DB before anything destructive.
    Full checklist: `alta-migrations` skill.
11. **Model tiering (owner decision 2026-06-26):** certainty-requiring LLM
    calls (client-vs-vendor role, quote-vs-worksheet, side inversion, ambiguous
    lifecycle) run on the strong tier — never gpt-4o-mini. Pin model snapshots.
    Confirm credit balances with the owner before any live LLM run.

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
│   └── skills/                   ← alta-preflight, alta-validate, alta-migrations
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
    ├── scripts/doctor.py         ← read-only invariant sweep (preflight step 4)
    └── src/project_db/           ← cli.py, db/, identity/, connectors/, ai/, web/, features.py
```

```bash
cd project-db && python -m pytest tests/ -q     # tests
python scripts/doctor.py                         # invariant sweep (read-only)
project_db serve --no-refresh                    # web UI, no background sync/spend
python scripts/monday_demo.py pull               # full Monday sync
# Feature flags: src/project_db/features.py — override with PROJECT_DB_FEATURE_<NAME>=true
```
