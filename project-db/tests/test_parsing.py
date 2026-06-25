"""Slice 2: parser abstraction + MIME routing + CSV parser, and the persisted
spine (Document -> DocumentParse -> EvidenceSpan -> DocumentText).

Uses the shared in-memory `session` fixture (conftest). These tests do not need
FK cascade (covered in test_document_parse.py), only that the spine persists.
"""

from __future__ import annotations

import json

from project_db.db.models.docs import Document, DocumentParse, DocumentText, EvidenceSpan
from project_db.parsing import (
    CsvParser,
    ParsedDocument,
    get_parser_for,
    parse_document_content,
    parse_documents,
)
from project_db.parsing import service as parsing_service

CSV_BYTES = b"Item,Qty,Price\nWindow,2,1080.45\nDoor,1,559.99\n"
# Quebec/French: semicolon delimiter + decimal commas inside quoted fields.
FR_CSV_BYTES = b'Description;Montant\n"Plomberie";"43 090,33"\n"Demolition";"1 600,00"\n'


def _doc(session, name="Quotes.csv", mime="text/csv") -> Document:
    d = Document(name=name, url=f"https://drive/{name}", mime_type=mime)
    session.add(d)
    session.commit()
    return d


# --------------------------------------------------------------------------- #
# CSV parser (pure)
# --------------------------------------------------------------------------- #


def test_csv_parser_parses_table():
    parsed = CsvParser().parse(CSV_BYTES, doc_name="Quotes.csv", mime="text/csv")
    assert isinstance(parsed, ParsedDocument)
    assert parsed.structured["headers"] == ["Item", "Qty", "Price"]
    assert parsed.structured["n_rows"] == 2
    assert parsed.structured["delimiter"] == ","
    assert "|" in parsed.rendered_text  # Markdown table, not a flat blob
    assert len(parsed.evidence_spans) == 1
    span = parsed.evidence_spans[0]
    assert span.evidence_type == "table_region"
    assert span.content_json["headers"] == ["Item", "Qty", "Price"]
    assert span.content_json["rows_sample"][0]["Item"] == "Window"


def test_csv_parser_detects_semicolon_delimiter():
    parsed = CsvParser().parse(FR_CSV_BYTES, doc_name="fr.csv", mime="text/csv")
    assert parsed.structured["delimiter"] == ";"
    assert parsed.structured["headers"] == ["Description", "Montant"]
    assert parsed.structured["n_rows"] == 2
    # The French decimal-comma amount stays intact inside the quoted field.
    assert parsed.evidence_spans[0].content_json["rows_sample"][0]["Montant"] == "43 090,33"


def test_csv_parser_empty_input():
    parsed = CsvParser().parse(b"\n\n", doc_name="empty.csv", mime="text/csv")
    assert parsed.structured["n_rows"] == 0
    assert parsed.evidence_spans == []
    assert parsed.rendered_text == ""


def test_csv_parser_can_parse_by_extension_and_mime():
    p = CsvParser()
    assert p.can_parse(mime="text/csv", filename=None)
    assert p.can_parse(mime=None, filename="export.CSV")
    assert p.can_parse(mime="text/csv; charset=utf-8", filename=None)
    assert not p.can_parse(mime="application/pdf", filename="x.pdf")


# --------------------------------------------------------------------------- #
# Routing
# --------------------------------------------------------------------------- #


def test_router_routes_csv_and_skips_others():
    assert isinstance(get_parser_for(mime="text/csv", filename=None), CsvParser)
    assert isinstance(get_parser_for(mime=None, filename="a.csv"), CsvParser)
    assert get_parser_for(mime="application/pdf", filename="a.pdf") is None


# --------------------------------------------------------------------------- #
# Persisted spine
# --------------------------------------------------------------------------- #


def test_parse_document_content_writes_full_spine(session):
    doc = _doc(session)
    parse = parse_document_content(session, document=doc, content=CSV_BYTES)
    session.commit()

    assert parse.status == "success"
    assert parse.parser_name == "csv"
    assert parse.source_hash and len(parse.source_hash) == 64  # sha256 hex
    assert json.loads(parse.structured_json)["n_rows"] == 2

    spans = session.query(EvidenceSpan).filter_by(parse_id=parse.id).all()
    assert len(spans) == 1 and spans[0].evidence_type == "table_region"

    dt = session.query(DocumentText).filter_by(document_id=doc.canonical_id).one()
    assert dt.extraction_method == "csv/1"  # parser name + version
    assert "|" in dt.extracted_text
    assert dt.token_count is not None


def test_parse_document_content_skips_unsupported_mime(session):
    doc = _doc(session, name="plan.pdf", mime="application/pdf")
    parse = parse_document_content(session, document=doc, content=b"%PDF-1.7 ...")
    session.commit()

    assert parse.status == "skipped"
    assert "no parser" in (parse.error or "")
    assert session.query(EvidenceSpan).filter_by(parse_id=parse.id).count() == 0
    # No DocumentText written for a skipped parse.
    assert session.query(DocumentText).filter_by(document_id=doc.canonical_id).count() == 0


def test_parse_document_content_records_failure(session, monkeypatch):
    class _Boom:
        name = "boom"
        version = "1"

        def can_parse(self, *, mime, filename):
            return True

        def parse(self, content, *, doc_name, mime):
            raise ValueError("kaboom")

    monkeypatch.setattr(parsing_service, "get_parser_for", lambda **_: _Boom())
    doc = _doc(session)
    parse = parse_document_content(session, document=doc, content=CSV_BYTES)
    session.commit()

    assert parse.status == "failed"
    assert "kaboom" in (parse.error or "")
    assert parse.parser_name == "boom"
    # A failed parse does not overwrite DocumentText.
    assert session.query(DocumentText).filter_by(document_id=doc.canonical_id).count() == 0


def test_parse_documents_pipeline(session):
    d1 = _doc(session, name="a.csv")
    d2 = _doc(session, name="b.csv")
    parses = list(parse_documents(session, [(d1, CSV_BYTES), (d2, FR_CSV_BYTES)]))

    assert len(parses) == 2
    assert all(p.status == "success" for p in parses)
    assert session.query(DocumentParse).count() == 2
    assert session.query(DocumentText).count() == 2
