"""Phase 3 Scope of Work: SowPackage + SowItem.

Scope only -- no cost, no quote, no PO, no ledger mutation. Covers:
- Fresh DB has both tables.
- Migration adds both tables to a DB that predates Phase 3.
- Project linkage, package -> items relationship.
- included/excluded scope flag.
- material_spec persistence.
- item_code uniqueness scoped to (project, package) -- not global.
- SowItem is a distinct, coarser concept than FinancialLineItem (no cost
  fields exist on SowItem).
"""

from __future__ import annotations

import json
import uuid

import pytest
from sqlalchemy import create_engine, inspect
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from project_db.db.base import Base
from project_db.db.migrations import ensure_sqlite_schema
from project_db.db.models import Client, Organization, Project, SowItem, SowPackage
from project_db.db.models.work import ProjectStatus

# ---------------------------------------------------------------------------
# Helpers
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


def _org_client(session):
    org = Organization(canonical_id=uuid.uuid4(), name="Test Org")
    client = Client(canonical_id=uuid.uuid4(), name="Test Client", organization_id=org.canonical_id)
    session.add_all([org, client])
    session.flush()
    return org, client


def _project(session, client, *, name="923-927 Rockland", code="2026001"):
    p = Project(
        canonical_id=uuid.uuid4(),
        name=name,
        client_id=client.canonical_id,
        status=ProjectStatus.ACTIVE,
        code=code,
    )
    session.add(p)
    session.flush()
    return p


def _package(session, project, *, division_code="22", trade_name="Plumbing", title="22-Plumbing"):
    pkg = SowPackage(
        canonical_id=uuid.uuid4(),
        project_id=project.canonical_id,
        division_code=division_code,
        trade_name=trade_name,
        title=title,
        status="draft",
    )
    session.add(pkg)
    session.flush()
    return pkg


def _item(session, project, package, *, item_code, description="test item", division_code="22", included=True, material_spec=None):
    item = SowItem(
        canonical_id=uuid.uuid4(),
        project_id=project.canonical_id,
        package_id=package.canonical_id if package is not None else None,
        item_code=item_code,
        description=description,
        division_code=division_code,
        included=included,
        material_spec=json.dumps(material_spec) if material_spec is not None else None,
    )
    session.add(item)
    session.flush()
    return item


# ---------------------------------------------------------------------------
# Schema tests
# ---------------------------------------------------------------------------

class TestSchema:
    def test_tables_present_on_fresh_db(self):
        engine = _make_engine()
        insp = inspect(engine)
        tables = set(insp.get_table_names())
        assert "sow_package" in tables
        assert "sow_item" in tables

    def test_tables_added_to_existing_db(self):
        """Simulate a DB that predates Phase 3: create tables minus sow_*, then migrate."""
        engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        # Build the metadata graph without the sow tables to simulate a pre-Phase-3 DB.
        tables_to_create = [
            t for name, t in Base.metadata.tables.items()
            if name not in ("sow_package", "sow_item")
        ]
        Base.metadata.create_all(engine, tables=tables_to_create)

        insp = inspect(engine)
        assert "sow_package" not in set(insp.get_table_names())

        ensure_sqlite_schema(engine)

        insp = inspect(engine)
        tables = set(insp.get_table_names())
        assert "sow_package" in tables
        assert "sow_item" in tables

    def test_sow_item_has_no_cost_fields(self):
        """SowItem is scope, not ledger -- it must not carry money columns."""
        insp_cols = {c.name for c in SowItem.__table__.columns}
        for forbidden in ("amount", "material_amount", "labour_amount", "total_amount", "cost", "price"):
            assert forbidden not in insp_cols, f"SowItem must not have a {forbidden!r} column"


# ---------------------------------------------------------------------------
# Relationship / behavior tests
# ---------------------------------------------------------------------------

class TestPackageItemLinkage:
    @pytest.fixture
    def session(self):
        engine = _make_engine()
        return _make_session(engine)

    def test_project_linkage(self, session):
        _org, client = _org_client(session)
        project = _project(session, client)
        pkg = _package(session, project)
        session.commit()

        fetched = session.query(SowPackage).filter_by(canonical_id=pkg.canonical_id).one()
        assert fetched.project_id == project.canonical_id

    def test_rockland_can_have_packages_and_items(self, session):
        _org, client = _org_client(session)
        project = _project(session, client, name="923-927 Rockland", code="2026001")
        pkg = _package(session, project, division_code="09", trade_name="Finishes", title="09-Finishes")
        item = _item(session, project, pkg, item_code="SOW-025", description="Interior paint, 2 coats")
        session.commit()

        fetched_pkg = session.query(SowPackage).filter_by(project_id=project.canonical_id).one()
        fetched_item = session.query(SowItem).filter_by(package_id=fetched_pkg.canonical_id).one()
        assert fetched_item.item_code == "SOW-025"
        assert fetched_item.project_id == project.canonical_id

    def test_package_has_many_items(self, session):
        _org, client = _org_client(session)
        project = _project(session, client)
        pkg = _package(session, project)
        _item(session, project, pkg, item_code="SOW-001", description="Rough-in")
        _item(session, project, pkg, item_code="SOW-002", description="Fixtures")
        session.commit()

        items = session.query(SowItem).filter_by(package_id=pkg.canonical_id).all()
        assert len(items) == 2

    def test_general_requirements_item_has_no_package(self, session):
        """Division 01 (General Requirements) is GC overhead -- it belongs to
        the SOW but to no subcontractor package (no PKG/QUOTE file exists for
        it, per NAMING_CONVENTIONS.md). package_id must accept NULL for this.
        """
        _org, client = _org_client(session)
        project = _project(session, client)
        item = _item(
            session, project, None,
            item_code="SOW-001", description="Site supervision and coordination",
            division_code="01",
        )
        session.commit()

        fetched = session.query(SowItem).filter_by(canonical_id=item.canonical_id).one()
        assert fetched.package_id is None
        assert fetched.division_code == "01"

    def test_included_excluded_scope(self, session):
        _org, client = _org_client(session)
        project = _project(session, client)
        pkg = _package(session, project)
        included_item = _item(session, project, pkg, item_code="SOW-010", included=True)
        excluded_item = _item(session, project, pkg, item_code="SOW-011", included=False)
        session.commit()

        assert session.query(SowItem).get(included_item.canonical_id).included is True
        assert session.query(SowItem).get(excluded_item.canonical_id).included is False

    def test_material_spec_persistence(self, session):
        _org, client = _org_client(session)
        project = _project(session, client)
        pkg = _package(session, project)
        spec = {"material": "PEX", "grade": "B", "finish": "n/a"}
        item = _item(session, project, pkg, item_code="SOW-020", material_spec=spec)
        session.commit()

        fetched = session.query(SowItem).filter_by(canonical_id=item.canonical_id).one()
        assert json.loads(fetched.material_spec) == spec


class TestItemCodeUniqueness:
    @pytest.fixture
    def session(self):
        engine = _make_engine()
        return _make_session(engine)

    def test_duplicate_item_code_same_package_raises(self, session):
        _org, client = _org_client(session)
        project = _project(session, client)
        pkg = _package(session, project)
        _item(session, project, pkg, item_code="SOW-030")
        session.commit()

        with pytest.raises(IntegrityError):
            _item(session, project, pkg, item_code="SOW-030")
            session.commit()

    def test_same_item_code_different_package_allowed(self, session):
        """item_code uniqueness is scoped to (project, package), not global."""
        _org, client = _org_client(session)
        project = _project(session, client)
        pkg_a = _package(session, project, division_code="09", title="09-Finishes")
        pkg_b = _package(session, project, division_code="22", title="22-Plumbing")
        _item(session, project, pkg_a, item_code="SOW-001")
        _item(session, project, pkg_b, item_code="SOW-001")
        session.commit()  # should not raise

        count = session.query(SowItem).filter_by(item_code="SOW-001").count()
        assert count == 2

    def test_multiple_null_item_codes_allowed(self, session):
        _org, client = _org_client(session)
        project = _project(session, client)
        pkg = _package(session, project)
        _item(session, project, pkg, item_code=None)
        _item(session, project, pkg, item_code=None)
        session.commit()  # should not raise

        count = session.query(SowItem).filter_by(package_id=pkg.canonical_id).count()
        assert count == 2


class TestNoLedgerMutation:
    """Phase 3 must not touch FinancialLineItem or any ledger table."""

    def test_creating_sow_data_does_not_touch_financial_line_item(self):
        from project_db.db.models import FinancialLineItem

        engine = _make_engine()
        session = _make_session(engine)
        _org, client = _org_client(session)
        project = _project(session, client)
        pkg = _package(session, project)
        _item(session, project, pkg, item_code="SOW-040")
        session.commit()

        assert session.query(FinancialLineItem).count() == 0
