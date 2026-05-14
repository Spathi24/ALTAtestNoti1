"""Connector registry.

Lets the CLI / scheduler / future UI ask "give me the QuickBooks connector"
without knowing where it's imported from. Add new connectors here.
"""
from __future__ import annotations

from typing import Type

from project_db.connectors.base import BaseConnector
from project_db.connectors.gdrive.connector import GDriveConnector
from project_db.connectors.monday.connector import MondayConnector
from project_db.connectors.quickbooks.connector import QuickBooksConnector
from project_db.db.models import SourceSystem

_REGISTRY: dict[SourceSystem, Type[BaseConnector]] = {
    SourceSystem.MONDAY: MondayConnector,
    SourceSystem.QUICKBOOKS: QuickBooksConnector,
    SourceSystem.GOOGLE_DRIVE: GDriveConnector,
    # SourceSystem.COMPANYCAM: CompanyCamConnector,  # TODO v0.3
}


def get_connector_class(source: SourceSystem) -> Type[BaseConnector]:
    if source not in _REGISTRY:
        raise NotImplementedError(
            f"No connector registered for {source.value}. "
            f"See docs/adding-a-connector.md."
        )
    return _REGISTRY[source]


def available_sources() -> list[SourceSystem]:
    return list(_REGISTRY.keys())
