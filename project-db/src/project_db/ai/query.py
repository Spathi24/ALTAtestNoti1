"""AI assistant entry point.

v0.1: just dispatches to the canned reports. Modes 2 (text-to-SQL) and 3 (RAG)
are stubbed and clearly marked TODO.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sqlalchemy.orm import Session

from project_db.ai.views import REPORT_REGISTRY


@dataclass
class AiResponse:
    mode: str            # "canned" | "sql" | "rag"
    answer: Any
    used_report: str | None = None


class AiAssistant:
    def __init__(self, session: Session):
        self.session = session

    def ask(self, question: str) -> AiResponse:
        # MODE 1 — canned report keyword matching. Crude but reliable.
        q = question.lower()
        if "active project" in q or "open project" in q:
            return AiResponse(
                mode="canned",
                used_report="active_projects",
                answer=REPORT_REGISTRY["active_projects"](self.session),
            )
        if "pipeline" in q or "deal value" in q:
            return AiResponse(
                mode="canned",
                used_report="deal_pipeline_value",
                answer=REPORT_REGISTRY["deal_pipeline_value"](self.session),
            )
        if "ar aging" in q or "outstanding invoice" in q or "receivable" in q:
            return AiResponse(
                mode="canned",
                used_report="ar_aging",
                answer=REPORT_REGISTRY["ar_aging"](self.session),
            )

        # MODE 2 — text-to-SQL. TODO: wire to an LLM (Anthropic API)
        # that's been given the schema and produces parameterized SQL.
        # MODE 3 — RAG over daily logs / docs via pgvector embeddings.

        return AiResponse(
            mode="canned",
            used_report=None,
            answer="No canned report matched; text-to-SQL not implemented yet.",
        )
