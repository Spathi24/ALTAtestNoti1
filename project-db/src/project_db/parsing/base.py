"""Parser abstraction for the evidence layer (Slice 2).

A parser turns one document's raw bytes into a `ParsedDocument`: a flat
`rendered_text` (for the `DocumentText` compatibility row + LLM/search), a
`structured` artifact (parser-native structure, stored as `structured_json`),
and a list of citeable `ParsedEvidence` spans (page/sheet/table/cell regions).

The `parsing.service` layer persists these into `DocumentParse` + `EvidenceSpan`
+ `DocumentText`. Parsers themselves are pure: no DB, no network -- they take
bytes and return a `ParsedDocument`, which makes them trivially testable.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable


@dataclass
class ParsedEvidence:
    """One citeable unit of evidence a parser emits.

    `evidence_type` must be one of `project_db.db.models.docs.EVIDENCE_TYPES`
    (validated at persist time). `locator` / `content_json` / `bbox` are
    parser-native dicts serialized to JSON; `content_text` is a readable
    rendering of the span.
    """

    evidence_type: str
    locator: dict | None = None
    content_text: str | None = None
    content_json: dict | None = None
    bbox: dict | None = None
    confidence: float | None = None


@dataclass
class ParsedDocument:
    """The full result of parsing one document."""

    rendered_text: str
    structured: dict = field(default_factory=dict)
    evidence_spans: list[ParsedEvidence] = field(default_factory=list)


@runtime_checkable
class DocumentParser(Protocol):
    """Duck-typed parser interface. A parser declares which inputs it handles
    (`can_parse`) and turns bytes into a `ParsedDocument` (`parse`).

    `name` + `version` land on `DocumentParse.parser_name` / `parser_version`
    (and become the `DocumentText.extraction_method`, e.g. ``csv/1``), so bump
    `version` when a parser's output changes.
    """

    name: str
    version: str

    def can_parse(self, *, mime: str | None, filename: str | None) -> bool: ...

    def parse(self, content: bytes, *, doc_name: str, mime: str | None) -> ParsedDocument: ...
