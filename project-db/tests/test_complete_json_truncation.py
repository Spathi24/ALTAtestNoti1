"""LLMProvider.complete_json: handles output-truncation correctly.

Background: 6554 Rue Saint Hubert's scope generation failed in
production -- the model's reply was cut off at the max_tokens ceiling
mid-JSON.  complete_json retried with the same cap and hit the wall
again.  The fix detects truncation via finish_reason and bumps
max_tokens for the retry; this file pins that behavior.
"""
from __future__ import annotations

from project_db.ai.providers.base import (
    LLMMessage,
    LLMProvider,
    LLMProviderError,
    LLMResponse,
)


class _ScriptedProvider(LLMProvider):
    """Returns responses from a script, recording every call's max_tokens.

    The script entries are tuples: (content, finish_reason).  Real
    backends populate finish_reason from the API; this mock matches the
    same field complete_json inspects.
    """
    name = "scripted"

    def __init__(self, script):
        self.script = list(script)
        self.calls: list[dict] = []

    def complete(self, *, messages, system=None, model=None,
                 temperature=0.0, max_tokens=4000, response_format="text"):
        content, finish = self.script.pop(0)
        self.calls.append({
            "max_tokens": max_tokens,
            "n_messages": len(messages),
        })
        return LLMResponse(
            content=content,
            finish_reason=finish,
            usage={},
            model="scripted",
            raw=None,
        )


def test_succeeds_on_first_valid_json():
    prov = _ScriptedProvider([('{"ok": true}', "stop")])
    result = prov.complete_json(
        messages=[LLMMessage(role="user", content="x")],
        max_tokens=2000,
    )
    assert result == {"ok": True}
    assert len(prov.calls) == 1
    assert prov.calls[0]["max_tokens"] == 2000


def test_retry_after_bad_json_keeps_same_max_tokens():
    """Non-truncation parse failure (e.g. model just wrote prose) -- we
    retry with the SAME cap.  Bumping tokens wouldn't help here."""
    prov = _ScriptedProvider([
        ("this is prose, not JSON", "stop"),
        ('{"ok": true}', "stop"),
    ])
    result = prov.complete_json(
        messages=[LLMMessage(role="user", content="x")],
        max_tokens=2000,
        max_retries=1,
    )
    assert result == {"ok": True}
    assert len(prov.calls) == 2
    # Both calls used the same max_tokens.
    assert prov.calls[0]["max_tokens"] == 2000
    assert prov.calls[1]["max_tokens"] == 2000


def test_retry_after_truncated_output_bumps_max_tokens():
    """When finish_reason indicates truncation, the retry must use
    a LARGER max_tokens -- retrying with the same cap will truncate
    again.  This is the 6554 fix."""
    # Anthropic's truncation signal:
    prov = _ScriptedProvider([
        ('{"scope_gaps": [{"scope_item": "Install kit', "max_tokens"),
        ('{"scope_gaps": []}', "stop"),
    ])
    result = prov.complete_json(
        messages=[LLMMessage(role="user", content="x")],
        max_tokens=2000,
        max_retries=1,
    )
    assert result == {"scope_gaps": []}
    assert len(prov.calls) == 2
    # First call used the requested cap.
    assert prov.calls[0]["max_tokens"] == 2000
    # Retry bumped the cap by 1.5x.
    assert prov.calls[1]["max_tokens"] == 3000


def test_retry_after_truncated_output_openai_compatible_finish_reason():
    """OpenAI / OpenAI-compatible backends use 'length' for the same
    condition.  complete_json must detect both."""
    prov = _ScriptedProvider([
        ('{"scope_gaps": [{"scope_item": "Install kit', "length"),
        ('{"scope_gaps": []}', "stop"),
    ])
    prov.complete_json(
        messages=[LLMMessage(role="user", content="x")],
        max_tokens=4000,
        max_retries=1,
    )
    assert prov.calls[1]["max_tokens"] == 6000  # 4000 * 1.5


def test_truncation_bump_respects_ceiling():
    """The bump must not exceed max_tokens_ceiling -- otherwise a
    misbehaving prompt could spend unboundedly."""
    prov = _ScriptedProvider([
        ('{"x": "trunc', "max_tokens"),
        ('{"x": 1}', "stop"),
    ])
    prov.complete_json(
        messages=[LLMMessage(role="user", content="x")],
        max_tokens=10_000,
        max_retries=1,
        max_tokens_ceiling=12_000,
    )
    # 10_000 * 1.5 = 15_000, capped at ceiling 12_000.
    assert prov.calls[1]["max_tokens"] == 12_000


def test_exhausted_retries_after_truncation_raises_with_hint():
    """When every attempt truncates, the final error must name truncation
    so the route / template can render a useful hint, instead of a
    generic 'bad JSON' message."""
    prov = _ScriptedProvider([
        ('{"a": "trunc', "max_tokens"),
        ('{"a": "still trunc', "max_tokens"),
    ])
    try:
        prov.complete_json(
            messages=[LLMMessage(role="user", content="x")],
            max_tokens=2000,
            max_retries=1,
        )
    except LLMProviderError as exc:
        msg = str(exc).lower()
        assert "truncat" in msg, f"error must mention truncation: {exc!r}"
        assert "max_tokens" in msg or "token cap" in msg
    else:
        raise AssertionError("complete_json should have raised after both truncated attempts")


def test_exhausted_retries_without_truncation_does_not_mention_truncation():
    """A non-truncation parse failure exhausting retries must NOT claim
    truncation -- that would mislead the caller into bumping max_tokens
    when the real problem is the prompt."""
    prov = _ScriptedProvider([
        ("prose 1", "stop"),
        ("prose 2", "stop"),
    ])
    try:
        prov.complete_json(
            messages=[LLMMessage(role="user", content="x")],
            max_tokens=2000,
            max_retries=1,
        )
    except LLMProviderError as exc:
        assert "truncat" not in str(exc).lower()
    else:
        raise AssertionError("complete_json should have raised")


def test_retry_appends_truncation_hint_to_followup_message():
    """The retry conversation should tell the model its previous reply
    was cut off; this gives the model a chance to be more concise."""
    prov = _ScriptedProvider([
        ('{"x": "trunc', "max_tokens"),
        ('{"x": 1}', "stop"),
    ])
    prov.complete_json(
        messages=[LLMMessage(role="user", content="ORIGINAL")],
        max_tokens=2000,
        max_retries=1,
    )
    # The retry sees original user + assistant + new user-followup.
    assert prov.calls[1]["n_messages"] == 3
