"""Export one self-contained financial bundle per project for the cross-document
reconciliation pass (Phase B).

A single-document extractor cannot see that a lump 'Statement of Work' restates
two itemized quotes, or that two PDFs are the same invoice scanned twice. This
dumps, per project, every financial document with its extracted ledger rows + a
text excerpt, so a reconciliation agent can read them TOGETHER and flag probable
double-counts / restatements / superseding versions.

Read-only. No DB writes, no API calls. Writes JSON bundles to a target dir:
    py -3.13 scripts/export_financial_bundles.py --out .reconcile_bundles
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

import project_db.config  # noqa: F401  (triggers selective .env load)
from project_db.db.models import Document, Project
from project_db.db.models.docs import DocumentText
from project_db.db.models.finance import FinancialLineItem
from project_db.db.session import session_scope

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
except Exception:
    pass

# Revenue rows in these statuses count as CONTRACTED (banked); "proposed" is
# pipeline and "superseded" is excluded -- mirrors report_division_margins.
_CONTRACTED = {"accepted", "actual", "unknown", None}


def _row_dict(r: FinancialLineItem) -> dict:
    try:
        meta = json.loads(r.source_meta_json or "{}")
    except Exception:
        meta = {}
    return {
        "side": r.side,
        "status": r.status,
        "division_code": r.division_code,
        "division_name": r.division_name,
        "amount_type": r.amount_type,
        "amount": float(r.amount or 0),
        "description": (r.description or "")[:120],
        "source": r.source,
        "is_summary_rollup": bool(meta.get("is_summary_rollup")),
    }


def export_project(session, project, *, text_chars: int) -> dict | None:
    rows = (
        session.query(FinancialLineItem)
        .filter(FinancialLineItem.project_id == project.canonical_id)
        .all()
    )
    if not rows:
        return None
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
    contracted_rev = proposed_rev = total_cost = 0.0
    for did, drows in by_doc.items():
        doc = docs.get(did)
        doc_rows = [_row_dict(r) for r in drows]
        rev_total = sum(d["amount"] for d in doc_rows if d["side"] == "revenue")
        cost_total = sum(d["amount"] for d in doc_rows if d["side"] == "cost")
        statuses = {d["status"] for d in doc_rows if d["side"] == "revenue"}
        for d in doc_rows:
            if d["side"] == "revenue":
                if d["status"] == "proposed":
                    proposed_rev += d["amount"]
                elif d["status"] != "superseded":
                    contracted_rev += d["amount"]
            elif d["side"] == "cost":
                total_cost += d["amount"]
        out_docs.append(
            {
                "document": (doc.name if doc else str(did)),
                "doc_type": next((r.source_doc_type for r in drows), None),
                "revenue_total": round(rev_total, 2),
                "cost_total": round(cost_total, 2),
                "revenue_statuses": sorted(s for s in statuses if s),
                "is_summary_rollup": any(d["is_summary_rollup"] for d in doc_rows),
                "rows": doc_rows,
                "text_excerpt": texts.get(did, "")[:text_chars],
            }
        )
    # Biggest-revenue doc first -- the most likely restatement target.
    out_docs.sort(key=lambda d: d["revenue_total"], reverse=True)

    return {
        "project": project.name,
        "project_id": str(project.canonical_id),
        "n_docs": len(out_docs),
        "naive_contracted_revenue": round(contracted_rev, 2),
        "naive_proposed_revenue": round(proposed_rev, 2),
        "naive_total_cost": round(total_cost, 2),
        "docs": out_docs,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=".reconcile_bundles", help="output dir")
    ap.add_argument("--text-chars", type=int, default=2800, help="excerpt chars per doc")
    args = ap.parse_args()

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    index = []
    with session_scope() as s:
        for p in s.query(Project).order_by(Project.name).all():
            bundle = export_project(s, p, text_chars=args.text_chars)
            if bundle is None:
                continue
            safe = "".join(c if c.isalnum() else "_" for c in p.name)[:50]
            path = out_dir / f"{safe}.json"
            path.write_text(json.dumps(bundle, indent=2, default=str), encoding="utf-8")
            index.append(
                {
                    "project": bundle["project"],
                    "file": path.name,
                    "n_docs": bundle["n_docs"],
                    "naive_contracted_revenue": bundle["naive_contracted_revenue"],
                    "naive_total_cost": bundle["naive_total_cost"],
                }
            )
    (out_dir / "_index.json").write_text(json.dumps(index, indent=2), encoding="utf-8")
    print(f"Wrote {len(index)} project bundle(s) to {out_dir}/")
    for e in index:
        print(f"  {e['project'][:40]:40} docs={e['n_docs']:>2} "
              f"rev=${e['naive_contracted_revenue']:>12,.2f} cost=${e['naive_total_cost']:>11,.2f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
