"""Deterministic labour-claim consolidation (no LLM).

Turns ``LabourClaim`` rows (from ANY source -- Gmail bridge today, Telegram
later) into ``LabourClaimCluster``s: groups of claims that probably describe
the same real-world shift. Matching sources reinforce; disagreement is surfaced
as a CONFLICT, never silently collapsed (the labour twin of the financial
reconcile gate).

Also the Gmail bridge: emit ``LabourClaim`` rows from the existing
``ProjectLogEntry`` rows so the consolidation layer works on real data today,
without changing the Project Log ingestion path.

All deterministic. The LLM only ever produces claims (elsewhere); clustering,
status, and canonical decisions are code.
"""

from __future__ import annotations

import json
import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy.orm import Session

from project_db.db.models import (
    LabourClaim,
    LabourClaimCluster,
    LabourClaimClusterMember,
    LabourSourceEvent,
)
from project_db.db.models.project_log import ProjectLogEntry, ProjectLogSubmission

# Two reported totals farther apart than this (hours) are a material conflict.
_HOURS_CONFLICT_TOL = Decimal("0.25")
_LOW_CONFIDENCE_THRESHOLD = 0.5  # below this, claims are flagged "low_confidence" for review
_AUTO_CLAIM_TYPES = {"labour_time", "attendance_only"}
_SOFT_REVIEW_FLAGS = {"low_confidence", "hours_mismatch"}

BRIDGE_VERSION = "gmail-bridge-v1"


def _norm(s: str | None) -> str:
    return " ".join((s or "").lower().split())


# ---------------------------------------------------------------------------
# Gmail bridge: ProjectLogEntry -> LabourClaim
# ---------------------------------------------------------------------------


def bridge_project_log_to_claims(session: Session, project_id: Any) -> int:
    """Emit a LabourClaim per ProjectLogEntry for a project (idempotent).

    Creates one LabourSourceEvent per ProjectLogSubmission and one LabourClaim
    per ProjectLogEntry, preserving the entry's resolved worker, raw name, times,
    and reported/computed hours. Re-running replaces the project's gmail-sourced
    claims+events. Returns the number of claims written. Flushes (caller commits).
    """
    # Idempotent: drop this project's prior gmail claims + their source events.
    prior_claims = (
        session.query(LabourClaim)
        .filter(LabourClaim.project_id == project_id, LabourClaim.source_channel == "gmail")
        .all()
    )
    prior_event_ids = {c.source_event_id for c in prior_claims if c.source_event_id}
    for c in prior_claims:
        session.delete(c)
    session.flush()
    if prior_event_ids:
        session.query(LabourSourceEvent).filter(
            LabourSourceEvent.canonical_id.in_(prior_event_ids)
        ).delete(synchronize_session="fetch")
    session.flush()

    pairs = (
        session.query(ProjectLogEntry, ProjectLogSubmission)
        .join(
            ProjectLogSubmission,
            ProjectLogSubmission.canonical_id == ProjectLogEntry.submission_id,
        )
        .filter(ProjectLogEntry.project_id == project_id)
        .all()
    )

    # One source event per submission (so claims keep their form provenance).
    events_by_submission: dict[Any, LabourSourceEvent] = {}
    written = 0
    for entry, submission in pairs:
        ev = events_by_submission.get(submission.canonical_id)
        if ev is None:
            ev = LabourSourceEvent(
                canonical_id=uuid.uuid4(),
                source_channel="gmail",
                source_kind="email_project_log",
                source_external_id=submission.source_email_message_id,
                source_message_id=submission.source_email_message_id,
                received_at=submission.received_at or datetime.utcnow(),
                ingestion_status="extracted",
                project_id_hint=project_id,
                raw_text=None,
            )
            session.add(ev)
            session.flush()
            events_by_submission[submission.canonical_id] = ev

        claim_type = "labour_time" if entry.total_hours_reported is not None else "attendance_only"
        claim = LabourClaim(
            canonical_id=uuid.uuid4(),
            source_event_id=ev.canonical_id,
            source_channel="gmail",
            source_confidence=entry.confidence,
            reporter_role="supervisor",  # the Project Log sheet is supervisor-filed
            reported_for_worker_id=entry.employee_id,
            employee_name_raw=entry.employee_name_raw,
            employee_match_method=entry.employee_match_method or "unresolved",
            employee_match_confidence=entry.employee_match_confidence,
            project_id=entry.project_id,
            project_name_raw=entry.site_name_raw,
            project_match_method="site_name" if entry.project_id else "unresolved",
            work_date=entry.work_date,
            work_date_raw=entry.work_date.isoformat() if entry.work_date else None,
            time_arrived=entry.time_arrived,
            time_left=entry.time_left,
            lunch_hours=entry.lunch_hours,
            total_hours_reported=entry.total_hours_reported,
            total_hours_computed=entry.total_hours_computed,
            hours_mismatch=bool(entry.hours_mismatch),
            claim_type=claim_type,
            extraction_method="gmail_bridge",
            extractor_version=BRIDGE_VERSION,
            review_status="pending",
        )
        session.add(claim)
        written += 1
    session.flush()
    return written


# ---------------------------------------------------------------------------
# Consolidation: claims -> clusters
# ---------------------------------------------------------------------------


@dataclass
class ConsolidationResult:
    project_id: str
    clusters: int = 0
    reinforced: int = 0
    single_source: int = 0
    needs_review: int = 0
    conflict: int = 0
    claims_clustered: int = 0
    warnings: list[str] = field(default_factory=list)

    def summary(self) -> str:
        return (
            f"Consolidated {self.claims_clustered} claim(s) into {self.clusters} cluster(s): "
            f"{self.reinforced} reinforced, {self.single_source} single-source, "
            f"{self.needs_review} needs-review, {self.conflict} conflict"
        )


def _worker_key(claim: LabourClaim) -> str | None:
    if claim.reported_for_worker_id:
        return f"w:{claim.reported_for_worker_id}"
    if claim.employee_name_raw:
        return f"n:{_norm(claim.employee_name_raw)}"
    return None


def _pick_chosen(members: list[LabourClaim]) -> LabourClaim:
    """The member that best represents the shift: most complete time fields,
    breaking ties toward the supervisor sheet (gmail)."""

    def score(c: LabourClaim) -> tuple:
        completeness = sum(
            1 for v in (c.time_arrived, c.time_left, c.total_hours_reported) if v is not None
        )
        gmail_pref = 1 if c.source_channel == "gmail" else 0
        return (completeness, gmail_pref)

    return max(members, key=score)


def _usable_hours_or_time(claim: LabourClaim) -> bool:
    return (
        claim.total_hours_reported is not None
        or claim.total_hours_computed is not None
        or (claim.time_arrived is not None and claim.time_left is not None)
    )


def _claim_review_flags(claim: LabourClaim) -> set[str]:
    flags: set[str] = set()
    if claim.claim_type not in _AUTO_CLAIM_TYPES:
        flags.add(f"claim_type:{claim.claim_type or 'unknown'}")
    if claim.review_status == "needs_review":
        flags.add("claim_needs_review")
    if claim.source_confidence is not None and claim.source_confidence < _LOW_CONFIDENCE_THRESHOLD:
        flags.add("low_confidence")
    if claim.hours_mismatch:
        flags.add("hours_mismatch")
    if claim.reported_for_worker_id is None:
        flags.add("unresolved_worker")
    if claim.project_id is None:
        flags.add("unresolved_project")
    if claim.work_date is None:
        flags.add("missing_date")
    if not _usable_hours_or_time(claim):
        flags.add("missing_hours")
    return flags


def _build_cluster(
    session: Session,
    project_id: Any,
    members: list[LabourClaim],
    dateless: bool,
    cluster_key: str,
) -> str:
    """Create one cluster (+ members) from a group of co-keyed claims. Returns status."""
    worker_id = next((m.reported_for_worker_id for m in members if m.reported_for_worker_id), None)
    work_date = next((m.work_date for m in members if m.work_date), None)
    channels = sorted({m.source_channel for m in members})
    review_flags = sorted({flag for m in members for flag in _claim_review_flags(m)})
    hard_flags = {flag for flag in review_flags if flag not in _SOFT_REVIEW_FLAGS}

    reported = [
        Decimal(str(m.total_hours_reported)) for m in members if m.total_hours_reported is not None
    ]
    hours_conflict = bool(reported) and (max(reported) - min(reported) > _HOURS_CONFLICT_TOL)

    worker_unresolved = worker_id is None

    # Status (per the plan's rules).
    conflict_flags: list[str] = []
    if hours_conflict:
        conflict_flags.append("hours")
    for flag in review_flags:
        if flag not in conflict_flags:
            conflict_flags.append(flag)
    if dateless:
        status, resolution = "needs_review", "conflict_unresolved"
    elif hours_conflict:
        status, resolution = "conflict", "conflict_unresolved"
    elif worker_unresolved:
        status, resolution = "needs_review", "conflict_unresolved"
    elif hard_flags:
        status, resolution = "needs_review", "conflict_unresolved"
    elif len(channels) >= 2:
        status, resolution = "auto_reinforced", "auto_reinforced"
    else:
        status, resolution = "auto_single_source", "auto_single_source"

    chosen = _pick_chosen(members)

    # Confidence: evidence + resolution + agreement.
    conf = 0.5
    if not worker_unresolved:
        conf += 0.2
    if len(channels) >= 2 and not hours_conflict:
        conf += 0.2
    if not hours_conflict and not dateless:
        conf += 0.1
    if status in ("conflict", "needs_review"):
        conf = min(conf, 0.4)
    conf = round(min(1.0, conf), 2)

    cluster = LabourClaimCluster(
        canonical_id=uuid.uuid4(),
        worker_id=worker_id,
        project_id=project_id,
        work_date=work_date,
        cluster_key=cluster_key,
        confidence=conf,
        status=status,
        chosen_time_arrived=chosen.time_arrived,
        chosen_time_left=chosen.time_left,
        chosen_lunch_hours=chosen.lunch_hours,
        chosen_total_hours=chosen.total_hours_reported
        if chosen.total_hours_reported is not None
        else chosen.total_hours_computed,
        evidence_count=len(members),
        source_channels_json=json.dumps(channels),
        conflict_flags_json=json.dumps(conflict_flags) if conflict_flags else None,
        resolution_method=resolution,
    )
    session.add(cluster)
    session.flush()

    for i, m in enumerate(members):
        if m.claim_type == "correction":
            rel = "correction"
        elif hours_conflict and m is not chosen:
            rel = "conflicting"
        elif i == 0:
            rel = "primary"
        else:
            rel = "supporting"
        session.add(
            LabourClaimClusterMember(
                canonical_id=uuid.uuid4(),
                cluster_id=cluster.canonical_id,
                claim_id=m.canonical_id,
                relationship=rel,
            )
        )
        m.canonical_cluster_id = cluster.canonical_id
        m.canonicalized = status in ("auto_reinforced", "auto_single_source")
        if status in ("conflict", "needs_review"):
            m.review_status = "needs_review"
    session.flush()
    return status


def consolidate_claims(session: Session, project_id: Any) -> ConsolidationResult:
    """Cluster a project's LabourClaims into shifts. Idempotent rebuild. Commits.

    Coarse cluster key = (worker, project, date). Dateless claims are not
    cross-clustered -- each becomes a singleton needs-review cluster (a date is
    required to assert two reports are the same shift).
    """
    result = ConsolidationResult(project_id=str(project_id))

    # Idempotent: clear this project's prior clusters + members; detach claims.
    prior = (
        session.query(LabourClaimCluster).filter(LabourClaimCluster.project_id == project_id).all()
    )
    prior_ids = [c.canonical_id for c in prior]
    if prior_ids:
        session.query(LabourClaimClusterMember).filter(
            LabourClaimClusterMember.cluster_id.in_(prior_ids)
        ).delete(synchronize_session="fetch")
        session.query(LabourClaim).filter(LabourClaim.canonical_cluster_id.in_(prior_ids)).update(
            {"canonical_cluster_id": None, "canonicalized": False},
            synchronize_session="fetch",
        )
        for c in prior:
            session.delete(c)
    session.flush()

    claims = session.query(LabourClaim).filter(LabourClaim.project_id == project_id).all()

    groups: dict[tuple, list[LabourClaim]] = defaultdict(list)
    for claim in claims:
        wk = _worker_key(claim)
        dk = claim.work_date.isoformat() if claim.work_date else None
        if dk is None:
            # Singleton: cannot assert "same shift" without a date.
            key = ("__nodate__", str(claim.canonical_id))
        else:
            key = (wk or "?", dk)
        groups[key].append(claim)

    for key, members in groups.items():
        dateless = key[0] == "__nodate__"
        status = _build_cluster(session, project_id, members, dateless, "|".join(key))
        result.clusters += 1
        result.claims_clustered += len(members)
        if status == "auto_reinforced":
            result.reinforced += 1
        elif status == "auto_single_source":
            result.single_source += 1
        elif status == "conflict":
            result.conflict += 1
        else:
            result.needs_review += 1

    session.commit()
    return result
