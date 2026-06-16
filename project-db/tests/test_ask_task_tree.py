"""The /ask path injects the deterministic task tree for a referenced project.

This is the fix for the askbot being hierarchy- and dependency-blind: when a
question names a project, the model must be handed that project's real tree
(parents + dependencies), not just the flat whole-DB snapshot.
"""

from __future__ import annotations

from datetime import date

import pytest

from project_db.ai.providers.mock import MockLLMProvider
from project_db.ai.query import AiAssistant
from project_db.db.models import (
    Client,
    Organization,
    Project,
    Task,
    TaskDependency,
)
from project_db.db.models.work import ProjectStatus, TaskStatus


@pytest.fixture
def project_with_graph(session):
    org = Organization(name="Co")
    session.add(org)
    session.flush()
    cli = Client(name="Owner", organization_id=org.canonical_id)
    session.add(cli)
    session.flush()
    p = Project(name="Rockland", status=ProjectStatus.ACTIVE, client_id=cli.canonical_id)
    session.add(p)
    session.flush()

    phase = Task(
        title="Plumbing Phase",
        status=TaskStatus.IN_PROGRESS,
        project_id=p.canonical_id,
        start_date=date(2026, 6, 9),
    )
    session.add(phase)
    session.flush()
    rough = Task(
        title="Rough-in plumbing",
        status=TaskStatus.DONE,
        project_id=p.canonical_id,
        is_subitem=True,
        parent_task_id=phase.canonical_id,
        end_date=date(2026, 6, 13),
    )
    rough.monday_status_label = "Done"
    drywall = Task(
        title="Drywall installation",
        status=TaskStatus.TODO,
        project_id=p.canonical_id,
        start_date=date(2026, 6, 14),
    )
    session.add_all([rough, drywall])
    session.flush()
    # Drywall depends on Rough-in plumbing.
    session.add(
        TaskDependency(
            predecessor_task_id=rough.canonical_id, successor_task_id=drywall.canonical_id
        )
    )
    session.commit()
    return p


def _last_user(prov: MockLLMProvider) -> str:
    return prov.calls[-1]["messages"][0].content


class TestAskInjectsTaskTree:
    def test_tree_in_user_prompt_when_project_referenced(self, session, project_with_graph):
        prov = MockLLMProvider(responses=["ok"])
        assistant = AiAssistant(session)
        # Reference the project by UUID so extract_project_ref resolves it
        # deterministically (no dependence on name-matching).
        assistant.answer_with_llm(
            f"what is blocking Drywall in project {project_with_graph.canonical_id}?",
            prov,
        )
        user = _last_user(prov)
        assert "TASK TREE" in user
        assert "Plumbing Phase" in user
        assert "Drywall installation" in user
        # The dependency annotation must be present (deps satisfied here).
        assert "Rough-in plumbing" in user
        # System prompt gains the task-tree instruction.
        assert "authoritative hierarchy" in prov.calls[-1]["system"]

    def test_no_tree_when_no_project_referenced(self, session, project_with_graph):
        prov = MockLLMProvider(responses=["ok"])
        assistant = AiAssistant(session)
        assistant.answer_with_llm("what should we focus on today?", prov)
        user = _last_user(prov)
        assert "TASK TREE" not in user

    def test_graceful_when_project_has_no_tasks(self, session):
        org = Organization(name="Co")
        session.add(org)
        session.flush()
        cli = Client(name="Owner", organization_id=org.canonical_id)
        session.add(cli)
        session.flush()
        p = Project(name="Empty", status=ProjectStatus.ACTIVE, client_id=cli.canonical_id)
        session.add(p)
        session.commit()
        prov = MockLLMProvider(responses=["ok"])
        AiAssistant(session).answer_with_llm(f"tell me about project {p.canonical_id}", prov)
        # No tasks -> no tree block, no crash.
        assert "TASK TREE" not in _last_user(prov)
