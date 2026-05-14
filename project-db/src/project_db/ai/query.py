"""AI assistant entry point.

v0.1: dispatches to the canned reports (Tier 1 per STRATEGY.md).

Mode 2 (text-to-SQL) is intentionally deferred per STRATEGY.md / ROADMAP.md
Phase 3 -- the strategic path is to build a structured Proposal-driven LLM
layer first, and only consider text-to-SQL once that proves valuable. The
stub remains so the dispatch shape doesn't change; do not extend it
without revisiting the strategy.

Mode 3 (RAG over DocumentText) is the actual next AI surface -- see
docs/ROADMAP.md Phase 3 for the prompts and table designs.
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
