---
name: alta-validate
description: Real-system validation ritual for ALTA / project_db. Use BEFORE declaring any change "done", "complete", or "validated" — a green pytest run is NOT validation in this repo. Triggers include finishing a slice, wiring a parser/extractor/connector change, touching financial numbers, sync/ingestion changes, or the user asking "is it done / does it work / validate it". Also use when writing the CHANGELOG entry for a change.
---

# ALTA Real-System Validation

Repo history: unit tests passed while the live DB had Rockland JOB COST at
$50.71 (real: $5,675.38), a digit-fragment matcher booked $13.7k to the wrong
project, and a mock-data check "verified" numbers circularly. Hence CLAUDE.md
hard rule 4: **validate on the real system, from the real repo path, against
the real workspace.** This skill is that rule made concrete.

## The universal three questions (answer in writing, every time)

1. **Provenance** — did the number/behavior you checked come from *real* data
   (live DB / real Drive doc / real Monday board), or from a fixture you or a
   prior session authored? If the latter, the check is circular: find a real
   sample.
2. **Reconciliation** — does an independent path agree? (line-item sum vs
   header total; DB aggregate vs the source sheet opened by hand; count in DB
   vs count in Drive/Monday.) "To the penny" is the standard for money.
3. **Downstream** — enumerate consumers of what you changed (reports, search,
   RAG, extractors, web routes) and smoke at least the nearest one.

## Per-subsystem smoke recipes

Run from `project-db/` against the real `project_db.sqlite`. All read-only.

**Parsers / evidence spine** (`parsing/`, `DocumentParse`, `EvidenceSpan`):
- Re-parse 1–2 REAL docs (a Rockland Google-Sheet estimate + one table-heavy
  PDF if in scope): `python scripts/parse_documents.py --project Rockland --limit 2 --overwrite`
- Check the detected header row is the true header (Rockland estimates: row 6,
  not the `,ESTIMATE,,,,` metadata row) and values stay bound to their columns.
- Confirm `DocumentText` compat behavior matches the slice's contract
  (`write_text` flag) — downstream reports read it.

**Financial extraction / ledger** (anything touching money):
- Pick one real doc with a known ground truth (923 Rockland ACCEPTED QUOTE /
  JOB COST). Verify: side (revenue vs cost) correct, `cost_status` set (watch
  the legacy `side='cost', cost_status NULL` rows — filter by allow-list, not
  exclusion), division code in the canonical format, line sum == header total.
- Certainty-requiring judgments (client-vs-vendor role, quote-vs-worksheet,
  side inversion) must run on the strong-model tier per the 2026-06-26
  decision — never gpt-4o-mini. Confirm which model actually ran.
- **Confirm LLM credit balance with the owner before any live LLM run.**

**Sync / connectors** (Drive, Monday, Telegram):
- After any delta-sync or impersonation-config change, re-verify containment:
  no ingested Document outside the team root (`PROJECT_STATE` privacy fix
  2026-06-26). `python scripts/doctor.py` includes an approximation; a Drive
  ancestry spot-check of 3 random new docs is the real check.
- Monday: verify against the live board with `inspect-board`, not memory —
  the API version has silently dropped arguments before.

**Reports / weekly changes**:
- `project_db weekly-changes <real project> --days 7` (no `--narrate` unless
  budget confirmed) and read the output as the boss would: are completed tasks
  dated, are field notes present, is the window boundary day-granular?

**Web UI**:
- `project_db serve --no-refresh`, hit the changed route against the live DB,
  and re-test the stale-guard path if the change touches accept/reject.

## Recording the result

The CHANGELOG entry must contain the live evidence, not adjectives: the real
doc/project used, the reconciled figures, and any honest gaps ("validated on
X; NOT yet validated on Y"). If validation was only synthetic, the entry must
say so explicitly — never imply live validation that didn't happen.
