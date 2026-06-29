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
        {
            "files": [folder_item, _make_file("root_file", "Overview.pdf", folder_id="root")],
            "nextPageToken": None,
        },
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
            {
                "files": [folder_item, _make_file("root_file", "Overview.pdf", folder_id="root")],
                "nextPageToken": None,
            },
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
                "id": fid,
                "name": name,
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
        linked = session.query(Document).filter(Document.project_id == project.canonical_id).all()
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

        # Seed an existing cursor so delta path is taken.
        from project_db.db.models import ExternalId, SourceSystem
        from project_db.db.models.docs import Document

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


class TestGeneratedReportsFolderSkipped:
    """The scanner must NOT ingest ALTA's own generated outputs, or a generated
    project-log CSV would be pulled back in as a source document (the loop the
    Project Log spec forbids)."""

    def test_generated_reports_folder_not_ingested(self, session, org):
        from project_db.connectors.gdrive.client import GDriveClient
        from project_db.connectors.gdrive.connector import GDriveConnector
        from project_db.db.models.docs import Document

        svc = MagicMock()
        gen_folder = _make_folder("genf", "ALTA Generated Reports")
        normal_file = _make_file("ok1", "Overview.pdf", folder_id="root")
        # Contents of the generated folder -- MUST NOT be reached if skip works.
        secret = _make_file("secret1", "project_log_entries.csv", folder_id="genf")
        list_mock = MagicMock()
        list_mock.execute.side_effect = [
            {"files": [gen_folder, normal_file], "nextPageToken": None},  # root
            {"files": [secret], "nextPageToken": None},  # genf (should be skipped)
        ]
        svc.files.return_value.list.return_value = list_mock
        svc.changes.return_value.getStartPageToken.return_value.execute.return_value = {
            "startPageToken": "tok"
        }
        svc.changes.return_value.list.return_value.execute.return_value = {
            "changes": [],
            "newStartPageToken": "tok2",
        }

        connector = GDriveConnector(
            session=session,
            organization_id=org.canonical_id,
            config={"_client": GDriveClient(service=svc), "root_folder": "root"},
        )
        connector.sync()

        names = {d.name for d in session.query(Document).all()}
        assert "Overview.pdf" in names  # normal file ingested
        assert "project_log_entries.csv" not in names  # generated export NOT ingested


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


# ---------------------------------------------------------------------------
# Delta-sync root containment (privacy guard)
# ---------------------------------------------------------------------------


class _FakeAncestryClient:
    """Minimal client: canned changes + a folder_id -> parents ancestry map."""

    def __init__(self, changes: list[dict], parents: dict[str, list[str]]) -> None:
        self._changes = changes
        self._parents = parents
        self.metadata_calls: list[str] = []

    def list_changes(self, cursor: str):
        return self._changes, "cursor_next"

    def get_file_metadata(self, file_id: str) -> dict:
        self.metadata_calls.append(file_id)
        if file_id not in self._parents:
            raise RuntimeError(f"not found: {file_id}")
        return {"id": file_id, "parents": self._parents[file_id]}


class TestGDriveDeltaContainment:
    """A delta sync must ingest ONLY files that live under the configured root."""

    def _connector(self, session, org, fake):
        from project_db.connectors.gdrive.connector import GDriveConnector

        return GDriveConnector(
            session=session,
            organization_id=org.canonical_id,
            config={"_client": fake, "root_folder": "ROOTID"},
        )

    def test_skips_file_outside_root_keeps_file_inside(self, session, org):
        from project_db.db.models.docs import Document

        under = _make_file("u1", "Team Quote.pdf", folder_id="SUB")
        foreign = _make_file("f1", "Private Lease.pdf", folder_id="OTHER")
        changes = [
            {"fileId": "u1", "removed": False, "file": under},
            {"fileId": "f1", "removed": False, "file": foreign},
        ]
        # SUB -> ROOTID (inside); OTHER -> PERSONAL -> (none) (outside)
        parents = {"SUB": ["ROOTID"], "OTHER": ["PERSONAL"], "PERSONAL": []}
        fake = _FakeAncestryClient(changes, parents)
        self._connector(session, org, fake)._delta_sync("cursor0")

        names = {d.name for d in session.query(Document).all()}
        assert "Team Quote.pdf" in names  # under root -> ingested
        assert "Private Lease.pdf" not in names  # outside root -> skipped

    def test_unverifiable_ancestry_is_treated_as_outside(self, session, org):
        from project_db.db.models.docs import Document

        ghost = _make_file("g1", "Mystery.pdf", folder_id="GHOST")
        changes = [{"fileId": "g1", "removed": False, "file": ghost}]
        fake = _FakeAncestryClient(changes, parents={})  # GHOST not resolvable
        self._connector(session, org, fake)._delta_sync("cursor0")

        assert session.query(Document).filter_by(storage_ref="g1").count() == 0

    def test_direct_child_of_root_is_kept(self, session, org):
        from project_db.db.models.docs import Document

        rootfile = _make_file("r1", "Overview.pdf", folder_id="ROOTID")
        changes = [{"fileId": "r1", "removed": False, "file": rootfile}]
        fake = _FakeAncestryClient(changes, parents={})  # no lookup needed
        self._connector(session, org, fake)._delta_sync("cursor0")

        assert session.query(Document).filter_by(storage_ref="r1").count() == 1
        assert fake.metadata_calls == []  # ROOTID matched directly, no API walk

    def test_folders_are_never_ingested_as_documents(self, session, org):
        from project_db.db.models.docs import Document

        # A folder under root (would pass the ancestry check) must STILL be
        # skipped -- folders are structure, not documents.
        folder = _make_folder("923 Rockland_id", "923 Rockland")
        folder["parents"] = ["ROOTID"]
        changes = [{"fileId": "923 Rockland_id", "removed": False, "file": folder}]
        fake = _FakeAncestryClient(changes, parents={})
        self._connector(session, org, fake)._delta_sync("cursor0")

        assert session.query(Document).count() == 0
        assert fake.metadata_calls == []  # skipped before any ancestry lookup
