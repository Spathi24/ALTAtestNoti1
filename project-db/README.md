# project_db — v0.2 Multi-System Integration

A unified data layer that pulls live data from all of the company's SaaS tools
(Monday.com, QuickBooks, CompanyCam, Google Drive) into one database, and lets
you query across all of them from a single command or — eventually — a plain
English question to an AI assistant.

**v0.2 focuses on:** Write mutations back to Monday, mirror-column data
recovery for portfolio-style boards, Google Drive connector live (750 docs
synced), QuickBooks connector skeleton, and a 131-test suite.

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

## What's New in v0.2

✅ **Write Mutations:** Push changes back to Monday (`change_multiple_column_values`)
✅ **Mirror-Column Overlay:** Recover status/timeline from linked portfolio items
✅ **Column Cache:** Board-column schema cached per `MondayClient` (one fetch / board / run)
✅ **Google Drive Connector:** 750 documents synced with full metadata; 300 linked to canonical Projects
✅ **QuickBooks Connector:** Code complete, awaiting live credentials
✅ **Ripple-Effect Ready:** Infrastructure for cross-system updates

🟡 **Delta Sync:** Monday withdrawn (API-Version 2026-07 dropped
`updated_after`). Drive has genuine `changes.list` delta sync.

**See [OPTIMIZATION_v0.2.md](docs/OPTIMIZATION_v0.2.md) for detailed breakdown
and [docs/STRATEGY.md](docs/STRATEGY.md) for the strategic direction.**

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
# Pull all data from Monday into the local DB
project_db sync monday

# Ask what projects are currently active
project_db ask "what active projects do we have?"

# See the current deal pipeline value by stage
project_db ask "what deals are in the pipeline?"

# See accounts receivable aging
project_db ask "show ar aging"
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
- [ ] ~~Delta Sync~~ — Withdrawn: Monday API-Version 2026-07 removed `updated_after`

### ✅ v0.2.5 — Google Drive live (done)

- [x] **Google Drive Connector** — 750 documents, full metadata, project linking via civic-number match
- [x] **One consolidated SQLite location** — absolute path in `.env`

### 🧠 v0.3 — The Brain (per [STRATEGY.md](docs/STRATEGY.md))

This is the next focus. Everything below derives from the strategic decision
that ALTA's product is the LLM reconciliation layer, not the sync.

- [ ] **`DocumentText` sidecar** — Extract text from PDFs, Google Docs, DOCX, Excel; cap at 10 MB; skip HEIC/DWG/audio
- [ ] **`Proposal` table** — LLM-generated suggestions awaiting human approval
- [ ] **LLM timeline-filling** — Given a Project + its DocumentText, propose dates for Monday tasks lacking them
- [ ] **LLM scope reconciliation** — Compare contract scope (Drive text) to Monday task list, flag missing items
- [ ] **Approval workflow CLI** — `project_db proposals list / accept / reject`; accepted writes flow back to Monday

### 🛑 Deferred (per STRATEGY.md)

These are valid items, but they are plumbing, not the brain. They are
explicitly deferred until v0.3 lands and a PM is using ALTA daily.

- ~~CompanyCam connector~~ — deferred until Monday+Drive produce daily value
- ~~QuickBooks live integration~~ — deferred (code is ready, run when invoices are needed)
- ~~Text-to-SQL natural-language layer~~ — too speculative; canned reports + LLM proposals first
- ~~Webhook receivers~~ — full-pull is fine at current scale
- ~~Postgres + Alembic migrations~~ — migrate when SQLite limits actually bite

See [adding-a-connector.md](docs/adding-a-connector.md) for the playbook on adding new connectors,
and [STRATEGY.md](docs/STRATEGY.md) for the full rationale on why the order above is correct.

---

## Configuration

All credentials go in `.env` (copy from `.env.example`):

```bash
# Database — SQLite for local dev, Postgres for production
PROJECT_DB_URL=sqlite:///./project_db.sqlite
# PROJECT_DB_URL=postgresql+psycopg://user:pass@host:5432/project_db

# Monday.com — required for sync monday
MONDAY_API_TOKEN=...

# QuickBooks (v0.2)
QUICKBOOKS_CLIENT_ID=...
QUICKBOOKS_CLIENT_SECRET=...
QUICKBOOKS_REALM_ID=...
QUICKBOOKS_ACCESS_TOKEN=...

# CompanyCam (v0.3)
COMPANYCAM_API_TOKEN=...

# Google Drive (v0.3)
GOOGLE_CREDENTIALS_PATH=/path/to/service-account.json

# Anthropic — for AI text-to-SQL mode (v0.3+)
ANTHROPIC_API_KEY=...
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
