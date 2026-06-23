"""Home Depot Pro purchase ingestion (variable-cost leak #1).

Two pieces:
* ``parse`` / ``importer`` -- deterministic ingestion of the two manual Excel
  exports (transaction headers + per-transaction line items) into the
  ``home_depot_transaction`` / ``home_depot_line_item`` ledger. No browser, no
  network, no LLM: this is the trustworthy spine.
* ``browser`` -- a logged-in Playwright bot that replays the manual per-receipt
  "detail export" so the line-item backfill stops being a hundreds-of-clicks
  chore. Optional; requires one-time operator login.
"""

from project_db.connectors.homedepot.importer import (
    import_details,
    import_transactions,
    link_job_to_project,
    relink_transactions,
)
from project_db.connectors.homedepot.parse import (
    HomeDepotParseError,
    ParsedExport,
    detect_format,
    parse_export,
    parse_money,
)

__all__ = [
    "HomeDepotParseError",
    "ParsedExport",
    "detect_format",
    "import_details",
    "import_transactions",
    "link_job_to_project",
    "parse_export",
    "parse_money",
    "relink_transactions",
]
