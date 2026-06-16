"""Identity resolution — translate (source, external_key) → canonical entity.

This is the core of the multi-source design. Every connector calls
`resolve_or_create` for each record it pulls. The resolver:

  1. Looks up ExternalId for (source, entity_type, external_key).
  2. If found → returns the existing canonical entity.
  3. If not found → optionally attempts a fuzzy match against existing
     canonical entities (e.g. matching a QuickBooks customer by name +
     billing address against existing Clients).
  4. If still no match → creates a new canonical entity and registers
     the ExternalId.

The matcher is pluggable: see `matcher.py`.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Any, TypeVar

from sqlalchemy.orm import Session

from project_db.db.models import ExternalId, SourceSystem
from project_db.identity.matcher import EntityMatcher, NoMatcher

logger = logging.getLogger(__name__)

T = TypeVar("T")


@dataclass
class ResolveResult:
    """What the resolver returns."""

    entity: Any  # the canonical entity (SQLAlchemy model)
    external_id_row: ExternalId
    was_created: bool  # True if we created a new canonical entity
    was_matched: bool  # True if we matched via fuzzy match (not exact)


class IdentityResolver:
    """Resolves source records to canonical entities and back."""

    def __init__(self, session: Session):
        self.session = session

    def resolve_or_create(
        self,
        *,
        source: SourceSystem,
        external_key: str,
        external_url: str | None,
        entity_class: type[T],
        attrs: dict[str, Any],
        matcher: EntityMatcher | None = None,
        payload_hash: str | None = None,
        create_only_attrs: set[str] | None = None,
    ) -> ResolveResult:
        """Main entrypoint. See module docstring.

        ``create_only_attrs`` names attributes applied only when the entity is
        first created -- never overwritten on a later sync of the same record.
        Use it for identity fields owned by one source: e.g. a Project's
        ``name`` is owned by its Drive folder, so a Monday sync must not
        rename it.
        """
        entity_type = entity_class.__name__
        matcher = matcher or NoMatcher()

        # Step 1: exact lookup by external id
        existing = (
            self.session.query(ExternalId)
            .filter_by(
                source=source,
                entity_type=entity_type,
                external_key=external_key,
            )
            .one_or_none()
        )
        if existing is not None:
            entity = (
                self.session.query(entity_class).filter_by(canonical_id=existing.canonical_id).one()
            )
            existing.last_synced_at = datetime.utcnow()
            if payload_hash is not None:
                existing.raw_payload_hash = payload_hash
            # Refresh URL — connectors occasionally change URL format
            # (e.g. v0.2 added board_id to Monday URLs).
            if external_url is not None and existing.external_url != external_url:
                existing.external_url = external_url
            # Update mutable attributes (skip create-only identity fields,
            # which belong to whichever source first created the row).
            for key, value in attrs.items():
                if create_only_attrs and key in create_only_attrs:
                    continue
                if hasattr(entity, key):
                    setattr(entity, key, value)
            return ResolveResult(
                entity=entity,
                external_id_row=existing,
                was_created=False,
                was_matched=False,
            )

        # Step 2: fuzzy match
        matched_entity = matcher.find_match(
            session=self.session,
            entity_class=entity_class,
            candidate_attrs=attrs,
        )
        was_matched = matched_entity is not None

        if matched_entity is None:
            # Step 3: create new canonical entity
            matched_entity = entity_class(**attrs)
            self.session.add(matched_entity)
            self.session.flush()  # populate canonical_id
            logger.info(
                "Created new %s canonical_id=%s from %s:%s",
                entity_type,
                matched_entity.canonical_id,
                source.value,
                external_key,
            )
        else:
            # Matched an existing canonical entity (another source, or a row
            # whose ExternalId was dropped by `rebuild`).  Apply the incoming
            # attrs so the canonical row reflects this source -- skipping
            # create-only identity fields, exactly as the exact-id path does.
            # Without this, a `rebuild` (which wipes ExternalId rows and so
            # forces every preserved Document down this matched path) would
            # never re-apply project_id / category, leaving every document
            # unlinked and uncategorised.
            for key, value in attrs.items():
                if create_only_attrs and key in create_only_attrs:
                    continue
                if hasattr(matched_entity, key):
                    setattr(matched_entity, key, value)

        # Register ExternalId
        ext = ExternalId(
            source=source,
            entity_type=entity_type,
            external_key=external_key,
            external_url=external_url,
            canonical_id=matched_entity.canonical_id,
            last_synced_at=datetime.utcnow(),
            raw_payload_hash=payload_hash,
        )
        self.session.add(ext)
        self.session.flush()

        return ResolveResult(
            entity=matched_entity,
            external_id_row=ext,
            was_created=not was_matched,
            was_matched=was_matched,
        )

    def lookup_external(
        self,
        *,
        source: SourceSystem,
        entity_class: type[T],
        external_key: str,
    ) -> T | None:
        """Lookup helper — returns the canonical entity or None."""
        ext = (
            self.session.query(ExternalId)
            .filter_by(
                source=source,
                entity_type=entity_class.__name__,
                external_key=external_key,
            )
            .one_or_none()
        )
        if ext is None:
            return None
        return (
            self.session.query(entity_class).filter_by(canonical_id=ext.canonical_id).one_or_none()
        )

    def get_external_ids(
        self,
        *,
        canonical_id: Any,
        entity_class: type[T] | None = None,
    ) -> list[ExternalId]:
        """All external IDs for a given canonical entity."""
        q = self.session.query(ExternalId).filter_by(canonical_id=canonical_id)
        if entity_class is not None:
            q = q.filter_by(entity_type=entity_class.__name__)
        return q.all()
