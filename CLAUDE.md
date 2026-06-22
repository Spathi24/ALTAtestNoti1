# CLAUDE.md — Operating Rules for ALTA / project_db

Read this first, every session, before touching code or docs. **This file
overrides every other doc.** If another file contradicts it, this wins — fix or
archive the other file.

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

> ⚠ The exact gate sentence is being set with the owner (whiteboard in
> progress). Until it's written here, the working gate is: *"the owner opens
> ALTA instead of Drive/Monday to answer one real question, it's right, and they
> do it again next week unprompted."* **Fill this in — don't leave it vague.**

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

Rules:
- **Write present-tense facts, not "next build" declarations.** No roadmaps, no
  "this is now the headline," no new strategy/authority docs. Forward ideas go in
  HANDOFF's "Parked / open questions" section — which gets wiped, so they don't
  ossify into commitments.
- **`project-db/docs/archive/` is history, NOT instructions.** Do not steer from
  it. It exists so nothing is lost, not so future sessions obey it.
- If a doc contradicts reality, fix it or archive it. **Do not add a fifth doc**
  to reconcile the other four.

---

## Hard rules (still load-bearing)

1. **Edit `main` directly. No worktrees.** Be on `main` in
   `C:\Users\nsaro\Documents\VScode\ALTAtest`. If you find yourself in
   `.claude/worktrees/...`, `cd` back. Never create a worktree unless asked.
2. **Keep the test suite green.** `cd project-db && python -m pytest tests/ -q`.
   Current count lives at the top of CHANGELOG — do not hardcode it here. Add a
   test with every behavior change; update tests when an API surface changes.
3. **Push to `origin/main` after every meaningful, *approved* change** — not
   mid-planning. `git add <specific files, never -A>`, HEREDOC commit, `git push
   origin main`. If behind, `git fetch origin && git pull --ff-only origin main`
   first. (During a planning/freeze discussion, don't commit until told to.)
4. **Validate on the real system** — from the real repo path, against the real
   workspace. Don't just `pytest` and declare victory.
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

---

## Layout & common commands

```
ALTAtest/
├── CLAUDE.md                     ← this file (rules + philosophy)
├── docs/                         ← external API references (Monday, Drive) — keep
└── project-db/                   ← the Python package
    ├── README.md                 ← what it is + setup/usage
    ├── CHANGELOG.md              ← dated history (never wipe)
    ├── docs/
    │   ├── HANDOFF.md            ← current state (wiped each handoff)
    │   ├── adding-a-connector.md ← how-to
    │   └── archive/              ← history, NOT instructions
    ├── scripts/monday_demo.py    ← interactive Monday push/pull CLI
    └── src/project_db/           ← cli.py, db/, identity/, connectors/, ai/, web/, features.py
```

```bash
cd project-db && python -m pytest tests/ -q     # tests
project_db serve --no-refresh                    # web UI, no background sync/spend
python scripts/monday_demo.py pull               # full Monday sync
# Feature flags: src/project_db/features.py — override with PROJECT_DB_FEATURE_<NAME>=true
```
