"""Local web UI for ALTA / project_db.

A thin, read-mostly projection over existing reports (``ai.views``) and the
existing proposal accept/reject functions (``ai.proposals``).  No new
business logic lives here.  The UI is a view, not a second app.

Constraints (see plan in HANDOFF.md and the M5 plan):
  - localhost-only (127.0.0.1), single-user, no auth
  - HTML pages are primary; JSON endpoints exist only where they materially
    aid debugging
  - the only mutating routes are ``accept_proposal`` / ``reject_proposal``,
    called as thin adapters with the same write-first/flip-second ordering
    the CLI uses

Phase A ships just the dashboard.  Routes are added phase-by-phase in
``routes/``.
"""
