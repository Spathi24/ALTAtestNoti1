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
    FOREIGN KEY (project_id) REFERENCES project(canonical_id),
    FOREIGN KEY (document_id) REFERENCES document(canonical_id) ON DELETE CASCADE
)
"""

# Columns added AFTER the initial financial_record DDL shipped.
SQLITE_FINANCIAL_RECORD_COLUMNS: dict[str, str] = {
    "amount_verified": "BOOLEAN",
    "is_rollup": "BOOLEAN",
}

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
    FOREIGN KEY (project_id) REFERENCES project(canonical_id),
    FOREIGN KEY (document_id) REFERENCES document(canonical_id) ON DELETE CASCADE
)
"""

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

# Columns added to worker after initial DDL (role/tags/verified for PM categorization).
SQLITE_WORKER_COLUMNS: dict[str, str] = {
    "role": "VARCHAR",
    "tags": "VARCHAR",
    "verified": "BOOLEAN NOT NULL DEFAULT 0",
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
            conn, tables, "contract_obligation", SQLITE_CONTRACT_OBLIGATION_DDL
        )
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
