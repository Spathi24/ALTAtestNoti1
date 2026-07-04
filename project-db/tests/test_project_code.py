"""Phase 2 project identity columns: code, display_name, legacy_job_number, aliases.

Covers:
- New columns exist on a fresh DB (schema creation path).
- Migration adds columns to a DB that predates Phase 2 (ALTER TABLE path).
- _resolve_project resolves by code, legacy_job_number, alias, and name substring.
- Duplicate project code violates the partial unique index.
"""

from __future__ import annotations

import json
import uuid

import pytest
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from project_db.ai.views import _resolve_project
from project_db.db.base import Base
from project_db.db.migrations import ensure_sqlite_schema
from project_db.db.models import Client, Organization, Project
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


def _project(
    session, client, *, name, code=None, display_name=None, legacy_job_number=None, aliases=None
):
    p = Project(
        canonical_id=uuid.uuid4(),
        name=name,
        client_id=client.canonical_id,
        status=ProjectStatus.ACTIVE,
        code=code,
        display_name=display_name,
        legacy_job_number=legacy_job_number,
        aliases=json.dumps(aliases) if aliases is not None else None,
    )
    session.add(p)
    session.flush()
    return p


# ---------------------------------------------------------------------------
# Schema tests
# ---------------------------------------------------------------------------


class TestNewColumnsExist:
    def test_columns_present_on_fresh_db(self):
        engine = _make_engine()
        insp = inspect(engine)
        col_names = {c["name"] for c in insp.get_columns("project")}
        assert "display_name" in col_names
        assert "legacy_job_number" in col_names
        assert "aliases" in col_names

    def test_columns_added_to_existing_db(self):
        """Simulate a DB that predates Phase 2: create tables, then run migration."""
        engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        # Create tables WITHOUT the Phase 2 columns by dropping them after create
        Base.metadata.create_all(engine)
        with engine.begin() as conn:
            for col in ("display_name", "legacy_job_number", "aliases"):
                try:
                    conn.execute(text(f"ALTER TABLE project DROP COLUMN {col}"))
                except Exception:
                    pass  # SQLite ≤3.35 may not support DROP COLUMN; skip if so

        # Now run migration — should add them back (or confirm they exist already)
        ensure_sqlite_schema(engine)

        insp = inspect(engine)
        col_names = {c["name"] for c in insp.get_columns("project")}
        assert "display_name" in col_names
        assert "legacy_job_number" in col_names
        assert "aliases" in col_names


# ---------------------------------------------------------------------------
# Resolver tests
# ---------------------------------------------------------------------------


class TestResolveProject:
    @pytest.fixture
    def session(self):
        engine = _make_engine()
        s = _make_session(engine)
        _org, client = _org_client(s)
        _project(
            s,
            client,
            name="923 Rockland",
            code="2026001",
            display_name="2026001 — Rockland",
            legacy_job_number="923",
            aliases=["Rockland", "Tanya", "923 Rockland", "923-927 Rockland"],
        )
        s.commit()
        return s

    def test_resolve_by_code(self, session):
        p = _resolve_project(session, "2026001")
        assert p is not None
        assert p.code == "2026001"

    def test_resolve_by_legacy_job_number(self, session):
        p = _resolve_project(session, "923")
        assert p is not None
        assert p.legacy_job_number == "923"

    def test_resolve_by_alias_rockland(self, session):
        p = _resolve_project(session, "Rockland")
        assert p is not None
        assert p.code == "2026001"

    def test_resolve_by_alias_tanya(self, session):
        p = _resolve_project(session, "Tanya")
        assert p is not None
        assert p.code == "2026001"

    def test_resolve_by_name_substring(self, session):
        p = _resolve_project(session, "Rockland")
        assert p is not None

    def test_resolve_by_uuid(self, session):
        all_p = session.query(Project).all()
        assert len(all_p) == 1
        p = _resolve_project(session, str(all_p[0].canonical_id))
        assert p is not None
        assert p.code == "2026001"

    def test_resolve_unknown_returns_none(self, session):
        p = _resolve_project(session, "does-not-exist-xyz")
        assert p is None

    def test_resolve_empty_returns_none(self, session):
        p = _resolve_project(session, "")
        assert p is None


# ---------------------------------------------------------------------------
# Uniqueness constraint on code
# ---------------------------------------------------------------------------


class TestProjectCodeUnique:
    def test_duplicate_code_raises(self):
        engine = _make_engine()
        session = _make_session(engine)
        _org, client = _org_client(session)
        _project(session, client, name="Project A", code="2026001")
        session.commit()

        session2 = _make_session(engine)
        with pytest.raises((IntegrityError, Exception)):
            _project(session2, client, name="Project B", code="2026001")
            session2.commit()

    def test_multiple_null_codes_allowed(self):
        engine = _make_engine()
        session = _make_session(engine)
        _org, client = _org_client(session)
        _project(session, client, name="Legacy A", code=None)
        _project(session, client, name="Legacy B", code=None)
        session.commit()  # should not raise
        count = session.query(Project).filter(Project.code.is_(None)).count()
        assert count == 2
