"""Tests for identity resolution and entity matchers.

The matcher API is `find_match(session, entity_class, candidate_attrs) -> entity | None`
(searches the session for a match), not a pairwise score function. The resolver
exposes resolve_or_create, lookup_external, and get_external_ids.
"""
from __future__ import annotations

import pytest
from sqlalchemy.orm import Session

from project_db.db.models import Client, ExternalId, SourceSystem
from project_db.identity import (
    ExactFieldMatcher,
    FuzzyFieldMatcher,
    IdentityResolver,
    NoMatcher,
)


# =====================================================================
# Matchers
# =====================================================================


class TestExactFieldMatcher:
    def test_match_finds_existing_client_by_name(self, session: Session, client_factory):
        client_factory(name="Acme Corp")
        matcher = ExactFieldMatcher(["name"])

        result = matcher.find_match(
            session=session,
            entity_class=Client,
            candidate_attrs={"name": "Acme Corp"},
        )
        assert result is not None
        assert result.name == "Acme Corp"

    def test_match_returns_none_when_no_match(self, session: Session, client_factory):
        client_factory(name="Acme Corp")
        matcher = ExactFieldMatcher(["name"])

        result = matcher.find_match(
            session=session,
            entity_class=Client,
            candidate_attrs={"name": "Different Co"},
        )
        assert result is None

    def test_match_multi_field_requires_all(self, session: Session, client_factory):
        client_factory(name="Acme Corp", email="acme@example.com")
        matcher = ExactFieldMatcher(["name", "email"])

        match = matcher.find_match(
            session=session,
            entity_class=Client,
            candidate_attrs={"name": "Acme Corp", "email": "acme@example.com"},
        )
        assert match is not None

        no_match = matcher.find_match(
            session=session,
            entity_class=Client,
            candidate_attrs={"name": "Acme Corp", "email": "wrong@example.com"},
        )
        assert no_match is None

    def test_match_returns_none_on_ambiguous(self, session: Session, client_factory):
        # Two clients with the same name → ambiguous, don't auto-merge.
        client_factory(name="Acme Corp", email="a@example.com")
        client_factory(name="Acme Corp", email="b@example.com")
        matcher = ExactFieldMatcher(["name"])

        result = matcher.find_match(
            session=session,
            entity_class=Client,
            candidate_attrs={"name": "Acme Corp"},
        )
        assert result is None


class TestFuzzyFieldMatcher:
    def test_match_similar_name(self, session: Session, client_factory):
        client_factory(name="Acme Corporation")
        matcher = FuzzyFieldMatcher(["name"], threshold=0.75)

        result = matcher.find_match(
            session=session,
            entity_class=Client,
            candidate_attrs={"name": "Acme Corporation Inc"},
        )
        assert result is not None

    def test_no_match_very_different(self, session: Session, client_factory):
        client_factory(name="Acme Corp")
        matcher = FuzzyFieldMatcher(["name"], threshold=0.85)

        result = matcher.find_match(
            session=session,
            entity_class=Client,
            candidate_attrs={"name": "Unrelated Inc"},
        )
        assert result is None


# =====================================================================
# Resolver
# =====================================================================


class TestIdentityResolverBasics:
    def test_resolve_or_create_new_entity(self, session: Session, org):
        resolver = IdentityResolver(session)

        result = resolver.resolve_or_create(
            source=SourceSystem.MONDAY,
            external_key="monday_item_123",
            external_url=None,
            entity_class=Client,
            attrs={"name": "Acme Corp", "organization_id": org.canonical_id},
        )

        assert result.was_created is True
        assert result.was_matched is False
        assert result.entity.name == "Acme Corp"
        assert result.entity.canonical_id is not None

    def test_resolve_finds_existing_by_external_id(self, session: Session, org):
        # First sync creates the entity + external id.
        resolver = IdentityResolver(session)
        first = resolver.resolve_or_create(
            source=SourceSystem.MONDAY,
            external_key="monday_item_123",
            external_url=None,
            entity_class=Client,
            attrs={"name": "Acme Corp", "organization_id": org.canonical_id},
        )

        # Second sync with same external_key returns the same entity, updates fields.
        second = resolver.resolve_or_create(
            source=SourceSystem.MONDAY,
            external_key="monday_item_123",
            external_url=None,
            entity_class=Client,
            attrs={"name": "Acme Corp Updated", "organization_id": org.canonical_id},
        )

        assert second.was_created is False
        assert second.was_matched is False  # exact match, not fuzzy
        assert second.entity.canonical_id == first.entity.canonical_id
        assert second.entity.name == "Acme Corp Updated"


class TestIdentityResolverMatching:
    def test_resolve_matches_by_exact_name(self, session: Session, org, client_factory):
        existing = client_factory(name="Acme Corp", email="acme@example.com")

        resolver = IdentityResolver(session)
        result = resolver.resolve_or_create(
            source=SourceSystem.QUICKBOOKS,
            external_key="qb_cust_456",
            external_url=None,
            entity_class=Client,
            attrs={
                "name": "Acme Corp",
                "email": "acme@example.com",
                "organization_id": org.canonical_id,
            },
            matcher=ExactFieldMatcher(["name"]),
        )

        assert result.was_matched is True
        assert result.entity.canonical_id == existing.canonical_id

    def test_resolve_falls_back_to_create_when_no_match(self, session: Session, org):
        resolver = IdentityResolver(session)
        result = resolver.resolve_or_create(
            source=SourceSystem.MONDAY,
            external_key="monday_789",
            external_url=None,
            entity_class=Client,
            attrs={"name": "New Client", "organization_id": org.canonical_id},
            matcher=ExactFieldMatcher(["name"]),
        )
        assert result.was_created is True
        assert result.was_matched is False


class TestIdentityResolverDeduplication:
    def test_multisource_dedup_same_external_keys_different_sources(
        self, session: Session, org
    ):
        resolver = IdentityResolver(session)

        # Same client from two sources, matched by name.
        monday = resolver.resolve_or_create(
            source=SourceSystem.MONDAY,
            external_key="monday_123",
            external_url=None,
            entity_class=Client,
            attrs={"name": "Acme Corp", "organization_id": org.canonical_id},
            matcher=ExactFieldMatcher(["name"]),
        )
        qb = resolver.resolve_or_create(
            source=SourceSystem.QUICKBOOKS,
            external_key="qb_456",
            external_url=None,
            entity_class=Client,
            attrs={"name": "Acme Corp", "organization_id": org.canonical_id},
            matcher=ExactFieldMatcher(["name"]),
        )

        # Same canonical entity, two ExternalId rows.
        assert qb.entity.canonical_id == monday.entity.canonical_id
        ext_ids = resolver.get_external_ids(canonical_id=monday.entity.canonical_id)
        assert len(ext_ids) == 2
        sources = {e.source for e in ext_ids}
        assert sources == {SourceSystem.MONDAY, SourceSystem.QUICKBOOKS}

    def test_prevents_duplicate_external_id_rows(
        self, session: Session, org, client_factory
    ):
        """Two ExternalId rows with the same (source, entity_type, external_key)
        violate the composite unique constraint."""
        from sqlalchemy.exc import IntegrityError

        c1 = client_factory(name="Client 1")
        c2 = client_factory(name="Client 2")

        session.add(
            ExternalId(
                source=SourceSystem.MONDAY,
                entity_type="Client",
                external_key="monday_123",
                canonical_id=c1.canonical_id,
            )
        )
        session.commit()

        session.add(
            ExternalId(
                source=SourceSystem.MONDAY,
                entity_type="Client",
                external_key="monday_123",
                canonical_id=c2.canonical_id,
            )
        )
        with pytest.raises(IntegrityError):
            session.commit()


class TestResolverLookupHelpers:
    def test_lookup_external_finds_entity(self, session: Session, org):
        resolver = IdentityResolver(session)
        created = resolver.resolve_or_create(
            source=SourceSystem.MONDAY,
            external_key="monday_999",
            external_url=None,
            entity_class=Client,
            attrs={"name": "Lookup Me", "organization_id": org.canonical_id},
        )

        looked_up = resolver.lookup_external(
            source=SourceSystem.MONDAY,
            entity_class=Client,
            external_key="monday_999",
        )
        assert looked_up is not None
        assert looked_up.canonical_id == created.entity.canonical_id

    def test_lookup_external_returns_none_when_missing(self, session: Session):
        resolver = IdentityResolver(session)
        result = resolver.lookup_external(
            source=SourceSystem.MONDAY,
            entity_class=Client,
            external_key="never_synced",
        )
        assert result is None
