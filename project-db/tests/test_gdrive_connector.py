"""Tests for Google Drive client and connector.

All Google API calls are mocked -- no real credentials or network needed.
The connector is exercised against an in-memory SQLite DB (same as every
other connector test).
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch
import pytest


# ---------------------------------------------------------------------------
# Helpers / shared fixtures
# ---------------------------------------------------------------------------


def _make_file(
    file_id: str = "file1",
    name: str = "Contract.pdf",
    mime_type: str = "application/pdf",
    folder_id: str = "folder1",
    web_view_link: str | None = None,
    trashed: bool = False,
) -> dict:
    return {
        "id": file_id,
        "name": name,
        "mimeType": mime_type,
        "modifiedTime": "2026-05-01T10:00:00Z",
        "size": "204800",
        "md5Checksum": "abc123",
        "parents": [folder_id],
        "driveId": "drive1",
        "webViewLink": web_view_link or f"https://drive.google.com/file/d/{file_id}",
        "trashed": trashed,
    }


def _make_folder(folder_id: str = "folder1", name: str = "923 Rockland") -> dict:
    return {
        "id": folder_id,
        "name": name,
        "mimeType": "application/vnd.google-apps.folder",
        "modifiedTime": "2026-05-01T09:00:00Z",
        "parents": ["root"],
        "webViewLink": f"https://drive.google.com/drive/folders/{folder_id}",
        "trashed": False,
    }


@pytest.fixture
def mock_gdrive_service():
    """Return a MagicMock that mimics the googleapiclient Drive v3 resource."""
    svc = MagicMock()

    folder_item = _make_folder("folder1", "923 Rockland")
    file_item = _make_file("file1", "Scope of Work.pdf", folder_id="folder1")

    # files().list().execute() returns different things depending on the query.
    # We set a side_effect so the first call (root) returns folder+file, second
    # call (inside folder) returns only the file.
    list_mock = MagicMock()
    list_mock.execute.side_effect = [
        # Root listing: one folder, one loose file
        {"files": [folder_item, _make_file("root_file", "Overview.pdf", folder_id="root")], "nextPageToken": None},
        # folder1 listing: one file
        {"files": [file_item], "nextPageToken": None},
    ]
    svc.files.return_value.list.return_value = list_mock

    # changes.getStartPageToken().execute()
    svc.changes.return_value.getStartPageToken.return_value.execute.return_value = {
        "startPageToken": "token_abc"
    }

    # changes.list().execute()
    svc.changes.return_value.list.return_value.execute.return_value = {
        "changes": [],
        "newStartPageToken": "token_xyz",
    }

    return svc


@pytest.fixture
def gdrive_client(mock_gdrive_service):
    """GDriveClient with injected mock service (no real credentials)."""
    from project_db.connectors.gdrive.client import GDriveClient
    return GDriveClient(service=mock_gdrive_service)


# ---------------------------------------------------------------------------
# GDriveClient unit tests
# ---------------------------------------------------------------------------


class TestGDriveClientInit:
    def test_init_with_injected_service(self, gdrive_client):
        """Client init succeeds with an injected mock service."""
        assert gdrive_client is not None

    def test_init_without_credentials_raises(self):
        """Client raises RuntimeError when no service is injected and credentials are missing.

        Accepts either error message because the exact message depends on which
        optional package is installed:
          - neither google-auth nor google-api-python-client -> "google-api-python-client" msg
          - google-auth installed but no key path set         -> "GDRIVE_SA_KEY_PATH" msg
          - google-api-python-client installed but no key path-> "GDRIVE_SA_KEY_PATH" msg
        """
        import os

        env_without_key = {k: v for k, v in os.environ.items() if k != "GDRIVE_SA_KEY_PATH"}
        with patch.dict(os.environ, env_without_key, clear=True):
            from project_db.connectors.gdrive.client import GDriveClient

            with pytest.raises(RuntimeError):
                GDriveClient()


class TestGDriveClientListFolder:
    def test_list_folder_returns_items(self, gdrive_client, mock_gdrive_service):
        """list_folder returns the items from the API response."""
        items = gdrive_client.list_folder("root")
        # First call returns folder + root_file
        assert len(items) == 2

    def test_list_folder_pagination(self, mock_gdrive_service):
        """list_folder follows nextPageToken until exhausted."""
        from project_db.connectors.gdrive.client import GDriveClient

        list_mock = MagicMock()
        list_mock.execute.side_effect = [
            {"files": [_make_file("f1")], "nextPageToken": "pg2"},
            {"files": [_make_file("f2")], "nextPageToken": None},
        ]
        mock_gdrive_service.files.return_value.list.return_value = list_mock

        client = GDriveClient(service=mock_gdrive_service)
        items = client.list_folder("somefolder")
        assert len(items) == 2
        assert {i["id"] for i in items} == {"f1", "f2"}


class TestGDriveClientDeltaSync:
    def test_get_start_page_token(self, gdrive_client):
        """get_start_page_token returns a token string."""
        token = gdrive_client.get_start_page_token()
        assert token == "token_abc"

    def test_list_changes_no_changes(self, gdrive_client):
        """list_changes returns empty list when nothing changed."""
        changes, new_token = gdrive_client.list_changes("token_abc")
        assert changes == []
        assert new_token == "token_xyz"

    def test_list_changes_with_changes(self, mock_gdrive_service):
        """list_changes returns change entries."""
        from project_db.connectors.gdrive.client import GDriveClient

        mock_gdrive_service.changes.return_value.list.return_value.execute.return_value = {
            "changes": [
                {"removed": False, "fileId": "f99", "file": _make_file("f99", "New.pdf")},
                {"removed": True, "fileId": "f_deleted"},
            ],
            "newStartPageToken": "token_next",
        }
        client = GDriveClient(service=mock_gdrive_service)
        changes, token = client.list_changes("old_token")
        assert len(changes) == 2
        assert token == "token_next"


# ---------------------------------------------------------------------------
# GDriveConnector integration tests (in-memory DB)
# ---------------------------------------------------------------------------


@pytest.fixture
def gdrive_connector(session, org, mock_gdrive_service):
    """GDriveConnector wired to in-memory DB with mocked Drive API."""
    from project_db.connectors.gdrive.client import GDriveClient
    from project_db.connectors.gdrive.connector import GDriveConnector

    mock_client = GDriveClient(service=mock_gdrive_service)
    connector = GDriveConnector(
        session=session,
        organization_id=org.canonical_id,
        config={
            "_client": mock_client,
            "root_folder": "root",
        },
    )
    return connector


class TestGDriveConnectorFullSync:
    def test_sync_creates_documents(self, gdrive_connector, session):
        """A full sync creates Document rows for each file under root."""
        from project_db.db.models.docs import Document

        report = gdrive_connector.sync()

        docs = session.query(Document).all()
        assert len(docs) >= 1
        assert any(d.mime_type == "application/pdf" for d in docs)

    def test_sync_report_has_no_failures(self, gdrive_connector):
        """Sync completes without errors."""
        report = gdrive_connector.sync()
        assert report.records_failed == 0

    def test_sync_idempotent(self, gdrive_connector, session, mock_gdrive_service):
        """Re-running sync does not create duplicate Document rows."""
        from project_db.connectors.gdrive.client import GDriveClient
        from project_db.connectors.gdrive.connector import GDriveConnector
        from project_db.db.models.docs import Document

        # First sync
        gdrive_connector.sync()
        count_after_first = session.query(Document).count()

        # Reset side_effect for second sync (same files)
        folder_item = _make_folder("folder1", "923 Rockland")
        file_item = _make_file("file1", "Scope of Work.pdf", folder_id="folder1")
        list_mock = MagicMock()
        list_mock.execute.side_effect = [
            {"files": [folder_item, _make_file("root_file", "Overview.pdf", folder_id="root")], "nextPageToken": None},
            {"files": [file_item], "nextPageToken": None},
        ]
        mock_gdrive_service.files.return_value.list.return_value = list_mock

        # Second connector instance (fresh report, same session)
        mock_client2 = GDriveClient(service=mock_gdrive_service)
        connector2 = GDriveConnector(
            session=session,
            organization_id=gdrive_connector.organization_id,
            config={"_client": mock_client2, "root_folder": "root"},
        )
        connector2.sync()
        count_after_second = session.query(Document).count()

        assert count_after_second == count_after_first

    def test_sync_links_document_to_project(self, session, org):
        """A file under 01. PROJECTS/<bucket>/<name> links to the Project the
        connector creates from that folder -- by ancestry, not name guessing."""
        from project_db.connectors.gdrive.client import GDriveClient
        from project_db.connectors.gdrive.connector import GDriveConnector
        from project_db.db.models import Project
        from project_db.db.models.docs import Document

        def _folder(fid, name, parent):
            return {
                "id": fid, "name": name,
                "mimeType": "application/vnd.google-apps.folder",
                "parents": [parent],
            }

        svc = MagicMock()
        list_mock = MagicMock()
        # root -> 01. PROJECTS -> ACTIVE -> 923 Rockland -> file
        list_mock.execute.side_effect = [
            {"files": [_folder("p", "01. PROJECTS", "root")], "nextPageToken": None},
            {"files": [_folder("a", "ACTIVE", "p")], "nextPageToken": None},
            {"files": [_folder("r", "923 Rockland", "a")], "nextPageToken": None},
            {"files": [_make_file("file1", "Scope.pdf", folder_id="r")], "nextPageToken": None},
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

        # The connector created the project from the folder...
        project = session.query(Project).filter_by(name="923 Rockland").one()
        # ...and the file under it is linked by ancestry.
        linked = (
            session.query(Document)
            .filter(Document.project_id == project.canonical_id)
            .all()
        )
        assert len(linked) == 1
        assert linked[0].storage_ref == "file1"

    def test_sync_stores_cursor(self, gdrive_connector, session):
        """After a full sync, the changes page token is persisted."""
        from project_db.db.models import ExternalId, SourceSystem

        gdrive_connector.sync()

        cursor_row = (
            session.query(ExternalId)
            .filter_by(
                source=SourceSystem.GOOGLE_DRIVE,
                entity_type="SyncState",
                external_key="gdrive_changes_page_token",
            )
            .one_or_none()
        )
        assert cursor_row is not None
        assert cursor_row.external_url == "token_abc"


class TestGDriveConnectorDeltaSync:
    def test_delta_sync_processes_new_file(self, gdrive_connector, session, mock_gdrive_service):
        """Delta sync adds a Document for a newly-changed file."""
        from project_db.connectors.gdrive.client import GDriveClient
        from project_db.connectors.gdrive.connector import GDriveConnector
        from project_db.db.models.docs import Document

        # Seed an existing cursor so delta path is taken.
        from project_db.db.models import ExternalId, SourceSystem
        cursor_row = ExternalId(
            source=SourceSystem.GOOGLE_DRIVE,
            entity_type="SyncState",
            external_key="gdrive_changes_page_token",
            canonical_id=gdrive_connector.organization_id,
            external_url="token_abc",
        )
        session.add(cursor_row)
        session.commit()

        new_file = _make_file("new_file_99", "Quote.pdf", folder_id="folder1")
        mock_gdrive_service.changes.return_value.list.return_value.execute.return_value = {
            "changes": [{"removed": False, "fileId": "new_file_99", "file": new_file}],
            "newStartPageToken": "token_next",
        }

        mock_client = GDriveClient(service=mock_gdrive_service)
        connector2 = GDriveConnector(
            session=session,
            organization_id=gdrive_connector.organization_id,
            config={"_client": mock_client, "root_folder": "root"},
        )
        report = connector2.sync()

        assert report.records_failed == 0
        docs = session.query(Document).filter_by(storage_ref="new_file_99").all()
        assert len(docs) == 1

    def test_delta_sync_handles_removal(self, gdrive_connector, session, mock_gdrive_service):
        """Delta sync marks a deleted file as [removed] in the Document URL."""
        from project_db.connectors.gdrive.client import GDriveClient
        from project_db.connectors.gdrive.connector import GDriveConnector
        from project_db.db.models import ExternalId, SourceSystem
        from project_db.db.models.docs import Document

        # First, full sync to create the document.
        gdrive_connector.sync()

        # Confirm file1 was created.
        docs = session.query(Document).filter_by(storage_ref="file1").all()
        assert len(docs) == 1

        # Now simulate a removal via delta sync.
        cursor_row = (
            session.query(ExternalId)
            .filter_by(
                source=SourceSystem.GOOGLE_DRIVE,
                entity_type="SyncState",
                external_key="gdrive_changes_page_token",
            )
            .one()
        )
        cursor_row.external_url = "token_abc"
        session.commit()

        mock_gdrive_service.changes.return_value.list.return_value.execute.return_value = {
            "changes": [{"removed": True, "fileId": "file1"}],
            "newStartPageToken": "token_next2",
        }
        mock_client = GDriveClient(service=mock_gdrive_service)
        connector2 = GDriveConnector(
            session=session,
            organization_id=gdrive_connector.organization_id,
            config={"_client": mock_client, "root_folder": "root"},
        )
        connector2.sync()

        doc = session.query(Document).filter_by(storage_ref="file1").one()
        assert doc.url.startswith("[removed]")


class TestGDriveConnectorRegistry:
    def test_connector_registered(self):
        """GDriveConnector is accessible through the registry."""
        from project_db.connectors.registry import get_connector_class
        from project_db.db.models import SourceSystem

        cls = get_connector_class(SourceSystem.GOOGLE_DRIVE)
        from project_db.connectors.gdrive.connector import GDriveConnector
        assert cls is GDriveConnector


class TestFolderNameNormalization:
    def test_normalize_name_strips_punctuation(self):
        from project_db.identity.matcher import normalize_name
        assert normalize_name("5768-5770 St. Laurent (Reno)") == "5768 5770 st laurent reno"

    def test_normalize_name_collapses_whitespace(self):
        from project_db.identity.matcher import normalize_name
        assert normalize_name("923  Rockland   Ave") == "923 rockland ave"

    def test_normalize_name_lowercases(self):
        from project_db.identity.matcher import normalize_name
        assert normalize_name("ALTA Group") == "alta group"
