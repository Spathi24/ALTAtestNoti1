"""Telegram intake: invite/binding, unbound quarantine, and a bound worker's
message becoming consolidated LabourClaims. Mock client + mock extractor (no
network, no API)."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from project_db.ai.telegram_intake import generate_invite, poll_telegram
from project_db.ai.telegram_labour_extraction import MockTelegramLabourExtractor
from project_db.connectors.telegram.client import MockTelegramClient
from project_db.db.base import Base
from project_db.db.models import (
    Client,
    Organization,
    Project,
    TelegramIdentity,
    Worker,
)
from project_db.db.models.labour_intake import (
    LabourClaim,
    LabourClaimCluster,
    LabourSourceEvent,
)
from project_db.db.models.work import ProjectStatus

_EPOCH = int(datetime(2026, 6, 18, 17, 30, tzinfo=timezone.utc).timestamp())


@pytest.fixture
def db_session():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)
    s = SessionLocal()
    yield s
    s.rollback()
    s.close()


def _project(session):
    org = Organization(canonical_id=uuid.uuid4(), name="O")
    cl = Client(canonical_id=uuid.uuid4(), name="C", organization_id=org.canonical_id)
    p = Project(
        canonical_id=uuid.uuid4(),
        name="923-927 Rockland",
        status=ProjectStatus.ACTIVE,
        client_id=cl.canonical_id,
    )
    session.add_all([org, cl, p])
    session.flush()
    return p


def _worker(session, name, default_project=None):
    w = Worker(
        canonical_id=uuid.uuid4(),
        display_name=name,
        active=True,
        default_project_id=default_project.canonical_id if default_project else None,
    )
    session.add(w)
    session.flush()
    return w


def _update(update_id, text, *, from_id=999, chat_id=123):
    return {
        "update_id": update_id,
        "message": {
            "message_id": update_id * 10,
            "chat_id": chat_id,
            "from_id": from_id,
            "from_username": "worker1",
            "from_first_name": "Mike",
            "from_last_name": None,
            "text": text,
            "date": _EPOCH,
        },
    }


def _labour_result():
    return {
        "document_type": "labour_update",
        "classification_confidence": 0.9,
        "reporter_role": "self",
        "claims": [
            {
                "claim_type": "labour_time",
                "employee_name": None,
                "employee_phone": None,
                "is_reporter_self": True,
                "project_name": "Rockland",
                "work_date": "2026-06-18",
                "time_arrived": "07:00",
                "time_left": "16:00",
                "lunch_hours": 0.5,
                "total_hours_reported": None,
                "activity_text": "basement framing",
                "trade": None,
                "unit": None,
                "confidence": 0.9,
                "missing_fields": [],
                "raw_excerpt": "worked rockland 7-4 half hour lunch",
            }
        ],
        "needs_followup": False,
        "followup_question": None,
    }


class TestInviteAndBinding:
    def test_generate_invite_creates_pending_identity(self, db_session):
        _worker(db_session, "Mike")
        client = MockTelegramClient()
        info = generate_invite(db_session, client, "Mike")
        assert info["deep_link"].startswith("https://t.me/")
        ident = db_session.query(TelegramIdentity).one()
        assert ident.invite_token == info["token"]
        assert ident.verified is False
        assert ident.telegram_user_id is None  # pending until /start

    def test_start_token_binds_worker(self, db_session):
        _worker(db_session, "Mike")
        client = MockTelegramClient()
        info = generate_invite(db_session, client, "Mike")
        ex = MockTelegramLabourExtractor()
        client2 = MockTelegramClient([_update(1, f"/start {info['token']}", from_id=555)])
        batch = poll_telegram(db_session, client2, ex)
        assert batch.bound == 1
        ident = db_session.query(TelegramIdentity).one()
        assert ident.verified is True
        assert ident.telegram_user_id == "555"
        assert ident.invite_token is None  # consumed
        assert any("linked as Mike" in t for _, t in client2.sent)

    def test_invalid_token_rejected(self, db_session):
        client = MockTelegramClient([_update(1, "/start bogus", from_id=555)])
        batch = poll_telegram(db_session, client, MockTelegramLabourExtractor())
        assert batch.bound == 0
        assert db_session.query(TelegramIdentity).count() == 0
        assert any("invalid" in t.lower() for _, t in client.sent)


class TestFreeTextIntake:
    def _bind(self, session, worker, user_id="555"):
        session.add(
            TelegramIdentity(
                canonical_id=uuid.uuid4(),
                worker_id=worker.canonical_id,
                telegram_user_id=user_id,
                telegram_chat_id="123",
                verified=True,
                verified_method="invite_token",
            )
        )
        session.flush()

    def test_unbound_sender_quarantined(self, db_session):
        _project(db_session)
        client = MockTelegramClient([_update(1, "worked rockland 8h", from_id=777)])
        batch = poll_telegram(db_session, client, MockTelegramLabourExtractor(_labour_result()))
        assert batch.quarantined == 1
        ev = db_session.query(LabourSourceEvent).one()
        assert ev.ingestion_status == "quarantined"
        assert ev.ingestion_reason == "unbound_sender"
        assert db_session.query(LabourClaim).count() == 0
        assert any("not linked" in t.lower() for _, t in client.sent)

    def test_bound_worker_message_creates_consolidated_claim(self, db_session):
        p = _project(db_session)
        mike = _worker(db_session, "Mike", default_project=p)
        self._bind(db_session, mike, user_id="555")
        client = MockTelegramClient(
            [_update(7, "worked rockland 7-4 half hour lunch basement framing", from_id=555)]
        )
        ex = MockTelegramLabourExtractor(_labour_result())
        batch = poll_telegram(db_session, client, ex)

        assert batch.errors == []
        assert batch.processed == 1
        assert batch.claims_created == 1
        claim = db_session.query(LabourClaim).one()
        assert claim.source_channel == "telegram"
        assert claim.reported_for_worker_id == mike.canonical_id
        assert claim.project_id == p.canonical_id
        assert claim.total_hours_computed == Decimal("8.50")
        # Consolidated into a shift cluster.
        cluster = db_session.query(LabourClaimCluster).one()
        assert cluster.worker_id == mike.canonical_id
        assert cluster.status in ("auto_single_source", "auto_reinforced")
        # The worker got a confirmation reply.
        assert any("Logged 1 claim" in t for _, t in client.sent)

    def test_foreman_message_auto_creates_crew(self, db_session):
        """The real use case: a bound foreman (Andres) reports several people in
        one message; unknown names get auto-created profiles, all attributed."""
        from project_db.db.models import Worker

        p = _project(db_session)
        andres = _worker(db_session, "Andres", default_project=p)
        mike = _worker(db_session, "Mike")
        self._bind(db_session, andres, user_id="555")
        foreman_result = {
            "document_type": "labour_update",
            "classification_confidence": 0.9,
            "reporter_role": "foreman",
            "claims": [
                {
                    "claim_type": "labour_time",
                    "employee_name": "Mike",
                    "employee_phone": None,
                    "is_reporter_self": False,
                    "project_name": "Rockland",
                    "work_date": "2026-06-18",
                    "time_arrived": None,
                    "time_left": None,
                    "lunch_hours": None,
                    "total_hours_reported": 8,
                    "activity_text": None,
                    "trade": None,
                    "unit": None,
                    "confidence": 0.9,
                    "missing_fields": [],
                    "raw_excerpt": "Mike 8",
                },
                {
                    "claim_type": "labour_time",
                    "employee_name": "NewGuy",
                    "employee_phone": None,
                    "is_reporter_self": False,
                    "project_name": "Rockland",
                    "work_date": "2026-06-18",
                    "time_arrived": None,
                    "time_left": None,
                    "lunch_hours": None,
                    "total_hours_reported": 7,
                    "activity_text": None,
                    "trade": None,
                    "unit": None,
                    "confidence": 0.9,
                    "missing_fields": [],
                    "raw_excerpt": "NewGuy 7",
                },
            ],
            "needs_followup": False,
            "followup_question": None,
        }
        client = MockTelegramClient([_update(9, "Mike 8 NewGuy 7 at Rockland", from_id=555)])
        batch = poll_telegram(db_session, client, MockTelegramLabourExtractor(foreman_result))
        assert batch.errors == []
        assert batch.claims_created == 2
        # NewGuy got a fresh unverified profile; Mike resolved to the existing one.
        newguy = db_session.query(Worker).filter(Worker.display_name == "NewGuy").one()
        assert newguy.verified is False
        claims = {c.employee_name_raw: c for c in db_session.query(LabourClaim).all()}
        assert claims["Mike"].reported_for_worker_id == mike.canonical_id
        assert claims["NewGuy"].reported_for_worker_id == newguy.canonical_id

    def test_offset_prevents_reprocessing(self, db_session):
        """The offset cursor (real dedup): after processing update 7, the next
        poll's offset is 8, so Telegram no longer returns update 7."""
        p = _project(db_session)
        mike = _worker(db_session, "Mike", default_project=p)
        self._bind(db_session, mike, user_id="555")
        ex = MockTelegramLabourExtractor(_labour_result())
        client = MockTelegramClient([_update(7, "worked rockland 7-4 lunch 30", from_id=555)])
        poll_telegram(db_session, client, ex)  # processes 7
        batch2 = poll_telegram(db_session, client, ex)  # offset now 8 -> filters 7 out
        assert batch2.total_seen == 0
        assert db_session.query(LabourSourceEvent).count() == 1
        assert db_session.query(LabourClaim).count() == 1

    def test_existing_event_guard_blocks_replay(self, db_session):
        """Defensive guard: if the same update_id is delivered again within the
        offset window (e.g. a mid-batch crash before the cursor advanced), the
        existing-event check skips it rather than double-writing."""

        class _ReplayClient(MockTelegramClient):
            def get_updates(self, offset=None):  # ignore offset -> always replay
                return list(self._updates)

        p = _project(db_session)
        mike = _worker(db_session, "Mike", default_project=p)
        self._bind(db_session, mike, user_id="555")
        ex = MockTelegramLabourExtractor(_labour_result())
        client = _ReplayClient([_update(7, "worked rockland 7-4 lunch 30", from_id=555)])
        poll_telegram(db_session, client, ex)
        batch2 = poll_telegram(db_session, client, ex)
        assert batch2.duplicate == 1
        assert db_session.query(LabourSourceEvent).count() == 1
        assert db_session.query(LabourClaim).count() == 1

    def test_help_and_status_reply(self, db_session):
        p = _project(db_session)
        mike = _worker(db_session, "Mike", default_project=p)
        self._bind(db_session, mike, user_id="555")
        client = MockTelegramClient(
            [_update(1, "/help", from_id=555), _update(2, "/status", from_id=555)]
        )
        batch = poll_telegram(db_session, client, MockTelegramLabourExtractor())
        assert batch.ignored == 2
        assert len(client.sent) == 2
        assert any("labour bot" in t.lower() for _, t in client.sent)


class TestOffsetCursor:
    def test_next_offset_advances(self, db_session):
        from project_db.ai.telegram_intake import _next_offset

        assert _next_offset(db_session) is None
        db_session.add(
            LabourSourceEvent(
                canonical_id=uuid.uuid4(),
                source_channel="telegram",
                source_kind="telegram_text",
                source_external_id="42",
                received_at=datetime.utcnow(),
                ingestion_status="ignored",
            )
        )
        db_session.flush()
        assert _next_offset(db_session) == 43
