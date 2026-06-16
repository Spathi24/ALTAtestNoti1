"""Tests for the project-context assembler.

This is what feeds every Phase-3 prompt.  If it's wrong, every prompt
downstream is wrong.  Covering:

  * Canonical fields populated correctly (project, client, stats)
  * Tasks / docs / invoices / logs all joined through Project FK
  * Trashed Documents excluded
  * Top-N doc text limit honored, newest first
  * Per-doc char cap actually clips long bodies
  * Global token budget evicts document bodies, records truncation
  * to_prompt_block produces a readable text block
  * Missing project raises ValueError cleanly
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

import pytest

from project_db.ai.context import (
    assemble_project_context,
)
from project_db.db.models import (
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
# Fixture: rich project mirroring what real Drive+Monday data looks like
# ---------------------------------------------------------------------------


@pytest.fixture
def context_fixture(session, client_factory):
    c = client_factory(name="Acme Construction", email="ops@acme.com")
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

    # Tasks: mix of dated and dateless, one subitem.
    session.add_all(
        [
            Task(
                title="Demo walls",
                status=TaskStatus.DONE,
                start_date=date(2026, 4, 1),
                end_date=date(2026, 4, 5),
                monday_status_label="Done",
                project_id=p.canonical_id,
            ),
            Task(title="Frame addition", status=TaskStatus.TODO, project_id=p.canonical_id),
            Task(
                title="Drywall sub-task",
                status=TaskStatus.TODO,
                is_subitem=True,
                project_id=p.canonical_id,
            ),
        ]
    )

    # Documents: one trashed, three live (mix of mimes).
    docs = [
        Document(
            name="OLD - contract v1.pdf",
            url="https://drive/x1",
            mime_type="application/pdf",
            storage_ref="d1",
            folder_path="Active/923 Rockland/Archive",
            size_bytes=1000,
            modified_at_source=datetime(2026, 1, 1),
            is_trashed=True,
            project_id=p.canonical_id,
        ),
        Document(
            name="Contract - 923 Rockland.pdf",
            url="https://drive/x2",
            mime_type="application/pdf",
            storage_ref="d2",
            folder_path="Active/923 Rockland",
            size_bytes=12345,
            modified_at_source=datetime(2026, 4, 10),
            project_id=p.canonical_id,
        ),
        Document(
            name="Scope.docx",
            url="https://drive/x3",
            mime_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            storage_ref="d3",
            folder_path="Active/923 Rockland",
            size_bytes=5000,
            modified_at_source=datetime(2026, 4, 12),
            project_id=p.canonical_id,
        ),
        Document(
            name="site_photo.heic",
            url="https://drive/x4",
            mime_type="image/heic",
            storage_ref="d4",
            folder_path="Active/923 Rockland/Photos",
            size_bytes=3_000_000,
            modified_at_source=datetime(2026, 4, 14),
            project_id=p.canonical_id,
        ),
    ]
    session.add_all(docs)
    session.commit()

    # Extracted text for the two contract-shaped docs (HEIC has no DocumentText).
    contract = session.query(Document).filter_by(storage_ref="d2").one()
    scope = session.query(Document).filter_by(storage_ref="d3").one()
    session.add_all(
        [
            DocumentText(
                document_id=contract.canonical_id,
                extracted_text="CONTRACT TOTAL: $148,500.00. Deposit: $14,850.",
                extraction_method="pdf-pymupdf",
                token_count=20,
            ),
            DocumentText(
                document_id=scope.canonical_id,
                extracted_text="Scope of work: demo, frame, drywall, finish.",
                extraction_method="docx-python",
                token_count=10,
            ),
        ]
    )

    session.add(
        Invoice(
            number="INV-001",
            amount=Decimal("14850.00"),
            status=InvoiceStatus.PAID,
            issue_date=date(2026, 3, 5),
            client_id=c.canonical_id,
            project_id=p.canonical_id,
        )
    )
    session.add(
        DailyLog(
            log_date=date(2026, 4, 10),
            summary="Crew arrived; demo started on east wall.",
            project_id=p.canonical_id,
        )
    )
    session.commit()
    return p


# ---------------------------------------------------------------------------
# Shape: every section populated correctly
# ---------------------------------------------------------------------------


class TestAssemble:
    def test_project_and_client_filled(self, session, context_fixture):
        ctx = assemble_project_context(session, context_fixture.canonical_id)
        assert ctx.project["name"] == "923 Rockland"
        assert ctx.project["status"] == "ACTIVE"
        assert ctx.project["budget_amount"] == 125000.0
        assert ctx.client["name"] == "Acme Construction"
        assert ctx.client["email"] == "ops@acme.com"

    def test_tasks_present_including_subitem(self, session, context_fixture):
        ctx = assemble_project_context(session, context_fixture.canonical_id)
        titles = [t["title"] for t in ctx.tasks]
        assert "Demo walls" in titles
        assert "Frame addition" in titles
        assert "Drywall sub-task" in titles
        subitem = next(t for t in ctx.tasks if t["title"] == "Drywall sub-task")
        assert subitem["is_subitem"] is True

    def test_trashed_documents_excluded(self, session, context_fixture):
        ctx = assemble_project_context(session, context_fixture.canonical_id)
        names = [d["name"] for d in ctx.documents]
        assert "OLD - contract v1.pdf" not in names
        # 3 live docs: contract.pdf, scope.docx, site_photo.heic
        assert len(ctx.documents) == 3

    def test_document_texts_only_when_extracted(self, session, context_fixture):
        ctx = assemble_project_context(session, context_fixture.canonical_id)
        # Only 2 of 3 live docs have DocumentText rows.
        text_names = [dt["name"] for dt in ctx.document_texts]
        assert "Contract - 923 Rockland.pdf" in text_names
        assert "Scope.docx" in text_names
        assert "site_photo.heic" not in text_names

    def test_invoices_and_daily_logs(self, session, context_fixture):
        ctx = assemble_project_context(session, context_fixture.canonical_id)
        assert len(ctx.invoices) == 1
        assert ctx.invoices[0]["number"] == "INV-001"
        assert ctx.invoices[0]["amount"] == 14850.0
        assert ctx.invoices[0]["status"] == "PAID"
        assert len(ctx.daily_logs) == 1
        assert "demo started" in ctx.daily_logs[0]["summary"]

    def test_unknown_project_raises(self, session):
        import uuid

        with pytest.raises(ValueError, match="No Project"):
            assemble_project_context(session, uuid.uuid4())


# ---------------------------------------------------------------------------
# Doc text limits & budget
# ---------------------------------------------------------------------------


class TestDocumentBudget:
    def test_max_documents_with_text_cap(self, session, context_fixture):
        # Force the cap to 1 -- only the newest doc should have its body attached.
        ctx = assemble_project_context(
            session,
            context_fixture.canonical_id,
            max_documents_with_text=1,
        )
        assert len(ctx.document_texts) == 1
        # Newest-first: Scope.docx (2026-04-12) beats Contract.pdf (2026-04-10).
        assert ctx.document_texts[0]["name"] == "Scope.docx"

    def test_per_doc_char_cap_clips_body(self, session, context_fixture):
        long_text = "A" * 20000
        contract = session.query(Document).filter_by(storage_ref="d2").one()
        dt = session.query(DocumentText).filter_by(document_id=contract.canonical_id).one()
        dt.extracted_text = long_text
        session.commit()

        ctx = assemble_project_context(
            session,
            context_fixture.canonical_id,
            per_doc_char_cap=500,
        )
        contract_body = next(
            d for d in ctx.document_texts if d["name"] == "Contract - 923 Rockland.pdf"
        )
        assert len(contract_body["text"]) == 500
        assert contract_body["truncated"] is True

    def test_global_token_budget_evicts_doc_bodies(self, session, context_fixture):
        # Set a tiny budget so doc bodies must be dropped.
        ctx = assemble_project_context(
            session,
            context_fixture.canonical_id,
            token_budget=50,  # ridiculously small
            per_doc_char_cap=2000,
        )
        # Both doc bodies are too big -- both should be evicted.
        assert ctx.document_texts == []
        assert ctx.truncated["document_bodies_dropped"] == 2

    def test_generous_budget_keeps_everything(self, session, context_fixture):
        ctx = assemble_project_context(
            session,
            context_fixture.canonical_id,
            token_budget=1_000_000,
        )
        assert len(ctx.document_texts) == 2
        assert ctx.truncated == {}


# ---------------------------------------------------------------------------
# Prompt block formatting
# ---------------------------------------------------------------------------


class TestPromptBlock:
    def test_contains_all_section_headers(self, session, context_fixture):
        ctx = assemble_project_context(session, context_fixture.canonical_id)
        block = ctx.to_prompt_block()
        for marker in [
            "=== PROJECT ===",
            "=== CLIENT ===",
            "=== TASKS",
            "=== INVOICES",
            "=== DAILY LOGS",
            "=== DOCUMENTS METADATA",
            "=== DOCUMENT BODIES",
        ]:
            assert marker in block, f"missing section marker: {marker!r}"

    def test_project_facts_present(self, session, context_fixture):
        block = assemble_project_context(session, context_fixture.canonical_id).to_prompt_block()
        assert "923 Rockland" in block
        assert "ACTIVE" in block
        assert "Acme Construction" in block

    def test_document_body_text_appears(self, session, context_fixture):
        block = assemble_project_context(session, context_fixture.canonical_id).to_prompt_block()
        assert "CONTRACT TOTAL: $148,500.00" in block
        assert "Scope of work" in block

    def test_truncation_note_appears_when_present(self, session, context_fixture):
        ctx = assemble_project_context(
            session,
            context_fixture.canonical_id,
            token_budget=50,
        )
        block = ctx.to_prompt_block()
        assert "TRUNCATION NOTES" in block
        assert "document_bodies_dropped" in block

    def test_block_is_a_string(self, session, context_fixture):
        block = assemble_project_context(session, context_fixture.canonical_id).to_prompt_block()
        assert isinstance(block, str)
        # And reasonably sized.
        assert 200 < len(block) < 50_000


# ---------------------------------------------------------------------------
# to_dict serialization
# ---------------------------------------------------------------------------


class TestSerialization:
    def test_to_dict_is_json_serializable(self, session, context_fixture):
        import json

        ctx = assemble_project_context(session, context_fixture.canonical_id)
        # Should round-trip without default=str fallback.
        json.dumps(ctx.to_dict())
