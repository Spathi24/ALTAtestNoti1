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
from project_db.db.models.docs import Document, DocumentText
from project_db.db.models.field_notes import FieldNote, NoteChannel, NoteClass
from project_db.db.models.workers import EmailIngest, Worker
from project_db.db.models.finance import (
    FINANCIAL_DIRECTIONS,
    FINANCIAL_DOC_ROLES,
    FINANCIAL_RECORD_KINDS,
    DocumentFinancialStatus,
    FinancialRecord,
    Invoice,
    InvoiceStatus,
)
from project_db.db.models.obligations import (
    OBLIGATION_DIRECTIONS,
    OBLIGATION_KINDS,
    ContractObligation,
)
from project_db.db.models.proposals import Proposal, ProposalStatus
from project_db.db.models.rag import DocumentChunk
from project_db.db.models.roadmap import (
    ROADMAP_PHASE_ORDER,
    RoadmapActor,
    RoadmapPhase,
    RoadmapTask,
)
from project_db.db.models.work import (
    DailyLog,
    Project,
    ProjectStatus,
    Task,
    TaskStatus,
)

__all__ = [
    "Client",
    "ContractObligation",
    "DailyLog",
    "Deal",
    "Document",
    "DocumentChunk",
    "OBLIGATION_DIRECTIONS",
    "OBLIGATION_KINDS",
    "DocumentFinancialStatus",
    "DocumentText",
    "ExternalId",
    "EmailIngest",
    "FieldNote",
    "NoteChannel",
    "NoteClass",
    "Worker",
    "FINANCIAL_DIRECTIONS",
    "FINANCIAL_DOC_ROLES",
    "FINANCIAL_RECORD_KINDS",
    "FinancialRecord",
    "Invoice",
    "InvoiceStatus",
    "Lead",
    "LeadStage",
    "Organization",
    "Project",
    "ProjectStatus",
    "Property",
    "Proposal",
    "ProposalStatus",
    "RoadmapActor",
    "RoadmapPhase",
    "RoadmapTask",
    "ROADMAP_PHASE_ORDER",
    "SourceSystem",
    "Task",
    "TaskStatus",
    "User",
    "Vendor",
]
