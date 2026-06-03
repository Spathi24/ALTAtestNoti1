"""RAG sidecar: embedded chunks of Document text for similarity search.

One row per (Document, chunk_index).  Mirrors the ``DocumentText`` sidecar
pattern -- ``extract-content`` fills ``DocumentText`` (the body); ``embed-
documents`` fills ``DocumentChunk`` (the searchable, vectorised pieces).

Why a separate table (not columns on Document/DocumentText):
  - There are MANY chunks per document; it is inherently 1:N.
  - The embedding blob is large and only the retrieval path needs it.
  - ``project_id`` is denormalised here so a per-project question can filter
    candidates with one indexed WHERE before the cosine pass.

The vector lives in ``embedding`` as raw little-endian float32 bytes (numpy
``tobytes()``).  We do brute-force cosine in Python at retrieval time -- at the
current corpus scale (hundreds of docs -> a few thousand chunks) that is
sub-10ms and needs no native extension.  ``content_hash`` makes re-embedding
idempotent: a chunk whose text + model + dims are unchanged is left alone.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    Integer,
    LargeBinary,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import UUID

from project_db.db.base import Base, CanonicalMixin


class DocumentChunk(Base, CanonicalMixin):
    document_id = Column(
        UUID(as_uuid=True),
        ForeignKey("document.canonical_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # Denormalised from Document so retrieval can filter by project cheaply.
    project_id = Column(
        UUID(as_uuid=True),
        ForeignKey("project.canonical_id"),
        nullable=True,
        index=True,
    )
    chunk_index = Column(Integer, nullable=False)
    text = Column(Text, nullable=False)
    token_count = Column(Integer, nullable=True)

    # Vector + provenance.  embedding is float32 little-endian bytes; None until
    # the chunk has actually been embedded (so a failed batch leaves a usable
    # text chunk without a bogus zero vector).
    embedding = Column(LargeBinary, nullable=True)
    embedding_model = Column(String, nullable=True)
    dims = Column(Integer, nullable=True)

    # sha256 of (normalised text + model + dims) -- idempotency key.
    content_hash = Column(String, nullable=False, index=True)
    embedded_at = Column(DateTime, nullable=True, default=datetime.utcnow)
