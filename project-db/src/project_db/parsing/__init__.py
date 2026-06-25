"""Evidence-backed document parsing (Slice 2+).

Public API:
    ParsedDocument, ParsedEvidence, DocumentParser   -- the parser abstraction
    CsvParser                                          -- the first parser
    get_parser_for, register_parser, available_parsers -- MIME/extension routing
    parse_document_content, parse_documents            -- persist to the evidence spine

The spine: ``Document -> DocumentParse -> EvidenceSpan -> DocumentText (compat)``.
Parsers are pure (bytes -> ParsedDocument); `service` persists. Adding a parser
later is one `register_parser(...)` call -- see `router`.
"""

from __future__ import annotations

from project_db.parsing.base import DocumentParser, ParsedDocument, ParsedEvidence
from project_db.parsing.csv_parser import CsvParser
from project_db.parsing.router import available_parsers, get_parser_for, register_parser
from project_db.parsing.service import parse_document_content, parse_documents
from project_db.parsing.xlsx_parser import XlsxParser

__all__ = [
    "CsvParser",
    "DocumentParser",
    "ParsedDocument",
    "ParsedEvidence",
    "XlsxParser",
    "available_parsers",
    "get_parser_for",
    "parse_document_content",
    "parse_documents",
    "register_parser",
]
