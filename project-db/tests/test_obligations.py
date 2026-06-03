"""Tests for contract-obligation extraction (ai/obligations.py).

All offline -- MockLLMProvider returns canned JSON; no live API. Mirrors the
financial-extraction tests: validate/coerce, amount verification, doc
attribution, skip-rules, and the all-or-nothing snapshot.
"""
from __future__ import annotations

import json
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import create_engine, inspect, text

from project_db.ai.obligations import extract_obligations_for_project
from project_db.ai.views import report_attention_briefing, report_commitments
from project_db.ai.providers import LLMProviderError
from project_db.ai.providers.mock import MockLLMProvider
from project_db.db.base import Base
from project_db.db.migrations import ensure_sqlite_schema
from project_db.db.models import ContractObligation, Document
from project_db.db.models.docs import DocumentText


def _contract_doc(session, project, *, name, body):
    d = Document(name=name, url=f"x://{name}", mime_type="application/pdf",
                 project_id=project.canonical_id)
    session.add(d)
    session.flush()
    session.add(DocumentText(document_id=d.canonical_id, extracted_text=body,
                             extraction_method="test"))
    session.flush()
    return d


def _mock(obligations):
    return MockLLMProvider(responses=[json.dumps({"obligations": obligations})])


TODAY = date(2026, 6, 3)


def _oblig(session, project, **kw):
    defaults = dict(project_id=project.canonical_id, kind="payment_milestone",
                    direction="owed_to_us")
    defaults.update(kw)
    o = ContractObligation(**defaults)
    session.add(o)
    session.flush()
    return o


class TestCommitmentsReport:
    def test_status_and_money_at_risk(self, session, project_factory):
        p = project_factory(name="Commit Proj")
        _oblig(session, p, direction="owed_to_us", amount=Decimal("10000"),
               due_date=TODAY - timedelta(days=5))                 # overdue
        _oblig(session, p, kind="penalty", direction="owed_by_us",
               amount=Decimal("500"), due_date=TODAY + timedelta(days=10))  # due_soon
        _oblig(session, p, kind="settlement", direction="owed_to_us",
               amount=Decimal("8000"), trigger="on key return")    # conditional
        _oblig(session, p, kind="deposit", direction="owed_to_us",
               amount=Decimal("2000"), due_date=TODAY + timedelta(days=90))  # upcoming
        session.commit()

        rep = report_commitments(session, str(p.canonical_id), today=TODAY)
        assert rep["obligation_count"] == 4
        assert rep["counts"]["overdue"] == 1
        assert rep["counts"]["due_soon"] == 1
        assert rep["counts"]["conditional"] == 1
        assert rep["money_at_risk"]["owed_to_us_overdue"] == 10000.0
        assert rep["money_at_risk"]["owed_to_us_total"] == 20000.0
        assert rep["money_at_risk"]["owed_by_us_total"] == 500.0
        assert rep["obligations"][0]["status"] == "overdue"        # most urgent first

    def test_error_on_bad_ref(self, session):
        assert report_commitments(session, "no-such-project").get("error")

    def test_empty_project_has_note(self, session, project_factory):
        p = project_factory(name="No Oblig Proj")
        rep = report_commitments(session, str(p.canonical_id), today=TODAY)
        assert rep["obligation_count"] == 0 and rep["note"]


class TestBriefingCommitments:
    def test_overdue_receivable_surfaces_high(self, session, project_factory):
        p = project_factory(name="AtRisk Proj")
        _oblig(session, p, direction="owed_to_us", amount=Decimal("12000"),
               due_date=TODAY - timedelta(days=3), description="final payment")
        session.commit()
        items = [
            i for i in report_attention_briefing(session, today=TODAY)["items"]
            if i["category"] == "commitments" and i["project_id"] == str(p.canonical_id)
        ]
        assert items and items[0]["severity"] == "high"
        assert "collect" in items[0]["headline"]

    def test_due_soon_obligation_is_medium(self, session, project_factory):
        p = project_factory(name="Soon Proj")
        _oblig(session, p, kind="insurance_expiry", direction="owed_by_us",
               amount=Decimal("500"), due_date=TODAY + timedelta(days=5),
               description="insurance renewal")
        session.commit()
        items = [
            i for i in report_attention_briefing(session, today=TODAY)["items"]
            if i["category"] == "commitments" and i["project_id"] == str(p.canonical_id)
        ]
        assert items and items[0]["severity"] == "medium"


class TestMigration:
    def test_creates_contract_obligation(self):
        e = create_engine("sqlite:///:memory:", future=True)
        Base.metadata.create_all(e)
        with e.begin() as c:
            c.execute(text("DROP TABLE contract_obligation"))
        assert "contract_obligation" not in inspect(e).get_table_names()
        ensure_sqlite_schema(e)
        cols = {col["name"] for col in inspect(e).get_columns("contract_obligation")}
        assert {"kind", "direction", "due_date", "trigger", "amount",
                "quoted_excerpt", "amount_verified"} <= cols
        ensure_sqlite_schema(e)  # idempotent
        e.dispose()


class TestExtraction:
    def test_extracts_verifies_and_attributes(self, session, project_factory):
        p = project_factory(name="Oblig Proj")
        _contract_doc(
            session, p, name="Contract.pdf",
            body="The client shall pay a deposit of $8,000.00 upon signing. "
                 "A penalty of $500 per day applies after 2026-08-01.",
        )
        session.commit()
        prov = _mock([
            {"document": 1, "kind": "deposit", "direction": "owed_to_us",
             "amount": 8000, "due_date": None, "trigger": "upon signing",
             "quoted_excerpt": "deposit of $8,000.00 upon signing", "confidence": 0.9},
            {"document": 1, "kind": "penalty", "direction": "owed_by_us",
             "amount": 500, "due_date": "2026-08-01", "trigger": None,
             "quoted_excerpt": "penalty of $500 per day", "confidence": 0.8},
        ])
        batch = extract_obligations_for_project(session, prov, p.canonical_id)
        assert batch.created_count == 2

        obs = {o.kind: o for o in session.query(ContractObligation).all()}
        dep = obs["deposit"]
        assert dep.direction == "owed_to_us"
        assert float(dep.amount) == 8000.0
        assert dep.amount_verified is True        # 8000 present as $8,000.00
        assert dep.trigger == "upon signing"
        assert dep.document_id is not None
        assert obs["penalty"].due_date == date(2026, 8, 1)

    def test_skips_item_with_no_amount_date_or_trigger(self, session, project_factory):
        p = project_factory(name="P1")
        _contract_doc(session, p, name="Contract.pdf",
                      body="payment milestone schedule and terms")
        session.commit()
        prov = _mock([{"document": 1, "kind": "other", "direction": "unknown",
                       "amount": None, "due_date": None, "trigger": None}])
        batch = extract_obligations_for_project(session, prov, p.canonical_id)
        assert batch.created_count == 0
        assert any("skipped" in w for w in batch.warnings)

    def test_unknown_vocab_coerced_and_warned(self, session, project_factory):
        p = project_factory(name="P2")
        _contract_doc(session, p, name="Contract.pdf",
                      body="deposit $1,000 due 2026-09-01")
        session.commit()
        prov = _mock([{"document": 1, "kind": "weird", "direction": "sideways",
                       "amount": 1000, "due_date": "2026-09-01", "trigger": None,
                       "quoted_excerpt": "deposit $1,000"}])
        extract_obligations_for_project(session, prov, p.canonical_id)
        ob = session.query(ContractObligation).one()
        assert ob.kind == "other" and ob.direction == "unknown"

    def test_unverified_amount_flagged(self, session, project_factory):
        p = project_factory(name="P3")
        _contract_doc(session, p, name="Contract.pdf",
                      body="a deposit is due on signing")  # no number in text
        session.commit()
        prov = _mock([{"document": 1, "kind": "deposit", "direction": "owed_to_us",
                       "amount": 99999, "due_date": None, "trigger": "on signing",
                       "quoted_excerpt": "a deposit is due"}])
        extract_obligations_for_project(session, prov, p.canonical_id)
        assert session.query(ContractObligation).one().amount_verified is False

    def test_no_contract_docs_skips(self, session, project_factory):
        p = project_factory(name="Empty Proj")
        batch = extract_obligations_for_project(session, _mock([]), p.canonical_id)
        assert batch.created_count == 0
        assert "no contract" in (batch.skipped_reason or "")

    def test_all_or_nothing_keeps_prior_on_failure(self, session, project_factory):
        p = project_factory(name="P4")
        _contract_doc(session, p, name="Contract.pdf",
                      body="deposit $1,000 due 2026-09-01")
        prior = ContractObligation(project_id=p.canonical_id, kind="deposit",
                                   direction="owed_to_us", amount=Decimal("1"))
        session.add(prior)
        session.commit()

        class _Boom(MockLLMProvider):
            def complete(self, **kw):  # non-transient -> no retry/sleep
                raise LLMProviderError("400 invalid request")

        batch = extract_obligations_for_project(session, _Boom(), p.canonical_id)
        assert batch.skipped_reason and "batches failed" in batch.skipped_reason
        # prior preserved; nothing written or deleted
        assert session.query(ContractObligation).count() == 1
