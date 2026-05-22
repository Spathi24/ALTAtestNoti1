"""LLM provider abstractions.

Import the type you need:

    from project_db.ai.providers import (
        LLMProvider, LLMMessage, LLMResponse, LLMProviderError,
        MockLLMProvider, AnthropicProvider, OpenAICompatibleProvider,
        get_default_provider, get_fast_provider,
    )

``get_default_provider()`` reads ``LLM_PROVIDER`` env var:
  - "mock"               -> MockLLMProvider (returns empty strings)
  - "anthropic"          -> AnthropicProvider (needs ANTHROPIC_API_KEY)
  - "openai-compatible"  -> OpenAICompatibleProvider (needs
                            OPENAI_BASE_URL + OPENAI_MODEL)
  unset                  -> "anthropic" if ANTHROPIC_API_KEY present,
                            else "mock"

``get_fast_provider()`` resolves the same backend but returns a cheaper,
summarization-grade model (Haiku on Anthropic) -- used by the `ask` LLM
fallback, where the job is reading + summarizing canonical data, not the
analytical reasoning reserved for proposal generation.
"""
from __future__ import annotations

import os

from project_db.ai.providers.anthropic_provider import AnthropicProvider
from project_db.ai.providers.base import (
    LLMMessage,
    LLMProvider,
    LLMProviderError,
    LLMResponse,
)
from project_db.ai.providers.mock import MockLLMProvider
from project_db.ai.providers.openai_compatible import OpenAICompatibleProvider

__all__ = [
    "LLMProvider",
    "LLMMessage",
    "LLMResponse",
    "LLMProviderError",
    "MockLLMProvider",
    "AnthropicProvider",
    "OpenAICompatibleProvider",
    "get_default_provider",
    "get_fast_provider",
]

# Small, cheap model for summarization-grade work -- the `ask` LLM fallback,
# which reads + summarizes the canonical DB rather than reasoning analytically.
# Override with ANTHROPIC_MODEL_FAST.  The proposal-grade ("deep") model stays
# on ANTHROPIC_MODEL (see AnthropicProvider / get_default_provider).
_DEFAULT_FAST_MODEL = "claude-haiku-4-5"


def _resolve_provider_name() -> str:
    """Resolve the configured backend name, with the long-standing fallback:
    explicit LLM_PROVIDER, else anthropic-if-key-present, else mock."""
    name = (os.environ.get("LLM_PROVIDER") or "").strip().lower()
    if not name:
        name = "anthropic" if os.environ.get("ANTHROPIC_API_KEY") else "mock"
    return name


def _build_provider(name: str, *, fast: bool) -> LLMProvider:
    """Construct the provider for backend ``name``.

    ``fast=True`` selects the cheaper/smaller model where the backend
    distinguishes one (Anthropic -> ANTHROPIC_MODEL_FAST / Haiku;
    openai-compatible -> OPENAI_MODEL_FAST when set).  It is a no-op for
    the mock backend.
    """
    if name == "mock":
        return MockLLMProvider()
    if name == "anthropic":
        if fast:
            return AnthropicProvider(
                default_model=os.environ.get(
                    "ANTHROPIC_MODEL_FAST", _DEFAULT_FAST_MODEL
                )
            )
        return AnthropicProvider()
    if name == "openai-compatible":
        base_url = os.environ.get("OPENAI_BASE_URL")
        model = os.environ.get("OPENAI_MODEL")
        if fast:
            model = os.environ.get("OPENAI_MODEL_FAST") or model
        if not base_url or not model:
            raise LLMProviderError(
                "openai-compatible provider requires OPENAI_BASE_URL and "
                "OPENAI_MODEL env vars."
            )
        return OpenAICompatibleProvider(base_url=base_url, default_model=model)
    raise LLMProviderError(f"Unknown LLM_PROVIDER={name!r}")


def get_default_provider() -> LLMProvider:
    """Resolve the proposal-grade ("deep") provider from env.

    On Anthropic this uses ANTHROPIC_MODEL (Sonnet by default).  Use it for
    analytical work: proposal generation, contract reconciliation.
    """
    return _build_provider(_resolve_provider_name(), fast=False)


def get_fast_provider() -> LLMProvider:
    """Resolve a cheap, summarization-grade provider from env.

    Same backend resolution as ``get_default_provider``, but on Anthropic it
    is pinned to a small/fast model (Haiku, via ANTHROPIC_MODEL_FAST).  Use it
    for the `ask` LLM fallback -- reading and summarizing canonical data, not
    analytical reasoning.
    """
    return _build_provider(_resolve_provider_name(), fast=True)
