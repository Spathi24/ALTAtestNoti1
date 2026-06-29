"""Slice 8: store cross-document reconciliation findings as ReconciliationIssue.

Advisory only -- like ``Proposal``, a human acknowledges/resolves/dismisses; nothing
here mutates the ledger. Two producers feed the same store:

  * a DETERMINISTIC detector (no LLM, no cost) that catches the cross-document
    double-count this whole refactor surfaced -- two documents in one project that
    sum to the SAME total, where one is a summary/rollup (a SOW restating its
    accepted quote). That is the $361k Rockland bug: ACCEPTED QUOTE $66,539.65 +
    its SOW $66,539.65 counted twice.
  * ``record_llm_finding`` maps a finding from the LLM cross-doc auditor
    (``scripts/reconcile_financials_llm.py``) into the same table.

``record_issue`` is idempotent on ``dedupe_key`` so re-runs update rather than
duplicate. Findings are stored ``status='open'``; surfacing/resolution is a human
step (reuses the ledger-health / Proposal review surface).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy.orm import Session

from project_db.db.models import (
    RECONCILIATION_ISSUE_TYPES,
    Document,
    FinancialLineItem,
    ReconciliationIssue,
)

# Two doc totals within this are "the same money" (cent-level extraction drift).
_DUP_ABS = Decimal("1.00")
_DUP_PCT = Decimal("0.005")


def record_issue(
    session: Session,
    *,
    project_id,
    issue_type: str,
    dedupe_key: str,
    severity: str = "medium",
    source: str = "deterministic",
    description: str | None = None,
    delta_amount: Decimal | None = None,
    currency: str | None = None,
    evidence: dict | None = None,
    prompt_version: str | None = None,
) -> ReconciliationIssue:
    """Upsert one reconciliation issue, keyed by ``dedupe_key`` (idempotent).

    A human's decision (status / decided_by / decided_at) is preserved across
    re-detection: an existing row's status is not reset to 'open'.
    """
    if issue_type not in RECONCILIATION_ISSUE_TYPES:
        issue_type = "other"
    existing = session.query(ReconciliationIssue).filter_by(dedupe_key=dedupe_key).one_or_none()
    payload = json.dumps(evidence, default=str) if evidence is not None else None
    if existing is not None:
        # Refresh the facts; leave the human's status/decision untouched.
        existing.issue_type = issue_type
        existing.severity = severity
        existing.source = source
        existing.description = description
        existing.delta_amount = delta_amount
        existing.currency = currency
        existing.evidence_json = payload
        existing.prompt_version = prompt_version
        session.flush()
        return existing
    issue = ReconciliationIssue(
        project_id=project_id,
        issue_type=issue_type,
        severity=severity,
        status="open",
        source=source,
        description=description,
        delta_amount=delta_amount,
        currency=currency,
        evidence_json=payload,
        dedupe_key=dedupe_key,
        prompt_version=prompt_version,
    )
    session.add(issue)
    session.flush()
    return issue


@dataclass
class _DocTotal:
    doc_id: str
    name: str
    total: Decimal
    is_rollup: bool
    currency: str | None


def _doc_totals(session: Session, project_id) -> list[_DocTotal]:
    """Per-document summed ledger total (revenue side) for one project."""
    rows = (
        session.query(FinancialLineItem)
        .filter(
            FinancialLineItem.project_id == project_id,
            FinancialLineItem.side == "revenue",
            FinancialLineItem.amount.isnot(None),
        )
        .all()
    )
    by_doc: dict = {}
    for r in rows:
        d = by_doc.setdefault(
            r.document_id,
            {"div_total": Decimal(0), "all": Decimal(0), "rollup": False, "currency": r.currency},
        )
        meta = {}
        if r.source_meta_json:
            try:
                meta = json.loads(r.source_meta_json)
            except (json.JSONDecodeError, TypeError):
                meta = {}
        if meta.get("is_summary_rollup"):
            d["rollup"] = True
        # The grid path emits BOTH a section `division_total` row AND its material/
        # labour component rows -- summing all double-counts the doc. When a doc has
        # section-total rows, those ARE the coherent doc total (the components sum
        # into them); otherwise (LLM / extras rows, already de-duped) sum all.
        d["all"] += r.amount
        if meta.get("kind") == "division_total":
            d["div_total"] += r.amount
    out: list[_DocTotal] = []
    for doc_id, agg in by_doc.items():
        doc = session.query(Document).filter_by(canonical_id=doc_id).one_or_none()
        total = agg["div_total"] if agg["div_total"] > 0 else agg["all"]
        out.append(
            _DocTotal(
                doc_id=str(doc_id),
                name=(doc.name if doc else "") or "",
                total=total,
                is_rollup=agg["rollup"],
                currency=agg["currency"],
            )
        )
    return out


def _same_money(a: Decimal, b: Decimal) -> bool:
    tol = max(_DUP_ABS, (abs(a) * _DUP_PCT))
    return abs(a - b) <= tol


def detect_duplicate_total_issues(session: Session, project_id) -> list[ReconciliationIssue]:
    """Flag document pairs whose revenue totals match -- likely the same money.

    A pair where one side is a summary/rollup is a ``rollup_double_count`` (high);
    otherwise ``duplicate_total`` (medium, "verify these aren't the same money").
    Deterministic, no LLM. Idempotent via a sorted-pair dedupe key.
    """
    totals = [t for t in _doc_totals(session, project_id) if t.total > 0]
    issues: list[ReconciliationIssue] = []
    for i in range(len(totals)):
        for j in range(i + 1, len(totals)):
            a, b = totals[i], totals[j]
            if not _same_money(a.total, b.total):
                continue
            rollup = a.is_rollup or b.is_rollup
            issue_type = "rollup_double_count" if rollup else "duplicate_total"
            severity = "high" if rollup else "medium"
            key = "dup:" + "|".join(sorted([a.doc_id, b.doc_id]))
            desc = (
                f"{a.name!r} and {b.name!r} both total ~{a.total} "
                f"({'one is a summary/rollup -> likely double-counted' if rollup else 'verify these are not the same money'})"
            )
            issues.append(
                record_issue(
                    session,
                    project_id=project_id,
                    issue_type=issue_type,
                    dedupe_key=key,
                    severity=severity,
                    description=desc,
                    delta_amount=a.total,
                    currency=a.currency or b.currency,
                    evidence={
                        "documents": [
                            {
                                "id": a.doc_id,
                                "name": a.name,
                                "total": str(a.total),
                                "rollup": a.is_rollup,
                            },
                            {
                                "id": b.doc_id,
                                "name": b.name,
                                "total": str(b.total),
                                "rollup": b.is_rollup,
                            },
                        ]
                    },
                )
            )
    return issues


def record_llm_finding(
    session: Session,
    *,
    project_id,
    finding: dict,
    prompt_version: str | None = None,
) -> ReconciliationIssue:
    """Map one LLM cross-doc auditor finding (flag_type/severity/...) into the store."""
    flag_type = (finding.get("flag_type") or finding.get("issue_type") or "other").strip()
    issue_type = flag_type if flag_type in RECONCILIATION_ISSUE_TYPES else "other"
    sev = (finding.get("severity") or "medium").strip().lower()
    if sev not in {"high", "medium", "low"}:
        sev = "medium"
    delta = finding.get("amount") or finding.get("delta")
    try:
        delta_amount = Decimal(str(delta)) if delta is not None else None
    except (ValueError, ArithmeticError):
        delta_amount = None
    key = "llm:" + (
        finding.get("dedupe_key") or json.dumps(finding, sort_keys=True, default=str)[:200]
    )
    return record_issue(
        session,
        project_id=project_id,
        issue_type=issue_type,
        dedupe_key=key,
        severity=sev,
        source="llm",
        description=finding.get("description") or finding.get("explanation"),
        delta_amount=delta_amount,
        evidence=finding,
        prompt_version=prompt_version,
    )
