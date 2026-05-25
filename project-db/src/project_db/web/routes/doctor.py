"""/doctor -- audit canonical-data integrity (read-only).

Renders the same data structure ``cmd_doctor`` prints.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from project_db.web import ui_views
from project_db.web.deps import db


def register(router: APIRouter, templates: Jinja2Templates) -> None:
    @router.get("/doctor", response_class=HTMLResponse)
    def doctor_page(request: Request, session: Session = Depends(db)) -> HTMLResponse:
        data = ui_views.doctor_report(session)
        return templates.TemplateResponse(
            request, "doctor.html", {"d": data}
        )
