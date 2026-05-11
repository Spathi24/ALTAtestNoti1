# Adding a new connector

This is the single most common kind of contribution to this repo. The whole
codebase is structured so adding a new source = predictable, repeatable steps.

## Steps

### 1. Create the subpackage

```
src/project_db/connectors/<source_name>/
├── __init__.py
├── client.py        ← thin wrapper around the source's API
└── connector.py     ← maps source data → canonical entities
```

### 2. Implement the API client

`client.py` is just a wrapper. It should:

- Read credentials from environment variables (and accept overrides for tests).
- Expose typed methods like `list_projects()` that return `list[dict]`.
- Handle pagination internally — the connector shouldn't think about it.
- Raise on auth errors — let the connector log and report.

Look at `connectors/monday/client.py` for the reference shape.

### 3. Implement the Connector

```python
from project_db.connectors.base import BaseConnector
from project_db.db.models import SourceSystem

class CompanyCamConnector(BaseConnector):
    source = SourceSystem.COMPANYCAM

    def sync(self):
        # 1. Pull data from self.client
        # 2. For each record, call self.resolver.resolve_or_create(...)
        # 3. Track results with self._record_result(...)
        # 4. Return self._finalize()
        ...
```

Three things every connector must do inside `sync()`:

1. **Set up the API client.** Usually in `__init__`.
2. **For every source record, call `self.resolver.resolve_or_create(...)`.**
   Pass the SourceSystem, the source's external key, the target canonical
   class, and the mapped attributes. Pick the right matcher per entity type.
3. **Track success/failure** via `self._record_result()` and `self._record_failure()`.
   Always `return self._finalize()`.

### 4. Add the SourceSystem enum value

If your source isn't already in `db/models/canonical.py` → `SourceSystem`,
add it.

### 5. Register in the registry

In `connectors/registry.py`:

```python
from project_db.connectors.companycam.connector import CompanyCamConnector

_REGISTRY = {
    SourceSystem.MONDAY: MondayConnector,
    SourceSystem.COMPANYCAM: CompanyCamConnector,   # ← add this
    ...
}
```

### 6. Add credentials to `.env.example`

So the next person knows what env vars to set.

### 7. Smoke-test it

```bash
python -m project_db.cli sync companycam
```

---

## Picking the right matcher

When the resolver doesn't find an exact ExternalId hit, it falls back to a
**Matcher** to dedupe against existing canonical entities. Pick one per
entity type:

| Entity | Suggested matcher | Why |
|---|---|---|
| Client | `ExactFieldMatcher(["name"])` | Names are usually unique within one org |
| Vendor | `ExactFieldMatcher(["name"])` | Same |
| User | `ExactFieldMatcher(["email"])` | Email is the canonical identity for a person |
| Property | `ExactFieldMatcher(["address"])` | Address is the natural key |
| Project | `NoMatcher()` | Projects are too easy to confuse — let humans merge |
| Lead / Deal | `NoMatcher()` | Same |

When in doubt, **use `NoMatcher()`**. Better to over-create and merge by hand
later than to silently merge two distinct entities.

---

## Common gotchas

- **Foreign keys aren't optional.** If your source has a Project record but
  no associated Client info yet, you can't insert the Project without a
  `client_id`. Either resolve the Client first, or attach to a placeholder
  (see `MondayConnector._get_or_create_placeholder_client_id`) and fix in a
  later pass.
- **Don't store raw API payloads in the canonical tables.** If you need them
  for debugging, add an `ExternalId.raw_payload_hash` and stash the full JSON
  in object storage keyed by hash.
- **Pagination is your problem, not the resolver's.** The resolver assumes
  one record at a time.
- **Webhooks vs polling.** For v0.1, just poll on a cron. Webhooks are a
  v0.2 concern.
