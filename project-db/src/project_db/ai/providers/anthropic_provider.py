"""Anthropic Messages API provider.

Translates our internal ``LLMProvider`` interface to Anthropic's SDK.
Available today via ``pip install -e .[ai]``; swapped out for a local
provider once Mac mini hardware is online.

Notes on the translation:
  - System prompt is a top-level ``system`` field in Anthropic's API,
    not a message turn.  We accept it both ways internally; the
    provider extracts it.
  - ``response_format`` is a no-op on Anthropic -- the SDK doesn't have
    a JSON-mode flag.  Callers wanting parsed JSON should use
    ``complete_json``, which retries on parse failure regardless of
    backend support.
  - Errors from the SDK are wrapped in ``LLMProviderError`` so the
    caller has a single exception type to handle.
"""

from __future__ import annotations

import logging
import os
from typing import Any

from project_db.ai.providers.base import (
    LLMMessage,
    LLMProvider,
    LLMProviderError,
    LLMResponse,
    ResponseFormat,
)

logger = logging.getLogger(__name__)

# Reasonable default; override with ANTHROPIC_MODEL env var or per-call `model` arg.
# Use a cheaper model (e.g. claude-3-5-haiku-20241022) for cost-sensitive testing.
_DEFAULT_MODEL = "claude-sonnet-4-5-20250929"


def _resolve_default_model(explicit: str) -> str:
    """Return the model to use, checking ANTHROPIC_MODEL env var first."""
    if explicit != _DEFAULT_MODEL:
        return explicit  # caller passed an explicit override
    return os.environ.get("ANTHROPIC_MODEL", _DEFAULT_MODEL)


class AnthropicProvider(LLMProvider):
    name = "anthropic"

    def __init__(
        self,
        *,
        api_key: str | None = None,
        default_model: str = _DEFAULT_MODEL,
        client: Any = None,  # for tests; pre-built anthropic.Anthropic
    ) -> None:
        if client is not None:
            self._client = client
        else:
            try:
                from anthropic import Anthropic
            except ImportError as exc:
                raise LLMProviderError(
                    "anthropic SDK not installed.  Run: pip install '.[ai]'"
                ) from exc
            key = api_key or os.environ.get("ANTHROPIC_API_KEY")
            if not key:
                raise LLMProviderError(
                    "ANTHROPIC_API_KEY not set.  Either pass api_key= or set the env var."
                )
            self._client = Anthropic(api_key=key)
        self._default_model = _resolve_default_model(default_model)

    def complete(
        self,
        *,
        messages: list[LLMMessage],
        system: str | None = None,
        model: str | None = None,
        temperature: float = 0.0,
        max_tokens: int = 4000,
        response_format: ResponseFormat = "text",
    ) -> LLMResponse:
        # Anthropic doesn't accept system as a message turn -- split it out.
        sys_text = system
        msgs: list[dict[str, str]] = []
        for m in messages:
            if m.role == "system":
                # If both `system=` and a system message turn are present,
                # the explicit `system=` arg wins; otherwise promote the turn.
                if sys_text is None:
                    sys_text = m.content
                continue
            msgs.append({"role": m.role, "content": m.content})

        kwargs: dict[str, Any] = {
            "model": model or self._default_model,
            "messages": msgs,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        if sys_text:
            kwargs["system"] = sys_text

        try:
            resp = self._client.messages.create(**kwargs)
        except Exception as exc:
            raise LLMProviderError(f"anthropic.messages.create failed: {exc}") from exc

        # Anthropic returns content as a list of blocks; we expect one text block.
        try:
            content = resp.content[0].text
        except (AttributeError, IndexError, TypeError) as exc:
            raise LLMProviderError(f"anthropic response missing text content: {resp!r}") from exc

        usage = {}
        if hasattr(resp, "usage") and resp.usage is not None:
            usage = {
                "input_tokens": getattr(resp.usage, "input_tokens", 0),
                "output_tokens": getattr(resp.usage, "output_tokens", 0),
            }

        return LLMResponse(
            content=content,
            finish_reason=getattr(resp, "stop_reason", "stop") or "stop",
            usage=usage,
            model=getattr(resp, "model", kwargs["model"]),
            raw=resp,
        )
