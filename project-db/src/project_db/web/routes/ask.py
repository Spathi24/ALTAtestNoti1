"""/ask -- natural-language Q&A over the canonical DB.

Wraps the existing AiAssistant + answer_with_llm.  Canned reports answer
instantly when a keyword matches; only the no-match fallthrough calls the
fast model (Haiku).  This is the same dispatch the CLI's
``project_db ask "..."`` uses, so UI and CLI cannot drift.
"""

from __future__ import annotations

import json

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from project_db.ai.query import AiAssistant, AiResponse
from project_db.web.deps import db


def _render_markdown(text: str) -> str:
    """Render LLM-style markdown to HTML.

    Haiku's answers come back with `**bold**`, `*italic*`, bullet lists,
    line breaks, headings, fenced code, etc.  Rendering them as plain
    text drops all of that on the floor (the user noticed -- 2025-05-26).

    Safety: the `markdown` library passes raw HTML through by design,
    so we ESCAPE the input first.  That turns any embedded ``<script>``
    into inert ``&lt;script&gt;`` text BEFORE markdown sees it, while
    leaving markdown's own ``**`` / ``#`` / ``-`` syntax untouched
    (the escape only touches angle brackets / ampersands / quotes).
    Localhost-only single-user, but defence-in-depth is cheap here.
    """
    from html import escape as _escape

    try:
        import markdown as _markdown
    except ImportError:
        # If the [ui] extra isn't installed, fall back to a tiny
        # whitespace-preserving wrapper.  No prettification, but at
        # least line breaks survive.
        return f"<pre style='white-space: pre-wrap'>{_escape(text)}</pre>"

    # Pre-escape, then render markdown.  Order matters: escape first
    # so `<script>` becomes inert; THEN markdown converts `**bold**`
    # without touching the escaped entities.
    safe = _escape(text, quote=False)
    return _markdown.markdown(
        safe,
        extensions=["sane_lists", "nl2br", "fenced_code"],
        output_format="html5",
    )


def _format_answer(answer) -> tuple[str, str]:
    """Return (rendered_html_or_json, format_for_display).

    Canned reports return dicts / lists -- pretty-print as JSON inside
    a <pre> so the page is honest about what came back.  LLM answers
    are markdown -- render to HTML so `**bold**`, bullets, and line
    breaks survive.
    """
    if isinstance(answer, (dict, list)):
        return json.dumps(answer, indent=2, default=str), "json"
    return _render_markdown(str(answer)), "html"


def register(router: APIRouter, templates: Jinja2Templates) -> None:
    @router.get("/ask", response_class=HTMLResponse)
    def ask_index(request: Request) -> HTMLResponse:
        return templates.TemplateResponse(
            request,
            "ask.html",
            {"result": None, "question": "", "format": None, "mode": None, "report": None},
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
        except Exception as exc:
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

        # RAG: supply relevant document excerpts when embeddings are available.
        try:
            from project_db.ai.embeddings import get_optional_embedding_provider

            embed_provider = get_optional_embedding_provider()
        except Exception:
            embed_provider = None

        llm_resp = assistant.answer_with_llm(
            question,
            provider,
            embedding_provider=embed_provider,
            public_identity=(
                "In the Ask tab UI, your public name is Pini. "
                "If asked who you are, say you are Pini. "
                "Do not mention ALTA as your name. "
                "This is only a presentation identity; do not change project names, "
                "database names, report names, fields, modes, or stored data."
            ),
        )
        text, fmt = _format_answer(llm_resp.answer)
        # De-duplicate cited documents for the "answered using" badge.
        sources = []
        seen = set()
        for s in llm_resp.sources or []:
            name = s.get("document_name") or "(unknown)"
            if name not in seen:
                seen.add(name)
                sources.append(s)
        return templates.TemplateResponse(
            request,
            "ask.html",
            {
                "result": text,
                "question": question,
                "format": fmt,
                "mode": llm_resp.mode,
                "report": llm_resp.used_report,
                "sources": sources,
            },
        )
