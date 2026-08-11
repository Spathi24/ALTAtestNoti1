"""SC-1: additive ScopeContext foundation.

Covers the model, the (project_id, context_key) DB uniqueness backstop, the two
additive Document binding columns and their defaults, and the SQLite migration
path (blank DB + old-DB ALTER + idempotency). SC-1 is schema-only: no backfill,
no behaviour change -- these tests pin exactly that.
"""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine, inspect
from sqlalchemy import text as _text
from sqlalchemy.exc import IntegrityError

from project_db.db.models import Client, Document, Organization, Project, ScopeContext
from project_db.db.models.work import ProjectStatus


@pytest.fixture
def project(session, org: Organization) -> Project:
    c = Client(name="Rockland Client", organization_id=org.canonical_id)
    session.add(c)
    session.flush()
    p = Project(
        name="923-927 Rockland",
        code="2026001",
        client_id=c.canonical_id,
        status=ProjectStatus.ACTIVE,
    )
    session.add(p)
    session.commit()
    return p


class TestScopeContextModel:
    def test_create_and_read(self, session, project):
        ctx = ScopeContext(
            project_id=project.canonical_id,
            context_key="923_INTERIOR",
            label="923 Rockland -- Interior",
            kind="unit",
            unit_area="3rd floor",
        )
        session.add(ctx)
        session.commit()
        got = session.query(ScopeContext).filter_by(context_key="923_INTERIOR").one()
        assert got.project_id == project.canonical_id
        assert got.label == "923 Rockland -- Interior"

    def test_context_key_unique_per_project(self, session, project):
        """DB backstop: (project_id, context_key) is unique. Deliberately bypasses
        any app guard -- a duplicate key must fail at the database."""
        session.add(ScopeContext(project_id=project.canonical_id, context_key="927_UNIT"))
        session.commit()
        session.add(ScopeContext(project_id=project.canonical_id, context_key="927_UNIT"))
        with pytest.raises(IntegrityError):
            session.commit()
        session.rollback()

    def test_same_key_allowed_in_different_projects(self, session, org, project):
        c = Client(name="Other", organization_id=org.canonical_id)
        session.add(c)
        session.flush()
        p2 = Project(
            name="Other Project",
            code="2026002",
            client_id=c.canonical_id,
            status=ProjectStatus.ACTIVE,
        )
        session.add(p2)
        session.flush()
        session.add(ScopeContext(project_id=project.canonical_id, context_key="EXTERIOR"))
        session.add(ScopeContext(project_id=p2.canonical_id, context_key="EXTERIOR"))
        session.commit()  # same key, different projects -> allowed
        assert session.query(ScopeContext).filter_by(context_key="EXTERIOR").count() == 2


class TestDocumentBindingColumns:
    def test_defaults_are_legacy_unscoped_and_unbound(self, session):
        """A freshly created Document is NULL-bound and LEGACY_UNSCOPED -- NOT
        UNRESOLVED. The distinction is the whole point of the state column."""
        d = Document(name="Final SOW.pdf", url="drive://x")
        session.add(d)
        session.commit()
        assert d.scope_context_id is None
        assert d.context_resolution_state == "LEGACY_UNSCOPED"

    def test_document_can_bind_to_context(self, session, project):
        ctx = ScopeContext(project_id=project.canonical_id, context_key="923_INTERIOR")
        session.add(ctx)
        session.flush()
        d = Document(
            name="SOW 923 Rockland",
            url="drive://y",
            scope_context_id=ctx.canonical_id,
            context_resolution_state="RESOLVED",
        )
        session.add(d)
        session.commit()
        got = session.query(Document).filter_by(name="SOW 923 Rockland").one()
        assert got.scope_context_id == ctx.canonical_id
        assert got.context_resolution_state == "RESOLVED"


class TestScopeContextMigration:
    def test_blank_db_gets_table_and_document_columns(self, tmp_path):
        from project_db.db.migrations import ensure_sqlite_schema

        db = tmp_path / "old.sqlite"
        engine = create_engine(f"sqlite:///{db}", future=True)
        # Old DB with a document table that predates SC-1.
        with engine.begin() as conn:
            conn.execute(_text("CREATE TABLE document (canonical_id TEXT PRIMARY KEY)"))
        assert "scope_context" not in set(inspect(engine).get_table_names())

        ensure_sqlite_schema(engine)
        ensure_sqlite_schema(engine)  # idempotent: second run must not raise

        names = set(inspect(engine).get_table_names())
        assert "scope_context" in names
        doc_cols = {c["name"] for c in inspect(engine).get_columns("document")}
        assert {"scope_context_id", "context_resolution_state"} <= doc_cols
        engine.dispose()

    def test_fresh_create_all_has_scope_context(self, session):
        """create_all (the fresh-DB path) builds the table + document columns."""
        insp = inspect(session.get_bind())
        assert "scope_context" in set(insp.get_table_names())
        doc_cols = {c["name"] for c in insp.get_columns("document")}
        assert {"scope_context_id", "context_resolution_state"} <= doc_cols
