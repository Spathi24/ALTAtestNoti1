"""AI assistant entry point.

v0.2: dispatches to canned reports (Tier 1 per STRATEGY.md).  Now supports
parameter extraction -- ``"overview of project 923 Rockland"`` resolves the
project ref and calls the report with it.

Mode 2 (text-to-SQL) is intentionally deferred per STRATEGY.md / ROADMAP.md
Phase 3 -- the strategic path is to build a structured Proposal-driven LLM
layer first, and only consider text-to-SQL once that proves valuable. The
stub remains so the dispatch shape doesn't change; do not extend it
without revisiting the strategy.

Mode 3 (RAG over DocumentText) is the actual next AI surface -- see
docs/ROADMAP.md Phase 3 for the prompts and table designs.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any

from sqlalchemy.orm import Session

from project_db.ai.providers import LLMMessage, LLMProvider, LLMProviderError
from project_db.ai.views import REPORT_REGISTRY


# Pulls a UUID (any 8-4-4-4-12 hex) from anywhere in the question.
_UUID_RE = re.compile(
    r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b",
    re.IGNORECASE,
)
# Pulls a project name after the literal "project" keyword.
# "overview of project 923 Rockland" -> "923 Rockland"
# Stops at trailing punctuation / question marks.
_PROJECT_NAME_RE = re.compile(
    r"\bproject\s+([^\?\.\,]+)",
    re.IGNORECASE,
)


# Surfaced by the dispatcher when a non-technical user types "help" / "?"
# or asks a meta question.  Order mirrors the routing precedence so the
# answer doubles as a debugging aid.
_HELP_PAYLOAD: dict[str, Any] = {
    "intro": (
        "I answer using canned reports.  Use one of the patterns below; "
        "<project> can be a name fragment ('Rockland') or a full UUID."
    ),
    "patterns": [
        {"say": "overview of project <project>", "report": "project_overview"},
        {"say": "docs for project <project>", "report": "docs_for_project"},
        {"say": "tasks without dates [for project <project>]", "report": "tasks_without_dates"},
        {"say": "which projects are missing documents", "report": "missing_documents"},
        {"say": "budget vs contract for project <project>", "report": "budget_vs_contract"},
        {"say": "active projects", "report": "active_projects"},
        {"say": "deal pipeline", "report": "deal_pipeline_value"},
        {"say": "ar aging / outstanding invoices", "report": "ar_aging"},
    ],
    "tip": "Type 'help' any time to see this list.",
}


def extract_project_ref(question: str) -> str | None:
    """Find a project reference -- UUID first, then text after 'project '."""
    if not question:
        return None
    m = _UUID_RE.search(question)
    if m:
        return m.group(0)
    m = _PROJECT_NAME_RE.search(question)
    if m:
        return m.group(1).strip()
    return None


@dataclass
class AiResponse:
    mode: str            # "canned" | "llm" | "sql" | "rag"
    answer: Any
    used_report: str | None = None


class AiAssistant:
    def __init__(self, session: Session):
        self.session = session

    def ask(self, question: str) -> AiResponse:
        # MODE 1 — canned report keyword matching. Crude but reliable.
        q = (question or "").lower().strip()
        ref = extract_project_ref(question)

        # Discoverability: a non-technical user has no way to know which
        # phrases work.  Catch the common "what can you do" formulations
        # and list every routed pattern so they can copy/paste.
        if q in {"help", "?", ""} or any(p in q for p in (
            "what can you do", "list reports", "what reports",
            "available reports", "available queries", "available commands",
        )):
            return AiResponse(
                mode="canned", used_report="help",
                answer=_HELP_PAYLOAD,
            )

        # Order matters: more specific patterns first so generic words don't
        # steal the match.
        if "budget" in q and ("contract" in q or "vs" in q):
            return self._dispatch_with_project("budget_vs_contract", ref)
        if "overview" in q or "snapshot" in q or "summary of project" in q:
            return self._dispatch_with_project("project_overview", ref)
        if ("docs" in q or "documents" in q or "files" in q) and ("missing" in q):
            return self._canned("missing_documents")
        if ("docs" in q or "documents" in q or "files" in q) and ref:
            return self._dispatch_with_project("docs_for_project", ref)
        if "tasks" in q and ("without date" in q or "no date" in q or "missing date" in q):
            return self._dispatch_with_project("tasks_without_dates", ref, allow_no_ref=True)
        if "active project" in q or "open project" in q:
            return self._canned("active_projects")
        if "pipeline" in q or "deal value" in q:
            return self._canned("deal_pipeline_value")
        if "ar aging" in q or "outstanding invoice" in q or "receivable" in q:
            return self._canned("ar_aging")

        # MODE 2 — text-to-SQL: still deferred.
        # MODE 3 — RAG over DocumentText: Phase 3.
        return AiResponse(
            mode="canned",
            used_report=None,
            answer="No canned report matched; text-to-SQL not implemented yet.",
        )

    def _canned(self, name: str) -> AiResponse:
        return AiResponse(
            mode="canned",
            used_report=name,
            answer=REPORT_REGISTRY[name](self.session),
        )

    def _dispatch_with_project(
        self, name: str, ref: str | None, *, allow_no_ref: bool = False,
    ) -> AiResponse:
        """Call a per-project report, surfacing a useful error when ref is missing."""
        if ref is None and not allow_no_ref:
            return AiResponse(
                mode="canned",
                used_report=name,
                answer={
                    "error": (
                        f"This report needs a project reference. "
                        f"Try: '{name.replace('_', ' ')} for project <name or UUID>'."
                    ),
                },
            )
        kwargs = {"project_ref": ref} if ref is not None else {}
        return AiResponse(
            mode="canned",
            used_report=name,
            answer=REPORT_REGISTRY[name](self.session, **kwargs),
        )

    def answer_with_llm(self, question: str, provider: LLMProvider) -> AiResponse:
        """Answer a free-form question with an LLM over the whole-DB snapshot.

        The escalation path when ``ask`` matches no canned report.  ``provider``
        should be a small/fast model (Haiku tier, via ``get_fast_provider``) --
        the work is reading and summarizing the canonical database, not the
        analytical reasoning reserved for proposal generation.  The model sees
        ONLY the structured snapshot and is told not to invent beyond it.
        """
        from project_db.ai.views import report_database_overview

        snapshot = report_database_overview(self.session)
        system = (
            "You are ALTA, the operations assistant for a construction "
            "company.  Answer the user's question using ONLY the JSON "
            "database snapshot provided -- it is the company's complete "
            "canonical operational record: projects, tasks, deals, leads, "
            "clients, invoices, and a document-category breakdown.\n\n"
            "Rules:\n"
            "- Use only facts present in the snapshot.  Never invent "
            "projects, tasks, numbers, or dates.\n"
            "- If the snapshot does not contain the answer, say so plainly.\n"
            "- The snapshot has no document/contract TEXT.  If the question "
            "needs contract content, say so and point to "
            "`project_db daily <project>`.\n"
            "- Be concise and specific: cite concrete names and numbers.\n"
            "- 'generated_on' is today's date; judge overdue / upcoming "
            "relative to it."
        )
        # Instruction at the TAIL: if the snapshot ever overflows the context
        # window, a front-loaded instruction is the first thing truncated.
        user = (
            f"DATABASE SNAPSHOT (JSON):\n{json.dumps(snapshot, default=str)}\n\n"
            "---\n\n"
            f"QUESTION: {question}\n\n"
            "Answer using only the snapshot above."
        )
        try:
            resp = provider.complete(
                messages=[LLMMessage(role="user", content=user)],
                system=system,
                max_tokens=1024,
            )
        except LLMProviderError as exc:
            return AiResponse(
                mode="llm", used_report=None, answer=f"LLM call failed: {exc}",
            )
        return AiResponse(
            mode="llm", used_report=None, answer=resp.content.strip(),
        )
