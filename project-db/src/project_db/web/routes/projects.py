"""Project list + detail + document detail routes.  Read-only."""

from __future__ import annotations

import uuid as _uuid

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from project_db.features import feature_enabled
from project_db.web import ui_views
from project_db.web.deps import db


def _require_feature(name: str) -> None:
    if not feature_enabled(name):
        raise HTTPException(status_code=404, detail="Feature disabled")


def register(router: APIRouter, templates: Jinja2Templates) -> None:
    @router.get("/projects", response_class=HTMLResponse)
    def projects_index(request: Request, session: Session = Depends(db)) -> HTMLResponse:
        rows = ui_views.project_list_rows(session)
        return templates.TemplateResponse(request, "project_list.html", {"rows": rows})

    @router.get("/projects/{project_id}", response_class=HTMLResponse)
    def project_show(
        project_id: str,
        request: Request,
        session: Session = Depends(db),
    ) -> HTMLResponse:
        data = ui_views.project_detail(session, project_id)
        if data is None:
            raise HTTPException(status_code=404, detail="Project not found")
        return templates.TemplateResponse(request, "project_detail.html", {"d": data})

    @router.get("/projects/{project_id}/financials", response_class=HTMLResponse)
    def project_financials_show(
        project_id: str,
        request: Request,
        session: Session = Depends(db),
    ) -> HTMLResponse:
        _require_feature("finance_legacy")
        data = ui_views.project_financials(session, project_id)
        if data is None:
            raise HTTPException(status_code=404, detail="Project not found")
        return templates.TemplateResponse(request, "project_financials.html", {"d": data})

    @router.get("/projects/{project_id}/margins", response_class=HTMLResponse)
    def project_margins_show(
        project_id: str,
        request: Request,
        session: Session = Depends(db),
    ) -> HTMLResponse:
        data = ui_views.project_division_margins(session, project_id)
        if data is None:
            raise HTTPException(status_code=404, detail="Project not found")
        return templates.TemplateResponse(request, "project_margins.html", {"d": data})

    @router.get("/projects/{project_id}/finance", response_class=HTMLResponse)
    def project_finance_show(
        project_id: str,
        request: Request,
        session: Session = Depends(db),
    ) -> HTMLResponse:
        _require_feature("finance_home")
        data = ui_views.project_finance_home(session, project_id)
        if data is None:
            raise HTTPException(status_code=404, detail="Project not found")
        return templates.TemplateResponse(request, "project_finance.html", {"d": data})

    @router.get("/projects/{project_id}/green-sheet", response_class=HTMLResponse)
    def project_green_sheet_show(
        project_id: str,
        request: Request,
        session: Session = Depends(db),
    ) -> HTMLResponse:
        _require_feature("green_sheet")
        data = ui_views.project_green_sheet(session, project_id)
        if data is None:
            raise HTTPException(status_code=404, detail="Project not found")
        return templates.TemplateResponse(request, "project_green_sheet.html", {"d": data})

    @router.get("/projects/{project_id}/ledger-health", response_class=HTMLResponse)
    def project_ledger_health_show(
        project_id: str,
        request: Request,
        session: Session = Depends(db),
    ) -> HTMLResponse:
        data = ui_views.project_ledger_health(session, project_id)
        if data is None:
            raise HTTPException(status_code=404, detail="Project not found")
        return templates.TemplateResponse(request, "project_ledger_health.html", {"d": data})

    @router.get("/projects/{project_id}/labour", response_class=HTMLResponse)
    def project_labour_show(
        project_id: str,
        request: Request,
        session: Session = Depends(db),
    ) -> HTMLResponse:
        _require_feature("labour_intake")
        data = ui_views.project_labour(session, project_id)
        if data is None:
            raise HTTPException(status_code=404, detail="Project not found")
        return templates.TemplateResponse(request, "project_labour.html", {"d": data})

    @router.get("/projects/{project_id}/gantt", response_class=HTMLResponse)
    def project_gantt_show(
        project_id: str,
        request: Request,
        session: Session = Depends(db),
    ) -> HTMLResponse:
        _require_feature("monday_gantt")
        data = ui_views.project_gantt(session, project_id)
        if data is None:
            raise HTTPException(status_code=404, detail="Project not found")
        return templates.TemplateResponse(request, "project_gantt.html", {"d": data})

    @router.post("/documents/{document_id}/financial-status", response_class=HTMLResponse)
    def set_financial_status(
        document_id: str,
        request: Request,
        confirmed: str = Form("true"),
        session: Session = Depends(db),
    ) -> HTMLResponse:
        _require_feature("finance_legacy")
        """Toggle a document's confirmed/quoted status; re-render the panel body.

        The only mutation on the financial surface.  It writes nothing external
        -- just our internal confirmation flag -- and is idempotent (setting
        confirmed=X yields X regardless of prior state), so no stale-state guard
        is needed.  Returns the financials body fragment for an HTMX swap so the
        Confirmed total recalculates live.
        """
        from project_db.ai.financials import set_document_financial_status
        from project_db.db.models import Document

        # Resolve the document FIRST -- a status row has a FK to document, so
        # writing it for a non-existent id would raise instead of 404.
        try:
            did = _uuid.UUID(document_id)
        except ValueError:
            raise HTTPException(status_code=404, detail="bad document id")
        doc = session.query(Document).filter_by(canonical_id=did).one_or_none()
        if doc is None or doc.project_id is None:
            raise HTTPException(status_code=404, detail="document/project not found")

        val = confirmed.strip().lower() in ("true", "1", "yes", "on")
        res = set_document_financial_status(
            session,
            document_id,
            val,
            decided_by="ui",
        )
        if not res.get("ok"):
            raise HTTPException(status_code=400, detail=res.get("error", "bad request"))
        data = ui_views.project_financials(session, str(doc.project_id))
        if data is None:
            raise HTTPException(status_code=404, detail="project not found")
        return templates.TemplateResponse(request, "_partials/financials_body.html", {"d": data})

    @router.post("/projects/{project_id}/field-note", response_class=HTMLResponse)
    def project_field_note_submit(
        project_id: str,
        request: Request,
        note_text: str = Form(""),
        session: Session = Depends(db),
    ) -> HTMLResponse:
        _require_feature("field_notes_typed")
        """Accept a plain-language field note, classify it, create PENDING proposals.

        Returns a small HTML fragment (HTMX swap target) reporting the outcome.
        The session is committed here -- the service function flushes but the
        route owns the transaction boundary.
        """
        ui_views.submit_field_note(session, project_id, note_text)
        session.commit()
        # Redirect back to the project proposals section so the PM sees the queue.
        from fastapi.responses import RedirectResponse

        return RedirectResponse(
            url=f"/projects/{project_id}#proposals",
            status_code=303,
        )

    @router.post(
        "/projects/{project_id}/proposals/dismiss-stale",
        response_class=HTMLResponse,
    )
    def dismiss_stale_proposals(
        project_id: str,
        request: Request,
        days_old: int = Form(30),
        session: Session = Depends(db),
    ) -> HTMLResponse:
        """Bulk-reject PENDING proposals older than days_old for this project.

        History is preserved (REJECTED rows stay); future proposals for the
        same targets are unaffected (supersession only looks at PENDING rows).
        """
        from fastapi.responses import RedirectResponse

        from project_db.ai.proposals import bulk_dismiss_stale

        bulk_dismiss_stale(session, project_id, days_old=days_old)
        session.commit()
        return RedirectResponse(
            url=f"/projects/{project_id}#proposals",
            status_code=303,
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
        return templates.TemplateResponse(request, "document_detail.html", {"d": data})
