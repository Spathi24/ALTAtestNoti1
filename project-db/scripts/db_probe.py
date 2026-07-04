"""db_probe -- the CANONICAL way to poke the real DB in a one-off. READ-ONLY.

Session history shows every fresh instance re-derives these imports by
traceback roulette (wrong guesses on record: ``project_db.db.engine``,
``SessionLocal``, ``get_session``, ``load_env``, ``Settings.database_url``,
``Project.id``, ``XlsxParser.parse(mime_type=...)``). This file is the crib:
run it for a quick DB snapshot, or copy its imports into your own probe.

Usage (from project-db/):  python scripts/db_probe.py [term]
  no arg -> row counts for the main tables + project list
  term   -> resolve it as a project (code / name / alias) and summarize it

THE CRIB (correct symbols, verified against src/):
  from project_db.db import session_scope, get_engine        # db/session.py
  from project_db.db.models import Project, Document, Task   # models/__init__.py
  # PKs are Project.canonical_id / Document.canonical_id -- there is NO .id
  # Project resolution by human ref: from project_db.ai.views import _resolve_project
  # Parsers: XlsxParser().parse(content, doc_name=..., mime=...) -> ParsedDocument
  #   spans: ParsedDocument.evidence_spans[i].content_json  (a dict, not str)
  # Env/config loads via ``import project_db.config`` side effect (selective .env)
"""

from __future__ import annotations

import sys

from project_db.cli import force_utf8_output
from project_db.db import session_scope
from project_db.db.models import (
    Document,
    FinancialLineItem,
    Project,
    Proposal,
    Task,
)

force_utf8_output()


def main() -> int:
    term = sys.argv[1] if len(sys.argv) > 1 else None
    with session_scope() as s:
        if term is None:
            for model in (Project, Document, Task, FinancialLineItem, Proposal):
                print(f"{model.__tablename__:22} {s.query(model).count():>6}")
            print("\nprojects:")
            for p in s.query(Project).order_by(Project.name).all():
                docs = s.query(Document).filter(Document.project_id == p.canonical_id).count()
                fli = (
                    s.query(FinancialLineItem)
                    .filter(FinancialLineItem.project_id == p.canonical_id)
                    .count()
                )
                print(f"  {p.name[:44]:44} docs={docs:<5} ledger_rows={fli}")
            return 0

        from project_db.ai.views import _resolve_project

        p = _resolve_project(s, term)
        if p is None:
            print(f"no project resolves from {term!r}")
            return 1
        print(f"project: {p.name}  (canonical_id={p.canonical_id})")
        docs = s.query(Document).filter(Document.project_id == p.canonical_id).count()
        tasks = s.query(Task).filter(Task.project_id == p.canonical_id).count()
        rows = (
            s.query(FinancialLineItem).filter(FinancialLineItem.project_id == p.canonical_id).all()
        )
        print(f"documents={docs}  tasks={tasks}  ledger_rows={len(rows)}")
        by_side: dict[str, int] = {}
        for r in rows:
            by_side[r.side or "?"] = by_side.get(r.side or "?", 0) + 1
        print(f"ledger by side: {by_side}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
