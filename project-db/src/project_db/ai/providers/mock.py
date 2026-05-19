"""Deterministic mock provider.

Used by every test that exercises the proposal pipeline -- no API key
needed, no network calls, repeatable.  Two construction patterns:

  1. ``MockLLMProvider(responses=["...", "..."])`` -- returns each
     string in turn, sticks on the last one once exhausted.

  2. ``MockLLMProvider(on_call=lambda **kw: ...)`` -- dynamic response,
     gets every kwarg ``complete`` was called with.  Useful when the
     prompt content should drive the response shape.

Every call is captured in ``self.calls`` so tests can assert what was
sent: ``provider.calls[0]["messages"]``, etc.
"""
from __future__ import annotations

from typing import Any, Callable

from project_db.ai.providers.base import (
    LLMMessage,
    LLMProvider,
    LLMResponse,
    ResponseFormat,
)


class MockLLMProvider(LLMProvider):
    name = "mock"

    def __init__(
        self,
        responses: list[str] | None = None,
        *,
        on_call: Callable[..., str] | None = None,
    ) -> None:
        self._responses = list(responses or [])
        self._on_call = on_call
        self.calls: list[dict[str, Any]] = []

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
        self.calls.append({
            "messages": messages,
            "system": system,
            "model": model,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "response_format": response_format,
        })

        if self._on_call is not None:
            content = self._on_call(
                messages=messages, system=system, model=model,
                temperature=temperature, max_tokens=max_tokens,
                response_format=response_format,
            )
        elif self._responses:
            idx = min(len(self.calls) - 1, len(self._responses) - 1)
            content = self._responses[idx]
        else:
            content = ""

        return LLMResponse(
            content=content,
            finish_reason="stop",
            usage={"input_tokens": sum(len(m.content) for m in messages) // 4,
                   "output_tokens": len(content) // 4},
            model=model or "mock",
            raw=None,
        )
