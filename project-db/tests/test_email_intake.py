"""Tests for Win 2 of the field-note MVP: Gmail API email intake.

Coverage:
  - Worker model creation (email + phone_gateway_email + default_project_id)
  - EmailIngest model creation + status values
  - FieldNote.email_ingest_id FK (set when note arrives via email)
  - _find_worker: matched by email, matched by phone_gateway, not found
  - _parse_plus_tag: plus-address tag extraction
  - _fuzzy_match_project: tag -> project canonical_id
  - _resolve_project_id: plus-tag wins; falls back to worker default
  - _extract_body_text: plain-text part, nested multipart, no text part
  - poll_mailbox: known sender happy path (processed + label applied)
  - poll_mailbox: unknown sender quarantined (label applied, no FieldNote)
  - poll_mailbox: duplicate message_id skipped (no second EmailIngest row)
  - poll_mailbox: empty body -> failed EmailIngest
  - poll_mailbox: no project resolved -> failed EmailIngest
  - poll_mailbox: multi-message batch
  - poll_mailbox: extractor returns no signals -> skipped (still processed row)
  - ingest_field_note: email_ingest_id set on FieldNote rows
  - MockGmailPoller: list_unprocessed / get_message / apply_label / ensure_labels
"""
from __future__ import annotations

import base64
import json
import uuid
from datetime import datetime

import pytest

from project_db.ai.email_intake import (
    MockGmailPoller,
    _auto_create_worker_stub,
    _extract_body_text,
    _find_worker,
    _fuzzy_match_project,
    _is_system_sender,
    _parse_plus_tag,
    _resolve_project_id,
    poll_mailbox,
    retry_quarantined,
)
from project_db.ai.field_note_extraction import MockFieldNoteExtractor, ingest_field_note
from project_db.db.models import (
    EmailIngest,
    FieldNote,
    NoteChannel,
    Project,
    Task,
    Worker,
)
from project_db.db.models.work import ProjectStatus, TaskStatus


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _b64(text: str) -> str:
    return base64.urlsafe_b64encode(text.encode()).decode()


def _make_message(
    gmail_id: str,
    sender: str,
    to: str,
    subject: str,
    body: str,
    *,
    thread_id: str = "thread1",
    rfc_id: str | None = None,
    internal_ms: int = 1_700_000_000_000,
) -> dict:
    headers = [
        {"name": "From", "value": sender},
        {"name": "To", "value": to},
        {"name": "Subject", "value": subject},
    ]
    if rfc_id:
        headers.append({"name": "Message-ID", "value": rfc_id})
    return {
        "id": gmail_id,
        "threadId": thread_id,
        "internalDate": str(internal_ms),
        "payload": {
            "mimeType": "text/plain",
            "headers": headers,
            "body": {"data": _b64(body)},
            "parts": [],
        },
    }


def _make_multipart_message(
    gmail_id: str,
    sender: str,
    to: str,
    body: str,
) -> dict:
    """A multipart/mixed message with one text/plain part."""
    return {
        "id": gmail_id,
        "threadId": "t2",
        "internalDate": "1700000001000",
        "payload": {
            "mimeType": "multipart/mixed",
            "headers": [
                {"name": "From", "value": sender},
                {"name": "To", "value": to},
                {"name": "Subject", "value": "Site update"},
            ],
            "body": {"data": ""},
            "parts": [
                {
                    "mimeType": "text/plain",
                    "body": {"data": _b64(body)},
                    "parts": [],
                    "filename": "",
                }
            ],
        },
    }


def _simple_extractor_done(task_index: int = 0) -> MockFieldNoteExtractor:
    return MockFieldNoteExtractor(responses=[{
        "signals": [{
            "classification": "task_done",
            "quoted_excerpt": "finished the work",
            "task_index": task_index,
            "proposed_status": "Done",
            "proposed_start_date": None,
            "proposed_end_date": None,
            "new_task_title": None,
            "workers": None,
            "hours_worked": None,
            "confidence": 0.9,
        }]
    }])


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


@pytest.fixture
def task(session, rockland):
    t = Task(
        title="Install silicone sealant",
        status=TaskStatus.TODO,
        project_id=rockland.canonical_id,
    )
    session.add(t)
    session.commit()
    return t


@pytest.fixture
def worker_marco(session, rockland):
    w = Worker(
        display_name="Marco",
        email="marco@example.com",
        default_project_id=rockland.canonical_id,
    )
    session.add(w)
    session.commit()
    return w


# ---------------------------------------------------------------------------
# Worker model tests
# ---------------------------------------------------------------------------


def test_worker_create(session, rockland):
    w = Worker(
        display_name="Carlos",
        email="carlos@example.com",
        phone_gateway_email="5141110000@txt.att.net",
        default_project_id=rockland.canonical_id,
        active=True,
    )
    session.add(w)
    session.commit()

    loaded = session.query(Worker).filter_by(email="carlos@example.com").one()
    assert loaded.display_name == "Carlos"
    assert loaded.phone_gateway_email == "5141110000@txt.att.net"
    assert str(loaded.default_project_id) == str(rockland.canonical_id)
    assert loaded.active is True


def test_worker_inactive_by_default_is_settable(session):
    w = Worker(display_name="Inactive", active=False)
    session.add(w)
    session.commit()
    loaded = session.query(Worker).filter_by(display_name="Inactive").one()
    assert loaded.active is False


def test_worker_role_tags_verified(session, rockland):
    """New categorization fields round-trip correctly."""
    w = Worker(
        display_name="Luis",
        email="luis@example.com",
        role="tradesman",
        tags="tiling,bathroom",
        verified=True,
        default_project_id=rockland.canonical_id,
    )
    session.add(w)
    session.commit()
    loaded = session.query(Worker).filter_by(email="luis@example.com").one()
    assert loaded.role == "tradesman"
    assert loaded.tags == "tiling,bathroom"
    assert loaded.verified is True


def test_worker_auto_stub_defaults_unverified(session):
    """Auto-created stubs have verified=False."""
    w = _auto_create_worker_stub(session, "newguy@example.com")
    session.commit()
    assert w.verified is False
    assert w.email == "newguy@example.com"
    assert w.display_name == "newguy@example.com"


# ---------------------------------------------------------------------------
# EmailIngest model tests
# ---------------------------------------------------------------------------


def test_email_ingest_create(session, rockland):
    row = EmailIngest(
        gmail_message_id="msg001",
        rfc_message_id="<abc@mail.gmail.com>",
        thread_id="thread001",
        sender_email="marco@example.com",
        subject="Site update",
        received_at=datetime(2026, 6, 12, 10, 0),
        status="pending",
        project_id=rockland.canonical_id,
    )
    session.add(row)
    session.commit()

    loaded = session.query(EmailIngest).filter_by(gmail_message_id="msg001").one()
    assert loaded.sender_email == "marco@example.com"
    assert loaded.status == "pending"
    assert str(loaded.project_id) == str(rockland.canonical_id)


def test_email_ingest_status_values(session):
    for status in ("pending", "processed", "quarantined", "duplicate", "failed"):
        row = EmailIngest(
            gmail_message_id=f"msg-{status}",
            received_at=datetime.utcnow(),
            status=status,
        )
        session.add(row)
    session.commit()
    rows = session.query(EmailIngest).all()
    statuses = {r.status for r in rows}
    assert {"pending", "processed", "quarantined", "duplicate", "failed"} <= statuses


# ---------------------------------------------------------------------------
# FieldNote.email_ingest_id FK
# ---------------------------------------------------------------------------


def test_field_note_email_ingest_id(session, rockland, task):
    ingest = EmailIngest(
        gmail_message_id="msg_fn_test",
        received_at=datetime.utcnow(),
        status="processed",
    )
    session.add(ingest)
    session.flush()

    extractor = _simple_extractor_done(task_index=0)
    batch = ingest_field_note(
        session,
        extractor,
        rockland.canonical_id,
        "finished the work on silicone",
        channel=NoteChannel.EMAIL,
        sender_ref="marco@example.com",
        email_ingest_id=str(ingest.canonical_id),
    )
    session.commit()

    assert batch.signal_count == 1
    fn = batch.field_notes[0]
    assert str(fn.email_ingest_id) == str(ingest.canonical_id)
    assert fn.channel == NoteChannel.EMAIL


# ---------------------------------------------------------------------------
# Helper function tests
# ---------------------------------------------------------------------------


def test_parse_plus_tag_present():
    assert _parse_plus_tag("fieldnotes+rockland@company.com") == "rockland"


def test_parse_plus_tag_absent():
    assert _parse_plus_tag("fieldnotes@company.com") is None


def test_parse_plus_tag_display_name():
    assert _parse_plus_tag("ALTA Notes <fieldnotes+site5@company.com>") == "site5"


def test_is_system_sender_noreply():
    assert _is_system_sender("noreply@accounts.google.com") is True
    assert _is_system_sender("no-reply@company.com") is True
    assert _is_system_sender("mailer-daemon@gmail.com") is True
    assert _is_system_sender("postmaster@domain.com") is True


def test_is_system_sender_human():
    assert _is_system_sender("marco@example.com") is False
    assert _is_system_sender("boss@company.com") is False
    assert _is_system_sender("fieldnotes@gmail.com") is False


def test_fuzzy_match_project(session, rockland):
    pid = _fuzzy_match_project(session, "rockland")
    assert pid == str(rockland.canonical_id)


def test_fuzzy_match_project_no_match(session, rockland):
    pid = _fuzzy_match_project(session, "nobodyhere")
    assert pid is None


def test_find_worker_by_email(session, worker_marco):
    found = _find_worker(session, "marco@example.com")
    assert found is not None
    assert str(found.canonical_id) == str(worker_marco.canonical_id)


def test_find_worker_by_email_case_insensitive(session, worker_marco):
    found = _find_worker(session, "MARCO@EXAMPLE.COM")
    assert found is not None


def test_find_worker_by_phone_gateway(session, rockland):
    w = Worker(
        display_name="Juan",
        phone_gateway_email="5145550099@txt.att.net",
        default_project_id=rockland.canonical_id,
    )
    session.add(w)
    session.commit()
    found = _find_worker(session, "5145550099@txt.att.net")
    assert found is not None
    assert found.display_name == "Juan"


def test_find_worker_not_found(session):
    found = _find_worker(session, "nobody@unknown.com")
    assert found is None


def test_find_worker_inactive_skipped(session, rockland):
    w = Worker(
        display_name="Former",
        email="former@example.com",
        default_project_id=rockland.canonical_id,
        active=False,
    )
    session.add(w)
    session.commit()
    assert _find_worker(session, "former@example.com") is None


def test_resolve_project_id_via_plus_tag(session, rockland, worker_marco):
    pid = _resolve_project_id(
        session,
        to_address="fieldnotes+rockland@company.com",
        worker=worker_marco,
    )
    assert pid == str(rockland.canonical_id)


def test_resolve_project_id_via_worker_default(session, rockland, worker_marco):
    pid = _resolve_project_id(
        session,
        to_address="fieldnotes@company.com",  # no plus tag
        worker=worker_marco,
    )
    assert pid == str(rockland.canonical_id)


def test_resolve_project_id_no_match(session, rockland, worker_marco):
    pid = _resolve_project_id(
        session,
        to_address="fieldnotes+zzznomatch@company.com",
        worker=worker_marco,
    )
    # Falls through to worker default
    assert pid == str(rockland.canonical_id)


def test_resolve_project_id_none_without_worker(session, rockland, monkeypatch):
    # GMAIL_DEFAULT_PROJECT_ID from .env must not pollute this test.
    monkeypatch.delenv("GMAIL_DEFAULT_PROJECT_ID", raising=False)
    pid = _resolve_project_id(
        session,
        to_address="fieldnotes@company.com",
        worker=None,
    )
    assert pid is None


def test_resolve_project_id_env_fallback(session, rockland, monkeypatch):
    """GMAIL_DEFAULT_PROJECT_ID env var used as last resort."""
    monkeypatch.setenv("GMAIL_DEFAULT_PROJECT_ID", str(rockland.canonical_id))
    pid = _resolve_project_id(
        session,
        to_address="fieldnotes@company.com",  # no plus-tag
        worker=None,
    )
    assert pid == str(rockland.canonical_id)


def test_resolve_project_id_env_fallback_name_fragment(session, rockland, monkeypatch):
    """GMAIL_DEFAULT_PROJECT_ID can be a project name fragment."""
    monkeypatch.setenv("GMAIL_DEFAULT_PROJECT_ID", "rockland")
    pid = _resolve_project_id(
        session,
        to_address="fieldnotes@company.com",
        worker=None,
    )
    assert pid == str(rockland.canonical_id)


# ---------------------------------------------------------------------------
# _extract_body_text
# ---------------------------------------------------------------------------


def test_extract_body_text_plain():
    payload = {"mimeType": "text/plain", "body": {"data": _b64("hello world")}, "parts": []}
    assert _extract_body_text(payload) == "hello world"


def test_extract_body_text_multipart():
    payload = {
        "mimeType": "multipart/alternative",
        "body": {"data": ""},
        "parts": [
            {"mimeType": "text/plain", "body": {"data": _b64("plain part")}, "parts": []},
            {"mimeType": "text/html", "body": {"data": _b64("<p>html</p>")}, "parts": []},
        ],
    }
    assert _extract_body_text(payload) == "plain part"


def test_extract_body_text_empty():
    payload = {"mimeType": "text/html", "body": {"data": _b64("<p>html only</p>")}, "parts": []}
    assert _extract_body_text(payload) == ""


# ---------------------------------------------------------------------------
# MockGmailPoller
# ---------------------------------------------------------------------------


def test_mock_poller_list_unprocessed():
    msg = _make_message("id1", "a@b.com", "fn@c.com", "s", "body")
    poller = MockGmailPoller([msg])
    listed = poller.list_unprocessed()
    assert len(listed) == 1
    assert listed[0]["id"] == "id1"


def test_mock_poller_get_message():
    msg = _make_message("id2", "a@b.com", "fn@c.com", "s", "body2")
    poller = MockGmailPoller([msg])
    assert poller.get_message("id2")["id"] == "id2"


def test_mock_poller_apply_label():
    poller = MockGmailPoller([])
    poller.apply_label("id3", "ALTA/Processed")
    assert ("id3", "ALTA/Processed", True) in poller.applied_labels


def test_mock_poller_ensure_labels():
    poller = MockGmailPoller([])
    poller.ensure_labels()
    assert poller.labels_ensured is True


# ---------------------------------------------------------------------------
# poll_mailbox: happy path
# ---------------------------------------------------------------------------


def test_poll_mailbox_happy_path(session, rockland, task, worker_marco):
    """Known sender + plus-address routing -> processed + label applied."""
    msg = _make_message(
        "happy001",
        "Marco <marco@example.com>",
        "fieldnotes+rockland@company.com",
        "Site update",
        "finished the work on silicone today",
    )
    poller = MockGmailPoller([msg])
    extractor = _simple_extractor_done(task_index=0)

    batch = poll_mailbox(session, extractor, poller)

    assert batch.total_seen == 1
    assert batch.processed == 1
    assert batch.quarantined == 0
    assert batch.failed == 0

    ingest = session.query(EmailIngest).filter_by(gmail_message_id="happy001").one()
    assert ingest.status == "processed"
    assert str(ingest.project_id) == str(rockland.canonical_id)

    fn_rows = session.query(FieldNote).filter_by(
        email_ingest_id=ingest.canonical_id
    ).all()
    assert len(fn_rows) == 1

    applied = [(mid, lbl) for mid, lbl, add in poller.applied_labels if add]
    assert ("happy001", "ALTA/Processed") in applied


def test_poll_mailbox_worker_default_project(session, rockland, task, worker_marco):
    """Worker default_project_id used when no plus-tag."""
    msg = _make_message(
        "default001",
        "marco@example.com",
        "fieldnotes@company.com",
        "Update",
        "finished the work on silicone",
    )
    poller = MockGmailPoller([msg])
    extractor = _simple_extractor_done(task_index=0)

    batch = poll_mailbox(session, extractor, poller)
    assert batch.processed == 1
    ingest = session.query(EmailIngest).filter_by(gmail_message_id="default001").one()
    assert str(ingest.project_id) == str(rockland.canonical_id)


# ---------------------------------------------------------------------------
# poll_mailbox: noreply / system quarantine
# ---------------------------------------------------------------------------


def test_poll_mailbox_noreply_sender_quarantined(session, rockland):
    """noreply senders are quarantined -- no Worker stub, no FieldNote."""
    msg = _make_message(
        "quar001",
        "noreply@accounts.google.com",
        "fieldnotes@company.com",
        "Welcome to Gmail",
        "Your account is ready.",
    )
    poller = MockGmailPoller([msg])
    extractor = MockFieldNoteExtractor()

    batch = poll_mailbox(session, extractor, poller)

    assert batch.quarantined == 1
    assert batch.processed == 0

    ingest = session.query(EmailIngest).filter_by(gmail_message_id="quar001").one()
    assert ingest.status == "quarantined"

    applied = [(mid, lbl) for mid, lbl, add in poller.applied_labels if add]
    assert ("quar001", "ALTA/Quarantine") in applied

    assert session.query(Worker).count() == 0
    assert session.query(FieldNote).count() == 0


def test_poll_mailbox_unknown_human_auto_creates_worker(session, rockland, task, monkeypatch):
    """Unknown human sender: auto-create Worker stub, process message."""
    monkeypatch.setenv("GMAIL_DEFAULT_PROJECT_ID", str(rockland.canonical_id))
    msg = _make_message(
        "newguy001",
        "newworker@example.com",
        "fieldnotes@company.com",
        "Site update",
        "finished the work on silicone",
    )
    poller = MockGmailPoller([msg])
    extractor = _simple_extractor_done(task_index=0)

    batch = poll_mailbox(session, extractor, poller)

    assert batch.processed == 1
    assert batch.quarantined == 0

    # Worker stub was auto-created
    stub = session.query(Worker).filter_by(email="newworker@example.com").one()
    assert stub.verified is False
    assert stub.display_name == "newworker@example.com"

    ingest = session.query(EmailIngest).filter_by(gmail_message_id="newguy001").one()
    assert ingest.status == "processed"


# ---------------------------------------------------------------------------
# poll_mailbox: dedup
# ---------------------------------------------------------------------------


def test_poll_mailbox_dedup_skips_duplicate(session, rockland, task, worker_marco):
    """Same gmail_message_id seen twice -> second run skips, marks duplicate."""
    msg = _make_message(
        "dup001",
        "marco@example.com",
        "fieldnotes+rockland@company.com",
        "Update",
        "finished the work on silicone",
    )
    poller = MockGmailPoller([msg])
    extractor = _simple_extractor_done(task_index=0)

    # First poll
    batch1 = poll_mailbox(session, extractor, poller)
    assert batch1.processed == 1

    # Restore the message (simulate it still appearing before label filter takes effect)
    poller2 = MockGmailPoller([msg])
    extractor2 = MockFieldNoteExtractor()

    batch2 = poll_mailbox(session, extractor2, poller2)
    assert batch2.duplicate == 1
    assert batch2.processed == 0

    # Only one EmailIngest row
    count = session.query(EmailIngest).filter_by(gmail_message_id="dup001").count()
    assert count == 1


# ---------------------------------------------------------------------------
# poll_mailbox: empty body
# ---------------------------------------------------------------------------


def test_poll_mailbox_empty_body_fails(session, rockland, worker_marco):
    """Empty body -> EmailIngest.status=failed."""
    msg = _make_message(
        "empty001",
        "marco@example.com",
        "fieldnotes+rockland@company.com",
        "Oops",
        "   ",  # whitespace only
    )
    poller = MockGmailPoller([msg])
    extractor = MockFieldNoteExtractor()

    batch = poll_mailbox(session, extractor, poller)
    assert batch.failed == 1

    ingest = session.query(EmailIngest).filter_by(gmail_message_id="empty001").one()
    assert ingest.status == "failed"
    assert "empty" in (ingest.failure_reason or "")

    applied = [(mid, lbl) for mid, lbl, add in poller.applied_labels if add]
    assert ("empty001", "ALTA/Failed") in applied


# ---------------------------------------------------------------------------
# poll_mailbox: no project resolved
# ---------------------------------------------------------------------------


def test_poll_mailbox_no_project_resolved_fails(session, rockland, monkeypatch):
    """Worker with no default_project + no matching plus-tag -> failed."""
    # GMAIL_DEFAULT_PROJECT_ID from .env must not act as a fallback here.
    monkeypatch.delenv("GMAIL_DEFAULT_PROJECT_ID", raising=False)
    w = Worker(display_name="Orphan", email="orphan@example.com")
    session.add(w)
    session.commit()

    msg = _make_message(
        "noproj001",
        "orphan@example.com",
        "fieldnotes@company.com",  # no plus-tag
        "Update",
        "some work happened",
    )
    poller = MockGmailPoller([msg])
    extractor = MockFieldNoteExtractor()

    batch = poll_mailbox(session, extractor, poller)
    assert batch.failed == 1

    ingest = session.query(EmailIngest).filter_by(gmail_message_id="noproj001").one()
    assert ingest.status == "failed"
    assert "project" in (ingest.failure_reason or "")


# ---------------------------------------------------------------------------
# poll_mailbox: extractor returns no signals
# ---------------------------------------------------------------------------


def test_poll_mailbox_no_signals_still_processed(session, rockland, task, worker_marco):
    """Extractor returns empty signals -> EmailIngest=processed, no FieldNote."""
    msg = _make_message(
        "nosig001",
        "marco@example.com",
        "fieldnotes+rockland@company.com",
        "vague",
        "something happened today",
    )
    poller = MockGmailPoller([msg])
    # Empty response (vague note)
    extractor = MockFieldNoteExtractor(responses=[{"signals": []}])

    batch = poll_mailbox(session, extractor, poller)
    assert batch.processed == 1
    assert batch.failed == 0

    fn_count = session.query(FieldNote).count()
    assert fn_count == 0

    ingest = session.query(EmailIngest).filter_by(gmail_message_id="nosig001").one()
    assert ingest.status == "processed"


# ---------------------------------------------------------------------------
# poll_mailbox: multipart body
# ---------------------------------------------------------------------------


def test_poll_mailbox_multipart_body(session, rockland, task, worker_marco):
    """multipart/mixed message -> body extracted from nested text/plain part."""
    msg = _make_multipart_message(
        "multi001",
        "marco@example.com",
        "fieldnotes+rockland@company.com",
        "finished the work on silicone",
    )
    poller = MockGmailPoller([msg])
    extractor = _simple_extractor_done(task_index=0)

    batch = poll_mailbox(session, extractor, poller)
    assert batch.processed == 1
    assert batch.field_note_batches[0].signal_count == 1


# ---------------------------------------------------------------------------
# poll_mailbox: multi-message batch
# ---------------------------------------------------------------------------


def test_poll_mailbox_multi_message_noreply_quarantined(session, rockland, task, worker_marco):
    """Known sender processed; noreply quarantined."""
    msg_known = _make_message(
        "batch001",
        "marco@example.com",
        "fieldnotes+rockland@company.com",
        "Update",
        "finished the work on silicone",
    )
    msg_noreply = _make_message(
        "batch002",
        "noreply@accounts.google.com",
        "fieldnotes@company.com",
        "Welcome",
        "Your account is ready.",
    )
    poller = MockGmailPoller([msg_known, msg_noreply])
    extractor = _simple_extractor_done(task_index=0)

    batch = poll_mailbox(session, extractor, poller)
    assert batch.total_seen == 2
    assert batch.processed == 1
    assert batch.quarantined == 1


def test_poll_mailbox_multi_message_unknown_human(session, rockland, task, worker_marco):
    """Known sender processed; unknown human auto-creates stub and also processed
    (via worker default from plus-tag on known-sender message)."""
    msg_known = _make_message(
        "batch101",
        "marco@example.com",
        "fieldnotes+rockland@company.com",
        "Update",
        "finished the work on silicone",
    )
    msg_new = _make_message(
        "batch102",
        "newbie@example.com",
        "fieldnotes+rockland@company.com",
        "Site note",
        "finished the work on silicone",
    )
    poller = MockGmailPoller([msg_known, msg_new])
    extractor = _simple_extractor_done(task_index=0)

    batch = poll_mailbox(session, extractor, poller)
    assert batch.total_seen == 2
    assert batch.processed == 2
    assert batch.quarantined == 0

    stub = session.query(Worker).filter_by(email="newbie@example.com").one()
    assert stub.verified is False


# ---------------------------------------------------------------------------
# retry_quarantined
# ---------------------------------------------------------------------------


def test_retry_quarantined_clears_rows(session):
    """retry_quarantined deletes quarantined EmailIngest rows."""
    for i in range(3):
        session.add(EmailIngest(
            gmail_message_id=f"q{i}",
            received_at=datetime.utcnow(),
            status="quarantined",
        ))
    session.add(EmailIngest(
        gmail_message_id="p1",
        received_at=datetime.utcnow(),
        status="processed",
    ))
    session.commit()

    count = retry_quarantined(session)
    assert count == 3

    remaining = session.query(EmailIngest).all()
    assert len(remaining) == 1
    assert remaining[0].gmail_message_id == "p1"


def test_retry_quarantined_empty(session):
    """retry_quarantined returns 0 when nothing to clear."""
    assert retry_quarantined(session) == 0


# ---------------------------------------------------------------------------
# poll_mailbox: email timestamp threading
# ---------------------------------------------------------------------------


def test_email_timestamp_flows_to_extractor_and_field_note(
    session, rockland, task, worker_marco
):
    """internalDate from Gmail is passed to ingest_field_note as received_at.

    Two assertions:
      1. The extractor's note_timestamp matches the email's internalDate (not
         utcnow()), so the LLM sees NOTE SENT in its prompt and can resolve
         'yesterday', 'next Monday', etc. into concrete ISO dates.
      2. FieldNote.received_at is the email's sent time, not ingest time.
    """
    from datetime import timezone

    # A specific internalDate: 2026-06-13 09:30:00 UTC expressed in milliseconds.
    ts_ms = 1_749_808_200_000  # python: datetime(2026,6,13,9,30,0,tzinfo=utc)
    msg = _make_message(
        "tsflow001",
        "Marco <marco@example.com>",
        "fieldnotes+rockland@company.com",
        "Timestamp threading test",
        "finished the work on silicone",
        internal_ms=ts_ms,
    )
    poller = MockGmailPoller([msg])
    extractor = _simple_extractor_done(task_index=0)

    batch = poll_mailbox(session, extractor, poller)
    assert batch.processed == 1

    # Compute the expected naive UTC datetime from internalDate (same formula
    # as email_intake.py).
    expected_ts = datetime.fromtimestamp(
        ts_ms / 1000.0, tz=timezone.utc
    ).replace(tzinfo=None)

    # 1. Extractor received the email's timestamp (not utcnow).
    assert len(extractor.timestamp_calls) == 1
    delta = abs((extractor.timestamp_calls[0] - expected_ts).total_seconds())
    assert delta < 1.0, (
        f"Expected extractor.note_timestamp ~{expected_ts}, "
        f"got {extractor.timestamp_calls[0]}"
    )

    # 2. FieldNote.received_at mirrors the email send time.
    fn_rows = session.query(FieldNote).filter_by(
        email_ingest_id=session.query(EmailIngest)
        .filter_by(gmail_message_id="tsflow001")
        .one()
        .canonical_id
    ).all()
    assert len(fn_rows) == 1
    fn_delta = abs((fn_rows[0].received_at - expected_ts).total_seconds())
    assert fn_delta < 1.0, (
        f"Expected FieldNote.received_at ~{expected_ts}, got {fn_rows[0].received_at}"
    )
