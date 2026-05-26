"""Reasoning prompts demand QUOTED EXCERPTS from source documents.

2026-05-26 tightening: previous prompts asked the model to cite
"which document and clause", which produced structural reasoning
("the contract mentions energy targets") instead of evidence-grounded
reasoning ("Final SOW Section 4: 'Contractor shall perform a quality
inspection at the conclusion of each phase'").

The fix bumped both prompt versions and rewrote the reasoning-field
spec in each prompt to require:
  - CONTRACT-sourced evidence: direct quoted excerpt in double quotes.
  - SCHEDULE-SEQUENCE evidence (timeline): named neighbour tasks + dates.
  - ROADMAP-sourced evidence: phase-ordinal+name citation.

Tests here pin the prompt language so a future "clean up the prompt"
edit doesn't accidentally drop the requirement.  Anti-hallucination
guards in the prompt-philosophy boundary (HANDOFF section 6) stay
intact -- this is a SHARPENING of the existing conservative posture,
not a loosening.
"""
from __future__ import annotations

from datetime import date

import pytest

from project_db.ai.context import ProjectContext
from project_db.ai.proposals import (
    SCOPE_PROMPT_VERSION,
    TIMELINE_PROMPT_VERSION,
    _build_scope_prompt,
    _build_timeline_prompt,
)


def _ctx() -> ProjectContext:
    return ProjectContext(
        project={"name": "P", "code": None, "status": "ACTIVE"},
        client=None,
        tasks=[],
        documents=[],
        document_texts=[
            {"name": "SOW.pdf", "folder_path": "p/",
             "mime_type": "application/pdf",
             "text": "Scope: install kitchen.", "truncated": False,
             "document_id": "abc"}
        ],
        invoices=[],
        daily_logs=[],
        truncated=False,
    )


# ---------------------------------------------------------------------------
# Prompt versions bumped
# ---------------------------------------------------------------------------


class TestVersions:
    def test_timeline_version_includes_quoted_milestone(self):
        assert "quoted" in TIMELINE_PROMPT_VERSION

    def test_scope_version_includes_quoted_milestone(self):
        assert "quoted" in SCOPE_PROMPT_VERSION


# ---------------------------------------------------------------------------
# Scope prompt -- without roadmap
# ---------------------------------------------------------------------------


class TestScopePromptDemandsQuotedExcerpt:
    def test_no_roadmap_contract_only_path(self):
        sys_p, user_p = _build_scope_prompt(_ctx(), roadmap_block="")
        # The EVIDENCE-CITATION block must be present
        assert "EVIDENCE-CITATION REQUIREMENT" in user_p
        # Must demand a QUOTED EXCERPT for contract evidence
        assert "QUOTED EXCERPT" in user_p
        # Must reject lazy reasoning
        assert "REJECTED" in user_p
        # Without roadmap, the prompt should NOT mention roadmap-evidence rules
        assert "ROADMAP-sourced gap" not in user_p

    def test_with_roadmap_both_evidence_rules_present(self):
        block = (
            "=== CANONICAL CONTRACTOR-RELEVANT ROADMAP ===\n"
            "-- CA phase --\n  [CA-01] (BOTH) Punch List"
        )
        sys_p, user_p = _build_scope_prompt(_ctx(), roadmap_block=block)
        # Both evidence rules must be present
        assert "QUOTED EXCERPT" in user_p  # contract rule
        assert "ROADMAP-sourced gap" in user_p  # roadmap rule
        assert "phase-ordinal+name" in user_p  # roadmap citation style


# ---------------------------------------------------------------------------
# Timeline prompt
# ---------------------------------------------------------------------------


class TestTimelinePromptDemandsSpecificEvidence:
    def test_evidence_block_present(self):
        sys_p, user_p = _build_timeline_prompt(
            _ctx(),
            dateless=[{"title": "T", "is_subitem": False}],
            dated=[],
            today=date(2026, 6, 1),
            roadmap_block="",
        )
        assert "EVIDENCE-CITATION REQUIREMENT" in user_p
        assert "QUOTED EXCERPT" in user_p
        # The three evidence sources are explicitly named
        assert "DOCUMENT" in user_p
        assert "SCHEDULE SEQUENCE" in user_p
        # Lazy reasoning rejected
        assert "REJECTED" in user_p
        # The schedule-sequence example phrasing exists
        assert "neighbour" in user_p.lower()

    def test_roadmap_evidence_added_when_block_provided(self):
        block = (
            "=== CANONICAL CONTRACTOR-RELEVANT ROADMAP ===\n"
            "-- CA phase --\n  [CA-01] (BOTH) Punch List"
        )
        sys_p, user_p = _build_timeline_prompt(
            _ctx(),
            dateless=[{"title": "T", "is_subitem": False}],
            dated=[],
            today=date(2026, 6, 1),
            roadmap_block=block,
        )
        # All three citation styles documented
        assert "QUOTED EXCERPT" in user_p
        assert "SCHEDULE SEQUENCE" in user_p
        assert "ROADMAP ENTRY" in user_p
        assert "phase-ordinal+name" in user_p


# ---------------------------------------------------------------------------
# Anti-hallucination posture preserved
# ---------------------------------------------------------------------------


class TestConservativePosturePreserved:
    """The tightening is a SHARPENING, not a loosening.  The existing
    "do not invent" / "returning fewer is correct" rules must still
    be in the system prompt."""

    def test_scope_system_still_forbids_inventing(self):
        sys_p, _ = _build_scope_prompt(_ctx(), roadmap_block="")
        assert "Never invent" in sys_p
        assert "Returning few flags, or none, is correct" in sys_p

    def test_timeline_system_still_demands_anchoring(self):
        sys_p, _ = _build_timeline_prompt(
            _ctx(),
            dateless=[{"title": "T", "is_subitem": False}],
            dated=[],
            today=date(2026, 6, 1),
        )
        # The "anchor to known schedule" rule and the past-date guard
        assert "ANCHOR every proposed date" in sys_p
        assert "must both be on or after today" in sys_p
