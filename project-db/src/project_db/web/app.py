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
from project_db.web.deps import db, db_path, git_sha
from project_db.web.routes import ask as ask_routes
from project_db.web.routes import doctor as doctor_routes
from project_db.web.routes import projects as project_routes
from project_db.web.routes import proposals as proposal_routes
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

    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

    @app.get("/", response_class=HTMLResponse)
    def dashboard(request: Request, session: Session = Depends(db)) -> HTMLResponse:
        summary = ui_views.dashboard_summary(session)
        pending = ui_views.recent_pending_proposals(session, limit=10)
        return templates.TemplateResponse(
            request,
            "dashboard.html",
            {"summary": summary, "pending": pending},
        )

    page_router = APIRouter()
    project_routes.register(page_router, templates)
    proposal_routes.register(page_router, templates)
    doctor_routes.register(page_router, templates)
    ask_routes.register(page_router, templates)
    task_routes.register(page_router, templates)
    app.include_router(page_router)

    return app
