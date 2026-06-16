"""Delivery-side entities: Project, Task, DailyLog."""

from __future__ import annotations

import enum

from sqlalchemy import Boolean, Column, Date, ForeignKey, Numeric, String, Text
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import UUID

from project_db.db.base import Base, CanonicalMixin


class ProjectStatus(str, enum.Enum):
    PROPOSED = "PROPOSED"
    ACTIVE = "ACTIVE"
    ON_HOLD = "ON_HOLD"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"


class TaskStatus(str, enum.Enum):
    TODO = "TODO"
    IN_PROGRESS = "IN_PROGRESS"
    BLOCKED = "BLOCKED"
    DONE = "DONE"
    CANCELLED = "CANCELLED"


class Project(Base, CanonicalMixin):
    name = Column(String, nullable=False)
    code = Column(String, nullable=True)
    status = Column(SAEnum(ProjectStatus), nullable=False, default=ProjectStatus.PROPOSED)
    start_date = Column(Date, nullable=True)
    end_date = Column(Date, nullable=True)
    budget_amount = Column(Numeric(12, 2), nullable=True)
    contract_amount = Column(Numeric(12, 2), nullable=True)

    client_id = Column(
        UUID(as_uuid=True),
        ForeignKey("client.canonical_id"),
        nullable=False,
    )
    deal_id = Column(
        UUID(as_uuid=True),
        ForeignKey("deal.canonical_id"),
        nullable=True,
    )
    property_id = Column(
        UUID(as_uuid=True),
        ForeignKey("property.canonical_id"),
        nullable=True,
    )
    project_manager_id = Column(
        UUID(as_uuid=True),
        ForeignKey("user.canonical_id"),
        nullable=True,
    )


class Task(Base, CanonicalMixin):
    title = Column(String, nullable=False)
    status = Column(SAEnum(TaskStatus), nullable=False, default=TaskStatus.TODO)
    monday_status_label = Column(String, nullable=True)
    priority = Column(String, nullable=True)
    group_title = Column(String, nullable=True)
    start_date = Column(Date, nullable=True)
    end_date = Column(Date, nullable=True)
    due_date = Column(Date, nullable=True)
    duration_days = Column(Numeric(10, 2), nullable=True)
    planned_effort = Column(Numeric(10, 2), nullable=True)
    effort_spent = Column(Numeric(10, 2), nullable=True)
    subcontractor = Column(String, nullable=True)
    supplier = Column(String, nullable=True)
    completed_at = Column(Date, nullable=True)
    is_subitem = Column(Boolean, nullable=False, default=False)
    source_columns_json = Column(Text, nullable=True)

    project_id = Column(
        UUID(as_uuid=True),
        ForeignKey("project.canonical_id"),
        nullable=False,
    )
    assignee_id = Column(
        UUID(as_uuid=True),
        ForeignKey("user.canonical_id"),
        nullable=True,
    )
    parent_task_id = Column(
        UUID(as_uuid=True),
        ForeignKey("task.canonical_id"),
        nullable=True,
    )


class DailyLog(Base, CanonicalMixin):
    log_date = Column(Date, nullable=False)
    summary = Column(String, nullable=True)

    project_id = Column(
        UUID(as_uuid=True),
        ForeignKey("project.canonical_id"),
        nullable=False,
    )
    author_id = Column(
        UUID(as_uuid=True),
        ForeignKey("user.canonical_id"),
        nullable=True,
    )
