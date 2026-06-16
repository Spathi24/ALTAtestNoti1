"""Tests for database models and their relationships.

Models use canonical schema: enums for statuses, FK chains for org scoping,
and a single ExternalId table for source-system mapping.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy.orm import Session

from project_db.db.models import (
    Client,
    Deal,
    ExternalId,
    Invoice,
    Lead,
    Organization,
    Project,
    SourceSystem,
    Task,
    User,
)
from project_db.db.models.crm import LeadStage
from project_db.db.models.finance import InvoiceStatus
from project_db.db.models.work import ProjectStatus, TaskStatus


class TestOrganizationModel:
    def test_create_organization(self, session: Session):
        org = Organization(name="Test Org")
        session.add(org)
        session.commit()

        assert org.canonical_id is not None
        assert org.name == "Test Org"

    def test_organization_has_children(self, org: Organization, session: Session):
        client = Client(organization_id=org.canonical_id, name="Test Client")
        session.add(client)
        session.commit()

        assert client.organization_id == org.canonical_id


class TestClientModel:
    def test_create_client(self, org: Organization, session: Session):
        client = Client(
            organization_id=org.canonical_id,
            name="Acme Corp",
            email="contact@acme.com",
            phone="555-1234",
        )
        session.add(client)
        session.commit()

        assert client.canonical_id is not None
        assert client.name == "Acme Corp"
        assert client.email == "contact@acme.com"

    def test_client_optional_fields(self, client_factory):
        client = client_factory(
            name="Beta Inc",
            email="info@beta.com",
            phone="555-5678",
            billing_address="123 Main St",
        )

        assert client.billing_address == "123 Main St"
        assert client.phone == "555-5678"


class TestProjectModel:
    def test_create_project(self, org: Organization, session: Session, client_factory):
        client = client_factory(name="Acme")
        project = Project(
            name="Website Redesign",
            code="PROJ001",
            status=ProjectStatus.ACTIVE,
            budget_amount=Decimal("50000.00"),
            client_id=client.canonical_id,
        )
        session.add(project)
        session.commit()

        assert project.canonical_id is not None
        assert project.name == "Website Redesign"
        assert project.code == "PROJ001"
        assert project.budget_amount == Decimal("50000.00")

    def test_project_status_values(self, project_factory):
        project = project_factory(status=ProjectStatus.COMPLETED)
        assert project.status == ProjectStatus.COMPLETED


class TestInvoiceModel:
    def test_create_invoice(
        self, org: Organization, session: Session, client_factory, project_factory
    ):
        client = client_factory(name="Acme")
        project = project_factory(name="Site", client=client)
        invoice = Invoice(
            number="INV-001",
            amount=Decimal("5000.00"),
            status=InvoiceStatus.DRAFT,
            issue_date=date.today(),
            client_id=client.canonical_id,
            project_id=project.canonical_id,
        )
        session.add(invoice)
        session.commit()

        assert invoice.canonical_id is not None
        assert invoice.number == "INV-001"
        assert invoice.amount == Decimal("5000.00")

    def test_invoice_with_date_fields(self, invoice_factory):
        today = date.today()
        invoice = invoice_factory(issue_date=today)
        assert invoice.issue_date == today


class TestLeadModel:
    def test_create_lead(self, session: Session):
        lead = Lead(
            stage=LeadStage.NEW,
            source_channel="referral",
            estimated_value=Decimal("15000"),
        )
        session.add(lead)
        session.commit()

        assert lead.canonical_id is not None
        assert lead.stage == LeadStage.NEW
        assert lead.source_channel == "referral"


class TestDealModel:
    def test_create_deal(self, session: Session, client_factory):
        client = client_factory(name="Acme")
        deal = Deal(
            name="Enterprise Contract",
            value=Decimal("100000.00"),
            stage=LeadStage.NEGOTIATION,
            client_id=client.canonical_id,
        )
        session.add(deal)
        session.commit()

        assert deal.canonical_id is not None
        assert deal.value == Decimal("100000.00")
        assert deal.stage == LeadStage.NEGOTIATION


class TestTaskModel:
    def test_create_task(self, session: Session, project_factory):
        project = project_factory(name="P")
        task = Task(
            title="Send proposal",
            status=TaskStatus.TODO,
            project_id=project.canonical_id,
            group_title="Planning",
            start_date=date(2026, 5, 1),
            end_date=date(2026, 5, 3),
            duration_days=Decimal("2.00"),
            planned_effort=Decimal("8.00"),
            effort_spent=Decimal("3.50"),
            subcontractor="Raul",
            supplier="BMR",
            priority="High",
            monday_status_label="Working on it",
            source_columns_json="[]",
        )
        session.add(task)
        session.commit()

        assert task.canonical_id is not None
        assert task.title == "Send proposal"
        assert task.status == TaskStatus.TODO
        assert task.group_title == "Planning"
        assert task.subcontractor == "Raul"
        assert task.planned_effort == Decimal("8.00")


class TestUserModel:
    def test_create_user(self, org: Organization, session: Session):
        user = User(
            organization_id=org.canonical_id,
            display_name="Alice Johnson",
            email="alice@company.com",
        )
        session.add(user)
        session.commit()

        assert user.canonical_id is not None
        assert user.display_name == "Alice Johnson"


class TestExternalIdModel:
    def test_create_external_id(self, org: Organization, session: Session, client_factory):
        client = client_factory(name="Acme")
        ext_id = ExternalId(
            source=SourceSystem.MONDAY,
            entity_type="Client",
            external_key="monday_item_123",
            canonical_id=client.canonical_id,
        )
        session.add(ext_id)
        session.commit()

        assert ext_id.id is not None
        assert ext_id.source == SourceSystem.MONDAY

    def test_external_id_uniqueness(self, org: Organization, session: Session, client_factory):
        from sqlalchemy.exc import IntegrityError

        client = client_factory(name="Acme")
        ext_id1 = ExternalId(
            source=SourceSystem.MONDAY,
            entity_type="Client",
            external_key="monday_item_123",
            canonical_id=client.canonical_id,
        )
        session.add(ext_id1)
        session.commit()

        ext_id2 = ExternalId(
            source=SourceSystem.MONDAY,
            entity_type="Client",
            external_key="monday_item_123",
            canonical_id=client.canonical_id,
        )
        session.add(ext_id2)

        with pytest.raises(IntegrityError):
            session.commit()


class TestModelRelationships:
    def test_query_entities_by_organization(self, populated_db: dict, session: Session):
        org = populated_db["org"]

        # Clients are scoped by organization_id directly.
        clients = session.query(Client).filter_by(organization_id=org.canonical_id).all()
        assert len(clients) >= 2

        # Projects scope through their client; verify they all belong to this org's clients.
        client_ids = {c.canonical_id for c in clients}
        projects = session.query(Project).all()
        assert all(p.client_id in client_ids for p in projects)
        assert len(projects) >= 2

        # Invoices similarly scope through their client.
        invoices = session.query(Invoice).all()
        assert all(i.client_id in client_ids for i in invoices)
        assert len(invoices) >= 2
