"""Slice 7: deterministic evidence verification (ai/evidence_verify.py).

Pure -- no DB, no LLM. Checks that extracted amounts are grounded in the cited
evidence text (value-based, 2-dp tolerant).
"""

from __future__ import annotations

from decimal import Decimal

from project_db.ai.evidence_verify import verify_against_evidence

EVIDENCE = (
    "## Table -- sheet 'Quote'\n"
    "| Description | Total Amount |\n"
    "| Demolition | $1,600.00 |\n"
    "| Carpentry | $5,080.00 |\n"
    "| Grand Total | $6,680.00 |\n"
)


def _d(x):
    return Decimal(str(x))


def test_grounded_amounts_are_found():
    v = verify_against_evidence(
        EVIDENCE, line_amounts=[_d("1600"), _d("5080")], stated_total=_d("6680")
    )
    assert v.lines_grounded == 2 and v.lines_total == 2
    assert v.all_lines_grounded is True
    assert v.total_in_evidence is True
    assert v.total_grounded is True
    assert v.fully_grounded is True


def test_decimal_tolerant_matching():
    # 1600 / 1,600.00 / 1600.0 all match the same value.
    v = verify_against_evidence(EVIDENCE, line_amounts=[_d("1600.0")], stated_total=_d("6680.00"))
    assert v.all_lines_grounded is True and v.total_in_evidence is True


def test_hallucinated_total_is_not_grounded():
    # A total the document does not contain -> not in evidence (the Slice-7 catch).
    v = verify_against_evidence(
        EVIDENCE, line_amounts=[_d("1600"), _d("5080")], stated_total=_d("99999")
    )
    assert v.all_lines_grounded is True
    assert v.total_in_evidence is False
    assert v.fully_grounded is False


def test_ungrounded_line_is_counted():
    v = verify_against_evidence(
        EVIDENCE, line_amounts=[_d("1600"), _d("4242")], stated_total=_d("6680")
    )
    assert v.lines_grounded == 1 and v.lines_total == 2
    assert v.all_lines_grounded is False


def test_no_stated_total_is_none_not_false():
    v = verify_against_evidence(EVIDENCE, line_amounts=[_d("1600")], stated_total=None)
    assert v.total_in_evidence is None
    assert v.total_grounded is False  # nothing to anchor to
    assert v.summary().endswith("none-stated")
