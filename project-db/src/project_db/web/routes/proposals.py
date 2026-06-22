"""Proposal queue + detail + decision actions.

Phase D adds the three mutation endpoints.  Each is a *thin* adapter over
the existing ``ai.proposals.accept_proposal`` / ``reject_proposal`` -- no
UI-specific proposal transformations, no silent error swallowing.

Stale-state handling (per the M5 plan review #5): every POST re-reads
the proposal *before* delegating.  If it's no longer PENDING, the route
returns the ``decision_stale`` fragment instead of attempting a mutation.
This is a first-class UI case, not a 4xx.

Accept renders ``decision_decided`` (green/grey, with a real decided_at).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Form, HTTPException, Query, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from project_db.ai.proposals import (
    accept_proposal,
    generate_scope_proposals,
    generate_timeline_proposals,
    reject_proposal,
)
from project_db.db.models import Project, Proposal
from project_db.db.models.proposals import ProposalStatus
from project_db.features import feature_enabled
from project_db.web import deps, ui_views
from project_db.web.deps import db


def _coerce_uuid(value: str):
    """Local UUID coercer that returns None on garbage (vs raising)."""
    import uuid

    try:
        return uuid.UUID(str(value))
    except (ValueError, TypeError, AttributeError):
        return None


def _require_feature(name: str) -> None:
    if not feature_enabled(name):
        raise HTTPException(404, "Feature disabled")


def _fresh_pending_proposal(session: Session, proposal_id: str) -> Proposal | None:
    """Re-read the proposal RIGHT BEFORE mutation.

    Returns the Proposal row only if it is currently PENDING.  Any other
    state (including not-found / bad-uuid) -> None, and the caller emits
    the stale fragment (or a 404 for genuine not-found).

    This is the load-bearing line for review #5: two browsers / a CLI
    decision between page load and click must not produce a double-write.
    """
    pid = _coerce_uuid(proposal_id)
    if pid is None:
        return None
    p = session.query(Proposal).filter_by(canonical_id=pid).one_or_none()
    if p is None:
        return None
    if p.status != ProposalStatus.PENDING:
        return None
    return p


def _render_idle(
    templates: Jinja2Templates,
    request: Request,
    proposal: Proposal,
    error: str | None = None,
) -> HTMLResponse:
    """Render the decision_idle partial for a PENDING proposal."""
    from project_db.ai.proposals import _ACCEPTABLE_FIELDS

    return templates.TemplateResponse(
        request,
        "_partials/decision_idle.html",
        {
            "proposal_id": str(proposal.canonical_id),
            "field_name": proposal.field_name,
            "can_accept": proposal.field_name in _ACCEPTABLE_FIELDS,
            "error": error,
        },
    )


def _render_stale(
    templates: Jinja2Templates,
    request: Request,
    proposal: Proposal,
    attempted: str,
) -> HTMLResponse:
    """Render the decision_stale fragment when a POST hits non-PENDING."""
    current = proposal.status.value if hasattr(proposal.status, "value") else str(proposal.status)
    return templates.TemplateResponse(
        request,
        "_partials/decision_stale.html",
        {
            "proposal_id": str(proposal.canonical_id),
            "current_status": current,
            "attempted": attempted,
        },
    )


def _render_decided(
    templates: Jinja2Templates,
    request: Request,
    proposal: Proposal,
    *,
    wrote_to_monday: dict | None = None,
    task_title: str | None = None,
) -> HTMLResponse:
    """Render the decision_decided fragment after a successful mutation."""
    status = proposal.status.value if hasattr(proposal.status, "value") else str(proposal.status)
    return templates.TemplateResponse(
        request,
        "_partials/decision_decided.html",
        {
            "status": status,
            "decided_at": proposal.decided_at.isoformat() if proposal.decided_at else None,
            "decided_by": proposal.decided_by,
            "rejection_reason": proposal.rejection_reason,
            "wrote_to_monday": wrote_to_monday,
            "task_title": task_title,
        },
    )


def _resolve_project_uuid(session: Session, project_id: str) -> Project | None:
    pid = _coerce_uuid(project_id)
    if pid is None:
        return None
    return session.query(Project).filter_by(canonical_id=pid).one_or_none()


def _render_propose_result(
    templates: Jinja2Templates,
    request: Request,
    *,
    project_id: str,
    kind: str,
    batch: object | None,
    error: str | None = None,
) -> HTMLResponse:
    return templates.TemplateResponse(
        request,
        "_partials/propose_result.html",
        {
            "project_id": project_id,
            "kind": kind,
            "batch": batch,
            "error": error,
        },
    )


def register(router: APIRouter, templates: Jinja2Templates) -> None:
    # ---------------------------------------------------------------- list
    @router.get("/proposals", response_class=HTMLResponse)
    def proposals_index(
        request: Request,
        status: str | None = Query(default=None),
        kind: str | None = Query(default=None),
        session: Session = Depends(db),
    ) -> HTMLResponse:
        _require_feature("proposals")
        data = ui_views.proposal_queue(session, status=status, kind=kind)
        return templates.TemplateResponse(request, "proposal_list.html", {"d": data})

    # ---------------------------------------------------------------- detail
    @router.get("/proposals/{proposal_id}", response_class=HTMLResponse)
    def proposal_show(
        proposal_id: str,
        request: Request,
        session: Session = Depends(db),
    ) -> HTMLResponse:
        _require_feature("proposals")
        detail = ui_views.proposal_detail(session, proposal_id)
        if detail is None:
            raise HTTPException(status_code=404, detail="Proposal not found")
        return templates.TemplateResponse(request, "proposal_detail.html", {"p": detail})

    # ---------------------------------------------------------------- GET decision (cancel + refresh)
    @router.get("/proposals/{proposal_id}/decision", response_class=HTMLResponse)
    def proposal_decision_idle(
        proposal_id: str,
        request: Request,
        session: Session = Depends(db),
    ) -> HTMLResponse:
        _require_feature("proposals")
        """Re-render the idle decision panel (GET /decision).

        If the proposal has already been decided, returns the decided partial
        so the page reflects current state."""
        pid = _coerce_uuid(proposal_id)
        if pid is None:
            raise HTTPException(404, "Proposal not found")
        p = session.query(Proposal).filter_by(canonical_id=pid).one_or_none()
        if p is None:
            raise HTTPException(404, "Proposal not found")
        if p.status != ProposalStatus.PENDING:
            return _render_decided(templates, request, p)
        return _render_idle(templates, request, p)

    # ---------------------------------------------------------------- POST accept
    @router.post("/proposals/{proposal_id}/accept", response_class=HTMLResponse)
    def proposal_accept(
        proposal_id: str,
        request: Request,
        session: Session = Depends(db),
    ) -> HTMLResponse:
        _require_feature("proposals")
        """Write the change to Monday, then flip the proposal to ACCEPTED.

        ORDER IS LOAD-BEARING (mirrors ai.proposals.accept_proposal):
        Monday write FIRST, status flip second.  A failed write leaves the
        proposal PENDING and we return the idle fragment with the error.
        """
        p = _fresh_pending_proposal(session, proposal_id)
        if p is None:
            pid = _coerce_uuid(proposal_id)
            existing = (
                session.query(Proposal).filter_by(canonical_id=pid).one_or_none() if pid else None
            )
            if existing is None:
                raise HTTPException(404, "Proposal not found")
            return _render_stale(templates, request, existing, attempted="accept")

        # Build the Monday connector at request time.  Tests monkeypatch
        # deps.build_monday_writeback to inject a fake.
        try:
            writeback = deps.build_monday_writeback(session)
        except Exception as exc:
            return _render_idle(
                templates,
                request,
                p,
                error=f"could not build Monday connector: {exc}",
            )

        decided_by = "ui:" + (request.client.host if request.client else "local")
        result = accept_proposal(
            session,
            proposal_id,
            writeback=writeback,
            dry_run=False,
            decided_by=decided_by,
        )
        if not result.get("ok"):
            # accept_proposal already guarantees nothing was committed on
            # failure.  Surface the error inline; proposal stays PENDING.
            return _render_idle(templates, request, p, error=result.get("error"))

        # Re-read to get the freshly-flipped status, decided_at, etc.
        session.refresh(p)
        return _render_decided(
            templates,
            request,
            p,
            wrote_to_monday=result.get("wrote_to_monday"),
            task_title=result.get("task_title"),
        )

    # ---------------------------------------------------------------- POST reject
    @router.post("/proposals/{proposal_id}/reject", response_class=HTMLResponse)
    def proposal_reject(
        proposal_id: str,
        request: Request,
        reason: str = Form(default=""),
        session: Session = Depends(db),
    ) -> HTMLResponse:
        _require_feature("proposals")
        """Flip status to REJECTED.  Pure DB; no external system touched."""
        p = _fresh_pending_proposal(session, proposal_id)
        if p is None:
            pid = _coerce_uuid(proposal_id)
            existing = (
                session.query(Proposal).filter_by(canonical_id=pid).one_or_none() if pid else None
            )
            if existing is None:
                raise HTTPException(404, "Proposal not found")
            return _render_stale(templates, request, existing, attempted="reject")

        decided_by = "ui:" + (request.client.host if request.client else "local")
        result = reject_proposal(
            session,
            proposal_id,
            reason=(reason or None),
            decided_by=decided_by,
        )
        if not result.get("ok"):
            return _render_idle(templates, request, p, error=result.get("error"))

        session.refresh(p)
        return _render_decided(templates, request, p)

    # ---------------------------------------------------------------- POST propose timelines
    @router.post(
        "/projects/{project_id}/propose/timelines",
        response_class=HTMLResponse,
    )
    def propose_timelines(
        project_id: str,
        request: Request,
        session: Session = Depends(db),
    ) -> HTMLResponse:
        _require_feature("proposal_generation")
        """Generate timeline proposals (spends LLM tokens).

        Thin adapter over ``generate_timeline_proposals``.  Uses the
        deep provider (Sonnet via ``get_default_provider``).  The button
        in the UI carries hx-confirm; this route assumes the user has
        already confirmed.
        """
        project = _resolve_project_uuid(session, project_id)
        if project is None:
            raise HTTPException(404, "Project not found")

        try:
            from project_db.ai.providers import get_default_provider

            provider = get_default_provider()
        except Exception as exc:
            return _render_propose_result(
                templates,
                request,
                project_id=project_id,
                kind="timeline",
                batch=None,
                error=f"could not build LLM provider: {exc}",
            )

        try:
            from project_db.ai.embeddings import get_optional_embedding_provider

            embed_provider = get_optional_embedding_provider()
        except Exception:
            embed_provider = None
        try:
            batch = generate_timeline_proposals(
                session,
                provider,
                project.canonical_id,
                embedding_provider=embed_provider,
            )
        except Exception as exc:
            return _render_propose_result(
                templates,
                request,
                project_id=project_id,
                kind="timeline",
                batch=None,
                error=f"proposal generation failed: {exc}",
            )

        return _render_propose_result(
            templates,
            request,
            project_id=project_id,
            kind="timeline",
            batch=batch,
        )

    # ---------------------------------------------------------------- POST propose scope
    @router.post(
        "/projects/{project_id}/propose/scope",
        response_class=HTMLResponse,
    )
    def propose_scope(
        project_id: str,
        request: Request,
        session: Session = Depends(db),
    ) -> HTMLResponse:
        _require_feature("proposal_generation")
        """Generate scope-gap proposals (spends LLM tokens).  Same shape
        as the timelines route -- thin adapter; hx-confirm in the template."""
        project = _resolve_project_uuid(session, project_id)
        if project is None:
            raise HTTPException(404, "Project not found")

        try:
            from project_db.ai.providers import get_default_provider

            provider = get_default_provider()
        except Exception as exc:
            return _render_propose_result(
                templates,
                request,
                project_id=project_id,
                kind="scope",
                batch=None,
                error=f"could not build LLM provider: {exc}",
            )

        try:
            from project_db.ai.embeddings import get_optional_embedding_provider

            embed_provider = get_optional_embedding_provider()
        except Exception:
            embed_provider = None
        try:
            batch = generate_scope_proposals(
                session,
                provider,
                project.canonical_id,
                embedding_provider=embed_provider,
            )
        except Exception as exc:
            return _render_propose_result(
                templates,
                request,
                project_id=project_id,
                kind="scope",
                batch=None,
                error=f"proposal generation failed: {exc}",
            )

        return _render_propose_result(
            templates,
            request,
            project_id=project_id,
            kind="scope",
            batch=batch,
        )
