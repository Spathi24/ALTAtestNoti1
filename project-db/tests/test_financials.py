"""Tests for the financial extraction engine + reconciliation report.

Everything runs against MockLLMProvider -- no API key, no network,
deterministic.  Coverage:

  * extract_financials_for_project happy path -> FinancialRecord rows
  * direction / doc_role / record_kind vocab coercion (+ warnings)
  * quoted-excerpt verification against source text (warn, don't reject)
  * malformed LLM items recorded as errors, not crashes
  * fresh-snapshot idempotency (re-run replaces prior records)
  * skip path (no financial-candidate documents)
  * candidate selection: keyword + mime gates
  * report_project_financials: two-sided totals + margin, representative
    amount (total preferred over line items), empty-project note
  * pure helpers: _parse_amount, _coerce_item_list, _norm
  * CLI parser routes extract-financials -> cmd_extract_financials
"""
from __future__ import annotations

import json
from datetime import date
from decimal import Decimal

import pytest

from decimal import Decimal as _D

from project_db.ai.financials import (
    _Candidate,
    _amount_in_text,
    _chunk_candidates,
    _coerce_item_list,
    _complete_with_backoff,
    _is_transient,
    _norm,
    _parse_amount,
    _parse_doc_classifications,
    _resolve_rollup,
    _select_financial_documents,
    extract_financials_for_project,
)
from project_db.ai.providers import MockLLMProvider
from project_db.ai.views import report_project_financials
from project_db.db.models import (
    Document,
    DocumentText,
    FinancialRecord,
    Project,
)
from project_db.db.models.work import ProjectStatus


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _add_doc(session, project, *, name, text, mime="application/pdf",
             folder="Active/Proj/Invoices"):
    """Create a Document + its DocumentText, return the Document."""
    doc = Document(
        name=name, url=f"https://drive/{name}", mime_type=mime,
        storage_ref=name, folder_path=folder, project_id=project.canonical_id,
    )
    session.add(doc)
    session.commit()
    session.add(DocumentText(
        document_id=doc.canonical_id, extracted_text=text,
        extraction_method="pdf-pymupdf", token_count=len(text) // 4,
    ))
    session.commit()
    return doc


@pytest.fixture
def financial_fixture(session, client_factory):
    """A project with two financial docs: a client quote and a supplier bill.

    docA scores higher on financial keywords than docB, so candidate
    selection order is deterministic: docA -> index 0, docB -> index 1.
    """
    c = client_factory(name="Acme")
    p = Project(
        name="5768 St-Laurent", code="SL5768", status=ProjectStatus.ACTIVE,
        client_id=c.canonical_id,
    )
    session.add(p)
    session.commit()

    doc_a = _add_doc(
        session, p,
        name="Quote Estimate Invoice.pdf",
        text="Quote to client. Total: $250.00 for kitchen renovation. Thanks.",
    )
    doc_b = _add_doc(
        session, p,
        name="Materials.pdf",
        text="Supplier bill. Labour: $100.00 for framing crew.",
    )
    return {"project": p, "doc_a": doc_a, "doc_b": doc_b}


def _mock(records_json: list[dict]) -> MockLLMProvider:
    """MockLLMProvider returning a well-formed records envelope."""
    return MockLLMProvider(responses=[json.dumps({"records": records_json})])


# ---------------------------------------------------------------------------
# Pure helpers
# ---------------------------------------------------------------------------


class TestParseAmount:
    def test_int_and_float(self):
        assert _parse_amount(250) == Decimal("250")
        assert _parse_amount(99.5) == Decimal("99.5")

    def test_string_with_symbols(self):
        assert _parse_amount("$1,250.00") == Decimal("1250.00")
        assert _parse_amount("CAD 300") == Decimal("300")

    def test_none_and_garbage(self):
        assert _parse_amount(None) is None
        assert _parse_amount("") is None
        assert _parse_amount("n/a") is None
        assert _parse_amount(True) is None  # bool is not a money amount


class TestCoerceItemList:
    def test_envelope(self):
        assert _coerce_item_list({"records": [1, 2]}) == [1, 2]

    def test_bare_list(self):
        assert _coerce_item_list([1, 2]) == [1, 2]

    def test_garbage(self):
        assert _coerce_item_list("nope") == []
        assert _coerce_item_list({"other": [1]}) == []


class TestNorm:
    def test_collapses_whitespace_and_lowercases(self):
        assert _norm("  Total:   $250.00\n ") == "total: $250.00"

    def test_none(self):
        assert _norm(None) == ""


class TestAmountInText:
    def test_thousands_separator_match(self):
        assert _amount_in_text(_D("3600"), _norm("Total 3,600.00 $")) is True

    def test_decimal_as_written(self):
        assert _amount_in_text(_D("287.44"), _norm("invoice total 287.44")) is True

    def test_trailing_zero_tolerance(self):
        # 12.5 must match a doc that writes "12.50" (same value).
        assert _amount_in_text(_D("12.5"), _norm("GST 5.00% 12.50")) is True

    def test_rounding_tolerance(self):
        # Model rounds 549241.8481 -> 549241.85; still the same money.
        assert _amount_in_text(_D("549241.85"),
                               _norm("Total after tax 549241.8481")) is True

    def test_french_decimal_comma(self):
        # Quebec invoices write "923,44 $"; the model outputs 923.44.
        assert _amount_in_text(_D("923.44"), _norm("Sous-total 923,44 $")) is True
        assert _amount_in_text(_D("40.16"), _norm("TPS 40,16 $")) is True

    def test_french_comma_not_confused_with_thousands(self):
        # "3,600" (English thousands) still matches 3600.
        assert _amount_in_text(_D("3600"), _norm("Total 3,600.00")) is True

    def test_space_thousands_separator(self):
        # Quebec/SI invoices write "$1 080.00" (space = thousands sep).
        assert _amount_in_text(_D("1080"), _norm("LABOUR $1 080.00")) is True
        assert _amount_in_text(_D("17384.91"), _norm("Total 17 384,91 $")) is True
        # chained groups
        assert _amount_in_text(_D("1234567"), _norm("Grand total 1 234 567")) is True

    def test_qty_price_not_lost_to_despace(self):
        # "1   500,00" is qty 1 + price 500,00 -- the un-despaced reading must
        # still recover 500.00 (despace alone would merge it to 1500).
        assert _amount_in_text(_D("500"), _norm("CONTENEUR 1 500,00 5")) is True

    def test_negative_amount_matches_magnitude(self):
        assert _amount_in_text(_D("-250"), _norm("Credit on install -250.00 $")) is True
        assert _amount_in_text(_D("-2001.42"),
                               _norm("Deposit on hand 1 -2,001.42")) is True

    def test_k_notation_expansion(self):
        # Tenant trackers write "8k" / "10.5k"; the model expands to 8000 etc.
        assert _amount_in_text(_D("8000"), _norm("Majd Nov 29th: PAID 8k")) is True
        assert _amount_in_text(_D("10500"), _norm("Henry Feb 1st: 10.5k + moving")) is True
        # not confused inside a word
        assert _amount_in_text(_D("8000"), _norm("worker okay")) is False

    def test_value_based_blocks_substring(self):
        # 600 must NOT match a doc whose only number is 3600 (different value).
        assert _amount_in_text(_D("600"), _norm("line item 3600.00 only")) is False

    def test_standalone_match(self):
        assert _amount_in_text(_D("600"), _norm("qty 15 cost 600 total")) is True

    def test_none(self):
        assert _amount_in_text(None, "anything") is False


# ---------------------------------------------------------------------------
# Candidate selection
# ---------------------------------------------------------------------------


class TestSelection:
    def test_orders_by_keyword_score(self, financial_fixture, session):
        cands = _select_financial_documents(
            session, financial_fixture["project"].canonical_id,
            max_documents=12, per_doc_char_cap=8000, total_char_budget=48000,
        )
        assert len(cands) == 2
        # docA has more financial keywords -> ranked first.
        assert cands[0].document.canonical_id == financial_fixture["doc_a"].canonical_id

    def test_mime_gate_excludes_images(self, session, client_factory):
        c = client_factory(name="C")
        p = Project(name="P", code="P", status=ProjectStatus.ACTIVE,
                    client_id=c.canonical_id)
        session.add(p)
        session.commit()
        # A financial-keyword name but an image mime -> excluded.
        _add_doc(session, p, name="Invoice photo.heic", text="$500",
                 mime="image/heif")
        cands = _select_financial_documents(
            session, p.canonical_id,
            max_documents=12, per_doc_char_cap=8000, total_char_budget=48000,
        )
        assert cands == []

    def test_keyword_gate_excludes_non_financial(self, session, client_factory):
        c = client_factory(name="C")
        p = Project(name="P", code="P", status=ProjectStatus.ACTIVE,
                    client_id=c.canonical_id)
        session.add(p)
        session.commit()
        _add_doc(session, p, name="Site photo notes.pdf", text="no money here",
                 folder="Active/P/Photos")
        cands = _select_financial_documents(
            session, p.canonical_id,
            max_documents=12, per_doc_char_cap=8000, total_char_budget=48000,
        )
        assert cands == []


# ---------------------------------------------------------------------------
# Extraction
# ---------------------------------------------------------------------------


class TestExtraction:
    def test_happy_path(self, financial_fixture, session):
        provider = _mock([
            {"doc_index": 0, "direction": "client_in", "doc_role": "quote",
             "record_kind": "total", "counterparty": "Acme",
             "description": "kitchen renovation", "amount": 250,
             "currency": "CAD", "doc_date": "2026-03-25",
             "quoted_excerpt": "Total: $250.00 for kitchen renovation",
             "confidence": 0.9},
            {"doc_index": 1, "direction": "contractor_out", "doc_role": "invoice",
             "record_kind": "line_item", "counterparty": "Framing Co",
             "description": "framing crew", "amount": 100,
             "quoted_excerpt": "Labour: $100.00", "confidence": 0.8},
        ])
        batch = extract_financials_for_project(
            session, provider, financial_fixture["project"].canonical_id,
        )
        assert batch.created_count == 2
        assert batch.documents_considered == 2
        assert not batch.errors
        assert not batch.warnings  # excerpts verify against source text

        rows = session.query(FinancialRecord).all()
        assert len(rows) == 2
        by_dir = {r.direction: r for r in rows}
        assert by_dir["client_in"].amount == Decimal("250.00")
        assert by_dir["client_in"].doc_date == date(2026, 3, 25)
        assert by_dir["contractor_out"].amount == Decimal("100.00")
        # both amounts appear in their source docs -> verified True
        assert all(r.amount_verified is True for r in rows)
        # prompt_version + raw kept
        assert all(r.prompt_version for r in rows)
        assert all(r.source_meta_json for r in rows)

    def test_amount_not_in_source_warns_but_keeps(self, financial_fixture, session):
        # 999 does not appear in docA's text -> flagged as possible
        # hallucination / computed value, but still created.
        provider = _mock([
            {"doc_index": 0, "direction": "client_in", "record_kind": "total",
             "amount": 999, "quoted_excerpt": "Total: $999.00",
             "confidence": 0.5},
        ])
        batch = extract_financials_for_project(
            session, provider, financial_fixture["project"].canonical_id,
        )
        assert batch.created_count == 1          # still created
        assert any("does not appear in the document" in w for w in batch.warnings)
        row = session.query(FinancialRecord).one()
        assert row.amount_verified is False
        rep = report_project_financials(
            session, str(financial_fixture["project"].canonical_id)
        )
        assert rep["unverified_count"] == 1

    def test_reflowed_excerpt_amount_present_no_warning(self, financial_fixture, session):
        # A non-verbatim excerpt is fine as long as the AMOUNT is in the doc
        # (docA text contains "$250.00").  This is the false-positive the old
        # verbatim-excerpt check produced; the amount-presence guard clears it.
        provider = _mock([
            {"doc_index": 0, "direction": "client_in", "record_kind": "total",
             "amount": 250,
             "quoted_excerpt": "kitchen renovation ... grand total 250",
             "confidence": 0.9},
        ])
        batch = extract_financials_for_project(
            session, provider, financial_fixture["project"].canonical_id,
        )
        assert batch.created_count == 1
        assert not batch.warnings

    def test_missing_excerpt_warns(self, financial_fixture, session):
        provider = _mock([
            {"doc_index": 0, "direction": "client_in", "record_kind": "total",
             "amount": 250},
        ])
        batch = extract_financials_for_project(
            session, provider, financial_fixture["project"].canonical_id,
        )
        assert batch.created_count == 1
        assert any("no quoted_excerpt" in w for w in batch.warnings)

    def test_bad_items_recorded_not_raised(self, financial_fixture, session):
        provider = _mock([
            {"doc_index": 99, "direction": "client_in", "amount": 1},   # bad index
            {"doc_index": 0, "direction": "client_in", "amount": "n/a"},  # bad amount
            "not even an object",
            {"doc_index": 1, "direction": "contractor_out", "record_kind": "line_item",
             "amount": 100, "quoted_excerpt": "Labour: $100.00"},        # good
        ])
        batch = extract_financials_for_project(
            session, provider, financial_fixture["project"].canonical_id,
        )
        assert batch.created_count == 1
        assert len(batch.errors) == 3

    def test_unknown_direction_coerced_and_warned(self, financial_fixture, session):
        provider = _mock([
            {"doc_index": 0, "direction": "sideways", "record_kind": "total",
             "amount": 250, "quoted_excerpt": "Total: $250.00 for kitchen renovation"},
        ])
        batch = extract_financials_for_project(
            session, provider, financial_fixture["project"].canonical_id,
        )
        assert batch.created_count == 1
        row = session.query(FinancialRecord).one()
        assert row.direction == "unknown"
        assert any("unknown value 'sideways'" in w for w in batch.warnings)

    def test_fresh_snapshot_idempotency(self, financial_fixture, session):
        provider = _mock([
            {"doc_index": 0, "direction": "client_in", "record_kind": "total",
             "amount": 250, "quoted_excerpt": "Total: $250.00 for kitchen renovation"},
        ])
        pid = financial_fixture["project"].canonical_id
        b1 = extract_financials_for_project(session, provider, pid)
        assert b1.superseded_count == 0
        assert session.query(FinancialRecord).count() == 1

        b2 = extract_financials_for_project(session, provider, pid)
        assert b2.superseded_count == 1          # prior row deleted
        assert session.query(FinancialRecord).count() == 1  # not accumulated

    def test_skip_when_no_financial_docs(self, session, client_factory):
        c = client_factory(name="C")
        p = Project(name="Empty", code="E", status=ProjectStatus.ACTIVE,
                    client_id=c.canonical_id)
        session.add(p)
        session.commit()
        batch = extract_financials_for_project(session, _mock([]), p.canonical_id)
        assert batch.created_count == 0
        assert batch.skipped_reason is not None


# ---------------------------------------------------------------------------
# Batching / full coverage  (the 2026-05-29 coverage-gap fix)
# ---------------------------------------------------------------------------


def _fake_cands(sizes: list[int]) -> list[_Candidate]:
    return [_Candidate(document=None, text="x" * n, full_text="", truncated=False)
            for n in sizes]


class TestBackoffRetry:
    def test_is_transient(self):
        assert _is_transient("Error code: 429 rate limit") is True
        assert _is_transient("overloaded_error 529") is True
        # billing / bad request must NOT be treated as transient
        assert _is_transient("Error code: 400 credit balance is too low") is False
        assert _is_transient("invalid api key") is False

    def test_no_retry_on_non_transient(self, monkeypatch):
        from project_db.ai.providers.base import LLMProviderError

        monkeypatch.setattr("time.sleep", lambda *a, **k: None)
        calls = {"n": 0}

        class P:
            def complete_json(self, **kw):
                calls["n"] += 1
                raise LLMProviderError("Error code: 400 credit balance too low")

        with pytest.raises(LLMProviderError):
            _complete_with_backoff(P(), "sys", "user", 1000)
        assert calls["n"] == 1  # failed once, did not retry a 400

    def test_retries_transient_then_succeeds(self, monkeypatch):
        from project_db.ai.providers.base import LLMProviderError

        monkeypatch.setattr("time.sleep", lambda *a, **k: None)
        calls = {"n": 0}

        class P:
            def complete_json(self, **kw):
                calls["n"] += 1
                if calls["n"] == 1:
                    raise LLMProviderError("429 rate limit")
                return {"records": []}

        out = _complete_with_backoff(P(), "sys", "user", 1000)
        assert out == {"records": []}
        assert calls["n"] == 2


class TestChunking:
    def test_splits_by_count(self):
        chunks = _chunk_candidates(_fake_cands([10] * 7), char_budget=10_000, max_docs=3)
        assert [len(c) for c in chunks] == [3, 3, 1]

    def test_splits_by_char_budget(self):
        chunks = _chunk_candidates(_fake_cands([5000, 5000, 5000, 5000]),
                                   char_budget=12_000, max_docs=10)
        assert [len(c) for c in chunks] == [2, 2]

    def test_oversized_doc_gets_its_own_batch_not_dropped(self):
        chunks = _chunk_candidates(_fake_cands([20_000, 100]),
                                   char_budget=12_000, max_docs=10)
        assert [len(c) for c in chunks] == [1, 1]   # big doc kept, alone


class TestBatchingCoverage:
    def test_all_docs_processed_across_multiple_calls(self, session, client_factory):
        c = client_factory(name="C")
        p = Project(name="Big", code="B", status=ProjectStatus.ACTIVE,
                    client_id=c.canonical_id)
        session.add(p)
        session.commit()
        for i in range(7):
            _add_doc(session, p, name=f"Invoice {i}.pdf",
                     text=f"Invoice {i}. Total: ${i+1}00.00 due.")
        provider = _mock([])   # empty records, but every batch is a call
        batch = extract_financials_for_project(
            session, provider, p.canonical_id, batch_max_docs=3,
        )
        # 7 docs / 3 per batch -> 3 LLM calls; all 7 considered.
        assert batch.documents_considered == 7
        assert len(provider.calls) == 3

    def test_batch_failure_keeps_prior_and_writes_nothing(
        self, session, client_factory, monkeypatch,
    ):
        """All-or-nothing: a batch failure must NOT destroy prior records or
        leave a partial snapshot.  (Data-safety lesson, 2026-05-29.)"""
        monkeypatch.setattr("time.sleep", lambda *a, **k: None)  # no real backoff wait
        c = client_factory(name="C")
        p = Project(name="Mix", code="M", status=ProjectStatus.ACTIVE,
                    client_id=c.canonical_id)
        session.add(p)
        session.commit()
        for i in range(4):
            _add_doc(session, p, name=f"Quote {i}.pdf",
                     text=f"Quote {i}. Total: ${i+1}50.00.")

        # Seed a prior good record that must survive a failed re-run.
        prior = FinancialRecord(
            project_id=p.canonical_id, direction="contractor_out",
            amount=Decimal("999.00"), amount_verified=True,
        )
        session.add(prior)
        session.commit()

        from project_db.ai.providers.base import LLMProviderError

        def on_call(**kw):
            raise LLMProviderError("boom")  # every attempt fails

        provider = MockLLMProvider(on_call=on_call)
        batch = extract_financials_for_project(
            session, provider, p.canonical_id, batch_max_docs=2,
        )
        # Run is a no-op: error recorded, nothing written, prior kept.
        assert any("LLM call failed for batch" in e for e in batch.errors)
        assert batch.skipped_reason is not None
        assert batch.created_count == 0
        assert batch.superseded_count == 0
        # The seeded prior record still exists.
        survivors = session.query(FinancialRecord).filter_by(
            project_id=p.canonical_id).all()
        assert len(survivors) == 1
        assert survivors[0].amount == Decimal("999.00")


# ---------------------------------------------------------------------------
# Reconciliation report
# ---------------------------------------------------------------------------


class TestRollupClassification:
    def test_parse_doc_classifications(self):
        raw = {"documents": [
            {"doc_index": 0, "kind": "rollup"},
            {"doc_index": 1, "kind": "primary"},
            {"doc_index": 9, "kind": "rollup"},   # out of range -> dropped
            {"doc_index": 2, "kind": "PRIMARY"},  # case-insensitive
        ]}
        m = _parse_doc_classifications(raw, n=3)
        assert m == {0: True, 1: False, 2: False}

    def test_missing_documents_defaults_empty(self):
        assert _parse_doc_classifications({"records": []}, n=2) == {}
        assert _parse_doc_classifications("nope", n=2) == {}

    def test_resolve_rollup_guard(self):
        # A transaction instrument is never a rollup, even if the model says so.
        assert _resolve_rollup(True, "other") is True
        assert _resolve_rollup(True, "quote") is False      # guard overrides
        assert _resolve_rollup(True, "estimate") is False
        assert _resolve_rollup(True, "invoice") is False
        assert _resolve_rollup(False, "other") is False

    def test_itemized_quote_not_marked_rollup(self, financial_fixture, session):
        # Model wrongly tags an itemized client quote (doc 0) as rollup, but its
        # doc_role is 'estimate' -> the guard forces it PRIMARY.
        provider = MockLLMProvider(responses=[json.dumps({
            "documents": [{"doc_index": 0, "kind": "rollup"}],
            "records": [
                {"doc_index": 0, "direction": "client_in", "doc_role": "estimate",
                 "record_kind": "total", "amount": 250,
                 "quoted_excerpt": "Total: $250.00 for kitchen renovation"},
            ],
        })])
        extract_financials_for_project(
            session, provider, financial_fixture["project"].canonical_id,
        )
        rec = session.query(FinancialRecord).filter_by(amount=Decimal("250.00")).one()
        assert rec.is_rollup is False   # transaction instrument, guard wins

    def test_extraction_marks_rollup_per_document(self, financial_fixture, session):
        # docA (index 0) flagged rollup, docB (index 1) primary.
        provider = MockLLMProvider(responses=[json.dumps({
            "documents": [
                {"doc_index": 0, "kind": "rollup"},
                {"doc_index": 1, "kind": "primary"},
            ],
            "records": [
                {"doc_index": 0, "direction": "client_in", "record_kind": "total",
                 "amount": 250,
                 "quoted_excerpt": "Total: $250.00 for kitchen renovation"},
                {"doc_index": 1, "direction": "contractor_out",
                 "record_kind": "line_item", "amount": 100,
                 "quoted_excerpt": "Labour: $100.00"},
            ],
        })])
        batch = extract_financials_for_project(
            session, provider, financial_fixture["project"].canonical_id,
        )
        assert batch.created_count == 2
        by_amt = {r.amount: r for r in session.query(FinancialRecord).all()}
        assert by_amt[Decimal("250.00")].is_rollup is True
        assert by_amt[Decimal("100.00")].is_rollup is False


class TestReport:
    def _record(self, session, project, doc, **kw):
        r = FinancialRecord(project_id=project.canonical_id,
                            document_id=doc.canonical_id, **kw)
        session.add(r)
        session.commit()
        return r

    def test_two_sided_totals_and_margin(self, financial_fixture, session):
        p, doc_a, doc_b = (financial_fixture[k] for k in ("project", "doc_a", "doc_b"))
        # docA: a line item AND a grand total -> representative is the total (250).
        self._record(session, p, doc_a, direction="client_in",
                     record_kind="line_item", amount=Decimal("100"))
        self._record(session, p, doc_a, direction="client_in",
                     record_kind="total", amount=Decimal("250"))
        # docB: two contractor line items -> 40 + 60 = 100.
        self._record(session, p, doc_b, direction="contractor_out",
                     record_kind="line_item", amount=Decimal("40"))
        self._record(session, p, doc_b, direction="contractor_out",
                     record_kind="line_item", amount=Decimal("60"))

        rep = report_project_financials(session, str(p.canonical_id))
        t = rep["totals"]
        assert t["client_in"] == pytest.approx(250.0)     # total, not 100+250
        assert t["contractor_out"] == pytest.approx(100.0)
        assert t["margin"] == pytest.approx(150.0)
        assert rep["record_count"] == 4
        assert len(rep["per_document"]) == 2

    def test_empty_project_returns_zeros_with_note(self, financial_fixture, session):
        rep = report_project_financials(
            session, str(financial_fixture["project"].canonical_id)
        )
        assert rep["totals"] == {
            "client_in": 0.0, "contractor_out": 0.0, "unknown": 0.0, "margin": 0.0,
        }
        assert "extract-financials" in rep["note"]

    def test_unresolved_project(self, session):
        rep = report_project_financials(session, "no-such-project")
        assert "error" in rep

    def test_rollup_excluded_from_totals_shown_as_crosscheck(
        self, financial_fixture, session,
    ):
        p, doc_a, doc_b = (financial_fixture[k] for k in ("project", "doc_a", "doc_b"))
        # doc_a: a PRIMARY supplier invoice, contractor_out 100.
        self._record(session, p, doc_a, direction="contractor_out",
                     record_kind="total", amount=Decimal("100"), is_rollup=False)
        # doc_b: an internal ROLL-UP cost sheet restating it (999) -- must NOT
        # be summed into the total, only cross-checked.
        self._record(session, p, doc_b, direction="contractor_out",
                     record_kind="total", amount=Decimal("999"), is_rollup=True)

        rep = report_project_financials(session, str(p.canonical_id))
        assert rep["totals"]["contractor_out"] == pytest.approx(100.0)  # not 1099
        assert rep["primary_record_count"] == 1
        assert rep["rollup_record_count"] == 1
        assert rep["rollup_crosscheck"]["contractor_out"] == pytest.approx(999.0)
        assert rep["rollup_crosscheck"]["document_count"] == 1


# ---------------------------------------------------------------------------
# CLI wiring
# ---------------------------------------------------------------------------


class TestCliParser:
    def test_extract_financials_routes(self):
        from project_db.cli import build_parser, cmd_extract_financials

        parser = build_parser()
        args = parser.parse_args(["extract-financials", "5768", "--max-docs", "3"])
        assert args.func is cmd_extract_financials
        assert args.project == "5768"
        assert args.max_docs == 3
