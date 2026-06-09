"""Tests for structured contract-obligation extraction.

All offline -- MockObligationExtractor returns canned classify-then-extract
results; no live API. Mirrors test_obligations.py (the legacy path) and the
structured-financials tests: classify, validate/coerce, amount verification,
doc attribution, the dated-or-dollar skip rule, the MIME scope, and the
all-or-nothing snapshot.
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal

from project_db.ai.obligation_extraction import (
    MockObligationExtractor,
    ObligationExtractorError,
    extract_obligations_structured_for_project,
)
from project_db.db.models import ContractObligation, Document
from project_db.db.models.docs import DocumentText


def _doc(session, project, *, name, body, mime="application/pdf"):
    d = Document(name=name, url=f"x://{name}", mime_type=mime,
                 project_id=project.canonical_id)
    session.add(d)
    session.flush()
    session.add(DocumentText(document_id=d.canonical_id, extracted_text=body,
                             extraction_method="test"))
    session.flush()
    return d


def _result(obligations, *, dtype="contract", contractual=True):
    return {"document_type": dtype, "is_contractual": contractual,
            "summary": "mock", "obligations": obligations}


class TestStructuredExtraction:
    def test_extracts_verifies_and_attributes(self, session, project_factory):
        p = project_factory(name="Oblig Proj")
        doc = _doc(
            session, p, name="Contract.pdf",
            body="The client shall pay a deposit of $8,000.00 upon signing. "
                 "A penalty of $500 per day applies after 2026-08-01.",
        )
        session.commit()
        extractor = MockObligationExtractor(by_name={
            "Contract.pdf": _result([
                {"kind": "deposit", "direction": "owed_to_us", "description": "deposit",
                 "amount": 8000, "currency": "CAD", "due_date": None,
                 "trigger": "upon signing", "counterparty": "client",
                 "quoted_excerpt": "deposit of $8,000.00 upon signing", "confidence": 0.9},
                {"kind": "penalty", "direction": "owed_by_us", "description": "late penalty",
                 "amount": 500, "currency": "CAD", "due_date": "2026-08-01",
                 "trigger": None, "counterparty": None,
                 "quoted_excerpt": "penalty of $500 per day", "confidence": 0.8},
            ]),
        })
        batch = extract_obligations_structured_for_project(session, extractor, p.canonical_id)
        assert batch.created_count == 2
        assert extractor.calls == ["Contract.pdf"]

        obs = {o.kind: o for o in session.query(ContractObligation).all()}
        dep = obs["deposit"]
        assert dep.direction == "owed_to_us"
        assert float(dep.amount) == 8000.0
        assert dep.amount_verified is True            # 8000 present as $8,000.00
        assert dep.trigger == "upon signing"
        assert dep.document_id == doc.canonical_id
        assert dep.prompt_version == "obligations-structured-v2"
        assert obs["penalty"].due_date == date(2026, 8, 1)

    def test_records_classification(self, session, project_factory):
        p = project_factory(name="Classify Proj")
        _doc(session, p, name="Report.pdf", body="site visit photos and notes")
        session.commit()
        extractor = MockObligationExtractor(by_name={
            "Report.pdf": _result([], dtype="other", contractual=False),
        })
        batch = extract_obligations_structured_for_project(session, extractor, p.canonical_id)
        assert batch.created_count == 0
        assert batch.documents_considered == 1
        assert batch.classifications == [("Report.pdf", "other", False)]

    def test_skips_item_with_no_amount_date_or_trigger(self, session, project_factory):
        p = project_factory(name="P1")
        _doc(session, p, name="Contract.pdf", body="payment milestone schedule and terms")
        session.commit()
        extractor = MockObligationExtractor(by_name={
            "Contract.pdf": _result([
                {"kind": "other", "direction": "unknown", "description": "vague",
                 "amount": None, "currency": None, "due_date": None, "trigger": None,
                 "counterparty": None, "quoted_excerpt": "terms", "confidence": 0.2},
            ]),
        })
        batch = extract_obligations_structured_for_project(session, extractor, p.canonical_id)
        assert batch.created_count == 0
        assert any("skipped" in w for w in batch.warnings)

    def test_zero_amount_treated_as_no_amount(self, session, project_factory):
        """$0.00 is template noise (the financial layer skips it): a $0 obligation
        with a real trigger is kept as a no-amount obligation; a $0 obligation
        with no date/trigger is dropped entirely."""
        p = project_factory(name="Zero Proj")
        _doc(session, p, name="Lease.pdf", body="rent is payable on the first of the month")
        session.commit()
        extractor = MockObligationExtractor(by_name={
            "Lease.pdf": _result([
                {"kind": "payment_milestone", "direction": "owed_by_us",
                 "description": "rent term", "amount": 0, "currency": None,
                 "due_date": None, "trigger": "on the first of the month",
                 "counterparty": None, "quoted_excerpt": "rent is payable",
                 "confidence": 0.3},
                {"kind": "deposit", "direction": "owed_by_us", "description": "noise",
                 "amount": 0, "currency": None, "due_date": None, "trigger": None,
                 "counterparty": None, "quoted_excerpt": "x", "confidence": 0.1},
            ]),
        })
        extract_obligations_structured_for_project(session, extractor, p.canonical_id)
        obs = session.query(ContractObligation).all()
        assert len(obs) == 1                      # the no-date/no-trigger $0 was dropped
        assert obs[0].amount is None              # $0 coerced to no-amount
        assert obs[0].trigger == "on the first of the month"

    def test_unverified_amount_flagged(self, session, project_factory):
        p = project_factory(name="P3")
        _doc(session, p, name="Contract.pdf", body="a deposit is due on signing")
        session.commit()
        extractor = MockObligationExtractor(by_name={
            "Contract.pdf": _result([
                {"kind": "deposit", "direction": "owed_to_us", "description": "deposit",
                 "amount": 99999, "currency": None, "due_date": None,
                 "trigger": "on signing", "counterparty": None,
                 "quoted_excerpt": "a deposit is due", "confidence": 0.5},
            ]),
        })
        extract_obligations_structured_for_project(session, extractor, p.canonical_id)
        assert session.query(ContractObligation).one().amount_verified is False

    def test_unknown_vocab_coerced(self, session, project_factory):
        p = project_factory(name="P2")
        _doc(session, p, name="Contract.pdf", body="deposit $1,000 due 2026-09-01")
        session.commit()
        extractor = MockObligationExtractor(by_name={
            "Contract.pdf": _result([
                {"kind": "weird", "direction": "sideways", "description": "x",
                 "amount": 1000, "currency": None, "due_date": "2026-09-01",
                 "trigger": None, "counterparty": None,
                 "quoted_excerpt": "deposit $1,000", "confidence": 0.7},
            ]),
        })
        extract_obligations_structured_for_project(session, extractor, p.canonical_id)
        ob = session.query(ContractObligation).one()
        assert ob.kind == "other" and ob.direction == "unknown"

    def test_mime_filter_excludes_nonprose(self, session, project_factory):
        """A spreadsheet/image doc is not a candidate (obligations are prose)."""
        p = project_factory(name="Sheet Proj")
        _doc(session, p, name="costs.xlsx", body="amounts here",
             mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        session.commit()
        extractor = MockObligationExtractor()
        batch = extract_obligations_structured_for_project(session, extractor, p.canonical_id)
        assert batch.created_count == 0
        assert "no contract" in (batch.skipped_reason or "")
        assert extractor.calls == []                  # the LLM was never called

    def test_no_docs_skips(self, session, project_factory):
        p = project_factory(name="Empty Proj")
        batch = extract_obligations_structured_for_project(
            session, MockObligationExtractor(), p.canonical_id)
        assert batch.created_count == 0
        assert "no contract" in (batch.skipped_reason or "")

    def test_all_or_nothing_keeps_prior_on_failure(self, session, project_factory):
        p = project_factory(name="P4")
        _doc(session, p, name="Contract.pdf", body="deposit $1,000 due 2026-09-01")
        prior = ContractObligation(project_id=p.canonical_id, kind="deposit",
                                   direction="owed_to_us", amount=Decimal("1"))
        session.add(prior)
        session.commit()

        class _Boom(MockObligationExtractor):
            def extract(self, **kw):
                raise ObligationExtractorError("OpenAI extraction call failed: 400")

        batch = extract_obligations_structured_for_project(session, _Boom(), p.canonical_id)
        assert batch.skipped_reason and "failed to extract" in batch.skipped_reason
        # prior preserved; nothing written or deleted
        assert session.query(ContractObligation).count() == 1
        assert float(session.query(ContractObligation).one().amount) == 1.0
