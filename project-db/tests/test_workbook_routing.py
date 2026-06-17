"""Multi-sheet workbook routing safety tests (Phase 1c hardening).

Verifies that:
  1.  split_workbook_sheets splits xlsx-extracted text correctly.
  2.  Each worksheet is classified independently (not the whole workbook).
  3.  Non-financial sheets (Overview, Measurements, Specs, task-note grids,
      Material + Labor Summaries) are classified as 'unknown' and skipped.
  4.  ESTIMATE sheets with the canonical quote format are parsed.
  5.  Duplicate sheets ('Copy of ESTIMATE') are deduplicated — only the first
      quote-type sheet per workbook is parsed, so rows are not double-counted.
  6.  Sheets that look like quotes by name ('Quote #' in header) but have no
      financial grid are safely skipped (no_header).
  7.  JOB COSTING workbooks: EXTRAS sheet parsed; Material/Labour skipped.
  8.  Single-sheet documents behave exactly as before.

All synthetic fixtures are TSV-format to match extract_xlsx output.
No LLM, no external I/O.
"""

from __future__ import annotations

import uuid
from datetime import datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from project_db.ai.financial_grid import (
    classify_financial_sheet,
    split_workbook_sheets,
)
from project_db.ai.financial_grid_populator import (
    populate_ledger_for_document,
)
from project_db.db.base import Base
from project_db.db.models import Client, Organization, Project
from project_db.db.models.docs import Document, DocumentText
from project_db.db.models.finance import FinancialLineItem
from project_db.db.models.work import ProjectStatus

# ---------------------------------------------------------------------------
# Synthetic workbook fixtures
# ---------------------------------------------------------------------------

# Mixed 10-sheet workbook (Common Area pattern).
# ESTIMATE uses single-column Total format — grid parser will not find the
# Material+Total header → ingestion_status=skipped, reason=no_header (safe).
_COMMON_AREA_WORKBOOK = """\
### Overview
Tiling\tANDRES\tOther\tMaterial
painting\tDemo Floor\tTile
wall panels\tTile Floor\tWall Panels

### Measurements
5768.0\tArea (in)\t5770.0\tArea (in)
3rd floor hallway: tile\t44.5 x 156\t6942

### Specs
Linear Lights
https://www.example.com/product/lights

### Material Categorization
Wall Panels\tCeramic\tMDF\tDark Grey Paint
Entry\tMailbox wall\tBaseboards in hallway

### 5768
ITEM\tTOTAL AREA\tPRICE/SF\tTOTAL COST
Ceramic
WALL PANELS\t18

### 5770
ITEM\tTOTAL AREA\tPRICE/SF\tTOTAL COST
Entry tile:\tWalls: 95 height\t56.0

### Material + Labor Summaries
ITEM\tCOST\tMULTIPLIER\tTOTAL
Wall Panels\t399.5\t313.15\t712.65
Ceramic\t400.0\t578.0\t978.0

### ESTIMATE
ESTIMATE
7557 Blvd Gouin Est.\tDate\t2026-06-11
Montreal, QC\tEstimate #\t25010
Description\tNotes/ Master Format values\tTotal Amount (CAD)
Ceramic Tile Work\t09 30 00\t$5000.00
Painting\t09 90 00\t$3000.00
Pre-Tax Total\t\t$8000.00

### Copy of ESTIMATE
ESTIMATE
7557 Blvd Gouin Est.\tDate\t2026-06-16
Montreal, QC\tEstimate #\t25010
Description\tNotes/ Master Format values\tTotal Amount (CAD)
Ceramic Tile Work\t09 30 00\t$5000.00
Painting\t09 90 00\t$3000.00
Pre-Tax Total\t\t$8000.00

### Est. Minus Sections
ESTIMATE
7557 Blvd Gouin Est.\tDate\t2026-06-16
Description\tNotes/ Master Format values\tTotal Amount (CAD)
Ceramic Tile Work\t09 30 00\t$5000.00
Pre-Tax Total\t\t$5000.00"""

# 5770 St-Laurent workbook: Sheet1 contains "Quote #" in a header row, but
# the body is NOT a financial grid — no Material/Total Amount columns.
# Procurement schedule is empty.
_5770_STLAURENT_WORKBOOK = """\
### Sheet1
5770 St-Laurent\tDate\t2026-05-01
Montreal, QC\tQuote #\t12345
Client ID
RBQ: 5867-9390-01\tValid Until\t2026-06-01
NEW

### Sheet2
Large Items\tSteps\tnotes\tMaterial\tnotes\tTools
Bathroom\tDemolition
Garbage removal/disposal
Structural
Any Repairs

### Procurement schedule"""

# JOB COSTING workbook: Material/Labour are job_cost; EXTRAS is parseable.
_JOB_COSTING_WORKBOOK = """\
### Material
MATERIAL SPENDING
Phase\tItem Description\tCost\tSupplier\tDate\tNotes\tMaterial Budget
Plumbing fixtures\t2150.00\tRona\t2024-01-15

### Labour (outdated)
Item Description\tCost\tSubcontractor\tDate
Demo\t4393.77\tBen

### Value of Progress up to 0424
Current Payments (as of 04/21) for 15 units\t137969.00
Total price per unit x 15\t355005

### EXTRAS
EXTRAS
CO #\tItem\tDescription\tCost/Unit\tApplied Units\tTotal\tStatus
CO 1\tKitchen Cabinets\tChange Standard 12" Upper to 15"\t600.00\t15.0\t9000\tCancelled
CO 2\tCurtains\tSupply and install Curtains\t600\t10.0\t6000.00\tPaid
CO 4\tBathroom Doors\tEnlarge Bathroom doors to 28"\t263.33\t6.0\t1579.98\tPaid

### Order Quantities
Item\tQty per Pack\t# of Packs\tTotal Units
Bathroom Exhaust Fan Cover\t1.0\t15.0\t15.0"""

# Canonical quote format: Material + Labour split, tri-column.
_CANONICAL_ESTIMATE_SHEET = """\
ESTIMATE
123 Test Ave\tDate\t2026-01-01
Montreal QC\tEstimate #\tT-999
Description\tNotes/ Master Format values\tMaterial Amount (CAD)\tLabour Amount (CAD)\tTotal Amount (CAD)
Demolition\t02 41 00\t$400.00\t$600.00\t$1000.00
Painting\t09 90 00\t$500.00\t$300.00\t$800.00
\t\t\t\tPre-Tax Total\t$1800.00"""

# Workbook with two quote sheets — only first should be parsed.
_DUPLICATE_ESTIMATE_WORKBOOK = (
    "### ESTIMATE\n"
    + _CANONICAL_ESTIMATE_SHEET
    + "\n\n### Copy of ESTIMATE\n"
    + _CANONICAL_ESTIMATE_SHEET.replace("Estimate #\tT-999", "Estimate #\tT-999B")
)

# Workbook with one quote + one extras — both are parseable (different types).
_QUOTE_AND_EXTRAS_WORKBOOK = (
    "### ESTIMATE\n"
    + _CANONICAL_ESTIMATE_SHEET
    + "\n\n### EXTRAS\nEXTRAS\nCO #\tItem\tCost/Unit\tTotal\tStatus\n"
    "1\tPlumbing upgrade\t300\t300.00\tAccepted\n"
)


# ---------------------------------------------------------------------------
# DB fixtures (reused from test_phase1c_mvp.py pattern)
# ---------------------------------------------------------------------------


@pytest.fixture
def db_session():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    s = Session()
    yield s
    s.rollback()
    s.close()


def _seed_project(session):
    org = Organization(canonical_id=uuid.uuid4(), name="Test Org")
    client = Client(canonical_id=uuid.uuid4(), name="Test Client", organization_id=org.canonical_id)
    project = Project(
        canonical_id=uuid.uuid4(),
        name="Test Project",
        status=ProjectStatus.ACTIVE,
        client_id=client.canonical_id,
    )
    session.add_all([org, client, project])
    session.flush()
    return project


def _make_doc(session, project, name, text):
    doc = Document(
        canonical_id=uuid.uuid4(),
        name=name,
        url=f"https://drive.google.com/{uuid.uuid4()}",
        is_trashed=False,
        project_id=project.canonical_id,
        modified_at_source=datetime(2026, 1, 20),
    )
    session.add(doc)
    session.flush()
    dt = DocumentText(
        document_id=doc.canonical_id,
        extracted_text=text,
        extraction_method="xlsx-openpyxl",
        extracted_at=datetime(2026, 1, 21),
    )
    session.add(dt)
    session.flush()
    return doc, dt


# ===========================================================================
# Part 1: split_workbook_sheets (pure, no DB)
# ===========================================================================


class TestSplitWorkbookSheets:
    def test_no_markers_returns_single_none_entry(self):
        text = "Description,Material,Total\nDemo,400,1000"
        sheets = split_workbook_sheets(text)
        assert sheets == [(None, text)]

    def test_empty_text_returns_single_none_entry(self):
        sheets = split_workbook_sheets("")
        assert sheets == [(None, "")]

    def test_two_sheets_split_correctly(self):
        text = "### Sheet1\nrow1\n\n### Sheet2\nrow2"
        sheets = split_workbook_sheets(text)
        assert len(sheets) == 2
        assert sheets[0][0] == "Sheet1"
        assert "row1" in sheets[0][1]
        assert sheets[1][0] == "Sheet2"
        assert "row2" in sheets[1][1]

    def test_omitted_marker_terminates_split(self):
        text = (
            "### Sheet1\nrow1\n### (further sheets omitted -- workbook too large)\n### Sheet2\nrow2"
        )
        sheets = split_workbook_sheets(text)
        # Only Sheet1 before the omitted marker
        assert len(sheets) == 1
        assert sheets[0][0] == "Sheet1"

    def test_empty_sheet_included_with_empty_text(self):
        text = "### Sheet1\nrow1\n\n### EmptySheet\n\n### Sheet3\nrow3"
        sheets = split_workbook_sheets(text)
        names = [s[0] for s in sheets]
        assert "EmptySheet" in names
        empty_text = next(t for n, t in sheets if n == "EmptySheet")
        assert empty_text == ""

    def test_paren_named_sheet_is_not_mistaken_for_omitted_marker(self):
        # A real worksheet may legitimately be named "(2024) Budget"; only the
        # extractor's "sheets omitted" sentinel should terminate the split.
        text = (
            "### (2024) Budget\nrow1\n"
            "### ESTIMATE\nrow2\n"
            "### (further sheets omitted -- workbook too large)\njunk"
        )
        sheets = split_workbook_sheets(text)
        names = [s[0] for s in sheets]
        assert names == ["(2024) Budget", "ESTIMATE"]

    def test_ten_sheet_common_area_workbook(self):
        sheets = split_workbook_sheets(_COMMON_AREA_WORKBOOK)
        names = [s[0] for s in sheets]
        assert "Overview" in names
        assert "ESTIMATE" in names
        assert "Copy of ESTIMATE" in names
        assert "Material + Labor Summaries" in names
        assert len(sheets) == 10

    def test_three_sheet_5770_workbook(self):
        sheets = split_workbook_sheets(_5770_STLAURENT_WORKBOOK)
        assert len(sheets) == 3
        assert sheets[0][0] == "Sheet1"
        assert sheets[1][0] == "Sheet2"
        assert sheets[2][0] == "Procurement schedule"


# ===========================================================================
# Part 2: classify_financial_sheet per sheet name (pure, no DB)
# ===========================================================================


class TestPerSheetClassification:
    def test_overview_sheet_is_unknown(self):
        text = "Tiling\tANDRES\tOther\tMaterial\npainting\tDemo Floor\tTile"
        assert classify_financial_sheet("Overview", text) == "unknown"

    def test_measurements_sheet_is_unknown(self):
        text = "5768.0\tArea (in)\t5770.0\tArea (in)\n3rd floor hallway\t44.5 x 156\t6942"
        assert classify_financial_sheet("Measurements", text) == "unknown"

    def test_material_labor_summaries_is_unknown(self):
        text = "ITEM\tCOST\tMULTIPLIER\tTOTAL\nWall Panels\t399.5\t313.15\t712.65"
        assert classify_financial_sheet("Material + Labor Summaries", text) == "unknown"

    def test_estimate_sheet_is_quote(self):
        assert classify_financial_sheet("ESTIMATE", _CANONICAL_ESTIMATE_SHEET) == "quote"

    def test_copy_of_estimate_is_still_quote(self):
        # Classifier sees "estimate" in name → quote (dedup handled by populator)
        assert classify_financial_sheet("Copy of ESTIMATE", _CANONICAL_ESTIMATE_SHEET) == "quote"

    def test_est_minus_sections_is_quote_via_content(self):
        # Name "Est. Minus Sections" alone doesn't match "estimate",
        # but content starts with "ESTIMATE" banner → quote
        content = (
            "ESTIMATE\n7557 Blvd Gouin\tDate\t2026-06-16\nDescription\tNotes\tTotal Amount (CAD)"
        )
        assert classify_financial_sheet("Est. Minus Sections", content) == "quote"

    def test_extras_sheet_is_extras(self):
        text = "EXTRAS\nCO #\tItem\tCost/Unit\tTotal\tStatus\n1\tFoo\t100\t100\tAccepted"
        assert classify_financial_sheet("EXTRAS", text) == "extras"

    def test_material_spending_sheet_is_job_cost(self):
        text = "MATERIAL SPENDING\nPhase\tItem Description\tCost\tSupplier"
        assert classify_financial_sheet("Material", text) == "job_cost"

    def test_order_quantities_sheet_is_order_quantities(self):
        text = "Item\tQty per Pack\t# of Packs\tTotal Units\nExhaust Fan\t1\t15\t15"
        assert classify_financial_sheet("Order Quantities", text) == "order_quantities"

    def test_sheet1_with_quote_number_in_header_is_quote(self):
        # Sheet1 of 5770 has "Quote #" as a label → classifier sees "quote"
        text = "5770 St-Laurent\tDate\t2026-05-01\nMontreal, QC\tQuote #\t12345\nClient ID"
        assert classify_financial_sheet("Sheet1", text) == "quote"

    def test_procurement_schedule_empty_sheet_is_unknown(self):
        assert classify_financial_sheet("Procurement schedule", "") == "unknown"

    def test_numeric_sheet_name_cost_table_is_unknown(self):
        # '5768' / '5770' per-unit cost calculation sheets — no financial markers
        text = "ITEM\tTOTAL AREA\tPRICE/SF\tTOTAL COST\nCeramic\nWALL PANELS\t18"
        assert classify_financial_sheet("5768", text) == "unknown"


# ===========================================================================
# Part 3: Integration — populate_ledger_for_document with multi-sheet text
# ===========================================================================


class TestCommonAreaWorkbook:
    def test_common_area_estimate_single_column_skipped(self, db_session):
        """ESTIMATE sheet uses single-column Total format — no Material column.

        The grid parser requires both 'material' AND 'total amount' in the
        header row (_looks_like_header).  Without Material, parse returns
        header_found=False → ingestion_status=skipped, reason=no_header.
        This is the correct safe behavior for unsupported estimate layouts.
        """
        project = _seed_project(db_session)
        doc, dt = _make_doc(db_session, project, "Common Area", _COMMON_AREA_WORKBOOK)
        result = populate_ledger_for_document(db_session, doc, dt)

        assert result.sheet_type == "quote"
        assert result.ingestion_status == "skipped"
        assert result.ingestion_reason == "no_header"
        assert result.rows_written == 0

    def test_no_rows_written_for_common_area_workbook(self, db_session):
        project = _seed_project(db_session)
        doc, dt = _make_doc(db_session, project, "Common Area", _COMMON_AREA_WORKBOOK)
        populate_ledger_for_document(db_session, doc, dt)

        count = (
            db_session.query(FinancialLineItem)
            .filter(FinancialLineItem.document_id == doc.canonical_id)
            .count()
        )
        assert count == 0


class TestDuplicateEstimateDedup:
    def test_only_first_estimate_sheet_parsed(self, db_session):
        """'ESTIMATE' + 'Copy of ESTIMATE' in same workbook: only first parsed."""
        project = _seed_project(db_session)
        doc, dt = _make_doc(db_session, project, "Common Area", _DUPLICATE_ESTIMATE_WORKBOOK)
        result = populate_ledger_for_document(db_session, doc, dt)

        assert result.ingestion_status == "parsed"
        assert result.rows_written > 0

    def test_rows_not_doubled_by_copy_of_estimate(self, db_session):
        """Row count from ESTIMATE+Copy must equal row count from ESTIMATE alone."""
        project = _seed_project(db_session)

        # Workbook with duplicate sheet
        doc_dup, dt_dup = _make_doc(
            db_session, project, "Common Area", _DUPLICATE_ESTIMATE_WORKBOOK
        )
        result_dup = populate_ledger_for_document(db_session, doc_dup, dt_dup)

        # Same ESTIMATE but as a single sheet
        doc_single, dt_single = _make_doc(
            db_session, project, "ACCEPTED QUOTE", "### ESTIMATE\n" + _CANONICAL_ESTIMATE_SHEET
        )
        result_single = populate_ledger_for_document(db_session, doc_single, dt_single)

        assert result_dup.rows_written == result_single.rows_written, (
            "Duplicate ESTIMATE sheets must not double the row count"
        )


class Test5770StLaurentWorkbook:
    def test_sheet1_with_quote_marker_no_grid_header_skipped(self, db_session):
        """Sheet1 of 5770 has 'Quote #' in headers but no financial grid.

        classify_financial_sheet returns 'quote', but parse_financial_grid
        finds no Material+Total header → ingestion_status=skipped, no_header.
        """
        project = _seed_project(db_session)
        doc, dt = _make_doc(db_session, project, "5770 St-Laurent", _5770_STLAURENT_WORKBOOK)
        result = populate_ledger_for_document(db_session, doc, dt)

        assert result.sheet_type == "quote"
        assert result.ingestion_status == "skipped"
        assert result.ingestion_reason == "no_header"
        assert result.rows_written == 0

    def test_no_rows_written_for_5770_workbook(self, db_session):
        project = _seed_project(db_session)
        doc, dt = _make_doc(db_session, project, "5770 St-Laurent", _5770_STLAURENT_WORKBOOK)
        populate_ledger_for_document(db_session, doc, dt)

        count = (
            db_session.query(FinancialLineItem)
            .filter(FinancialLineItem.document_id == doc.canonical_id)
            .count()
        )
        assert count == 0


class TestJobCostingWorkbook:
    def test_extras_sheet_parsed_from_mixed_workbook(self, db_session):
        """JOB COSTING workbook: EXTRAS sheet is parsed; all others are skipped."""
        project = _seed_project(db_session)
        doc, dt = _make_doc(db_session, project, "JOB COSTING", _JOB_COSTING_WORKBOOK)
        result = populate_ledger_for_document(db_session, doc, dt)

        assert result.sheet_type == "extras"
        assert result.ingestion_status == "parsed"
        assert result.rows_written > 0

    def test_only_accepted_paid_extras_rows_written(self, db_session):
        """CO 1 (Cancelled) must be excluded; CO 2 and CO 4 (Paid/accepted) included."""
        project = _seed_project(db_session)
        doc, dt = _make_doc(db_session, project, "JOB COSTING", _JOB_COSTING_WORKBOOK)
        populate_ledger_for_document(db_session, doc, dt)

        rows = (
            db_session.query(FinancialLineItem)
            .filter(FinancialLineItem.document_id == doc.canonical_id)
            .all()
        )
        amounts = {float(r.amount) for r in rows}
        assert 9000.0 not in amounts, "Cancelled CO 1 must not be written"
        assert any(a in amounts for a in (6000.0, 1579.98)), "Paid COs must be written"

    def test_material_and_labour_sheets_skipped(self, db_session):
        """Material spending and Labour sheets must not land in FinancialLineItem."""
        project = _seed_project(db_session)
        doc, dt = _make_doc(db_session, project, "JOB COSTING", _JOB_COSTING_WORKBOOK)
        populate_ledger_for_document(db_session, doc, dt)

        rows = (
            db_session.query(FinancialLineItem)
            .filter(FinancialLineItem.document_id == doc.canonical_id)
            .all()
        )
        # All rows should be from the EXTRAS sheet (source=grid/extras, doc_role=change_order)
        for r in rows:
            assert r.source == "grid/extras"
            assert r.doc_role == "change_order"


class TestQuoteAndExtrasInOneWorkbook:
    def test_quote_and_extras_both_parsed(self, db_session):
        """A workbook with ESTIMATE + EXTRAS sheets should parse both."""
        project = _seed_project(db_session)
        doc, dt = _make_doc(db_session, project, "ACCEPTED QUOTE", _QUOTE_AND_EXTRAS_WORKBOOK)
        result = populate_ledger_for_document(db_session, doc, dt)

        assert result.ingestion_status == "parsed"
        rows = (
            db_session.query(FinancialLineItem)
            .filter(FinancialLineItem.document_id == doc.canonical_id)
            .all()
        )
        sources = {r.source for r in rows}
        assert "grid" in sources, "quote rows expected"
        assert "grid/extras" in sources, "extras rows expected"


class TestSingleSheetBehaviorUnchanged:
    def test_csv_text_no_markers_uses_doc_name(self, db_session):
        """Non-xlsx document (no ### headers) falls through to document-name routing."""
        text = (
            ",ESTIMATE,,,,\n"
            "Description,Notes/ Master Format values,,"
            " Material Amount (CAD),Labour Amount (CAD),Total Amount (CAD)\n"
            "Demolition,02 41 00,,$400.00,$600.00,$1000.00\n"
            ",,,,,Pre-Tax Total,$1000.00\n"
        )
        project = _seed_project(db_session)
        doc, dt = _make_doc(db_session, project, "923 ACCEPTED QUOTE", text)
        result = populate_ledger_for_document(db_session, doc, dt)

        assert result.sheet_type == "quote"
        assert result.ingestion_status == "parsed"
        assert result.rows_written > 0

    def test_idempotent_on_multi_sheet_workbook(self, db_session):
        """Running populate twice on the same multi-sheet workbook is idempotent."""
        project = _seed_project(db_session)
        doc, dt = _make_doc(db_session, project, "ACCEPTED QUOTE", _QUOTE_AND_EXTRAS_WORKBOOK)
        r1 = populate_ledger_for_document(db_session, doc, dt)
        db_session.flush()
        r2 = populate_ledger_for_document(db_session, doc, dt)
        db_session.flush()

        assert r1.rows_written == r2.rows_written
        count = (
            db_session.query(FinancialLineItem)
            .filter(FinancialLineItem.document_id == doc.canonical_id)
            .count()
        )
        assert count == r2.rows_written


# ===========================================================================
# Part 4: Extras-classifier fallback to quote parser
# ===========================================================================

# Synthetic "EXTRAS+ROOF" style document: "extras" in the title/header but
# the body is a canonical tri-column quote grid, not a CO sheet.
_EXTRAS_NAMED_BUT_QUOTE_BODY = (
    ",EXTRAS+ROOF,,,,"
    "\n7557 Blvd Gouin Est.,,Date,5/5/2026,,"
    '\n"Montreal, QC",,Estimate #,25008,,'
    "\nDescription,Notes/ Master Format values,, Material Amount (CAD),Labour Amount (CAD),Total Amount (CAD)"
    "\nStructural engineer report,,,,,$3200.00"
    "\nRoof replacement (materials),,,,,$11740.00"
    "\nOverhead and Profit 15,,,,,$2541.00"
    "\n,,,,Pre-Tax total,$17480.00"
    "\n,,,,After-Tax Total,$20102.00"
)


class TestExtrasFallbackToQuote:
    def test_mislabeled_extras_quote_body_parsed_as_quote(self, db_session):
        """'EXTRAS+ROOF' doc with quote-grid body must parse via the fallback path."""
        project = _seed_project(db_session)
        doc, dt = _make_doc(db_session, project, "EXTRAS ACCEPTED", _EXTRAS_NAMED_BUT_QUOTE_BODY)
        result = populate_ledger_for_document(db_session, doc, dt)

        assert result.ingestion_status == "parsed", result.ingestion_reason
        assert result.sheet_type == "quote"
        assert result.rows_written > 0

    def test_mislabeled_extras_rows_have_quote_metadata(self, db_session):
        """Rows parsed via the extras→quote fallback must carry quote provenance."""
        project = _seed_project(db_session)
        doc, dt = _make_doc(db_session, project, "EXTRAS ACCEPTED", _EXTRAS_NAMED_BUT_QUOTE_BODY)
        populate_ledger_for_document(db_session, doc, dt)

        rows = (
            db_session.query(FinancialLineItem)
            .filter(FinancialLineItem.document_id == doc.canonical_id)
            .all()
        )
        assert rows
        for r in rows:
            assert r.source == "grid"
            assert r.source_doc_type == "quote"
            assert r.doc_role == "quote"

    def test_real_extras_sheet_still_parsed_after_fallback_added(self, db_session):
        """A genuine CO extras sheet must still parse correctly (fallback not triggered)."""
        csv = (
            "CO #,Item,Cost/Unit,Total,Status\n"
            "1,Plumbing upgrade,300,300.00,Accepted\n"
            "2,Tile upgrade,500,500.00,Accepted\n"
        )
        project = _seed_project(db_session)
        doc, dt = _make_doc(db_session, project, "EXTRAS ACCEPTED", csv)
        result = populate_ledger_for_document(db_session, doc, dt)

        assert result.ingestion_status == "parsed"
        assert result.sheet_type == "extras"
        rows = (
            db_session.query(FinancialLineItem)
            .filter(FinancialLineItem.document_id == doc.canonical_id)
            .all()
        )
        assert all(r.source == "grid/extras" for r in rows)
        assert all(r.doc_role == "change_order" for r in rows)
