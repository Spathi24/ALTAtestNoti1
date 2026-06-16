"""One-off migration: consolidate the personal-Drive -> team-Drive switch.

Background
----------
The Drive root folder was switched from the owner's personal Drive to the
company team (shared) Drive.  A full crawl ingested ~1000 new Documents, but
because project identity keys on the Drive *folder id* (ExternalId
``folder:<id>``) and the team Drive has different folder ids, the crawl created
DUPLICATE Project rows (one per real project) instead of matching the existing
ones by name.  It also left the old personal-Drive Documents marked active, so
the overlapping projects double-count.

This script consolidates each duplicate-named project pair onto the OLD row
(the survivor -- it carries Monday links, canonical fields, and all derived
FinancialRecord / ContractObligation / DocumentText / embeddings), re-points the
new team-Drive Documents onto it, swaps its Drive-folder pointer to the new
folder so future syncs match, deletes the now-empty new row, and soft-trashes
the old personal-Drive Documents.

It is STRUCTURAL ONLY and spends no API credits.  Re-extraction
(extract-content -> embed -> extract-financials -> extract-obligations) is a
separate, credit-spending step run afterwards; both extractors are
replace-per-project AND skip trashed docs, so re-extraction cleanly supersedes
the stale personal-Drive numbers with no double-count.

Personal-Drive-only projects (no team-Drive twin) are left fully intact.

Usage
-----
    py -3.13 scripts/migrate_to_team_drive.py            # dry-run (default)
    py -3.13 scripts/migrate_to_team_drive.py --apply    # mutate the DB

Idempotent: after a successful --apply there are no 2-row duplicates left, so a
re-run is a no-op.
"""

from __future__ import annotations

import sys
from collections import defaultdict
from datetime import datetime

# Boundary between OLD personal-Drive docs and NEW team-Drive docs.
# Verified gap in the live DB: newest OLD doc 2026-06-10 15:10 UTC,
# oldest NEW doc 2026-06-10 17:16 UTC.  16:30 sits cleanly between them.
CUTOFF = datetime(2026, 6, 10, 16, 30, 0)


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
        ExternalId,
        FinancialRecord,
        Project,
        SourceSystem,
    )

    engine = get_engine()
    Base.metadata.create_all(engine)

    mode = "APPLY" if apply else "DRY-RUN"
    print(f"=== Team-Drive consolidation ({mode}) ===\n")

    with session_scope() as s:
        by_name: dict[str, list] = defaultdict(list)
        for p in s.query(Project).all():
            by_name[p.name].append(p)
        dupes = {n: ps for n, ps in by_name.items() if len(ps) == 2}

        if not dupes:
            print("No 2-row duplicate projects found -- project merge already done. Nothing to do.")
            return 0

        def n_new(pid) -> int:
            return (
                s.query(Document)
                .filter(Document.project_id == pid, Document.created_at >= CUTOFF)
                .count()
            )

        def n_old(pid) -> int:
            return (
                s.query(Document)
                .filter(Document.project_id == pid, Document.created_at < CUTOFF)
                .count()
            )

        total_docs_moved = 0
        total_docs_trashed = 0
        total_rows_deleted = 0
        skipped: list[str] = []

        for name, (a, b) in sorted(dupes.items()):
            # Survivor = the row with the OLD docs; loser = the NEW team-Drive row.
            a_new, b_new = n_new(a.canonical_id), n_new(b.canonical_id)
            if a_new > b_new:
                loser, survivor = a, b
            elif b_new > a_new:
                loser, survivor = b, a
            else:
                skipped.append(f"{name} (ambiguous: equal new-doc counts)")
                continue

            # Sanity: survivor must hold the old docs, loser the new docs.
            if n_old(survivor.canonical_id) == 0 or n_new(loser.canonical_id) == 0:
                skipped.append(f"{name} (sanity: survivor has no old / loser no new)")
                continue

            has_monday = bool(
                s.query(ExternalId)
                .filter_by(canonical_id=survivor.canonical_id, source=SourceSystem.MONDAY)
                .first()
            )

            loser_docs = s.query(Document).filter(Document.project_id == loser.canonical_id).all()
            survivor_old_docs = (
                s.query(Document)
                .filter(
                    Document.project_id == survivor.canonical_id,
                    Document.created_at < CUTOFF,
                    Document.is_trashed.is_(False),
                )
                .all()
            )

            print(f"- {name}{'  [MONDAY-linked]' if has_monday else ''}")
            print(
                f"    survivor {str(survivor.canonical_id)[:8]}  "
                f"(old docs: {n_old(survivor.canonical_id)}, "
                f"derived FRs: "
                f"{s.query(FinancialRecord).filter_by(project_id=survivor.canonical_id).count()}, "
                f"obligations: "
                f"{s.query(ContractObligation).filter_by(project_id=survivor.canonical_id).count()})"
            )
            print(
                f"    loser    {str(loser.canonical_id)[:8]}  "
                f"-> re-point {len(loser_docs)} team-Drive docs to survivor, "
                f"delete row"
            )
            print(f"    trash    {len(survivor_old_docs)} old personal-Drive docs on survivor")

            if apply:
                # 1. Move the team-Drive documents onto the survivor.
                for d in loser_docs:
                    d.project_id = survivor.canonical_id
                total_docs_moved += len(loser_docs)

                # 2. Defensive: re-point any derived rows that landed on the
                #    loser (should be none -- it was a fresh crawl row).
                for cls in (FinancialRecord, ContractObligation):
                    for r in s.query(cls).filter_by(project_id=loser.canonical_id).all():
                        r.project_id = survivor.canonical_id

                # 3. Swap the Drive-folder pointer: give the survivor the
                #    team-Drive folder ExternalId, drop its stale old-folder one.
                loser_drive_ext = (
                    s.query(ExternalId)
                    .filter_by(
                        canonical_id=loser.canonical_id,
                        source=SourceSystem.GOOGLE_DRIVE,
                        entity_type="Project",
                    )
                    .all()
                )
                old_drive_ext = (
                    s.query(ExternalId)
                    .filter_by(
                        canonical_id=survivor.canonical_id,
                        source=SourceSystem.GOOGLE_DRIVE,
                        entity_type="Project",
                    )
                    .all()
                )
                for e in old_drive_ext:
                    s.delete(e)
                for e in loser_drive_ext:
                    e.canonical_id = survivor.canonical_id
                # Move any other stray loser ExternalIds (defensive).
                for e in s.query(ExternalId).filter_by(canonical_id=loser.canonical_id).all():
                    e.canonical_id = survivor.canonical_id

                s.flush()

                # 4. Soft-trash the old personal-Drive docs on the survivor.
                for d in survivor_old_docs:
                    d.is_trashed = True
                total_docs_trashed += len(survivor_old_docs)

                # 5. Delete the now-empty loser Project row.
                s.delete(loser)
                total_rows_deleted += 1
                s.flush()

        # NOTE -- a "Phase 2" that soft-trashed remaining personal-Drive docs on
        # team-present projects was prototyped here and DELIBERATELY NOT RUN.
        # Two findings killed it:
        #   1. The team Drive is NOT a complete superset of the personal Drive
        #      -- several projects' contracts (e.g. 923 Rockland's SOW / accepted
        #      quote) and working files exist only on the personal Drive.  A
        #      date/folder heuristic would soft-trash REAL documents the team
        #      Drive is missing.
        #   2. The genuinely-redundant case is the SAME file content appearing as
        #      two file objects (personal copy + team copy).  That is the
        #      cross-document near-duplicate problem (INTENTIONS Section 6,
        #      entity resolution), to be solved at the CONTENT level -- not by
        #      created_at.  Keeping both copies active is safe meanwhile: the
        #      money chokepoint collapses per-(document,direction) groups and the
        #      money-line already declines to present inflated all-in totals.
        # So this script does the project-level merge only.  Stale-doc cleanup
        # waits for the content-dedup work.

        print()
        if skipped:
            print("SKIPPED (need manual review):")
            for sk in skipped:
                print(f"  ! {sk}")
            print()

        print(f"Duplicate pairs handled    : {len(dupes) - len(skipped)}")
        print(f"Team-Drive docs moved      : {total_docs_moved}")
        print(f"Old docs soft-trashed      : {total_docs_trashed}")
        print(f"Empty project rows freed   : {total_rows_deleted}")

        if not apply:
            print("\nDRY-RUN -- no changes written. Re-run with --apply to migrate.")
            # Roll back any flush side-effects defensively.
            s.rollback()
        else:
            print("\nAPPLIED. Duplicate projects consolidated onto the team-Drive folders.")
            print("Next (when OpenAI credits are live):")
            print("  project_db extract-content")
            print("  project_db embed-documents")
            print("  project_db extract-financials --structured <project>")
            print("  project_db extract-obligations  --structured <project>")

    return 0


if __name__ == "__main__":
    sys.exit(main(apply="--apply" in sys.argv[1:]))
