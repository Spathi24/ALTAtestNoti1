"""Paragraph-aware text chunking for embedding.

Splits a document's extracted text into ~``target_tokens``-sized chunks at
paragraph boundaries, with a small token overlap so a clause split across a
boundary is still retrievable from either side.  Pure functions, no I/O.

Token counting uses ``tiktoken`` (``cl100k_base``, the encoding the v3
embedding models use) when available, falling back to a cheap chars/4 estimate
so the chunker -- and the test suite -- never depends on a network download.
The fallback only affects WHERE boundaries land, never correctness.
"""
from __future__ import annotations

from typing import Any, Callable

# tiktoken's encoding is loaded lazily + cached; if it (or its vocab download)
# is unavailable we fall back to a heuristic.  Module-level cache so we try the
# import at most once.
_ENCODER: Any = None
_ENCODER_TRIED = False


def _get_encoder() -> Any:
    global _ENCODER, _ENCODER_TRIED
    if _ENCODER_TRIED:
        return _ENCODER
    _ENCODER_TRIED = True
    try:
        import tiktoken

        _ENCODER = tiktoken.get_encoding("cl100k_base")
    except Exception:  # noqa: BLE001 -- missing lib OR offline vocab fetch
        _ENCODER = None
    return _ENCODER


def count_tokens(text: str) -> int:
    """Token count via tiktoken if available, else a chars/4 estimate."""
    if not text:
        return 0
    enc = _get_encoder()
    if enc is not None:
        try:
            return len(enc.encode(text))
        except Exception:  # noqa: BLE001
            pass
    return max(1, len(text) // 4)


def _split_paragraphs(text: str) -> list[str]:
    """Split on blank lines; collapse runs of whitespace-only lines.

    Falls back to single-newline splitting for a paragraph that is itself huge
    (some PDFs reflow an entire page onto one line)."""
    raw = [p.strip() for p in text.replace("\r\n", "\n").split("\n\n")]
    return [p for p in raw if p]


def _split_oversized(paragraph: str, target_tokens: int,
                     counter: Callable[[str], int]) -> list[str]:
    """Break a single paragraph that exceeds the target into token-sized
    pieces, preferring sentence then line then hard splits."""
    if counter(paragraph) <= target_tokens:
        return [paragraph]

    # Try sentence-ish boundaries first.
    import re

    pieces = re.split(r"(?<=[.!?])\s+|\n", paragraph)
    out: list[str] = []
    buf = ""
    for piece in pieces:
        piece = piece.strip()
        if not piece:
            continue
        candidate = f"{buf} {piece}".strip() if buf else piece
        if buf and counter(candidate) > target_tokens:
            out.append(buf)
            buf = piece
        else:
            buf = candidate
    if buf:
        out.append(buf)

    # If a single sentence is still oversized, hard-split it by characters
    # (approx target_tokens*4 chars per piece).
    final: list[str] = []
    approx_chars = max(200, target_tokens * 4)
    for piece in out:
        if counter(piece) <= target_tokens:
            final.append(piece)
        else:
            for i in range(0, len(piece), approx_chars):
                final.append(piece[i:i + approx_chars])
    return final


def chunk_document_text(
    text: str | None,
    *,
    target_tokens: int = 500,
    overlap_tokens: int = 50,
    counter: Callable[[str], int] | None = None,
) -> list[dict[str, Any]]:
    """Chunk ``text`` into ~``target_tokens`` paragraph-aware pieces.

    Returns a list of ``{"chunk_index", "text", "token_count"}`` dicts in
    document order.  Consecutive chunks share a tail/head overlap of roughly
    ``overlap_tokens`` so a boundary-straddling clause stays retrievable.
    Empty / whitespace-only input returns ``[]``.
    """
    count = counter or count_tokens
    if not text or not text.strip():
        return []

    # Expand oversized paragraphs first so the greedy packer only sees pieces
    # that individually fit.
    paragraphs: list[str] = []
    for para in _split_paragraphs(text):
        paragraphs.extend(_split_oversized(para, target_tokens, count))

    chunks: list[str] = []
    buf: list[str] = []
    buf_tokens = 0
    for para in paragraphs:
        pt = count(para)
        if buf and buf_tokens + pt > target_tokens:
            chunk_text = "\n\n".join(buf)
            chunks.append(chunk_text)
            # Seed the next chunk with a BOUNDED trailing slice (~overlap_tokens)
            # of what we just emitted -- not whole paragraphs, which would
            # roughly double chunk size when paragraphs are themselves
            # target-sized.
            if overlap_tokens > 0:
                approx_chars = overlap_tokens * 4
                tail_text = chunk_text[-approx_chars:].lstrip()
                buf = [tail_text] if tail_text else []
                buf_tokens = count(tail_text) if tail_text else 0
            else:
                buf, buf_tokens = [], 0
        buf.append(para)
        buf_tokens += pt
    if buf:
        chunks.append("\n\n".join(buf))

    return [
        {"chunk_index": i, "text": c, "token_count": count(c)}
        for i, c in enumerate(chunks)
    ]
