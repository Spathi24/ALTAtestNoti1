"""Auto-resolve a subcontractor QUOTE (or PKG/PO) filename to
project/package/vendor identity, so `ai/subcontractor_quote_ingest.py` can be
called without a human already knowing the three IDs by hand.

Phase 5 design item #3 (recorded 2026-07-02 in REFOUNDATION_BUILD_NOTES.md):
"filename -> package/vendor resolution... a NEW small resolver module ABOVE
the ingester... never inside financial_grid.py or the ingester itself."
This is that module.

DELIBERATELY NARROW, per owner scoping (2026-07-02): reuse the pattern
already proven in `connectors/homedepot/importer.py::link_job_to_project`
rather than build a general-purpose matcher. Same discipline throughout:
  - Descending-confidence deterministic passes only. No fuzzy/embedding/LLM
    matching -- this is Home Depot's exact shape, applied to a different
    document type.
  - A field resolves to exactly ONE candidate or it does not resolve at all.
    Ambiguous (>1 candidate) is treated the same as zero candidates --
    "flag, never silently sort" (the same rule as Home Depot's job linker
    and the original meeting SOPs).
  - Each of project/package/vendor resolves INDEPENDENTLY and is reported
    independently -- a document can partially resolve (e.g. project + vendor
    known, package ambiguous) rather than all-or-nothing.

Filename convention (settled 2026-06-30, docs/templates/NAMING_CONVENTIONS.md):
    {YYYYNNN}[-{PPP}]_{DOCTYPE}[_{DD}-{TradeName}][_{VendorSlug}][_{status}].ext
Regex verified directly against every real filename shape in the mock Drive
before being written here (QUOTE/PO/SOW/PKG/GREENSHEET/BUDGET/JOBCOST).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from project_db.ai.financial_divisions import canonical_division_code

_FILENAME_RE = re.compile(
    r"^(?P<project_code>\d{7})(?:-(?P<po_seq>\d{3}))?"
    r"_(?P<doctype>SOW|PKG|QUOTE|GREENSHEET|PO|BUDGET|JOBCOST|CHANGE)"
    r"(?:_(?P<div_code>\d{2,4})-(?P<trade_name>[A-Za-z]+))?"
    r"(?:_(?P<vendor_slug>[A-Z][A-Za-z]{1,11}))?"
    r"(?:_(?P<status>pending|recommended|selected|rejected|awarded|v\d+|snapshot))?"
    r"\.(?P<ext>\w+)$"
)


@dataclass
class ParsedFilename:
    project_code: str | None = None
    po_seq: str | None = None
    doctype: str | None = None
    division_code: str | None = None
    trade_name: str | None = None
    vendor_slug: str | None = None
    status: str | None = None
    matched: bool = False


def parse_quote_filename(filename: str) -> ParsedFilename:
    """Deterministic filename parse -- no DB access, pure regex. Returns
    ``matched=False`` (all fields None) on anything that doesn't fit the
    settled convention; never raises.

    ``division_code`` is normalized to the canonical DB form: filenames spell
    range divisions WITHOUT the dash ("1012" -> "10-12"), because a dash would
    collide with the convention's field separators. Without this fold, the
    SowPackage exact-match below can never hit a canonically-stored range
    division (the 1012-vs-10-12 trap)."""
    m = _FILENAME_RE.match(filename or "")
    if not m:
        return ParsedFilename(matched=False)
    g = m.groupdict()
    return ParsedFilename(
        project_code=g["project_code"],
        po_seq=g["po_seq"],
        doctype=g["doctype"],
        division_code=canonical_division_code(g["div_code"]),
        trade_name=g["trade_name"],
        vendor_slug=g["vendor_slug"],
        status=g["status"],
        matched=True,
    )


def _normalize(s: str | None) -> str:
    """Lowercase, alphanumerics only -- so 'PlombertInc' and 'Plombert Inc.'
    both fold to 'plombertinc'."""
    return re.sub(r"[^a-z0-9]+", "", (s or "").lower())


@dataclass
class ResolutionResult:
    filename: str
    parsed: ParsedFilename
    project_id: Any | None = None
    project_method: str = "unresolved"
    package_id: Any | None = None
    package_method: str = "unresolved"
    vendor_id: Any | None = None
    vendor_method: str = "unresolved"
    warnings: list[str] = field(default_factory=list)

    @property
    def fully_resolved(self) -> bool:
        return (
            self.project_id is not None
            and self.package_id is not None
            and (self.vendor_id is not None or self.parsed.vendor_slug is None)
        )


def resolve_quote_document(session, filename: str) -> ResolutionResult:
    """Resolve *filename* to project/package/vendor. Never guesses: an
    unresolvable or ambiguous field stays ``None`` with its method recorded
    and a warning, exactly Home Depot's ``link_job_to_project`` discipline
    ("a wrong link is worse than none").
    """
    from project_db.ai.views import _resolve_project
    from project_db.db.models.core import Vendor
    from project_db.db.models.sow import SowPackage

    parsed = parse_quote_filename(filename)
    result = ResolutionResult(filename=filename, parsed=parsed)

    if not parsed.matched:
        result.warnings.append(
            f"filename {filename!r} does not match the settled naming convention "
            "-- nothing to resolve"
        )
        return result

    # --- project: the filename embeds the project code directly (SOP
    # convention), so this is an exact lookup, not fuzzy matching -- unlike
    # Home Depot's till-abbreviation problem, the code IS the identity here.
    project = _resolve_project(session, parsed.project_code)
    if project is None:
        result.warnings.append(
            f"project_code {parsed.project_code!r} did not resolve to a Project "
            "-- unresolved, not guessed"
        )
        return result
    result.project_id = project.canonical_id
    result.project_method = "filename_project_code"

    # --- package: exact division_code match WITHIN the resolved project.
    # Ambiguous (>1 package for the same division in this project) is
    # treated as unresolved, same as zero matches -- never pick arbitrarily.
    if parsed.division_code is not None:
        candidates = (
            session.query(SowPackage)
            .filter(
                SowPackage.project_id == project.canonical_id,
                SowPackage.division_code == parsed.division_code,
            )
            .all()
        )
        if len(candidates) == 1:
            result.package_id = candidates[0].canonical_id
            result.package_method = "filename_division_code"
        elif len(candidates) == 0:
            result.warnings.append(
                f"no SowPackage for division {parsed.division_code!r} in project "
                f"{project.name!r} -- unresolved, not guessed"
            )
        else:
            result.warnings.append(
                f"{len(candidates)} SowPackage rows for division "
                f"{parsed.division_code!r} in project {project.name!r} -- "
                "ambiguous, unresolved (never pick arbitrarily)"
            )

    # --- vendor: VendorSlug is a camelCase abbreviation, not an exact name,
    # so this needs the same normalize+match tiering as Home Depot's job
    # linker (exact fold, then substring either direction, unique required).
    if parsed.vendor_slug is not None:
        slug_norm = _normalize(parsed.vendor_slug)
        vendors = session.query(Vendor).all()
        exact = [v for v in vendors if _normalize(v.name) == slug_norm]
        if len(exact) == 1:
            result.vendor_id = exact[0].canonical_id
            result.vendor_method = "vendor_slug_exact"
        elif len(exact) == 0:
            substr = [
                v
                for v in vendors
                if slug_norm
                and (slug_norm in _normalize(v.name) or _normalize(v.name) in slug_norm)
            ]
            if len(substr) == 1:
                result.vendor_id = substr[0].canonical_id
                result.vendor_method = "vendor_slug_substring"
            elif len(substr) == 0:
                result.warnings.append(
                    f"VendorSlug {parsed.vendor_slug!r} matched no Vendor -- "
                    "unresolved, not guessed"
                )
            else:
                result.warnings.append(
                    f"VendorSlug {parsed.vendor_slug!r} matched {len(substr)} "
                    "vendors ambiguously -- unresolved (never pick arbitrarily)"
                )
        else:
            result.warnings.append(
                f"VendorSlug {parsed.vendor_slug!r} exact-matched {len(exact)} "
                "vendors ambiguously -- unresolved (never pick arbitrarily)"
            )

    return result
