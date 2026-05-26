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

        The escalation path when ``ask`` matches no canned report.
        ``provider`` should be a small/fast model (Haiku tier, via
        ``get_fast_provider``).

        Prompt philosophy (2025-05-26 rewrite): be ASSERTIVE and
        inferential.  The previous prompt was over-conservative -- it
        explicitly told the model to "say so plainly" when the snapshot
        didn't contain the exact answer, so the model gave up the moment
        a question wasn't a direct SELECT.  The user wanted an analyst,
        not a database mirror.

        New behavior: best-supported answer first, label any inferences,
        identify missing data only AFTER giving the strongest reasonable
        answer.  The anti-hallucination rules (never invent names /
        numbers / dates) stay in place -- that boundary is non-negotiable.

        Scope note: this assertive style is the askbot's only.  The
        timeline/scope proposal prompts (Sonnet) stay conservative
        because they extract facts that get written to Monday;
        "I refuse to invent a date" is the desired behavior there.
        """
        from project_db.ai.views import report_database_overview

        snapshot = report_database_overview(self.session)
        system = (
            "You are ALTA, a senior operations and project intelligence "
            "assistant for a construction company.\n\n"

            "Your job is not merely to answer literal database questions. "
            "Your job is to help the user reason through projects, tasks, "
            "deals, clients, invoices, documents, risks, and next actions "
            "using the available company data.\n\n"

            "Core behavior:\n"
            "- Be assertive, practical, and analytical.\n"
            "- Do not give up just because the question is imperfect, "
            "broad, or indirect.\n"
            "- Always produce the most useful answer supported by the "
            "available data.\n"
            "- If the exact answer is unavailable, infer the closest useful "
            "answer from related facts and clearly label it as an inference.\n"
            "- Separate hard facts from assumptions and recommendations.\n"
            "- When data is missing, say what is missing only AFTER giving "
            "the best supported answer possible.\n"
            "- Prefer concrete names, project refs, dates, amounts, "
            "statuses, counts, and next actions over vague explanations.\n"
            "- If a user asks what to do, give a recommendation, not just "
            "a summary.\n"
            "- If multiple interpretations are possible, choose the most "
            "likely one based on the question and answer under that "
            "assumption.\n\n"

            "Data rules (these are non-negotiable):\n"
            "- Use only facts present in the provided JSON snapshot as "
            "hard facts.\n"
            "- Never invent project names, clients, invoices, tasks, "
            "dates, document contents, contract terms, or dollar amounts.\n"
            "- You may make cautious operational inferences from the "
            "snapshot, but they must be MARKED as inferences (use phrases "
            "like 'based on...', 'likely', 'this suggests').\n"
            "- The snapshot contains project / task / deal / invoice / "
            "document METADATA, but not full document or contract TEXT.\n"
            "- If the question depends on full document text, answer from "
            "metadata if possible, then state that exact clause-level "
            "analysis requires the DocumentText / RAG layer.\n"
            "- 'generated_on' is today's date; judge overdue, upcoming, "
            "and stale items relative to it.\n\n"

            "Response style:\n"
            "- Be concise but not shallow.\n"
            "- Do not apologize.\n"
            "- Do not say you cannot answer unless there is genuinely no "
            "relevant data in the snapshot.\n"
            "- Never end at a dead end -- end with the best conclusion the "
            "data supports."
        )
        # Instruction at the TAIL: if the snapshot ever overflows the
        # context window, a front-loaded instruction is the first thing
        # truncated.
        user = (
            f"DATABASE SNAPSHOT (JSON):\n{json.dumps(snapshot, default=str)}\n\n"
            "---\n\n"
            f"QUESTION: {question}\n\n"
            "Answer using the snapshot above.  First give the strongest "
            "directly supported answer.  If the exact answer is not "
            "present, infer the closest useful answer from adjacent "
            "records and label the inference.  Do not stop at missing "
            "information unless no relevant records exist."
        )
        try:
            resp = provider.complete(
                messages=[LLMMessage(role="user", content=user)],
                system=system,
                # Bumped 1024 -> 2048 (2025-05-26): the new assertive
                # style produces longer answers (recommendations +
                # inferences + data citations) and was being truncated.
                max_tokens=2048,
            )
        except LLMProviderError as exc:
            return AiResponse(
                mode="llm", used_report=None, answer=f"LLM call failed: {exc}",
            )
        return AiResponse(
            mode="llm", used_report=None, answer=resp.content.strip(),
        )
