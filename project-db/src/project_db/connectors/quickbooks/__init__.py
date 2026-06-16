"""QuickBooks Online connector.

Pulls financial data: invoices, estimates, journal entries, customers.
Maps to canonical Invoice, Deal, and Client entities.

The QB connector demonstrates multi-system integration:
  - Pull invoice data from QB
  - Match invoices to canonical Projects via job number / external reference
  - Create ripple effects: Invoice status → update Monday project status
"""

from .connector import QuickBooksConnector

__all__ = ["QuickBooksConnector"]
