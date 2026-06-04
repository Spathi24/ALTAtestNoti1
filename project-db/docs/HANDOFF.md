# ALTA / project_db — Developer Handoff

**For the next Claude instance.** You have NO memory of prior sessions — only
this file and the repo docs. This document is the consolidated context so you
don't have to re-derive it from the code. It captures what ISN'T in
README / ROADMAP / CHANGELOG / STRATEGY: invariants, the financial layer (the
current centre of gravity), worked-through problems and their solutions, and
guidance for working on this project well.

**Read these first, in order:** `docs/EVALUATION.md` (the honest current-state
assessment + standing rules — the single most useful doc), `docs/FEATURES.md`
(plain-language feature list), then this. STRATEGY.md and ROADMAP.md are older
but give the mission framing.

Last updated: 2026-06-03, at **797 tests**, after **RAG** shipped (the askbot
can now read document text, not just metadata) on top of the deterministic
**attention briefing** (EVALUATION §3/§5 reveal-don't-generate landing) and the
financial extraction + reconciliation layer.

**RAG (newest):** `ai/embeddings.py` (OpenAI `text-embedding-3-small`, mock for
tests), `ai/chunking.py` (paragraph-aware ~500-tok), `ai/rag.py`
(`embed_documents_for` idempotent via content_hash; `retrieve_chunks`
brute-force numpy cosine — NOT sqlite-vec, that's the upgrade path). Vectors in
`DocumentChunk` (float32 blob). `retrieve_chunks` is HYBRID (cosine + keyword distinct-term coverage fused via
reciprocal rank fusion -- catches exact identifiers pure-vector blurs; `hybrid=
False` for cosine-only). `answer_with_llm` injects retrieved excerpts as
citable facts (mode=`rag`, `sources`). CLI `embed-documents` / `rag-search`.
**Embeddings are the ONLY OpenAI use — chat stays Anthropic.** `OPENAI_API_KEY`
in `.env` (gitignored). Full corpus embedded live (462 docs / 5590 chunks /
$0.052). Develop on `MockEmbeddingProvider` (free); a real embed run is cheap
(~$0.02–0.06 whole corpus) and idempotent (unchanged docs skip).
RAG also feeds the **proposal bots** (`generate_timeline_proposals` /
`generate_scope_proposals` take `embedding_provider=`; additive RELEVANT
DOCUMENT EXCERPTS section, conservative posture unchanged, `ProposalBatch.
rag_chunks_used`). `retrieve_chunks` excludes trashed-doc chunks.

**Refresh (`connectors/refresh.py::run_refresh`):** one call = delta-sync the
live connectors (Monday; Drive when live) + re-embed ONLY changed docs
(content_hash idempotent — answers "do we re-embed every change?": no). Every
step guarded/reported, never raises. CLI `project_db refresh [--full]
[--no-embed]`. `serve` runs it in a daemon thread on startup (opt-out
`--no-refresh`) — BACKGROUND-only, never in `create_app` (tests stay offline);
footer shows last-refresh via `web/refresh_state.py`. NOTE: the Drive OAuth
token can expire (`invalid_grant`) — re-run `gdrive-auth`; the refresh reports
it as a non-fatal step and continues.

**The briefing (newest, read this):** `ai/views.py::report_attention_briefing`
is a pure deterministic detector — no LLM, no API, recomputes free over stored
data — that ranks cross-system truths (money risk / scope gaps / overdue tasks /
missing contracts) into one list. Money items compose
`report_project_financials` (never re-sum rows). Surfaced by `project_db
briefing` and as the web `/` landing (`ui_views.attention_briefing`). Detectors
+ thresholds live next to the function; tests in `test_attention_briefing.py` /
`test_web_briefing.py`. It is pure-reveal (no write-back), honoring A8/N2/N8.

---

## 0. The 30-second orientation

ALTA pulls Monday.com + Google Drive into one canonical SQLite DB, then runs an
LLM layer that reads the documents and reconciles them against the boards. The
**financial reconciliation layer is the current product focus and the "draw"**:
it reads quotes/invoices out of Drive PDFs and computes a per-project money
picture. The sync is plumbing; the reading/reconciliation is the point.

The repo root is **`ALTAtest/`**; the package is in **`project-db/`**. Edit
under `project-db/...`. Ignore any `.claude/worktrees/...` — all real work is on
`main` in the main checkout. Push to `origin/main` after meaningful changes.

```
project-db/
  src/project_db/
    ai/          context.py, proposals.py, query.py, views.py, financials.py, providers/
    connectors/  monday/, gdrive/, quickbooks/   (companycam stubbed)
    db/          base.py, models/, migrations.py, session.py
    identity/    resolver.py, matcher.py
    web/         app.py, deps.py, ui_views.py, routes/, templates/, static/
    cli.py       single entry point
    config.py    selective .env loader
  tests/         pytest; conftest.py has fixtures + env stubs (685 tests)
  docs/          EVALUATION.md, FEATURES.md, STRATEGY.md, ROADMAP.md, HANDOFF.md
```

**Python / running things (Windows):** the project runs on **Python 3.13**,
invoked as `py -3.13`. The package is installed editable into that interpreter
(`py -3.13 -c "import project_db"` works; plain `python` on PATH is 3.11 and
does NOT have it). Run tests with `py -3.13 -m pytest <abs-path>/tests -q`.
Console is cp1252 → **ASCII only in any `print()` that lands in scripts/CLI**
(no `→ ✓ ✗ … —` in CLI output; `main()` forces UTF-8 stdout for LLM prose, but
don't rely on it for ASCII-art).

---

## 1. Governing invariants (do not break)

1. **The LLM is an advisor, never an actor.** AI field changes for Monday land
   in the `Proposal` table as PENDING; a human accepts/rejects. `accept` writes
   to Monday FIRST, flips status only on success. **Financial extraction is the
   exception to "advisor" only in that it writes to OUR OWN DB** (FinancialRecord
   rows) — it never touches an external system, so it needs no approval gate.
   The quoted excerpt + verification flag are what make extracted facts
   trustworthy.
2. **Identity is deterministic; uncertainty surfaces in `doctor`, not guessed.**
   Project identity = Drive folder ancestry. Monday boards match INTO Drive
   projects via `ProjectMatcher` (civic-number then exact-name, unique-hit-only).
   A board matching no allowlisted rule is SKIPPED, not guessed. The deleted
   substring matcher caused the "Rockland matches 927 Rockland" bug — never
   reinstate it.
3. **LLM extracts; deterministic code (SQL/Python) computes.** Sums, margins,
   over/under, classification-where-rules-suffice — all deterministic. The LLM's
   job is reading prose and pulling out evidence-backed facts, never arithmetic.
   This is load-bearing for trust (hallucinated math = bad data on the money).
4. **Every extracted amount carries verifiable evidence** (a verbatim
   `quoted_excerpt`) and is checked against the source text (`amount_verified`).
5. **One report chokepoint for money.** ALL financial totals (CLI, web, ask)
   flow through `ai/views.py::report_project_financials`. Nothing else sums raw
   `FinancialRecord` rows. If you add a consumer, call the report, don't
   re-aggregate — otherwise the confirmed-vs-quoted / rollup / confidence logic
   gets bypassed.
6. **Human decisions live separately from extracted data.** The confirmed/quoted
   status is in its OWN table (`document_financial_status`) keyed by document,
   because `extract-financials` deletes+rebuilds FinancialRecord rows on every
   run. Anything a human decides about financial docs must survive
   re-extraction.

---

## 2. THE FINANCIAL LAYER (the big new thing — read this fully)

This is ~all the recent work and is not in README/CHANGELOG yet. Everything
lives in **`ai/financials.py`** (extraction + helpers) and
**`ai/views.py::report_project_financials`** (the aggregation chokepoint), with
models in **`db/models/finance.py`**.

### 2.1 The pipeline

```
Drive doc -> extract-content (DocumentText) -> extract-financials (FinancialRecord)
          -> report_project_financials  -> CLI / web Financials panel / ask
```

Drive is the canonical financial source (per the owner: the CEO gets quotes /
invoices by email and files them in Drive; QuickBooks will NOT have the full
picture). `extract-content` must have run first (financial extraction reads
`DocumentText`, not the raw file).

### 2.2 Schema (`db/models/finance.py`)

- **`FinancialRecord`** — one monetary amount from one document. Schema-light:
  `direction` (`client_in` / `contractor_out` / `unknown`), `doc_role`
  (quote/estimate/invoice/receipt/change_order/other), `record_kind`
  (total/line_item/tax/deposit/other) are validated strings (unknown values
  coerced to a catch-all + warned, never crash). Plus `amount` (Numeric),
  `currency`, `counterparty`, `description`, `phase`, `quoted_excerpt`,
  `confidence`, `amount_verified` (bool), `is_rollup` (bool), `doc_date`,
  `prompt_version`, `source_meta_json` (raw LLM item — keep everything).
- **`DocumentFinancialStatus`** — the human confirmed/quoted decision. Separate
  table, keyed by `document_id`, survives re-extraction. Only docs a human
  explicitly toggled get a row; absence => smart default.
- Migrations for both are in `db/migrations.py::ensure_sqlite_schema` (the
  project has no Alembic; this idempotent helper ALTERs/CREATEs on existing
  SQLite files). Every CLI command that touches the DB calls it.

### 2.3 Extraction (`ai/financials.py::extract_financials_for_project`)

Mirrors the proposal engine. The non-obvious design points (each earned the
hard way — see §4):

- **Candidate selection**: bilingual keyword prior on name+folder + a
  financial-mime gate. Cheap pre-filter; the LLM still reads content. A doc with
  no keyword hit or a non-financial mime (image/CAD) is skipped.
- **Batching**: documents are processed in BATCHES across multiple LLM calls
  (char-budgeted, default ALL candidate docs). A single call over ~15 docs blew
  past the JSON output ceiling and truncated. `_chunk_candidates` greedily fills
  ~14k chars / ≤5 docs per batch.
- **All-or-nothing data safety**: capture prior records, build the new set,
  and only delete+swap on FULL success. A failed batch (rate limit, out of
  credits) keeps the prior records and writes nothing. **Never delete prior
  records up front** — that wiped 189 good records once when the run then 429'd.
- **Backoff retry** only on TRANSIENT errors (`_is_transient`: 429/overloaded/
  timeout). A 400 (billing / bad key) fails fast — don't retry it.
- **Validate-don't-crash**: bad items go to `batch.errors`; `$0` amounts are
  skipped (template noise).
- The prompt: instruction at the TAIL, docs referenced by integer index,
  conservative ("never invent an amount not in the text"), prefer totals /
  ~20 records/doc cap (keeps output bounded so it doesn't truncate).
- **Company identity for direction**: `COMPANY_NAME` env (default
  `"Alta Construction Group"`) is injected so the model can read from/to and
  decide `client_in` vs `contractor_out`. Without it, a client-facing estimate
  on our letterhead was read as a contractor cost (inverted a margin by ~$200k).

### 2.4 amount_verified — the value-based verification guard (§4 saga)

`_amount_in_text(amount, text)` checks the amount's VALUE appears in the source,
not the string. It must tolerate every way Quebec/bilingual docs write numbers:
EN thousands `1,234.56`, FR decimal comma `923,44`, **space thousands**
`$1 080.00` / `17 384,91`, `k`-notation `8k`/`10.5k`, signs `-250` (match abs),
rounding (`549241.8481` → model's `549241.85`), and the qty-vs-thousands
ambiguity (`1 500,00` = qty 1 + price 500,00). `_document_amounts` unions
multiple locale interpretations (raw + de-spaced) and adds k/m-suffix
expansions. **Do not regress this** — it took several real projects to get
right, and it's the difference between meaningful flags and noise. Verified
~99–100% on real corpora; the few remaining flags are genuinely garbled-OCR or
model-computed values (correctly surfaced for review).

### 2.5 is_rollup — deterministic, name-based (NOT the LLM)

Internal summary/tracking sheets (cost trackers, payment logs, statements of
account) restate the individual invoices, so summing both double-counts. They're
EXCLUDED from totals and shown as a cross-check. **An earlier version asked the
LLM to classify primary-vs-rollup; it was unreliable** — it mislabeled a $549k
client estimate as a rollup and dropped it, swinging the margin ~$200k. Replaced
with `_name_is_rollup` (a regex on the doc name: `costs/costing/tracker/payment
log/listing/breakdown/etat de compte/contractors+material`). Conservative and
fail-safe: when in doubt → PRIMARY (included). A wrong include is a visible
cross-check gap; a wrong exclude silently deletes real money. Decision (owner):
**individual invoices/quotes are authoritative; summary sheets are the
cross-check.** Known gap: `budget` sheets (e.g. 3940's "C61 revamp budget.xlsx")
aren't matched — see §5.

### 2.6 money_type — deterministic buckets

`classify_money_type(direction, record_kind, doc_name, folder_path)` →
`contract_revenue / supplier_cost / buyout_cost / lease_rental / deposit / tax /
other`. So different KINDS of money aren't blindly netted. Free (no LLM),
derived at report time. `tenant`/`quittance`/`settlement`/`lease` name+folder
signals drive buyout/lease classification.

### 2.7 Confidence guard

The report computes `classified_ratio` (share of money in interpretable
revenue/cost buckets vs `other`) and `low_confidence` (<50%). When a project
type isn't modeled (6554 is a real-estate DEVELOPMENT deal — asking price, loan,
lease income), the system flags LOW CONFIDENCE instead of showing a
confident-looking margin. This is the key generalization mechanism: it lets the
software be honest about its limits rather than forcing every project to fit.

### 2.8 Confirmed-vs-quoted toggle (built with extreme care — §4)

The owner's team dumps every quote into a project folder, including ones they
didn't go with, so totals include money that never happened. The toggle:

- `document_financial_status` (separate table, survives re-extraction).
- Smart default (owner decision): a doc with an **invoice/receipt** role is
  confirmed (work happened); pure quotes/estimates are unconfirmed until a human
  toggles them. `default_confirmed()` + per-doc roles drive this in the report.
- `report_project_financials` computes BOTH all-in totals (unchanged) and
  `confirmed_totals` / `confirmed_by_money_type` / `confirmation` counts. The
  web panel shows the confirmed margin as the headline KPI; a per-document HTMX
  toggle (`POST /documents/{id}/financial-status`) recalculates it live. That
  route is the ONLY mutation on the financial surface — internal flag only,
  idempotent, no external write, no stale guard needed.

### 2.9 report_project_financials — the chokepoint

Returns: `totals` (all-in direction), `by_money_type`, `money_summary`
(construction_margin + low_confidence + classified_ratio + buyout_note),
`confirmed_totals` / `confirmed_by_money_type` / `confirmed_construction_margin`
/ `confirmation`, `rollup_crosscheck`, `per_document` (with confirmed flags),
and `records` (capped, each with money_type / is_rollup / amount_verified /
confirmed). Uses `_representative_amount` to collapse a (doc, direction) group
so a line item and its document total aren't both counted.

### 2.10 Project types seen so far (and how the system handles each)

| Type | Example | Behaviour |
|---|---|---|
| Renovation (clean) | 1455 St. Mathieu | trustworthy end-to-end; high confidence |
| Tenant-buyout (agency) | 5768 St-Laurent | buyout cost captured; margin needs the client-agreed price, usually NOT in docs → flagged |
| Real-estate development | 6554 St-Hubert | not modeled (financing/acquisition/lease) → LOW CONFIDENCE flag |
| Small / single-doc | 2150 Tupper, 927 Rockland | works on what's there |
| Early-stage (proposed) | 25-1000, 25-1001 | docs are plans/reports/approvals → correctly extracts 0 (no hallucination) |

**Agency buyout model (owner input, not fully built):** in a CLIENT buyout
project, the client pays Alta a SET PRICE per tenant buyout; Alta keeps
(agreed − actual). In an OWN project, a buyout is a pure cost. The agreed price
is typically not in the Drive docs, so we capture `buyout_cost` and do NOT
invent the revenue side. A real buyout margin needs that figure supplied.

---

## 3. The rest of the architecture (still accurate)

### ExternalId + resolver
`resolve_or_create(source, entity_class, external_key, matcher,
create_only_attrs, **attrs)`. A MATCHED path applies attrs (a regression once
left every doc unlinked on `rebuild`). `create_only_attrs` stops Monday from
renaming a Drive-authoritative project. Matchers: `ExactFieldMatcher`,
`FuzzyFieldMatcher` (clients/people only — never projects), `ProjectMatcher`
(civic-number then exact normalized name, unique-hit-only, no substring).

### Drive = project source
`01. PROJECTS/{ACTIVE,INACTIVE,LEADS}/<name>/` — each immediate child is one
Project keyed by folder id; two folders never merge. Files inherit `project_id`
by ancestry. Non-project files get `Document.category` and `project_id = NULL`.

### Monday mirror overlay (subtle)
`column_values` OMITS empty columns. Per-task Status/Timeline often lives on a
linked portfolio item (`board_relation`/`dependency`). `apply_portfolio_mirror_
overlay` walks items + subitems, collects linked ids, fetches mirror values,
enriches the original column_values (native wins over mirror). `_classify_board`
fails closed.

### Roadmap (Layer 2 injection was REMOVED 2026-05-29)
`RoadmapTask` table + `import-roadmap`/`classify-roadmap` CLIs are KEPT (harmless,
queryable via `/db`). But the prompt INJECTION into the proposal bots was
removed: it pushed an architect design-phase workflow into contractor-execution
prompts and produced template-derived flags the PM had to second-guess
(flagged as slop in EVALUATION §3). Do NOT re-add roadmap content to
`_build_timeline_prompt` / `_build_scope_prompt`. Versions: `timeline-v5-quoted`,
`scope-v4-quoted`.

### Proposals (timeline + scope)
`ai/proposals.py`. `generate_timeline_proposals` (dateless Monday tasks → dates,
write-back-able), `generate_scope_proposals` (documented scope with no task,
advisory-only). Conservative; quoted-excerpt evidence required; past-dated
proposals rejected; `accept_proposal` writes to Monday first / flips second.
`_ACCEPTABLE_FIELDS = {"timeline"}`.

### Web UI (M5 + Financials)
FastAPI + Jinja + HTMX + Pico.css, vendored static, no build pipeline,
localhost-only (127.0.0.1, no auth, no CORS, no `--host`). **Service-module
discipline**: every derived value computed in `ai/views.py` (CLI+web shared) or
`web/ui_views.py` (web-only), never in templates/routes. Routes are thin
adapters. Mutations re-read state before writing. The Financials panel
(`/projects/{id}/financials`) renders `report_project_financials`; its body is a
swappable partial (`_partials/financials_body.html`) so the toggle can
re-render it.

### AI providers
`get_default_provider()` (deep/Sonnet, for propose + financial extraction),
`get_fast_provider()` (Haiku, for the `ask` fallback). Resolver:
`LLM_PROVIDER` → anthropic-if-key → mock. `complete_json` retries on bad JSON
AND bumps `max_tokens` on truncation (`finish_reason == max_tokens`/`length`).

### Prompt-philosophy boundary (load-bearing — don't converge them)
Askbot (`answer_with_llm`, Haiku) = assertive, inferential, recommends.
Proposal + financial-extraction bots (Sonnet) = conservative, refuse on
uncertainty, "returning none is correct". Pinned by
`tests/test_askbot_assertive_prompt.py::TestProposalBotsStayConservative`.

---

## 4. Worked-through problems + their solutions (the expensive lessons)

Read this before touching the financial layer — these cost real iterations.

1. **Direction inversion.** A client estimate on our letterhead (`Quoting
   File.xlsx`, $549k) was classified `contractor_out`, flipping the margin to
   −$600k. Cause: the model didn't know which company is "us". Fix: inject
   `COMPANY_NAME` + explicit from/to rules. Result: 5768 went −$600k → +$176k.
   Remaining: genuinely ambiguous docs land as `unknown` (safe). See #12 in §5.

2. **The locale-parsing saga (multiple rounds).** The verification guard kept
   false-flagging real amounts. Each round was a NEW way Quebec docs write
   numbers: PDF-reflow excerpts (switched from verbatim-excerpt to value-based
   check), French decimal commas, space thousands separators, `k`-notation,
   negative signs, rounding, qty-vs-thousands. Solution converged on
   `_document_amounts` unioning interpretations. Lesson: **locale variety is a
   convergent problem (fix once, works for all Quebec docs), not a treadmill.**

3. **Rollup classification was an LLM job → made it deterministic.** The LLM
   over-excluded ambiguous docs. Name-based rule is predictable, auditable,
   cheaper (dropped the classification tokens), and fails safe. Lesson: prefer a
   deterministic rule with a safe failure mode over an LLM guess that fails
   silently.

4. **Re-extraction destroyed data.** The first batched version deleted prior
   records up front; a mid-run failure wiped them. Fix: all-or-nothing. And the
   confirmed-toggle status MUST live in a separate table for the same reason.
   Lesson: **anything humans decide, or that must persist, cannot live on rows
   that get rebuilt.**

5. **Truncation = the cost killer.** A run that truncates resends the whole
   prompt and regenerates, 2–3×. Bounding output (prefer totals, ≤20 records/doc,
   smaller batches) is both a quality and a COST fix. Re-running projects
   repeatedly during dev is what actually drained credits — see §6.

6. **6554 revealed a project type we don't model** (real-estate development).
   The right response was NOT to fine-tune for it — it was the confidence guard
   (flag low-confidence). Lesson: when a project doesn't fit, **flag it, don't
   force it.** This is the antidote to overfitting the owner is (rightly) wary
   of.

7. **The owner is wary of a "fine-tuning treadmill."** Validated by running a
   4th and 5th+ project: the curve flattened (6305 and the small projects needed
   zero new rules). The general mechanisms (locale-tolerant parsing, conservative
   direction, deterministic rules, confidence guard, the human toggle) handle
   variety on their own. Keep choosing GENERAL mechanisms over per-project rules.

---

## 5. Known issues / next steps (so you don't have to rediscover them)

In rough priority. None are urgent; the dominant cases (renovation, buyout) work.

- **#12 — Direction refinement (needs API, ~$0.5–1/project).** 5768's $549k
  estimate + chunks of 655/3940 sit in `unknown` because the model can't always
  tell client-vs-internal. Likely fix: inject the project's CLIENT name (from
  the canonical Project→Client link) into the direction prompt so it can match
  "Client ID: <name>". Needs re-extraction of the affected project to validate —
  hence gated on API budget.
- **#14 — Development/investment project-type money model.** 6554-style deals
  need buckets for acquisition / financing / lease income. For now the
  confidence guard honestly flags them. Build when this type matters enough.
- **`budget` roll-up keyword (free, but it's keyword-tuning).** 3940's "C61
  revamp budget.xlsx" is an internal budget tracker that isn't caught by
  `_name_is_rollup`, so its $400k+ aggregations pollute `other` and tank 3940's
  confidence (which the guard flags). Adding `budget` to the regex is a one-line,
  free recompute — but weigh it against the fine-tuning concern (§4.7). Left
  un-done deliberately; the guard already flags 3940.
- **The strategic question worth answering: is Drive the COMPLETE financial
  source per project?** Several projects show small/partial amounts because the
  main contract isn't financial-readable in their Drive folder (money lives in
  Monday/QB/un-filed email). The financial layer is bankable where Drive is
  complete (1455) and only indicative where it isn't. The confidence flag
  surfaces this per project — that's the right mechanism; the open question is
  whether to invest in pulling the missing pieces from elsewhere (QB live, etc.).
- **Adoption test (the real one, per STRATEGY §9).** The financial layer +
  toggle are built and viewable. The highest-value next move is arguably NOT more
  code — it's putting the Financials panel in front of a real PM and seeing if it
  changes how they work. A PM demo happened ~2026-06-01; their feedback is the
  signal to chase.
- Deferred plumbing (CompanyCam, QB live, webhooks, Postgres, RAG, text-to-SQL):
  per STRATEGY.md, not until the brain is in daily PM use.

---

## 6. API budget reality (important — the owner is credit-constrained)

The Anthropic credits are small and paid by the owner's employer; they run out.
**Default to developing on mocks (free); treat a live extraction as an explicit,
budgeted action.** Numbers: a clean full-project extraction is ~$0.05–0.40
(scales with doc count); truncation retries can push it to ~$1. The whole
21-project portfolio is now extracted (~few dollars total).

**The free-recompute technique** (use it constantly): `is_rollup`, `money_type`,
the confidence guard, and `confirmed` all recompute over already-stored
FinancialRecord rows for FREE — change the logic, re-run the report, verify on
real data without any API. Only **direction** changes need re-extraction (the
LLM assigns direction at extract time). So most financial-logic iteration is
free; reserve API for direction work and for validating on a genuinely new
project. Validate logic via mocks/tests first; do ONE live run to confirm, not
many.

---

## 7. CLI + web route maps (current)

Key CLI (full list: `--help`): `init-db`, `sync monday [--delta]`,
`sync GOOGLE_DRIVE`, `gdrive-auth`, `extract-content`, `ask`, `daily`,
`propose timelines|scope <project>`, `proposals list|show|accept|reject`,
`doctor`, `rebuild --yes`, `serve [--port]`, `import-roadmap`,
`classify-roadmap`, **`extract-financials <project> [--max-docs N]`**
(batched, fresh-snapshot, prints the money-flow + confidence + roll-up
cross-check), **`briefing [--limit N]`** (deterministic portfolio attention
list — money/scope/schedule/docs, ranked; no LLM), **`embed-documents
[--project] [--overwrite] [--limit]`** (chunk+embed for RAG; idempotent; prints
cost), **`rag-search <query> [--project] [--top-k N]`** (retrieval debug), and
**`refresh [--full] [--no-embed]`** (delta sync + re-embed only changed docs),
**`extract-obligations <project>`** (Money-at-Risk extraction), and
**`commitments <project>`** (read-only obligations + status).

Key web routes: `/` (**Attention briefing** — the ranked truths landing),
`/ask` (now **RAG-backed** when docs are embedded — `mode=rag`, cites sources),
`/search` (read-only hybrid corpus search, no LLM tokens),
`/projects`, `/projects/{id}`,
**`/projects/{id}/financials`** (the money panel), `/documents/{id}`,
**`POST /documents/{id}/financial-status`** (the confirmed/quoted toggle —
returns the panel body partial), `/proposals[...]`, `/ask`, `/doctor`, `/db`.
Localhost only.

---

## 8. Testing patterns + footguns (carried forward, still true)

**Testing:**
- `conftest.py` stubs env vars BEFORE importing app modules (tests think
  `LLM_PROVIDER=anthropic`). Any test that could hit `.complete()` must mock the
  provider. `MockLLMProvider(responses=[...])` (sticks on last) or
  `on_call=lambda **kw: ...`. Financial tests build `FinancialRecord`s directly
  for report tests and use `MockLLMProvider` returning `{"records":[...]}` for
  extraction tests.
- Web tests override `db_engine` with `StaticPool` + `check_same_thread=False`
  (FastAPI TestClient dispatches sync routes through a threadpool; SQLite's
  default refuses cross-thread). `patched_session_factory` binds the web
  `session_scope` to the test engine.
- `expire_on_commit=False` → after a CLI/route commits via its own session, the
  outer test `session` has stale attrs; call `session.expire_all()`.

**Footguns that have bitten us (the financial ones first):**
- Don't put human decisions / persistent flags on `FinancialRecord` — it's
  deleted+rebuilt on re-extraction (use a side table).
- Don't sum raw FinancialRecord rows anywhere but `report_project_financials`.
- Don't delete prior records before a batched extraction succeeds (all-or-nothing).
- Don't regress the locale number parsing (`_document_amounts` / `_amount_in_text`).
- `extract-financials` resolves a status-table FK to Document — resolve the
  document BEFORE writing a status row (a bad id would raise instead of 404).
- (Older, still true) Starlette `TemplateResponse(request, name, ctx)` new
  signature; `hx-indicator` inherits down the DOM (put it on the specific
  button); `complete_json` must detect truncation; `markdown` passes raw HTML
  (askbot pre-escapes); `get_default_provider` silently builds Anthropic if a
  key is set; `rebuild` is destructive (preflights connectors first); never
  `git add -A` (the egg-info trap — stage specific files).

---

## 9. How to work on this well (guidance, not rigid rules)

The owner's words: "be sure of yourself but not hardheaded… don't get stuck in
your own rules and sacrifice actual quality of decisions." Take that seriously —
these are defaults, not a cage.

- **Prefer general mechanisms over per-project rules.** Every keyword you add to
  fix one project is a small step onto the fine-tuning treadmill the owner fears.
  When a project breaks, first ask: can the confidence guard / a human control
  handle this, rather than a new rule? (It usually can.)
- **Be honest in the output.** Flag low-confidence, badge unverified amounts,
  return 0 rather than hallucinate. The product's trust comes from knowing what
  it doesn't know. A confident-but-wrong number is far worse than a flagged one.
- **Develop on mocks; budget the API.** Validate logic for free; spend a live
  run only to confirm, and tell the owner the cost.
- **Keep the chokepoints.** One report function for money; one resolver for
  identity; service modules for derived values. These are what keep the codebase
  reviewable as it grows (the owner has flagged rising complexity).
- **Verify against the real data, not just tests.** Because we can recompute over
  stored records for free, prove financial changes on the actual 1455/5768/6554
  data, not only on mocks. That's how every real bug here was caught.
- **When you change something, run the suite and push.** `py -3.13 -m pytest
  <abs>/tests -q` must stay green; commit to `main` (Co-Authored-By trailer);
  `git push origin main`. Don't accumulate uncommitted work.
- **Read EVALUATION.md §6** for the standing ALWAYS/NEVER rules — they encode the
  load-bearing decisions (advisor-not-actor, deterministic identity, read-value-
  before-write-value, no premature connectors). Don't re-litigate them without
  the owner.

Don't over-index on any one of these if it's making a decision worse. Use
judgment. The owner values quality of decisions over rule-following.

---

## 10. Tracking conventions

- Test count in README/this doc is hand-maintained; update when you add tests.
- CHANGELOG newest-on-top; one entry per work session (date + theme + what +
  tests + state).
- Commit messages: imperative, group by concern, mention test count. Co-author
  trailer: `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>` (use the
  model actually running; older commits used Sonnet 4.6).
- Strategic docs to keep current: **EVALUATION.md** (the honest assessment +
  rules), **FEATURES.md** (plain-language features). Both were accurate as of
  2026-06-01.
