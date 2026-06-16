"""The /ask Haiku fallback uses an ASSERTIVE inferential prompt, not the
old over-conservative one.

Bug report 2025-05-26 (user): the askbot was "annoying" -- it refused
to answer broad / indirect questions, saying things like "I cannot
determine that from the snapshot."  Root cause: the system prompt
literally said "If the snapshot does not contain the answer, say so
plainly", which trained the model to bail out.

The rewrite swaps that for "infer the closest useful answer from
adjacent records and label the inference" + "Never end at a dead end"
+ "If a user asks what to do, give a recommendation, not just a
summary."  The anti-hallucination rules (never invent names / numbers
/ dates) are preserved -- that boundary is non-negotiable.

This file pins:
  - The new assertive phrases are in the system prompt.
  - The old over-conservative phrasing is gone.
  - max_tokens is 2048 (bumped from 1024).
  - The user-prompt wrapper also pushes for best-effort answers.
  - The anti-hallucination guardrails are still there.

Scope note: the proposal bots (timeline / scope) stay conservative
-- they extract facts for Monday write-back; refusal-on-uncertainty
is the desired behavior there.  This file does NOT test them.
"""

from __future__ import annotations

import pytest

from project_db.ai.providers.mock import MockLLMProvider
from project_db.ai.query import AiAssistant


@pytest.fixture
def mock_provider():
    return MockLLMProvider(responses=["mocked answer"])


@pytest.fixture
def empty_assistant(session, org):
    """An AiAssistant over an empty-but-valid DB.  Enough for the LLM
    pipeline to run -- the prompt content is what we're testing, not
    the data shape."""
    return AiAssistant(session)


def _last_call_args(prov: MockLLMProvider) -> dict:
    assert prov.calls, "provider was not called"
    return prov.calls[-1]


# ---------------------------------------------------------------------------
# System prompt: assertive behavior
# ---------------------------------------------------------------------------


class TestSystemPromptAssertive:
    def test_old_conservative_phrase_is_gone(self, empty_assistant, mock_provider):
        empty_assistant.answer_with_llm("anything", mock_provider)
        system = _last_call_args(mock_provider)["system"]
        # The exact phrasing that made the model bail:
        assert "say so plainly" not in system, (
            "the over-conservative 'say so plainly' phrasing must be "
            "gone -- it trained Haiku to give up on broad questions."
        )

    def test_new_assertive_phrases_present(self, empty_assistant, mock_provider):
        empty_assistant.answer_with_llm("anything", mock_provider)
        system = _last_call_args(mock_provider)["system"]
        # Pin a handful of the load-bearing assertive instructions.
        for phrase in [
            "assertive",
            "Do not give up",
            "infer the closest useful answer",
            "label",  # "label it as an inference"
            "give a recommendation",
            "Never end at a dead end",
        ]:
            assert phrase in system, (
                f"system prompt must contain {phrase!r} -- this is what "
                f"makes the askbot push past 'I cannot determine that'."
            )

    def test_anti_hallucination_rules_preserved(self, empty_assistant, mock_provider):
        """The new prompt is assertive but NOT permissive about
        inventing facts.  The hard rules stay."""
        empty_assistant.answer_with_llm("anything", mock_provider)
        system = _last_call_args(mock_provider)["system"]
        # The CRITICAL guard: model must not invent.
        assert "Never invent" in system
        # Inferences must be flagged, not presented as facts.
        assert "marked as inferences" in system or "MARKED as inferences" in system
        # The hard-fact source is the snapshot.
        assert "snapshot" in system.lower()


# ---------------------------------------------------------------------------
# User prompt: instruction at the TAIL pushes best-effort answers
# ---------------------------------------------------------------------------


class TestUserPromptPushesBestEffort:
    def test_old_user_terminator_gone(self, empty_assistant, mock_provider):
        empty_assistant.answer_with_llm("what should we do?", mock_provider)
        msgs = _last_call_args(mock_provider)["messages"]
        user_content = msgs[-1].content
        # The old terminator -- "Answer using only the snapshot above." --
        # was the reinforcement that trained the model to be conservative.
        # The new terminator MUST NOT be that bare line; it should be the
        # longer "infer the closest useful answer ... do not stop" version.
        assert user_content.rstrip().endswith("no relevant records exist."), (
            "user prompt must end with the assertive instruction, not "
            "the old 'Answer using only the snapshot above.' bare line."
        )

    def test_new_user_terminator_present(self, empty_assistant, mock_provider):
        empty_assistant.answer_with_llm("what should we do?", mock_provider)
        msgs = _last_call_args(mock_provider)["messages"]
        user_content = msgs[-1].content
        for phrase in [
            "First give the strongest",
            "infer the closest useful answer",
            "label the inference",
            "Do not stop at missing information",
        ]:
            assert phrase in user_content, f"user prompt must contain {phrase!r}."


# ---------------------------------------------------------------------------
# max_tokens raised 1024 -> 2048
# ---------------------------------------------------------------------------


class TestMaxTokensBumped:
    def test_max_tokens_is_at_least_2048(self, empty_assistant, mock_provider):
        empty_assistant.answer_with_llm("anything", mock_provider)
        call = _last_call_args(mock_provider)
        assert call["max_tokens"] >= 2048, (
            "the askbot's new assertive style produces longer answers "
            "(recommendations + inferences + data citations) and was "
            "being truncated at 1024.  max_tokens >= 2048 required."
        )


# ---------------------------------------------------------------------------
# Proposal bots are NOT affected (scope check)
# ---------------------------------------------------------------------------


class TestProposalBotsStayConservative:
    """Sanity test: the timeline / scope proposal prompts still contain
    their existing conservatism markers.  This file should fail loudly
    if someone accidentally applies the askbot's assertive style to a
    proposal prompt (where it would actively cause hallucination)."""

    def test_timeline_prompt_still_forbids_inventing(self):
        # _build_timeline_prompt is internal; we import directly to check.
        # We can't call it without a ProjectContext, but its source text
        # contains the conservative anchors -- read the function's
        # source and check.
        import inspect

        from project_db.ai.proposals import _build_timeline_prompt

        src = inspect.getsource(_build_timeline_prompt).lower()
        # The timeline prompt is explicit about staying conservative.
        # Look for ANY of the existing anchors that mean "don't make stuff up".
        conservative_anchors = [
            "do not propose",
            "do not propose -- returning fewer",
            "not evidence",
            "must cite its specific evidence",
            "anchor every proposed date",
            "must both be on or after today",
        ]
        assert any(a in src for a in conservative_anchors), (
            "timeline prompt should retain its conservative anchors -- "
            "if this fails, someone may have applied the askbot's "
            "assertive style to a proposal bot, which would cause "
            "active hallucination of dates."
        )

    def test_scope_prompt_still_forbids_inventing(self):
        import inspect

        from project_db.ai.proposals import _build_scope_prompt

        src = inspect.getsource(_build_scope_prompt)
        assert (
            "never invent" in src.lower()
            or "do not flag" in src.lower()
            or "explicitly stated" in src.lower()
        ), "scope prompt should still warn against inventing scope."
