"""Task date edit routes -- manual write-back to Monday.

Thin adapter over ``ai.proposals.set_task_timeline``.  Same write-first /
mirror-second ordering accept_proposal uses, but no Proposal row is
created (manual edits are deliberate human actions, not AI suggestions).

POST /tasks/{id}/set-dates  -- write dates, render the updated row
GET  /tasks/{id}/dates-form -- render the inline edit form
GET  /tasks/{id}/row        -- render the static row (Cancel target)
"""
from __future__ import annotations

import uuid as _uuid

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from project_db.ai.proposals import set_task_timeline
from project_db.db.models import Task
from project_db.web import deps
from project_db.web.deps import db


def _coerce_uuid(value: str):
    try:
        return _uuid.UUID(str(value))
    except (ValueError, TypeError, AttributeError):
        return None


def _task_row_payload(task: Task) -> dict:
    """Shape the row template renders for both static and post-save."""
    return {
        "canonical_id": str(task.canonical_id),
        "title": task.title,
        "status": task.status.value if hasattr(task.status, "value") else str(task.status),
        "monday_status_label": task.monday_status_label,
        "start_date": task.start_date.isoformat() if task.start_date else None,
        "end_date": task.end_date.isoformat() if task.end_date else None,
        "due_date": task.due_date.isoformat() if task.due_date else None,
        "is_subitem": bool(task.is_subitem),
    }


def register(router: APIRouter, templates: Jinja2Templates) -> None:
    @router.get("/tasks/{task_id}/dates-form", response_class=HTMLResponse)
    def dates_form(
        task_id: str,
        request: Request,
        session: Session = Depends(db),
    ) -> HTMLResponse:
        """Render the inline edit form for one task row."""
        tid = _coerce_uuid(task_id)
        if tid is None:
            raise HTTPException(404, "Task not found")
        task = session.query(Task).filter_by(canonical_id=tid).one_or_none()
        if task is None:
            raise HTTPException(404, "Task not found")
        return templates.TemplateResponse(
            request,
            "_partials/task_dates_form.html",
            {"task": _task_row_payload(task), "error": None},
        )

    @router.get("/tasks/{task_id}/row", response_class=HTMLResponse)
    def task_row(
        task_id: str,
        request: Request,
        session: Session = Depends(db),
    ) -> HTMLResponse:
        """Render the static row.  Used by the form's Cancel button."""
        tid = _coerce_uuid(task_id)
        if tid is None:
            raise HTTPException(404, "Task not found")
        task = session.query(Task).filter_by(canonical_id=tid).one_or_none()
        if task is None:
            raise HTTPException(404, "Task not found")
        return templates.TemplateResponse(
            request,
            "_partials/task_dates_row.html",
            {"t": _task_row_payload(task)},
        )

    @router.post("/tasks/{task_id}/set-dates", response_class=HTMLResponse)
    def set_dates(
        task_id: str,
        request: Request,
        start_date: str = Form(default=""),
        end_date: str = Form(default=""),
        session: Session = Depends(db),
    ) -> HTMLResponse:
        """Write dates to Monday + mirror onto the canonical Task.

        On any failure (validation, connector unavailable, Monday refused),
        the row stays as-is and the form re-renders with an inline error.
        """
        tid = _coerce_uuid(task_id)
        if tid is None:
            raise HTTPException(404, "Task not found")
        task = session.query(Task).filter_by(canonical_id=tid).one_or_none()
        if task is None:
            raise HTTPException(404, "Task not found")

        try:
            writeback = deps.build_monday_writeback(session)
        except Exception as exc:  # noqa: BLE001
            return templates.TemplateResponse(
                request,
                "_partials/task_dates_form.html",
                {
                    "task": _task_row_payload(task),
                    "error": f"could not build Monday connector: {exc}",
                },
            )

        decided_by = "ui:" + (request.client.host if request.client else "local")
        result = set_task_timeline(
            session, str(tid),
            start_date=start_date or None,
            end_date=end_date or None,
            writeback=writeback,
            decided_by=decided_by,
        )
        if not result.get("ok"):
            # Re-render the form with the error, original values preserved.
            return templates.TemplateResponse(
                request,
                "_partials/task_dates_form.html",
                {
                    "task": _task_row_payload(task),
                    "error": result.get("error"),
                },
            )

        session.refresh(task)
        return templates.TemplateResponse(
            request,
            "_partials/task_dates_row.html",
            {"t": _task_row_payload(task), "just_saved": True},
        )
