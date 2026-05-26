"""/db raw-row inspector -- read-only dev affordance.

Reflective: every SQLAlchemy table in Base.metadata gets a page
automatically.  No edit, no exec, no query -- DB Browser for SQLite
covers anything beyond "top 100 rows."

Per the M5 plan review #4: keep this small and ugly.  Resist the urge
to add a query builder, a filter UI, an export button, or any other
DB-Browser-shaped feature -- they pull this past the dev-affordance
line into "second product surface."
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from project_db.web import ui_views
from project_db.web.deps import db


def register(router: APIRouter, templates: Jinja2Templates) -> None:
    @router.get("/db", response_class=HTMLResponse)
    def db_index(request: Request, session: Session = Depends(db)) -> HTMLResponse:
        tables = ui_views.db_table_index(session)
        return templates.TemplateResponse(
            request, "db_index.html", {"tables": tables}
        )

    @router.get("/db/{table_name}", response_class=HTMLResponse)
    def db_show(
        table_name: str,
        request: Request,
        session: Session = Depends(db),
    ) -> HTMLResponse:
        data = ui_views.db_table_rows(session, table_name, limit=100)
        if data is None:
            raise HTTPException(status_code=404, detail="Table not found")
        return templates.TemplateResponse(
            request, "db_table.html", {"d": data}
        )
