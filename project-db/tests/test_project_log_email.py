"""Project Log routing through Gmail email intake.

Verifies the classifier fork in email_intake._process_one: an image attachment
that is an ALTA PROJECT LOG is routed to the project-log path (and NOT the
field-note path), while a non-project-log image falls through to field notes.
Uses MockGmailPoller + MockProjectLogExtractor + MockFieldNoteExtractor; no API.
"""

from __future__ import annotations

import base64

import pytest

from project_db.ai.email_intake import MockGmailPoller, poll_mailbox
from project_db.ai.field_note_extraction import MockFieldNoteExtractor
from project_db.ai.project_log_extraction import MockProjectLogExtractor
from project_db.db.models import (
    EmailIngest,
    Project,
    ProjectLogEntry,
    ProjectLogSubmission,
)
from project_db.db.models.work import ProjectStatus

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _b64(text: str) -> str:
    return base64.urlsafe_b64encode(text.encode()).decode()


def _img_message(
    gmail_id: str,
    sender: str,
    to: str,
    *,
    filename: str,
    body: str = "",
    image_bytes: bytes = b"\xff\xd8\xff\xe0\x00\x10JFIF-fake-bytes",
) -> dict:
    parts = []
    if body:
        parts.append(
            {"mimeType": "text/plain", "body": {"data": _b64(body)}, "parts": [], "filename": ""}
        )
    parts.append(
        {
            "mimeType": "image/jpeg",
            "filename": filename,
            "body": {"data": base64.urlsafe_b64encode(image_bytes).decode()},
            "parts": [],
        }
    )
    return {
        "id": gmail_id,
        "threadId": "t1",
        "internalDate": "1700000000000",
        "payload": {
            "mimeType": "multipart/mixed",
            "headers": [
                {"name": "From", "value": sender},
                {"name": "To", "value": to},
                {"name": "Subject", "value": "Project Log"},
            ],
            "body": {"data": ""},
            "parts": parts,
        },
    }


def _pl_log_response(site="Rockland", confidence=0.95, rows=None):
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
            }
        ]
    return {
        "document_type": "project_log",
        "site_name": site,
        "classification_confidence": confidence,
        "rows": rows,
    }


def _pl_other_response():
    return {
        "document_type": "other",
        "site_name": None,
        "classification_confidence": 0.05,
        "rows": [],
    }


@pytest.fixture
def rockland(session, client_factory):
    c = client_factory(name="Rockland Owner")
    p = Project(
        name="923-927 Rockland",
        code="R923",
        status=ProjectStatus.ACTIVE,
        client_id=c.canonical_id,
    )
    session.add(p)
    session.commit()
    return p


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_project_log_image_routed_to_project_log_path(session, rockland, tmp_path):
    """A project-log image is handled by the project-log path, NOT field notes."""
    msg = _img_message(
        "pl001",
        "supervisor@example.com",
        "logs@company.com",  # no plus-tag; site name resolves the project
        filename="ALTA_Project_Log.jpg",
    )
    poller = MockGmailPoller([msg])
    field_ex = MockFieldNoteExtractor()
    pl_ex = MockProjectLogExtractor([_pl_log_response()])

    batch = poll_mailbox(
        session,
        field_ex,
        poller,
        attachment_dir=str(tmp_path),
        project_log_extractor=pl_ex,
    )

    assert batch.processed == 1
    assert len(batch.project_log_batches) == 1
    # Field-note extractor must NOT have been invoked for this email.
    assert field_ex.calls == []
    # Project-log extractor was invoked once.
    assert len(pl_ex.calls) == 1

    sub = session.query(ProjectLogSubmission).one()
    assert sub.ingestion_status == "parsed"
    assert sub.project_id == rockland.canonical_id  # resolved via site name
    assert session.query(ProjectLogEntry).count() == 1

    ingest = session.query(EmailIngest).filter_by(gmail_message_id="pl001").one()
    assert ingest.status == "processed"
    assert ingest.notes and "project_log" in ingest.notes


def test_non_project_log_image_falls_through_to_field_notes(session, rockland, tmp_path):
    """An image the classifier rejects continues to the field-note path."""
    msg = _img_message(
        "fn001",
        "marco@example.com",
        "fieldnotes+rockland@company.com",  # plus-tag resolves project for field notes
        filename="site_photo.jpg",
        body="poured the slab today",
    )
    poller = MockGmailPoller([msg])
    field_ex = MockFieldNoteExtractor()  # returns {"signals": []}
    pl_ex = MockProjectLogExtractor([_pl_other_response()])

    batch = poll_mailbox(
        session,
        field_ex,
        poller,
        attachment_dir=str(tmp_path),
        project_log_extractor=pl_ex,
    )

    assert batch.processed == 1
    assert batch.project_log_batches == []
    # Project-log classifier ran (once) and declined...
    assert len(pl_ex.calls) == 1
    # ...so the field-note extractor WAS invoked.
    assert len(field_ex.calls) == 1
    assert session.query(ProjectLogSubmission).count() == 0


def test_no_project_log_extractor_means_field_note_path(session, rockland, tmp_path):
    """Backward compat: without a project_log_extractor, nothing changes."""
    msg = _img_message(
        "fn002",
        "marco@example.com",
        "fieldnotes+rockland@company.com",
        filename="photo.jpg",
        body="finished framing",
    )
    poller = MockGmailPoller([msg])
    field_ex = MockFieldNoteExtractor()

    batch = poll_mailbox(session, field_ex, poller, attachment_dir=str(tmp_path))

    assert batch.processed == 1
    assert batch.project_log_batches == []
    assert len(field_ex.calls) == 1  # field-note path used as before


def test_project_log_routed_even_when_project_unresolved(session, tmp_path):
    """No project resolvable (unknown sender, no plus-tag, unmatchable site):
    still routed to project-log and quarantined as unknown_site -- never
    silently dropped into field notes."""
    msg = _img_message(
        "pl002",
        "stranger@example.com",
        "logs@company.com",
        filename="ALTA_Project_Log.jpg",
    )
    poller = MockGmailPoller([msg])
    field_ex = MockFieldNoteExtractor()
    pl_ex = MockProjectLogExtractor([_pl_log_response(site="Totally Unknown Site")])

    batch = poll_mailbox(
        session,
        field_ex,
        poller,
        attachment_dir=str(tmp_path),
        project_log_extractor=pl_ex,
    )

    assert batch.processed == 1
    assert field_ex.calls == []  # NOT field-noted
    sub = session.query(ProjectLogSubmission).one()
    assert sub.ingestion_status == "quarantined"
    assert sub.ingestion_reason == "unknown_site"
    assert sub.project_id is None
    # Raw rows preserved despite quarantine.
    assert session.query(ProjectLogEntry).count() == 1
