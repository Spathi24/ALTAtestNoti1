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


def ensure_sqlite_schema(engine) -> None:
    """Add nullable compatibility columns to existing SQLite files."""
    if engine.dialect.name != "sqlite":
        return
    inspector = inspect(engine)
    if "task" not in inspector.get_table_names():
        return

    existing = {col["name"] for col in inspector.get_columns("task")}
    with engine.begin() as conn:
        for name, ddl_type in SQLITE_TASK_COLUMNS.items():
            if name not in existing:
                conn.execute(text(f"ALTER TABLE task ADD COLUMN {name} {ddl_type}"))
