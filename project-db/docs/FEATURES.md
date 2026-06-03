# ALTA (`project_db`) — Feature Overview

*Plain-language description of what the software does today. Written for a
presentation / non-technical audience. Current as of 2026-06 (supersedes the
README's older feature list).*

---

## What ALTA is, in one sentence

ALTA pulls a contractor's scattered operational data — Monday.com boards and
the documents in Google Drive — into one local database, then uses AI to read
the contracts and money in those documents and reconcile them against what the
project boards say, so a project manager can see the real state of a job in one
place.

**What makes it different from a sync tool:** it doesn't just centralize data.
It *reads the documents* — extracting tasks, dates, scope, and dollar amounts —
and tells you where reality and paperwork disagree. The sync is plumbing; the
reading and reconciliation is the product.

---

## The core idea: one canonical record per real thing

Every project, client, task, document, and dollar figure lives once in a
central database with an ID ALTA owns. Source systems (Monday, Drive) map into
it. Google Drive's folder structure is the source of truth for *which project a
document belongs to* (deterministic, by folder — no guessing). This means you
can ask one question and get an answer stitched across tools, instead of opening
six tabs.

---

## Feature areas

### 0. The daily briefing — the landing screen (newest)
When you open ALTA, the first thing you see is a ranked **briefing of what
needs attention** across every project — not a wall of counts. Each line is a
cross-system truth you can't get by opening Monday and Drive in two tabs:

- **Money risk** — a project whose money picture is low-confidence, whose
  confirmed costs exceed its confirmed revenue, or that has a large pile of
  unconfirmed quotes sitting in its folder.
- **Scope gaps** — contract scope items with no matching task.
- **Schedule** — tasks that are overdue and not marked done.
- **Missing paperwork** — an active project with no contract on file.

Items are ranked by severity (high / medium / low) and each links straight to
its evidence. It's **computed deterministically** from data already pulled in —
no AI guessing, no per-question cost — so it's always up to date and never
invents a number. Also available as a one-line command (`project_db briefing`).

### 1. Data sync — Monday.com and Google Drive
- **Monday.com:** pulls every board, item, status, date, owner, and CRM record
  into the canonical database. Recognizes column meanings automatically. Can
  also *write changes back* to Monday (e.g. accepted task dates).
- **Google Drive:** pulls all documents with full metadata (folder, dates,
  size, owner) and links each to its project by folder location. ~750 documents
  across the live workspace.
- Both support fast "delta" sync (only re-pull what changed).

### 2. Document understanding — reading the contracts
- Extracts the **text** of PDFs, Word docs, Excel sheets, and Google
  Docs/Sheets into the database, so the AI can actually read them. Hundreds of
  documents have readable, indexed text.
- This is the foundation that makes everything below possible — the AI reasons
  over real contract language, not guesses.

### 3. AI proposals — timelines and scope (human-approved)
- **Timeline proposals:** most Monday tasks have no dates. ALTA reads the
  contract/schedule and *proposes* start/end dates for dateless tasks, each
  backed by a **direct quoted excerpt** from the source document.
- **Scope proposals:** compares what the contract commits to against the task
  list and flags scope items that have **no matching task** — the work you
  agreed to but isn't tracked anywhere.
- **The AI never acts on its own.** Every suggestion lands in a review queue.
  A human accepts or rejects; only an accepted timeline is written back to
  Monday. Conservative by design — "no suggestion" is a valid answer.

### 4. Ask — plain-language questions
- Type a question; instant canned reports answer the common ones (active
  projects, deal pipeline, docs for a project, tasks without dates, etc.). For
  anything else, a fast AI model reads a database snapshot and answers.

### 5. Financial reconciliation — the money picture (newest, headline feature)
This is the layer that reads the *money* out of Drive documents — because at
this company the quotes and invoices arrive by email and get filed into Drive,
so Drive (not QuickBooks) is the most complete financial source.

- **Extraction:** reads every quote, estimate, invoice, and receipt for a
  project and pulls out each dollar amount with the **verbatim text that proves
  it** — handling English and French (Quebec) number formats (`923,44 $`,
  `1 080.00`, `8k`), taxes (GST/QST/TPS/TVQ), and signs.
- **Two-sided ledger:** separates **money in** (what we quote/invoice the
  client) from **money out** (what contractors/suppliers bill us) — the spread
  is the margin.
- **De-duplication:** internal summary/tracking sheets are excluded from the
  totals (and shown as a cross-check) so they don't double-count the individual
  invoices they restate. Individual invoices are treated as authoritative.
- **Money-type buckets:** sorts amounts into contract revenue, supplier cost,
  tenant-buyout cost, lease/rent, deposit, and tax — so different *kinds* of
  money aren't blindly netted together.
- **Honesty guard:** every extracted amount is checked against the source
  text — anything the AI computed or couldn't verify is flagged for review. And
  when most of a project's money can't be confidently classified (e.g. an
  unusual project type), the reconciliation is **flagged low-confidence**
  instead of showing a misleading margin.

### 6. Local web dashboard
- A browser interface (localhost, single-user) to read everything: project
  overviews, documents with their extracted text, the proposal review queue
  (accept/reject with the evidence shown), a data-integrity audit, and a
  **Financials panel** per project showing the money buckets, margin,
  cross-check, and per-document breakdown with verification badges.

### 7. Command-line tools & data integrity
- A full CLI for every operation (sync, extract, ask, propose, review,
  financials), plus `doctor` (audits the data for problems) and `rebuild`
  (safely re-derives the database from the sources).

---

## What it's good at today vs. where it's honest about limits

**Strong today:**
- Renovation projects: the financial reconciliation is trustworthy end-to-end
  and viewable in the browser.
- Reading scattered, bilingual, messy real-world documents and pulling
  evidence-backed numbers out of them.
- Never inventing data: AI output is gated by human approval and verified
  against source text.

**Honest current limits (flagged, not hidden):**
- Some project types aren't yet modeled financially (e.g. real-estate
  development deals with financing and lease income) — these are *flagged
  low-confidence* rather than shown as a confident margin.
- The agency tenant-buyout margin needs the client-agreed price, which often
  isn't in the documents — the software refuses to invent it.
- Documents include quotes the company *didn't* end up using; distinguishing
  "confirmed" from "just collected" is the next planned feature.

---

## The one-line takeaway

ALTA turns a pile of project boards and a messy Drive full of PDFs into a single
place where a PM can see — with evidence — what a job has committed to, what's
being tracked, and where the money actually is.
