"""Run structured financial + obligation extraction over EVERY project.

Used after the clean-slate team-Drive reset: once documents are re-crawled and
text-extracted, this fills FinancialRecord + ContractObligation for the whole
portfolio in one pass (the CLI does one project at a time).

Both extractors are replace-per-project and all-or-nothing, so this is safely
resumable -- re-running re-does each project from its current docs.  Uses the
OpenAI structured-outputs extractors (Anthropic credits are $0; the provider
fallback is OpenAI).

Usage:
    py -3.13 scripts/extract_all_team.py                 # all projects
    py -3.13 scripts/extract_all_team.py --financials    # only financials
    py -3.13 scripts/extract_all_team.py --obligations   # only obligations
"""

from __future__ import annotations

import sys


def main(argv: list[str]) -> int:
    try:
        from project_db.cli import force_utf8_output

        force_utf8_output()
    except Exception:
        pass

    do_fin = "--obligations" not in argv
    do_obl = "--financials" not in argv

    from project_db.ai.doc_extraction import (
        OpenAIStructuredExtractor,
        StructuredExtractorError,
        extract_financials_structured_for_project,
    )
    from project_db.ai.obligation_extraction import (
        ObligationExtractorError,
        OpenAIObligationExtractor,
        extract_obligations_structured_for_project,
    )
    from project_db.db import get_engine, session_scope
    from project_db.db.base import Base
    from project_db.db.models import Project

    engine = get_engine()
    Base.metadata.create_all(engine)

    try:
        fin_ex = OpenAIStructuredExtractor() if do_fin else None
        obl_ex = OpenAIObligationExtractor() if do_obl else None
    except (StructuredExtractorError, ObligationExtractorError) as exc:
        print(f"FAIL: cannot build extractor -- {exc}", file=sys.stderr)
        return 2

    with session_scope() as s:
        projects = [(p.canonical_id, p.name) for p in s.query(Project).order_by(Project.name).all()]

    print(
        f"=== Portfolio extraction over {len(projects)} projects "
        f"(financials={do_fin} obligations={do_obl}) ===\n"
    )

    tot = {"fin_records": 0, "obligations": 0, "fin_fail": 0, "obl_fail": 0, "projects_done": 0}
    for i, (pid, name) in enumerate(projects, 1):
        line = f"[{i:>2}/{len(projects)}] {name[:42]:<42} "
        # Each project in its own transaction so one failure can't roll back
        # the whole run.
        if do_fin:
            try:
                with session_scope() as s:
                    b = extract_financials_structured_for_project(s, fin_ex, pid)
                n = len(b.records)
                tot["fin_records"] += n
                line += f"fin={n:>3}"
                if b.skipped_reason and not b.records:
                    line += f"({b.skipped_reason[:24]})"
            except Exception as exc:
                tot["fin_fail"] += 1
                line += f"fin=ERR({str(exc)[:40]})"
        if do_obl:
            try:
                with session_scope() as s:
                    b = extract_obligations_structured_for_project(s, obl_ex, pid)
                n = len(b.obligations)
                tot["obligations"] += n
                line += f"  obl={n:>3}"
            except Exception as exc:
                tot["obl_fail"] += 1
                line += f"  obl=ERR({str(exc)[:40]})"
        tot["projects_done"] += 1
        print(line, flush=True)

    print("\n=== DONE ===")
    print(f"  financial records written: {tot['fin_records']}")
    print(f"  obligations written      : {tot['obligations']}")
    print(f"  financial failures       : {tot['fin_fail']}")
    print(f"  obligation failures      : {tot['obl_fail']}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
