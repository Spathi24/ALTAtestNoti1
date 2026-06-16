"""Anthropic primary + OpenAI backup (owner 2026-06-04)."""

from __future__ import annotations

from project_db.ai.providers import (
    AnthropicProvider,
    FallbackProvider,
    LLMMessage,
    LLMProvider,
    LLMProviderError,
    LLMResponse,
    MockLLMProvider,
    OpenAICompatibleProvider,
    get_default_provider,
    get_fast_provider,
)


class _Boom(LLMProvider):
    name = "boom"

    def complete(self, **kwargs):
        raise LLMProviderError("out of credits")


def _resp(text):
    return LLMResponse(content=text, finish_reason="stop", usage={}, model="m", raw=None)


class TestResolution:
    def test_wraps_anthropic_with_openai_backup(self, monkeypatch):
        monkeypatch.setenv("ANTHROPIC_API_KEY", "a-key")
        monkeypatch.setenv("OPENAI_API_KEY", "o-key")
        monkeypatch.delenv("LLM_PROVIDER", raising=False)
        p = get_default_provider()
        assert isinstance(p, FallbackProvider)
        assert isinstance(p.primary, AnthropicProvider)
        assert isinstance(p.fallback, OpenAICompatibleProvider)
        assert "anthropic" in p.name and "openai" in p.name

    def test_fast_also_wrapped(self, monkeypatch):
        monkeypatch.setenv("ANTHROPIC_API_KEY", "a-key")
        monkeypatch.setenv("OPENAI_API_KEY", "o-key")
        monkeypatch.delenv("LLM_PROVIDER", raising=False)
        assert isinstance(get_fast_provider(), FallbackProvider)

    def test_openai_used_directly_without_anthropic(self, monkeypatch):
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        monkeypatch.setenv("OPENAI_API_KEY", "o-key")
        monkeypatch.delenv("LLM_PROVIDER", raising=False)
        p = get_default_provider()
        assert isinstance(p, OpenAICompatibleProvider)

    def test_no_backup_without_openai_key(self, monkeypatch):
        monkeypatch.setenv("ANTHROPIC_API_KEY", "a-key")
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        monkeypatch.delenv("LLM_PROVIDER", raising=False)
        assert isinstance(get_default_provider(), AnthropicProvider)

    def test_explicit_mock_respected(self, monkeypatch):
        monkeypatch.setenv("LLM_PROVIDER", "mock")
        monkeypatch.setenv("OPENAI_API_KEY", "o-key")
        assert isinstance(get_default_provider(), MockLLMProvider)


class TestFallbackBehavior:
    def test_complete_uses_primary_on_success(self):
        primary = MockLLMProvider(responses=["from primary"])
        fallback = MockLLMProvider(responses=["from fallback"])
        fp = FallbackProvider(primary, fallback)
        out = fp.complete(messages=[LLMMessage(role="user", content="hi")])
        assert out.content == "from primary"
        assert fallback.calls == []  # fallback never touched

    def test_complete_falls_back_on_primary_error(self):
        fallback = MockLLMProvider(responses=["from fallback"])
        fp = FallbackProvider(_Boom(), fallback)
        out = fp.complete(messages=[LLMMessage(role="user", content="hi")])
        assert out.content == "from fallback"

    def test_complete_json_falls_back(self):
        fallback = MockLLMProvider(responses=['{"ok": true}'])
        fp = FallbackProvider(_Boom(), fallback)
        out = fp.complete_json(messages=[LLMMessage(role="user", content="hi")])
        assert out == {"ok": True}
