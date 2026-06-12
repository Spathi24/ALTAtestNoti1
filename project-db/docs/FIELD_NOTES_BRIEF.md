# Field-Note MVP — Implementation Brief for Claude Code

**Date:** 2026-06-12. **Author:** owner + Fable 5 planning session.
**Status:** decisions below are SETTLED. Do not re-litigate them; if one proves
technically impossible, stop and report back instead of improvising around it.

**Read first, in this order:** `docs/STRATEGY.md` (mission + Standing Rules
A1–A9 / N1–N6 — these are binding), `docs/HANDOFF.md` (engineering state +
footguns), `docs/INTENTIONS.md` §0 (the active-adaptation design this brief
implements). This brief is the requirements that §0 was waiting on.

---

## 1. What this is

The active-adaptation feature (INTENTIONS §0), scoped to an MVP after the
job-site visit. A field worker or PM reports in plain language what happened on
site ("finished the silicone in the bathroom, glass door still sticking, me and
Marco did 6 hours"). ALTA classifies it, matches it to that project's Monday
tasks, and emits **Proposals** (existing engine) that a human reviews and
accepts → Monday write-back. Advisor-not-actor throughout (A1).

**This is built INSIDE the existing ALTA repo** (`project-db/` package), not a
new repo. It reuses: `DailyLog` (storage), the classify-then-extract structured
pattern (`ai/doc_extraction.py` is the style reference), `assemble_project_context`,
the Proposal engine (`ai/proposals.py`), and the existing review UI. New code is
the input adapters + one extraction module + a roster table.

## 2. Settled decisions (from the planning session)

- **Pilot project: 923 Rockland.** Live job, beginner PM committed to reviewing
  proposals a few times per week. The pilot IS the one-PM adoption trial from
  STRATEGY §9 — treat PM-facing friction as a bug.
- **Provider: status quo.** Anthropic credits are at $0; extraction uses OpenAI
  **structured outputs** (strict JSON schema), same pattern and model tier as
  `ai/doc_extraction.py` (gpt-4o-mini). Develop on mocks; live calls are
  budgeted and announced (HANDOFF budget note).
- **Intake transport: email, polled.** Workers send texts/photos to a dedicated
  mailbox; the brain POLLS via IMAP/Gmail API (outbound-only connection). This
  preserves the localhost / no-public-endpoint posture (N7). The mailbox is the
  durable queue. Plus-addressing (`address+rockland@...`) for deterministic
  project routing where possible; classifier infers project otherwise.
- **No dependency cascade in the MVP.** Empirical finding from the live board
  data: dependency columns exist on 139 tasks but only **11 are populated** (one
  hand-built bathroom/plumbing/drywall chain); Owner/people column is **0/209**;
  ~35% of tasks have dates. There is no graph to walk. Instead, a later win lets
  the LLM PROPOSE dependency edges (human-approved, written to Monday's
  "Dependent On" column) so the graph gets built over time.
- **Man-hours: capture-only, no product yet.** The company has zero labor
  records anywhere. The extraction schema carries optional `workers` /
  `hours_worked` fields populated when a note mentions them. No timesheet UI,
  no utilization reports until data accumulates.
- **Explicitly NOT in scope:** fixed/ambient cameras, trade-scheduling
  deconfliction, auto-apply of any change, WhatsApp/Telegram adapters,
  multi-user auth, hosting. Do not build these.

## 3. Build order — three independently demoable wins

Ship each win fully (code + tests + a live demo path) before starting the next.
Each ends with the suite green, committed, pushed (repo conventions in
HANDOFF §10).

### Win 1 — Channel-agnostic core, typed text first  ← START HERE

The entire brain, with the cheapest possible input: a CLI command and a plain
text box on the project page.

1. **Schema.** A structured sidecar to `DailyLog` (mirror the
   `Document`→`DocumentText`/`FinancialRecord` sidecar pattern):
   `FieldNote` rows carrying: raw text, received_at, source channel
   (`cli` / `web` / `email`), sender ref (nullable for now), project_id,
   classification, verbatim evidence excerpt, optional workers/hours,
   matched_task_id (nullable), confidence. SQLite migration follows the
   existing back-compat column-map pattern.
2. **Extraction module: `ai/field_note_extraction.py`.** Classify-then-extract
   with structured outputs. Classification vocab:
   `task_done | task_progress | blocker | new_task | date_shift |
   scope_change | other`. Every extraction carries a verbatim
   `quoted_excerpt` (A6). Conservative posture: proposal-bot rules apply —
   "returning none is correct" (A7/N1). One note may yield multiple signals
   (the example note above = task_progress + blocker + labor info).
3. **Task matching.** Candidate retrieval over the project's tasks using the
   existing embedding machinery, then an LLM verdict picks the match or
   declines. A declined match is NOT a failure — it may be a `new_task`
   signal. Never substring/fuzzy-match across projects (N3).
4. **Proposal generation.** Map signals → existing Proposal rows:
   task_done → status change; date_shift → timeline change; new_task →
   task-creation proposal; blocker → status BLOCKED proposal + surfacing on
   the briefing. Extend `_ACCEPTABLE_FIELDS` carefully (A2/A3 ordering is
   sacred: external write first, local mirror second, fresh-read before
   mutate).
5. **Surfaces.** CLI: `project_db field-note <project> "text"` . Web: a text
   box on the project detail page posting to the same service function (A5:
   logic in a service module, consumed identically by CLI + web). Output =
   the normal proposal review queue.
6. **Tests.** Mocked-LLM end-to-end (note → signals → proposals), schema
   migration, conservative-decline behavior, multi-signal notes, the
   A2/A3 ordering on the new proposal types. Live smoke on Rockland with
   2–3 realistic notes (announce token cost).

**Done =** the Rockland PM can paste a sentence into the web page and accept a
resulting proposal that updates Monday.

### Win 2 — Email intake adapter

An IMAP/Gmail poller that turns mailbox messages into the same `FieldNote`
ingest path. Key points:

- **Roster table** (`Worker` or extend `User`): maps sender email/phone-gateway
  address → person → default project. Unknown senders are quarantined for
  review, never silently processed (prompt-injection surface: email content is
  untrusted input — it produces Proposals only, never direct writes, and the
  extraction prompt must treat message text as data).
- Poller runs as part of `project_db refresh` and/or a `poll-mail` command;
  idempotent via Message-ID dedup; attachments stored raw (they feed Win 3).
- Plus-address routing first; classifier-inferred project as fallback with
  lower confidence.
- **Before building the carrier path into anything:** the iPhone
  Messages→email transport must be verified on ONE real worker's phone (their
  actual carrier, with a photo + a voice memo). If flaky, fallback is the Mail
  app or a shared iOS Shortcut. The poller doesn't care either way.

**Done =** a text sent from a phone shows up as a pending proposal with no
human touching a computer in between.

### Win 3 — Photos through the same pipe

Attachments from Win 2 pass through the vision-capable model with the SAME
classification schema (a photo is just another field signal). Photo +
accompanying text are one combined signal, not two. No fixed cameras.

### Free win (1 hour, anytime) — the chaos report

A deterministic one-page report (no LLM, A8/N2 style) quantifying board
hygiene from canonical data: dependency fill rate (11/139), owner fill (0/209),
dated tasks (74/209), status mix. CLI + a panel. This is the owner's "why this
project exists" slide.

## 4. Guardrails recap (the ones most at risk in this feature)

- **A1/advisor-not-actor:** field notes NEVER auto-apply. Everything lands as
  PENDING proposals.
- **A6 evidence:** every proposal cites the verbatim note excerpt.
- **N7:** nothing listens on the public internet. The email poller is
  outbound-only. If you find yourself writing a webhook receiver, stop.
- **Eval harness (INTENTIONS §8):** as soon as the first real field notes
  exist, freeze 5 of them + hand labels as a gold set with a scorer; run it on
  every prompt/model change to this module.
- **ASCII-only in CLI prints; suite green; commit + push per session**
  (HANDOFF §9–10).

## 5. Open items owned by the human (not Claude Code)

- Verify the Messages→email transport on a real worker phone.
- Collect 2–3 real messy field notes at the next site visit (gold-set seeds).
- Confirm the Rockland PM's review cadence and get their first feedback —
  the PM's reaction, not more features, drives iteration after Win 1.
