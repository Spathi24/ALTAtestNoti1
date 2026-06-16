"""Process-wide store for the most recent background refresh result.

The web server's startup auto-refresh runs in a daemon thread and writes its
result here; the footer reads it so a PM can see "data refreshed N seconds
ago". Trivial shared state -- this is a single-process, localhost-only app.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

_LAST: dict[str, Any] = {"at": None, "summary": None, "ok": None, "running": False}


def mark_running() -> None:
    _LAST["running"] = True


def set_last(report: Any) -> None:
    _LAST["running"] = False
    _LAST["at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    _LAST["summary"] = report.one_line() if report is not None else None
    _LAST["ok"] = report.ok if report is not None else None


def get_last() -> dict[str, Any]:
    return dict(_LAST)
