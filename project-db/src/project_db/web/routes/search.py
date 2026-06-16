"""/search -- hybrid (semantic + keyword) search over embedded document text.

Read-only retrieval: no LLM tokens spent, just the tiny query embedding. Finds
the exact clause / number / name across every contract. GET with query params
so results are shareable/bookmarkable.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from project_db.web import ui_views
from project_db.web.deps import db


def register(router: APIRouter, templates: Jinja2Templates) -> None:
    @router.get("/search", response_class=HTMLResponse)
    def search(
        request: Request,
        q: str = "",
        project: str = "",
        session: Session = Depends(db),
    ) -> HTMLResponse:
        data = ui_views.search_documents(session, q, project_ref=(project or None))
        return templates.TemplateResponse(
            request,
            "search.html",
            {"data": data, "q": q, "project": project},
        )
