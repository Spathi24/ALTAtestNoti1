"""Canonical design-phase roadmap.

A reusable template of the architect/designer-side workflow that every
project goes through: Schematic Design (SD) -> Design Development (DD)
-> Construction Documents (CD) -> Construction Administration (CA).

This is NOT project-specific data.  It's a SHARED reference that the AI
layer uses two ways:

1. **Scope-gap detection.**  When `propose scope` runs, the model
   compares the project's existing Monday tasks against this canonical
   roadmap and flags standard tasks that are missing.

2. **Timeline ordering.**  When `propose timelines` runs, the roadmap
   gives the model the canonical ORDER (SD before DD before CD before
   CA, with ordinals within each phase) so timeline proposals respect
   the natural sequence of work.

Source: imported from ``docs/Project Roadmap.xlsx`` via
``project_db import-roadmap``.  The xlsx is the editorial source of
truth; this table is its persisted projection.
"""
from __future__ import annotations

import enum

from sqlalchemy import Column, Enum as SAEnum, Integer, String, Text, UniqueConstraint

from project_db.db.base import Base, CanonicalMixin


class RoadmapPhase(str, enum.Enum):
    """The four canonical design phases.

    Order matters: SD < DD < CD < CA.  The AI layer uses this ordering
    as the "phase X cannot start before phase X-1 finishes" anchor in
    timeline proposals.
    """
    SD = "SD"   # Schematic Design
    DD = "DD"   # Design Development
    CD = "CD"   # Construction Documents
    CA = "CA"   # Construction Administration


class RoadmapActor(str, enum.Enum):
    """Who's primarily responsible for executing this roadmap task.

    The AI layer FILTERS the roadmap by actor before injecting it into
    proposal prompts -- our Monday boards are contractor-side, so a
    pure ARCHITECT task showing up as a "gap" is noise, not signal.
    BOTH is for kickoff / sign-off / submittal review style tasks
    where the contractor is genuinely co-responsible.
    """
    ARCHITECT = "ARCHITECT"
    CONTRACTOR = "CONTRACTOR"
    BOTH = "BOTH"


# Numeric ordering for sort comparisons.  Used by ai.roadmap helpers
# that need to ask "is this task in an earlier phase than that one?".
ROADMAP_PHASE_ORDER: dict[RoadmapPhase, int] = {
    RoadmapPhase.SD: 1,
    RoadmapPhase.DD: 2,
    RoadmapPhase.CD: 3,
    RoadmapPhase.CA: 4,
}


class RoadmapTask(Base, CanonicalMixin):
    """One canonical task in the design-phase roadmap.

    Identified by ``(phase, ordinal)`` so re-imports of the xlsx can
    update task names / sub-tasks in place without churning canonical
    UUIDs.  The CanonicalMixin's ``notes`` column carries the xlsx's
    Notes column when present.
    """

    __table_args__ = (
        # The xlsx is ordered: each phase's rows are in editorial order.
        # We carry that order via ``ordinal`` and pin it as unique within
        # a phase so re-imports are stable.
        UniqueConstraint("phase", "ordinal", name="uq_roadmap_phase_ordinal"),
    )

    phase = Column(SAEnum(RoadmapPhase), nullable=False)
    ordinal = Column(Integer, nullable=False)
    task_name = Column(String, nullable=False)
    # JSON-encoded list[str] of the bulleted sub-task items from the
    # xlsx's "Sub-tasks" column.  Stored as a JSON string (TEXT) for
    # portability across SQLite / Postgres.  None when the xlsx cell
    # was blank.
    sub_tasks_json = Column(Text, nullable=True)
    # Who's primarily responsible for this task.  Nullable -- a fresh
    # import has NULL here until ``project_db classify-roadmap`` runs
    # (Sonnet drafts; reviewer confirms).  The proposal-prompt
    # filter ignores NULL rows so we don't accidentally inject
    # unclassified tasks before review.
    actor = Column(SAEnum(RoadmapActor), nullable=True)
