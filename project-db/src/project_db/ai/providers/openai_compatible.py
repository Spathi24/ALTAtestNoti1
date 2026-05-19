"""OpenAI-compatible Chat Completions provider.

Works with any server speaking the OpenAI Chat Completions wire format:
  - Ollama        (default http://localhost:11434/v1)
  - vLLM          (e.g. http://localhost:8000/v1)
  - llama.cpp HTTP server
  - LM Studio
  - TGI in OpenAI mode
  - OpenAI itself (https://api.openai.com/v1)

This is the provider we'll point at the Mac mini once the local model
is up.  Zero new code -- just construct with a different ``base_url``.

Uses ``httpx`` (already a project dependency); no openai SDK needed.
"""
from __future__ import annotations

import logging
import os
from typing import Any

import httpx

from project_db.ai.providers.base import (
    LLMMessage,
    LLMProvider,
    LLMProviderError,
    LLMResponse,
    ResponseFormat,
)

logger = logging.getLogger(__name__)


class OpenAICompatibleProvider(LLMProvider):
    name = "openai-compatible"

    def __init__(
        self,
        *,
        base_url: str,
        default_model: str,
        api_key: str | None = None,
        timeout_seconds: float | None = None,
    ) -> None:
        """
        Args:
          base_url:       e.g. "http://localhost:11434/v1" for Ollama,
                          "https://api.openai.com/v1" for OpenAI.
                          Trailing slash optional.
          default_model:  Model id the server recognizes (e.g.
                          "qwen2.5:32b" for Ollama, "gpt-4o" for OpenAI).
          api_key:        Many local servers ignore auth -- pass any
                          non-empty string ("EMPTY" is conventional).
                          Reads OPENAI_API_KEY env var if None.
          timeout_seconds: HTTP timeout per request.  If None, reads
                          OPENAI_TIMEOUT env var, else defaults to 600s.
                          Cold-start of a local CPU model + 1k+ input
                          tokens routinely runs 60-180s; cloud APIs
                          finish in <30s.  We default generous so the
                          local-laptop happy path doesn't blow up on
                          first use; tune down via env var if you'd
                          rather fail fast.
        """
        self._base_url = base_url.rstrip("/")
        self._default_model = default_model
        self._api_key = api_key or os.environ.get("OPENAI_API_KEY") or "EMPTY"
        if timeout_seconds is None:
            env_val = os.environ.get("OPENAI_TIMEOUT")
            self._timeout = float(env_val) if env_val else 600.0
        else:
            self._timeout = timeout_seconds

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
        # OpenAI shape: system is a message turn (role="system" first).
        wire_messages: list[dict[str, str]] = []
        if system:
            wire_messages.append({"role": "system", "content": system})
        for m in messages:
            wire_messages.append({"role": m.role, "content": m.content})

        payload: dict[str, Any] = {
            "model": model or self._default_model,
            "messages": wire_messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        # response_format is honored by OpenAI + most local backends.
        # Backends that ignore it return free text -- complete_json handles
        # parsing/retry on top.
        if response_format == "json_object":
            payload["response_format"] = {"type": "json_object"}

        try:
            resp = httpx.post(
                f"{self._base_url}/chat/completions",
                json=payload,
                headers={
                    "Authorization": f"Bearer {self._api_key}",
                    "Content-Type": "application/json",
                },
                timeout=self._timeout,
            )
            resp.raise_for_status()
            data = resp.json()
        except httpx.HTTPError as exc:
            raise LLMProviderError(f"{self.name} HTTP error: {exc}") from exc
        except ValueError as exc:  # JSON decode
            raise LLMProviderError(f"{self.name}: non-JSON response: {exc}") from exc

        try:
            choice = data["choices"][0]
            content = choice["message"]["content"]
            finish = choice.get("finish_reason", "stop")
        except (KeyError, IndexError, TypeError) as exc:
            raise LLMProviderError(
                f"{self.name}: unexpected response shape: {data!r}"
            ) from exc

        usage = {}
        if "usage" in data and isinstance(data["usage"], dict):
            usage = {
                "input_tokens": data["usage"].get("prompt_tokens", 0),
                "output_tokens": data["usage"].get("completion_tokens", 0),
            }

        return LLMResponse(
            content=content,
            finish_reason=finish or "stop",
            usage=usage,
            model=data.get("model", payload["model"]),
            raw=data,
        )
