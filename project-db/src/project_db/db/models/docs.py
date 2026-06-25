"""Document references — actual files stay in Drive / CompanyCam / etc.

Beyond the canonical name/url/mime/storage_ref, we keep enough Drive-side
metadata to answer real questions without re-hitting the API:

  - modified_at_source / created_at_source: timestamps from the source system
  - size_bytes:        for filtering big binaries, sorting, quota planning
  - md5_checksum:      cheap "did the content actually change" signal
  - drive_id:          shared-drive id (None for personal My Drive files)
  - parent_folder_id:  first parent folder id (re-linkable to projects)
  - folder_path:       human-readable breadcrumb like "Active/923 Rockland/Contracts"
  - category:          which top-level Drive area the file lives in
                       (projects / company / real_estate / construction /
                       intelligence) — set deterministically from folder_path
  - owner_email:       so we know who owns it
  - is_trashed:        soft-delete signal from Drive
  - source_meta_json:  raw payload for anything we don't promote to a column
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import UUID

from project_db.db.base import Base, CanonicalMixin

# Status of a single parse run. Plain strings (schema-light style), not a DB enum.
PARSE_STATUSES = ("success", "failed", "skipped")

# Kinds of citeable evidence a parser can emit. Plain strings, not a DB enum.
EVIDENCE_TYPES = (
    "text_block",
    "table_region",
    "cell_range",
    "paragraph",
    "page",
    "sheet",
)


class Document(Base, CanonicalMixin):
    name = Column(String, nullable=False)
    mime_type = Column(String, nullable=True)
    url = Column(String, nullable=False)
    storage_ref = Column(String, nullable=True)

    # --- Source-system metadata (filled by Drive / CompanyCam connectors) ---
    created_at_source = Column(DateTime, nullable=True)
    modified_at_source = Column(DateTime, nullable=True)
    size_bytes = Column(BigInteger, nullable=True)
    md5_checksum = Column(String, nullable=True)
    drive_id = Column(String, nullable=True)
    parent_folder_id = Column(String, nullable=True)
    folder_path = Column(String, nullable=True)
    # Top-level Drive area: projects / company / real_estate / construction /
    # intelligence.  Project files also carry project_id; non-project files
    # have project_id NULL and rely on category for their home.
    category = Column(String, nullable=True)
    owner_email = Column(String, nullable=True)
    is_trashed = Column(Boolean, nullable=False, default=False)
    source_meta_json = Column(Text, nullable=True)

    project_id = Column(
        UUID(as_uuid=True),
        ForeignKey("project.canonical_id"),
        nullable=True,
    )
    deal_id = Column(
        UUID(as_uuid=True),
        ForeignKey("deal.canonical_id"),
        nullable=True,
    )
    client_id = Column(
        UUID(as_uuid=True),
        ForeignKey("client.canonical_id"),
        nullable=True,
    )


class DocumentText(Base):
    """Extracted text content for a Document. One row per Document, 1:1.

    Lives in its own table (not promoted onto Document) because the body can
    be megabytes and most queries don't need it. The `extraction_method`
    column doubles as a status marker: a row with method 'skipped-size' or
    'skipped-mime' means we looked at this Document and decided not to read
    it, which is different from never having tried.
    """

    document_id = Column(
        UUID(as_uuid=True),
        ForeignKey("document.canonical_id", ondelete="CASCADE"),
        primary_key=True,
    )
    extracted_text = Column(Text, nullable=True)
    extraction_method = Column(String, nullable=False)
    extracted_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    token_count = Column(Integer, nullable=True)


class DocumentParse(Base):
    """One parse run for one Document.

    The canonical parse artifact going forward. Records WHICH parser produced
    the artifact, what source hash it parsed, whether it succeeded, an
    LLM/human-readable rendering (`rendered_text`), and the structured parser
    output (`structured_json`). `DocumentText` becomes a compatibility view
    written FROM a successful parse's `rendered_text` (see
    `db/parse_compat.py`) so existing reports/search keep working.

    Status is a plain string in `PARSE_STATUSES` (success | failed | skipped) --
    schema-light, no DB enum, matching the rest of the project.
    """

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id = Column(
        UUID(as_uuid=True),
        ForeignKey("document.canonical_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    parser_name = Column(String, nullable=False)
    parser_version = Column(String, nullable=True)
    source_hash = Column(String, nullable=True)
    status = Column(String, nullable=False)  # one of PARSE_STATUSES
    rendered_text = Column(Text, nullable=True)
    structured_json = Column(Text, nullable=True)
    error = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    token_count = Column(Integer, nullable=True)


class EvidenceSpan(Base):
    """A citeable unit of evidence produced by a parse run.

    A PDF text block / table region, an XLSX sheet range or cell range, a CSV
    row group, a DOCX paragraph/table, or a page-level block. This is the anchor
    a financial claim cites (later slices add `evidence_span_id` FKs to the
    ledger), so every extracted number can answer "which page/sheet/range did
    this come from".

    `evidence_type` is a plain string in `EVIDENCE_TYPES`. `locator_json`,
    `content_json`, and `bbox_json` hold parser-specific structure as JSON text;
    `content_text` holds a readable rendering of the span.
    """

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id = Column(
        UUID(as_uuid=True),
        ForeignKey("document.canonical_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    parse_id = Column(
        UUID(as_uuid=True),
        ForeignKey("document_parse.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    evidence_type = Column(String, nullable=False)  # one of EVIDENCE_TYPES
    locator_json = Column(Text, nullable=True)
    content_text = Column(Text, nullable=True)
    content_json = Column(Text, nullable=True)
    bbox_json = Column(Text, nullable=True)
    confidence = Column(Float, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
