"""Telegram free-text -> LabourClaim extraction (mock LLM; no API).

Covers self-report, foreman multi-worker, worker/project resolution, date/time
normalization + computed hours, activity-only, and an end-to-end reinforcement
of a Telegram self-report against a Gmail claim through the consolidator.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from project_db.ai.labour_consolidation import consolidate_claims
from project_db.ai.telegram_labour_extraction import (
    MockTelegramLabourExtractor,
    ingest_telegram_labour_claims,
)
from project_db.db.base import Base
from project_db.db.models import Client, Organization, Project, Worker
from project_db.db.models.labour_intake import (
    LabourClaim,
    LabourClaimCluster,
    LabourSourceEvent,
)
from project_db.db.models.work import ProjectStatus

_MSG_DT = datetime(2026, 6, 18, 17, 30)


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


def _project(session, name="923-927 Rockland"):
    org = Organization(canonical_id=uuid.uuid4(), name="O")
    cl = Client(canonical_id=uuid.uuid4(), name="C", organization_id=org.canonical_id)
    p = Project(
        canonical_id=uuid.uuid4(), name=name, status=ProjectStatus.ACTIVE, client_id=cl.canonical_id
    )
    session.add_all([org, cl, p])
    session.flush()
    return p


def _worker(session, name):
    w = Worker(canonical_id=uuid.uuid4(), display_name=name, active=True)
    session.add(w)
    session.flush()
    return w


def _event(session, text):
    ev = LabourSourceEvent(
        canonical_id=uuid.uuid4(),
        source_channel="telegram",
        source_kind="telegram_text",
        received_at=_MSG_DT,
        raw_text=text,
        ingestion_status="received",
    )
    session.add(ev)
    session.flush()
    return ev


def _claim_dict(**kw):
    base = {
        "claim_type": "labour_time",
        "employee_name": None,
        "employee_phone": None,
        "is_reporter_self": False,
        "project_name": "Rockland",
        "work_date": "2026-06-18",
        "time_arrived": None,
        "time_left": None,
        "lunch_hours": None,
        "total_hours_reported": None,
        "activity_text": None,
        "trade": None,
        "unit": None,
        "confidence": 0.9,
        "missing_fields": [],
        "raw_excerpt": "x",
    }
    base.update(kw)
    return base


def _result(claims, reporter_role="self"):
    return {
        "document_type": "labour_update",
        "classification_confidence": 0.9,
        "reporter_role": reporter_role,
        "claims": claims,
        "needs_followup": False,
        "followup_question": None,
    }


class TestTelegramExtraction:
    def test_self_report_computes_hours(self, db_session):
        p = _project(db_session)
        mike = _worker(db_session, "Mike")
        ev = _event(db_session, "worked rockland 7-4 half hour lunch")
        ex = MockTelegramLabourExtractor(
            _result(
                [
                    _claim_dict(
                        is_reporter_self=True,
                        time_arrived="07:00",
                        time_left="16:00",
                        lunch_hours=0.5,
                    )
                ]
            )
        )
        claims = ingest_telegram_labour_claims(
            db_session,
            ex,
            text=ev.raw_text,
            source_event_id=ev.canonical_id,
            message_datetime=_MSG_DT,
            reporter_worker=mike,
            default_project_id=p.canonical_id,
        )
        db_session.commit()
        assert len(claims) == 1
        c = claims[0]
        assert c.reported_for_worker_id == mike.canonical_id
        assert c.employee_match_method == "telegram_identity"
        assert c.project_id == p.canonical_id
        assert c.work_date == date(2026, 6, 18)
        assert c.total_hours_computed == Decimal("8.50")
        assert c.source_channel == "telegram"

    def test_foreman_multi_worker(self, db_session):
        p = _project(db_session)
        for nm in ("John", "Mike", "Alex"):
            _worker(db_session, nm)
        ev = _event(db_session, "John 8h Mike 7.5 Alex 5 at Rockland demo")
        ex = MockTelegramLabourExtractor(
            _result(
                [
                    _claim_dict(employee_name="John", total_hours_reported=8),
                    _claim_dict(employee_name="Mike", total_hours_reported=7.5),
                    _claim_dict(employee_name="Alex", total_hours_reported=5),
                ],
                reporter_role="foreman",
            )
        )
        claims = ingest_telegram_labour_claims(
            db_session,
            ex,
            text=ev.raw_text,
            source_event_id=ev.canonical_id,
            message_datetime=_MSG_DT,
            default_project_id=p.canonical_id,
        )
        db_session.commit()
        assert len(claims) == 3
        assert all(c.reporter_role == "foreman" for c in claims)
        assert all(c.reported_for_worker_id is not None for c in claims)  # all resolved by name
        assert all(c.employee_match_method == "exact" for c in claims)

    def test_unresolved_name_kept_raw_when_no_reporter(self, db_session):
        # No bound reporter (reporter_worker=None) -> no auto-create -> unresolved.
        p = _project(db_session)
        ev = _event(db_session, "NewGuy 8h")
        ex = MockTelegramLabourExtractor(
            _result(
                [_claim_dict(employee_name="NewGuy", total_hours_reported=8)],
                reporter_role="foreman",
            )
        )
        claims = ingest_telegram_labour_claims(
            db_session,
            ex,
            text=ev.raw_text,
            source_event_id=ev.canonical_id,
            message_datetime=_MSG_DT,
            default_project_id=p.canonical_id,
        )
        c = claims[0]
        assert c.reported_for_worker_id is None
        assert c.employee_match_method == "unresolved"
        assert c.employee_name_raw == "NewGuy"  # never discarded

    def test_foreman_auto_creates_unknown_crew(self, db_session):
        """A BOUND foreman naming an unknown person auto-creates an unverified
        Worker stub; a known name still resolves exact. No fuzzy merge."""
        p = _project(db_session)
        andres = _worker(db_session, "Andres")
        mike = _worker(db_session, "Mike")
        ev = _event(db_session, "Mike 8h NewGuy 7h at Rockland")
        ex = MockTelegramLabourExtractor(
            _result(
                [
                    _claim_dict(employee_name="Mike", total_hours_reported=8),
                    _claim_dict(employee_name="NewGuy", total_hours_reported=7),
                ],
                reporter_role="foreman",
            )
        )
        claims = ingest_telegram_labour_claims(
            db_session,
            ex,
            text=ev.raw_text,
            source_event_id=ev.canonical_id,
            message_datetime=_MSG_DT,
            reporter_worker=andres,  # bound -> allow_create
            default_project_id=p.canonical_id,
        )
        db_session.commit()
        by = {c.employee_name_raw: c for c in claims}
        assert by["Mike"].employee_match_method == "exact"
        assert by["Mike"].reported_for_worker_id == mike.canonical_id
        assert by["NewGuy"].employee_match_method == "auto_created"
        assert by["NewGuy"].reported_for_worker_id is not None
        newguy = db_session.query(Worker).filter(Worker.display_name == "NewGuy").one()
        assert newguy.verified is False  # flagged for confirm/merge

    def test_auto_created_worker_reused_not_duplicated(self, db_session):
        p = _project(db_session)
        andres = _worker(db_session, "Andres")
        ex = MockTelegramLabourExtractor(
            _result(
                [_claim_dict(employee_name="NewGuy", total_hours_reported=8)],
                reporter_role="foreman",
            )
        )
        for uid in (1, 2):
            ev = _event(db_session, "NewGuy 8h")
            ingest_telegram_labour_claims(
                db_session,
                ex,
                text=ev.raw_text,
                source_event_id=ev.canonical_id,
                message_datetime=_MSG_DT,
                reporter_worker=andres,
                default_project_id=p.canonical_id,
            )
            db_session.commit()
        assert db_session.query(Worker).filter(Worker.display_name == "NewGuy").count() == 1

    def test_project_default_when_unnamed(self, db_session):
        p = _project(db_session)
        mike = _worker(db_session, "Mike")
        ev = _event(db_session, "worked 8 hours today")
        ex = MockTelegramLabourExtractor(
            _result([_claim_dict(is_reporter_self=True, project_name=None, total_hours_reported=8)])
        )
        claims = ingest_telegram_labour_claims(
            db_session,
            ex,
            text=ev.raw_text,
            source_event_id=ev.canonical_id,
            message_datetime=_MSG_DT,
            reporter_worker=mike,
            default_project_id=p.canonical_id,
        )
        c = claims[0]
        assert c.project_id == p.canonical_id
        assert c.project_match_method == "worker_default"

    def test_activity_only_no_hours(self, db_session):
        p = _project(db_session)
        mike = _worker(db_session, "Mike")
        ev = _event(db_session, "finished basement framing")
        ex = MockTelegramLabourExtractor(
            _result(
                [
                    _claim_dict(
                        claim_type="activity_only",
                        is_reporter_self=True,
                        activity_text="finished basement framing",
                    )
                ]
            )
        )
        claims = ingest_telegram_labour_claims(
            db_session,
            ex,
            text=ev.raw_text,
            source_event_id=ev.canonical_id,
            message_datetime=_MSG_DT,
            reporter_worker=mike,
            default_project_id=p.canonical_id,
        )
        c = claims[0]
        assert c.claim_type == "activity_only"
        assert c.total_hours_reported is None
        assert c.total_hours_computed is None
        assert c.activity_text == "finished basement framing"

    def test_non_labour_message_no_claims(self, db_session):
        p = _project(db_session)
        ev = _event(db_session, "what time is the meeting?")
        ex = MockTelegramLabourExtractor()  # default -> document_type "other"
        claims = ingest_telegram_labour_claims(
            db_session,
            ex,
            text=ev.raw_text,
            source_event_id=ev.canonical_id,
            message_datetime=_MSG_DT,
            default_project_id=p.canonical_id,
        )
        assert claims == []


class TestEndToEndReinforcement:
    def test_telegram_self_report_reinforces_gmail(self, db_session):
        """A Telegram self-report + a Gmail claim for the same worker/project/date
        consolidate into ONE auto_reinforced shift."""
        p = _project(db_session)
        mike = _worker(db_session, "Mike")

        # Pre-existing Gmail claim (as the bridge would have produced).
        gmail = LabourClaim(
            canonical_id=uuid.uuid4(),
            source_channel="gmail",
            reported_for_worker_id=mike.canonical_id,
            employee_name_raw="Mike",
            employee_match_method="exact",
            project_id=p.canonical_id,
            work_date=date(2026, 6, 18),
            total_hours_reported=Decimal("8.5"),
            claim_type="labour_time",
            extraction_method="gmail_bridge",
        )
        db_session.add(gmail)
        db_session.flush()

        # Telegram self-report for the same shift.
        ev = _event(db_session, "worked rockland 7-4 half hour lunch")
        ex = MockTelegramLabourExtractor(
            _result(
                [
                    _claim_dict(
                        is_reporter_self=True,
                        time_arrived="07:00",
                        time_left="16:00",
                        lunch_hours=0.5,
                    )
                ]
            )
        )
        ingest_telegram_labour_claims(
            db_session,
            ex,
            text=ev.raw_text,
            source_event_id=ev.canonical_id,
            message_datetime=_MSG_DT,
            reporter_worker=mike,
            default_project_id=p.canonical_id,
        )
        db_session.commit()

        res = consolidate_claims(db_session, p.canonical_id)
        assert res.clusters == 1
        assert res.reinforced == 1
        cluster = db_session.query(LabourClaimCluster).one()
        assert cluster.status == "auto_reinforced"
        assert cluster.evidence_count == 2
