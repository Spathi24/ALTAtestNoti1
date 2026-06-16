"""Tests for the standalone PERT/CPM project optimizer script."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "project_optimizer.py"
SPEC = importlib.util.spec_from_file_location("project_optimizer", SCRIPT_PATH)
project_optimizer = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
sys.modules[SPEC.name] = project_optimizer
SPEC.loader.exec_module(project_optimizer)


def task(task_id: str, duration: float) -> dict:
    return {
        "id": task_id,
        "name": f"Task {task_id}",
        "group": "Test",
        "status": "",
        "start_date": None,
        "end_date": None,
        "duration": duration,
    }


def test_cpm_identifies_critical_path_and_float() -> None:
    tasks = [task("A", 2), task("B", 4), task("C", 3), task("D", 2)]
    deps = {
        "A": [],
        "B": ["A"],
        "C": ["A"],
        "D": ["B", "C"],
    }

    activities = project_optimizer.analyze_network(tasks, deps)

    assert activities["D"].ef == 8
    assert [a.id for a in project_optimizer.get_critical_path(activities)] == ["A", "B", "D"]
    assert activities["C"].total_float == 1
    assert activities["C"].free_float == 1


def test_pert_probability_uses_critical_path_variance() -> None:
    tasks = [task("A", 2), task("B", 4), task("C", 3)]
    deps = {"A": [], "B": ["A"], "C": ["B"]}
    pert = {
        "A": {"optimistic": 1, "most_likely": 2, "pessimistic": 3},
        "B": {"optimistic": 2, "most_likely": 4, "pessimistic": 8},
        "C": {"optimistic": 2, "most_likely": 3, "pessimistic": 4},
    }

    activities = project_optimizer.analyze_network(tasks, deps, pert)
    probability = project_optimizer.pert_probability(activities, target_days=10)

    assert probability["critical_path_mean_days"] == 9.33
    assert probability["critical_path_std_dev"] > 0
    assert probability["probability_pct"] > 50


def test_probability_does_not_sum_parallel_critical_paths() -> None:
    tasks = [task("A", 5), task("B", 5)]
    deps = {"A": [], "B": []}

    activities = project_optimizer.analyze_network(tasks, deps)
    probability = project_optimizer.pert_probability(activities, target_days=5)

    assert [a.id for a in project_optimizer.get_critical_path(activities)] == ["A", "B"]
    assert probability["critical_path_mean_days"] == 5.0
    assert probability["probability_pct"] == 100.0


def test_dependency_cycle_returns_clean_error() -> None:
    tasks = [task("A", 1), task("B", 1)]
    deps = {"A": ["B"], "B": ["A"]}

    with pytest.raises(ValueError, match="Dependency cycle detected"):
        project_optimizer.analyze_network(tasks, deps)


def test_invalid_pert_estimates_are_rejected() -> None:
    tasks = [task("A", 1)]
    deps = {"A": []}
    pert = {"A": {"optimistic": 5, "most_likely": 2, "pessimistic": 10}}

    with pytest.raises(ValueError, match="optimistic <= most_likely"):
        project_optimizer.analyze_network(tasks, deps, pert)


def test_demo_project_has_useful_parallel_path() -> None:
    tasks, deps, pert = project_optimizer.demo_project()

    activities = project_optimizer.analyze_network(tasks, deps, pert)
    critical_ids = [a.id for a in project_optimizer.get_critical_path(activities)]

    assert len(tasks) >= 10
    assert "J" in critical_ids
    assert any(not a.is_critical and a.total_float > 0 for a in activities.values())
    assert max(a.drag for a in activities.values()) > 0


def test_list_project_boards_filters_non_schedule_boards() -> None:
    class FakeClient:
        def list_boards(self, limit: int = 200) -> list[dict]:
            return [
                {
                    "id": "1",
                    "name": "923 Rockland",
                    "board_kind": "public",
                    "workspace": {"name": "Project Management"},
                },
                {
                    "id": "2",
                    "name": "Activities",
                    "board_kind": "public",
                    "workspace": {"name": "CRM"},
                },
                {
                    "id": "3",
                    "name": "Task Sheet",
                    "board_kind": "public",
                    "workspace": {"name": "TEAM ALTA"},
                },
                {
                    "id": "4",
                    "name": "1840 Main Street",
                    "board_kind": "public",
                    "workspace": {"name": "Real Estate"},
                },
            ]

        def list_board_columns(self, board_id: int) -> list[dict]:
            return [{"id": "timeline", "title": "Timeline", "type": "timeline"}]

    boards = project_optimizer.list_project_boards(FakeClient())

    assert [b["id"] for b in boards] == ["1", "4"]
