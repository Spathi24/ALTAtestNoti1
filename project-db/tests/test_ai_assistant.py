"""Tests for the AI assistant + canned reports."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from sqlalchemy.orm import Session

from project_db.ai import REPORT_REGISTRY, AiAssistant
from project_db.ai.providers import LLMProvider, LLMProviderError, MockLLMProvider
from project_db.ai.views import (
    report_active_projects,
    report_ar_aging,
    report_database_overview,
    report_deal_pipeline_value,
    report_entity_external_ids,
)
from project_db.db.models import (
    ExternalId,
    SourceSystem,
)
from project_db.db.models.crm import LeadStage
from project_db.db.models.finance import InvoiceStatus
from project_db.db.models.work import ProjectStatus


class TestAiAssistantBasics:
    def test_assistant_initialization(self, session: Session):
        assistant = AiAssistant(session)
        assert assistant is not None

    def test_report_registry_exposes_expected_reports(self):
        assert "active_projects" in REPORT_REGISTRY
        assert "deal_pipeline_value" in REPORT_REGISTRY
        assert "ar_aging" in REPORT_REGISTRY


class TestAiCannedReports:
    def test_active_projects_report(self, session: Session, project_factory):
        project_factory(name="Active One", status=ProjectStatus.ACTIVE)
        project_factory(name="Done One", status=ProjectStatus.COMPLETED)

        rows = report_active_projects(session)
        names = [r["name"] for r in rows]
        assert "Active One" in names
        assert "Done One" not in names

    def test_deal_pipeline_value_report(self, session: Session, deal_factory):
        deal_factory(name="D1", stage=LeadStage.NEGOTIATION, value=Decimal("25000"))
        deal_factory(name="D2", stage=LeadStage.PROPOSAL, value=Decimal("15000"))
        deal_factory(name="D3", stage=LeadStage.WON, value=Decimal("99999"))  # excluded

        rows = report_deal_pipeline_value(session)
        stages = {r["stage"] for r in rows}
        assert "NEGOTIATION" in stages
        assert "PROPOSAL" in stages
        assert "WON" not in stages  # report filters out WON / LOST

    def test_ar_aging_report(self, session: Session, invoice_factory):
        invoice_factory(number="A", status=InvoiceStatus.SENT, amount=Decimal("500"))
        invoice_factory(number="B", status=InvoiceStatus.OVERDUE, amount=Decimal("750"))
        invoice_factory(number="C", status=InvoiceStatus.PAID, amount=Decimal("9999"))  # excluded

        rows = report_ar_aging(session)
        statuses = {r["status"] for r in rows}
        assert "SENT" in statuses
        assert "OVERDUE" in statuses
        assert "PAID" not in statuses

    def test_entity_external_ids_report(self, session: Session, client_factory):
        client = client_factory(name="Acme")
        session.add(
            ExternalId(
                source=SourceSystem.MONDAY,
                entity_type="Client",
                external_key="monday_123",
                canonical_id=client.canonical_id,
            )
        )
        session.commit()

        rows = report_entity_external_ids(session, "Client", client.canonical_id)
        assert len(rows) == 1
        assert rows[0]["source"] == "MONDAY"
        assert rows[0]["external_key"] == "monday_123"


class TestAiAssistantAsk:
    def test_ask_dispatches_to_active_projects(self, session: Session, project_factory):
        project_factory(name="Sample", status=ProjectStatus.ACTIVE)

        assistant = AiAssistant(session)
        resp = assistant.ask("what active projects do we have?")

        assert resp.mode == "canned"
        assert resp.used_report == "active_projects"
        assert any(r["name"] == "Sample" for r in resp.answer)

    def test_ask_dispatches_to_pipeline(self, session: Session, deal_factory):
        deal_factory(name="D1", stage=LeadStage.NEGOTIATION, value=Decimal("1000"))

        assistant = AiAssistant(session)
        resp = assistant.ask("show me the pipeline")

        assert resp.used_report == "deal_pipeline_value"

    def test_ask_dispatches_to_ar_aging(self, session: Session, invoice_factory):
        invoice_factory(number="X", status=InvoiceStatus.OVERDUE)

        assistant = AiAssistant(session)
        resp = assistant.ask("show me outstanding invoices")

        assert resp.used_report == "ar_aging"

    def test_ask_falls_through_when_no_keyword_matches(self, session: Session):
        assistant = AiAssistant(session)
        resp = assistant.ask("what is the meaning of life")

        assert resp.used_report is None
        # Body explains text-to-SQL not wired yet.
        assert "not implemented" in resp.answer.lower()


class TestAiReportIntegration:
    def test_reports_accessible_from_populated_db(self, session: Session, populated_db):
        # populated_db creates ACTIVE projects by default
        rows = report_active_projects(session)
        assert len(rows) > 0
        assert all("name" in r for r in rows)


# ---------------------------------------------------------------------------
# Database overview snapshot -- the context for the LLM `ask` fallback
# ---------------------------------------------------------------------------


class TestDatabaseOverview:
    def test_overview_shape_and_totals(self, session: Session, populated_db):
        ov = report_database_overview(session)
        for key in (
            "generated_on",
            "totals",
            "projects",
            "tasks",
            "deals",
            "leads",
            "clients",
            "invoices",
            "documents_by_category",
        ):
            assert key in ov, f"missing section: {key}"
        assert ov["totals"]["projects"] == 2
        assert ov["totals"]["invoices"] == 2
        names = {p["name"] for p in ov["projects"]}
        assert "Website Redesign" in names
        assert "Mobile App" in names

    def test_overview_is_json_serializable(self, session: Session, populated_db):
        import json

        json.dumps(report_database_overview(session))  # must not raise

    def test_overview_rolls_up_project_counts(
        self, session: Session, client_factory, project_factory, task_factory
    ):
        p = project_factory(name="Counted Job", client=client_factory(name="CC"))
        task_factory(title="dated", project=p, start_date=date(2026, 6, 1))
        task_factory(title="dateless", project=p)

        ov = report_database_overview(session)
        row = next(r for r in ov["projects"] if r["name"] == "Counted Job")
        assert row["task_count"] == 2
        assert row["tasks_without_dates"] == 1

    def test_overview_empty_db(self, session: Session):
        ov = report_database_overview(session)
        assert ov["totals"]["projects"] == 0
        assert ov["projects"] == []
        assert ov["tasks"] == []


# ---------------------------------------------------------------------------
# LLM `ask` fallback -- answer_with_llm (no canned report matched)
# ---------------------------------------------------------------------------


class TestAnswerWithLlm:
    def test_returns_llm_mode_with_provider_text(self, session: Session, populated_db):
        provider = MockLLMProvider(responses=["We have 2 active projects."])
        resp = AiAssistant(session).answer_with_llm("how many projects?", provider)
        assert resp.mode == "llm"
        assert resp.used_report is None
        assert resp.answer == "We have 2 active projects."

    def test_feeds_db_snapshot_and_question_to_provider(self, session: Session, populated_db):
        provider = MockLLMProvider(responses=["ok"])
        AiAssistant(session).answer_with_llm("what is going on here", provider)
        assert len(provider.calls) == 1
        sent = provider.calls[0]["messages"][0].content
        assert "DATABASE SNAPSHOT" in sent
        assert "what is going on here" in sent
        # Real canonical data reached the prompt.
        assert "Website Redesign" in sent

    def test_provider_error_is_handled_gracefully(self, session: Session):
        class _Boom(LLMProvider):
            name = "boom"

            def complete(self, **kwargs):
                raise LLMProviderError("kaboom")

        resp = AiAssistant(session).answer_with_llm("q", _Boom())
        assert resp.mode == "llm"
        assert "kaboom" in resp.answer
