"""Monday.com push/pull demo.

Demonstrates the full read -> inspect -> modify -> push-back cycle.

Usage (after running `project_db init-db`):

    # 1. Pull everything from Monday
    python scripts/monday_demo.py pull

    # 2. Show what landed in the local DB
    python scripts/monday_demo.py inspect

    # 3. Update a Project field locally and push it back to Monday
    python scripts/monday_demo.py push <canonical_uuid> status=Done

    # 4. Re-pull to confirm Monday reflects the change
    python scripts/monday_demo.py pull

Prerequisites
-------------
Set in .env (project-db/.env):
    MONDAY_API_TOKEN=<your_token>

Or as environment variables before running.
"""
from __future__ import annotations

import json
import sys
import uuid
from decimal import Decimal

from sqlalchemy.orm import Session

# ------------------------------------------------------------------
# Shared helpers
# ------------------------------------------------------------------


def _get_session() -> Session:
    """Open a session against the configured DB (defaults to SQLite)."""
    from project_db.db import get_engine, session_scope
    from project_db.db.base import Base

    engine = get_engine()
    Base.metadata.create_all(engine)
    return engine


def _get_org(session: Session):
    from project_db.db.models import Organization

    org = session.query(Organization).first()
    if org is None:
        print("No organization found. Run `project_db init-db` first.")
        sys.exit(1)
    return org


# ------------------------------------------------------------------
# pull: sync Monday -> canonical DB
# ------------------------------------------------------------------


def cmd_pull() -> None:
    """Pull all Monday boards into the local canonical DB."""
    from project_db.connectors.monday import MondayConnector
    from project_db.db import get_engine, session_scope
    from project_db.db.base import Base

    engine = get_engine()
    Base.metadata.create_all(engine)

    with session_scope() as session:
        org = _get_org(session)
        print(f"Syncing Monday -> DB for org {org.canonical_id}...\n")
        connector = MondayConnector(session=session, organization_id=org.canonical_id)
        report = connector.sync()
        print(report.summary())
        if report.errors:
            print("\nErrors during sync:")
            for e in report.errors:
                print(f"  ERROR: {e}")


# ------------------------------------------------------------------
# inspect: show what's in the canonical DB
# ------------------------------------------------------------------


def cmd_inspect() -> None:
    """Print a summary of every canonical entity currently in the DB."""
    from project_db.db import get_engine, session_scope
    from project_db.db.base import Base
    from project_db.db.models import (
        Client, Deal, ExternalId, Invoice, Lead, Project, SourceSystem, Task, User,
    )

    engine = get_engine()
    Base.metadata.create_all(engine)

    with session_scope() as session:
        def _header(title: str) -> None:
            print(f"\n{'-'*60}")
            print(f"  {title}")
            print(f"{'-'*60}")

        _header("CLIENTS")
        for c in session.query(Client).all():
            ext = session.query(ExternalId).filter_by(canonical_id=c.canonical_id).all()
            sources = ", ".join(f"{e.source.value}:{e.external_key}" for e in ext)
            print(f"  [{c.canonical_id}]  {c.name:<30}  email={c.email}  sources=[{sources}]")

        _header("PROJECTS")
        for p in session.query(Project).all():
            ext = session.query(ExternalId).filter_by(
                canonical_id=p.canonical_id, source=SourceSystem.MONDAY
            ).first()
            monday_key = ext.external_key if ext else "-"
            monday_url = ext.external_url if ext else "-"
            print(
                f"  [{p.canonical_id}]\n"
                f"    name   : {p.name}\n"
                f"    status : {p.status.value}\n"
                f"    budget : {p.budget_amount}\n"
                f"    monday : key={monday_key}  url={monday_url}\n"
            )

        _header("TASKS")
        for t in session.query(Task).all():
            print(f"  [{t.canonical_id}]  {t.title:<40}  status={t.status.value}")

        _header("LEADS")
        for l in session.query(Lead).all():
            print(f"  [{l.canonical_id}]  stage={l.stage.value}  value={l.estimated_value}")

        _header("DEALS")
        for d in session.query(Deal).all():
            print(f"  [{d.canonical_id}]  {d.name:<30}  stage={d.stage.value}  value={d.value}")

        _header("USERS")
        for u in session.query(User).all():
            print(f"  [{u.canonical_id}]  {u.display_name:<25}  email={u.email}")

        _header("INVOICES")
        for i in session.query(Invoice).all():
            print(f"  [{i.canonical_id}]  {i.number}  amount={i.amount}  status={i.status.value}")

        _header("EXTERNAL ID MAP")
        for e in session.query(ExternalId).order_by(ExternalId.source).all():
            print(
                f"  {e.source.value:<15} {e.entity_type:<10} "
                f"key={e.external_key:<20} -> {e.canonical_id}"
            )


# ------------------------------------------------------------------
# push: update a canonical entity and write the change back to Monday
# ------------------------------------------------------------------


def cmd_push(canonical_id_str: str, *updates: str) -> None:
    """Push field updates to Monday for a given canonical entity.

    Updates are passed as key=value pairs.

    Monday column_values mapping:
      status=<label>    ->  {"label": "<label>"}
      budget=<number>   ->  "<number>"
      name=<text>       ->  "<text>"

    Examples:
      python scripts/monday_demo.py push <uuid> status=Done
      python scripts/monday_demo.py push <uuid> status="Working on it" budget=75000
    """
    import json

    from project_db.connectors.monday import MondayConnector
    from project_db.db import get_engine, session_scope
    from project_db.db.base import Base
    from project_db.db.models import ExternalId, Project, SourceSystem

    try:
        cid = uuid.UUID(canonical_id_str)
    except ValueError:
        print(f"Error: {canonical_id_str!r} is not a valid UUID")
        sys.exit(1)

    if not updates:
        print("Error: provide at least one key=value update")
        sys.exit(1)

    # Parse key=value pairs into a Monday column_values dict
    # We convert high-level names like "status" -> Monday JSON shape
    field_updates: dict[str, object] = {}
    local_updates: dict[str, object] = {}

    for kv in updates:
        if "=" not in kv:
            print(f"Skipping malformed update: {kv!r}  (expected key=value)")
            continue
        key, _, value = kv.partition("=")
        key = key.strip()
        value = value.strip()

        if key == "status":
            # Monday status column -> {"label": "..."}
            field_updates["status"] = {"label": value}
            # Also map to canonical ProjectStatus if recognisable
            from project_db.db.models.work import ProjectStatus
            status_map = {
                "done": ProjectStatus.COMPLETED,
                "completed": ProjectStatus.COMPLETED,
                "active": ProjectStatus.ACTIVE,
                "working on it": ProjectStatus.ACTIVE,
                "on hold": ProjectStatus.ON_HOLD,
                "cancelled": ProjectStatus.CANCELLED,
            }
            canonical_status = status_map.get(value.lower())
            if canonical_status:
                local_updates["status"] = canonical_status

        elif key == "budget":
            try:
                field_updates["budget"] = str(float(value))
                local_updates["budget_amount"] = Decimal(value)
            except ValueError:
                print(f"Invalid budget value: {value!r}")
                continue

        elif key == "name":
            field_updates["name"] = value
            local_updates["name"] = value

        else:
            # Pass through unknown keys as plain string values
            field_updates[key] = value

    engine = get_engine()
    Base.metadata.create_all(engine)

    with session_scope() as session:
        org = _get_org(session)

        # Find the entity — for now we look across Project, then Lead, Deal
        entity = session.query(Project).filter_by(canonical_id=cid).one_or_none()
        entity_type = "Project"
        if entity is None:
            from project_db.db.models import Lead
            entity = session.query(Lead).filter_by(canonical_id=cid).one_or_none()
            entity_type = "Lead"
        if entity is None:
            from project_db.db.models import Deal
            entity = session.query(Deal).filter_by(canonical_id=cid).one_or_none()
            entity_type = "Deal"
        if entity is None:
            print(f"No Project/Lead/Deal found with canonical_id={cid}")
            sys.exit(1)

        print(f"Found {entity_type}: {entity.name if hasattr(entity, 'name') else cid}")

        # Apply local updates first
        for attr, val in local_updates.items():
            if hasattr(entity, attr):
                setattr(entity, attr, val)
                print(f"  Local update: {attr} = {val}")
        session.flush()

        # Look up Monday external ID to confirm the item is tracked
        ext = session.query(ExternalId).filter_by(
            canonical_id=cid,
            source=SourceSystem.MONDAY,
            entity_type=entity_type,
        ).one_or_none()

        if ext is None:
            print(
                f"\nNo Monday mapping found for this {entity_type}.\n"
                f"Run `pull` first to sync from Monday, then try push again."
            )
            session.commit()
            return

        print(f"\nMonday item: key={ext.external_key}  url={ext.external_url}")

        # Resolve logical column names to actual Monday column IDs.
        # "status" is a logical name; real column ID varies per board.
        if "status" in field_updates:
            from project_db.config import settings as _settings
            from project_db.connectors.monday.client import MondayClient
            item_id_for_lookup = int(ext.external_key)
            client_tmp = MondayClient(token=_settings.monday_api_token)
            board_id_tmp = None
            try:
                gql = "query ($ids: [ID!]!) { items(ids: $ids) { board { id } } }"
                d = client_tmp.query(gql, {"ids": [item_id_for_lookup]})
                items_tmp = d.get("items") or []
                if items_tmp:
                    board_id_tmp = int(items_tmp[0]["board"]["id"])
            except Exception:
                pass
            if board_id_tmp:
                cols = client_tmp.list_board_columns(board_id_tmp)
                status_col = next(
                    (c["id"] for c in cols if c.get("type") == "status" and "status" in c.get("title", "").lower()),
                    None,
                )
                if status_col and status_col != "status":
                    field_updates[status_col] = field_updates.pop("status")
                    print(f"  Resolved 'status' -> column id '{status_col}'")

        print(f"Pushing column_values: {json.dumps(field_updates, indent=2)}")

        connector = MondayConnector(session=session, organization_id=org.canonical_id)
        ok = connector.sync_back(entity, field_updates)

        if ok:
            print("\nOK: Monday updated successfully.")
        else:
            print(
                "\nFAIL: sync_back returned False.\n"
                "  Check logs above. Common causes:\n"
                "  - The item URL format doesn't embed a board ID (view.monday.com/<item_id>)\n"
                "  - Monday token doesn't have write permission on this board\n"
                "  - The external_key is a board: prefix (ProjectBoard — update tasks instead)"
            )


# ------------------------------------------------------------------
# add-item: create a new item on a Monday board and link it locally
# ------------------------------------------------------------------


def cmd_add_item(board_id_str: str, name: str) -> None:
    """Create a new item on a Monday board and register it in the canonical DB.

    Example:
        python scripts/monday_demo.py add-item 1234567890 "New Client ABC"
    """
    try:
        board_id = int(board_id_str)
    except ValueError:
        print(f"Error: {board_id_str!r} is not a valid board ID")
        sys.exit(1)

    from project_db.config import settings
    from project_db.connectors.monday.client import MondayClient
    from project_db.db import get_engine, session_scope
    from project_db.db.base import Base
    from project_db.db.models import Client, ExternalId, SourceSystem

    engine = get_engine()
    Base.metadata.create_all(engine)

    client = MondayClient(token=settings.monday_api_token)

    # Create the item on Monday
    print(f"Creating item {name!r} on board {board_id}...")
    result = client.create_item(board_id=board_id, item_name=name)
    item_id = result.get("id")
    if not item_id:
        print(f"Monday API returned: {result}")
        sys.exit(1)

    print(f"OK: Created Monday item id={item_id}")

    # Register it as a canonical Client in the local DB
    with session_scope() as session:
        org = _get_org(session)
        canonical = Client(name=name, organization_id=org.canonical_id)
        session.add(canonical)
        session.flush()

        ext = ExternalId(
            source=SourceSystem.MONDAY,
            entity_type="Client",
            external_key=str(item_id),
            external_url=f"https://view.monday.com/{item_id}",
            canonical_id=canonical.canonical_id,
        )
        session.add(ext)
        session.commit()

        print(
            f"OK: Registered as canonical Client\n"
            f"  canonical_id : {canonical.canonical_id}\n"
            f"  monday_item  : {item_id}"
        )


# ------------------------------------------------------------------
# list-boards: thin wrapper around the CLI for convenience
# ------------------------------------------------------------------


def cmd_list_boards() -> None:
    from project_db.cli import cmd_list_boards as _cmd
    import argparse
    _cmd(argparse.Namespace())


# ------------------------------------------------------------------
# Entrypoint
# ------------------------------------------------------------------

USAGE = """
Monday.com Push/Pull Demo
-------------------------
  python scripts/monday_demo.py list-boards
      List all Monday boards (get board IDs from here)

  python scripts/monday_demo.py pull
      Sync all Monday boards -> local canonical DB

  python scripts/monday_demo.py inspect
      Show every entity now in the local DB with source mappings

  python scripts/monday_demo.py push <uuid> status=Done
  python scripts/monday_demo.py push <uuid> status="Working on it" budget=75000
      Update a canonical entity locally and push the change back to Monday

  python scripts/monday_demo.py add-item <board_id> "Item Name"
      Create a new item on a Monday board and register it in the local DB

Typical workflow
----------------
  1. python scripts/monday_demo.py list-boards          # find your board IDs
  2. python scripts/monday_demo.py pull                 # pull everything
  3. python scripts/monday_demo.py inspect              # see what landed
  4. python scripts/monday_demo.py push <uuid> status=Done   # push a change
  5. python scripts/monday_demo.py pull                 # re-pull to confirm
  6. python scripts/monday_demo.py inspect              # verify updated status
"""


def main() -> None:
    args = sys.argv[1:]
    if not args or args[0] in ("-h", "--help"):
        print(USAGE)
        return

    cmd = args[0]

    if cmd == "pull":
        cmd_pull()
    elif cmd == "inspect":
        cmd_inspect()
    elif cmd == "push":
        if len(args) < 3:
            print("Usage: monday_demo.py push <canonical_uuid> key=value [key=value …]")
            sys.exit(1)
        cmd_push(args[1], *args[2:])
    elif cmd == "add-item":
        if len(args) < 3:
            print("Usage: monday_demo.py add-item <board_id> <item_name>")
            sys.exit(1)
        cmd_add_item(args[1], args[2])
    elif cmd == "list-boards":
        cmd_list_boards()
    else:
        print(f"Unknown command: {cmd!r}")
        print(USAGE)
        sys.exit(1)


if __name__ == "__main__":
    main()
