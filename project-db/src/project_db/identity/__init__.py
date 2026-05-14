"""Identity resolution layer -- canonical ID strategy."""
from project_db.identity.matcher import (
    EntityMatcher,
    ExactFieldMatcher,
    FuzzyFieldMatcher,
    NoMatcher,
)
from project_db.identity.resolver import IdentityResolver, ResolveResult

__all__ = [
    "EntityMatcher",
    "ExactFieldMatcher",
    "FuzzyFieldMatcher",
    "IdentityResolver",
    "NoMatcher",
    "ResolveResult",
]
