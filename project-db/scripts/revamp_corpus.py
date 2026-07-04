"""One-off corpus revamp: run the NEW parsers over the WHOLE Drive corpus, in
priority order, with live visible progress.

WHY priority order: a full Docling pass is CPU-heavy (~minutes per PDF, ~a day
for the whole corpus on a laptop), but spreadsheets parse in ~0.05s and that is
where the financial ledger actually lives. So we drain the cheap, financially
dense files first, then PDFs ranked financial-first -- if you stop the run early,
the highest-value evidence is already captured.

This is the SAME seam as scripts/parse_documents.py (parse_document_content ->
DocumentParse + EvidenceSpan + DocumentText). It is idempotent: docs that already
have a successful parse are skipped (no fetch), so it is safe to stop and resume.

    py -3.13 scripts/revamp_corpus.py --plan          # show the order, parse nothing
    py -3.13 scripts/revamp_corpus.py                 # parse all, financial-first
    py -3.13 scripts/revamp_corpus.py --financial-only# skip non-financial PDFs entirely
    py -3.13 scripts/revamp_corpus.py --overwrite     # re-parse even already-parsed docs

Handled: PDF, XLSX, CSV, Google Sheets (exported CSV). Other types are skipped.
"""

from __future__ import annotations

import argparse
import time

import project_db.config  # noqa: F401
from project_db.cli import force_utf8_output
from project_db.connectors.gdrive.client import GDriveClient
from project_db.db.migrations import ensure_sqlite_schema
from project_db.db.models import Document, DocumentParse, Project
from project_db.db.session import get_engine, session_scope
from project_db.parsing import parse_document_content

force_utf8_output()

# Fetch maps (mirror scripts/parse_documents.py).
_BINARY_MIMES = {
    "application/pdf": "application/pdf",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": (
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    ),
    "text/csv": "text/csv",
}
_EXPORT_MIMES = {"application/vnd.google-apps.spreadsheet": "text/csv"}
_HANDLED = set(_BINARY_MIMES) | set(_EXPORT_MIMES)
# Fast types parse in ~0.05s; PDFs go through Docling (minutes).
_FAST_MIMES = _HANDLED - {"application/pdf"}

# Financial signal in a filename / folder / category.
_FIN_KW = (
    "estimate",
    "invoice",
    "quote",
    "quotation",
    "receipt",
    "budget",
    "cost",
    "sow",
    "scope of work",
    "change order",
    "change-order",
    "proposal",
    "contract",
    "billing",
    "payment",
    "ledger",
    "extras",
    "job cost",
    "purchase order",
    "deposit",
    # Quebec French
    "facture",
    "soumission",
    "devis",
    "bon de commande",
    "contrat",
)


def _fin_signal(*parts: str | None) -> bool:
    blob = " ".join(p.lower() for p in parts if p)
    return any(kw in blob for kw in _FIN_KW)


def _priority(doc: Document, *, active_project_ids: set) -> int:
    """Higher = parse sooner. Cheap+financial first, then financial PDFs, then rest."""
    score = 0
    if doc.mime_type in _FAST_MIMES:
        score += 100  # cheap AND ledger-dense -> always first
    if _fin_signal(doc.name):
        score += 40
    if _fin_signal(doc.folder_path, doc.category):
        score += 15
    if doc.project_id is not None:
        score += 5
        if doc.project_id in active_project_ids:
            score += 20
    return score


def _fetch_bytes(client: GDriveClient, doc: Document) -> tuple[bytes, str]:
    if doc.mime_type in _EXPORT_MIMES:
        m = _EXPORT_MIMES[doc.mime_type]
        return client.export_google_doc(doc.storage_ref, m), m
    return client.download_file(doc.storage_ref), _BINARY_MIMES[doc.mime_type]


def _fmt_eta(seconds: float) -> str:
    seconds = int(max(0, seconds))
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    if h:
        return f"{h}h{m:02d}m"
    if m:
        return f"{m}m{s:02d}s"
    return f"{s}s"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--plan", action="store_true", help="print the parse order, parse nothing")
    ap.add_argument(
        "--financial-only", action="store_true", help="skip PDFs with no financial signal"
    )
    ap.add_argument("--overwrite", action="store_true", help="re-parse already-parsed docs")
    ap.add_argument("--limit", type=int, default=None, help="cap number of docs (smoke test)")
    args = ap.parse_args()

    ensure_sqlite_schema(get_engine())
    client = None if args.plan else GDriveClient()

    with session_scope() as s:
        active_project_ids = {
            p.canonical_id
            for p in s.query(Project).all()
            if getattr(getattr(p, "status", None), "name", "") == "ACTIVE"
        }

        docs = (
            s.query(Document)
            .filter(
                Document.mime_type.in_(list(_HANDLED)),
                Document.storage_ref.isnot(None),
                Document.is_trashed.is_(False),
            )
            .all()
        )

        if args.financial_only:
            docs = [
                d
                for d in docs
                if d.mime_type in _FAST_MIMES or _fin_signal(d.name, d.folder_path, d.category)
            ]

        docs.sort(
            key=lambda d: (
                -_priority(d, active_project_ids=active_project_ids),
                0 if d.mime_type in _FAST_MIMES else 1,
                (d.name or "").lower(),
            )
        )
        if args.limit:
            docs = docs[: args.limit]

        n_fast = sum(1 for d in docs if d.mime_type in _FAST_MIMES)
        n_pdf = len(docs) - n_fast
        print("=" * 70, flush=True)
        print("CORPUS REVAMP -- new structure-preserving parsers (Docling/openpyxl)", flush=True)
        print(
            f"  {len(docs)} doc(s) queued: {n_fast} fast (xlsx/csv/sheet), {n_pdf} PDF "
            f"| overwrite={args.overwrite} financial_only={args.financial_only}",
            flush=True,
        )
        print(f"  active projects: {len(active_project_ids)}", flush=True)
        print("  order: cheap+financial first, then financial PDFs, then the rest", flush=True)
        print("=" * 70, flush=True)

        if args.plan:
            for i, d in enumerate(docs[:60], 1):
                pr = _priority(d, active_project_ids=active_project_ids)
                tag = "FAST" if d.mime_type in _FAST_MIMES else "pdf "
                print(f"  {i:>3}. [{tag} p{pr:>3}] {(d.name or '')[:60]}", flush=True)
            if len(docs) > 60:
                print(f"  ... and {len(docs) - 60} more", flush=True)
            return 0

        done = skipped = failed = 0
        pdf_times: list[float] = []
        t_start = time.monotonic()

        for i, doc in enumerate(docs, 1):
            existing = (
                s.query(DocumentParse)
                .filter_by(document_id=doc.canonical_id, status="success")
                .first()
            )
            if existing and not args.overwrite:
                skipped += 1
                continue
            if existing and args.overwrite:
                for p in s.query(DocumentParse).filter_by(document_id=doc.canonical_id).all():
                    s.delete(p)
                s.flush()

            is_pdf = doc.mime_type == "application/pdf"
            try:
                raw, parser_mime = _fetch_bytes(client, doc)
            except Exception as exc:
                failed += 1
                print(
                    f"  [{i}/{len(docs)}] FETCH-FAIL {(doc.name or '')[:46]!r}: {exc}", flush=True
                )
                continue

            t0 = time.monotonic()
            try:
                parse = parse_document_content(
                    s, document=doc, content=raw, mime=parser_mime, filename=doc.name
                )
            except Exception as exc:
                failed += 1
                s.rollback()
                print(f"  [{i}/{len(docs)}] ERROR {(doc.name or '')[:46]!r}: {exc}", flush=True)
                continue
            dt = time.monotonic() - t0
            s.commit()

            if parse.status == "success":
                done += 1
            elif parse.status == "skipped":
                skipped += 1
            else:
                failed += 1

            tag = "PDF" if is_pdf else "fast"
            line = (
                f"  [{i}/{len(docs)}] {tag} {dt:6.1f}s  {parse.status:>7}  {(doc.name or '')[:48]}"
            )
            if is_pdf:
                pdf_times.append(dt)
                avg = sum(pdf_times) / len(pdf_times)
                pdf_left = sum(1 for d in docs[i:] if d.mime_type == "application/pdf")
                line += f"  | pdf avg {avg:4.0f}s, ~{_fmt_eta(avg * pdf_left)} left"
            print(line, flush=True)

        elapsed = time.monotonic() - t_start
        print("=" * 70, flush=True)
        print(
            f"DONE in {_fmt_eta(elapsed)} -- parsed {done}, skipped {skipped}, failed {failed}",
            flush=True,
        )
        print(
            "Evidence spine populated. Slice 6 will read these spans into the ledger.", flush=True
        )
        print("=" * 70, flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
