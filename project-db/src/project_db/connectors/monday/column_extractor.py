"""Extract canonical field values from Monday.com column_values.

Monday returns column_values as a flat list of {id, type, text, value} per
item. This module maps those raw values into meaningful canonical fields
(client_name, status, start_date, etc.) using two strategies:

  1. Explicit mapping  — caller provides {column_id: canonical_field_name}
  2. Heuristic titles  — column title matched against keyword patterns

Usage
-----
    extractor = ColumnExtractor(column_defs, explicit_mapping={"text7": "client_name"})
    fields = extractor.extract(item["column_values"])
    # fields.client_name == "Smith Renovation"
    # fields.status      == ProjectStatus.ACTIVE

The extractor is intentionally lenient: unrecognised columns are silently
skipped, and missing/empty values stay as None so callers can decide what
to do (fall back to default, warn, etc.).
"""
from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any

from project_db.db.models import LeadStage, ProjectStatus, TaskStatus

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Title -> canonical field heuristics
# Order matters: first match wins per column.
# ---------------------------------------------------------------------------

_TITLE_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    # client / account -- check before "value" so "Account Value" goes here first
    (re.compile(r"\bclient\b|\bcustomer\b|\baccounts?\b|\bcontacts?\b", re.I), "client_name"),
    # status (stage, phase -- but NOT "priority" which is a separate concern)
    (re.compile(r"\bstatus\b|\bstage\b|\bphase\b|\bpipeline\b", re.I), "status_label"),
    # dates -- more specific patterns first
    (re.compile(r"start\s*date|kick.?off|\bbegin\b", re.I), "start_date"),
    (re.compile(r"end\s*date|due\s*date|deadline|completion\s*date|close\s*date|expected.*close", re.I), "end_date"),
    (re.compile(r"\btimeline\b", re.I), "timeline"),
    # money -- word boundaries prevent "subcontractor" matching "contract"
    (re.compile(r"\bbudget\b|\bestimate\b", re.I), "budget_amount"),
    (re.compile(r"\bcontract\b|\bquote\b|\bprice\b|\bdeal\s+value\b|\bcontract\s+value\b", re.I), "contract_amount"),
    # contact info
    (re.compile(r"\baddress\b|\blocation\b|\bproperty\b|\bsite\b", re.I), "address"),
    (re.compile(r"\bemail\b|\be-mail\b", re.I), "email"),
    (re.compile(r"\bphone\b|\bmobile\b|\bcell\b|\btel\b", re.I), "phone"),
    # assignment
    (re.compile(r"\bowner\b|\bassigned\b|project\s*manager|\bpm\b", re.I), "assigned_user"),
    # probability (deals)
    (re.compile(r"\bprobability\b|\bchance\b|\bconfidence\b", re.I), "probability"),
    # notes
    (re.compile(r"\bnotes?\b|\bdescription\b|\bdetails?\b|\bsummary\b", re.I), "notes"),
]

# ---------------------------------------------------------------------------
# Monday status label -> ProjectStatus
# ---------------------------------------------------------------------------

_PROJECT_STATUS_MAP: dict[str, ProjectStatus] = {
    "done": ProjectStatus.COMPLETED,
    "completed": ProjectStatus.COMPLETED,
    "complete": ProjectStatus.COMPLETED,
    "finished": ProjectStatus.COMPLETED,
    "working on it": ProjectStatus.ACTIVE,
    "in progress": ProjectStatus.ACTIVE,
    "active": ProjectStatus.ACTIVE,
    "in production": ProjectStatus.ACTIVE,
    "ongoing": ProjectStatus.ACTIVE,
    "stuck": ProjectStatus.ON_HOLD,
    "on hold": ProjectStatus.ON_HOLD,
    "paused": ProjectStatus.ON_HOLD,
    "waiting": ProjectStatus.ON_HOLD,
    "blocked": ProjectStatus.ON_HOLD,
    "cancelled": ProjectStatus.CANCELLED,
    "canceled": ProjectStatus.CANCELLED,
    "void": ProjectStatus.CANCELLED,
    "proposed": ProjectStatus.PROPOSED,
    "new": ProjectStatus.PROPOSED,
    "not started": ProjectStatus.PROPOSED,
    "pending": ProjectStatus.PROPOSED,
}

# Monday status label -> TaskStatus (for task items within a ProjectBoard)
_TASK_STATUS_MAP: dict[str, TaskStatus] = {
    "done": TaskStatus.DONE,
    "completed": TaskStatus.DONE,
    "complete": TaskStatus.DONE,
    "working on it": TaskStatus.IN_PROGRESS,
    "in progress": TaskStatus.IN_PROGRESS,
    "active": TaskStatus.IN_PROGRESS,
    "stuck": TaskStatus.BLOCKED,
    "blocked": TaskStatus.BLOCKED,
    "on hold": TaskStatus.BLOCKED,
    "cancelled": TaskStatus.CANCELLED,
    "canceled": TaskStatus.CANCELLED,
    "not started": TaskStatus.TODO,
    "pending": TaskStatus.TODO,
    "new": TaskStatus.TODO,
    "to do": TaskStatus.TODO,
    "todo": TaskStatus.TODO,
}

# Monday status label -> LeadStage (for Deal / Lead boards)
_LEAD_STAGE_MAP: dict[str, LeadStage] = {
    "new": LeadStage.NEW,
    "new lead": LeadStage.NEW,
    "contacted": LeadStage.NEW,
    "qualified": LeadStage.QUALIFIED,
    "proposal": LeadStage.PROPOSAL,
    "proposal sent": LeadStage.PROPOSAL,
    "negotiation": LeadStage.NEGOTIATION,
    "won": LeadStage.WON,
    "closed won": LeadStage.WON,
    "lost": LeadStage.LOST,
    "closed lost": LeadStage.LOST,
    "disqualified": LeadStage.LOST,
}


@dataclass
class ExtractedFields:
    """Canonical field values extracted from one Monday item's column_values."""

    client_name: str | None = None
    status: ProjectStatus | None = None
    task_status: TaskStatus | None = None
    lead_stage: LeadStage | None = None
    start_date: date | None = None
    end_date: date | None = None
    budget_amount: Decimal | None = None
    contract_amount: Decimal | None = None
    probability: float | None = None
    address: str | None = None
    email: str | None = None
    phone: str | None = None
    notes: str | None = None
    # Monday user IDs of assigned people (resolved to User later)
    assigned_monday_user_ids: list[str] = field(default_factory=list)
    # Everything that didn't match a known field (for debugging)
    unmatched: dict[str, str] = field(default_factory=dict)


class ColumnExtractor:
    """Stateless extractor bound to a board's column definitions.

    Parameters
    ----------
    column_defs:
        Output of ``MondayClient.list_board_columns(board_id)`` --
        list of {id, title, type, settings_str}.
    explicit_mapping:
        Optional override dict {column_id: canonical_field_name}.
        Takes precedence over heuristic title matching.
        Valid field names: client_name, status_label, start_date, end_date,
        timeline, budget_amount, contract_amount, address, email, phone,
        assigned_user, probability, notes.
    """

    def __init__(
        self,
        column_defs: list[dict[str, Any]],
        explicit_mapping: dict[str, str] | None = None,
    ) -> None:
        self._explicit = explicit_mapping or {}
        self._col_meta: dict[str, dict[str, str]] = {
            col["id"]: {"title": col.get("title", ""), "type": col.get("type", "")}
            for col in column_defs
        }
        # Pre-compute heuristic assignments: col_id -> canonical_field
        self._heuristic: dict[str, str] = {}
        for col_id, meta in self._col_meta.items():
            if col_id in self._explicit:
                continue
            title = meta["title"]
            for pattern, field_name in _TITLE_PATTERNS:
                if pattern.search(title):
                    self._heuristic[col_id] = field_name
                    break

    def extract(self, column_values: list[dict[str, Any]]) -> ExtractedFields:
        """Map one item's column_values list to an ExtractedFields instance."""
        result = ExtractedFields()

        for cv in column_values:
            col_id = cv.get("id", "")
            col_type = cv.get("type", "")
            text = (cv.get("text") or "").strip()
            raw_value = cv.get("value")

            target_field = self._explicit.get(col_id) or self._heuristic.get(col_id)
            if target_field is None:
                if text:
                    result.unmatched[col_id] = text
                continue

            parsed_value = _parse_value(col_type, text, raw_value)

            if target_field == "client_name":
                result.client_name = _as_str(parsed_value) or None

            elif target_field == "status_label":
                label = _as_str(parsed_value)
                if label:
                    result.status = _map_project_status(label)
                    result.task_status = _map_task_status(label)
                    result.lead_stage = _map_lead_stage(label)

            elif target_field == "probability":
                result.probability = _as_float(parsed_value)

            elif target_field == "start_date":
                result.start_date = _as_date(parsed_value)

            elif target_field == "end_date":
                result.end_date = _as_date(parsed_value)

            elif target_field == "timeline":
                if isinstance(parsed_value, dict):
                    result.start_date = result.start_date or parsed_value.get("from_date")
                    result.end_date = result.end_date or parsed_value.get("to_date")

            elif target_field == "budget_amount":
                result.budget_amount = _as_decimal(parsed_value)

            elif target_field == "contract_amount":
                result.contract_amount = _as_decimal(parsed_value)

            elif target_field == "address":
                result.address = _as_str(parsed_value) or None

            elif target_field == "email":
                result.email = _as_str(parsed_value) or None

            elif target_field == "phone":
                result.phone = _as_str(parsed_value) or None

            elif target_field == "notes":
                result.notes = _as_str(parsed_value) or None

            elif target_field == "assigned_user":
                if isinstance(parsed_value, list):
                    result.assigned_monday_user_ids = parsed_value

        return result


# ---------------------------------------------------------------------------
# Per-type value parsers
# ---------------------------------------------------------------------------

def _parse_value(col_type: str, text: str, raw_value: Any) -> Any:
    """Parse a column value into a Python-native type based on col_type."""
    value_str = raw_value if isinstance(raw_value, str) else None
    parsed: Any = None
    if value_str:
        try:
            parsed = json.loads(value_str)
        except (json.JSONDecodeError, TypeError):
            parsed = value_str

    if col_type in ("text", "long_text"):
        if isinstance(parsed, dict):
            return parsed.get("text", text)
        return text

    if col_type == "numbers":
        return _coerce_number(text) or _coerce_number(str(parsed))

    if col_type == "status":
        if isinstance(parsed, dict):
            return parsed.get("label") or text
        return text

    if col_type == "dropdown":
        if isinstance(parsed, dict):
            labels = parsed.get("labels") or []
            return ", ".join(labels) if labels else text
        return text

    if col_type == "date":
        if isinstance(parsed, dict) and "date" in parsed:
            return _parse_date_str(parsed["date"])
        return _parse_date_str(text)

    if col_type == "timeline":
        if isinstance(parsed, dict):
            return {
                "from_date": _parse_date_str(parsed.get("from", "")),
                "to_date": _parse_date_str(parsed.get("to", "")),
            }
        return None

    if col_type == "email":
        if isinstance(parsed, dict):
            return parsed.get("email") or text
        return text

    if col_type == "phone":
        if isinstance(parsed, dict):
            return parsed.get("phone") or text
        return text

    if col_type == "location":
        if isinstance(parsed, dict):
            return parsed.get("address") or text
        return text

    if col_type == "people":
        if isinstance(parsed, dict):
            persons = parsed.get("personsAndTeams") or []
            return [str(p["id"]) for p in persons if p.get("kind") == "person"]
        return []

    if col_type == "link":
        if isinstance(parsed, dict):
            return parsed.get("url") or text
        return text

    return text or None


def _as_str(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _as_date(value: Any) -> date | None:
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        return _parse_date_str(value)
    return None


def _as_decimal(value: Any) -> Decimal | None:
    if value is None:
        return None
    try:
        cleaned = re.sub(r"[^\d.\-]", "", str(value))
        return Decimal(cleaned) if cleaned else None
    except InvalidOperation:
        return None


def _coerce_number(s: str | None) -> str | None:
    if not s:
        return None
    cleaned = re.sub(r"[^\d.\-]", "", s)
    return cleaned if cleaned else None


def _parse_date_str(s: str) -> date | None:
    if not s:
        return None
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%d/%m/%Y", "%Y/%m/%d"):
        try:
            from datetime import datetime
            return datetime.strptime(s.strip(), fmt).date()
        except ValueError:
            continue
    return None


def _as_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(re.sub(r"[^\d.\-]", "", str(value)))
    except (ValueError, TypeError):
        return None


def _map_project_status(label: str) -> ProjectStatus:
    key = label.strip().lower()
    return _PROJECT_STATUS_MAP.get(key, ProjectStatus.ACTIVE)


def _map_task_status(label: str) -> TaskStatus:
    key = label.strip().lower()
    return _TASK_STATUS_MAP.get(key, TaskStatus.TODO)


def _map_lead_stage(label: str) -> LeadStage:
    key = label.strip().lower()
    return _LEAD_STAGE_MAP.get(key, LeadStage.NEW)
