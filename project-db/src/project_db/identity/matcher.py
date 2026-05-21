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

import re
import unicodedata
from abc import ABC, abstractmethod
from difflib import SequenceMatcher
from typing import Any, Type, TypeVar

from sqlalchemy.orm import Session

T = TypeVar("T")


# ---------------------------------------------------------------------------
# Name / civic-number helpers (used by ProjectMatcher; importable elsewhere)
# ---------------------------------------------------------------------------


def normalize_name(name: str) -> str:
    """Lowercase, strip accents + punctuation, collapse whitespace.

    '5768-5770 St. Laurent (Reno)' -> '5768 5770 st laurent reno'
    """
    name = unicodedata.normalize("NFKD", name or "").encode("ascii", "ignore").decode()
    name = name.lower()
    name = re.sub(r"[^\w\s]", " ", name)      # punctuation -> space
    name = re.sub(r"\s+", " ", name).strip()  # collapse whitespace
    return name


# Civic numbers in this portfolio are 3-5 digits.  Requiring 3+ digits is
# load-bearing: it rejects section-header folders ("01. PROJECTS") AND
# lead-tracking prefixes ("25-1001 580 Rue Viau" -> the "25" is dropped, so
# two different leads never collide on a spurious shared "25").
_CIVIC_NUMBER_RE = re.compile(r"^\s*(\d{3,5})(?:[-\s]+(\d{3,5}))?\b")


def extract_civic_numbers(name: str) -> set[str]:
    """Pull leading civic number(s) from an address-like name.

    '1455 Rue St. Mathieu'        -> {'1455'}
    '5768-5770 St Laurent'        -> {'5768', '5770'}
    '923 Rockland (3rd Floor)'    -> {'923'}
    'Cherrier' / '25-1001 ...'    -> set()   (no 3-5 digit leading number)
    """
    m = _CIVIC_NUMBER_RE.match(name or "")
    if not m:
        return set()
    nums = {m.group(1)}
    if m.group(2):
        nums.add(m.group(2))
    return nums


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


class ProjectMatcher(EntityMatcher):
    """Match a Project record from one source onto an existing canonical Project.

    Used when a Monday board needs to attach to a Project the Drive
    connector already created from a folder.

    CONTRACT -- this matcher returns exactly one of:
      * a single confident match (one Project, by a deterministic key)
      * no match (None)
    It MUST NOT be extended to rank, score, prefer, guess, or fall back to
    fuzzy / substring logic.  Substring matching is precisely the bug that
    mis-linked 927 Rockland's files onto "Rockland".  If a future change
    seems to need "smarter" matching, the correct move is to surface the
    ambiguity in `doctor` -- never to guess here.

    It checks two deterministic identity keys; each is exact and accepted
    only on a UNIQUE hit:
      1. Civic number -- if EXACTLY ONE existing Project shares a civic
         number with the candidate, that is the match.  0 or 2+ hits is
         not a civic match (a civic shared across streets stays ambiguous).
      2. Exact normalized-name equality -- "923 rockland" == "923 rockland",
         accepted only when exactly one Project matches.

    Anything not uniquely identified returns None: the resolver creates a
    new Project and `doctor` surfaces it.  A wrong auto-merge silently
    destroys data, so the bias is always "don't merge".
    """

    def find_match(
        self,
        *,
        session: Session,
        entity_class: Type[T],
        candidate_attrs: dict[str, Any],
    ) -> T | None:
        cand_name = candidate_attrs.get("name")
        if not cand_name or not isinstance(cand_name, str):
            return None

        existing = session.query(entity_class).all()

        # Pass 1: civic-number match, must be unambiguous.
        cand_civics = extract_civic_numbers(cand_name)
        if cand_civics:
            hits = [
                p for p in existing
                if extract_civic_numbers(getattr(p, "name", "") or "") & cand_civics
            ]
            if len(hits) == 1:
                return hits[0]
            # 0 or 2+ -> do not guess; fall through to name matching.

        # Pass 2: exact normalized-name equality, must be unambiguous.
        cand_norm = normalize_name(cand_name)
        if cand_norm:
            name_hits = [
                p for p in existing
                if normalize_name(getattr(p, "name", "") or "") == cand_norm
            ]
            if len(name_hits) == 1:
                return name_hits[0]

        return None
