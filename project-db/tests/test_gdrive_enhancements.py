"""Tests for the 2026-05-14 Drive enhancements.

Covers what test_gdrive_connector.py did not:
  - Civic-number extraction from folder names
  - Civic-first matching strategy (specific > loose)
  - All new Document columns populated on upsert
  - RFC3339 timestamp parsing
  - SQLite document-column migration helper
  - Recursive walk catches deeply-nested files
"""

from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock

import pytest

# ---------------------------------------------------------------------------
# Civic number extraction (pure function)
# ---------------------------------------------------------------------------


class TestExtractCivicNumbers:
    def test_single_civic_number(self):
        from project_db.identity.matcher import extract_civic_numbers

        assert extract_civic_numbers("1455 Rue St. Mathieu") == {"1455"}

    def test_dash_separated_range(self):
        from project_db.identity.matcher import extract_civic_numbers

        assert extract_civic_numbers("5768-5770 St Laurent") == {"5768", "5770"}

    def test_space_separated_range(self):
        from project_db.identity.matcher import extract_civic_numbers

        assert extract_civic_numbers("5768 5770 St Laurent") == {"5768", "5770"}

    def test_with_unit_suffix(self):
        from project_db.identity.matcher import extract_civic_numbers

        assert extract_civic_numbers("923 Rockland (3rd Floor unit)") == {"923"}

    def test_no_civic_number(self):
        from project_db.identity.matcher import extract_civic_numbers

        assert extract_civic_numbers("Active Projects") == set()
        assert extract_civic_numbers("05. INTELLIGENCE") == set()

    def test_empty_string(self):
        from project_db.identity.matcher import extract_civic_numbers

        assert extract_civic_numbers("") == set()

    def test_two_digit_lead_prefix_is_not_a_civic(self):
        # "25-1001 580 Rue Viau": the "25-1001" lead-tracking prefix must NOT
        # be read as a civic, or two unrelated leads collide on a shared "25".
        from project_db.identity.matcher import extract_civic_numbers

        assert extract_civic_numbers("25-1001 580 Rue Viau") == set()
        assert extract_civic_numbers("25-1000 Triplex Rue Hadley") == set()


# ---------------------------------------------------------------------------
# Folder taxonomy: deterministic project-folder + category detection
# (this replaced the deleted substring/civic _match_project_by_name)
# ---------------------------------------------------------------------------


class TestFolderTaxonomy:
    def test_project_bucket_detection(self):
        from project_db.connectors.gdrive.connector import _project_bucket_for_path

        assert _project_bucket_for_path("01. PROJECTS/ACTIVE/923 Rockland") == "ACTIVE"
        assert _project_bucket_for_path("01. PROJECTS/INACTIVE/2150 Tupper") == "INACTIVE"
        assert _project_bucket_for_path("01. PROJECTS/LEADS/Bates") == "LEADS"

    def test_non_project_paths_are_not_buckets(self):
        from project_db.connectors.gdrive.connector import _project_bucket_for_path

        assert _project_bucket_for_path("01. PROJECTS/ACTIVE") is None  # too shallow
        assert _project_bucket_for_path("01. PROJECTS/ACTIVE/X/Contracts") is None  # too deep
        assert _project_bucket_for_path("00. COMPANY/2. DOCUMENTS") is None
        assert _project_bucket_for_path("") is None
        assert _project_bucket_for_path(None) is None

    def test_category_classification(self):
        from project_db.connectors.gdrive.connector import _category_for_path

        assert _category_for_path("01. PROJECTS/ACTIVE/923 Rockland") == "projects"
        assert _category_for_path("00. COMPANY/2. DOCUMENTS") == "company"
        assert _category_for_path("02. REAL ESTATE/4. UNDERWRITING") == "real_estate"
        assert _category_for_path("03. CONSTRUCTION/1. RESOURCES") == "construction"
        assert _category_for_path("05. INTELLIGENCE/BIM") == "intelligence"
        assert _category_for_path(None) is None


# ---------------------------------------------------------------------------
# Project discovery: a Drive project folder IS a canonical Project,
# files link by physical folder ancestry (never by name guessing)
# ---------------------------------------------------------------------------


class TestProjectFolderDiscovery:
    @staticmethod
    def _folder(fid: str, name: str, parent: str) -> dict:
        return {
            "id": fid,
            "name": name,
            "mimeType": "application/vnd.google-apps.folder",
            "parents": [parent],
        }

    def test_folders_become_projects_files_link_by_ancestry(self, session, org):
        """923 and 927 are SEPARATE folders -> separate projects; their files
        link to their own folder's project and are never cross-linked."""
        from project_db.connectors.gdrive.client import GDriveClient
        from project_db.connectors.gdrive.connector import GDriveConnector
        from project_db.db.models import Project
        from project_db.db.models.docs import Document
        from project_db.db.models.work import ProjectStatus

        svc = MagicMock()
        list_mock = MagicMock()
        # Depth-first walk order: root, 01.PROJECTS, ACTIVE, 923, 927, 00.COMPANY.
        list_mock.execute.side_effect = [
            {
                "files": [
                    self._folder("p", "01. PROJECTS", "root"),
                    self._folder("co", "00. COMPANY", "root"),
                ],
                "nextPageToken": None,
            },
            {"files": [self._folder("a", "ACTIVE", "p")], "nextPageToken": None},
            {
                "files": [
                    self._folder("f923", "923 Rockland (3rd Floor unit)", "a"),
                    self._folder("f927", "927 Rockland (Ground Floor unit)", "a"),
                ],
                "nextPageToken": None,
            },
            {"files": [_rich_file_payload("doc923")], "nextPageToken": None},
            {"files": [_rich_file_payload("doc927")], "nextPageToken": None},
            {"files": [_rich_file_payload("doccompany")], "nextPageToken": None},
        ]
        svc.files.return_value.list.return_value = list_mock
        svc.changes.return_value.getStartPageToken.return_value.execute.return_value = {
            "startPageToken": "tok"
        }

        connector = GDriveConnector(
            session=session,
            organization_id=org.canonical_id,
            config={"_client": GDriveClient(service=svc), "root_folder": "root"},
        )
        connector.sync()

        # Two distinct projects, named after their folders, status from bucket.
        p923 = session.query(Project).filter_by(name="923 Rockland (3rd Floor unit)").one()
        p927 = session.query(Project).filter_by(name="927 Rockland (Ground Floor unit)").one()
        assert p923.canonical_id != p927.canonical_id
        assert p923.status == ProjectStatus.ACTIVE

        # Each file links to ITS OWN project folder -- never cross-linked.
        d923 = session.query(Document).filter_by(storage_ref="doc923").one()
        d927 = session.query(Document).filter_by(storage_ref="doc927").one()
        assert d923.project_id == p923.canonical_id
        assert d927.project_id == p927.canonical_id
        assert d923.category == "projects"

        # A company-knowledge file: no project, but a category.
        dco = session.query(Document).filter_by(storage_ref="doccompany").one()
        assert dco.project_id is None
        assert dco.category == "company"


# ---------------------------------------------------------------------------
# Timestamp parsing
# ---------------------------------------------------------------------------


class TestParseRFC3339:
    def test_with_z_suffix(self):
        from project_db.connectors.gdrive.connector import _parse_rfc3339

        result = _parse_rfc3339("2026-05-14T12:34:56Z")
        assert result is not None
        assert result.year == 2026 and result.month == 5 and result.day == 14

    def test_with_milliseconds(self):
        from project_db.connectors.gdrive.connector import _parse_rfc3339

        result = _parse_rfc3339("2026-05-14T12:34:56.789Z")
        assert result is not None

    def test_none_input(self):
        from project_db.connectors.gdrive.connector import _parse_rfc3339

        assert _parse_rfc3339(None) is None

    def test_empty_string(self):
        from project_db.connectors.gdrive.connector import _parse_rfc3339

        assert _parse_rfc3339("") is None

    def test_garbage_returns_none(self):
        from project_db.connectors.gdrive.connector import _parse_rfc3339

        assert _parse_rfc3339("not a date") is None


# ---------------------------------------------------------------------------
# Document upsert populates all new fields
# ---------------------------------------------------------------------------


def _rich_file_payload(file_id: str = "file42") -> dict:
    """Drive file dict shaped like what the broader fields= request returns."""
    return {
        "id": file_id,
        "name": "Contract.pdf",
        "mimeType": "application/pdf",
        "createdTime": "2026-04-01T10:00:00.000Z",
        "modifiedTime": "2026-05-10T15:30:00.000Z",
        "size": "1048576",
        "md5Checksum": "deadbeef" * 4,
        "parents": ["folder_xyz"],
        "driveId": None,
        "webViewLink": f"https://drive.google.com/file/d/{file_id}",
        "webContentLink": f"https://drive.google.com/uc?id={file_id}",
        "iconLink": "https://drive-thirdparty.google.com/icon",
        "trashed": False,
        "shared": True,
        "starred": False,
        "owners": [{"emailAddress": "owner@example.com", "displayName": "Owner Name"}],
        "lastModifyingUser": {"emailAddress": "editor@example.com", "displayName": "Editor"},
        "capabilities": {"canDownload": True, "canEdit": False},
    }


@pytest.fixture
def mock_gdrive_service_rich():
    """Service returning one rich file under one folder."""
    svc = MagicMock()

    folder = {
        "id": "folder_xyz",
        "name": "5768 St-Laurent",
        "mimeType": "application/vnd.google-apps.folder",
        "parents": ["root"],
    }
    file = _rich_file_payload("file42")

    list_mock = MagicMock()
    list_mock.execute.side_effect = [
        # root listing: one folder
        {"files": [folder], "nextPageToken": None},
        # folder listing: one rich file
        {"files": [file], "nextPageToken": None},
    ]
    svc.files.return_value.list.return_value = list_mock

    svc.changes.return_value.getStartPageToken.return_value.execute.return_value = {
        "startPageToken": "tok"
    }
    return svc


class TestDocumentFieldPopulation:
    def test_all_new_fields_populated(self, session, org, mock_gdrive_service_rich):
        """After full sync, the Document row carries every Drive-metadata field."""
        from project_db.connectors.gdrive.client import GDriveClient
        from project_db.connectors.gdrive.connector import GDriveConnector
        from project_db.db.models.docs import Document

        connector = GDriveConnector(
            session=session,
            organization_id=org.canonical_id,
            config={
                "_client": GDriveClient(service=mock_gdrive_service_rich),
                "root_folder": "root",
            },
        )
        connector.sync()

        doc = session.query(Document).filter_by(storage_ref="file42").one()
        assert doc.name == "Contract.pdf"
        assert doc.mime_type == "application/pdf"
        assert doc.size_bytes == 1048576
        assert doc.md5_checksum == "deadbeef" * 4
        assert doc.owner_email == "owner@example.com"
        assert doc.parent_folder_id == "folder_xyz"
        assert doc.folder_path == "5768 St-Laurent"
        assert doc.is_trashed is False
        assert isinstance(doc.modified_at_source, datetime)
        assert doc.modified_at_source.year == 2026
        assert isinstance(doc.created_at_source, datetime)
        assert doc.created_at_source.month == 4
        # source_meta_json must include the fields we didn't promote.
        import json

        meta = json.loads(doc.source_meta_json)
        assert meta["shared"] is True
        assert meta["capabilities"]["canEdit"] is False
        assert meta["lastModifyingUser"]["emailAddress"] == "editor@example.com"

    def test_folder_path_breadcrumb_built_correctly(self, session, org):
        """Nested folder structure produces a slash-joined path."""
        from project_db.connectors.gdrive.client import GDriveClient
        from project_db.connectors.gdrive.connector import GDriveConnector
        from project_db.db.models.docs import Document

        svc = MagicMock()
        list_mock = MagicMock()
        # Nesting: root -> "01. PROJECTS" -> "ACTIVE" -> "5768 St-Laurent" -> file
        list_mock.execute.side_effect = [
            {
                "files": [
                    {
                        "id": "p",
                        "name": "01. PROJECTS",
                        "mimeType": "application/vnd.google-apps.folder",
                        "parents": ["root"],
                    }
                ],
                "nextPageToken": None,
            },
            {
                "files": [
                    {
                        "id": "a",
                        "name": "ACTIVE",
                        "mimeType": "application/vnd.google-apps.folder",
                        "parents": ["p"],
                    }
                ],
                "nextPageToken": None,
            },
            {
                "files": [
                    {
                        "id": "s",
                        "name": "5768 St-Laurent",
                        "mimeType": "application/vnd.google-apps.folder",
                        "parents": ["a"],
                    }
                ],
                "nextPageToken": None,
            },
            {"files": [_rich_file_payload("deep_file")], "nextPageToken": None},
        ]
        svc.files.return_value.list.return_value = list_mock
        svc.changes.return_value.getStartPageToken.return_value.execute.return_value = {
            "startPageToken": "tok"
        }

        connector = GDriveConnector(
            session=session,
            organization_id=org.canonical_id,
            config={"_client": GDriveClient(service=svc), "root_folder": "root"},
        )
        connector.sync()

        doc = session.query(Document).filter_by(storage_ref="deep_file").one()
        assert doc.folder_path == "01. PROJECTS/ACTIVE/5768 St-Laurent"

    def test_recursion_catches_deep_files(self, session, org):
        """Files past depth 3 are no longer dropped (was a bug pre-2026-05-14)."""
        from project_db.connectors.gdrive.client import GDriveClient
        from project_db.connectors.gdrive.connector import GDriveConnector
        from project_db.db.models.docs import Document

        svc = MagicMock()
        # Build a 6-deep chain ending in one file -- the old 3-level walk would miss it.
        side_effects = []
        for i in range(6):
            child_id = f"d{i + 1}"
            side_effects.append(
                {
                    "files": [
                        {
                            "id": child_id,
                            "name": f"Level {i + 1}",
                            "mimeType": "application/vnd.google-apps.folder",
                            "parents": [f"d{i}"] if i > 0 else ["root"],
                        }
                    ],
                    "nextPageToken": None,
                }
            )
        # Final folder contains the file
        side_effects.append({"files": [_rich_file_payload("deep6")], "nextPageToken": None})

        list_mock = MagicMock()
        list_mock.execute.side_effect = side_effects
        svc.files.return_value.list.return_value = list_mock
        svc.changes.return_value.getStartPageToken.return_value.execute.return_value = {
            "startPageToken": "tok"
        }

        connector = GDriveConnector(
            session=session,
            organization_id=org.canonical_id,
            config={"_client": GDriveClient(service=svc), "root_folder": "root"},
        )
        connector.sync()

        doc = session.query(Document).filter_by(storage_ref="deep6").one_or_none()
        assert doc is not None, "File 6 levels deep was dropped -- recursion regressed"
        assert doc.folder_path.count("/") == 5  # six segments, five slashes


# ---------------------------------------------------------------------------
# SQLite migration helper
# ---------------------------------------------------------------------------


class TestDocumentSchemaMigration:
    def test_ensure_sqlite_schema_adds_new_document_columns(self):
        """Verify the migration helper adds new columns to a legacy SQLite file."""
        from sqlalchemy import create_engine, inspect, text

        engine = create_engine("sqlite:///:memory:", future=True)

        # Build a legacy document table with only the old four columns.
        with engine.begin() as conn:
            conn.execute(
                text("""
                CREATE TABLE document (
                    canonical_id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    mime_type TEXT,
                    url TEXT NOT NULL,
                    storage_ref TEXT,
                    created_at DATETIME NOT NULL,
                    updated_at DATETIME NOT NULL
                )
            """)
            )

        # Also create a 'task' table so the helper doesn't bail.
        with engine.begin() as conn:
            conn.execute(text("CREATE TABLE task (canonical_id TEXT PRIMARY KEY)"))

        from project_db.db.migrations import SQLITE_DOCUMENT_COLUMNS, ensure_sqlite_schema

        ensure_sqlite_schema(engine)

        inspector = inspect(engine)
        cols = {c["name"] for c in inspector.get_columns("document")}
        for new_col in SQLITE_DOCUMENT_COLUMNS:
            assert new_col in cols, f"Migration didn't add {new_col!r}"

    def test_ensure_sqlite_schema_is_idempotent(self):
        """Calling the migration twice doesn't error or duplicate."""
        from sqlalchemy import create_engine, text

        from project_db.db.migrations import ensure_sqlite_schema

        engine = create_engine("sqlite:///:memory:", future=True)
        with engine.begin() as conn:
            conn.execute(
                text("""
                CREATE TABLE document (
                    canonical_id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    url TEXT NOT NULL,
                    created_at DATETIME NOT NULL,
                    updated_at DATETIME NOT NULL
                )
            """)
            )
            conn.execute(text("CREATE TABLE task (canonical_id TEXT PRIMARY KEY)"))

        ensure_sqlite_schema(engine)
        ensure_sqlite_schema(engine)  # second call must not raise
