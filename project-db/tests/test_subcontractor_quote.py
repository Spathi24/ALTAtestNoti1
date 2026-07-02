"""Phase 4: SubcontractorQuote + cost-side FinancialLineItem ingestion.

Covers the owner-review acceptance list: schema (fresh + migrated), quote
linkage, status vocabulary, SOW_Item_Ref resolution (incl. flagging of
missing/unknown refs), cost-side (not revenue) rows, selected-stays-quoted (no
committed cost), no PO/obligation/budget, division-total not aggregated, and the
material/labour split preserved.
"""

from __future__ import annotations

import json
import uuid

import pytest
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from project_db.ai.financial_grid import parse_financial_grid_rows
from project_db.ai.subcontractor_quote_ingest import (
    _status_from_name,
    ingest_subcontractor_quote,
)
from project_db.db.base import Base
from project_db.db.migrations import ensure_sqlite_schema
from project_db.db.models import (
    Client,
    ContractObligation,
    Document,
    DocumentParse,
    EvidenceSpan,
    FinancialLineItem,
    Organization,
    Project,
    SowItem,
    SowPackage,
    SubcontractorQuote,
    Vendor,
)
from project_db.db.models.finance import SUBCONTRACTOR_QUOTE_STATUSES
from project_db.db.models.work import ProjectStatus

# ---------------------------------------------------------------------------
# The mock Plumbing quote grid, mirroring the generated Quote_Lines sheet.
# rows_preview includes the header row first (as the real xlsx parser emits).
# ---------------------------------------------------------------------------

_HEADERS = [
    "Description", "Masterformat", "Material Amount", "Labour Amount",
    "Total Amount", "Item_ID", "Coverage_Y_N", "Mat_Incl", "Exclusions",
    "Notes", "SOW_Item_Ref",
]
_DATA_ROWS = [
    ["Plumbing", "22", "", "", 6800, "", "", "", "", "", ""],  # section total
    ["Rough-in plumbing (drain, supply, vent)", "22", 800, 2400, "", "QI-001", "Y", "N", "", "PEX-A", "SOW-025"],
    ["Supply and install plumbing fixtures", "22", 1600, 1200, "", "QI-002", "Y", "Y", "", "Moen Adler", "SOW-026"],
    ["Hot water heater replacement", "22", 500, 300, "", "QI-003", "Y", "Y", "", "40-gal electric", "SOW-027"],
    ["", "", "", "", 6800, "Pre-Tax Total", "", "", "", "", ""],  # grand total
]


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

def _make_engine():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    ensure_sqlite_schema(engine)
    return engine


def _make_session(engine):
    return sessionmaker(bind=engine)()


def _project_with_sow(session):
    org = Organization(canonical_id=uuid.uuid4(), name="Org")
    client = Client(canonical_id=uuid.uuid4(), name="Client", organization_id=org.canonical_id)
    session.add_all([org, client])
    session.flush()
    project = Project(
        canonical_id=uuid.uuid4(), name="923-927 Rockland", code="2026001",
        client_id=client.canonical_id, status=ProjectStatus.ACTIVE,
    )
    session.add(project)
    session.flush()
    pkg = SowPackage(
        canonical_id=uuid.uuid4(), project_id=project.canonical_id,
        division_code="22", trade_name="Plumbing", title="22-Plumbing", status="draft",
    )
    session.add(pkg)
    session.flush()
    for code in ("SOW-025", "SOW-026", "SOW-027"):
        session.add(SowItem(
            canonical_id=uuid.uuid4(), project_id=project.canonical_id,
            package_id=pkg.canonical_id, item_code=code, division_code="22",
        ))
    vendor = Vendor(canonical_id=uuid.uuid4(), name="Plombert Inc.", organization_id=org.canonical_id)
    session.add(vendor)
    session.flush()
    return org, project, pkg, vendor


def _quote_doc_with_evidence(session, *, name="2026001_QUOTE_22-Plumbing_PlombertInc_selected.xlsx",
                             data_rows=None):
    rows = data_rows if data_rows is not None else _DATA_ROWS
    doc = Document(
        canonical_id=uuid.uuid4(), name=name, url=f"https://drive/{name}",
        mime_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    session.add(doc)
    session.flush()
    parse = DocumentParse(
        document_id=doc.canonical_id, parser_name="xlsx", parser_version="1",
        status="success", rendered_text="x",
    )
    session.add(parse)
    session.flush()
    rows_sample = [dict(zip(_HEADERS, r)) for r in rows]
    rows_preview = [list(_HEADERS)] + [list(r) for r in rows]
    span = EvidenceSpan(
        document_id=doc.canonical_id, parse_id=parse.id, evidence_type="table_region",
        locator_json=json.dumps({"sheet": "Quote_Lines", "range": "A1:K6", "header_row": 1}),
        content_json=json.dumps({
            "sheet": "Quote_Lines", "headers": _HEADERS,
            "rows_sample": rows_sample, "rows_preview": rows_preview,
            "header_confidence": 1.0,
        }),
        confidence=1.0,
    )
    session.add(span)
    session.flush()
    return doc, span


# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------

class TestSchema:
    def test_fresh_db_has_table_and_columns(self):
        engine = _make_engine()
        insp = inspect(engine)
        assert "subcontractor_quote" in set(insp.get_table_names())
        fli_cols = {c["name"] for c in insp.get_columns("financial_line_item")}
        for c in ("purchase_type", "cost_status", "sow_item_id", "line_markup_factor"):
            assert c in fli_cols

    def test_existing_db_migration_adds_table_and_columns(self):
        engine = create_engine(
            "sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool,
        )
        # Simulate pre-Phase-4: build metadata minus subcontractor_quote, then
        # drop the 4 new FLI columns.
        tables = [t for n, t in Base.metadata.tables.items() if n != "subcontractor_quote"]
        Base.metadata.create_all(engine, tables=tables)
        with engine.begin() as conn:
            for col in ("purchase_type", "cost_status", "sow_item_id", "line_markup_factor"):
                try:
                    conn.execute(text(f"ALTER TABLE financial_line_item DROP COLUMN {col}"))
                except Exception:
                    pass
        assert "subcontractor_quote" not in set(inspect(engine).get_table_names())

        ensure_sqlite_schema(engine)

        insp = inspect(engine)
        assert "subcontractor_quote" in set(insp.get_table_names())
        fli_cols = {c["name"] for c in insp.get_columns("financial_line_item")}
        for c in ("purchase_type", "cost_status", "sow_item_id", "line_markup_factor"):
            assert c in fli_cols


# ---------------------------------------------------------------------------
# Status vocabulary + filename derivation
# ---------------------------------------------------------------------------

class TestStatus:
    def test_status_from_filename(self):
        assert _status_from_name("2026001_QUOTE_22-Plumbing_PlombertInc_selected.xlsx") == "selected"
        assert _status_from_name("2026001_QUOTE_09-Finishes_ABCTile_pending.xlsx") == "pending"
        assert _status_from_name("x_recommended.xlsx") == "recommended"
        assert _status_from_name("x_rejected.xlsx") == "rejected"
        assert _status_from_name("no marker here.xlsx") == "pending"

    def test_ingested_status_is_in_vocabulary(self):
        engine = _make_engine()
        s = _make_session(engine)
        _org, project, pkg, vendor = _project_with_sow(s)
        doc, _span = _quote_doc_with_evidence(s)
        res = ingest_subcontractor_quote(
            s, doc, project_id=project.canonical_id, package_id=pkg.canonical_id,
            vendor_id=vendor.canonical_id,
        )
        assert res.status in SUBCONTRACTOR_QUOTE_STATUSES
        quote = s.query(SubcontractorQuote).one()
        assert quote.status in SUBCONTRACTOR_QUOTE_STATUSES


# ---------------------------------------------------------------------------
# Parser: SOW_Item_Ref capture
# ---------------------------------------------------------------------------

class TestParserSowRef:
    def test_grid_parser_captures_sow_item_ref(self):
        # The parser receives stringified cells (as _single_table_grid_rows produces).
        str_rows = [list(_HEADERS)] + [["" if c == "" else str(c) for c in r] for r in _DATA_ROWS]
        grid = parse_financial_grid_rows(str_rows)
        line_items = [r for r in grid.rows if r.kind == "line_item"]
        # 3 items x (material + labour) = 6 rows, all carrying their SOW ref.
        assert len(line_items) == 6
        refs = {r.sow_item_ref for r in line_items}
        assert refs == {"SOW-025", "SOW-026", "SOW-027"}
        # SOW_Item_Ref must NOT have been swallowed by the description column.
        assert all(r.description for r in line_items)


# ---------------------------------------------------------------------------
# Ingestion behaviour
# ---------------------------------------------------------------------------

class TestIngest:
    @pytest.fixture
    def ingested(self):
        engine = _make_engine()
        s = _make_session(engine)
        _org, project, pkg, vendor = _project_with_sow(s)
        doc, span = _quote_doc_with_evidence(s)
        res = ingest_subcontractor_quote(
            s, doc, project_id=project.canonical_id, package_id=pkg.canonical_id,
            vendor_id=vendor.canonical_id,
        )
        s.commit()
        return s, res, project, pkg, vendor, span

    def test_one_quote_linked_to_project_package_vendor_evidence(self, ingested):
        s, _res, project, pkg, vendor, span = ingested
        quotes = s.query(SubcontractorQuote).all()
        assert len(quotes) == 1
        q = quotes[0]
        assert q.project_id == project.canonical_id
        assert q.package_id == pkg.canonical_id
        assert q.vendor_id == vendor.canonical_id
        assert q.evidence_span_id == span.id
        assert q.status == "selected"
        assert q.amount == 6800

    def test_rows_are_cost_side_not_revenue(self, ingested):
        s, _res, *_ = ingested
        rows = s.query(FinancialLineItem).all()
        assert rows
        assert all(r.side == "cost" for r in rows)
        assert not any(r.side == "revenue" for r in rows)

    def test_sow_refs_resolve_to_correct_items(self, ingested):
        s, res, project, *_ = ingested
        assert res.resolved_refs == 3
        assert res.unresolved_refs == []
        by_code = {
            si.item_code: si.canonical_id
            for si in s.query(SowItem).filter_by(project_id=project.canonical_id)
        }
        for row in s.query(FinancialLineItem).all():
            meta = json.loads(row.source_meta_json)
            ref = meta["sow_item_ref"]
            assert row.sow_item_id == by_code[ref]
            assert meta["sow_item_resolved"] is True

    def test_material_labour_split_preserved(self, ingested):
        s, _res, *_ = ingested
        rows = s.query(FinancialLineItem).all()
        mats = sorted(float(r.amount) for r in rows if r.amount_type == "material")
        labs = sorted(float(r.amount) for r in rows if r.amount_type == "labour")
        assert mats == [500.0, 800.0, 1600.0]
        assert labs == [300.0, 1200.0, 2400.0]

    def test_division_total_not_written_as_cost_row(self, ingested):
        s, res, *_ = ingested
        rows = s.query(FinancialLineItem).all()
        # No section-total / grand-total row is persisted as a cost fact.
        assert not any(r.amount_type == "total" for r in rows)
        # Reconciliation cross-check still computed, and the sum is not doubled.
        assert float(res.line_item_sum) == 6800.0
        assert float(res.grand_total) == 6800.0
        assert res.reconcile_ok is True

    def test_selected_stays_quoted_no_committed_cost(self, ingested):
        s, _res, *_ = ingested
        rows = s.query(FinancialLineItem).all()
        assert all(r.cost_status == "quoted" for r in rows)
        assert not any(r.cost_status == "committed" for r in rows)
        # purchase_type set deliberately.
        assert all(r.purchase_type == "vendor" for r in rows)

    def test_no_po_obligation_budget_created(self, ingested):
        s, _res, *_ = ingested
        # ContractObligation exists as a table; Phase 4 must not emit any.
        assert s.query(ContractObligation).count() == 0
        # PurchaseOrder / BudgetSnapshot models do not exist yet -- absence is
        # structurally guaranteed. Assert here that no committed cost slipped in.
        assert s.query(FinancialLineItem).filter_by(cost_status="committed").count() == 0

    def test_all_rows_have_evidence_provenance(self, ingested):
        s, _res, _project, _pkg, _vendor, span = ingested
        rows = s.query(FinancialLineItem).all()
        assert all(r.evidence_span_id == span.id for r in rows)
        assert all(r.evidence_locator_json for r in rows)

    def test_idempotent_reingest(self, ingested):
        s, _res, project, pkg, vendor, _span = ingested
        doc = s.query(Document).one()
        ingest_subcontractor_quote(
            s, doc, project_id=project.canonical_id, package_id=pkg.canonical_id,
            vendor_id=vendor.canonical_id,
        )
        s.commit()
        assert s.query(SubcontractorQuote).count() == 1
        assert s.query(FinancialLineItem).count() == 6


class TestMultiTableWorkbook:
    def test_selects_quote_table_ignoring_parser_contract(self):
        """A real QUOTE workbook has a Parser_Contract sheet too, so the bundle
        carries >1 table_region span. The quote grid must be selected by its
        money-column signature, not by assuming a single table."""
        engine = _make_engine()
        s = _make_session(engine)
        _org, project, pkg, vendor = _project_with_sow(s)
        doc, span = _quote_doc_with_evidence(s)
        # Add a second span mirroring the Parser_Contract metadata sheet.
        pc_headers = ["Sheet_Name", "Ingest", "Table_Name", "Primary_Key", "Notes"]
        pc_rows = [["Quote_Lines", "Y", "tblQuoteLines", "Item_ID", "..."]]
        s.add(EvidenceSpan(
            document_id=doc.canonical_id,
            parse_id=s.query(DocumentParse).filter_by(document_id=doc.canonical_id).one().id,
            evidence_type="table_region",
            locator_json=json.dumps({"sheet": "Parser_Contract"}),
            content_json=json.dumps({
                "sheet": "Parser_Contract", "headers": pc_headers,
                "rows_sample": [dict(zip(pc_headers, pc_rows[0]))],
                "rows_preview": [pc_headers, *pc_rows], "header_confidence": 1.0,
            }),
            confidence=1.0,
        ))
        s.flush()
        res = ingest_subcontractor_quote(
            s, doc, project_id=project.canonical_id, package_id=pkg.canonical_id,
            vendor_id=vendor.canonical_id,
        )
        s.commit()
        assert res.rows_written == 6
        assert float(res.line_item_sum) == 6800.0
        # The cited span is the Quote_Lines table, not Parser_Contract.
        assert s.query(SubcontractorQuote).one().evidence_span_id == span.id


class TestSowRefFlagging:
    def test_unknown_sow_ref_is_flagged_not_swallowed(self):
        engine = _make_engine()
        s = _make_session(engine)
        _org, project, pkg, vendor = _project_with_sow(s)
        # Point the last line at a SOW code that does not exist in the project.
        bad_rows = [list(r) for r in _DATA_ROWS]
        bad_rows[3][-1] = "SOW-099"  # Hot water heater -> unknown ref
        doc, _span = _quote_doc_with_evidence(s, data_rows=bad_rows)
        res = ingest_subcontractor_quote(
            s, doc, project_id=project.canonical_id, package_id=pkg.canonical_id,
            vendor_id=vendor.canonical_id,
        )
        s.commit()
        assert "SOW-099" in res.unresolved_refs
        assert any("SOW-099" in w for w in res.warnings)
        # The affected cost rows are written but left UNLINKED (not silently
        # assigned to a wrong item).
        unlinked = [
            r for r in s.query(FinancialLineItem).all()
            if json.loads(r.source_meta_json)["sow_item_ref"] == "SOW-099"
        ]
        assert unlinked
        assert all(r.sow_item_id is None for r in unlinked)

    def test_missing_sow_ref_is_flagged(self):
        engine = _make_engine()
        s = _make_session(engine)
        _org, project, pkg, vendor = _project_with_sow(s)
        bad_rows = [list(r) for r in _DATA_ROWS]
        bad_rows[1][-1] = ""  # first line item has no SOW_Item_Ref
        doc, _span = _quote_doc_with_evidence(s, data_rows=bad_rows)
        res = ingest_subcontractor_quote(
            s, doc, project_id=project.canonical_id, package_id=pkg.canonical_id,
            vendor_id=vendor.canonical_id,
        )
        s.commit()
        assert any("no SOW_Item_Ref" in w for w in res.warnings)
        unlinked = [
            r for r in s.query(FinancialLineItem).all()
            if json.loads(r.source_meta_json)["sow_item_ref"] == ""
        ]
        assert unlinked
        assert all(r.sow_item_id is None for r in unlinked)
