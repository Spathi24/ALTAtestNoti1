"""Clean-slate reset: rebuild Drive data from the team Drive as if it were the
source from the start.

Owner directive (2026-06-10): the personal-Drive-first start was a mistake.
Wipe ALL documents and ALL derived intelligence (financials, obligations,
embeddings, extracted text) so NOTHING from the personal Drive -- and nothing
stale (files deleted between the two versions) -- remains.  Do NOT merge the
two ("no frankensteining"); rebuild from the team Drive from scratch.

What this script DOES (the destructive DB part only):
  - DELETE all document_chunk (embeddings)
  - DELETE all financial_record
  - DELETE all contract_obligation
  - DELETE all document_financial_status (human confirm/quote toggles -- they
    were made on personal-Drive docs being wiped)
  - DELETE all document_text
  - DELETE all ExternalId rows of entity_type 'Document' (the Drive file-id
    mappings)
  - DELETE the Drive changes cursor (entity_type 'SyncState') so the next
    `sync GOOGLE_DRIVE` is a FULL crawl
  - DELETE all document rows

What it PRESERVES (not personal-Drive data; re-derivable / Monday-owned):
  - project / task / client / vendor / lead / deal / user rows
  - Monday ExternalIds and the team-Drive PROJECT folder pointers
    (so the re-crawl re-creates docs under the existing projects)

After this script:  full Drive re-crawl -> empty-project cleanup ->
extract-content -> embed -> extract-financials/obligations (separate steps).

Usage:
    py -3.13 scripts/reset_from_team_drive.py          # dry-run
    py -3.13 scripts/reset_from_team_drive.py --apply
"""

from __future__ import annotations

import sys


def main(apply: bool) -> int:
    try:
        from project_db.cli import force_utf8_output

        force_utf8_output()
    except Exception:
        pass

    from sqlalchemy import inspect as sa_inspect
    from sqlalchemy import text

    from project_db.db import get_engine
    from project_db.db.base import Base

    engine = get_engine()
    Base.metadata.create_all(engine)
    existing = set(sa_inspect(engine).get_table_names())

    mode = "APPLY" if apply else "DRY-RUN"
    print(f"=== Clean-slate Drive reset ({mode}) ===\n")

    # (table, where-clause or None for whole table)
    deletes = [
        ("document_chunk", None),
        ("financial_record", None),
        ("contract_obligation", None),
        ("document_financial_status", None),
        ("document_text", None),
        ("external_id", "entity_type = 'Document'"),
        ("external_id", "entity_type = 'SyncState' AND external_key = 'gdrive_changes_page_token'"),
        ("document", None),
    ]

    with engine.begin() as conn:
        is_sqlite = engine.dialect.name == "sqlite"
        # Report counts first.
        for table, where in deletes:
            if table not in existing:
                print(f"  (skip {table}: table not present)")
                continue
            q = f'SELECT COUNT(*) FROM "{table}"'
            if where:
                q += f" WHERE {where}"
            n = conn.execute(text(q)).scalar()
            label = table + (f"  [{where}]" if where else "")
            print(f"  DELETE {n:>6}  from {label}")

        if not apply:
            print("\nDRY-RUN -- no rows deleted. Re-run with --apply.")
            return 0

        print("\nApplying...")
        if is_sqlite:
            conn.execute(text("PRAGMA foreign_keys=OFF"))
        for table, where in deletes:
            if table not in existing:
                continue
            stmt = f'DELETE FROM "{table}"'
            if where:
                stmt += f" WHERE {where}"
            conn.execute(text(stmt))
        if is_sqlite:
            conn.execute(text("PRAGMA foreign_keys=ON"))

    print(
        "Wipe complete. Documents and all derived data cleared; Drive cursor "
        "reset.\nNext: project_db sync GOOGLE_DRIVE  (full team-Drive crawl)."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main(apply="--apply" in sys.argv[1:]))
