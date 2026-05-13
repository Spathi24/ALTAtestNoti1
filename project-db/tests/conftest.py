"""Shared pytest fixtures.

These fixtures match the actual canonical schema. Key things to know:

- Most entities (Client, Project, Deal, etc.) get their organization scope
  via FK chains through Client → org, not via a direct organization_id column.
  Only User, Client, Vendor, Property, and Organization itself carry org_id.
- Statuses are SQLAlchemy enums (ProjectStatus, TaskStatus, LeadStage,
  InvoiceStatus), not free-form strings.
- ExternalId uses the column name `source` (a SourceSystem enum), not
  `source_system`, and has no organization_id column.
"""
from __future__ import annotations

import os
from datetime import date
from decimal import Decimal
from unittest.mock import MagicMock

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

# Force in-memory SQLite + dummy credentials BEFORE importing app modules.
os.environ["PROJECT_DB_URL"] = "sqlite:///:memory:"
os.environ["MONDAY_API_TOKEN"] = "test_monday_token_12345"
os.environ["QUICKBOOKS_CLIENT_ID"] = "test_qb_client_id"
os.environ["QUICKBOOKS_CLIENT_SECRET"] = "test_qb_secret"
os.environ["QUICKBOOKS_REALM_ID"] = "test_realm_123"
os.environ["QUICKBOOKS_ACCESS_TOKEN"] = "test_access_token"
os.environ["ANTHROPIC_API_KEY"] = "test_anthropic_key"

from project_db.db.base import Base
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


# =====================================================================
# DB SETUP
# =====================================================================


@pytest.fixture
def db_engine():
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    yield engine
    engine.dispose()


@pytest.fixture
def session(db_engine):
    SessionLocal = sessionmaker(bind=db_engine, expire_on_commit=False)
    s = SessionLocal()
    yield s
    s.rollback()
    s.close()


@pytest.fixture
def org(session: Session) -> Organization:
    org = Organization(name="Test Organization")
    session.add(org)
    session.commit()
    return org


# =====================================================================
# FACTORIES
# =====================================================================


@pytest.fixture
def client_factory(org: Organization, session: Session):
    def _create(
        name: str = "Test Client",
        email: str = "test@example.com",
        phone: str = "555-0001",
        billing_address: str | None = None,
        **kwargs,
    ) -> Client:
        client = Client(
            organization_id=org.canonical_id,
            name=name,
            email=email,
            phone=phone,
            billing_address=billing_address,
            **kwargs,
        )
        session.add(client)
        session.commit()
        return client
    return _create


@pytest.fixture
def user_factory(org: Organization, session: Session):
    def _create(
        display_name: str = "Test User",
        email: str = "user@example.com",
        **kwargs,
    ) -> User:
        user = User(
            organization_id=org.canonical_id,
            display_name=display_name,
            email=email,
            **kwargs,
        )
        session.add(user)
        session.commit()
        return user
    return _create


@pytest.fixture
def project_factory(org: Organization, session: Session, client_factory):
    """Project requires a client_id; factory creates a default client if none given."""
    def _create(
        name: str = "Test Project",
        code: str = "PRJ001",
        status: ProjectStatus = ProjectStatus.ACTIVE,
        budget: Decimal | None = None,
        client=None,
        **kwargs,
    ) -> Project:
        if client is None:
            client = client_factory(name=f"Client for {name}")
        project = Project(
            name=name,
            code=code,
            status=status,
            budget_amount=budget or Decimal("10000.00"),
            client_id=client.canonical_id,
            **kwargs,
        )
        session.add(project)
        session.commit()
        return project
    return _create


@pytest.fixture
def lead_factory(org: Organization, session: Session):
    def _create(
        stage: LeadStage = LeadStage.NEW,
        source_channel: str | None = "test",
        estimated_value: Decimal | None = None,
        **kwargs,
    ) -> Lead:
        lead = Lead(
            stage=stage,
            source_channel=source_channel,
            estimated_value=estimated_value or Decimal("5000.00"),
            **kwargs,
        )
        session.add(lead)
        session.commit()
        return lead
    return _create


@pytest.fixture
def deal_factory(org: Organization, session: Session, client_factory):
    """Deal requires client_id; factory creates a default client if none given."""
    def _create(
        name: str = "Test Deal",
        value: Decimal | None = None,
        stage: LeadStage = LeadStage.NEGOTIATION,
        client=None,
        **kwargs,
    ) -> Deal:
        if client is None:
            client = client_factory(name=f"Client for {name}")
        deal = Deal(
            name=name,
            value=value or Decimal("25000.00"),
            stage=stage,
            client_id=client.canonical_id,
            **kwargs,
        )
        session.add(deal)
        session.commit()
        return deal
    return _create


@pytest.fixture
def invoice_factory(org: Organization, session: Session, client_factory, project_factory):
    """Invoice requires both project_id and client_id."""
    def _create(
        number: str = "INV-001",
        amount: Decimal | None = None,
        status: InvoiceStatus = InvoiceStatus.DRAFT,
        issue_date: date | None = None,
        client=None,
        project=None,
        **kwargs,
    ) -> Invoice:
        if client is None:
            client = client_factory(name=f"Client for {number}")
        if project is None:
            project = project_factory(name=f"Project for {number}", client=client)
        invoice = Invoice(
            number=number,
            amount=amount or Decimal("5000.00"),
            status=status,
            issue_date=issue_date or date.today(),
            project_id=project.canonical_id,
            client_id=client.canonical_id,
            **kwargs,
        )
        session.add(invoice)
        session.commit()
        return invoice
    return _create


@pytest.fixture
def task_factory(org: Organization, session: Session, project_factory):
    """Task requires project_id."""
    def _create(
        title: str = "Test Task",
        status: TaskStatus = TaskStatus.TODO,
        project=None,
        **kwargs,
    ) -> Task:
        if project is None:
            project = project_factory(name=f"Project for {title}")
        task = Task(
            title=title,
            status=status,
            project_id=project.canonical_id,
            **kwargs,
        )
        session.add(task)
        session.commit()
        return task
    return _create


# =====================================================================
# EXTERNAL ID BUILDER
# =====================================================================


@pytest.fixture
def external_id_builder(session: Session):
    def _create(
        source: SourceSystem,
        entity_type: str,
        external_key: str,
        canonical_id,
        external_url: str | None = None,
    ) -> ExternalId:
        ext_id = ExternalId(
            source=source,
            entity_type=entity_type,
            external_key=external_key,
            canonical_id=canonical_id,
            external_url=external_url,
        )
        session.add(ext_id)
        session.commit()
        return ext_id
    return _create


# =====================================================================
# POPULATED DB
# =====================================================================


@pytest.fixture
def populated_db(
    session: Session,
    org: Organization,
    client_factory,
    project_factory,
    invoice_factory,
    user_factory,
):
    acme = client_factory(name="Acme Corp", email="contact@acme.com")
    beta = client_factory(name="Beta Inc", email="info@beta.com")

    proj1 = project_factory(name="Website Redesign", code="PROJ001", client=acme)
    proj2 = project_factory(name="Mobile App", code="PROJ002", client=beta)

    inv1 = invoice_factory(number="INV-001", amount=Decimal("5000.00"), client=acme, project=proj1)
    inv2 = invoice_factory(number="INV-002", amount=Decimal("7500.00"), client=beta, project=proj2)

    user1 = user_factory(display_name="Alice Johnson", email="alice@company.com")
    user2 = user_factory(display_name="Bob Smith", email="bob@company.com")

    return {
        "org": org,
        "clients": [acme, beta],
        "projects": [proj1, proj2],
        "invoices": [inv1, inv2],
        "users": [user1, user2],
    }


# =====================================================================
# MOCKED API CLIENTS
# =====================================================================


@pytest.fixture
def mock_monday_client():
    client = MagicMock()
    client.list_boards.return_value = [
        {"id": "123456", "name": "CRM Board", "workspace": {"id": "ws1", "name": "WS 1"}, "state": "active"},
        {"id": "789012", "name": "Projects Board", "workspace": {"id": "ws1", "name": "WS 1"}, "state": "active"},
    ]
    client.list_board_columns.return_value = [
        {"id": "name", "title": "Name", "type": "text"},
        {"id": "status", "title": "Status", "type": "status"},
        {"id": "budget", "title": "Budget", "type": "numbers"},
        {"id": "date123", "title": "Start Date", "type": "date"},
    ]
    client.list_items.return_value = [
        {
            "id": "item1",
            "name": "Acme Corp",
            "group": {"id": "g1", "title": "Active"},
            "column_values": [
                {"id": "name", "type": "text", "text": "Acme Corp", "value": "Acme Corp"},
                {"id": "status", "type": "status", "text": "Active", "value": '{"index": 0}'},
                {"id": "budget", "type": "numbers", "text": "50000", "value": "50000"},
            ],
        },
        {
            "id": "item2",
            "name": "Beta Inc",
            "group": {"id": "g1", "title": "Active"},
            "column_values": [
                {"id": "name", "type": "text", "text": "Beta Inc", "value": "Beta Inc"},
            ],
        },
    ]
    client.list_users.return_value = [
        {"id": "user1", "name": "Alice", "email": "alice@monday.com", "is_admin": True},
        {"id": "user2", "name": "Bob", "email": "bob@monday.com", "is_admin": False},
    ]
    client.change_column_value.return_value = {"id": "item1", "column_values": []}
    client.change_multiple_column_values.return_value = {"id": "item1", "column_values": []}
    client.create_item.return_value = {"id": "new_item", "name": "New Item"}
    client.delete_item.return_value = True
    return client


@pytest.fixture
def mock_quickbooks_client():
    client = MagicMock()
    client.list_customers.return_value = [
        {"id": "cust1", "DisplayName": "Acme Corp", "PrimaryEmailAddr": {"Address": "acme@example.com"}},
        {"id": "cust2", "DisplayName": "Beta Inc", "PrimaryEmailAddr": {"Address": "beta@example.com"}},
    ]
    client.list_invoices.return_value = [
        {
            "id": "inv1",
            "DocNumber": "INV-001",
            "TotalAmt": 5000.00,
            "Status": "SENT",
            "CustomerRef": {"value": "cust1"},
            "MetaData": {"CreateTime": "2026-01-01T00:00:00Z"},
        },
    ]
    client.list_estimates.return_value = [
        {"id": "est1", "DocNumber": "EST-001", "TotalAmt": 25000.00, "CustomerRef": {"value": "cust1"}},
    ]
    client.query.return_value = [
        {"Id": "cust1", "DisplayName": "Acme Corp"},
    ]
    client.list_invoices_updated_since.return_value = []
    return client
