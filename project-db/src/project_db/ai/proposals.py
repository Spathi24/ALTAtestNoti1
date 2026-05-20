"""LLM proposal generation -- the Tier-2 brain.

This is where the LLM stops being a demo and starts producing
operationally useful output.  The flow:

    assemble_project_context  ->  build a kind-specific prompt
    ->  provider.complete_json  ->  validate each item
    ->  write Proposal rows (status=PENDING)

Per STRATEGY.md the LLM is an advisor: nothing here writes to Monday
or mutates a canonical field.  Everything lands in the Proposal table
for a human to accept/reject later.

Session 3b ships ONE kind -- timeline extraction (the flagship per
STRATEGY.md: only ~11% of Monday tasks have dates; the contracts hold
the real schedule).  scope-reconciliation and anomaly-detection follow
the same shape and reuse ``_persist_proposals``.

Design decisions worth knowing:
  - The LLM references tasks by INTEGER INDEX, never UUID.  Models
    reliably miscopy 36-char UUIDs; an index it cannot get subtly
    wrong.  We map index -> canonical Task ourselves.
  - The instruction sits at the TAIL of the user message (lesson from
    2026-05-16: front-loaded instructions get truncated away on small
    context windows).
  - Every LLM item is validated before it becomes a Proposal.  Bad
    items are recorded in ``ProposalBatch.errors``, not raised --
    one malformed row must not sink the whole batch.
  - New proposals auto-supersede prior PENDING proposals for the same
    (entity_type, entity_id, field_name) so the reviewer only ever
    sees the latest suggestion.
"""
from __future__ import annotations

import json
import logging
import uuid
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any

from sqlalchemy.orm import Session

from project_db.ai.context import ProjectContext, assemble_project_context
from project_db.ai.providers.base import LLMMessage, LLMProvider, LLMProviderError
from project_db.db.models import Proposal, ProposalStatus

logger = logging.getLogger(__name__)

# Bump when the prompt text or output schema changes -- lets us tell
# which proposals came from which prompt generation.
TIMELINE_PROMPT_VERSION = "timeline-v1"


@dataclass
class ProposalBatch:
    """Outcome of one generation run -- everything the CLI needs to report."""
    project_id: str
    project_name: str
    kind: str                          # "timeline" | "scope" | "anomaly"
    prompt_version: str
    proposals: list[Proposal] = field(default_factory=list)
    superseded_count: int = 0
    llm_raw_item_count: int = 0
    errors: list[str] = field(default_factory=list)
    skipped_reason: str | None = None  # set when the run was a no-op

    @property
    def created_count(self) -> int:
        return len(self.proposals)

    def summary(self) -> str:
        if self.skipped_reason:
            return f"[{self.kind}] {self.project_name}: skipped -- {self.skipped_reason}"
        return (
            f"[{self.kind}] {self.project_name}: "
            f"{self.created_count} proposal(s) created, "
            f"{self.superseded_count} superseded, "
            f"{len(self.errors)} item(s) rejected as malformed "
            f"(LLM returned {self.llm_raw_item_count})"
        )


# ---------------------------------------------------------------------------
# Timeline extraction
# ---------------------------------------------------------------------------


def generate_timeline_proposals(
    session: Session,
    provider: LLMProvider,
    project_id: Any,
    *,
    token_budget: int = 80_000,
    max_documents_with_text: int = 15,
    max_output_tokens: int = 2000,
) -> ProposalBatch:
    """Read a project's contract text + dateless tasks, propose start/end dates.

    Returns a ``ProposalBatch``.  Proposals are flushed to the session
    but NOT committed -- the caller (CLI) owns the transaction.

    A run is a no-op (``skipped_reason`` set) when the project has no
    tasks missing dates, or no extracted document text to reason from.
    """
    ctx = assemble_project_context(
        session, project_id,
        token_budget=token_budget,
        max_documents_with_text=max_documents_with_text,
    )
    project_name = ctx.project.get("name", "?")
    batch = ProposalBatch(
        project_id=str(project_id),
        project_name=project_name,
        kind="timeline",
        prompt_version=TIMELINE_PROMPT_VERSION,
    )

    # Tasks with zero date signal -- the ones worth proposing for.
    dateless = [
        t for t in ctx.tasks
        if not t.get("start_date") and not t.get("end_date") and not t.get("due_date")
    ]
    if not dateless:
        batch.skipped_reason = "no tasks are missing dates"
        return batch
    if not ctx.document_texts:
        batch.skipped_reason = (
            "no extracted document text -- nothing to base a timeline on "
            "(run extract-content for this project's documents first)"
        )
        return batch

    system, user = _build_timeline_prompt(ctx, dateless)

    try:
        raw = provider.complete_json(
            messages=[LLMMessage(role="user", content=user)],
            system=system,
            max_tokens=max_output_tokens,
        )
    except LLMProviderError as exc:
        batch.errors.append(f"LLM call failed: {exc}")
        batch.skipped_reason = "LLM call failed"
        return batch

    items = _coerce_item_list(raw)
    batch.llm_raw_item_count = len(items)

    _persist_timeline_items(session, batch, items, dateless, ctx)
    return batch


def _build_timeline_prompt(
    ctx: ProjectContext, dateless: list[dict[str, Any]]
) -> tuple[str, str]:
    """Construct (system, user) for timeline extraction.

    Dateless tasks are enumerated with integer indices.  The LLM
    references those indices in its output -- never a UUID.
    """
    system = (
        "You are a construction project analyst.  You read a project's "
        "Monday task list and its contract / scope-of-work documents, and "
        "you propose start and end dates for tasks that currently have no "
        "dates.\n\n"
        "Hard rules:\n"
        "- Propose dates ONLY when the document text gives real evidence "
        "for them (an explicit date, a sequence, a duration, a phase "
        "ordering).  Do not guess.\n"
        "- It is correct and expected to return FEWER proposals than there "
        "are dateless tasks.  Returning an empty list is a valid answer.\n"
        "- Every proposal must cite the evidence in its 'reasoning' field.\n"
        "- proposed_end must be on or after proposed_start.\n"
        "- Output STRICT JSON only.  No prose, no markdown fences."
    )

    # Project header.
    lines: list[str] = []
    lines.append("=== PROJECT ===")
    for k in ("name", "code", "status", "start_date", "end_date"):
        v = ctx.project.get(k)
        if v:
            lines.append(f"{k}: {v}")

    # Dateless tasks, enumerated.
    lines.append("\n=== TASKS MISSING DATES (reference these by index) ===")
    for i, t in enumerate(dateless):
        sub = " [subitem]" if t.get("is_subitem") else ""
        lines.append(f"[{i}] {t.get('title', '(untitled)')}{sub}")

    # Document bodies -- the evidence.
    lines.append(f"\n=== DOCUMENT TEXT ({len(ctx.document_texts)} document(s)) ===")
    for d in ctx.document_texts:
        lines.append(f"\n--- {d['name']} ---")
        lines.append(d["text"])

    context_block = "\n".join(lines)

    user = (
        f"{context_block}\n\n"
        "---\n\n"
        "INSTRUCTION: Using ONLY the document text above, propose start and "
        "end dates for the tasks listed under 'TASKS MISSING DATES'.  "
        "Reference each task by its integer index.  Return strict JSON:\n\n"
        "{\n"
        '  "proposals": [\n'
        "    {\n"
        '      "task_index": <int>,\n'
        '      "proposed_start": "YYYY-MM-DD",\n'
        '      "proposed_end": "YYYY-MM-DD",\n'
        '      "confidence": <float 0.0-1.0>,\n'
        '      "reasoning": "<why these dates, citing the document evidence>",\n'
        '      "source_document": "<exact document name the evidence came from>"\n'
        "    }\n"
        "  ]\n"
        "}\n\n"
        "If the documents give no basis to date any task, return "
        '{"proposals": []}.'
    )
    return system, user


def _persist_timeline_items(
    session: Session,
    batch: ProposalBatch,
    items: list[Any],
    dateless: list[dict[str, Any]],
    ctx: ProjectContext,
) -> None:
    """Validate each LLM item and turn the good ones into Proposal rows."""
    # Map document name -> canonical id for source attribution.
    doc_id_by_name = {d["name"]: d["document_id"] for d in ctx.document_texts}

    for raw_item in items:
        if not isinstance(raw_item, dict):
            batch.errors.append(f"item is not an object: {raw_item!r}")
            continue

        idx = raw_item.get("task_index")
        if not isinstance(idx, int) or not (0 <= idx < len(dateless)):
            batch.errors.append(f"task_index out of range or non-int: {idx!r}")
            continue

        start = _parse_date(raw_item.get("proposed_start"))
        end = _parse_date(raw_item.get("proposed_end"))
        if start is None or end is None:
            batch.errors.append(
                f"task_index={idx}: unparseable dates "
                f"start={raw_item.get('proposed_start')!r} "
                f"end={raw_item.get('proposed_end')!r}"
            )
            continue
        if end < start:
            batch.errors.append(
                f"task_index={idx}: end {end} precedes start {start}"
            )
            continue

        confidence = _clamp_confidence(raw_item.get("confidence"))
        reasoning = str(raw_item.get("reasoning") or "").strip()
        source_doc_name = raw_item.get("source_document")
        source_doc_ids: list[str] = []
        if source_doc_name and source_doc_name in doc_id_by_name:
            source_doc_ids.append(doc_id_by_name[source_doc_name])

        task = dateless[idx]
        task_cid = task.get("canonical_id")
        try:
            entity_uuid = uuid.UUID(str(task_cid))
        except (ValueError, TypeError):
            batch.errors.append(f"task_index={idx}: bad canonical_id {task_cid!r}")
            continue

        # Auto-supersede any prior PENDING timeline proposal for this task.
        superseded = (
            session.query(Proposal)
            .filter_by(
                entity_type="Task",
                entity_id=entity_uuid,
                field_name="timeline",
                status=ProposalStatus.PENDING,
            )
            .all()
        )
        for old in superseded:
            old.status = ProposalStatus.SUPERSEDED
            batch.superseded_count += 1

        proposal = Proposal(
            entity_type="Task",
            entity_id=entity_uuid,
            field_name="timeline",
            proposed_value=json.dumps({
                "start_date": start.isoformat(),
                "end_date": end.isoformat(),
                "task_title": task.get("title"),
                "reasoning": reasoning,
            }),
            confidence=confidence,
            source_doc_ids=json.dumps(source_doc_ids) if source_doc_ids else None,
            prompt_version=batch.prompt_version,
            status=ProposalStatus.PENDING,
        )
        session.add(proposal)
        batch.proposals.append(proposal)

    session.flush()


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _coerce_item_list(raw: Any) -> list[Any]:
    """Pull the proposal list out of whatever shape the LLM returned.

    Accepts ``{"proposals": [...]}`` (the requested shape) or a bare
    ``[...]`` list (a common LLM deviation).  Anything else -> [].
    """
    if isinstance(raw, dict):
        inner = raw.get("proposals")
        return inner if isinstance(inner, list) else []
    if isinstance(raw, list):
        return raw
    return []


def _parse_date(value: Any) -> date | None:
    """Parse an ISO date string.  None / unparseable -> None (never raises)."""
    if not value or not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value.strip()).date()
    except (ValueError, TypeError):
        return None


def _clamp_confidence(value: Any) -> float | None:
    """Coerce a confidence into [0, 1].  None / non-numeric -> None."""
    if value is None:
        return None
    try:
        f = float(value)
    except (ValueError, TypeError):
        return None
    return max(0.0, min(1.0, f))


# ---------------------------------------------------------------------------
# Read side -- powers `proposals list` / `proposals show`
# ---------------------------------------------------------------------------


def _enrich_target(session: Session, proposal: Proposal) -> dict[str, Any]:
    """Resolve a proposal's polymorphic target into human-readable context.

    Today the only entity_type produced is "Task"; this is written to
    extend cleanly when scope/anomaly proposals target Projects etc.
    """
    info: dict[str, Any] = {
        "entity_type": proposal.entity_type,
        "entity_id": str(proposal.entity_id),
        "entity_label": None,
        "project_name": None,
    }
    if proposal.entity_type == "Task":
        from project_db.db.models import Project, Task
        task = (
            session.query(Task)
            .filter_by(canonical_id=proposal.entity_id)
            .one_or_none()
        )
        if task is not None:
            info["entity_label"] = task.title
            project = (
                session.query(Project)
                .filter_by(canonical_id=task.project_id)
                .one_or_none()
            )
            if project is not None:
                info["project_name"] = project.name
    return info


def list_proposals(
    session: Session,
    *,
    status: ProposalStatus | None = None,
    kind: str | None = None,
    limit: int = 100,
) -> list[dict[str, Any]]:
    """Return proposals as JSON-friendly dicts, newest first.

    Args:
      status: filter by ProposalStatus (default: all)
      kind:   filter by field_name ("timeline", etc.)
      limit:  cap result size
    """
    q = session.query(Proposal)
    if status is not None:
        q = q.filter(Proposal.status == status)
    if kind is not None:
        q = q.filter(Proposal.field_name == kind)
    q = q.order_by(Proposal.created_at.desc()).limit(limit)

    out: list[dict[str, Any]] = []
    for p in q.all():
        target = _enrich_target(session, p)
        try:
            value = json.loads(p.proposed_value)
        except (json.JSONDecodeError, TypeError):
            value = p.proposed_value
        out.append({
            "proposal_id": str(p.canonical_id),
            "status": p.status.value if hasattr(p.status, "value") else str(p.status),
            "field_name": p.field_name,
            "entity_type": target["entity_type"],
            "entity_label": target["entity_label"],
            "project_name": target["project_name"],
            "confidence": p.confidence,
            "proposed_value": value,
            "prompt_version": p.prompt_version,
            "created_at": p.created_at.isoformat() if p.created_at else None,
        })
    return out


def reject_proposal(
    session: Session,
    proposal_id: Any,
    *,
    reason: str | None = None,
    decided_by: str | None = None,
) -> dict[str, Any]:
    """Flip a PENDING proposal to REJECTED.

    Pure DB -- no external system is touched.  This is the safe half of
    the approval loop; `accept` (which writes back to Monday) is a
    separate, carefully-staged piece.

    Guards (all return ``{"ok": False, "error": ...}``):
      - proposal id must be a valid UUID
      - proposal must exist
      - proposal must currently be PENDING.  Rejecting something already
        ACCEPTED / REJECTED / SUPERSEDED is an explicit error, not a
        silent no-op -- the caller should know the state didn't change.

    On success returns ``{"ok": True, ...}`` and sets status=REJECTED,
    decided_at, decided_by, rejection_reason.  Flushes but does not
    commit -- the caller owns the transaction.
    """
    try:
        pid = uuid.UUID(str(proposal_id))
    except (ValueError, TypeError):
        return {"ok": False, "error": f"not a valid UUID: {proposal_id!r}"}

    p = session.query(Proposal).filter_by(canonical_id=pid).one_or_none()
    if p is None:
        return {"ok": False, "error": f"no proposal with id {proposal_id}"}

    if p.status != ProposalStatus.PENDING:
        current = p.status.value if hasattr(p.status, "value") else str(p.status)
        return {
            "ok": False,
            "error": (
                f"proposal is {current}, not PENDING -- only PENDING "
                f"proposals can be rejected"
            ),
        }

    p.status = ProposalStatus.REJECTED
    p.decided_at = datetime.utcnow()
    p.decided_by = decided_by
    p.rejection_reason = reason
    session.flush()

    return {
        "ok": True,
        "proposal_id": str(p.canonical_id),
        "previous_status": "PENDING",
        "new_status": "REJECTED",
        "decided_by": decided_by,
        "rejection_reason": reason,
    }


def get_proposal_detail(
    session: Session, proposal_id: Any
) -> dict[str, Any] | None:
    """Full detail for one proposal, or None if not found.

    Includes the resolved target, the parsed proposed_value, source
    document excerpts, and the decision audit fields.
    """
    try:
        pid = uuid.UUID(str(proposal_id))
    except (ValueError, TypeError):
        return None
    p = session.query(Proposal).filter_by(canonical_id=pid).one_or_none()
    if p is None:
        return None

    target = _enrich_target(session, p)
    try:
        value = json.loads(p.proposed_value)
    except (json.JSONDecodeError, TypeError):
        value = p.proposed_value

    source_docs: list[dict[str, Any]] = []
    if p.source_doc_ids:
        try:
            doc_ids = json.loads(p.source_doc_ids)
        except (json.JSONDecodeError, TypeError):
            doc_ids = []
        if doc_ids:
            from project_db.db.models import Document
            for d in (
                session.query(Document)
                .filter(Document.canonical_id.in_([uuid.UUID(x) for x in doc_ids]))
                .all()
            ):
                source_docs.append({
                    "document_id": str(d.canonical_id),
                    "name": d.name,
                    "folder_path": d.folder_path,
                })

    return {
        "proposal_id": str(p.canonical_id),
        "status": p.status.value if hasattr(p.status, "value") else str(p.status),
        "field_name": p.field_name,
        "entity_type": target["entity_type"],
        "entity_id": target["entity_id"],
        "entity_label": target["entity_label"],
        "project_name": target["project_name"],
        "confidence": p.confidence,
        "proposed_value": value,
        "source_documents": source_docs,
        "prompt_version": p.prompt_version,
        "created_at": p.created_at.isoformat() if p.created_at else None,
        "decided_at": p.decided_at.isoformat() if p.decided_at else None,
        "decided_by": p.decided_by,
        "rejection_reason": p.rejection_reason,
    }
