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

from sqlalchemy import func
from sqlalchemy.orm import Session

from project_db.ai.context import ProjectContext, assemble_project_context
from project_db.ai.providers.base import LLMMessage, LLMProvider, LLMProviderError
from project_db.db.models import Proposal, ProposalStatus

logger = logging.getLogger(__name__)

# Bump when the prompt text or output schema changes -- lets us tell
# which proposals came from which prompt generation.
#
# Roadmap injection (Layer 2) was REMOVED 2026-05-29.  It injected the
# canonical design-phase roadmap (an ARCHITECT SD->DD->CD->CA workflow) into
# these contractor-execution prompts so the bots would also flag
# "roadmap-sourced" template gaps.  In practice that produced generic,
# template-derived flags the PM had to second-guess (the scope UI even
# carried a "does this apply here?" caveat) -- review burden without a lift
# in trust.  The RoadmapTask table + import/classify CLIs are kept (harmless,
# queryable); only the prompt injection is gone.  Proposals are now grounded
# purely in the project's own contracts and schedule, with quoted-excerpt
# evidence.  See STRATEGY.md rule N5 (the frozen roadmap-injection slop).
TIMELINE_PROMPT_VERSION = "timeline-v5-quoted"
SCOPE_PROMPT_VERSION = "scope-v4-quoted"


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
    warnings: list[str] = field(default_factory=list)
    skipped_reason: str | None = None  # set when the run was a no-op
    rag_chunks_used: int = 0           # relevance-retrieved excerpts injected

    """``errors``   -- items REJECTED (never became a Proposal): bad index,
                       unparseable dates, end-before-start, etc.
       ``warnings`` -- items that WERE created but tripped an
                       anti-hallucination check (no evidence cited, or a
                       source document the model named that we never
                       actually supplied).  The reviewer should look
                       harder at these before accepting."""

    @property
    def created_count(self) -> int:
        return len(self.proposals)

    def summary(self) -> str:
        if self.skipped_reason:
            return f"[{self.kind}] {self.project_name}: skipped -- {self.skipped_reason}"
        line = (
            f"[{self.kind}] {self.project_name}: "
            f"{self.created_count} proposal(s) created, "
            f"{self.superseded_count} superseded, "
            f"{len(self.errors)} item(s) rejected as malformed "
            f"(LLM returned {self.llm_raw_item_count})"
        )
        if self.warnings:
            line += f", {len(self.warnings)} flagged for review"
        return line


# ---------------------------------------------------------------------------
# Timeline extraction
# ---------------------------------------------------------------------------


def _retrieve_proposal_chunks(
    session: Session,
    embedding_provider: Any,
    project_id: Any,
    query: str,
    *,
    top_k: int,
    min_similarity: float,
) -> list[dict[str, Any]]:
    """Best-effort relevance retrieval for proposal context.

    Returns project-scoped chunks most relevant to the proposal's intent, so a
    clause buried deep in a long contract (past the recency-truncation window
    ``assemble_project_context`` applies) is still seen.  Never raises -- a
    retrieval hiccup just yields no excerpts and the bots fall back to the
    recency-ordered bodies exactly as before.  This is an INPUT upgrade only;
    the conservative prompt posture is unchanged.
    """
    if embedding_provider is None:
        return []
    try:
        from project_db.ai.rag import retrieve_chunks

        return retrieve_chunks(
            session, embedding_provider, query,
            project_id=project_id, top_k=top_k, min_similarity=min_similarity,
        )
    except Exception:  # noqa: BLE001 -- retrieval must never break propose
        return []


def _render_rag_excerpts(rag_chunks: list[dict[str, Any]]) -> list[str]:
    """Prompt lines for a RELEVANT DOCUMENT EXCERPTS section ([] when none)."""
    if not rag_chunks:
        return []
    lines = [
        "\n=== RELEVANT DOCUMENT EXCERPTS (semantic search -- the most "
        "on-topic passages, which may come from parts of long documents not "
        "shown in full below) ==="
    ]
    for c in rag_chunks:
        body = " ".join((c.get("text") or "").split())
        lines.append(f"\n--- EXCERPT from {c.get('document_name')} ---")
        lines.append(body)
    return lines


def generate_timeline_proposals(
    session: Session,
    provider: LLMProvider,
    project_id: Any,
    *,
    # Kept well under the Anthropic tier's 50k input-tokens-per-minute
    # rate limit -- small enough that even a complete_json retry (which
    # resends the whole prompt) still fits inside one minute's budget.
    # Raise this when the API tier's rate limit is raised.
    token_budget: int = 20_000,
    max_documents_with_text: int = 30,
    max_output_tokens: int = 3000,
    embedding_provider: Any | None = None,
    rag_top_k: int = 8,
    rag_min_similarity: float = 0.25,
) -> ProposalBatch:
    """Propose forward-looking start/end dates for a project's dateless tasks.

    Anchored: the model is given today's date and the project's already-
    dated tasks (its known schedule), so a proposal is bounded by the
    project's real window instead of floating free -- which is how a 2022
    tenant-lease date once landed on a renovation task.

    Returns a ``ProposalBatch``.  Proposals are flushed to the session
    but NOT committed -- the caller (CLI) owns the transaction.

    A run is a no-op (``skipped_reason`` set) when the project has no
    dateless tasks, or nothing to anchor on (no document text AND no
    already-dated tasks).
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

    # Split tasks: dateless ones are what we propose for; dated ones are
    # the ANCHOR -- the project's known schedule, fed to the model so a
    # proposal stays bounded by the project's real window.
    dateless = [
        t for t in ctx.tasks
        if not t.get("start_date") and not t.get("end_date") and not t.get("due_date")
    ]
    dated = [
        t for t in ctx.tasks
        if t.get("start_date") or t.get("end_date") or t.get("due_date")
    ]
    if not dateless:
        batch.skipped_reason = "no tasks are missing dates"
        return batch
    if not ctx.document_texts and not dated:
        batch.skipped_reason = (
            "nothing to anchor a timeline on -- no extracted document text "
            "and no already-dated tasks (run extract-content first, or set "
            "dates on a few tasks in Monday)"
        )
        return batch

    today = date.today()

    # RAG: retrieve the passages most relevant to scheduling THESE tasks, so a
    # milestone clause deep in a long contract is seen even when the recency
    # truncation hid it.  Project-scoped; conservative posture unchanged.
    rag_query = (
        "construction schedule: start dates, end dates, durations, and "
        "milestones for these tasks -- "
        + "; ".join(t.get("title", "") for t in dateless[:25])
    )
    rag_chunks = _retrieve_proposal_chunks(
        session, embedding_provider, project_id, rag_query,
        top_k=rag_top_k, min_similarity=rag_min_similarity,
    )
    batch.rag_chunks_used = len(rag_chunks)

    system, user = _build_timeline_prompt(ctx, dateless, dated, today, rag_chunks)

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

    _persist_timeline_items(session, batch, items, dateless, ctx, today)
    return batch


def _build_timeline_prompt(
    ctx: ProjectContext,
    dateless: list[dict[str, Any]],
    dated: list[dict[str, Any]],
    today: date,
    rag_chunks: list[dict[str, Any]] | None = None,
) -> tuple[str, str]:
    """Construct (system, user) for forward-looking timeline proposals.

    Dateless tasks are enumerated with integer indices; the LLM references
    those indices in its output -- never a UUID.

    The prompt is ANCHORED: it shows the model today's date and the
    project's already-dated tasks (the KNOWN SCHEDULE), so a proposed date
    is bounded by the project's real window.  Free-floating extraction is
    how a 2022 tenant-lease term once landed on a renovation task.
    """
    system = (
        "You are a construction project scheduler.  Some of a project's "
        "Monday tasks have no dates; you propose start and end dates for "
        "them -- FORWARD-LOOKING schedule dates, not a record of past work.\n\n"
        "Hard rules:\n"
        "- ANCHOR every proposed date to the KNOWN SCHEDULE (the tasks that "
        "already have dates) and to today's date.  A date outside the "
        "project's real window is wrong.\n"
        "- Valid evidence is EITHER (a) the task's place in the schedule "
        "sequence -- a dateless task between two dated tasks can be timed "
        "from its neighbours -- OR (b) an explicit forward schedule in a "
        "document (a contract milestone, a scope-of-work start date).\n"
        "- NOT evidence: the date an invoice was issued, a work report was "
        "filed, a tenant lease term, or any record of work already DONE.  "
        "Those are history, not a schedule -- ignore them.\n"
        "- The evidence must describe the SPECIFIC task you are dating, not "
        "merely the same category of work.\n"
        "- Propose ONLY for tasks that are upcoming or in progress.  If a "
        "task looks already complete, or you have no real anchor for it, do "
        "NOT propose -- returning fewer proposals, or none, is correct.\n"
        "- proposed_start and proposed_end must both be on or after today; "
        "proposed_end on or after proposed_start.\n"
        "- Every proposal must cite its specific evidence in 'reasoning'.\n"
        "- Output STRICT JSON only.  No prose, no markdown fences."
    )

    lines: list[str] = []
    lines.append(f"=== TODAY ===\n{today.isoformat()}")

    lines.append("\n=== PROJECT ===")
    for k in ("name", "code", "status", "start_date", "end_date"):
        v = ctx.project.get(k)
        if v:
            lines.append(f"{k}: {v}")

    # Known schedule -- the anchor.  Every proposed date is checked, by the
    # model and then again by the server, against this window.
    lines.append(
        f"\n=== KNOWN SCHEDULE -- tasks that already have dates "
        f"({len(dated)}) ==="
    )
    if dated:
        for t in dated:
            start = t.get("start_date") or "?"
            end = t.get("end_date") or t.get("due_date") or "?"
            lines.append(f"- {t.get('title', '(untitled)')}: {start} -> {end}")
    else:
        lines.append(
            "(none -- this project has no dated tasks yet.  Rely on explicit "
            "document schedule statements, and keep every date on or after "
            "today.)"
        )

    lines.append("\n=== TASKS NEEDING DATES (reference these by index) ===")
    for i, t in enumerate(dateless):
        sub = " [subitem]" if t.get("is_subitem") else ""
        lines.append(f"[{i}] {t.get('title', '(untitled)')}{sub}")

    # Relevance-retrieved excerpts (RAG) -- targeted passages first, so a
    # schedule clause from deep in a long contract is visible even when the
    # recency truncation below cut it.
    lines.extend(_render_rag_excerpts(rag_chunks or []))

    # Document bodies -- secondary evidence.  Each is introduced with its
    # Drive folder path and type so the model can tell a contract from an
    # invoice or a lease.  A truncated body is labelled as such.
    lines.append(f"\n=== DOCUMENT TEXT ({len(ctx.document_texts)} document(s)) ===")
    for d in ctx.document_texts:
        header = f"\n--- DOCUMENT: {d['name']}"
        if d.get("folder_path"):
            header += f"  |  Drive folder: {d['folder_path']}"
        if d.get("mime_type"):
            header += f"  |  type: {d['mime_type']}"
        header += " ---"
        lines.append(header)
        if d.get("truncated"):
            lines.append(
                f"(NOTE: only the first {len(d['text'])} characters of this "
                f"document are shown -- it continues beyond this point.  "
                f"Do not treat the absence of later content as meaningful.)"
            )
        lines.append(d["text"])

    context_block = "\n".join(lines)

    user = (
        f"{context_block}\n\n"
        "---\n\n"
        "INSTRUCTION: Propose FORWARD-LOOKING start and end dates for the "
        "tasks under 'TASKS NEEDING DATES'.  Anchor every date to the KNOWN "
        "SCHEDULE window and to today's date.  Use only real evidence: a "
        "task's place in the schedule sequence, or an explicit forward "
        "schedule in a document.  Ignore invoice dates, work-report dates, "
        "lease terms, and every record of completed work.  Skip any task "
        "that is already finished or that you cannot anchor."
        "  Reference each task by its integer index.\n\n"
        "EVIDENCE-CITATION REQUIREMENT for the 'reasoning' field:\n"
        "- When evidence comes from a DOCUMENT: include a direct "
        "QUOTED EXCERPT in double quotes (max ~30 words) of the exact "
        "sentence or clause that supports the proposed date.  Name the "
        "document.  Then briefly explain why that excerpt anchors the "
        "specific task you're dating.\n"
        "- When evidence comes from the SCHEDULE SEQUENCE (dated "
        "neighbour tasks): name the neighbour tasks by their title and "
        "their dates, e.g. 'between Demolition (2026-06-01 to 06-10) "
        "and Final Inspection (2026-08-12)'.\n"
        "- A reasoning that says only 'based on the contract' or 'per "
        "the schedule' is REJECTED.  Specific evidence required.\n\n"
        "Return strict JSON:\n\n"
        "{\n"
        '  "proposals": [\n'
        "    {\n"
        '      "task_index": <int>,\n'
        '      "proposed_start": "YYYY-MM-DD",\n'
        '      "proposed_end": "YYYY-MM-DD",\n'
        '      "confidence": <float 0.0-1.0>,\n'
        '      "reasoning": "<one paragraph: quoted excerpt (if doc) '
        '+ named neighbour tasks with dates (if sequence).  Specific '
        'evidence only -- see requirement above.>",\n'
        '      "source_document": "<exact document name, or empty string if '
        'the evidence is the schedule sequence rather than a document>"\n'
        "    }\n"
        "  ]\n"
        "}\n\n"
        'If no task can be anchored, return {"proposals": []}.'
    )
    return system, user


def _persist_timeline_items(
    session: Session,
    batch: ProposalBatch,
    items: list[Any],
    dateless: list[dict[str, Any]],
    ctx: ProjectContext,
    today: date,
) -> None:
    """Validate each LLM item and turn the good ones into Proposal rows.

    A timeline entirely in the past is rejected: proposals are
    forward-looking, so a past end date means the task is already done.
    """
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
        if end < today:
            batch.errors.append(
                f"task_index={idx} ({_safe_title(dateless, idx)}): proposed "
                f"timeline {start} -> {end} is entirely in the past -- a "
                f"timeline proposal must be forward-looking (this task "
                f"looks already complete)"
            )
            continue

        confidence = _clamp_confidence(raw_item.get("confidence"))
        reasoning = str(raw_item.get("reasoning") or "").strip()
        source_doc_name = raw_item.get("source_document")

        # Resolve the cited source to a real document.  An unmatched
        # citation is the strongest hallucination signal we have: the
        # model claims evidence from a document we never showed it.
        source_doc_ids: list[str] = []
        matched_id = _match_source_document(source_doc_name, doc_id_by_name)
        if matched_id:
            source_doc_ids.append(matched_id)

        # --- anti-hallucination checks: warn, don't reject --------------
        # The proposal is still created (a human may know the dates are
        # right) but it is flagged so the reviewer scrutinises it.
        if not reasoning:
            batch.warnings.append(
                f"task_index={idx} ({_safe_title(dateless, idx)}): "
                f"proposal cites no reasoning -- the prompt requires evidence"
            )
        # A source document is optional -- a proposal may be anchored to the
        # schedule sequence instead.  But a source that is NAMED yet matches
        # nothing we supplied is a hallucination signal.
        if source_doc_name and matched_id is None:
            batch.warnings.append(
                f"task_index={idx} ({_safe_title(dateless, idx)}): cited "
                f"source {source_doc_name!r} is not among the documents "
                f"shown to the model -- possible hallucination, verify "
                f"before accepting"
            )

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
# Scope reconciliation
# ---------------------------------------------------------------------------


def generate_scope_proposals(
    session: Session,
    provider: LLMProvider,
    project_id: Any,
    *,
    token_budget: int = 20_000,
    max_documents_with_text: int = 30,
    # Scope responses tend to be longer than timeline responses -- the
    # model lists multiple gap items, each with scope_item +
    # suggested_task_title + reasoning + source_document.  5000 leaves
    # enough room for ~15-20 well-cited gaps; complete_json bumps further
    # via its truncation-detection retry path.  Was 3000 -- raised after
    # 6554 Rue Saint Hubert produced 9k-character truncated JSON on the
    # first attempt AND the retry, with no useful result.
    max_output_tokens: int = 5000,
    embedding_provider: Any | None = None,
    rag_top_k: int = 8,
    rag_min_similarity: float = 0.25,
) -> ProposalBatch:
    """Flag scope-of-work items in a project's documents that have no Monday task.

    Reads the project's contract / SOW documents and its current task list,
    and asks the LLM which committed scope items are not represented by any
    task.  Each gap becomes an advisory Proposal (entity_type="Project",
    field_name="scope_gap") for human review -- scope proposals are NOT
    auto-written back to Monday; the reviewer decides.

    A run is a no-op (``skipped_reason`` set) when the project has no
    extracted document text to read scope from.

    Proposals are flushed to the session but NOT committed -- the caller
    owns the transaction.
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
        kind="scope",
        prompt_version=SCOPE_PROMPT_VERSION,
    )
    if not ctx.document_texts:
        batch.skipped_reason = (
            "no contract/scope documents with extracted text "
            "(run extract-content first)"
        )
        return batch

    # RAG: pull the most scope-relevant passages (project-scoped) so deliverables
    # listed deep in a long SOW aren't missed by the recency truncation.
    rag_query = (
        f"{project_name} scope of work: deliverables, responsibilities, and "
        "items the contractor must perform"
    )
    rag_chunks = _retrieve_proposal_chunks(
        session, embedding_provider, project_id, rag_query,
        top_k=rag_top_k, min_similarity=rag_min_similarity,
    )
    batch.rag_chunks_used = len(rag_chunks)

    system, user = _build_scope_prompt(ctx, rag_chunks)
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

    items = _coerce_item_list(raw, key="scope_gaps")
    batch.llm_raw_item_count = len(items)
    _persist_scope_items(session, batch, items, ctx, project_id)
    return batch


def _build_scope_prompt(
    ctx: ProjectContext,
    rag_chunks: list[dict[str, Any]] | None = None,
) -> tuple[str, str]:
    """Construct (system, user) for scope-reconciliation proposals.

    The model is shown the project's contract / scope-of-work documents and
    its current Monday task list, and flags scope items the documents commit
    to that have NO corresponding task.  Gaps are grounded in THIS project's
    documents -- the canonical-roadmap injection was removed 2026-05-29 (it
    produced template-derived flags the PM had to second-guess; see the
    TIMELINE_PROMPT_VERSION note and STRATEGY.md rule N5).

    Instruction sits at the TAIL (truncation lesson from the timeline prompt).
    """
    system = (
        "You are a construction project analyst.  You compare a project's "
        "contract and scope-of-work documents against its current Monday "
        "task list, and flag scope items the documents commit to that have "
        "NO corresponding task.\n\n"
        "Hard rules:\n"
        "- Flag ONLY scope items explicitly stated in the documents shown.  "
        "Never invent scope.\n"
        "- If a current task already covers a scope item, do NOT flag it -- "
        "even if the wording differs.\n"
        "- A flag is a genuine GAP: real work the documents require that the "
        "task list is missing.\n"
        "- Every flag must cite the specific document and clause/section in "
        "'reasoning'.\n"
        "- Returning few flags, or none, is correct when the task list "
        "already covers the documented scope.\n"
        "\n- Output STRICT JSON only.  No prose, no markdown fences."
    )

    lines: list[str] = []
    lines.append("=== PROJECT ===")
    for k in ("name", "code", "status"):
        v = ctx.project.get(k)
        if v:
            lines.append(f"{k}: {v}")

    lines.append(f"\n=== CURRENT MONDAY TASKS ({len(ctx.tasks)}) ===")
    if ctx.tasks:
        for t in ctx.tasks:
            sub = " [subitem]" if t.get("is_subitem") else ""
            lines.append(f"- {t.get('title', '(untitled)')}{sub}")
    else:
        lines.append("(none -- this project has no tasks yet)")

    # Relevance-retrieved excerpts (RAG) first -- targeted scope passages,
    # including from parts of long SOWs the recency truncation below cut.
    lines.extend(_render_rag_excerpts(rag_chunks or []))

    lines.append(f"\n=== DOCUMENT TEXT ({len(ctx.document_texts)} document(s)) ===")
    for d in ctx.document_texts:
        header = f"\n--- DOCUMENT: {d['name']}"
        if d.get("folder_path"):
            header += f"  |  Drive folder: {d['folder_path']}"
        if d.get("mime_type"):
            header += f"  |  type: {d['mime_type']}"
        header += " ---"
        lines.append(header)
        if d.get("truncated"):
            lines.append(
                f"(NOTE: only the first {len(d['text'])} characters of this "
                f"document are shown -- it continues beyond this point.)"
            )
        lines.append(d["text"])

    context_block = "\n".join(lines)

    user = (
        f"{context_block}\n\n"
        "---\n\n"
        "INSTRUCTION: Compare the scope of work in the documents above "
        "against the CURRENT MONDAY TASKS.  Identify scope items the "
        "documents commit to that NO current task covers.  Skip anything a "
        "task already covers.  Flag only real gaps."
        "\n\nEVIDENCE-CITATION REQUIREMENT for the 'reasoning' field:\n"
        "- Include a direct QUOTED EXCERPT in double quotes (max ~30 words) "
        "of the exact sentence or clause from the source document that "
        "commits to this scope.  Name the document.  Then one short sentence "
        "explaining why no current Monday task covers it.\n"
        '- A reasoning that says only "stated in the contract" or '
        '"part of the scope" is REJECTED.  Specific evidence required.\n\n'
        "Return strict JSON:\n\n"
        "{\n"
        '  "scope_gaps": [\n'
        "    {\n"
        '      "scope_item": "<the documented scope item, concise>",\n'
        '      "suggested_task_title": "<a Monday task title that would '
        'close the gap>",\n'
        '      "confidence": <float 0.0-1.0>,\n'
        '      "reasoning": "<quoted excerpt + document name + why missing.  '
        'See requirement above.>",\n'
        '      "source_document": "<exact document name>"\n'
        "    }\n"
        "  ]\n"
        "}\n\n"
        'If the task list already covers the documented scope, '
        'return {"scope_gaps": []}.'
    )
    return system, user


def _persist_scope_items(
    session: Session,
    batch: ProposalBatch,
    items: list[Any],
    ctx: ProjectContext,
    project_id: Any,
) -> None:
    """Validate each LLM scope item and turn the good ones into Proposal rows.

    A scope run is a fresh snapshot of what is missing: prior PENDING scope
    proposals for this project are superseded so the reviewer only ever sees
    the latest analysis.
    """
    try:
        project_uuid = uuid.UUID(str(project_id))
    except (ValueError, TypeError):
        batch.errors.append(f"bad project id {project_id!r}")
        return

    doc_id_by_name = {d["name"]: d["document_id"] for d in ctx.document_texts}
    # All titles (incl. subitems) -- used only to detect that *something* with
    # this name already exists.
    existing_titles = {
        (t.get("title") or "").strip().lower() for t in ctx.tasks
    }
    # lower-title -> list of TOP-LEVEL tasks with that title.  Only a top-level
    # task can host a subitem (Monday forbids sub-subitems), and a title may map
    # to >1 top-level task (a multi-address project has one "Structural
    # Demolition" per building) -- an AMBIGUOUS parent we must not guess at.
    top_level_by_title: dict[str, list[dict[str, Any]]] = {}
    for _t in ctx.tasks:
        if _t.get("is_subitem"):
            continue
        _key = (_t.get("title") or "").strip().lower()
        if _key:
            top_level_by_title.setdefault(_key, []).append(_t)

    # A scope run replaces the project's prior scope analysis.
    prior = (
        session.query(Proposal)
        .filter_by(
            entity_type="Project",
            entity_id=project_uuid,
            field_name="scope_gap",
            status=ProposalStatus.PENDING,
        )
        .all()
    )
    for old in prior:
        old.status = ProposalStatus.SUPERSEDED
        batch.superseded_count += 1

    for raw_item in items:
        if not isinstance(raw_item, dict):
            batch.errors.append(f"item is not an object: {raw_item!r}")
            continue

        scope_item = str(raw_item.get("scope_item") or "").strip()
        if not scope_item:
            batch.errors.append("scope item missing 'scope_item' text")
            continue

        suggested = str(raw_item.get("suggested_task_title") or "").strip()
        reasoning = str(raw_item.get("reasoning") or "").strip()
        confidence = _clamp_confidence(raw_item.get("confidence"))
        source_doc_name = raw_item.get("source_document")
        # Layer 2: the model labels each gap as 'contract' or 'roadmap'.
        # Default to 'contract' for backward compatibility -- pre-Layer-2
        # prompts don't request this field; missing == contract.
        source_label = str(raw_item.get("source") or "contract").strip().lower()
        if source_label not in {"contract", "roadmap"}:
            batch.warnings.append(
                f"scope item {scope_item!r}: unknown source label "
                f"{source_label!r} -- expected 'contract' or 'roadmap'.  "
                f"Defaulting to 'contract'."
            )
            source_label = "contract"

        # A title collision with an existing task is NOT proof of a duplicate.
        # The model was already shown the full task list and the instruction
        # "if a task covers this, don't flag it" -- it judged this a gap anyway.
        # The likely truth: this scope item is a SUB-STEP of the same-named
        # broad task (e.g. "install load-bearing columns" under "Structural
        # Demolition").  So instead of hard-rejecting, propose it as a SUBITEM
        # under that task and flag it for the reviewer.  (Was a hard reject
        # before 2026-06-15 -- it silently buried real specific gaps.)
        parent_task_title = ""
        parent_task_id = ""
        child_title = suggested
        if suggested and suggested.lower() in existing_titles:
            top_matches = top_level_by_title.get(suggested.lower(), [])
            child_title = scope_item  # the specific work, not the colliding bucket
            if len(top_matches) == 1:
                # Unambiguous parent -- nest under it and pin the exact id so
                # accept never has to re-match by (possibly duplicated) title.
                parent = top_matches[0]
                parent_task_title = (parent.get("title") or "").strip()
                parent_task_id = str(parent.get("canonical_id") or "")
                batch.warnings.append(
                    f"scope item {scope_item!r}: a task titled {suggested!r} "
                    f"already exists -- proposing this as a SUBITEM under it; "
                    f"verify the hierarchy before accepting"
                )
            elif len(top_matches) > 1:
                # >1 top-level task shares this title -- cannot pick a parent
                # safely.  Propose top-level and flag for manual re-parenting.
                batch.warnings.append(
                    f"scope item {scope_item!r}: {len(top_matches)} top-level "
                    f"tasks are named {suggested!r} -- ambiguous parent; "
                    f"proposing as a top-level item, re-parent in Monday if needed"
                )
            else:
                # The only same-named task(s) are subitems -- a subitem cannot
                # host another.  Propose top-level.
                batch.warnings.append(
                    f"scope item {scope_item!r}: a SUBITEM named {suggested!r} "
                    f"exists but a subitem cannot host another -- proposing as a "
                    f"top-level item"
                )

        source_doc_ids: list[str] = []
        matched_id = _match_source_document(source_doc_name, doc_id_by_name)
        if matched_id:
            source_doc_ids.append(matched_id)

        # --- anti-hallucination checks: warn, don't reject ------------------
        if not reasoning:
            batch.warnings.append(
                f"scope item {scope_item!r}: cites no reasoning -- the "
                f"prompt requires a document/clause citation"
            )
        # Source-doc check only applies to contract-sourced flags.
        # Roadmap-sourced flags legitimately have no source_document.
        if source_label == "contract" and source_doc_name and matched_id is None:
            batch.warnings.append(
                f"scope item {scope_item!r}: cited source {source_doc_name!r} "
                f"is not among the documents shown to the model -- possible "
                f"hallucination, verify before accepting"
            )

        proposal = Proposal(
            entity_type="Project",
            entity_id=project_uuid,
            field_name="scope_gap",
            proposed_value=json.dumps({
                "scope_item": scope_item,
                "suggested_task_title": child_title,
                "parent_task_title": parent_task_title,
                "parent_task_id": parent_task_id,
                "reasoning": reasoning,
                "source": source_label,
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


def _coerce_item_list(raw: Any, *, key: str = "proposals") -> list[Any]:
    """Pull the item list out of whatever shape the LLM returned.

    Accepts ``{<key>: [...]}`` (the requested shape) or a bare ``[...]``
    list (a common LLM deviation).  Anything else -> [].  ``key`` is
    "proposals" for timelines, "scope_gaps" for scope reconciliation.
    """
    if isinstance(raw, dict):
        inner = raw.get(key)
        return inner if isinstance(inner, list) else []
    if isinstance(raw, list):
        return raw
    return []


def _safe_title(dateless: list[dict[str, Any]], idx: int) -> str:
    """Best-effort task title for a warning message.  Never raises."""
    if 0 <= idx < len(dateless):
        return str(dateless[idx].get("title") or "untitled")
    return "?"


def _match_source_document(
    name: Any, doc_id_by_name: dict[str, str]
) -> str | None:
    """Resolve an LLM-cited source-document name to a canonical id, or None.

    ``None`` means the cited name matches NO document we supplied -- the
    caller treats that as a possible hallucination and flags the proposal.

    Matching is deliberately generous because models abbreviate ("the
    contract" for "Alta Construction Group - contract.pdf"): exact, then
    case-insensitive exact, then an UNAMBIGUOUS substring match in either
    direction.  An ambiguous substring (2+ candidate documents) returns
    None -- we will not guess which document the evidence came from.
    """
    if not name or not isinstance(name, str):
        return None
    cited = name.strip()
    if cited in doc_id_by_name:
        return doc_id_by_name[cited]
    lowered = {k.lower(): v for k, v in doc_id_by_name.items()}
    if cited.lower() in lowered:
        return lowered[cited.lower()]
    cl = cited.lower()
    hits = {
        v for k, v in doc_id_by_name.items()
        if cl in k.lower() or k.lower() in cl
    }
    if len(hits) == 1:
        return next(iter(hits))
    return None


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
    elif proposal.entity_type == "Project":
        from project_db.db.models import Project
        project = (
            session.query(Project)
            .filter_by(canonical_id=proposal.entity_id)
            .one_or_none()
        )
        if project is not None:
            info["entity_label"] = project.name
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


def bulk_dismiss_stale(
    session: Session,
    project_id: Any,
    *,
    days_old: int = 30,
    decided_by: str = "pm-bulk-dismiss",
) -> int:
    """Reject all PENDING proposals older than days_old days for a project.

    Never deletes rows -- sets status=REJECTED with a timestamped reason so
    history is preserved and future proposals for the same target are not
    penalized (supersession only looks at PENDING rows, not REJECTED ones).
    Returns the number of proposals dismissed.
    """
    from datetime import datetime, timedelta

    from project_db.db.models.work import Task as _Task  # avoid shadowing

    try:
        pid = uuid.UUID(str(project_id))
    except (ValueError, TypeError):
        return 0

    cutoff = datetime.utcnow() - timedelta(days=days_old)
    # entity_id is UUID(as_uuid=True); use UUID objects in all filters.
    task_uuids = [
        row[0]
        for row in session.query(_Task.canonical_id).filter(_Task.project_id == pid).all()
    ]

    stale: list[Proposal] = []
    if task_uuids:
        stale.extend(
            session.query(Proposal)
            .filter(
                Proposal.entity_type == "Task",
                Proposal.entity_id.in_(task_uuids),
                Proposal.status == ProposalStatus.PENDING,
                Proposal.created_at < cutoff,
            )
            .all()
        )
    stale.extend(
        session.query(Proposal)
        .filter(
            Proposal.entity_type == "Project",
            Proposal.entity_id == pid,
            Proposal.status == ProposalStatus.PENDING,
            Proposal.created_at < cutoff,
        )
        .all()
    )

    now = datetime.utcnow()
    for p in stale:
        p.status = ProposalStatus.REJECTED
        p.rejection_reason = f"bulk-dismissed: stale (>{days_old} days old)"
        p.decided_at = now
        p.decided_by = decided_by

    session.flush()
    return len(stale)


# Proposal field_names the approval loop knows how to ACT on (write back).
# "timeline"     -> Monday timeline column (start + end dates).
# "task_status"  -> Monday status column (Done / Working on it / Stuck).
# "scope_gap"    -> creates a new Monday item from a scope-gap proposal.
# "new_task"     -> creates a new Monday item from a field-note signal.
# "scope_change" -> creates a new Monday item from a field-note scope signal.
_ACCEPTABLE_FIELDS = {"timeline", "task_status", "scope_gap", "new_task", "scope_change"}


def accept_proposal(
    session: Session,
    proposal_id: Any,
    *,
    writeback: Any = None,
    dry_run: bool = False,
    decided_by: str | None = None,
) -> dict[str, Any]:
    """Accept a PENDING proposal: write the change to Monday, then flip status.

    ORDER IS LOAD-BEARING.  The Monday write happens FIRST; the proposal
    flips to ACCEPTED only on a True return.  Reverse that and a failed
    write would leave an ACCEPTED proposal that never reached Monday.
    (`MondayConnector.sync_back` returns a clean bool and never raises,
    which makes the ordering safe to rely on.)

    dry_run=True: resolve + validate everything, return a preview of what
    WOULD be written, touch nothing -- no DB change, no API call.
    ``writeback`` may be None in dry-run mode.

    For a real accept, ``writeback`` must expose
    ``sync_back(entity, field_updates) -> bool`` -- in practice a
    ``MondayConnector``; in tests, a fake.

    Returns ``{"ok": bool, ...}``.  On ANY failure the proposal is left
    PENDING and nothing is written.
    """
    from project_db.db.models import Task
    from project_db.db.models.work import Project

    # --- resolve + guard --------------------------------------------------
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
                f"proposals can be accepted"
            ),
        }

    if p.field_name not in _ACCEPTABLE_FIELDS:
        return {
            "ok": False,
            "error": (
                f"don't know how to act on a {p.field_name!r} proposal yet "
                f"(acceptable: {sorted(_ACCEPTABLE_FIELDS)})"
            ),
        }

    # --- parse the proposed value ----------------------------------------
    try:
        value = json.loads(p.proposed_value)
    except (json.JSONDecodeError, TypeError):
        return {"ok": False, "error": "proposed_value is not valid JSON"}

    # --- dispatch to field-specific handler (each loads its own entity) ---
    if p.field_name in ("timeline", "task_status"):
        if p.entity_type != "Task":
            return {"ok": False, "error": f"{p.field_name!r} requires entity_type=Task, got {p.entity_type!r}"}
        task = session.query(Task).filter_by(canonical_id=p.entity_id).one_or_none()
        if task is None:
            return {"ok": False, "error": f"target Task {p.entity_id} not found"}
        if p.field_name == "timeline":
            return _accept_timeline(
                session, p, task, value, writeback=writeback, dry_run=dry_run,
                decided_by=decided_by,
            )
        return _accept_task_status(
            session, p, task, value, writeback=writeback, dry_run=dry_run,
            decided_by=decided_by,
        )

    if p.field_name in ("scope_gap", "new_task", "scope_change"):
        if p.entity_type != "Project":
            return {"ok": False, "error": f"{p.field_name!r} requires entity_type=Project, got {p.entity_type!r}"}
        project = session.query(Project).filter_by(canonical_id=p.entity_id).one_or_none()
        if project is None:
            return {"ok": False, "error": f"target Project {p.entity_id} not found"}
        return _accept_create_task(
            session, p, project, value, writeback=writeback, dry_run=dry_run,
            decided_by=decided_by,
        )

    # Guard: unreachable if _ACCEPTABLE_FIELDS and dispatch branches stay in sync.
    return {
        "ok": False,
        "error": (
            f"accept handler for {p.field_name!r} is not yet implemented "
            f"(field is in _ACCEPTABLE_FIELDS but has no dispatch branch)"
        ),
    }


def _accept_timeline(
    session: Session,
    p: Any,
    task: Any,
    value: dict,
    *,
    writeback: Any,
    dry_run: bool,
    decided_by: str | None,
) -> dict[str, Any]:
    """Accept handler for field_name='timeline' (A2/A3: Monday first, mirror second)."""
    start = _parse_date(value.get("start_date"))
    end = _parse_date(value.get("end_date"))
    if start is None or end is None:
        return {
            "ok": False,
            "error": (
                f"proposed_value has unparseable dates: "
                f"start={value.get('start_date')!r} end={value.get('end_date')!r}"
            ),
        }
    field_updates = {"timeline": {"from": start.isoformat(), "to": end.isoformat()}}
    if dry_run:
        return {
            "ok": True, "dry_run": True,
            "proposal_id": str(p.canonical_id),
            "task_title": task.title, "field": "timeline",
            "would_write": field_updates,
            "note": "Nothing written. Re-run without --dry-run to apply.",
        }
    if writeback is None:
        return {"ok": False, "error": "no writeback connector supplied for a non-dry-run accept"}
    try:
        wrote = writeback.sync_back(task, field_updates)
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": f"write-back raised ({exc}) -- proposal left PENDING"}
    if not wrote:
        return {
            "ok": False,
            "error": (
                "Monday write-back returned False -- proposal left PENDING. "
                "Likely causes: the task's board has no timeline column, or "
                "no Monday mapping (ExternalId) exists for this task."
            ),
        }
    p.status = ProposalStatus.ACCEPTED
    p.decided_at = datetime.utcnow()
    p.decided_by = decided_by
    task.start_date = start
    task.end_date = end
    session.flush()
    return {
        "ok": True, "dry_run": False,
        "proposal_id": str(p.canonical_id),
        "previous_status": "PENDING", "new_status": "ACCEPTED",
        "task_title": task.title, "wrote_to_monday": field_updates,
        "decided_by": decided_by,
    }


def _accept_task_status(
    session: Session,
    p: Any,
    task: Any,
    value: dict,
    *,
    writeback: Any,
    dry_run: bool,
    decided_by: str | None,
) -> dict[str, Any]:
    """Accept handler for field_name='task_status' (A2/A3: Monday first, mirror second)."""
    from project_db.db.models.work import TaskStatus

    monday_label = value.get("monday_label")
    canonical_status_str = value.get("status")
    if not monday_label or not canonical_status_str:
        return {
            "ok": False,
            "error": (
                "proposed_value must have 'monday_label' and 'status' keys; "
                f"got: {list(value.keys())}"
            ),
        }
    try:
        canonical_status = TaskStatus(canonical_status_str)
    except ValueError:
        return {
            "ok": False,
            "error": f"unknown canonical status {canonical_status_str!r}",
        }

    field_updates = {"status": {"label": monday_label}}

    if dry_run:
        return {
            "ok": True, "dry_run": True,
            "proposal_id": str(p.canonical_id),
            "task_title": task.title, "field": "task_status",
            "would_write": field_updates,
            "note": "Nothing written. Re-run without --dry-run to apply.",
        }
    if writeback is None:
        return {"ok": False, "error": "no writeback connector supplied for a non-dry-run accept"}
    try:
        wrote = writeback.sync_back(task, field_updates)
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": f"write-back raised ({exc}) -- proposal left PENDING"}
    if not wrote:
        return {
            "ok": False,
            "error": (
                "Monday write-back returned False -- proposal left PENDING. "
                "Likely causes: the task's board has no status column, or "
                "no Monday mapping (ExternalId) exists for this task."
            ),
        }
    p.status = ProposalStatus.ACCEPTED
    p.decided_at = datetime.utcnow()
    p.decided_by = decided_by
    task.status = canonical_status
    task.monday_status_label = monday_label
    session.flush()
    return {
        "ok": True, "dry_run": False,
        "proposal_id": str(p.canonical_id),
        "previous_status": "PENDING", "new_status": "ACCEPTED",
        "task_title": task.title, "wrote_to_monday": field_updates,
        "decided_by": decided_by,
    }


def _accept_create_task(
    session: Session,
    p: Any,
    project: Any,
    value: dict,
    *,
    writeback: Any,
    dry_run: bool,
    decided_by: str | None,
) -> dict[str, Any]:
    """Accept handler for scope_gap / new_task / scope_change proposals.

    Creates a new Monday item (or SUBITEM, when the proposal names a parent
    task) and mirrors it as a canonical Task + ExternalId.  ORDER IS
    LOAD-BEARING: Monday write first, canonical mirror second, proposal flip
    last.
    """
    from project_db.db.models.work import Task, TaskStatus
    from project_db.db.models import ExternalId

    title = (
        (value.get("new_task_title") or "").strip()
        or (value.get("suggested_task_title") or "").strip()
        or (value.get("scope_item") or "").strip()
        or "New task"
    )

    # Optional parent: when the gap is a sub-step of an existing task, the
    # proposal carries its title.  Resolve to a canonical Task on THIS project
    # (case-insensitive) so the new task is created as a Monday subitem rather
    # than an orphan top-level item.
    parent_title = (value.get("parent_task_title") or "").strip()
    parent_id_raw = (value.get("parent_task_id") or "").strip()
    parent_task = None
    if parent_id_raw:
        # Preferred: generation pinned the exact parent canonical_id, so there
        # is no title ambiguity to resolve.
        try:
            parent_uuid = uuid.UUID(parent_id_raw)
        except (ValueError, TypeError):
            return {"ok": False, "error": f"bad parent_task_id {parent_id_raw!r}"}
        parent_task = session.query(Task).filter_by(canonical_id=parent_uuid).one_or_none()
        if parent_task is None:
            return {
                "ok": False,
                "error": (
                    f"parent task {parent_id_raw} no longer exists -- "
                    f"cannot create subitem"
                ),
            }
    elif parent_title:
        # Legacy / title-only proposals: resolve among TOP-LEVEL tasks only
        # (a subitem cannot host another) and REFUSE if the title is ambiguous
        # rather than guessing the wrong parent.
        matches = (
            session.query(Task)
            .filter(
                Task.project_id == project.canonical_id,
                func.lower(Task.title) == parent_title.lower(),
                Task.is_subitem.is_(False),
            )
            .all()
        )
        if not matches:
            return {
                "ok": False,
                "error": (
                    f"no top-level parent task titled {parent_title!r} on project "
                    f"{project.name!r} -- cannot create subitem"
                ),
            }
        if len(matches) > 1:
            return {
                "ok": False,
                "error": (
                    f"{len(matches)} top-level tasks are named {parent_title!r} "
                    f"-- ambiguous parent; re-file this subitem manually in Monday"
                ),
            }
        parent_task = matches[0]

    # A subitem cannot host another subitem (Monday forbids sub-subitems).
    if parent_task is not None and parent_task.is_subitem:
        return {
            "ok": False,
            "error": (
                f"parent task {parent_task.title!r} is itself a subitem -- "
                f"Monday cannot nest a subitem under a subitem"
            ),
        }

    if dry_run:
        return {
            "ok": True, "dry_run": True,
            "proposal_id": str(p.canonical_id),
            "task_title": project.name,
            "field": p.field_name,
            "would_write": (
                {"create_subitem": title, "under_parent": parent_title}
                if parent_task is not None
                else {"create_item": title}
            ),
            "note": "Nothing written. Re-run without dry_run to apply.",
        }

    if writeback is None:
        return {"ok": False, "error": "no writeback connector supplied for a non-dry-run accept"}

    # Create the Monday item/subitem (raises RuntimeError on API failure).
    try:
        item = writeback.create_task(project, title, parent_task=parent_task)
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": f"Monday create failed: {exc}"}

    if not item or not item.get("id"):
        return {"ok": False, "error": "Monday returned empty result for create"}

    monday_item_id = int(item["id"])

    # Board id for the external_url.  A subitem lives on its own subitem board
    # (returned in the create result); a top-level item lives on the project
    # board (looked up from the project's ExternalId).
    board_id_str = ""
    if parent_task is not None:
        board_id_str = str((item.get("board") or {}).get("id") or "")
    if not board_id_str:
        board_ext = (
            session.query(ExternalId)
            .filter(
                ExternalId.entity_type == "Project",
                ExternalId.canonical_id == project.canonical_id,
                ExternalId.external_key.like("board:%"),
            )
            .one_or_none()
        )
        board_id_str = board_ext.external_key.split(":", 1)[1] if board_ext else ""
    source = writeback.source if hasattr(writeback, "source") else "MONDAY"

    # Mirror in canonical DB (preserve the subitem hierarchy on the read side).
    new_task = Task(
        title=title,
        project_id=project.canonical_id,
        status=TaskStatus.TODO,
        is_subitem=parent_task is not None,
        parent_task_id=parent_task.canonical_id if parent_task is not None else None,
    )
    session.add(new_task)
    session.flush()  # materialise canonical_id

    ext = ExternalId(
        source=source,
        entity_type="Task",
        canonical_id=new_task.canonical_id,
        external_key=str(monday_item_id),
        external_url=(
            f"https://view.monday.com/boards/{board_id_str}/pulses/{monday_item_id}"
            if board_id_str else None
        ),
        last_synced_at=datetime.utcnow(),
    )
    session.add(ext)

    p.status = ProposalStatus.ACCEPTED
    p.decided_at = datetime.utcnow()
    p.decided_by = decided_by
    session.flush()

    wrote = (
        {"create_subitem": title, "under_parent": parent_title, "monday_id": monday_item_id}
        if parent_task is not None
        else {"create_item": title, "monday_id": monday_item_id}
    )
    return {
        "ok": True, "dry_run": False,
        "proposal_id": str(p.canonical_id),
        "previous_status": "PENDING", "new_status": "ACCEPTED",
        "task_title": project.name,
        "wrote_to_monday": wrote,
        "decided_by": decided_by,
    }


def set_task_timeline(
    session: Session,
    task_id: Any,
    *,
    start_date: Any,
    end_date: Any,
    writeback: Any,
    decided_by: str | None = None,
) -> dict[str, Any]:
    """Write a task's timeline directly to Monday + mirror onto the canonical row.

    The "manual edit" sibling of ``accept_proposal``.  No Proposal row is
    created -- this is a deliberate human action, not an AI suggestion,
    so the proposal table would only add noise.  The audit trail lives
    in Monday's activity log + this DB's updated_at on the Task.

    SAME ORDERING as accept_proposal: Monday write FIRST, canonical
    mirror SECOND.  A failed write leaves the Task untouched.

    Args:
      task_id      canonical Task UUID
      start_date   ISO date string or date; may be None to clear the column
      end_date     ISO date string or date; may be None
      writeback    Object with ``sync_back(task, field_updates) -> bool``
                   (in practice ``MondayConnector``; in tests, a fake)
      decided_by   Audit string; mirrored onto Task.notes for traceability
                   when set (cheap audit; structured audit will follow
                   when M5 ships a dedicated activity log).

    Returns ``{"ok": bool, ...}``.  On any failure the DB is left untouched.
    """
    from project_db.db.models import Task

    try:
        tid = uuid.UUID(str(task_id))
    except (ValueError, TypeError):
        return {"ok": False, "error": f"not a valid UUID: {task_id!r}"}

    task = session.query(Task).filter_by(canonical_id=tid).one_or_none()
    if task is None:
        return {"ok": False, "error": f"no task with id {task_id}"}

    # Both dates optional, but if BOTH are missing it's a no-op (clearing
    # a Monday timeline column requires a different payload shape we
    # haven't built yet -- guard against it explicitly so we don't write
    # something the connector silently ignores).
    start = _parse_date(start_date) if start_date else None
    end = _parse_date(end_date) if end_date else None
    if start is None and end is None:
        return {
            "ok": False,
            "error": "at least one of start_date / end_date is required "
                     "(clearing the timeline isn't supported yet).",
        }
    if start_date and start is None:
        return {"ok": False, "error": f"unparseable start_date: {start_date!r}"}
    if end_date and end is None:
        return {"ok": False, "error": f"unparseable end_date: {end_date!r}"}
    if start and end and end < start:
        return {
            "ok": False,
            "error": f"end_date ({end}) is before start_date ({start})",
        }

    if writeback is None:
        return {"ok": False, "error": "no writeback connector supplied"}

    # If only one date was supplied, default the missing one to the
    # supplied one so Monday gets a valid 2-key payload.  Single-date
    # timelines aren't well-supported by Monday's timeline column.
    monday_from = (start or end).isoformat()
    monday_to = (end or start).isoformat()
    field_updates = {"timeline": {"from": monday_from, "to": monday_to}}

    try:
        wrote = writeback.sync_back(task, field_updates)
    except Exception as exc:  # noqa: BLE001
        return {
            "ok": False,
            "error": f"write-back raised ({exc}) -- task left unchanged",
        }
    if not wrote:
        return {
            "ok": False,
            "error": (
                "Monday write-back returned False -- task left unchanged. "
                "Likely causes: the task's board has no timeline column, or "
                "no Monday mapping (ExternalId) exists for this task."
            ),
        }

    # Mirror onto canonical Task.  ``end`` may be None when caller only
    # supplied start (legal as long as we got SOMETHING).
    task.start_date = start
    task.end_date = end
    if decided_by:
        # Lightweight audit note -- not a formal log, just enough to see
        # in `project_db doctor` / the UI later that this was a manual edit.
        prefix = f"[manual edit by {decided_by}] "
        task.notes = (prefix + (task.notes or "")).strip()
    session.flush()

    return {
        "ok": True,
        "task_id": str(tid),
        "task_title": task.title,
        "wrote_to_monday": field_updates,
        "start_date": start.isoformat() if start else None,
        "end_date": end.isoformat() if end else None,
        "decided_by": decided_by,
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
        valid_doc_uuids: list[uuid.UUID] = []
        for x in doc_ids:
            try:
                valid_doc_uuids.append(uuid.UUID(str(x)))
            except (ValueError, AttributeError, TypeError):
                pass
        if valid_doc_uuids:
            from project_db.db.models import Document
            for d in (
                session.query(Document)
                .filter(Document.canonical_id.in_(valid_doc_uuids))
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
