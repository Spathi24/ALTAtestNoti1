"""FastAPI app factory for the local UI.

Localhost-only.  Mounts:
  - ``/`` (and the eventual phase B-E routes) as Jinja-rendered HTML
  - ``/static`` for app.css and vendored htmx.min.js
  - ``/docs`` is FastAPI's auto Swagger -- a free debugging surface, not a
    user-facing API
"""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from project_db.web import ui_views
from project_db.web.deps import (
    app_version,
    db,
    db_path,
    git_sha,
    uptime_str,
)
from project_db.web.routes import ask as ask_routes
from project_db.web.routes import db as db_routes
from project_db.web.routes import doctor as doctor_routes
from project_db.web.routes import projects as project_routes
from project_db.web.routes import proposals as proposal_routes
from project_db.web.routes import search as search_routes
from project_db.web.routes import tasks as task_routes

_PKG_DIR = Path(__file__).parent
TEMPLATES_DIR = _PKG_DIR / "templates"
STATIC_DIR = _PKG_DIR / "static"


def create_app() -> FastAPI:
    """Construct the FastAPI app.  Called from ``cmd_serve`` and tests."""
    app = FastAPI(
        title="ALTA / project_db",
        description="Local read-mostly UI.  Not for remote use.",
        version="0.3.0-ui-phaseA",
        # No CORS middleware on purpose -- this app is 127.0.0.1-only.
    )

    templates = Jinja2Templates(directory=str(TEMPLATES_DIR))
    templates.env.globals["git_sha"] = git_sha
    templates.env.globals["db_path"] = db_path
    templates.env.globals["app_version"] = app_version
    templates.env.globals["uptime_str"] = uptime_str

    # Last background-refresh result (populated by the serve auto-refresh
    # thread; defaults to "never" so the footer is safe in tests / when
    # refresh is disabled).
    from project_db.web import refresh_state

    templates.env.globals["last_refresh"] = refresh_state.get_last

    # Plain-language money glossary -- rendered by the project page and the
    # Financials panel so the "which number do I trust?" story is consistent.
    templates.env.globals["money_glossary"] = ui_views.money_glossary

    # `| from_json` -- safely parse a JSON string in templates.  Used by
    # propose_result.html to break scope proposals down by source label
    # (contract / roadmap) without forcing the service module to
    # pre-parse every proposed_value.  Returns None on bad JSON so
    # templates can fall back via `| default({})`.
    import json as _json

    def _from_json(value):
        if value is None:
            return None
        if isinstance(value, (dict, list)):
            return value
        try:
            return _json.loads(value)
        except (_json.JSONDecodeError, TypeError):
            return None

    templates.env.filters["from_json"] = _from_json

    def _days_since(iso_string: str | None) -> int | None:
        """Return integer days elapsed since an ISO datetime string (UTC)."""
        if not iso_string:
            return None
        try:
            from datetime import datetime

            dt = datetime.fromisoformat(iso_string.replace("Z", "+00:00"))
            if dt.tzinfo is not None:
                dt = dt.replace(tzinfo=None)
            return max(0, (datetime.utcnow() - dt).days)
        except (ValueError, TypeError, AttributeError):
            return None

    templates.env.filters["days_since"] = _days_since

    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

    @app.get("/", response_class=HTMLResponse)
    def dashboard(request: Request, session: Session = Depends(db)) -> HTMLResponse:
        briefing = ui_views.attention_briefing(session)
        value = ui_views.value_caught(session)
        summary = ui_views.dashboard_summary(session)
        pending = ui_views.recent_pending_proposals(session, limit=10)
        return templates.TemplateResponse(
            request,
            "dashboard.html",
            {"briefing": briefing, "value_caught": value, "summary": summary, "pending": pending},
        )

    page_router = APIRouter()
    project_routes.register(page_router, templates)
    proposal_routes.register(page_router, templates)
    search_routes.register(page_router, templates)
    doctor_routes.register(page_router, templates)
    ask_routes.register(page_router, templates)
    task_routes.register(page_router, templates)
    db_routes.register(page_router, templates)
    app.include_router(page_router)

    return app
