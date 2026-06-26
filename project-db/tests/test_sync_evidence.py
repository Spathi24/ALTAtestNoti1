"""Wiring backfill into live sync: `_parse_recent_evidence`.

Verifies the additive evidence-spine population that runs after `--sync`:
  - fast types (CSV/XLSX/Google Sheets) are parsed into DocumentParse + EvidenceSpan
  - it is downstream-SAFE: write_text=False, so the legacy DocumentText is untouched
  - idempotent: docs that already have a successful parse are skipped (no fetch)
  - PDFs are gated off by default (Docling cost) unless the env flag is set
"""

from __future__ import annotations

from datetime import datetime, timedelta
from unittest.mock import MagicMock

from sqlalchemy.orm import sessionmaker

import project_db.cli as cli
import project_db.connectors.gdrive.client as gdrive_client
import project_db.db as db_pkg
from project_db.db.models.docs import Document, DocumentParse, DocumentText, EvidenceSpan

CSV_BYTES = b"Item,Qty,Price\nWindow,2,1080.45\nDoor,1,559.99\n"


def _doc(session, project, *, name, mime, days_ago=1):
    d = Document(
        name=name,
        url=f"https://drive/{name}",
        mime_type=mime,
        storage_ref=f"file-{name}",
        project_id=project.canonical_id,
        is_trashed=False,
        modified_at_source=datetime.utcnow() - timedelta(days=days_ago),
    )
    session.add(d)
    session.commit()
    return d


def _wire(monkeypatch, db_engine, *, csv_bytes=CSV_BYTES):
    """Point the helper at the test DB and a mock Drive client; return the client."""
    factory = sessionmaker(bind=db_engine, expire_on_commit=False)
    monkeypatch.setattr(db_pkg, "get_session_factory", lambda: factory)
    fake = MagicMock()
    fake.download_file.return_value = csv_bytes
    fake.export_google_doc.return_value = csv_bytes
    monkeypatch.setattr(gdrive_client, "GDriveClient", lambda *a, **k: fake)
    return fake


def test_parse_recent_evidence_populates_spine_without_touching_documenttext(
    monkeypatch, session, db_engine, project_factory
):
    proj = project_factory(name="Active Job")
    doc = _doc(session, proj, name="Estimate.csv", mime="text/csv")

    _wire(monkeypatch, db_engine)
    cli._parse_recent_evidence(since_days=30)

    parse = session.query(DocumentParse).filter_by(document_id=doc.canonical_id).one()
    assert parse.status == "success"
    assert parse.parser_name == "csv"
    assert session.query(EvidenceSpan).filter_by(parse_id=parse.id).count() == 1
    # Downstream-safe: the legacy DocumentText is NOT written (Slice 6 owns that switch).
    assert session.query(DocumentText).filter_by(document_id=doc.canonical_id).count() == 0


def test_parse_recent_evidence_is_idempotent(monkeypatch, session, db_engine, project_factory):
    proj = project_factory(name="Active Job")
    doc = _doc(session, proj, name="Estimate.csv", mime="text/csv")
    session.add(DocumentParse(document_id=doc.canonical_id, parser_name="csv", status="success"))
    session.commit()

    fake = _wire(monkeypatch, db_engine)
    cli._parse_recent_evidence(since_days=30)

    # Already parsed -> no fetch, no second parse row.
    fake.download_file.assert_not_called()
    assert session.query(DocumentParse).filter_by(document_id=doc.canonical_id).count() == 1


def test_parse_recent_evidence_skips_pdf_by_default(
    monkeypatch, session, db_engine, project_factory
):
    proj = project_factory(name="Active Job")
    pdf = _doc(session, proj, name="Quote.pdf", mime="application/pdf")

    fake = _wire(monkeypatch, db_engine)
    monkeypatch.delenv("PROJECT_DB_PARSE_PDF_ON_SYNC", raising=False)
    cli._parse_recent_evidence(since_days=30)

    # PDF is gated off (Docling cost) -> not fetched, not parsed.
    fake.download_file.assert_not_called()
    assert session.query(DocumentParse).filter_by(document_id=pdf.canonical_id).count() == 0


def test_parse_recent_evidence_skips_old_documents(
    monkeypatch, session, db_engine, project_factory
):
    proj = project_factory(name="Active Job")
    old = _doc(session, proj, name="Old.csv", mime="text/csv", days_ago=90)

    _wire(monkeypatch, db_engine)
    cli._parse_recent_evidence(since_days=30)

    assert session.query(DocumentParse).filter_by(document_id=old.canonical_id).count() == 0
