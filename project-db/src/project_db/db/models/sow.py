"""Scope of Work: SowPackage (per-trade tendering package) and SowItem (one
scope line within a package).

Phase 3 of the financial refoundation (see docs/REFOUNDATION_BUILD_NOTES.md).
Scope only -- no cost, no quote, no PO, no ledger mutation. SowItem is
deliberately COARSER than FinancialLineItem: one SowItem may later be
referenced by many FinancialLineItem rows (via FinancialLineItem.sow_item_id,
added in Phase 4). Do not conflate the two.

The SOW is the contract boundary (owner's words): presented to the client to
justify cost, presented to subs so they can quote. Work outside the SOW
becomes a ChangeOrder (Phase 6+), never silently absorbed.
"""

from __future__ import annotations

from sqlalchemy import (
    Boolean,
    Column,
    ForeignKey,
    Index,
    Numeric,
    String,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import UUID

from project_db.db.base import Base, CanonicalMixin

# Package lifecycle -- mirrors the settled quote/PO vocabulary
# (pending -> recommended -> selected/rejected -> awarded), applied here to
# "has this trade's tendering gone out and come back yet."
SOW_PACKAGE_STATUSES = {"draft", "issued", "quoting", "awarded"}


class SowPackage(Base, CanonicalMixin):
    """One subcontractor trade package (e.g. "22-Plumbing") carved out of a
    project's SOW for tendering.
    """

    project_id = Column(
        UUID(as_uuid=True),
        ForeignKey("project.canonical_id"),
        nullable=False,
    )

    division_code = Column(String, nullable=False, default="99")  # CSI code, e.g. "22"
    trade_name = Column(String, nullable=True)  # e.g. "Plumbing"
    title = Column(String, nullable=True)  # display name, e.g. "22-Plumbing"
    status = Column(String, nullable=False, default="draft")

    drawings_refs_json = Column(Text, nullable=True)  # JSON array of drawing/DWG refs
    source_meta_json = Column(Text, nullable=True)  # raw parser row, kept for audit


class SowItem(Base, CanonicalMixin):
    """One scope line within a SOW -- what is (or isn't) included, and the
    material spec that drives it. Scope, not cost.

    Usually belongs to a SowPackage (a subcontractor trade). package_id is
    nullable for division-01 General Requirements items (site supervision,
    overhead/profit, deliveries) that are GC overhead, not a subcontracted
    trade -- there is no PKG/QUOTE file for those.
    """

    project_id = Column(
        UUID(as_uuid=True),
        ForeignKey("project.canonical_id"),
        nullable=False,
    )
    # Nullable: division 01 (General Requirements) items belong to the SOW but
    # to no subcontractor package -- there is no PKG/QUOTE file for GC overhead
    # (see docs/templates/NAMING_CONVENTIONS.md, "Division 01" note). A NULL
    # package_id is a real, intentional state, not missing data.
    package_id = Column(
        UUID(as_uuid=True),
        ForeignKey("sow_package.canonical_id"),
        nullable=True,
    )

    # Human-facing scope item code, e.g. "SOW-025". Structural join key for
    # Quote_Lines.SOW_Item_Ref in Phase 4 -- never parsed out of Notes text.
    # MUST resolve unambiguously within a project (a quote line's SOW_Item_Ref
    # carries only "SOW-025", no package context), so uniqueness is scoped to
    # (project_id, item_code), NOT (project, package) -- see __table_args__.
    item_code = Column(String, nullable=True)
    description = Column(Text, nullable=True)
    division_code = Column(String, nullable=False, default="99")  # CSI code
    included = Column(Boolean, nullable=False, default=True)  # False = explicit exclusion
    material_spec = Column(Text, nullable=True)  # JSON: material/spec details
    quantity = Column(Numeric(14, 2), nullable=True)
    unit = Column(String, nullable=True)
    assumptions = Column(Text, nullable=True)
    exclusions = Column(Text, nullable=True)

    source_meta_json = Column(Text, nullable=True)  # raw parser row, kept for audit

    __table_args__ = (
        # item_code is unique PER PROJECT when set. Scoping to the project (not
        # the package) makes SOW_Item_Ref a clean structural join key: a quote
        # line references only "SOW-025", so "SOW-025" must identify exactly one
        # scope item in the project. A partial index (WHERE item_code IS NOT
        # NULL) leaves the code optional -- and, critically, closes the hole a
        # plain UniqueConstraint would leave for division-01 items where
        # package_id IS NULL (NULLs compare distinct, so a package-scoped
        # constraint would let duplicate null-package codes through).
        Index(
            "uq_sow_item_project_item_code",
            "project_id",
            "item_code",
            unique=True,
            sqlite_where=text("item_code IS NOT NULL"),
            postgresql_where=text("item_code IS NOT NULL"),
        ),
    )
