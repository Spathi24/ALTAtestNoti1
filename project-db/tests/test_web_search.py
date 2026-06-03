"""The documents search page (`/search`) -- hybrid retrieval surface.

Read-only. Uses a mock embedding provider (monkeypatched in, matching the
mock-embedded corpus) so no OpenAI key / network is needed.
"""
from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

fastapi = pytest.importorskip("fastapi")
from fastapi.testclient import TestClient  # noqa: E402

from project_db.ai.embeddings import MockEmbeddingProvider  # noqa: E402
from project_db.ai.rag import embed_documents_for  # noqa: E402
from project_db.db.base import Base  # noqa: E402
from project_db.db.models import Document  # noqa: E402
from project_db.db.models.docs import DocumentText  # noqa: E402


@pytest.fixture
def db_engine():
    engine = create_engine(
        "sqlite:///:memory:", future=True,
        connect_args={"check_same_thread": False}, poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    yield engine
    engine.dispose()


@pytest.fixture
def patched_session_factory(db_engine, monkeypatch):
    from project_db.db import session as session_mod

    factory = sessionmaker(bind=db_engine, expire_on_commit=False)
    monkeypatch.setattr(session_mod, "_SessionLocal", factory)
    yield factory


@pytest.fixture
def client(patched_session_factory):
    from project_db.web.app import create_app

    return TestClient(create_app())


def _seed_and_embed(session, project_factory):
    p = project_factory(name="Search Proj")
    d = Document(name="Payments.pdf", url="x://1", mime_type="application/pdf",
                 project_id=p.canonical_id)
    session.add(d)
    session.flush()
    session.add(DocumentText(
        document_id=d.canonical_id, extraction_method="test",
        extracted_text="The client shall pay fifty percent on signing and the "
                       "balance on completion."))
    session.commit()
    embed_documents_for(session, MockEmbeddingProvider(dims=64))


class TestSearchPage:
    def test_empty_query_renders_form(self, client):
        r = client.get("/search")
        assert r.status_code == 200
        assert "Search documents" in r.text
        assert "documents embedded" in r.text

    def test_no_embeddings_shows_hint(self, client):
        r = client.get("/search", params={"q": "payment"})
        assert r.status_code == 200
        assert "No documents are embedded" in r.text

    def test_results_render(self, client, session, project_factory, monkeypatch):
        _seed_and_embed(session, project_factory)
        monkeypatch.setattr(
            "project_db.ai.embeddings.get_optional_embedding_provider",
            lambda: MockEmbeddingProvider(dims=64),
        )
        r = client.get("/search", params={"q": "when does the client pay"})
        assert r.status_code == 200
        assert 'data-testid="search-result"' in r.text
        assert "Payments.pdf" in r.text

    def test_no_provider_shows_hint(self, client, session, project_factory, monkeypatch):
        _seed_and_embed(session, project_factory)
        monkeypatch.setattr(
            "project_db.ai.embeddings.get_optional_embedding_provider",
            lambda: None,
        )
        r = client.get("/search", params={"q": "payment"})
        assert r.status_code == 200
        assert "No embedding provider" in r.text


class TestSearchService:
    def test_empty_query_no_error(self, session):
        from project_db.web.ui_views import search_documents

        out = search_documents(session, "")
        assert out["error"] is None
        assert out["results"] == []
        assert out["embedded"] is False

    def test_unembedded_corpus_errors(self, session, project_factory):
        from project_db.web.ui_views import search_documents

        out = search_documents(session, "payment terms")
        assert "embed" in (out["error"] or "").lower()
