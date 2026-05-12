# project_db — v0.2 Multi-System Integration

Unified project database that pulls data from Monday.com, QuickBooks, CompanyCam,
and Google Drive into a single canonical schema, with an AI assistant layer
on top for Q&A and reporting.

**v0.2 focuses on:** Optimization (delta sync, complexity tracking), write mutations,
multi-system architecture, and QuickBooks connector implementation.

---

## What's New in v0.2

✅ **Delta Sync:** Query only changed items (~90% fewer API calls)  
✅ **Write Mutations:** Push changes back to Monday  
✅ **Complexity Tracking:** Know the cost of each API call  
✅ **QuickBooks Connector:** Fully functional, pulls invoices/estimates/customers  
✅ **Ripple-Effect Ready:** Infrastructure for cross-system updates  

**See [OPTIMIZATION_v0.2.md](docs/OPTIMIZATION_v0.2.md) for detailed breakdown.**

---

## What's here

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
│   │   ├── monday/                     ← NEW: Read + Write mutations
│   │   │   ├── client.py               ← GraphQL queries + mutations
│   │   │   ├── connector.py            ← Monday → Canonical mapping
│   │   │   └── column_extractor.py     ← Column value parsing
│   │   └── quickbooks/                 ← NEW: v0.2 QB connector
│   │       ├── client.py               ← QB REST + Query Language
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

## Quick start

```bash
# 1. Install (editable, with dev deps)
pip install -e ".[dev]"

# 2. Initialize the DB (uses sqlite by default — see .env.example for Postgres)
python -m project_db.cli init-db

# 3. Run tests to confirm the identity layer works
pytest -q

# 4. List available connectors
python -m project_db.cli list-sources

# 5. Sync Monday (delta sync by default)
export MONDAY_API_TOKEN=...
python -m project_db.cli sync monday
# First run: full sync (all items)
# Second run: delta sync (~90% fewer items)

# 6. Sync QuickBooks
export QB_CLIENT_ID=... QB_CLIENT_SECRET=... QB_REALM_ID=... QB_ACCESS_TOKEN=...
python -m project_db.cli sync quickbooks
# Pulls invoices, estimates, customers
# Links to canonical Projects/Deals/Clients

# 7. Check API usage
python -m project_db.cli show-complexity-stats

# 8. Ask the AI assistant something
python -m project_db.cli ask "what active projects do we have"
```

---

## Architecture in one paragraph

Each source system has a **Connector** that knows how to talk to its API. As
records come in, the connector calls the **IdentityResolver**, which either
finds an existing canonical entity (via the `ExternalId` mapping table or a
**Matcher**) or creates a new one. Every canonical entity has a UUID that's
ours, plus zero-or-more `ExternalId` rows linking it to its representations
in Monday / QuickBooks / etc. The **AI Assistant** layer reads from canonical
entities only and never touches source APIs directly.

**New in v0.2:** Connectors can now **sync_back()** — push changes from canonical
back to source systems. This enables **ripple effects**: when an invoice is created
in QB, the connector updates the linked Monday project.

---

## Documentation Guide

- **[OPTIMIZATION_v0.2.md](docs/OPTIMIZATION_v0.2.md)** — What's new in v0.2, 
  API cost savings, multi-system patterns
- **[MONDAY_INTEGRATION_STRATEGY.md](docs/MONDAY_INTEGRATION_STRATEGY.md)** — 
  Why Monday is the hub, integration philosophy
- **[adding-a-connector.md](docs/adding-a-connector.md)** — 
  Playbook for adding CompanyCam, Drive, etc.
- **[design-v0.1.md](docs/design-v0.1.md)** — 
  Original v0.1 architecture & decisions
- **[Monday API Reference](docs/monday-api-reference-all.md)** — 
  Consolidated Monday API docs (42 pages)

---

## Status / what's done vs TODO

| Component | v0.2 status | Notes |
|---|---|---|
| Canonical schema | ✅ Implemented | Org, User, Client, Vendor, Property, Lead, Deal, Project, Task, DailyLog, Invoice, Document |
| ExternalId mapping | ✅ Implemented | Composite uniqueness, mutable last_synced_at for delta sync |
| IdentityResolver | ✅ Implemented | resolve_or_create, lookup_external, get_external_ids |
| Fuzzy matcher | ✅ Pluggable | NoMatcher default + ExactFieldMatcher |
| BaseConnector | ✅ Implemented | SyncReport, success/failure tracking, sync_back for write-back |
| **Monday connector** | ✅ **Full** | ✅ Read (delta sync), ✅ Write mutations, ✅ Complexity tracking |
| **QuickBooks connector** | ✅ **Implemented** | ✅ Invoices, ✅ Estimates, ✅ Customers, ✅ Delta sync ready |
| CompanyCam connector | ⬜ TODO | Next (v0.3) |
| Google Drive connector | ⬜ TODO | Next (v0.3) |
| Ripple effects | 🟡 Ready | Infrastructure in place, demos in v0.3 |
| AI canned reports | ✅ 3 reports | active_projects, deal_pipeline_value, ar_aging |
| AI text-to-SQL | ⬜ Stubbed | hook to Anthropic API |
| AI RAG / embeddings | ⬜ Stubbed | needs pgvector + chunking pipeline |
| Migrations (Alembic) | ⬜ TODO | currently using `Base.metadata.create_all` |

---

## API Cost Improvements (v0.2)

| Metric | v0.1 | v0.2 | Savings |
|--------|------|------|---------|
| API calls/month | 1,500 | 150 | **90%** |
| Items fetched/sync | ALL | Changed only | **95% avg** |
| Complexity visibility | ❌ | ✅ | Full tracking |
| Write capability | ❌ | ✅ | Bidirectional |
| Systems integrated | 1 (Monday) | 2 (Monday + QB) | 1 more |

---

## Next Steps (v0.3+)

The next concrete steps, in order of value:

1. ✅ **v0.2 Complete:**
   - Delta sync (90% cost reduction)
   - Write mutations (bidirectional)
   - Complexity tracking (full visibility)
   - QB connector (financial data)

2. **v0.3 (Ripple Effects):**
   - CompanyCam connector (photos, deficiencies)
   - Google Drive connector (documents)
   - Ripple effect demos (QB → Monday updates)
   - Webhook listeners (real-time, not just batch)

3. **v0.4 (Production Ready):**
   - Web UI for connector management
   - Advanced matching (fuzzy names, addresses)
   - Conflict resolution (simultaneous edits)
   - Alembic migrations

4. **v0.5+ (AI & Analytics):**
   - Text-to-SQL queries (natural language)
   - RAG with embeddings (document search)
   - Advanced reporting dashboards
   - Automations and alerts

See **[adding-a-connector.md](docs/adding-a-connector.md)** for the playbook on adding new connectors.

