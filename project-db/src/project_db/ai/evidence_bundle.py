"""Read a document's stored evidence into an LLM-ready bundle (Slice 6a).

The financial extractors today read the flat ``DocumentText`` blob and run it
through ``tsv_to_markdown``. That loses exactly what makes a number trustworthy:
which sheet / page / cell range it came from, and which row is the header. A
vendor cost worksheet flattened to text reads like a client quote -- the root
cause of the audit errors this whole refactor targets.

This module is the READ side of the new spine. Given a ``Document`` that the new
parsers have already processed (``DocumentParse`` + ``EvidenceSpan``), it
assembles those spans into an ``EvidenceBundle``:

  * structured tables (headers + sampled rows) tagged with their sheet/page/range
    locator and the parser's ``header_confidence`` uncertainty signal,
  * page text blocks for PDFs,
  * a clean ``render_for_llm()`` that gives the model labelled tables instead of
    a flat blob, and
  * the hooks Slice 6b needs: ``is_low_confidence()`` (the deterministic ->
    LLM-escalation gate) and the span ids to link onto each extracted record
    (``evidence_span_id``).

PURE over the DB read: it builds the bundle and renders text; it does NOT call an
LLM, mutate the ledger, or touch ``DocumentText``. Callers that get ``None`` (no
successful parse yet) fall back to the legacy flat-text path -- this is additive.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy.orm import Session

from project_db.db.models import Document, DocumentParse, EvidenceSpan

# Below this header_confidence a table is "uncertain" -- the seam where Slice 6b
# escalates from the cheap deterministic read to an LLM (and then a stronger
# model). 0.5 is the parser's "ambiguous tie" rung (1.0 clear / 0.8 thinner /
# 0.5 ambiguous / 0.3 no header), so <0.5 means the header guess is a real coin
# flip, not merely a thinner-looking row.
LOW_CONFIDENCE_THRESHOLD = 0.5

_MAX_ROWS_PER_TABLE = 25
_DEFAULT_MAX_CHARS = 16_000


def _loads(blob: str | None) -> Any:
    if not blob:
        return None
    try:
        return json.loads(blob)
    except (json.JSONDecodeError, TypeError):
        return None


@dataclass
class BundleTable:
    """One structured table region, with its citeable locator."""

    span_id: Any
    evidence_type: str
    locator: dict[str, Any]
    headers: list[str]
    rows: list[dict[str, Any]]  # rows_sample: each {header: value}
    rows_preview: list[list[Any]]  # raw safety net when rows_sample is thin
    header_confidence: float | None

    @property
    def sheet(self) -> str | None:
        return self.locator.get("sheet")

    @property
    def page(self) -> int | None:
        return self.locator.get("page")

    def _label(self) -> str:
        bits: list[str] = []
        if self.sheet:
            bits.append(f"sheet '{self.sheet}'")
        if self.page is not None:
            bits.append(f"page {self.page}")
        rng = self.locator.get("range")
        if rng:
            bits.append(f"range {rng}")
        hr = self.locator.get("header_row")
        if hr:
            bits.append(f"header row {hr}")
        if self.header_confidence is not None:
            bits.append(f"header confidence {self.header_confidence:g}")
        return ", ".join(bits) or "table"

    def render(self) -> str:
        """Markdown rendering: a labelled header line + a real Markdown table."""
        out = [f"## Table -- {self._label()}"]
        rows = self.rows[:_MAX_ROWS_PER_TABLE]
        if self.headers and rows:
            out.append("| " + " | ".join(str(h) for h in self.headers) + " |")
            out.append("| " + " | ".join("---" for _ in self.headers) + " |")
            for r in rows:
                cells = [str(r.get(h, "")) for h in self.headers]
                out.append("| " + " | ".join(cells) + " |")
        elif self.rows_preview:
            # No clean header/rows -> show the raw preview so nothing is hidden.
            for raw in self.rows_preview[:_MAX_ROWS_PER_TABLE]:
                out.append("| " + " | ".join("" if c is None else str(c) for c in raw) + " |")
        return "\n".join(out)


@dataclass
class BundlePage:
    """One page-level text block (PDF)."""

    span_id: Any
    page: int | None
    text: str

    def render(self) -> str:
        head = f"## Page {self.page}" if self.page is not None else "## Page"
        return f"{head}\n{self.text}".rstrip()


@dataclass
class EvidenceBundle:
    """A document's stored evidence, assembled for an LLM and for linking."""

    document_id: Any
    parse_id: Any
    parser_name: str
    parser_version: str | None
    doc_name: str
    tables: list[BundleTable] = field(default_factory=list)
    pages: list[BundlePage] = field(default_factory=list)

    @property
    def parser_label(self) -> str:
        return (
            f"{self.parser_name}/{self.parser_version}" if self.parser_version else self.parser_name
        )

    @property
    def header_confidences(self) -> list[float]:
        return [t.header_confidence for t in self.tables if t.header_confidence is not None]

    @property
    def min_header_confidence(self) -> float | None:
        confs = self.header_confidences
        return min(confs) if confs else None

    def is_empty(self) -> bool:
        return not self.tables and not self.pages

    def is_low_confidence(self, threshold: float = LOW_CONFIDENCE_THRESHOLD) -> bool:
        """True when any table's header read is a coin flip -- the Slice-6b gate.

        A bundle with NO tables (e.g. pure page text, or an empty parse) is not
        "low confidence" here; that is a separate has-no-structure signal the
        caller can check via ``is_empty`` / ``tables``.
        """
        mn = self.min_header_confidence
        return mn is not None and mn < threshold

    def primary_span_id(self) -> Any | None:
        """The most representative span to cite on a record extracted from this
        doc: the table with the most sampled rows, else the first page span."""
        if self.tables:
            return max(self.tables, key=lambda t: len(t.rows)).span_id
        if self.pages:
            return self.pages[0].span_id
        return None

    def render_for_llm(self, *, max_chars: int = _DEFAULT_MAX_CHARS) -> str:
        """Clean, labelled rendering: tables first (where money lives), then pages."""
        parts = [f"# DOCUMENT: {self.doc_name}  (parsed by {self.parser_label})"]
        for t in self.tables:
            parts.append(t.render())
        for p in self.pages:
            if p.text:
                parts.append(p.render())
        return "\n\n".join(parts)[:max_chars]


def _latest_success_parse(session: Session, document_id: Any) -> DocumentParse | None:
    return (
        session.query(DocumentParse)
        .filter(DocumentParse.document_id == document_id, DocumentParse.status == "success")
        .order_by(DocumentParse.created_at.desc())
        .first()
    )


def build_evidence_bundle(session: Session, document: Document) -> EvidenceBundle | None:
    """Assemble *document*'s latest successful parse into an ``EvidenceBundle``.

    Returns ``None`` when the document has no successful parse yet, so the caller
    can fall back to the legacy flat ``DocumentText`` path (additive migration).
    """
    parse = _latest_success_parse(session, document.canonical_id)
    if parse is None:
        return None

    bundle = EvidenceBundle(
        document_id=document.canonical_id,
        parse_id=parse.id,
        parser_name=parse.parser_name,
        parser_version=parse.parser_version,
        doc_name=document.name or "",
    )

    spans = (
        session.query(EvidenceSpan)
        .filter(EvidenceSpan.parse_id == parse.id)
        .order_by(EvidenceSpan.created_at.asc())
        .all()
    )
    for span in spans:
        if span.evidence_type in ("table_region", "cell_range"):
            cj = _loads(span.content_json) or {}
            loc = _loads(span.locator_json) or {}
            headers = cj.get("headers") or []
            bundle.tables.append(
                BundleTable(
                    span_id=span.id,
                    evidence_type=span.evidence_type,
                    locator=loc if isinstance(loc, dict) else {},
                    headers=[str(h) for h in headers],
                    rows=cj.get("rows_sample") or [],
                    rows_preview=cj.get("rows_preview") or [],
                    header_confidence=(
                        cj.get("header_confidence")
                        if cj.get("header_confidence") is not None
                        else span.confidence
                    ),
                )
            )
        elif span.evidence_type in ("page", "text_block", "paragraph"):
            loc = _loads(span.locator_json) or {}
            text = span.content_text or ""
            if not text:
                cj = _loads(span.content_json) or {}
                text = cj.get("text") or ""
            bundle.pages.append(
                BundlePage(
                    span_id=span.id,
                    page=loc.get("page") if isinstance(loc, dict) else None,
                    text=text,
                )
            )
    return bundle
