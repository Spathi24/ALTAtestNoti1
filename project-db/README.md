# project_db — v0.1 skeleton

Unified project database that pulls data from Monday.com, CompanyCam, QuickBooks,
and Google Drive into a single canonical schema, with an AI assistant layer
on top for Q&A and reporting.

This is a **skeleton**, not a finished product. The goal is to lock in the
architecture (canonical IDs, modular connectors, pluggable matchers, pluggable
AI modes) so the rest of the work can happen in parallel without rework.

---

## What's here

```
project-db/
├── docs/
│   ├── design-v0.1.md           ← the architectural design doc
│   ├── model-v0.1.ump           ← Umple UML — v0.1 skeleton model
│   ├── model-full.ump           ← Umple UML — full target model
│   └── adding-a-connector.md    ← how to plug in a new source
├── src/project_db/
│   ├── db/                      ← SQLAlchemy models (canonical schema)
│   ├── identity/                ← canonical-ID resolver + fuzzy matchers
│   ├── connectors/              ← one subpackage per source system
│   │   ├── base.py              ← abstract Connector class
│   │   ├── registry.py          ← lookup by SourceSystem enum
│   │   └── monday/              ← reference implementation
│   ├── ai/                      ← AI assistant — canned reports, text-to-SQL stub
│   ├── cli.py                   ← `project_db ...` command-line
│   └── config.py                ← env-var loading
├── tests/                       ← smoke tests for identity resolution
├── scripts/init_db.py           ← one-shot DB init helper
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

# 5. With a Monday API token in your env, run a sync
export MONDAY_API_TOKEN=...
python -m project_db.cli sync monday

# 6. Ask the AI assistant something
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

The whole point of this structure: **adding a new source = subclass
`BaseConnector` + register it**. Everything else (schema, identity, AI) is
unchanged.

---

## Status / what's done vs TODO

| Component | v0.1 status | Notes |
|---|---|---|
| Canonical schema | ✅ Implemented | Org, User, Client, Vendor, Property, Lead, Deal, Project, Task, DailyLog, Invoice, Document |
| ExternalId mapping | ✅ Implemented | Composite uniqueness, mutable last_synced_at |
| IdentityResolver | ✅ Implemented | resolve_or_create, lookup_external, get_external_ids |
| Fuzzy matcher | ✅ Pluggable | NoMatcher default + ExactFieldMatcher |
| BaseConnector | ✅ Implemented | SyncReport, success/failure tracking |
| Monday connector | 🟡 Partial | Auth + board/item fetch works; column-value mapping for Client/Property linkage is stubbed |
| CompanyCam connector | ⬜ TODO | |
| QuickBooks connector | ⬜ TODO | |
| Google Drive connector | ⬜ TODO | |
| AI canned reports | ✅ 3 reports | active_projects, deal_pipeline_value, ar_aging |
| AI text-to-SQL | ⬜ Stubbed | hook to Anthropic API |
| AI RAG / embeddings | ⬜ Stubbed | needs pgvector + chunking pipeline |
| Migrations (Alembic) | ⬜ TODO | currently using `Base.metadata.create_all` |

---

## Where to go from here

The next concrete steps, in order of value:

1. **Decide the open questions** in `docs/design-v0.1.md` — especially "who
   creates a Project first" and "permissions model".
2. **Finish Monday column-value mapping** so Projects link to real Clients
   instead of an "Unknown Client" placeholder.
3. **Add the QuickBooks connector.** Most leverage for finance reporting.
4. **Swap sqlite for Postgres** on Supabase or Neon. Five-minute change.
5. **Wire Alembic** for migrations before the schema starts drifting.
6. **Stand up the AI text-to-SQL mode** once you have a few weeks of real
   data and trust the schema.

See `docs/adding-a-connector.md` for the playbook on step 3.
