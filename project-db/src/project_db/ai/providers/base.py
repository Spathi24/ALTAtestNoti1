"""LLM provider abstraction.

The contract every backend implements.  Designed so the rest of the code
(prompt building, proposal writing, approval flow) never imports any
specific SDK -- swap backends by config, not by code change.

Canonical message shape mirrors OpenAI Chat Completions because every
local-model server (Ollama, vLLM, llama.cpp, LM Studio, TGI) exposes
that shape natively.  Anthropic adapts via a thin translator inside
its provider.

Design rules:
  - One required method (`complete`).  Higher-level conveniences
    (`complete_json` with retry) live on the base class so every
    provider gets them for free.
  - Return a structured ``LLMResponse``.  Callers should not inspect
    backend-specific raw payloads except for debugging.
  - Never raise generic exceptions.  Wrap backend errors in
    ``LLMProviderError`` so callers can write one ``except`` block.
"""
from __future__ import annotations

import json
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Literal

logger = logging.getLogger(__name__)

Role = Literal["system", "user", "assistant"]
ResponseFormat = Literal["text", "json_object"]


@dataclass
class LLMMessage:
    """One message in the conversation.

    System messages are conventionally first.  Anthropic's API takes the
    system prompt as a separate field -- our providers handle that
    translation internally.
    """
    role: Role
    content: str


@dataclass
class LLMResponse:
    """A model's response, normalized across backends."""
    content: str
    finish_reason: str            # "stop" | "length" | "error" | backend-specific
    usage: dict[str, int] = field(default_factory=dict)  # {"input_tokens": N, "output_tokens": N}
    model: str | None = None
    raw: Any = None               # backend-specific payload, for debugging


class LLMProviderError(RuntimeError):
    """Raised when a provider can't complete the request.

    Wraps API errors, transport errors, and bad-JSON failures from
    ``complete_json``.  Callers can do `except LLMProviderError` once.
    """


class LLMProvider(ABC):
    """Abstract base.  Every backend implements ``complete``.

    Subclasses MUST NOT raise raw SDK exceptions -- catch and re-raise
    as ``LLMProviderError`` so callers have a single failure mode.
    """

    name: str = "base"

    @abstractmethod
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
        """Run one completion and return the response.

        Args:
          messages:        Ordered list of turns.  System message (if any)
                           should be passed via ``system``, not as a turn.
          system:          Optional system prompt.
          model:           Provider-specific model id; falls back to the
                           provider's default if None.
          temperature:     Sampling temperature.  Default 0.0 because
                           every downstream prompt wants determinism.
          max_tokens:      Cap on output length.
          response_format: "json_object" is a HINT -- backends that
                           support it (OpenAI, most local servers) will
                           constrain decoding.  Backends that don't
                           (Anthropic) ignore it; use ``complete_json``
                           if you need a parsed result.
        """

    # Backend finish_reason values that mean "I ran out of room, the
    # output is truncated."  Normalized across backends:
    #   - Anthropic: stop_reason = "max_tokens"
    #   - OpenAI / OpenAI-compatible: finish_reason = "length"
    _TRUNCATION_REASONS = frozenset({"max_tokens", "length"})

    def complete_json(
        self,
        *,
        messages: list[LLMMessage],
        system: str | None = None,
        model: str | None = None,
        max_retries: int = 1,
        max_tokens: int = 4000,
        max_tokens_ceiling: int = 16000,
    ) -> Any:
        """Convenience: call ``complete`` and parse the response as JSON.

        On parse failure, retries up to ``max_retries`` times by replaying
        the conversation with an explicit "your previous output was not
        valid JSON, here is the parse error" instruction.  Works on
        every backend regardless of native structured-output support.

        Truncation handling: when the previous response had
        ``finish_reason`` in ``_TRUNCATION_REASONS``, the parse failure
        is almost certainly because the model ran out of room.  Retrying
        with the same cap is wasted -- the next call will also truncate.
        We bump ``max_tokens`` by 1.5x (capped at ``max_tokens_ceiling``)
        for the retry, and the error message names truncation
        specifically so the caller can render a useful hint instead of
        a generic "bad JSON" message.

        Raises ``LLMProviderError`` after exhausting retries.
        """
        attempt = 0
        last_error: Exception | None = None
        last_was_truncated = False
        current_max_tokens = max_tokens
        convo = list(messages)
        while attempt <= max_retries:
            resp = self.complete(
                messages=convo,
                system=system,
                model=model,
                temperature=0.0,
                max_tokens=current_max_tokens,
                response_format="json_object",
            )
            text = resp.content.strip()
            # Strip common preambles: ```json ... ```  fences.
            if text.startswith("```"):
                text = text.split("\n", 1)[1] if "\n" in text else text
                if text.endswith("```"):
                    text = text.rsplit("```", 1)[0]
                text = text.strip()
            try:
                return json.loads(text)
            except json.JSONDecodeError as exc:
                last_error = exc
                truncated = resp.finish_reason in self._TRUNCATION_REASONS
                last_was_truncated = truncated
                logger.warning(
                    "[%s] JSON parse failed on attempt %d (finish_reason=%s%s): %s",
                    self.name, attempt + 1, resp.finish_reason,
                    "; output truncated -- bumping max_tokens for retry"
                    if truncated else "",
                    exc,
                )
                # If we ran out of room last time, retrying with the same
                # cap is wasted -- bump it.  Cap the growth so we don't
                # spend unboundedly on a misbehaving prompt.
                if truncated:
                    current_max_tokens = min(
                        int(current_max_tokens * 1.5),
                        max_tokens_ceiling,
                    )
                convo = list(messages) + [
                    LLMMessage(role="assistant", content=resp.content),
                    LLMMessage(
                        role="user",
                        content=(
                            f"Your previous output was not valid JSON.  "
                            f"Parse error: {exc}.  "
                            + (
                                "Your previous reply was cut off because "
                                "you ran out of token budget; be more "
                                "concise this time.  "
                                if truncated else ""
                            )
                            + "Reply with ONLY valid JSON, no prose, no "
                            "markdown fences."
                        ),
                    ),
                ]
                attempt += 1
        # Surface truncation explicitly so callers can render a useful
        # message ("the model's output was too long for the configured
        # max_tokens") instead of a generic "bad JSON".
        truncation_hint = (
            "  The model's output was truncated at the token cap on the "
            "last attempt -- pass a larger max_tokens, or shrink the "
            "input prompt."
            if last_was_truncated else ""
        )
        raise LLMProviderError(
            f"{self.name}: response was not parseable JSON after "
            f"{max_retries + 1} attempts.  Last error: {last_error}."
            + truncation_hint
        )
