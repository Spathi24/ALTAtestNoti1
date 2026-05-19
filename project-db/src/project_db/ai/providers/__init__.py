"""LLM provider abstractions.

Import the type you need:

    from project_db.ai.providers import (
        LLMProvider, LLMMessage, LLMResponse, LLMProviderError,
        MockLLMProvider, AnthropicProvider, OpenAICompatibleProvider,
        get_default_provider,
    )

``get_default_provider()`` reads ``LLM_PROVIDER`` env var:
  - "mock"               -> MockLLMProvider (returns empty strings)
  - "anthropic"          -> AnthropicProvider (needs ANTHROPIC_API_KEY)
  - "openai-compatible"  -> OpenAICompatibleProvider (needs
                            OPENAI_BASE_URL + OPENAI_MODEL)
  unset                  -> "anthropic" if ANTHROPIC_API_KEY present,
                            else "mock"
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
]


def get_default_provider() -> LLMProvider:
    """Resolve the configured provider from env, with sane fallbacks."""
    name = (os.environ.get("LLM_PROVIDER") or "").strip().lower()
    if not name:
        name = "anthropic" if os.environ.get("ANTHROPIC_API_KEY") else "mock"

    if name == "mock":
        return MockLLMProvider()
    if name == "anthropic":
        return AnthropicProvider()
    if name == "openai-compatible":
        base_url = os.environ.get("OPENAI_BASE_URL")
        model = os.environ.get("OPENAI_MODEL")
        if not base_url or not model:
            raise LLMProviderError(
                "openai-compatible provider requires OPENAI_BASE_URL and "
                "OPENAI_MODEL env vars."
            )
        return OpenAICompatibleProvider(base_url=base_url, default_model=model)
    raise LLMProviderError(f"Unknown LLM_PROVIDER={name!r}")
