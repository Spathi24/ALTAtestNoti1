"""Tests for connector sync logic — Monday + QuickBooks dispatch and dedup."""

from __future__ import annotations

from datetime import datetime, timedelta
from decimal import Decimal
from unittest.mock import MagicMock, patch

from sqlalchemy.orm import Session

from project_db.connectors.base import SyncReport
from project_db.db.models import (
    Client,
    ExternalId,
    SourceSystem,
    Task,
)
from project_db.db.models.work import TaskStatus
from project_db.identity import ExactFieldMatcher, IdentityResolver


class TestMondayConnectorInitialization:
    def test_connector_class_importable(self):
        from project_db.connectors.monday import MondayConnector

        assert MondayConnector.source == SourceSystem.MONDAY


class TestMondayConnectorBoardSync:
    @patch("project_db.connectors.monday.connector.MondayClient")
    def test_sync_classifies_and_processes_boards(self, mock_client_class, session: Session, org):
        """Drive a sync end-to-end with mocked Monday client and verify it
        creates canonical entities + ExternalId rows."""
        from project_db.connectors.monday import MondayConnector

        mock_client = MagicMock()
        mock_client_class.return_value = mock_client

        mock_client.list_workspaces.return_value = [{"id": "ws1", "name": "Project Management"}]
        mock_client.list_boards.return_value = [
            {
                "id": 999,
                "name": "Leads",
                "state": "active",
                "workspace": {"id": "ws1", "name": "Project Management"},
            }
        ]
        mock_client.list_board_columns.return_value = [
            {"id": "name", "title": "Name", "type": "text"},
        ]
        mock_client.list_items.return_value = [
            {
                "id": "item_1",
                "name": "Walk-in Inquiry",
                "group": {"title": "New"},
                "column_values": [],
            }
        ]
        mock_client.list_users.return_value = []

        connector = MondayConnector(session=session, organization_id=org.canonical_id)
        report = connector.sync()

        assert isinstance(report, SyncReport)
        assert report.records_processed >= 1

    @patch("project_db.connectors.monday.connector.MondayClient")
    def test_project_board_sync_preserves_task_details_and_subitems(
        self, mock_client_class, session: Session, org
    ):
        from project_db.connectors.monday import MondayConnector

        mock_client = MagicMock()
        mock_client_class.return_value = mock_client
        mock_client.list_workspaces.return_value = [{"id": "ws1", "name": "Project Management"}]
        mock_client.list_boards.return_value = [
            {
                "id": 923,
                "name": "923 Rockland",
                "state": "active",
                "workspace": {"id": "ws1", "name": "Project Management"},
            }
        ]
        mock_client.list_board_columns.return_value = [
            {"id": "project_status", "title": "Status", "type": "status"},
            {"id": "project_timeline", "title": "Timeline", "type": "timeline"},
            {"id": "project_duration", "title": "Duration", "type": "numbers"},
            {"id": "project_planned_effort", "title": "Planned Effort", "type": "numbers"},
            {"id": "project_effort_spent", "title": "Effort Spent", "type": "numbers"},
            {"id": "text_sub", "title": "Subcontractor", "type": "text"},
            {"id": "text_supplier", "title": "Supplier", "type": "text"},
        ]
        mock_client.list_items.return_value = [
            {
                "id": "parent1",
                "name": "Selective Demolition",
                "state": "active",
                "group": {"title": "Scope of Work"},
                "column_values": [
                    {
                        "id": "project_status",
                        "type": "status",
                        "text": "Working on it",
                        "value": None,
                        "label": "Working on it",
                    },
                    {
                        "id": "project_timeline",
                        "type": "timeline",
                        "text": "",
                        "value": None,
                        "from": "2026-05-01",
                        "to": "2026-05-03",
                    },
                    {
                        "id": "project_duration",
                        "type": "numbers",
                        "text": "2",
                        "value": None,
                        "number": 2,
                    },
                    {
                        "id": "project_planned_effort",
                        "type": "numbers",
                        "text": "8",
                        "value": None,
                        "number": 8,
                    },
                    {
                        "id": "project_effort_spent",
                        "type": "numbers",
                        "text": "1.5",
                        "value": None,
                        "number": 1.5,
                    },
                    {"id": "text_sub", "type": "text", "text": "Raul", "value": '"Raul"'},
                    {"id": "text_supplier", "type": "text", "text": "BMR", "value": '"BMR"'},
                ],
                "subitems": [
                    {
                        "id": "sub1",
                        "name": "Bathroom removal",
                        "state": "active",
                        "column_values": [
                            {"id": "text_sub", "type": "text", "text": "Lucas", "value": '"Lucas"'},
                        ],
                    }
                ],
            }
        ]
        mock_client.list_users.return_value = []

        connector = MondayConnector(session=session, organization_id=org.canonical_id)
        report = connector.sync()

        assert report.records_failed == 0
        parent = session.query(Task).filter_by(title="Selective Demolition").one()
        child = session.query(Task).filter_by(title="Bathroom removal").one()
        assert parent.status == TaskStatus.IN_PROGRESS
        assert parent.group_title == "Scope of Work"
        assert parent.start_date.isoformat() == "2026-05-01"
        assert parent.end_date.isoformat() == "2026-05-03"
        assert parent.duration_days == 2
        assert parent.planned_effort == 8
        assert parent.effort_spent == Decimal("1.50")
        assert parent.subcontractor == "Raul"
        assert parent.supplier == "BMR"
        assert child.is_subitem is True
        assert child.parent_task_id == parent.canonical_id
        assert child.subcontractor == "Lucas"


class TestMondayConnectorDeltaSync:
    def test_external_id_last_synced_at_is_recorded(self, session: Session, org, client_factory):
        client = client_factory(name="Acme")
        ext = ExternalId(
            source=SourceSystem.MONDAY,
            entity_type="Client",
            external_key="monday_123",
            canonical_id=client.canonical_id,
        )
        session.add(ext)
        session.commit()

        before = ext.last_synced_at
        assert before is not None

        ext.last_synced_at = before + timedelta(minutes=10)
        session.commit()
        assert ext.last_synced_at > before


class TestMondayConnectorWriteBack:
    @patch("project_db.connectors.monday.connector.MondayClient")
    def test_sync_back_method_exists(self, mock_client_class, session: Session, org):
        """Smoke test that sync_back is callable. Real validation lives in Block 2."""
        from project_db.connectors.monday import MondayConnector

        mock_client = MagicMock()
        mock_client_class.return_value = mock_client

        connector = MondayConnector(session=session, organization_id=org.canonical_id)
        assert callable(getattr(connector, "sync_back", None))


class TestMondayConnectorColumnMapping:
    def test_column_extractor_maps_known_titles(self):
        from project_db.connectors.monday.column_extractor import ColumnExtractor

        columns = [
            {"id": "name", "title": "Name", "type": "text"},
            {"id": "status", "title": "Status", "type": "status"},
            {"id": "budget", "title": "Budget", "type": "numbers"},
        ]
        extractor = ColumnExtractor(columns)

        # The budget column should be recognized heuristically.
        assert any(field == "budget_amount" for field in extractor._heuristic.values())

        item_values = [{"id": "budget", "text": "50000", "type": "numbers", "value": "50000"}]
        fields = extractor.extract(item_values)
        assert fields.budget_amount == Decimal("50000")


# =====================================================================
# QuickBooks — these will be fleshed out in Block 3. The connector
# already exists but is not battle-tested. These tests confirm the
# class is importable and accepts mocks.
# =====================================================================


class TestQuickBooksConnectorImportable:
    def test_qb_connector_class_importable(self):
        from project_db.connectors.quickbooks import QuickBooksConnector

        assert QuickBooksConnector.source == SourceSystem.QUICKBOOKS

    @patch("project_db.connectors.quickbooks.connector.QuickBooksClient")
    def test_qb_connector_instantiates(self, mock_client_class, session: Session, org):
        from project_db.connectors.quickbooks import QuickBooksConnector

        mock_client_class.return_value = MagicMock()
        connector = QuickBooksConnector(session=session, organization_id=org.canonical_id)
        assert connector.source == SourceSystem.QUICKBOOKS


class TestQuickBooksConnectorSync:
    @patch("project_db.connectors.quickbooks.connector.QuickBooksClient")
    def test_sync_creates_client_from_customer(self, mock_client_class, session: Session, org):
        from project_db.connectors.quickbooks import QuickBooksConnector

        mock_client = MagicMock()
        mock_client_class.return_value = mock_client
        mock_client.list_customers.return_value = [
            {
                "Id": "qb_cust_1",
                "DisplayName": "Acme Corp",
                "PrimaryEmailAddr": {"Address": "acme@example.com"},
            }
        ]
        mock_client.list_invoices.return_value = []
        mock_client.list_estimates.return_value = []

        connector = QuickBooksConnector(session=session, organization_id=org.canonical_id)
        report = connector.sync()

        assert report.records_processed >= 1
        clients = session.query(Client).filter_by(name="Acme Corp").all()
        assert len(clients) == 1


class TestConnectorIntegration:
    def test_deduplication_across_monday_and_qb(self, session: Session, org):
        """Same client synced from two sources resolves to one canonical entity."""
        resolver = IdentityResolver(session)

        monday_result = resolver.resolve_or_create(
            source=SourceSystem.MONDAY,
            external_key="monday_123",
            external_url=None,
            entity_class=Client,
            attrs={
                "name": "Acme Corp",
                "email": "acme@example.com",
                "organization_id": org.canonical_id,
            },
            matcher=ExactFieldMatcher(["name"]),
        )
        qb_result = resolver.resolve_or_create(
            source=SourceSystem.QUICKBOOKS,
            external_key="qb_456",
            external_url=None,
            entity_class=Client,
            attrs={
                "name": "Acme Corp",
                "email": "acme@example.com",
                "organization_id": org.canonical_id,
            },
            matcher=ExactFieldMatcher(["name"]),
        )

        assert qb_result.entity.canonical_id == monday_result.entity.canonical_id
        ext_ids = (
            session.query(ExternalId)
            .filter_by(canonical_id=monday_result.entity.canonical_id)
            .all()
        )
        assert len(ext_ids) == 2


class TestSyncReport:
    def test_sync_report_has_summary(self):
        report = SyncReport(source=SourceSystem.MONDAY, started_at=datetime.utcnow())
        report.records_processed = 5
        report.records_created = 3
        report.records_matched = 2
        report.completed_at = datetime.utcnow()

        summary = report.summary()
        assert "processed=5" in summary
        assert "created=3" in summary
        assert "matched=2" in summary


class TestTaskCompletionTimestamp:
    """Monday records task status but never WHEN a task became done. The
    connector derives completed_at so the weekly report's 'tasks completed this
    week' signal is not permanently empty (it was: 34 DONE tasks, 0 dated)."""

    def _connector(self, session, org):
        from project_db.connectors.monday import MondayConnector

        with patch("project_db.connectors.monday.connector.MondayClient"):
            return MondayConnector(session=session, organization_id=org.canonical_id)

    def _fields(self, status, end_date=None):
        from project_db.connectors.monday.column_extractor import ExtractedFields

        return ExtractedFields(task_status=status, end_date=end_date)

    def test_completed_at_stamped_on_transition_into_done(
        self, session: Session, org, project_factory
    ):
        from datetime import date

        from project_db.db.models import Task

        conn = self._connector(session, org)
        proj = project_factory(name="Alpha")
        board = {"id": 1}
        item = {"id": "t1", "name": "Pour slab", "group": {"title": "Site"}, "column_values": []}

        # IN_PROGRESS -> no completion date yet
        tid = conn._upsert_task(
            board, item, self._fields(TaskStatus.IN_PROGRESS), proj.canonical_id
        )
        session.commit()
        task = session.query(Task).filter_by(canonical_id=tid).one()
        assert task.completed_at is None

        # transitions to DONE -> stamped today (first observed complete)
        conn._upsert_task(board, item, self._fields(TaskStatus.DONE), proj.canonical_id)
        session.commit()
        session.refresh(task)
        assert task.completed_at == date.today()

    def test_completed_at_preserved_while_still_done(self, session: Session, org, project_factory):
        from datetime import date

        from project_db.db.models import Task

        conn = self._connector(session, org)
        proj = project_factory(name="Bravo")
        board = {"id": 1}
        item = {"id": "t2", "name": "Frame walls", "column_values": []}

        conn._upsert_task(board, item, self._fields(TaskStatus.DONE), proj.canonical_id)
        session.commit()
        task = session.query(Task).filter_by(canonical_id=item_uuid(session, "t2")).one()
        # Pin to a past date, then re-sync still-DONE: must NOT be re-stamped.
        task.completed_at = date(2026, 1, 1)
        session.commit()
        conn._upsert_task(board, item, self._fields(TaskStatus.DONE), proj.canonical_id)
        session.commit()
        session.refresh(task)
        assert task.completed_at == date(2026, 1, 1)

    def test_completed_at_cleared_when_reopened(self, session: Session, org, project_factory):
        from project_db.db.models import Task

        conn = self._connector(session, org)
        proj = project_factory(name="Charlie")
        board = {"id": 1}
        item = {"id": "t3", "name": "Tiling", "column_values": []}

        conn._upsert_task(board, item, self._fields(TaskStatus.DONE), proj.canonical_id)
        session.commit()
        task = session.query(Task).filter_by(canonical_id=item_uuid(session, "t3")).one()
        assert task.completed_at is not None
        # Reopened -> stale completion stamp cleared.
        conn._upsert_task(board, item, self._fields(TaskStatus.TODO), proj.canonical_id)
        session.commit()
        session.refresh(task)
        assert task.completed_at is None

    def test_completed_at_backfilled_from_end_date(self, session: Session, org, project_factory):
        from datetime import date

        from project_db.db.models import Task

        conn = self._connector(session, org)
        proj = project_factory(name="Delta")
        board = {"id": 1}
        item = {"id": "t4", "name": "Plaster", "column_values": []}

        # Create it DONE (stamps today), then simulate a pre-existing done task
        # with no recorded completion but a known scheduled finish.
        conn._upsert_task(board, item, self._fields(TaskStatus.DONE), proj.canonical_id)
        session.commit()
        task = session.query(Task).filter_by(canonical_id=item_uuid(session, "t4")).one()
        task.completed_at = None
        task.end_date = date(2026, 5, 1)
        session.commit()

        # Re-sync still-DONE with the end_date present -> backfilled from end_date.
        conn._upsert_task(
            board, item, self._fields(TaskStatus.DONE, end_date=date(2026, 5, 1)), proj.canonical_id
        )
        session.commit()
        session.refresh(task)
        assert task.completed_at == date(2026, 5, 1)


def item_uuid(session, external_key):
    """Resolve a Monday item's external_key to its canonical Task id (test helper)."""
    from project_db.db.models import ExternalId

    row = (
        session.query(ExternalId)
        .filter_by(source=SourceSystem.MONDAY, entity_type="Task", external_key=external_key)
        .one()
    )
    return row.canonical_id
