"""QuickBooks Online REST API client.

Handles OAuth2 authentication, API calls, and pagination.

QB API uses REST/JSON (not GraphQL). The connector handles:
  - OAuth2 token management (refresh tokens)
  - Company/Realm ID management
  - Query language (QBOs use a custom QL similar to SQL)
  - Pagination via startPosition

Env vars:
  QB_CLIENT_ID — OAuth client ID
  QB_CLIENT_SECRET — OAuth client secret
  QB_REALM_ID — QBO company/realm ID
  QB_ACCESS_TOKEN — Current access token (or refresh from token store)
"""

from __future__ import annotations

import logging
import os
from typing import Any

import httpx

logger = logging.getLogger(__name__)

API_URL = "https://quickbooks.api.intuit.com"
API_VERSION = "v2"


class QuickBooksClient:
    """QuickBooks Online REST API client."""

    def __init__(
        self,
        client_id: str | None = None,
        client_secret: str | None = None,
        realm_id: str | None = None,
        access_token: str | None = None,
    ):
        """Initialize QB client with OAuth credentials.

        Args:
            client_id: OAuth client ID (or env QB_CLIENT_ID)
            client_secret: OAuth client secret (or env QB_CLIENT_SECRET)
            realm_id: QBO company realm ID (or env QB_REALM_ID)
            access_token: Current access token
        """
        self.client_id = client_id or os.environ.get("QB_CLIENT_ID")
        self.client_secret = client_secret or os.environ.get("QB_CLIENT_SECRET")
        self.realm_id = realm_id or os.environ.get("QB_REALM_ID")
        self.access_token = access_token or os.environ.get("QB_ACCESS_TOKEN")

        if not all([self.client_id, self.client_secret, self.realm_id]):
            raise RuntimeError(
                "QuickBooks credentials not set. "
                "Set QB_CLIENT_ID, QB_CLIENT_SECRET, QB_REALM_ID env vars."
            )

        self._http = httpx.Client(
            base_url=f"{API_URL}/{API_VERSION}/companies/{self.realm_id}",
            headers={
                "Authorization": f"Bearer {self.access_token}",
                "Accept": "application/json",
            },
            timeout=30.0,
        )

    # ------------------------------------------------------------------
    # Low-level query runner
    # ------------------------------------------------------------------

    def query(self, ql: str) -> list[dict[str, Any]]:
        """Execute a QB Query Language (QQL) query.

        QB uses a SQL-like query language (not GraphQL).

        Examples:
            "SELECT * FROM Invoice WHERE TxnDate > '2026-01-01'"
            "SELECT Id, DocNumber, TotalAmt FROM Invoice MAXRESULTS 100"

        Args:
            ql: The QB Query Language query string

        Returns:
            List of matching records (dicts)
        """
        params = {"query": ql}
        resp = self._http.get("/query", params=params)
        resp.raise_for_status()
        payload = resp.json()

        if "Fault" in payload:
            raise RuntimeError(f"QB API error: {payload['Fault']}")

        # QB returns QueryResponse with embedded records
        query_response = payload.get("QueryResponse", {})
        return query_response.get("entities", []) if query_response else []

    # ------------------------------------------------------------------
    # Invoices
    # ------------------------------------------------------------------

    def list_invoices(
        self,
        max_results: int = 100,
        start_position: int = 1,
    ) -> list[dict[str, Any]]:
        """Fetch invoices from QB.

        Args:
            max_results: Max records to return per call (1-1000)
            start_position: Pagination offset (1-indexed)

        Returns:
            List of invoice dicts
        """
        ql = f"SELECT * FROM Invoice MAXRESULTS {max_results} STARTPOSITION {start_position}"
        return self.query(ql)

    def list_invoices_updated_since(self, since_date: str) -> list[dict[str, Any]]:
        """Fetch invoices updated since a date (delta sync).

        Args:
            since_date: ISO-8601 date string (e.g., "2026-05-01")

        Returns:
            List of invoice dicts
        """
        ql = f"SELECT * FROM Invoice WHERE UpdatedTime > '{since_date}'"
        return self.query(ql)

    def get_invoice(self, invoice_id: str) -> dict[str, Any]:
        """Fetch a single invoice by ID."""
        ql = f"SELECT * FROM Invoice WHERE Id = '{invoice_id}'"
        results = self.query(ql)
        return results[0] if results else {}

    # ------------------------------------------------------------------
    # Customers
    # ------------------------------------------------------------------

    def list_customers(
        self,
        max_results: int = 100,
        start_position: int = 1,
    ) -> list[dict[str, Any]]:
        """Fetch customers from QB."""
        ql = f"SELECT * FROM Customer MAXRESULTS {max_results} STARTPOSITION {start_position}"
        return self.query(ql)

    def get_customer(self, customer_id: str) -> dict[str, Any]:
        """Fetch a single customer by ID."""
        ql = f"SELECT * FROM Customer WHERE Id = '{customer_id}'"
        results = self.query(ql)
        return results[0] if results else {}

    # ------------------------------------------------------------------
    # Estimates
    # ------------------------------------------------------------------

    def list_estimates(
        self,
        max_results: int = 100,
        start_position: int = 1,
    ) -> list[dict[str, Any]]:
        """Fetch estimates from QB."""
        ql = f"SELECT * FROM Estimate MAXRESULTS {max_results} STARTPOSITION {start_position}"
        return self.query(ql)

    # ------------------------------------------------------------------
    # Journal Entries (general ledger)
    # ------------------------------------------------------------------

    def list_journal_entries(
        self,
        max_results: int = 100,
        start_position: int = 1,
    ) -> list[dict[str, Any]]:
        """Fetch journal entries from QB."""
        ql = f"SELECT * FROM JournalEntry MAXRESULTS {max_results} STARTPOSITION {start_position}"
        return self.query(ql)

    # ------------------------------------------------------------------
    # Write operations (future work)
    # ------------------------------------------------------------------
    # TODO: Implement create/update mutations
    #   - create_invoice()
    #   - update_invoice_status()
    #   - create_customer()
    #   - etc.
