"""Slice 6b: the financial LLM extractor reads the structured evidence bundle,
links every row to its EvidenceSpan, and escalates low-confidence docs.

No OpenAI: a recording mock extractor captures the text it was handed so we can
assert it received the labelled bundle (not the flat blob), and the evidence
link is asserted on the written FinancialLineItem rows.
"""

from __future__ import annotations

import json
from typing import Any

from project_db.ai.financial_llm_extractor import (
    FinancialLineExtractor,
    populate_ledger_llm_for_document,
)
from project_db.db.models import FinancialLineItem
from project_db.db.models.docs import Document, DocumentParse, DocumentText, EvidenceSpan

_RESULT = {
    "document_type": "construction_quote",
    "ledger_side": "revenue",
    "unit": None,
    "currency": "CAD",
    "stated_total": 1000.0,
    "is_summary_rollup": False,
    "line_items": [
        {
            "description": "Demolition",
            "division_code": "02",
            "masterformat_hint": None,
            "amount": 1000.0,
            "amount_type": "total",
            "quoted_excerpt": "Demolition $1,000.00",
            "confidence": 0.9,
        }
    ],
}


class _RecordingExtractor(FinancialLineExtractor):
    name = "recording"

    def __init__(self, result: dict[str, Any]) -> None:
        self.result = result
        self.seen: list[str] = []

    def extract(self, *, doc_name: str, doc_text: str, company_name: str) -> dict[str, Any]:
        self.seen.append(doc_text)
        return self.result


def _doc(session, name="927 QUOTE.csv", mime="text/csv"):
    d = Document(name=name, url=f"https://drive/{name}", mime_type=mime)
    session.add(d)
    session.commit()
    return d


def _flat_text(session, doc, text="Demolition 1000.00"):
    dt = DocumentText(
        document_id=doc.canonical_id,
        extracted_text=text,
        extraction_method="legacy",
        token_count=5,
    )
    session.add(dt)
    session.commit()
    return dt


def _parse_with_table(session, doc, *, header_conf=1.0):
    p = DocumentParse(
        document_id=doc.canonical_id,
        parser_name="csv",
        parser_version="1",
        status="success",
        rendered_text="x",
    )
    session.add(p)
    session.commit()
    span = EvidenceSpan(
        document_id=doc.canonical_id,
        parse_id=p.id,
        evidence_type="table_region",
        locator_json=json.dumps({"sheet": "Quote", "range": "B4:F29", "header_row": 6}),
        content_json=json.dumps(
            {
                "sheet": "Quote",
                "headers": ["Description", "Total Amount"],
                "rows_sample": [{"Description": "Demolition", "Total Amount": "1000.00"}],
                "rows_preview": [["Demolition", "1000.00"]],
                "header_confidence": header_conf,
            }
        ),
        confidence=header_conf,
    )
    session.add(span)
    session.commit()
    return p, span


def test_extractor_reads_bundle_and_links_evidence(session):
    doc = _doc(session)
    dt = _flat_text(session, doc)
    _p, span = _parse_with_table(session, doc)
    ext = _RecordingExtractor(_RESULT)

    res = populate_ledger_llm_for_document(session, doc, dt, ext, company_name="Alta")
    session.commit()

    # The model was handed the labelled evidence bundle, not the flat blob.
    assert "## Table" in ext.seen[0]
    assert "Total Amount" in ext.seen[0]

    rows = session.query(FinancialLineItem).filter_by(document_id=doc.canonical_id).all()
    assert len(rows) == 1
    assert res.ingestion_status == "parsed"
    # Every written row cites the structured span it came from.
    assert rows[0].evidence_span_id == span.id
    assert json.loads(rows[0].evidence_locator_json)["range"] == "B4:F29"
    assert rows[0].amount_verified is True


def test_falls_back_to_flat_text_without_a_parse(session):
    doc = _doc(session)
    dt = _flat_text(session, doc)
    # No DocumentParse -> no bundle -> legacy flat-text path, no evidence link.
    ext = _RecordingExtractor(_RESULT)

    res = populate_ledger_llm_for_document(session, doc, dt, ext, company_name="Alta")
    session.commit()

    assert ext.seen[0] == "Demolition 1000.00"  # the flat blob, verbatim
    assert "## Table" not in ext.seen[0]
    rows = session.query(FinancialLineItem).filter_by(document_id=doc.canonical_id).all()
    assert res.ingestion_status == "parsed"
    assert rows[0].evidence_span_id is None
    assert rows[0].evidence_locator_json is None


def test_low_confidence_escalates_to_strong_extractor(session):
    doc = _doc(session)
    dt = _flat_text(session, doc)
    _parse_with_table(session, doc, header_conf=0.3)  # low -> escalate
    weak = _RecordingExtractor(_RESULT)
    strong = _RecordingExtractor(_RESULT)

    populate_ledger_llm_for_document(
        session, doc, dt, weak, company_name="Alta", strong_extractor=strong
    )
    session.commit()

    assert strong.seen and not weak.seen  # the strong model handled this doc


def test_high_confidence_does_not_escalate(session):
    doc = _doc(session)
    dt = _flat_text(session, doc)
    _parse_with_table(session, doc, header_conf=1.0)  # clear header -> no escalation
    weak = _RecordingExtractor(_RESULT)
    strong = _RecordingExtractor(_RESULT)

    populate_ledger_llm_for_document(
        session, doc, dt, weak, company_name="Alta", strong_extractor=strong
    )
    session.commit()

    assert weak.seen and not strong.seen


# Slice 7: evidence-grounding gate -- a reconcile on a hallucinated total is rejected.
_HALLUCINATED = {
    "document_type": "construction_quote",
    "ledger_side": "revenue",
    "unit": None,
    "currency": "CAD",
    "stated_total": 9999.0,  # NOT a value present in the table evidence
    "is_summary_rollup": False,
    "line_items": [
        {
            "description": "Phantom scope",
            "division_code": "02",
            "masterformat_hint": None,
            "amount": 9999.0,  # lines sum to the stated total -> reconcile passes...
            "amount_type": "total",
            "quoted_excerpt": "Phantom $9,999.00",
            "confidence": 0.9,
        }
    ],
}


def test_quarantines_when_total_not_in_evidence(session):
    doc = _doc(session)
    dt = _flat_text(session, doc, text="")  # force the bundle to be the only input
    _parse_with_table(session, doc)  # table evidence contains 1000.00, NOT 9999
    ext = _RecordingExtractor(_HALLUCINATED)

    res = populate_ledger_llm_for_document(session, doc, dt, ext, company_name="Alta")
    session.commit()

    # Reconciles ($9,999 lines == $9,999 stated) but the total is absent from the
    # cited evidence -> Slice-7 gate quarantines it instead of writing it.
    assert res.ingestion_status == "quarantined"
    assert res.ingestion_reason == "total_not_in_evidence"
    assert session.query(FinancialLineItem).filter_by(document_id=doc.canonical_id).count() == 0


def test_grounded_total_still_writes(session):
    doc = _doc(session)
    dt = _flat_text(session, doc, text="")
    _parse_with_table(session, doc)  # evidence contains 1000.00
    grounded = {
        **_HALLUCINATED,
        "stated_total": 1000.0,  # present in the table evidence
        "line_items": [{**_HALLUCINATED["line_items"][0], "amount": 1000.0}],
    }
    ext = _RecordingExtractor(grounded)

    res = populate_ledger_llm_for_document(session, doc, dt, ext, company_name="Alta")
    session.commit()

    assert res.ingestion_status == "parsed"
    assert session.query(FinancialLineItem).filter_by(document_id=doc.canonical_id).count() == 1
