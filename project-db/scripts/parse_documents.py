"""Backfill the evidence layer: run the NEW parsers over real Drive documents.

This is the integration seam that makes the parsing refactor actually USED. It
fetches each document's bytes from Drive and runs `parse_document_content`,
storing a `DocumentParse` + `EvidenceSpan` rows + a synced `DocumentText`
(structure-preserving, replacing the old flat extraction as the canonical parse).

Idempotent: by default it SKIPS documents that already have a successful parse
(no fetch), so it is safe to re-run and to point at the whole corpus. `--overwrite`
re-parses (and drops the document's old parses first). A future step wires this
same seam into the live sync so refreshes re-parse changed documents
automatically.

    py -3.13 scripts/parse_documents.py --limit 5            # small validation run
    py -3.13 scripts/parse_documents.py --project Rockland   # one project
    py -3.13 scripts/parse_documents.py --all                # whole corpus (slow: Docling)

Handled today: PDF, XLSX, CSV, and Google Sheets (exported as CSV). Images,
Google Docs/Slides, and other types are skipped (no table parser yet).
"""

from __future__ import annotations

import argparse
import sys
import time

import project_db.config  # noqa: F401
from project_db.connectors.gdrive.client import GDriveClient
from project_db.db.migrations import ensure_sqlite_schema
from project_db.db.models import Document, DocumentParse, Project
from project_db.db.session import get_engine, session_scope
from project_db.parsing import parse_document_content

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
except Exception:
    pass

# mime -> how to fetch bytes + what mime to tell the parser router.
_BINARY_MIMES = {
    "application/pdf": "application/pdf",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": (
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    ),
    "text/csv": "text/csv",
}
_EXPORT_MIMES = {
    # Google Sheets -> export as CSV so CsvParser handles it.
    "application/vnd.google-apps.spreadsheet": "text/csv",
}
_HANDLED = set(_BINARY_MIMES) | set(_EXPORT_MIMES)


def _fetch_bytes(client: GDriveClient, doc: Document) -> tuple[bytes, str]:
    """Return (raw_bytes, parser_mime) for a document, or raise."""
    if doc.mime_type in _EXPORT_MIMES:
        export_mime = _EXPORT_MIMES[doc.mime_type]
        return client.export_google_doc(doc.storage_ref, export_mime), export_mime
    return client.download_file(doc.storage_ref), _BINARY_MIMES[doc.mime_type]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--project", default=None, help="only documents of projects matching this name")
    ap.add_argument("--all", action="store_true", help="parse the whole corpus")
    ap.add_argument("--limit", type=int, default=None, help="cap number of documents")
    ap.add_argument(
        "--overwrite", action="store_true", help="re-parse docs that already have a parse"
    )
    ap.add_argument(
        "--mimes", default=None, help="comma-separated mime filter (default: all handled)"
    )
    args = ap.parse_args()

    if not (args.all or args.project or args.limit):
        print(
            "Refusing to run unbounded. Pass --all, --project NAME, or --limit N.", file=sys.stderr
        )
        return 2

    want_mimes = set(args.mimes.split(",")) if args.mimes else _HANDLED

    # Ensure the evidence tables exist on the real DB (idempotent; the CLI does
    # this on init/serve, but a standalone script must apply it itself).
    ensure_sqlite_schema(get_engine())

    client = GDriveClient()
    counts: dict[str, int] = {}
    timings: dict[str, list[float]] = {}
    n_skipped_existing = 0
    processed = 0

    with session_scope() as s:
        q = s.query(Document).filter(
            Document.mime_type.in_(list(want_mimes)),
            Document.storage_ref.isnot(None),
            Document.is_trashed.is_(False),
        )
        if args.project:
            proj_ids = [
                p.canonical_id
                for p in s.query(Project).filter(Project.name.ilike(f"%{args.project}%")).all()
            ]
            q = q.filter(Document.project_id.in_(proj_ids or [None]))
        docs = q.all()
        if args.limit:
            docs = docs[: args.limit]
        total = len(docs)
        print(f"Candidates: {total} document(s). overwrite={args.overwrite}\n")

        for i, doc in enumerate(docs, 1):
            existing = (
                s.query(DocumentParse)
                .filter_by(document_id=doc.canonical_id, status="success")
                .first()
            )
            if existing and not args.overwrite:
                n_skipped_existing += 1
                continue
            if existing and args.overwrite:
                for p in s.query(DocumentParse).filter_by(document_id=doc.canonical_id).all():
                    s.delete(p)
                s.flush()

            try:
                raw, parser_mime = _fetch_bytes(client, doc)
            except Exception as exc:
                counts["fetch-failed"] = counts.get("fetch-failed", 0) + 1
                print(f"  [{i}/{total}] FETCH-FAIL {doc.name[:42]!r}: {exc}")
                continue

            t0 = time.monotonic()
            try:
                parse = parse_document_content(
                    s, document=doc, content=raw, mime=parser_mime, filename=doc.name
                )
            except Exception as exc:
                counts["unhandled"] = counts.get("unhandled", 0) + 1
                print(f"  [{i}/{total}] UNHANDLED {doc.name[:42]!r}: {exc}")
                s.rollback()
                continue
            dt = time.monotonic() - t0

            key = doc.mime_type.split(".")[-1][:8]
            counts[parse.status] = counts.get(parse.status, 0) + 1
            timings.setdefault(key, []).append(dt)
            processed += 1
            if i % 10 == 0 or i == total:
                s.commit()
                print(
                    f"  [{i}/{total}] committed. last={doc.name[:38]!r} status={parse.status} {dt:.1f}s"
                )
        s.commit()

    print("\n--- Summary ---")
    print(f"  skipped (already parsed): {n_skipped_existing}")
    for k, v in sorted(counts.items()):
        print(f"  {k:>16}: {v}")
    print("\n--- Timing (avg seconds/doc by type) ---")
    for k, ts in sorted(timings.items()):
        print(f"  {k:>8}: n={len(ts):>3}  avg={sum(ts) / len(ts):.2f}s  max={max(ts):.2f}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
