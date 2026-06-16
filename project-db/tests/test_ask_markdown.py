"""/ask renders LLM responses as markdown.

Background: bug report 2025-05-26 -- Haiku's markdown-formatted answer
came back as one long line of unformatted text.  The fix renders the
LLM's response through `markdown` -> HTML before passing to the
template.  This file pins:
  - LLM answers go through markdown rendering (`format == "html"`)
  - Bold / italic / lists / line breaks survive
  - HTML embedded in the LLM output is escaped (safety net)
  - Canned-report dict/list answers still go through JSON path
"""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

fastapi = pytest.importorskip("fastapi")
pytest.importorskip("markdown")
from fastapi.testclient import TestClient

from project_db.db.base import Base


@pytest.fixture
def db_engine():
    engine = create_engine(
        "sqlite:///:memory:",
        future=True,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    yield engine
    engine.dispose()


@pytest.fixture
def patched_session_factory(db_engine, monkeypatch):
    from project_db.db import session as session_mod

    factory = sessionmaker(bind=db_engine, expire_on_commit=False)
    monkeypatch.setattr(session_mod, "_SessionLocal", factory)
    yield factory


@pytest.fixture
def client(patched_session_factory):
    from project_db.web.app import create_app

    return TestClient(create_app())


@pytest.fixture
def fake_haiku(monkeypatch):
    """Mock get_fast_provider so /ask's no-match fallback hits a fake."""
    from project_db.ai.providers import mock as mock_mod

    prov = mock_mod.MockLLMProvider(
        responses=[
            "Based on the snapshot, **923 Rockland** appears most at risk:\n\n"
            "- 63 dateless tasks\n"
            "- 3 documents only\n\n"
            "Recommended: run `propose timelines` for that project."
        ]
    )
    monkeypatch.setattr(
        "project_db.ai.providers.get_fast_provider",
        lambda: prov,
    )
    return prov


def test_unit_markdown_renders_bold_and_lists():
    from project_db.web.routes.ask import _render_markdown

    html = _render_markdown("Hello **world**.\n\n- one\n- two\n\nNext paragraph.")
    assert "<strong>world</strong>" in html
    # markdown's `extra` extension produces standard <ul><li>
    assert "<ul>" in html
    assert "<li>one</li>" in html
    assert "<li>two</li>" in html
    # Two distinct paragraphs
    assert html.count("<p>") >= 2


def test_unit_markdown_escapes_embedded_html():
    """Safety net: even though we render LLM output as HTML, raw HTML
    embedded by the model must NOT pass through."""
    from project_db.web.routes.ask import _render_markdown

    html = _render_markdown("Hello <script>alert('xss')</script> world")
    # The lib escapes the angle brackets -- the literal text appears,
    # the executable tag does not.
    assert "<script>" not in html
    assert "&lt;script&gt;" in html


def test_post_llm_fallback_returns_rendered_markdown(client, fake_haiku):
    resp = client.post(
        "/ask",
        data={"question": "which project looks most at risk?"},
    )
    assert resp.status_code == 200
    body = resp.text
    # Rendered output must include the formatting we asked Haiku to use.
    assert "<strong>923 Rockland</strong>" in body
    assert "<li>63 dateless tasks</li>" in body
    assert "<code>propose timelines</code>" in body
    # The raw markdown source must NOT appear unrendered.
    assert "**923 Rockland**" not in body
    assert "- 63 dateless tasks" not in body


def test_post_canned_still_uses_json_format(client):
    """Canned reports return dicts/lists.  They go through the JSON
    branch and render inside a <pre>, NOT through markdown."""
    resp = client.post("/ask", data={"question": "help"})
    assert resp.status_code == 200
    body = resp.text
    # Help response is a dict -- rendered as JSON inside <pre>
    assert "<pre" in body
    # Sanity: the help payload includes the routed patterns
    assert "active_projects" in body or "deal_pipeline_value" in body
