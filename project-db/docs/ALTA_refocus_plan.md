# ALTA (`project_db`) — Refocusing Plan
**Date:** June 2026 | **Purpose:** Job-site demo prep + scope convergence

---

## The honest diagnosis up front

The system is not broken. The architecture is genuinely good — deterministic
identity, solid canonical schema, a sound web UI, 797 passing tests. The problem
is that it explored too wide a surface area before confirming that any one
part of it was indispensable to a real PM's daily workflow. That's normal for
a project with a broad mandate, and it's fixable. The fix is not a rewrite;
it's a focus cut.

The core failure mode: the system currently surfaces *activity it generated*
(timeline proposals, roadmap flags, scope gaps) rather than *truths it
discovered* (money risk, missed obligations, scope with no task). Proposals
that write dates to Monday feel risky and low-value. A morning briefing that
says "this job is under-billed $18k and here's the clause" feels essential.
The system has most of the raw material for the latter. It just hasn't been
pointed there hard enough yet.

---

## 1. Feature inventory and real-world assessment

### 1.1 Monday.com sync (read + delta)
- **Workflow:** keeps the canonical DB current with board/task/status changes
- **User:** backend / automated; PM never runs it directly
- **Replaces:** nothing visible — it's plumbing
- **Frequency:** daily, ideally automated on `serve` startup (already wired)
- **Time saved:** indirect — all downstream features depend on it
- **Error reduction:** yes, eliminates the tab-switching join
- **New risk:** Monday API changes, rate limits, delta cursor drift
- **Demo-ready:** yes, but invisible — never demo this directly

**Classification: Production-ready, background infrastructure. Do not demo it
standalone.**

---

### 1.2 Google Drive sync + document text extraction
- **Workflow:** indexes every PDF, DOCX, Excel, and Google Doc in Drive so
  the AI can read them
- **User:** automated; PM benefits without touching it
- **Replaces:** manually opening Drive PDFs to find contract clauses
- **Frequency:** on-demand (daily delta is already wired to `serve`)
- **Time saved:** high once downstream features are built; currently latent value
- **Error reduction:** eliminates missed documents, bilingual number errors
- **New risk:** Drive OAuth token expiry (`invalid_grant`) — annoying in a demo
- **Demo-ready:** yes as a foundation story, not as a standalone demo

**Classification: Production-ready infrastructure. Mention it once as the
reason the AI can read contracts; move on.**

---

### 1.3 Attention briefing (`/` landing + `project_db briefing`)
- **Workflow:** Monday-morning ranked list of money risk, overdue tasks,
  scope gaps, missing contracts — each with a severity badge and a link to
  evidence
- **User:** PM / owner, daily
- **Replaces:** opening 4 tabs and doing a mental join across systems
- **Frequency:** daily or every project visit
- **Time saved:** significant — the cross-system join is the whole point
- **Error reduction:** yes — surfaces missed milestones, overdue tasks,
  money flags that would otherwise be invisible
- **New risk:** low — it's purely deterministic, no LLM, no external write
- **Demo-ready:** yes — this is the single most demonstrable feature

**Classification: Production-ready small win. Lead with this in the demo.**

---

### 1.4 Financial reconciliation layer (`/projects/{id}/financials`)
- **Workflow:** reads every quote, estimate, invoice, receipt from Drive PDFs
  and computes a two-sided money picture: money IN (client) vs money OUT
  (contractor), margin, money-type buckets, per-document breakdown
- **User:** PM / owner, per-project review
- **Replaces:** manually hunting through Drive folders to piece together
  who owes what
- **Frequency:** per project, whenever financials need a reality check
- **Time saved:** high — a Quebec bilingual PDF pile is extremely slow to
  reconcile manually
- **Error reduction:** yes — catches direction errors, double-counting,
  unverified amounts; the confidence flag prevents false confidence
- **New risk:** low-confidence flag (honest); direction errors on ambiguous
  docs (flagged, not hidden); Drive OAuth needed
- **Demo-ready:** yes for clean renovation projects (1455 St-Mathieu is the
  best example — 100% confidence, honest margin); avoid 6554 in the demo

**Classification: Production-ready small win for renovation-type projects.
Second feature to demo.**

---

### 1.5 Confirmed-vs-quoted toggle (financial status per document)
- **Workflow:** lets a PM mark which quotes the company actually accepted,
  so the confirmed margin excludes speculative quotes
- **User:** PM, per-project
- **Replaces:** a spreadsheet toggle or mental note
- **Frequency:** one-time setup per project, then updated on new awards
- **Time saved:** moderate — prevents quote inflation from polluting the margin
- **Error reduction:** yes — addresses the "we dump every quote in there"
  problem
- **New risk:** low — it's a DB flag on the document, not an external write
- **Demo-ready:** yes, briefly — show the toggle and the margin recalculating

**Classification: Production-ready small win. Include as a 60-second aside
in the financials demo.**

---

### 1.6 Document-aware `ask` (RAG over contract text)
- **Workflow:** ask a plain-English question and get an answer grounded in
  actual contract clauses, with citations
- **User:** PM / owner, ad-hoc
- **Replaces:** Ctrl-F across multiple PDFs or calling someone to look it up
- **Frequency:** ad-hoc but high-value when needed ("what are our payment
  terms?", "what does the SOW say about the scope?")
- **Time saved:** high when used — eliminates reading 80-page PDFs
- **Error reduction:** yes — citations prevent hallucination; hybrid search
  catches exact tokens (invoice numbers, names)
- **New risk:** requires `OPENAI_API_KEY` for embeddings; answers are only
  as good as the extracted text; Drive OAuth needed for fresh content
- **Demo-ready:** yes, for 1–2 prepared questions you've already tested

**Classification: Promising, demo-ready with prepared questions. Third demo
beat.**

---

### 1.7 Hybrid document search (`/search`)
- **Workflow:** search across all project documents — meaning-based AND exact
  keyword — from a browser
- **User:** PM, ad-hoc
- **Replaces:** Drive's own (weak) search
- **Frequency:** ad-hoc
- **Time saved:** moderate
- **Error reduction:** yes — hybrid search surfaces exact identifiers (estimate
  number, civic address) that pure vector search misses
- **New risk:** low — it's read-only
- **Demo-ready:** yes

**Classification: Production-ready small win. Can be shown in 30 seconds as
part of the `ask` / RAG beat.**

---

### 1.8 Contract obligations / commitments (`extract-obligations`, `commitments`)
- **Workflow:** extracts dated/dollar obligations from contracts (payment
  milestones, retainage, penalty clauses, settlement payments) and flags
  which are overdue, due soon, or uncollected
- **User:** PM / owner, per-project
- **Replaces:** manually reading every contract clause and tracking in a
  spreadsheet
- **Frequency:** per project, weekly check
- **Time saved:** high — this is where money gets lost silently
- **Error reduction:** very high — the $8k key-return settlement example is
  exactly the kind of thing that disappears in a folder
- **New risk:** requires an extraction run (API spend); the code exists but
  has not been live-validated on the full portfolio
- **Demo-ready:** not yet — obligations extraction hasn't been run against
  real projects; it's built on mocks

**Classification: Promising but needs stabilization. Run `extract-obligations`
on 1455 and validate before demoing. Do not include in the first demo.**

---

### 1.9 Timeline proposals + Monday write-back
- **Workflow:** LLM reads contract and proposes start/end dates for dateless
  Monday tasks; a human accepts → dates written to Monday
- **User:** PM, per-project
- **Replaces:** manually filling in task dates
- **Frequency:** low — PMs either know the dates or don't care
- **Time saved:** low — filling dates in Monday takes 30 seconds manually
- **Error reduction:** low — the model must refuse to invent past dates;
  accepted proposals that are wrong introduce bad data into Monday
- **New risk:** high — writing AI-inferred dates to the source of truth is
  the owner's stated concern; a bad date is invisible until something goes wrong
- **Demo-ready:** technically yes; strategically no — it's the feature the
  owner said "feels dangerous"

**Classification: Freeze for demo purposes. Don't show write-back. The
underlying pipeline (proposals, accept/reject) is sound engineering and can
come back when there's a higher-value write-back use case (e.g. marking a
milestone billed).**

---

### 1.10 Scope proposals (advisory-only)
- **Workflow:** LLM reads contract and flags scope items with no matching
  Monday task
- **User:** PM, per-project
- **Replaces:** manually comparing SOW to task list
- **Frequency:** once per project, at kickoff or mid-job review
- **Time saved:** moderate — depends on contract length
- **Error reduction:** yes — surfaces the "agreed to X, forgot to track it"
  problem
- **New risk:** advisory-only (no write-back); but the flags require manual
  review and transcription, which is friction; roadmap-injected flags are
  labelled as "may not apply"
- **Demo-ready:** partially — the contract-sourced flags with quoted excerpts
  are demonstrable; the roadmap-sourced flags should be hidden

**Classification: Promising, demo with caution. Show one clean example from
a real project (923 Rockland's SOW is the best candidate). Do not generate
proposals live in the demo — pre-run and show the output.**

---

### 1.11 Roadmap integration (import, classify, prompt injection)
- **Workflow:** imported 44-task architect design-phase checklist, classified
  by actor (architect vs contractor), injected into proposal prompts
- **User:** no one, currently
- **Replaces:** nothing the PM was doing
- **Frequency:** never in normal use
- **Time saved:** negative — adds review burden (template flags the PM must
  second-guess)
- **Error reduction:** negative — adds noise (EVALUATION §3 verdict: slop)
- **New risk:** prompt pollution; flags that say "review with 'does this apply
  here?' in mind" signal low reliability
- **Demo-ready:** no

**Classification: Freeze/archive. The table and CLI are harmless; the prompt
injection was already removed (2026-05-29). Do not mention this feature.**

---

### 1.12 `doctor` and `rebuild`
- **Workflow:** audits the canonical DB for mislinks, orphaned docs, bad
  project identity; `rebuild` re-derives from sources
- **User:** developer / maintainer only
- **Replaces:** manual DB inspection
- **Frequency:** rarely — after a major sync issue or schema change
- **Time saved:** high for the developer
- **Error reduction:** essential for data integrity
- **New risk:** `rebuild` is destructive (well-guarded, but still)
- **Demo-ready:** no — this is maintenance tooling

**Classification: Production-ready for internal use. Never demo. Just
mention "we have data integrity checks" if asked.**

---

### 1.13 QuickBooks connector
- **Workflow:** would sync invoices/payments/estimates from QB into canonical DB
- **User:** N/A — has never run against live data
- **Replaces:** N/A
- **Frequency:** N/A
- **Time saved:** N/A
- **New risk:** credential-blocked; Invoice table is still empty
- **Demo-ready:** no

**Classification: Freeze. Code is complete; activate when credentials appear.
Do not mention in the demo.**

---

### 1.14 Local web UI (`project_db serve`)
- **Workflow:** browser-based access to briefing, projects, documents,
  proposals, financials, ask, search
- **User:** PM / owner
- **Replaces:** the CLI, which is unusable for non-developers
- **Frequency:** daily if the PM adopts it
- **Time saved:** high — the CLI has too many commands to navigate
- **Error reduction:** two-click confirm, stale-state guard, spinners prevent
  accidental writes
- **Demo-ready:** yes — this is the demo surface

**Classification: Production-ready small win. All demos run through the
browser, not the terminal.**

---

## 2. Feature classification summary

| Feature | Classification |
|---|---|
| Monday sync (background) | ✅ Production-ready — infrastructure |
| Drive sync + text extraction | ✅ Production-ready — infrastructure |
| **Attention briefing (`/`)** | ✅ **Production-ready small win — lead demo** |
| **Financial reconciliation** | ✅ **Production-ready small win — second demo** |
| **Confirmed/quoted toggle** | ✅ **Production-ready small win — demo aside** |
| **Ask / RAG (document-aware)** | ✅ **Production-ready (with prep) — third demo** |
| Hybrid search (`/search`) | ✅ Production-ready — 30s add-on |
| Contract obligations/commitments | 🟡 Promising — validate before demoing |
| Scope proposals | 🟡 Promising — demo with pre-run output only |
| Timeline proposals + write-back | 🔴 Freeze for demo — owner flagged as risky |
| Roadmap injection | 🔴 Freeze/archive — already removed from prompts |
| `doctor` / `rebuild` | ✅ Production-ready for internal use only |
| QuickBooks connector | 🔴 Freeze — credential-blocked |
| Local web UI | ✅ Production-ready — the demo surface |

---

## 3. Top 3 workflows for the job-site demo

**#1 — The Monday-morning briefing**
Open the browser at `/`. Show the ranked attention list: money risk, overdue
tasks, scope gaps, missing contracts. Point at a real item ("this project has
confirmed costs exceeding confirmed revenue — click it"). Land on the evidence.
This is the one thing no other tool can produce from a single screen.

**#2 — The financial picture for one project**
Navigate to a clean renovation project (1455 St-Mathieu is the best candidate).
Open `/projects/{id}/financials`. Show money IN vs money OUT, the margin,
the per-document breakdown, the verification badges, and the confirmed/quoted
toggle. Explain: "we read your Drive PDFs — in English and French — and turned
them into this." That's the value prop in one screen.

**#3 — Ask a contract question**
Go to `/ask`. Type: *"What scope does the 923 Rockland contract describe?"*
Watch it come back with cited excerpts from the actual SOW PDFs. This is the
"the system read your contracts" moment. Test this question in advance and
confirm the answer looks good before the demo.

---

## 4. Thin-slice MVP (10-minute demo flow)

**Setup (before you arrive):**
- `project_db serve` running
- Drive OAuth token not expired (test this)
- 1455 St-Mathieu financials pre-extracted and verified
- One `ask` question pre-tested with a good answer

**The demo (10 minutes):**

| Time | What you do | What they see |
|---|---|---|
| 0:00–1:00 | Open `/` | The briefing — ranked list with severity badges |
| 1:00–2:30 | Click a money-risk item | The financial panel for that project |
| 2:30–5:00 | Walk the financials panel | Two-sided ledger, margin, per-doc breakdown, toggle |
| 5:00–6:00 | Show the document text panel | "Here's the actual contract clause behind that number" |
| 6:00–8:00 | Go to `/ask`, type the SOW question | RAG answer with citations |
| 8:00–9:00 | Show `/search` | "You can also search across every document" |
| 9:00–10:00 | Summarize | "One screen, every project, reads your contracts" |

**What you do NOT show:** proposals, write-back, the CLI, doctor, roadmap, QB.

---

## 5. Things to remove or hide from the demo and current UI

**Hide or de-emphasize now:**

- The "Generate proposals" buttons on the project detail page — move them
  behind an "Advanced" disclosure or remove from the main nav until the
  financial story is proven
- The `Propose timelines` / `Propose scope` UI forms — they invite a click
  that spends tokens and produces output the PM has to second-guess
- The roadmap classification (already removed from prompts; make sure no
  UI surface mentions it)
- Raw JSON debug panels — collapse them by default (already `<details>`),
  or remove from the non-dev build
- The `/db` inspector — great for you, noise for a PM; keep it but don't
  link it from the nav

**Remove from the active CLI help output / `ask "help"`:**
- `classify-roadmap`, `import-roadmap` — hide, not delete
- `llm-test` — developer tool, hide
- `proposals accept all --yes` / `reject all --yes` — hide from the help
  summary; too powerful and too easy to misfire

**Unnecessary abstractions to simplify before the demo:**

- The `LLM_PROVIDER=mock|anthropic|openai-compatible` resolver is correct
  engineering but confusing in a demo; hard-code Anthropic in the demo env
  and don't mention it
- The `--delta` / `--full` sync flags should default to delta and not
  require any flag in the demo

---

## 6. Engineering fixes to reduce demo risk and daily friction

These are one-session items, highest ROI first:

**1. Drive OAuth guard (critical for demo)**
If the token is expired, `serve` currently starts but Drive-dependent features
fail silently or with a cryptic error. Add a startup check: detect
`invalid_grant` on the first Drive call and display a clear banner in the
web UI: *"Drive connection expired — run `project_db gdrive-auth` to reconnect."*
Do not let this appear mid-demo.

**2. Briefing item "last updated" timestamp**
The briefing recomputes from stored data, which is only as fresh as the last
sync. Show a "data as of [timestamp]" in the footer of every briefing item so
a PM trusts the numbers are current. This is already in the footer for the
last refresh; surface it more prominently on the briefing itself.

**3. Financials confidence flag — plain English**
The "LOW CONFIDENCE" flag is correct but technical. Change the label to
something like: *"⚠ This project type isn't modeled yet — treat this as
a rough estimate."* Make it obvious why so the PM doesn't panic.

**4. Financial extraction — pre-run, don't run live**
`extract-financials` is a multi-step LLM call that can take 30–60 seconds
per project and can fail mid-run. Never call it live in a demo or as a default
page load. Pre-extract all demo projects the night before. The web Financials
panel should show "Extraction pending — run `extract-financials` to populate"
if no records exist, not an empty state with no explanation.

**5. `/ask` input validation**
If the user submits an empty question or a very short one, the LLM call still
fires. Add a 3-character minimum check client-side before submitting.

**6. Proposal accept guard — mandatory dry-run**
If someone clicks Accept on a proposal in the UI, require a dry-run step first.
The current flow technically requires two clicks with the HTMX confirm, but add
a server-side gate that refuses an accept without a logged dry-run in the last
5 minutes for that proposal. This makes write-back feel safer without removing
the feature.

**7. Error messages in plain English**
Several error states show raw Python exception text or JSON error objects.
Audit the proposal detail, financials panel, and ask response for any case
where a raw error bleeds through to the UI and replace with a human-readable
message + a suggested action.

---

## 7. Revised roadmap

### This week (before the demo)

1. **Run `project_db serve` end-to-end** on the demo machine and verify
   every route loads cleanly
2. **Pre-extract financials** for the 3 demo projects
   (`extract-financials "1455 Saint Mathieu"`, etc.) and confirm the panel
   looks right
3. **Test the Drive OAuth token** — if expired, re-authenticate now
4. **Pre-run and eyeball** the `ask "what scope does the 923 Rockland contract
   describe?"` question — confirm the answer is good
5. **Add the Drive-expiry banner** (30 min engineering, critical for demo)
6. **Hide the proposal-generation buttons** from the main project page or
   move them behind an "Advanced" disclosure (1 hour)
7. **Confirm the briefing loads fast** — it's deterministic and should be
   sub-second; if it isn't, profile it

### The demo itself

Lead with the briefing. Financials second. Ask/RAG third. 10 minutes. No
write-back, no proposals, no CLI.

### After the demo (next 2 weeks, based on feedback)

- **If the financials land:** stabilize `extract-obligations` against real
  projects and add the commitments/money-at-risk category to the briefing
  — this is the highest-ROI next build (INTENTIONS §1)
- **If the `ask` lands:** run a full fresh embed pass and broaden the demo
  question set
- **If the scope proposals are asked about:** pre-run scope for one project
  and add a passive "watch list" panel (not the proposal-review machinery)
- **If write-back comes up:** frame it as "we can do that — it's built, but
  we want to make sure the data is right first"

### Postpone (1–2 months)

- Contract obligations / commitments — validate with 3 real projects first
- Scope proposal action path (create-task in Monday)
- `project_db daily` HTML version in the UI

### Freeze / do not touch

- Roadmap injection — already removed from prompts; leave it
- QuickBooks live integration — waiting on credentials
- Bulk accept/reject UI — correctly omitted from M5; leave it
- Any new write-back feature until financial reading is proven

### Delete / hide from users

- `import-roadmap`, `classify-roadmap` CLI commands — hide from `ask "help"`
- `llm-test` — hide from `ask "help"`
- Raw-JSON debug panels — collapse by default in production

---

## 8. What to tell your boss

Here's a framing that's honest and positions this well:

---

*"The first phase of the project was exploratory — the brief was broad, and we
built a wide surface to find out which parts actually matched how the team works.
That's normal engineering: you don't know what the valuable parts are until you
can see them working together.*

*What we found is that the system does three things that are genuinely hard to
replicate any other way: it reads your Drive documents — contracts, quotes,
invoices, in English and French — and surfaces a cross-system money picture and
morning briefing that you simply can't get by opening Monday and Drive side by
side. Those are the three things we're going to demo.*

*The other features — AI date suggestions, roadmap tracking, write-back
workflows — are built and tested, but they turned out to be solving problems
that weren't painful enough. We're putting them on the shelf and focusing on
what actually saves time and catches money.*

*For the site visit, the demo will be 10 minutes: you open a browser, see a
ranked list of what needs attention across every project, click into the
financial picture for a specific job, and ask the system a question about a
contract. Everything you see comes from your actual Drive files — no manual data
entry. From here we tighten that loop and add the next highest-value piece:
flagging payment obligations that are overdue or coming due."*

---

## The one-sentence version

**ALTA does one thing well that no tool in your stack does: it reads your
contracts and tells you, in one screen, where the money doesn't add up.**
Everything else is secondary until that sentence is undeniably true.
