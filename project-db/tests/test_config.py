"""Tests for configuration loading."""
from __future__ import annotations

import os


def test_config_loads_from_env():
    """conftest.py sets test creds via env vars before importing settings."""
    from project_db.config import settings

    assert settings.monday_api_token == "test_monday_token_12345"
    assert settings.quickbooks_client_id == "test_qb_client_id"
    assert settings.anthropic_api_key == "test_anthropic_key"


def test_database_url_override():
    assert os.getenv("PROJECT_DB_URL") == "sqlite:///:memory:"


def test_qb_short_aliases_match_long_form():
    """qb_* shortcuts should resolve to the same values as quickbooks_* fields."""
    from project_db.config import settings

    assert settings.qb_client_id == settings.quickbooks_client_id
    assert settings.qb_client_secret == settings.quickbooks_client_secret
    assert settings.qb_realm_id == settings.quickbooks_realm_id
    assert settings.qb_access_token == settings.quickbooks_access_token
