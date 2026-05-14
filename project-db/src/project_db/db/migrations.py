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
    "owner_email": "VARCHAR",
    "is_trashed": "BOOLEAN NOT NULL DEFAULT 0",
    "source_meta_json": "TEXT",
}


def _add_missing_columns(conn, inspector, table: str, columns: dict[str, str]) -> None:
    existing = {col["name"] for col in inspector.get_columns(table)}
    for name, ddl_type in columns.items():
        if name not in existing:
            conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {name} {ddl_type}"))


def ensure_sqlite_schema(engine) -> None:
    """Add nullable compatibility columns to existing SQLite files."""
    if engine.dialect.name != "sqlite":
        return
    inspector = inspect(engine)
    tables = set(inspector.get_table_names())
    with engine.begin() as conn:
        if "task" in tables:
            _add_missing_columns(conn, inspector, "task", SQLITE_TASK_COLUMNS)
        if "document" in tables:
            _add_missing_columns(conn, inspector, "document", SQLITE_DOCUMENT_COLUMNS)
