"""Pluggable matchers for fuzzy entity dedup.

When a new record arrives from a source system and we have no exact ExternalId
hit, we may want to match it against existing canonical entities. Examples:

  - A QuickBooks Customer with the same name + billing_address as an
    existing Client probably IS that client.
  - A CompanyCam project named "923 Rockland — Reno" probably maps to the
    existing Property with address "923 Rockland".

Each matcher is a stateless object the resolver can call. Replace `NoMatcher`
with something smarter once you've seen real data shape.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Type, TypeVar

from sqlalchemy.orm import Session

T = TypeVar("T")


class EntityMatcher(ABC):
    """Returns an existing canonical entity if it looks like a match."""

    @abstractmethod
    def find_match(
        self,
        *,
        session: Session,
        entity_class: Type[T],
        candidate_attrs: dict[str, Any],
    ) -> T | None: ...


class NoMatcher(EntityMatcher):
    """Default: never match. Always creates new canonical entities.

    Safest starting point — humans can merge duplicates later. Once you have
    confidence in your data, swap in a smarter matcher per entity type.
    """

    def find_match(self, **_: Any) -> Any | None:
        return None


class ExactFieldMatcher(EntityMatcher):
    """Match if a specific set of fields is equal (case-insensitive for strings)."""

    def __init__(self, fields: list[str]):
        self.fields = fields

    def find_match(
        self,
        *,
        session: Session,
        entity_class: Type[T],
        candidate_attrs: dict[str, Any],
    ) -> T | None:
        filters = {}
        for f in self.fields:
            if f not in candidate_attrs or candidate_attrs[f] is None:
                return None
            filters[f] = candidate_attrs[f]
        # Case-insensitive name match for safety — most string fields here
        # are names / addresses.
        q = session.query(entity_class)
        for k, v in filters.items():
            col = getattr(entity_class, k)
            if isinstance(v, str):
                q = q.filter(col.ilike(v))
            else:
                q = q.filter(col == v)
        results = q.limit(2).all()
        if len(results) == 1:
            return results[0]
        # 0 results or 2+ ambiguous matches → don't auto-merge.
        return None


# Suggested default matchers per entity. Tweak as real data reveals weirdness.
DEFAULT_MATCHERS: dict[str, EntityMatcher] = {
    "Client": ExactFieldMatcher(["name"]),
    "Vendor": ExactFieldMatcher(["name"]),
    "Property": ExactFieldMatcher(["address"]),
    "User": ExactFieldMatcher(["email"]),
}
