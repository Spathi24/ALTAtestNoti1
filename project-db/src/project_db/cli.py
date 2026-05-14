"""Command-line entry point for the project DB.

Usage:
    project_db init-db
    project_db sync monday
    project_db list-boards
    project_db inspect-board <board_id>
    project_db ask "what active projects do we have?"
    project_db list-external Project <canonical-id>
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
import uuid

from project_db.ai import AiAssistant
from project_db.connectors import available_sources, get_connector_class
from project_db.db import Base, ensure_sqlite_schema, get_engine, session_scope
from project_db.db.models import (  # noqa: F401 — needed for metadata to know about tables
    Client,
    DailyLog,
    Deal,
    Document,
    ExternalId,
    Invoice,
    Lead,
    Organization,
    Project,
    Property,
    SourceSystem,
    Task,
    User,
    Vendor,
)


def cmd_init_db(_: argparse.Namespace) -> int:
    """Create all tables and seed one Organization row if empty."""
    engine = get_engine()
    Base.metadata.create_all(engine)
    ensure_sqlite_schema(engine)
    print("Tables created.")
    with session_scope() as s:
        if s.query(Organization).count() == 0:
            org = Organization(name="Default Org")
            s.add(org)
            s.flush()
            print(f"Seeded default organization: {org.canonical_id}")
        else:
            org = s.query(Organization).first()
            print(f"Organization already exists: {org.canonical_id}")
    return 0


def cmd_sync(args: argparse.Namespace) -> int:
    try:
        source = SourceSystem[args.source.upper()]
    except KeyError:
        print(f"Unknown source: {args.source}", file=sys.stderr)
        print(f"Available: {[s.value for s in available_sources()]}", file=sys.stderr)
        return 2
    try:
        connector_cls = get_connector_class(source)
    except NotImplementedError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    engine = get_engine()
    Base.metadata.create_all(engine)
    ensure_sqlite_schema(engine)

    with session_scope() as s:
        org = s.query(Organization).first()
        if org is None:
            print("No organization found. Run init-db first.", file=sys.stderr)
            return 2
        connector = connector_cls(session=s, organization_id=org.canonical_id)
        report = connector.sync()
        print(report.summary())
        if report.errors:
            print("Errors:")
            for e in report.errors:
                print(f"  - {e}")
    return 0


def cmd_list_boards(_: argparse.Namespace) -> int:
    """List all Monday boards with their IDs."""
    from project_db.config import settings
    from project_db.connectors.monday.client import MondayClient

    client = MondayClient(token=settings.monday_api_token)
    boards = client.list_boards()
    if not boards:
        print("No boards found.")
        return 0

    print(f"{'ID':<15} {'Workspace':<25} {'State':<10} Name")
    print("-" * 80)
    for b in boards:
        ws_name = (b.get("workspace") or {}).get("name", "-")
        print(f"{b['id']:<15} {ws_name:<25} {b.get('state',''):<10} {b['name']}")
    return 0


def cmd_inspect_board(args: argparse.Namespace) -> int:
    """Show a board's columns and sample items — use this to tune column mapping."""
    from project_db.config import settings
    from project_db.connectors.monday.client import MondayClient
    from project_db.connectors.monday.column_extractor import ColumnExtractor

    board_id = int(args.board_id)
    client = MondayClient(token=settings.monday_api_token)

    print(f"\nFetching board {board_id} ...\n")

    columns = client.list_board_columns(board_id)
    if not columns:
        print("No columns returned. Check the board ID.")
        return 1

    print(f"{'Column ID':<20} {'Type':<18} Title")
    print("-" * 65)
    for col in columns:
        print(f"{col['id']:<20} {col['type']:<18} {col['title']}")

    extractor = ColumnExtractor(columns)
    assignments = {**extractor._heuristic}
    if assignments:
        print("\nHeuristic field assignments (auto-detected):")
        for col_id, field_name in assignments.items():
            title = extractor._col_meta[col_id]["title"]
            print(f"  {col_id:<20} -> {field_name}  (title: {title!r})")
    else:
        print("\nNo columns matched heuristics — add explicit_mapping in connector config.")

    print(f"\nFetching all items on board {board_id} ...")
    items = client.list_items(board_id)
    if not items:
        print("Board is empty.")
        return 0

    print(f"\n{'Item ID':<15} {'Group':<20} Name  ({len(items)} items total)")
    print("-" * 65)
    for item in items:
        group_title = (item.get("group") or {}).get("title", "-")
        print(f"{item['id']:<15} {group_title:<20} {item['name']}")
        fields = extractor.extract(item.get("column_values") or [])
        field_dict = {
            k: v for k, v in vars(fields).items()
            if v and v != [] and k != "unmatched"
        }
        for k, v in field_dict.items():
            print(f"    {k}: {v}")
        if fields.unmatched:
            print(f"    unmatched: {fields.unmatched}")

    return 0


def cmd_ask(args: argparse.Namespace) -> int:
    question = " ".join(args.question)
    with session_scope() as s:
        assistant = AiAssistant(s)
        response = assistant.ask(question)
        print(f"[mode={response.mode}", end="")
        if response.used_report:
            print(f" report={response.used_report}", end="")
        print("]")
        print(json.dumps(response.answer, indent=2, default=str))
    return 0


def cmd_list_external(args: argparse.Namespace) -> int:
    """Show every source-system ID for a canonical entity."""
    from project_db.ai.views import report_entity_external_ids

    try:
        cid = uuid.UUID(args.canonical_id)
    except ValueError:
        print(f"Invalid UUID: {args.canonical_id}", file=sys.stderr)
        return 2
    with session_scope() as s:
        rows = report_entity_external_ids(s, args.entity_type, str(cid))
        print(json.dumps(rows, indent=2, default=str))
    return 0


def cmd_list_sources(_: argparse.Namespace) -> int:
    for s in available_sources():
        print(s.value)
    return 0


def cmd_gdrive_auth(_: argparse.Namespace) -> int:
    """One-time OAuth browser flow to authorize Google Drive access.

    Only needed when GDRIVE_SA_KEY_PATH points to an OAuth Desktop client
    secret JSON (the kind you download from Google Cloud Console).
    Service-account credentials never need this step.
    """
    import json
    import os

    from project_db.connectors.gdrive.client import SCOPES

    client_secret_path = os.environ.get("GDRIVE_SA_KEY_PATH")
    if not client_secret_path:
        print("FAIL: GDRIVE_SA_KEY_PATH is not set in your .env file.", file=sys.stderr)
        return 2

    if not os.path.exists(client_secret_path):
        print(f"FAIL: File not found: {client_secret_path}", file=sys.stderr)
        return 2

    # Confirm this is an OAuth client secret, not a service account.
    with open(client_secret_path) as fh:
        cred_data = json.load(fh)

    if cred_data.get("type") == "service_account":
        print("This credential is a service account -- no browser auth needed.")
        print("Service accounts authenticate headlessly. Try: project_db sync GOOGLE_DRIVE")
        return 0

    if "installed" not in cred_data and "web" not in cred_data:
        print(f"FAIL: Unrecognized credential format in {client_secret_path}", file=sys.stderr)
        return 2

    try:
        from google_auth_oauthlib.flow import InstalledAppFlow
    except ImportError:
        print(
            "FAIL: google-auth-oauthlib is not installed.\n"
            "Run: pip install google-auth-oauthlib",
            file=sys.stderr,
        )
        return 2

    token_path = os.environ.get("GDRIVE_TOKEN_PATH") or os.path.join(
        os.path.dirname(os.path.abspath(client_secret_path)), "gdrive_token.json"
    )

    print("Opening browser for Google Drive authorization...")
    print("Sign in with the Google account that owns the Drive you want to sync.\n")

    flow = InstalledAppFlow.from_client_secrets_file(client_secret_path, SCOPES)
    creds = flow.run_local_server(port=0, open_browser=True)

    with open(token_path, "w") as fh:
        fh.write(creds.to_json())

    print(f"\nOK: Token saved to {token_path}")
    print("You can now run: project_db sync GOOGLE_DRIVE")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="project_db")
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("init-db", help="Create tables + seed org").set_defaults(func=cmd_init_db)
    sub.add_parser("list-sources", help="Show registered connectors").set_defaults(
        func=cmd_list_sources
    )
    sub.add_parser("list-boards", help="List Monday boards with IDs").set_defaults(
        func=cmd_list_boards
    )

    inspect = sub.add_parser(
        "inspect-board",
        help="Show board columns + sample item extraction (use before sync to tune mapping)",
    )
    inspect.add_argument("board_id", help="Monday board ID (from list-boards)")
    inspect.set_defaults(func=cmd_inspect_board)

    sync = sub.add_parser("sync", help="Run a connector sync")
    sync.add_argument("source", help="e.g. monday")
    sync.set_defaults(func=cmd_sync)

    ask = sub.add_parser("ask", help="Ask the AI assistant a question")
    ask.add_argument("question", nargs="+")
    ask.set_defaults(func=cmd_ask)

    le = sub.add_parser(
        "list-external", help="Show all external IDs for one canonical entity"
    )
    le.add_argument("entity_type", help="e.g. Project, Client")
    le.add_argument("canonical_id", help="UUID of the canonical entity")
    le.set_defaults(func=cmd_list_external)

    sub.add_parser(
        "gdrive-auth",
        help="One-time browser login for Google Drive (OAuth Desktop credentials only)",
    ).set_defaults(func=cmd_gdrive_auth)

    return p


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
