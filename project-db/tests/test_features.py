"""Feature flag defaults and env override parsing."""

from __future__ import annotations

import pytest

from project_db.features import (
    FeatureDisabled,
    demo_project_ref,
    enabled_features,
    env_var_for_feature,
    feature_enabled,
    require_feature,
)


def test_demo_spine_defaults_visible():
    flags = enabled_features(env={})

    assert flags["core"] is True
    assert flags["ask"] is True
    assert flags["search"] is True
    assert flags["proposals"] is True
    assert flags["field_notes_typed"] is True
    assert flags["finance_margins"] is True
    assert flags["ledger_health"] is True


def test_non_demo_defaults_quarantined():
    flags = enabled_features(env={})

    for name in (
        "field_notes_email",
        "field_notes_photo",
        "finance_legacy",
        "obligations",
        "value_caught",
        "project_logs",
        "labour_intake",
        "telegram_intake",
        "monday_gantt",
        "roadmap",
        "llm_pdf_finance",
        "lead_gen",
        "proposal_generation",
        "task_date_edit",
    ):
        assert flags[name] is False


def test_admin_nav_hidden_but_cli_enabled_by_default():
    assert feature_enabled("admin_nav", env={}) is False
    assert feature_enabled("admin_cli", env={}) is True


@pytest.mark.parametrize("raw", ["1", "true", "TRUE", "yes", "on", "enabled"])
def test_true_env_values_enable_disabled_feature(raw):
    assert feature_enabled("telegram-intake", env={"PROJECT_DB_FEATURE_TELEGRAM_INTAKE": raw})


@pytest.mark.parametrize("raw", ["0", "false", "FALSE", "no", "off", "disabled"])
def test_false_env_values_disable_enabled_feature(raw):
    assert not feature_enabled(
        "field_notes_typed", env={"PROJECT_DB_FEATURE_FIELD_NOTES_TYPED": raw}
    )


def test_invalid_env_value_preserves_default():
    assert feature_enabled(
        "field_notes_typed", env={"PROJECT_DB_FEATURE_FIELD_NOTES_TYPED": "maybe"}
    )
    assert not feature_enabled(
        "telegram_intake", env={"PROJECT_DB_FEATURE_TELEGRAM_INTAKE": "maybe"}
    )


def test_unknown_features_fail_closed():
    assert feature_enabled("not_real", env={}) is False


def test_env_var_for_feature_normalizes_name():
    assert env_var_for_feature("field-notes-typed") == "PROJECT_DB_FEATURE_FIELD_NOTES_TYPED"


def test_require_feature_raises_clear_error():
    with pytest.raises(FeatureDisabled) as exc:
        require_feature("telegram_intake", env={})

    assert "PROJECT_DB_FEATURE_TELEGRAM_INTAKE=true" in str(exc.value)


def test_demo_project_ref_prefers_id_over_name():
    assert (
        demo_project_ref(
            env={
                "PROJECT_DB_DEMO_PROJECT": "923-927 Rockland",
                "PROJECT_DB_DEMO_PROJECT_ID": "abc123",
            }
        )
        == "abc123"
    )


def test_demo_project_ref_allows_name_without_hardcoding():
    assert (
        demo_project_ref(env={"PROJECT_DB_DEMO_PROJECT": "923-927 Rockland"}) == "923-927 Rockland"
    )
