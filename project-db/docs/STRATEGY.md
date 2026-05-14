# ALTA Strategy & Decision Manifesto

**Date:** 2026-05-14
**Status:** Active — this document is the strategic source of truth.
**Audience:** Anyone working on this codebase, including future Claude sessions.

This is the answer to the question "what are we actually building and why?"
It overrides any earlier roadmap, plan, or doc that contradicts it.
Re-read it before adding a feature, deciding scope, or pitching the project.

---

## 1. PROJECT VIABILITY

The project is viable, but not for the reason you started it. "Centralized
canonical database across Drive and Monday" framed as a sync problem is
something Zapier, Make, n8n, or a 20-line Airbyte pipeline can do at 70%
quality for $20/month. If that were the goal, you should stop today.

The actual viable problem — and it is real, valuable, and unsolved by
off-the-shelf — is **using LLMs to fill in the data your business runs on but
never bothers to type in.** Monday is 14% complete on task dates. Drive holds
the contracts and scopes of work that contain those dates in prose. No tool
on the market reconciles "what the signed contract promised" against "what
Monday says is happening." That reconciliation, automated, is the unlock.
Everything else — the schema, the connectors, the sync — is plumbing in
service of that.

You are not overcomplicating; you have built the right plumbing for the
wrong stated goal. Refocus the goal on the LLM arbitration layer and the
plumbing immediately becomes load-bearing instead of decorative.

---

## 2. CORE PURPOSE

Stated plainly: **ALTA is a contractor operations brain. It reads your
fragmented operational reality across Monday and Drive, builds one
consistent model of every active project, and answers questions and
proposes corrections that no single tool can.**

It is superior to manual syncing in three concrete ways. First, it sees
across silos — a project manager toggling between four tabs is using human
RAM as the join key; this system makes the join key persistent and
queryable. Second, it has memory — yesterday's state versus today's is
something a human re-derives by re-reading; the canonical store has it
instantly. Third, and most important, it has interpretive power — a PM
scanning a PDF for the slab pour date is doing what an LLM does in two
seconds, and the LLM does it consistently and never gets tired and never
quits. Off-the-shelf iPaaS tools do none of this. Notion and Airtable do
the first two but not the third, and require you to abandon Monday and
Drive — politically impossible.

The honest test of whether it's working: does a PM open this system before
opening Monday? If yes, the system is alive. If no, you've built
infrastructure with no users.

---

## 3. DATA ARCHITECTURE

Stay relational. Stay SQL. Do not introduce a graph database, do not
introduce a document store, do not even introduce Elasticsearch yet. The
relationships in a contracting business are overwhelmingly hierarchical
(Project → Tasks, Project → Documents, Project → Invoices, Client →
Projects) with a handful of many-to-many overlaps (Vendors on Projects,
Users on Tasks). SQL with judicious JSON columns handles this for the next
two years. The schema you already have is correct in shape — thirteen
entities, an ExternalId bridge table, source-system IDs decoupled from
canonical UUIDs. Don't redesign it.

What needs to be added is layered context, not a different paradigm.
Specifically: a `DocumentText` sidecar table for extracted file content
(one row per Document, columns: extracted_text, extraction_method,
extracted_at, token_count); a `Proposal` table for LLM-generated
suggestions awaiting human approval (entity_type, entity_id, field,
proposed_value, confidence, source_doc_ids, status); and an `EntityLink`
table or extended ExternalId rows for soft links the LLM proposes that
aren't hard joins yet (e.g., "this contract mentions a deadline that
probably maps to Task X with 0.7 confidence"). Move from SQLite to Postgres
when you have more than one writer or when you want full-text search and
JSON path queries; that's a one-day migration with the schema you have,
not a rewrite.

How records become one unified record: they don't, at the source level, and
they shouldn't. A Monday item and a Drive file are different *kinds* of
objects — one is a task, one is a document — and you link them by **what
project they belong to**, not by trying to make them identical. The Project
entity is the join nucleus. Every connector's job is to assign each of its
records to the right Project canonical ID, and after that you query across
types via the Project FK. You're already doing this; it works. Resist any
pressure to merge a Monday item with a Drive file into one row — it'll
create a Frankenstein object that loses information from both sides.

---

## 4. SYNC LOGIC

Bidirectional sync with full conflict resolution is the swamp every project
of this kind dies in. Do not enter the swamp. Instead, **declare a source
of truth per entity type** and let writes flow only in one direction per
type. Monday is the source of truth for Tasks, Projects, and CRM entities
(Leads, Deals, Clients). Drive is the source of truth for Documents —
there is no scenario where you want to programmatically create files in
Drive based on Monday changes. QuickBooks, when live, is the source of
truth for Invoices. The canonical DB **reads from all**, writes back to
the source-of-truth system when the system itself is correcting drift
(e.g., an LLM-proposed task due date gets approved → written back to
Monday). One-way reads in both directions; one-way writes in one
direction; conflicts get logged, not silently resolved.

Keep everything. Storage is cheap. Even fields you don't think you need
today — Monday's `creator_id`, Drive's `lastModifyingUser`, file
`md5Checksum` — store them, in either a real column or a `source_meta_json`
blob. The pattern you've already adopted (promoted columns for queryable
fields, JSON blob for everything else) is correct. The cost of re-pulling
because you didn't store something is real; the cost of storing extra text
is zero.

On file content specifically: now is the moment to extend Drive ingestion
past metadata. Add content extraction for the four formats that matter —
Google Docs (export as text/plain), PDFs (PyMuPDF or pdfminer), DOCX
(python-docx), and Excel (openpyxl). Skip everything else, including HEIC
photos and DWG drawings, which are bytes you cannot interpret without
GPT-4V or specialized tooling and which are not where the operational
language lives. Cap at 10 MB per file, store the extracted text in
`DocumentText`, and now you have an LLM-ready corpus tied to projects.
This is the input the AI layer needs to actually produce value; without
it, the LLM is starving.

When the same entity appears in two places — say, a contract amount in
Drive and a budget in Monday — they are not the same field and shouldn't
be reconciled by automation. The contract amount is the *promise*; the
Monday budget is the *current operational number*. They should be
displayed side by side, and a divergence beyond X% should produce a flag,
not a sync.

---

## 5. AI LAYER

Build it in two clearly separated tiers, and do not blur them.

**Tier one is deterministic.** Canned SQL reports against the canonical
schema. "Active projects." "Documents missing for project X." "Tasks
without owners." "Projects where Drive contract amount diverges from
Monday budget by more than 15%." You already started this; finish it.
It's the boring, reliable, daily-use layer that builds trust. Every report
is a stored SQL query plus a result formatter. No LLM. No surprises. This
is the layer your PMs will use ten times a day if it's good.

**Tier two is generative.** Claude (or your model of choice) sits behind a
prompt template that takes a Project canonical ID, pulls its tasks, its
documents, its extracted text, its invoices, its clients — all via SQL —
and produces specific outputs: extracted task timelines from the contract,
gaps between contract scope and current Monday task list, projected
completion date based on percent-complete signal, flagged anomalies. The
output is **always written to the Proposal table first**, never directly
to canonical fields, never directly to Monday. A human approves; the
approval triggers the write-back. This keeps the LLM in advisor mode,
which is the only safe mode for a system that touches money and customer
commitments.

Where the data lives for this to work: the canonical DB is the single
context window builder. When the AI wants to reason about Project X, it
issues SQL queries — give me the project, its tasks, its documents, the
text of those documents, its invoices — and assembles a context block. The
schema doesn't need to do anything special for this beyond having the
joins and `DocumentText`. Eventually you'll want embeddings for semantic
search over documents (`pgvector` extension on Postgres when you migrate),
but not today and not in SQLite.

The Monday-vs-Drive question — same projects, different stores — is now
framed correctly: they are not separate stores. The canonical Project
table is the store. Monday provides its operational view via the Monday
connector; Drive provides its document view via the Drive connector; both
write through the resolver into one Project row with two ExternalId rows
pointing at the same canonical UUID. You already built this. It works.
Don't separate them.

Decisions the AI should be able to optimize, in priority order: (1)
Timeline gap-filling — read contracts, propose dates for Monday tasks
lacking them. This is the single highest-value AI use case because it
solves the 11%-of-tasks-dated problem directly. (2) Scope reconciliation —
does every contract line item have a corresponding Monday task? Flag
missing scope items. This catches forgotten work before it becomes a
margin disaster. (3) Anomaly surfacing — projects where the data tells a
contradictory story (Monday says 80% complete, no recent daily logs, 30%
budget remaining). (4) Eventually: resource conflict detection across
projects, which requires a Resource/Assignment model you don't have yet.

---

## 6. BUSINESS VALUE

The competitive edge claim has to be precise or it's marketing. Here's
what's concretely true if this works.

A project manager at a mid-sized contractor spends roughly two to four
hours a week per active project on cross-tool reconciliation — switching
tabs, copying numbers, re-reading contracts, manually checking that what
was promised is what's being built. Across six active projects that's
twelve to twenty-four hours weekly per PM. Eliminate even half of that and
you free up a working week per PM per month. That's the time-savings
argument.

The error-reduction argument is stronger. The expensive mistakes in
contracting are not typos; they're forgotten scope items, missed deadlines
that trigger penalty clauses, invoices that don't get sent because a
milestone wasn't marked complete, and crew showing up to a site where the
materials weren't ordered. Every one of those mistakes is a
data-consistency failure across two or more systems. The AI-driven
reconciliation layer turns those failures into flagged anomalies before
they become invoiced losses. Saving one missed change order per quarter —
typical value $5K-$25K for residential construction work — pays for the
entire system many times over.

The decision-quality argument is the longest-term and the hardest to
quantify but ultimately the largest. Once your operational reality is
queryable, you can answer questions you currently cannot: which clients
have the best margin per dollar of project effort, which vendors deliver
on time, which job types systematically under-bid. That's not automation;
that's becoming a data-informed contractor in an industry where almost no
one is. That is genuinely an edge, and it compounds — every project synced
makes the next decision better.

What you should not claim, and what your CEO should not believe: this will
not replace PMs, it will not run projects autonomously, and it will not
give you a moat against a competitor who hires a better PM. It will,
however, let a five-person operations team run what otherwise needs eight.

---

## 7. VERDICT

Continue. The schema, connectors, identity resolver, and data hygiene work
you've built are the right foundation, and starting over would discard six
weeks of correct infrastructure to re-derive the same correct
infrastructure. But ruthlessly narrow scope: no new connectors (CompanyCam
and QuickBooks-live stay on the shelf until Monday+Drive produce daily
value), no text-to-SQL natural language layer yet, no Postgres migration
yet. Build content extraction, build the Proposal table, build the
LLM-driven timeline-filling and scope-reconciliation features for real,
and put them in a CLI workflow a non-technical PM will actually use. If
that doesn't get adoption within four to six weeks, then re-evaluate; if
it does, you have a moat.

---

## Executive Summary

ALTA is on the right track but with the wrong stated mission. Framed as a
sync tool, it's redundant with Zapier and not worth building. Framed as an
LLM-powered operations brain that reads your contracts, compares them to
what's being built, and proposes corrections — it's a genuinely novel tool
no off-the-shelf product delivers, and the infrastructure you've built so
far is precisely what such a tool needs. The path forward is not more
connectors or fancier sync; it's content extraction from Drive documents,
an AI layer that proposes timeline and scope corrections, and a
human-in-the-loop approval workflow that writes those corrections back to
Monday. Done well over the next month, this saves your PMs roughly a
working week each per month, catches the kinds of mistakes that lose
contractors real money, and gives the business a queryable operational
memory no competitor will have. Continue, but stop building plumbing and
start building the brain.

---

## Operating Principles (Quick Reference)

Distilled from the above for daily use. When tempted to add a feature,
check it against these:

1. **The schema is right. Don't redesign it.** Thirteen canonical entities
   plus ExternalId. Add tables (`DocumentText`, `Proposal`, `EntityLink`)
   rather than reshaping existing ones.

2. **Project is the join nucleus.** Never merge a Monday item with a Drive
   file. Link them through their shared `project_id`.

3. **One source of truth per entity type for writes.** Monday → Tasks,
   Projects, CRM. Drive → Documents. QB → Invoices. Reads come from
   everywhere; writes go to exactly one place.

4. **Keep everything.** Storage is cheap. Promote queryable fields to
   columns, dump the rest in `source_meta_json`.

5. **The LLM is an advisor, never an actor.** All AI-generated changes go
   to a `Proposal` table for human approval. No silent writes to Monday.

6. **Tier-one (canned reports) before tier-two (LLM).** Build trust with
   deterministic SQL first. The LLM layer assumes the structured layer
   already works.

7. **Don't add connectors until the existing ones produce daily value.**
   CompanyCam and live QuickBooks are deferred until Monday+Drive is
   actively used by a PM.

8. **No new tech.** No graph DB, no document store, no Elasticsearch, no
   Postgres yet, no pgvector yet, no text-to-SQL yet. Add them when SQL
   limits actually bite.

9. **The success test is adoption, not features.** If a PM opens this
   system before opening Monday, it's working. If not, no amount of
   schema elegance matters.

10. **Stop building plumbing. Start building the brain.**
