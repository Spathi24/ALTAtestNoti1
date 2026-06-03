# project_db — v0.3 (in progress): The Brain

A unified data layer that pulls live data from all of the company's SaaS tools
(Monday.com, QuickBooks, CompanyCam, Google Drive) into one database, and lets
you query across all of them — or have an LLM read your contracts and propose
corrections to what Monday says is happening.

**Current status (2026-05-26):**
- Phase 1 (Brain foundation): DocumentText sidecar + Proposal table +
  content extractors + Drive reconciliation. **Done.**
- Phase 2 (Tier-1 deterministic reports): 5 canned reports wired into
  `ask` and verified against the live DB. **Done.**
- Phase 2.5 (Foundation correctness): Drive folders define project
  identity; deterministic linkage; `doctor` and `rebuild` exist. **Done.**
- Phase 3 (Tier-2 LLM proposals): timeline + scope proposals, list/show,
  accept/reject with Monday write-back. **Done.**
- Phase 4 (Approval workflow): list / show / accept / reject / bulk;
  one real Monday accept verified live. **Done.**
- **Phase 6 / M5 (Local web UI): the full read+decision+action loop
  in the browser -- dashboard, projects, documents, proposals
  (filterable + reviewable with citations), `/ask` with assertive
  Haiku fallback, inline task date editing, propose-from-UI with
  hx-confirm token-cost dialogs, `/doctor`, `/db` raw inspector.
  **Closed 2026-05-26.**
- **Financial reconciliation layer (2026-05-29 → 06-01): the current
  headline.** `extract-financials` reads quotes / invoices / estimates
  out of a project's Drive documents into a `FinancialRecord` table —
  every amount carrying the verbatim text that proves it, handling
  English + French (Quebec) number formats. It computes a two-sided
  money picture (revenue vs. cost, margin), de-duplicates internal
  roll-up sheets, sorts amounts into money-type buckets, **flags
  low-confidence reconciliations** for project types it can't model,
  and supports a human **confirmed-vs-quoted toggle** (so quotes the
  company didn't go with don't inflate the totals). Viewable in the
  browser at `/projects/{id}/financials`. Extracted across the full
  portfolio.
- **Roadmap prompt injection REMOVED (2026-05-29).** The `roadmap_task`
  table + import/classify CLIs are kept, but injecting the architect
  design-phase roadmap into the contractor proposal prompts produced
  template noise and was stripped (see `docs/EVALUATION.md` §3).
- **Attention briefing (2026-06-03): the new landing.** The web `/`
  now leads with a ranked, deterministic briefing of the cross-system
  truths that need attention — money risk (low-confidence margins,
  confirmed costs exceeding revenue, unconfirmed-quote piles), scope
  gaps, overdue tasks, missing contracts — each linking to its evidence.
  No LLM, no API spend (it recomputes over already-stored data). Also a
  `project_db briefing` CLI. This is the EVALUATION.md §3/§5 shift from
  *showing activity ALTA generated* to *revealing truths it discovered*.
- **RAG (2026-06-03): the askbot can read the contracts.** Document text
  is chunked + embedded (OpenAI `text-embedding-3-small`) into a
  `DocumentChunk` table; `ask` now retrieves the most relevant excerpts
  and answers clause-level questions ("what scope does the 923 Rockland
  contract describe?") with answers cited to the source documents
  (`mode=rag`, "document-aware"). `project_db embed-documents` (idempotent;
  prints cost) + `rag-search`. Needs `OPENAI_API_KEY` in `.env`. RAG also feeds
  the **proposal bots** (timeline/scope) as extra evidence — surfacing clauses
  buried deep in long contracts — with the conservative posture unchanged.
- **Stays current automatically (2026-06-03).** `project_db refresh` does a
  delta sync of the live connectors then re-embeds ONLY the documents whose text
  changed (idempotent — unchanged docs cost $0). `serve` runs it in a background
  thread on startup (opt out `--no-refresh`), so opening the app gives fresh
  Monday data + current embeddings; the footer shows when it last refreshed.

**766-test suite.** For "what does it do?" read
**[docs/FEATURES.md](docs/FEATURES.md)** (plain-language feature list);
for the honest current-state assessment + standing rules read
**[docs/EVALUATION.md](docs/EVALUATION.md)**; for the developer handoff
(invariants, the financial layer, worked-through problems, footguns) read
**[docs/HANDOFF.md](docs/HANDOFF.md)**; day-by-day log in
**[CHANGELOG.md](CHANGELOG.md)**.

---

## Mission

**ALTA is a contractor operations brain, not a sync tool.**

Most SaaS integration projects build a fancy version of Zapier. This one
doesn't. Once Monday and Drive are flowing into one canonical database, the
real product is an LLM layer that **reads what your contracts promised and
compares it to what Monday says is actually happening** — then proposes
corrections you approve before they get written back.

Concretely, this means:

- **Time saved.** A PM at a mid-sized contractor spends roughly 12–24 hours
  per week across six active projects toggling tabs to reconcile what's in
  Monday vs. what's in Drive vs. what's in QuickBooks. Eliminating half of
  that frees up roughly a working week per PM per month.
- **Errors caught.** Forgotten scope items, missed deadlines, and unsent
  invoices are all data-consistency failures across two or more systems.
  This system turns them into flagged anomalies before they become invoiced
  losses. One caught change order per quarter pays for the project.
- **Decisions improved.** Once your operational reality is queryable, you
  can finally answer questions like *"which clients have the best margin
  per dollar of project effort?"* — questions that almost no contractor
  in the industry can answer today.

Frame this project as *sync* and it's redundant with Zapier. Frame it as
*the layer that sits under Monday and Drive and uses LLMs to enforce
contract-to-execution consistency* and it's something nobody else is
building. **The latter is the real project.**

The full strategic mission, architecture rationale, and decision manifesto
lives in **[docs/STRATEGY.md](docs/STRATEGY.md)** — read it before
contributing.

---

## What's New in v0.3 (in progress)

✅ **DocumentText sidecar table** — 1:1 with `Document`, stores extracted
text + extraction method + token count. Enables the LLM layer to actually
read your contracts.
✅ **Proposal table** — every LLM-generated suggestion lands here as
PENDING; a human accept/reject is what triggers write-back to Monday.
LLM is an advisor, never an actor.
✅ **Content extractors** — PDF (PyMuPDF), DOCX (python-docx), XLSX
(openpyxl), Google Docs / Sheets via Drive export. 10 MB cap.
Unsupported mimes recorded as `skipped-mime` so we don't retry them.
✅ **`extract-content` CLI** — idempotent text extraction with
`--missing-only` (default), `--overwrite`, `--project`, `--limit`.
Periodic commits + Ctrl-C handling for long runs.
✅ **Drive sync reconciliation** — full sync now soft-marks Documents
that vanished from Drive (was insert-only; orphans lingered).
Conservative scope rules; soft-delete only per STRATEGY.md.
✅ **5 new canned reports** — `project_overview`, `docs_for_project`,
`tasks_without_dates`, `missing_documents`, `budget_vs_contract`.
All importable from `project_db.ai.views` for the Phase 3 LLM tool layer.
✅ **`ask` LLM fallback** — a question that matches no canned report is
answered by a fast model (Haiku) reading a whole-database snapshot
(`report_database_overview`). Canned reports stay instant + deterministic;
only the fall-through spends a token. `propose` keeps the deeper model.
✅ **Bulk proposal review** — `proposals accept` / `reject` with no id list
the pending queue so you can choose; `accept all` / `reject all` act on
every pending proposal at once, both gated behind `--yes`.

### What's New in v0.2

✅ Write mutations back to Monday • mirror-column overlay •
column cache • Google Drive connector live (750 docs, 300 linked) •
QuickBooks connector code complete • Drive delta sync via
`changes.list` cursor.

✅ Monday delta sync now uses `Board.activity_logs(from, to, ...)` through
`project_db sync monday --delta`. Webhook receivers are still deferred; the
blocker is hosting a public HTTPS endpoint, not Monday API capability.

**See [docs/STRATEGY.md](docs/STRATEGY.md) for the strategic direction,
[docs/ROADMAP.md](docs/ROADMAP.md) for the phased plan, and
[CHANGELOG.md](CHANGELOG.md) for day-by-day progress.**

---

## The Problem

The company's operational data lives in four separate systems that don't talk to
each other:

| Tool | What lives there |
|---|---|
| **Monday.com** | Projects, tasks, CRM pipeline (leads, deals, contacts), team activity |
| **QuickBooks** | Invoices, payments, purchase orders, financial reporting |
| **CompanyCam** | Job-site photos, inspection reports, daily logs |
| **Google Drive** | Contracts, scopes of work, drawings, documents |

Answering a cross-tool question today means opening multiple tabs and stitching
results together by hand. Questions like:

- *"Which active projects are over budget?"*
- *"What's the total value of open deals vs. invoiced revenue this quarter?"*
- *"Show me everything related to 923 Rockland — tasks, photos, invoices, documents."*

...currently have no single place to go.

---

## The Solution

`project_db` solves this by acting as a **canonical data layer**:

1. Every source system gets a **Connector** that knows how to pull its data via API.
2. Every record from every source is mapped to a **canonical entity** with a single
   UUID we own — a Client is one record regardless of whether it came from Monday,
   QuickBooks, or both.
3. All queries, reports, and AI interactions read from the canonical layer only —
   they never need to know which source the data came from.

```
Monday.com  ──┐
QuickBooks  ──┤  Connectors  →  Identity Resolver  →  Canonical DB  →  AI / Reports
CompanyCam  ──┤
Google Drive──┘
```

Adding a new data source = writing one new Connector class. Everything else
(schema, deduplication, AI, reporting) stays the same.

---

## What Works Today (v0.1)

The Monday.com connector is fully operational. Running a sync pulls your entire
Monday workspace into a local database in about 20 seconds.

### Setup

```bash
# Install (requires Python 3.10+)
pip install -e ".[dev]"

# Copy credentials template and fill in your Monday API token
cp .env.example .env
# Edit .env — MONDAY_API_TOKEN is required to sync

# Create the database tables
project_db init-db
```

### Daily use

```bash
# --- Sync ---
project_db sync monday              # full pull (every board)
project_db sync monday --delta      # smart-skip: query Board.activity_logs,
                                    # skip boards with no changes since cursor
project_db sync GOOGLE_DRIVE        # pull Drive metadata (run gdrive-auth once first)
project_db gdrive-auth              # one-time OAuth browser flow (Desktop creds)

# --- Open the local web UI (M5) ---
project_db serve                                 # http://127.0.0.1:8000
project_db serve --port 9000                     # alternate port

# --- Read contract text ---
project_db extract-content --limit 5            # smoke test
project_db extract-content                      # default: every doc missing text
project_db extract-content --project <UUID>     # restrict to one project
project_db extract-content --overwrite          # re-extract everything

# --- Read the MONEY out of documents (financial reconciliation) ---
project_db extract-financials "923 Rockland"    # extract quotes/invoices -> FinancialRecord,
                                                # then print the money-flow reconciliation
project_db extract-financials "923 Rockland" --max-docs 6   # cap docs (cheaper smoke run)
project_db serve                                # then open /projects/{id}/financials in browser

# --- Ask (canned reports + LLM fallback) ---
project_db ask "what active projects do we have?"
project_db ask "what deals are in the pipeline?"
project_db ask "show ar aging"
project_db ask "overview of project 923 Rockland"
project_db ask "docs for project Rockland"
project_db ask "tasks without dates"
project_db ask "tasks without dates for project Rockland"
project_db ask "which projects are missing documents"
project_db ask "budget vs contract for project Rockland"
project_db ask "help"                       # list every routed pattern
project_db ask "which project looks most at risk?"   # no canned match ->
                                            # fast (Haiku) LLM reads the DB snapshot
project_db daily "923 Rockland"             # one-screen PM/developer review
project_db daily "923 Rockland" --propose-timelines  # optional LLM proposal run

# --- LLM smoke (Phase 3a) ---
project_db llm-test Rockland                # assemble context + call configured LLM
project_db llm-test 5768-5770 --verbose     # also dump prompts, timing, tokens
project_db llm-test Rockland --token-budget 8000 --max-docs 1 \
                              --max-output-tokens 200   # shrink for slow local models

# --- LLM proposals (Phase 3b) ---
project_db propose timelines "923 Rockland"   # LLM proposes dates -> Proposal table
project_db propose scope "923 Rockland"       # LLM flags documented scope items
                                              # with no matching Monday task
project_db proposals list                     # all proposals, newest first
project_db proposals list --status pending    # filter by status
project_db proposals show <proposal-uuid>     # full detail + source documents
project_db proposals accept                   # no id -> list pending, pick one
project_db proposals accept <proposal-uuid> --dry-run  # preview Monday write-back
project_db proposals accept <proposal-uuid>            # write approved change to Monday
project_db proposals accept all --yes         # accept every pending proposal
project_db proposals reject <proposal-uuid> --reason "not supported by contract"
project_db proposals reject all --yes         # reject every pending proposal

# --- Admin / diagnostic ---
project_db init-db                          # one-time table create + seed org
project_db list-sources                     # registered connectors
project_db list-boards                      # Monday boards (needs MONDAY_API_TOKEN)
project_db inspect-board <board_id>        # columns + heuristic mapping + sample items
project_db list-external <EntityType> <UUID>   # every source-system ID for one canonical entity
```

### Example output

```
$ project_db sync monday
[MONDAY] processed=85 created=81 matched=4 failed=0 duration=19.8s

$ project_db ask "what active projects do we have?"
[mode=canned report=active_projects]
[
  { "name": "923 Rockland",        "code": "MONDAY-BOARD-18412002783", "start_date": null },
  { "name": "5768-5770 St Laurent","code": "MONDAY-BOARD-18412200212", "start_date": null },
  { "name": "1455 Saint Mathieu",  "code": "MONDAY-BOARD-18412776683", "start_date": null },
  { "name": "Rockland",            "code": "MONDAY-BOARD-18412002814", "start_date": null },
  ...
]

$ project_db ask "what deals are in the pipeline?"
[mode=canned report=deal_pipeline_value]
[
  { "stage": "NEW",      "total_value": 125000.0, "count": 2 },
  { "stage": "PROPOSAL", "total_value": 100000.0, "count": 1 }
]
```

### What gets synced from Monday

| Canonical entity | Where it comes from |
|---|---|
| **User** | Your Monday.com team members |
| **Client** | Contacts board, Accounts board |
| **Lead** | Leads board |
| **Deal** | Deals board (with value, stage, close date, probability) |
| **Project** | Client Projects board (CRM-linked projects) |
| **Project + Tasks** | Property boards like "923 Rockland" — the board becomes a Project, every item becomes a Task with status and due date |

The Monday connector automatically maps column values to the right canonical
fields using the column titles — it recognizes columns named "Status", "Budget",
"Timeline", "Owner", "Client", "Expected Close Date", etc. without any manual
configuration.

---

## Monday.com push / pull / add workflows

For the full end-to-end workflow (pulling Monday data into the canonical DB,
pushing changes back to Monday, creating new Monday items from the canonical
side, troubleshooting), see **[docs/MONDAY_USAGE.md](docs/MONDAY_USAGE.md)**.

Quick reference:

```bash
python scripts/monday_demo.py list-boards
python scripts/monday_demo.py pull
python scripts/monday_demo.py inspect
python scripts/monday_demo.py push <canonical_uuid> status="Working on it"
python scripts/monday_demo.py add-item <board_id> "New Item Name"
```

## Exploration & Diagnostics

Before syncing a board you haven't seen before, inspect it first:

```bash
# See all your Monday boards and their IDs
project_db list-boards

# See exactly what columns a board has and what the system will extract from them
project_db inspect-board 18412002783
```

`inspect-board` output:

```
Column ID            Type               Title
-----------------------------------------------------------------
project_status       status             Status
project_timeline     timeline           Timeline
project_budget       numbers            Budget
project_task_completion_date date       Completion Date
project_owner        people             Owner

Heuristic field assignments (auto-detected):
  project_status       -> status_label  (title: 'Status')
  project_timeline     -> timeline      (title: 'Timeline')
  project_budget       -> budget_amount (title: 'Budget')
  project_task_completion_date -> end_date (title: 'Completion Date')
  project_owner        -> assigned_user (title: 'Owner')

Sample items:
  11941695903   Planning    Project Kickoff Meeting
    task_status: TaskStatus.TODO
  11941725666   Planning    Design Approval
    task_status: TaskStatus.TODO
```

---

## Architecture

### Canonical schema (13 entities)

```
Organization
├── User           (team members)
├── Client         (customers / contacts)
├── Vendor
├── Property       (job-site address)
├── Lead           (CRM pipeline entry)
├── Deal           (qualified opportunity with value + stage)
├── Project        (active or completed job)
│   ├── Task       (individual work item with status + due date)
│   └── DailyLog   (field notes / progress entries)
├── Invoice
└── Document       (reference to a file in Drive / CompanyCam)

ExternalId         (maps any canonical UUID → source system record ID)
```

Every entity has a stable UUID (`canonical_id`) that is ours — independent of
any source system. The `ExternalId` table records how each canonical entity
maps to one or more source records:

```
Project "923 Rockland"  (canonical_id: abc-123)
    ├── MONDAY board:18412002783
    ├── QUICKBOOKS job:QBJ-9231     (once QB connector is built)
    └── COMPANYCAM project:CC-4421  (once CompanyCam connector is built)
```

This means the same project in Monday and QuickBooks becomes **one record** in
the canonical DB — no duplicates, no manual linking.

### Identity resolution

When a connector syncs a record, it goes through three steps:

1. **Exact lookup** — has this `(source, external_id)` pair been seen before?
   If yes, update the existing canonical entity.
2. **Fuzzy match** — does a canonical entity with the same name / email /
   address already exist? If yes, link to it (e.g. a QuickBooks customer named
   "Smith Renovation" matches the Monday client "Smith Renovation").
3. **Create** — if no match, create a new canonical entity and register the
   external ID.

Subsequent syncs are idempotent — re-running `sync monday` updates existing
records without creating duplicates.

### Connectors

Each source system is a self-contained Python package under `connectors/`:

```
connectors/
├── base.py          ← abstract BaseConnector + SyncReport
├── registry.py      ← maps SourceSystem enum → connector class
└── monday/
    ├── client.py    ← Monday GraphQL API wrapper (auth, pagination)
    ├── connector.py ← board classification + entity upsert logic
    └── column_extractor.py ← maps Monday column types to canonical fields
```

Adding QuickBooks, CompanyCam, or Drive means adding a new folder following
the same pattern. See `docs/adding-a-connector.md` for the step-by-step.

---

## Project Structure

```
project-db/
├── docs/
│   ├── design-v0.1.md                  ← architectural design doc
│   ├── OPTIMIZATION_v0.2.md            ← NEW: v0.2 improvements breakdown
│   ├── MONDAY_INTEGRATION_STRATEGY.md  ← why Monday is the hub
│   ├── model-v0.1.ump                  ← Umple UML — v0.1 skeleton model
│   ├── model-full.ump                  ← Umple UML — full target model
│   ├── adding-a-connector.md           ← how to plug in a new source
│   ├── monday-api-reference-all.md     ← Monday API docs (42 pages)
│   ├── monday-graphql-schema.json      ← Monday GraphQL schema
│   └── monday-graphql-schema-summary.md ← Monday schema summary
├── src/project_db/
│   ├── db/
│   │   └── models/
│   │       ├── canonical.py            ← Core entities + ExternalId mapping
│   │       ├── finance.py              ← Invoice, financial entities
│   │       ├── work.py                 ← Projects, Tasks, etc.
│   │       └── ...
│   ├── identity/                       ← canonical-ID resolver + fuzzy matchers
│   ├── connectors/
│   │   ├── base.py                     ← abstract Connector class
│   │   ├── registry.py                 ← lookup by SourceSystem enum
│   │   ├── monday/                     ← Read + Write mutations (v0.2)
│   │   │   ├── client.py               ← GraphQL queries + mutations
│   │   │   ├── connector.py            ← Monday → Canonical mapping
│   │   │   └── column_extractor.py     ← Column value parsing
│   │   └── quickbooks/                 ← NEW: v0.2 QB connector
│   │       ├── client.py               ← QB REST + Query Language client
│   │       └── connector.py            ← QB → Canonical mapping
│   ├── ai/                             ← AI assistant — canned reports
│   ├── cli.py                          ← `project_db ...` command-line
│   └── config.py                       ← env-var loading
├── tests/
│   └── test_identity.py                ← identity resolution tests
├── scripts/
│   ├── init_db.py                      ← one-shot DB init
│   ├── build_monday_api_reference.py   ← scrape Monday docs
│   └── dump_monday_schema.py           ← export Monday GraphQL schema
└── pyproject.toml
```

---

## Roadmap

### ✅ v0.1 — Monday connector (complete)

- [x] Canonical schema (13 entities)
- [x] Identity resolver with exact + fuzzy matching
- [x] Monday connector: boards, items, column extraction, user sync
- [x] Board classification: CRM boards vs. property/job boards
- [x] CLI: `init-db`, `sync`, `list-boards`, `inspect-board`, `ask`
- [x] 3 canned AI reports: active projects, deal pipeline, AR aging
- [x] Credentials loaded from `.env`

### ✅ v0.2 — Write-back + QuickBooks scaffolding (complete)

- [x] **Write Mutations** — Push changes back to Monday
- [x] **Mirror-Column Overlay** — Recover status/timeline from linked portfolio items
- [x] **Column Cache** — One column-schema fetch per board per run
- [x] **QuickBooks Connector** — Invoices, estimates, customers (live test pending)
- [x] **Ripple Effects** — Infrastructure for cross-system updates
- [x] **Delta Sync (via `activity_logs`)** — `project_db sync monday --delta`
  skips boards with no activity since the saved cursor

### ✅ v0.2.5 — Google Drive live (done)

- [x] **Google Drive Connector** — 750 documents, full metadata, recursive sync
- [x] **One consolidated SQLite location** — absolute path in `.env`

### ✅ v0.2.6 — Foundation correctness (done)

- [x] **Drive folder registry** — project folders define canonical Projects
- [x] **Deterministic document linking** — documents link by physical folder
  ancestry, not substring name matching
- [x] **`doctor` / `rebuild`** — audit and re-derive the canonical DB
- [x] **Deal/project trust cleanup** — Google and Amazon are deals, not
  construction projects; reports and `doctor` recognize those empty CRM
  placeholders when matching `deal` rows exist

### 🧠 v0.3 — The Brain (per [STRATEGY.md](docs/STRATEGY.md))

The current focus. The phased plan lives in
[docs/ROADMAP.md](docs/ROADMAP.md); the abridged version:

**Phase 1 — Brain foundation (done)**
- [x] `DocumentText` sidecar — extract text from PDFs, Google Docs, DOCX, Excel; 10 MB cap
- [x] `Proposal` table — LLM-generated suggestions awaiting human approval
- [x] `extract-content` CLI — idempotent, project-scoped, with `--overwrite`
- [x] Drive sync reconciliation — soft-mark vanished files

**Phase 2 — Tier-1 reports (done, live verified)**
- [x] `project_overview`, `docs_for_project`, `tasks_without_dates`,
  `missing_documents`, `budget_vs_contract`
- [x] Wired into `ask` via keyword + project-ref extraction
- [x] All importable from `project_db.ai.views` for the Phase 3 LLM tool layer

**Phase 3 — Tier-2 LLM proposals (in progress)**
- [x] Session 3a: `LLMProvider` abstraction (mock + anthropic + openai-compatible) + `assemble_project_context` + `llm-test` smoke CLI + Monday `activity_logs` delta sync
- [x] Session 3b pt.1: proposal engine + timeline-extraction prompt + `propose` / `proposals list/show` CLI
- [x] Session 3b pt.2a: `proposals accept/reject` with Monday write-back
- [ ] Session 3b pt.2b: scope & anomaly prompts, plus better handling for
  dateless tasks where the model correctly refuses to invent past dates
- [ ] Session 3c: fine-tuning corpus exporter + personality config + local-backend swap

**Phase 4 — Approval workflow**
- [x] `proposals list / show / accept / reject`
- [x] Accept triggers Monday write-back via existing `sync_back`
- [x] Auto-supersede on new proposals for the same field
- [x] Add a daily review command that makes this usable without remembering
  the whole CLI surface

**Phase 5 — Adoption**
- [ ] One PM, one project, daily run for two weeks
- [x] `project_db daily <project_id>` — read-only project review by default;
  `--propose-timelines` intentionally spends LLM tokens to create proposals
- [ ] Minimal local UI for report/proposal review; this can move forward
  before adoption is complete because the CLI surface is already hard to
  navigate even for the developer
- [ ] Decision point at 4-6 weeks: is it being used?

### 🛑 Deferred (per STRATEGY.md)

These are valid items, but they are plumbing, not the brain. They are
explicitly deferred until v0.3 lands and a PM is using ALTA daily.

- ~~CompanyCam connector~~ — deferred until Monday+Drive produce daily value
- ~~QuickBooks live integration~~ — deferred (code is ready, run when invoices are needed)
- ~~Text-to-SQL natural-language layer~~ — too speculative; canned reports + LLM proposals first
- **Webhook receivers** — `create_webhook` is scriptable in the live API; blocker is hosting a public HTTPS endpoint, not API capability. Natural fit when the local-model hardware (Mac mini) comes online.
- ~~Postgres + Alembic migrations~~ — migrate when SQLite limits actually bite

See [adding-a-connector.md](docs/adding-a-connector.md) for the playbook on adding new connectors,
and [STRATEGY.md](docs/STRATEGY.md) for the full rationale on why the order above is correct.

---

## Configuration

All credentials go in `.env` (copy from `.env.example`):

```bash
# Database — SQLite for local dev, Postgres for production.
# Use an absolute path so the same file is used regardless of cwd.
PROJECT_DB_URL=sqlite:///C:/full/path/to/project-db/project_db.sqlite
# PROJECT_DB_URL=postgresql+psycopg://user:pass@host:5432/project_db

# Monday.com — required for sync monday
MONDAY_API_TOKEN=...

# QuickBooks (v0.2, code complete, live test deferred)
QUICKBOOKS_CLIENT_ID=...
QUICKBOOKS_CLIENT_SECRET=...
QUICKBOOKS_REALM_ID=...
QUICKBOOKS_ACCESS_TOKEN=...

# Google Drive (v0.2.5 live; OAuth Desktop or service-account JSON)
GDRIVE_SA_KEY_PATH=/path/to/oauth_client_or_service_account.json
GDRIVE_IMPERSONATE=workspace-user@example.com    # service-account flow only
GDRIVE_TOKEN_PATH=/path/to/gdrive_token.json     # OAuth flow only; auto-created
GDRIVE_ROOT_FOLDER=root                          # or a specific Drive folder ID

# --- LLM provider (Phase 3a) ---
# Resolver order: LLM_PROVIDER -> anthropic-if-key -> mock fallback.
LLM_PROVIDER=mock                 # mock | anthropic | openai-compatible

# Anthropic provider:
ANTHROPIC_API_KEY=...
ANTHROPIC_MODEL=claude-sonnet-4-5-20250929   # "deep" model: propose / analysis
ANTHROPIC_MODEL_FAST=claude-haiku-4-5        # "fast" model: the `ask` LLM fallback

# OpenAI-compatible provider -- works with Ollama, vLLM, llama.cpp,
# LM Studio, OpenAI itself.  When the Mac mini ships, point BASE_URL
# at it and MODEL at the loaded model.  Zero code change.
OPENAI_BASE_URL=http://localhost:11434/v1     # Ollama default
OPENAI_MODEL=qwen2.5:3b                       # or llama3.2:3b, qwen2.5:32b, ...
OPENAI_API_KEY=EMPTY                          # most local servers ignore auth
OPENAI_TIMEOUT=600                            # seconds; bump for slow CPU inference

# CompanyCam — deferred per STRATEGY.md
# COMPANYCAM_API_TOKEN=...
```

The `.env` file is gitignored and never committed. `project_db` finds it
automatically, so the command works from anywhere.

---

## Tuning the Monday column mapping

If the auto-detected field assignments aren't right for a board, you can
override them explicitly in `connector.py` under `DEFAULT_COLUMN_MAPPING`:

```python
DEFAULT_COLUMN_MAPPING = {
    "Project": {
        "text7": "client_name",       # force column text7 → client_name
        "status8": "status_label",    # force column status8 → status
    },
}
```

Use `project_db inspect-board <board_id>` to find the exact column IDs.

---

## Development

### Setup

```bash
# Install with dev dependencies (includes pytest, coverage tools, etc)
pip install -e ".[dev]"

# Install dev-only requirements
pip install -r requirements-dev.txt
```

### Running Tests

The project includes a comprehensive test suite covering all features.

```bash
# Run all tests
pytest tests/ -v

# Run with coverage report
pytest tests/ --cov=project_db --cov-report=html

# Run specific test file
pytest tests/test_db_models.py -v

# Run specific test
pytest tests/test_db_models.py::TestClientModel::test_create_client -v

# Run tests and display print statements
pytest tests/ -v -s
```

**Test coverage includes:**
- ✅ All 17 database models and relationships
- ✅ Monday.com client (queries, mutations, delta sync, complexity tracking)
- ✅ QuickBooks client (queries, entity mapping, delta sync)
- ✅ Sync logic (identity resolution, deduplication, sync workflows)
- ✅ Identity resolution and fuzzy matching
- ✅ AI assistant and report generation
- ✅ CLI commands (init-db, sync, list-boards, inspect-board, ask, etc.)
- ✅ Database sessions and transaction management

See [tests/README.md](tests/README.md) for detailed testing documentation, fixtures, and examples.

### Code Quality

```bash
# Format code
black src/ tests/

# Sort imports
isort src/ tests/

# Lint
flake8 src/ tests/

# Type checking
mypy src/
```

### Development Workflow

1. **Add a feature** in `src/project_db/`
2. **Add tests** in `tests/test_*.py` (use fixtures from `conftest.py`)
3. **Run tests** — `pytest tests/ -v`
4. **Check coverage** — `pytest tests/ --cov=project_db`
5. **Commit** with test-passing code

See [docs/adding-a-connector.md](docs/adding-a-connector.md) for how to add a new source system connector.
