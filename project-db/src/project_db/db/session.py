"""Engine and session factory.

The DB URL is read from `PROJECT_DB_URL` in the environment. For local dev,
sqlite works out of the box (with UUID stored as TEXT — see `base.py`); for
production use Postgres.
"""
from __future__ import annotations

import os
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

# Default DB path: <project-db>/project_db.sqlite, regardless of cwd.
# (Used only if PROJECT_DB_URL env var is unset.)
_PKG_ROOT = Path(__file__).resolve().parent.parent.parent.parent
DEFAULT_URL = f"sqlite:///{(_PKG_ROOT / 'project_db.sqlite').as_posix()}"


def get_engine(url: str | None = None):
    """Build a SQLAlchemy engine. Resolves URL from env if not given."""
    resolved = url or os.environ.get("PROJECT_DB_URL", DEFAULT_URL)
    # SQLite: same-thread restriction off, makes the CLI nicer to work with.
    connect_args = {"check_same_thread": False} if resolved.startswith("sqlite") else {}
    return create_engine(resolved, connect_args=connect_args, future=True)


@event.listens_for(Engine, "connect")
def _enable_sqlite_foreign_keys(dbapi_connection, connection_record):
    """SQLite ignores FK constraints unless `PRAGMA foreign_keys=ON` per-connection.

    Without this, DocumentText's CASCADE-delete annotation is decorative --
    deleting a Document would orphan its DocumentText row.
    """
    if dbapi_connection.__class__.__module__.startswith("sqlite3"):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


_SessionLocal: sessionmaker[Session] | None = None


def get_session_factory() -> sessionmaker[Session]:
    global _SessionLocal
    if _SessionLocal is None:
        _SessionLocal = sessionmaker(bind=get_engine(), expire_on_commit=False)
    return _SessionLocal


@contextmanager
def session_scope() -> Iterator[Session]:
    """Provide a transactional scope around a series of operations."""
    factory = get_session_factory()
    session = factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
