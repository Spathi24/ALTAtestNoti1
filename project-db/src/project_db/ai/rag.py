"""RAG over DocumentText: embed chunks, retrieve by similarity.

Two entry points, both deterministic given a provider:

  - ``embed_documents_for`` -- chunk each document's extracted text, embed the
    chunks, and store them in ``DocumentChunk``.  Idempotent: a document whose
    chunks already exist with the same content hash + model + dims is SKIPPED,
    so re-running costs nothing for unchanged docs (this matters -- embeddings
    are a paid API call).  A changed document has its chunks rebuilt.

  - ``retrieve_chunks`` -- embed a query and return the most cosine-similar
    stored chunks, optionally filtered to one project.  Brute-force in numpy:
    at the current corpus scale that is sub-10ms and needs no vector-index
    extension.  Swap in sqlite-vec/ANN here if the corpus ever outgrows it.

The LLM never sees the vectors -- only the retrieved chunk TEXT, which it cites.
Arithmetic (cosine) is deterministic; the model's job stays "read + answer".
"""
from __future__ import annotations

import hashlib
import re
from typing import Any

import numpy as np
from sqlalchemy.orm import Session

from project_db.ai.chunking import chunk_document_text, count_tokens
from project_db.ai.embeddings import EmbeddingProvider, estimate_cost_usd
from project_db.db.models import Document, DocumentChunk
from project_db.db.models.docs import DocumentText


def _content_hash(text: str, model: str, dims: int) -> str:
    h = hashlib.sha256()
    h.update(f"{model}|{dims}|".encode("utf-8"))
    h.update((text or "").strip().encode("utf-8"))
    return h.hexdigest()


def _pack(vec: list[float]) -> bytes:
    return np.asarray(vec, dtype=np.float32).tobytes()


def _unpack(blob: bytes) -> np.ndarray:
    return np.frombuffer(blob, dtype=np.float32)


def _candidate_documents(
    session: Session, project_id: Any | None, limit: int | None
) -> list[tuple[Document, str]]:
    """(Document, extracted_text) for live docs with non-empty text."""
    q = (
        session.query(Document, DocumentText.extracted_text)
        .join(DocumentText, DocumentText.document_id == Document.canonical_id)
        .filter(
            Document.is_trashed.is_(False),
            DocumentText.extracted_text.isnot(None),
        )
    )
    if project_id is not None:
        q = q.filter(Document.project_id == project_id)
    q = q.order_by(Document.name)
    if limit:
        q = q.limit(limit)
    return [(doc, txt) for doc, txt in q.all() if txt and txt.strip()]


def embed_documents_for(
    session: Session,
    provider: EmbeddingProvider,
    *,
    project_id: Any | None = None,
    overwrite: bool = False,
    limit: int | None = None,
    commit_every: int = 10,
    target_tokens: int = 500,
    overlap_tokens: int = 50,
) -> dict[str, Any]:
    """Chunk + embed documents into ``DocumentChunk`` (idempotent).

    Returns stats: documents_processed / documents_skipped / chunks_embedded /
    tokens_embedded / estimated_cost_usd / interrupted.

    Commits every ``commit_every`` processed documents and on KeyboardInterrupt
    so a paid run is never lost or double-charged on resume.
    """
    docs = _candidate_documents(session, project_id, limit)
    stats = {
        "documents_total": len(docs),
        "documents_processed": 0,
        "documents_skipped": 0,
        "chunks_embedded": 0,
        "tokens_embedded": 0,
        "estimated_cost_usd": 0.0,
        "interrupted": False,
    }
    model, dims = provider.model, provider.dims
    since_commit = 0

    try:
        for doc, text in docs:
            new_chunks = chunk_document_text(
                text, target_tokens=target_tokens, overlap_tokens=overlap_tokens,
            )
            if not new_chunks:
                continue
            new_hashes = [_content_hash(c["text"], model, dims) for c in new_chunks]

            existing = (
                session.query(DocumentChunk)
                .filter(DocumentChunk.document_id == doc.canonical_id)
                .order_by(DocumentChunk.chunk_index)
                .all()
            )
            unchanged = (
                not overwrite
                and len(existing) == len(new_hashes)
                and all(e.content_hash == h for e, h in zip(existing, new_hashes))
                and all(e.embedding is not None for e in existing)
                and all(e.embedding_model == model and e.dims == dims for e in existing)
            )
            if unchanged:
                stats["documents_skipped"] += 1
                continue

            # Rebuild this document's chunks.
            for e in existing:
                session.delete(e)
            session.flush()

            vectors = provider.embed([c["text"] for c in new_chunks])
            for c, vec, chash in zip(new_chunks, vectors, new_hashes):
                session.add(DocumentChunk(
                    document_id=doc.canonical_id,
                    project_id=doc.project_id,
                    chunk_index=c["chunk_index"],
                    text=c["text"],
                    token_count=c["token_count"],
                    embedding=_pack(vec),
                    embedding_model=model,
                    dims=dims,
                    content_hash=chash,
                ))
                stats["chunks_embedded"] += 1
                stats["tokens_embedded"] += int(c["token_count"] or 0)
            stats["documents_processed"] += 1
            since_commit += 1
            if since_commit >= commit_every:
                session.commit()
                since_commit = 0
    except KeyboardInterrupt:
        stats["interrupted"] = True

    session.commit()
    stats["estimated_cost_usd"] = round(
        estimate_cost_usd(stats["tokens_embedded"], model=model), 4
    )
    return stats


# Tiny English/French stopword set so common glue words don't dominate the
# keyword score.  Deliberately small -- domain terms (numbers, names, "scope",
# "payment") must survive.
_STOPWORDS = {
    "the", "a", "an", "of", "to", "in", "on", "for", "and", "or", "is", "are",
    "be", "by", "at", "as", "it", "this", "that", "with", "from", "we", "our",
    "what", "does", "do", "how", "which", "when", "where", "shall", "will",
    "le", "la", "les", "de", "des", "du", "un", "une", "et", "en", "au", "aux",
    "que", "qui", "pour", "dans", "sur", "est", "sont",
}

# Reciprocal-rank-fusion constant (standard default).
_RRF_K = 60


def _tokenize(text: str | None) -> list[str]:
    return [
        t for t in re.findall(r"[a-z0-9]+", (text or "").lower())
        if len(t) >= 2 and t not in _STOPWORDS
    ]


def _keyword_scores(query: str, texts: list[str]) -> list[float]:
    """Distinct query-term coverage per text, in [0, 1].

    Length-independent (presence, not raw frequency) so a long chunk isn't
    favoured just for being long.  Catches the exact tokens -- invoice numbers,
    civic addresses, proper names, ``QST`` -- that pure cosine similarity blurs.
    """
    qterms = set(_tokenize(query))
    if not qterms:
        return [0.0] * len(texts)
    out: list[float] = []
    for t in texts:
        tset = set(_tokenize(t))
        out.append(sum(1 for q in qterms if q in tset) / len(qterms) if tset else 0.0)
    return out


def retrieve_chunks(
    session: Session,
    provider: EmbeddingProvider,
    query: str,
    *,
    project_id: Any | None = None,
    top_k: int = 12,
    min_similarity: float = 0.0,
    hybrid: bool = True,
) -> list[dict[str, Any]]:
    """Return the ``top_k`` chunks most relevant to ``query``.

    By default uses HYBRID retrieval: semantic (cosine) ranking fused with a
    keyword ranking via reciprocal rank fusion.  Pure cosine blurs exact tokens
    (an invoice number, a civic address, a proper name); the keyword side pins
    them.  Set ``hybrid=False`` for cosine-only.

    Only chunks embedded with the SAME model + dims as ``provider`` are
    candidates (mixing embedding spaces is meaningless).  Returns
    JSON-serializable dicts ordered best-first; each carries ``similarity``
    (cosine), ``keyword_score`` (term coverage), and ``score`` (the fused rank
    score actually used to order, or the cosine when ``hybrid=False``).
    """
    if not query or not query.strip():
        return []

    # Join Document so chunks whose document was later trashed in Drive are
    # excluded -- the soft-delete must not keep surfacing stale text.
    cq = (
        session.query(DocumentChunk)
        .join(Document, Document.canonical_id == DocumentChunk.document_id)
        .filter(
            DocumentChunk.embedding.isnot(None),
            DocumentChunk.embedding_model == provider.model,
            DocumentChunk.dims == provider.dims,
            Document.is_trashed.is_(False),
        )
    )
    if project_id is not None:
        cq = cq.filter(DocumentChunk.project_id == project_id)
    candidates = cq.all()
    if not candidates:
        return []

    qvec = np.asarray(provider.embed([query])[0], dtype=np.float32)
    qnorm = float(np.linalg.norm(qvec)) or 1.0

    matrix = np.vstack([_unpack(c.embedding) for c in candidates])
    norms = np.linalg.norm(matrix, axis=1)
    norms[norms == 0] = 1.0
    sims = (matrix @ qvec) / (norms * qnorm)

    kw = np.asarray(_keyword_scores(query, [c.text for c in candidates]))

    if hybrid:
        # Reciprocal rank fusion of the cosine ranking and the keyword ranking.
        sem_rank = np.empty(len(sims), dtype=int)
        sem_rank[np.argsort(-sims)] = np.arange(len(sims))
        kw_rank = np.empty(len(kw), dtype=int)
        kw_rank[np.argsort(-kw)] = np.arange(len(kw))
        fused = 1.0 / (_RRF_K + sem_rank) + 1.0 / (_RRF_K + kw_rank)
    else:
        fused = sims

    order = np.argsort(-fused)

    # Names for every candidate's document (few distinct docs even for many
    # chunks) so the post-filter loop always has a name available.
    doc_ids = {c.document_id for c in candidates}
    names = {
        d.canonical_id: (d.name, d.url)
        for d in session.query(Document)
        .filter(Document.canonical_id.in_(doc_ids))
        .all()
    }

    out: list[dict[str, Any]] = []
    for idx in order:
        i = int(idx)
        sim = float(sims[i])
        kscore = float(kw[i])
        # Keep a chunk if it is semantically relevant enough OR it contains the
        # query's exact terms -- so an exact-identifier hit with low cosine
        # still surfaces (the whole point of hybrid).
        if sim < min_similarity and kscore == 0.0:
            continue
        c = candidates[i]
        name, url = names.get(c.document_id, (None, None))
        out.append({
            "chunk_id": str(c.canonical_id),
            "document_id": str(c.document_id),
            "document_name": name,
            "document_url": url,
            "project_id": str(c.project_id) if c.project_id else None,
            "chunk_index": c.chunk_index,
            "text": c.text,
            "similarity": round(sim, 4),
            "keyword_score": round(kscore, 4),
            "score": round(float(fused[i]), 6),
        })
        if len(out) >= top_k:
            break
    return out


def embedding_coverage(session: Session) -> dict[str, Any]:
    """How much of the corpus is embedded -- for the CLI/UI status line."""
    total_text_docs = (
        session.query(DocumentText.document_id)
        .join(Document, DocumentText.document_id == Document.canonical_id)
        .filter(
            Document.is_trashed.is_(False),
            DocumentText.extracted_text.isnot(None),
        )
        .count()
    )
    embedded_docs = (
        session.query(DocumentChunk.document_id)
        .filter(DocumentChunk.embedding.isnot(None))
        .distinct()
        .count()
    )
    total_chunks = (
        session.query(DocumentChunk)
        .filter(DocumentChunk.embedding.isnot(None))
        .count()
    )
    return {
        "documents_with_text": int(total_text_docs),
        "documents_embedded": int(embedded_docs),
        "chunks": int(total_chunks),
    }
