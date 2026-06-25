"""MIME/extension routing to a parser.

The registry is the single extension point for the whole refactor. Adding a
parser in a later slice is one line -- e.g. ``register_parser(XlsxParser())``
(Slice 3) or ``register_parser(DoclingPdfParser())`` (Slice 4). Order matters:
the first parser whose `can_parse` returns True wins, so register more specific
parsers before broad fallbacks.

Types with no registered parser route to ``None``; the service then records a
``skipped`` `DocumentParse` (not a failure), so an unimplemented format is
handled gracefully and "lights up" automatically once its parser is registered.
"""

from __future__ import annotations

from project_db.parsing.base import DocumentParser
from project_db.parsing.csv_parser import CsvParser
from project_db.parsing.pdf_parser import PdfParser
from project_db.parsing.xlsx_parser import XlsxParser

# Registered parsers, in priority order. DOCX registers here in its slice
# without touching callers.
_PARSERS: list[DocumentParser] = [
    CsvParser(),
    XlsxParser(),
    PdfParser(),
]


def register_parser(parser: DocumentParser, *, front: bool = False) -> None:
    """Add a parser to the registry. `front=True` gives it priority over
    already-registered parsers (use for a more specific matcher)."""
    if front:
        _PARSERS.insert(0, parser)
    else:
        _PARSERS.append(parser)


def get_parser_for(*, mime: str | None, filename: str | None) -> DocumentParser | None:
    """Return the first parser that handles this (mime, filename), or None."""
    for parser in _PARSERS:
        if parser.can_parse(mime=mime, filename=filename):
            return parser
    return None


def available_parsers() -> list[DocumentParser]:
    """Snapshot of the registry (for diagnostics/tests)."""
    return list(_PARSERS)
