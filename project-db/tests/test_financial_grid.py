"""Deterministic grid parser (ai/financial_grid.py) -- Phase 1 of the
financial redesign.

Uses a SYNTHETIC fixture modeled exactly on the real 923 Rockland ACCEPTED
QUOTE structure (metadata block above the header, Description / Master-Format /
spacer / Material / Labour / Total columns, Div-hinted section subtotals,
indented line items, a comma-in-description row, a col-0-blank continuation
row, Contingency/OHP without hints, and Pre-Tax/After-Tax grand-total rows with
the label in a non-description column) -- but with fake names/amounts so no
real client data lands in the repo. The real-data reconciliation
($66,539.65 to the penny) is verified out-of-band, not committed.
"""

from __future__ import annotations

from decimal import Decimal

from project_db.ai.financial_grid import (
    classify_financial_sheet,
    parse_financial_grid,
    parse_money,
)

# A job-cost / "MATERIAL SPENDING" sheet -- a DIFFERENT layout (Phase | Cost |
# Supplier, plus budget side-blocks). The quote parser must DECLINE it rather
# than scrape garbage amounts (the real JOB COSTING regression).
_JOBCOST_FIXTURE = """\
MATERIAL SPENDING,,,,,,,,Material Budget,Material Price
Phase,Item Description, Cost ,Supplier,Date,Notes,,,"$9,200.00","$11,984.75"
Finishing,Floor," $ 11,506.24 ",Ecarpet,in progress,flooring,,,,
Rough,Misc," $ 8,221.08 ",Home Depot,02/11,,,,Receivable total," $ 322,500.00 "
"""

# The same quote layout but TAB-separated (how xlsx files come out of
# extract_xlsx). The delimiter must be sniffed.
_TSV_QUOTE = (
    "Description\tNotes\t\tMaterial Amount (CAD)\tLabour Amount (CAD)\tTotal Amount (CAD)\n"
    "Demolition\tDiv. 02\t\t\t\t$1,000.00\n"
    "    Selective demo\t02 41 19\t\t$400.00\t$600.00\t\n"
)

# Section totals: 1000 + 500 + 300 + 54 + 146 = 2000 == stated Pre-Tax.
_FIXTURE = """\
,ESTIMATE,,,,
123 Fake St.,,Date,1/1/2026,,
Faketown QC,,Estimate #,99999,,
,,Client ID,Test Client,,
,,Valid Until,2/1/2026,,
,,,,,
Description,Notes/ Master Format values,, Material Amount (CAD),Labour Amount (CAD),Total Amount (CAD)
,,,,,
Demolition,Div. 02,,,,"$1,000.00"
    Selective demo,02 41 19,,$400.00,$600.00,
,Continuation note row,,$100.00,,
,,,,,
Plumbing,Div. 22,,,,$500.00
    Rough plumbing,22 11 16,,$500.00,,
Fixtures,Div. 10-12,,,,$300.00
"Sink, faucet and vanity",22 40 00,,$300.00,,
Contingency,,,,,$54.00
Contingency 3%,waste,,,,
OHP,,,,,$146.00
Overhead and Profit 12,GC,,,,
,,,,,
,,,,Pre-Tax total,"$2,000.00"
,,,,After-Tax Total,"$2,299.50"
"""


class TestParseMoney:
    def test_formats(self):
        assert parse_money("$1,000.00") == Decimal("1000.00")
        assert parse_money("$400.00") == Decimal("400.00")
        assert parse_money("500") == Decimal("500")
        assert parse_money("($250.00)") == Decimal("-250.00")

    def test_non_money(self):
        assert parse_money("") is None
        assert parse_money(None) is None
        assert parse_money("3%") is None
        assert parse_money("Div. 02") is None
        assert parse_money("n/a") is None


class TestParseGrid:
    def _result(self):
        return parse_financial_grid(_FIXTURE)

    def test_header_and_grand_totals(self):
        r = self._result()
        assert r.header_found
        assert r.warnings == []
        assert r.grand_total == Decimal("2000.00")
        assert r.after_tax_total == Decimal("2299.50")

    def test_reconciles_to_the_penny(self):
        r = self._result()
        # The whole point: section subtotals sum to the stated Pre-Tax total.
        assert r.division_total == r.grand_total == Decimal("2000.00")

    def test_grand_total_rows_excluded(self):
        r = self._result()
        # Pre-Tax / After-Tax must NOT appear as division rows.
        descs = [row.description.lower() for row in r.rows]
        assert not any("pre-tax" in d or "after-tax" in d for d in descs)

    def test_section_classification(self):
        r = self._result()
        totals = {
            (row.division_code, row.amount_type): row.amount
            for row in r.rows
            if row.kind == "division_total"
        }
        assert totals[("02", "total")] == Decimal("1000.00")  # Demolition
        assert totals[("22", "total")] == Decimal("500.00")  # Plumbing
        assert totals[("10-12", "total")] == Decimal("300.00")  # Fixtures
        assert totals[("01", "contingency")] == Decimal("54.00")
        assert totals[("01", "markup")] == Decimal("146.00")  # OHP

    def test_line_items_inherit_section_division(self):
        r = self._result()
        # The "Sink, faucet" line carries its own "22 40 00" hint but sits under
        # the Fixtures (10-12) section -> it must inherit 10-12, NOT 22.
        sink = next(row for row in r.rows if row.description.startswith("Sink"))
        assert sink.kind == "line_item"
        assert sink.division_code == "10-12"
        assert sink.amount_type == "material"
        assert sink.amount == Decimal("300.00")

    def test_line_item_material_labour_split(self):
        r = self._result()
        demo_lines = [
            (row.amount_type, row.amount)
            for row in r.rows
            if row.kind == "line_item" and row.division_code == "02"
        ]
        # "Selective demo" emits a material(400) row AND a labour(600) row.
        assert ("material", Decimal("400.00")) in demo_lines
        assert ("labour", Decimal("600.00")) in demo_lines

    def test_continuation_row_uses_col1_description(self):
        r = self._result()
        # col-0-blank row: description falls back to the Notes column text.
        cont = next((row for row in r.rows if row.description == "Continuation note row"), None)
        assert cont is not None
        assert cont.kind == "line_item"
        assert cont.division_code == "02"  # inherited from Demolition


class TestClassifyFinancialSheet:
    def test_quote(self):
        assert classify_financial_sheet("ACCEPTED QUOTE", ",ESTIMATE,,") == "quote"
        assert classify_financial_sheet("927 QUOTE (NOT STARTED)", "") == "quote"

    def test_extras_beats_quote(self):
        # "EXTRAS ACCEPTED" carries "accepted" but must route to extras.
        assert classify_financial_sheet("EXTRAS ACCEPTED", "") == "extras"

    def test_job_cost(self):
        assert classify_financial_sheet("JOB COSTING", "") == "job_cost"
        assert classify_financial_sheet("Sheet1", "MATERIAL SPENDING\nPhase,Cost") == "job_cost"

    def test_order_quantities(self):
        assert classify_financial_sheet("Door Order sheet", "") == "order_quantities"

    def test_unknown(self):
        assert classify_financial_sheet("Contractors + Material", "random,stuff") == "unknown"


class TestRoutingSafety:
    def test_jobcost_sheet_is_not_a_quote(self):
        # Classifier routes it away from the quote parser...
        assert classify_financial_sheet("JOB COSTING", _JOBCOST_FIXTURE) == "job_cost"
        # ...and even if mis-handed to the parser, it DECLINES (no garbage rows).
        r = parse_financial_grid(_JOBCOST_FIXTURE)
        assert r.header_found is False
        assert r.rows == []

    def test_tsv_quote_is_parsed(self):
        # xlsx export is tab-separated; the delimiter must be sniffed.
        r = parse_financial_grid(_TSV_QUOTE)
        assert r.header_found is True
        assert r.division_total == Decimal("1000.00")


class TestFallback:
    def test_no_header_is_flagged_not_crash(self):
        r = parse_financial_grid("just,some\nrandom,csv\nno,money,header")
        assert r.header_found is False
        assert r.rows == []
        assert r.warnings

    def test_empty(self):
        r = parse_financial_grid("")
        assert r.header_found is False
        assert r.warnings
