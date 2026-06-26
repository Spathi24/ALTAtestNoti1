"""Slice 6a: the evidence-bundle reader that turns stored EvidenceSpans into
LLM-ready, citeable input (ai/evidence_bundle.py).

Pure over a DB read -- no LLM, no ledger writes. Uses the shared in-memory
`session` fixture.
"""

from __future__ import annotations

import json

from project_db.ai.evidence_bundle import build_evidence_bundle
from project_db.db.models.docs import Document, DocumentParse, EvidenceSpan


def _doc(
    session,
    name="Quote.xlsx",
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
):
    d = Document(name=name, url=f"https://drive/{name}", mime_type=mime)
    session.add(d)
    session.commit()
    return d


def _parse(session, doc, *, parser="xlsx", version="1", status="success"):
    p = DocumentParse(
        document_id=doc.canonical_id,
        parser_name=parser,
        parser_version=version,
        status=status,
        rendered_text="x",
    )
    session.add(p)
    session.commit()
    return p


def _table_span(session, doc, parse, *, headers, rows, header_conf, sheet="Quote", header_row=6):
    span = EvidenceSpan(
        document_id=doc.canonical_id,
        parse_id=parse.id,
        evidence_type="table_region",
        locator_json=json.dumps({"sheet": sheet, "range": "B4:F29", "header_row": header_row}),
        content_json=json.dumps(
            {
                "sheet": sheet,
                "headers": headers,
                "rows_sample": rows,
                "rows_preview": [list(r.values()) for r in rows],
                "header_confidence": header_conf,
            }
        ),
        confidence=header_conf,
    )
    session.add(span)
    session.commit()
    return span


def test_build_returns_none_without_a_successful_parse(session):
    doc = _doc(session)
    assert build_evidence_bundle(session, doc) is None
    # A failed parse also yields no bundle (caller falls back to flat text).
    _parse(session, doc, status="failed")
    assert build_evidence_bundle(session, doc) is None


def test_bundle_assembles_tables_with_locator_and_confidence(session):
    doc = _doc(session)
    p = _parse(session, doc)
    _table_span(
        session,
        doc,
        p,
        headers=["Description", "Material", "Labour", "Total"],
        rows=[
            {"Description": "Demolition", "Material": "", "Labour": "400.00", "Total": "1000.00"},
            {
                "Description": "Framing",
                "Material": "1200.00",
                "Labour": "800.00",
                "Total": "2000.00",
            },
        ],
        header_conf=1.0,
    )
    bundle = build_evidence_bundle(session, doc)
    assert bundle is not None
    assert bundle.parser_label == "xlsx/1"
    assert len(bundle.tables) == 1
    t = bundle.tables[0]
    assert t.sheet == "Quote"
    assert t.headers == ["Description", "Material", "Labour", "Total"]
    assert t.header_confidence == 1.0
    assert len(t.rows) == 2

    rendered = bundle.render_for_llm()
    # The rendering is a labelled Markdown table, not a flat blob.
    assert "## Table -- sheet 'Quote'" in rendered
    assert "| Description | Material | Labour | Total |" in rendered
    assert "Demolition" in rendered and "header confidence 1" in rendered


def test_low_confidence_gate(session):
    doc = _doc(session)
    p = _parse(session, doc)
    _table_span(session, doc, p, headers=["a", "b"], rows=[{"a": "1", "b": "2"}], header_conf=0.3)
    bundle = build_evidence_bundle(session, doc)
    assert bundle.min_header_confidence == 0.3
    assert bundle.is_low_confidence() is True  # 0.3 < 0.5 -> escalate in Slice 6b


def test_high_confidence_does_not_escalate(session):
    doc = _doc(session)
    p = _parse(session, doc)
    _table_span(session, doc, p, headers=["a", "b"], rows=[{"a": "1", "b": "2"}], header_conf=0.8)
    bundle = build_evidence_bundle(session, doc)
    assert bundle.is_low_confidence() is False


def test_primary_span_picks_table_with_most_rows(session):
    doc = _doc(session)
    p = _parse(session, doc)
    _table_span(session, doc, p, headers=["a"], rows=[{"a": "1"}], header_conf=1.0, sheet="Small")
    big = _table_span(
        session,
        doc,
        p,
        headers=["a"],
        rows=[{"a": "1"}, {"a": "2"}, {"a": "3"}],
        header_conf=1.0,
        sheet="Big",
    )
    bundle = build_evidence_bundle(session, doc)
    assert bundle.primary_span_id() == big.id


def test_pages_render_for_pdf_text(session):
    doc = _doc(session, name="Contract.pdf", mime="application/pdf")
    p = _parse(session, doc, parser="pdf")
    session.add(
        EvidenceSpan(
            document_id=doc.canonical_id,
            parse_id=p.id,
            evidence_type="page",
            locator_json=json.dumps({"page": 3}),
            content_text="The contract total is $76,503.96.",
        )
    )
    session.commit()
    bundle = build_evidence_bundle(session, doc)
    assert bundle.tables == []
    assert len(bundle.pages) == 1
    assert bundle.pages[0].page == 3
    # No tables -> not "low confidence" (that's a header-read signal, not absence).
    assert bundle.is_low_confidence() is False
    assert bundle.primary_span_id() == bundle.pages[0].span_id
    assert "76,503.96" in bundle.render_for_llm()


def test_empty_parse_yields_empty_bundle(session):
    doc = _doc(session)
    _parse(session, doc)  # success parse, but no spans (e.g. empty doc)
    bundle = build_evidence_bundle(session, doc)
    assert bundle is not None
    assert bundle.is_empty() is True
    assert bundle.primary_span_id() is None
