# ALTA — Intentions (the money-saving roadmap, to complete later)

**Date:** 2026-06-03 (status note 2026-06-04). **Status:** durable intentions.

> **STATUS 2026-06-09:** #1 (Money-at-Risk) is now BUILT **and structured + run
> live**. `ai/obligation_extraction.py` (OpenAI structured outputs,
> `extract-obligations --structured`) replaced the keyword-gated batched
> approach; live-validated on 2150 Tupper + 5768 St-Laurent (the "$8,000 on key
> return" settlement surfaces, verified). Known residual limits (deferred, not
> forced): cross-copy settlement duplication + agency-buyout direction — see the
> CHANGELOG 2026-06-09 entry and HANDOFF. **#2 (value-caught tally) is now also
> DONE** (`report_value_caught` + `value-caught` CLI + the `/` headline card;
> live: "$1,926 surfaced across 2 projects"). **#3 (the plain-English
> per-project money one-liner) is now also DONE** (`report_project_money_line`
> + `money-line` CLI + a project-page banner; reworked to headline the CONFIRMED
> view rather than a quote-inflated margin). The
> financial extraction was rebuilt the same way earlier (CHANGELOG 2026-06-04).
> Provider is Anthropic-primary / OpenAI-fallback (Anthropic credits at $0).
>
> **STATUS 2026-06-12: §0 requirements have LANDED.** The job-site visit +
> planning session produced **`docs/FIELD_NOTES_BRIEF.md`** — the settled
> implementation spec for the field-note MVP (pilot: 923-927 Rockland; email
> intake, polled, N7-safe; no dependency cascade — the graph is empty;
> capture-only man-hours). **That brief now leads the roadmap.** Where this
> file's §0 sketch and the brief disagree, the brief wins. Also: the Drive
> source was switched to the team shared Drive with a clean-slate rebuild
> (2026-06-10) — 1081 docs, 439 financial records, 170 obligations, all
> team-only.
>
> **STATUS 2026-06-15: the field-note MVP (§0) is now BUILT.** All three Wins
> from `FIELD_NOTES_BRIEF.md` shipped — channel-agnostic core (typed text),
> Gmail-API email intake (N7-safe), and photos through the same vision pipe —
> plus a composite-scored task block, `parent_task_index` subitem creation, and
> RAG contract context in extraction. 958 tests. The loop is live: site note ->
> Proposal -> human accept -> Monday write-back. **Per STRATEGY §9 the next move
> is the Rockland adoption trial, not more building.** Open brief item: the
> deterministic "chaos report" (board-hygiene one-pager). See CHANGELOG
> 2026-06-15 + HANDOFF top block.
>
> **STATUS 2026-06-16: the financial layer is being REDESIGNED.** Moving from
> the `FinancialRecord` aggregate-net model to a division-keyed line-item
> ledger (`FinancialLineItem`) that reconciles profit per `(unit, CSI
> division)` — the model the owner's boss actually uses. Skeleton landed (CSI
> division vocabulary + model + migration); grid parser → `report_division_
> margins` → cutover are next. **`docs/FINANCIAL_REDESIGN.md` is the
> authoritative intent** — read it before touching the financial layer. The
> Monday task-graph rework (dependencies + schedule cascade + Gantt + write-
> back, phases 1-4) also shipped this stretch — see `docs/MONDAY_AUDIT.md`.
>
> **STATUS 2026-06-17: financial layer Phase 1a through 1c-hardening DONE.**
> The extras parser (`extras_grid.py`, extras-v1), classification metadata on
> all rows, `ingestion_status`/`ingestion_reason` on `DocLedgerResult`, and
> multi-sheet workbook routing (`split_workbook_sheets`) are all live. The
> populator now classifies each xlsx worksheet independently, deduplicates
> same-type sheets (first wins), and commits one atomic batch per document.
> An extras→quote fallback handles mislabeled documents (e.g. "EXTRAS+ROOF"
> with a quote grid body). Real-corpus verification on Rockland: 4 docs parsed,
> 133 rows, $278k total quoted revenue; St-Laurent correctly writes 0 rows
> (empty PDFs, unsupported simple-estimate format, meeting notes — all safely
> skipped). 1170 tests. **The financial layer is now safe and routing-correct.**
> What is NOT yet solved: cost-side truth, simple estimates (single-column
> format), PDF/Word extraction, version survivorship, status/date layering,
> PM-facing review workflow, FinancialRecord cutover. **Next is Phase 1d:
> Ledger Health / Review Surface** — an audit layer that makes the parser's
> decisions visible and lets a PM understand what was counted and why. See
> `FINANCIAL_REDESIGN.md §9` for the full Phase 1d spec. Do NOT build more
> parsers (job_cost, Word/PDF, LLM ingestion) until Phase 1d exists and an
> eval harness (§8) is in place.

> **STATUS 2026-06-17 (b): Project Log image ingestion MVP BUILT.**
> Daily ALTA Project Log labour/time sheets emailed in as images are classified
> separately from field notes (a fork in `email_intake._process_one`), extracted
> by a vision structured-output call, validated deterministically (hours
> computed vs reported, mismatches flagged, blanks dropped), and written to
> `ProjectLogSubmission` / `ProjectLogEntry` (employee linkage reuses `Worker` +
> a new `WorkerAlias`). A CSV mirror is exported under `ALTA Generated Reports/`
> which the Drive scanner now skips (no re-ingestion loop). CLI: `project-logs
> <project> [--export-dir]`, `poll-mail --no-project-logs`. Source of truth is
> the canonical DB, not Drive. Full spec + build status:
> `docs/PROJECT_LOG_INGESTION.md`. **Next = adoption** (send a real sheet;
> needs OPENAI_API_KEY + gmail-auth). Deferred: PDF rendering, fuzzy employee
> matching, employee profile UI, productivity analytics.

**Framing (owner, via boss):** the software is already well-built; what it is
*paid for* is **saving the company money over the long term** — being useful,
usable, and informative, not just clever. Every intention below is judged by
that: *does it put dollars back in the company's pocket, and will a PM actually
use it?*

These are intention-like (the "why" + a realistic implementation + how it
integrates), not step-by-step tasks. Each names a **build-when** trigger.
Read with `EVALUATION.md` (standing rules) and `STRATEGY.md` (mission).

The unifying idea: **ALTA already holds the raw materials** (contract text via
RAG, money via `FinancialRecord`, operational state via Monday, schedule via
tasks). The money-saving product is *connecting* them to catch the boring,
recurring, cross-system leaks a human lets slip. LLM **extracts evidence once**
(cached/idempotent); **deterministic code reconciles forever** (free).

---

## Honest tensions — named 2026-06-09, BOTH DECIDED 2026-06-12

Two mismatches between what the docs said and what was actually happening.
Both got their owner decision via the field-note planning session
(`FIELD_NOTES_BRIEF.md`):

1. **Adoption (was: the one unchecked box).** DECIDED: the **923-927 Rockland
   field-note pilot IS the one-PM trial** (STRATEGY §9). A beginner PM on a
   live job is committed to reviewing proposals a few times per week. The
   brief makes PM-facing friction a bug, not a backlog item. Building beyond
   the MVP wins before the pilot produces feedback = borrowing against this
   decision.
2. **Mission framing (was: financial-truth tool wearing an automation
   mission).** DECIDED: **recommitted to §0 active adaptation as the core
   line.** The financial layer is the supporting truth substrate, not the
   product. The field-note MVP is the first real §0 build; financial-trust
   work (§6/§7/§9) continues opportunistically behind it.

---

## 0. Active adaptation — automatic field-update management  ⭐⭐ (THE core purpose)

**Status: REQUIREMENTS LANDED (2026-06-12) → BUILD PHASE.** The settled
implementation spec is **`docs/FIELD_NOTES_BRIEF.md`** (pilot, provider,
intake transport, scope cuts, three-win build order). This section remains the
design rationale; **the brief overrides it wherever they differ.** This
consolidates the former `TRANSCRIPTION_FEATURE.md`.

**What.** A worker on site reports — by chat (WhatsApp to a number), voice, or
later a photo — *what was done / what's left*. ALTA classifies it, matches it to
that day's to-do list and the project timeline/scope, and proposes the resulting
updates **dependency-aware** (is this task done? does it slip a date? is it
off-plan? does it cascade to dependents?), through human approval. This is the
original purpose — automatic management — and the thing nobody else does;
financials are secondary to it.

**The key architectural insight: chat, voice transcription, and image
recognition are ONE pipeline with three input adapters, not three features:**

```
[ typed chat msg ]  ┐
[ voice transcript ] ├─→ FIELD SIGNAL → classify (done / new task / scope-change /
[ site photo (vision)]┘  (raw+project)   blocker / date-shift) + verbatim evidence
                                           ↓ reconcile vs tasks/timeline/scope/deps
                                           ↓ PROPOSALS → human approves → Monday / canonical DB
```

Build the core **once** (field-signal → classify → reconcile → propose); add
adapters cheaply. Google Docs are INPUT-only — outputs land in the canonical DB
or as Monday tasks, never written back to a Doc.

**Maps onto the existing framework (it's mostly an input source, not a new
paradigm):** `DailyLog` (storage; bare today — add a structured sidecar like
`DocumentText`/`FinancialRecord`), the classify-then-extract structured pattern
(`ai/doc_extraction.py`, `ai/obligation_extraction.py`),
`assemble_project_context` (current state for the prompt), and the Proposal
write-back engine (`ai/proposals.py`; `_ACCEPTABLE_FIELDS` extends *carefully* —
A2/A3, advisor-not-actor).

**⚠ The deployment/N7 collision — RESOLVED (2026-06-12), cheaper than the
original sketch.** This section originally predicted a small separate hosted
intake service as the likely shape. The settled answer is better: **email,
polled.** Workers text/photo a dedicated mailbox; the brain POLLS it via
IMAP/Gmail API — an outbound-only connection, so **nothing listens on the
public internet and N7 is never touched.** The mailbox itself is the durable
queue (retries, ordering, attachments for free). Plus-addressing
(`address+rockland@...`) gives deterministic project routing; the classifier
infers the project otherwise. No hosting, no webhook receiver, no new infra.

**The job-site questions — ANSWERED (recorded in the brief):**
1. *Deployment/ownership:* email intake as above; roster table maps sender →
   person → default project; unknown senders quarantined (untrusted input —
   prompt-injection surface).
2. *Dependency graph:* **empirically empty** — dependency columns exist on 139
   tasks but only ~11 are populated; Owner/people 0/209; 74/209 dated
   (verified against the canonical DB 2026-06-12). There is no graph to walk →
   **no dependency cascade in the MVP.** Inverted into a win: the LLM
   PROPOSES dependency edges (human-approved, written to Monday's "Dependent
   On" column) so the graph gets built over time.
3. *Granularity:* `task_done | task_progress | blocker | new_task | date_shift
   | scope_change | other`. Write-back appetite: advisory Proposals only (A1).
4. *Real field notes:* to be collected as the pilot runs — they seed the
   module's gold set (§8 posture).

**Build order = the brief's three wins:** Win 1 channel-agnostic core (CLI +
web text box → `FieldNote` sidecar → `ai/field_note_extraction.py` → task
match → Proposals); Win 2 email intake adapter (+ roster, Message-ID dedup);
Win 3 photos through the same pipe (vision, same schema). Plus the 1-hour
deterministic **chaos report** (board-hygiene stats) anytime.
`_ACCEPTABLE_FIELDS` extends *carefully* (A2/A3, advisor-not-actor).

---

## 1. Commitments & Money-at-Risk layer  ⭐ (highest ROI — do first)

**What.** Extract the *dated/dollar obligations* out of contracts — payment
milestones, retainage / final-payment, penalty clauses, deposit due dates,
settlement payments (e.g. 5768's "$8,000 due on key return"), insurance/permit
expiries — into a structured table, then deterministically reconcile them
against invoices + Monday status, and surface the ones that are **due, overdue,
or unbilled**.

**Why it saves money (concrete leaks it catches):**
- *Unbilled completed work* — milestone done in Monday, no invoice → uncollected
  revenue.
- *Forgotten obligations with a date+dollar* — the $8k settlement, the 10%
  retainage nobody's tracking.
- *Margin eroding mid-job* — supplier costs creeping past contracted revenue,
  caught while you can still act.
- *Overpaying suppliers* — an invoice exceeding the sub's quote, or a duplicate.
- *Penalty exposure* — a late-completion clause + a slipping schedule.

**Realistic implementation (mirrors the financial layer exactly):**
- New sidecar table `ContractObligation` (`db/models/`): `project_id`,
  `document_id`, `kind` (payment_milestone / retainage / penalty / deposit /
  insurance_expiry / settlement / other), `amount` (Numeric, nullable),
  `due_date` / `trigger` (free text, e.g. "on key return"), `direction`
  (owed_to_us / owed_by_us), `quoted_excerpt`, `confidence`, `status_signal`
  (computed), `prompt_version`, `source_meta_json`. Migration in
  `ensure_sqlite_schema` (same idempotent pattern).
- New `ai/obligations.py::extract_obligations_for_project` — same conservative,
  quoted-evidence, validate-don't-crash, all-or-nothing posture as
  `ai/financials.py`. CLI `extract-obligations <project>`.
- New deterministic reconciler `ai/views.py::report_commitments(session,
  project)` — joins obligations × `FinancialRecord` (is this milestone billed?)
  × Monday task status (is the triggering work done?) × today (is it overdue?).
  **No LLM here** — pure SQL/Python (invariant N2).
- **Integration:** a new `commitments` category in
  `report_attention_briefing` (the existing ranked landing) — each item a
  dollar figure + the clause + a recommended action. Plus a "Commitments"
  panel on the project page next to Financials.

**Cost posture:** extraction is the only spend — one LLM pass per doc, cached
+ idempotent (re-runs only on changed text). Run portfolio-wide via the
**Batch API (50% off)**; structure the prompt **static-instructions-first** so
**prompt caching** applies (see §4). Reconciliation + briefing are free forever.

**Build-when:** next. This is the most direct answer to "does it save money,"
and it makes the briefing genuinely *informative* ("here's money about to
slip"). Gated only on a small API budget for the one-time extraction.

---

## 2. "Value caught" ROI tally  ⭐ (cheap; the pay-justification feature)

**What.** ALTA counts the money it surfaced: *"This quarter ALTA flagged $43k in
unbilled milestones and 2 deadline risks."* A running scoreboard of dollars the
system put in front of a human.

**Why.** Converts "amazing software" into a number the owner/boss can see — the
literal justification for the work. Today ALTA does valuable things silently.

**Realistic implementation:** deterministic, no LLM. A `report_value_caught
(session, since=...)` that sums the dollar exposure of briefing/commitments
items over a window (and, once actioned, what was actually billed/avoided). A
small `BriefingEvent` log table (item surfaced → later resolved) gives the
"caught vs ignored" history. Surface as a headline card on `/` and a one-line
footer stat.

**Build-when:** alongside §1 (it needs commitments to have dollar figures to
tally). Tiny once §1 exists.

---

## 3. Usability / informativeness wins (mostly free)

Lighter, high-informativeness, near-zero cost. Each is a small deterministic
add unless noted.
- ~~**Plain-English money one-liner per project**~~ **DONE 2026-06-09**
  (`report_project_money_line` + `money-line` CLI + project-page banner;
  headlines the CONFIRMED view rather than a quote-inflated margin).
- **"What changed since you last looked"** — a weekly diff over the canonical DB
  (new invoices, milestone done-but-unbilled, new sub invoice over quote). Makes
  opening ALTA a habit. Needs a lightweight per-week snapshot.
- **Exportable / printable project brief** — a clean one-page financial + risk
  summary the PM can email the owner or client. Gets ALTA's value out of
  localhost into the business's workflow.
- **Small UX/robustness backlog** (from the former refocus plan): a Drive-OAuth-
  expiry banner in the web UI (token expiry currently fails quietly); a
  plain-English "this project type isn't modeled — rough estimate" label instead
  of the technical LOW CONFIDENCE; an "extraction pending — run extract-financials"
  empty state on the Financials panel; plain-English error messages. Low effort,
  do opportunistically.

**Build-when:** opportunistically; pairs with §1/§2.

---

## 4. Extraction cost + reliability hardening (apply the OpenAI/Anthropic API best-practices)

**What.** Make the extraction layer (financials + the §1 commitments) cheap and
reliable to run repeatedly across the whole portfolio. Not a feature — an
efficiency pass that makes §1 affordable from day one. See
`memory/openai_api_optimization.md`.

**Realistic implementation:**
- **Prompt caching:** keep the large static extraction instructions in a STABLE
  system prompt (head); only the per-document text varies. Byte-identical prefix
  across docs → up to ~90% input-cost reduction (OpenAI auto ≥1024 tok;
  Anthropic via explicit `cache_control`). Audit `_build_*_prompt` so the static
  part is truly invariant per run.
- **Batch API (50% off):** add a `--batch` path to `extract-financials` /
  `extract-obligations` that emits a `.jsonl`, submits one batch job for all
  candidate docs, and ingests results — for non-urgent portfolio re-extraction.
  (Anthropic Message Batches for the Anthropic path.)
- **Structured outputs / tool-schema:** replace ask-and-parse `complete_json`
  with schema-constrained output where the provider supports it, to cut
  malformed-JSON retries (each retry resends the whole prompt = wasted spend).
- **Model selection:** a cheaper model for easy docs; reserve the deep model for
  hard ones.
- **NOT fine-tuning** — OpenAI is winding it down; it's the treadmill the owner
  rejects. Few-shot + better prompts + RAG instead.

**Build-when:** fold into §1 as it's built (so the new extractor is cheap from
the start); retrofit financials opportunistically.

---

## 5. Acquisition / development-viability intelligence  🌟 (north star — different surface, same spine)

**What (the recruiting vision).** Given a stream of property leads — prospective
or early development projects — automatically assess **viability and profit
potential** to gain an edge over competitors who pay analysts and brokers, but
do it *automatically*. Context: a teammate built a scraper over **all Montreal
lot numbers** that pulls lot data → owning company → (via a shareholder-search
site) shareholders → contact info for outreach. That kind of data is what the
software team is producing.

**Why it saves/makes money.** This is the *acquisition* edge: surface
under-valued or high-margin development opportunities and warm leads before
competitors, automatically. Different from the operations brain (running current
jobs) — it's the deal-sourcing brain (finding the next ones). Long-term, the
larger prize.

**Why it fits the existing architecture (not a bolt-on):**
- The canonical schema **already has `Property`, `Lead`, `Deal`, `Client`** —
  this layer enriches the CRM side that's currently thin, it doesn't invent a
  paradigm.
- It reuses every existing pattern: a **new connector** (the lot/scraper feed)
  subclassing `BaseConnector`, registered in `connectors/registry.py`, writing
  `Property`/`Lead` rows through the **identity resolver** (dedupe lots/owners);
  **LLM extraction** of viability signals from listing/zoning/permit text (same
  conservative, evidence-backed posture); **deterministic scoring** of profit
  potential (lot size × zoning × comps × cost model — SQL/Python, NOT the LLM);
  and surfacing in a **new "Pipeline" briefing view** ranked by score, each lead
  with its evidence + the contact path.

**Partner's data pipeline (as described by the teammate, 2026-06-03) — the
actual feed this layer would consume:**
- *Property/owner outreach pipeline:* a Montreal-wide **properties CSV** keyed
  by **matricule** -> search matricule on Montreal.ca (form + scraper bot) ->
  **owning company name** -> look that company up on **REQ** (Registraire des
  entreprises du Quebec) -> **owner + shareholder names** (individuals) ->
  web / LinkedIn search -> **contact info**. Output: per-property owner contacts.
- *Contractor-lead pipeline:* contractors within ~50 km with a **verified
  website** -> email CSV -> automated outreach via **Instantly** (anti-spam) ->
  invite to a **form** (management + HR-operations sections) -> submissions
  matched into a **Supabase** DB (by VAT/phone; website already stored) -> a
  connected **review dashboard**.
- ALTA integration notes: **matricule** is the natural external key for the
  existing `Property` entity; REQ owner/shareholder records map to `Client` /
  `Lead` people via the resolver; the **Supabase** store + **Instantly**
  campaign are existing external systems to *read from* (a future connector),
  not to rebuild. ALTA's distinct edge is the **viability/profit scoring + the
  canonical join** layered on top of this feed.

**Realistic first slice (when the data feed is stable):**
- Ingest the teammate's lot dataset into `Property` (lot number = external key)
  + owning-company → `Client`/`Lead` via the resolver.
- A deterministic `report_lead_viability` scoring leads on the structured
  signals already present (size, zoning, assessed value vs ask, owner type).
- An LLM *narration*/enrichment pass (RAG over any listing/zoning docs) that
  explains a score with evidence — never computes it.
- A `/pipeline` view + a briefing category "high-potential leads."

**Cost posture / contingencies:** scoring is free (deterministic); enrichment is
bounded LLM (batched/cached per §4). Gated on (a) the scraper feed being a
stable, queryable source, and (b) explicit owner sign-off — this is a **new
product surface** and per `STRATEGY.md` / rule N6 we don't open new surfaces
until the current brain is in daily PM use. Keep it as the documented north star;
build the connector slice when the lead data is ready and a PM is using the ops
side.

**Build it as a SEPARATE app, integrated via shared DATA — not merged code
(owner discussion 2026-06-09).** The co-worker is scraping two DBs (leads =
properties; contractors = pricing/employment). The optimizer ("which contractor
is best for this project given scope/timeline/financials") is a *different
product* with different users and cadence than the ops brain; folding it into
this codebase is how you get another ~19k lines and lose the plot (the exact
drift we're fighting). Keep both codebases independently comprehensible and
connect them at the **canonical data layer** (the optimizer reads the ops DB —
project scope/timeline/financials — plus the two scraped DBs). Define that data
interface even while the optimizer lives elsewhere. **Technique note:** the
contractor-to-task choice is a **matching / assignment + weighted-scoring**
problem (constraint optimization / linear assignment, or a simple weighted rank
to start) — NOT gradient descent (that's for continuous differentiable
objectives). Aim at the right tool.

---

## 6. Cross-document quote/version dedup — entity resolution (financial trust)

**What.** The "huge number" failure mode (audited on 1455, 2026-06-09: reported
revenue $931k, but ~3× of it is the Richard Geller job counted across R1.pdf,
R2.pdf, and a renamed "Penthouse" copy, plus competing quotes summed). The
per-document dedup works; what's missing is a **cross-document** view that
recognizes "these N documents are versions/copies of the same quote." Same
failure class as the obligations cross-copy duplication.

**Don't hand-roll it — it's a textbook problem.** This is **entity resolution /
record linkage** + **near-duplicate detection** + **MDM golden-record /
survivorship**. Canonical pipeline: **block → match → cluster → survivorship →
human review**. (Algorithms: MinHash/LSH, SimHash, Fellegi-Sunter. Libraries:
`dedupe`, `Splink`, `recordlinkage`, `datasketch`.)

**ALTA already has most of it — extend, don't bolt on:**
- *Block* = within a project (already scoped).
- *Match* = `identity/resolver.py` + matchers ARE a record-linkage engine; reuse
  the pattern. Similarity signal = the existing `DocumentChunk` embeddings
  (document cosine) — no MinHash/LSH infra needed at our scale (dozens of docs).
  Precision order: near-equal total + same counterparty (deterministic) →
  filename version pattern (R1/R2/"Copy of"/v2) → embedding cosine for fuzzy cases.
- *Cluster* = connected components over matched pairs (small new code).
- *Survivorship + human review* = the **confirmed/quoted toggle** ("the awarded
  quote survives") routed through the **Proposal** table. Don't auto-merge.
- *Resolve* = `report_project_financials` counts one representative per GROUP
  instead of per document.
- The `Deal` canonical entity is the natural home for a "quote group".

**Cost/posture:** mostly deterministic + reuse existing embeddings (cheap). An
LLM grouping pass (optional, for fuzzy cases) is bounded + lands as Proposals.
At thousands-of-docs scale, `datasketch`/LSH is the documented upgrade (like
`sqlite-vec` for RAG) — a deliberate, not blind, simplicity for now.

**Build-when:** it's the real fix for financial trust, but a focused build of its
own. The money-line/financials already DON'T present the inflated all-in number
as truth (they say "confirm awarded quotes"), so this is an enhancement, not a
fire. Sequence it after active adaptation, or sooner if financial trust blocks
adoption.

## 7. Acquisition/development project-type money model (the "$0" failure mode)

**What.** The mirror of §6, found by hand-auditing 6554 (2026-06-09): a project
reads **$0 revenue** not because extraction broke but because ALTA has **no money
model for acquisition/development deals**. 6554's `SIGNED PSA.pdf` states a
**$1,500,000 purchase price + $50,000 deposit** — the biggest number on the
project — and it is captured NOWHERE. The structured extractor correctly classes
a Purchase & Sale Agreement as not-a-construction-transaction, then drops it.

**The subtle honesty hole:** the low-confidence guard did NOT fire for 6554,
because it can only flag money that landed in the `other` bucket — and here the
$1.5M was *skipped*, not mis-bucketed. **The guard can't flag money it never
extracted.** So 6554 masquerades as a clean $9k-cost project. This is the real
defect behind "the $0 is obviously wrong."

**Fix (when development deals matter enough):**
- New money-types: `acquisition_price`, `deposit_held`, `financing/loan`,
  `lease_income` — and a doc class for purchase/sale agreements that EXTRACTS the
  headline figures instead of skipping the doc.
- A project-type signal (construction vs acquisition/development) so the report
  uses the right model and the confidence guard fires when an
  acquisition-shaped project has no acquisition figures captured.
- Keep the deterministic posture: the LLM extracts the PSA's stated price with a
  quoted excerpt; code computes. (This was the former EVALUATION known-issue #14.)

**Build-when:** when development/acquisition projects matter to a PM. Until then,
at minimum the confidence guard should flag "this looks like an acquisition (PSA
present) but no acquisition money captured" so a $1.5M deal can't read as clean.

## 8. Extraction eval harness ⭐ (do BEFORE more extraction features)

**What.** The core capability — does the extractor get the money RIGHT on real
documents — is validated by HAND (the 1455/5768/6554 audits). That's anecdotal,
not regression-protected. There's no labeled gold set, no precision/recall on
amounts + directions. **Acutely dangerous right now:** production quietly runs on
`gpt-4o-mini` via the OpenAI fallback, but the prompts were tuned on Sonnet, and
NOTHING measures whether extraction degraded on that swap. This is the
highest-leverage missing infrastructure in the project (external review,
2026-06-09) and a "should-have-existed-long-ago" gap.

**Realistic, minimal implementation (don't overbuild):**
- Turn the existing hand-audits into a small **gold set** (`evals/`): for ~5 real
  documents, the known-correct key figures (e.g. 1455 Richard Geller quote total
  $159,120; 6554 PSA purchase price $1.5M *should be captured*; 5768 settlement
  $8,000 owed_by_us). YAML/JSON, hand-labeled once.
- A **scorer** that runs extraction on those docs and reports precision/recall on
  amounts + direction-correctness vs the gold. Run it on every prompt/model
  change. Cheap (5 docs).
- Catches: the gpt-4o-mini regression, future prompt edits, and (once §6/§7 land)
  whether dedup/acquisition-capture actually improved the numbers.

**Build-when:** before ANY further extraction-prompt or model change — it's the
guardrail that makes those changes safe. Note: this is infra, not a feature; keep
it to ~5 docs so it doesn't become its own project.

## 9. Bootstrap the confirmed/quoted default (lower the trust-curation friction)

**What.** A trustworthy margin only appears once a PM curates the confirmed/quoted
toggle — but that's chicken-and-egg (won't curate until they trust it, won't
trust it until it shows a real number). The smart default already confirms
invoice/receipt-role docs; extend it so the PM **corrects a guess** instead of
**curating from scratch**: infer "awarded" from a signed-contract doc, from a
quote that matches a later invoice, eventually from QuickBooks. Surface a
best-guess contract value with a one-click "confirm/correct", not a $0.

**Build-when:** pairs with §6 (which quote is the awarded one is the same
question). Small, high-adoption-leverage.

---

## Sequencing (updated 2026-06-17)

**Done (2026-06-09):** §1 Commitments/Money-at-Risk (structured + live), §2
Value-caught tally, §3 money one-liner. **Decided (2026-06-12):** both Honest
Tensions (pilot = the one-PM trial; mission = active adaptation).
**Done (2026-06-15):** §0 field-note MVP — all three wins (text/email/photo),
composite task scoring, Monday write-back. 958 → 1170 tests.
**Done (2026-06-17):** financial layer Phase 1a–1c-hardening — extras parser,
multi-sheet routing, ingestion metadata, extras→quote fallback. Rockland corpus:
4 docs / 133 rows / $278k revenue; St-Laurent: 0 rows (all skips are correct).

**Now, in order:**

1. **Rockland adoption trial (the one-PM test).** No new features until the
   Rockland PM has used the field-note + margin system and given feedback.
   Building beyond the three wins before feedback = borrowing against this
   decision.

2. **Financial Phase 1d — Ledger Health / Review Surface
   (`FINANCIAL_REDESIGN.md §9`). ✅ DONE 2026-06-17.** `fill-ledger --audit` /
   `report_ledger_health`: per-document table of classified_type /
   ingestion_status / ingestion_reason / rows_written / reconcile_ok /
   recommended_action, attention-first sorted. Validated on real Rockland (2 ok,
   2 reconcile-fail, 4 unsupported, 23 safe skips). The parser's decisions are
   now visible. **This unblocks further financial parser work (still gated on
   the §8 eval harness).**

3. **§8 eval harness for financial extraction.** Gold set (1455 Geller $159,120;
   6554 PSA $1.5M should-capture; 5768 $8k settlement). Required BEFORE any
   financial prompt/model change or new extractor (job_cost, Word/PDF, LLM).

4. **Financial Phase 2 — status/date layering (`FINANCIAL_REDESIGN.md §6`).**
   Proposed-vs-accepted filter on `report_division_margins`. Filename status
   already extracted; report modes (`--confirmed`, `--pipeline`) are next.
   Also: quote version survivorship (accepted > proposed, newer date wins).

5. **Financial Phase 3 — simple_estimate_grid.py.** Single-column
   `Description | Notes | Total Amount` layout (used by Common Area.xlsx
   ESTIMATE). Only build once Phase 1d audit confirms these docs matter and
   the eval harness can catch regressions.

6. **Financial Phase 4 — job_cost actual-spend parser.** ONLY reads the
   `Phase | Cost | Supplier | Date` block; ignores budget summaries, receivable
   projections, "Jair quoted" values. Requires: Phase 1d (audit), eval harness,
   and a clear business case that cost-side coverage matters to a PM's decision.
   The most dangerous parser to rush — see `FINANCIAL_REDESIGN.md §10`.

7. **Financial Phase 5 — PDF/Word/LLM ingestion.** Gated behind eval harness.
   LLM classifies/maps; deterministic code validates; ledger writes only
   validated facts. No prompt/model change without the gold set.

8. **Financial Phase 6 — FinancialRecord cutover.** Point the UI/briefing money
   story at `report_division_margins`; retire `FinancialRecord` aggregate-net
   path once parity is proven. No big-bang migration.

9. **§6 cross-document quote dedup.** Root-caused (entity resolution + version
   survivorship). Pull forward if financial trust blocks adoption.

10. **§3 usability wins** + UX/robustness backlog — opportunistic alongside above.

11. **§5 acquisition intelligence** — separate app, shared data; when the lead
    feed is stable AND the ops brain is in daily PM use.

**Standing rules for the financial layer:**
- No new parser (job_cost, Word, LLM) without Phase 1d audit + §8 eval harness.
- No cost-side rows until `job_cost` actual-spend region detection is built and
  validated against known spend amounts.
- No LLM financial ingestion without eval. LLM can classify/map; deterministic
  code validates and computes; ledger writes only validated facts.
- Dedup rule is still "first sheet wins" (safety heuristic); do not treat it as
  survivorship logic until Phase 2 status layering lands.

The test for all of it (rule N8): *does a PM/owner open ALTA sooner, and can you
point at dollars it saved?* If an idea fails that, it doesn't ship.
