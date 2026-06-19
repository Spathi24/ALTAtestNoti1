"""Labour consolidation spine: Gmail bridge + deterministic claim clustering.

Implements the plan's Examples 1-5 (reinforce / foreman multi-worker /
single-source / conflict) as tests. No LLM, no Telegram transport -- pure
deterministic consolidation over LabourClaim rows.
"""

from __future__ import annotations

import json
import uuid
from datetime import date, datetime
from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from project_db.ai.labour_consolidation import (
    bridge_project_log_to_claims,
    consolidate_claims,
)
from project_db.db.base import Base
from project_db.db.models import (
    Client,
    Organization,
    Project,
    Worker,
)
from project_db.db.models.docs import Document
from project_db.db.models.labour_intake import (
    LabourClaim,
    LabourClaimCluster,
    LabourClaimClusterMember,
)
from project_db.db.models.project_log import ProjectLogEntry, ProjectLogSubmission
from project_db.db.models.work import ProjectStatus


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


def _claim(
    session,
    project,
    *,
    channel,
    worker=None,
    name=None,
    d=date(2026, 6, 18),
    reported=None,
    computed=None,
    arrived=None,
    left=None,
    claim_type="labour_time",
    source_confidence=0.9,
    review_status="pending",
    hours_mismatch=False,
):
    c = LabourClaim(
        canonical_id=uuid.uuid4(),
        source_channel=channel,
        reported_for_worker_id=worker.canonical_id if worker else None,
        employee_name_raw=name or (worker.display_name if worker else None),
        employee_match_method="exact" if worker else "unresolved",
        project_id=project.canonical_id,
        work_date=d,
        time_arrived=arrived,
        time_left=left,
        total_hours_reported=Decimal(str(reported)) if reported is not None else None,
        total_hours_computed=Decimal(str(computed)) if computed is not None else None,
        hours_mismatch=hours_mismatch,
        source_confidence=source_confidence,
        claim_type=claim_type,
        extraction_method="text_llm" if channel == "telegram" else "gmail_bridge",
        review_status=review_status,
    )
    session.add(c)
    session.flush()
    return c


# ---------------------------------------------------------------------------
# Gmail bridge
# ---------------------------------------------------------------------------


class TestGmailBridge:
    def _project_log(self, session, project, worker):
        doc = Document(
            canonical_id=uuid.uuid4(),
            name="Rockland Log.jpg",
            url="x",
            is_trashed=False,
            project_id=project.canonical_id,
        )
        session.add(doc)
        session.flush()
        sub = ProjectLogSubmission(
            canonical_id=uuid.uuid4(),
            project_id=project.canonical_id,
            source_email_message_id="m1",
            source_attachment_filename="Rockland Log.jpg",
            received_at=datetime(2026, 6, 18, 18, 0),
            document_type="project_log",
            ingestion_status="parsed",
        )
        session.add(sub)
        session.flush()
        e = ProjectLogEntry(
            canonical_id=uuid.uuid4(),
            submission_id=sub.canonical_id,
            project_id=project.canonical_id,
            work_date=date(2026, 6, 18),
            employee_name_raw="Mike",
            employee_id=worker.canonical_id,
            employee_match_method="exact",
            time_arrived="07:00",
            time_left="16:00",
            lunch_hours=Decimal("0.5"),
            total_hours_reported=Decimal("8.5"),
            total_hours_computed=Decimal("8.5"),
            hours_mismatch=False,
            row_index=1,
        )
        session.add(e)
        session.flush()
        return sub, e

    def test_bridge_creates_claim_per_entry(self, db_session):
        p = _project(db_session)
        w = _worker(db_session, "Mike")
        self._project_log(db_session, p, w)
        n = bridge_project_log_to_claims(db_session, p.canonical_id)
        db_session.commit()
        assert n == 1
        claims = (
            db_session.query(LabourClaim).filter(LabourClaim.project_id == p.canonical_id).all()
        )
        assert len(claims) == 1
        c = claims[0]
        assert c.source_channel == "gmail"
        assert c.reported_for_worker_id == w.canonical_id
        assert c.employee_name_raw == "Mike"
        assert c.total_hours_reported == Decimal("8.50")
        assert c.work_date == date(2026, 6, 18)
        assert c.reporter_role == "supervisor"

    def test_bridge_idempotent(self, db_session):
        p = _project(db_session)
        w = _worker(db_session, "Mike")
        self._project_log(db_session, p, w)
        bridge_project_log_to_claims(db_session, p.canonical_id)
        db_session.commit()
        bridge_project_log_to_claims(db_session, p.canonical_id)
        db_session.commit()
        assert (
            db_session.query(LabourClaim).filter(LabourClaim.project_id == p.canonical_id).count()
            == 1
        )


# ---------------------------------------------------------------------------
# Consolidation -- the plan's examples
# ---------------------------------------------------------------------------


class TestConsolidation:
    def test_example1_gmail_and_telegram_reinforce(self, db_session):
        p = _project(db_session)
        mike = _worker(db_session, "Mike")
        _claim(
            db_session, p, channel="gmail", worker=mike, reported=8.5, arrived="07:00", left="16:00"
        )
        _claim(
            db_session,
            p,
            channel="telegram",
            worker=mike,
            reported=8.5,
            arrived="07:00",
            left="16:00",
        )
        res = consolidate_claims(db_session, p.canonical_id)
        assert res.clusters == 1
        assert res.reinforced == 1
        cluster = db_session.query(LabourClaimCluster).one()
        assert cluster.status == "auto_reinforced"
        assert cluster.evidence_count == 2
        assert set(json.loads(cluster.source_channels_json)) == {"gmail", "telegram"}

    def test_example2_foreman_multi_worker(self, db_session):
        p = _project(db_session)
        for nm, hrs in [("John", 8), ("Mike", 7.5), ("Alex", 5)]:
            w = _worker(db_session, nm)
            _claim(db_session, p, channel="telegram", worker=w, reported=hrs)
        res = consolidate_claims(db_session, p.canonical_id)
        # Three distinct workers -> three separate shift clusters.
        assert res.clusters == 3
        assert res.single_source == 3

    def test_example3_telegram_only_single_source(self, db_session):
        p = _project(db_session)
        mike = _worker(db_session, "Mike")
        _claim(db_session, p, channel="telegram", worker=mike, reported=8)
        res = consolidate_claims(db_session, p.canonical_id)
        assert res.single_source == 1
        assert db_session.query(LabourClaimCluster).one().status == "auto_single_source"

    def test_low_confidence_single_source_is_flagged_but_confirmed(self, db_session):
        p = _project(db_session)
        mike = _worker(db_session, "Mike")
        c = _claim(
            db_session,
            p,
            channel="telegram",
            worker=mike,
            reported=8,
            source_confidence=0.4,
        )
        res = consolidate_claims(db_session, p.canonical_id)
        assert res.single_source == 1
        cluster = db_session.query(LabourClaimCluster).one()
        assert cluster.status == "auto_single_source"
        assert "low_confidence" in json.loads(cluster.conflict_flags_json)
        assert c.canonicalized is True

    def test_low_confidence_telegram_can_reinforce_reliable_gmail(self, db_session):
        p = _project(db_session)
        mike = _worker(db_session, "Mike")
        _claim(db_session, p, channel="gmail", worker=mike, reported=8)
        _claim(
            db_session,
            p,
            channel="telegram",
            worker=mike,
            reported=8,
            source_confidence=0.4,
        )
        res = consolidate_claims(db_session, p.canonical_id)
        assert res.reinforced == 1
        assert db_session.query(LabourClaimCluster).one().status == "auto_reinforced"

    def test_example5_conflict_surfaced(self, db_session):
        p = _project(db_session)
        mike = _worker(db_session, "Mike")
        _claim(db_session, p, channel="gmail", worker=mike, reported=8.5)
        _claim(db_session, p, channel="telegram", worker=mike, reported=5.0)
        res = consolidate_claims(db_session, p.canonical_id)
        assert res.conflict == 1
        cluster = db_session.query(LabourClaimCluster).one()
        assert cluster.status == "conflict"
        assert "hours" in json.loads(cluster.conflict_flags_json)
        # The conflict is surfaced, not silently collapsed.
        assert cluster.confidence <= 0.4

    def test_reported_vs_computed_mismatch_is_flagged_but_confirmed(self, db_session):
        """Nicholas/Rockland class: stated 8h but 7-4 minus half-hour computes 8.5."""
        p = _project(db_session)
        nicholas = _worker(db_session, "Nicholas")
        c = _claim(
            db_session,
            p,
            channel="telegram",
            worker=nicholas,
            reported=8,
            computed=8.5,
            arrived="07:00",
            left="16:00",
            hours_mismatch=True,
        )
        res = consolidate_claims(db_session, p.canonical_id)
        assert res.single_source == 1
        cluster = db_session.query(LabourClaimCluster).one()
        assert cluster.status == "auto_single_source"
        assert "hours_mismatch" in json.loads(cluster.conflict_flags_json)
        assert c.canonicalized is True

    def test_activity_only_not_canonical_labour(self, db_session):
        p = _project(db_session)
        mike = _worker(db_session, "Mike")
        c = _claim(
            db_session,
            p,
            channel="telegram",
            worker=mike,
            reported=None,
            claim_type="activity_only",
            review_status="needs_review",
        )
        res = consolidate_claims(db_session, p.canonical_id)
        assert res.needs_review == 1
        cluster = db_session.query(LabourClaimCluster).one()
        assert cluster.status == "needs_review"
        assert cluster.chosen_total_hours is None
        assert c.canonicalized is False
        assert db_session.query(ProjectLogEntry).count() == 0

    def test_correction_does_not_create_clean_duplicate_shift(self, db_session):
        p = _project(db_session)
        mike = _worker(db_session, "Mike")
        c = _claim(
            db_session,
            p,
            channel="telegram",
            worker=mike,
            reported=6,
            claim_type="correction",
            review_status="needs_review",
        )
        res = consolidate_claims(db_session, p.canonical_id)
        assert res.needs_review == 1
        cluster = db_session.query(LabourClaimCluster).one()
        assert cluster.status == "needs_review"
        assert "claim_type:correction" in json.loads(cluster.conflict_flags_json)
        assert c.canonicalized is False
        assert db_session.query(ProjectLogEntry).count() == 0

    def test_unresolved_worker_needs_review(self, db_session):
        p = _project(db_session)
        # name only, no resolved worker_id
        _claim(db_session, p, channel="telegram", worker=None, name="SomeNewGuy", reported=8)
        res = consolidate_claims(db_session, p.canonical_id)
        assert res.needs_review == 1
        assert db_session.query(LabourClaimCluster).one().status == "needs_review"

    def test_dateless_claim_singleton_needs_review(self, db_session):
        p = _project(db_session)
        mike = _worker(db_session, "Mike")
        _claim(db_session, p, channel="telegram", worker=mike, d=None, reported=8)
        res = consolidate_claims(db_session, p.canonical_id)
        assert res.needs_review == 1
        flags = json.loads(db_session.query(LabourClaimCluster).one().conflict_flags_json)
        assert "missing_date" in flags

    def test_claims_linked_to_cluster(self, db_session):
        p = _project(db_session)
        mike = _worker(db_session, "Mike")
        _claim(db_session, p, channel="gmail", worker=mike, reported=8.5)
        _claim(db_session, p, channel="telegram", worker=mike, reported=8.5)
        consolidate_claims(db_session, p.canonical_id)
        claims = (
            db_session.query(LabourClaim).filter(LabourClaim.project_id == p.canonical_id).all()
        )
        cluster_ids = {c.canonical_cluster_id for c in claims}
        assert len(cluster_ids) == 1 and None not in cluster_ids
        assert all(c.canonicalized for c in claims)  # reinforced -> canonicalized
        assert db_session.query(LabourClaimClusterMember).count() == 2

    def test_idempotent_rebuild(self, db_session):
        p = _project(db_session)
        mike = _worker(db_session, "Mike")
        _claim(db_session, p, channel="gmail", worker=mike, reported=8.5)
        _claim(db_session, p, channel="telegram", worker=mike, reported=8.5)
        consolidate_claims(db_session, p.canonical_id)
        consolidate_claims(db_session, p.canonical_id)
        assert db_session.query(LabourClaimCluster).count() == 1
        assert db_session.query(LabourClaimClusterMember).count() == 2

    def test_separate_dates_separate_clusters(self, db_session):
        p = _project(db_session)
        mike = _worker(db_session, "Mike")
        _claim(db_session, p, channel="gmail", worker=mike, d=date(2026, 6, 18), reported=8)
        _claim(db_session, p, channel="gmail", worker=mike, d=date(2026, 6, 19), reported=8)
        res = consolidate_claims(db_session, p.canonical_id)
        assert res.clusters == 2  # different dates = different shifts

    def test_two_sheets_same_day_merge_not_double_counted(self, db_session):
        """Two Project Log sheets for the same worker+day must merge into ONE
        shift cluster (evidence 2), never two -- the user's merge requirement."""
        p = _project(db_session)
        w = _worker(db_session, "Mike")
        # Reuse the bridge helper to make two submissions for the same worker/day.
        TestGmailBridge()._project_log(db_session, p, w)
        TestGmailBridge()._project_log(db_session, p, w)
        bridge_project_log_to_claims(db_session, p.canonical_id)
        db_session.commit()
        res = consolidate_claims(db_session, p.canonical_id)
        assert res.clusters == 1  # merged, not double-counted
        cluster = db_session.query(LabourClaimCluster).one()
        assert cluster.evidence_count == 2
        assert cluster.work_date == date(2026, 6, 18)


class TestReportLabour:
    def test_bad_ref(self, db_session):
        from project_db.ai.views import report_labour

        assert "error" in report_labour(db_session, "nope xyz")

    def test_confirmed_shift_and_roster(self, db_session):
        from project_db.ai.views import report_labour

        p = _project(db_session)
        mike = _worker(db_session, "Mike")
        _claim(db_session, p, channel="gmail", worker=mike, reported=8.5)
        _claim(db_session, p, channel="telegram", worker=mike, reported=8.5)
        consolidate_claims(db_session, p.canonical_id)
        rep = report_labour(db_session, "923-927 Rockland")
        assert rep["shift_count"] == 1
        assert rep["confirmed_count"] == 1
        assert rep["review_count"] == 0
        assert rep["total_hours"] == pytest.approx(8.5)
        assert rep["roster"][0]["worker"] == "Mike"
        assert rep["roster"][0]["hours"] == pytest.approx(8.5)
        assert rep["shifts"][0]["sources"] == ["gmail", "telegram"]

    def test_conflict_surfaced_as_exception(self, db_session):
        from project_db.ai.views import report_labour

        p = _project(db_session)
        mike = _worker(db_session, "Mike")
        _claim(db_session, p, channel="gmail", worker=mike, reported=8.5)
        _claim(db_session, p, channel="telegram", worker=mike, reported=5.0)
        consolidate_claims(db_session, p.canonical_id)
        rep = report_labour(db_session, "923-927 Rockland")
        assert rep["review_count"] == 1
        assert rep["confirmed_count"] == 0
        assert rep["exceptions"][0]["status"] == "conflict"
        assert rep["total_hours"] in (None, 0.0)  # nothing confirmed

    def test_unresolved_name_listed(self, db_session):
        from project_db.ai.views import report_labour

        p = _project(db_session)
        _claim(db_session, p, channel="telegram", worker=None, name="NewGuy", reported=8)
        consolidate_claims(db_session, p.canonical_id)
        rep = report_labour(db_session, "923-927 Rockland")
        assert "NewGuy" in rep["unresolved_names"]
        assert rep["review_count"] == 1  # unresolved worker -> needs_review
