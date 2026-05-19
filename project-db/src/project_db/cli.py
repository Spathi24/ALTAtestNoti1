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
import os
import sys
import uuid

# Importing config triggers python-dotenv to load .env into os.environ.
# Must happen before any os.environ.get(...) calls below.
from project_db import config as _config  # noqa: F401
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
        # --delta is only meaningful for Monday today (Drive's sync already
        # uses changes.list internally).  Other connectors silently ignore.
        sync_kwargs = {}
        if getattr(args, "delta", False) and source == SourceSystem.MONDAY:
            sync_kwargs["delta"] = True
        report = connector.sync(**sync_kwargs)
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


def cmd_extract_content(args: argparse.Namespace) -> int:
    """Run text extraction over already-synced Documents.

    Pulls bytes from Drive (via export or download), runs the appropriate
    parser, writes DocumentText rows.  Safe to run repeatedly:
      --missing-only (default): only Documents with no DocumentText yet
      --overwrite:               re-extract everything, replacing existing rows
      --project <UUID>:          restrict to one project's documents
      --limit <N>:               stop after N documents (good for smoke tests)

    Documents we deliberately can't read (unsupported mime, too big) still
    get a DocumentText row with extraction_method='skipped-*' so we don't
    re-check them every run.
    """
    from project_db.connectors.gdrive.client import GDriveClient
    from project_db.connectors.gdrive.content_pipeline import extract_and_store

    overwrite = bool(args.overwrite)
    missing_only = not overwrite  # default mode

    engine = get_engine()
    Base.metadata.create_all(engine)
    ensure_sqlite_schema(engine)

    project_filter = None
    if args.project:
        try:
            project_filter = uuid.UUID(args.project)
        except ValueError:
            print(f"FAIL: Invalid project UUID: {args.project}", file=sys.stderr)
            return 2

    try:
        client = GDriveClient()
    except RuntimeError as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 2

    # NOTE: we manage the session manually instead of using session_scope() so we
    # can commit periodically.  A 750-doc run that crashes (or gets Ctrl-C'd) on
    # doc 500 would otherwise lose all 500 rows -- session_scope only commits at
    # the end.  Periodic commits cap that loss at <COMMIT_EVERY> rows.
    COMMIT_EVERY = 25
    counts: dict[str, int] = {"extracted": 0, "failed": 0, "noop": 0}
    from project_db.db import get_session_factory
    from project_db.db.models import DocumentText

    s = get_session_factory()()
    try:
        q = s.query(Document).filter(Document.is_trashed.is_(False))
        if project_filter is not None:
            q = q.filter(Document.project_id == project_filter)
        if missing_only:
            q = q.outerjoin(DocumentText, DocumentText.document_id == Document.canonical_id)
            q = q.filter(DocumentText.document_id.is_(None))
        if args.limit:
            q = q.limit(int(args.limit))

        docs = q.all()
        total = len(docs)
        print(f"Processing {total} document(s)... (commit every {COMMIT_EVERY})")
        for i, doc in enumerate(docs, 1):
            try:
                row = extract_and_store(
                    session=s, client=client, document=doc, overwrite=overwrite,
                )
            except Exception as exc:  # noqa: BLE001
                print(f"  [{i}/{total}] UNHANDLED {doc.name[:40]!r}: {exc}")
                counts["failed"] += 1
                continue

            method = row.extraction_method
            if method.startswith("skipped-"):
                counts[method] = counts.get(method, 0) + 1
            elif method.startswith("failed-"):
                counts["failed"] += 1
            elif row.extracted_text:
                counts["extracted"] += 1
            else:
                counts["noop"] += 1
            if i % COMMIT_EVERY == 0 or i == total:
                s.commit()
                print(f"  [{i}/{total}] committed. last={doc.name[:40]!r} method={method}")
    except KeyboardInterrupt:
        print("\nInterrupted -- committing partial progress...")
        s.commit()
        print("Partial progress saved.")
    except Exception:
        s.rollback()
        raise
    finally:
        s.close()

    print("\n--- Summary ---")
    for k, v in sorted(counts.items()):
        print(f"  {k:>16}: {v}")
    return 0


def cmd_llm_test(args: argparse.Namespace) -> int:
    """Smoke-test the LLM stack end-to-end against a real project.

    Picks the configured provider via LLM_PROVIDER env var (mock /
    anthropic / openai-compatible), assembles a real project context,
    sends a short "describe this project briefly" prompt, prints the
    model's response.

    This is intentionally a one-shot prove-the-wires command, NOT
    proposal generation -- it doesn't write Proposal rows.  It exists
    so you can verify the whole stack (context assembler -> provider ->
    real model) before Phase 3b's real prompts go in.
    """
    from project_db.ai import (
        LLMMessage,
        LLMProviderError,
        assemble_project_context,
        get_default_provider,
    )
    from project_db.ai.views import _resolve_project

    try:
        provider = get_default_provider()
    except LLMProviderError as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        print(
            "\nSet LLM_PROVIDER and the relevant env vars.  Examples:\n"
            "  LLM_PROVIDER=mock                  (offline, returns empty)\n"
            "  LLM_PROVIDER=anthropic   + ANTHROPIC_API_KEY=...\n"
            "  LLM_PROVIDER=openai-compatible + OPENAI_BASE_URL=http://localhost:11434/v1\n"
            "                                 + OPENAI_MODEL=llama3.2:3b",
            file=sys.stderr,
        )
        return 2

    with session_scope() as s:
        project = _resolve_project(s, args.project)
        if project is None:
            print(f"FAIL: no project matched {args.project!r}", file=sys.stderr)
            return 2

        print(f"Provider: {provider.name}")
        print(f"Project:  {project.name}  ({project.canonical_id})")
        print()
        print("Assembling context...")
        ctx = assemble_project_context(
            s, project.canonical_id,
            token_budget=int(args.token_budget),
            max_documents_with_text=int(args.max_docs),
        )
        block = ctx.to_prompt_block()
        print(f"  context: {len(block):,} chars / ~{len(block)//4:,} tokens")
        print(f"  tasks={len(ctx.tasks)}  docs={len(ctx.documents)}  "
              f"doc_bodies={len(ctx.document_texts)}  invoices={len(ctx.invoices)}")
        if ctx.truncated:
            print(f"  truncated: {ctx.truncated}")
        print()

        # Prompt structure rule (matters more than it looks): put the
        # INSTRUCTION at the TAIL of the user message, not the head.
        # When a prompt exceeds the model's context window, most servers
        # (including Ollama) truncate from the FRONT.  A head-loaded
        # instruction gets cut, the model only sees the document bodies
        # at the bottom, and starts "helpfully" responding to that
        # instead.  (We hit this once -- got a French lease rewrite
        # instead of a project status.  Lesson burned in.)
        system = (
            "You are reading internal project records for a construction "
            "company.  Given the structured records below, produce a "
            "concise (3-5 sentences) plain-English status update.  Use "
            "ONLY the data shown -- do not invent facts.  If the records "
            "are insufficient, say so explicitly."
        )
        user = (
            f"{block}\n\n"
            "---\n\n"
            "INSTRUCTION: Based ONLY on the project records above, "
            "give me a brief plain-English status update covering:\n"
            "  - what the project is\n"
            "  - what's been done\n"
            "  - what's outstanding\n"
            "  - any obvious gaps you notice (missing dates, missing "
            "contract, missing invoices, etc.)\n"
            "Stay under 5 sentences.  Do not invent facts."
        )

        # Cheap overflow detection: most local models default to
        # 2048-4096-token context unless the user has bumped num_ctx
        # in their Ollama config.  Warn if our prompt would not fit.
        prompt_estimated_tokens = (len(user) + len(system)) // 4
        if prompt_estimated_tokens > 3500:
            print()
            print(
                f"  WARNING: estimated prompt size is ~{prompt_estimated_tokens:,} "
                f"tokens.  Many local servers (Ollama default) cap context at "
                f"2048-4096 and silently TRUNCATE excess from the FRONT.  Even "
                f"with the instruction at the tail this can produce confused "
                f"output.  Drop --token-budget to ~10000 and --max-docs to 1 "
                f"if the response looks wrong.",
                file=sys.stderr,
            )

        if args.verbose:
            print()
            print("=== SYSTEM PROMPT ===")
            print(system)
            print("\n=== USER PROMPT (first 1000 chars) ===")
            print(user[:1000] + ("\n... [truncated]" if len(user) > 1000 else ""))
            print("\n=== FULL ASSEMBLED CONTEXT (first 500 chars) ===")
            print(block[:500] + ("\n... [truncated]" if len(block) > 500 else ""))
            print()

        print(f"Calling LLM (max_output_tokens={args.max_output_tokens})...")
        print("  (first call to a freshly-pulled local model can take 30-180s")
        print("   on CPU while weights load -- subsequent calls are fast)")
        import time as _time
        t0 = _time.monotonic()
        try:
            resp = provider.complete(
                messages=[LLMMessage(role="user", content=user)],
                system=system,
                max_tokens=int(args.max_output_tokens),
            )
        except LLMProviderError as exc:
            print(f"FAIL: {exc}", file=sys.stderr)
            print(
                "\nTroubleshooting:\n"
                "  - HTTP timeout?  Set OPENAI_TIMEOUT=900 or warm the model:\n"
                "      ollama run llama3.2:3b \"say hi\"\n"
                "  - Connection refused?  Is Ollama running?  ollama ps\n"
                "  - Model not found?  ollama pull <model>",
                file=sys.stderr,
            )
            return 1
        elapsed = _time.monotonic() - t0

        in_toks = resp.usage.get("input_tokens", 0)
        out_toks = resp.usage.get("output_tokens", 0)
        tok_per_sec = (out_toks / elapsed) if elapsed > 0 and out_toks else 0

        print()
        print(
            f"--- response (finish={resp.finish_reason}, "
            f"in={in_toks} out={out_toks}, "
            f"{elapsed:.1f}s @ {tok_per_sec:.1f} tok/s) ---"
        )
        print(resp.content)

        if args.verbose:
            print()
            print("=== METADATA ===")
            print(f"  model:         {resp.model}")
            print(f"  finish_reason: {resp.finish_reason}")
            print(f"  input_tokens:  {in_toks}")
            print(f"  output_tokens: {out_toks}")
            print(f"  elapsed_sec:   {elapsed:.2f}")
            print(f"  tok_per_sec:   {tok_per_sec:.1f}")
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
    sync.add_argument(
        "--delta",
        action="store_true",
        help="Monday only: skip boards with no activity_logs since last sync",
    )
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

    lt = sub.add_parser(
        "llm-test",
        help="Smoke-test the LLM stack against a real project (no Proposal written)",
    )
    lt.add_argument("project", help="Project name fragment or canonical UUID")
    lt.add_argument(
        "--token-budget", default=20_000, type=int,
        help="Cap on assembled-context size (default 20k tokens; small models choke on more)",
    )
    lt.add_argument(
        "--max-docs", default=3, type=int,
        help="Max number of document bodies to attach (default 3)",
    )
    lt.add_argument(
        "--max-output-tokens", default=300, type=int,
        help="Output cap (default 300; lower = faster on slow CPU models)",
    )
    lt.add_argument(
        "--verbose", action="store_true",
        help="Dump system prompt, user prompt excerpt, context, and timing metadata",
    )
    lt.set_defaults(func=cmd_llm_test)

    ec = sub.add_parser(
        "extract-content",
        help="Extract text from Drive documents into DocumentText (idempotent)",
    )
    ec.add_argument("--project", help="Restrict to one Project canonical UUID")
    ec.add_argument(
        "--overwrite",
        action="store_true",
        help="Re-extract documents that already have a DocumentText row",
    )
    ec.add_argument("--limit", type=int, help="Stop after N documents (smoke test)")
    ec.set_defaults(func=cmd_extract_content)

    return p


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
