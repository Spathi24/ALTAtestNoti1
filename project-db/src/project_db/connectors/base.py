"""Abstract Connector base class.

To add a new source system:

  1. Create a new package under `connectors/` (e.g. `quickbooks/`).
  2. Implement a `Client` that wraps the source API.
  3. Implement a `Connector(BaseConnector)` subclass.
  4. Register it in `registry.py`.

Every connector must implement `sync()`. Inside `sync()`, the connector pulls
records from the source, then for each record calls
`self.resolver.resolve_or_create(...)` to map it to a canonical entity.

The connector is responsible for:
  - Authentication / pagination / rate limiting against the source API
  - Mapping source-specific fields → canonical entity attributes
  - Choosing the right matcher per entity type (see `identity/matcher.py`)

The connector is NOT responsible for:
  - DB schema (lives in `db/models/`)
  - Identity resolution (lives in `identity/`)
  - Querying canonical data (lives in `ai/` and downstream consumers)
"""
from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from project_db.db.models import SourceSystem
from project_db.identity import IdentityResolver

logger = logging.getLogger(__name__)


@dataclass
class SyncReport:
    """What a connector run returns. Suitable for logging or surfacing in a UI."""

    source: SourceSystem
    started_at: datetime
    completed_at: datetime | None = None
    records_processed: int = 0
    records_created: int = 0
    records_matched: int = 0
    records_failed: int = 0
    errors: list[str] = field(default_factory=list)

    def summary(self) -> str:
        duration = (
            (self.completed_at - self.started_at).total_seconds()
            if self.completed_at
            else 0.0
        )
        return (
            f"[{self.source.value}] processed={self.records_processed} "
            f"created={self.records_created} matched={self.records_matched} "
            f"failed={self.records_failed} duration={duration:.1f}s"
        )


class BaseConnector(ABC):
    """Subclass this to integrate a new source system."""

    source: SourceSystem  # subclasses set this

    def __init__(
        self,
        *,
        session: Session,
        organization_id: Any,
        config: dict[str, Any] | None = None,
    ):
        self.session = session
        self.organization_id = organization_id
        self.config = config or {}
        self.resolver = IdentityResolver(session)
        self.report = SyncReport(source=self.source, started_at=datetime.utcnow())

    @abstractmethod
    def sync(self) -> SyncReport:
        """Pull data from the source and upsert into the canonical DB."""

    # ----- helpers subclasses can use -----

    def _record_result(self, was_created: bool, was_matched: bool) -> None:
        self.report.records_processed += 1
        if was_created and not was_matched:
            self.report.records_created += 1
        if was_matched:
            self.report.records_matched += 1

    def _record_failure(self, msg: str) -> None:
        self.report.records_failed += 1
        self.report.errors.append(msg)
        logger.error("[%s] %s", self.source.value, msg)

    def _finalize(self) -> SyncReport:
        self.report.completed_at = datetime.utcnow()
        logger.info(self.report.summary())
        return self.report
