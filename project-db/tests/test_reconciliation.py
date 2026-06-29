"""Slice 8: ReconciliationIssue storage + deterministic cross-doc detector.

Catches the cross-document double-count (a SOW restating its accepted quote) that
inflated Rockland's revenue. Advisory only -- stored for human review.
"""

from __future__ import annotations

import json
from decimal import Decimal

from project_db.ai.reconciliation import (
    detect_duplicate_total_issues,
    record_issue,
    record_llm_finding,
)
from project_db.db.models import Document, ReconciliationIssue
from project_db.db.models.finance import FinancialLineItem


def _doc(session, project, name):
    d = Document(
        name=name,
        url=f"https://drive/{name}",
        mime_type="text/csv",
        project_id=project.canonical_id,
    )
    session.add(d)
    session.commit()
    return d


def _line(session, project, doc, amount, *, rollup=False):
    session.add(
        FinancialLineItem(
            project_id=project.canonical_id,
            document_id=doc.canonical_id,
            side="revenue",
            amount=Decimal(str(amount)),
            currency="CAD",
            source="llm",
            source_meta_json=json.dumps({"is_summary_rollup": rollup}),
        )
    )
    session.commit()


def test_record_issue_is_idempotent_and_preserves_human_status(session, project_factory):
    proj = project_factory(name="P")
    a = record_issue(
        session,
        project_id=proj.canonical_id,
        issue_type="duplicate_total",
        dedupe_key="k1",
        description="first",
    )
    a.status = "dismissed"  # a human acted on it
    a.decided_by = "owner"
    session.commit()

    # Re-detect the same finding -> updates facts, keeps the human's decision.
    b = record_issue(
        session,
        project_id=proj.canonical_id,
        issue_type="duplicate_total",
        dedupe_key="k1",
        description="updated",
    )
    session.commit()
    assert a.canonical_id == b.canonical_id
    assert session.query(ReconciliationIssue).count() == 1
    assert b.description == "updated"
    assert b.status == "dismissed"  # not reset to 'open'


def test_detects_rollup_double_count(session, project_factory):
    proj = project_factory(name="Rockland-like")
    quote = _doc(session, proj, "ACCEPTED QUOTE")
    sow = _doc(session, proj, "SOW 923")
    _line(session, proj, quote, "66539.65")
    _line(session, proj, sow, "66539.65", rollup=True)  # SOW restates the quote

    issues = detect_duplicate_total_issues(session, proj.canonical_id)
    session.commit()
    assert len(issues) == 1
    assert issues[0].issue_type == "rollup_double_count"
    assert issues[0].severity == "high"
    assert issues[0].delta_amount == Decimal("66539.65")
    ev = json.loads(issues[0].evidence_json)
    assert {d["name"] for d in ev["documents"]} == {"ACCEPTED QUOTE", "SOW 923"}


def test_equal_totals_without_rollup_are_medium_duplicate(session, project_factory):
    proj = project_factory(name="P")
    a = _doc(session, proj, "Quote A")
    b = _doc(session, proj, "Quote B")
    _line(session, proj, a, "5000.00")
    _line(session, proj, b, "5000.00")

    issues = detect_duplicate_total_issues(session, proj.canonical_id)
    assert len(issues) == 1
    assert issues[0].issue_type == "duplicate_total"
    assert issues[0].severity == "medium"


def test_distinct_totals_produce_no_issue(session, project_factory):
    proj = project_factory(name="P")
    a = _doc(session, proj, "Quote A")
    b = _doc(session, proj, "Quote B")
    _line(session, proj, a, "5000.00")
    _line(session, proj, b, "191843.68")

    assert detect_duplicate_total_issues(session, proj.canonical_id) == []


def test_detect_is_idempotent(session, project_factory):
    proj = project_factory(name="P")
    a = _doc(session, proj, "Quote A")
    b = _doc(session, proj, "Quote B")
    _line(session, proj, a, "5000.00")
    _line(session, proj, b, "5000.00")

    detect_duplicate_total_issues(session, proj.canonical_id)
    detect_duplicate_total_issues(session, proj.canonical_id)  # second run
    session.commit()
    assert session.query(ReconciliationIssue).count() == 1


def _grid_line(session, project, doc, amount, *, kind, amount_type):
    session.add(
        FinancialLineItem(
            project_id=project.canonical_id,
            document_id=doc.canonical_id,
            side="revenue",
            amount=Decimal(str(amount)),
            currency="CAD",
            source="grid",
            amount_type=amount_type,
            source_meta_json=json.dumps({"kind": kind}),
        )
    )
    session.commit()


def test_grid_double_structure_uses_section_totals_not_raw_sum(session, project_factory):
    """A grid doc emits section totals AND their material/labour components; the
    coherent doc total is the section totals, not the (double-counted) raw sum."""
    proj = project_factory(name="P")
    grid = _doc(session, proj, "ACCEPTED QUOTE")
    # Section total $1000 = its $400 material + $600 labour components.
    _grid_line(session, proj, grid, "1000.00", kind="division_total", amount_type="total")
    _grid_line(session, proj, grid, "400.00", kind="line_item", amount_type="material")
    _grid_line(session, proj, grid, "600.00", kind="line_item", amount_type="labour")
    # Another doc (the SOW) restates the same $1000.
    sow = _doc(session, proj, "SOW")
    _line(session, proj, sow, "1000.00", rollup=True)

    issues = detect_duplicate_total_issues(session, proj.canonical_id)
    # Raw sum of the grid doc would be $2000 (double-counted) and would NOT match;
    # the section-total logic makes it $1000 -> matches the SOW -> caught.
    assert len(issues) == 1
    assert issues[0].issue_type == "rollup_double_count"
    assert issues[0].delta_amount == Decimal("1000.00")


def test_record_llm_finding_maps_fields(session, project_factory):
    proj = project_factory(name="P")
    issue = record_llm_finding(
        session,
        project_id=proj.canonical_id,
        finding={
            "flag_type": "side_error",
            "severity": "high",
            "amount": 123456.78,
            "description": "vendor-billed doc sided as revenue",
            "dedupe_key": "doc-42",
        },
        prompt_version="recon-v1",
    )
    session.commit()
    assert issue.issue_type == "side_error"
    assert issue.severity == "high"
    assert issue.source == "llm"
    assert issue.delta_amount == Decimal("123456.78")
    assert issue.prompt_version == "recon-v1"
