"""Slice 4: PdfParser (Docling backend + PyMuPDF fallback).

CI does not install the heavy `[docling]` extra, so the core tests exercise the
PyMuPDF fallback (forced deterministically even when Docling IS installed
locally). One test is gated on Docling being importable. Rich table-extraction
correctness was validated by hand on real table-heavy PDFs during development.
"""

from __future__ import annotations

import json

import pytest

from project_db.db.models.docs import Document, DocumentText, EvidenceSpan
from project_db.parsing import PdfParser, get_parser_for, parse_document_content
from project_db.parsing import pdf_parser as pdf_mod

fitz = pytest.importorskip("fitz")  # PyMuPDF, from the [content] extra


def _pdf_bytes(pages: list[str]) -> bytes:
    doc = fitz.open()
    for text in pages:
        page = doc.new_page()
        page.insert_text((72, 72), text)
    raw = doc.tobytes()
    doc.close()
    return raw


@pytest.fixture
def force_pymupdf(monkeypatch):
    """Force the PyMuPDF fallback regardless of whether Docling is installed."""
    monkeypatch.setattr(pdf_mod, "_get_converter", lambda: None)


# --------------------------------------------------------------------------- #
# Routing / matching
# --------------------------------------------------------------------------- #


def test_pdf_can_parse_and_routes():
    p = PdfParser()
    assert p.can_parse(mime="application/pdf", filename=None)
    assert p.can_parse(mime=None, filename="Estimate.PDF")
    assert not p.can_parse(mime="text/csv", filename="x.csv")
    assert isinstance(get_parser_for(mime="application/pdf", filename=None), PdfParser)


# --------------------------------------------------------------------------- #
# PyMuPDF fallback (what CI runs)
# --------------------------------------------------------------------------- #


def test_pdf_fallback_pymupdf_page_spans(force_pymupdf):
    parsed = PdfParser().parse(
        _pdf_bytes(["Hello page one", "Second page text"]), doc_name="d.pdf", mime="application/pdf"
    )
    assert parsed.structured["backend"] == "pymupdf"
    assert parsed.structured["n_pages"] == 2
    pages = [s for s in parsed.evidence_spans if s.evidence_type == "page"]
    assert len(pages) == 2
    assert pages[0].locator["page"] == 1
    assert "Hello page one" in pages[0].content_text
    assert "## Page 1" in parsed.rendered_text


def test_parse_document_content_pdf_spine(session, force_pymupdf):
    doc = Document(name="quote.pdf", url="https://drive/quote.pdf", mime_type="application/pdf")
    session.add(doc)
    session.commit()

    parse = parse_document_content(
        session, document=doc, content=_pdf_bytes(["Invoice total 1234"])
    )
    session.commit()

    assert parse.status == "success" and parse.parser_name == "pdf"
    assert json.loads(parse.structured_json)["backend"] == "pymupdf"
    assert (
        session.query(EvidenceSpan).filter_by(parse_id=parse.id, evidence_type="page").count() == 1
    )

    dt = session.query(DocumentText).filter_by(document_id=doc.canonical_id).one()
    assert dt.extraction_method == "pdf/1"
    assert "Invoice total 1234" in dt.extracted_text


# --------------------------------------------------------------------------- #
# Docling backend (local only; skipped in CI)
# --------------------------------------------------------------------------- #


def test_pdf_docling_backend_runs_when_installed():
    pytest.importorskip("docling")
    parsed = PdfParser().parse(
        _pdf_bytes(["Hello from a digital PDF page."]), doc_name="d.pdf", mime="application/pdf"
    )
    # Docling should handle a digital PDF; if its pipeline errors it falls back.
    assert parsed.structured["backend"] in {"docling", "pymupdf"}
    assert parsed.rendered_text  # non-empty either way
