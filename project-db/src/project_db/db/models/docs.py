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

from datetime import datetime

from sqlalchemy import BigInteger, Boolean, Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID

from project_db.db.base import Base, CanonicalMixin


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
