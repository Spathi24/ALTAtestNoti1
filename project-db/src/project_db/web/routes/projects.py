"""Project list + detail + document detail routes.  Read-only."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from project_db.web import ui_views
from project_db.web.deps import db


def register(router: APIRouter, templates: Jinja2Templates) -> None:
    @router.get("/projects", response_class=HTMLResponse)
    def projects_index(request: Request, session: Session = Depends(db)) -> HTMLResponse:
        rows = ui_views.project_list_rows(session)
        return templates.TemplateResponse(
            request, "project_list.html", {"rows": rows}
        )

    @router.get("/projects/{project_id}", response_class=HTMLResponse)
    def project_show(
        project_id: str,
        request: Request,
        session: Session = Depends(db),
    ) -> HTMLResponse:
        data = ui_views.project_detail(session, project_id)
        if data is None:
            raise HTTPException(status_code=404, detail="Project not found")
        return templates.TemplateResponse(
            request, "project_detail.html", {"d": data}
        )

    @router.get("/projects/{project_id}/financials", response_class=HTMLResponse)
    def project_financials_show(
        project_id: str,
        request: Request,
        session: Session = Depends(db),
    ) -> HTMLResponse:
        data = ui_views.project_financials(session, project_id)
        if data is None:
            raise HTTPException(status_code=404, detail="Project not found")
        return templates.TemplateResponse(
            request, "project_financials.html", {"d": data}
        )

    @router.get("/documents/{document_id}", response_class=HTMLResponse)
    def document_show(
        document_id: str,
        request: Request,
        session: Session = Depends(db),
    ) -> HTMLResponse:
        data = ui_views.document_detail(session, document_id)
        if data is None:
            raise HTTPException(status_code=404, detail="Document not found")
        return templates.TemplateResponse(
            request, "document_detail.html", {"d": data}
        )
