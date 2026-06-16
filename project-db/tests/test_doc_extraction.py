"""Tests for the structured (LLM-classify) extraction path. Offline / mock."""

from __future__ import annotations

from project_db.ai.doc_extraction import (
    MockStructuredExtractor,
    StructuredExtractorError,
    extract_financials_structured_for_project,
    tsv_to_markdown,
)
from project_db.db.models import Document, FinancialRecord
from project_db.db.models.docs import DocumentText

XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def _doc(session, p, name, body, mime="application/pdf"):
    d = Document(name=name, url=f"x://{name}", mime_type=mime, project_id=p.canonical_id)
    session.add(d)
    session.flush()
    session.add(
        DocumentText(document_id=d.canonical_id, extracted_text=body, extraction_method="t")
    )
    session.flush()
    return d


class TestTsvToMarkdown:
    def test_renders_sheet_as_markdown_table(self):
        md = tsv_to_markdown("### Quote\nItem\tCost\nTiles\t1000")
        assert "**Sheet: Quote**" in md
        assert "| Item | Cost |" in md
        assert "| --- | --- |" in md
        assert "| Tiles | 1000 |" in md

    def test_ragged_rows_padded(self):
        md = tsv_to_markdown("### S\nA\tB\tC\nx\ty")  # short row
        assert "| x | y |  |" in md


class TestStructuredExtraction:
    def test_transactional_quote_stored_primary(self, session, project_factory):
        p = project_factory(name="P")
        _doc(session, p, "Quote.pdf", "Total renovation cost: $5,000.00")
        session.commit()
        ext = MockStructuredExtractor(
            by_name={
                "Quote.pdf": {
                    "document_type": "construction_quote",
                    "is_transactional": True,
                    "summary": "quote",
                    "records": [
                        {
                            "amount": 5000,
                            "currency": "CAD",
                            "direction": "client_in",
                            "record_kind": "total",
                            "description": "reno",
                            "quoted_excerpt": "Total renovation cost: $5,000.00",
                            "confidence": 0.9,
                        }
                    ],
                }
            }
        )
        batch = extract_financials_structured_for_project(session, ext, p.canonical_id)
        assert batch.created_count == 1
        r = session.query(FinancialRecord).one()
        assert r.direction == "client_in" and float(r.amount) == 5000.0
        assert r.is_rollup is False
        assert r.amount_verified is True  # 5000 present as $5,000.00

    def test_market_report_skipped(self, session, project_factory):
        p = project_factory(name="P")
        _doc(session, p, "Market Report.pdf", "Total Investment $2.5 billion projected")
        session.commit()
        ext = MockStructuredExtractor(
            by_name={
                "Market Report.pdf": {
                    "document_type": "market_report_or_valuation",
                    "is_transactional": False,
                    "summary": "market report",
                    "records": [
                        {
                            "amount": 2500000000,
                            "currency": "CAD",
                            "direction": "unknown",
                            "record_kind": "total",
                            "description": "projected",
                            "quoted_excerpt": "Total Investment $2.5 billion",
                            "confidence": 0.5,
                        }
                    ],
                }
            }
        )
        batch = extract_financials_structured_for_project(session, ext, p.canonical_id)
        assert batch.created_count == 0  # NOT extracted (the $2.5B junk gone)
        assert batch.documents_skipped_nontransactional == 1
        assert session.query(FinancialRecord).count() == 0

    def test_budget_kept_as_rollup(self, session, project_factory):
        p = project_factory(name="P")
        _doc(session, p, "C61 budget.xlsx", "### Budget\nTotal\t400000", mime=XLSX)
        session.commit()
        ext = MockStructuredExtractor(
            by_name={
                "C61 budget.xlsx": {
                    "document_type": "budget_or_cost_tracker",
                    "is_transactional": False,
                    "summary": "budget",
                    "records": [
                        {
                            "amount": 400000,
                            "currency": None,
                            "direction": "contractor_out",
                            "record_kind": "total",
                            "description": "budget total",
                            "quoted_excerpt": "Total 400000",
                            "confidence": 0.7,
                        }
                    ],
                }
            }
        )
        batch = extract_financials_structured_for_project(session, ext, p.canonical_id)
        assert batch.created_count == 1
        assert session.query(FinancialRecord).one().is_rollup is True  # cross-check only

    def test_all_or_nothing_on_failure_keeps_prior(self, session, project_factory):
        p = project_factory(name="P")
        d = _doc(session, p, "Quote.pdf", "Total $5,000")
        session.add(
            FinancialRecord(
                project_id=p.canonical_id,
                document_id=d.canonical_id,
                direction="client_in",
                record_kind="total",
                amount=1,
            )
        )
        session.commit()

        class _Boom(MockStructuredExtractor):
            def extract(self, **kw):
                raise StructuredExtractorError("boom")

        batch = extract_financials_structured_for_project(session, _Boom(), p.canonical_id)
        assert batch.skipped_reason
        assert session.query(FinancialRecord).count() == 1  # prior preserved

    def test_unknown_direction_resolved_from_doc_type(self, session, project_factory):
        # An estimate the LLM typed correctly but left direction=unknown -> the
        # type entails client_in (revenue), deterministically.
        p = project_factory(name="P")
        _doc(session, p, "Estimation.pdf", "TOTAL 71,975 $")
        session.commit()
        ext = MockStructuredExtractor(
            by_name={
                "Estimation.pdf": {
                    "document_type": "construction_estimate",
                    "is_transactional": True,
                    "summary": "estimate",
                    "records": [
                        {
                            "amount": 71975,
                            "currency": "CAD",
                            "direction": "unknown",
                            "record_kind": "total",
                            "description": "total",
                            "quoted_excerpt": "TOTAL 71,975 $",
                            "confidence": 0.8,
                        }
                    ],
                }
            }
        )
        extract_financials_structured_for_project(session, ext, p.canonical_id)
        assert session.query(FinancialRecord).one().direction == "client_in"

    def test_zero_and_unparseable_amounts_skipped(self, session, project_factory):
        p = project_factory(name="P")
        _doc(session, p, "Q.pdf", "stuff")
        session.commit()
        ext = MockStructuredExtractor(
            by_name={
                "Q.pdf": {
                    "document_type": "construction_quote",
                    "is_transactional": True,
                    "summary": "q",
                    "records": [
                        {
                            "amount": 0,
                            "currency": None,
                            "direction": "client_in",
                            "record_kind": "total",
                            "description": "",
                            "quoted_excerpt": "",
                            "confidence": 0.5,
                        },
                    ],
                }
            }
        )
        batch = extract_financials_structured_for_project(session, ext, p.canonical_id)
        assert batch.created_count == 0
