"""Verification tool: compare extracted FinancialLineItem rows against the
ACTUAL source document text, so we can prove the files are being read correctly.

For a project (or --all), per financial document this prints:
  * the document type the extractor decided + how many rows landed
  * every row: side / status / division / amount_type / amount / verified flag
    + the quoted_excerpt the amount supposedly came from
  * a deterministic FIDELITY CHECK: does the amount actually appear in the
    document's extracted_text? (catches a model hallucinating a number)
  * the head of the raw source text so a human can eyeball the real document

Read-only. No DB writes, no API calls. Run:
    py -3.13 scripts/audit_financial_extraction.py "1455 Rue St. Mathieu"
    py -3.13 scripts/audit_financial_extraction.py --all --json
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict

import project_db.config  # noqa: F401  (triggers selective .env load)
from project_db.db.models import Project
from project_db.db.models.docs import Document, DocumentText
from project_db.db.models.finance import FinancialLineItem
from project_db.db.session import session_scope

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
except Exception:
    pass


def _amount_in_text(amount, text: str) -> bool:
    """True if the numeric amount appears in the source text in any common
    formatting (1234.5 / 1,234.50 / 1 234,50 -- Quebec French). Tolerant: we are
    checking 'did the model invent this number', not exact string match."""
    if amount is None or not text:
        return False
    try:
        val = float(amount)
    except (TypeError, ValueError):
        return False
    if val == 0:
        return True  # zero rows are structural placeholders, not hallucinations
    # Normalise the text: drop spaces used as thousands sep, unify decimal comma.
    norm = text.replace(" ", " ")  # noqa: RUF001 - intentional Quebec-French NBSP/narrow-NBSP handling
    norm_nospace = re.sub(r"(?<=\d)[  ](?=\d)", "", norm)  # noqa: RUF001 - "1 234" -> "1234"
    candidates = set()
    whole = round(val)  # val is float -> round() already returns int
    candidates.add(f"{val:.2f}")  # 1234.50
    candidates.add(f"{val:.2f}".rstrip("0").rstrip("."))  # 1234.5 / 1234
    candidates.add(f"{whole}")  # 1234
    candidates.add(f"{whole:,}")  # 1,234
    candidates.add(f"{val:,.2f}")  # 1,234.50
    # French decimal comma forms
    candidates.add(f"{val:.2f}".replace(".", ","))  # 1234,50
    candidates.add(f"{val:,.2f}".replace(",", " ").replace(".", ","))  # 1 234,50
    hay = norm + "\n" + norm_nospace
    return any(c in hay for c in candidates if c)


def audit_project(session, project) -> dict:
    rows = (
        session.query(FinancialLineItem)
        .filter(FinancialLineItem.project_id == project.canonical_id)
        .all()
    )
    doc_ids = {r.document_id for r in rows if r.document_id}
    docs = {
        d.canonical_id: d
        for d in session.query(Document).filter(Document.canonical_id.in_(doc_ids or [None])).all()
    }
    texts = {
        t.document_id: (t.extracted_text or "")
        for t in session.query(DocumentText)
        .filter(DocumentText.document_id.in_(doc_ids or [None]))
        .all()
    }

    by_doc: dict = defaultdict(list)
    for r in rows:
        by_doc[r.document_id].append(r)

    out_docs = []
    n_rows = 0
    n_verified_flag = 0
    n_in_text = 0
    n_missing_text = 0
    for did, drows in by_doc.items():
        doc = docs.get(did)
        text = texts.get(did, "")
        doc_rows = []
        for r in drows:
            n_rows += 1
            in_text = _amount_in_text(r.amount, text)
            if r.amount_verified:
                n_verified_flag += 1
            if in_text:
                n_in_text += 1
            doc_rows.append(
                {
                    "side": r.side,
                    "status": r.status,
                    "div": r.division_code,
                    "div_name": r.division_name,
                    "amount_type": r.amount_type,
                    "amount": float(r.amount or 0),
                    "method": r.classification_method,
                    "amount_verified_flag": bool(r.amount_verified),
                    "amount_found_in_source": in_text,
                    "excerpt": (r.quoted_excerpt or "")[:120],
                    "description": (r.description or "")[:80],
                }
            )
        if not text:
            n_missing_text += 1
        out_docs.append(
            {
                "document": (doc.name if doc else str(did)),
                "source_doc_type": next((r.source_doc_type for r in drows), None),
                "text_len": len(text),
                "rows": doc_rows,
                "text_head": text[:600],
            }
        )

    return {
        "project": project.name,
        "n_docs_with_rows": len(by_doc),
        "n_rows": n_rows,
        "n_amount_found_in_source": n_in_text,
        "n_amount_verified_flag": n_verified_flag,
        "n_docs_missing_text": n_missing_text,
        "docs": out_docs,
    }


def _print_human(rep: dict) -> None:
    print(f"\n{'=' * 88}\nPROJECT: {rep['project']}")
    print(
        f"  docs={rep['n_docs_with_rows']} rows={rep['n_rows']} "
        f"amount-found-in-source={rep['n_amount_found_in_source']}/{rep['n_rows']} "
        f"(model-verified-flag={rep['n_amount_verified_flag']})"
    )
    for d in rep["docs"]:
        print(
            f"\n  --- {d['document']}  (type={d['source_doc_type']} text_len={d['text_len']}) ---"
        )
        for r in d["rows"]:
            ok = "OK " if r["amount_found_in_source"] else "!! "
            print(
                f"    {ok}{r['side']:7} {r['status']!s:9} div{r['div']:>5} "
                f"{r['amount_type']:9} {r['amount']:>12,.2f}  [{r['method']}]"
            )
            if not r["amount_found_in_source"]:
                print(f"        excerpt: {r['excerpt']!r}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("project", nargs="?", help="project name/ref (omit with --all)")
    ap.add_argument("--all", action="store_true", help="audit every project with rows")
    ap.add_argument("--json", action="store_true", help="emit JSON")
    args = ap.parse_args()

    with session_scope() as s:
        if args.all:
            projects = s.query(Project).all()
        else:
            if not args.project:
                print("FAIL: give a project name or --all", file=sys.stderr)
                return 2
            projects = s.query(Project).filter(Project.name.ilike(f"%{args.project}%")).all()
            if not projects:
                print(f"FAIL: no project matched {args.project!r}", file=sys.stderr)
                return 2

        reports = []
        for p in projects:
            rep = audit_project(s, p)
            if rep["n_rows"] == 0:
                continue
            reports.append(rep)

        if args.json:
            print(json.dumps(reports, indent=2, default=str))
        else:
            grand_rows = sum(r["n_rows"] for r in reports)
            grand_found = sum(r["n_amount_found_in_source"] for r in reports)
            for rep in reports:
                _print_human(rep)
            print(f"\n{'=' * 88}")
            print(
                f"TOTAL: {len(reports)} projects, {grand_rows} rows, "
                f"{grand_found} amounts found verbatim in source "
                f"({100 * grand_found / grand_rows if grand_rows else 0:.1f}%)"
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
