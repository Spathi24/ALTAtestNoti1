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
from project_db.db.models.docs import (
    EVIDENCE_TYPES,
    PARSE_STATUSES,
    Document,
    DocumentParse,
    DocumentText,
    EvidenceSpan,
)
from project_db.db.models.field_notes import FieldNote, NoteChannel, NoteClass
from project_db.db.models.finance import (
    COST_STATUSES,
    FINANCIAL_DIRECTIONS,
    FINANCIAL_DOC_ROLES,
    FINANCIAL_RECORD_KINDS,
    LINE_ITEM_AMOUNT_TYPES,
    LINE_ITEM_SIDES,
    LINE_ITEM_SOURCES,
    LINE_ITEM_STATUSES,
    PURCHASE_TYPES,
    RECONCILIATION_ISSUE_TYPES,
    RECONCILIATION_SEVERITIES,
    RECONCILIATION_SOURCES,
    RECONCILIATION_STATUSES,
    SUBCONTRACTOR_QUOTE_STATUSES,
    DocumentFinancialStatus,
    FinancialLineItem,
    FinancialRecord,
    Invoice,
    InvoiceStatus,
    ReconciliationIssue,
    SubcontractorQuote,
)
from project_db.db.models.homedepot import (
    HD_DETAIL_STATUSES,
    HD_PROJECT_MATCH_METHODS,
    HomeDepotLineItem,
    HomeDepotTransaction,
)
from project_db.db.models.labour_intake import (
    CLAIM_TYPES,
    CLUSTER_STATUSES,
    LabourClaim,
    LabourClaimCluster,
    LabourClaimClusterMember,
    LabourSourceEvent,
)
from project_db.db.models.obligations import (
    OBLIGATION_DIRECTIONS,
    OBLIGATION_KINDS,
    ContractObligation,
)
from project_db.db.models.project_log import (
    EMPLOYEE_MATCH_METHODS,
    PROJECT_LOG_CLASSIFICATION_METHODS,
    PROJECT_LOG_INGESTION_REASONS,
    PROJECT_LOG_INGESTION_STATUSES,
    WORKER_ALIAS_SOURCES,
    ProjectLogEntry,
    ProjectLogSubmission,
    WorkerAlias,
)
from project_db.db.models.proposals import Proposal, ProposalStatus
from project_db.db.models.rag import DocumentChunk
from project_db.db.models.roadmap import (
    ROADMAP_PHASE_ORDER,
    RoadmapActor,
    RoadmapPhase,
    RoadmapTask,
)
from project_db.db.models.sow import (
    SOW_PACKAGE_STATUSES,
    SowItem,
    SowPackage,
)
from project_db.db.models.telegram_identity import TelegramIdentity
from project_db.db.models.work import (
    DailyLog,
    Project,
    ProjectStatus,
    Task,
    TaskDependency,
    TaskStatus,
)
from project_db.db.models.workers import EmailIngest, Worker

__all__ = [
    "CLAIM_TYPES",
    "CLUSTER_STATUSES",
    "COST_STATUSES",
    "EMPLOYEE_MATCH_METHODS",
    "EVIDENCE_TYPES",
    "FINANCIAL_DIRECTIONS",
    "FINANCIAL_DOC_ROLES",
    "FINANCIAL_RECORD_KINDS",
    "HD_DETAIL_STATUSES",
    "HD_PROJECT_MATCH_METHODS",
    "LINE_ITEM_AMOUNT_TYPES",
    "LINE_ITEM_SIDES",
    "LINE_ITEM_SOURCES",
    "LINE_ITEM_STATUSES",
    "OBLIGATION_DIRECTIONS",
    "OBLIGATION_KINDS",
    "PARSE_STATUSES",
    "PROJECT_LOG_CLASSIFICATION_METHODS",
    "PROJECT_LOG_INGESTION_REASONS",
    "PROJECT_LOG_INGESTION_STATUSES",
    "PURCHASE_TYPES",
    "RECONCILIATION_ISSUE_TYPES",
    "RECONCILIATION_SEVERITIES",
    "RECONCILIATION_SOURCES",
    "RECONCILIATION_STATUSES",
    "ROADMAP_PHASE_ORDER",
    "SOW_PACKAGE_STATUSES",
    "SUBCONTRACTOR_QUOTE_STATUSES",
    "WORKER_ALIAS_SOURCES",
    "Client",
    "ContractObligation",
    "DailyLog",
    "Deal",
    "Document",
    "DocumentChunk",
    "DocumentFinancialStatus",
    "DocumentParse",
    "DocumentText",
    "EmailIngest",
    "EvidenceSpan",
    "ExternalId",
    "FieldNote",
    "FinancialLineItem",
    "FinancialRecord",
    "HomeDepotLineItem",
    "HomeDepotTransaction",
    "Invoice",
    "InvoiceStatus",
    "LabourClaim",
    "LabourClaimCluster",
    "LabourClaimClusterMember",
    "LabourSourceEvent",
    "Lead",
    "LeadStage",
    "NoteChannel",
    "NoteClass",
    "Organization",
    "Project",
    "ProjectLogEntry",
    "ProjectLogSubmission",
    "ProjectStatus",
    "Property",
    "Proposal",
    "ProposalStatus",
    "ReconciliationIssue",
    "RoadmapActor",
    "RoadmapPhase",
    "RoadmapTask",
    "SourceSystem",
    "SowItem",
    "SowPackage",
    "SubcontractorQuote",
    "Task",
    "TaskDependency",
    "TaskStatus",
    "TelegramIdentity",
    "User",
    "Vendor",
    "Worker",
    "WorkerAlias",
]
