"""Embedding providers for RAG.

Mirrors the ``LLMProvider`` split: an abstract interface, a real OpenAI-backed
implementation, and a deterministic mock for tests.  Embeddings are a commodity
-- we BUY this (OpenAI ``text-embedding-3-small``) rather than hand-roll it; the
domain value lives in how we chunk, store, filter-by-project, and feed results
to the bots, not in the vector math.

Vectors are plain ``list[float]`` at this boundary; ``ai/rag.py`` packs them to
float32 bytes for storage.  ``text-embedding-3-small`` returns length-1536,
L2-normalised vectors, so cosine similarity == dot product.
"""

from __future__ import annotations

import hashlib
import math
import os
import re
from abc import ABC, abstractmethod


class EmbeddingError(RuntimeError):
    """Raised when an embedding backend can't be built or a call fails."""


class EmbeddingProvider(ABC):
    name: str = "abstract"
    model: str = "abstract"
    dims: int = 0

    @abstractmethod
    def embed(self, texts: list[str]) -> list[list[float]]:
        """Return one vector per input text, in order."""
        raise NotImplementedError


# OpenAI text-embedding-3-small pricing (2026): ~$0.02 per 1M input tokens.
OPENAI_SMALL_USD_PER_1M_TOKENS = 0.02
DEFAULT_EMBEDDING_MODEL = "text-embedding-3-small"
DEFAULT_EMBEDDING_DIMS = 1536


class OpenAIEmbeddingProvider(EmbeddingProvider):
    """Real embeddings via the OpenAI API.

    Pins ``base_url`` to the official endpoint by default so a stale
    ``OPENAI_BASE_URL`` (e.g. an abandoned local Ollama) can never silently
    hijack embedding traffic.  Pass ``base_url`` explicitly to override.
    """

    name = "openai"

    def __init__(
        self,
        *,
        api_key: str | None = None,
        model: str = DEFAULT_EMBEDDING_MODEL,
        dims: int = DEFAULT_EMBEDDING_DIMS,
        base_url: str = "https://api.openai.com/v1",
        batch_size: int = 128,
        timeout_seconds: float = 60.0,
    ) -> None:
        self.model = model
        self.dims = dims
        self._batch_size = batch_size
        key = api_key or os.environ.get("OPENAI_API_KEY")
        if not key:
            raise EmbeddingError(
                "OPENAI_API_KEY is not set. Put it in project-db/.env "
                "(OPENAI_API_KEY=sk-...) to enable embeddings."
            )
        try:
            from openai import OpenAI
        except ImportError as exc:  # pragma: no cover
            raise EmbeddingError(
                "openai package not installed. Install with: pip install "
                "'.[rag]' (or `pip install openai tiktoken numpy`)."
            ) from exc
        self._client = OpenAI(api_key=key, base_url=base_url, timeout=timeout_seconds)

    def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        # The API rejects empty strings; embed a single space in their place so
        # indices stay aligned with the input list.
        cleaned = [(t.replace("\n", " ").strip() or " ") for t in texts]
        out: list[list[float]] = []
        for i in range(0, len(cleaned), self._batch_size):
            batch = cleaned[i : i + self._batch_size]
            try:
                resp = self._client.embeddings.create(
                    model=self.model,
                    input=batch,
                    dimensions=self.dims,
                    encoding_format="float",
                )
            except Exception as exc:
                raise EmbeddingError(f"OpenAI embeddings call failed: {exc}") from exc
            # The API guarantees data is returned in input order, but sort on
            # index defensively.
            for item in sorted(resp.data, key=lambda d: d.index):
                out.append(list(item.embedding))
        return out


class MockEmbeddingProvider(EmbeddingProvider):
    """Deterministic hashed-bag-of-words embeddings for tests.

    No network.  Texts sharing words get higher cosine similarity, so retrieval
    ordering is meaningful and assertable.  Returns L2-normalised vectors.
    """

    name = "mock"

    def __init__(self, *, dims: int = 64, model: str = "mock-embed") -> None:
        self.dims = dims
        self.model = model

    def embed(self, texts: list[str]) -> list[list[float]]:
        out: list[list[float]] = []
        for t in texts:
            vec = [0.0] * self.dims
            for tok in re.findall(r"[a-z0-9]+", (t or "").lower()):
                h = int(hashlib.md5(tok.encode("utf-8")).hexdigest(), 16)
                vec[h % self.dims] += 1.0
            norm = math.sqrt(sum(x * x for x in vec)) or 1.0
            out.append([x / norm for x in vec])
        return out


def get_embedding_provider() -> EmbeddingProvider:
    """Resolve the embedding provider for CLI/app use.

    OpenAI when ``OPENAI_API_KEY`` is set, else a clear error.  Tests construct
    ``MockEmbeddingProvider`` directly rather than going through here.
    """
    if os.environ.get("OPENAI_API_KEY"):
        return OpenAIEmbeddingProvider()
    raise EmbeddingError("No embedding provider available: set OPENAI_API_KEY in .env.")


def get_optional_embedding_provider() -> EmbeddingProvider | None:
    """Embedding provider if configured, else None -- never raises.

    For surfaces (the askbot) that want RAG WHEN available but must keep
    working when there's no OpenAI key or nothing has been embedded yet.
    """
    try:
        return get_embedding_provider()
    except EmbeddingError:
        return None


def estimate_cost_usd(token_count: int, *, model: str = DEFAULT_EMBEDDING_MODEL) -> float:
    """Rough USD cost to embed ``token_count`` tokens (text-embedding-3-small)."""
    return (token_count / 1_000_000) * OPENAI_SMALL_USD_PER_1M_TOKENS
