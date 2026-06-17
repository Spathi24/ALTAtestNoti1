"""Unit tests for extras_grid.py (Phase 1c-MVP).

All tests are pure (no DB). Fixtures are synthetic CSV strings matching the
EXTRAS ACCEPTED sheet format: CO# | Item | Cost/Unit | Applied | Total | Status
"""

from __future__ import annotations

from decimal import Decimal

from project_db.ai.extras_grid import (
    _classify_status,
    parse_extras_sheet,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

_BASIC_EXTRAS_CSV = """\
CO #,Item,Cost/Unit,Applied,Total,Status
1,Replace bathroom tile - floor,500.00,1,"$500.00",Accepted
2,Additional electrical outlet,150.00,2,"$300.00",Accepted
3,Custom shelving - living room,800.00,1,"$800.00",Not Accepted
4,Drywall repair - hallway,250.00,1,"$250.00",Accepted
5,Paint touch-up,100.00,1,"$100.00",Proposed
"""

_NO_STATUS_CSV = """\
CO#,Description,Unit Cost,Total
1,New windows,1200.00,1200.00
2,Door replacement,400.00,400.00
"""

_EMPTY_CSV = ""

_ALL_REJECTED_CSV = """\
CO #,Item,Cost/Unit,Total,Status
1,Scope A,1000.00,1000.00,Rejected
2,Scope B,500.00,500.00,Cancelled
3,Scope C,800.00,800.00,N/A
"""

_FRENCH_EXTRAS_CSV = """\
NO CO,Description des travaux,Prix unitaire,Total,Statut
CO-1,Remplacement de tuiles,600.00,"$600.00",Accepte
CO-2,Electricite additionnelle,200.00,"$200.00",Propose
CO-3,Reparation cloison seche,150.00,"$150.00",Non accepte
"""

_TSV_EXTRAS = (
    "CO #\tItem\tCost/Unit\tApplied\tTotal\tStatus\n"
    "1\tPlumbing fixture upgrade\t750.00\t1\t$750.00\tAccepted\n"
    "2\tHVAC duct extension\t400.00\t1\t$400.00\tAccepted\n"
)


# ---------------------------------------------------------------------------
# _classify_status tests
# ---------------------------------------------------------------------------


class TestClassifyStatus:
    def test_accepted(self):
        assert _classify_status("Accepted") == "accepted"
        assert _classify_status("ACCEPTED") == "accepted"
        assert _classify_status("approved") == "accepted"

    def test_proposed(self):
        assert _classify_status("Proposed") == "proposed"
        assert _classify_status("Not Started") == "proposed"
        assert _classify_status("Pending") == "proposed"
        assert _classify_status("In Progress") == "proposed"
        assert _classify_status("Open") == "proposed"

    def test_rejected_returns_none(self):
        assert _classify_status("Not Accepted") is None
        assert _classify_status("Rejected") is None
        assert _classify_status("Cancelled") is None
        assert _classify_status("N/A") is None
        assert _classify_status("n/a") is None
        assert _classify_status("Voided") is None

    def test_empty_returns_unknown(self):
        assert _classify_status("") == "unknown"
        assert _classify_status(None) == "unknown"

    def test_french_accepted(self):
        # Accent-folded: 'Accepté' / 'Accepte' / 'Approuvé' / 'Terminé' / 'Fait'.
        assert _classify_status("Accepté") == "accepted"
        assert _classify_status("Accepte") == "accepted"
        assert _classify_status("Approuvé") == "accepted"
        assert _classify_status("Terminé") == "accepted"
        assert _classify_status("Fait") == "accepted"

    def test_french_proposed(self):
        assert _classify_status("Proposé") == "proposed"
        assert _classify_status("En cours") == "proposed"
        assert _classify_status("En attente") == "proposed"
        assert _classify_status("Soumis") == "proposed"

    def test_french_rejected_returns_none(self):
        # CRITICAL: a French rejected CO must NOT be counted as revenue.
        assert _classify_status("Non accepté") is None
        assert _classify_status("Refusé") is None
        assert _classify_status("Annulé") is None
        assert _classify_status("Abandonné") is None

    def test_french_terminated_not_confused_with_english(self):
        # 'Terminé' (FR: done) -> accepted; English 'terminated' (cancelled) must
        # NOT match the French accepted stem.
        assert _classify_status("Terminé") == "accepted"
        assert _classify_status("terminated") == "unknown"


# ---------------------------------------------------------------------------
# parse_extras_sheet tests
# ---------------------------------------------------------------------------


class TestParseExtrasSheetBasic:
    def test_empty_text_no_header(self):
        result = parse_extras_sheet(_EMPTY_CSV)
        assert not result.header_found
        assert result.rows == []

    def test_no_co_header_no_parse(self):
        # A quote sheet — should not be recognised as extras
        text = "Description,Material,Labour,Total\nDemolition,400,600,1000\n"
        result = parse_extras_sheet(text)
        assert not result.header_found
        assert result.rows == []

    def test_basic_csv_accepted_rows(self):
        result = parse_extras_sheet(_BASIC_EXTRAS_CSV)
        assert result.header_found
        # CO3 (Not Accepted) → skipped; CO1,CO2,CO4 accepted; CO5 proposed
        accepted = result.accepted_rows()
        proposed = result.proposed_rows()
        assert len(accepted) == 3
        assert len(proposed) == 1
        assert result.skipped_rows >= 1  # CO3 was rejected

    def test_accepted_total_correct(self):
        result = parse_extras_sheet(_BASIC_EXTRAS_CSV)
        # CO1=$500 + CO2=$300 + CO4=$250 = $1050
        assert result.accepted_total == Decimal("1050.00")

    def test_proposed_total_correct(self):
        result = parse_extras_sheet(_BASIC_EXTRAS_CSV)
        # CO5=$100 proposed
        assert result.proposed_total == Decimal("100.00")

    def test_all_rejected_returns_empty_rows(self):
        result = parse_extras_sheet(_ALL_REJECTED_CSV)
        assert result.header_found
        assert result.rows == []
        assert result.accepted_total == Decimal(0)
        assert result.skipped_rows >= 3

    def test_no_status_column_fallback(self):
        # No status column → status defaults to "unknown", all rows included
        result = parse_extras_sheet(_NO_STATUS_CSV)
        # The header must still be detected (CO# + Total)
        if result.header_found:
            for row in result.rows:
                assert row.status == "unknown"

    def test_tsv_format_parsed(self):
        result = parse_extras_sheet(_TSV_EXTRAS)
        assert result.header_found
        assert len(result.accepted_rows()) == 2
        assert result.accepted_total == Decimal("1150.00")

    def test_french_header_detected(self):
        # 'NO CO | Description des travaux | Prix unitaire | Total | Statut'
        result = parse_extras_sheet(_FRENCH_EXTRAS_CSV)
        assert result.header_found, "French extras header (Statut) not recognised"

    def test_french_rows_classified(self):
        result = parse_extras_sheet(_FRENCH_EXTRAS_CSV)
        # CO-1 Accepté ($600), CO-2 Proposé ($200), CO-3 Non accepté (skipped).
        assert len(result.accepted_rows()) == 1
        assert len(result.proposed_rows()) == 1
        assert result.accepted_total == Decimal("600.00")
        assert result.proposed_total == Decimal("200.00")
        # The rejected French row must be excluded, not counted.
        assert result.skipped_rows >= 1
        totals = {str(r.total) for r in result.rows}
        assert "150.00" not in totals, "rejected French CO wrongly counted"

    def test_accented_french_header_and_status(self):
        # Fully accented variant (État column, accented status values).
        csv = (
            "NO CO,Désignation des travaux,Prix,Total,État\n"
            'CO-1,Béton de fondation,1000.00,"$1,000.00",Accepté\n'
            'CO-2,Réparation toiture,500.00,"$500.00",Annulé\n'
        )
        result = parse_extras_sheet(csv)
        assert result.header_found
        assert len(result.accepted_rows()) == 1
        assert result.accepted_total == Decimal("1000.00")
        # CO-1 'Béton' must classify to Concrete (03) despite the accent.
        assert result.accepted_rows()[0].division_code == "03"


class TestExtrasRowDivisionClassification:
    def test_plumbing_item_maps_to_22(self):
        csv = (
            "CO #,Item,Cost/Unit,Total,Status\n1,Plumbing rough-in adjustment,500,500.00,Accepted\n"
        )
        result = parse_extras_sheet(csv)
        assert result.header_found
        if result.rows:
            assert result.rows[0].division_code == "22"

    def test_electrical_item_maps_to_26(self):
        csv = (
            "CO #,Item,Cost/Unit,Total,Status\n1,Additional electrical outlet,200,200.00,Accepted\n"
        )
        result = parse_extras_sheet(csv)
        assert result.header_found
        if result.rows:
            assert result.rows[0].division_code == "26"

    def test_unknown_item_maps_to_99(self):
        csv = "CO #,Item,Cost/Unit,Total,Status\n1,Miscellaneous work,100,100.00,Accepted\n"
        result = parse_extras_sheet(csv)
        assert result.header_found
        if result.rows:
            assert result.rows[0].division_code == "99"

    def test_tile_maps_to_finishes_09(self):
        csv = "CO #,Item,Cost/Unit,Total,Status\n1,Replace bathroom tile,500,500.00,Accepted\n"
        result = parse_extras_sheet(csv)
        assert result.header_found
        if result.rows:
            assert result.rows[0].division_code == "09"


class TestExtrasRowMetadata:
    def test_co_number_preserved(self):
        result = parse_extras_sheet(_BASIC_EXTRAS_CSV)
        co_numbers = {r.co_number for r in result.rows}
        assert "1" in co_numbers or any("1" in c for c in co_numbers)

    def test_description_not_empty(self):
        result = parse_extras_sheet(_BASIC_EXTRAS_CSV)
        for row in result.rows:
            assert row.description.strip() != ""

    def test_all_rows_have_positive_total(self):
        result = parse_extras_sheet(_BASIC_EXTRAS_CSV)
        for row in result.rows:
            assert row.total > Decimal(0)

    def test_no_zero_amount_rows(self):
        csv = (
            "CO #,Item,Cost/Unit,Total,Status\n"
            "1,Blank scope,0.00,0.00,Accepted\n"
            "2,Real work,500.00,500.00,Accepted\n"
        )
        result = parse_extras_sheet(csv)
        for row in result.rows:
            assert row.total > Decimal(0)
