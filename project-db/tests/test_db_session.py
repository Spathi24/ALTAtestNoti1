"""Tests for the engine, session factory, and session_scope context manager."""
from __future__ import annotations

import pytest
from sqlalchemy import inspect
from sqlalchemy.orm import Session, sessionmaker

from project_db.db import get_engine, session_scope
from project_db.db.models import Client, Organization


@pytest.fixture
def shared_session_scope(db_engine, monkeypatch):
    """Patch the package's cached session factory to bind to our test engine.

    Required because session_scope() pulls from the cached factory in
    project_db.db.session — without this, it opens a separate :memory: DB.
    """
    from project_db.db import session as session_mod

    factory = sessionmaker(bind=db_engine, expire_on_commit=False)
    monkeypatch.setattr(session_mod, "_SessionLocal", factory)
    yield
    # monkeypatch undoes itself automatically


class TestSessionManagement:
    def test_session_scope_is_context_manager(self, shared_session_scope):
        with session_scope() as s:
            assert isinstance(s, Session)
            assert s.is_active

    def test_session_scope_commits_on_success(
        self, shared_session_scope, session: Session, org: Organization
    ):
        with session_scope() as s:
            client = Client(organization_id=org.canonical_id, name="Committed Client")
            s.add(client)

        result = session.query(Client).filter_by(name="Committed Client").first()
        assert result is not None

    def test_session_scope_rolls_back_on_error(
        self, shared_session_scope, session: Session, org: Organization
    ):
        with pytest.raises(ValueError):
            with session_scope() as s:
                s.add(Client(organization_id=org.canonical_id, name="Will Not Commit"))
                raise ValueError("Force rollback")

        result = session.query(Client).filter_by(name="Will Not Commit").first()
        assert result is None


class TestSessionTransactions:
    def test_multiple_operations_in_one_commit(self, session: Session, org: Organization):
        session.add_all(
            [
                Client(organization_id=org.canonical_id, name="Client 1"),
                Client(organization_id=org.canonical_id, name="Client 2"),
            ]
        )
        session.commit()

        count = session.query(Client).filter_by(organization_id=org.canonical_id).count()
        assert count == 2


class TestDatabaseConnection:
    def test_get_engine_returns_inspectable_engine(self):
        engine = get_engine()
        assert engine is not None
        inspector = inspect(engine)
        assert inspector is not None

    def test_engine_can_open_multiple_connections(self):
        engine = get_engine()
        conn1 = engine.connect()
        conn2 = engine.connect()
        try:
            assert conn1 is not conn2
        finally:
            conn1.close()
            conn2.close()


class TestConcurrentSessions:
    def test_multiple_sessions_see_same_data(
        self, shared_session_scope, session: Session, org: Organization
    ):
        client = Client(organization_id=org.canonical_id, name="Shared Client")
        session.add(client)
        session.commit()
        cid = client.canonical_id

        with session_scope() as s:
            result = s.query(Client).filter_by(canonical_id=cid).first()
            assert result is not None
            assert result.name == "Shared Client"
