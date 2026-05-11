"""Centralized config — environment variable lookups in one place."""
from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    db_url: str = os.environ.get("PROJECT_DB_URL", "sqlite:///./project_db.sqlite")
    monday_api_token: str | None = os.environ.get("MONDAY_API_TOKEN")
    companycam_api_token: str | None = os.environ.get("COMPANYCAM_API_TOKEN")
    quickbooks_client_id: str | None = os.environ.get("QUICKBOOKS_CLIENT_ID")
    quickbooks_client_secret: str | None = os.environ.get("QUICKBOOKS_CLIENT_SECRET")
    google_credentials_path: str | None = os.environ.get("GOOGLE_CREDENTIALS_PATH")
    anthropic_api_key: str | None = os.environ.get("ANTHROPIC_API_KEY")


settings = Settings()
