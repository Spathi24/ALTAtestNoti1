"""Tests for the LLM provider abstraction layer.

Three providers, one contract.  These tests verify:

  * The abstract base's complete_json wrapper handles retry-on-bad-JSON
    transparently for ANY provider.
  * MockLLMProvider is faithful enough for downstream tests to rely on.
  * AnthropicProvider translates messages correctly (mocked SDK).
  * OpenAICompatibleProvider builds the right HTTP payload (mocked httpx).
  * get_default_provider() picks the right backend from env vars.

Real-network tests are intentionally absent -- those live in a future
integration suite.  Everything here runs offline.
"""
from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from project_db.ai.providers import (
    AnthropicProvider,
    LLMMessage,
    LLMProviderError,
    LLMResponse,
    MockLLMProvider,
    OpenAICompatibleProvider,
    get_default_provider,
    get_fast_provider,
)
from project_db.ai.providers.base import LLMProvider


@pytest.fixture(autouse=True)
def _no_openai_backup(monkeypatch):
    """These tests probe BACKEND RESOLUTION; the Anthropic->OpenAI fallback is
    covered in test_provider_fallback.py.  Ensure a leaked OPENAI_API_KEY (from
    .env in a full-suite run) doesn't wrap providers in a FallbackProvider here.
    """
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)


# ---------------------------------------------------------------------------
# MockLLMProvider
# ---------------------------------------------------------------------------


class TestMockLLMProvider:
    def test_returns_canned_response(self):
        p = MockLLMProvider(responses=["hello"])
        resp = p.complete(messages=[LLMMessage(role="user", content="hi")])
        assert resp.content == "hello"
        assert resp.finish_reason == "stop"

    def test_sticks_on_last_response_after_exhausted(self):
        p = MockLLMProvider(responses=["a", "b"])
        for _ in range(5):
            assert p.complete(messages=[LLMMessage(role="user", content="x")]).content in ("a", "b")
        # Sequential: 1st = "a", 2nd = "b", 3rd-5th = "b" (sticky)
        assert p.complete(messages=[LLMMessage(role="user", content="x")]).content == "b"

    def test_on_call_callable_overrides(self):
        p = MockLLMProvider(on_call=lambda **kw: f"echo:{kw['messages'][0].content}")
        resp = p.complete(messages=[LLMMessage(role="user", content="ping")])
        assert resp.content == "echo:ping"

    def test_captures_all_calls(self):
        p = MockLLMProvider(responses=["x"])
        p.complete(messages=[LLMMessage(role="user", content="a")], system="be brief")
        p.complete(messages=[LLMMessage(role="user", content="b")], temperature=0.7)
        assert len(p.calls) == 2
        assert p.calls[0]["system"] == "be brief"
        assert p.calls[1]["temperature"] == 0.7


# ---------------------------------------------------------------------------
# complete_json (base class) — exercised via the mock
# ---------------------------------------------------------------------------


class TestCompleteJson:
    def test_parses_clean_json(self):
        p = MockLLMProvider(responses=['{"a": 1, "b": [2, 3]}'])
        out = p.complete_json(messages=[LLMMessage(role="user", content="give me JSON")])
        assert out == {"a": 1, "b": [2, 3]}

    def test_strips_markdown_fences(self):
        p = MockLLMProvider(responses=['```json\n{"ok": true}\n```'])
        assert p.complete_json(messages=[LLMMessage(role="user", content="x")]) == {"ok": True}

    def test_strips_unlabeled_fences(self):
        p = MockLLMProvider(responses=['```\n[1, 2, 3]\n```'])
        assert p.complete_json(messages=[LLMMessage(role="user", content="x")]) == [1, 2, 3]

    def test_retries_on_bad_json_and_succeeds(self):
        p = MockLLMProvider(responses=["not json", '{"recovered": true}'])
        out = p.complete_json(
            messages=[LLMMessage(role="user", content="x")],
            max_retries=1,
        )
        assert out == {"recovered": True}
        # Second call should have the parse-error correction appended.
        assert len(p.calls) == 2
        second_msgs = p.calls[1]["messages"]
        assert any("not valid JSON" in m.content for m in second_msgs)

    def test_raises_after_exhausting_retries(self):
        p = MockLLMProvider(responses=["nope", "still nope", "garbage"])
        with pytest.raises(LLMProviderError) as exc_info:
            p.complete_json(
                messages=[LLMMessage(role="user", content="x")],
                max_retries=2,
            )
        assert "not parseable JSON" in str(exc_info.value)

    def test_response_format_hint_passed_to_complete(self):
        p = MockLLMProvider(responses=['{"x": 1}'])
        p.complete_json(messages=[LLMMessage(role="user", content="x")])
        assert p.calls[0]["response_format"] == "json_object"


# ---------------------------------------------------------------------------
# AnthropicProvider
# ---------------------------------------------------------------------------


def _fake_anthropic_response(text: str, in_tokens: int = 10, out_tokens: int = 5):
    """Build a mock matching what the anthropic SDK returns."""
    content_block = MagicMock()
    content_block.text = text
    resp = MagicMock()
    resp.content = [content_block]
    resp.stop_reason = "end_turn"
    resp.model = "claude-test"
    resp.usage = MagicMock(input_tokens=in_tokens, output_tokens=out_tokens)
    return resp


class TestAnthropicProvider:
    def test_translates_messages_and_extracts_text(self):
        client = MagicMock()
        client.messages.create.return_value = _fake_anthropic_response("hi back")
        p = AnthropicProvider(client=client)

        resp = p.complete(
            messages=[LLMMessage(role="user", content="hi")],
            system="be terse",
        )
        assert resp.content == "hi back"
        assert resp.finish_reason == "end_turn"
        assert resp.usage == {"input_tokens": 10, "output_tokens": 5}

        # Verify the SDK call shape.
        call_kwargs = client.messages.create.call_args.kwargs
        assert call_kwargs["system"] == "be terse"
        assert call_kwargs["messages"] == [{"role": "user", "content": "hi"}]
        # System should NOT appear as a message turn.
        assert all(m["role"] != "system" for m in call_kwargs["messages"])

    def test_promotes_system_message_turn_to_system_field(self):
        """If caller passes system via a message turn, Anthropic provider lifts it."""
        client = MagicMock()
        client.messages.create.return_value = _fake_anthropic_response("ok")
        p = AnthropicProvider(client=client)

        p.complete(messages=[
            LLMMessage(role="system", content="from turn"),
            LLMMessage(role="user", content="hi"),
        ])
        call_kwargs = client.messages.create.call_args.kwargs
        assert call_kwargs["system"] == "from turn"
        # The system turn should not survive as a message.
        assert call_kwargs["messages"] == [{"role": "user", "content": "hi"}]

    def test_explicit_system_arg_wins_over_message_turn(self):
        client = MagicMock()
        client.messages.create.return_value = _fake_anthropic_response("ok")
        p = AnthropicProvider(client=client)

        p.complete(
            messages=[LLMMessage(role="system", content="from turn"),
                      LLMMessage(role="user", content="hi")],
            system="from arg",
        )
        assert client.messages.create.call_args.kwargs["system"] == "from arg"

    def test_sdk_error_wrapped_as_provider_error(self):
        client = MagicMock()
        client.messages.create.side_effect = RuntimeError("API exploded")
        p = AnthropicProvider(client=client)
        with pytest.raises(LLMProviderError) as exc:
            p.complete(messages=[LLMMessage(role="user", content="x")])
        assert "API exploded" in str(exc.value)

    def test_missing_api_key_raises_clean_error(self, monkeypatch):
        pytest.importorskip("anthropic")  # If SDK missing, a different error fires (also OK).
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        with pytest.raises(LLMProviderError) as exc:
            AnthropicProvider()
        assert "ANTHROPIC_API_KEY" in str(exc.value)


# ---------------------------------------------------------------------------
# OpenAICompatibleProvider
# ---------------------------------------------------------------------------


def _fake_oai_response(content: str):
    """Shape of OpenAI Chat Completions response."""
    return {
        "id": "chatcmpl-x",
        "object": "chat.completion",
        "created": 0,
        "model": "qwen2.5-32b",
        "choices": [{
            "index": 0,
            "message": {"role": "assistant", "content": content},
            "finish_reason": "stop",
        }],
        "usage": {"prompt_tokens": 7, "completion_tokens": 4, "total_tokens": 11},
    }


class TestOpenAICompatibleProvider:
    def test_builds_correct_request_payload(self):
        p = OpenAICompatibleProvider(base_url="http://localhost:8000/v1", default_model="qwen2.5-32b")

        mock_response = MagicMock()
        mock_response.json.return_value = _fake_oai_response("hello")
        mock_response.raise_for_status = MagicMock()
        with patch("httpx.post", return_value=mock_response) as mock_post:
            resp = p.complete(
                messages=[LLMMessage(role="user", content="hi")],
                system="be terse",
                response_format="json_object",
            )

        assert resp.content == "hello"
        assert resp.usage == {"input_tokens": 7, "output_tokens": 4}

        call_kwargs = mock_post.call_args.kwargs
        assert call_kwargs["json"]["model"] == "qwen2.5-32b"
        assert call_kwargs["json"]["messages"][0] == {"role": "system", "content": "be terse"}
        assert call_kwargs["json"]["messages"][1] == {"role": "user", "content": "hi"}
        assert call_kwargs["json"]["response_format"] == {"type": "json_object"}
        assert call_kwargs["headers"]["Authorization"].startswith("Bearer ")

    def test_no_system_message_when_unset(self):
        p = OpenAICompatibleProvider(base_url="http://localhost:8000/v1", default_model="m")
        mock_response = MagicMock()
        mock_response.json.return_value = _fake_oai_response("hi")
        mock_response.raise_for_status = MagicMock()
        with patch("httpx.post", return_value=mock_response) as mock_post:
            p.complete(messages=[LLMMessage(role="user", content="x")])
        # Only the user turn, no system.
        msgs = mock_post.call_args.kwargs["json"]["messages"]
        assert msgs == [{"role": "user", "content": "x"}]

    def test_http_error_wrapped(self):
        import httpx
        p = OpenAICompatibleProvider(base_url="http://localhost:8000/v1", default_model="m")
        with patch("httpx.post", side_effect=httpx.ConnectError("server down")):
            with pytest.raises(LLMProviderError) as exc:
                p.complete(messages=[LLMMessage(role="user", content="x")])
            assert "server down" in str(exc.value).lower() or "HTTP" in str(exc.value)

    def test_malformed_response_wrapped(self):
        p = OpenAICompatibleProvider(base_url="http://localhost:8000/v1", default_model="m")
        mock_response = MagicMock()
        mock_response.json.return_value = {"oops": "no choices key"}
        mock_response.raise_for_status = MagicMock()
        with patch("httpx.post", return_value=mock_response):
            with pytest.raises(LLMProviderError) as exc:
                p.complete(messages=[LLMMessage(role="user", content="x")])
            assert "unexpected response shape" in str(exc.value)

    def test_openai_timeout_env_var(self, monkeypatch):
        """OPENAI_TIMEOUT env var overrides the default 600s."""
        monkeypatch.setenv("OPENAI_TIMEOUT", "42")
        p = OpenAICompatibleProvider(base_url="http://localhost:8000/v1", default_model="m")
        assert p._timeout == 42.0

    def test_explicit_timeout_wins_over_env(self, monkeypatch):
        monkeypatch.setenv("OPENAI_TIMEOUT", "42")
        p = OpenAICompatibleProvider(
            base_url="http://localhost:8000/v1", default_model="m",
            timeout_seconds=99.0,
        )
        assert p._timeout == 99.0

    def test_default_timeout_generous_for_local(self, monkeypatch):
        """No env, no explicit -- should default high enough for CPU cold starts."""
        monkeypatch.delenv("OPENAI_TIMEOUT", raising=False)
        p = OpenAICompatibleProvider(base_url="http://localhost:8000/v1", default_model="m")
        assert p._timeout >= 300.0  # Generous; current value is 600.

    def test_response_format_text_omits_json_object_hint(self):
        p = OpenAICompatibleProvider(base_url="http://localhost:8000/v1", default_model="m")
        mock_response = MagicMock()
        mock_response.json.return_value = _fake_oai_response("x")
        mock_response.raise_for_status = MagicMock()
        with patch("httpx.post", return_value=mock_response) as mock_post:
            p.complete(messages=[LLMMessage(role="user", content="x")], response_format="text")
        # Default text mode should NOT include response_format in the payload.
        assert "response_format" not in mock_post.call_args.kwargs["json"]


# ---------------------------------------------------------------------------
# get_default_provider
# ---------------------------------------------------------------------------


class TestGetDefaultProvider:
    def test_explicit_mock(self, monkeypatch):
        monkeypatch.setenv("LLM_PROVIDER", "mock")
        assert isinstance(get_default_provider(), MockLLMProvider)

    def test_falls_back_to_mock_without_anthropic_key(self, monkeypatch):
        monkeypatch.delenv("LLM_PROVIDER", raising=False)
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        assert isinstance(get_default_provider(), MockLLMProvider)

    def test_picks_anthropic_when_key_present(self, monkeypatch):
        monkeypatch.delenv("LLM_PROVIDER", raising=False)
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
        # AnthropicProvider tries to import the SDK -- skip if not installed.
        try:
            import anthropic  # noqa: F401
        except ImportError:
            pytest.skip("anthropic SDK not installed in this env")
        provider = get_default_provider()
        assert isinstance(provider, AnthropicProvider)

    def test_openai_compatible_needs_env_vars(self, monkeypatch):
        monkeypatch.setenv("LLM_PROVIDER", "openai-compatible")
        monkeypatch.delenv("OPENAI_BASE_URL", raising=False)
        monkeypatch.delenv("OPENAI_MODEL", raising=False)
        with pytest.raises(LLMProviderError):
            get_default_provider()

    def test_openai_compatible_constructs_when_vars_set(self, monkeypatch):
        monkeypatch.setenv("LLM_PROVIDER", "openai-compatible")
        monkeypatch.setenv("OPENAI_BASE_URL", "http://localhost:11434/v1")
        monkeypatch.setenv("OPENAI_MODEL", "qwen2.5:32b")
        provider = get_default_provider()
        assert isinstance(provider, OpenAICompatibleProvider)

    def test_unknown_provider_raises(self, monkeypatch):
        monkeypatch.setenv("LLM_PROVIDER", "bogus")
        with pytest.raises(LLMProviderError):
            get_default_provider()


class TestGetFastProvider:
    """get_fast_provider resolves the same backend as get_default_provider
    but pins Anthropic to a small/fast (Haiku) model -- used by the `ask`
    LLM fallback so summarization-grade questions don't pay Sonnet prices."""

    def test_explicit_mock(self, monkeypatch):
        monkeypatch.setenv("LLM_PROVIDER", "mock")
        assert isinstance(get_fast_provider(), MockLLMProvider)

    def test_falls_back_to_mock_without_anthropic_key(self, monkeypatch):
        monkeypatch.delenv("LLM_PROVIDER", raising=False)
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        assert isinstance(get_fast_provider(), MockLLMProvider)

    def test_unknown_provider_raises(self, monkeypatch):
        monkeypatch.setenv("LLM_PROVIDER", "bogus")
        with pytest.raises(LLMProviderError):
            get_fast_provider()

    def test_anthropic_pinned_to_haiku(self, monkeypatch):
        monkeypatch.setenv("LLM_PROVIDER", "anthropic")
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
        monkeypatch.delenv("ANTHROPIC_MODEL_FAST", raising=False)
        try:
            import anthropic  # noqa: F401
        except ImportError:
            pytest.skip("anthropic SDK not installed in this env")
        provider = get_fast_provider()
        assert isinstance(provider, AnthropicProvider)
        # The fast provider must NOT be on the Sonnet-tier default.
        assert "haiku" in provider._default_model.lower()

    def test_anthropic_model_fast_env_override(self, monkeypatch):
        monkeypatch.setenv("LLM_PROVIDER", "anthropic")
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
        monkeypatch.setenv("ANTHROPIC_MODEL_FAST", "claude-custom-fast")
        try:
            import anthropic  # noqa: F401
        except ImportError:
            pytest.skip("anthropic SDK not installed in this env")
        assert get_fast_provider()._default_model == "claude-custom-fast"

    def test_default_provider_not_dragged_to_fast_model(self, monkeypatch):
        """Regression: get_default_provider (proposals) must stay Sonnet-tier."""
        monkeypatch.setenv("LLM_PROVIDER", "anthropic")
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
        monkeypatch.delenv("ANTHROPIC_MODEL", raising=False)
        try:
            import anthropic  # noqa: F401
        except ImportError:
            pytest.skip("anthropic SDK not installed in this env")
        assert "haiku" not in get_default_provider()._default_model.lower()


# ---------------------------------------------------------------------------
# Interface contract: every provider returns a well-formed LLMResponse
# ---------------------------------------------------------------------------


class TestProviderContract:
    """Smoke-check: every concrete provider, called the same way, produces
    a response with the same shape.  If we add a 4th provider tomorrow,
    add it to this list and the contract is enforced automatically."""

    def _all_providers(self):
        client = MagicMock()
        client.messages.create.return_value = _fake_anthropic_response("anthropic-said-this")
        anth = AnthropicProvider(client=client)

        mock_response = MagicMock()
        mock_response.json.return_value = _fake_oai_response("openai-said-this")
        mock_response.raise_for_status = MagicMock()
        oai_patch = patch("httpx.post", return_value=mock_response)
        oai_patch.start()
        oai = OpenAICompatibleProvider(base_url="http://localhost:8000/v1", default_model="m")

        return [
            ("mock", MockLLMProvider(responses=["mock-said-this"])),
            ("anthropic", anth),
            ("openai-compatible", oai),
        ], oai_patch

    def test_every_provider_returns_llmresponse(self):
        providers, patch_handle = self._all_providers()
        try:
            for name, p in providers:
                resp = p.complete(messages=[LLMMessage(role="user", content="hi")])
                assert isinstance(resp, LLMResponse), f"{name} returned {type(resp).__name__}"
                assert resp.content, f"{name} returned empty content"
                assert resp.finish_reason, f"{name} missing finish_reason"
        finally:
            patch_handle.stop()
