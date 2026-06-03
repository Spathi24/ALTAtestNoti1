"""Tests for the attention-briefing detector (``report_attention_briefing``).

The briefing is the deterministic "Monday-morning risk-and-money" surface: it
composes already-stored money / scope / schedule / document signals into one
ranked list of cross-system truths.  No LLM is involved, so every assertion
here is exact.

Detectors covered:
  - schedule: overdue tasks (medium/high thresholds, done/cancelled/future excl.)
  - scope:    pending scope_gap proposals (accepted + timeline excluded)
  - money:    low-confidence reconciliation, confirmed-loss (B) with buyout
              guard, unconfirmed-quote pile (C)
  - documents: active/proposed project with no contract-shaped doc
  - ranking, capping, counts-over-all-items, JSON-serializability
  - the ``project_db briefing`` CLI renderer
"""
from __future__ import annotations

import argparse
import json
from datetime import date, timedelta
from decimal import Decimal

import pytest
from sqlalchemy.orm import sessionmaker

from project_db.ai.views import report_attention_briefing
from project_db.db.models import (
    Document,
    FinancialRecord,
    Project,
    Proposal,
    ProposalStatus,
)
from project_db.db.models.work import ProjectStatus, TaskStatus

# A fixed "today" so overdue arithmetic is deterministic.
TODAY = date(2026, 6, 3)


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _items(report, *, category=None, project_id=None, severity=None):
    out = report["items"]
    if category is not None:
        out = [i for i in out if i["category"] == category]
    if severity is not None:
        out = [i for i in out if i["severity"] == severity]
    if project_id is not None:
        out = [i for i in out if i["project_id"] == str(project_id)]
    return out


def _add_financial_doc(session, project, *, name, direction, amount,
                       doc_role, record_kind="total", is_rollup=False):
    """Create a contract-shaped Document + one FinancialRecord on it."""
    doc = Document(name=name, url=f"x://{name}", mime_type="application/pdf",
                   project_id=project.canonical_id)
    session.add(doc)
    session.flush()
    session.add(FinancialRecord(
        project_id=project.canonical_id, document_id=doc.canonical_id,
        direction=direction, record_kind=record_kind, amount=Decimal(str(amount)),
        is_rollup=is_rollup, doc_role=doc_role, amount_verified=True,
    ))
    session.flush()
    return doc


def _add_scope_proposal(session, project, *, status=ProposalStatus.PENDING,
                        field_name="scope_gap"):
    p = Proposal(
        entity_type="Project", entity_id=project.canonical_id,
        field_name=field_name, proposed_value='{"scope_item": "x"}',
        confidence=0.8, status=status,
    )
    session.add(p)
    session.flush()
    return p


# ---------------------------------------------------------------------------
# empty / shape
# ---------------------------------------------------------------------------


class TestEmptyAndShape:
    def test_empty_db_returns_no_items(self, session):
        rep = report_attention_briefing(session, today=TODAY)
        assert rep["item_count"] == 0
        assert rep["items"] == []
        assert rep["by_category"] == {}
        assert rep["by_severity"] == {}
        assert rep["project_count"] == 0
        assert rep["truncated"] is False
        assert rep["generated_on"] == TODAY.isoformat()

    def test_result_is_json_serializable(self, session, project_factory, task_factory):
        p = project_factory(name="JSON Proj")
        task_factory(project=p, title="late", status=TaskStatus.TODO,
                     due_date=TODAY - timedelta(days=10))
        rep = report_attention_briefing(session, today=TODAY)
        # Must not raise.
        json.dumps(rep)


# ---------------------------------------------------------------------------
# schedule detector
# ---------------------------------------------------------------------------


class TestScheduleDetector:
    def test_overdue_task_flagged_medium(self, session, project_factory, task_factory):
        p = project_factory(name="Sched Proj")
        task_factory(project=p, title="Hang doors", status=TaskStatus.TODO,
                     due_date=TODAY - timedelta(days=10))
        sched = _items(report_attention_briefing(session, today=TODAY),
                       category="schedule", project_id=p.canonical_id)
        assert len(sched) == 1
        assert sched[0]["severity"] == "medium"
        assert "1 task(s) overdue" in sched[0]["headline"]
        assert "2026-05-24" in sched[0]["detail"]  # 10 days before TODAY

    def test_many_overdue_is_high(self, session, project_factory, task_factory):
        p = project_factory(name="Busy Proj")
        for i in range(5):
            task_factory(project=p, title=f"t{i}", status=TaskStatus.TODO,
                         due_date=TODAY - timedelta(days=3))
        sched = _items(report_attention_briefing(session, today=TODAY),
                       category="schedule", project_id=p.canonical_id)
        assert sched[0]["severity"] == "high"
        assert "5 task(s) overdue" in sched[0]["headline"]

    def test_far_overdue_is_high(self, session, project_factory, task_factory):
        p = project_factory(name="Stale Proj")
        task_factory(project=p, title="forgotten", status=TaskStatus.IN_PROGRESS,
                     due_date=TODAY - timedelta(days=40))
        sched = _items(report_attention_briefing(session, today=TODAY),
                       category="schedule", project_id=p.canonical_id)
        assert sched[0]["severity"] == "high"

    def test_done_and_cancelled_not_counted(self, session, project_factory, task_factory):
        p = project_factory(name="Closed Proj")
        task_factory(project=p, title="done", status=TaskStatus.DONE,
                     due_date=TODAY - timedelta(days=10))
        task_factory(project=p, title="cancelled", status=TaskStatus.CANCELLED,
                     due_date=TODAY - timedelta(days=10))
        sched = _items(report_attention_briefing(session, today=TODAY),
                       category="schedule", project_id=p.canonical_id)
        assert sched == []

    def test_future_due_not_counted(self, session, project_factory, task_factory):
        p = project_factory(name="Future Proj")
        task_factory(project=p, title="upcoming", status=TaskStatus.TODO,
                     due_date=TODAY + timedelta(days=5))
        sched = _items(report_attention_briefing(session, today=TODAY),
                       category="schedule", project_id=p.canonical_id)
        assert sched == []

    def test_dateless_task_not_counted(self, session, project_factory, task_factory):
        p = project_factory(name="Dateless Proj")
        task_factory(project=p, title="no dates", status=TaskStatus.TODO,
                     due_date=None)
        sched = _items(report_attention_briefing(session, today=TODAY),
                       category="schedule", project_id=p.canonical_id)
        assert sched == []


# ---------------------------------------------------------------------------
# scope detector
# ---------------------------------------------------------------------------


class TestScopeDetector:
    def test_pending_scope_gaps_flagged(self, session, project_factory):
        p = project_factory(name="Scope Proj")
        for _ in range(3):
            _add_scope_proposal(session, p)
        session.commit()
        scope = _items(report_attention_briefing(session, today=TODAY),
                       category="scope", project_id=p.canonical_id)
        assert len(scope) == 1
        assert scope[0]["severity"] == "medium"
        assert scope[0]["weight"] == 3.0
        assert "3 contract scope item(s)" in scope[0]["headline"]

    def test_accepted_scope_gap_not_counted(self, session, project_factory):
        p = project_factory(name="Accepted Proj")
        _add_scope_proposal(session, p, status=ProposalStatus.ACCEPTED)
        session.commit()
        scope = _items(report_attention_briefing(session, today=TODAY),
                       category="scope", project_id=p.canonical_id)
        assert scope == []

    def test_timeline_proposal_not_counted_as_scope(self, session, project_factory):
        p = project_factory(name="Timeline Proj")
        _add_scope_proposal(session, p, field_name="timeline")
        session.commit()
        scope = _items(report_attention_briefing(session, today=TODAY),
                       category="scope", project_id=p.canonical_id)
        assert scope == []


# ---------------------------------------------------------------------------
# money detectors
# ---------------------------------------------------------------------------


class TestMoneyDetectors:
    def test_low_confidence_flagged_medium(self, session, project_factory):
        p = project_factory(name="Murky Proj")
        # A single unknown-direction "other" record -> 0% classified -> low conf.
        _add_financial_doc(session, p, name="Mystery.pdf", direction="unknown",
                           amount=50000, doc_role="other", record_kind="other")
        session.commit()
        money = _items(report_attention_briefing(session, today=TODAY),
                       category="money", project_id=p.canonical_id)
        assert len(money) == 1
        assert money[0]["severity"] == "medium"
        assert "low-confidence" in money[0]["headline"]

    def test_confirmed_loss_flagged_high(self, session, project_factory):
        p = project_factory(name="Bleeding Proj")
        # Both invoices -> confirmed by default.  cost (150k) > revenue (100k).
        _add_financial_doc(session, p, name="Client Invoice.pdf",
                           direction="client_in", amount=100000, doc_role="invoice")
        _add_financial_doc(session, p, name="Sub Invoice.pdf",
                           direction="contractor_out", amount=150000, doc_role="invoice")
        session.commit()
        money = _items(report_attention_briefing(session, today=TODAY),
                       category="money", project_id=p.canonical_id)
        highs = [m for m in money if m["severity"] == "high"]
        assert len(highs) == 1
        assert "exceed confirmed revenue" in highs[0]["headline"]
        assert highs[0]["weight"] == pytest.approx(50000.0)

    def test_buyout_guard_no_false_loss(self, session, project_factory):
        """Confirmed cost with NO revenue must NOT be flagged a loss."""
        p = project_factory(name="Buyout Proj")
        _add_financial_doc(session, p, name="Sub Invoice.pdf",
                           direction="contractor_out", amount=150000, doc_role="invoice")
        session.commit()
        money = _items(report_attention_briefing(session, today=TODAY),
                       category="money", project_id=p.canonical_id)
        assert [m for m in money if m["severity"] == "high"] == []

    def test_unconfirmed_quote_pile_flagged_low(self, session, project_factory):
        p = project_factory(name="Quote Pile Proj")
        # Two unconfirmed client quotes, 15k each -> 30k pile across 2 docs.
        _add_financial_doc(session, p, name="Quote A.pdf",
                           direction="client_in", amount=15000, doc_role="quote")
        _add_financial_doc(session, p, name="Quote B.pdf",
                           direction="client_in", amount=15000, doc_role="quote")
        session.commit()
        money = _items(report_attention_briefing(session, today=TODAY),
                       category="money", project_id=p.canonical_id)
        lows = [m for m in money if m["severity"] == "low"]
        assert len(lows) == 1
        assert "unconfirmed quotes" in lows[0]["headline"]
        assert lows[0]["weight"] == pytest.approx(30000.0)

    def test_small_unconfirmed_pile_not_flagged(self, session, project_factory):
        """Below the $20k floor -> no nag."""
        p = project_factory(name="Tiny Proj")
        _add_financial_doc(session, p, name="Quote A.pdf",
                           direction="client_in", amount=500, doc_role="quote")
        _add_financial_doc(session, p, name="Quote B.pdf",
                           direction="client_in", amount=500, doc_role="quote")
        session.commit()
        money = _items(report_attention_briefing(session, today=TODAY),
                       category="money", project_id=p.canonical_id, severity="low")
        assert money == []

    def test_project_without_financials_has_no_money_item(
        self, session, project_factory
    ):
        p = project_factory(name="No Money Proj")
        money = _items(report_attention_briefing(session, today=TODAY),
                       category="money", project_id=p.canonical_id)
        assert money == []


# ---------------------------------------------------------------------------
# documents detector
# ---------------------------------------------------------------------------


class TestDocumentsDetector:
    def test_active_project_missing_contract_doc_is_medium(
        self, session, project_factory
    ):
        p = project_factory(name="No Contract Proj", status=ProjectStatus.ACTIVE)
        docs = _items(report_attention_briefing(session, today=TODAY),
                      category="documents", project_id=p.canonical_id)
        assert len(docs) == 1
        assert docs[0]["severity"] == "medium"
        assert "no contract document" in docs[0]["headline"]

    def test_proposed_project_missing_contract_doc_is_low(
        self, session, project_factory
    ):
        p = project_factory(name="Proposed Proj", status=ProjectStatus.PROPOSED)
        docs = _items(report_attention_briefing(session, today=TODAY),
                      category="documents", project_id=p.canonical_id)
        assert len(docs) == 1
        assert docs[0]["severity"] == "low"

    def test_project_with_contract_doc_not_flagged(self, session, project_factory):
        p = project_factory(name="Has Contract Proj", status=ProjectStatus.ACTIVE)
        d = Document(name="Contract.pdf", url="x://c", mime_type="application/pdf",
                     project_id=p.canonical_id)
        session.add(d)
        session.commit()
        docs = _items(report_attention_briefing(session, today=TODAY),
                      category="documents", project_id=p.canonical_id)
        assert docs == []


# ---------------------------------------------------------------------------
# ranking / capping / counts
# ---------------------------------------------------------------------------


class TestRankingAndCap:
    def test_high_ranks_above_low(self, session, project_factory, task_factory):
        high_p = project_factory(name="High Proj")
        for i in range(5):  # 5 overdue -> high
            task_factory(project=high_p, title=f"t{i}", status=TaskStatus.TODO,
                         due_date=TODAY - timedelta(days=2))
        low_p = project_factory(name="Low Proj")
        _add_financial_doc(session, low_p, name="Quote A.pdf",
                           direction="client_in", amount=15000, doc_role="quote")
        _add_financial_doc(session, low_p, name="Quote B.pdf",
                           direction="client_in", amount=15000, doc_role="quote")
        session.commit()

        rep = report_attention_briefing(session, today=TODAY)
        sev_ranks = [it["severity_rank"] for it in rep["items"]]
        # Non-increasing severity rank across the whole ordered list.
        assert sev_ranks == sorted(sev_ranks, reverse=True)
        # The high schedule item precedes the low money item.
        high_idx = next(i for i, it in enumerate(rep["items"])
                        if it["category"] == "schedule")
        low_idx = next(i for i, it in enumerate(rep["items"])
                       if it["severity"] == "low")
        assert high_idx < low_idx

    def test_weight_orders_within_severity(self, session, project_factory, task_factory):
        small = project_factory(name="AAA Small")
        task_factory(project=small, title="x", status=TaskStatus.TODO,
                     due_date=TODAY - timedelta(days=2))  # medium, weight 100+1
        big = project_factory(name="ZZZ Big")
        for i in range(3):  # medium (3<5, days<30), weight 300+2
            task_factory(project=big, title=f"y{i}", status=TaskStatus.TODO,
                         due_date=TODAY - timedelta(days=2))
        rep = report_attention_briefing(session, today=TODAY)
        sched = _items(rep, category="schedule")
        # Bigger weight first despite alphabetical name coming later.
        assert sched[0]["project_name"] == "ZZZ Big"

    def test_limit_caps_and_marks_truncated(self, session, project_factory, task_factory):
        for n in range(4):
            pr = project_factory(name=f"Proj {n}")
            task_factory(project=pr, title="late", status=TaskStatus.TODO,
                         due_date=TODAY - timedelta(days=5))
        rep = report_attention_briefing(session, today=TODAY, limit=2)
        assert rep["shown_count"] == 2
        assert len(rep["items"]) == 2
        assert rep["item_count"] >= 4
        assert rep["truncated"] is True

    def test_counts_describe_all_items_not_just_shown(
        self, session, project_factory, task_factory
    ):
        for n in range(4):
            pr = project_factory(name=f"P{n}")
            task_factory(project=pr, title="late", status=TaskStatus.TODO,
                         due_date=TODAY - timedelta(days=5))
        rep = report_attention_briefing(session, today=TODAY, limit=1)
        assert sum(rep["by_severity"].values()) == rep["item_count"]
        assert sum(rep["by_category"].values()) == rep["item_count"]
        assert rep["item_count"] > rep["shown_count"]


# ---------------------------------------------------------------------------
# CLI renderer
# ---------------------------------------------------------------------------


@pytest.fixture
def patched_session_factory(db_engine, monkeypatch):
    """Bind session_scope() to the test engine for CLI tests that hit the DB."""
    from project_db.db import session as session_mod

    factory = sessionmaker(bind=db_engine, expire_on_commit=False)
    monkeypatch.setattr(session_mod, "_SessionLocal", factory)
    yield factory


class TestBriefingCli:
    def test_empty_prints_nothing_needs_attention(
        self, session, patched_session_factory, capsys
    ):
        from project_db.cli import cmd_briefing

        rc = cmd_briefing(argparse.Namespace(limit=25))
        assert rc == 0
        assert "Nothing needs attention" in capsys.readouterr().out

    def test_renders_overdue_item(
        self, session, patched_session_factory, project_factory, task_factory, capsys
    ):
        from project_db.cli import cmd_briefing

        p = project_factory(name="CLI Proj")
        # Relative to real today (the CLI uses date.today()).
        task_factory(project=p, title="late thing", status=TaskStatus.TODO,
                     due_date=date.today() - timedelta(days=10))

        rc = cmd_briefing(argparse.Namespace(limit=25))
        out = capsys.readouterr().out
        assert rc == 0
        assert "ATTENTION BRIEFING" in out
        assert "overdue" in out
