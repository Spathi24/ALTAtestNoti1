"""Tests for Phase-1 Step-2: content extraction.

Covers four layers:
  - Pure byte parsers (extractors.py) -- one per mime
  - Pipeline policy (content_pipeline.py) -- skip/size/mime decisions
  - Connector wiring -- the extract_content config flag
  - CLI -- argument parsing and the --missing-only / --overwrite paths

Heavy parser libs (pymupdf, python-docx, openpyxl) are guarded with
pytest.importorskip so the suite still runs cleanly without the
[content] optional dependency group installed.
"""
from __future__ import annotations

import io
import uuid
from unittest.mock import MagicMock

import pytest

from project_db.connectors.gdrive import extractors
from project_db.connectors.gdrive.content_pipeline import (
    MAX_BYTES,
    extract_and_store,
)
from project_db.db.models import Document, DocumentText, Project
from project_db.db.models.work import ProjectStatus


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_doc(
    session,
    client_factory,
    *,
    mime: str,
    size: int | None = 1024,
    storage_ref: str = "f1",
) -> Document:
    c = client_factory(name="C")
    p = Project(
        name="P", code="P", status=ProjectStatus.ACTIVE,
        client_id=c.canonical_id,
    )
    session.add(p)
    session.commit()
    doc = Document(
        name="x", url="about:blank",
        mime_type=mime, storage_ref=storage_ref, size_bytes=size,
        project_id=p.canonical_id,
    )
    session.add(doc)
    session.commit()
    return doc


# ---------------------------------------------------------------------------
# Pure byte parsers
# ---------------------------------------------------------------------------


class TestExtractGdocExport:
    def test_decodes_utf8(self):
        text, method = extractors.extract_gdoc_export("Hello world".encode("utf-8"))
        assert text == "Hello world"
        assert method == "gdoc-export"

    def test_empty_bytes_yields_none(self):
        text, method = extractors.extract_gdoc_export(b"")
        assert text is None
        assert method == "gdoc-export"

    def test_replaces_bad_bytes(self):
        text, method = extractors.extract_gdoc_export(b"ok \xff\xfe more")
        assert text is not None and "ok" in text and "more" in text
        assert method == "gdoc-export"


class TestExtractGsheetExport:
    def test_csv_passthrough(self):
        raw = b"a,b,c\n1,2,3\n"
        text, method = extractors.extract_gsheet_export(raw)
        assert "a,b,c" in text and "1,2,3" in text
        assert method == "gsheet-export"


class TestExtractPdf:
    def test_real_pdf_roundtrip(self):
        fitz = pytest.importorskip("fitz")  # PyMuPDF
        doc = fitz.open()
        page = doc.new_page()
        page.insert_text((72, 72), "ALTA test PDF body")
        buf = io.BytesIO()
        doc.save(buf)
        doc.close()

        text, method = extractors.extract_pdf(buf.getvalue())
        assert text is not None and "ALTA test PDF body" in text
        assert method == "pdf-pymupdf"

    def test_garbage_bytes_fail_clean(self):
        pytest.importorskip("fitz")
        text, method = extractors.extract_pdf(b"not a pdf")
        assert text is None
        assert method == "failed-parse"


class TestExtractDocx:
    def test_real_docx_roundtrip(self):
        docx = pytest.importorskip("docx")
        d = docx.Document()
        d.add_paragraph("First paragraph")
        d.add_paragraph("Second paragraph with content")
        table = d.add_table(rows=1, cols=2)
        table.rows[0].cells[0].text = "Item"
        table.rows[0].cells[1].text = "Value"
        buf = io.BytesIO()
        d.save(buf)

        text, method = extractors.extract_docx(buf.getvalue())
        assert "First paragraph" in text
        assert "Second paragraph" in text
        assert "Item" in text and "Value" in text
        assert method == "docx-python"

    def test_garbage_fails_clean(self):
        pytest.importorskip("docx")
        text, method = extractors.extract_docx(b"not a docx")
        assert text is None
        assert method == "failed-parse"


class TestExtractXlsx:
    def test_real_xlsx_roundtrip(self):
        openpyxl = pytest.importorskip("openpyxl")
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Budget"
        ws.append(["Item", "Amount"])
        ws.append(["Concrete", 12000])
        ws.append(["Lumber", 8500])
        buf = io.BytesIO()
        wb.save(buf)

        text, method = extractors.extract_xlsx(buf.getvalue())
        assert "Budget" in text  # sheet name header
        assert "Concrete" in text and "12000" in text
        assert method == "xlsx-openpyxl"


class TestEstimateTokens:
    def test_none_input(self):
        assert extractors.estimate_tokens(None) is None
        assert extractors.estimate_tokens("") is None

    def test_short_text(self):
        # "hello world" = 11 chars -> 11//4 = 2 (floor with minimum 1)
        assert extractors.estimate_tokens("hello world") == 2

    def test_long_text(self):
        # 4000 chars -> ~1000 tokens
        assert extractors.estimate_tokens("a" * 4000) == 1000


class TestExtractTextDispatch:
    def test_unsupported_mime_returns_skip(self):
        text, method = extractors.extract_text(b"...", "image/heic")
        assert text is None
        assert method == "skipped-mime"

    def test_supported_mime_dispatches(self):
        text, method = extractors.extract_text(b"hello", "application/vnd.google-apps.document")
        assert text == "hello"
        assert method == "gdoc-export"


# ---------------------------------------------------------------------------
# Pipeline policy
# ---------------------------------------------------------------------------


class TestPipelinePolicy:
    def test_unsupported_mime_skipped_without_download(self, session, org, client_factory):
        doc = _make_doc(session, client_factory, mime="image/heic", size=1024)
        client = MagicMock()
        row = extract_and_store(session=session, client=client, document=doc)
        session.commit()

        assert row.extraction_method == "skipped-mime"
        assert row.extracted_text is None
        client.download_file.assert_not_called()
        client.export_google_doc.assert_not_called()

    def test_oversize_pdf_skipped_without_download(self, session, org, client_factory):
        doc = _make_doc(
            session, client_factory,
            mime="application/pdf", size=MAX_BYTES + 1,
        )
        client = MagicMock()
        row = extract_and_store(session=session, client=client, document=doc)
        session.commit()

        assert row.extraction_method == "skipped-size"
        client.download_file.assert_not_called()

    def test_google_doc_uses_export_endpoint(self, session, org, client_factory):
        doc = _make_doc(
            session, client_factory,
            mime="application/vnd.google-apps.document",
            size=None,
            storage_ref="gdoc_xyz",
        )
        client = MagicMock()
        client.export_google_doc.return_value = b"Hello from Google Docs"

        row = extract_and_store(session=session, client=client, document=doc)
        session.commit()

        client.export_google_doc.assert_called_once_with("gdoc_xyz", "text/plain")
        client.download_file.assert_not_called()
        assert row.extracted_text == "Hello from Google Docs"
        assert row.extraction_method == "gdoc-export"
        assert row.token_count == max(1, len("Hello from Google Docs") // 4)

    def test_pdf_uses_download_endpoint(self, session, org, client_factory):
        pytest.importorskip("fitz")
        import fitz
        d = fitz.open()
        d.new_page().insert_text((72, 72), "Pipeline PDF test")
        buf = io.BytesIO()
        d.save(buf)
        d.close()

        doc = _make_doc(
            session, client_factory,
            mime="application/pdf", size=len(buf.getvalue()),
            storage_ref="pdf_42",
        )
        client = MagicMock()
        client.download_file.return_value = buf.getvalue()

        row = extract_and_store(session=session, client=client, document=doc)
        session.commit()

        client.download_file.assert_called_once_with("pdf_42")
        client.export_google_doc.assert_not_called()
        assert "Pipeline PDF test" in row.extracted_text
        assert row.extraction_method == "pdf-pymupdf"

    def test_download_failure_recorded_not_raised(self, session, org, client_factory):
        doc = _make_doc(
            session, client_factory,
            mime="application/pdf", size=1024, storage_ref="boom",
        )
        client = MagicMock()
        client.download_file.side_effect = RuntimeError("network down")
        row = extract_and_store(session=session, client=client, document=doc)
        session.commit()
        assert row.extraction_method == "failed-download"
        assert row.extracted_text is None

    def test_trashed_document_skipped_without_download(self, session, org, client_factory):
        """A trashed Document gets a skipped-trashed marker, no API call."""
        doc = _make_doc(
            session, client_factory,
            mime="application/pdf", size=1024, storage_ref="trash_me",
        )
        doc.is_trashed = True
        session.commit()

        client = MagicMock()
        row = extract_and_store(session=session, client=client, document=doc)
        session.commit()
        assert row.extraction_method == "skipped-trashed"
        client.download_file.assert_not_called()
        client.export_google_doc.assert_not_called()

    def test_no_storage_ref_fails_clean(self, session, org, client_factory):
        doc = _make_doc(
            session, client_factory,
            mime="application/pdf", size=1024, storage_ref=None,
        )
        client = MagicMock()
        row = extract_and_store(session=session, client=client, document=doc)
        session.commit()
        assert row.extraction_method == "failed-no-storage-ref"

    def test_missing_only_is_noop_when_row_exists(self, session, org, client_factory):
        doc = _make_doc(session, client_factory, mime="application/pdf", size=1024)
        session.add(DocumentText(
            document_id=doc.canonical_id,
            extracted_text="OLD",
            extraction_method="pdf-pymupdf",
            token_count=1,
        ))
        session.commit()

        client = MagicMock()
        row = extract_and_store(session=session, client=client, document=doc, overwrite=False)
        session.commit()
        assert row.extracted_text == "OLD"
        client.download_file.assert_not_called()
        client.export_google_doc.assert_not_called()

    def test_overwrite_replaces_existing_row(self, session, org, client_factory):
        doc = _make_doc(
            session, client_factory,
            mime="application/vnd.google-apps.document",
            size=None, storage_ref="gdoc_1",
        )
        session.add(DocumentText(
            document_id=doc.canonical_id,
            extracted_text="STALE",
            extraction_method="gdoc-export",
            token_count=1,
        ))
        session.commit()

        client = MagicMock()
        client.export_google_doc.return_value = b"FRESH"
        row = extract_and_store(session=session, client=client, document=doc, overwrite=True)
        session.commit()
        assert row.extracted_text == "FRESH"
        # Still one row -- this is an update, not an insert.
        n = session.query(DocumentText).filter_by(document_id=doc.canonical_id).count()
        assert n == 1


# ---------------------------------------------------------------------------
# Connector wiring: extract_content flag
# ---------------------------------------------------------------------------


class TestConnectorExtractFlag:
    def _build_connector(self, session, org, *, extract_content: bool):
        from project_db.connectors.gdrive.client import GDriveClient
        from project_db.connectors.gdrive.connector import GDriveConnector

        svc = MagicMock()
        folder = {
            "id": "f1", "name": "923 Rockland",
            "mimeType": "application/vnd.google-apps.folder", "parents": ["root"],
        }
        # The file is a Google Doc -> export endpoint will be used.
        file = {
            "id": "file42",
            "name": "Contract.gdoc",
            "mimeType": "application/vnd.google-apps.document",
            "createdTime": "2026-04-01T10:00:00Z",
            "modifiedTime": "2026-05-10T15:30:00Z",
            "size": None,
            "parents": ["f1"],
            "webViewLink": "https://drive.google.com/d/file42",
            "owners": [{"emailAddress": "o@x.com", "displayName": "O"}],
        }
        list_mock = MagicMock()
        list_mock.execute.side_effect = [
            {"files": [folder], "nextPageToken": None},
            {"files": [file], "nextPageToken": None},
        ]
        svc.files.return_value.list.return_value = list_mock
        svc.changes.return_value.getStartPageToken.return_value.execute.return_value = {
            "startPageToken": "tok"
        }

        client = GDriveClient(service=svc)
        client.export_google_doc = MagicMock(return_value=b"Body of the contract")
        client.download_file = MagicMock(return_value=b"")

        return GDriveConnector(
            session=session,
            organization_id=org.canonical_id,
            config={
                "_client": client,
                "root_folder": "root",
                "extract_content": extract_content,
            },
        ), client

    def test_off_by_default_no_extraction_runs(self, session, org):
        connector, client = self._build_connector(session, org, extract_content=False)
        connector.sync()
        assert session.query(DocumentText).count() == 0
        client.export_google_doc.assert_not_called()

    def test_on_flag_creates_document_text(self, session, org):
        connector, client = self._build_connector(session, org, extract_content=True)
        connector.sync()
        rows = session.query(DocumentText).all()
        assert len(rows) == 1
        assert rows[0].extracted_text == "Body of the contract"
        assert rows[0].extraction_method == "gdoc-export"
        client.export_google_doc.assert_called_once()

    def test_on_flag_uses_resolver_entity_not_requery(self, session, org):
        """The connector should use resolver result.entity, not re-query by storage_ref.

        Sanity check: with extract_content on, exactly one Document exists
        (not two from a duplicate insert via re-query race) and exactly one
        DocumentText was created.
        """
        connector, _ = self._build_connector(session, org, extract_content=True)
        connector.sync()
        from project_db.db.models import Document
        assert session.query(Document).filter_by(storage_ref="file42").count() == 1
        assert session.query(DocumentText).count() == 1


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


class TestExtractContentCLI:
    def test_parser_accepts_extract_content_with_flags(self):
        from project_db.cli import build_parser

        ns = build_parser().parse_args([
            "extract-content", "--project", str(uuid.uuid4()),
            "--overwrite", "--limit", "10",
        ])
        assert ns.cmd == "extract-content"
        assert ns.overwrite is True
        assert ns.limit == 10

    def test_parser_defaults(self):
        from project_db.cli import build_parser

        ns = build_parser().parse_args(["extract-content"])
        assert ns.overwrite is False
        assert ns.limit is None
        assert ns.project is None
