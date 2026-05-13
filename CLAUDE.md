# CLAUDE.md — Working Rules for the ALTAtest / project_db Repo

This file is read at the start of every session. **Read it before touching code.**

---

## What this project is

**ALTAtest / `project_db`** is a centralized data platform that pulls live data
from the company's SaaS tools (Monday.com, QuickBooks, CompanyCam, Google Drive)
into a single canonical Postgres/SQLite database, so we can answer cross-tool
questions — and eventually have an AI assistant answer them in plain English.

**Why it exists:** work, money, and photos are siloed across four tools. There
is no single place to ask things like *"what's the margin on Project X?"* or
*"show me everything for 923 Rockland — tasks, photos, invoices, documents."*

**Architecture in three pieces:**

1. **Canonical schema** — 13 entities (Organization, User, Client, Vendor,
   Property, Lead, Deal, Project, Task, DailyLog, Invoice, Document,
   ExternalId). Every entity has a UUID we own (`canonical_id`). Source-system
   IDs live in the `ExternalId` table, which maps any canonical UUID to one or
   more source records.
2. **Connectors** — one per source system. Each subclasses `BaseConnector` and
   is registered in `connectors/registry.py`. Adding a new source = writing a
   new connector. Currently: Monday (full read + write-back), QuickBooks
   (read).
3. **Identity Resolver** — `resolve_or_create(source, external_key, attrs,
   matcher)` returns the canonical entity, deduping across sources via
   `ExactFieldMatcher`/`FuzzyFieldMatcher`. The matcher is pluggable per
   entity type.

**The repo lives at `C:\Users\nsaro\Documents\VScode\ALTAtest\project-db`.**
That's the only path you write to. Worktrees are off — see below.

---

## Hard rules (the user has asked for these explicitly)

### 1. Edit `main` directly. No worktrees.

The user got burned multiple times by changes living on a `claude/*` branch in
`.claude/worktrees/` while `main` was out of sync. **Stop doing that.**

- `git status` should show you on `main` in
  `C:\Users\nsaro\Documents\VScode\ALTAtest`.
- If you find yourself in `.claude/worktrees/...`, `cd` back to the main repo.
- Never create a new worktree unless the user explicitly asks for one.

### 2. Push to `origin/main` after every meaningful change.

After every fix, feature, or test addition:

```bash
git add <specific files, never -A>
git commit -m "..."     # HEREDOC, include Co-Authored-By
git push origin main
```

Don't accumulate uncommitted work. If `main` falls behind `origin/main` because
the user committed from the GitHub UI or another machine, **pull first** before
making more changes:

```bash
git fetch origin
git pull --ff-only origin main
```

A merge conflict at push time is a failure of this rule.

### 3. Keep the test suite green.

There are **102 tests** in `project-db/tests/`. Before pushing anything that
touches `src/`:

```bash
cd project-db && python -m pytest tests/ -q
```

Expected: `102 passed`. Anything less is a regression — fix it before you push.

If you add a feature, add a test for it. If you change an API surface (renamed
function, new required arg, dropped enum value), update the test that exercises
it.

### 4. Run things on the user's actual system, not on assumptions.

When validating a fix, **actually run the command** the user would run, from
the main repo path, against the real Monday workspace. Don't just `pytest` and
declare victory — the user has called this out by name.

### 5. Windows console = ASCII only in script output.

The default Windows code page is cp1252. Unicode arrows (`→`), bullets (`✓`,
`✗`), box-drawing chars (`─`), and ellipses (`…`) crash with
`UnicodeEncodeError` in scripts the user runs. Use `->`, `OK:`, `FAIL:`, `-`,
`...` in any `print()` that lands in `scripts/` or `cli.py`.

### 6. Don't make redundant API calls.

If we already know something (because we synced it), **don't ask the source
system for it again**. Concrete patterns this project uses:

- `ExternalId.external_url` embeds `board_id` for Monday items
  (`https://view.monday.com/boards/{board_id}/pulses/{item_id}`) so `sync_back`
  parses it locally instead of hitting `items(ids: [...]) { board { id } }`.
- `MondayClient.list_board_columns` is cached per-instance — push N times on
  the same board, fetch columns once.
- Logical column-name resolution (`status` -> `project_status`) lives in
  `MondayConnector._resolve_column_id` and uses the cached column metadata.

When you add a new feature: if it queries an external API for data we already
hold canonically, that's a smell. Cache it or store it during sync.

### 7. Never commit secrets, `.env`, or `*.pyc`.

`.env` is gitignored. If `git status` shows it, something is wrong. Same for
`__pycache__/` and `.sqlite` files — they're already in `.gitignore`.

### 8. Commits and PRs always credit Claude.

Every commit body ends with:

```
Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>
```

Pass commit messages via HEREDOC, never via flags with embedded newlines.

---

## Project layout (where to look)

```
ALTAtest/
├── CLAUDE.md                        ← you are here
├── README.md                        ← top-level project overview
├── docs/                            ← top-level design + planning docs
└── project-db/                      ← the actual Python package
    ├── README.md                    ← user-facing setup + usage docs
    ├── docs/
    │   ├── MONDAY_USAGE.md          ← push/pull/add workflow for Monday
    │   ├── design-v0.1.md
    │   ├── OPTIMIZATION_v0.2.md
    │   ├── adding-a-connector.md
    │   └── ...
    ├── scripts/
    │   └── monday_demo.py           ← interactive push/pull demo CLI
    ├── src/project_db/
    │   ├── cli.py                   ← `project_db ...` entry point
    │   ├── config.py                ← .env loading
    │   ├── db/                      ← SQLAlchemy models + session
    │   ├── identity/                ← resolver + matchers
    │   ├── connectors/
    │   │   ├── base.py              ← abstract BaseConnector
    │   │   ├── registry.py
    │   │   ├── monday/              ← client.py, connector.py, column_extractor.py
    │   │   └── quickbooks/
    │   └── ai/                      ← canned reports + (stub) text-to-SQL
    └── tests/                       ← pytest suite (102 tests)
```

---

## Common tasks

### Run the test suite
```bash
cd project-db && python -m pytest tests/ -q
```

### Sync Monday data
```bash
cd project-db
project_db init-db                   # one-time
python scripts/monday_demo.py pull   # full Monday sync
python scripts/monday_demo.py inspect
```

See [`project-db/docs/MONDAY_USAGE.md`](project-db/docs/MONDAY_USAGE.md) for
the complete Monday push/pull workflow including writing changes back to
Monday.

### Add a new connector
See [`project-db/docs/adding-a-connector.md`](project-db/docs/adding-a-connector.md).
Pattern: subclass `BaseConnector`, register in `connectors/registry.py`, add an
entry to `SourceSystem` enum, write tests, run `pytest`, push.

---

## Status (v0.2)

Done:
- Canonical schema (13 entities) + identity resolver with fuzzy match.
- Monday connector: full board/item read + column extraction + push (`sync_back`).
- QuickBooks connector: customers, invoices, estimates.
- 102-test suite.
- Demo CLI: `list-boards`, `pull`, `inspect`, `push`, `add-item`.

Next:
- CompanyCam connector.
- Google Drive connector.
- Webhook receivers (replace polling).
- Text-to-SQL AI layer over canonical schema.
- Postgres + Alembic migrations.
