"""Centralized config — loads from .env then environment variables.

Place a .env file in the project-db/ directory (next to pyproject.toml).
A .env.example with all supported keys is checked in alongside it.

Lookup order for .env:
  1. Directory containing this file's package root (project-db/)
  2. Current working directory
  3. Each parent of cwd up to filesystem root
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def _find_env_file() -> Path | None:
    """Search for a .env file starting from the package root, then cwd upwards."""
    # Package root = project-db/ (3 levels up from src/project_db/config.py)
    pkg_root = Path(__file__).parent.parent.parent
    candidate = pkg_root / ".env"
    if candidate.exists():
        return candidate

    # Walk up from cwd
    for directory in [Path.cwd(), *Path.cwd().parents]:
        candidate = directory / ".env"
        if candidate.exists():
            return candidate

    return None


try:
    from dotenv import load_dotenv

    _env_file = _find_env_file()
    if _env_file:
        load_dotenv(_env_file, override=False)  # real env vars take precedence
except ImportError:
    pass  # python-dotenv not installed — rely purely on environment variables


@dataclass(frozen=True)
class Settings:
    db_url: str = os.environ.get("PROJECT_DB_URL", "sqlite:///./project_db.sqlite")
    monday_api_token: str | None = os.environ.get("MONDAY_API_TOKEN")
    companycam_api_token: str | None = os.environ.get("COMPANYCAM_API_TOKEN")
    quickbooks_client_id: str | None = os.environ.get("QUICKBOOKS_CLIENT_ID")
    quickbooks_client_secret: str | None = os.environ.get("QUICKBOOKS_CLIENT_SECRET")
    quickbooks_realm_id: str | None = os.environ.get("QUICKBOOKS_REALM_ID")
    quickbooks_access_token: str | None = os.environ.get("QUICKBOOKS_ACCESS_TOKEN")
    google_credentials_path: str | None = os.environ.get("GOOGLE_CREDENTIALS_PATH")
    gdrive_impersonate: str | None = os.environ.get("GDRIVE_IMPERSONATE")
    gdrive_root_folder: str = os.environ.get("GDRIVE_ROOT_FOLDER", "root")
    anthropic_api_key: str | None = os.environ.get("ANTHROPIC_API_KEY")

    @property
    def qb_client_id(self) -> str | None:
        return self.quickbooks_client_id

    @property
    def qb_client_secret(self) -> str | None:
        return self.quickbooks_client_secret

    @property
    def qb_realm_id(self) -> str | None:
        return self.quickbooks_realm_id

    @property
    def qb_access_token(self) -> str | None:
        return self.quickbooks_access_token


settings = Settings()
