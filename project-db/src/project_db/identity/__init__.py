"""Identity resolution layer — canonical ID strategy."""
from project_db.identity.matcher import (
    DEFAULT_MATCHERS,
    EntityMatcher,
    ExactFieldMatcher,
    NoMatcher,
)
from project_db.identity.resolver import IdentityResolver, ResolveResult

__all__ = [
    "DEFAULT_MATCHERS",
    "EntityMatcher",
    "ExactFieldMatcher",
    "IdentityResolver",
    "NoMatcher",
    "ResolveResult",
]
