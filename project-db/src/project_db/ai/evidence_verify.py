"""Slice 7: deterministic verification of an extraction against its cited evidence.

A reconcile-OK extraction can still rest on a HALLUCINATED total -- the model
invents a grand total, then emits lines that happen to sum to it, so the reconcile
check passes on numbers that are not in the document. This module checks the
model's numbers against the structured evidence the document actually contains:
the stated_total and each line amount must appear as a real value somewhere in the
``EvidenceSpan`` bundle.

Pure + deterministic (no LLM): it reuses the financial layer's value-based amount
matcher (``_amount_in_text`` -- 2-dp tolerant, so 3,600.00 / 3600 / 3600.0 all
match) against the bundle's rendered text, which contains every cell value.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from project_db.ai.financials import _amount_in_text, _norm


@dataclass
class EvidenceVerification:
    """Deterministic grounding facts for one document's extraction."""

    total_in_evidence: bool | None  # None = the model stated no total to check
    lines_grounded: int  # line amounts found verbatim in the evidence
    lines_total: int  # line amounts checked (non-null)

    @property
    def all_lines_grounded(self) -> bool:
        return self.lines_total > 0 and self.lines_grounded == self.lines_total

    @property
    def total_grounded(self) -> bool:
        """True when a stated total exists AND appears in the evidence. A model
        that states no total is NOT 'grounded' (nothing to anchor the sum to)."""
        return self.total_in_evidence is True

    @property
    def fully_grounded(self) -> bool:
        """Every line amount is in the evidence and the stated total is too --
        the strongest deterministic trust signal short of an LLM verifier."""
        return self.all_lines_grounded and self.total_grounded

    def summary(self) -> str:
        tot = {True: "in-evidence", False: "NOT-in-evidence", None: "none-stated"}[
            self.total_in_evidence
        ]
        return f"lines grounded {self.lines_grounded}/{self.lines_total}, stated_total {tot}"


def verify_against_evidence(
    evidence_text: str | None,
    *,
    line_amounts: list[Decimal | None],
    stated_total: Decimal | None,
) -> EvidenceVerification:
    """Check that the extracted amounts actually appear in *evidence_text*.

    *evidence_text* should be the cited evidence (e.g. ``bundle.render_for_llm()``),
    which contains every parsed cell value. Returns grounding counts; the caller
    decides how strict to be (e.g. require ``total_grounded`` before trusting).
    """
    norm = _norm(evidence_text or "")
    checked = [a for a in line_amounts if a is not None]
    grounded = sum(1 for a in checked if _amount_in_text(a, norm))
    total_in = None if stated_total is None else _amount_in_text(stated_total, norm)
    return EvidenceVerification(
        total_in_evidence=total_in,
        lines_grounded=grounded,
        lines_total=len(checked),
    )
