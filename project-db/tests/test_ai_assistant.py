"""Tests for the AI assistant + canned reports."""
from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy.orm import Session

from project_db.ai import AiAssistant, REPORT_REGISTRY
from project_db.ai.views import (
    report_active_projects,
    report_ar_aging,
    report_deal_pipeline_value,
    report_entity_external_ids,
)
from project_db.db.models import (
    Client,
    Deal,
    ExternalId,
    Invoice,
    Project,
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
