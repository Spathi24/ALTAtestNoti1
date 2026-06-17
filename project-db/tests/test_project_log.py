"""Project Log ingestion (Win: labour/time-sheet images).

Covers the deterministic validation helpers (pure) and the ingest_project_log /
email-batch service against an in-memory DB with a MockProjectLogExtractor.
No API calls, no real client data.
"""

from __future__ import annotations

import csv as _csv
import json
import os
import uuid
from datetime import date, datetime
from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from project_db.ai.project_log_extraction import (
    MockProjectLogExtractor,
    _compute_hours,
    _normalize_date,
    _normalize_time,
    _to_decimal,
    _validate_row,
    ingest_project_log,
    ingest_project_logs_from_email,
)
from project_db.db.base import Base
from project_db.db.models import (
    Client,
    Organization,
    Project,
    ProjectLogEntry,
    ProjectLogSubmission,
    Worker,
    WorkerAlias,
)
from project_db.db.models.work import ProjectStatus

# ---------------------------------------------------------------------------
# Pure validation helpers
# ---------------------------------------------------------------------------


class TestNormalizeTime:
    @pytest.mark.parametrize(
        "raw,expected",
        [
            ("7:30", "07:30"),
            ("07:30", "07:30"),
            ("16:00", "16:00"),
            ("7:30 AM", "07:30"),
            ("7:30am", "07:30"),
            ("4 pm", "16:00"),
            ("4pm", "16:00"),
            ("12:00 AM", "00:00"),
            ("12:00 PM", "12:00"),
            ("12 am", "00:00"),
            ("0730", "07:30"),
            ("730", "07:30"),
            ("1600", "16:00"),
        ],
    )
    def test_valid(self, raw, expected):
        assert _normalize_time(raw) == expected

    @pytest.mark.parametrize("raw", [None, "", "   ", "garbage", "25:00", "7:99", "99"])
    def test_invalid_returns_none(self, raw):
        assert _normalize_time(raw) is None


class TestComputeHours:
    def test_basic_with_lunch(self):
        assert _compute_hours("07:30", "16:00", Decimal("0.5")) == Decimal("8.00")

    def test_no_lunch(self):
        assert _compute_hours("08:00", "16:00", None) == Decimal("8.00")

    def test_missing_time_returns_none(self):
        assert _compute_hours(None, "16:00", Decimal("0.5")) is None
        assert _compute_hours("08:00", None, None) is None

    def test_overnight_returns_none(self):
        # left before arrived -> implausible for a day log
        assert _compute_hours("16:00", "07:30", Decimal("0.5")) is None

    def test_lunch_exceeds_span_returns_none(self):
        assert _compute_hours("08:00", "08:30", Decimal("1.0")) is None


class TestNormalizeDate:
    def test_iso(self):
        assert _normalize_date("2026-06-17") == date(2026, 6, 17)

    def test_us_slash(self):
        assert _normalize_date("06/17/2026") == date(2026, 6, 17)

    @pytest.mark.parametrize("raw", [None, "", "garbage", "2026-13-99"])
    def test_invalid(self, raw):
        assert _normalize_date(raw) is None


class TestToDecimal:
    def test_basic(self):
        assert _to_decimal("8") == Decimal("8.00")
        assert _to_decimal(0.5) == Decimal("0.50")

    def test_comma_decimal(self):
        assert _to_decimal("0,5") == Decimal("0.50")

    def test_negative_dropped(self):
        assert _to_decimal("-1") is None

    @pytest.mark.parametrize("raw", [None, "abc", ""])
    def test_invalid(self, raw):
        assert _to_decimal(raw) is None


class TestValidateRow:
    def test_clean_row_no_mismatch(self):
        v = _validate_row(
            {
                "row_index": 1,
                "date": "2026-06-17",
                "name": "Mike",
                "time_arrived": "07:30",
                "time_left": "16:00",
                "lunch_hours": 0.5,
                "total_hours_reported": 8.0,
                "supervisor_signature_present": True,
                "confidence": 0.9,
                "raw_notes": None,
            }
        )
        assert not v.is_blank
        assert v.total_hours_computed == Decimal("8.00")
        assert v.total_hours_reported == Decimal("8.00")
        assert v.hours_mismatch is False
        assert v.missing_fields == []
        assert v.supervisor_signature_present is True

    def test_mismatch_flagged_reported_preserved(self):
        v = _validate_row(
            {
                "row_index": 2,
                "date": "2026-06-17",
                "name": "Sam",
                "time_arrived": "08:00",
                "time_left": "16:00",
                "lunch_hours": 0.0,
                "total_hours_reported": 9.0,  # says 9, computes 8
                "supervisor_signature_present": False,
                "confidence": 0.8,
                "raw_notes": None,
            }
        )
        assert v.total_hours_computed == Decimal("8.00")
        assert v.total_hours_reported == Decimal("9.00")  # NOT overwritten
        assert v.hours_mismatch is True

    def test_blank_row(self):
        v = _validate_row(
            {
                "row_index": 5,
                "date": None,
                "name": None,
                "time_arrived": None,
                "time_left": None,
                "lunch_hours": None,
                "total_hours_reported": None,
                "supervisor_signature_present": False,
                "confidence": 0.0,
                "raw_notes": None,
            }
        )
        assert v.is_blank is True

    def test_missing_fields_tracked(self):
        v = _validate_row(
            {
                "row_index": 3,
                "date": None,
                "name": "Pat",
                "time_arrived": "08:00",
                "time_left": None,
                "lunch_hours": None,
                "total_hours_reported": None,
                "supervisor_signature_present": False,
                "confidence": 0.5,
                "raw_notes": "smudged",
            }
        )
        assert "date" in v.missing_fields
        assert "time_left" in v.missing_fields
        assert "total_hours" in v.missing_fields
        assert v.raw_notes == "smudged"


# ---------------------------------------------------------------------------
# DB fixtures
# ---------------------------------------------------------------------------


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


def _seed_project(session, name="923-927 Rockland"):
    org = Organization(canonical_id=uuid.uuid4(), name="Test Org")
    client = Client(canonical_id=uuid.uuid4(), name="Test Client", organization_id=org.canonical_id)
    project = Project(
        canonical_id=uuid.uuid4(),
        name=name,
        status=ProjectStatus.ACTIVE,
        client_id=client.canonical_id,
    )
    session.add_all([org, client, project])
    session.flush()
    return project


def _pl_response(site="Rockland", confidence=0.95, rows=None, doc_type="project_log"):
    if rows is None:
        rows = [
            {
                "row_index": 1,
                "date": "2026-06-17",
                "name": "Mike",
                "time_arrived": "07:30",
                "time_left": "16:00",
                "lunch_hours": 0.5,
                "total_hours_reported": 8.0,
                "supervisor_signature_present": True,
                "confidence": 0.9,
                "raw_notes": None,
            },
            {
                "row_index": 2,
                "date": "2026-06-17",
                "name": "Sam",
                "time_arrived": "08:00",
                "time_left": "16:00",
                "lunch_hours": 0.0,
                "total_hours_reported": 9.0,  # mismatch (computes 8)
                "supervisor_signature_present": False,
                "confidence": 0.85,
                "raw_notes": None,
            },
        ]
    return {
        "document_type": doc_type,
        "site_name": site,
        "classification_confidence": confidence,
        "rows": rows,
    }


# ---------------------------------------------------------------------------
# ingest_project_log
# ---------------------------------------------------------------------------


class TestIngestProjectLog:
    def test_happy_path(self, db_session):
        project = _seed_project(db_session)
        ex = MockProjectLogExtractor([_pl_response()])
        res = ingest_project_log(
            db_session,
            ex,
            image_path="/tmp/log1.jpg",
            attachment_hash="hash1",
            source_email_message_id="msg1",
            received_at=datetime(2026, 6, 17, 18, 0),
        )
        assert res.handled is True
        assert res.ingestion_status == "parsed"
        assert res.entry_count == 2
        sub = res.submission
        assert sub.project_id == project.canonical_id
        assert sub.site_name_resolved == "923-927 Rockland"
        assert sub.classification_method == "vision_llm"
        assert sub.raw_extraction_json is not None
        # Row 1 clean, row 2 mismatch; reported preserved on both.
        entries = sorted(res.entries, key=lambda e: e.row_index)
        assert entries[0].total_hours_computed == Decimal("8.00")
        assert entries[0].hours_mismatch is False
        assert entries[1].total_hours_reported == Decimal("9.00")
        assert entries[1].hours_mismatch is True

    def test_not_a_project_log_is_not_handled(self, db_session):
        _seed_project(db_session)
        ex = MockProjectLogExtractor([_pl_response(doc_type="other", confidence=0.1, rows=[])])
        res = ingest_project_log(
            db_session, ex, image_path="/tmp/photo.jpg", source_email_message_id="m"
        )
        assert res.handled is False
        assert res.submission is None
        assert db_session.query(ProjectLogSubmission).count() == 0

    def test_low_confidence_quarantined(self, db_session):
        _seed_project(db_session)
        ex = MockProjectLogExtractor([_pl_response(confidence=0.3)])
        res = ingest_project_log(
            db_session, ex, image_path="/tmp/log.jpg", source_email_message_id="m"
        )
        assert res.handled is True  # claimed, not field-noted
        assert res.ingestion_status == "quarantined"
        assert res.ingestion_reason == "low_confidence_project_log_classification"
        assert res.entry_count == 0

    def test_unknown_site_quarantined_but_rows_kept(self, db_session):
        # No project seeded that matches; no hint -> unknown_site, rows preserved.
        ex = MockProjectLogExtractor([_pl_response(site="Nowhere Ville")])
        res = ingest_project_log(
            db_session, ex, image_path="/tmp/log.jpg", source_email_message_id="m"
        )
        assert res.handled is True
        assert res.ingestion_status == "quarantined"
        assert res.ingestion_reason == "unknown_site"
        assert res.submission.project_id is None
        assert res.entry_count == 2  # raw extraction preserved
        assert all(e.project_id is None for e in res.entries)
        # employee_name_raw is never discarded
        assert {e.employee_name_raw for e in res.entries} == {"Mike", "Sam"}

    def test_empty_form_skipped(self, db_session):
        _seed_project(db_session)
        blank = [
            {
                "row_index": 1,
                "date": None,
                "name": None,
                "time_arrived": None,
                "time_left": None,
                "lunch_hours": None,
                "total_hours_reported": None,
                "supervisor_signature_present": False,
                "confidence": 0.0,
                "raw_notes": None,
            }
        ]
        ex = MockProjectLogExtractor([_pl_response(rows=blank)])
        res = ingest_project_log(
            db_session, ex, image_path="/tmp/log.jpg", source_email_message_id="m"
        )
        assert res.ingestion_status == "skipped"
        assert res.ingestion_reason == "empty_form"
        assert res.entry_count == 0

    def test_no_rows_skipped(self, db_session):
        _seed_project(db_session)
        ex = MockProjectLogExtractor([_pl_response(rows=[])])
        res = ingest_project_log(
            db_session, ex, image_path="/tmp/log.jpg", source_email_message_id="m"
        )
        assert res.ingestion_status == "skipped"
        assert res.ingestion_reason == "no_rows_detected"

    def test_blank_rows_dropped(self, db_session):
        _seed_project(db_session)
        rows = _pl_response()["rows"] + [
            {
                "row_index": 3,
                "date": None,
                "name": None,
                "time_arrived": None,
                "time_left": None,
                "lunch_hours": None,
                "total_hours_reported": None,
                "supervisor_signature_present": False,
                "confidence": 0.0,
                "raw_notes": None,
            }
        ]
        ex = MockProjectLogExtractor([_pl_response(rows=rows)])
        res = ingest_project_log(
            db_session, ex, image_path="/tmp/log.jpg", source_email_message_id="m"
        )
        assert res.entry_count == 2  # the blank 3rd row dropped

    def test_employee_resolution_exact_and_alias(self, db_session):
        project = _seed_project(db_session)
        # Worker "Michael Smith"; alias "Mike" -> him.
        w = Worker(canonical_id=uuid.uuid4(), display_name="Sam", active=True)
        w2 = Worker(canonical_id=uuid.uuid4(), display_name="Michael Smith", active=True)
        db_session.add_all([w, w2])
        db_session.flush()
        db_session.add(
            WorkerAlias(
                canonical_id=uuid.uuid4(),
                worker_id=w2.canonical_id,
                alias_text="Mike",
                source="manual",
                confidence=0.95,
            )
        )
        db_session.flush()
        ex = MockProjectLogExtractor([_pl_response()])
        res = ingest_project_log(
            db_session, ex, image_path="/tmp/log.jpg", source_email_message_id="m"
        )
        by_name = {e.employee_name_raw: e for e in res.entries}
        # "Sam" -> exact
        assert by_name["Sam"].employee_id == w.canonical_id
        assert by_name["Sam"].employee_match_method == "exact"
        # "Mike" -> alias to Michael Smith
        assert by_name["Mike"].employee_id == w2.canonical_id
        assert by_name["Mike"].employee_match_method == "alias"

    def test_unresolved_employee_kept_raw(self, db_session):
        _seed_project(db_session)
        ex = MockProjectLogExtractor([_pl_response()])
        res = ingest_project_log(
            db_session, ex, image_path="/tmp/log.jpg", source_email_message_id="m"
        )
        for e in res.entries:
            assert e.employee_id is None
            assert e.employee_match_method == "unresolved"
            assert e.employee_name_raw in {"Mike", "Sam"}

    def test_project_hint_used_when_no_site_match(self, db_session):
        project = _seed_project(db_session)
        ex = MockProjectLogExtractor([_pl_response(site="Unmatchable Site XYZ")])
        res = ingest_project_log(
            db_session,
            ex,
            image_path="/tmp/log.jpg",
            source_email_message_id="m",
            project_hint=str(project.canonical_id),
        )
        assert res.ingestion_status == "parsed"
        assert res.submission.project_id == project.canonical_id

    def test_idempotent_replace(self, db_session):
        _seed_project(db_session)
        ex = MockProjectLogExtractor([_pl_response(), _pl_response()])
        ingest_project_log(
            db_session,
            ex,
            image_path="/tmp/log.jpg",
            attachment_hash="h1",
            source_email_message_id="msg1",
        )
        ingest_project_log(
            db_session,
            ex,
            image_path="/tmp/log.jpg",
            attachment_hash="h1",
            source_email_message_id="msg1",
        )
        assert db_session.query(ProjectLogSubmission).count() == 1
        assert db_session.query(ProjectLogEntry).count() == 2

    def test_raw_json_roundtrips(self, db_session):
        _seed_project(db_session)
        resp = _pl_response()
        ex = MockProjectLogExtractor([resp])
        res = ingest_project_log(
            db_session, ex, image_path="/tmp/log.jpg", source_email_message_id="m"
        )
        stored = json.loads(res.submission.raw_extraction_json)
        assert stored["document_type"] == "project_log"
        assert len(stored["rows"]) == 2


# ---------------------------------------------------------------------------
# Email batch
# ---------------------------------------------------------------------------


class TestEmailBatch:
    def test_two_attachments_one_log_one_other(self, db_session):
        _seed_project(db_session)
        ex = MockProjectLogExtractor(
            [
                _pl_response(),  # a.jpg -> project log
                _pl_response(doc_type="other", confidence=0.1, rows=[]),  # b.jpg -> other
            ]
        )
        batch = ingest_project_logs_from_email(
            db_session,
            ex,
            ["/tmp/a.jpg", "/tmp/b.jpg"],
            source_email_message_id="msg1",
        )
        assert batch.any_project_log is True
        assert sum(1 for r in batch.results if r.handled) == 1
        assert db_session.query(ProjectLogSubmission).count() == 1

    def test_two_project_logs_same_email_both_kept(self, db_session):
        _seed_project(db_session)
        ex = MockProjectLogExtractor([_pl_response(), _pl_response()])
        batch = ingest_project_logs_from_email(
            db_session, ex, ["/tmp/a.jpg", "/tmp/b.jpg"], source_email_message_id="msg1"
        )
        # Different filenames -> sibling attachments must NOT delete each other.
        assert db_session.query(ProjectLogSubmission).count() == 2
        assert batch.total_entries == 4

    def test_no_logs_means_not_handled(self, db_session):
        _seed_project(db_session)
        ex = MockProjectLogExtractor([_pl_response(doc_type="other", confidence=0.0, rows=[])])
        batch = ingest_project_logs_from_email(
            db_session, ex, ["/tmp/photo.jpg"], source_email_message_id="msg1"
        )
        assert batch.any_project_log is False


# ---------------------------------------------------------------------------
# report_project_log_hours
# ---------------------------------------------------------------------------


class TestReportHours:
    def test_empty_project(self, db_session):
        from project_db.ai.views import report_project_log_hours

        _seed_project(db_session)
        rep = report_project_log_hours(db_session, "923-927 Rockland")
        assert rep["entry_count"] == 0
        assert rep["employees"] == []

    def test_bad_ref(self, db_session):
        from project_db.ai.views import report_project_log_hours

        assert "error" in report_project_log_hours(db_session, "nope xyz")

    def test_grouping_and_totals(self, db_session):
        from project_db.ai.views import report_project_log_hours

        _seed_project(db_session)
        # Worker "Sam" exists (exact); "Mike" stays unresolved.
        w = Worker(canonical_id=uuid.uuid4(), display_name="Sam", active=True)
        db_session.add(w)
        db_session.flush()
        ex = MockProjectLogExtractor([_pl_response(), _pl_response()])
        # Two sheets, distinct filenames -> two submissions, 4 entries total.
        ingest_project_log(db_session, ex, image_path="/tmp/d1.jpg", source_email_message_id="m1")
        ingest_project_log(db_session, ex, image_path="/tmp/d2.jpg", source_email_message_id="m2")
        rep = report_project_log_hours(db_session, "923-927 Rockland")
        assert rep["submission_count"] == 2
        assert rep["entry_count"] == 4
        names = {e["name"]: e for e in rep["employees"]}
        # Sam resolved (grouped by worker across both sheets): 2 entries.
        assert names["Sam"]["resolved"] is True
        assert names["Sam"]["entries"] == 2
        # Mike unresolved but grouped by raw name across both sheets: 2 entries.
        assert names["Mike"]["resolved"] is False
        assert names["Mike"]["entries"] == 2
        # Sam computes 8h x2 = 16; reported 9h x2 = 18 (mismatch each).
        assert names["Sam"]["reported_hours"] == pytest.approx(18.0)
        assert names["Sam"]["mismatches"] == 2
        assert rep["mismatch_count"] == 2
        assert rep["unresolved_entry_count"] == 2
        # Days collapse to one distinct work_date.
        assert names["Sam"]["days"] == 1

    def test_submissions_listed_with_status(self, db_session):
        from project_db.ai.views import report_project_log_hours

        _seed_project(db_session)
        ex = MockProjectLogExtractor([_pl_response()])
        ingest_project_log(
            db_session, ex, image_path="/tmp/sheet.jpg", source_email_message_id="m1"
        )
        rep = report_project_log_hours(db_session, "923-927 Rockland")
        assert len(rep["submissions"]) == 1
        assert rep["submissions"][0]["status"] == "parsed"
        assert rep["submissions"][0]["document"] == "sheet.jpg"


# ---------------------------------------------------------------------------
# CSV export (mirror; DB stays source of truth)
# ---------------------------------------------------------------------------


_EXPECTED_CSV_HEADER = [
    "Received At",
    "Source File",
    "Site Name",
    "Resolved Project",
    "Date",
    "Name",
    "Time Arrived",
    "Time Left",
    "Lunch Hours",
    "Total Hours Reported",
    "Total Hours Computed",
    "Hours Mismatch",
    "Supervisor Signature Present",
    "Confidence",
    "Review Status",
]


class TestCsvExport:
    def test_export_writes_csv_under_generated_folder(self, db_session, tmp_path):
        from project_db.ai.project_log_export import export_project_log_csv

        _seed_project(db_session)
        ex = MockProjectLogExtractor([_pl_response()])
        ingest_project_log(db_session, ex, image_path="/tmp/log.jpg", source_email_message_id="m1")
        db_session.commit()

        path = export_project_log_csv(db_session, "923-927 Rockland", out_root=str(tmp_path))
        assert path is not None
        assert os.path.exists(path)
        # Lands under the generated-reports tree the Drive scanner skips.
        assert "ALTA Generated Reports" in path
        assert os.path.join("Project Logs", "923-927 Rockland") in path

        with open(path, newline="", encoding="utf-8") as fh:
            rows = list(_csv.reader(fh))
        assert rows[0] == _EXPECTED_CSV_HEADER
        assert len(rows) == 3  # header + Mike + Sam
        by_name = {r[5]: r for r in rows[1:]}
        sam = by_name["Sam"]
        assert sam[9] == "9.00"  # Total Hours Reported (preserved)
        assert sam[10] == "8.00"  # Total Hours Computed
        assert sam[11] == "yes"  # Hours Mismatch
        assert sam[3] == "923-927 Rockland"  # Resolved Project
        assert sam[14] == "parsed"  # Review Status

    def test_export_none_when_no_rows(self, db_session, tmp_path):
        from project_db.ai.project_log_export import export_project_log_csv

        _seed_project(db_session)
        assert (
            export_project_log_csv(db_session, "923-927 Rockland", out_root=str(tmp_path)) is None
        )

    def test_export_none_for_bad_ref(self, db_session, tmp_path):
        from project_db.ai.project_log_export import export_project_log_csv

        assert export_project_log_csv(db_session, "nonexistent xyz", out_root=str(tmp_path)) is None

    def test_export_idempotent_overwrite(self, db_session, tmp_path):
        from project_db.ai.project_log_export import export_project_log_csv

        _seed_project(db_session)
        ex = MockProjectLogExtractor([_pl_response(), _pl_response()])
        ingest_project_log(db_session, ex, image_path="/tmp/log.jpg", source_email_message_id="m1")
        db_session.commit()
        p1 = export_project_log_csv(db_session, "923-927 Rockland", out_root=str(tmp_path))
        p2 = export_project_log_csv(db_session, "923-927 Rockland", out_root=str(tmp_path))
        assert p1 == p2  # same path, overwritten (no duplicate files)
        with open(p1, newline="", encoding="utf-8") as fh:
            rows = list(_csv.reader(fh))
        assert len(rows) == 3  # still header + 2 rows, not doubled
