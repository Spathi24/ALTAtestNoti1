"""Deterministic ingestion of parsed Home Depot exports into the ledger.

Idempotent by design:
* transaction headers upsert on ``transaction_number`` (the receipt's natural
  key) -- re-importing the same 24-month export updates in place.
* a transaction's line items are replaced wholesale on detail import (fresh
  snapshot), so a corrected re-export self-heals instead of double-counting.

Nothing is trusted to the source: ``tax`` is re-derived (``total - subtotal``),
and the line-item sum is reconciled against the header subtotal so a mis-scanned
or partial receipt is flagged ``unbalanced`` for review rather than silently
absorbed. ``job_name`` is resolved to the ``Project`` join nucleus, but the link
is conservative (substring/exact only) and never guessed -- the raw label is
always kept, and an unmatched job stays ``unresolved``.
"""

from __future__ import annotations

import json
import re
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy.orm import Session

from project_db.connectors.homedepot.parse import ParsedExport
from project_db.db.models import HomeDepotLineItem, HomeDepotTransaction, Project

# Street-type / filler words dropped when distilling a project name or job code
# to its bare street-name signature ("5768 St-Laurent" -> "stlaurent"). "st"
# itself is kept (it is "Saint", part of the street name), and "saint" is folded
# to "st" so "SAINT LAUR" and "St-Laurent" share a signature.
_STREET_TYPES = {"rue", "av", "ave", "avenue", "chemin", "ch", "blvd", "boul", "boulevard"}


def _normalize_job(value: str | None) -> str:
    """Lowercase, collapse non-alphanumerics to single spaces."""
    return re.sub(r"[^a-z0-9]+", " ", (value or "").lower()).strip()


def _phrase_in(needle_norm: str, haystack_norm: str) -> bool:
    """True if *needle* appears in *haystack* on WHOLE-TOKEN boundaries.

    Guards against the digit-fragment trap: raw ``"0" in "3940 cote des neiges"``
    is True (the char in "3940"), wrongly matching job "0" to that project.
    Token-boundary matching rejects that but still matches a real street-number
    job (``"3940"`` -> ``"3940 Cote des Neiges"``) or a phrase (``"st laurent"``).
    """
    if not needle_norm or not haystack_norm:
        return False
    return f" {needle_norm} " in f" {haystack_norm} "


def _street_tokens(value: str | None) -> list[str]:
    """Significant street-name tokens: drop numbers + street-type words; saint->st."""
    out: list[str] = []
    for tok in _normalize_job(value).split():
        if tok in _STREET_TYPES or any(c.isdigit() for c in tok):
            continue
        out.append("st" if tok == "saint" else tok)
    return out


def _street_concat(value: str | None) -> str:
    """A project's bare street signature, e.g. '5768 St-Laurent' -> 'stlaurent'."""
    return "".join(_street_tokens(value))


def _job_prefix_candidates(job_name: str | None) -> set[str]:
    """Register-code prefixes from a job: first token, and first-two concatenated.

    A purchaser types 'STL', 'STL-GIFT-K', 'STMAT', 'SAINT LAUR' at the till.
    The leading token (or two) is the project code; trailing tokens are sub-job
    labels (GIFT, KEVCAR). We only build candidates >= 3 chars to stay safe.
    """
    toks = _street_tokens(job_name)
    cands: set[str] = set()
    if toks:
        if len(toks[0]) >= 3:
            cands.add(toks[0])
        if len(toks) >= 2 and len(toks[0] + toks[1]) >= 3:
            cands.add(toks[0] + toks[1])
    return cands


def link_job_to_project(
    session: Session,
    job_name: str | None,
    *,
    _project_cache: list[Project] | None = None,
) -> tuple[Any | None, str, float | None]:
    """Resolve a Home Depot job name to a Project.

    Returns ``(project_id, match_method, confidence)``. Conservative, in
    descending confidence: exact name/code, substring either direction, then a
    street-acronym/prefix pass for register codes (``STL`` -> ``5768
    St-Laurent``) -- but only when it resolves to exactly ONE project. No
    confident match -> ``(None, "unresolved", None)``: a wrong link is worse
    than none, and ``ONLINE ORDER`` / ``BODFS Order`` / blank stay unresolved.
    """
    jn = _normalize_job(job_name)
    if not jn:
        return (None, "unresolved", None)

    projects = _project_cache if _project_cache is not None else session.query(Project).all()

    # Pass 1: exact match against normalized name or code.
    for p in projects:
        if jn and jn in (_normalize_job(p.name), _normalize_job(p.code)):
            return (p.canonical_id, "job_name", 1.0)

    # Pass 2: whole-token phrase match either direction (name first, then code).
    for p in projects:
        pname = _normalize_job(p.name)
        if _phrase_in(jn, pname) or _phrase_in(pname, jn):
            return (p.canonical_id, "job_name", 0.8)
    for p in projects:
        pcode = _normalize_job(p.code)
        if _phrase_in(jn, pcode) or _phrase_in(pcode, jn):
            return (p.canonical_id, "job_name", 0.85)

    # Pass 3: street-acronym / prefix match for till abbreviations. Require a
    # UNIQUE project so "STA..." never silently picks between two St- streets.
    cands = _job_prefix_candidates(job_name)
    if cands:
        matched: dict[Any, Project] = {}
        for p in projects:
            pc = _street_concat(p.name)
            if len(pc) < 3:
                continue
            if any(c == pc or pc.startswith(c) or c.startswith(pc) for c in cands):
                matched[p.canonical_id] = p
        if len(matched) == 1:
            p = next(iter(matched.values()))
            return (p.canonical_id, "job_name", 0.7)

    return (None, "unresolved", None)


def relink_transactions(session: Session) -> dict[str, int]:
    """Re-run job -> project linking over all existing transactions.

    Run after improving the matcher, adding projects, or fixing a job name.
    Never clobbers a ``manual`` assignment. Also re-stamps line items whose
    project link is derived from the header.
    """
    projects = session.query(Project).all()
    stats = {"linked": 0, "unresolved": 0, "unchanged": 0, "manual_kept": 0}
    for header in session.query(HomeDepotTransaction).all():
        if header.project_match_method == "manual":
            stats["manual_kept"] += 1
            continue
        pid, method, conf = link_job_to_project(
            session, header.job_name_raw, _project_cache=projects
        )
        changed = header.project_id != pid
        header.project_id = pid
        header.project_match_method = method
        header.project_match_confidence = conf
        if pid is not None:
            stats["linked"] += 1
        else:
            stats["unresolved"] += 1
        if changed:
            session.query(HomeDepotLineItem).filter_by(
                transaction_id=header.canonical_id
            ).update({"project_id": pid})
        else:
            stats["unchanged"] += 1
    return stats


def _is_online_order_number(num: str | None) -> bool:
    """Online/order numbers are plain digits (e.g. 0641960928); in-store numbers
    are the dashed store-register-txn-date form (e.g. 7149-00035-92581-20260313).
    """
    if not num:
        return False
    s = num.strip()
    return "-" not in s and s.isdigit()


def find_duplicate_candidates(session: Session, *, day_window: int = 2) -> list[dict[str, Any]]:
    """Find in-store/online transaction pairs that are the same event listed twice.

    A candidate = one in-store transaction (dashed number) + one online order
    (plain-digit number) with the SAME absolute total, same refund sign, same
    resolved project (None==None allowed), and sales dates within ``day_window``
    days. The in-store row is the primary (kept); the online row is the
    duplicate. Standalone online orders with no in-store twin are NOT returned.

    Already-flagged rows are skipped, so this is safe to re-run.
    """
    txns = (
        session.query(HomeDepotTransaction)
        .filter(HomeDepotTransaction.duplicate_of_id.is_(None))
        .all()
    )
    instore = [t for t in txns if not _is_online_order_number(t.transaction_number)]
    online = [t for t in txns if _is_online_order_number(t.transaction_number)]

    pairs: list[dict[str, Any]] = []
    used: set[Any] = set()
    for ins in instore:
        if ins.total is None:
            continue
        for onl in online:
            if onl.canonical_id in used or onl.total is None:
                continue
            if abs(Decimal(str(ins.total))) != abs(Decimal(str(onl.total))):
                continue
            if bool(ins.is_refund) != bool(onl.is_refund):
                continue
            if ins.project_id != onl.project_id:
                continue
            if ins.sales_date is None or onl.sales_date is None:
                continue
            days = abs((ins.sales_date - onl.sales_date).days)
            if days > day_window:
                continue
            used.add(onl.canonical_id)
            pairs.append(
                {
                    "primary": ins,
                    "duplicate": onl,
                    "total": Decimal(str(ins.total)),
                    "days_apart": days,
                }
            )
            break
    return pairs


def apply_duplicates(session: Session, pairs: list[dict[str, Any]]) -> int:
    """Point each pair's online row at the in-store primary via duplicate_of_id."""
    n = 0
    for p in pairs:
        p["duplicate"].duplicate_of_id = p["primary"].canonical_id
        n += 1
    session.flush()
    return n


# Reconciliation tolerance: penny rounding per line plus a small per-receipt slack.
def _reconcile_tolerance(n_items: int) -> Decimal:
    return Decimal("0.01") * n_items + Decimal("0.02")


def _reconcile(header: HomeDepotTransaction, items: list[HomeDepotLineItem]) -> None:
    """Recompute line-item rollup + reconcile against the header subtotal."""
    header.line_item_count = len(items)
    subtotal_sum = sum((i.subtotal for i in items if i.subtotal is not None), Decimal("0"))
    header.line_items_subtotal = subtotal_sum if items else None

    if items and header.subtotal is not None:
        delta = subtotal_sum - Decimal(str(header.subtotal))
        header.reconcile_delta = delta
        header.reconciled = abs(delta) <= _reconcile_tolerance(len(items))
    else:
        header.reconcile_delta = None
        header.reconciled = None


def _meta(record: dict[str, Any]) -> str:
    return json.dumps(record.get("_raw", {}), default=str, ensure_ascii=False)


def import_transactions(
    session: Session,
    parsed: ParsedExport,
    *,
    source_file: str | None = None,
) -> dict[str, int]:
    """Upsert transaction headers from a parsed transaction export.

    Preserves per-transaction detail-backfill state and any manual project
    assignment across re-imports.
    """
    if parsed.kind != "transactions":
        raise ValueError(f"expected a 'transactions' export, got {parsed.kind!r}")

    src = source_file or parsed.source_file
    projects = session.query(Project).all()
    stats = {"inserted": 0, "updated": 0, "refunds": 0, "linked": 0, "unresolved": 0}

    for row in parsed.rows:
        txn_no = row["transaction_number"]
        subtotal = row.get("subtotal")
        total = row.get("total")
        tax = (total - subtotal) if (total is not None and subtotal is not None) else None
        is_refund = (total is not None and total < 0) or (subtotal is not None and subtotal < 0)

        header = (
            session.query(HomeDepotTransaction)
            .filter_by(transaction_number=txn_no)
            .one_or_none()
        )
        if header is None:
            header = HomeDepotTransaction(transaction_number=txn_no, detail_status="pending")
            session.add(header)
            stats["inserted"] += 1
        else:
            stats["updated"] += 1

        header.sales_date = row.get("sales_date")
        header.purchase_location = row.get("purchase_location")
        header.job_name_raw = row.get("job_name")
        header.status = row.get("status")
        header.purchaser = row.get("purchaser")
        header.subtotal = subtotal
        header.total = total
        header.tax = tax
        header.currency = header.currency or "CAD"
        header.is_refund = bool(is_refund)
        header.source_export_file = src
        header.source_meta_json = _meta(row)

        # Resolve the job -> project link, but never clobber a manual assignment.
        if header.project_match_method != "manual":
            pid, method, conf = link_job_to_project(
                session, row.get("job_name"), _project_cache=projects
            )
            header.project_id = pid
            header.project_match_method = method
            header.project_match_confidence = conf
        if header.project_id is not None:
            stats["linked"] += 1
        else:
            stats["unresolved"] += 1
        if is_refund:
            stats["refunds"] += 1

        session.flush()
        # A header subtotal change can flip an already-backfilled reconcile.
        if header.line_item_count:
            items = (
                session.query(HomeDepotLineItem)
                .filter_by(transaction_id=header.canonical_id)
                .all()
            )
            _reconcile(header, items)

    return stats


def import_details(
    session: Session,
    parsed: ParsedExport,
    *,
    source_file: str | None = None,
) -> dict[str, int]:
    """Ingest per-transaction line items, replacing any prior snapshot.

    Creates a stub header if the transaction has not been imported yet (so the
    line items are never orphaned), then reconciles and sets ``detail_status``.
    """
    if parsed.kind != "details":
        raise ValueError(f"expected a 'details' export, got {parsed.kind!r}")

    src = source_file or parsed.source_file
    stats = {
        "transactions": 0,
        "line_items": 0,
        "reconciled": 0,
        "unbalanced": 0,
        "headers_created": 0,
    }

    # Group rows by transaction number, preserving order within each receipt.
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in parsed.rows:
        grouped.setdefault(row["transaction_number"], []).append(row)

    for txn_no, rows in grouped.items():
        header = (
            session.query(HomeDepotTransaction)
            .filter_by(transaction_number=txn_no)
            .one_or_none()
        )
        if header is None:
            # Detail arrived before the header export -- stub it so nothing is lost.
            header = HomeDepotTransaction(
                transaction_number=txn_no,
                sales_date=rows[0].get("sales_date"),
                purchase_location=rows[0].get("purchase_location"),
                detail_status="pending",
            )
            session.add(header)
            session.flush()
            stats["headers_created"] += 1

        # Fresh snapshot: drop the prior line items for this transaction.
        session.query(HomeDepotLineItem).filter_by(transaction_id=header.canonical_id).delete()

        items: list[HomeDepotLineItem] = []
        for i, row in enumerate(rows, start=1):
            item = HomeDepotLineItem(
                transaction_id=header.canonical_id,
                transaction_number=txn_no,
                line_number=i,
                sku=row.get("sku"),
                product_name=row.get("product_name"),
                quantity=row.get("quantity"),
                unit_price=row.get("unit_price"),
                subtotal=row.get("subtotal"),
                project_id=header.project_id,
                sales_date=header.sales_date or row.get("sales_date"),
                purchase_location=header.purchase_location or row.get("purchase_location"),
                source_export_file=src,
                source_meta_json=_meta(row),
            )
            session.add(item)
            items.append(item)
        stats["line_items"] += len(items)
        stats["transactions"] += 1

        _reconcile(header, items)
        header.detail_fetched_at = datetime.utcnow()
        if not items:
            header.detail_status = "no_items"
        elif header.reconciled is False:
            header.detail_status = "unbalanced"
            stats["unbalanced"] += 1
        else:
            header.detail_status = "imported"
            if header.reconciled:
                stats["reconciled"] += 1
        session.flush()

    return stats
