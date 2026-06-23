# HANDOFF — current engineering state

**This file is wiped and retyped at every handoff.** It holds ONLY what is true
*right now*. History → `../CHANGELOG.md`. Rules & philosophy → `../../CLAUDE.md`
(read it first; it overrides everything).

Last retyped: 2026-06-22.

---

## Where things stand (the honest summary)

The project is in a **deliberate build-freeze + documentation reset** (see
CLAUDE.md). The chosen first build (it passes the time-saved gate: the bosses
review cross-project change weekly to make decisions) is the **weekly
per-project report**. Build #1 (the deterministic delta) is done; the narration
layer is next.

**Git:** on `main`, pushed to `origin/main`. The full, fully-exposed pre-reset
build is frozen on the **`full-exposed-build`** branch as the fallback. The doc
reset, the feature-flag quarantine, and weekly-report build #1 are committed.

**Tests:** see the top of CHANGELOG (1394 passing as last recorded).

**Active build — weekly report:** Both layers complete and tested.

`report_weekly_changes` (`ai/views.py`) — content-complete deterministic delta:
- Documents: `DocumentText.extracted_text` included (3 000-char cap per doc)
- Field notes: full `raw_text` (was truncated to 200 chars)
- Proposals: `proposed_value` parsed from JSON (the actual suggested value)
- Tasks: all schedule fields (start/end/due, group, subcontractor)
- `events`: all items merged into one chronological list per project
- `prior_window`: counts from the previous N days for trajectory context
- Window start is floored to MIDNIGHT (day-granular). Earlier it used a
  minute-precise boundary, so ~N-day-old field notes flickered in/out by the
  clock time of the run — the report's best content. Confirmed + fixed.

`narrate_weekly_report` (`ai/views.py`) — LLM narration using the events list:
- Passes the chronological `events` list (not separate lists) to the provider
- Includes `prior_week` counts for trajectory narrative
- 2 000-token budget (was 300 -- that was a metadata stub, not a report)
- Zero-change projects get hard-coded text, no LLM call

CLI: `weekly-changes [project] [--days N] [--narrate] [--sync]`
- `--narrate`: calls fast provider (OpenAI currently, Anthropic when credits available)
- `--sync`: runs Drive + Monday sync + auto content-extraction, then narrates
- Connector/resolver/httpx INFO logging is muted for this command (clean output)
- Proposal events are collapsed to one summary line in the printed view
  (e.g. "[proposals] 10 opened, 10 accepted, 17 rejected") — the full proposals
  still go to the LLM; only the boss-facing print is summarized

**Task completion dates (fixed 2026-06-22):** Monday tracks status but never
records WHEN a task became DONE — the live DB had 34 DONE tasks, 0 dated, so the
report's "tasks completed this week" was permanently empty (the real cause of
"nothing done last week", NOT the Drive timestamps, which are correct). The
Monday connector (`_upsert_task`) now derives `completed_at`: today on a real
transition into DONE (first-observed-complete), backfilled from `end_date` for
tasks already DONE with a scheduled finish, cleared if reopened. After one live
sync, 8/34 are dated (the rest have no Monday end_date → stay null, honestly
undated until they next transition).

**Telegram general intake — BUILT 2026-06-23 (owner-directed).** Anyone can now
text the bot and the message is captured, attributed to a project, and surfaced
in the weekly report — beyond the original labour-only, invite-gated design.
- Why: the bosses ARE the GDrive/Monday admins, so that data is low-marginal-
  value. Field comms are the untapped signal.
- Architecture (no new tables): every message is still recorded as exactly one
  `LabourSourceEvent` (real send time, sender id, raw text). Two paths fork off
  that one row — (A) LABOUR (unchanged, specialized): a bound worker + the
  OpenAI extractor → LabourClaims; (B) GENERAL (new): any sender, kept as
  `ingestion_status='received'`, reason `general_content`, with a deterministic
  project attribution into `project_id_hint`.
- Project attribution (`_attribute_project`, telegram_intake.py, NO LLM):
  text-match on a site name → bound worker's default project → recency-weighted
  vote over the sender's last 14d (7d half-life, ≥60% dominance) → else
  unresolved (project-less "Site communications" section). Constants are
  module-level (`_ATTRIB_HALF_LIFE_DAYS/_WINDOW_DAYS/_DOMINANCE`).
- Report: `report_weekly_changes` reads telegram `LabourSourceEvent` rows
  (status in {received, extracted}) as a 5th "communications" event source,
  timestamped by `source_created_at` (fallback `received_at`); project-less rows
  go to a top-level `site_communications` key. Quarantined/ignored excluded.
- Anonymous senders: keyed on the stable telegram user id; shown as a verified
  Worker name if bound, else `sender <id>` + an unverified `@username` hint.
  Person-names *in* a message are free-text only — never resolved to Workers.
- Feature gating (split, both default-off): `telegram_general_intake` enables
  open intake; `telegram_intake` enables the labour path. `poll-telegram` runs
  if EITHER is on; the OpenAI labour extractor is OPTIONAL (no key → general
  runs LLM-free). Gating is at the CLI edge; `poll_telegram(..., general_intake=)`
  takes it as an explicit input (logic stays flag-free + testable).
- Restore live: `PROJECT_DB_FEATURE_TELEGRAM_GENERAL_INTAKE=true` (+ optionally
  `..._TELEGRAM_INTAKE=true` for labour). Live bot: @ALTA_employeebot.
- Deferred (NOT built): per-message LLM classifier (content_type/summary/
  mentions) — the report's narration already summarizes raw text; media
  (photo/voice) bytes; rate-limiting for abuse.

Other known gaps (NOT yet built):
- No money in the report (owner's stated #1: Home Depot + labour overrun). The
  financial layer isn't portfolio-reliable enough to feed numbers in.
- Proposals appear in the timeline by AI-run time (created_at clusters on ~6
  generation days), not the real-world event date — chronology is approximate
  for proposals (docs/notes/task-completions are real).

Documented limits: financial rows excluded (ledger rebuilt on each fill-ledger
run → `created_at` is noisy); "newly filed but Drive-old" docs not caught
(only `modified_at_source` used, which is wipe-proof); prior-window counts for
proposals are approximate (polymorphic attribution at prior-window time).

---

## What's visible vs hidden right now

A feature-flag layer (`src/project_db/features.py`) decides what's reachable. It
is purely presentational — no schema, parser, or stored data was changed. Flip
any flag with `PROJECT_DB_FEATURE_<NAME>=true`.

- **Visible spine (default on):** core, `ask`, `search`, `proposals`, typed field
  notes, finance margins (`FinancialLineItem`), ledger health.
- **Hidden (default off, fully built, reversible):** email/photo field notes,
  legacy financials (`FinancialRecord`), obligations / money-at-risk,
  value-caught, project-logs, labour intake, Telegram intake, Monday Gantt,
  roadmap, LLM PDF finance, lead-gen, admin nav, batch proposal generation,
  manual task-date edit.

---

## Subsystem reality (present tense, no spin)

- **Financial / margins:** `FinancialLineItem` (division-keyed, per-unit) is the
  current ledger; a deterministic grid parser reconciles Rockland-style quote
  spreadsheets to the penny. **It is NOT portfolio-useful yet** — most other
  projects' money lives in PDFs / simple-estimate / job-cost sheets the grid
  parser doesn't read, and the **cost side is essentially absent**, so margins
  show `revenue_only`. Legacy `FinancialRecord` remains as a transition net.
- **Home Depot Pro purchases (variable-cost leak #1):** import spine BUILT +
  validated on the real export — 190 transactions ($58,997.52 net), tax
  re-derived, line-item sum reconciled to the header. After a by-hand audit +
  digit-fragment matcher fix (job `"0"` was wrongly matching street number
  `"3940"`), attribution is **105/190 linked**: St-Laurent $27,437 is the only
  well-covered project (Rockland $2,088, St-Mathieu $1,555); **$27,917 / 47% is
  UNRESOLVED** because no usable job was typed at the till — `"0"` ($13.7k) and
  online `BODFS/ONLINE ORDER` ($16k). Cote-des-Neiges has NO real HD spend (its
  old $13.7k was the bug). Per-project HD costing is capped by till discipline.
  Two known data issues left to owner judgement: HD's detail export leaves
  `Product Name` blank (we keep SKU+qty+price, not descriptions); and suspected
  duplicate in-store/online transaction pairs (~$4.7k, same amount+date) are NOT
  auto-deduped. Line items backfilled manually (19/190 so far).
  CLI: `homedepot import|status|report|queue|relink`. Visible behind `homedepot`.
- **Labour intake (Telegram/Gmail):** built and technically live, but **blocked
  on adoption** — nobody is reliably logging labour, so there is nothing to
  reconcile. Hidden.
- **Providers / budget:** LLM calls route through a fallback provider (Anthropic
  primary, OpenAI backup). **Confirm current credit balances with the owner
  before any live LLM run** — last recorded as very low. Develop on mocks.
- **Tier-1 reports + RAG + attention briefing:** built and working; the passive
  read/reconcile story.

---

## Parked / open questions (NOT a roadmap — do not build without the gate)

- **The usage-gate sentence** — owner is whiteboarding it. This unblocks
  everything. Settle it first.
- **Which product to be:** *passive truth layer* (reads docs that already exist —
  validatable by the owner alone, no adoption bet) vs *active operations layer*
  (labour, field-note → Monday — depends on other people changing habits).
  Current lean: passive first.
- **Financial re-architecture idea** (owner + ChatGPT; reference preserved in
  `archive/FINANCIAL_REDESIGN.md`): AI *classifies* documents/sheets first
  (structured output), deterministic code *validates & writes* second; emit a
  per-document audit ("what is this, can it be counted, why") BEFORE any
  margin/money-at-risk view. **Do not start building until the gate is set and
  this is the chosen lane.**
- **Home Depot line items are backfilled MANUALLY (bot abandoned).** ~189
  transactions still have header-only data; the per-receipt detail export is
  ~5 clicks each. A logged-in Playwright bot to automate that was prototyped and
  **dropped** — Home Depot's Akamai bot-protection reset/stalled the automated
  browser at page load, and the owner won't risk the company Pro account on a
  scraper (he flagged that risk up front; it was the correct call). The workflow
  is: `homedepot queue` ranks which receipts are worth exporting (top ~50 ≈ 80%
  of spend) → export those by hand → `homedepot import <folder>`. Do NOT revive a
  browser bot without an explicit owner decision. Hourly labour remains the other
  unvalidated watch target.

---

## If you are a fresh Claude instance

1. Read `../../CLAUDE.md`. Honor the build freeze.
2. Read the top CHANGELOG entry for "what works today."
3. Do not resurrect anything in `archive/` as instructions.
4. Before building anything, answer: *whose time does this save, and how will we
   know?* If you can't, stop and ask.
