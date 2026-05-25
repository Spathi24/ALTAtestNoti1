"""/ask -- natural-language Q&A over the canonical DB.

Wraps the existing AiAssistant + answer_with_llm.  Canned reports answer
instantly when a keyword matches; only the no-match fallthrough calls the
fast model (Haiku).  This is the same dispatch the CLI's
``project_db ask "..."`` uses, so UI and CLI cannot drift.
"""
from __future__ import annotations

import json
from typing import Optional

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from project_db.ai.query import AiAssistant, AiResponse
from project_db.web.deps import db


def _format_answer(answer) -> tuple[str, str]:
    """Return (pretty_json_or_text, mode_for_display).

    Canned reports return dicts / lists -- pretty-print as JSON so the
    page is honest about what came back.  LLM answers are already plain
    text -- preserve them as-is.
    """
    if isinstance(answer, (dict, list)):
        return json.dumps(answer, indent=2, default=str), "json"
    return str(answer), "text"


def register(router: APIRouter, templates: Jinja2Templates) -> None:
    @router.get("/ask", response_class=HTMLResponse)
    def ask_index(request: Request) -> HTMLResponse:
        return templates.TemplateResponse(
            request,
            "ask.html",
            {"result": None, "question": "", "format": None, "mode": None,
             "report": None},
        )

    @router.post("/ask", response_class=HTMLResponse)
    def ask_submit(
        request: Request,
        question: str = Form(default=""),
        session: Session = Depends(db),
    ) -> HTMLResponse:
        question = (question or "").strip()
        if not question:
            return templates.TemplateResponse(
                request,
                "ask.html",
                {
                    "result": "Type a question above.",
                    "question": "",
                    "format": "text",
                    "mode": None,
                    "report": None,
                },
            )

        assistant = AiAssistant(session)
        canned: AiResponse = assistant.ask(question)

        # ``ask`` returns a placeholder canned response when no keyword
        # matches ("No canned report matched...").  That is the signal to
        # escalate to the fast (Haiku) LLM, mirroring the CLI.
        no_match = (
            canned.mode == "canned"
            and canned.used_report is None
            and isinstance(canned.answer, str)
            and "No canned report matched" in canned.answer
        )
        if not no_match:
            text, fmt = _format_answer(canned.answer)
            return templates.TemplateResponse(
                request,
                "ask.html",
                {
                    "result": text,
                    "question": question,
                    "format": fmt,
                    "mode": canned.mode,
                    "report": canned.used_report,
                },
            )

        try:
            from project_db.ai.providers import get_fast_provider
            provider = get_fast_provider()
        except Exception as exc:  # noqa: BLE001
            return templates.TemplateResponse(
                request,
                "ask.html",
                {
                    "result": (
                        f"No canned report matched, and the fast LLM provider "
                        f"could not be built ({exc}).  Try a more specific "
                        f"question, or run `project_db ask 'help'` for "
                        f"discoverable patterns."
                    ),
                    "question": question,
                    "format": "text",
                    "mode": "error",
                    "report": None,
                },
            )

        llm_resp = assistant.answer_with_llm(question, provider)
        text, fmt = _format_answer(llm_resp.answer)
        return templates.TemplateResponse(
            request,
            "ask.html",
            {
                "result": text,
                "question": question,
                "format": fmt,
                "mode": llm_resp.mode,
                "report": llm_resp.used_report,
            },
        )
