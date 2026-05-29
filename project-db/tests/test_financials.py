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

from project_db.ai.financials import (
    _coerce_item_list,
    _norm,
    _parse_amount,
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
        # prompt_version + raw kept
        assert all(r.prompt_version for r in rows)
        assert all(r.source_meta_json for r in rows)

    def test_excerpt_not_in_source_warns_but_keeps(self, financial_fixture, session):
        provider = _mock([
            {"doc_index": 0, "direction": "client_in", "record_kind": "total",
             "amount": 250,
             "quoted_excerpt": "Grand total nine hundred dollars",  # not in text
             "confidence": 0.5},
        ])
        batch = extract_financials_for_project(
            session, provider, financial_fixture["project"].canonical_id,
        )
        assert batch.created_count == 1          # still created
        assert any("not found verbatim" in w for w in batch.warnings)

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
# Reconciliation report
# ---------------------------------------------------------------------------


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
