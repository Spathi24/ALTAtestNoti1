"""Engine and session factory.

The DB URL is read from `PROJECT_DB_URL` in the environment. For local dev,
sqlite works out of the box (with UUID stored as TEXT — see `base.py`); for
production use Postgres.
"""
from __future__ import annotations

import os
from contextlib import contextmanager
from typing import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

DEFAULT_URL = "sqlite:///./project_db.sqlite"


def get_engine(url: str | None = None):
    """Build a SQLAlchemy engine. Resolves URL from env if not given."""
    resolved = url or os.environ.get("PROJECT_DB_URL", DEFAULT_URL)
    # SQLite: same-thread restriction off, makes the CLI nicer to work with.
    connect_args = {"check_same_thread": False} if resolved.startswith("sqlite") else {}
    return create_engine(resolved, connect_args=connect_args, future=True)


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
