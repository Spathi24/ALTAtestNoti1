"""Tests for the value-caught ROI tally (ai/views.report_value_caught).

Deterministic, offline -- builds ContractObligation rows directly (no LLM) and
asserts the portfolio aggregation. Mirrors test_obligations.py's _oblig helper.
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

from project_db.ai.views import report_value_caught
from project_db.db.models import ContractObligation

TODAY = date(2026, 6, 9)


def _oblig(session, project, **kw):
    defaults = {
        "project_id": project.canonical_id,
        "kind": "payment_milestone",
        "direction": "owed_to_us",
    }
    defaults.update(kw)
    o = ContractObligation(**defaults)
    session.add(o)
    session.flush()
    return o


class TestValueCaught:
    def test_aggregates_overdue_buckets(self, session, project_factory):
        p = project_factory(name="Proj A")
        _oblig(
            session,
            p,
            direction="owed_to_us",
            amount=Decimal("10000"),
            due_date=TODAY - timedelta(days=5),
        )  # receivable overdue
        _oblig(
            session,
            p,
            direction="owed_by_us",
            kind="penalty",
            amount=Decimal("2000"),
            due_date=TODAY - timedelta(days=2),
        )  # we owe overdue
        _oblig(
            session,
            p,
            direction="owed_to_us",
            kind="deposit",
            amount=Decimal("500"),
            due_date=TODAY + timedelta(days=10),
        )  # due soon
        _oblig(
            session,
            p,
            direction="owed_to_us",
            amount=Decimal("9999"),
            due_date=TODAY + timedelta(days=90),
        )  # upcoming -> excluded
        session.commit()

        rep = report_value_caught(session, today=TODAY)
        assert rep["money"]["receivables_overdue"] == 10000.0
        assert rep["money"]["obligations_overdue"] == 2000.0
        assert rep["money"]["receivables_due_soon"] == 500.0
        # headline = overdue receivable + overdue obligation (NOT due-soon/upcoming)
        assert rep["headline_total"] == 12000.0
        assert rep["flagged_project_count"] == 1
        assert rep["projects"][0]["project_name"] == "Proj A"

    def test_sums_across_projects_and_ranks(self, session, project_factory):
        big = project_factory(name="Big")
        small = project_factory(name="Small")
        _oblig(
            session,
            big,
            direction="owed_to_us",
            amount=Decimal("50000"),
            due_date=TODAY - timedelta(days=1),
        )
        _oblig(
            session,
            small,
            direction="owed_to_us",
            amount=Decimal("1000"),
            due_date=TODAY - timedelta(days=1),
        )
        session.commit()

        rep = report_value_caught(session, today=TODAY)
        assert rep["headline_total"] == 51000.0
        assert rep["flagged_project_count"] == 2
        # ranked by exposure desc
        assert [p["project_name"] for p in rep["projects"]] == ["Big", "Small"]

    def test_null_amount_overdue_contributes_zero_and_no_flag(self, session, project_factory):
        """A dateless/past obligation with no dollar value adds nothing to the
        dollar scoreboard and does not show as a $0 project."""
        p = project_factory(name="Permit Proj")
        _oblig(
            session,
            p,
            direction="owed_by_us",
            kind="permit_deadline",
            amount=None,
            due_date=TODAY - timedelta(days=3),
        )
        session.commit()

        rep = report_value_caught(session, today=TODAY)
        assert rep["headline_total"] == 0.0
        assert rep["flagged_project_count"] == 0
        assert rep["projects"] == []
        # the obligation is still counted in the status tally
        assert rep["obligation_count"] == 1
        assert rep["status_counts"].get("overdue") == 1

    def test_conditional_not_counted(self, session, project_factory):
        """A triggered settlement with no date (conditional) is real money but
        not yet 'past due to collect' / overdue -- excluded from the tally."""
        p = project_factory(name="Buyout")
        _oblig(
            session,
            p,
            direction="owed_by_us",
            kind="settlement",
            amount=Decimal("8000"),
            trigger="on key return",
        )
        session.commit()

        rep = report_value_caught(session, today=TODAY)
        assert rep["headline_total"] == 0.0
        assert rep["status_counts"].get("conditional") == 1

    def test_empty_portfolio_has_note(self, session):
        rep = report_value_caught(session, today=TODAY)
        assert rep["headline_total"] == 0.0
        assert rep["flagged_project_count"] == 0
        assert rep["note"]
