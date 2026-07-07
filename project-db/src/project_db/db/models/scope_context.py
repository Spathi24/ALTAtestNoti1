"""ScopeContext -- a coherent scope boundary WITHIN a project (site / unit /
area / phase / contract scope).

SC-1 of the ScopeContext migration
(docs/architecture/SCOPECONTEXT_TRANSITION_PLAN.md). A Project may hold several
ScopeContexts (the pilot 2026001 "923-927 Rockland" is three: 923 interior, 927
unit, exterior). Contexts are additive/parallel -- NOT revisions of each other,
and NOT isolated sub-projects (employees, materials and financing flow freely
across them; contexts partition SCOPE/AUTHORITY, not cost-sharing).

Authority (which SOW/source wins for a given role) is resolved WITHIN a
(context, document_role) and therefore belongs to a future SowVersion/source,
NOT to this row -- so there is deliberately no `authority_state` here.

SC-1 is additive/foundational: this table + two Document columns
(`scope_context_id`, `context_resolution_state`). No other table gets a context
FK yet; scope/quote/budget/finance inherit context in their own later slices
once their ownership model is settled.
"""

from __future__ import annotations

from sqlalchemy import Column, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID

from project_db.db.base import Base, CanonicalMixin

# A Document's context-resolution state. Plain strings (schema-light style), not
# a DB enum. NULL scope_context_id is NOT self-describing: LEGACY_UNSCOPED
# (pre-existing / not-yet-migrated) must stay observably distinct from
# UNRESOLVED (quarantine -- we tried to bind and could not). RESOLVED implies a
# non-NULL scope_context_id; NOT_APPLICABLE is for documents that legitimately
# belong to no single context.
CONTEXT_RESOLUTION_STATES = (
    "LEGACY_UNSCOPED",
    "RESOLVED",
    "UNRESOLVED",
    "NOT_APPLICABLE",
)


class ScopeContext(Base, CanonicalMixin):
    project_id = Column(
        UUID(as_uuid=True),
        ForeignKey("project.canonical_id"),
        nullable=False,
    )
    # Stable, project-scoped identity, e.g. "923_INTERIOR". Idempotent creation
    # keys on (project_id, context_key); the human `label` may change without
    # creating a new semantic context.
    context_key = Column(String, nullable=False)
    label = Column(String, nullable=True)  # mutable display, e.g. "923 Rockland -- Interior"
    kind = Column(String, nullable=True)  # site | unit | area | phase | contract (free string)
    site = Column(String, nullable=True)
    unit_area = Column(String, nullable=True)
    phase = Column(String, nullable=True)
    source_meta_json = Column(Text, nullable=True)  # raw provenance, kept for audit

    __table_args__ = (
        UniqueConstraint("project_id", "context_key", name="uq_scope_context_project_key"),
    )
