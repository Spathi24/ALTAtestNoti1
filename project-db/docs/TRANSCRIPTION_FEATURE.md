# Live Transcription & Consolidation — design notes + job-site questions

**Status:** DESIGN ONLY (2026-06-09). **Do not build before the job-site
requirements visit.** This doc exists to (a) record how the feature maps onto the
framework that already exists, so a future session doesn't re-derive it, and (b)
structure the open questions so the on-site visit is a productive requirements
session rather than a guess.

---

## 1. What the feature is (owner, 2026-06-09)

On a site visit, a PM describes — out loud or in writing — **what was done and
what's left to do**. ALTA should **classify and categorize** that description and
**automatically update the project's timeline and scope**, taking **full account
of all dependencies** of the new information, through the existing
human-approval flow. The owner says the framework is "already set up" — and it
largely is (see §3). The feature is a new *input source* (a field note) into the
machinery ALTA already has, not a new paradigm.

Restated as a pipeline:

```
field note (voice->text or typed)
   -> classify each statement (done / to-do / scope-change / blocker / date-shift)
   -> extract structured updates WITH verbatim evidence
   -> reconcile against current project state (tasks, dates, scope, dependencies)
   -> propose updates (dependency-aware) to the Proposal table
   -> human approves -> write back to Monday (existing path)
```

---

## 2. Governing invariants it MUST respect (do not relax)

- **Advisor, never actor (A1/N-series).** Every update lands in `Proposal` as
  PENDING; a human accepts before anything writes to Monday. A field note must
  not auto-mutate the board. This is the load-bearing trust rule.
- **LLM extracts; deterministic code computes (N2).** The LLM classifies the note
  and pulls structured statements with evidence; the dependency cascade / date
  math / status reconciliation is deterministic Python.
- **Every extraction carries verbatim evidence (A6).** A proposed update quotes
  the sentence of the note that justifies it (same discipline as financials /
  obligations).
- **Identity stays deterministic (A4/N3).** A note maps to a project (and tasks)
  by explicit reference, never fuzzy guessing.

---

## 3. How it maps onto what already exists (confirmed by exploration)

| Need | Existing piece | Path |
|---|---|---|
| Store the raw field note | `DailyLog` (bare: `log_date`, `summary`, `project_id`, `author_id`) | `db/models/work.py:98` |
| Structured extractions sidecar | the `DocumentText` / `FinancialRecord` / `ContractObligation` pattern (sidecar table, evidence + confidence + source_meta_json) | `db/models/` |
| Classify-then-extract via strict schema | the pattern we just built twice | `ai/doc_extraction.py`, `ai/obligation_extraction.py` |
| Current project state for the prompt | `assemble_project_context` (tasks, dates, docs) | `ai/context.py:148` |
| Propose → review → write back to Monday | the Proposal engine | `ai/proposals.py` (`ProposalBatch`, `accept_proposal:1073`) |
| Surface what changed | the attention briefing / project page | `ai/views.py`, `web/` |

**So the genuinely NEW code is small in surface but careful in substance:**
1. A **field-note ingest** entry point (CLI `ingest-note <project>` and/or a web
   textarea) that stores the note in `DailyLog` (+ a structured sidecar).
2. `ai/field_note_extraction.py` — classify each statement (done / to-do /
   scope-change / blocker / date-shift) + extract structured updates with
   evidence, OpenAI structured outputs (same shape as the other two extractors).
3. **Proposal generation from a note** (not from a contract): map extracted
   statements → `Proposal` rows (task status change, new task, date shift, scope
   add), each with the quoted note sentence as evidence.
4. **Dependency-aware reconciliation** (the hard part — see §4).
5. *Carefully* extending `ai/proposals.py::_ACCEPTABLE_FIELDS` (today
   `{"timeline"}`) so new update kinds can write back — each new writable field
   needs the write-first/flip-second ordering and a stale-state guard (A2/A3).

---

## 4. The hard part: dependency-aware timeline updates

"Taking full consideration of all dependencies" is the crux and the riskiest
piece. A note like *"framing is done, but the slab pour slipped a week"* should
not just edit one date — it should cascade the slip through everything that
depends on the slab pour.

Open design questions (resolve before building):
- **Where does the dependency graph live?** Monday has `dependency` /
  `board_relation` columns (already used by the mirror overlay,
  `connectors/monday/...`). Are real task dependencies actually populated on the
  boards, or only implied? If implied, a cascade has nothing deterministic to
  walk.
- **Cascade policy.** When a task slips N days, do dependents shift by N
  (hard-linked), or only flag for review? Hard auto-cascade writing many dates to
  Monday is exactly the "feels dangerous" write-back the owner flagged — likely
  the cascade should PROPOSE a batch the human reviews, not auto-apply.
- **Determinism.** The cascade itself must be deterministic graph math over the
  dependency edges (N2) — the LLM only identifies *which* task slipped and by how
  much, from the note.

---

## 5. Open questions for the job-site visit (bring these)

Prioritized — the first three gate the whole design.

1. **Input modality.** Live audio → speech-to-text on-site (needs a transcription
   integration — OpenAI Whisper API is the obvious fit given the OpenAI budget),
   or typed/pasted text after the fact? Real-time during the walk, or a debrief
   afterward? (Drives whether we need an audio pipeline at all.)
2. **Write-back appetite.** Advisory proposals only (matches the owner's stated
   wariness of writing to Monday), or should some high-confidence updates
   auto-apply? (Strong prior: proposals only, at least to start.)
3. **Dependencies — are they real in Monday?** Do the boards actually carry task
   dependencies, or is the sequencing in people's heads? This decides whether a
   deterministic cascade is even possible now (see §4).
4. **Update granularity.** Which of these should the feature propose: task done /
   task %-complete / new task / date shift / scope addition / blocker-flag? Which
   matter most to the PM on a real visit?
5. **Who / when / retention.** Author of the note (a `User`)? One note per visit
   per project, or cross-project? Keep the raw transcript (likely yes, as
   evidence — it's the `quoted_excerpt` source)?
6. **What does "good" look like?** Get one or two REAL example field notes from
   the PM (verbatim, messy, bilingual) — they become the test fixtures and the
   thing we validate the extractor against, exactly as the 5768 docs grounded the
   obligations work.

---

## 6. Proposed phased build (AFTER requirements land)

Sequenced smallest-useful-first, each shippable + testable on mocks:
1. **Ingest + store** a typed note in `DailyLog` (+ structured sidecar). No AI yet.
2. **Classify + extract** statements (`ai/field_note_extraction.py`, mock-tested).
3. **Generate advisory proposals** from the note (no new write-back fields yet —
   reuse the existing PENDING/review surface).
4. **Dependency-aware date proposals** (only if Monday carries real dependencies).
5. **Audio → text** (Whisper) only if modality #1 calls for it.
6. *Last and most carefully:* extend `_ACCEPTABLE_FIELDS` for new write-back
   kinds, each with the A2/A3 guards + a test.

Develop on mocks (free); one live OpenAI run per phase to confirm, per the
standing budget discipline (HANDOFF §6).
