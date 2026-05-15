# CLAUDE.md — Working Rules for the ALTAtest / project_db Repo

This file is read at the start of every session. **Read it before touching code.**

---

## Strategic Direction (READ FIRST)

The full strategic mission lives in
[`project-db/docs/STRATEGY.md`](project-db/docs/STRATEGY.md). Read it before
any non-trivial planning conversation. The short version:

**ALTA is a contractor operations brain, not a sync tool.** Framed as
"centralize Monday + Drive," this project is redundant with Zapier. Framed as
"use LLMs to reconcile what contracts promised against what Monday says is
happening, and propose corrections" — it is genuinely novel and worth
building.

**Operating principles** (the 10-point list from STRATEGY.md — apply these
when choosing what to build):

1. The schema is right. Don't redesign it.
2. `Project` is the join nucleus. Never merge a Monday item with a Drive file —
   link them via shared `project_id`.
3. One source of truth per entity type for writes (Monday → Tasks/Projects/CRM,
   Drive → Documents, QB → Invoices). Reads everywhere; writes one direction.
4. Keep everything. Promote queryable fields to columns; dump the rest in
   `source_meta_json`.
5. The LLM is an advisor, never an actor. All AI proposals go to a
   `Proposal` table for human approval before any write-back.
6. Tier-one (canned reports) before tier-two (LLM).
7. No new connectors until Monday+Drive produce daily PM-facing value.
   CompanyCam and live QuickBooks are deferred.
8. No new tech yet — no graph DB, no Elasticsearch, no Postgres, no pgvector,
   no text-to-SQL. Add them when SQL limits actually bite.
9. The success test is **adoption**, not feature count. If a PM opens this
   system before opening Monday, it's working.
10. Stop building plumbing. Start building the brain.

**Current focus per STRATEGY.md:** content extraction from Drive documents
(PDFs, Docs, DOCX, Excel) into a `DocumentText` sidecar table, then an LLM
layer that proposes task timelines and scope reconciliations, gated by a
`Proposal` table with human approval before write-back to Monday.

---

## What this project is

**ALTAtest / `project_db`** is a centralized data platform that pulls live data
from the company's SaaS tools (Monday.com, QuickBooks, CompanyCam, Google Drive)
into a single canonical Postgres/SQLite database, so we can answer cross-tool
questions — and eventually have an AI assistant answer them in plain English.

**Why it exists:** work, money, and photos are siloed across four tools. There
is no single place to ask things like *"what's the margin on Project X?"* or
*"show me everything for 923 Rockland — tasks, photos, invoices, documents."*

**What it really is** (per STRATEGY.md): an LLM-powered operations brain that
reconciles the contract (Drive) against the operational state (Monday) and
proposes corrections. The sync is plumbing; the reconciliation is the product.

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

There are **245+ tests** in `project-db/tests/` (the count grows; check
the latest pass line in CHANGELOG.md if you need a precise number).
Before pushing anything that touches `src/`:

```bash
cd project-db && python -m pytest tests/ -q
```

Expected: every test passes. Anything less is a regression — fix it before you push.

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

## Status (v0.2, as of 2026-05-14)

Done:
- Canonical schema (13 entities) + identity resolver (exact + fuzzy).
- Monday connector: full board/item read + column extraction + push (`sync_back`).
- Mirror-column overlay: pulls status/timeline from portfolio items that
  proxy task-board values.
- QuickBooks connector code complete (live test still pending real creds).
- **Google Drive connector live**: 750 documents synced with full metadata
  (folder_path, modified_time, size, md5, owner, etc.), 300 linked to
  canonical Projects via civic-number + name matching.
- One consolidated SQLite location (`project-db/project_db.sqlite`,
  absolute path in `.env`).
- **Phase 1 (Brain foundation) done:** DocumentText sidecar + Proposal
  table + content extractors (PDF / DOCX / XLSX / Google Docs+Sheets),
  `extract-content` CLI, Drive sync reconciliation. 463/751 documents
  have non-empty extracted text in the live DB.
- **Phase 2 (Tier-1 reports) done:** `project_overview`,
  `docs_for_project`, `tasks_without_dates`, `missing_documents`,
  `budget_vs_contract` reachable via `project_db ask "..."`.
  Run `project_db ask "help"` to see all routed patterns.
- 250+-test suite (see CHANGELOG.md for precise current count).
- Demo CLI: `list-boards`, `pull`, `inspect`, `push`, `add-item`,
  `gdrive-auth`, `extract-content`, `ask`.

Known limits / non-features (do not pretend otherwise):
- **Sync is full-pull only for Monday.** Monday API-Version 2026-07 removed
  `updated_after` from `items_page`. The old `_get_last_sync_time` was theatre
  and got removed on 2026-05-14. True incremental sync = webhook work.
  Drive does have genuine `changes.list` delta sync via stored cursor.
- **QB connector has never been run live.** Invoice table is empty in dev.
  **Deferred per STRATEGY.md** — do not pick this up until Monday+Drive are
  in daily PM use.
- **Task data is sparse.** Only ~11% of Monday tasks have a date/duration
  filled in. This is the *exact problem the AI layer is meant to solve*
  (read Drive contracts → propose dates for Monday tasks). Not a bug to
  fix in Monday; a feature to build in ALTA.
- **AI assistant is canned-reports only.** Tier 2 (LLM-driven proposals) is
  the next big build, per STRATEGY.md.

Next (in priority order per STRATEGY.md):
1. **`DocumentText` sidecar table + content extraction** for PDFs, Google
   Docs, DOCX, Excel. Cap at 10 MB per file. Skip HEIC, DWG, audio.
2. **`Proposal` table** for LLM-generated suggestions (entity_type,
   entity_id, field, proposed_value, confidence, source_doc_ids, status).
   All AI writes flow through here, gated by human approval.
3. **LLM timeline-filling**: given a Project + its `DocumentText`, propose
   `start_date` / `end_date` / `duration_days` for tasks lacking them.
4. **LLM scope reconciliation**: compare contract scope (Drive text) to
   Monday task list, flag missing items.
5. **Approval workflow CLI**: `project_db proposals list`, `accept`,
   `reject`. Accepted proposals → write back to Monday via existing
   `sync_back`.

Explicitly NOT next (per STRATEGY.md):
- CompanyCam connector
- QB live integration
- Text-to-SQL natural language layer
- Postgres migration / Alembic
- Webhook receivers
- Any new source system

These are real items but they're plumbing. The brain (#1-5 above) comes first.
