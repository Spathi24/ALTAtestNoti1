"""project_db doctor -- read-only invariant sweep over the real SQLite DB.

Run from project-db/:  python scripts/doctor.py [path/to/project_db.sqlite]

Design constraints (deliberate):
- READ-ONLY. Never mutates. Reports FAIL/WARN/INFO and exits nonzero on FAIL.
- No project imports -- raw sqlite3 + PRAGMA introspection, so it keeps working
  across model refactors and can run before the venv is even healthy. (This is
  why it cannot call cli.force_utf8_output(); output is kept pure-ASCII per
  CLAUDE.md rule 5 so the Windows console never garbles it.)
- Generic where possible: FK-orphan detection walks PRAGMA foreign_key_list on
  every table instead of hardcoding relationships.

Standing invariants covered (see PROJECT_STATE.md / HANDOFF.md):
- No orphaned derived rows (post foreign-purge cleanliness, 2026-06-26).
- No cost-side FinancialLineItem with NULL cost_status silently in play
  (legacy llm-v1 rows must be allow-list filtered, not summed).
- DONE tasks without completed_at (report-visible gap, fixed 2026-06-22 --
  count should only shrink).
- No duplicate ExternalId (source, entity_type, external_key).
- Foreign-doc containment approximation: documents whose top folder segment
  does not match the team-root folder convention (real check = Drive ancestry;
  this is a smoke). Default convention is the company's "NN. NAME" numbered
  root folders (01. PROJECTS, 05. INTELLIGENCE, ...); override with
  ALTA_TEAM_ROOT_REGEX. folder_path is stored RELATIVE to the team root, so a
  fixed root NAME never appears in it -- matching the numbered top segment is
  the correct signal, not a substring search for the root's name.
"""

from __future__ import annotations

import os
import re
import sqlite3
import sys

DEFAULT_DB = os.environ.get("PROJECT_DB_SQLITE", "project_db.sqlite")
# Team-root folder convention. All legitimately-synced docs live under a
# top-level "NN. NAME" numbered Drive folder; a foreign doc would not.
TEAM_ROOT_REGEX = os.environ.get("ALTA_TEAM_ROOT_REGEX", r"^\d{2}\. ")

fails: list[str] = []
warns: list[str] = []
infos: list[str] = []


def q1(con: sqlite3.Connection, sql: str, args: tuple = ()) -> int:
    try:
        row = con.execute(sql, args).fetchone()
        return int(row[0]) if row and row[0] is not None else 0
    except sqlite3.Error:
        return -1  # table/column missing -- caller decides


def tables(con: sqlite3.Connection) -> list[str]:
    return [
        r[0]
        for r in con.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
        )
    ]


def columns(con: sqlite3.Connection, table: str) -> set[str]:
    return {r[1] for r in con.execute(f"PRAGMA table_info('{table}')")}


def check_fk_orphans(con: sqlite3.Connection) -> None:
    for t in tables(con):
        for fk in con.execute(f"PRAGMA foreign_key_list('{t}')"):
            # fk: (id, seq, ref_table, from_col, to_col, on_update, on_delete, match)
            ref, col, to_col = fk[2], fk[3], fk[4] or "rowid"
            n = q1(
                con,
                f"SELECT COUNT(*) FROM '{t}' c WHERE c.'{col}' IS NOT NULL "
                f"AND NOT EXISTS (SELECT 1 FROM '{ref}' p WHERE p.'{to_col}' = c.'{col}')",
            )
            if n > 0:
                fails.append(f"{t}.{col}: {n} orphan row(s) -> missing {ref}.{to_col}")


def check_financial(con: sqlite3.Connection) -> None:
    for t in tables(con):
        cols = columns(con, t)
        if {"side", "cost_status"} <= cols:
            n = q1(
                con,
                f"SELECT COUNT(*) FROM '{t}' WHERE side='cost' AND cost_status IS NULL",
            )
            if n > 0:
                warns.append(
                    f"{t}: {n} cost-side row(s) with NULL cost_status "
                    "(legacy llm-v1) -- aggregates must ALLOW-LIST cost_status, "
                    "never sum these implicitly."
                )


def check_tasks(con: sqlite3.Connection) -> None:
    for t in tables(con):
        cols = columns(con, t)
        if {"status", "completed_at"} <= cols and "title" in cols:
            n = q1(
                con,
                f"SELECT COUNT(*) FROM '{t}' WHERE UPPER(status) LIKE '%DONE%' "
                "AND completed_at IS NULL",
            )
            if n > 0:
                infos.append(
                    f"{t}: {n} DONE task(s) undated (no Monday end_date; "
                    "honest-null -- should only shrink over time)."
                )


def check_external_ids(con: sqlite3.Connection) -> None:
    if "external_id" not in tables(con):
        return
    n = q1(
        con,
        "SELECT COUNT(*) FROM (SELECT source, entity_type, external_key, COUNT(*) c "
        "FROM external_id GROUP BY 1,2,3 HAVING c > 1)",
    )
    if n > 0:
        fails.append(f"external_id: {n} duplicate (source, entity_type, key) group(s).")


def _top_segment(path: str) -> str:
    return re.split(r"[\\/]", path.strip(), maxsplit=1)[0]


def check_containment(con: sqlite3.Connection) -> None:
    pat = re.compile(TEAM_ROOT_REGEX)
    for t in tables(con):
        cols = columns(con, t)
        if not ({"folder_path", "drive_id"} <= cols):
            continue
        trash = "AND COALESCE(is_trashed,0)=0" if "is_trashed" in cols else ""
        try:
            rows = con.execute(
                f"SELECT folder_path FROM '{t}' WHERE folder_path IS NOT NULL {trash}"
            ).fetchall()
        except sqlite3.Error:
            continue
        total = len(rows)
        if total == 0:
            continue
        outside = [r[0] for r in rows if not pat.match(_top_segment(r[0]))]
        n = len(outside)
        if n == 0:
            continue
        if n >= max(1, int(total * 0.9)):
            # Almost everything failed -- the regex is misconfigured for this
            # corpus, NOT a real leak. Say so instead of flagging every doc.
            infos.append(
                f"{t}: team-root regex {TEAM_ROOT_REGEX!r} matched only "
                f"{total - n}/{total} doc(s) -- likely misconfigured for this "
                "corpus, not a containment leak. Set ALTA_TEAM_ROOT_REGEX to the "
                "team's top folder convention."
            )
        else:
            sample = ", ".join(sorted({_top_segment(p) for p in outside})[:5])
            warns.append(
                f"{t}: {n}/{total} doc(s) whose top folder does not match the "
                f"team-root convention {TEAM_ROOT_REGEX!r} (e.g. {sample}) -- "
                "smoke only; confirm with a Drive ancestry spot-check (delta-sync "
                "containment, PROJECT_STATE 2026-06-26)."
            )


def main() -> int:
    db = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_DB
    if not os.path.exists(db):
        print(f"doctor: DB not found at {db} (pass a path or set PROJECT_DB_SQLITE)")
        return 1
    con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    try:
        for check in (
            check_fk_orphans,
            check_financial,
            check_tasks,
            check_external_ids,
            check_containment,
        ):
            check(con)
    finally:
        con.close()

    for m in fails:
        print(f"FAIL: {m}")
    for m in warns:
        print(f"WARN: {m}")
    for m in infos:
        print(f"INFO: {m}")
    if not (fails or warns or infos):
        print("OK: all invariant checks clean.")
    else:
        print(f"-> {len(fails)} fail / {len(warns)} warn / {len(infos)} info")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
