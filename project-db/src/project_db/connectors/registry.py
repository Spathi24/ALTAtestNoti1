"""Connector registry.

Lets the CLI / scheduler / future UI ask "give me the QuickBooks connector"
without knowing where it's imported from. Add new connectors here.
"""

from __future__ import annotations

from project_db.connectors.base import BaseConnector
from project_db.connectors.gdrive.connector import GDriveConnector
from project_db.connectors.monday.connector import MondayConnector
from project_db.connectors.quickbooks.connector import QuickBooksConnector
from project_db.db.models import SourceSystem

_REGISTRY: dict[SourceSystem, type[BaseConnector]] = {
    SourceSystem.MONDAY: MondayConnector,
    SourceSystem.QUICKBOOKS: QuickBooksConnector,
    SourceSystem.GOOGLE_DRIVE: GDriveConnector,
    # SourceSystem.COMPANYCAM: CompanyCamConnector,
    # Deferred per STRATEGY.md -- do not pick up until Monday+Drive produce
    # daily PM-facing value via the LLM reconciliation layer.
}


def get_connector_class(source: SourceSystem) -> type[BaseConnector]:
    if source not in _REGISTRY:
        raise NotImplementedError(
            f"No connector registered for {source.value}. See docs/adding-a-connector.md."
        )
    return _REGISTRY[source]


def available_sources() -> list[SourceSystem]:
    return list(_REGISTRY.keys())
