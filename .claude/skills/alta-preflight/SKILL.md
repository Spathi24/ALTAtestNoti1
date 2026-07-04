---
name: alta-preflight
description: Mandatory session-start ritual for the ALTA / project_db repo. Run this at the START of every Claude Code session in ALTAtest, before reading code, planning, or editing anything — even if the user's first message is a task. Also re-run it after any long gap mid-session, after switching branches, or whenever you are unsure of repo state. Triggers include starting work in ALTAtest, "continue the slice", "pick up where we left off", or any first task of a session.
---

# ALTA Session Preflight

Purpose: kill the three recurring session-start failures — working in a
worktree, working from stale facts (drifted test counts / stale HANDOFF), and
starting a slice without its Definition of Done in view.

Run the steps IN ORDER. Do not start the user's task until all steps pass or
the user has explicitly waived a failing one.

## Step 1 — Location & branch (hard gate)

```bash
pwd
git rev-parse --abbrev-ref HEAD
git status --short
```

- cwd must be the real repo (`...\VScode\ALTAtest`), NOT `.claude/worktrees/...`.
  If in a worktree: `cd` back to the real repo. Never create a worktree.
- Branch must be `main`. If behind: `git fetch origin && git pull --ff-only origin main`.
- If `git status` shows `.env`, `*.sqlite`, or `*.pyc` as tracked/staged,
  STOP and report — something is wrong (CLAUDE.md hard rule 7).

## Step 2 — Read order (no skipping)

1. `CLAUDE.md` (root) — rules; it overrides everything.
2. `PROJECT_STATE.md` (root) — Current Focus, Known Bugs, Risks/Drift Warnings.
   If Current Focus links a slice doc (e.g. `EVIDENCE_REFACTOR.md`), open it and
   **quote the active slice's Definition of Done + hard scope limits into your
   plan verbatim** before any edit (owner mandate 2026-06-25).
3. `project-db/docs/HANDOFF.md` — current engineering state.
4. Top entry of `project-db/CHANGELOG.md` — what works today + last test count.

Never read `project-db/docs/archive/` as instructions.

## Step 3 — Interpreter check (the 3.11-vs-3.13 trap)

This machine has TWO Pythons (3.11 = `python` + the `project_db` console
script; 3.13 = `py -3.13`). The project runs on **`python` (3.11)** — use it
for EVERYTHING; never mix in `py -3.13` (real incident: tests "failed" under
one interpreter, the user's CLI died under the other, two days of confusion).

```bash
python --version && python -c "import project_db, openai, openpyxl, anthropic; print('env OK')"
```

If an import fails, the interpreter/env drifted — STOP and report; do not
debug it as a code problem.

## Step 4 — Green base (don't stack work on a broken base)

```bash
cd project-db
python -m pytest tests/ -q
python -m ruff check .
```

- Compare the pytest count to the top CHANGELOG entry. Mismatch = facts have
  drifted; reconcile (update CHANGELOG or investigate) before new work.
- Ruff must be GREEN before continuing (owner lint gate, 2026-06-25). Ruff is
  pinned (`ruff==0.15.18`); if errors appear in files you haven't touched,
  check the pin before "fixing" code. Run checks SEPARATELY — never chain
  pytest and ruff in one command (a trailing lint nit makes a green suite
  read as failed and triggers pointless full re-runs).

## Step 5 — Invariant sweep (fast, read-only)

```bash
python scripts/doctor.py
```

Any FAIL is reported to the user before task work begins; do not silently fix
data. For one-off DB probes use `python scripts/db_probe.py [project]` — its
docstring is the canonical import crib (session_scope, canonical_id, parser
signatures). After ONE traceback from a guessed symbol, Read the source — no
second probe.

## Step 6 — Anchor the session

Before the first edit, state in one short block:
- The active slice + its DoD (verbatim quote).
- What is explicitly OUT of scope this session.
- The self-scrutiny question you will re-ask after every change:
  *"did this save someone time, or did I just make the code more complete?"*

## Post-compaction re-anchor

After any context compaction, treat ALL file knowledge as stale: Read before
every Edit (compaction resets read-state — repeated real incidents), re-verify
cwd with absolute paths, and re-quote the active DoD before continuing.

## Session-end pairing

This skill's mirror obligations at session end: suite green, ruff green, push
approved changes (`git add <specific files>`, never `-A`; commit via the Bash
tool heredoc or `git commit -F <scratch file>` — NEVER a multi-line `-m` in
PowerShell; body ends `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`),
retype HANDOFF if state changed, append CHANGELOG (newest on top, include the
new test count), update PROJECT_STATE's Completed/Current sections.

- **Read before the ritual writes:** HANDOFF.md and CHANGELOG.md must be Read
  in-session before the wipe/append — even for a full retype (7+ real misses).
- **Session-local artifacts:** HANDOFF must list files referenced OUTSIDE the
  repo (e.g. a template in Downloads) and in-conversation decisions not yet in
  any doc — a cold instance floundered for an hour missing exactly these.
- **Deferral ledger:** anything the code deliberately skips (a doc type, a
  project, a side) is written to PROJECT_STATE as "deliberately not ingested:
  X, because Y" — silent deferral caused the worst trust collapse on record.
- **Visible delta:** end every slice with one command or URL the user can run
  to SEE the change, plus a coverage line ("works on N of 22 projects") — or
  an explicit "nothing visible changed, here's why".
