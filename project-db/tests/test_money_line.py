"""Tests for the plain-English money one-liner (INTENTIONS #3).

Deterministic, offline -- builds FinancialRecord / ContractObligation rows
directly (no LLM) and asserts the rendered sentence.
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

from project_db.ai.views import _money_short, report_project_money_line
from project_db.db.models import ContractObligation, Document, FinancialRecord


def _doc(session, project, name="Quote.pdf"):
    d = Document(
        name=name, url=f"x://{name}", mime_type="application/pdf", project_id=project.canonical_id
    )
    session.add(d)
    session.flush()
    return d


class TestMoneyShort:
    def test_compact_formatting(self):
        assert _money_short(402) == "$402"
        assert _money_short(52000) == "$52k"
        assert _money_short(76500) == "$76.5k"
        assert _money_short(1200000) == "$1.2M"
        assert _money_short(-250) == "-$250"
        assert _money_short(None) == "$0"


class TestMoneyLine:
    def test_no_records(self, session, project_factory):
        p = project_factory(name="Empty Proj")
        out = report_project_money_line(session, str(p.canonical_id))
        assert out["has_records"] is False
        assert "no financial records" in out["line"]

    def test_clean_renovation_confirmed(self, session, project_factory):
        """When client revenue is CONFIRMED (invoice-role docs default confirmed),
        the one-liner shows a real margin agreeing with the Financials panel."""
        p = project_factory(name="1455 Reno")
        da = _doc(session, p, "Client Invoice.pdf")
        db_ = _doc(session, p, "Supplier Invoice.pdf")
        session.add_all(
            [
                FinancialRecord(
                    project_id=p.canonical_id,
                    document_id=da.canonical_id,
                    direction="client_in",
                    record_kind="total",
                    doc_role="invoice",
                    amount=Decimal("80000"),
                    is_rollup=False,
                ),
                FinancialRecord(
                    project_id=p.canonical_id,
                    document_id=db_.canonical_id,
                    direction="contractor_out",
                    record_kind="total",
                    doc_role="invoice",
                    amount=Decimal("52000"),
                    is_rollup=False,
                ),
            ]
        )
        session.commit()
        out = report_project_money_line(session, str(p.canonical_id))
        assert out["has_records"] is True
        assert out["low_confidence"] is False
        assert "revenue $80k" in out["line"]
        assert "costs $52k" in out["line"]
        assert "margin ~$28k" in out["line"]
        assert "(confirmed)" in out["line"]

    def test_unconfirmed_revenue_is_flagged_not_a_fake_margin(self, session, project_factory):
        """Client side is just quotes (not confirmed): don't print a misleading
        margin -- lead with known costs and flag revenue as unconfirmed quotes."""
        p = project_factory(name="Quotes Only")
        da = _doc(session, p, "Soumission.pdf")
        db_ = _doc(session, p, "Supplier Invoice.pdf")
        session.add_all(
            [
                FinancialRecord(
                    project_id=p.canonical_id,
                    document_id=da.canonical_id,
                    direction="client_in",
                    record_kind="total",
                    doc_role="quote",
                    amount=Decimal("90000"),
                    is_rollup=False,
                ),
                FinancialRecord(
                    project_id=p.canonical_id,
                    document_id=db_.canonical_id,
                    direction="contractor_out",
                    record_kind="total",
                    doc_role="invoice",
                    amount=Decimal("40000"),
                    is_rollup=False,
                ),
            ]
        )
        session.commit()
        out = report_project_money_line(session, str(p.canonical_id))
        assert "not yet confirmed" in out["line"]
        assert "quoted on file" in out["line"]
        assert "margin ~" not in out["line"]  # no confident-but-wrong margin

    def test_low_confidence_says_so(self, session, project_factory):
        p = project_factory(name="6554 Dev")
        d = _doc(session, p)
        session.add_all(
            [
                FinancialRecord(
                    project_id=p.canonical_id,
                    document_id=d.canonical_id,
                    direction="unknown",
                    record_kind="total",
                    amount=Decimal("1000000"),
                    is_rollup=False,
                ),
                FinancialRecord(
                    project_id=p.canonical_id,
                    document_id=d.canonical_id,
                    direction="contractor_out",
                    record_kind="total",
                    amount=Decimal("100"),
                    is_rollup=False,
                ),
            ]
        )
        session.commit()
        out = report_project_money_line(session, str(p.canonical_id))
        assert out["low_confidence"] is True
        assert "LOW CONFIDENCE" in out["line"]
        # no confident margin printed for an unmodeled project type
        assert "margin ~" not in out["line"]

    def test_overdue_obligation_tail(self, session, project_factory):
        p = project_factory(name="With Oblig")
        d = _doc(session, p)
        session.add(
            FinancialRecord(
                project_id=p.canonical_id,
                document_id=d.canonical_id,
                direction="client_in",
                record_kind="total",
                amount=Decimal("10000"),
                is_rollup=False,
            )
        )
        session.add(
            ContractObligation(
                project_id=p.canonical_id,
                kind="payment_milestone",
                direction="owed_to_us",
                amount=Decimal("3000"),
                due_date=date.today() - timedelta(days=5),
            )
        )
        session.commit()
        out = report_project_money_line(session, str(p.canonical_id))
        assert "overdue" in out["line"]
        assert "to collect" in out["line"]

    def test_bad_ref_errors(self, session):
        assert report_project_money_line(session, "no-such-project").get("error")
