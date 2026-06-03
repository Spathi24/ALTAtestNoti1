"""Tests for the refresh orchestration (sync + incremental re-embed).

Connectors are mocked (no live API). The embed step uses MockEmbeddingProvider.
Pins: per-step reporting, resilience (a failing connector doesn't abort the
run or the embed step), preflight when no org, and embed on/off.
"""
from __future__ import annotations

import pytest

from project_db.ai.embeddings import MockEmbeddingProvider
from project_db.connectors import refresh as refresh_mod
from project_db.connectors.refresh import run_refresh
from project_db.db.models import Document, DocumentChunk, Organization, SourceSystem
from project_db.db.models.docs import DocumentText


class _FakeReport:
    def __init__(self, text="synced 3 created / 1 updated"):
        self._text = text

    def summary(self):
        return self._text


class _FakeConnector:
    last_kwargs = None

    def __init__(self, *, session, organization_id):
        self.session = session
        self.organization_id = organization_id

    def sync(self, **kwargs):
        _FakeConnector.last_kwargs = kwargs
        return _FakeReport()


class _BoomConnector:
    def __init__(self, *, session, organization_id):
        pass

    def sync(self, **kwargs):
        raise RuntimeError("no credentials")


@pytest.fixture
def _org(session):
    o = Organization(name="Refresh Org")
    session.add(o)
    session.commit()
    return o


def _doc_with_text(session, name, body):
    d = Document(name=name, url=f"x://{name}", mime_type="application/pdf")
    session.add(d)
    session.flush()
    session.add(DocumentText(document_id=d.canonical_id, extracted_text=body,
                             extraction_method="test"))
    session.commit()
    return d


class TestRunRefresh:
    def test_no_org_preflight_fails(self, session):
        report = run_refresh(session, embed=False)
        assert report.steps[0].name == "preflight"
        assert report.steps[0].ok is False

    def test_monday_sync_step_ok_and_passes_delta(self, session, _org, monkeypatch):
        monkeypatch.setattr(refresh_mod, "get_connector_class",
                            lambda src: _FakeConnector)
        report = run_refresh(session, delta=True, embed=False,
                             sources=[SourceSystem.MONDAY])
        assert len(report.steps) == 1
        assert report.steps[0].ok is True
        assert "synced" in report.steps[0].summary
        assert _FakeConnector.last_kwargs == {"delta": True}
        assert report.ok is True

    def test_failing_connector_is_recorded_not_fatal(self, session, _org, monkeypatch):
        monkeypatch.setattr(refresh_mod, "get_connector_class",
                            lambda src: _BoomConnector)
        report = run_refresh(session, embed=False, sources=[SourceSystem.MONDAY])
        assert report.steps[0].ok is False
        assert "no credentials" in report.steps[0].error
        assert report.ok is False

    def test_embed_step_runs_with_provider(self, session, _org):
        _doc_with_text(session, "Contract.pdf", "client payment terms on signing")
        report = run_refresh(
            session, embed=True, sources=[],
            embedding_provider=MockEmbeddingProvider(dims=64),
        )
        embed_steps = [s for s in report.steps if s.name == "embed"]
        assert embed_steps and embed_steps[0].ok is True
        assert session.query(DocumentChunk).count() >= 1

    def test_embed_disabled_skips(self, session, _org):
        _doc_with_text(session, "Contract.pdf", "scope of work demolition")
        report = run_refresh(session, embed=False, sources=[])
        assert [s for s in report.steps if s.name == "embed"] == []
        assert session.query(DocumentChunk).count() == 0

    def test_embed_without_provider_reports_missing(self, session, _org, monkeypatch):
        # No provider passed AND resolver returns None -> a recorded (non-fatal)
        # "no embedding provider" step.
        monkeypatch.setattr(
            "project_db.ai.embeddings.get_optional_embedding_provider",
            lambda: None,
        )
        report = run_refresh(session, embed=True, sources=[])
        embed_steps = [s for s in report.steps if s.name == "embed"]
        assert embed_steps and embed_steps[0].ok is False
        assert "embedding provider" in embed_steps[0].error

    def test_one_line_summary(self, session, _org, monkeypatch):
        monkeypatch.setattr(refresh_mod, "get_connector_class",
                            lambda src: _FakeConnector)
        report = run_refresh(session, embed=False, sources=[SourceSystem.MONDAY])
        assert "step(s) ok" in report.one_line()
