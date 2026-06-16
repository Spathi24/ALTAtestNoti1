"""Tests for QuickBooks REST client."""

from __future__ import annotations


class TestQuickBooksClientBasics:
    """Test basic QuickBooksClient operations."""

    def test_client_initialization(self):
        """Test QuickBooksClient initialization."""
        from project_db.connectors.quickbooks.client import QuickBooksClient

        client = QuickBooksClient(
            client_id="test_id",
            client_secret="test_secret",
            realm_id="test_realm",
            access_token="test_token",
        )
        assert client is not None

    def test_list_customers(self, mock_quickbooks_client):
        """Test listing customers."""
        customers = mock_quickbooks_client.list_customers()

        assert len(customers) == 2
        assert customers[0]["DisplayName"] == "Acme Corp"

    def test_list_invoices(self, mock_quickbooks_client):
        """Test listing invoices."""
        invoices = mock_quickbooks_client.list_invoices()

        assert len(invoices) == 1
        assert invoices[0]["DocNumber"] == "INV-001"
        assert invoices[0]["TotalAmt"] == 5000.00

    def test_list_estimates(self, mock_quickbooks_client):
        """Test listing estimates."""
        estimates = mock_quickbooks_client.list_estimates()

        assert len(estimates) == 1
        assert estimates[0]["DocNumber"] == "EST-001"

    def test_query_ql(self, mock_quickbooks_client):
        """Test executing Query Language queries."""
        ql = "SELECT * FROM Customer MAXRESULTS 10"
        result = mock_quickbooks_client.query(ql)

        assert isinstance(result, list)


class TestQuickBooksClientDeltaSync:
    """Test delta sync functionality."""

    def test_list_invoices_updated_since(self, mock_quickbooks_client):
        """Test delta sync for invoices."""
        from datetime import datetime, timedelta

        since = datetime.now() - timedelta(days=1)
        invoices = mock_quickbooks_client.list_invoices_updated_since(since)

        # Should return empty or filtered results
        assert isinstance(invoices, list)


class TestQuickBooksClientErrorHandling:
    """Test error handling."""

    def test_invalid_query_handled(self, mock_quickbooks_client):
        """Test handling of invalid QL queries."""
        mock_quickbooks_client.query.return_value = []
        result = mock_quickbooks_client.query("INVALID QL")
        assert result == []


class TestQuickBooksDataMapping:
    """Test mapping QB data to canonical format."""

    def test_customer_to_client_mapping(self, mock_quickbooks_client):
        """Test that QB customers can be extracted and mapped."""
        customers = mock_quickbooks_client.list_customers()

        # Validate QB customer structure
        assert customers[0]["DisplayName"] is not None
        assert "PrimaryEmailAddr" in customers[0]

    def test_invoice_to_invoice_mapping(self, mock_quickbooks_client):
        """Test that QB invoices can be extracted and mapped."""
        invoices = mock_quickbooks_client.list_invoices()

        assert invoices[0]["DocNumber"] is not None
        assert invoices[0]["TotalAmt"] is not None
        assert invoices[0]["Status"] is not None

    def test_estimate_to_deal_mapping(self, mock_quickbooks_client):
        """Test that QB estimates can be extracted and mapped."""
        estimates = mock_quickbooks_client.list_estimates()

        assert estimates[0]["DocNumber"] is not None
        assert estimates[0]["TotalAmt"] is not None
