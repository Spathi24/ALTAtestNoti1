"""Telegram intake: invite/binding, unbound quarantine, and a bound worker's
message becoming consolidated LabourClaims. Mock client + mock extractor (no
network, no API)."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timedelta, timezone
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


def _raw_update(update_id, text, *, from_id=999, chat_id=123):
    return {
        "update_id": update_id,
        "message": {
            "message_id": update_id * 10,
            "chat": {"id": chat_id},
            "from": {
                "id": from_id,
                "username": "worker1",
                "first_name": "Mike",
                "last_name": None,
            },
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

    def test_already_bound_user_rejected(self, db_session):
        """If a Telegram user is already verified, /start with a new token is rejected
        rather than silently overwriting their binding."""
        mike = _worker(db_session, "Mike")
        andres = _worker(db_session, "Andres")
        # Mike is already bound.
        db_session.add(
            TelegramIdentity(
                canonical_id=uuid.uuid4(),
                worker_id=mike.canonical_id,
                telegram_user_id="555",
                telegram_chat_id="123",
                verified=True,
                verified_method="invite_token",
            )
        )
        db_session.flush()
        # Generate a new invite for Andres, but Mike sends it.
        client_for_invite = MockTelegramClient()
        invite = generate_invite(db_session, client_for_invite, "Andres")
        client = MockTelegramClient([_update(1, f"/start {invite['token']}", from_id=555)])
        batch = poll_telegram(db_session, client, MockTelegramLabourExtractor())
        assert batch.bound == 0
        # Andres's pending identity stays unverified.
        andres_identity = (
            db_session.query(TelegramIdentity)
            .filter_by(worker_id=andres.canonical_id)
            .one()
        )
        assert andres_identity.verified is False
        assert andres_identity.telegram_user_id is None
        assert any("already linked" in t.lower() for _, t in client.sent)


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
        batch = poll_telegram(
            db_session, client, MockTelegramLabourExtractor(_labour_result()), general_intake=False
        )
        assert batch.quarantined == 1
        ev = db_session.query(LabourSourceEvent).one()
        assert ev.ingestion_status == "quarantined"
        assert ev.ingestion_reason == "unbound_sender"
        assert db_session.query(LabourClaim).count() == 0
        assert any("not linked" in t.lower() for _, t in client.sent)

    def test_raw_nested_update_shape_still_processes(self, db_session):
        p = _project(db_session)
        mike = _worker(db_session, "Mike", default_project=p)
        self._bind(db_session, mike, user_id="555")
        client = MockTelegramClient(
            [_raw_update(3, "worked rockland 7-4 half hour lunch", from_id=555)]
        )
        batch = poll_telegram(db_session, client, MockTelegramLabourExtractor(_labour_result()))
        assert batch.errors == []
        assert batch.claims_created == 1
        ev = db_session.query(LabourSourceEvent).one()
        assert ev.source_sender_key == "555"
        assert ev.source_chat_id == "123"
        assert ev.source_created_at == datetime.fromtimestamp(_EPOCH, tz=timezone.utc).replace(
            tzinfo=None
        )
        assert json.loads(ev.raw_payload_json)["message"]["from"]["id"] == 555

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
        ev = db_session.query(LabourSourceEvent).one()
        assert ev.raw_payload_json is not None
        assert json.loads(ev.raw_payload_json)["update_id"] == 7
        assert ev.source_created_at == datetime.fromtimestamp(_EPOCH, tz=timezone.utc).replace(
            tzinfo=None
        )
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
        # /help describes the bot; copy is now open-intake ("site bot") not "labour bot".
        assert any("site bot" in t.lower() for _, t in client.sent)


def _seed_comm(session, sender, project_id, *, days_ago, now):
    """Seed a prior project-attributed telegram event for attribution-history tests."""
    ts = now - timedelta(days=days_ago)
    session.add(
        LabourSourceEvent(
            canonical_id=uuid.uuid4(),
            source_channel="telegram",
            source_kind="telegram_text",
            ingestion_status="received",
            received_at=ts,
            source_created_at=ts,
            source_sender_key=sender,
            project_id_hint=project_id,
            raw_text="x",
        )
    )
    session.flush()


class TestGeneralIntake:
    """Open intake: anyone can text; non-labour messages are accepted as general
    content, attributed to a project, and surfaced in the weekly report."""

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

    def test_unbound_sender_accepted_and_text_attributed(self, db_session):
        p = _project(db_session)  # "923-927 Rockland"
        client = MockTelegramClient(
            [_update(1, "Concrete poured at 923-927 Rockland, looks good", from_id=777)]
        )
        batch = poll_telegram(
            db_session, client, MockTelegramLabourExtractor(), general_intake=True
        )
        assert batch.quarantined == 0
        assert batch.general == 1
        ev = db_session.query(LabourSourceEvent).one()
        assert ev.ingestion_status == "received"
        assert ev.ingestion_reason == "general_content"
        assert ev.project_id_hint == p.canonical_id  # text match on the site name
        assert db_session.query(LabourClaim).count() == 0
        assert any("logged" in t.lower() for _, t in client.sent)

    def test_general_message_without_project_is_unattributed(self, db_session):
        _project(db_session)
        client = MockTelegramClient([_update(1, "Who has the gate key?", from_id=777)])
        batch = poll_telegram(
            db_session, client, MockTelegramLabourExtractor(), general_intake=True
        )
        assert batch.general == 1
        ev = db_session.query(LabourSourceEvent).one()
        assert ev.project_id_hint is None  # -> lands in the Site communications section

    def test_one_source_event_per_update(self, db_session):
        _project(db_session)
        client = MockTelegramClient([_update(1, "generic site update", from_id=777)])
        poll_telegram(db_session, client, MockTelegramLabourExtractor(), general_intake=True)
        assert db_session.query(LabourSourceEvent).count() == 1

    def test_labour_takes_precedence_when_general_on(self, db_session):
        p = _project(db_session)
        mike = _worker(db_session, "Mike", default_project=p)
        self._bind(db_session, mike)
        client = MockTelegramClient([_update(7, "worked rockland 7-4", from_id=555)])
        batch = poll_telegram(
            db_session,
            client,
            MockTelegramLabourExtractor(_labour_result()),
            general_intake=True,
        )
        assert batch.claims_created == 1
        assert batch.general == 0
        ev = db_session.query(LabourSourceEvent).one()
        assert ev.ingestion_status == "extracted"

    def test_general_off_still_quarantines_strangers(self, db_session):
        _project(db_session)
        client = MockTelegramClient([_update(1, "random message", from_id=777)])
        batch = poll_telegram(
            db_session, client, MockTelegramLabourExtractor(), general_intake=False
        )
        assert batch.quarantined == 1
        assert batch.general == 0


class TestProjectAttribution:
    def test_text_match_wins(self, db_session):
        from project_db.ai.telegram_intake import _attribute_project

        p = _project(db_session)
        pid, method, _ = _attribute_project(
            db_session, "999", "all done at 923-927 Rockland today"
        )
        assert pid == p.canonical_id
        assert method == "text_match"

    def test_word_token_match_address_format(self, db_session):
        """'Flooding at Rockland' should match '923-927 Rockland' via word token."""
        from project_db.ai.telegram_intake import _attribute_project

        p = _project(db_session)
        pid, method, _ = _attribute_project(
            db_session, "999", "Flooding at Rockland over the weekend. Work progressing to fix it."
        )
        assert pid == p.canonical_id
        assert method == "text_match_word"

    def test_worker_default_used_when_no_text_match(self, db_session):
        from project_db.ai.telegram_intake import _attribute_project

        p = _project(db_session)
        w = _worker(db_session, "Mike", default_project=p)
        pid, method, _ = _attribute_project(db_session, "999", "no site named here", worker=w)
        assert pid == p.canonical_id
        assert method == "worker_default"

    def test_recency_weighted_dominant_project_wins(self, db_session):
        from project_db.ai.telegram_intake import _attribute_project

        a = _project(db_session)
        b = Project(
            canonical_id=uuid.uuid4(),
            name="5768 St-Laurent",
            status=ProjectStatus.ACTIVE,
            client_id=a.client_id,
        )
        db_session.add(b)
        db_session.flush()
        now = datetime(2026, 6, 22, 12, 0, 0)
        _seed_comm(db_session, "888", a.canonical_id, days_ago=1, now=now)
        _seed_comm(db_session, "888", a.canonical_id, days_ago=2, now=now)
        _seed_comm(db_session, "888", a.canonical_id, days_ago=3, now=now)
        _seed_comm(db_session, "888", b.canonical_id, days_ago=10, now=now)
        pid, method, _ = _attribute_project(db_session, "888", "generic note", now=now)
        assert pid == a.canonical_id
        assert method == "sender_recency"

    def test_constant_switcher_is_ambiguous(self, db_session):
        from project_db.ai.telegram_intake import _attribute_project

        a = _project(db_session)
        b = Project(
            canonical_id=uuid.uuid4(),
            name="5768 St-Laurent",
            status=ProjectStatus.ACTIVE,
            client_id=a.client_id,
        )
        db_session.add(b)
        db_session.flush()
        now = datetime(2026, 6, 22, 12, 0, 0)
        _seed_comm(db_session, "888", a.canonical_id, days_ago=1, now=now)
        _seed_comm(db_session, "888", a.canonical_id, days_ago=2, now=now)
        _seed_comm(db_session, "888", b.canonical_id, days_ago=1, now=now)
        _seed_comm(db_session, "888", b.canonical_id, days_ago=2, now=now)
        pid, method, _ = _attribute_project(db_session, "888", "generic note", now=now)
        assert pid is None
        assert method == "unresolved"


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

    def test_non_message_update_advances_cursor(self, db_session):
        client = MockTelegramClient([{"update_id": 7, "message": None, "poll": {"id": "p1"}}])
        batch = poll_telegram(db_session, client, MockTelegramLabourExtractor())
        assert batch.ignored == 1
        ev = db_session.query(LabourSourceEvent).one()
        assert ev.source_external_id == "7"
        assert ev.ingestion_status == "ignored"
        assert ev.ingestion_reason == "non_message_update"

        batch2 = poll_telegram(db_session, client, MockTelegramLabourExtractor())
        assert batch2.total_seen == 0
        assert db_session.query(LabourSourceEvent).count() == 1

    def test_callback_query_advances_cursor(self, db_session):
        update = {
            "update_id": 8,
            "message": None,
            "callback_query": {
                "data": "noop",
                "from": {"id": 555},
                "message": {"message_id": 80, "chat_id": 123, "date": _EPOCH},
            },
        }
        client = MockTelegramClient([update])
        batch = poll_telegram(db_session, client, MockTelegramLabourExtractor())
        assert batch.ignored == 1
        ev = db_session.query(LabourSourceEvent).one()
        assert ev.source_external_id == "8"
        assert ev.source_kind == "telegram_callback"
        assert ev.source_sender_key == "555"
        assert ev.ingestion_reason == "callback_query"
