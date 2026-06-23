"""Home Depot Pro purchase ingestion: parsing, import, reconcile, linking.

Synthetic xlsx files mirror the real export headers (leading spaces and all)
and include the exact STL-GIFT-K reconcile case from the owner's real detail
export (three line items summing to $111.58).
"""

from __future__ import annotations

from decimal import Decimal

import openpyxl
import pytest

from project_db.connectors.homedepot import (
    import_details,
    import_transactions,
    link_job_to_project,
    parse_export,
)
from project_db.connectors.homedepot import reports as hd_reports
from project_db.connectors.homedepot.parse import HomeDepotParseError, parse_money
from project_db.db.models import HomeDepotLineItem, HomeDepotTransaction, Project

TXN_HEADERS = [
    "Sales Date",
    " Transaction Number",
    " Purchase Location",
    " Job Name",
    " Status",
    " Purchaser",
    " Subtotal",
    " Total",
]
DETAIL_HEADERS = [
    "Sales Date",
    " Transaction Number",
    " Purchase Location",
    " SKU Number",
    " Product Name",
    " Quantity",
    " Unit Price",
    " Subtotal",
]


def _write_xlsx(path, headers, rows):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(headers)
    for r in rows:
        ws.append(r)
    wb.save(path)
    return path


def _txn_file(tmp_path, rows, name="Pro_Transactions.xlsx"):
    return _write_xlsx(tmp_path / name, TXN_HEADERS, rows)


def _detail_file(tmp_path, rows, name="Pro_Transactions_Details.xlsx"):
    return _write_xlsx(tmp_path / name, DETAIL_HEADERS, rows)


# Real STL-GIFT-K detail rows (sum == 111.58 == the header subtotal).
STL_GIFT_K = "7149-00007-62120-20260622"
STL_GIFT_K_ITEMS = [
    ("22/06/2026", STL_GIFT_K, "BEAUBIEN OUEST", "1000839582", "Gold Series 6-Piece Paint Kit", "1", "$23.27", "$23.27"),
    ("22/06/2026", STL_GIFT_K, "BEAUBIEN OUEST", "1000402569", "Interior Eggshell Enamel Paint", "1", "$44.97", "$44.97"),
    ("22/06/2026", STL_GIFT_K, "BEAUBIEN OUEST", "1000107097", "Broan-NuTone Bathroom Fan", "1", "$43.34", "$43.34"),
]


# --- parse_money ------------------------------------------------------------


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("$26.41", Decimal("26.41")),
        ("$111.58", Decimal("111.58")),
        ("($5.00)", Decimal("-5.00")),
        ("-$33.35", Decimal("-33.35")),
        ("$1,234.56", Decimal("1234.56")),
        ("1 234,56", Decimal("1234.56")),  # French-Quebec grouping + decimal comma
        ("44.97", Decimal("44.97")),
        ("", None),
        (None, None),
        ("n/a", None),
    ],
)
def test_parse_money(raw, expected):
    assert parse_money(raw) == expected


# --- format detection + parsing ---------------------------------------------


def test_detect_and_parse_transactions(tmp_path):
    f = _txn_file(
        tmp_path,
        [("22/06/2026", "7149-1", "BEAUBIEN OUEST", "STL_GIFT", "Paid", "Lorenzo", "$26.41", "$30.36")],
    )
    parsed = parse_export(f)
    assert parsed.kind == "transactions"
    assert len(parsed) == 1
    row = parsed.rows[0]
    assert row["transaction_number"] == "7149-1"
    assert row["subtotal"] == Decimal("26.41")
    assert row["sales_date"].isoformat() == "2026-06-22"


def test_detect_and_parse_details(tmp_path):
    f = _detail_file(tmp_path, STL_GIFT_K_ITEMS)
    parsed = parse_export(f)
    assert parsed.kind == "details"
    assert len(parsed) == 3
    assert parsed.rows[0]["sku"] == "1000839582"
    assert parsed.rows[0]["unit_price"] == Decimal("23.27")


def test_unrecognized_file_raises(tmp_path):
    f = _write_xlsx(tmp_path / "junk.xlsx", ["Foo", "Bar"], [("a", "b")])
    with pytest.raises(HomeDepotParseError):
        parse_export(f)


# --- transaction import -----------------------------------------------------


def test_import_transactions_derives_tax_and_refund(session, tmp_path):
    f = _txn_file(
        tmp_path,
        [
            ("22/06/2026", STL_GIFT_K, "BEAUBIEN OUEST", "STL-GIFT-K", "Paid", "Lorenzo", "$111.58", "$128.29"),
            ("19/06/2026", "7149-ref", "BEAUBIEN OUEST", "ROCKLAND", "Refunded", "Lorenzo", "-$29.01", "-$33.35"),
        ],
    )
    stats = import_transactions(session, parse_export(f))
    session.commit()
    assert stats["inserted"] == 2
    assert stats["refunds"] == 1

    paid = session.query(HomeDepotTransaction).filter_by(transaction_number=STL_GIFT_K).one()
    assert paid.tax == Decimal("16.71")
    assert paid.is_refund is False

    refund = session.query(HomeDepotTransaction).filter_by(transaction_number="7149-ref").one()
    assert refund.is_refund is True


def test_import_transactions_is_idempotent(session, tmp_path):
    f = _txn_file(
        tmp_path,
        [("22/06/2026", STL_GIFT_K, "BEAUBIEN OUEST", "STL-GIFT-K", "Paid", "Lorenzo", "$111.58", "$128.29")],
    )
    import_transactions(session, parse_export(f))
    session.commit()
    stats2 = import_transactions(session, parse_export(f))
    session.commit()
    assert stats2["updated"] == 1
    assert stats2["inserted"] == 0
    assert session.query(HomeDepotTransaction).count() == 1


# --- line-item import + reconcile -------------------------------------------


def test_import_details_reconciles_balanced(session, tmp_path):
    tf = _txn_file(
        tmp_path,
        [("22/06/2026", STL_GIFT_K, "BEAUBIEN OUEST", "STL-GIFT-K", "Paid", "Lorenzo", "$111.58", "$128.29")],
    )
    import_transactions(session, parse_export(tf))
    session.commit()

    df = _detail_file(tmp_path, STL_GIFT_K_ITEMS)
    stats = import_details(session, parse_export(df))
    session.commit()

    assert stats["line_items"] == 3
    assert stats["reconciled"] == 1
    assert stats["unbalanced"] == 0

    header = session.query(HomeDepotTransaction).filter_by(transaction_number=STL_GIFT_K).one()
    assert header.line_item_count == 3
    assert header.line_items_subtotal == Decimal("111.58")
    assert header.reconciled is True
    assert header.detail_status == "imported"
    assert session.query(HomeDepotLineItem).count() == 3


def test_import_details_flags_unbalanced(session, tmp_path):
    tf = _txn_file(
        tmp_path,
        # Header subtotal deliberately wrong (should be 111.58).
        [("22/06/2026", STL_GIFT_K, "BEAUBIEN OUEST", "STL-GIFT-K", "Paid", "Lorenzo", "$999.99", "$1149.99")],
    )
    import_transactions(session, parse_export(tf))
    session.commit()
    df = _detail_file(tmp_path, STL_GIFT_K_ITEMS)
    stats = import_details(session, parse_export(df))
    session.commit()

    assert stats["unbalanced"] == 1
    header = session.query(HomeDepotTransaction).filter_by(transaction_number=STL_GIFT_K).one()
    assert header.reconciled is False
    assert header.detail_status == "unbalanced"


def test_import_details_replaces_prior_snapshot(session, tmp_path):
    tf = _txn_file(
        tmp_path,
        [("22/06/2026", STL_GIFT_K, "BEAUBIEN OUEST", "STL-GIFT-K", "Paid", "Lorenzo", "$111.58", "$128.29")],
    )
    import_transactions(session, parse_export(tf))
    df = _detail_file(tmp_path, STL_GIFT_K_ITEMS)
    import_details(session, parse_export(df))
    session.commit()
    # Re-import the same details -- must not double the line items.
    import_details(session, parse_export(df))
    session.commit()
    assert session.query(HomeDepotLineItem).count() == 3


def test_details_before_header_creates_stub(session, tmp_path):
    df = _detail_file(tmp_path, STL_GIFT_K_ITEMS)
    stats = import_details(session, parse_export(df))
    session.commit()
    assert stats["headers_created"] == 1
    header = session.query(HomeDepotTransaction).filter_by(transaction_number=STL_GIFT_K).one()
    # No header subtotal yet -> cannot reconcile, but items are kept.
    assert header.line_item_count == 3
    assert header.reconciled is None
    assert header.subtotal is None


# --- project linking --------------------------------------------------------


def test_link_job_to_project_substring(session, project_factory):
    proj = project_factory(name="923 Rockland", code="ROCK")
    pid, method, conf = link_job_to_project(session, "ROCKLAND")
    assert pid == proj.canonical_id
    assert method == "job_name"
    assert conf and conf >= 0.8


@pytest.mark.parametrize(
    "job",
    ["STL", "STLAU", "STLAURENT", "STL-GIFT-K", "STL_KEVCAR", "STL-OVERHE", "SAINT LAUR", "Saint-Laurent"],
)
def test_register_codes_resolve_to_st_laurent(session, project_factory, job):
    """Till abbreviations for the one St-Laurent project all resolve to it."""
    project_factory(name="5768 St-Laurent", code="MONDAY-BOARD-1")
    project_factory(name="3940 Cote des Neiges", code="MONDAY-BOARD-2")
    project_factory(name="923-927 Rockland", code="MONDAY-BOARD-3")
    pid, method, _ = link_job_to_project(session, job)
    proj = session.query(Project).filter_by(name="5768 St-Laurent").one()
    assert pid == proj.canonical_id, job
    assert method == "job_name"


@pytest.mark.parametrize("job", ["STMAT", "STMATHIEU", "1455 st mathieu"])
def test_register_codes_resolve_to_st_mathieu(session, project_factory, job):
    project_factory(name="1455 Rue St. Mathieu", code="M1")
    project_factory(name="5768 St-Laurent", code="M2")
    pid, _, _ = link_job_to_project(session, job)
    from project_db.db.models import Project

    proj = session.query(Project).filter_by(name="1455 Rue St. Mathieu").one()
    assert pid == proj.canonical_id, job


@pytest.mark.parametrize("job", ["ONLINE ORDER", "BODFS Order", "TANIA", "RETURN ORDER", "", "."])
def test_unidentifiable_jobs_stay_unresolved(session, project_factory, job):
    project_factory(name="5768 St-Laurent", code="M1")
    project_factory(name="1455 Rue St. Mathieu", code="M2")
    pid, method, _ = link_job_to_project(session, job)
    assert pid is None, job
    assert method == "unresolved"


@pytest.mark.parametrize("job", ["0", "00", "000"])
def test_numeric_placeholder_job_does_not_match_street_number(session, project_factory, job):
    """Regression: job '0' must NOT match '3940 Cote des Neiges' via the digit in 3940."""
    project_factory(name="3940 Cote des Neiges", code=None)
    project_factory(name="25-1001 580 Rue Viau", code=None)
    pid, method, _ = link_job_to_project(session, job)
    assert pid is None, job
    assert method == "unresolved"


def test_real_street_number_job_still_matches(session, project_factory):
    """A whole street-number typed as the job DOES resolve (token-boundary match)."""
    proj = project_factory(name="3940 Cote des Neiges", code=None)
    pid, method, _ = link_job_to_project(session, "3940")
    assert pid == proj.canonical_id
    assert method == "job_name"


def test_relink_after_adding_project(session, tmp_path, project_factory):
    # Import an STL transaction with NO matching project yet -> unresolved.
    tf = _txn_file(
        tmp_path,
        [("22/06/2026", "7149-stl", "BEAUBIEN OUEST", "STL-GIFT-K", "Paid", "Lorenzo", "$50.00", "$57.49")],
    )
    import_transactions(session, parse_export(tf))
    session.commit()
    header = session.query(HomeDepotTransaction).filter_by(transaction_number="7149-stl").one()
    assert header.project_id is None

    # Now the St-Laurent project lands; relink should resolve it.
    from project_db.connectors.homedepot import relink_transactions

    proj = project_factory(name="5768 St-Laurent", code="M1")
    stats = relink_transactions(session)
    session.commit()
    assert stats["linked"] == 1
    session.refresh(header)
    assert header.project_id == proj.canonical_id


def test_import_links_and_propagates_project_to_line_items(session, tmp_path, project_factory):
    proj = project_factory(name="923 Rockland", code="ROCK")
    tf = _txn_file(
        tmp_path,
        [("20/06/2026", "7149-rk", "BEAUBIEN OUEST", "ROCKLAND", "Paid", "Lorenzo", "$23.27", "$26.76")],
    )
    import_transactions(session, parse_export(tf))
    df = _detail_file(
        tmp_path,
        [("20/06/2026", "7149-rk", "BEAUBIEN OUEST", "1000839582", "Gold Series Paint Kit", "1", "$23.27", "$23.27")],
    )
    import_details(session, parse_export(df))
    session.commit()

    header = session.query(HomeDepotTransaction).filter_by(transaction_number="7149-rk").one()
    assert header.project_id == proj.canonical_id
    item = session.query(HomeDepotLineItem).filter_by(transaction_number="7149-rk").one()
    assert item.project_id == proj.canonical_id  # denormalized from the header


# --- reports ----------------------------------------------------------------


def test_coverage_summary(session, tmp_path, project_factory):
    project_factory(name="923 Rockland", code="ROCK")
    tf = _txn_file(
        tmp_path,
        [
            ("22/06/2026", STL_GIFT_K, "BEAUBIEN OUEST", "STL-GIFT-K", "Paid", "Lorenzo", "$111.58", "$128.29"),
            ("19/06/2026", "7149-ref", "BEAUBIEN OUEST", "ROCKLAND", "Refunded", "Lorenzo", "-$29.01", "-$33.35"),
        ],
    )
    import_transactions(session, parse_export(tf))
    import_details(session, parse_export(_detail_file(tmp_path, STL_GIFT_K_ITEMS)))
    session.commit()

    c = hd_reports.coverage_summary(session)
    assert c["transactions"] == 2
    assert c["purchases"] == 1
    assert c["refunds"] == 1
    assert c["gross_spend"] == Decimal("128.29")
    assert c["net_spend"] == Decimal("94.94")  # 128.29 - 33.35
    assert c["line_items"] == 3
    assert c["backfilled_count"] == 1
