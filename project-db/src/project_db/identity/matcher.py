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
from difflib import SequenceMatcher
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


class FuzzyFieldMatcher(EntityMatcher):
    """Match if a string field is similar above a similarity threshold.

    Uses difflib.SequenceMatcher (case-insensitive). 1.0 = identical, 0.0 = no
    overlap. Threshold of 0.85 is a reasonable default for names; 0.75 tolerates
    suffix differences like "Acme Corp" vs "Acme Corporation Inc".
    """

    def __init__(self, fields: list[str], threshold: float = 0.85):
        self.fields = fields
        self.threshold = threshold

    def find_match(
        self,
        *,
        session: Session,
        entity_class: Type[T],
        candidate_attrs: dict[str, Any],
    ) -> T | None:
        for f in self.fields:
            if f not in candidate_attrs or candidate_attrs[f] is None:
                return None

        best: T | None = None
        best_score = 0.0
        for row in session.query(entity_class).all():
            score = 1.0
            for f in self.fields:
                candidate = candidate_attrs[f]
                existing = getattr(row, f, None)
                if existing is None:
                    score = 0.0
                    break
                if isinstance(candidate, str) and isinstance(existing, str):
                    s = SequenceMatcher(None, candidate.lower(), existing.lower()).ratio()
                else:
                    s = 1.0 if candidate == existing else 0.0
                score = min(score, s)
            if score >= self.threshold and score > best_score:
                best = row
                best_score = score
        return best


# Suggested default matchers per entity. Tweak as real data reveals weirdness.
DEFAULT_MATCHERS: dict[str, EntityMatcher] = {
    "Client": ExactFieldMatcher(["name"]),
    "Vendor": ExactFieldMatcher(["name"]),
    "Property": ExactFieldMatcher(["address"]),
    "User": ExactFieldMatcher(["email"]),
}
