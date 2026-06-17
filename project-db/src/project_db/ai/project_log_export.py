"""Deterministic human-readable export of Project Log entries (CSV).

THE CANONICAL DB IS THE SOURCE OF TRUTH (written during ingestion). This module
only mirrors it to a CSV a human can open. Files land under an
``ALTA Generated Reports/Project Logs/<project>/`` tree; the Drive scanner skips
``ALTA Generated Reports/`` (connector._GENERATED_REPORTS_FOLDER) so an exported
CSV is never pulled back in as a source document.

Pure + deterministic: re-exporting overwrites the file with a fresh full
snapshot (idempotent). No LLM, no network.
"""

from __future__ import annotations

import csv
import os
import re
from typing import Any

from sqlalchemy.orm import Session

# Top-level folder for ALL generated outputs (must match the Drive-scanner skip).
GENERATED_ROOT = "ALTA Generated Reports"

_CSV_COLUMNS = [
    "Received At",
    "Source File",
    "Site Name",
    "Resolved Project",
    "Date",
    "Name",
    "Time Arrived",
    "Time Left",
    "Lunch Hours",
    "Total Hours Reported",
    "Total Hours Computed",
    "Hours Mismatch",
    "Supervisor Signature Present",
    "Confidence",
    "Review Status",
]


def _safe_dirname(name: str) -> str:
    """Filesystem-safe folder name from a project/site label."""
    cleaned = re.sub(r"[^\w.\- ]", "_", (name or "project").strip())
    return cleaned or "project"


def _fmt(v: Any) -> str:
    if v is None:
        return ""
    if isinstance(v, bool):
        return "yes" if v else "no"
    return str(v)


def export_project_log_csv(
    session: Session,
    project_ref: str,
    *,
    out_root: str | None = None,
) -> str | None:
    """Write all ProjectLogEntry rows for a project to a CSV. Returns the path,
    or None if the project doesn't resolve or has no rows.

    ``out_root`` (or env ``PROJECT_LOG_EXPORT_DIR``, else cwd) is the base; the
    file is written to ``<out_root>/ALTA Generated Reports/Project Logs/
    <project>/project_log_entries.csv``.
    """
    from project_db.ai.views import _resolve_project
    from project_db.db.models.project_log import ProjectLogEntry, ProjectLogSubmission

    project = _resolve_project(session, project_ref)
    if project is None:
        return None

    rows = (
        session.query(ProjectLogEntry, ProjectLogSubmission)
        .join(
            ProjectLogSubmission,
            ProjectLogSubmission.canonical_id == ProjectLogEntry.submission_id,
        )
        .filter(ProjectLogEntry.project_id == project.canonical_id)
        .all()
    )
    if not rows:
        return None

    base = out_root or os.environ.get("PROJECT_LOG_EXPORT_DIR") or os.getcwd()
    target_dir = os.path.join(base, GENERATED_ROOT, "Project Logs", _safe_dirname(project.name))
    os.makedirs(target_dir, exist_ok=True)
    path = os.path.join(target_dir, "project_log_entries.csv")

    def _sort_key(pair: tuple[ProjectLogEntry, ProjectLogSubmission]) -> tuple:
        e, _s = pair
        return (
            e.work_date.isoformat() if e.work_date else "",
            (e.employee_name_raw or "").lower(),
        )

    with open(path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(_CSV_COLUMNS)
        for entry, sub in sorted(rows, key=_sort_key):
            writer.writerow(
                [
                    _fmt(sub.received_at.isoformat() if sub.received_at else None),
                    _fmt(sub.source_attachment_filename),
                    _fmt(entry.site_name_raw or sub.site_name_raw),
                    _fmt(project.name),
                    _fmt(entry.work_date.isoformat() if entry.work_date else None),
                    _fmt(entry.employee_name_raw),
                    _fmt(entry.time_arrived),
                    _fmt(entry.time_left),
                    _fmt(entry.lunch_hours),
                    _fmt(entry.total_hours_reported),
                    _fmt(entry.total_hours_computed),
                    _fmt(entry.hours_mismatch),
                    _fmt(entry.supervisor_signature_present),
                    _fmt(entry.confidence),
                    _fmt(sub.ingestion_status),
                ]
            )
    return path
