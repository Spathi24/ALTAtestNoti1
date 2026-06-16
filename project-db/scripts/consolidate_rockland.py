"""One-off: consolidate the three Rockland rows into one property project.

Decision (owner, 2026-06-10): 923 and 927 Rockland are two units of the SAME
building -> ONE canonical Project, ONE grouped financial picture.  Per-unit
distinctions live at the task level, not by splitting the Project (splitting
would fragment the money picture -- the exact failure we're avoiding).

State going in -- three rows:
  * "923-927 Rockland"            (team-drive container folder; 31 docs; the
                                    correct go-forward Drive pointer)
  * "923 Rockland (3rd Floor unit)" (Monday board + 164 tasks + 21 FRs; 3 docs)
  * "927 Rockland (Ground Floor unit)" (18 docs + 4 FRs)

Survivor = the 923 row (keeps Monday + tasks + FRs in place -- least re-pointing).
We rename it to "923-927 Rockland", fold the other two rows' docs/financials/
obligations into it, move the TEAM-DRIVE container folder pointer onto it (so
future syncs resolve the container -> this one project), drop the two stale
personal-Drive folder pointers, and delete the two empty rows.

No documents are trashed -- every unit's files are kept as the property's files.

Usage:
    py -3.13 scripts/consolidate_rockland.py            # dry-run
    py -3.13 scripts/consolidate_rockland.py --apply
"""

from __future__ import annotations

import sys

SURVIVOR_PREFIX = "94d15ea8"  # 923 row (Monday + 164 tasks + 21 FRs)
CONTAINER_PREFIX = "c67c87cb"  # team-drive container (folder 1ZAGf...)
UNIT927_PREFIX = "b3a2e796"  # 927 personal row
NEW_NAME = "923-927 Rockland"
TEAM_FOLDER_KEY_PREFIX = "folder:1ZAGf"  # the go-forward Drive pointer to keep


def main(apply: bool) -> int:
    try:
        from project_db.cli import force_utf8_output

        force_utf8_output()
    except Exception:
        pass

    from project_db.db import get_engine, session_scope
    from project_db.db.base import Base
    from project_db.db.models import (
        ContractObligation,
        Document,
        DocumentChunk,
        ExternalId,
        FinancialRecord,
        Project,
        SourceSystem,
        Task,
    )

    engine = get_engine()
    Base.metadata.create_all(engine)
    mode = "APPLY" if apply else "DRY-RUN"
    print(f"=== Rockland consolidation ({mode}) ===\n")

    with session_scope() as s:
        projs = s.query(Project).all()

        def find(pfx):
            return next((p for p in projs if str(p.canonical_id).startswith(pfx)), None)

        survivor = find(SURVIVOR_PREFIX)
        losers = [p for p in (find(CONTAINER_PREFIX), find(UNIT927_PREFIX)) if p]

        if survivor is None:
            # Idempotent: maybe already consolidated.
            survivor = next((p for p in projs if p.name == NEW_NAME), None)
            if survivor and not losers:
                print(
                    "Already consolidated -- one Rockland project named "
                    f"{NEW_NAME!r}. Nothing to do."
                )
                return 0
            print("ERROR: survivor 923 row not found and not already merged.")
            return 1

        sid = survivor.canonical_id
        print(f"Survivor: {survivor.name!r} [{str(sid)[:8]}] -> rename to {NEW_NAME!r}")

        moved = {"docs": 0, "frs": 0, "obs": 0, "tasks": 0, "chunks": 0, "dailylogs": 0}
        for loser in losers:
            lid = loser.canonical_id
            d = s.query(Document).filter_by(project_id=lid).count()
            fr = s.query(FinancialRecord).filter_by(project_id=lid).count()
            ob = s.query(ContractObligation).filter_by(project_id=lid).count()
            tk = s.query(Task).filter_by(project_id=lid).count()
            drive_exts = [
                e.external_key for e in s.query(ExternalId).filter_by(canonical_id=lid).all()
            ]
            print(f"\nLoser: {loser.name!r} [{str(lid)[:8]}]")
            print(f"    move docs={d} FRs={fr} obligations={ob} tasks={tk}")
            print(f"    externalids: {drive_exts}")

            if apply:
                for cls, key in (
                    (Document, "docs"),
                    (FinancialRecord, "frs"),
                    (ContractObligation, "obs"),
                    (Task, "tasks"),
                    (DocumentChunk, "chunks"),
                ):
                    for r in s.query(cls).filter_by(project_id=lid).all():
                        r.project_id = sid
                        moved[key] += 1
                # DailyLog if present
                try:
                    from project_db.db.models import DailyLog

                    for r in s.query(DailyLog).filter_by(project_id=lid).all():
                        r.project_id = sid
                        moved["dailylogs"] += 1
                except Exception:
                    pass
                # ExternalIds: keep the team container folder pointer (move to
                # survivor); drop stale personal-Drive folder pointers.
                for e in s.query(ExternalId).filter_by(canonical_id=lid).all():
                    if (
                        e.source == SourceSystem.GOOGLE_DRIVE
                        and e.entity_type == "Project"
                        and e.external_key.startswith(TEAM_FOLDER_KEY_PREFIX)
                    ):
                        e.canonical_id = sid  # keep -> go-forward pointer
                    else:
                        s.delete(e)  # stale folder pointer
                s.flush()
                s.delete(loser)
                s.flush()

        if apply:
            survivor.name = NEW_NAME
            # Drop the survivor's OWN stale personal-Drive folder pointer
            # (its old 923-only folder); keep Monday + the team container.
            for e in (
                s.query(ExternalId)
                .filter_by(
                    canonical_id=sid, source=SourceSystem.GOOGLE_DRIVE, entity_type="Project"
                )
                .all()
            ):
                if not e.external_key.startswith(TEAM_FOLDER_KEY_PREFIX):
                    s.delete(e)
            s.flush()

        print("\n" + "-" * 50)
        if apply:
            print(f"APPLIED. One project {NEW_NAME!r} [{str(sid)[:8]}].")
            print(f"  moved: {moved}")
            # Final state
            d = s.query(Document).filter_by(project_id=sid, is_trashed=False).count()
            fr = s.query(FinancialRecord).filter_by(project_id=sid).count()
            tk = s.query(Task).filter_by(project_id=sid).count()
            exts = [
                f"{e.source.value}:{e.external_key[:24]}"
                for e in s.query(ExternalId).filter_by(canonical_id=sid).all()
            ]
            print(f"  final: docs={d} FRs={fr} tasks={tk}")
            print(f"  externalids: {exts}")
            remaining = [p.name for p in s.query(Project).all() if "rockland" in p.name.lower()]
            print(f"  rockland rows now: {remaining}")
        else:
            print("DRY-RUN -- no changes written. Re-run with --apply.")
            s.rollback()
    return 0


if __name__ == "__main__":
    sys.exit(main(apply="--apply" in sys.argv[1:]))
