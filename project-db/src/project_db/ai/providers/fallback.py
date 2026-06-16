"""A provider that tries a primary backend, then a fallback on failure.

Keeps the better/preferred model (Anthropic) as the default while ensuring a
dead-credits / auth / outage situation degrades to the fallback (OpenAI)
instead of erroring the whole feature.  Owner decision 2026-06-04: "keep
Anthropic as the main client, but use OpenAI en lieu of a straight error."

Wraps at the ``complete`` / ``complete_json`` level so each backend's own retry
/ truncation logic runs fully on the primary before we move to the fallback.
"""

from __future__ import annotations

import logging
from typing import Any

from project_db.ai.providers.base import LLMProvider, LLMProviderError, LLMResponse

logger = logging.getLogger(__name__)


class FallbackProvider(LLMProvider):
    name = "fallback"

    def __init__(self, primary: LLMProvider, fallback: LLMProvider) -> None:
        self.primary = primary
        self.fallback = fallback
        self.name = f"{getattr(primary, 'name', '?')}->{getattr(fallback, 'name', '?')}"

    def complete(self, **kwargs: Any) -> LLMResponse:
        try:
            return self.primary.complete(**kwargs)
        except LLMProviderError as exc:
            logger.warning(
                "primary provider %s failed (%s); falling back to %s",
                getattr(self.primary, "name", "?"),
                exc,
                getattr(self.fallback, "name", "?"),
            )
            return self.fallback.complete(**kwargs)

    def complete_json(self, **kwargs: Any) -> Any:
        try:
            return self.primary.complete_json(**kwargs)
        except LLMProviderError as exc:
            logger.warning(
                "primary provider %s failed for JSON (%s); falling back to %s",
                getattr(self.primary, "name", "?"),
                exc,
                getattr(self.fallback, "name", "?"),
            )
            return self.fallback.complete_json(**kwargs)
