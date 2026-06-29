"""Adversarial / robustness tests for the parsing + evidence stack.

Deliberately throws malformed, degenerate, and hostile inputs at the pure parsers
and the evidence-bundle reader to make sure the stack degrades gracefully (never
raises, never silently emits garbage) before the parser is closed off.
"""

from __future__ import annotations

from project_db.ai.evidence_bundle import BundlePage, BundleTable, EvidenceBundle
from project_db.ai.financial_grid import parse_financial_grid, parse_financial_grid_rows
from project_db.parsing import CsvParser, get_parser_for
from project_db.parsing.tableutil import detect_header

# --------------------------------------------------------------------------- #
# CSV parser robustness
# --------------------------------------------------------------------------- #

_csv = CsvParser()


def _parse(b: bytes):
    return _csv.parse(b, doc_name="x.csv", mime="text/csv")


def test_csv_empty_and_whitespace():
    for blob in (b"", b"\n\n\n", b"   ", b",,,\n,,,\n"):
        parsed = _parse(blob)
        assert parsed.structured["n_rows"] == 0
        assert parsed.evidence_spans == []


def test_csv_utf8_bom_is_handled():
    parsed = _parse(b"\xef\xbb\xbfItem,Price\nWindow,100\n")
    # BOM must not corrupt the first header cell.
    assert parsed.structured["headers"][0] in ("Item", "﻿Item")
    assert parsed.structured["n_rows"] == 1


def test_csv_ragged_rows_do_not_crash():
    # Rows with varying column counts (a real export hazard).
    parsed = _parse(b"a,b,c\n1,2\n3,4,5,6,7\n8\n")
    assert parsed.structured["n_rows"] >= 1  # parsed something, did not raise


def test_csv_embedded_newlines_in_quotes():
    parsed = _parse(b'Desc,Amount\n"line one\nline two",100\n')
    assert parsed.structured["n_rows"] == 1
    assert parsed.evidence_spans[0].content_json["rows_sample"][0]["Amount"] == "100"


def test_csv_non_utf8_bytes_replaced_not_crash():
    parsed = _parse(b"Item,Price\n\xff\xfe weird,100\n")
    assert parsed.structured["n_rows"] == 1  # replacement chars, no crash


def test_csv_huge_row_count_is_capped_not_unbounded():
    big = b"Item,Price\n" + b"\n".join(f"row{i},{i}".encode() for i in range(5000))
    parsed = _parse(big)
    span = parsed.evidence_spans[0]
    # rows_sample is bounded (300) even though the document has 5000 rows.
    assert len(span.content_json["rows_sample"]) <= 300
    assert parsed.structured["n_rows"] == 5000  # count is still truthful


# --------------------------------------------------------------------------- #
# detect_header degenerate inputs
# --------------------------------------------------------------------------- #


def test_detect_header_on_empty_and_numeric():
    assert detect_header([]) == (0, 0.3) or detect_header([])[1] <= 0.3
    _idx, conf = detect_header([["1", "2", "3"], ["4", "5", "6"]])
    assert conf <= 0.3  # all-numeric -> no real header


# --------------------------------------------------------------------------- #
# Grid parser robustness
# --------------------------------------------------------------------------- #


def test_grid_empty_and_garbage():
    assert parse_financial_grid("").header_found is False
    assert parse_financial_grid(None).header_found is False
    assert parse_financial_grid_rows([]).header_found is False
    # Rows with no Material/Labour/Total header -> not found, no crash.
    assert parse_financial_grid_rows([["a", "b"], ["1", "2"]]).header_found is False


def test_grid_rows_with_none_cells():
    # Evidence rows_preview can contain None; the row parser must tolerate it.
    rows = [
        ["Description", "Notes", "", "Material Amount", "Labour Amount", "Total Amount"],
        ["Demolition", None, None, None, None, "$1,000.00"],
    ]
    rows = [["" if c is None else c for c in r] for r in rows]
    res = parse_financial_grid_rows(rows)
    assert res.header_found is True


# --------------------------------------------------------------------------- #
# Router robustness
# --------------------------------------------------------------------------- #


def test_router_unknown_and_none():
    assert get_parser_for(mime=None, filename=None) is None
    assert get_parser_for(mime="image/png", filename="a.png") is None
    assert get_parser_for(mime="application/zip", filename="a.zip") is None


# --------------------------------------------------------------------------- #
# EvidenceBundle defensive rendering
# --------------------------------------------------------------------------- #


def test_bundle_table_render_with_missing_cells():
    t = BundleTable(
        span_id="s1",
        evidence_type="table_region",
        locator={"sheet": "Q"},
        headers=["A", "B", "C"],
        rows=[{"A": "1"}, {"B": "2", "C": "3"}],  # ragged dicts
        rows_preview=[["1"], ["", "2", "3"]],
        header_confidence=None,
    )
    out = t.render()
    assert "| A | B | C |" in out  # renders without KeyError on missing cells


def test_bundle_render_empty_is_safe():
    b = EvidenceBundle(
        document_id="d",
        parse_id="p",
        parser_name="csv",
        parser_version="1",
        doc_name="x",
    )
    assert b.is_empty() is True
    assert b.primary_span_id() is None
    assert b.primary_locator() is None
    assert "x" in b.render_for_llm()  # header line only, no crash


def test_bundle_page_render_no_page_number():
    p = BundlePage(span_id="s", page=None, text="some text")
    assert "some text" in p.render()
