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

## Step 3 — Green base (don't stack work on a broken base)

```bash
cd project-db
python -m pytest tests/ -q
python -m ruff check . && python -m ruff format --check .
```

- Compare the pytest count to the top CHANGELOG entry. Mismatch = facts have
  drifted; reconcile (update CHANGELOG or investigate) before new work.
- Ruff must be GREEN before continuing (owner lint gate, 2026-06-25). If ruff
  errors appear in files you haven't touched, suspect ruff version drift
  (`ruff>=0.5` was unpinned) — check the pin before "fixing" code.

## Step 4 — Invariant sweep (fast, read-only)

```bash
python scripts/doctor.py
```

If `doctor.py` doesn't exist yet, skip with a note. Any FAIL is reported to the
user before task work begins; do not silently fix data.

## Step 5 — Anchor the session

Before the first edit, state in one short block:
- The active slice + its DoD (verbatim quote).
- What is explicitly OUT of scope this session.
- The self-scrutiny question you will re-ask after every change:
  *"did this save someone time, or did I just make the code more complete?"*

## Session-end pairing

This skill's mirror obligations at session end: suite green, ruff green, push
approved changes (`git add <specific files>`, never `-A`; HEREDOC commit ending
`Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`), retype HANDOFF if
state changed, append CHANGELOG (newest on top, include the new test count),
update PROJECT_STATE's Completed/Current sections.
