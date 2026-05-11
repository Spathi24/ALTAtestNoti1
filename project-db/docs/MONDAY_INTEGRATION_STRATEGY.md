# Monday.com Integration Strategy — Why, What, How

**Date:** May 2026  
**Scope:** v0.1 canonical layer + v0.2 expansion  
**Purpose:** Clarify the strategic value of Monday integration beyond "just having data on Monday"

---

## TL;DR: The Value Proposition

**Problem:** You have work, money, and photos scattered across Monday, QuickBooks, CompanyCam, and Drive. None of them know about each other. Questions like *"What's the margin on the Smith bathroom reno?"* require manually bouncing between tools.

**Solution:** Monday is the **hub**. It's where projects live, where the team collaborates, where work gets tracked. The canonical layer syncs Monday with QuickBooks, CompanyCam, and Drive—then **unifies the identity** so the AI can answer *any* question in one place.

**Value:**
- **One source of truth** for projects, tasks, team, budget, status
- **Cross-system queries** — join project status (Monday) + invoice due date (QB) + site photos (CompanyCam)
- **AI Q&A** — natural language access to everything, no tool-switching
- **Audit trail** — all changes timestamped and traced back to source
- **Reduced manual work** — no more copying project IDs between systems, no more "is this the same project?"

---

## Why Monday (Not Just QuickBooks or Direct DB Entry)?

Monday.com is where **projects start**. It's the single source of truth for:

1. **Project hierarchy & ownership** — "which property, which client, which PM?"
2. **Live task tracking** — current state, assignees, due dates (more current than QB)
3. **Team collaboration** — comments, attachments, notifications
4. **CRM pipeline** — leads, deals, activities (sales data QB doesn't have)
5. **Custom workflows** — your team has already built their process there

**Key insight:** If you made the DB the source of truth, every change would require an approval workflow. But in Monday, the team *already* changes data in real-time. The DB should *follow*, not lead.

QuickBooks is downstream — it tracks *commitments* (invoices, expenses, payments) that emerge from Monday projects. CompanyCam captures *evidence* (photos, deficiencies). Drive stores *documents*. None of them track project *intent* the way Monday does.

---

## Monday Integration Architecture

### Level 1: Board Classification & Entity Mapping

**Current State (v0.1):** Basic pattern matching

```python
DEFAULT_BOARD_MAPPING: list[dict[str, Any]] = [
    {"pattern": r"(?i)leads?", "entity": "Lead"},
    {"pattern": r"(?i)deals?", "entity": "Deal"},
    {"pattern": r"(?i)contacts?|accounts?", "entity": "Client"},
    {"pattern": r"(?i)client projects?", "entity": "Project"},
    {"pattern": r"^\d+[-\s].+", "entity": "Project"},  # address-like
]
```

**How it works:**
- Sync discovers all Monday workspaces
- For each board, regex-match the name to determine entity type
- Example: Board "Q2 2026 Leads" → Lead entities; Board "923 Rockland — Oakland" → Project entity

**Why config-driven?** The team renames boards all the time. Storing mapping in code forces redeployments. Config lets ops adjust without code changes.

---

### Level 2: Column-Value Extraction (v0.2)

**Next milestone:** Parse column values to extract canonical fields.

Monday columns map to canonical model:

| Monday Column | Canonical Field | Entity | Notes |
|---|---|---|---|
| Item name | `name` | Project, Lead, Deal, Client | Core identity |
| Status dropdown | `status` | Project, Lead, Deal | Becomes enum |
| Assigned person | `assignee_id` | Project (PM), Task | FK to User |
| Money column | `value` / `amount` | Deal, Invoice | Numeric |
| Date column | `due_date` / `start_date` | Project, Task | ISO-8601 |
| External link column | *external reference* | Project | Cross-reference to QB job number, CompanyCam project ID |
| Board connector column | Cross-board refs | Project → Client | Link to Clients board |

**Strategy:**
1. Define column mappings per board-type (config-driven again)
2. Extract column values for each item
3. Feed attributes into canonical entity creation
4. Use fuzzy matchers for dedup (e.g., match client by name)

**Example flow:**
```
Monday item (board: "Clients"):
  name: "ABC Construction"
  phone: "555-1234"
  address: "123 Main St"
  
↓ (resolve_or_create with ExactFieldMatcher on name)

Canonical Client:
  canonical_id: uuid-123
  name: "ABC Construction"
  organization_id: org-456
  
ExternalId:
  source: MONDAY
  entity_type: Client
  external_key: monday-item-99
  canonical_id: uuid-123
```

---

### Level 3: Webhook-Driven Real-Time Sync (v0.2/v0.3)

**Current state:** Nightly batch sync only.

**Next:** Webhooks for live updates.

Monday webhooks fire when items/columns change:
```
POST /sync-webhook (authenticated)
{
  "event": "create_item",
  "board_id": 12345,
  "item_id": 67890,
  "user_id": 11,
  "changes": [
    {"field": "name", "value": "New Project Name"},
    {"field": "status", "value": "Active"}
  ]
}
```

**Handler logic:**
1. Validate webhook signature
2. Fetch full item from Monday (webhook gives partial data)
3. Call resolver.resolve_or_create() → upsert canonical entity
4. Emit event (for audit, AI indexing, etc.)

**Why?** Work status in Monday changes constantly. Nightly sync means the AI answers yesterday's questions. Webhooks mean real-time Q&A.

---

## Data Flow: Monday → Canonical → Queries

```
┌─────────────────────────────────────────────────────────────────┐
│ MONDAY.COM (Source of Truth)                                    │
├─────────────────────────────────────────────────────────────────┤
│ Workspaces: CRM | Project Management | Admin                    │
│  ├─ Leads board (lead items, stage, notes)                      │
│  ├─ Deals board (deal name, value, client link, stage)          │
│  ├─ Clients board (account, phone, address)                     │
│  ├─ "923 Rockland — Oakland" board (project, PM, status)        │
│  ├─ Tasks board (task, assigned to, due date)                   │
│  └─ Activities board (completed actions, timestamps)            │
└──────────────────────┬──────────────────────────────────────────┘
                       │
         ┌─────────────▼──────────────┐
         │  Python Connector (v0.1)   │
         │  • Discovers boards        │
         │  • Classifies by pattern   │
         │  • Extracts column values  │
         │  • Calls resolver          │
         └─────────────┬──────────────┘
                       │
         ┌─────────────▼────────────────────────┐
         │ Identity Resolver                    │
         │ • Exact match: (source, ext_key)    │
         │ • Fuzzy match: entity matcher       │
         │ • Create canonical entity if new    │
         │ • Register ExternalId mapping       │
         └─────────────┬────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────────────────┐
│ CANONICAL DB (Postgres + SQLAlchemy)                            │
├──────────────────────────────────────────────────────────────────┤
│ Organization (tenant)                                            │
│  ├─ Project (uuid-1, name, client_fk, status, ...)             │
│  ├─ Task (uuid-2, name, project_fk, assignee_fk, ...)          │
│  ├─ Lead (uuid-3, stage, source_channel, ...)                  │
│  ├─ Deal (uuid-4, client_fk, value, stage, ...)                │
│  ├─ Client (uuid-5, name, address, ...)                        │
│  ├─ User (uuid-6, email, name, ...)                            │
│  └─ ExternalId mapping:                                         │
│      (source=MONDAY, entity_type=Project, external_key=m123,   │
│       canonical_id=uuid-1, last_synced_at, ...)                │
│                                                                  │
│ + Later: Invoice (QB), DailyLog (CompanyCam), Document (Drive) │
└──────────────────────┬──────────────────────────────────────────┘
                       │
     ┌─────────────────┼─────────────────┐
     │                 │                 │
 ┌───▼───┐      ┌─────▼────┐       ┌────▼────┐
 │ AI Q&A│      │ SQL Views│       │ Webhooks│
 └───────┘      └──────────┘       │ Indexing│
     │               │              └─────────┘
     │          ┌────▼────┐
     │          │ Dashboard
     │          └─────────
  "Show me      SQL: SELECT p.name, p.status, i.amount, i.due_date
all invoices   FROM project p
for the        LEFT JOIN invoice i ON p.id = i.project_id
Smith           WHERE p.client_id = (SELECT canonical_id FROM client WHERE name ILIKE 'Smith%')
project"
```

---

## What Monday Provides vs. What the Canonical Layer Adds

### Just Monday (Today)
- ✅ Project list
- ✅ Team can see tasks & status
- ✅ Conversations & comments
- ❌ **No** invoice/payment data
- ❌ **No** site photos
- ❌ **No** documents (unless manually linked)
- ❌ **No** historical financials
- ❌ **No** unified queries across systems
- ❌ **No** AI access

### With Canonical Layer
- ✅ All Monday data + QB invoices, payments, expenses
- ✅ All Monday data + CompanyCam photos, deficiencies, daily logs
- ✅ All Monday data + Drive documents (contracts, quotes, reports)
- ✅ **One** unified project view (status + budget + photos + docs)
- ✅ Cross-system queries: *"Show me projects with unpaid invoices"*
- ✅ AI Q&A: *"What's the margin on the Anderson bathroom?"* (pulls status from Monday, costs from QB, photos from CompanyCam)
- ✅ Audit trail: what changed, when, from which source
- ✅ **No tool switching** — everything accessible via natural language

---

## Deduplication Strategy

### Problem
Monday project `"923 Rockland"` exists as:
- Monday item ID: 99999 (Project board)
- QuickBooks Job: 923 (in QB customer record)
- CompanyCam project: "923 Rockland — Reno" (ID: cam-987)
- Drive folder: "923 Rockland Reno" (folder ID: drive-xyz)

**Without dedup:** Four separate records, no way to join them.  
**With dedup:** One canonical Project, four ExternalId mappings → AI can query everything.

### Current v0.1 Approach: Exact Match + Fuzzy Match

**Phase 1: Exact match (highest confidence)**
```python
# If Monday item has a column "QB Job Number" with value "923",
# we can register the ExternalId immediately:
external_id = ExternalId(
    source=MONDAY,
    entity_type="Project",
    external_key="99999",  # Monday item ID
    canonical_id=uuid-1,   # created from Monday data
)

# Later, when QB sync runs:
existing_ext_id = session.query(ExternalId).filter_by(
    canonical_id=uuid-1,
    external_key="923"  # QB job number
).one_or_none()
# → QB data updates the same canonical Project
```

**Phase 2: Fuzzy match (good enough)**
```python
# CompanyCam project "923 Rockland — Reno" arrives
# We have no exact QB/Monday cross-reference, so:
matcher = ExactFieldMatcher(["address"])

# Query canonicals: find Project with address like "923 Rockland"
match = session.query(Project).filter(
    Project.address.ilike("%923 Rockland%")
).one_or_none()

# If found, link CompanyCam to the same canonical Project
if match:
    ext_id = ExternalId(
        source=COMPANYCAM,
        entity_type="Project",
        external_key="cam-987",
        canonical_id=match.canonical_id
    )
    # Both Monday and CompanyCam now resolve to same Project UUID
```

**Phase 3: Manual review for ambiguous cases**
```python
# If exact match returns 2+ results (ambiguous), DON'T auto-merge.
# Log for manual review: "Ambiguous match for Project 'Smith'— could be
# 'Smith Bathroom' or 'Smith Landscaping'."
# Ops resolves in UI, locks the mapping, AI learns for future.
```

### Why This Prevents Data Loss

- **No silent merges.** If fuzzy match is ambiguous, humans decide.
- **Reversible.** An ExternalId mapping can be removed/corrected without data loss.
- **Audit trail.** Every sync records which source created/updated which field.
- **Graceful degradation.** If dedup fails, you get duplicates, not false merges.

---

## v0.1 Monday Scope (Current)

### What's Implemented
✅ Board discovery + classification  
✅ Basic item pull (name, state, created_at, updated_at)  
✅ Entity upsert for Project, Lead, Deal, Client  
✅ Placeholder client for projects (all projects point to "Unknown Client" for now)  
✅ ExternalId registration (exact match)  

### What's Missing
❌ Column value extraction (accessing custom fields on items)  
❌ Cross-board relationships (Clients → Projects, Deals → Projects)  
❌ User/assignee resolution  
❌ Webhook integration  
❌ Pagination (hardcoded limit: 100 items/board)  
❌ Rate limiting (Monday: 5000 calls/day depending on plan)  

### Why v0.1 is minimal
- **Column values are schema-dependent.** Every workspace customizes columns. v0.1 extracts name only (which exists on every board).
- **Webhooks add operational complexity.** v0.1 uses nightly batch. Adds robustness incrementally.
- **Pagination requires state tracking.** v0.1 assumes <100 items/board (unrealistic, but testable).

---

## v0.2+ Roadmap

### v0.2: Column Extraction + Relationships (2–3 weeks)
- [ ] Define column mapping schema (config: which board columns map to which canonical fields)
- [ ] Extract custom column values (status, money, date, dropdown)
- [ ] Parse board-connector columns (link to Clients board)
- [ ] Implement fuzzy matchers for Client, User, Property
- [ ] Validate dedup against real data

### v0.3: Webhooks + Real-Time (2–4 weeks)
- [ ] Implement webhook receiver (`POST /webhooks/monday`)
- [ ] Validate webhook signatures
- [ ] Queue incoming events (SQS or Postgres queue)
- [ ] Process queue asynchronously (avoids slow webhook timeouts)
- [ ] Test high-throughput scenarios

### v0.4: Multi-Source Sync (3–6 weeks)
- [ ] QuickBooks sync (via Airbyte or custom)
- [ ] Cross-reference Project ↔ Invoice, Project ↔ Payment
- [ ] CompanyCam daily log sync
- [ ] Drive document metadata sync

### v0.5: AI Integration (2–4 weeks)
- [ ] Canned reports (project P&L, AR aging, project status)
- [ ] Text-to-SQL queries against canonical schema
- [ ] Webhook-triggered indexing (new projects, status changes)

---

## Implementation Sequence for v0.1 → Now

### Phase A: Stabilize Monday Connector (This Week)
1. Test board discovery against your live Monday workspace
2. Validate board classification patterns (do they match your actual board names?)
3. Run full sync; observe ExternalId creation
4. **Action item:** List all Monday boards + desired entity mappings; confirm pattern config

### Phase B: Add Client Column Extraction (Next Week)
1. Add a "Client Link" column to your Project board (board connector type)
2. Update connector to parse this column
3. When syncing Project item, look up linked Client item
4. Register ExternalId for both Client and Project
5. Verify "Unknown Client" placeholder is replaced by real clients

### Phase C: Cross-Validate with QB (Week After)
1. Get a QuickBooks API token
2. Implement minimal QB sync (jobs only — no invoices/payments yet)
3. For each QB job, extract job number (maps to Monday Project)
4. Run resolver with exact matcher on job number
5. Verify projects are linked across Monday ↔ QB

### Phase D: AI Q&A Pilot (3–4 Weeks)
1. Build 3 canned SQL reports (project status, active projects, top clients)
2. Test LLM integration against canonical DB
3. Internal beta: does AI return correct answers?

---

## Key Decisions: What's True Right Now?

### Decision 1: Who Creates Projects?
**Assumption (confirm):** PM or sales creates Project in Monday first.  
**Then:** QB job is created later, referencing Monday project ID.  
**Implication:** Monday is source-of-truth for project identity; QB is downstream.

### Decision 2: Must Every Project Have a Client?
**Assumption:** Yes (FK constraint in schema).  
**If false:** Change `client_id` to nullable; allow internal/exploratory projects.

### Decision 3: Board Names Are Stable?
**Assumption:** Board names rarely change (but column names do).  
**If false:** Add a board name → canonical ID mapping table; ops can adjust without code/config.

### Decision 4: One Monday Account = One Organization?
**Assumption:** Yes (scoping for single company, single org).  
**If false:** Need workspace → Organization mapping; adds multi-tenancy complexity.

---

## Questions for You (Before v0.2)

1. **What Monday boards do you actually have?** (list them + desired entity type)
2. **What columns define a client in your workflow?** (name only? phone? address?)
3. **How is a project "linked" to a client in Monday today?** (board connector? lookup column? text field?)
4. **Do you create projects in Monday, or does QB create them first?**
5. **Are there projects without clients?** (research, scoping, internal work)
6. **When is Monday data "too old"?** (nightly sync ok? or need real-time?)

---

## Quick Start: Validate v0.1 This Week

```bash
# 1. Set Monday API token
export MONDAY_API_TOKEN=<your token from Monday > Admin > API>

# 2. Run sync against your workspace
python -m project_db.cli sync --source monday --organization-id <your org uuid>

# 3. Check logs
# Expected output:
#   Found N Monday workspaces
#   Found M boards across all workspaces
#   syncing board "Leads" as Lead — K items
#   Created new Lead canonical_id=<uuid> from monday:<item_id>
#   ...

# 4. Query canonical DB
psql -U postgres -d project_db -c \
  "SELECT entity_type, COUNT(*) FROM external_id WHERE source = 'MONDAY' GROUP BY entity_type;"

# Expected output:
#   entity_type | count
#   ─────────────┼─────
#   Lead        |    12
#   Project     |     8
#   Client      |     5
```

---

## Summary: The Move

**Monday is not just "a tool to put data into."** It's the **operational hub** — the system your team uses every day to build, plan, and execute work.

The canonical layer **mirrors Monday's decisions** (projects, tasks, status, assignments) while **augmenting with data from elsewhere** (QB financial truth, CompanyCam photographic evidence, Drive legal/contract basis).

**The unified database then enables:**
- AI that answers real questions in real time
- Reports that join work + money + photos + docs in one query
- Audit trail of who did what, when, and which source system it came from
- Reduced manual work (no copying IDs between systems)

**v0.1 goal:** Prove the plumbing works. Sync Monday projects/tasks/clients. Verify ExternalId dedup. Build confidence in data.

**v0.2 goal:** Add QB + CompanyCam. Answer cross-system queries. Unlock AI.

**v0.3+ goal:** Real-time webhooks, advanced analytics, write-back actions.

---

*Questions? Clarifications? Run the quick-start validation above and we'll iterate based on what your Monday workspace actually looks like.*
