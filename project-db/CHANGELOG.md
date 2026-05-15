# ALTA / project_db — Work Log

A day-by-day journal of what was built, what works, and how the project's
capability grew. Newest entry on top. Lower-level "what changed" detail
is in commit messages; this is the human-readable version.

If you want **"what can this product do today?"** read the top entry.
If you want **"how did we get here?"** read top to bottom.

---

## 2026-05-15 (afternoon) — Phase 1 + Phase 2 close-out

**Theme:** Exit tests passed. Both phases officially done.

### Phase 1 exit test (PASSED)
Ran `project_db extract-content` over the full Drive tree.
- 742 documents processed (5 were already done)
- **457 with non-empty extracted text** (target was ≥200)
- 255 properly skipped as unsupported mime (HEIC, JPG, .wav, etc.)
- 12 skipped as too big (>10 MB)
- 1 actual failure (download error)
- 17 no-op (parsed cleanly but produced empty text — image-only PDFs)
- Every successful extraction carries a token_count

Total DocumentText rows in live DB: **751** (every Document has a status row).
Spot-check confirmed real readable text from contracts, leases, estimates,
DOCX scopes of work.

### Phase 2 exit test (PASSED)
All five reports verified live:
- `tasks_without_dates` → 137 dateless tasks
- `missing_documents` → 1 PROPOSED project flagged
- `project_overview` → Rockland: 1 task, 18 docs, 0 invoices
- `docs_for_project` → Rockland: 18 docs with folder_path context
- `budget_vs_contract` → 5768-5770 St Laurent contracts produced
  real $ extractions (rents, lease months, line items). Honestly
  returns `divergence_pct=null` when Monday budget is unset.

### New: discoverability for non-technical users
`project_db ask "help"` (or `?`, `what can you do`, `list reports`, etc.)
now returns the full list of routed patterns. Closes the gap where a
non-technical user had no way to discover phrases like
"budget vs contract for project X" without reading code.

### Doc hygiene
- CLAUDE.md: stale "113 tests" / "131-test suite" → current numbers
  and a pointer to CHANGELOG for the precise count.
- ROADMAP.md: Phase 1 + Phase 2 checkboxes flipped to `[x]`, exit-test
  results recorded inline.
- README.md: test count updated, `ask "help"` added to daily-use list.

### Tests
- **246 total** (+1 today for the help route).



**Theme:** Stop building plumbing, start building the brain.

### Schema
- New `DocumentText` table: 1:1 sidecar to `Document`, stores extracted text
  + extraction_method + token_count.
- New `Proposal` table: polymorphic LLM-output table gated by human
  approval. Carries entity ref, field name, JSON value, confidence,
  source doc ids, prompt version, decision audit.
- Migration helper (`ensure_sqlite_schema`) now creates both tables on
  legacy SQLite files. Idempotent.
- SQLite foreign-key enforcement turned on (`PRAGMA foreign_keys=ON`
  per connection) — without it the new CASCADE FK was decorative.

### Drive content extraction (`[content]` optional deps)
- `extractors.py` — pure bytes→text functions per mime:
  PDF (PyMuPDF), DOCX (python-docx), XLSX (openpyxl),
  Google Docs (`text/plain` export), Google Sheets (`text/csv` export).
- `content_pipeline.py` — orchestrator with skip-mime, skip-size (10 MB cap),
  skip-trashed, failed-* error labels. Never raises.
- New CLI: **`project_db extract-content [--project UUID] [--overwrite] [--limit N]`**.
  Idempotent; periodic commits every 25 docs; handles Ctrl-C cleanly.
- Live smoke test: 3 Google Docs + 1 XLSX extracted with real text
  (~2000 tokens each).

### Drive sync reconciliation
- Full sync now soft-marks Documents that vanished from Drive since
  the last walk (was an insert-only sync before — orphans linger forever).
- Conservative guardrails: only acts on visited folders, skips if any
  listing failed, leaves legacy null-parent rows alone. Per
  STRATEGY.md "keep everything" — soft delete, never hard.

### Phase 2 reports (Tier-1, zero LLM)
- 5 new canned reports in `ai/views.py`:
  - `project_overview` — one-screen snapshot (tasks, docs, invoices, logs)
  - `docs_for_project` — every doc for a project ordered by folder
  - `tasks_without_dates` — surfaces the 11%-dated-tasks problem
  - `missing_documents` — projects with no contract-shaped doc
  - `budget_vs_contract` — regex `$amounts` vs Monday budget, flags >15% divergence
- Dispatcher in `ai/query.py` now extracts a project ref from natural
  language (UUID anywhere OR text after the word `project`).
- Per-project reports return helpful `{"error": ...}` dicts when no
  project ref is parseable.

### Bugs caught by live smoke testing
- `_ser(ProjectStatus.ACTIVE)` returned `"ProjectStatus.ACTIVE"` (wrong)
  because enum check ran *after* `isinstance(str)` — but the enum
  inherits from str. Enum check moved first. Regression test added.
- CASCADE delete didn't fire (covered above).

### Tests
- **245 total** (up from 151 yesterday). +94 across Phase 1 and Phase 2.
- All green.

### Commands available today
| Command | Phase | Status |
|---|---|---|
| `project_db init-db` | Setup | Works |
| `project_db sync monday` | v0.1 | Works |
| `project_db sync GOOGLE_DRIVE` | v0.2.5 | Works (OAuth) |
| `project_db gdrive-auth` | v0.2.5 | Works (one-time) |
| `project_db list-boards` | v0.1 | Works |
| `project_db inspect-board <id>` | v0.1 | Works |
| `project_db list-sources` | v0.1 | Works |
| `project_db list-external <type> <uuid>` | v0.1 | Works |
| `project_db ask "..."` | v0.1 + Phase 2 | 8 canned reports |
| **`project_db extract-content`** | **Phase 1** | **Works (Drive→DocumentText)** |

### `ask` patterns that work today
| Phrase | Routes to |
|---|---|
| "active projects" / "open projects" | `active_projects` |
| "pipeline" / "deal value" | `deal_pipeline_value` |
| "ar aging" / "outstanding invoices" | `ar_aging` |
| "overview of project X" | `project_overview` |
| "docs for project X" / "files for project X" | `docs_for_project` |
| "tasks without dates" [`for project X`] | `tasks_without_dates` |
| "which projects are missing documents" | `missing_documents` |
| "budget vs contract for project X" | `budget_vs_contract` |

---

## 2026-05-14 — Google Drive live + strategic refocus

**Theme:** Drive sync working at scale; STRATEGY.md written; ROADMAP.md
established; +20 tests; cleanup.

### Drive connector live
- 750 documents synced with full metadata (folder_path, modified_time,
  size, md5, owner, etc.).
- 300 of 750 linked to canonical Projects via civic-number + name match.
- Recursive walk (depth-20 cap) replaced the old 3-level walk that
  silently dropped deep files.
- Delta sync via `changes.list` cursor stored in synthetic ExternalId row.
- OAuth Desktop credential flow (`gdrive-auth`) for personal/non-Workspace
  Google accounts. Auto-detects service-account vs OAuth Desktop from
  the JSON file.
- Folder→Project matching: civic number first (`923 Rockland` beats
  generic `Rockland`), then substring fallback.

### Infra
- Two `.sqlite` files consolidated into one (absolute path in `.env`).
- `Document` model expanded with 10 new columns
  (created_at_source, modified_at_source, size_bytes, md5_checksum,
   drive_id, parent_folder_id, folder_path, owner_email, is_trashed,
   source_meta_json).

### Strategy
- **STRATEGY.md** written — the canonical decision manifesto.
  Reframes ALTA from "sync tool" (commodity) to "LLM operations brain"
  (genuinely novel). 10 operating principles distilled.
- **ROADMAP.md** written — Phase 0 (done) through Phase 5 (adoption).
- CLAUDE.md updated with the strategic direction so future sessions
  can't drift.

### Tests
- 131 total (up from 111). Civic-number matching, RFC3339 parsing,
  Drive document field population, recursion depth, migration helper.

### Bugs fixed
- `gdrive-auth` was reading `GOOGLE_CREDENTIALS_PATH` (settings.py) but
  `.env` was using `GDRIVE_SA_KEY_PATH` — read switched to the env var
  directly.
- `python-dotenv` wasn't loading in `cmd_gdrive_auth` because
  `from project_db.config import settings` had been removed; restored
  via module-level `from project_db import config as _config`.
- `getStartPageToken` rejected `includeItemsFromAllDrives` (only valid
  on `changes.list`); param removed.

---

## 2026-05-13 — Monday push/pull/fuzzy/optimizer/mirror-columns

**Theme:** Monday became fully operational. Tests, fuzzy matching,
column caching, mirror columns, and the inspect tool all landed.

### Monday
- `change_multiple_column_values` write-back works end-to-end —
  `sync_back` parses board_id from the ExternalId URL so it doesn't
  re-query Monday for it.
- Mirror-column overlay: pulls status/timeline from linked portfolio
  items (so tasks proxying portfolio rows display the right value).
- Column metadata cached per `MondayClient` instance (1 fetch / board
  / run instead of N).
- `inspect-board` CLI shows columns + heuristic field assignments +
  sample items.
- `add-item` works for creating Monday items from the canonical side.
- Project optimizer analysis script added.

### Identity
- `FuzzyFieldMatcher` for approximate dedup
  (email-normalized, name-fuzzy, address-fuzzy).

### Cleanup
- Stale files culled. Compiled `.pyc` and SQLite removed from tracking.
- Test suite expanded to ~110 tests.

### Bug fixes
- Removed invalid `updated_after` argument from Monday `items_page`
  query (Monday API-Version 2026-07 dropped it).
- Corrected several GraphQL mutation signatures discovered against
  the live API.

---

## 2026-05-12 — Monday connector real implementation + QB skeleton

**Theme:** Monday went from architectural sketch to real working
connector. QuickBooks connector scaffolded.

### Monday
- Real column extraction with `ColumnExtractor`: maps Monday column
  types (status, timeline, numbers, people, date, ...) to canonical
  fields via title-based heuristics.
- ProjectBoard classification: distinguishes CRM boards from
  property/job boards.
- Per-board sync workflow: boards become Projects, items become Tasks.
- `.env` loading via `python-dotenv` so credentials don't leak into
  version control.

### QuickBooks
- Client + connector code complete (REST + Query Language).
- Mapping for customers, invoices, estimates.
- Live test pending real credentials.

### Docs
- README rewritten with full project scope, current usage, roadmap.

---

## 2026-05-11 — Genesis

**Theme:** Repo created. Architecture sketched in Umple UML. Monday
API reference docs scraped for offline reading.

- Initial schema design: 13 canonical entities + ExternalId bridge.
- Umple UML model compiled to Java; 0 compile errors but logical work
  in progress.
- Monday.com API reference fully documented (42 pages of GraphQL
  schema + examples cached locally).
- First-pass connector skeleton.

---

## How to read this log

- **Newest on top** so the top entry is "today's product state."
- **Each entry has a theme** so you can scan to find when something was
  built without reading every commit message.
- **Commands available today** in the latest entry is the live cheat
  sheet — if a command isn't listed there, assume it's planned but
  not built.
