"""Compatibility bridge: write `DocumentText` from a successful `DocumentParse`.

`DocumentText` is no longer the canonical parse artifact -- `DocumentParse` is
(see EVIDENCE_REFACTOR.md). But every existing report, search, RAG-embedding,
and financial extractor still reads `DocumentText`, so after a parser writes a
`DocumentParse`, it calls this helper to keep the old 1:1 `DocumentText` row in
sync. This is the seam that lets new parsers land without breaking the app.

Additive only: this never deletes the existing Drive `extract_and_store` path
(`connectors/gdrive/content_pipeline.py`). It upserts the same `DocumentText`
row that path maintains, mirroring its behavior.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy.orm import Session

from project_db.db.models.docs import DocumentParse, DocumentText


def _approx_token_count(text: str | None) -> int | None:
    """Cheap, deterministic token estimate (~4 chars/token).

    `DocumentText.token_count` is approximate by design; we avoid importing the
    Drive extractor's tokenizer so this DB-layer helper stays dependency-light.
    """
    if not text:
        return None
    return max(1, len(text) // 4)


def parse_extraction_method(parse: DocumentParse) -> str:
    """The `DocumentText.extraction_method` label for a parse: parser name,
    suffixed with the version when present (e.g. 'docling/2.1')."""
    name = parse.parser_name or "unknown"
    if parse.parser_version:
        return f"{name}/{parse.parser_version}"
    return name


def write_document_text_from_parse(
    session: Session,
    parse: DocumentParse,
    *,
    only_if_success: bool = True,
) -> DocumentText | None:
    """Upsert the `DocumentText` row for *parse*'s document from its rendering.

    - `extracted_text`    <- parse.rendered_text
    - `extraction_method` <- parser_name (+ '/' + parser_version)
    - `extracted_at`      <- now
    - `token_count`       <- approximate token count of rendered_text

    Returns the upserted `DocumentText` row (flushed, committed by the caller),
    or ``None`` when *only_if_success* is set and the parse did not succeed --
    we don't overwrite a good DocumentText with a failed/skipped parse's
    (usually empty) rendering. The caller decides whether to record failures.
    """
    if only_if_success and parse.status != "success":
        return None

    method = parse_extraction_method(parse)
    text = parse.rendered_text
    tokens = parse.token_count if parse.token_count is not None else _approx_token_count(text)

    existing = session.query(DocumentText).filter_by(document_id=parse.document_id).one_or_none()
    if existing is None:
        row = DocumentText(
            document_id=parse.document_id,
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
