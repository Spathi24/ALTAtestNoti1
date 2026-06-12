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
from typing import Any

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
    Proposal,
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

        # No canned report matched -> escalate to the fast (Haiku) LLM, which
        # reads the whole canonical-DB snapshot and answers in prose.  Canned
        # reports stay instant + deterministic; only the fall-through spends a
        # token.
        if response.used_report is None:
            from project_db.ai import LLMProviderError, get_fast_provider

            try:
                provider = get_fast_provider()
            except LLMProviderError as exc:
                print("[mode=canned]")
                print(
                    "No canned report matched, and no LLM is configured for "
                    f"free-form questions.\n  ({exc})\n"
                    "Try:  project_db ask help"
                )
                return 0
            print(
                f"[asking {provider.name} -- reading the database snapshot...]",
                file=sys.stderr,
            )
            # RAG: feed relevant document excerpts when embeddings are
            # available (and something has been embedded).  Free-ish: embeds
            # only the short question, and only if there are candidate chunks.
            from project_db.ai.embeddings import get_optional_embedding_provider

            embed_provider = get_optional_embedding_provider()
            response = assistant.answer_with_llm(
                question, provider, embedding_provider=embed_provider,
            )

        print(f"[mode={response.mode}", end="")
        if response.used_report:
            print(f" report={response.used_report}", end="")
        print("]")
        # Canned reports return JSON-shaped data; the LLM returns prose.
        if isinstance(response.answer, str):
            print(response.answer)
        else:
            print(json.dumps(response.answer, indent=2, default=str))
        if response.sources:
            print(f"\n[answered using {len(response.sources)} document "
                  f"excerpt(s):]")
            seen = []
            for s in response.sources:
                name = s.get("document_name") or "(unknown)"
                if name not in seen:
                    seen.append(name)
                    print(f"  - {name} (similarity {s.get('similarity')})")
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


def cmd_embed_documents(args: argparse.Namespace) -> int:
    """Chunk + embed document text into vectors for RAG (OpenAI embeddings).

    Idempotent: unchanged documents are skipped (no re-charge). Run after
    `extract-content`. This spends OpenAI embedding tokens -- cost is printed.
    """
    from project_db.ai.embeddings import EmbeddingError, get_embedding_provider
    from project_db.ai.rag import embed_documents_for, embedding_coverage
    from project_db.ai.views import _resolve_project

    engine = get_engine()
    Base.metadata.create_all(engine)
    ensure_sqlite_schema(engine)

    try:
        provider = get_embedding_provider()
    except EmbeddingError as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 2

    with session_scope() as s:
        project_id = None
        if args.project:
            p = _resolve_project(s, args.project)
            if p is None:
                print(f"FAIL: no project matched {args.project!r}", file=sys.stderr)
                return 2
            project_id = p.canonical_id
            print(f"Project: {p.name} ({p.canonical_id})")
        print(f"Embedding model: {provider.model} ({provider.dims} dims)")
        print("Chunking + embedding (calls the OpenAI embeddings API)...")
        stats = embed_documents_for(
            s, provider,
            project_id=project_id,
            overwrite=bool(args.overwrite),
            limit=int(args.limit) if args.limit else None,
        )
        print()
        print(f"  Documents: {stats['documents_processed']} embedded, "
              f"{stats['documents_skipped']} unchanged, of "
              f"{stats['documents_total']} with text")
        print(f"  Chunks embedded:  {stats['chunks_embedded']}")
        print(f"  Tokens (approx):  {stats['tokens_embedded']:,}")
        print(f"  Est. cost (USD):  ${stats['estimated_cost_usd']:.4f}")
        if stats["interrupted"]:
            print("  (interrupted -- progress committed; re-run to continue)")
        cov = embedding_coverage(s)
        print(f"  Coverage: {cov['documents_embedded']}/"
              f"{cov['documents_with_text']} docs embedded, "
              f"{cov['chunks']} chunks total")
    return 0


def cmd_rag_search(args: argparse.Namespace) -> int:
    """Retrieve the most relevant document chunks for a query (RAG debug).

    Embeds the query and returns the top cosine-similar stored chunks. Useful
    for sanity-checking retrieval before it feeds the askbot.
    """
    from project_db.ai.embeddings import EmbeddingError, get_embedding_provider
    from project_db.ai.rag import retrieve_chunks
    from project_db.ai.views import _resolve_project

    engine = get_engine()
    Base.metadata.create_all(engine)
    ensure_sqlite_schema(engine)

    try:
        provider = get_embedding_provider()
    except EmbeddingError as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 2

    with session_scope() as s:
        project_id = None
        if args.project:
            p = _resolve_project(s, args.project)
            if p is None:
                print(f"FAIL: no project matched {args.project!r}", file=sys.stderr)
                return 2
            project_id = p.canonical_id
        hits = retrieve_chunks(
            s, provider, args.query,
            project_id=project_id, top_k=int(args.top_k),
        )
        if not hits:
            print("No matching chunks. Run `embed-documents` first.")
            return 0
        print(f"Top {len(hits)} chunk(s) for: {args.query!r}\n")
        for i, h in enumerate(hits, 1):
            print(f"{i:>2}. sim={h['similarity']:.3f}  {h['document_name']}  "
                  f"[chunk {h['chunk_index']}]")
            snippet = " ".join((h["text"] or "")[:240].split())
            print(f"      {snippet}...")
    return 0


def _cmd_extract_obligations_structured(args: argparse.Namespace) -> int:
    """Structured (OpenAI, classify-then-extract) obligation extraction path."""
    from project_db.ai.obligation_extraction import (
        ObligationExtractorError,
        OpenAIObligationExtractor,
        extract_obligations_structured_for_project,
    )
    from project_db.ai.views import _resolve_project, report_commitments

    engine = get_engine()
    Base.metadata.create_all(engine)
    ensure_sqlite_schema(engine)

    try:
        extractor = OpenAIObligationExtractor()
    except ObligationExtractorError as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 2

    with session_scope() as s:
        project = _resolve_project(s, args.project)
        if project is None:
            print(f"FAIL: no project matched {args.project!r}", file=sys.stderr)
            return 2
        print(f"Extractor: {extractor.name} ({extractor.model})")
        print(f"Project:   {project.name}  ({project.canonical_id})")
        print("Classifying + extracting each document (OpenAI structured outputs)...")
        try:
            batch = extract_obligations_structured_for_project(
                s, extractor, project.canonical_id)
        except Exception as exc:  # noqa: BLE001
            print(f"FAIL: {exc}", file=sys.stderr)
            return 1

        print()
        print(batch.summary())
        for e in batch.errors[:10]:
            print(f"  - {e}")
        if batch.classifications:
            print("\n  Document classifications:")
            for name, dtype, contractual in batch.classifications[:50]:
                tag = "oblig" if contractual else "skip "
                print(f"    [{tag}] {dtype:<26} {name[:45]}")
        if batch.obligations:
            print("\n  Obligations:")
            for ob in batch.obligations[:40]:
                amt = f"${ob.amount:,.2f}" if ob.amount is not None else "(no amount)"
                when = ob.due_date.isoformat() if ob.due_date else (ob.trigger or "?")
                verify = "" if ob.amount is None else (
                    " [verified]" if ob.amount_verified else " [UNVERIFIED]")
                print(f"    - [{ob.kind}/{ob.direction}] {amt} due {when}{verify}")

        rep = report_commitments(s, str(project.canonical_id))
        c = rep.get("counts", {})
        mar = rep.get("money_at_risk", {})
        print(f"\n  Commitments: {rep.get('obligation_count', 0)} total | "
              f"overdue {c.get('overdue', 0)} | due-soon {c.get('due_soon', 0)} | "
              f"conditional {c.get('conditional', 0)}")
        print(f"  Money at risk: ${mar.get('owed_to_us_overdue', 0):,.2f} overdue to "
              f"collect | ${mar.get('owed_to_us_total', 0):,.2f} owed to us total | "
              f"${mar.get('owed_by_us_total', 0):,.2f} owed by us total")
    return 0


def cmd_extract_obligations(args: argparse.Namespace) -> int:
    """Extract dated/dollar obligations from a project's contract documents.

    Payment milestones, retainage, penalties, deposits, settlements, insurance/
    permit deadlines -> ContractObligation rows, each with the verbatim clause.
    Calls the LLM (batched); fresh-snapshot per run. Nothing leaves the local DB.

    With --structured, uses the OpenAI structured-outputs extractor (classifies
    each document, no keyword gate) -- the recommended path, mirroring
    extract-financials --structured.
    """
    if getattr(args, "structured", False):
        return _cmd_extract_obligations_structured(args)

    from project_db.ai import LLMProviderError, get_default_provider
    from project_db.ai.obligations import extract_obligations_for_project
    from project_db.ai.views import _resolve_project

    engine = get_engine()
    Base.metadata.create_all(engine)
    ensure_sqlite_schema(engine)

    try:
        provider = get_default_provider()
    except LLMProviderError as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 2

    with session_scope() as s:
        project = _resolve_project(s, args.project)
        if project is None:
            print(f"FAIL: no project matched {args.project!r}", file=sys.stderr)
            return 2

        print(f"Provider: {provider.name}")
        print(f"Project:  {project.name}  ({project.canonical_id})")
        print("Extracting contract obligations (this calls the LLM, batched)...")
        try:
            batch = extract_obligations_for_project(s, provider, project.canonical_id)
        except Exception as exc:  # noqa: BLE001
            print(f"FAIL: {exc}", file=sys.stderr)
            return 1

        print()
        print(batch.summary())
        if batch.errors:
            print(f"\n  {len(batch.errors)} error(s):")
            for e in batch.errors[:20]:
                print(f"    - {e}")
        if batch.warnings:
            print(f"\n  {len(batch.warnings)} item(s) flagged:")
            for w in batch.warnings[:20]:
                print(f"    - {w}")
        if batch.obligations:
            print("\n  Obligations:")
            for ob in batch.obligations[:40]:
                amt = f"${ob.amount:,.2f}" if ob.amount is not None else "(no amount)"
                when = ob.due_date.isoformat() if ob.due_date else (ob.trigger or "?")
                verify = "" if ob.amount is None else (
                    " [verified]" if ob.amount_verified else " [UNVERIFIED]")
                print(f"    - [{ob.kind}/{ob.direction}] {amt} due {when}{verify}")
                if ob.description:
                    print(f"        {ob.description}")
    return 0


def _cmd_extract_financials_structured(args: argparse.Namespace) -> int:
    """Structured (OpenAI, classify-then-extract) financial extraction path."""
    from project_db.ai.doc_extraction import (
        OpenAIStructuredExtractor,
        StructuredExtractorError,
        extract_financials_structured_for_project,
    )
    from project_db.ai.views import _resolve_project, report_project_financials

    engine = get_engine()
    Base.metadata.create_all(engine)
    ensure_sqlite_schema(engine)

    try:
        extractor = OpenAIStructuredExtractor()
    except StructuredExtractorError as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 2

    with session_scope() as s:
        project = _resolve_project(s, args.project)
        if project is None:
            print(f"FAIL: no project matched {args.project!r}", file=sys.stderr)
            return 2
        print(f"Extractor: {extractor.name} ({extractor.model})")
        print(f"Project:   {project.name}  ({project.canonical_id})")
        print("Classifying + extracting each document (OpenAI structured outputs)...")
        try:
            batch = extract_financials_structured_for_project(
                s, extractor, project.canonical_id)
        except Exception as exc:  # noqa: BLE001
            print(f"FAIL: {exc}", file=sys.stderr)
            return 1

        print()
        print(batch.summary())
        for e in batch.errors[:10]:
            print(f"  - {e}")
        if batch.classifications:
            print("\n  Document classifications:")
            for name, dtype, txn in batch.classifications[:50]:
                print(f"    [{'txn ' if txn else 'skip'}] {dtype:<28} {name[:45]}")

        rep = report_project_financials(s, str(project.canonical_id))
        t = rep.get("totals", {})
        ms = rep.get("money_summary", {})
        print(f"\n  Client in {t.get('client_in',0):,.2f} | Contractor out "
              f"{t.get('contractor_out',0):,.2f} | Unknown {t.get('unknown',0):,.2f} "
              f"| Margin {t.get('margin',0):,.2f}")
        cr = ms.get("classified_ratio")
        if cr is not None:
            print(f"  Classified: {cr*100:.0f}%"
                  + ("  LOW CONFIDENCE" if ms.get("low_confidence") else ""))
    return 0


def cmd_extract_financials(args: argparse.Namespace) -> int:
    """Extract monetary records from a project's Drive financial documents.

    Reads the project's quotes / estimates / invoices / receipts (already
    text-extracted via `extract-content`), asks the deep LLM to pull every
    stated amount with a verbatim excerpt, and writes FinancialRecord rows.
    Then prints the two-sided money-flow reconciliation (client-in vs
    contractor-out vs margin), computed deterministically -- not by the LLM.

    Fresh snapshot: a re-run replaces the project's prior financial records.
    Nothing is written to any external system; this only enriches the
    canonical DB.

    With --structured, uses the OpenAI structured-outputs extractor, which
    CLASSIFIES each document (quote / invoice / supplier bill / budget / model /
    market report) and extracts via a strict schema -- no keyword/roll-up
    heuristics.  Recommended.
    """
    if getattr(args, "structured", False):
        return _cmd_extract_financials_structured(args)

    from project_db.ai import (
        LLMProviderError,
        extract_financials_for_project,
        get_default_provider,
    )
    from project_db.ai.views import _resolve_project, report_project_financials

    engine = get_engine()
    Base.metadata.create_all(engine)
    ensure_sqlite_schema(engine)

    try:
        provider = get_default_provider()
    except LLMProviderError as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 2

    with session_scope() as s:
        project = _resolve_project(s, args.project)
        if project is None:
            print(f"FAIL: no project matched {args.project!r}", file=sys.stderr)
            return 2

        print(f"Provider: {provider.name}")
        print(f"Project:  {project.name}  ({project.canonical_id})")
        print("Extracting financial records (this calls the LLM, batched)...")
        try:
            kwargs = {}
            if args.max_docs:
                kwargs["max_documents"] = int(args.max_docs)
            batch = extract_financials_for_project(
                s, provider, project.canonical_id, **kwargs,
            )
        except Exception as exc:  # noqa: BLE001
            print(f"FAIL: {exc}", file=sys.stderr)
            return 1

        print()
        print(batch.summary())
        if batch.errors:
            print(f"\n  {len(batch.errors)} error(s):")
            for e in batch.errors[:20]:
                print(f"    - {e}")
        if batch.warnings:
            print(f"\n  {len(batch.warnings)} item(s) flagged for review:")
            for w in batch.warnings[:20]:
                print(f"    - {w}")

        # Reconciliation summary (reads what we just wrote, still uncommitted).
        report = report_project_financials(s, str(project.canonical_id))
        totals = report.get("totals", {})
        print("\n--- Money-flow reconciliation (PRIMARY docs only) ---")
        print(f"  Records:          {report.get('record_count', 0)} "
              f"(primary {report.get('primary_record_count', 0)} / "
              f"rollup {report.get('rollup_record_count', 0)})")
        print(f"  Client in (rev):  {totals.get('client_in', 0):,.2f}")
        print(f"  Contractor out:   {totals.get('contractor_out', 0):,.2f}")
        print(f"  Unknown side:     {totals.get('unknown', 0):,.2f}")
        print(f"  Margin (in-out):  {totals.get('margin', 0):,.2f}")
        xc = report.get("rollup_crosscheck", {})
        if xc.get("document_count"):
            print(f"\n  Roll-up cross-check ({xc['document_count']} internal "
                  f"sheet(s), NOT in totals):")
            print(f"    client_in {xc.get('client_in', 0):,.2f} | "
                  f"contractor_out {xc.get('contractor_out', 0):,.2f} | "
                  f"unknown {xc.get('unknown', 0):,.2f}")

        bmt = report.get("by_money_type", {})
        if bmt:
            print("\n  By money type (primary docs):")
            for k, v in bmt.items():
                print(f"    {k:18} {v:,.2f}")
            ms = report.get("money_summary", {})
            cr = ms.get("classified_ratio")
            if cr is not None:
                print(f"  Classified: {cr*100:.0f}% of money in revenue/cost "
                      f"buckets")
            if ms.get("confidence_note"):
                print(f"  {ms['confidence_note']}")
            print(f"  Construction margin (revenue - supplier cost): "
                  f"{ms.get('construction_margin', 0):,.2f}")
            if ms.get("buyout_note"):
                print(f"  NOTE: {ms['buyout_note']}")

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


def cmd_propose(args: argparse.Namespace) -> int:
    """Generate LLM proposals for a project -> Proposal table (PENDING).

    `project_db propose timelines <project>` reads the project's contract
    text + dateless tasks and proposes start/end dates.

    `project_db propose scope <project>` flags documented scope-of-work
    items that have no matching Monday task (advisory only).

    Nothing is written to Monday -- proposals wait in the Proposal table
    for a human to accept/reject via `project_db proposals`.  `anomalies`
    lands in a later session.
    """
    from project_db.ai import (
        LLMProviderError,
        generate_scope_proposals,
        generate_timeline_proposals,
        get_default_provider,
    )
    from project_db.ai.views import _resolve_project

    kind = args.kind.lower()
    if kind in ("timeline", "timelines"):
        generator, kind_label = generate_timeline_proposals, "timeline"
    elif kind in ("scope", "scopes"):
        generator, kind_label = generate_scope_proposals, "scope"
    else:
        print(f"FAIL: unknown propose kind {args.kind!r}.", file=sys.stderr)
        print("Available: timelines, scope  (anomalies come later)", file=sys.stderr)
        return 2

    engine = get_engine()
    Base.metadata.create_all(engine)
    ensure_sqlite_schema(engine)

    try:
        provider = get_default_provider()
    except LLMProviderError as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 2

    with session_scope() as s:
        project = _resolve_project(s, args.project)
        if project is None:
            print(f"FAIL: no project matched {args.project!r}", file=sys.stderr)
            return 2

        from project_db.ai.embeddings import get_optional_embedding_provider
        embed_provider = get_optional_embedding_provider()

        print(f"Provider: {provider.name}")
        print(f"Project:  {project.name}  ({project.canonical_id})")
        print(f"Generating {kind_label} proposals (this calls the LLM)...")
        try:
            batch = generator(
                s, provider, project.canonical_id,
                embedding_provider=embed_provider,
            )
        except Exception as exc:  # noqa: BLE001
            print(f"FAIL: {exc}", file=sys.stderr)
            return 1

        print()
        print(batch.summary())
        if batch.rag_chunks_used:
            print(f"  (+{batch.rag_chunks_used} relevance-retrieved document "
                  f"excerpt(s) used as extra evidence)")
        for p in batch.proposals:
            val = json.loads(p.proposed_value)
            conf = f"{p.confidence:.2f}" if p.confidence is not None else "?"
            print(f"  - {p.canonical_id}")
            if batch.kind == "scope":
                print(f"      gap:    {val.get('scope_item')}")
                print(f"      task:   {val.get('suggested_task_title')}")
            else:
                print(f"      task:   {val.get('task_title')}")
                print(f"      dates:  {val.get('start_date')} -> {val.get('end_date')}")
            print(f"      conf:   {conf}")
        if batch.warnings:
            print("  flagged for review (created, but scrutinise before accepting):")
            for w in batch.warnings:
                print(f"    ! {w}")
        if batch.errors:
            print("  malformed items rejected:")
            for e in batch.errors:
                print(f"    - {e}")
    return 0


def _print_pending_proposals(rows: list[dict[str, Any]]) -> None:
    """Render the PENDING proposal list for interactive accept/reject.

    Shown when the user runs `proposals accept` / `reject` with no id, so
    they can see what is open and copy an id to act on.
    """
    print(f"{len(rows)} pending proposal(s):\n")
    for r in rows:
        conf = r.get("confidence")
        conf_s = f"{conf:.2f}" if isinstance(conf, (int, float)) else "?"
        label = r.get("entity_label") or r.get("entity_type")
        proj = r.get("project_name") or "?"
        print(f"  {r['proposal_id']}")
        print(f"      [{r['field_name']}] {proj} / {label}   confidence={conf_s}")
        val = r.get("proposed_value")
        if isinstance(val, dict):
            start, end = val.get("start_date"), val.get("end_date")
            if start or end:
                print(f"      proposed: {start} -> {end}")
            reasoning = (val.get("reasoning") or "").strip()
            if reasoning:
                snippet = reasoning if len(reasoning) <= 140 else reasoning[:137] + "..."
                print(f"      reasoning: {snippet}")
        print()
    print("Decide:")
    print("  project_db proposals accept <id>            write one change to Monday")
    print("  project_db proposals accept <id> --dry-run  preview the write")
    print("  project_db proposals reject <id> [--reason \"...\"]")
    print("  project_db proposals accept all --yes       accept every pending proposal")
    print("  project_db proposals reject all --yes       reject every pending proposal")


def _accept_all(
    session: Any, *, decided_by: str, dry_run: bool, assume_yes: bool
) -> int:
    """Accept every PENDING proposal.  Returns a process exit code.

    --dry-run previews every write and needs no confirmation.  A real bulk
    write to Monday is gated behind --yes, because it mutates an external
    system once per proposal.
    """
    from project_db.ai import accept_proposal, list_proposals
    from project_db.db.models import ProposalStatus

    rows = list_proposals(session, status=ProposalStatus.PENDING)
    if not rows:
        print("No pending proposals.")
        return 0

    if dry_run:
        print(f"DRY RUN -- previewing {len(rows)} pending proposal(s):\n")
        for r in rows:
            result = accept_proposal(session, r["proposal_id"], dry_run=True)
            if result.get("ok"):
                print(f"  {r['proposal_id']}  {result['task_title']}")
                print(
                    f"      would write ({result['field']}): "
                    f"{json.dumps(result['would_write'])}"
                )
            else:
                print(f"  {r['proposal_id']}  SKIP -- {result.get('error')}")
        print("\nNothing was written.  Re-run with --yes to apply.")
        return 0

    if not assume_yes:
        print(f"accept all would write {len(rows)} proposal(s) back to Monday:")
        for r in rows:
            label = r.get("entity_label") or r.get("entity_type")
            print(f"  - {r['proposal_id']}  {r.get('project_name') or '?'} / {label}")
        print("\nRe-run to proceed:  project_db proposals accept all --yes")
        print("Preview first:      project_db proposals accept all --dry-run")
        return 1

    # Build the Monday connector ONCE, reuse it for every write.
    from project_db.connectors.monday.connector import MondayConnector

    org = session.query(Organization).first()
    if org is None:
        print("FAIL: no organization. Run init-db first.", file=sys.stderr)
        return 2
    try:
        connector = MondayConnector(session=session, organization_id=org.canonical_id)
    except Exception as exc:  # noqa: BLE001
        print(f"FAIL: could not build Monday connector: {exc}", file=sys.stderr)
        return 2

    accepted = failed = 0
    for r in rows:
        result = accept_proposal(
            session, r["proposal_id"], writeback=connector, decided_by=decided_by,
        )
        if result.get("ok"):
            accepted += 1
            print(
                f"  OK    {r['proposal_id']}  {result['task_title']}  "
                f"-> {json.dumps(result['wrote_to_monday'])}"
            )
        else:
            failed += 1
            print(f"  FAIL  {r['proposal_id']}  {result.get('error')}")
    print(f"\naccepted {accepted}, failed {failed} (by {decided_by})")
    return 0 if failed == 0 else 1


def _reject_all(
    session: Any, *, decided_by: str, reason: str | None, assume_yes: bool
) -> int:
    """Reject every PENDING proposal.  Returns a process exit code.

    Reject is pure-DB (no Monday write), but REJECTED is terminal -- so the
    bulk action is still gated behind --yes.
    """
    from project_db.ai import list_proposals, reject_proposal
    from project_db.db.models import ProposalStatus

    rows = list_proposals(session, status=ProposalStatus.PENDING)
    if not rows:
        print("No pending proposals.")
        return 0

    if not assume_yes:
        print(f"reject all would reject {len(rows)} pending proposal(s):")
        for r in rows:
            label = r.get("entity_label") or r.get("entity_type")
            print(f"  - {r['proposal_id']}  {r.get('project_name') or '?'} / {label}")
        print("\nRe-run to proceed:  project_db proposals reject all --yes")
        return 1

    rejected = failed = 0
    for r in rows:
        result = reject_proposal(
            session, r["proposal_id"], reason=reason, decided_by=decided_by,
        )
        if result.get("ok"):
            rejected += 1
        else:
            failed += 1
            print(f"  FAIL  {r['proposal_id']}  {result.get('error')}")
    print(f"rejected {rejected}, failed {failed} (by {decided_by})")
    return 0 if failed == 0 else 1


def cmd_proposals(args: argparse.Namespace) -> int:
    """View and decide on LLM proposals: list / show / reject / accept.

    `accept` is the only action that mutates an external system -- it
    writes the proposed change back to Monday before flipping the
    proposal status.  Use `accept --dry-run` to preview the write first.

    `accept` / `reject` with NO proposal id print the pending list so the
    user can choose.  `accept all` / `reject all` act on every pending
    proposal at once -- both require `--yes` to proceed (a real bulk write
    to Monday, or a terminal bulk status change).
    """
    import getpass

    from project_db.ai import (
        accept_proposal,
        get_proposal_detail,
        list_proposals,
        reject_proposal,
    )
    from project_db.db.models import ProposalStatus

    with session_scope() as s:
        if args.proposals_action == "list":
            status = None
            if args.status:
                try:
                    status = ProposalStatus[args.status.upper()]
                except KeyError:
                    valid = ", ".join(x.value for x in ProposalStatus)
                    print(f"FAIL: unknown status {args.status!r}. Valid: {valid}",
                          file=sys.stderr)
                    return 2
            rows = list_proposals(s, status=status, kind=args.kind)
            print(f"{len(rows)} proposal(s)")
            print(json.dumps(rows, indent=2, default=str))
            return 0

        if args.proposals_action == "show":
            detail = get_proposal_detail(s, args.proposal_id)
            if detail is None:
                print(f"FAIL: no proposal with id {args.proposal_id!r}", file=sys.stderr)
                return 2
            print(json.dumps(detail, indent=2, default=str))
            return 0

        if args.proposals_action == "reject":
            # decided_by: an explicit --by wins, else the OS user, for a
            # real audit trail without needing an auth system.
            decided_by = args.by or getpass.getuser()
            target = (args.proposal_id or "").strip()

            # Omitted id -> show the pending list so the user can choose.
            if not target:
                rows = list_proposals(s, status=ProposalStatus.PENDING)
                if not rows:
                    print("No pending proposals.")
                    return 0
                _print_pending_proposals(rows)
                return 0

            # `reject all` -> bulk reject every pending proposal (--yes gated).
            if target.lower() == "all":
                return _reject_all(
                    s, decided_by=decided_by, reason=args.reason,
                    assume_yes=args.yes,
                )

            result = reject_proposal(
                s, target, reason=args.reason, decided_by=decided_by,
            )
            if not result.get("ok"):
                print(f"FAIL: {result.get('error')}", file=sys.stderr)
                return 2
            print(
                f"OK: proposal {result['proposal_id']} "
                f"{result['previous_status']} -> {result['new_status']} "
                f"(by {result['decided_by']})"
            )
            if result.get("rejection_reason"):
                print(f"  reason: {result['rejection_reason']}")
            return 0

        if args.proposals_action == "accept":
            decided_by = args.by or getpass.getuser()
            target = (args.proposal_id or "").strip()

            # Omitted id -> show the pending list so the user can choose.
            if not target:
                rows = list_proposals(s, status=ProposalStatus.PENDING)
                if not rows:
                    print("No pending proposals.")
                    return 0
                _print_pending_proposals(rows)
                return 0

            # `accept all` -> bulk accept.  --dry-run previews every write;
            # a real bulk write to Monday is gated behind --yes.
            if target.lower() == "all":
                return _accept_all(
                    s, decided_by=decided_by, dry_run=args.dry_run,
                    assume_yes=args.yes,
                )

            # Dry-run never builds a connector and never touches Monday.
            if args.dry_run:
                result = accept_proposal(s, target, dry_run=True)
                if not result.get("ok"):
                    print(f"FAIL: {result.get('error')}", file=sys.stderr)
                    return 2
                print("DRY RUN -- nothing was written.")
                print(f"  proposal: {result['proposal_id']}")
                print(f"  task:     {result['task_title']}")
                print(f"  would write to Monday ({result['field']}):")
                print(f"    {json.dumps(result['would_write'])}")
                print("  Re-run without --dry-run to apply.")
                return 0

            # Real accept -- writes to Monday.  Build the connector
            # (needs MONDAY_API_TOKEN); fail clean if it's missing.
            from project_db.connectors.monday.connector import MondayConnector

            org = s.query(Organization).first()
            if org is None:
                print("FAIL: no organization. Run init-db first.", file=sys.stderr)
                return 2
            try:
                connector = MondayConnector(session=s, organization_id=org.canonical_id)
            except Exception as exc:  # noqa: BLE001
                print(f"FAIL: could not build Monday connector: {exc}", file=sys.stderr)
                return 2

            result = accept_proposal(
                s, target, writeback=connector, decided_by=decided_by,
            )
            if not result.get("ok"):
                print(f"FAIL: {result.get('error')}", file=sys.stderr)
                return 1
            print(
                f"OK: proposal {result['proposal_id']} "
                f"{result['previous_status']} -> {result['new_status']} "
                f"(by {result['decided_by']})"
            )
            print(f"  task:    {result['task_title']}")
            print(f"  written: {json.dumps(result['wrote_to_monday'])}")
            return 0

    return 0


def cmd_daily(args: argparse.Namespace) -> int:
    """One-screen daily review for a project.

    The default path is intentionally read-only: it summarizes the current DB
    truth, pending proposals, and unresolved dateless tasks.  The LLM is called
    only when the user passes ``--propose-timelines`` so token spend remains an
    explicit decision.
    """
    from project_db.ai import (
        LLMProviderError,
        generate_timeline_proposals,
        get_default_provider,
        list_proposals,
    )
    from project_db.ai.views import (
        _resolve_project,
        report_budget_vs_contract,
        report_missing_documents,
        report_project_overview,
        report_tasks_without_dates,
    )
    from project_db.db.models import ProposalStatus

    project_ref = " ".join(args.project) if isinstance(args.project, list) else args.project

    engine = get_engine()
    Base.metadata.create_all(engine)
    ensure_sqlite_schema(engine)

    with session_scope() as s:
        project = _resolve_project(s, project_ref)
        if project is None:
            print(f"FAIL: no project matched {project_ref!r}", file=sys.stderr)
            return 2

        if args.propose_timelines:
            try:
                provider = get_default_provider()
            except LLMProviderError as exc:
                print(f"FAIL: {exc}", file=sys.stderr)
                return 2
            print(f"[daily] generating timeline proposals with {provider.name}...")
            try:
                batch = generate_timeline_proposals(
                    s,
                    provider,
                    project.canonical_id,
                    token_budget=int(args.token_budget),
                    max_documents_with_text=int(args.max_docs),
                    max_output_tokens=int(args.max_output_tokens),
                )
            except Exception as exc:  # noqa: BLE001
                print(f"FAIL: {exc}", file=sys.stderr)
                return 1
            print(batch.summary())
            for warning in batch.warnings:
                print(f"  ! {warning}")
            for error in batch.errors:
                print(f"  - rejected: {error}")
            print()

        overview = report_project_overview(s, str(project.canonical_id))
        dateless = report_tasks_without_dates(s, str(project.canonical_id))
        budget = report_budget_vs_contract(s, str(project.canonical_id))
        missing_docs = report_missing_documents(s)
        pending = [
            row for row in list_proposals(s, status=ProposalStatus.PENDING)
            if row.get("project_name") == project.name
        ]

        stats = overview.get("stats", {})
        project_info = overview.get("project", {})
        print("=== DAILY REVIEW ===")
        print(f"Project: {project_info.get('name')} ({project_info.get('status')})")
        print(f"ID:      {project_info.get('canonical_id')}")
        print()
        print("Snapshot")
        print(f"  tasks:            {stats.get('task_count', 0)}")
        print(f"  tasks no dates:   {stats.get('tasks_without_dates', 0)}")
        print(f"  documents:        {stats.get('document_count', 0)}")
        print(f"  invoices:         {stats.get('invoice_count', 0)}")
        print(f"  pending proposals:{len(pending):>4}")

        contract_amount = budget.get("contract_amount_estimate")
        monday_budget = budget.get("monday_budget")
        if contract_amount is not None or monday_budget is not None:
            print()
            print("Budget / Contract")
            print(f"  monday budget:    {monday_budget}")
            print(f"  contract estimate: {contract_amount}")
            if budget.get("flagged"):
                print(f"  ! divergence above {budget.get('divergence_threshold')}")

        print()
        print("Pending Proposals")
        if pending:
            for row in pending[: int(args.limit)]:
                print(
                    f"  - {row['proposal_id']} [{row['field_name']}] "
                    f"{row.get('entity_label') or row['entity_type']} "
                    f"conf={row.get('confidence')}"
                )
            if len(pending) > int(args.limit):
                print(f"  ... {len(pending) - int(args.limit)} more")
            print("  Review: project_db proposals show <proposal-id>")
        else:
            print("  none")

        tasks = dateless.get("tasks", [])
        print()
        print("Unresolved Dateless Tasks")
        if tasks:
            for task in tasks[: int(args.limit)]:
                label = task.get("monday_status_label") or task.get("status") or "?"
                print(f"  - [{label}] {task.get('title')}")
            if len(tasks) > int(args.limit):
                print(f"  ... {len(tasks) - int(args.limit)} more")
            if not args.propose_timelines:
                print(
                    "  Generate proposals: "
                    f"project_db daily \"{project.name}\" --propose-timelines"
                )
        else:
            print("  none")

        missing_ids = {
            row.get("canonical_id") for row in missing_docs.get("projects", [])
        }
        print()
        print("Trust Checks")
        if str(project.canonical_id) in missing_ids:
            print("  ! no contract-shaped document found for this project")
        else:
            print("  contract/document check: ok")
        print("  full audit: project_db doctor")

    return 0


def cmd_field_note(args: argparse.Namespace) -> int:
    """Submit a plain-language field note for a project.

    Classifies the note, matches signals to project tasks, and writes PENDING
    Proposals for human review.  Uses OpenAI structured outputs (gpt-4o-mini).
    """
    from project_db.ai.field_note_extraction import (
        FieldNoteExtractorError,
        NoteChannel,
        OpenAIFieldNoteExtractor,
        ingest_field_note,
    )
    from project_db.ai.views import _resolve_project

    engine = get_engine()
    Base.metadata.create_all(engine)
    ensure_sqlite_schema(engine)

    note_text = args.note if isinstance(args.note, str) else " ".join(args.note)
    project_ref = args.project

    try:
        extractor = OpenAIFieldNoteExtractor()
    except FieldNoteExtractorError as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 2

    with session_scope() as s:
        project = _resolve_project(s, project_ref)
        if project is None:
            print(f"FAIL: no project matched {project_ref!r}", file=sys.stderr)
            return 2

        print(f"[field-note] project: {project.name}")
        print(f"[field-note] note:    {note_text[:120]}")
        print()

        batch = ingest_field_note(
            s, extractor, project.canonical_id, note_text,
            channel=NoteChannel.CLI,
        )

    if batch.skipped_reason:
        print(f"SKIP: {batch.skipped_reason}")
        return 0

    for err in batch.errors:
        print(f"WARN: {err}")

    print(batch.summary())
    for fn in batch.field_notes:
        print(
            f"  signal: {fn.classification.value if fn.classification else '?'}"
            f"  conf={fn.confidence:.2f}"
            f"  excerpt: {(fn.quoted_excerpt or '')[:60]}"
        )
    if batch.proposals:
        print(f"  -> {len(batch.proposals)} proposal(s) created (PENDING review)")
        print("  Review with: project_db proposals list --status pending")
    return 0


def cmd_doctor(_: argparse.Namespace) -> int:
    """Audit canonical-data integrity (read-only).

    Surfaces the failure modes the foundation rebuild targets: phantom or
    duplicate projects, documents linked to the wrong project, orphaned
    files.  Run it after `rebuild` to confirm the data is sound.

    Thin renderer over ``ai.views.report_doctor`` -- the UI ``/doctor``
    route renders the same data structure.
    """
    from project_db.ai.views import report_doctor

    engine = get_engine()
    Base.metadata.create_all(engine)
    ensure_sqlite_schema(engine)

    with session_scope() as s:
        data = report_doctor(s)

    print(f"=== PROJECTS ({len(data['projects'])}) ===")
    for p in data["projects"]:
        print(f"  {p['name']}")
        print(
            f"      status={p['status']}  docs={p['doc_count']}  "
            f"tasks={p['task_count']}  source={p['sources_label']}"
        )

    docs = data["documents"]
    print(f"\n=== DOCUMENTS ({docs['total']} live) ===")
    print(f"  linked to a project: {docs['linked']}")
    for cat, n in docs["by_category"].items():
        print(f"  category={cat}: {n}")

    flags = data["flags"]
    print(f"\n=== FLAGS ({len(flags)}) ===")
    if not flags:
        print("  none -- canonical data looks sound.")
    else:
        for flag in flags:
            print(f"  ! {flag}")
    return 0


def cmd_commitments(args: argparse.Namespace) -> int:
    """Money-at-Risk for one project (read-only): obligations + their status.

    Deterministic over already-extracted ContractObligation rows -- no LLM.
    Thin renderer over ``ai.views.report_commitments``.
    """
    from project_db.ai.views import report_commitments

    engine = get_engine()
    Base.metadata.create_all(engine)
    ensure_sqlite_schema(engine)

    with session_scope() as s:
        data = report_commitments(s, args.project)

    if data.get("error"):
        print(f"FAIL: {data['error']}", file=sys.stderr)
        return 2

    print(f"=== COMMITMENTS: {data['project']['name']} ({data['generated_on']}) ===")
    if not data["obligation_count"]:
        print(f"  {data.get('note') or 'No obligations on file.'}")
        return 0

    m = data["money_at_risk"]
    print(f"  Money at risk -- to collect (overdue): ${m['owed_to_us_overdue']:,.0f} "
          f"of ${m['owed_to_us_total']:,.0f}  |  we owe (overdue): "
          f"${m['owed_by_us_overdue']:,.0f} of ${m['owed_by_us_total']:,.0f}")
    print("  by status: " + ", ".join(
        f"{k} {v}" for k, v in sorted(data["counts"].items())))
    print()

    tag = {"overdue": "[OVERDUE]", "due_soon": "[SOON]   ",
           "conditional": "[COND]   ", "upcoming": "[FUTURE] ", "open": "[OPEN]   "}
    for ob in data["obligations"][:40]:
        amt = f"${float(ob['amount']):,.2f}" if ob["amount"] is not None else "(no amount)"
        when = ob["due_date"] or (ob["trigger"] or "?")
        print(f"  {tag.get(ob['status'], '')} [{ob['kind']}/{ob['direction']}] "
              f"{amt} due {when}")
        if ob["description"]:
            print(f"       {ob['description']}")
    return 0


def cmd_value_caught(args: argparse.Namespace) -> int:
    """The ROI scoreboard (read-only): total money ALTA has surfaced as needing
    action across the whole portfolio (INTENTIONS #2).

    Deterministic over already-extracted ContractObligation rows -- no LLM, no
    API. Thin renderer over ``ai.views.report_value_caught``; the web `/` landing
    shows the same number as a headline card.
    """
    from project_db.ai.views import report_value_caught

    engine = get_engine()
    Base.metadata.create_all(engine)
    ensure_sqlite_schema(engine)

    with session_scope() as s:
        data = report_value_caught(s)

    print(f"=== VALUE CAUGHT ({data['generated_on']}) ===")
    print(f"  ALTA has surfaced ${data['headline_total']:,.0f} needing attention "
          f"across {data['flagged_project_count']} project(s).")
    m = data["money"]
    print(f"    - Revenue past due to collect (overdue): ${m['receivables_overdue']:,.0f}")
    print(f"    - Receivables due soon:                   ${m['receivables_due_soon']:,.0f}")
    print(f"    - Obligations we owe (overdue):           ${m['obligations_overdue']:,.0f}")
    if not data["flagged_project_count"]:
        print(f"  {data.get('note') or ''}")
        return 0
    print()
    print("  By project:")
    for p in data["projects"][:30]:
        total = p["receivables_overdue"] + p["obligations_overdue"]
        print(f"    ${total:>12,.0f}  {p['project_name']}  "
              f"(collect ${p['receivables_overdue']:,.0f} / owe "
              f"${p['obligations_overdue']:,.0f})")
    return 0


def cmd_money_line(args: argparse.Namespace) -> int:
    """One-line money summary for a project (read-only): revenue / costs / margin
    plus any overdue obligations (INTENTIONS #3).

    Deterministic over already-extracted records -- no LLM, no API. Thin renderer
    over ``ai.views.report_project_money_line``; the project page shows the same
    sentence.
    """
    from project_db.ai.views import report_project_money_line

    engine = get_engine()
    Base.metadata.create_all(engine)
    ensure_sqlite_schema(engine)

    with session_scope() as s:
        data = report_project_money_line(s, args.project)
    if data.get("error"):
        print(f"FAIL: {data['error']}", file=sys.stderr)
        return 2
    print(data["line"])
    return 0


def cmd_briefing(args: argparse.Namespace) -> int:
    """Portfolio attention briefing (read-only): the cross-system truths that
    need a PM's attention -- money risk, scope gaps, overdue tasks, missing
    contracts -- ranked by severity.

    Deterministic: no LLM, no external API call.  Composes the money / scope /
    schedule / document signals already stored in the canonical DB.  Thin
    renderer over ``ai.views.report_attention_briefing``; the web `/` landing
    renders the same data.
    """
    from project_db.ai.views import report_attention_briefing

    engine = get_engine()
    Base.metadata.create_all(engine)
    ensure_sqlite_schema(engine)

    limit = int(args.limit) if getattr(args, "limit", None) else 25
    with session_scope() as s:
        data = report_attention_briefing(s, limit=limit)

    n = data["item_count"]
    if not n:
        print("Nothing needs attention -- no money, scope, schedule, or "
              "document flags across the portfolio.")
        return 0

    bysev = data["by_severity"]
    print(f"=== ATTENTION BRIEFING ({data['generated_on']}) ===")
    print(f"  {n} item(s) across {data['project_count']} project(s): "
          f"{bysev.get('high', 0)} high / {bysev.get('medium', 0)} medium / "
          f"{bysev.get('low', 0)} low")
    print("  by area: " + ", ".join(
        f"{cat} {cnt}" for cat, cnt in sorted(data["by_category"].items())
    ))
    print()

    tag = {"high": "[HIGH] ", "medium": "[MED]  ", "low": "[LOW]  "}
    for i, it in enumerate(data["items"], 1):
        print(f"{i:>2}. {tag.get(it['severity'], '')}{it['headline']}")
        print(f"      ({it['category']}) {it['detail']}")
    if data["truncated"]:
        print(f"\n  ... and {n - data['shown_count']} more "
              f"(showing top {data['shown_count']}).")
    return 0


def cmd_import_roadmap(args: argparse.Namespace) -> int:
    """Import the canonical design-phase roadmap from an xlsx.

    The xlsx is the editorial source of truth (architect-side workflow:
    SD -> DD -> CD -> CA).  This loads it into ``roadmap_task`` so the
    AI layer can reference it for scope-gap detection and timeline
    ordering.

    Idempotent: re-run with --overwrite to pick up edits to the xlsx
    (drops + re-inserts the entire roadmap; no schema migration needed).
    """
    import os

    from project_db.ai.roadmap import import_roadmap_rows, parse_roadmap_xlsx

    # Default to the bundled docs path so a no-arg invocation Just Works.
    default_path = os.path.join("docs", "Project Roadmap.xlsx")
    path = args.path or default_path
    if not os.path.exists(path):
        # Try the parent directory too -- the user often runs from
        # project-db/ but the xlsx lives at ALTAtest/docs/.
        alt = os.path.join("..", "docs", "Project Roadmap.xlsx")
        if not args.path and os.path.exists(alt):
            path = alt
        else:
            print(f"FAIL: roadmap xlsx not found: {path}", file=sys.stderr)
            print(
                "  Pass an explicit path:\n"
                "    project_db import-roadmap path/to/Project Roadmap.xlsx",
                file=sys.stderr,
            )
            return 2

    engine = get_engine()
    Base.metadata.create_all(engine)
    ensure_sqlite_schema(engine)

    try:
        parsed = parse_roadmap_xlsx(path)
    except (ValueError, RuntimeError) as exc:
        print(f"FAIL: could not parse {path}: {exc}", file=sys.stderr)
        return 1

    print(f"Parsed {len(parsed)} roadmap task(s) from {path}")
    with session_scope() as s:
        result = import_roadmap_rows(s, parsed, overwrite=args.overwrite)

    if not result.get("ok"):
        print(f"FAIL: {result.get('error')}", file=sys.stderr)
        return 1

    breakdown = " / ".join(
        f"{n} {phase}" for phase, n in result["by_phase"].items() if n
    )
    print(f"OK -- imported {result['total']} task(s): {breakdown}")
    if result["overwrote"]:
        print(f"  (replaced {result['overwrote']} existing row(s))")
    return 0


def cmd_classify_roadmap(args: argparse.Namespace) -> int:
    """Use Sonnet to draft an actor (ARCHITECT/CONTRACTOR/BOTH) for each
    roadmap_task row.

    One-shot batch call: sends all 44 tasks to the LLM, parses the
    structured JSON response, writes actor values back.  Idempotent --
    re-running re-classifies all rows (overwrites previous actors).
    Per the M5 prompt-philosophy boundary, this uses the DEEP provider
    (Sonnet) because correctness matters more than latency here, and
    the call only happens when the user explicitly runs this command.
    """
    from project_db.ai.providers import get_default_provider
    from project_db.ai.roadmap import classify_roadmap_actors

    engine = get_engine()
    Base.metadata.create_all(engine)
    ensure_sqlite_schema(engine)

    try:
        provider = get_default_provider()
    except Exception as exc:  # noqa: BLE001
        print(f"FAIL: could not build LLM provider: {exc}", file=sys.stderr)
        return 2

    print("Calling Sonnet to classify roadmap tasks (this is a single "
          "LLM call; ~5-15s)...")
    with session_scope() as s:
        result = classify_roadmap_actors(s, provider)

    if not result.get("ok"):
        print(f"FAIL: {result.get('error')}", file=sys.stderr)
        return 1

    print(f"OK -- classified {result['updated']} task(s):")
    for actor, n in result["by_actor"].items():
        print(f"  {actor:<10} {n}")
    if result["errors"]:
        print(f"\n{len(result['errors'])} item(s) rejected as malformed:")
        for e in result["errors"][:10]:
            print(f"  - {e}")
    print("\nReview the results with:  project_db ask "
          "\"list roadmap tasks by actor\"  (placeholder -- use /db/roadmap_task)")
    print("Or open the UI:  http://127.0.0.1:8000/db/roadmap_task")
    return 0


def cmd_rebuild(args: argparse.Namespace) -> int:
    """Re-derive the canonical DB from the sources (Drive first, then Monday).

    The canonical DB is a projection of the source systems, so the clean
    way to fix accumulated drift is to re-derive it:
      - DROPS all connector-derived rows (projects, tasks, leads, deals,
        clients, external-ids, proposals, ...).
      - PRESERVES Document + DocumentText -- documents re-match by their
        stable Drive file id, so extracted text is NOT lost.
      - re-syncs Google Drive FIRST (Drive folders define the projects),
        then Monday (boards match into those projects).

    Proposals are dropped: they reference Task ids that change on
    re-derivation, and any existing ones were generated over pre-rebuild
    (incorrect) data anyway.  Destructive -- requires --yes.
    """
    engine = get_engine()
    Base.metadata.create_all(engine)
    ensure_sqlite_schema(engine)

    with session_scope() as s:
        n_proj = s.query(Project).count()
        n_prop = s.query(Proposal).count()
        n_doc = s.query(Document).count()

    if not args.yes:
        print("rebuild will RE-DERIVE the canonical database:")
        print(
            f"  - drop {n_proj} project(s), all tasks / leads / deals / "
            f"clients / external-ids"
        )
        print(
            f"  - export {n_prop} proposal(s) to JSON, then drop them"
        )
        print(f"  - preserve {n_doc} document(s) and their extracted text")
        print("  - re-sync Google Drive, then Monday")
        print("\nRe-run to proceed:  project_db rebuild --yes")
        return 1

    from datetime import datetime
    from pathlib import Path

    from sqlalchemy import inspect as sa_inspect, text

    # --- Preflight -------------------------------------------------------
    # Build every connector BEFORE touching the database.  Constructing the
    # Drive connector refreshes its OAuth token, so a dead credential is
    # caught here -- and the rebuild aborts with the DB completely untouched
    # rather than half-wiped.  Drive runs FIRST: its folders define project
    # identity; Monday boards then match into those projects.
    with session_scope() as s:
        if s.query(Organization).count() == 0:
            s.add(Organization(name="Default Org"))
        org_id = s.query(Organization).first().canonical_id

    sync_plan: list[tuple[str, Any]] = []
    for label, source in (
        ("Google Drive", SourceSystem.GOOGLE_DRIVE),
        ("Monday", SourceSystem.MONDAY),
    ):
        try:
            connector_cls = get_connector_class(source)
            with session_scope() as s:
                connector_cls(session=s, organization_id=org_id)  # construct only
        except Exception as exc:  # noqa: BLE001
            print(
                f"FAIL preflight: cannot initialise the {label} connector.",
                file=sys.stderr,
            )
            print(f"  {exc}", file=sys.stderr)
            print(
                "\nThe database was NOT modified -- nothing was wiped.",
                file=sys.stderr,
            )
            if source == SourceSystem.GOOGLE_DRIVE:
                print(
                    "  The Google Drive token looks expired/revoked. Run:\n"
                    "      project_db gdrive-auth\n"
                    "  then re-run:  project_db rebuild --yes",
                    file=sys.stderr,
                )
            return 2
        sync_plan.append((label, connector_cls))
    print("[rebuild] preflight OK -- all connectors reachable.")

    # --- Export proposals (the one piece of human-authored data) ---------
    with session_scope() as s:
        proposal_dump = [
            {col.name: getattr(p, col.name) for col in Proposal.__table__.columns}
            for p in s.query(Proposal).all()
        ]
    if proposal_dump:
        backup = (
            Path(__file__).resolve().parent.parent.parent
            / f"proposals_backup_{datetime.utcnow():%Y%m%d_%H%M%S}.json"
        )
        backup.write_text(
            json.dumps(proposal_dump, indent=2, default=str), encoding="utf-8"
        )
        print(f"[rebuild] exported {len(proposal_dump)} proposal(s) -> {backup}")

    # --- Wipe connector-derived rows -------------------------------------
    derived = [
        "proposal", "task", "invoice", "daily_log", "project",
        "lead", "deal", "client", "vendor", "property", "user",
        "external_id",
    ]
    existing = set(sa_inspect(engine).get_table_names())

    print("[rebuild] wiping connector-derived tables...")
    with engine.begin() as conn:
        is_sqlite = engine.dialect.name == "sqlite"
        if is_sqlite:
            conn.execute(text("PRAGMA foreign_keys=OFF"))
        # Detach preserved Documents from rows about to be deleted so no
        # foreign key dangles once FK enforcement is back on.
        conn.execute(
            text(
                "UPDATE document SET project_id=NULL, deal_id=NULL, "
                "client_id=NULL, category=NULL"
            )
        )
        for table in derived:
            if table in existing:
                conn.execute(text(f'DELETE FROM "{table}"'))
        if is_sqlite:
            conn.execute(text("PRAGMA foreign_keys=ON"))
    print("[rebuild] wipe complete.")

    with session_scope() as s:
        if s.query(Organization).count() == 0:
            s.add(Organization(name="Default Org"))

    # --- Re-sync (connectors already preflight-validated) ----------------
    for label, connector_cls in sync_plan:
        print(f"[rebuild] syncing {label}...")
        try:
            with session_scope() as s:
                org = s.query(Organization).first()
                connector = connector_cls(session=s, organization_id=org.canonical_id)
                report = connector.sync()
            print(f"  {report.summary()}")
            for err in report.errors[:10]:
                print(f"    - {err}")
        except Exception as exc:  # noqa: BLE001
            print(f"  FAIL: {label} sync errored: {exc}", file=sys.stderr)
            print(
                "  DB is mid-rebuild -- fix the issue and re-run "
                "`project_db rebuild --yes`.",
                file=sys.stderr,
            )
            return 1

    print("\n[rebuild] done.  Run `project_db doctor` to verify.")
    return 0


def cmd_refresh(args: argparse.Namespace) -> int:
    """Pull fresh data (delta sync) then re-embed any CHANGED documents.

    One command: delta-syncs the live connectors (Monday now; Drive when it
    goes live), then runs the idempotent embed step so only documents whose
    text actually changed get re-embedded. Each step is independent -- a
    connector without credentials is reported and skipped, not fatal.
    """
    from project_db.connectors.refresh import run_refresh

    engine = get_engine()
    Base.metadata.create_all(engine)
    ensure_sqlite_schema(engine)

    with session_scope() as s:
        report = run_refresh(
            s,
            delta=not args.full,
            embed=not args.no_embed,
            log=lambda m: print(m),
        )

    print()
    status = "OK" if report.ok else "completed WITH ERRORS"
    print(f"=== REFRESH {status} ({report.one_line()}) ===")
    for st in report.steps:
        mark = "OK  " if st.ok else "FAIL"
        print(f"  [{mark}] {st.name}: {st.summary or st.error or ''}")
    return 0 if report.ok else 1


def cmd_serve(args: argparse.Namespace) -> int:
    """Launch the local web UI bound to 127.0.0.1.

    Hard-binds to loopback -- there is no --host flag on purpose.  The UI
    has no auth and exposes mutation routes; remote access is out of scope.

    On startup it kicks off a BACKGROUND refresh (delta sync + incremental
    re-embed) so the app opens on fresh data without blocking startup. The
    footer shows when it last refreshed. Disable with --no-refresh.
    """
    try:
        import uvicorn
    except ImportError:
        print(
            "uvicorn not installed.  Install the UI extra:\n"
            "    pip install -e \".[ui]\"",
            file=sys.stderr,
        )
        return 2

    engine = get_engine()
    Base.metadata.create_all(engine)
    ensure_sqlite_schema(engine)

    if not getattr(args, "no_refresh", False):
        import threading

        from project_db.connectors.refresh import run_refresh
        from project_db.web import refresh_state

        def _bg_refresh() -> None:
            try:
                refresh_state.mark_running()
                with session_scope() as s:
                    rep = run_refresh(
                        s, delta=True, embed=True,
                        log=lambda m: print(m, file=sys.stderr),
                    )
                refresh_state.set_last(rep)
                print(f"[refresh] done: {rep.one_line()}", file=sys.stderr)
            except Exception as exc:  # noqa: BLE001 -- background, never crash serve
                refresh_state.set_last(None)
                print(f"[refresh] background refresh errored: {exc}", file=sys.stderr)

        threading.Thread(target=_bg_refresh, name="alta-refresh", daemon=True).start()
        print("[refresh] background data refresh started "
              "(delta sync + re-embed changed docs; --no-refresh to disable)")

    from project_db.web.app import create_app

    app = create_app()
    print(f"project_db UI starting on http://127.0.0.1:{args.port}")
    print("Ctrl-C to stop.")
    uvicorn.run(app, host="127.0.0.1", port=args.port, log_level="info")
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

    daily = sub.add_parser(
        "daily",
        help="One-screen daily project review; read-only unless --propose-timelines",
    )
    daily.add_argument("project", nargs="+", help="Project name fragment or UUID")
    daily.add_argument(
        "--propose-timelines",
        action="store_true",
        help="Call the configured LLM and write PENDING timeline proposals",
    )
    daily.add_argument(
        "--limit",
        default=10,
        type=int,
        help="Max pending proposals / dateless tasks to print (default 10)",
    )
    daily.add_argument(
        "--token-budget",
        default=20_000,
        type=int,
        help="LLM context token budget when --propose-timelines is used",
    )
    daily.add_argument(
        "--max-docs",
        default=30,
        type=int,
        help="Max document bodies for timeline proposal generation",
    )
    daily.add_argument(
        "--max-output-tokens",
        default=3000,
        type=int,
        help="LLM output cap for timeline proposal generation",
    )
    daily.set_defaults(func=cmd_daily)

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

    propose = sub.add_parser(
        "propose",
        help="Generate LLM proposals for a project (writes PENDING Proposal rows)",
    )
    propose.add_argument("kind", help="What to propose: timelines | scope")
    propose.add_argument("project", help="Project name fragment or canonical UUID")
    propose.set_defaults(func=cmd_propose)

    proposals = sub.add_parser("proposals", help="View LLM proposals")
    proposals_sub = proposals.add_subparsers(dest="proposals_action", required=True)
    pl = proposals_sub.add_parser("list", help="List proposals (newest first)")
    pl.add_argument(
        "--status",
        help="Filter: pending | accepted | rejected | superseded",
    )
    pl.add_argument("--kind", help="Filter by field_name, e.g. timeline")
    ps = proposals_sub.add_parser("show", help="Show one proposal in full detail")
    ps.add_argument("proposal_id", help="Proposal canonical UUID")
    pr = proposals_sub.add_parser(
        "reject", help="Reject a PENDING proposal (status -> REJECTED; no Monday write)",
    )
    pr.add_argument(
        "proposal_id", nargs="?",
        help="Proposal UUID, or 'all'. Omit to list pending proposals.",
    )
    pr.add_argument("--reason", help="Why it was rejected (stored on the proposal)")
    pr.add_argument("--by", help="Who rejected it (default: OS username)")
    pr.add_argument(
        "--yes", action="store_true",
        help="Required to confirm 'reject all'",
    )
    pa = proposals_sub.add_parser(
        "accept",
        help="Accept a PENDING proposal -- writes the change back to Monday",
    )
    pa.add_argument(
        "proposal_id", nargs="?",
        help="Proposal UUID, or 'all'. Omit to list pending proposals.",
    )
    pa.add_argument(
        "--dry-run", action="store_true",
        help="Preview the Monday write without applying it or changing status",
    )
    pa.add_argument("--by", help="Who accepted it (default: OS username)")
    pa.add_argument(
        "--yes", action="store_true",
        help="Required to confirm 'accept all'",
    )
    proposals.set_defaults(func=cmd_proposals)

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

    sub.add_parser(
        "doctor",
        help="Audit canonical-data integrity (read-only): phantom/duplicate "
             "projects, mislinked or orphaned documents",
    ).set_defaults(func=cmd_doctor)

    briefing = sub.add_parser(
        "briefing",
        help="Attention briefing (read-only): ranked money/scope/schedule/"
             "document flags across the portfolio. No LLM.",
    )
    briefing.add_argument(
        "--limit", type=int, default=25,
        help="Maximum number of items to show (default 25)",
    )
    briefing.set_defaults(func=cmd_briefing)

    commit = sub.add_parser(
        "commitments",
        help="Money-at-Risk for a project (read-only): contract obligations "
             "with overdue/due-soon status. No LLM.",
    )
    commit.add_argument("project", help="Project canonical UUID or name fragment")
    commit.set_defaults(func=cmd_commitments)

    vc = sub.add_parser(
        "value-caught",
        help="ROI scoreboard (read-only): total money ALTA has surfaced as "
             "needing action across the portfolio. No LLM.",
    )
    vc.set_defaults(func=cmd_value_caught)

    ml = sub.add_parser(
        "money-line",
        help="One-line money summary for a project (read-only): revenue / costs "
             "/ margin + overdue obligations. No LLM.",
    )
    ml.add_argument("project", help="Project canonical UUID or name fragment")
    ml.set_defaults(func=cmd_money_line)

    rebuild = sub.add_parser(
        "rebuild",
        help="Re-derive the canonical DB from Drive + Monday (drops derived "
             "rows, preserves documents + extracted text). Requires --yes.",
    )
    rebuild.add_argument(
        "--yes",
        action="store_true",
        help="Confirm the destructive re-derivation (required to proceed)",
    )
    rebuild.set_defaults(func=cmd_rebuild)

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

    ef = sub.add_parser(
        "extract-financials",
        help="Extract monetary records (quotes/invoices/receipts) from a "
             "project's Drive documents into FinancialRecord, then print the "
             "two-sided money-flow reconciliation.  Calls the LLM; "
             "fresh-snapshot per run.",
    )
    ef.add_argument("project", help="Project canonical UUID or name fragment")
    ef.add_argument(
        "--max-docs", type=int, default=None,
        help="Cap the number of financial documents processed (default: all "
             "candidates; documents are batched across multiple LLM calls)",
    )
    ef.add_argument(
        "--structured", action="store_true",
        help="Use the OpenAI structured-outputs extractor (classifies each doc; "
             "no keyword/roll-up heuristics). Needs OPENAI_API_KEY. Recommended.",
    )
    ef.set_defaults(func=cmd_extract_financials)

    eo = sub.add_parser(
        "extract-obligations",
        help="Extract dated/dollar obligations (milestones, retainage, "
             "penalties, deposits, settlements, deadlines) from a project's "
             "contract documents. Calls the LLM; fresh-snapshot per run.",
    )
    eo.add_argument("project", help="Project canonical UUID or name fragment")
    eo.add_argument(
        "--structured", action="store_true",
        help="Use the OpenAI structured-outputs extractor (classifies each doc; "
             "no keyword gate). Needs OPENAI_API_KEY. Recommended.",
    )
    eo.set_defaults(func=cmd_extract_obligations)

    ed = sub.add_parser(
        "embed-documents",
        help="Embed document text into vectors for RAG (OpenAI embeddings). "
             "Idempotent; skips unchanged docs. Run after extract-content.",
    )
    ed.add_argument("--project", default=None,
                    help="Limit to one project (UUID or name fragment)")
    ed.add_argument("--overwrite", action="store_true",
                    help="Re-embed even unchanged documents")
    ed.add_argument("--limit", type=int, default=None,
                    help="Cap the number of documents processed")
    ed.set_defaults(func=cmd_embed_documents)

    rs = sub.add_parser(
        "rag-search",
        help="Retrieve the most relevant document chunks for a query (RAG "
             "debug surface).",
    )
    rs.add_argument("query", help="The search query")
    rs.add_argument("--project", default=None,
                    help="Limit retrieval to one project (UUID or name fragment)")
    rs.add_argument("--top-k", type=int, default=8,
                    help="Number of chunks to return (default 8)")
    rs.set_defaults(func=cmd_rag_search)

    impr = sub.add_parser(
        "import-roadmap",
        help="Import the canonical design-phase roadmap from an xlsx into "
             "the roadmap_task table (Layer 1 of the roadmap integration).",
    )
    impr.add_argument(
        "path", nargs="?", default=None,
        help="Path to the roadmap xlsx (defaults to docs/Project Roadmap.xlsx)",
    )
    impr.add_argument(
        "--overwrite", action="store_true",
        help="Drop existing roadmap_task rows before importing (required "
             "on re-import after edits)",
    )
    impr.set_defaults(func=cmd_import_roadmap)

    classify = sub.add_parser(
        "classify-roadmap",
        help="Use Sonnet to draft actor (ARCHITECT/CONTRACTOR/BOTH) for "
             "each roadmap_task row.  Single LLM call.  Re-runnable.",
    )
    classify.set_defaults(func=cmd_classify_roadmap)

    fn = sub.add_parser(
        "field-note",
        help="Submit a plain-language field note -- classifies, task-matches, and "
             "creates PENDING Proposals for human review. Needs OPENAI_API_KEY.",
    )
    fn.add_argument("project", help="Project name fragment or canonical UUID")
    fn.add_argument("note", nargs="+", help="The field note text (quoted or multiple words)")
    fn.set_defaults(func=cmd_field_note)

    serve = sub.add_parser(
        "serve",
        help="Launch the local web UI on 127.0.0.1 (localhost only, no auth)",
    )
    serve.add_argument(
        "--port", type=int, default=8000,
        help="TCP port to bind on 127.0.0.1 (default 8000)",
    )
    serve.add_argument(
        "--no-refresh", action="store_true",
        help="Skip the background data refresh (delta sync + re-embed) on startup",
    )
    serve.set_defaults(func=cmd_serve)

    refresh = sub.add_parser(
        "refresh",
        help="Pull fresh data (delta sync) then re-embed only CHANGED documents",
    )
    refresh.add_argument(
        "--full", action="store_true",
        help="Force a full sync instead of delta",
    )
    refresh.add_argument(
        "--no-embed", action="store_true",
        help="Sync only; skip the re-embedding step",
    )
    refresh.set_defaults(func=cmd_refresh)

    return p


def force_utf8_output() -> None:
    """Make console output crash-proof against the bilingual (FR) dataset.

    Windows consoles default stdout to a legacy code page (cp1252) that hard-
    CRASHES (UnicodeEncodeError) on accented French text and the em-dashes /
    arrows LLM answers are full of.  Reconfiguring to UTF-8 with
    ``errors="replace"`` fixes both: prose renders correctly, and any char the
    terminal still can't encode degrades to '?' instead of raising.  This is the
    once-and-for-all fix -- call it at every entry point (CLI + scripts) so no
    `print()` anywhere has to stay paranoid about non-ASCII.
    """
    for _stream in (sys.stdout, sys.stderr):
        try:
            _stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass


def main(argv: list[str] | None = None) -> int:
    force_utf8_output()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
