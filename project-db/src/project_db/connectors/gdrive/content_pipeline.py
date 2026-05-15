"""Drive-file -> DocumentText pipeline.

Wraps the byte-level extractors with the policy a real sync needs:
  - skip files over 10 MB without downloading them
  - skip mime types we don't know how to read
  - call the right Drive endpoint (export vs. get_media) per mime
  - never raise -- every Document we look at gets a DocumentText row,
    even if only to record the skip/failure decision

This is the only place that talks to both the Drive client and the
DocumentText model.  The byte parsers in ``extractors.py`` are pure.
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from project_db.connectors.gdrive.client import GDriveClient
from project_db.connectors.gdrive.extractors import (
    GOOGLE_NATIVE_MIMES,
    SUPPORTED_MIMES,
    estimate_tokens,
    extract_text,
)
from project_db.db.models import Document, DocumentText

logger = logging.getLogger(__name__)

# Per STRATEGY.md: cap at 10 MB.  Above this we record 'skipped-size'
# without downloading the file.
MAX_BYTES = 10 * 1024 * 1024


def extract_and_store(
    *,
    session: Session,
    client: GDriveClient,
    document: Document,
    overwrite: bool = False,
) -> DocumentText:
    """Extract content for *document* and upsert a DocumentText row.

    Returns the DocumentText row (committed by the caller).  Always returns
    a row -- skip/failure cases record themselves rather than raising, so
    callers can iterate over a whole library and inspect outcomes from the
    DB afterwards.

    overwrite=False (default) is a no-op when a DocumentText row already
    exists.  overwrite=True replaces it (useful when re-running with a
    fixed extractor).
    """
    existing = (
        session.query(DocumentText)
        .filter_by(document_id=document.canonical_id)
        .one_or_none()
    )
    if existing is not None and not overwrite:
        return existing

    text, method, tokens = _decide_and_extract(client, document)

    if existing is None:
        row = DocumentText(
            document_id=document.canonical_id,
            extracted_text=text,
            extraction_method=method,
            token_count=tokens,
            extracted_at=datetime.utcnow(),
        )
        session.add(row)
    else:
        existing.extracted_text = text
        existing.extraction_method = method
        existing.token_count = tokens
        existing.extracted_at = datetime.utcnow()
        row = existing

    session.flush()
    return row


def _decide_and_extract(
    client: GDriveClient,
    document: Document,
) -> tuple[str | None, str, int | None]:
    """Decide whether to download, do so, and run the right extractor.

    Returns (text, method, token_count).  Never raises -- every error
    becomes a 'failed-*' method label so the caller can tell skip from
    failure when scanning DocumentText later.
    """
    mime = document.mime_type or ""
    file_id = document.storage_ref or ""

    if not file_id:
        return None, "failed-no-storage-ref", None

    if mime not in SUPPORTED_MIMES:
        return None, "skipped-mime", None

    # Size check applies only to non-Google-native files.  Google-native
    # docs have no .size_bytes on Document (Drive doesn't report a size for
    # them) and Drive caps exports at 10 MB on its side anyway.
    if mime not in GOOGLE_NATIVE_MIMES:
        size = document.size_bytes or 0
        if size > MAX_BYTES:
            return None, "skipped-size", None

    # Fetch bytes via the right endpoint.
    try:
        if mime in GOOGLE_NATIVE_MIMES:
            raw = client.export_google_doc(file_id, GOOGLE_NATIVE_MIMES[mime])
        else:
            raw = client.download_file(file_id)
    except Exception as exc:  # noqa: BLE001
        logger.warning("[GDRIVE] download failed for %s (%s): %s", file_id, mime, exc)
        return None, "failed-download", None

    text, method = extract_text(raw, mime)
    tokens = estimate_tokens(text)
    return text, method, tokens
