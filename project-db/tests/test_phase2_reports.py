"""Tests for Phase-2 Tier-1 reports + ask dispatcher.

These reports are the "boring reliable layer" per STRATEGY.md.  They are
deterministic SQL queries the LLM in Phase 3 will be allowed to call as
tools.  No LLM here.

Coverage:
  - Each of the 5 new reports against fixture data
  - Project-ref extraction from natural-language questions
  - Dispatcher routes the right report and surfaces missing-ref errors
  - "Pure function" contract: no side effects, JSON-serializable
"""
from __future__ import annotations

import json
import uuid
from datetime import date, datetime
from decimal import Decimal

import pytest

from project_db.ai import extract_project_ref
from project_db.ai.query import AiAssistant
from project_db.ai.views import (
    report_budget_vs_contract,
    report_docs_for_project,
    report_missing_documents,
    report_project_overview,
    report_tasks_without_dates,
    _extract_money_amounts,
    _resolve_project,
)
from project_db.db.models import (
    Client,
    DailyLog,
    Document,
    DocumentText,
    Invoice,
    InvoiceStatus,
    Project,
    Task,
    TaskStatus,
)
from project_db.db.models.work import ProjectStatus


# ---------------------------------------------------------------------------
# Fixture: a richly-populated project for the overview / docs / budget tests
# ---------------------------------------------------------------------------


@pytest.fixture
def rich_project(session, client_factory):
    """Build one project with tasks, docs, invoices, daily logs."""
    c = client_factory(name="Acme Co")
    p = Project(
        name="923 Rockland",
        code="R923",
        status=ProjectStatus.ACTIVE,
        start_date=date(2026, 3, 1),
        budget_amount=Decimal("125000.00"),
        client_id=c.canonical_id,
    )
    session.add(p)
    session.commit()

    # 3 tasks: 1 fully dated, 2 dateless
    session.add_all([
        Task(title="Demo walls", status=TaskStatus.DONE,
             start_date=date(2026, 4, 1), end_date=date(2026, 4, 5),
             project_id=p.canonical_id),
        Task(title="Frame addition", status=TaskStatus.TODO,
             project_id=p.canonical_id),
        Task(title="Inspections", status=TaskStatus.TODO,
             project_id=p.canonical_id),
    ])

    # 2 docs: one contract PDF (extracted), one stray image
    contract = Document(
        name="Contract - 923 Rockland.pdf", url="https://drive/c",
        mime_type="application/pdf", storage_ref="c1",
        folder_path="Active/923 Rockland",
        size_bytes=12345,
        modified_at_source=datetime(2026, 4, 10),
        project_id=p.canonical_id,
    )
    image = Document(
        name="site.heic", url="https://drive/i",
        mime_type="image/heic", storage_ref="i1",
        folder_path="Active/923 Rockland",
        size_bytes=2000000,
        modified_at_source=datetime(2026, 4, 12),
        project_id=p.canonical_id,
    )
    session.add_all([contract, image])
    session.commit()

    # Contract text mentions several dollar amounts; the largest should be
    # treated as the "contract total" by the regex extractor.
    session.add(DocumentText(
        document_id=contract.canonical_id,
        extracted_text=(
            "TOTAL CONTRACT PRICE: $148,500.00 inclusive of taxes.\n"
            "Deposit due on signing: $14,850.00\n"
            "Mid-project milestone: $50,000.00\n"
        ),
        extraction_method="pdf-pymupdf",
        token_count=20,
    ))
    session.add(Invoice(
        number="INV-001", amount=Decimal("14850.00"),
        status=InvoiceStatus.PAID, issue_date=date(2026, 3, 5),
        client_id=c.canonical_id, project_id=p.canonical_id,
    ))
    session.add(DailyLog(
        log_date=date(2026, 4, 10), summary="Crew arrived",
        project_id=p.canonical_id,
    ))
    session.commit()
    return p


# ---------------------------------------------------------------------------
# Pure helpers
# ---------------------------------------------------------------------------


class TestResolveProject:
    def test_uuid_string_resolves(self, session, rich_project):
        result = _resolve_project(session, str(rich_project.canonical_id))
        assert result is not None and result.canonical_id == rich_project.canonical_id

    def test_substring_match(self, session, rich_project):
        result = _resolve_project(session, "Rockland")
        assert result is not None and result.name == "923 Rockland"

    def test_case_insensitive_substring(self, session, rich_project):
        result = _resolve_project(session, "rockland")
        assert result is not None

    def test_no_match_returns_none(self, session, rich_project):
        assert _resolve_project(session, "Nowhere") is None

    def test_empty_string_returns_none(self, session, rich_project):
        assert _resolve_project(session, "") is None


class TestSerializer:
    """Regression: enums inheriting from str must yield their .value, not the
    repr like 'ProjectStatus.ACTIVE'.  Caught by a live-DB smoke test."""

    def test_str_enum_serializes_to_value(self):
        from project_db.ai.views import _ser
        assert _ser(ProjectStatus.ACTIVE) == "ACTIVE"
        assert _ser(TaskStatus.DONE) == "DONE"

    def test_none_passthrough(self):
        from project_db.ai.views import _ser
        assert _ser(None) is None

    def test_decimal_becomes_float(self):
        from project_db.ai.views import _ser
        assert _ser(Decimal("123.45")) == 123.45

    def test_date_to_iso(self):
        from project_db.ai.views import _ser
        assert _ser(date(2026, 5, 15)) == "2026-05-15"


class TestMoneyExtraction:
    def test_single_amount(self):
        assert _extract_money_amounts("Total: $50,000.00") == [50000.0]

    def test_multiple_amounts(self):
        text = "Contract $148,500.00 with deposit $14,850 and milestone $50,000.00"
        assert _extract_money_amounts(text) == [148500.0, 14850.0, 50000.0]

    def test_no_dollar_sign_ignored(self):
        # "100,000" without $ is not a money amount; we conservatively skip.
        assert _extract_money_amounts("Crew of 12 worked 100,000 hours") == []

    def test_none_input(self):
        assert _extract_money_amounts(None) == []
        assert _extract_money_amounts("") == []


# ---------------------------------------------------------------------------
# Reports
# ---------------------------------------------------------------------------


class TestProjectOverview:
    def test_full_overview_shape(self, session, rich_project):
        result = report_project_overview(session, str(rich_project.canonical_id))
        assert "error" not in result

        assert result["project"]["name"] == "923 Rockland"
        assert result["project"]["status"] == "ACTIVE"
        assert result["client"]["name"] == "Acme Co"

        stats = result["stats"]
        assert stats["task_count"] == 3
        assert stats["tasks_without_dates"] == 2
        assert stats["document_count"] == 2
        assert stats["invoice_count"] == 1
        assert stats["invoice_total"] == 14850.0
        assert stats["daily_log_count"] == 1

        assert len(result["tasks"]) == 3
        assert len(result["recent_documents"]) == 2
        assert len(result["invoices"]) == 1

    def test_resolves_by_name_substring(self, session, rich_project):
        result = report_project_overview(session, "Rockland")
        assert "error" not in result
        assert result["project"]["name"] == "923 Rockland"

    def test_unknown_ref_returns_error(self, session, rich_project):
        result = report_project_overview(session, "Nope")
        assert "error" in result

    def test_output_is_json_serializable(self, session, rich_project):
        """LLM tool layer requires JSON-serializable output."""
        result = report_project_overview(session, str(rich_project.canonical_id))
        # Should not raise on json.dumps with default str fallback.
        json.dumps(result)

    def test_trashed_docs_excluded(self, session, rich_project):
        # Trash the contract; the overview should now show 1 doc.
        contract = session.query(Document).filter_by(storage_ref="c1").one()
        contract.is_trashed = True
        session.commit()
        result = report_project_overview(session, str(rich_project.canonical_id))
        assert result["stats"]["document_count"] == 1


class TestDocsForProject:
    def test_lists_all_docs(self, session, rich_project):
        result = report_docs_for_project(session, "Rockland")
        assert result["document_count"] == 2
        names = [d["name"] for d in result["documents"]]
        assert "Contract - 923 Rockland.pdf" in names
        assert "site.heic" in names

    def test_unknown_ref(self, session, rich_project):
        assert "error" in report_docs_for_project(session, "Nope")


class TestTasksWithoutDates:
    def test_all_projects_scope(self, session, rich_project):
        result = report_tasks_without_dates(session)
        assert result["scope"] == "all-projects"
        assert result["task_count"] == 2
        titles = [t["title"] for t in result["tasks"]]
        assert "Frame addition" in titles
        assert "Inspections" in titles
        assert "Demo walls" not in titles  # this one has dates

    def test_single_project_scope(self, session, rich_project):
        result = report_tasks_without_dates(session, str(rich_project.canonical_id))
        assert result["scope"] == "single-project"
        assert result["task_count"] == 2

    def test_project_name_attached_in_all_scope(self, session, rich_project):
        result = report_tasks_without_dates(session)
        for t in result["tasks"]:
            assert t["project_name"] == "923 Rockland"

    def test_unknown_project_ref(self, session, rich_project):
        assert "error" in report_tasks_without_dates(session, "ghost")


class TestMissingDocuments:
    def test_project_without_contract_is_flagged(self, session, client_factory):
        c = client_factory(name="C")
        # Project has NO documents at all.
        bare = Project(
            name="Bare Project", code="B", status=ProjectStatus.ACTIVE,
            client_id=c.canonical_id,
        )
        session.add(bare)
        session.commit()

        result = report_missing_documents(session)
        assert result["missing_count"] == 1
        assert result["projects"][0]["name"] == "Bare Project"

    def test_project_with_contract_is_not_flagged(self, session, rich_project):
        # rich_project has a Contract PDF -- should NOT be in missing.
        result = report_missing_documents(session)
        for p in result["projects"]:
            assert p["name"] != "923 Rockland"

    def test_completed_projects_not_in_scope(self, session, client_factory):
        c = client_factory(name="C")
        done = Project(
            name="Old Job", code="O", status=ProjectStatus.COMPLETED,
            client_id=c.canonical_id,
        )
        session.add(done)
        session.commit()

        result = report_missing_documents(session)
        names = [p["name"] for p in result["projects"]]
        assert "Old Job" not in names

    def test_trashed_contracts_dont_count(self, session, rich_project):
        contract = session.query(Document).filter_by(storage_ref="c1").one()
        contract.is_trashed = True
        session.commit()
        result = report_missing_documents(session)
        names = [p["name"] for p in result["projects"]]
        assert "923 Rockland" in names  # now flagged because contract trashed


class TestBudgetVsContract:
    def test_extracts_max_amount_and_flags_divergence(self, session, rich_project):
        # budget=125000, contract max=148500 -> ~18.8% > 15% -> flagged
        result = report_budget_vs_contract(session, "Rockland")
        assert result["monday_budget"] == 125000.0
        assert result["contract_amount_estimate"] == 148500.0
        assert result["divergence_pct"] is not None
        assert result["divergence_pct"] > 0.15
        assert result["flagged"] is True

    def test_per_document_breakdown(self, session, rich_project):
        result = report_budget_vs_contract(session, "Rockland")
        assert len(result["per_document"]) == 1
        d = result["per_document"][0]
        assert d["document_name"] == "Contract - 923 Rockland.pdf"
        assert d["max_amount"] == 148500.0

    def test_no_contract_text_yields_none_estimate(self, session, rich_project):
        # Trash the contract so the join finds nothing.
        contract = session.query(Document).filter_by(storage_ref="c1").one()
        contract.is_trashed = True
        session.commit()
        result = report_budget_vs_contract(session, "Rockland")
        assert result["contract_amount_estimate"] is None
        assert result["flagged"] is False

    def test_unknown_project(self, session, rich_project):
        assert "error" in report_budget_vs_contract(session, "Nowhere")

    def test_custom_threshold(self, session, rich_project):
        # 50% threshold -- 18.8% divergence should NOT flag.
        result = report_budget_vs_contract(
            session, "Rockland", divergence_threshold=0.50,
        )
        assert result["flagged"] is False


# ---------------------------------------------------------------------------
# Dispatcher
# ---------------------------------------------------------------------------


class TestExtractProjectRef:
    def test_uuid_anywhere_in_question(self):
        u = str(uuid.uuid4())
        assert extract_project_ref(f"give me overview {u} please") == u

    def test_after_project_keyword(self):
        assert extract_project_ref("overview of project 923 Rockland") == "923 Rockland"

    def test_uuid_beats_keyword(self):
        u = str(uuid.uuid4())
        assert extract_project_ref(f"project Foo or maybe {u}") == u

    def test_no_ref_returns_none(self):
        assert extract_project_ref("show me active projects") is None
        assert extract_project_ref("") is None
        assert extract_project_ref(None) is None

    def test_strips_question_mark(self):
        assert extract_project_ref("budget for project 923 Rockland?") == "923 Rockland"


class TestAskDispatcher:
    def test_routes_to_overview(self, session, rich_project):
        a = AiAssistant(session)
        resp = a.ask("give me an overview of project Rockland")
        assert resp.used_report == "project_overview"
        assert resp.answer["project"]["name"] == "923 Rockland"

    def test_routes_to_docs(self, session, rich_project):
        a = AiAssistant(session)
        resp = a.ask("show me the docs for project Rockland")
        assert resp.used_report == "docs_for_project"
        assert resp.answer["document_count"] == 2

    def test_routes_to_tasks_without_dates_all_scope(self, session, rich_project):
        a = AiAssistant(session)
        resp = a.ask("show me tasks without dates")
        assert resp.used_report == "tasks_without_dates"
        assert resp.answer["scope"] == "all-projects"

    def test_routes_to_tasks_without_dates_single_scope(self, session, rich_project):
        a = AiAssistant(session)
        resp = a.ask("tasks with no dates for project Rockland")
        assert resp.used_report == "tasks_without_dates"
        assert resp.answer["scope"] == "single-project"

    def test_routes_to_missing_documents(self, session, rich_project):
        a = AiAssistant(session)
        resp = a.ask("which projects are missing documents")
        assert resp.used_report == "missing_documents"
        assert isinstance(resp.answer["missing_count"], int)

    def test_routes_to_budget_vs_contract(self, session, rich_project):
        a = AiAssistant(session)
        resp = a.ask("budget vs contract for project Rockland")
        assert resp.used_report == "budget_vs_contract"
        assert resp.answer["flagged"] is True

    def test_overview_without_project_returns_helpful_error(self, session, rich_project):
        a = AiAssistant(session)
        resp = a.ask("give me an overview")
        assert "error" in resp.answer

    def test_unknown_question_falls_through(self, session, rich_project):
        a = AiAssistant(session)
        resp = a.ask("what is the meaning of life")
        assert resp.used_report is None
