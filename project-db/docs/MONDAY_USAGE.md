# Monday.com — Pull, Push, Add

End-to-end recipes for moving data between your Monday workspace and the local
canonical DB. All commands assume you're in `project-db/`.

## Setup (one-time)

1. **Install the package** (Python 3.10+):
   ```bash
   pip install -e ".[dev]"
   ```
2. **Set your Monday token** in `.env`:
   ```
   MONDAY_API_TOKEN=eyJhbGciOi...
   ```
   Get a token from Monday > avatar > Admin > API. Personal tokens are fine
   for development; service-account tokens are preferred for production.
3. **Create the DB**:
   ```bash
   project_db init-db
   ```
   Creates `project_db.sqlite` and seeds one `Organization`.

You're done. Every command below works from `project-db/`.

---

## The five commands

| Command | What it does |
|---|---|
| `list-boards` | Print every Monday board with its ID, workspace, and state. |
| `pull` | Sync **everything** on Monday into the canonical DB. Idempotent. |
| `inspect` | Dump every canonical entity in the local DB with its source mappings. Use this to find canonical UUIDs. |
| `push <uuid> key=value …` | Update a canonical entity locally **and** push the change back to Monday. |
| `add-item <board_id> "Name"` | Create a new item on a Monday board and register it as a canonical Client. |

All five live in `scripts/monday_demo.py`. The `project_db` CLI also exposes
`list-boards`, `inspect-board <board_id>`, and `sync monday` — use whichever
matches the task.

---

## 1. Pull data from Monday

```bash
python scripts/monday_demo.py pull
```

What happens:

1. The connector calls `list_boards()`, classifies each by name regex
   (`DEFAULT_BOARD_MAPPING`) — CRM boards → Lead/Deal/Client, "Project
   Management" boards → ProjectBoard, etc.
2. For each board it loads the column schema once
   (`list_board_columns`, cached for the rest of the run).
3. It calls `list_items(board_id)` with full cursor pagination (200 per page).
4. Each item goes through `IdentityResolver.resolve_or_create`:
   - Exact match on `(MONDAY, entity_type, external_key)` → update existing.
   - Else fuzzy match via `ExactFieldMatcher(["name"])` → link if exactly one
     canonical entity matches.
   - Else create a new canonical entity with a fresh UUID.
5. Each item gets an `ExternalId` row with
   `external_url = https://view.monday.com/boards/{board_id}/pulses/{item_id}`
   so `sync_back` can find the board without an extra API call.

Sample output:
```
Syncing Monday -> DB for org df84eef8-8cfb-4827-a1c3-e28f15588f12...
[MONDAY] processed=87 created=0 matched=0 failed=0 duration=19.9s
```

- `created`: brand-new canonical entities
- `matched`: linked to an existing canonical entity via fuzzy match
- `processed - (created+matched)`: idempotent updates to existing rows
- Re-running `pull` after no Monday changes is a no-op.

---

## 2. Inspect what landed in the local DB

```bash
python scripts/monday_demo.py inspect
```

Prints every Client, Project, Task, Lead, Deal, User, and Invoice with their
canonical UUIDs and source mappings. The output is the **source of truth for
canonical UUIDs** — copy a UUID from here to use in a `push` command.

Example chunk:
```
------------------------------------------------------------
  PROJECTS
------------------------------------------------------------
  [80f24087-3239-492f-8f66-114dc233a30c]
    name   : Project  - Google deal
    status : ACTIVE
    budget : None
    monday : key=11976700463  url=https://view.monday.com/boards/18412569177/pulses/11976700463
```

The `[uuid]` is the canonical_id. The `monday : key=...` is what's in the
`ExternalId` table. Both are needed for `push`.

You can also inspect a single Monday board's columns and **all** its items:

```bash
project_db inspect-board 18412569177
```

This prints the column schema (column id, type, title), the heuristic
field-name assignments (e.g. `project_status -> status_label`), and every
item on the board with its extracted canonical-field values. Use this when
the column auto-detection got something wrong and you need to add an explicit
mapping in `DEFAULT_COLUMN_MAPPING`.

---

## 3. Push a change back to Monday

```bash
python scripts/monday_demo.py push <canonical_uuid> key=value [key=value …]
```

Supported logical keys (work on any board — the connector resolves them to the
real per-board column id):

| Key | Maps to | Value format |
|---|---|---|
| `status` | first `status`-type column whose title contains "status" | `Done`, `Working on it`, `On Hold`, … (status label) |
| `priority` | first `status`-type column whose title contains "priority" | `High`, `Medium`, `Low`, … |
| `date` / `due_date` | first `date`-type column | `2026-05-30` |
| `timeline` | first `timeline`-type column | not yet supported in the demo CLI |
| `budget` | first `numbers` column whose title contains "budget" | `75000` |
| `name` | not pushed (Monday's `change_name` mutation isn't wired up; coming) | — |

You can also pass a real Monday column id directly (e.g.
`project_status="Done"`) — anything that already matches a column id on the
target board is used as-is.

Example:
```bash
python scripts/monday_demo.py push 80f24087-3239-492f-8f66-114dc233a30c status=Done
```

Output:
```
Found Project: Project  - Google deal
  Local update: status = ProjectStatus.COMPLETED

Monday item: key=11976700463  url=https://view.monday.com/boards/18412569177/pulses/11976700463
Pushing column_values: {
  "status": {
    "label": "Done"
  }
}

OK: Monday updated successfully.
```

What happens behind the scenes:

1. Look up the entity (`Project`, `Lead`, or `Deal`) by canonical_id.
2. Apply the local update (so the canonical DB reflects the change too).
3. Find the `ExternalId` row, parse `board_id` from `external_url` —
   **no extra API call**.
4. `MondayConnector._resolve_column_id` maps `status` → `project_status` using
   cached column metadata.
5. Call `change_multiple_column_values(board_id, item_id, {project_status: {label: "Done"}})`.

Logical key resolution and column caching mean a 10-update push on the same
board is ~1 API call, not ~11.

### Caveats

- **ProjectBoard wrappers can't be pushed directly.** Boards like "923 Rockland"
  are stored as a canonical `Project` with `external_key=board:18412002814` and
  their items are Tasks. `sync_back` on the board wrapper is a no-op — update
  the individual Tasks instead.
- **Status labels are case-sensitive on Monday.** If pushing `status=done`
  fails, try `status=Done`. The label has to exactly match a column setting.
- **Unknown status labels** raise `ColumnValueException`. Pass
  `create_labels_if_missing=true` only if you actually want to create labels
  on the fly (not currently wired into `sync_back`).

---

## 4. Create a new Monday item

```bash
python scripts/monday_demo.py add-item <board_id> "Item Name"
```

Creates a new item on Monday via `create_item` mutation and immediately
registers it as a canonical `Client` (with the new item_id in `ExternalId`).
Useful for the demo / smoke-testing the write path.

Example:
```bash
python scripts/monday_demo.py add-item 18412569178 "Acme Corp"
```

Output:
```
Creating item 'Acme Corp' on board 18412569178...
OK: Created Monday item id=12003523257
OK: Registered as canonical Client
  canonical_id : 12f0ea3e-0472-4436-9f70-79308a6d4b53
  monday_item  : 12003523257
```

After this, running `pull` again will idempotently re-link the new item (it
won't double-create — the `ExternalId` row already exists).

---

## 5. The full demo loop

```bash
# Discover board IDs.
python scripts/monday_demo.py list-boards

# Pull everything to canonical DB.
python scripts/monday_demo.py pull

# See what landed; copy a canonical UUID.
python scripts/monday_demo.py inspect

# Push a local change to Monday.
python scripts/monday_demo.py push <uuid> status="Working on it"

# Re-pull and verify Monday reflects the new status.
python scripts/monday_demo.py pull
python scripts/monday_demo.py inspect
```

---

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `MONDAY_API_TOKEN not set` | `.env` missing or token blank | Set `MONDAY_API_TOKEN` in `project-db/.env` |
| `Unknown argument "updated_after"` | Old client code; `items_page` in API-Version 2026-07 has no `updated_after` | Pull latest `main` |
| `InvalidColumnIdException: column_id='status'` | The board's status column isn't literally named `status` | Use logical key `status=…` (auto-resolved) or run `project_db inspect-board <board_id>` to see real column ids |
| `Cannot sync_back a ProjectBoard wrapper item` | Tried to push a board-as-project entity | Push the underlying Tasks instead |
| `sync_back returned False` with no logs | Mutation declared variables incorrectly | Already fixed in `client.py`; pull latest `main` |
| Pull returns `created=0 matched=0 processed=N` | All items already synced; idempotent re-run | This is the normal steady state |

---

## API-cost notes

- A full Monday workspace pull is **one** column-schema fetch per board plus
  **one** `items_page` (with cursor) per board. ~20–30s for our workspace.
- A push is **one** mutation (`change_multiple_column_values`) per item. Board
  columns are cached on the `MondayClient` instance, so back-to-back pushes on
  the same board share that cost.
- `change_multiple_column_values` is ~150× cheaper than N `change_column_value`
  calls. The connector always uses the batched form.
- We don't currently use `complexity { before after query }` on mutations
  because wrapping a mutation in a query document breaks it. Read queries can
  pass `track_complexity=True` if you want to log the cost.
