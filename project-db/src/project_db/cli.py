"""Command-line entry point for the project DB.

Usage:
    python -m project_db.cli init-db
    python -m project_db.cli sync monday
    python -m project_db.cli ask "what active projects do we have?"
    python -m project_db.cli list-external Project <canonical-id>
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
import uuid

from project_db.ai import AiAssistant
from project_db.connectors import available_sources, get_connector_class
from project_db.db import Base, get_engine, session_scope
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
    print("Tables created.")
    with session_scope() as s:
        if s.query(Organization).count() == 0:
            org = Organization(name="Default Org")
            s.add(org)
            s.flush()
            print(f"Seeded default organization: {org.canonical_id}")
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


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="project_db")
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("init-db", help="Create tables").set_defaults(func=cmd_init_db)
    sub.add_parser("list-sources", help="Show registered connectors").set_defaults(
        func=cmd_list_sources
    )

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

    return p


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
