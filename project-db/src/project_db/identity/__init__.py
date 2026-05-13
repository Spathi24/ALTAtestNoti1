"""Identity resolution layer — canonical ID strategy."""
from project_db.identity.matcher import (
    DEFAULT_MATCHERS,
    EntityMatcher,
    ExactFieldMatcher,
    FuzzyFieldMatcher,
    NoMatcher,
)
from project_db.identity.resolver import IdentityResolver, ResolveResult

__all__ = [
    "DEFAULT_MATCHERS",
    "EntityMatcher",
    "ExactFieldMatcher",
    "FuzzyFieldMatcher",
    "IdentityResolver",
    "NoMatcher",
    "ResolveResult",
]
