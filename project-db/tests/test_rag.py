"""Tests for the RAG layer: chunking, embeddings, embed/retrieve, migration.

All deterministic and offline -- the real OpenAI provider is never called.
``MockEmbeddingProvider`` gives hashed-bag-of-words vectors so similarity
ordering is meaningful and assertable, and the chunker uses a chars/4 token
fallback when tiktoken's vocab isn't available.
"""
from __future__ import annotations

import numpy as np
import pytest
from sqlalchemy import create_engine, inspect, text

from project_db.ai.chunking import chunk_document_text, count_tokens
from project_db.ai.embeddings import (
    MockEmbeddingProvider,
    estimate_cost_usd,
)
from project_db.ai.rag import (
    _content_hash,
    embed_documents_for,
    embedding_coverage,
    retrieve_chunks,
)
from project_db.ai.proposals import (
    generate_scope_proposals,
    generate_timeline_proposals,
)
from project_db.ai.providers.mock import MockLLMProvider
from project_db.ai.query import AiAssistant
from project_db.db.base import Base
from project_db.db.migrations import ensure_sqlite_schema
from project_db.db.models import Document, DocumentChunk
from project_db.db.models.docs import DocumentText
from project_db.db.models.work import TaskStatus


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _doc_with_text(session, project, *, name, body):
    d = Document(name=name, url=f"x://{name}", mime_type="application/pdf",
                 project_id=project.canonical_id if project else None)
    session.add(d)
    session.flush()
    session.add(DocumentText(document_id=d.canonical_id, extracted_text=body,
                             extraction_method="test"))
    session.flush()
    return d


# ---------------------------------------------------------------------------
# chunking
# ---------------------------------------------------------------------------


class TestChunking:
    def test_empty_returns_no_chunks(self):
        assert chunk_document_text("") == []
        assert chunk_document_text(None) == []
        assert chunk_document_text("   \n\n  ") == []

    def test_short_text_is_one_chunk(self):
        cs = chunk_document_text("A short contract clause.", target_tokens=500)
        assert len(cs) == 1
        assert cs[0]["chunk_index"] == 0
        assert "short contract" in cs[0]["text"]

    def test_oversized_paragraph_is_split(self):
        body = "word " * 4000  # one giant paragraph
        cs = chunk_document_text(body, target_tokens=200, overlap_tokens=20)
        assert len(cs) > 1
        # No chunk wildly exceeds the target (allow overlap headroom).
        assert max(c["token_count"] for c in cs) <= 400

    def test_chunks_are_indexed_in_order(self):
        body = "\n\n".join(f"Paragraph number {i} with some filler words." * 10
                           for i in range(20))
        cs = chunk_document_text(body, target_tokens=100, overlap_tokens=10)
        assert [c["chunk_index"] for c in cs] == list(range(len(cs)))

    def test_count_tokens_positive(self):
        assert count_tokens("hello world") >= 1
        assert count_tokens("") == 0


# ---------------------------------------------------------------------------
# mock embeddings
# ---------------------------------------------------------------------------


class TestMockEmbeddings:
    def test_deterministic_and_normalized(self):
        m = MockEmbeddingProvider(dims=64)
        a = m.embed(["the client shall pay on signing"])[0]
        b = m.embed(["the client shall pay on signing"])[0]
        assert a == b
        assert np.isclose(np.linalg.norm(a), 1.0)

    def test_shared_words_more_similar(self):
        m = MockEmbeddingProvider(dims=128)
        v = m.embed([
            "demolition of the bathroom wall and tiles",
            "client payment terms fifty percent on signing",
        ])
        q = np.asarray(m.embed(["when does the client payment happen"])[0])
        sims = [float(np.dot(q, np.asarray(x))) for x in v]
        assert sims[1] > sims[0]

    def test_estimate_cost_scales(self):
        assert estimate_cost_usd(0) == 0.0
        assert estimate_cost_usd(1_000_000) == pytest.approx(0.02)

    def test_content_hash_changes_with_model_and_text(self):
        h1 = _content_hash("text", "model-a", 1536)
        assert h1 == _content_hash("text", "model-a", 1536)
        assert h1 != _content_hash("text", "model-b", 1536)
        assert h1 != _content_hash("other", "model-a", 1536)
        assert h1 != _content_hash("text", "model-a", 512)


# ---------------------------------------------------------------------------
# embed_documents_for
# ---------------------------------------------------------------------------


class TestEmbedDocuments:
    def test_embeds_chunks_with_vectors(self, session, project_factory):
        p = project_factory(name="Embed Proj")
        _doc_with_text(session, p, name="Contract.pdf",
                       body="Payment is due on completion. " * 50)
        session.commit()
        m = MockEmbeddingProvider(dims=64)
        stats = embed_documents_for(session, m)
        assert stats["documents_processed"] == 1
        assert stats["chunks_embedded"] >= 1
        rows = session.query(DocumentChunk).all()
        assert rows and all(r.embedding is not None for r in rows)
        assert all(r.embedding_model == "mock-embed" and r.dims == 64 for r in rows)
        assert all(r.project_id == p.canonical_id for r in rows)

    def test_rerun_is_idempotent_skip(self, session, project_factory):
        p = project_factory(name="Idem Proj")
        _doc_with_text(session, p, name="Contract.pdf", body="Scope of work. " * 80)
        session.commit()
        m = MockEmbeddingProvider(dims=64)
        embed_documents_for(session, m)
        first = session.query(DocumentChunk).count()
        stats2 = embed_documents_for(session, m)
        assert stats2["documents_skipped"] == 1
        assert stats2["documents_processed"] == 0
        assert session.query(DocumentChunk).count() == first

    def test_overwrite_reembeds(self, session, project_factory):
        p = project_factory(name="OW Proj")
        _doc_with_text(session, p, name="Contract.pdf", body="Scope of work. " * 80)
        session.commit()
        m = MockEmbeddingProvider(dims=64)
        embed_documents_for(session, m)
        stats = embed_documents_for(session, m, overwrite=True)
        assert stats["documents_processed"] == 1
        assert stats["documents_skipped"] == 0

    def test_changed_text_rebuilds_and_cleans_stale(self, session, project_factory):
        p = project_factory(name="Change Proj")
        d = _doc_with_text(session, p, name="Contract.pdf",
                           body="Original short clause.")
        session.commit()
        m = MockEmbeddingProvider(dims=64)
        embed_documents_for(session, m)
        # Replace the text with much longer content -> more chunks; old gone.
        txt = session.query(DocumentText).filter_by(document_id=d.canonical_id).one()
        txt.extracted_text = "Completely different and much longer body. " * 200
        session.commit()
        embed_documents_for(session, m)
        rows = (session.query(DocumentChunk)
                .filter_by(document_id=d.canonical_id)
                .order_by(DocumentChunk.chunk_index).all())
        assert rows and rows[0].text.startswith("Completely different")
        # chunk_index is contiguous from 0 (no orphaned stale rows)
        assert [r.chunk_index for r in rows] == list(range(len(rows)))

    def test_project_filter_and_limit(self, session, project_factory):
        p1 = project_factory(name="P1")
        p2 = project_factory(name="P2")
        _doc_with_text(session, p1, name="A.pdf", body="Alpha content here. " * 20)
        _doc_with_text(session, p2, name="B.pdf", body="Beta content here. " * 20)
        session.commit()
        m = MockEmbeddingProvider(dims=64)
        stats = embed_documents_for(session, m, project_id=p1.canonical_id)
        assert stats["documents_processed"] == 1
        pids = {r.project_id for r in session.query(DocumentChunk).all()}
        assert pids == {p1.canonical_id}

    def test_trashed_and_textless_docs_skipped(self, session, project_factory):
        p = project_factory(name="Skip Proj")
        # trashed doc with text
        d1 = _doc_with_text(session, p, name="Trashed.pdf", body="ignored " * 30)
        d1.is_trashed = True
        # doc with empty text
        d2 = Document(name="Empty.pdf", url="x://e", mime_type="application/pdf",
                      project_id=p.canonical_id)
        session.add(d2)
        session.flush()
        session.add(DocumentText(document_id=d2.canonical_id, extracted_text="",
                                 extraction_method="skipped-mime"))
        session.commit()
        m = MockEmbeddingProvider(dims=64)
        stats = embed_documents_for(session, m)
        assert stats["documents_total"] == 0
        assert session.query(DocumentChunk).count() == 0


# ---------------------------------------------------------------------------
# retrieve_chunks
# ---------------------------------------------------------------------------


class TestRetrieve:
    def _seed(self, session, project_factory):
        p = project_factory(name="Retr Proj")
        _doc_with_text(session, p, name="Payments.pdf",
                       body="The client shall pay fifty percent on signing and "
                            "the balance on completion of the work.")
        _doc_with_text(session, p, name="Demo.pdf",
                       body="Demolition of the bathroom wall, removal of old "
                            "tiles and fixtures from the unit.")
        session.commit()
        m = MockEmbeddingProvider(dims=128)
        embed_documents_for(session, m)
        return p, m

    def test_ranks_relevant_chunk_first(self, session, project_factory):
        _, m = self._seed(session, project_factory)
        hits = retrieve_chunks(session, m, "when does the client pay the balance",
                               top_k=5)
        assert hits
        assert hits[0]["document_name"] == "Payments.pdf"
        assert hits[0]["similarity"] >= hits[-1]["similarity"]

    def test_project_filter(self, session, project_factory):
        p, m = self._seed(session, project_factory)
        other = project_factory(name="Other Proj")
        hits = retrieve_chunks(session, m, "client payment",
                               project_id=other.canonical_id, top_k=5)
        assert hits == []

    def test_empty_query_returns_empty(self, session, project_factory):
        _, m = self._seed(session, project_factory)
        assert retrieve_chunks(session, m, "  ") == []

    def test_model_mismatch_excluded(self, session, project_factory):
        self._seed(session, project_factory)  # embedded with dims=128
        other_model = MockEmbeddingProvider(dims=64)  # different space
        assert retrieve_chunks(session, other_model, "client payment") == []

    def test_top_k_caps_results(self, session, project_factory):
        p = project_factory(name="Many Proj")
        _doc_with_text(session, p, name="Big.pdf",
                       body="\n\n".join(f"Clause {i} about work scope details."
                                        for i in range(30)))
        session.commit()
        m = MockEmbeddingProvider(dims=64)
        embed_documents_for(session, m, target_tokens=20, overlap_tokens=0)
        hits = retrieve_chunks(session, m, "work scope", top_k=3)
        assert len(hits) <= 3

    def test_coverage_counts(self, session, project_factory):
        self._seed(session, project_factory)
        cov = embedding_coverage(session)
        assert cov["documents_with_text"] == 2
        assert cov["documents_embedded"] == 2
        assert cov["chunks"] >= 2


# ---------------------------------------------------------------------------
# migration
# ---------------------------------------------------------------------------


class TestAskbotRag:
    """answer_with_llm wires retrieved excerpts into the prompt as RAG."""

    def _seed_embedded(self, session, project_factory, embed):
        p = project_factory(name="RAG Ask Proj")
        _doc_with_text(session, p, name="Payments.pdf",
                       body="The client shall pay fifty percent on signing and "
                            "the remaining balance on completion of the work.")
        session.commit()
        embed_documents_for(session, embed)
        return p

    def test_excerpts_injected_and_mode_rag(self, session, project_factory):
        embed = MockEmbeddingProvider(dims=128)
        self._seed_embedded(session, project_factory, embed)
        chat = MockLLMProvider(responses=["50% on signing. (Payments.pdf)"])

        resp = AiAssistant(session).answer_with_llm(
            "what do our client payment terms say?", chat,
            embedding_provider=embed, min_similarity=0.0,
        )
        assert resp.mode == "rag"
        assert resp.sources and resp.sources[0]["document_name"] == "Payments.pdf"
        # The prompt actually carried the excerpts + the RAG system rule.
        user_msg = chat.calls[0]["messages"][0].content
        assert "RELEVANT DOCUMENT EXCERPTS" in user_msg
        assert "Payments.pdf" in user_msg
        assert "DOCUMENT EXCERPTS (RAG)" in chat.calls[0]["system"]

    def test_no_embedding_provider_is_plain_llm(self, session, project_factory):
        embed = MockEmbeddingProvider(dims=128)
        self._seed_embedded(session, project_factory, embed)
        chat = MockLLMProvider(responses=["plain answer"])

        resp = AiAssistant(session).answer_with_llm(
            "what do our payment terms say?", chat,  # no embedding_provider
        )
        assert resp.mode == "llm"
        assert resp.sources is None
        assert "RELEVANT DOCUMENT EXCERPTS" not in chat.calls[0]["messages"][0].content

    def test_empty_corpus_is_plain_llm(self, session, project_factory):
        project_factory(name="No Embeds Proj")  # nothing embedded
        embed = MockEmbeddingProvider(dims=128)
        chat = MockLLMProvider(responses=["plain answer"])

        resp = AiAssistant(session).answer_with_llm(
            "what do our payment terms say?", chat, embedding_provider=embed,
        )
        assert resp.mode == "llm"
        assert resp.sources is None

    def test_retrieval_error_falls_back_to_llm(self, session, project_factory):
        embed = MockEmbeddingProvider(dims=128)
        self._seed_embedded(session, project_factory, embed)

        class _BoomEmbed(MockEmbeddingProvider):
            def embed(self, texts):
                raise RuntimeError("boom")

        chat = MockLLMProvider(responses=["plain answer"])
        resp = AiAssistant(session).answer_with_llm(
            "what do our payment terms say?", chat,
            embedding_provider=_BoomEmbed(dims=128), min_similarity=0.0,
        )
        # Retrieval blew up -> no excerpts, but the answer still comes back.
        assert resp.mode == "llm"
        assert resp.sources is None


class TestRetrieveTrashed:
    def test_trashed_doc_chunks_excluded(self, session, project_factory):
        p = project_factory(name="Trash Retr Proj")
        d = _doc_with_text(session, p, name="Old.pdf",
                           body="client payment terms fifty percent on signing")
        session.commit()
        m = MockEmbeddingProvider(dims=64)
        embed_documents_for(session, m)
        assert retrieve_chunks(session, m, "payment") != []     # found while live
        d.is_trashed = True
        session.commit()
        assert retrieve_chunks(session, m, "payment") == []     # excluded once trashed


class TestProposalRag:
    """Relevance excerpts feed the proposal bots as extra evidence (additive)."""

    def _seed(self, session, project_factory, task_factory, embed):
        p = project_factory(name="Prop RAG Proj")
        _doc_with_text(
            session, p, name="SOW.pdf",
            body="Scope of work: demolition, framing, and final inspection. "
                 "The contractor shall complete framing and pass final "
                 "inspection per the project schedule and milestones.",
        )
        task_factory(project=p, title="Framing", status=TaskStatus.TODO)
        session.commit()
        embed_documents_for(session, embed)
        return p

    def test_timeline_injects_excerpts(self, session, project_factory, task_factory):
        embed = MockEmbeddingProvider(dims=128)
        p = self._seed(session, project_factory, task_factory, embed)

        captured = {}

        def on_call(**kw):
            captured["user"] = kw["messages"][0].content
            return '{"proposals": []}'

        chat = MockLLMProvider(on_call=on_call)
        batch = generate_timeline_proposals(
            session, chat, p.canonical_id,
            embedding_provider=embed, rag_min_similarity=0.0,
        )
        assert batch.rag_chunks_used >= 1
        assert "RELEVANT DOCUMENT EXCERPTS" in captured["user"]

    def test_timeline_without_embedding_has_no_excerpts(
        self, session, project_factory, task_factory
    ):
        embed = MockEmbeddingProvider(dims=128)
        p = self._seed(session, project_factory, task_factory, embed)

        captured = {}

        def on_call(**kw):
            captured["user"] = kw["messages"][0].content
            return '{"proposals": []}'

        chat = MockLLMProvider(on_call=on_call)
        batch = generate_timeline_proposals(session, chat, p.canonical_id)
        assert batch.rag_chunks_used == 0
        assert "RELEVANT DOCUMENT EXCERPTS" not in captured["user"]

    def test_scope_injects_excerpts(self, session, project_factory, task_factory):
        embed = MockEmbeddingProvider(dims=128)
        p = self._seed(session, project_factory, task_factory, embed)

        captured = {}

        def on_call(**kw):
            captured["user"] = kw["messages"][0].content
            return '{"scope_gaps": []}'

        chat = MockLLMProvider(on_call=on_call)
        batch = generate_scope_proposals(
            session, chat, p.canonical_id,
            embedding_provider=embed, rag_min_similarity=0.0,
        )
        assert batch.rag_chunks_used >= 1
        assert "RELEVANT DOCUMENT EXCERPTS" in captured["user"]


class TestMigration:
    def test_ensure_schema_creates_document_chunk(self):
        engine = create_engine("sqlite:///:memory:", future=True)
        Base.metadata.create_all(engine)
        with engine.begin() as conn:
            conn.execute(text("DROP TABLE document_chunk"))
        assert "document_chunk" not in inspect(engine).get_table_names()
        ensure_sqlite_schema(engine)
        insp = inspect(engine)
        assert "document_chunk" in insp.get_table_names()
        cols = {c["name"] for c in insp.get_columns("document_chunk")}
        assert {"document_id", "embedding", "content_hash", "dims",
                "embedding_model", "chunk_index"} <= cols
        # idempotent second run
        ensure_sqlite_schema(engine)
        engine.dispose()
