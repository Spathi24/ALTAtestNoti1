# ALTA / project_db — Independent Architecture & Product Evaluation

**Author:** Senior architect / product strategist (fresh eyes, no prior involvement)
**Date:** 2026-05-29
**Inputs read in full:** README.md, ROADMAP.md, CHANGELOG.md (1,587 lines), HANDOFF.md
**Authority note:** This document is meant to be durable. Future sessions —
including cheaper models — should be able to execute against it without
re-deriving intent. Where I give a rule, I give the decision rule, not a vibe.

---

## OWNER CLARIFICATIONS (2026-05-29, post-evaluation discussion)

These refine Sections 4–5. **Where they conflict with the body below, these
win** — they come from the owner directly after reading the evaluation.

1. **Google Drive is the canonical and most complete financial source — NOT
   QuickBooks.** The CEO receives quotes/invoices by email; they are filed into
   Drive. QB will *not* hold the full picture. Financial reconciliation must
   center on Drive-document extraction. QB is supplementary and later — it does
   NOT "replace PDF-scraping with structured truth" as Section 5's stop-note
   implied. Reading the scattered Drive PDFs cohesively *is* the point.
2. **Project value structure varies per project:** some have a single
   quote/total; others are phased, with the phases listed in the quote. The
   extractor must handle both a single contract total and phased/milestone
   breakdowns.
3. **The goal is bookkeeping + cohesive money-flow understanding, not just
   budget-vs-contract divergence.** Track, per project: amount received from
   client, amount paid out, what the client still owes, which invoices are paid
   vs. unpaid. Big projects have many moving parts that are hard to track in
   bulk. Build incrementally.
4. **Hands-on financial *actions* (drafting/issuing invoices, pushing to QB)
   are explicitly deferred.** Reveal / narrate / bookkeep now; act later.
5. **Target UI is a scannable, auto-updating money dashboard with a tree-like
   structure** showing where money is going and for what, capturing
   interdependencies (project → phases → line items → invoices → payments).
   Dashboard-first, not conversational-first.
6. **Architecture principle (owner-affirmed):** specialized, independent layers
   that share state through the canonical DB — as `proposals` and the askbot
   already do — are the correct pattern. New layers are welcome ONLY when they
   add efficiency or capability, never for novelty; extra layers for their own
   sake create clutter and interdependencies. This is rule **N8**, restated by
   the owner as a standing gate on all future work.

7. **Every project has a TWO-SIDED ledger with an upcharge between the sides.**
   - **Client side (money IN):** the amount *we* invoice the client. Drives
     "received from client" and "what the client owes." Tied to the invoice we
     SEND.
   - **Contractor side (money OUT):** contractors/suppliers quote *us*; we input
     those quotes. Tied to our quote and to invoices we RECEIVE.
   - **The upcharge is the spread between the two — that margin is the
     business.** The financial model MUST represent both directions per project
     and the margin, not a single money column. "Where the money goes and for
     what" = client invoice → contractor line items/phases → retained margin.
     The superior flagged this as the hardest part to conceptualize.
8. **Do NOT hardcode a rigid financial schema to today's file conventions —
   they vary per project and will change.** Owner's explicit long-term concern
   is software longevity. Design schema-light: content-driven extraction (the
   LLM reads the doc), folder/filename used only as a weak prior, raw kept in
   JSON, queryable fields promoted to columns (operating principle #4). A
   per-doc-type rigid model keyed to current folder names is a trap.

**What the live DB shows (verified 2026-05-29, read-only audit):**
- `invoice` table = 0 rows, `vendor` table = 0 rows. Contractors/suppliers
  (e.g. "Resistance Electrique", "Laurentien Electrique") are NOT modeled as
  counterparties yet. The contractor side of the ledger has no home in the
  schema today.
- Financial docs exist but are messy: filename signals are partial and
  **bilingual** (FR: `facture`=invoice, `soumission`/`devis`=quote,
  `quittance`=receipt/release). Folder conventions vary wildly — projects are
  organized by tenant name, by date, by building, or by function ("Invoices",
  "Estimates", "Quittance", "Sub Quotes").
- Folder names are a WEAK hint, not authoritative: 5768's "Invoices" folder
  contained a `Soumission` (a quote), not just invoices.
- **Project TYPES differ.** 5768 St-Laurent is a real-estate / tenant-buyout
  project (quittances, NDAs, tenant settlements) — structurally different from a
  construction project where we invoice a client and receive contractor quotes.
  The extractor must not assume one project shape.
- Classification of doc role (quote / invoice / receipt) and direction (client
  vs. contractor) therefore REQUIRES reading content; rules alone won't do it.

**Drive testing posture (2026-05-29):** the Drive directory is currently a
STATIC CLONE on the owner's personal drive — fine for throwing test extractions
at, but it does not receive live updates. Monday.com IS live. Trigger for
plugging in the real Drive: only once single-project financial extraction +
reconciliation is proven trustworthy on the static clone AND we need to validate
the *incremental-update* path (delta sync → a new invoice lands → ledger
updates). Build and prove extraction on the clone first; switch to live Drive to
test live updates. The owner will plug it in on request — ask explicitly.

---

## SECTION 1 — WHAT THIS PROJECT ACTUALLY IS (AND ISN'T)

ALTA (`project_db`) is a single-user, localhost data platform that pulls a
contractor's operational data out of Monday.com and Google Drive into one
canonical SQLite database, and then runs an LLM layer on top of it that reads
the contracts sitting in Drive and proposes corrections to what Monday says is
happening. The spine is a 13-entity canonical schema with an `ExternalId`
bridge, fed by per-source connectors and an identity resolver; Drive folder
ancestry deterministically defines project identity, and Monday boards match
*into* those projects. On top of that spine sit three things: deterministic
"canned reports" (`ask`), an LLM proposal pipeline (`propose timelines` /
`propose scope`) that writes suggestions to a `Proposal` table for human
approval, and a local web UI (`serve`) that exposes the whole read → review →
accept loop in a browser. The one and only thing the system writes back to the
outside world is a Monday column update — and only for timeline dates — and
only after a human clicks accept. That is the entire product surface today.

What ALTA is **not**, despite how it sometimes describes itself: it is **not a
financial management system**, even though the README mission promises "manage
projects' finances" and "global awareness of financial continuity." There is no
financial extraction code in `src/` at all (I checked — no
`extract-financials`, no invoice/line-item/change-order tables, nothing). The
only money feature is `budget_vs_contract`, which regexes dollar signs out of
contract text and picks the max. The Invoice table is empty; the QuickBooks
connector has never been run against live data. It is also **not the
"reconciliation brain" the strategy claims** in any deep sense yet — the only
reconciliation that closes the loop is dateless-task filling. Scope
reconciliation exists but is advisory-only with no action path. And it is **not
a sync tool** in the Zapier sense, though the connector/registry/`ExternalId`
machinery is large enough that a reader skimming the code could reasonably
think the sync *is* the product. The feature areas that blur the line most are:
(a) the **roadmap integration** (a 44-task architect design workflow imported,
actor-classified, and injected into proposal prompts) — sophisticated machinery
serving a thin slice of value; (b) the **QuickBooks connector** — complete,
tested, never run; and (c) the **`/db` inspector and raw-JSON panels** — useful
dev affordances that can read like a second product surface.

**Is the core value proposition still coherent?** Partially — and the
incoherence is exactly what the owner is feeling. The *stated* value prop
(reconcile contract-vs-execution across money, scope, and schedule; catch
cross-system errors before they cost money) is excellent and genuinely
differentiated. But the *delivered* value prop has narrowed to a single thin
capability: "the LLM proposes start/end dates for tasks that lack them, and you
accept them into Monday." That is the least valuable of the three mission pillars
(schedule), built first because it was the most tractable, while the pillar the
owner actually cares about (money/financial continuity) has zero
implementation. The drift wasn't a wrong turn — every individual phase was
sound and well-executed — it was an **order-of-operations drift**: the team
kept building the tractable, demonstrable, test-greenable slices (timeline
proposals, then the approval CLI, then the web UI, then roadmap injection, then
prompt-quality polish) and never crossed into the hard, high-value financial
reconciliation that is the whole reason the project beats opening two tabs. The
original goal — the thing in the mission statement — is still right. The build
sequence quietly optimized for shippability over draw.

---

## SECTION 2 — WHAT WORKS AND GENUINELY DELIVERS VALUE

**1. Monday.com sync (read + delta).** Works, sound, and genuinely load-bearing
— but invisible to a PM. The full pull is ~20s; delta sync via
`Board.activity_logs` gets a quiet day down to ~6s with 11/12 boards skipped.
The mirror-column overlay (recovering per-task status/timeline from linked
portfolio items, 5/118 → 93/118 on 923 Rockland) is a real piece of hard-won
domain engineering. Verdict: this is excellent plumbing that the PM never sees
and never should. It earns its keep only because everything else reads from it.

**2. Google Drive sync + document text extraction.** Works and is the most
valuable raw asset in the system. 750 documents with full metadata, 554 linked
to projects by deterministic folder ancestry, 463 with extracted text across
PDF/DOCX/XLSX/Google Docs/Sheets. This is the substrate the entire "brain"
depends on — without extracted contract text there is no reconciliation. The
extraction is idempotent and respects a 10 MB cap. Verdict: sound and
high-value, but it is *potential* value — the text is extracted and then barely
used (the askbot can't even see it; see #4).

**3. The canonical identity/resolver layer (Drive folders as registry,
ProjectMatcher, ExternalId bridge).** Works and is the single best architectural
decision in the project. The Phase 2.5 rebuild — making Drive folder ancestry
the deterministic source of project identity and deleting the substring matcher
that caused "Rockland matches 927 Rockland" — fixed a root-level data-integrity
disease that was silently corrupting every report and proposal. The
"uncertainty surfaces in `doctor`, never guessed in code" invariant is
exactly right. Verdict: works, sound, and should never be touched. This is the
foundation that makes everything above it trustworthy.

**4. The `ask` command + Haiku LLM fallback.** Works but is structurally
hobbled. The 8 canned reports are instant and deterministic — good. The Haiku
fallback reads a whole-DB *metadata* snapshot (`report_database_overview`) and
**deliberately excludes document text**. So it can tell you which tasks are
dateless but it cannot answer "what does our standard payment-terms clause say?"
or "what scope does the 923 Rockland SOW commit us to?" — the questions that
would make a PM go *"I couldn't get that anywhere else."* The 2026-05-26
assertive-prompt rewrite made it less annoying, but assertiveness over thin
context just produces confident thin answers. Verdict: works, useful for quick
structured lookups, but it is not yet a reason to open the app. It is blind to
the most valuable data in the system.

**5. Timeline proposals (generation, review, accept/reject, Monday
write-back).** Works end-to-end and is the most carefully engineered path in the
codebase — write-first/flip-second ordering, past-date rejection guard, integer
indices instead of UUIDs, validate-don't-crash, auto-supersede, one verified
real Monday accept. The engineering is genuinely good. **But this is precisely
the feature the owner says nobody needs:** filling in a couple of dates is
something a PM can do faster by hand in Monday, and writing LLM-inferred dates
into the source of truth is the part that "feels dangerous." Verdict: works,
sound implementation, low user value. This is a clever demo of the pipeline, not
a draw.

**6. Scope proposals (advisory-only).** Works as a generator, and is closer to
real value than timelines — flagging contract scope items with no matching
Monday task is the kind of thing a human genuinely misses. The quoted-excerpt
reasoning makes the flags verifiable. **But it is a half-built feature:** it is
advisory-only, `accept_proposal` refuses `scope_gap`, and there is no
create-task-in-Monday action path. So the system can tell you "the contract
commits you to X and it's not on the board" and then... you go do it manually.
Verdict: works as analysis, valuable as a signal, but the loop is open — it
produces homework, not action, and it currently competes for the PM's attention
with roadmap-template noise (see #8).

**7. The local web UI (`serve`).** Works, is well-architected (service-module
discipline, thin routes, permission-boundary tests, stale-state guards,
HTMX-without-a-build-pipeline), and was the right call to pull forward because
the CLI was unusable for daily work. **But its center of gravity is wrong for
what the owner wants.** It is built as an *action console* — its marquee
interactions are "generate proposals (spend Sonnet tokens)" and "accept → write
to Monday." The owner explicitly said the UI should be "more informational and
interactive" and that the write-back is low-value. The UI is currently
optimized for the exact loop the owner is questioning. Verdict: the
*engineering* is sound and reusable; the *product framing* of the UI is the
thing that needs to change.

**8. Roadmap integration (Layer 1 storage + Layer 2 prompt injection).** Works
technically and was honestly evaluated (Layer 3 was correctly skipped). **But
this is the clearest case of effort outrunning value in the whole project.** The
imported roadmap is an *architect's* design-phase workflow (SD → DD → CD → CA);
24 of 44 tasks are ARCHITECT-only and filtered out as noise on a contractor's
execution board. What survives injection produces "template-derived" scope flags
that the UI itself has to caveat with "review with 'does this apply here?' in
mind." So the system built an enum, a classification LLM pass, an xlsx importer,
and dual-prompt injection in order to surface generic checklist items that the
PM must then second-guess. Verdict: works, but it adds review burden and
cognitive load without a corresponding lift in trust. Freeze it; do not extend
it.

**9. The quoted-excerpt reasoning requirement.** Works and is genuinely
excellent — the single highest leverage-per-line change in the recent log. Every
contract-sourced proposal now carries a literal quoted excerpt + document name,
so accept/reject becomes evidence-based instead of trust-based, and a PM can
Ctrl-F the source in one click. It also lowers the hallucination floor by
forcing verifiable text rather than summary. Verdict: works, sound, keep and
apply this discipline to every future LLM-extraction feature.

**10. The `doctor` and `rebuild` commands.** Work and are essential, but they
are developer/maintainer tools, not PM features. `doctor` is the trust
instrument that proves the canonical data is correct (554/554 linked, 0
mislinks); `rebuild` re-derives the DB safely (preflights connectors before
wiping, preserves DocumentText, exports Proposals first). Verdict: both work and
are well-designed; correctly scoped as infrastructure. A PM will never run them
and shouldn't.

---

## SECTION 3 — WHAT IS SLOP (CODE OR FEATURES THAT DON'T EARN THEIR KEEP)

I was skeptical of myself here, as instructed, and I do not think the answer is
"nothing." There is real slop, and it follows a recognizable pattern: features
built because they were *tractable and demonstrable*, not because a PM was
blocked without them.

**Roadmap integration (Layers 1 + 2) — the headline item. Freeze, do not
extend; consider deleting from the prompt path.** What it is: a `RoadmapTask`
table, a `RoadmapActor` enum, an `import-roadmap` xlsx parser, a
`classify-roadmap` Sonnet pass, and prompt injection into both proposal bots.
Why it was built: the owner had a design-phase roadmap spreadsheet and it seemed
natural to make the AI "aware" of it. Why it's slop: it injects an *architect
design workflow* into a *contractor execution* tool; more than half the tasks
are filtered as noise, and what remains produces generic template flags the UI
must explicitly tell the user to distrust. It increased the review surface
without increasing trust. The honest Layer 3 skip shows the team half-sensed
this. Recommendation: **freeze**. Leave the table and importer (harmless,
already tested), but seriously consider removing the prompt injection — the live
5768 test produced 4 roadmap flags vs 6 contract flags, and the contract flags
are the ones with real evidence. The roadmap flags are the ones that feel like
the system padding its output.

**QuickBooks connector — frozen plumbing.** What it is: complete client +
connector code with tests for invoices/estimates/customers. Why it was built:
QB is one of the four mission systems and it was scaffolded early. Why it
qualifies: it has never run against live data, the Invoice table is empty, and
it has sat "code complete, live test pending" since 2026-05-12. Recommendation:
**keep but do not extend** until credentials exist — and when they do, it
becomes genuinely valuable (structured invoice truth instead of PDF scraping).
This is deferred-correctly, not deleted. Flagging it so no one mistakes
"connector exists" for "financial data exists."

**The `/db` raw inspector + raw-JSON debug panels — keep, freeze.** What it is:
a reflective table browser and collapsible raw-data dumps on detail pages. Why
it was built: developer convenience during M5. Why I'm flagging it: it is a
second read surface that competes conceptually with the actual product surface
and could tempt future "let me just add a filter to /db" creep. Recommendation:
**keep** (it's cheap and genuinely useful for debugging) **but freeze** — it is
explicitly a dev affordance, never a product feature, and the read-only
forbidden-route tests should stay.

**Scope proposals' advisory-only dead-end — not slop, but unfinished in a way
that produces slop-like UX.** Generating flags that nothing can action means the
feature's output is friction (a to-do list the PM transcribes by hand).
Recommendation: either close the loop (a `create-task` write-back path) or
demote scope flags to a passive "watch list" panel rather than the
proposal/accept machinery. Right now it borrows the heavyweight Proposal
lifecycle for something that can't be accepted.

**What is NOT slop, to be clear:** the connector/resolver/`ExternalId` spine,
the Drive-folder identity model, `doctor`/`rebuild`, the quoted-excerpt
discipline, the service-module/permission-boundary architecture of the web UI,
and the dual-provider abstraction are all earning their keep. The 625-test suite
is a real asset. The slop is concentrated in *speculative AI surface area*
(roadmap injection) and *premature connector breadth* (QB), exactly where
STRATEGY.md warned it would accumulate.

---

## SECTION 4 — THE CORE PROBLEM THE OWNER IS DESCRIBING

**4.1 — What is the owner actually saying is wrong?** Strip the phrasing down
and there are three claims. First: *the only thing the product does for me is
write task dates back to Monday, and that's not worth doing* ("at that rate we
can just fill in those entries ourselves"). Second: *writing AI-inferred values
into my source of truth feels risky relative to how little I get back* ("finicky
and awkward... almost seems dangerous"). Third: *the thing I actually wanted —
the system managing finances and data automatically — isn't what I got.* The
precise capability gap is this: **ALTA delivers schedule write-back (low value,
feels risky) and has delivered none of the financial reconciliation that was the
actual draw.** The owner built a careful approval pipeline for the *cheapest*
piece of the mission and is now staring at it wondering why it doesn't feel
special. It doesn't feel special because filling two date fields is not a
problem anyone needed solved.

**4.2 — Is Monday write-back the right anchor for value?** No. It is a *correct
capability* but the *wrong anchor*. Writing to Monday should be the occasional
last step, not the headline. The reason it feels like extra work is that the
economics are upside-down: the PM spends a token-costing Sonnet call, reviews a
proposal, dry-runs it, and clicks accept — a multi-step, slightly scary ritual —
to accomplish something they could do in Monday in five seconds. Write-back
becomes compelling only when the thing being written is something the PM
*couldn't easily compute themselves and trusts the system to have gotten right*
— e.g. "this invoice's line items reconcile to the contract; mark the milestone
billed." Schedule dates are neither hard to compute nor high-stakes enough to
justify the ceremony. The anchor should move from *write* to *reveal*: the
product's primary action should be surfacing a cross-system truth, with
write-back as an optional convenience on top.

**4.3 — What would make this feel genuinely useful rather than a clever demo?**
Picture the best case. A PM opens ALTA on Monday morning and the landing screen
says, in plain language: *"3 things need your attention. (1) 5768 St-Laurent is
invoiced at $142k against a contract value of $165k, but Monday shows the job
85% complete — you're under-billed by roughly $18k; here's the contract clause
and the milestone. (2) 923 Rockland has a settlement-payment obligation in the
contract ($8,000 on key return) with no corresponding task or invoice. (3) Two
projects have contract scope items with no matching task."* Every line is a thing
the PM cannot see by opening Monday and Drive in two tabs, because it requires
reading the contract, joining it to Monday status, and joining that to the money.
The PM clicks one, sees the evidence (quoted excerpt, the numbers, the source
docs), and decides. That is the product at its best: **a Monday-morning
risk-and-money briefing that no single tool can produce.**

What the PM actually sees today: a dashboard of counts (21 projects, 463 docs
with text, N pending proposals) and a queue of timeline proposals suggesting
dates for tasks. To get anything richer they must navigate to a project, spend
tokens to generate proposals, and review schedule suggestions. **The gap is
that the system currently surfaces *activity it generated* (proposals) rather
than *truths it discovered* (money/scope/schedule inconsistencies).** It shows
its own output, not the business's reality.

**4.4 — What is the "draw"?** This is the crux. The draw is **cross-system,
contract-grounded financial and scope reconciliation that a human cannot get by
looking at Monday and Drive directly.** A PM in Monday sees tasks and a budget
number. In Drive they see a folder of PDFs. Nowhere can they see "contract
promised X, Monday says we've done Y%, QuickBooks/our invoices say we've billed
Z, therefore we are over/under by W and here is the clause that proves it."
ALTA is the *only* place that can compute that, because it is the only place
that has read the contract text, the operational state, and (eventually) the
money in one canonical join. Right now that answer is **not strong** — the money
half doesn't exist, so the most differentiated question the system could answer
is the one question it can't. What would make it undeniably strong: structured
financial extraction (contract value, invoice line items, change orders) landing
in queryable tables, a deterministic SQL reconciliation that computes the
over/under, and an LLM that *narrates* the result with quoted evidence. The
moment a PM sees "you're under-billed $18k on this job and here's why," opening
ALTA before Monday stops being a behavior you have to coach and becomes a
behavior you can't stop. That — not date write-back — is the specialty.

---

## SECTION 5 — THE PRIORITIZED BUILD LIST

The ordering principle: move ALTA's center of gravity from *writing schedule
data into Monday* to *revealing money-and-scope truths nobody else can compute*.
Read-value first; write-back stays a bounded convenience, not the headline.

## 1. STRUCTURED FINANCIAL EXTRACTION (CONTRACT VALUE + INVOICE LINE ITEMS)
WHAT: Per-document-type LLM extractors that pull structured financial records
(contract total + payment milestones, invoice line items, change orders) out of
already-extracted `DocumentText` into new canonical tables, using the same
conservative, quoted-evidence, validate-don't-crash posture as the proposal
bots.
SOLVES: The PM has no machine-readable contract value or billing data anywhere;
"what's the financial state of this job?" is unanswerable today. This is the
raw material for the entire draw.
DONE WHEN: Running `extract-financials --doc-type contract` and `--doc-type
invoice` on a real project populates new tables with line items, each carrying a
quoted source excerpt and a `project_id`; a SQL query returns contract total and
sum-of-invoiced for at least 3 real projects, spot-checked against the actual
PDFs.
DEPENDS ON: DocumentText (done). Nothing else. Explicitly does NOT depend on QB.
EFFORT: 3–4 sessions (one per doc-type, ship contract value first, then invoice
line items, then change orders only if used).

## 2. THE RECONCILIATION SURFACE (THE "MONEY TRUTH" VIEW)
WHAT: A deterministic SQL reconciliation that joins contract value (from #1) ×
Monday completion/status × invoiced amount × budget, computes over/under-billing
and budget divergence per project, and a read-only UI panel + portfolio view
that surfaces it — with an LLM *narrating* (not computing) the result, citing
the contract clause.
SOLVES: Directly answers "is this project bleeding money, and why?" — the
single most differentiated question ALTA can answer and the one the owner keeps
pointing at ("manage finances," "global awareness of financial continuity").
DONE WHEN: A project detail page shows contract value, % complete, invoiced,
and a computed over/under figure with a one-line LLM narration carrying a quoted
clause; the dashboard ranks projects by financial risk. Numbers are SQL-derived,
never LLM-derived.
DEPENDS ON: #1 (financial extraction). Hard prerequisite.
EFFORT: 1–2 sessions.

## 3. REFRAME THE UI FROM ACTION CONSOLE TO MONDAY-MORNING BRIEFING
WHAT: Restructure the landing experience so the first thing a PM sees is a
ranked list of *discovered truths needing attention* (money divergences, scope
gaps, overdue/at-risk items) — each a click-through to evidence — instead of a
counts dashboard plus a proposal queue. Demote "generate proposals / write to
Monday" to a secondary, clearly-bounded action.
SOLVES: The owner's exact complaint — "needs to be more informational and
interactive," and write-back "almost seems dangerous." Makes the product a
read-first briefing where writes are optional, not the centerpiece.
DONE WHEN: Opening `serve` lands on a briefing of the top N attention items
across all projects, each with evidence and a recommended action; the user can
get value from a full session without writing anything to Monday.
DEPENDS ON: #2 for the money items to be real (can ship a scope/schedule-only
version of the briefing earlier if needed, then enrich once #2 lands).
EFFORT: 2 sessions.

## 4. RAG OVER DocumentText (MAKE THE ASKBOT SEE THE CONTRACTS)
WHAT: Chunk + embed `DocumentText`, store vectors in `sqlite-vec`, and feed
relevance-ranked excerpts to the askbot (and as supplementary context to the
proposal bots), per the detailed plan already in ROADMAP.
SOLVES: Today `ask` is blind to document text — it cannot answer "what does our
standard payment-terms clause say?" or "which insurance certificate expires
next?" RAG turns `ask` into a contract-knowledge layer that genuinely cannot be
replicated by browsing Drive.
DONE WHEN: `ask "what does the 923 Rockland contract say about payment terms?"`
returns an answer grounded in retrieved chunks with a citation link, verified
against the actual document.
DEPENDS ON: DocumentText (done). Independent of #1–#3; can be done concurrently.
EFFORT: ~4 sessions (per the existing ROADMAP breakdown).

## 5. ANOMALY / INCONSISTENCY DETECTION (THE "ERRORS CAUGHT" PROMISE)
WHAT: A detection pass (mostly deterministic SQL, LLM only to narrate) that
flags cross-system inconsistencies: contract obligations with no task or
invoice, milestones marked done in Monday but not invoiced, scope items with no
task, deadlines past with status not-done.
SOLVES: The mission's "errors caught" pillar ("one caught change order per
quarter pays for the project") — turning silent cross-tool gaps into flagged
items before they become losses.
DONE WHEN: The Monday-morning briefing (#3) populates from a real anomaly
detector, and at least one real, non-obvious inconsistency is surfaced on a live
project and confirmed genuine by the owner.
DEPENDS ON: #1 and #2 (money anomalies) and the existing scope generator (scope
anomalies).
EFFORT: 2 sessions.

I stop here. Items beyond this (live QB — valuable but credential-blocked and
~1 session whenever creds appear; anomaly-as-proposals write-back; fine-tuning
corpus; local-model swap) are real but I do not have conviction they should be
built *before* the five above prove the draw. Live QB specifically should slot
in opportunistically the moment credentials exist, because it replaces #1's
invoice PDF-scraping with structured truth — but it is gated on creds, not on
priority.

---

## SECTION 6 — STANDING RULES FOR ALL FUTURE SESSIONS

### ALWAYS DO

**A1. The LLM proposes; a human disposes; the LLM never computes money.** Every
AI-produced field change lands in `Proposal` as PENDING and requires human
accept/reject. Financial *totals, margins, and over/under figures are computed
in SQL, never by the LLM* — the LLM extracts line items (with quoted evidence)
and narrates results; arithmetic is deterministic. (This is the load-bearing
extension of the existing advisor-not-actor invariant for the financial work in
Section 5.)

**A2. Every Monday-touching mutation writes externally FIRST, flips local state
SECOND.** `accept_proposal` and `set_task_timeline` already do this. Any new
write-back path (e.g. create-task from scope) must preserve it: a failed
external write must leave canonical state untouched and the proposal PENDING. The
test `test_write_back_false_leaves_proposal_pending` is the canary.

**A3. Every mutation route re-reads the entity state immediately before
mutating and renders a stale fragment if it is no longer actionable.** No write
route in `web/routes/` may call a service mutation without first re-reading and
checking status. The stale-state guard is non-optional.

**A4. Identity stays deterministic; uncertainty surfaces in `doctor`, never
guessed in code.** Project identity comes from Drive folder ancestry; Monday
matches in via `ProjectMatcher` (civic-number then exact-name, unique-hit-only).
A board matching no allowlisted rule is skipped, not guessed.

**A5. No business logic in templates or routes — it lives in a service module
(`ai/views.py`, `web/ui_views.py`) consumed identically by CLI and UI.** This is
what keeps the two surfaces from drifting and the codebase reviewable.

**A6. Every LLM extraction carries verifiable evidence.** The quoted-excerpt
requirement (literal quote + document name for contract/document evidence) is
mandatory for every current and future extraction feature, including financial
extraction. Summaries ("the contract states...") are rejected.

**A7. The prompt-philosophy boundary is permanent.** Askbot = assertive,
inferential, recommends, no external write. Proposal/extraction bots =
conservative, refuse on uncertainty, "returning none is correct." The regression
test `TestProposalBotsStayConservative` pins it.

**A8. Read value before write value.** When choosing what to build, prefer
features that *reveal* a cross-system truth the PM can't otherwise compute over
features that *write* data back. Write-back is a bounded convenience on top of
revealed value, never the headline.

**A9. Keep the suite green and the posture intact.** Run `pytest` before
pushing anything touching `src/`; add a test for every feature. ASCII-only in
script/CLI `print()` output (Windows cp1252). Commit to `main`, push after
meaningful changes, never `git add -A` (the egg-info trap).

### NEVER DO

**N1. Never make a proposal/extraction bot "smarter" by giving it the askbot's
assertive style.** The right answer to "weak proposals" is better evidence (RAG,
quoted excerpts, better source selection) — never loosening the
anti-hallucination posture. Hallucinated dates/amounts flow to Monday and become
real bad data.

**N2. Never let the LLM perform financial arithmetic that SQL can do.** Sums,
margins, over/under, % complete — all deterministic. The LLM's financial job is
extraction (evidence-backed) and narration only. Violating this reintroduces
exactly the trust problem that makes write-back feel dangerous.

**N3. Never reinstate substring/fuzzy project matching.** The deleted
`_match_project_by_name` caused the "Rockland matches 927 Rockland" corruption.
Identity is folder-ancestry-deterministic, full stop.

**N4. Never add a UI write route without A2 + A3 (write-first ordering + stale
re-read), and never add bulk-accept to the UI.** One bad proposal in a batch of
20 reaches Monday before anyone notices. Bulk stays CLI-only.

**N5. Never expand the roadmap-integration (architect design-phase) machinery,
and do not add anomaly/scope features that increase the PM's review burden
without increasing trust.** The roadmap injection is frozen. If a feature's
output is something the PM has to second-guess ("does this apply here?"), it is
making the product worse, not better.

**N6. Never pick up deferred plumbing before the brain ships and a PM is using
the daily loop.** Permanently off the table until explicit owner sign-off:
CompanyCam connector, Monday webhook receivers, Postgres + Alembic, text-to-SQL
natural-language layer, multi-tenant/multi-user/auth/hosting, resource/crew
scheduling. (`sqlite-vec` for RAG is the *one* sanctioned "new tech" exception,
because ANN search is where SQL genuinely bites — see Section 5 #4.)

**N7. Never break the single-user / localhost / no-auth posture.** Multi-user is
a different product that invalidates the M5 architecture (no CORS, no `--host`,
no session auth). If it comes up, it is a separate project, not a feature.

**N8. Never build a feature because it is tractable, demonstrable, or
technically interesting.** The test for any new work is: *does a PM open the app
sooner because of it?* If the honest answer is "it makes the demo richer" or "it
rounds out the architecture," stop. This is the anti-pattern that produced the
roadmap-injection slop and the never-run QB connector — both individually
defensible, collectively a drift away from the draw.

---

## EXECUTIVE SUMMARY

Three things the owner needs to hear plainly. **First:** the foundation is
genuinely good — the canonical schema, the Drive-folder identity model,
`doctor`/`rebuild`, the quoted-excerpt discipline, and the web UI's architecture
are sound and worth building on; nothing structural is wrong. **Second:** the
product drifted into delivering its *cheapest* mission pillar (writing task
dates to Monday) and *none* of its most valuable one (financial reconciliation)
— which is exactly why it feels finicky, low-value, and "dangerous": you built a
careful, slightly scary approval ritual around a problem nobody needed solved,
while the draw you actually want — "this job is under-billed $18k and here's the
contract clause" — has zero implementation because there is no financial
extraction code at all. **Third:** the fix is not more polish on the
write-back loop; it is to shift the product's center of gravity from *writing
schedule data* to *revealing money-and-scope truths nobody else can compute* —
build structured financial extraction, then a deterministic reconciliation
surface, then reframe the UI as a Monday-morning risk-and-money briefing. Do
that and ALTA stops being a clever demo and becomes the one screen a PM opens
first.

EVALUATION COMPLETE. Save this document as EVALUATION.md
