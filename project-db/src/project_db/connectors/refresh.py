"""Refresh orchestration: pull fresh data, then keep embeddings current.

One call that (1) delta-syncs the live connectors (Monday today; Drive when it
goes live), then (2) re-embeds any documents whose text CHANGED -- idempotent
via content_hash, so unchanged docs cost nothing. This is what answers "do we
re-embed every time?": no -- only the documents whose text actually changed.

Used by ``project_db refresh`` and by the web server's optional background
auto-refresh on startup. Every step is guarded: a connector without
credentials, or a transient API error, records itself in the report and the
refresh continues. ``run_refresh`` never raises.

Note on the document pipeline: a newly-synced Drive file only gains searchable
text after ``extract-content`` has run (that step needs the Drive client and is
left explicit/heavy). The embed step here runs on EVERY refresh, so the moment
``DocumentText`` changes by any means, the next refresh re-embeds exactly the
changed documents.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable

from sqlalchemy.orm import Session

from project_db.connectors import get_connector_class
from project_db.db.models import Organization, SourceSystem

# The connectors we actually refresh. QuickBooks / CompanyCam are deferred and
# would just error on missing creds, so they're not in the default set.
_DEFAULT_SOURCES = [SourceSystem.MONDAY, SourceSystem.GOOGLE_DRIVE]


@dataclass
class RefreshStep:
    name: str
    ok: bool
    summary: str = ""
    error: str | None = None


@dataclass
class RefreshReport:
    started_at: str
    finished_at: str | None = None
    duration_seconds: float = 0.0
    steps: list[RefreshStep] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return all(s.ok for s in self.steps) if self.steps else True

    def one_line(self) -> str:
        good = sum(1 for s in self.steps if s.ok)
        return (f"{good}/{len(self.steps)} step(s) ok"
                f" in {self.duration_seconds}s")


def run_refresh(
    session: Session,
    *,
    delta: bool = True,
    embed: bool = True,
    poll_mail: bool = False,
    embedding_provider: Any | None = None,
    sources: list[SourceSystem] | None = None,
    log: Callable[[str], None] | None = None,
) -> RefreshReport:
    """Sync the live connectors, then re-embed changed documents.

    Pure-ish orchestration over existing, tested operations. Commits after each
    connector so a later failure doesn't roll back earlier progress. Never
    raises -- inspect ``report.steps`` for per-step outcomes.
    """
    emit = log or (lambda _m: None)
    t0 = time.monotonic()
    report = RefreshReport(started_at=datetime.now(timezone.utc).isoformat())

    org = session.query(Organization).first()
    if org is None:
        report.steps.append(RefreshStep(
            "preflight", False, error="no organization (run init-db first)"))
        report.finished_at = datetime.now(timezone.utc).isoformat()
        return report

    srcs = _DEFAULT_SOURCES if sources is None else sources
    for source in srcs:
        name = f"sync:{source.value}"
        try:
            connector_cls = get_connector_class(source)
        except Exception as exc:  # noqa: BLE001 -- not registered / not impl
            report.steps.append(RefreshStep(name, False, error=f"unavailable: {exc}"))
            continue
        try:
            connector = connector_cls(session=session, organization_id=org.canonical_id)
            kwargs: dict[str, Any] = {}
            # --delta is meaningful for Monday; Drive deltas via changes.list.
            if delta and source == SourceSystem.MONDAY:
                kwargs["delta"] = True
            sync_report = connector.sync(**kwargs)
            session.commit()
            report.steps.append(RefreshStep(name, True, summary=sync_report.summary()))
            emit(f"[refresh] {name}: {sync_report.summary()}")
        except Exception as exc:  # noqa: BLE001 -- missing creds / API error
            session.rollback()
            report.steps.append(RefreshStep(name, False, error=str(exc)))
            emit(f"[refresh] {name} FAILED: {exc}")

    if embed:
        try:
            provider = embedding_provider
            if provider is None:
                from project_db.ai.embeddings import get_optional_embedding_provider
                provider = get_optional_embedding_provider()
            if provider is None:
                report.steps.append(RefreshStep(
                    "embed", False,
                    error="no embedding provider (set OPENAI_API_KEY to enable RAG)"))
            else:
                from project_db.ai.rag import embed_documents_for

                stats = embed_documents_for(session, provider)
                summary = (
                    f"{stats['documents_processed']} embedded, "
                    f"{stats['documents_skipped']} unchanged, "
                    f"{stats['chunks_embedded']} chunks, "
                    f"${stats['estimated_cost_usd']:.4f}"
                )
                report.steps.append(RefreshStep("embed", True, summary=summary))
                emit(f"[refresh] embed: {summary}")
        except Exception as exc:  # noqa: BLE001
            session.rollback()
            report.steps.append(RefreshStep("embed", False, error=str(exc)))
            emit(f"[refresh] embed FAILED: {exc}")

    if poll_mail:
        try:
            from project_db.ai.email_intake import GmailPoller, poll_mailbox
            from project_db.ai.field_note_extraction import OpenAIFieldNoteExtractor
            extractor = OpenAIFieldNoteExtractor()
            poller = GmailPoller()
            mail_batch = poll_mailbox(session, extractor, poller)
            summary = (
                f"{mail_batch.total_seen} seen, "
                f"{mail_batch.processed} processed, "
                f"{mail_batch.quarantined} quarantined, "
                f"{mail_batch.failed} failed"
            )
            report.steps.append(RefreshStep("poll-mail", mail_batch.ok, summary=summary))
            emit(f"[refresh] poll-mail: {summary}")
        except Exception as exc:  # noqa: BLE001
            session.rollback()
            report.steps.append(RefreshStep("poll-mail", False, error=str(exc)))
            emit(f"[refresh] poll-mail FAILED: {exc}")

    report.finished_at = datetime.now(timezone.utc).isoformat()
    report.duration_seconds = round(time.monotonic() - t0, 2)
    return report
