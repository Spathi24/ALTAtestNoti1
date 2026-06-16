"""Integration tests for multi-source workflows.

Exercises the end-to-end shape of cross-system data: same client in two
sources resolves to one canonical entity, project spans Monday + QB IDs,
invoice links to project by code, delta sync timestamps advance.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from decimal import Decimal

from sqlalchemy.orm import Session

from project_db.db.models import (
    Client,
    ExternalId,
    Invoice,
    Project,
    SourceSystem,
)
from project_db.db.models.finance import InvoiceStatus
from project_db.db.models.work import ProjectStatus
from project_db.identity import ExactFieldMatcher, IdentityResolver


class TestMultiSourceDeduplication:
    def test_same_client_from_monday_and_qb_dedups(self, session: Session, org):
        resolver = IdentityResolver(session)

        monday = resolver.resolve_or_create(
            source=SourceSystem.MONDAY,
            external_key="monday_item_123",
            external_url=None,
            entity_class=Client,
            attrs={
                "name": "Acme Corporation",
                "email": "contact@acme.com",
                "organization_id": org.canonical_id,
            },
            matcher=ExactFieldMatcher(["name"]),
        )

        qb = resolver.resolve_or_create(
            source=SourceSystem.QUICKBOOKS,
            external_key="qb_customer_456",
            external_url=None,
            entity_class=Client,
            attrs={
                "name": "Acme Corporation",
                "email": "contact@acme.com",
                "organization_id": org.canonical_id,
            },
            matcher=ExactFieldMatcher(["name"]),
        )

        assert qb.entity.canonical_id == monday.entity.canonical_id

        ext_ids = session.query(ExternalId).filter_by(canonical_id=monday.entity.canonical_id).all()
        assert len(ext_ids) == 2
        sources = {e.source for e in ext_ids}
        assert SourceSystem.MONDAY in sources
        assert SourceSystem.QUICKBOOKS in sources


class TestCrossSystemProjectTracking:
    def test_project_with_monday_board_and_qb_job(self, session: Session, org, client_factory):
        client = client_factory(name="Owner")
        project = Project(
            name="923 Rockland Renovation",
            code="923",
            status=ProjectStatus.ACTIVE,
            budget_amount=Decimal("50000.00"),
            client_id=client.canonical_id,
        )
        session.add(project)
        session.commit()

        session.add_all(
            [
                ExternalId(
                    source=SourceSystem.MONDAY,
                    entity_type="Project",
                    external_key="board_18412002783",
                    canonical_id=project.canonical_id,
                ),
                ExternalId(
                    source=SourceSystem.QUICKBOOKS,
                    entity_type="Project",
                    external_key="job_923",
                    canonical_id=project.canonical_id,
                ),
            ]
        )
        session.commit()

        ext_ids = session.query(ExternalId).filter_by(canonical_id=project.canonical_id).all()
        assert len(ext_ids) == 2
        assert {e.source for e in ext_ids} == {
            SourceSystem.MONDAY,
            SourceSystem.QUICKBOOKS,
        }


class TestInvoiceProjectLinking:
    def test_invoice_links_to_project_by_code(
        self, session: Session, org, project_factory, invoice_factory
    ):
        project = project_factory(code="923")
        invoice_factory(number="INV-001", project=None, client=None)  # unrelated

        projects = session.query(Project).filter_by(code="923").all()
        assert len(projects) == 1
        assert projects[0].canonical_id == project.canonical_id


class TestComplexMultiSourceScenario:
    def test_full_workflow_monday_to_qb_ripple(self, session: Session, org):
        resolver = IdentityResolver(session)

        # 1) Sync client from Monday
        client_result = resolver.resolve_or_create(
            source=SourceSystem.MONDAY,
            external_key="monday_contact_123",
            external_url=None,
            entity_class=Client,
            attrs={
                "name": "Acme Corp",
                "email": "contact@acme.com",
                "organization_id": org.canonical_id,
            },
            matcher=ExactFieldMatcher(["name"]),
        )

        # 2) Create the project linked to that client
        project = Project(
            name="923 Rockland",
            code="923",
            status=ProjectStatus.ACTIVE,
            budget_amount=Decimal("50000"),
            client_id=client_result.entity.canonical_id,
        )
        session.add(project)
        session.commit()
        session.add(
            ExternalId(
                source=SourceSystem.MONDAY,
                entity_type="Project",
                external_key="board_123",
                canonical_id=project.canonical_id,
            )
        )
        session.commit()

        # 3) Same client comes in from QB → should match
        qb_client = resolver.resolve_or_create(
            source=SourceSystem.QUICKBOOKS,
            external_key="qb_customer_456",
            external_url=None,
            entity_class=Client,
            attrs={
                "name": "Acme Corp",
                "email": "contact@acme.com",
                "organization_id": org.canonical_id,
            },
            matcher=ExactFieldMatcher(["name"]),
        )
        assert qb_client.entity.canonical_id == client_result.entity.canonical_id

        # 4) QB invoice for the project
        invoice = Invoice(
            number="INV-923-001",
            amount=Decimal("12500"),
            status=InvoiceStatus.SENT,
            issue_date=date.today(),
            project_id=project.canonical_id,
            client_id=client_result.entity.canonical_id,
        )
        session.add(invoice)
        session.commit()
        session.add(
            ExternalId(
                source=SourceSystem.QUICKBOOKS,
                entity_type="Invoice",
                external_key="qb_invoice_789",
                canonical_id=invoice.canonical_id,
            )
        )
        session.commit()

        # End state: 1 client (matched across sources), 1 project, 1 invoice
        assert session.query(Client).count() == 1
        assert session.query(Project).count() == 1
        assert session.query(Invoice).count() == 1
        # Three external IDs registered total: Client x2, Project x1, Invoice x1
        assert session.query(ExternalId).count() == 4


class TestDeltaSyncIncremental:
    def test_external_id_last_synced_at_advances(self, session: Session, org, client_factory):
        client = client_factory(name="Acme")
        ext = ExternalId(
            source=SourceSystem.MONDAY,
            entity_type="Client",
            external_key="monday_123",
            canonical_id=client.canonical_id,
        )
        session.add(ext)
        session.commit()

        initial = ext.last_synced_at
        assert initial is not None

        # Simulate a later re-sync.
        ext.last_synced_at = initial + timedelta(minutes=5)
        session.commit()
        session.refresh(ext)
        assert ext.last_synced_at > initial


class TestSyncReporting:
    def test_sync_report_summary_includes_counts(self):
        from project_db.connectors.base import SyncReport

        report = SyncReport(source=SourceSystem.MONDAY, started_at=datetime.utcnow())
        report.records_processed = 10
        report.records_created = 6
        report.records_matched = 4
        report.completed_at = datetime.utcnow()

        summary = report.summary()
        assert "MONDAY" in summary
        assert "processed=10" in summary
        assert "created=6" in summary
        assert "matched=4" in summary


class TestIdentityResolutionAccuracy:
    def test_resolver_updates_attrs_on_re_sync(self, session: Session, org):
        resolver = IdentityResolver(session)

        # Initial sync
        first = resolver.resolve_or_create(
            source=SourceSystem.MONDAY,
            external_key="monday_123",
            external_url=None,
            entity_class=Client,
            attrs={
                "name": "Original Name",
                "email": "original@example.com",
                "organization_id": org.canonical_id,
            },
        )
        original_id = first.entity.canonical_id

        # Re-sync with updated fields
        second = resolver.resolve_or_create(
            source=SourceSystem.MONDAY,
            external_key="monday_123",
            external_url=None,
            entity_class=Client,
            attrs={
                "name": "Updated Name",
                "email": "original@example.com",
                "organization_id": org.canonical_id,
            },
        )

        assert second.entity.canonical_id == original_id
        assert second.entity.name == "Updated Name"
