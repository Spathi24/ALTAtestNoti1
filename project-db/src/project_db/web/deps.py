"""FastAPI request-time dependencies and process-wide helpers.

These are deliberately thin.  Anything that does derived work belongs in
``ui_views`` (a service module the routes call into), not here.
"""
from __future__ import annotations

import os
import subprocess
from functools import lru_cache
from typing import Iterator

from sqlalchemy.orm import Session

from project_db.db import session_scope


def db() -> Iterator[Session]:
    """FastAPI dependency: yield a transactional Session for the request.

    Routes are sync; FastAPI runs them in a threadpool, so a plain
    ``session_scope`` works.  Mutations commit on the way out via
    ``session_scope`` itself; we never call commit inside a route.
    """
    with session_scope() as session:
        yield session


@lru_cache(maxsize=1)
def git_sha() -> str:
    """Short git SHA of the working tree, for the footer.

    Must never crash startup.  When the package is installed outside a git
    checkout (pip install, archive copy, sdist), ``git rev-parse`` will
    fail; we return "unknown" instead.
    """
    try:
        out = subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
            stderr=subprocess.DEVNULL,
            timeout=2,
        )
        return out.decode("ascii", errors="replace").strip() or "unknown"
    except (subprocess.SubprocessError, FileNotFoundError, OSError):
        return "unknown"


@lru_cache(maxsize=1)
def db_path() -> str:
    """Display path for the footer.  Reads PROJECT_DB_URL after .env load."""
    url = os.environ.get("PROJECT_DB_URL", "(unset)")
    return url


def build_monday_writeback(session):
    """Construct a MondayConnector to pass as ``writeback`` to accept_proposal.

    Isolated here so tests can ``monkeypatch.setattr`` this single function
    instead of patching MondayConnector / the Monday API.  The accept route
    calls it; nothing else does.

    Raises whatever the connector constructor raises (typically: missing
    MONDAY_API_TOKEN).  The route catches and surfaces it as an error in
    the decision_idle fragment.
    """
    from project_db.connectors.monday.connector import MondayConnector
    from project_db.db.models import Organization

    org = session.query(Organization).first()
    if org is None:
        raise RuntimeError("no Organization row -- run init-db first")
    return MondayConnector(session=session, organization_id=org.canonical_id)
