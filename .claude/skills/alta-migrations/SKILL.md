---
name: alta-migrations
description: Schema-change ritual for ALTA / project_db's CUSTOM migration system (db/migrations.py::ensure_sqlite_schema — this repo does NOT use Alembic). Use whenever adding or altering a table, column, index, or FK; whenever creating a new SQLAlchemy model; or whenever a migration must be applied to the real project_db.sqlite. Trigger on words like "new table", "add column", "model", "migration", "schema".
---

# ALTA Schema Changes

The migration system is hand-rolled. Alembic instincts will break existing
local databases. Follow this checklist exactly.

## Dual registration (the rule that gets missed)

Every new table needs BOTH:
1. A **SQLAlchemy model** (in `src/project_db/db/models/`) — serves
   `create_all` on fresh DBs. Export it from `models/__init__.py`.
2. A **DDL block wired into `db/migrations.py::ensure_sqlite_schema`** —
   serves existing local SQLite files that `create_all` won't touch.

New columns on existing tables need the model attribute AND an `ALTER TABLE
... ADD COLUMN` in `ensure_sqlite_schema` (SQLite ALTER cannot add
`REFERENCES` — such FKs are application-level only; note that honestly).

## Ordering & constraints

- Create tables in FK-dependency order inside `ensure_sqlite_schema`
  (e.g. `document_parse` before `evidence_span`).
- FK behavior: prefer `ON DELETE SET NULL` for evidence/citation links —
  deleting evidence must never delete a financial fact.
- `PRAGMA foreign_keys=ON` is a global connect-listener; tests and prod both
  enforce FKs. A DB uniqueness/FK constraint should keep its own test that
  deliberately bypasses application guards, proving it is an independent
  backstop.
- Plain-string status/type constants (like `PARSE_STATUSES`), not DB enums.

## Style invariants

- **Additive only** during transitions: old rows stay valid (new cols
  nullable); never delete an existing extract/write path in the same change.
- One span/evidence link per record (no many-to-many joins); no per-cell
  tables. These were explicitly rejected — don't relitigate.
- Enumerate downstream consumers of the changed model BEFORE editing (models
  ripple: parse layer, extractors, reports, web). Update all call sites +
  tests in the same pass.

## Applying & verifying on the real DB

- Back up first for anything destructive:
  `project_db.sqlite.bak_<reason>_<date>` (repo precedent).
- Apply by running the code path that calls `ensure_sqlite_schema` (or the
  relevant script), then verify columns exist:
  `python -c "import sqlite3; c=sqlite3.connect('project_db.sqlite'); print([r[1] for r in c.execute('PRAGMA table_info(<table>)')])"`
- Tests to add every time: create row, FK link, cascade/SET NULL behavior,
  migration on a BLANK db, migration idempotent on an already-migrated db.
- Never commit `*.sqlite` or backups.
