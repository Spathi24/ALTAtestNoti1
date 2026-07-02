"""Phase 5 item #3: quote_document_resolver -- deterministic filename ->
project/package/vendor resolution, reusing Home Depot's link_job_to_project
discipline (descending-confidence passes, unique-match-required, never
guess). No LLM, no fuzzy/embedding matching, no ledger mutation.
"""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from project_db.ai.quote_document_resolver import (
    parse_quote_filename,
    resolve_quote_document,
)
from project_db.db.base import Base
from project_db.db.migrations import ensure_sqlite_schema
from project_db.db.models import Client, Organization, Project, SowPackage, Vendor
from project_db.db.models.work import ProjectStatus

# ---------------------------------------------------------------------------
# Filename parsing -- pure, no DB
# ---------------------------------------------------------------------------

class TestParseFilename:
    @pytest.mark.parametrize(
        "filename,expected",
        [
            (
                "2026001_QUOTE_22-Plumbing_PlombertInc_selected.xlsx",
                {
                    "project_code": "2026001", "po_seq": None, "doctype": "QUOTE",
                    "division_code": "22", "trade_name": "Plumbing",
                    "vendor_slug": "PlombertInc", "status": "selected",
                },
            ),
            (
                "2026001_QUOTE_09-Finishes_ABCTile_pending.xlsx",
                {
                    "project_code": "2026001", "po_seq": None, "doctype": "QUOTE",
                    "division_code": "09", "trade_name": "Finishes",
                    "vendor_slug": "ABCTile", "status": "pending",
                },
            ),
            (
                "2026001-001_PO_22-Plumbing_PlombertInc_awarded.xlsx",
                {
                    "project_code": "2026001", "po_seq": "001", "doctype": "PO",
                    "division_code": "22", "trade_name": "Plumbing",
                    "vendor_slug": "PlombertInc", "status": "awarded",
                },
            ),
            (
                "2026001_SOW_v1.xlsx",
                {
                    "project_code": "2026001", "po_seq": None, "doctype": "SOW",
                    "division_code": None, "trade_name": None,
                    "vendor_slug": None, "status": "v1",
                },
            ),
            (
                "2026001_PKG_22-Plumbing.xlsx",
                {
                    "project_code": "2026001", "po_seq": None, "doctype": "PKG",
                    "division_code": "22", "trade_name": "Plumbing",
                    "vendor_slug": None, "status": None,
                },
            ),
            (
                "2026001_GREENSHEET.xlsx",
                {
                    "project_code": "2026001", "po_seq": None, "doctype": "GREENSHEET",
                    "division_code": None, "trade_name": None,
                    "vendor_slug": None, "status": None,
                },
            ),
            (
                "2026001_BUDGET_v1.xlsx",
                {
                    "project_code": "2026001", "po_seq": None, "doctype": "BUDGET",
                    "division_code": None, "trade_name": None,
                    "vendor_slug": None, "status": "v1",
                },
            ),
            (
                "2026001_JOBCOST.xlsx",
                {
                    "project_code": "2026001", "po_seq": None, "doctype": "JOBCOST",
                    "division_code": None, "trade_name": None,
                    "vendor_slug": None, "status": None,
                },
            ),
        ],
    )
    def test_every_real_filename_shape_parses(self, filename, expected):
        """Verified directly against every real filename shape in the mock
        Drive (docs/templates/mock_drive) before being written."""
        parsed = parse_quote_filename(filename)
        assert parsed.matched is True
        for field_name, value in expected.items():
            assert getattr(parsed, field_name) == value, field_name

    @pytest.mark.parametrize(
        "filename",
        [
            "923 ACCEPTED QUOTE.xlsx",  # legacy pre-SOP naming
            "random_document.pdf",
            "",
            "2026001.xlsx",  # missing DOCTYPE
            "not_a_project_code_QUOTE.xlsx",
        ],
    )
    def test_non_convention_filenames_do_not_match(self, filename):
        parsed = parse_quote_filename(filename)
        assert parsed.matched is False
        assert parsed.project_code is None


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


def _project(session, *, name="923-927 Rockland", code="2026001"):
    org = Organization(canonical_id=uuid.uuid4(), name="Org")
    client = Client(canonical_id=uuid.uuid4(), name="Client", organization_id=org.canonical_id)
    session.add_all([org, client])
    session.flush()
    p = Project(
        canonical_id=uuid.uuid4(), name=name, code=code,
        client_id=client.canonical_id, status=ProjectStatus.ACTIVE,
    )
    session.add(p)
    session.flush()
    return org, p


def _package(session, project, *, division_code, title=None):
    pkg = SowPackage(
        canonical_id=uuid.uuid4(), project_id=project.canonical_id,
        division_code=division_code, title=title or f"{division_code}-pkg", status="draft",
    )
    session.add(pkg)
    session.flush()
    return pkg


def _vendor(session, org, *, name):
    v = Vendor(canonical_id=uuid.uuid4(), name=name, organization_id=org.canonical_id)
    session.add(v)
    session.flush()
    return v


# ---------------------------------------------------------------------------
# Full resolution
# ---------------------------------------------------------------------------

class TestResolveQuoteDocument:
    def test_fully_resolves_when_everything_exists_and_is_unique(self):
        engine = _make_engine()
        s = _make_session(engine)
        org, project = _project(s)
        _package(s, project, division_code="22", title="22-Plumbing")
        _vendor(s, org, name="Plombert Inc.")
        s.flush()

        res = resolve_quote_document(
            s, "2026001_QUOTE_22-Plumbing_PlombertInc_selected.xlsx"
        )
        assert res.project_id == project.canonical_id
        assert res.project_method == "filename_project_code"
        assert res.package_id is not None
        assert res.package_method == "filename_division_code"
        assert res.vendor_id is not None
        assert res.vendor_method == "vendor_slug_exact"
        assert res.fully_resolved is True
        assert res.warnings == []

    def test_non_convention_filename_returns_unresolved_with_warning(self):
        engine = _make_engine()
        s = _make_session(engine)
        res = resolve_quote_document(s, "923 ACCEPTED QUOTE.xlsx")
        assert res.project_id is None
        assert res.fully_resolved is False
        assert any("does not match" in w for w in res.warnings)

    def test_unknown_project_code_stays_unresolved(self):
        engine = _make_engine()
        s = _make_session(engine)
        res = resolve_quote_document(
            s, "9999999_QUOTE_22-Plumbing_PlombertInc_selected.xlsx"
        )
        assert res.project_id is None
        assert res.package_id is None
        assert res.vendor_id is None
        assert any("did not resolve to a Project" in w for w in res.warnings)


class TestPackageResolution:
    def test_missing_package_stays_unresolved_not_guessed(self):
        engine = _make_engine()
        s = _make_session(engine)
        _org, project = _project(s)
        s.flush()
        res = resolve_quote_document(
            s, "2026001_QUOTE_22-Plumbing_PlombertInc_selected.xlsx"
        )
        assert res.project_id == project.canonical_id  # project still resolves
        assert res.package_id is None
        assert any("no SowPackage" in w for w in res.warnings)

    def test_ambiguous_package_same_division_stays_unresolved(self):
        """Two SowPackage rows for the same division in the same project --
        never pick arbitrarily."""
        engine = _make_engine()
        s = _make_session(engine)
        _org, project = _project(s)
        _package(s, project, division_code="22", title="22-Plumbing-A")
        _package(s, project, division_code="22", title="22-Plumbing-B")
        s.flush()

        res = resolve_quote_document(
            s, "2026001_QUOTE_22-Plumbing_PlombertInc_selected.xlsx"
        )
        assert res.package_id is None
        assert any("ambiguous" in w for w in res.warnings)

    def test_package_resolution_scoped_to_project(self):
        """A division match in a DIFFERENT project must not resolve."""
        engine = _make_engine()
        s = _make_session(engine)
        _org, project_a = _project(s, name="Project A", code="2026001")
        _org2, project_b = _project(s, name="Project B", code="2026002")
        _package(s, project_b, division_code="22")  # only project_b has div 22
        s.flush()

        res = resolve_quote_document(
            s, "2026001_QUOTE_22-Plumbing_PlombertInc_selected.xlsx"
        )
        assert res.project_id == project_a.canonical_id
        assert res.package_id is None  # project_a has no div-22 package


class TestVendorResolution:
    def test_exact_normalized_match(self):
        engine = _make_engine()
        s = _make_session(engine)
        org, _proj = _project(s)
        _vendor(s, org, name="Plombert Inc.")
        s.flush()
        res = resolve_quote_document(
            s, "2026001_QUOTE_22-Plumbing_PlombertInc_selected.xlsx"
        )
        assert res.vendor_id is not None
        assert res.vendor_method == "vendor_slug_exact"

    def test_substring_match_either_direction(self):
        engine = _make_engine()
        s = _make_session(engine)
        org, _proj = _project(s)
        # Vendor name has extra words the slug doesn't carry.
        _vendor(s, org, name="ABC Tile and Stone Ltd")
        s.flush()
        res = resolve_quote_document(
            s, "2026001_QUOTE_09-Finishes_ABCTile_pending.xlsx"
        )
        assert res.vendor_id is not None
        assert res.vendor_method == "vendor_slug_substring"

    def test_no_vendor_match_stays_unresolved(self):
        engine = _make_engine()
        s = _make_session(engine)
        _org, _proj = _project(s)
        s.flush()
        res = resolve_quote_document(
            s, "2026001_QUOTE_22-Plumbing_PlombertInc_selected.xlsx"
        )
        assert res.vendor_id is None
        assert any("matched no Vendor" in w for w in res.warnings)

    def test_ambiguous_vendor_match_stays_unresolved(self):
        """Two vendor names that fold to the exact same normalized string --
        a genuine tie, not just superficially similar names."""
        engine = _make_engine()
        s = _make_session(engine)
        org, _proj = _project(s)
        _vendor(s, org, name="Plombert Inc.")
        _vendor(s, org, name="PLOMBERT INC")  # same fold: "plombertinc"
        s.flush()
        res = resolve_quote_document(
            s, "2026001_QUOTE_22-Plumbing_PlombertInc_selected.xlsx"
        )
        assert res.vendor_id is None
        assert any("ambiguously" in w for w in res.warnings)

    def test_no_vendor_slug_in_filename_is_not_an_error(self):
        """SOW/GREENSHEET/JOBCOST/BUDGET filenames carry no VendorSlug at
        all -- that's a valid shape, not a resolution failure."""
        engine = _make_engine()
        s = _make_session(engine)
        _org, project = _project(s)
        s.flush()
        res = resolve_quote_document(s, "2026001_SOW_v1.xlsx")
        assert res.project_id == project.canonical_id
        assert res.vendor_id is None
        assert res.vendor_method == "unresolved"
        # No vendor-specific warning -- there was nothing to resolve.
        assert not any("Vendor" in w for w in res.warnings)


class TestPartialResolution:
    def test_project_and_vendor_resolve_package_does_not(self):
        engine = _make_engine()
        s = _make_session(engine)
        org, _proj = _project(s)
        _vendor(s, org, name="Plombert Inc.")
        s.flush()  # no SowPackage created

        res = resolve_quote_document(
            s, "2026001_QUOTE_22-Plumbing_PlombertInc_selected.xlsx"
        )
        assert res.project_id is not None
        assert res.vendor_id is not None
        assert res.package_id is None
        assert res.fully_resolved is False


# ---------------------------------------------------------------------------
# Real-DB smoke check: resolves correctly against Rockland, the one real
# structured project that exists. Explicitly does NOT claim this proves
# resolution against a second real project -- confirmed separately that no
# real project besides Rockland has any SowPackage data, and no real Drive
# document anywhere follows the new naming convention yet (see
# REFOUNDATION_BUILD_NOTES.md). That gap is real and unaddressed by this
# resolver being correct.
# ---------------------------------------------------------------------------

class TestRealDbSmoke:
    @pytest.fixture
    def real_session(self):
        from pathlib import Path

        from project_db.db.session import get_engine

        db_path = Path(__file__).resolve().parents[1] / "project_db.sqlite"
        if not db_path.exists():
            pytest.skip("real project_db.sqlite not present in this checkout")
        engine = get_engine(f"sqlite:///{db_path.as_posix()}")
        SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)
        s = SessionLocal()
        yield s
        s.close()

    def test_resolves_rockland_plumbing_quote_from_filename_alone(self, real_session):
        res = resolve_quote_document(
            real_session, "2026001_QUOTE_22-Plumbing_PlombertInc_selected.xlsx"
        )
        assert res.project_id is not None, res.warnings
        assert res.package_id is not None, res.warnings
        # Vendor may or may not exist in the real DB depending on prior
        # verification runs -- assert project+package only, which are the
        # parts guaranteed to exist (Rockland's real, persisted SOW data).
