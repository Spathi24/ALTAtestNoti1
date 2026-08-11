"""SC-2: deterministic ScopeContext backfill for the pilot (Documents only).

Creates the pilot 2026001 ("923-927 Rockland") scope contexts and binds its
Documents to them, using an EXPLICIT REGISTERED folder map -- NOT a general
"first subfolder == context" rule (the standard project Drive uses
organizational folders SOW/ quotes/ POs/ budget/ ... which must never become
contexts; see docs/templates/NAMING_CONVENTIONS.md). Anything not under a
registered context root is left UNRESOLVED (quarantine), never guessed.

Scope (SC-2, see docs/architecture/SCOPECONTEXT_TRANSITION_PLAN.md):
  - binds DOCUMENTS only; does NOT touch the 111 SowItems, quotes, budget, PO,
    or any other project's documents;
  - deterministic, no LLM;
  - idempotent: contexts get-or-created by (project_id, context_key); document
    state is a pure function of folder_path, so re-running is a no-op.

Usage:
    python project-db/scripts/backfill_scope_contexts.py            # apply
    python project-db/scripts/backfill_scope_contexts.py --dry-run  # report only
"""

from __future__ import annotations

import argparse

# Pilot registered mapping. The project folder is "923-927 Rockland"; the folder
# SEGMENT directly beneath it selects the context. Exact-match; unknown -> None
# -> UNRESOLVED. This is pilot-specific by design (SC-3 generalizes it).
PILOT_PROJECT_CODE = "2026001"
PILOT_PROJECT_FOLDER = "923-927 Rockland"
# context_key -> (label, kind, {registered folder segments})
PILOT_CONTEXTS: dict[str, tuple[str, str, set[str]]] = {
    "923_INTERIOR": ("923 Rockland -- Interior", "unit", {"923 Rockland"}),
    "927_UNIT": ("927 Rockland -- Unit", "unit", {"927 ROCKLAND"}),
    "EXTERIOR": ("Exterior / common", "area", {"EXTERIOR"}),
}


def _segment_to_key() -> dict[str, str]:
    """Flatten the registered map to {folder_segment: context_key}."""
    out: dict[str, str] = {}
    for key, (_label, _kind, segments) in PILOT_CONTEXTS.items():
        for seg in segments:
            out[seg] = key
    return out


def resolve_context_key(
    folder_path: str | None,
    *,
    project_folder: str = PILOT_PROJECT_FOLDER,
    segment_to_key: dict[str, str] | None = None,
) -> str | None:
    """Registered-mapping resolver: the folder segment directly beneath the
    project folder selects the context. Returns the context_key, or None when
    the path is missing / the project folder is absent / there is no segment
    below it / the segment is not a registered context root (-> UNRESOLVED).
    """
    if not folder_path:
        return None
    mapping = segment_to_key if segment_to_key is not None else _segment_to_key()
    parts = [p for p in folder_path.split("/") if p]
    if project_folder not in parts:
        return None
    idx = parts.index(project_folder)
    if idx + 1 >= len(parts):
        return None  # path stops at the project folder -- no context segment
    return mapping.get(parts[idx + 1])  # unknown segment -> None -> UNRESOLVED


def backfill_pilot_scope_contexts(session, *, project_code: str = PILOT_PROJECT_CODE) -> dict:
    """Idempotently create the pilot contexts and bind its Documents.

    Returns a summary dict. DOCUMENTS ONLY -- no scope/quote/budget/PO writes.
    """
    from project_db.db.models import Document, Project, ScopeContext

    project = session.query(Project).filter(Project.code == project_code).one()

    # 1. get-or-create the registered contexts (keyed by project + context_key).
    contexts: dict[str, ScopeContext] = {}
    created = 0
    for key, (label, kind, _segments) in PILOT_CONTEXTS.items():
        ctx = (
            session.query(ScopeContext)
            .filter_by(project_id=project.canonical_id, context_key=key)
            .one_or_none()
        )
        if ctx is None:
            ctx = ScopeContext(
                project_id=project.canonical_id,
                context_key=key,
                label=label,
                kind=kind,
            )
            session.add(ctx)
            session.flush()
            created += 1
        contexts[key] = ctx

    # 2. bind DOCUMENTS only. State is a pure function of folder_path -> idempotent.
    seg_map = _segment_to_key()
    docs = session.query(Document).filter(Document.project_id == project.canonical_id).all()
    resolved = unresolved = 0
    per_ctx: dict[str, int] = dict.fromkeys(PILOT_CONTEXTS, 0)
    for d in docs:
        key = resolve_context_key(d.folder_path, segment_to_key=seg_map)
        if key is not None:
            d.scope_context_id = contexts[key].canonical_id
            d.context_resolution_state = "RESOLVED"
            per_ctx[key] += 1
            resolved += 1
        else:
            d.scope_context_id = None
            d.context_resolution_state = "UNRESOLVED"
            unresolved += 1

    return {
        "project_code": project_code,
        "contexts_created": created,
        "contexts_total": len(contexts),
        "documents_seen": len(docs),
        "documents_resolved": resolved,
        "documents_unresolved": unresolved,
        "per_context": per_ctx,
    }


def main() -> None:
    from project_db.cli import force_utf8_output

    force_utf8_output()
    ap = argparse.ArgumentParser(description="SC-2 pilot ScopeContext backfill (Documents only)")
    ap.add_argument("--dry-run", action="store_true", help="report, do not commit")
    args = ap.parse_args()

    from project_db.db import session_scope

    with session_scope() as session:
        summary = backfill_pilot_scope_contexts(session)
        if args.dry_run:
            session.rollback()
        print("SC-2 backfill", "(DRY RUN)" if args.dry_run else "(committed):")
        for k, v in summary.items():
            print(f"  {k}: {v}")


if __name__ == "__main__":
    main()
