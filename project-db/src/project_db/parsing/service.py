"""Persist a parse: bytes -> DocumentParse + EvidenceSpan + DocumentText.

This is the single seam future work plugs into. A caller (Drive sync, a CLI, a
re-parse job) fetches a document's bytes and calls `parse_document_content`;
routing, evidence persistence, and the `DocumentText` compatibility write-back
all happen here. It is ADDITIVE -- it does not touch the live Drive
`extract_and_store` path; both can coexist until a later slice migrates the live
sync onto this seam.

Outcomes are recorded, never raised: a missing parser -> `status='skipped'`, a
parser exception -> `status='failed'` with the error text, success ->
`status='success'` with rendered_text + structured_json + evidence spans, and a
synced `DocumentText` row. Callers commit.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable, Iterator

from sqlalchemy.orm import Session

from project_db.db.models.docs import EVIDENCE_TYPES, Document, DocumentParse, EvidenceSpan
from project_db.db.parse_compat import write_document_text_from_parse
from project_db.parsing.router import get_parser_for


def _as_bytes(content: bytes | str) -> bytes:
    if isinstance(content, (bytes, bytearray)):
        return bytes(content)
    return content.encode("utf-8", errors="replace")


def _approx_token_count(text: str | None) -> int | None:
    if not text:
        return None
    return max(1, len(text) // 4)


def parse_document_content(
    session: Session,
    *,
    document: Document,
    content: bytes | str,
    mime: str | None = None,
    filename: str | None = None,
    write_text: bool = True,
) -> DocumentParse:
    """Route, parse, and persist one document's *content*.

    Always returns a `DocumentParse` row (flushed; the caller commits). When
    *write_text* is set and the parse succeeds, the legacy `DocumentText` row is
    upserted from the rendering so existing reports/search keep working.
    """
    mime = mime if mime is not None else getattr(document, "mime_type", None)
    filename = filename if filename is not None else getattr(document, "name", None)
    raw = _as_bytes(content) if content is not None else b""
    source_hash = hashlib.sha256(raw).hexdigest() if raw else None

    parser = get_parser_for(mime=mime, filename=filename)
    if parser is None:
        parse = DocumentParse(
            document_id=document.canonical_id,
            parser_name="router",
            source_hash=source_hash,
            status="skipped",
            error=f"no parser for mime={mime!r} filename={filename!r}",
        )
        session.add(parse)
        session.flush()
        return parse

    try:
        parsed = parser.parse(raw, doc_name=filename or "", mime=mime)
    except Exception as exc:
        parse = DocumentParse(
            document_id=document.canonical_id,
            parser_name=parser.name,
            parser_version=str(parser.version),
            source_hash=source_hash,
            status="failed",
            error=f"{type(exc).__name__}: {exc}",
        )
        session.add(parse)
        session.flush()
        return parse

    parse = DocumentParse(
        document_id=document.canonical_id,
        parser_name=parser.name,
        parser_version=str(parser.version),
        source_hash=source_hash,
        status="success",
        rendered_text=parsed.rendered_text,
        structured_json=json.dumps(parsed.structured, default=str),
        token_count=_approx_token_count(parsed.rendered_text),
    )
    session.add(parse)
    session.flush()

    for ev in parsed.evidence_spans:
        if ev.evidence_type not in EVIDENCE_TYPES:
            # Defensive: a parser emitted an unknown evidence_type; skip rather
            # than poison the parse. (Parsers should only emit EVIDENCE_TYPES.)
            continue
        session.add(
            EvidenceSpan(
                document_id=document.canonical_id,
                parse_id=parse.id,
                evidence_type=ev.evidence_type,
                locator_json=json.dumps(ev.locator, default=str)
                if ev.locator is not None
                else None,
                content_text=ev.content_text,
                content_json=(
                    json.dumps(ev.content_json, default=str)
                    if ev.content_json is not None
                    else None
                ),
                bbox_json=json.dumps(ev.bbox, default=str) if ev.bbox is not None else None,
                confidence=ev.confidence,
            )
        )
    session.flush()

    if write_text:
        write_document_text_from_parse(session, parse)

    return parse


def parse_documents(
    session: Session,
    items: Iterable[tuple[Document, bytes | str]],
    *,
    write_text: bool = True,
    commit_every: int = 50,
) -> Iterator[DocumentParse]:
    """Pipeline helper: parse a stream of (document, content) pairs.

    Yields each `DocumentParse` as it is produced and commits periodically, so a
    future batch/re-parse job over many documents has a ready entry point. Pure
    over the seam above -- no source-system coupling (the caller supplies bytes).
    """
    for i, (document, content) in enumerate(items, 1):
        parse = parse_document_content(
            session, document=document, content=content, write_text=write_text
        )
        yield parse
        if commit_every and i % commit_every == 0:
            session.commit()
    session.commit()
