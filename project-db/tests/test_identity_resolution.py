"""Tests for identity resolution and entity matchers.

The matcher API is `find_match(session, entity_class, candidate_attrs) -> entity | None`
(searches the session for a match), not a pairwise score function. The resolver
exposes resolve_or_create, lookup_external, and get_external_ids.
"""

from __future__ import annotations

import pytest
from sqlalchemy.orm import Session

from project_db.db.models import Client, ExternalId, Project, SourceSystem
from project_db.db.models.work import ProjectStatus
from project_db.identity import (
    ExactFieldMatcher,
    FuzzyFieldMatcher,
    IdentityResolver,
    ProjectMatcher,
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


class TestProjectMatcher:
    """ProjectMatcher is deterministic: civic number, then exact normalized
    name -- each on a UNIQUE hit only.  No substring, no fuzzy, no guessing."""

    @staticmethod
    def _project(session: Session, client, name: str) -> Project:
        p = Project(name=name, status=ProjectStatus.ACTIVE, client_id=client.canonical_id)
        session.add(p)
        session.flush()
        return p

    def test_civic_number_match(self, session: Session, client_factory):
        """Monday board '5768-5770 St Laurent' matches Drive '5768 St-Laurent'."""
        c = client_factory(name="C")
        drive = self._project(session, c, "5768 St-Laurent")

        result = ProjectMatcher().find_match(
            session=session,
            entity_class=Project,
            candidate_attrs={"name": "5768-5770 St Laurent"},
        )
        assert result is not None
        assert result.canonical_id == drive.canonical_id

    def test_exact_name_match_when_no_civic(self, session: Session, client_factory):
        c = client_factory(name="C")
        drive = self._project(session, c, "Cherrier")

        result = ProjectMatcher().find_match(
            session=session,
            entity_class=Project,
            candidate_attrs={"name": "Cherrier"},
        )
        assert result is not None
        assert result.canonical_id == drive.canonical_id

    def test_no_substring_match(self, session: Session, client_factory):
        """'Bates' must NOT match '183 Chemin Bates' -- substring matching is
        the exact bug this rebuild removed."""
        c = client_factory(name="C")
        self._project(session, c, "183 Chemin Bates")

        result = ProjectMatcher().find_match(
            session=session,
            entity_class=Project,
            candidate_attrs={"name": "Bates"},
        )
        assert result is None

    def test_different_civic_never_matches(self, session: Session, client_factory):
        """927 must never match 923 -- the precise mislink the rebuild fixes."""
        c = client_factory(name="C")
        self._project(session, c, "923 Rockland (3rd Floor unit)")

        result = ProjectMatcher().find_match(
            session=session,
            entity_class=Project,
            candidate_attrs={"name": "927 Rockland (Ground Floor unit)"},
        )
        assert result is None

    def test_ambiguous_civic_does_not_guess(self, session: Session, client_factory):
        """Two projects share civic 5768 -> ambiguous -> no civic match; the
        name pass also fails -> None.  The matcher never guesses between them."""
        c = client_factory(name="C")
        self._project(session, c, "5768 St-Laurent")
        self._project(session, c, "5768 Other Street")

        result = ProjectMatcher().find_match(
            session=session,
            entity_class=Project,
            candidate_attrs={"name": "5768 Elsewhere"},
        )
        assert result is None

    def test_no_projects_returns_none(self, session: Session):
        result = ProjectMatcher().find_match(
            session=session,
            entity_class=Project,
            candidate_attrs={"name": "Anything"},
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


class TestResolverCreateOnlyAttrs:
    def test_create_only_field_not_overwritten_on_update(self, session: Session, org):
        """A create-only attr is set at creation but never overwritten when the
        same external record re-syncs -- e.g. a Drive-owned project name that
        a later Monday sync must not rename."""
        resolver = IdentityResolver(session)
        first = resolver.resolve_or_create(
            source=SourceSystem.GOOGLE_DRIVE,
            external_key="folder:abc",
            external_url=None,
            entity_class=Client,
            attrs={"name": "Drive Name", "organization_id": org.canonical_id},
        )
        second = resolver.resolve_or_create(
            source=SourceSystem.GOOGLE_DRIVE,
            external_key="folder:abc",
            external_url=None,
            entity_class=Client,
            attrs={"name": "Changed Name", "organization_id": org.canonical_id},
            create_only_attrs={"name"},
        )
        assert second.entity.canonical_id == first.entity.canonical_id
        assert second.entity.name == "Drive Name"  # create-only -> NOT overwritten

    def test_non_create_only_field_still_updates(self, session: Session, org):
        """Fields outside create_only_attrs update normally."""
        resolver = IdentityResolver(session)
        resolver.resolve_or_create(
            source=SourceSystem.MONDAY,
            external_key="m1",
            external_url=None,
            entity_class=Client,
            attrs={
                "name": "N",
                "email": "old@x.com",
                "organization_id": org.canonical_id,
            },
        )
        second = resolver.resolve_or_create(
            source=SourceSystem.MONDAY,
            external_key="m1",
            external_url=None,
            entity_class=Client,
            attrs={
                "name": "N",
                "email": "new@x.com",
                "organization_id": org.canonical_id,
            },
            create_only_attrs={"name"},
        )
        assert second.entity.email == "new@x.com"

    def test_matched_entity_receives_attrs(self, session: Session, org):
        """When the matcher (not exact-id) finds an existing entity, the
        incoming attrs ARE applied to it.

        This is the exact path `rebuild` relies on: it wipes ExternalId rows,
        so every preserved row misses Step 1 and is found by the matcher in
        Step 2.  If Step 2 did not apply attrs, a rebuild would leave every
        Document unlinked -- the bug this test guards against.
        """
        resolver = IdentityResolver(session)
        first = resolver.resolve_or_create(
            source=SourceSystem.MONDAY,
            external_key="m1",
            external_url=None,
            entity_class=Client,
            attrs={
                "name": "Acme",
                "email": "old@x.com",
                "organization_id": org.canonical_id,
            },
        )
        # Simulate `rebuild`: drop the ExternalId, keep the Client row.
        session.query(ExternalId).delete()
        session.flush()
        # Re-sync: Step 1 misses, the matcher matches by name, and the new
        # email MUST land on the matched row.
        second = resolver.resolve_or_create(
            source=SourceSystem.MONDAY,
            external_key="m1",
            external_url=None,
            entity_class=Client,
            attrs={
                "name": "Acme",
                "email": "new@x.com",
                "organization_id": org.canonical_id,
            },
            matcher=ExactFieldMatcher(["name"]),
        )
        assert second.was_matched is True
        assert second.entity.canonical_id == first.entity.canonical_id
        assert second.entity.email == "new@x.com"


class TestIdentityResolverDeduplication:
    def test_multisource_dedup_same_external_keys_different_sources(self, session: Session, org):
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

    def test_prevents_duplicate_external_id_rows(self, session: Session, org, client_factory):
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
