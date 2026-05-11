"""Re-exports for convenient access to all entities.

Usage:
    from project_db.db.models import Project, Client, ExternalId, SourceSystem
"""
from project_db.db.models.canonical import (
    ExternalId,
    Organization,
    SourceSystem,
)
from project_db.db.models.core import Client, Property, User, Vendor
from project_db.db.models.crm import Deal, Lead, LeadStage
from project_db.db.models.docs import Document
from project_db.db.models.finance import Invoice, InvoiceStatus
from project_db.db.models.work import (
    DailyLog,
    Project,
    ProjectStatus,
    Task,
    TaskStatus,
)

__all__ = [
    "Client",
    "DailyLog",
    "Deal",
    "Document",
    "ExternalId",
    "Invoice",
    "InvoiceStatus",
    "Lead",
    "LeadStage",
    "Organization",
    "Project",
    "ProjectStatus",
    "Property",
    "SourceSystem",
    "Task",
    "TaskStatus",
    "User",
    "Vendor",
]
