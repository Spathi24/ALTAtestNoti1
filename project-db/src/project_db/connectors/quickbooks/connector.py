"""QuickBooks Online -> Canonical DB connector.

Syncs financial data from QB: invoices, estimates, customers, journal entries.
Maps to canonical Invoice, Deal, Client entities.

This connector demonstrates multi-system ripple effects:

1. PULL from QB:
   - Pull invoice data and link to Projects via job number
   - Pull customer data and link to existing Clients
   - Pull estimates for forecasting

2. CROSS-SYSTEM MATCHING:
   - Match QB invoice Job Number to canonical Project
   - Match QB customer to canonical Client (via email or name)
   - Update ExternalId mapping so we can find both directions

3. RIPPLE EFFECTS (future):
   - When invoice is paid in QB → update Project status → update Monday
   - When new expense in QB → update Project budget → alert team
   - When estimate created in QB → create Deal in Monday

The QB connector uses REST API + Query Language (not GraphQL).
Complexity is tracked via simple API call counting (no complex budget like Monday).
"""
from __future__ import annotations

import logging
from typing import Any

from project_db.connectors.base import BaseConnector, SyncReport
from project_db.connectors.quickbooks.client import QuickBooksClient
from project_db.db.models import Client, Deal, Invoice, InvoiceStatus, Project, SourceSystem
from project_db.identity.matcher import ExactFieldMatcher

logger = logging.getLogger(__name__)


class QuickBooksConnector(BaseConnector):
    """QuickBooks Online connector."""

    source = SourceSystem.QUICKBOOKS

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        from project_db.config import settings

        self.client = QuickBooksClient(
            client_id=self.config.get("client_id") or settings.qb_client_id,
            client_secret=self.config.get("client_secret") or settings.qb_client_secret,
            realm_id=self.config.get("realm_id") or settings.qb_realm_id,
            access_token=self.config.get("access_token") or settings.qb_access_token,
        )

    # ------------------------------------------------------------------
    # Entry point
    # ------------------------------------------------------------------

    def sync(self) -> SyncReport:
        """Sync QB data to canonical DB."""
        try:
            logger.info("Starting QuickBooks sync...")

            # 1. Sync customers first (so invoices can link to them)
            self._sync_customers()

            # 2. Sync invoices (link to projects via job number)
            self._sync_invoices()

            # 3. Sync estimates (for forecasting / deals)
            self._sync_estimates()

            logger.info(self.report.summary())

        except Exception as exc:  # noqa: BLE001
            self._record_failure(f"QB sync failed: {exc}")

        return self._finalize()

    # ------------------------------------------------------------------
    # Customers → Clients
    # ------------------------------------------------------------------

    def _sync_customers(self) -> None:
        """Sync QB customers to canonical Clients."""
        try:
            qb_customers = self.client.list_customers(max_results=1000)
            logger.info("Syncing %d QB customers", len(qb_customers))

            for qb_cust in qb_customers:
                try:
                    self._upsert_client(qb_cust)
                except Exception as exc:  # noqa: BLE001
                    self._record_failure(f"Customer {qb_cust.get('Id')}: {exc}")

        except Exception as exc:  # noqa: BLE001
            logger.warning("Customer sync failed (non-fatal): %s", exc)

    @staticmethod
    def _map_invoice_status(qb_status: str) -> InvoiceStatus:
        """Map QB invoice status to canonical InvoiceStatus."""
        status_map = {
            "DRAFT": InvoiceStatus.DRAFT,
            "SENT": InvoiceStatus.SENT,
            "VIEWED": InvoiceStatus.SENT,
            "PARTIAL": InvoiceStatus.PARTIAL,
            "PAID": InvoiceStatus.PAID,
            "OVERDUE": InvoiceStatus.OVERDUE,
            "VOID": InvoiceStatus.VOID,
        }
        return status_map.get(qb_status.upper(), InvoiceStatus.DRAFT)

    def _upsert_client(self, qb_customer: dict[str, Any]) -> None:
        """Map QB customer to canonical Client."""
        attrs: dict[str, Any] = {
            "name": qb_customer.get("DisplayName", "Unknown"),
            "organization_id": self.organization_id,
        }

        # Extract contact info if available
        if "BillAddr" in qb_customer:
            addr = qb_customer["BillAddr"]
            parts = []
            for key in ["Line1", "Line2", "City", "CountrySubDivisionCode", "PostalCode"]:
                if addr.get(key):
                    parts.append(addr[key])
            if parts:
                attrs["billing_address"] = ", ".join(parts)

        # Email from contact info
        if "PrimaryEmailAddr" in qb_customer:
            attrs["email"] = qb_customer["PrimaryEmailAddr"].get("Address")

        result = self.resolver.resolve_or_create(
            source=self.source,
            external_key=qb_customer["Id"],
            external_url=f"https://quickbooks.intuit.com/customer/{qb_customer['Id']}",
            entity_class=Client,
            attrs=attrs,
            matcher=ExactFieldMatcher(["name"]),
        )
        self._record_result(result.was_created, result.was_matched)

    # ------------------------------------------------------------------
    # Invoices
    # ------------------------------------------------------------------

    def _sync_invoices(self) -> None:
        """Sync QB invoices to canonical Invoices."""
        try:
            qb_invoices = self.client.list_invoices(max_results=1000)
            logger.info("Syncing %d QB invoices", len(qb_invoices))

            for qb_inv in qb_invoices:
                try:
                    self._upsert_invoice(qb_inv)
                except Exception as exc:  # noqa: BLE001
                    self._record_failure(f"Invoice {qb_inv.get('DocNumber')}: {exc}")

        except Exception as exc:  # noqa: BLE001
            logger.warning("Invoice sync failed (non-fatal): %s", exc)

    def _upsert_invoice(self, qb_invoice: dict[str, Any]) -> None:
        """Map QB invoice to canonical Invoice.
        
        Links invoices to Projects via QB custom field (job number).
        """
        from project_db.db.models import ExternalId

        # Extract job number (often stored in QB custom field as project reference)
        job_number = None
        if "CustomField" in qb_invoice and qb_invoice["CustomField"]:
            job_number = qb_invoice["CustomField"][0].get("StringValue")

        # Try to link to a Project if job number is available
        project_id = None
        if job_number:
            # Search canonical Projects for matching job number
            from sqlalchemy import or_

            matching_project = (
                self.session.query(Project)
                .filter(
                    or_(
                        Project.code == job_number,
                        Project.name.ilike(f"%{job_number}%"),
                    )
                )
                .first()
            )
            if matching_project:
                project_id = matching_project.canonical_id
                logger.debug(f"Linked QB invoice {qb_invoice['Id']} to project {project_id}")

        # Get client from QB customer ref
        client_id = None
        if "CustomerRef" in qb_invoice:
            customer_id = qb_invoice["CustomerRef"].get("value")
            if customer_id:
                # Look up the canonical client from our ExternalId mapping
                ext_id = (
                    self.session.query(ExternalId)
                    .filter_by(
                        source=self.source,
                        entity_type="Client",
                        external_key=customer_id,
                    )
                    .one_or_none()
                )
                if ext_id:
                    client_id = ext_id.canonical_id

        # Build invoice attributes (matching Invoice model fields)
        attrs: dict[str, Any] = {
            "number": qb_invoice.get("DocNumber", ""),
            "amount": float(qb_invoice.get("TotalAmt", 0)),
            "status": self._map_invoice_status(qb_invoice.get("Status", "DRAFT")),
            "project_id": project_id,
            "client_id": client_id,
            "organization_id": self.organization_id,
        }

        if "DueDate" in qb_invoice:
            attrs["due_date"] = qb_invoice["DueDate"]

        if "TxnDate" in qb_invoice:
            attrs["issue_date"] = qb_invoice["TxnDate"]

        result = self.resolver.resolve_or_create(
            source=self.source,
            external_key=qb_invoice["Id"],
            external_url=f"https://quickbooks.intuit.com/invoice/{qb_invoice['Id']}",
            entity_class=Invoice,
            attrs=attrs,
            matcher=ExactFieldMatcher(["number"]),
        )
        self._record_result(result.was_created, result.was_matched)

    # ------------------------------------------------------------------
    # Estimates → Deals
    # ------------------------------------------------------------------

    def _sync_estimates(self) -> None:
        """Sync QB estimates to canonical Deals."""
        try:
            qb_estimates = self.client.list_estimates(max_results=1000)
            logger.info("Syncing %d QB estimates", len(qb_estimates))

            for qb_est in qb_estimates:
                try:
                    self._upsert_deal(qb_est)
                except Exception as exc:  # noqa: BLE001
                    self._record_failure(f"Estimate {qb_est.get('DocNumber')}: {exc}")

        except Exception as exc:  # noqa: BLE001
            logger.warning("Estimate sync failed (non-fatal): %s", exc)

    def _upsert_deal(self, qb_estimate: dict[str, Any]) -> None:
        """Map QB estimate to canonical Deal (for pipeline forecasting)."""
        attrs: dict[str, Any] = {
            "name": f"Est-{qb_estimate.get('DocNumber')}",
            "stage": "PROPOSAL",  # Estimate = proposal stage
            "value": float(qb_estimate.get("TotalAmt", 0)),
            "organization_id": self.organization_id,
        }

        if "CustomerRef" in qb_estimate:
            # Try to link to a Client
            customer_id = qb_estimate["CustomerRef"].get("value")
            if customer_id:
                # Look up the canonical client from our ExternalId mapping
                from project_db.db.models import ExternalId

                ext_id = (
                    self.session.query(ExternalId)
                    .filter_by(
                        source=self.source,
                        entity_type="Client",
                        external_key=customer_id,
                    )
                    .one_or_none()
                )
                if ext_id:
                    attrs["client_id"] = ext_id.canonical_id

        result = self.resolver.resolve_or_create(
            source=self.source,
            external_key=qb_estimate["Id"],
            external_url=f"https://quickbooks.intuit.com/estimate/{qb_estimate['Id']}",
            entity_class=Deal,
            attrs=attrs,
            matcher=ExactFieldMatcher(["name"]),
        )
        self._record_result(result.was_created, result.was_matched)
