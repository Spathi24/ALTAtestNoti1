"""Small compatibility migrations for local SQLite databases.

The project does not have Alembic yet. These helpers keep an existing local
SQLite file usable when the SQLAlchemy models gain nullable columns.
"""

from __future__ import annotations

from sqlalchemy import inspect, text

SQLITE_TASK_COLUMNS: dict[str, str] = {
    "monday_status_label": "VARCHAR",
    "priority": "VARCHAR",
    "group_title": "VARCHAR",
    "start_date": "DATE",
    "end_date": "DATE",
    "duration_days": "NUMERIC(10, 2)",
    "planned_effort": "NUMERIC(10, 2)",
    "effort_spent": "NUMERIC(10, 2)",
    "subcontractor": "VARCHAR",
    "supplier": "VARCHAR",
    "is_subitem": "BOOLEAN NOT NULL DEFAULT 0",
    "source_columns_json": "TEXT",
    "parent_task_id": "UUID",
}

SQLITE_DOCUMENT_COLUMNS: dict[str, str] = {
    "created_at_source": "DATETIME",
    "modified_at_source": "DATETIME",
    "size_bytes": "BIGINT",
    "md5_checksum": "VARCHAR",
    "drive_id": "VARCHAR",
    "parent_folder_id": "VARCHAR",
    "folder_path": "VARCHAR",
    "category": "VARCHAR",
    "owner_email": "VARCHAR",
    "is_trashed": "BOOLEAN NOT NULL DEFAULT 0",
    "source_meta_json": "TEXT",
}


SQLITE_DOCUMENT_TEXT_DDL = """
CREATE TABLE document_text (
    document_id TEXT PRIMARY KEY,
    extracted_text TEXT,
    extraction_method VARCHAR NOT NULL,
    extracted_at DATETIME NOT NULL,
    token_count INTEGER,
    FOREIGN KEY (document_id) REFERENCES document(canonical_id) ON DELETE CASCADE
)
"""

# Evidence-backed parsing layer (slice 1). document_parse must be created
# BEFORE evidence_span (FK -> document_parse.id). Both cascade-delete with their
# Document.
SQLITE_DOCUMENT_PARSE_DDL = """
CREATE TABLE document_parse (
    id TEXT PRIMARY KEY,
    document_id TEXT NOT NULL,
    parser_name VARCHAR NOT NULL,
    parser_version VARCHAR,
    source_hash VARCHAR,
    status VARCHAR NOT NULL,
    rendered_text TEXT,
    structured_json TEXT,
    error TEXT,
    created_at DATETIME NOT NULL,
    token_count INTEGER,
    FOREIGN KEY (document_id) REFERENCES document(canonical_id) ON DELETE CASCADE
)
"""

SQLITE_DOCUMENT_PARSE_INDEXES = (
    "CREATE INDEX IF NOT EXISTS ix_document_parse_document_id ON document_parse (document_id)",
)

SQLITE_EVIDENCE_SPAN_DDL = """
CREATE TABLE evidence_span (
    id TEXT PRIMARY KEY,
    document_id TEXT NOT NULL,
    parse_id TEXT NOT NULL,
    evidence_type VARCHAR NOT NULL,
    locator_json TEXT,
    content_text TEXT,
    content_json TEXT,
    bbox_json TEXT,
    confidence FLOAT,
    created_at DATETIME NOT NULL,
    FOREIGN KEY (document_id) REFERENCES document(canonical_id) ON DELETE CASCADE,
    FOREIGN KEY (parse_id) REFERENCES document_parse(id) ON DELETE CASCADE
)
"""

SQLITE_EVIDENCE_SPAN_INDEXES = (
    "CREATE INDEX IF NOT EXISTS ix_evidence_span_document_id ON evidence_span (document_id)",
    "CREATE INDEX IF NOT EXISTS ix_evidence_span_parse_id ON evidence_span (parse_id)",
)

SQLITE_PROPOSAL_DDL = """
CREATE TABLE proposal (
    canonical_id TEXT PRIMARY KEY,
    created_at DATETIME NOT NULL,
    updated_at DATETIME NOT NULL,
    notes VARCHAR,
    entity_type VARCHAR NOT NULL,
    entity_id TEXT NOT NULL,
    field_name VARCHAR NOT NULL,
    proposed_value TEXT NOT NULL,
    confidence FLOAT,
    source_doc_ids TEXT,
    prompt_version VARCHAR,
    status VARCHAR NOT NULL DEFAULT 'PENDING',
    decided_at DATETIME,
    decided_by VARCHAR,
    rejection_reason TEXT
)
"""

SQLITE_ROADMAP_TASK_DDL = """
CREATE TABLE roadmap_task (
    canonical_id TEXT PRIMARY KEY,
    created_at DATETIME NOT NULL,
    updated_at DATETIME NOT NULL,
    notes VARCHAR,
    phase VARCHAR NOT NULL,
    ordinal INTEGER NOT NULL,
    task_name VARCHAR NOT NULL,
    sub_tasks_json TEXT,
    actor VARCHAR,
    CONSTRAINT uq_roadmap_phase_ordinal UNIQUE (phase, ordinal)
)
"""

# Columns added AFTER the initial roadmap_task DDL shipped.  ALTER TABLE
# in SQLite for existing local DB files.
SQLITE_ROADMAP_TASK_COLUMNS: dict[str, str] = {
    "actor": "VARCHAR",
}

SQLITE_FINANCIAL_RECORD_DDL = """
CREATE TABLE financial_record (
    canonical_id TEXT PRIMARY KEY,
    created_at DATETIME NOT NULL,
    updated_at DATETIME NOT NULL,
    notes VARCHAR,
    project_id TEXT,
    document_id TEXT,
    direction VARCHAR NOT NULL DEFAULT 'unknown',
    doc_role VARCHAR,
    record_kind VARCHAR,
    counterparty VARCHAR,
    description TEXT,
    phase VARCHAR,
    amount NUMERIC(14, 2),
    currency VARCHAR,
    doc_date DATE,
    quoted_excerpt TEXT,
    confidence FLOAT,
    amount_verified BOOLEAN,
    is_rollup BOOLEAN,
    prompt_version VARCHAR,
    source_meta_json TEXT,
    evidence_span_id TEXT,
    evidence_locator_json TEXT,
    FOREIGN KEY (project_id) REFERENCES project(canonical_id),
    FOREIGN KEY (document_id) REFERENCES document(canonical_id) ON DELETE CASCADE
)
"""

# Columns added AFTER the initial financial_record DDL shipped.
SQLITE_FINANCIAL_RECORD_COLUMNS: dict[str, str] = {
    "amount_verified": "BOOLEAN",
    "is_rollup": "BOOLEAN",
    # Evidence link (Slice 5). FK to evidence_span.id is enforced via the model on
    # fresh DBs; on an ALTER we add a plain TEXT column (SQLite can't add an FK).
    "evidence_span_id": "TEXT",
    "evidence_locator_json": "TEXT",
}

SQLITE_FINANCIAL_LINE_ITEM_DDL = """
CREATE TABLE financial_line_item (
    canonical_id TEXT PRIMARY KEY,
    created_at DATETIME NOT NULL,
    updated_at DATETIME NOT NULL,
    notes VARCHAR,
    project_id TEXT,
    document_id TEXT,
    unit VARCHAR,
    division_code VARCHAR NOT NULL DEFAULT '99',
    division_name VARCHAR,
    side VARCHAR NOT NULL DEFAULT 'unknown',
    amount_type VARCHAR NOT NULL DEFAULT 'total',
    status VARCHAR NOT NULL DEFAULT 'unknown',
    doc_role VARCHAR,
    description TEXT,
    amount NUMERIC(14, 2),
    currency VARCHAR,
    doc_date DATE,
    quote_expiry DATE,
    source VARCHAR,
    quoted_excerpt TEXT,
    confidence FLOAT,
    amount_verified BOOLEAN,
    extractor_version VARCHAR,
    source_meta_json TEXT,
    evidence_span_id TEXT,
    evidence_locator_json TEXT,
    classification_method VARCHAR,
    classification_confidence FLOAT,
    source_doc_type VARCHAR,
    source_region VARCHAR,
    purchase_type VARCHAR,
    cost_status VARCHAR,
    sow_item_id TEXT,
    line_markup_factor FLOAT,
    subcontractor_quote_id TEXT,
    FOREIGN KEY (project_id) REFERENCES project(canonical_id),
    FOREIGN KEY (document_id) REFERENCES document(canonical_id) ON DELETE CASCADE,
    FOREIGN KEY (sow_item_id) REFERENCES sow_item(canonical_id) ON DELETE SET NULL,
    FOREIGN KEY (subcontractor_quote_id) REFERENCES subcontractor_quote(canonical_id) ON DELETE SET NULL
)
"""

# Columns added to financial_line_item after the initial DDL (Phase 1c-MVP +
# Phase 4/5). `_add_missing_columns` adds any of these absent from an existing DB.
SQLITE_FINANCIAL_LINE_ITEM_COLUMNS: dict[str, str] = {
    "classification_method": "VARCHAR",
    "classification_confidence": "FLOAT",
    "source_doc_type": "VARCHAR",
    "source_region": "VARCHAR",
    # Evidence link (Slice 5) -- see SQLITE_FINANCIAL_RECORD_COLUMNS.
    "evidence_span_id": "TEXT",
    "evidence_locator_json": "TEXT",
    # Phase 4: cost lifecycle + SOW traceability.
    "purchase_type": "VARCHAR",
    "cost_status": "VARCHAR",
    "sow_item_id": "TEXT",
    "line_markup_factor": "FLOAT",
    # Phase 5: which quote priced this row (read by PO award to find rows to commit).
    "subcontractor_quote_id": "TEXT",
}

# Columns added to contract_obligation after the initial DDL (Slice 5 evidence link).
SQLITE_CONTRACT_OBLIGATION_COLUMNS: dict[str, str] = {
    "evidence_span_id": "TEXT",
    "evidence_locator_json": "TEXT",
}

SQLITE_FINANCIAL_LINE_ITEM_INDEXES = (
    "CREATE INDEX IF NOT EXISTS ix_financial_line_item_project_id "
    "ON financial_line_item (project_id)",
    "CREATE INDEX IF NOT EXISTS ix_financial_line_item_document_id "
    "ON financial_line_item (document_id)",
    "CREATE INDEX IF NOT EXISTS ix_financial_line_item_unit_division "
    "ON financial_line_item (project_id, unit, division_code)",
)

SQLITE_CONTRACT_OBLIGATION_DDL = """
CREATE TABLE contract_obligation (
    canonical_id TEXT PRIMARY KEY,
    created_at DATETIME NOT NULL,
    updated_at DATETIME NOT NULL,
    notes VARCHAR,
    project_id TEXT,
    document_id TEXT,
    kind VARCHAR NOT NULL DEFAULT 'other',
    direction VARCHAR NOT NULL DEFAULT 'unknown',
    description TEXT,
    amount NUMERIC(14, 2),
    currency VARCHAR,
    due_date DATE,
    trigger VARCHAR,
    counterparty VARCHAR,
    quoted_excerpt TEXT,
    confidence FLOAT,
    amount_verified BOOLEAN,
    prompt_version VARCHAR,
    source_meta_json TEXT,
    evidence_span_id TEXT,
    evidence_locator_json TEXT,
    FOREIGN KEY (project_id) REFERENCES project(canonical_id),
    FOREIGN KEY (document_id) REFERENCES document(canonical_id) ON DELETE CASCADE
)
"""

SQLITE_RECONCILIATION_ISSUE_DDL = """
CREATE TABLE reconciliation_issue (
    canonical_id TEXT PRIMARY KEY,
    created_at DATETIME NOT NULL,
    updated_at DATETIME NOT NULL,
    notes VARCHAR,
    project_id TEXT,
    issue_type VARCHAR NOT NULL,
    severity VARCHAR NOT NULL DEFAULT 'medium',
    status VARCHAR NOT NULL DEFAULT 'open',
    source VARCHAR NOT NULL DEFAULT 'deterministic',
    description TEXT,
    delta_amount NUMERIC(14, 2),
    currency VARCHAR,
    evidence_json TEXT,
    dedupe_key VARCHAR,
    prompt_version VARCHAR,
    decided_by VARCHAR,
    decided_at DATETIME,
    FOREIGN KEY (project_id) REFERENCES project(canonical_id)
)
"""

SQLITE_RECONCILIATION_ISSUE_INDEXES = (
    "CREATE INDEX IF NOT EXISTS ix_reconciliation_issue_project "
    "ON reconciliation_issue (project_id)",
    "CREATE INDEX IF NOT EXISTS ix_reconciliation_issue_dedupe "
    "ON reconciliation_issue (dedupe_key)",
)

SQLITE_DOCUMENT_CHUNK_DDL = """
CREATE TABLE document_chunk (
    canonical_id TEXT PRIMARY KEY,
    created_at DATETIME NOT NULL,
    updated_at DATETIME NOT NULL,
    notes VARCHAR,
    document_id TEXT NOT NULL,
    project_id TEXT,
    chunk_index INTEGER NOT NULL,
    text TEXT NOT NULL,
    token_count INTEGER,
    embedding BLOB,
    embedding_model VARCHAR,
    dims INTEGER,
    content_hash VARCHAR NOT NULL,
    embedded_at DATETIME,
    FOREIGN KEY (document_id) REFERENCES document(canonical_id) ON DELETE CASCADE,
    FOREIGN KEY (project_id) REFERENCES project(canonical_id)
)
"""

SQLITE_DOCUMENT_CHUNK_INDEXES = (
    "CREATE INDEX IF NOT EXISTS ix_document_chunk_document_id ON document_chunk (document_id)",
    "CREATE INDEX IF NOT EXISTS ix_document_chunk_project_id ON document_chunk (project_id)",
    "CREATE INDEX IF NOT EXISTS ix_document_chunk_content_hash ON document_chunk (content_hash)",
)

SQLITE_DOCUMENT_FINANCIAL_STATUS_DDL = """
CREATE TABLE document_financial_status (
    document_id TEXT PRIMARY KEY,
    confirmed BOOLEAN NOT NULL,
    decided_by VARCHAR,
    decided_at DATETIME NOT NULL,
    FOREIGN KEY (document_id) REFERENCES document(canonical_id) ON DELETE CASCADE
)
"""


SQLITE_FIELD_NOTE_DDL = """
CREATE TABLE field_note (
    canonical_id TEXT PRIMARY KEY,
    created_at DATETIME NOT NULL,
    updated_at DATETIME NOT NULL,
    notes VARCHAR,
    raw_text TEXT NOT NULL,
    received_at DATETIME NOT NULL,
    channel VARCHAR NOT NULL DEFAULT 'cli',
    sender_ref VARCHAR,
    project_id TEXT NOT NULL,
    classification VARCHAR,
    quoted_excerpt TEXT,
    workers VARCHAR,
    hours_worked NUMERIC(8, 2),
    matched_task_id TEXT,
    confidence FLOAT,
    email_ingest_id TEXT,
    FOREIGN KEY (project_id) REFERENCES project(canonical_id),
    FOREIGN KEY (matched_task_id) REFERENCES task(canonical_id),
    FOREIGN KEY (email_ingest_id) REFERENCES email_ingest(canonical_id)
)
"""

# Columns added to field_note after the initial DDL shipped.
SQLITE_FIELD_NOTE_COLUMNS: dict[str, str] = {
    "email_ingest_id": "TEXT",
}

SQLITE_WORKER_DDL = """
CREATE TABLE worker (
    canonical_id TEXT PRIMARY KEY,
    created_at DATETIME NOT NULL,
    updated_at DATETIME NOT NULL,
    notes VARCHAR,
    display_name VARCHAR NOT NULL,
    email VARCHAR,
    phone_gateway_email VARCHAR,
    default_project_id TEXT,
    active BOOLEAN NOT NULL DEFAULT 1,
    FOREIGN KEY (default_project_id) REFERENCES project(canonical_id)
)
"""

SQLITE_EMAIL_INGEST_DDL = """
CREATE TABLE email_ingest (
    canonical_id TEXT PRIMARY KEY,
    created_at DATETIME NOT NULL,
    updated_at DATETIME NOT NULL,
    notes VARCHAR,
    gmail_message_id VARCHAR NOT NULL,
    rfc_message_id VARCHAR,
    thread_id VARCHAR,
    sender_email VARCHAR,
    subject VARCHAR,
    received_at DATETIME NOT NULL,
    processed_at DATETIME,
    status VARCHAR NOT NULL DEFAULT 'pending',
    failure_reason TEXT,
    project_id TEXT,
    attachment_refs_json TEXT,
    FOREIGN KEY (project_id) REFERENCES project(canonical_id)
)
"""

SQLITE_EMAIL_INGEST_INDEXES = (
    "CREATE UNIQUE INDEX IF NOT EXISTS uq_email_ingest_gmail_message_id "
    "ON email_ingest (gmail_message_id)",
)

# Phase 3: Scope of Work -- SowPackage before SowItem (FK order).
SQLITE_SOW_PACKAGE_DDL = """
CREATE TABLE sow_package (
    canonical_id TEXT PRIMARY KEY,
    created_at DATETIME NOT NULL,
    updated_at DATETIME NOT NULL,
    notes VARCHAR,
    project_id TEXT NOT NULL,
    division_code VARCHAR NOT NULL DEFAULT '99',
    trade_name VARCHAR,
    title VARCHAR,
    status VARCHAR NOT NULL DEFAULT 'draft',
    drawings_refs_json TEXT,
    source_meta_json TEXT,
    FOREIGN KEY (project_id) REFERENCES project(canonical_id)
)
"""

SQLITE_SOW_ITEM_DDL = """
CREATE TABLE sow_item (
    canonical_id TEXT PRIMARY KEY,
    created_at DATETIME NOT NULL,
    updated_at DATETIME NOT NULL,
    notes VARCHAR,
    project_id TEXT NOT NULL,
    package_id TEXT,
    item_code VARCHAR,
    description TEXT,
    division_code VARCHAR NOT NULL DEFAULT '99',
    included BOOLEAN NOT NULL DEFAULT 1,
    material_spec TEXT,
    quantity NUMERIC(14, 2),
    unit VARCHAR,
    assumptions TEXT,
    exclusions TEXT,
    source_meta_json TEXT,
    FOREIGN KEY (project_id) REFERENCES project(canonical_id),
    FOREIGN KEY (package_id) REFERENCES sow_package(canonical_id)
)
"""

# item_code unique PER PROJECT when set (partial). SOW_Item_Ref on a quote line
# carries only "SOW-025" (no package context), so the code must identify exactly
# one scope item in the project. Partial (WHERE item_code IS NOT NULL) also
# closes the null-package hole a package-scoped constraint would leave open.
SQLITE_SOW_ITEM_INDEXES = (
    "CREATE UNIQUE INDEX IF NOT EXISTS uq_sow_item_project_item_code "
    "ON sow_item (project_id, item_code) WHERE item_code IS NOT NULL",
)

# Phase 4: one subcontractor/vendor quote for one SowPackage. References project,
# sow_package, vendor, document, evidence_span -- all created before it.
SQLITE_SUBCONTRACTOR_QUOTE_DDL = """
CREATE TABLE subcontractor_quote (
    canonical_id TEXT PRIMARY KEY,
    created_at DATETIME NOT NULL,
    updated_at DATETIME NOT NULL,
    notes VARCHAR,
    project_id TEXT,
    package_id TEXT,
    vendor_id TEXT,
    document_id TEXT,
    division_code VARCHAR,
    status VARCHAR NOT NULL DEFAULT 'pending',
    amount NUMERIC(14, 2),
    currency VARCHAR,
    quote_date DATE,
    coverage TEXT,
    exclusions TEXT,
    assumptions TEXT,
    materials_included TEXT,
    evidence_span_id TEXT,
    evidence_locator_json TEXT,
    source VARCHAR,
    source_meta_json TEXT,
    FOREIGN KEY (project_id) REFERENCES project(canonical_id),
    FOREIGN KEY (package_id) REFERENCES sow_package(canonical_id),
    FOREIGN KEY (vendor_id) REFERENCES vendor(canonical_id),
    FOREIGN KEY (document_id) REFERENCES document(canonical_id) ON DELETE CASCADE,
    FOREIGN KEY (evidence_span_id) REFERENCES evidence_span(id) ON DELETE SET NULL
)
"""

SQLITE_SUBCONTRACTOR_QUOTE_INDEXES = (
    "CREATE INDEX IF NOT EXISTS ix_subcontractor_quote_project_id "
    "ON subcontractor_quote (project_id)",
    "CREATE INDEX IF NOT EXISTS ix_subcontractor_quote_package_id "
    "ON subcontractor_quote (package_id)",
    "CREATE INDEX IF NOT EXISTS ix_subcontractor_quote_document_id "
    "ON subcontractor_quote (document_id)",
)

# Phase 5: PurchaseOrder -- always created by awarding a SubcontractorQuote, so
# subcontractor_quote_id is NOT NULL + unique (one PO per quote; a re-award
# attempt is rejected, not silently re-issued). Created after subcontractor_quote,
# vendor, project (FK order).
SQLITE_PURCHASE_ORDER_DDL = """
CREATE TABLE purchase_order (
    canonical_id TEXT PRIMARY KEY,
    created_at DATETIME NOT NULL,
    updated_at DATETIME NOT NULL,
    notes VARCHAR,
    project_id TEXT,
    package_id TEXT,
    vendor_id TEXT,
    subcontractor_quote_id TEXT NOT NULL,
    po_number VARCHAR NOT NULL,
    division_code VARCHAR,
    status VARCHAR NOT NULL DEFAULT 'awarded',
    contract_amount NUMERIC(14, 2),
    currency VARCHAR,
    awarded_date DATE,
    terms TEXT,
    source_meta_json TEXT,
    FOREIGN KEY (project_id) REFERENCES project(canonical_id),
    FOREIGN KEY (package_id) REFERENCES sow_package(canonical_id),
    FOREIGN KEY (vendor_id) REFERENCES vendor(canonical_id),
    FOREIGN KEY (subcontractor_quote_id) REFERENCES subcontractor_quote(canonical_id),
    CONSTRAINT uq_purchase_order_po_number UNIQUE (po_number),
    CONSTRAINT uq_purchase_order_subcontractor_quote_id UNIQUE (subcontractor_quote_id)
)
"""

SQLITE_PURCHASE_ORDER_INDEXES = (
    "CREATE INDEX IF NOT EXISTS ix_purchase_order_project_id ON purchase_order (project_id)",
    "CREATE INDEX IF NOT EXISTS ix_purchase_order_package_id ON purchase_order (package_id)",
)

# Phase 6: BudgetSnapshot (header) before BudgetSnapshotLine (FK order).
SQLITE_BUDGET_SNAPSHOT_DDL = """
CREATE TABLE budget_snapshot (
    canonical_id TEXT PRIMARY KEY,
    created_at DATETIME NOT NULL,
    updated_at DATETIME NOT NULL,
    notes VARCHAR,
    project_id TEXT NOT NULL,
    label VARCHAR,
    snapshot_date DATE,
    source_meta_json TEXT,
    FOREIGN KEY (project_id) REFERENCES project(canonical_id)
)
"""

SQLITE_BUDGET_SNAPSHOT_LINE_DDL = """
CREATE TABLE budget_snapshot_line (
    canonical_id TEXT PRIMARY KEY,
    created_at DATETIME NOT NULL,
    updated_at DATETIME NOT NULL,
    notes VARCHAR,
    snapshot_id TEXT NOT NULL,
    project_id TEXT NOT NULL,
    division_code VARCHAR NOT NULL DEFAULT '99',
    division_name VARCHAR,
    budget_amount NUMERIC(14, 2),
    line_markup_factor FLOAT,
    source_meta_json TEXT,
    FOREIGN KEY (snapshot_id) REFERENCES budget_snapshot(canonical_id) ON DELETE CASCADE,
    FOREIGN KEY (project_id) REFERENCES project(canonical_id),
    CONSTRAINT uq_budget_snapshot_line_division UNIQUE (snapshot_id, division_code)
)
"""

SQLITE_BUDGET_SNAPSHOT_INDEXES = (
    "CREATE INDEX IF NOT EXISTS ix_budget_snapshot_project_id ON budget_snapshot (project_id)",
    "CREATE INDEX IF NOT EXISTS ix_budget_snapshot_line_snapshot_id "
    "ON budget_snapshot_line (snapshot_id)",
    "CREATE INDEX IF NOT EXISTS ix_budget_snapshot_line_project_id "
    "ON budget_snapshot_line (project_id)",
)

# Columns added to worker after initial DDL (role/tags/verified for PM categorization).
SQLITE_WORKER_COLUMNS: dict[str, str] = {
    "role": "VARCHAR",
    "tags": "VARCHAR",
    "verified": "BOOLEAN NOT NULL DEFAULT 0",
}

# Phase 2 identity columns on project (display_name, legacy_job_number, aliases).
# `code` already exists as a nullable VARCHAR from the initial DDL (used by QuickBooks).
SQLITE_PROJECT_COLUMNS: dict[str, str] = {
    "display_name": "VARCHAR",
    "legacy_job_number": "VARCHAR",
    "aliases": "TEXT",
}


SQLITE_TASK_DEPENDENCY_DDL = """
CREATE TABLE task_dependency (
    id TEXT PRIMARY KEY,
    predecessor_task_id TEXT NOT NULL,
    successor_task_id TEXT NOT NULL,
    source VARCHAR NOT NULL DEFAULT 'MONDAY',
    created_at DATETIME NOT NULL,
    FOREIGN KEY (predecessor_task_id) REFERENCES task(canonical_id),
    FOREIGN KEY (successor_task_id) REFERENCES task(canonical_id)
)
"""

SQLITE_TASK_DEPENDENCY_INDEXES = (
    "CREATE UNIQUE INDEX IF NOT EXISTS uq_task_dependency_edge "
    "ON task_dependency (predecessor_task_id, successor_task_id)",
    "CREATE INDEX IF NOT EXISTS ix_task_dependency_predecessor "
    "ON task_dependency (predecessor_task_id)",
    "CREATE INDEX IF NOT EXISTS ix_task_dependency_successor "
    "ON task_dependency (successor_task_id)",
)


SQLITE_PROJECT_LOG_SUBMISSION_DDL = """
CREATE TABLE project_log_submission (
    canonical_id TEXT PRIMARY KEY,
    created_at DATETIME NOT NULL,
    updated_at DATETIME NOT NULL,
    notes VARCHAR,
    project_id TEXT,
    email_ingest_id TEXT,
    site_name_raw VARCHAR,
    site_name_resolved VARCHAR,
    source_email_message_id VARCHAR,
    source_attachment_filename VARCHAR,
    source_attachment_hash VARCHAR,
    source_image_uri VARCHAR,
    drive_file_id VARCHAR,
    received_at DATETIME,
    processed_at DATETIME,
    document_type VARCHAR NOT NULL DEFAULT 'project_log',
    classification_method VARCHAR,
    classification_confidence FLOAT,
    ingestion_status VARCHAR NOT NULL DEFAULT 'parsed',
    ingestion_reason TEXT,
    extractor_version VARCHAR,
    raw_extraction_json TEXT,
    FOREIGN KEY (project_id) REFERENCES project(canonical_id),
    FOREIGN KEY (email_ingest_id) REFERENCES email_ingest(canonical_id)
)
"""

SQLITE_PROJECT_LOG_SUBMISSION_INDEXES = (
    "CREATE INDEX IF NOT EXISTS ix_project_log_submission_project_id "
    "ON project_log_submission (project_id)",
    "CREATE INDEX IF NOT EXISTS ix_project_log_submission_attachment_hash "
    "ON project_log_submission (source_attachment_hash)",
)

SQLITE_PROJECT_LOG_ENTRY_DDL = """
CREATE TABLE project_log_entry (
    canonical_id TEXT PRIMARY KEY,
    created_at DATETIME NOT NULL,
    updated_at DATETIME NOT NULL,
    notes VARCHAR,
    submission_id TEXT NOT NULL,
    project_id TEXT,
    site_name_raw VARCHAR,
    site_name_resolved VARCHAR,
    work_date DATE,
    employee_name_raw VARCHAR,
    employee_id TEXT,
    employee_match_confidence FLOAT,
    employee_match_method VARCHAR NOT NULL DEFAULT 'unresolved',
    time_arrived VARCHAR,
    time_left VARCHAR,
    lunch_hours NUMERIC(5, 2),
    total_hours_reported NUMERIC(6, 2),
    total_hours_computed NUMERIC(6, 2),
    hours_mismatch BOOLEAN NOT NULL DEFAULT 0,
    supervisor_signature_present BOOLEAN NOT NULL DEFAULT 0,
    row_index INTEGER,
    confidence FLOAT,
    missing_fields_json TEXT,
    source_bbox_json TEXT,
    source_meta_json TEXT,
    FOREIGN KEY (submission_id) REFERENCES project_log_submission(canonical_id) ON DELETE CASCADE,
    FOREIGN KEY (project_id) REFERENCES project(canonical_id),
    FOREIGN KEY (employee_id) REFERENCES worker(canonical_id)
)
"""

SQLITE_PROJECT_LOG_ENTRY_INDEXES = (
    "CREATE INDEX IF NOT EXISTS ix_project_log_entry_submission_id "
    "ON project_log_entry (submission_id)",
    "CREATE INDEX IF NOT EXISTS ix_project_log_entry_project_id ON project_log_entry (project_id)",
    "CREATE INDEX IF NOT EXISTS ix_project_log_entry_employee_id "
    "ON project_log_entry (employee_id)",
)

SQLITE_WORKER_ALIAS_DDL = """
CREATE TABLE worker_alias (
    canonical_id TEXT PRIMARY KEY,
    created_at DATETIME NOT NULL,
    updated_at DATETIME NOT NULL,
    notes VARCHAR,
    worker_id TEXT NOT NULL,
    alias_text VARCHAR NOT NULL,
    source VARCHAR NOT NULL DEFAULT 'project_log',
    confidence FLOAT,
    FOREIGN KEY (worker_id) REFERENCES worker(canonical_id) ON DELETE CASCADE
)
"""

SQLITE_WORKER_ALIAS_INDEXES = (
    "CREATE INDEX IF NOT EXISTS ix_worker_alias_worker_id ON worker_alias (worker_id)",
    "CREATE INDEX IF NOT EXISTS ix_worker_alias_alias_text ON worker_alias (alias_text)",
)


SQLITE_LABOUR_SOURCE_EVENT_DDL = """
CREATE TABLE labour_source_event (
    canonical_id TEXT PRIMARY KEY,
    created_at DATETIME NOT NULL,
    updated_at DATETIME NOT NULL,
    notes VARCHAR,
    source_channel VARCHAR NOT NULL DEFAULT 'manual',
    source_kind VARCHAR NOT NULL DEFAULT 'manual',
    source_external_id VARCHAR,
    source_parent_id VARCHAR,
    source_sender_key VARCHAR,
    source_chat_id VARCHAR,
    source_message_id VARCHAR,
    received_at DATETIME NOT NULL,
    source_created_at DATETIME,
    raw_text TEXT,
    raw_payload_json TEXT,
    attachment_paths_json TEXT,
    attachment_hashes_json TEXT,
    ingestion_status VARCHAR NOT NULL DEFAULT 'received',
    ingestion_reason TEXT,
    worker_id TEXT,
    project_id_hint TEXT,
    FOREIGN KEY (worker_id) REFERENCES worker(canonical_id),
    FOREIGN KEY (project_id_hint) REFERENCES project(canonical_id)
)
"""

SQLITE_LABOUR_SOURCE_EVENT_INDEXES = (
    "CREATE INDEX IF NOT EXISTS ix_labour_source_event_external "
    "ON labour_source_event (source_external_id)",
    "CREATE INDEX IF NOT EXISTS ix_labour_source_event_worker ON labour_source_event (worker_id)",
)

SQLITE_LABOUR_CLAIM_DDL = """
CREATE TABLE labour_claim (
    canonical_id TEXT PRIMARY KEY,
    created_at DATETIME NOT NULL,
    updated_at DATETIME NOT NULL,
    notes VARCHAR,
    source_event_id TEXT,
    source_channel VARCHAR NOT NULL DEFAULT 'manual',
    source_confidence FLOAT,
    reporter_worker_id TEXT,
    reporter_role VARCHAR NOT NULL DEFAULT 'unknown',
    reported_for_worker_id TEXT,
    employee_name_raw VARCHAR,
    employee_phone_raw VARCHAR,
    employee_match_method VARCHAR NOT NULL DEFAULT 'unresolved',
    employee_match_confidence FLOAT,
    project_id TEXT,
    project_name_raw VARCHAR,
    project_match_method VARCHAR NOT NULL DEFAULT 'unresolved',
    project_match_confidence FLOAT,
    work_date DATE,
    work_date_raw VARCHAR,
    time_arrived VARCHAR,
    time_left VARCHAR,
    lunch_hours NUMERIC(5, 2),
    total_hours_reported NUMERIC(6, 2),
    total_hours_computed NUMERIC(6, 2),
    hours_mismatch BOOLEAN NOT NULL DEFAULT 0,
    activity_text TEXT,
    trade VARCHAR,
    unit VARCHAR,
    claim_type VARCHAR NOT NULL DEFAULT 'unknown',
    extraction_method VARCHAR NOT NULL DEFAULT 'manual',
    extractor_version VARCHAR,
    missing_fields_json TEXT,
    raw_extraction_json TEXT,
    canonical_cluster_id TEXT,
    canonicalized BOOLEAN NOT NULL DEFAULT 0,
    review_status VARCHAR NOT NULL DEFAULT 'pending',
    FOREIGN KEY (source_event_id) REFERENCES labour_source_event(canonical_id) ON DELETE CASCADE,
    FOREIGN KEY (reporter_worker_id) REFERENCES worker(canonical_id),
    FOREIGN KEY (reported_for_worker_id) REFERENCES worker(canonical_id),
    FOREIGN KEY (project_id) REFERENCES project(canonical_id),
    FOREIGN KEY (canonical_cluster_id) REFERENCES labour_claim_cluster(canonical_id)
)
"""

SQLITE_LABOUR_CLAIM_INDEXES = (
    "CREATE INDEX IF NOT EXISTS ix_labour_claim_source_event ON labour_claim (source_event_id)",
    "CREATE INDEX IF NOT EXISTS ix_labour_claim_cluster ON labour_claim (canonical_cluster_id)",
    "CREATE INDEX IF NOT EXISTS ix_labour_claim_project ON labour_claim (project_id)",
    "CREATE INDEX IF NOT EXISTS ix_labour_claim_for_worker "
    "ON labour_claim (reported_for_worker_id)",
    "CREATE INDEX IF NOT EXISTS ix_labour_claim_work_date ON labour_claim (work_date)",
)

SQLITE_LABOUR_CLAIM_CLUSTER_DDL = """
CREATE TABLE labour_claim_cluster (
    canonical_id TEXT PRIMARY KEY,
    created_at DATETIME NOT NULL,
    updated_at DATETIME NOT NULL,
    notes VARCHAR,
    worker_id TEXT,
    project_id TEXT,
    work_date DATE,
    cluster_key VARCHAR NOT NULL,
    confidence FLOAT,
    status VARCHAR NOT NULL DEFAULT 'open',
    chosen_time_arrived VARCHAR,
    chosen_time_left VARCHAR,
    chosen_lunch_hours NUMERIC(5, 2),
    chosen_total_hours NUMERIC(6, 2),
    evidence_count INTEGER NOT NULL DEFAULT 0,
    source_channels_json TEXT,
    conflict_flags_json TEXT,
    resolution_method VARCHAR,
    canonical_submission_id TEXT,
    canonical_entry_id TEXT,
    FOREIGN KEY (worker_id) REFERENCES worker(canonical_id),
    FOREIGN KEY (project_id) REFERENCES project(canonical_id),
    FOREIGN KEY (canonical_submission_id) REFERENCES project_log_submission(canonical_id),
    FOREIGN KEY (canonical_entry_id) REFERENCES project_log_entry(canonical_id)
)
"""

SQLITE_LABOUR_CLAIM_CLUSTER_INDEXES = (
    "CREATE INDEX IF NOT EXISTS ix_labour_cluster_key ON labour_claim_cluster (cluster_key)",
    "CREATE INDEX IF NOT EXISTS ix_labour_cluster_wpd "
    "ON labour_claim_cluster (worker_id, project_id, work_date)",
)

SQLITE_LABOUR_CLAIM_CLUSTER_MEMBER_DDL = """
CREATE TABLE labour_claim_cluster_member (
    canonical_id TEXT PRIMARY KEY,
    created_at DATETIME NOT NULL,
    updated_at DATETIME NOT NULL,
    notes VARCHAR,
    cluster_id TEXT NOT NULL,
    claim_id TEXT NOT NULL,
    relationship VARCHAR NOT NULL DEFAULT 'supporting',
    similarity_score FLOAT,
    FOREIGN KEY (cluster_id) REFERENCES labour_claim_cluster(canonical_id) ON DELETE CASCADE,
    FOREIGN KEY (claim_id) REFERENCES labour_claim(canonical_id) ON DELETE CASCADE
)
"""

SQLITE_LABOUR_CLAIM_CLUSTER_MEMBER_INDEXES = (
    "CREATE INDEX IF NOT EXISTS ix_labour_member_cluster "
    "ON labour_claim_cluster_member (cluster_id)",
    "CREATE INDEX IF NOT EXISTS ix_labour_member_claim ON labour_claim_cluster_member (claim_id)",
)


SQLITE_TELEGRAM_IDENTITY_DDL = """
CREATE TABLE telegram_identity (
    canonical_id TEXT PRIMARY KEY,
    created_at DATETIME NOT NULL,
    updated_at DATETIME NOT NULL,
    notes VARCHAR,
    worker_id TEXT NOT NULL,
    telegram_user_id VARCHAR,
    telegram_chat_id VARCHAR,
    telegram_username VARCHAR,
    telegram_first_name VARCHAR,
    telegram_last_name VARCHAR,
    telegram_phone VARCHAR,
    verified BOOLEAN NOT NULL DEFAULT 0,
    verified_method VARCHAR,
    invite_token VARCHAR,
    first_seen_at DATETIME,
    last_seen_at DATETIME,
    FOREIGN KEY (worker_id) REFERENCES worker(canonical_id) ON DELETE CASCADE
)
"""

SQLITE_TELEGRAM_IDENTITY_INDEXES = (
    "CREATE INDEX IF NOT EXISTS ix_telegram_identity_user ON telegram_identity (telegram_user_id)",
    "CREATE INDEX IF NOT EXISTS ix_telegram_identity_token ON telegram_identity (invite_token)",
    "CREATE INDEX IF NOT EXISTS ix_telegram_identity_worker ON telegram_identity (worker_id)",
)


SQLITE_HOME_DEPOT_TRANSACTION_DDL = """
CREATE TABLE home_depot_transaction (
    canonical_id TEXT PRIMARY KEY,
    created_at DATETIME NOT NULL,
    updated_at DATETIME NOT NULL,
    notes VARCHAR,
    transaction_number VARCHAR NOT NULL,
    sales_date DATE,
    purchase_location VARCHAR,
    job_name_raw VARCHAR,
    status VARCHAR,
    purchaser VARCHAR,
    subtotal NUMERIC(14, 2),
    total NUMERIC(14, 2),
    tax NUMERIC(14, 2),
    currency VARCHAR,
    is_refund BOOLEAN NOT NULL DEFAULT 0,
    project_id TEXT,
    project_match_method VARCHAR NOT NULL DEFAULT 'unresolved',
    project_match_confidence FLOAT,
    detail_status VARCHAR NOT NULL DEFAULT 'pending',
    line_item_count INTEGER NOT NULL DEFAULT 0,
    line_items_subtotal NUMERIC(14, 2),
    reconciled BOOLEAN,
    reconcile_delta NUMERIC(14, 2),
    detail_attempts INTEGER NOT NULL DEFAULT 0,
    detail_last_error TEXT,
    detail_fetched_at DATETIME,
    duplicate_of_id TEXT,
    source_export_file VARCHAR,
    source_meta_json TEXT,
    FOREIGN KEY (project_id) REFERENCES project(canonical_id),
    FOREIGN KEY (duplicate_of_id) REFERENCES home_depot_transaction(canonical_id)
)
"""

# Columns added to home_depot_transaction after the initial DDL shipped.
SQLITE_HOME_DEPOT_TRANSACTION_COLUMNS: dict[str, str] = {
    "duplicate_of_id": "TEXT",
}

SQLITE_HOME_DEPOT_TRANSACTION_INDEXES = (
    "CREATE UNIQUE INDEX IF NOT EXISTS uq_home_depot_transaction_number "
    "ON home_depot_transaction (transaction_number)",
    "CREATE INDEX IF NOT EXISTS ix_home_depot_transaction_project "
    "ON home_depot_transaction (project_id)",
    "CREATE INDEX IF NOT EXISTS ix_home_depot_transaction_detail_status "
    "ON home_depot_transaction (detail_status)",
)

SQLITE_HOME_DEPOT_LINE_ITEM_DDL = """
CREATE TABLE home_depot_line_item (
    canonical_id TEXT PRIMARY KEY,
    created_at DATETIME NOT NULL,
    updated_at DATETIME NOT NULL,
    notes VARCHAR,
    transaction_id TEXT,
    transaction_number VARCHAR NOT NULL,
    line_number INTEGER,
    sku VARCHAR,
    product_name TEXT,
    quantity NUMERIC(12, 3),
    unit_price NUMERIC(14, 4),
    subtotal NUMERIC(14, 2),
    project_id TEXT,
    sales_date DATE,
    purchase_location VARCHAR,
    category_guess VARCHAR,
    source_export_file VARCHAR,
    source_meta_json TEXT,
    FOREIGN KEY (transaction_id) REFERENCES home_depot_transaction(canonical_id) ON DELETE CASCADE,
    FOREIGN KEY (project_id) REFERENCES project(canonical_id)
)
"""

SQLITE_HOME_DEPOT_LINE_ITEM_INDEXES = (
    "CREATE INDEX IF NOT EXISTS ix_home_depot_line_item_transaction "
    "ON home_depot_line_item (transaction_id)",
    "CREATE INDEX IF NOT EXISTS ix_home_depot_line_item_txn_number "
    "ON home_depot_line_item (transaction_number)",
    "CREATE INDEX IF NOT EXISTS ix_home_depot_line_item_sku ON home_depot_line_item (sku)",
    "CREATE INDEX IF NOT EXISTS ix_home_depot_line_item_project "
    "ON home_depot_line_item (project_id)",
)


def _add_missing_columns(conn, inspector, table: str, columns: dict[str, str]) -> None:
    existing = {col["name"] for col in inspector.get_columns(table)}
    for name, ddl_type in columns.items():
        if name not in existing:
            conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {name} {ddl_type}"))


def _create_table_if_missing(conn, tables: set[str], name: str, ddl: str) -> None:
    if name not in tables:
        conn.execute(text(ddl))


def ensure_sqlite_schema(engine) -> None:
    """Add nullable compatibility columns + Phase-1 tables to existing SQLite files."""
    if engine.dialect.name != "sqlite":
        return
    inspector = inspect(engine)
    tables = set(inspector.get_table_names())
    with engine.begin() as conn:
        if "task" in tables:
            _add_missing_columns(conn, inspector, "task", SQLITE_TASK_COLUMNS)
        if "document" in tables:
            _add_missing_columns(conn, inspector, "document", SQLITE_DOCUMENT_COLUMNS)
        _create_table_if_missing(conn, tables, "document_text", SQLITE_DOCUMENT_TEXT_DDL)
        # Evidence-backed parsing layer: parse before span (FK -> document_parse.id).
        _create_table_if_missing(conn, tables, "document_parse", SQLITE_DOCUMENT_PARSE_DDL)
        for _idx_ddl in SQLITE_DOCUMENT_PARSE_INDEXES:
            conn.execute(text(_idx_ddl))
        _create_table_if_missing(conn, tables, "evidence_span", SQLITE_EVIDENCE_SPAN_DDL)
        for _idx_ddl in SQLITE_EVIDENCE_SPAN_INDEXES:
            conn.execute(text(_idx_ddl))
        _create_table_if_missing(conn, tables, "proposal", SQLITE_PROPOSAL_DDL)
        _create_table_if_missing(conn, tables, "roadmap_task", SQLITE_ROADMAP_TASK_DDL)
        _create_table_if_missing(conn, tables, "financial_record", SQLITE_FINANCIAL_RECORD_DDL)
        if "financial_record" in tables:
            _add_missing_columns(
                conn,
                inspector,
                "financial_record",
                SQLITE_FINANCIAL_RECORD_COLUMNS,
            )
        _create_table_if_missing(
            conn,
            tables,
            "document_financial_status",
            SQLITE_DOCUMENT_FINANCIAL_STATUS_DDL,
        )
        _create_table_if_missing(
            conn, tables, "financial_line_item", SQLITE_FINANCIAL_LINE_ITEM_DDL
        )
        if "financial_line_item" in tables:
            _add_missing_columns(
                conn, inspector, "financial_line_item", SQLITE_FINANCIAL_LINE_ITEM_COLUMNS
            )
        for _idx_ddl in SQLITE_FINANCIAL_LINE_ITEM_INDEXES:
            conn.execute(text(_idx_ddl))
        _create_table_if_missing(
            conn, tables, "contract_obligation", SQLITE_CONTRACT_OBLIGATION_DDL
        )
        if "contract_obligation" in tables:
            _add_missing_columns(
                conn, inspector, "contract_obligation", SQLITE_CONTRACT_OBLIGATION_COLUMNS
            )
        _create_table_if_missing(
            conn, tables, "reconciliation_issue", SQLITE_RECONCILIATION_ISSUE_DDL
        )
        for _idx_ddl in SQLITE_RECONCILIATION_ISSUE_INDEXES:
            conn.execute(text(_idx_ddl))
        _create_table_if_missing(conn, tables, "document_chunk", SQLITE_DOCUMENT_CHUNK_DDL)
        for _idx_ddl in SQLITE_DOCUMENT_CHUNK_INDEXES:
            conn.execute(text(_idx_ddl))
        # worker must exist before email_ingest (email_ingest has no FK to worker,
        # but both must exist before field_note references email_ingest).
        _create_table_if_missing(conn, tables, "worker", SQLITE_WORKER_DDL)
        if "worker" in tables:
            _add_missing_columns(conn, inspector, "worker", SQLITE_WORKER_COLUMNS)
        _create_table_if_missing(conn, tables, "email_ingest", SQLITE_EMAIL_INGEST_DDL)
        for _idx_ddl in SQLITE_EMAIL_INGEST_INDEXES:
            conn.execute(text(_idx_ddl))
        _create_table_if_missing(conn, tables, "task_dependency", SQLITE_TASK_DEPENDENCY_DDL)
        for _idx_ddl in SQLITE_TASK_DEPENDENCY_INDEXES:
            conn.execute(text(_idx_ddl))
        # Project Log tables (need worker + email_ingest + project to exist first).
        _create_table_if_missing(conn, tables, "worker_alias", SQLITE_WORKER_ALIAS_DDL)
        for _idx_ddl in SQLITE_WORKER_ALIAS_INDEXES:
            conn.execute(text(_idx_ddl))
        _create_table_if_missing(
            conn, tables, "project_log_submission", SQLITE_PROJECT_LOG_SUBMISSION_DDL
        )
        for _idx_ddl in SQLITE_PROJECT_LOG_SUBMISSION_INDEXES:
            conn.execute(text(_idx_ddl))
        _create_table_if_missing(conn, tables, "project_log_entry", SQLITE_PROJECT_LOG_ENTRY_DDL)
        for _idx_ddl in SQLITE_PROJECT_LOG_ENTRY_INDEXES:
            conn.execute(text(_idx_ddl))
        # Labour consolidation layer (needs worker/project/project_log_* to exist).
        # Order: source_event -> cluster -> claim (FK->cluster) -> member.
        _create_table_if_missing(
            conn, tables, "labour_source_event", SQLITE_LABOUR_SOURCE_EVENT_DDL
        )
        for _idx_ddl in SQLITE_LABOUR_SOURCE_EVENT_INDEXES:
            conn.execute(text(_idx_ddl))
        _create_table_if_missing(
            conn, tables, "labour_claim_cluster", SQLITE_LABOUR_CLAIM_CLUSTER_DDL
        )
        for _idx_ddl in SQLITE_LABOUR_CLAIM_CLUSTER_INDEXES:
            conn.execute(text(_idx_ddl))
        _create_table_if_missing(conn, tables, "labour_claim", SQLITE_LABOUR_CLAIM_DDL)
        for _idx_ddl in SQLITE_LABOUR_CLAIM_INDEXES:
            conn.execute(text(_idx_ddl))
        _create_table_if_missing(
            conn, tables, "labour_claim_cluster_member", SQLITE_LABOUR_CLAIM_CLUSTER_MEMBER_DDL
        )
        for _idx_ddl in SQLITE_LABOUR_CLAIM_CLUSTER_MEMBER_INDEXES:
            conn.execute(text(_idx_ddl))
        _create_table_if_missing(conn, tables, "telegram_identity", SQLITE_TELEGRAM_IDENTITY_DDL)
        for _idx_ddl in SQLITE_TELEGRAM_IDENTITY_INDEXES:
            conn.execute(text(_idx_ddl))
        # Home Depot Pro purchase ledger (FK -> project; project exists already).
        _create_table_if_missing(
            conn, tables, "home_depot_transaction", SQLITE_HOME_DEPOT_TRANSACTION_DDL
        )
        if "home_depot_transaction" in tables:
            _add_missing_columns(
                conn, inspector, "home_depot_transaction", SQLITE_HOME_DEPOT_TRANSACTION_COLUMNS
            )
        for _idx_ddl in SQLITE_HOME_DEPOT_TRANSACTION_INDEXES:
            conn.execute(text(_idx_ddl))
        _create_table_if_missing(
            conn, tables, "home_depot_line_item", SQLITE_HOME_DEPOT_LINE_ITEM_DDL
        )
        for _idx_ddl in SQLITE_HOME_DEPOT_LINE_ITEM_INDEXES:
            conn.execute(text(_idx_ddl))
        _create_table_if_missing(conn, tables, "field_note", SQLITE_FIELD_NOTE_DDL)
        # Post-DDL columns on field_note (email_ingest_id added after initial DDL).
        if "field_note" in tables:
            _add_missing_columns(conn, inspector, "field_note", SQLITE_FIELD_NOTE_COLUMNS)
        # Post-DDL columns on roadmap_task (for DB files created before
        # the actor column landed).
        if "roadmap_task" in tables:
            _add_missing_columns(
                conn,
                inspector,
                "roadmap_task",
                SQLITE_ROADMAP_TASK_COLUMNS,
            )
        # Phase 2: project identity columns + partial unique index on code.
        if "project" in tables:
            _add_missing_columns(conn, inspector, "project", SQLITE_PROJECT_COLUMNS)
            conn.execute(
                text(
                    "CREATE UNIQUE INDEX IF NOT EXISTS ix_project_code_unique "
                    "ON project (code) WHERE code IS NOT NULL"
                )
            )
        # Phase 3: Scope of Work -- SowPackage before SowItem (FK order).
        _create_table_if_missing(conn, tables, "sow_package", SQLITE_SOW_PACKAGE_DDL)
        _create_table_if_missing(conn, tables, "sow_item", SQLITE_SOW_ITEM_DDL)
        for _idx_ddl in SQLITE_SOW_ITEM_INDEXES:
            conn.execute(text(_idx_ddl))
        # Phase 4: subcontractor quotes (after sow_package + vendor + document).
        _create_table_if_missing(
            conn, tables, "subcontractor_quote", SQLITE_SUBCONTRACTOR_QUOTE_DDL
        )
        for _idx_ddl in SQLITE_SUBCONTRACTOR_QUOTE_INDEXES:
            conn.execute(text(_idx_ddl))
        # Phase 5: purchase orders (after subcontractor_quote + vendor + project).
        _create_table_if_missing(conn, tables, "purchase_order", SQLITE_PURCHASE_ORDER_DDL)
        for _idx_ddl in SQLITE_PURCHASE_ORDER_INDEXES:
            conn.execute(text(_idx_ddl))
        # Phase 6: budget snapshots -- header before lines (FK order).
        _create_table_if_missing(conn, tables, "budget_snapshot", SQLITE_BUDGET_SNAPSHOT_DDL)
        _create_table_if_missing(
            conn, tables, "budget_snapshot_line", SQLITE_BUDGET_SNAPSHOT_LINE_DDL
        )
        for _idx_ddl in SQLITE_BUDGET_SNAPSHOT_INDEXES:
            conn.execute(text(_idx_ddl))
