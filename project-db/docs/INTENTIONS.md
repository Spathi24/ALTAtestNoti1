# ALTA — Intentions (the money-saving roadmap, to complete later)

**Date:** 2026-06-03 (status note 2026-06-04). **Status:** durable intentions.

> **STATUS 2026-06-09:** #1 (Money-at-Risk) is now BUILT **and structured + run
> live**. `ai/obligation_extraction.py` (OpenAI structured outputs,
> `extract-obligations --structured`) replaced the keyword-gated batched
> approach; live-validated on 2150 Tupper + 5768 St-Laurent (the "$8,000 on key
> return" settlement surfaces, verified). Known residual limits (deferred, not
> forced): cross-copy settlement duplication + agency-buyout direction — see the
> CHANGELOG 2026-06-09 entry and HANDOFF. **Next agreed task: #2 (value-caught
> tally)**, then the per-project money one-liner (#3), then show the PM. The
> financial extraction was rebuilt the same way earlier (CHANGELOG 2026-06-04).
> Provider is Anthropic-primary / OpenAI-fallback (Anthropic credits at $0).
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
- **Plain-English money one-liner per project** — "Contracted $76.5k · invoiced
  $52k · costs $48k · ~$28k margin · 2 milestones unbilled." A deterministic
  template over `report_project_financials` + commitments. One sentence = the
  whole financial state. (No LLM.)
- **"What changed since you last looked"** — a weekly diff over the canonical DB
  (new invoices, milestone done-but-unbilled, new sub invoice over quote). Makes
  opening ALTA a habit. Needs a lightweight per-week snapshot.
- **Exportable / printable project brief** — a clean one-page financial + risk
  summary the PM can email the owner or client. Gets ALTA's value out of
  localhost into the business's workflow.

**Build-when:** opportunistically; the one-liner is the cheapest and pairs with
§1/§2.

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

---

## Sequencing (intention, not commitment)

1. **§1 Commitments & Money-at-Risk** + **§2 Value-caught tally** — the
   demonstrable-ROI core. Build §4's cost techniques into it as you go.
2. **§3 usability wins** — opportunistic, mostly free, high informativeness.
3. **§5 acquisition intelligence** — the north star; begin the connector slice
   when the lot-data feed is stable AND the ops brain is in real PM use.

The test for all of it (rule N8): *does a PM/owner open ALTA sooner, and can you
point at dollars it saved?* If an idea fails that, it doesn't ship.
