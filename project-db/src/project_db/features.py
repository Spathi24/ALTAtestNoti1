"""Feature flags for quarantining non-demo surfaces at the edges.

The flags here deliberately do not change schema, extraction logic, or stored
data. They only decide which entrypoints and buttons are visible or reachable.
"""

from __future__ import annotations

import os
from collections.abc import Mapping


class FeatureDisabled(RuntimeError):
    """Raised when a guarded feature is intentionally disabled."""


_TRUE_VALUES = {"1", "true", "yes", "y", "on", "enabled"}
_FALSE_VALUES = {"0", "false", "no", "n", "off", "disabled"}


DEFAULT_FEATURES: dict[str, bool] = {
    # Demo spine.
    "core": True,
    "ask": True,
    "search": True,
    "proposals": True,
    "field_notes_typed": True,
    "finance_margins": True,
    "ledger_health": True,
    # Green-sheet: per-division budget vs quoted vs committed vs actual
    # (the refoundation financial gate view; reads report_green_sheet).
    "green_sheet": True,
    # Financial Command Center -- the new ground-up UI (UI_REFOUNDATION.md
    # Slice U1): the whole money lifecycle for one project on one screen.
    "finance_home": True,
    "task_date_edit": True,
    # Explicitly quarantined by default.
    "field_notes_email": False,
    "field_notes_photo": False,
    "finance_legacy": False,
    "obligations": False,
    "value_caught": False,
    "project_logs": True,
    "labour_intake": True,
    "telegram_intake": True,
    # General (non-labour) Telegram intake: anyone can text the bot and the
    # message is captured + attributed to a project + surfaced in the weekly
    # report. Independent of telegram_intake (labour hour-logging) so open
    # intake can be piloted without enabling labour write-back.
    "telegram_general_intake": True,
    # Home Depot Pro purchase ledger (variable-cost leak #1 in CLAUDE.md).
    # Deterministic import of the transaction + line-item Excel exports.
    "homedepot": True,
    "monday_gantt": False,
    "roadmap": False,
    "llm_pdf_finance": False,
    "lead_gen": False,
    # Admin nuance: hide PM-facing chrome, keep operator CLI available.
    "admin_nav": False,
    "admin_cli": True,
    # Token-spending batch proposal generation is not part of the rescue demo.
    "proposal_generation": True,
}


def _normalize_feature_name(name: str) -> str:
    return name.strip().lower().replace("-", "_")


def env_var_for_feature(name: str) -> str:
    """Return the environment variable used to override a feature."""
    feature = _normalize_feature_name(name).upper()
    return f"PROJECT_DB_FEATURE_{feature}"


def _parse_bool(value: str) -> bool | None:
    normalized = value.strip().lower()
    if normalized in _TRUE_VALUES:
        return True
    if normalized in _FALSE_VALUES:
        return False
    return None


def feature_enabled(name: str, env: Mapping[str, str] | None = None) -> bool:
    """Return whether a feature is enabled, honoring env overrides.

    Unknown features default to False so typos fail closed.
    Invalid env values are ignored, preserving the committed default.
    """
    env_map = os.environ if env is None else env
    feature = _normalize_feature_name(name)
    default = DEFAULT_FEATURES.get(feature, False)
    raw = env_map.get(env_var_for_feature(feature))
    if raw is None:
        return default
    parsed = _parse_bool(raw)
    return default if parsed is None else parsed


def enabled_features(env: Mapping[str, str] | None = None) -> dict[str, bool]:
    """Return the effective feature map for templates and diagnostics."""
    return {name: feature_enabled(name, env=env) for name in DEFAULT_FEATURES}


def require_feature(name: str, env: Mapping[str, str] | None = None) -> None:
    """Raise FeatureDisabled if the feature is currently disabled."""
    if not feature_enabled(name, env=env):
        raise FeatureDisabled(
            f"Feature '{_normalize_feature_name(name)}' is disabled. "
            f"Set {env_var_for_feature(name)}=true to enable it."
        )


def demo_project_ref(env: Mapping[str, str] | None = None) -> str | None:
    """Configured demo project reference, if an operator wants one.

    This is intentionally a reference string, not product logic. Callers may use
    it for local validation or operator shortcuts without hardcoding a project.
    """
    env_map = os.environ if env is None else env
    return env_map.get("PROJECT_DB_DEMO_PROJECT_ID") or env_map.get("PROJECT_DB_DEMO_PROJECT")
