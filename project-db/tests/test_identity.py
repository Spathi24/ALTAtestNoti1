"""Basic smoke tests for identity resolution.

Run with: pytest -q
"""
from __future__ import annotations

import os

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Force in-memory sqlite before importing the app
os.environ["PROJECT_DB_URL"] = "sqlite:///:memory:"

from project_db.db.base import Base
from project_db.db.models import Client, Organization, SourceSystem
from project_db.identity import ExactFieldMatcher, IdentityResolver


@pytest.fixture()
def session():
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    s = Session()
    org = Organization(name="Test Org")
    s.add(org)
    s.commit()
    s.org_id = org.canonical_id  # type: ignore[attr-defined]
    yield s
    s.close()


def test_resolve_creates_new_entity(session):
    r = IdentityResolver(session)
    result = r.resolve_or_create(
        source=SourceSystem.MONDAY,
        external_key="123",
        external_url=None,
        entity_class=Client,
        attrs={"name": "Acme", "organization_id": session.org_id},
    )
    assert result.was_created
    assert not result.was_matched
    assert result.entity.name == "Acme"


def test_resolve_is_idempotent(session):
    r = IdentityResolver(session)
    a = r.resolve_or_create(
        source=SourceSystem.MONDAY,
        external_key="123",
        external_url=None,
        entity_class=Client,
        attrs={"name": "Acme", "organization_id": session.org_id},
    )
    session.commit()
    b = r.resolve_or_create(
        source=SourceSystem.MONDAY,
        external_key="123",
        external_url=None,
        entity_class=Client,
        attrs={"name": "Acme Updated", "organization_id": session.org_id},
    )
    assert a.entity.canonical_id == b.entity.canonical_id
    assert not b.was_created
    # Mutable fields update on re-sync
    assert b.entity.name == "Acme Updated"


def test_fuzzy_match_links_two_sources(session):
    """Same Client exists in Monday and QuickBooks under different IDs but
    same name. The matcher should link them to one canonical entity."""
    r = IdentityResolver(session)

    monday = r.resolve_or_create(
        source=SourceSystem.MONDAY,
        external_key="m-123",
        external_url=None,
        entity_class=Client,
        attrs={"name": "Acme Corp", "organization_id": session.org_id},
    )
    session.commit()

    qb = r.resolve_or_create(
        source=SourceSystem.QUICKBOOKS,
        external_key="qb-999",
        external_url=None,
        entity_class=Client,
        attrs={"name": "Acme Corp", "organization_id": session.org_id},
        matcher=ExactFieldMatcher(["name"]),
    )
    assert qb.was_matched
    assert not qb.was_created
    assert qb.entity.canonical_id == monday.entity.canonical_id

    # Both external IDs should now point at the same canonical Client
    externals = r.get_external_ids(canonical_id=monday.entity.canonical_id)
    sources = {e.source for e in externals}
    assert sources == {SourceSystem.MONDAY, SourceSystem.QUICKBOOKS}
