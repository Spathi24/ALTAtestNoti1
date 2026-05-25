"""Proposal queue + detail routes.

Phase B+C ships READ-ONLY.  Accept / reject POST endpoints are deliberately
absent here -- they land in Phase D as the riskiest piece of the UI.
A test (`tests/test_web_phase_b.py::TestForbiddenRoutes`) pins this until
Phase D lands.
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from project_db.web import ui_views
from project_db.web.deps import db


def register(router: APIRouter, templates: Jinja2Templates) -> None:
    @router.get("/proposals", response_class=HTMLResponse)
    def proposals_index(
        request: Request,
        status: Optional[str] = Query(default=None),
        kind: Optional[str] = Query(default=None),
        session: Session = Depends(db),
    ) -> HTMLResponse:
        data = ui_views.proposal_queue(session, status=status, kind=kind)
        return templates.TemplateResponse(
            request, "proposal_list.html", {"d": data}
        )

    @router.get("/proposals/{proposal_id}", response_class=HTMLResponse)
    def proposal_show(
        proposal_id: str,
        request: Request,
        session: Session = Depends(db),
    ) -> HTMLResponse:
        detail = ui_views.proposal_detail(session, proposal_id)
        if detail is None:
            raise HTTPException(status_code=404, detail="Proposal not found")
        return templates.TemplateResponse(
            request, "proposal_detail.html", {"p": detail}
        )
