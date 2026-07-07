# ScopeContext — Transition Plan (repo-grounded, NO implementation yet)

**Status:** approved in direction 2026-07-07; corrections applied (owner review).
This is the ONE dedicated plan+state doc for the ScopeContext migration (per
CLAUDE.md doc discipline). Companion maps:
[`FINANCIAL_SPINE_MAP.md`](FINANCIAL_SPINE_MAP.md),
[`alta_financial_spine.ump`](alta_financial_spine.ump) — **domain maps, not
schema mandates.** The repo *migrates toward* them in isolated,
compatibility-preserving slices; it is never forced isomorphic in one change.

**The architectural question this station answers:**
> What is the smallest *additive* ScopeContext foundation that gives a stable
> migration seam for the rest of the financial spine **without** forcing
> SowItem, quote, budget, PO, and report migrations in the same slice?

**Answer (the seam), narrowed per review:** a new additive `ScopeContext` table
+ **exactly two additions on `Document`**: `scope_context_id` (nullable FK) and a
`context_resolution_state` (a real state, not prose). Context binding is derived
**deterministically from a registered context-root folder mapping** (never
"first subfolder", never LLM). **No other table gets a context FK in SC-1** —
SowItem/quote/budget/FLI inherit context through their established ownership in
*their own later slices*, when that ownership model is actually settled. The
pilot's 111 SowItems are **not touched** until SC-5.

**Framing correction (owner, 2026-07-07):** 923 / 927 / exterior are **one
project, one client** — coherent scope boundaries with employees, materials and
financing flowing *freely* between them. They are **not** isolated sub-projects.
Neither `$66,539.65` (923 signed) nor `$191,843.68` (927) is a project aggregate;
there is no authoritative aggregate contract value yet. `Project.contract_amount`
is a **temporary legacy containment display**, not a semantic total.

---

## A. CURRENT-STATE INVENTORY (grounded in the real repo + pilot DB)

Every place that assumes **one Project == one scope/contract boundary**.
Urgency: **BLOCKING** (SC-1), **EARLY** (first few slices), **LATER** (its own
consumer slice), **NO CHANGE**.

| # | Dependency (file:sym) | Current assumption | Why ScopeContext touches it | Urgency |
|---|---|---|---|---|
| 1 | `db/models/work.py:57` `Project.contract_amount` | one contract $ per project | contract belongs to a context's governing agreement, not the project | **EARLY** (semantics), LATER (retire) |
| 2 | `web/ui_views.py:196` finance contract line | shows `project.contract_amount` | must read context/agreement amount, or stay labelled "signed contract on file (923)" | LATER |
| 3 | `ai/views.py:283,1506` + `ai/context.py:255` serializers | emit `contract_amount` as *the* project number | consumers (askbot, API) misread one number for a multi-context project | LATER |
| 4 | `connectors/monday/connector.py:726` (read) `:754,:778` (write) + `column_extractor.py:280` | Monday owns `Project.contract_amount`, bidirectional | **next Monday pull overwrites the containment value** | **SC-0.5 (now)** |
| 5 | `db/models/sow.py` `SowItem`/`SowPackage.project_id` (NOT NULL) | scope owned directly by Project | target ownership passes through context (via SowVersion) | LATER (SC-5/6) |
| 6 | `db/models/sow.py:99` `uq_sow_item_project_item_code` | `item_code` unique per **project** | two contexts each numbering `SOW-001…` collide; latent (only 1 SOW ingested) | **EARLY** (before 2nd-context SOW ingest; lands SC-5) |
| 7 | `ai/sow_ingest.py` `ingest_sow_workbook(session, project, …)` | one SOW universe per project; idempotent *replace by project* | must ingest INTO a context; "replace" scoped to context (else re-ingesting 923 nukes 927) | **EARLY** (SC-6) |
| 8 | `ai/quote_document_resolver.py` `resolve_quote_document` | resolves project + package by `project.code` + division | package/vendor/ref must resolve within context | LATER (SC-6) |
| 9 | Phase-4 `SOW_Item_Ref` resolution (`subcontractor_quote_ingest.py`) | `SOW-025` → one SowItem per project | ambiguous once codes repeat across contexts | **EARLY** (couples #6, SC-5) |
| 10 | `db/models/finance.py` `SubcontractorQuote.project_id` | quote owned by project | quote inherits context **through SowPackage**, not a direct FK | LATER |
| 11 | `ai/purchase_order_award.py:67` `_next_po_number` `{code}-{PPP}` | PO numbering per project | **keep** — PO number is an identifier; context lives on the quote/package | **NO CHANGE** |
| 12 | `db/models/finance.py:520` `uq_budget_snapshot_line_division` (`snapshot_id`,`division_code`) | one budget line per division per snapshot | collision across contexts sharing a division — **decision deferred to SC-7** (see §D SC-7) | LATER (SC-7) |
| 13 | `ai/green_sheet.py:79` `report_green_sheet(session, project_ref, snapshot_id)` | aggregates the whole project across divisions | needs optional context filter; project aggregate only when meaning is explicit | LATER (SC-7) |
| 14 | `ai/views.py:74` `_resolve_project` (+ email/telegram/proposals resolvers) | ref → one Project | keep — project resolution is correct; context is an additive *sub*-resolution | **NO CHANGE** (project) |
| 15 | `connectors/gdrive/connector.py:599` `_resolve_project_folder` ("one folder = one project, full stop") | project = top project folder via `ExternalId folder:<id>` | keep the anti-merge rule; context binding operates *below* it via a **registered** mapping | **NO CHANGE** (project) |
| 16 | `Document.project_id` + `Document.folder_path` | doc attributed to project by folder | context bound via a **registered context-root mapping**; resolution recorded as an explicit state | **SC-1/SC-2/SC-3** |
| 17 | `db/models/finance.py` `FinancialLineItem.sow_item_id` (app-level FK on real DB) + `.phase` col | cost links to a per-project SowItem; a `phase` string already exists | cost inherits context via its SowItem/quote/allocation; `phase` is a **different axis** — keep, don't conflate | LATER |
| 18 | `scripts/demo_rockland.py` + pilot backfill | seed one project / one SOW universe | demo still works; backfill becomes context-aware (additive, Documents-only in SC-2) | EARLY |
| 19 | Tests constructing one project + one SOW | fixtures assume project-level scope | keep passing under compatibility (NULL FK + LEGACY_UNSCOPED); add context fixtures later | LATER |
| 20 | `PurchaseOrder.contract_amount` (`finance.py:454`) + `contract_amount_estimate` (Monday report) | **distinct** columns, NOT the project contract | **NO CHANGE** — flagged only to prevent conflation with #1 | **NO CHANGE** |

**Standard vs pilot Drive layout (grounds correction #2).** The *standard*
project folder (`docs/templates/NAMING_CONVENTIONS.md` §Folder structure) uses
**organizational** subfolders — `SOW/`, `SOW/packages/`, `quotes/`, `POs/`,
`budget/`, `green-sheet/`, `JOBCOST/`, `actuals/`. Those are DOCTYPE roots, **not
contexts.** The pilot instead has *legacy* context-like subfolders under the one
project folder `.../ACTIVE/923-927 Rockland/`: `923 Rockland/`, `927 ROCKLAND/`,
`EXTERIOR/` (+ 7 docs with NULL `folder_path`). Therefore a generalized resolver
**must** consult a registered/known context-root mapping — never "first subfolder
== context", which would turn `SOW/` into a context.

**Pilot identity facts:** Project `2026001` "923-927 Rockland", legacy `923`,
aliases `["Rockland","Tanya","923 Rockland","923-927 Rockland"]` ("927" resolves
via name-substring, not alias), `property_id` NULL. 111 SowItems
(`SOW-001…111`, all distinct — one consolidated 923-interior+exterior file; 927
not yet ingested as SowItems), 13 SowPackages. `contract_amount` is **not**
summed anywhere across projects.

---

## B. TARGET INVARIANTS (minimal — do not invent future fields)

1. A `Project` contains **one or more** `ScopeContext`s.
2. A `ScopeContext` names a coherent scope boundary (site / unit / area / phase
   / contract-scope). Contexts under a project are **additive/parallel**, not
   revisions of each other.
3. **Revisions of one scope stay within that context** (a future SowVersion
   belongs to exactly one context).
4. Document authority is compared **within `(scope_context, document_role)`**,
   never globally — but **authority is a property of a source/SowVersion within a
   context**, *not* of the `ScopeContext` row itself.
5. **Context attribution is an explicit state**, not the absence of a value.
   `context_resolution_state ∈ {LEGACY_UNSCOPED, RESOLVED, UNRESOLVED,
   NOT_APPLICABLE}` (names may follow repo convention). **`UNRESOLVED`
   (quarantine) is observably different from `LEGACY_UNSCOPED`**, even though
   both may have `scope_context_id IS NULL`.
6. Unknown context is `UNRESOLVED` — deterministic (registered folder mapping) or
   unresolved. **Never** an LLM guess, never a silent default.
7. `Project.code` remains **the** project code. No second project-code concept.
8. Resources (labour, materials, financing) flow **freely across contexts of the
   same project** — contexts partition *scope/authority*, not *cost sharing*.
9. Project-level aggregation across contexts is allowed **only when its meaning
   is explicit**, never an implicit silent sum of unrelated scopes.
10. ScopeContext must **not** break current folder→project or ref→project
    resolution (additive sub-resolution).
11. A `ScopeContext` has a **stable project-scoped identity** (`context_key`),
    independent of its human `label`. `UNIQUE(project_id, context_key)`.

---

## C. TRANSITION STATES

| State | What is true | Authoritative representation | Anti-double-count rule |
|---|---|---|---|
| **CURRENT** | scope/finance owned by `project_id`; no context exists | `project_id` on SowItem/quote/budget/FLI/Document | single level; nothing to reconcile |
| **TRANSITIONAL** | `ScopeContext` exists; `Document` carries `scope_context_id`+state; other tables still project-level | Documents: **`RESOLVED` ⇒ context-level; `LEGACY_UNSCOPED`/`UNRESOLVED`/`NOT_APPLICABLE` ⇒ project-level (legacy)**. All other tables: project-level. | a document is counted at one level only; scope/finance stay project-level until their own slice migrates |
| **TARGET** | context-sensitive scope/contract/finance; SowVersion under context; authority resolved per `(context, role)` | `scope_context_id` (+ SowVersion) authoritative where set; project aggregates are explicit folds | aggregation is an explicit fold over contexts; project-level contract interpretation retired |

**Compatibility rule preventing double creation:** context creation is keyed on
`(project_id, context_key)`; a document binds to at most one context; re-running
never creates a parallel context or re-parents existing rows. A row is
authoritative at exactly one level, chosen by its resolution state — never both.

---

## D. SLICE PLAN (dependency-ordered; refined after inspecting the repo)

> Each slice: purpose · files · schema · migration/backfill · idempotency ·
> compatibility · tests · manual DB verify · rollback/risk · non-goals · prereq ·
> unlocks. **SC-0 is this document.**

### SC-0.5 — Monday contract_amount guard — **DONE** (commit 3e52c0f)
- **What was actually implemented:** `contract_amount` added to the project
  upsert's existing `create_only_attrs` set in
  `connectors/monday/connector.py::_upsert_project` (alongside `name`).
- **HONEST SEMANTIC EFFECT — this is a connector-WIDE behaviour change, not a
  Rockland-only guard:**

  ```
  OLD:
  Monday may update Project.contract_amount on existing projects.

  TRANSITION (now):
  Monday may POPULATE contract_amount on project creation,
  but may NOT overwrite it on any subsequent sync -- for EVERY project,
  not only 2026001.

  REASON:
  Project-level contract ownership is semantically unresolved while
  ScopeContext / agreement ownership is being established (SC-8 retires this).
  ```

  This is acceptable (arguably preferable) because project-level contract amount
  is now semantically suspect, but it must not be described as merely protecting
  the pilot's `$66,539.65`. It changed Monday's ownership of the field globally.
- **Tests:** `test_connector_sync.py::TestMondayContractAmountGuard` — a re-sync
  carrying a different `contract_amount` does not overwrite the stored value;
  `budget_amount` (not guarded) still updates normally.
- **Rollback:** remove `contract_amount` from the set. **Superseded by:** SC-8.

### SC-1 — additive ScopeContext model + Document binding fields (schema only)
- **Purpose:** create the seam. No behaviour change.
- **FK-surface classification (correction #3) — what SC-1 does and does NOT add:**

  | Candidate FK | Classification | SC-1? |
  |---|---|---|
  | `Document.scope_context_id` | **REQUIRED DIRECT ASSOCIATION** — the evidence layer is what we bind deterministically first | **YES** |
  | `sow_item.scope_context_id` | OWNERSHIP, but ownership model unsettled until SowVersion | No → SC-5 |
  | `sow_package.scope_context_id` | OWNERSHIP (likely the natural scope-owning unit) but unsettled | No → SC-5/6 |
  | `subcontractor_quote.scope_context_id` | INHERITABLE via SowPackage | No → later |
  | `financial_line_item.scope_context_id` | INHERITABLE via SowItem/quote/allocation | No → later |
  | `budget_snapshot.scope_context_id` | PREMATURE — context semantics undecided (SC-7) | No → SC-7 |

- **Files:** `db/models/scope.py` (new `ScopeContext`), `db/migrations.py`
  (CREATE TABLE + two additive `document` columns), model `__init__` imports.
- **Schema:**
  - `scope_context`: `project_id` FK (NOT NULL), **`context_key`** (stable,
    project-scoped id, e.g. `923_INTERIOR`), `label` (mutable display),
    `kind` (site/unit/area/phase/contract — free string for now), `site`,
    `unit_area`, `phase`, `source_meta_json`. `UNIQUE(project_id, context_key)`.
    **No `authority_state`** (authority lives on a source/SowVersion within
    `(context, role)`, not on the context — correction #4).
  - `document`: `scope_context_id` (nullable FK) + `context_resolution_state`
    (default `LEGACY_UNSCOPED`).
- **Migration/backfill:** DDL only; **no row writes.** Works on both `create_all`
  (tests) and existing-SQLite ALTER path. Existing documents default to
  `LEGACY_UNSCOPED` (not `UNRESOLVED`).
- **Idempotency:** column/table adds guarded by existence checks.
- **Compatibility:** every reader ignores the new columns → zero behaviour change;
  suite byte-identical; all financial counts unchanged.
- **Tests:** model construction; `UNIQUE(project_id, context_key)`; migration
  idempotency; `create_all` parity; document defaults (`NULL` FK +
  `LEGACY_UNSCOPED`).
- **Manual verify:** columns/table exist on real DB after migrate; every existing
  document `scope_context_id IS NULL` and state `LEGACY_UNSCOPED`; suite green;
  green-sheet/margins numbers identical.
- **Rollback:** additive; inert; no data lost.
- **Non-goals:** no backfill, no other-table FKs, no consumer changes, no
  uniqueness changes, no authority logic.
- **Prereq:** SC-0.5. **Unlocks:** everything.

### SC-2 — deterministic pilot context backfill (data, additive, Documents only)
- **Purpose:** materialize the 3 pilot contexts; bind Documents. **Do NOT touch
  the 111 SowItems.**
- **Files:** `scripts/backfill_scope_contexts.py` (new, one-shot, idempotent).
- **Backfill:** create `ScopeContext(context_key = 923_INTERIOR | 927_UNIT |
  EXTERIOR)` for the pilot; bind each `Document` via the **registered** pilot
  folder map (`923 Rockland/`→923_INTERIOR, `927 ROCKLAND/`→927_UNIT,
  `EXTERIOR/`→EXTERIOR) → `RESOLVED`; NULL/ambiguous `folder_path` →
  `scope_context_id` NULL + **`UNRESOLVED`** (real quarantine, not
  `LEGACY_UNSCOPED`).
- **Idempotency:** keyed by `(project_id, context_key)`; re-run creates nothing
  new, re-binds identically.
- **Compatibility:** SowItems/quotes/budget untouched → all reports unchanged.
- **Tests:** backfill on a synthetic project with the real folder shapes; re-run
  no-op; NULL-path docs land `UNRESOLVED`; resolved counts match the folder_path
  census.
- **Manual verify:** 3 contexts on pilot; per-context document counts match; 7
  NULL-path docs `UNRESOLVED`; **backup DB first**.
- **Rollback:** delete the 3 contexts + reset doc FK/state.
- **Non-goals:** no SowItem re-parenting, no authority logic, no generalized
  resolver.
- **Prereq:** SC-1. **Unlocks:** SC-3, SC-5.

### SC-3 — generalized document→context binding (registered mapping) + quarantine
- **Purpose:** make binding reusable via a **registered/deterministic
  context-root mapping**, NOT "first subfolder == context".
- **Files:** `ai/scope_context_resolver.py` (new; consults a per-project
  registered context-root map / known context roots; unique-or-`UNRESOLVED`,
  Home-Depot-linker discipline). Additive post-step in the Drive ingest path.
- **Rule:** only registered context roots yield a context; organizational folders
  (`SOW/`, `quotes/`, `POs/`, `budget/`, `JOBCOST/`, `actuals/`, ALTA-generated)
  and anything unknown → `UNRESOLVED`. No LLM.
- **Compatibility:** sets FK + state only; never moves `project_id`.
- **Tests:** registered root → `RESOLVED`; organizational/unknown → `UNRESOLVED`;
  ambiguous → `UNRESOLVED`; never guesses.
- **Manual verify:** re-run on pilot reproduces SC-2 bindings exactly.
- **Rollback:** reset FK/state. **Non-goals:** no LLM, no authority ranking, no
  new folder convention (that is a future SOP decision).
- **Prereq:** SC-2. **Unlocks:** SC-4.

### SC-4 — context-aware authority (scoped comparison) — **LATER, not bundled**
- No authority-resolver module exists yet (TARGET in the map). SC-4 is either the
  first authority-resolver build, scoped context-aware from day one, or deferred
  until commissioned. Recorded LATER. **Prereq:** SC-3. **Unlocks:** SC-5.

### SC-5 — SowVersion + context ownership of scope
- **Purpose:** scope ownership passes through context; introduce `SowVersion`;
  add `SowItem.scope_context_id`; change `item_code` uniqueness to
  `(project, context, item_code)`.
- **Scope-semantics correction (correction #5) — three independent axes, NOT one
  enum:**
  - `scope_state ∈ {INCLUDED, EXCLUDED, PROPOSED, UNRESOLVED, SUPERSEDED}` —
    **no `CLIENT_RESPONSIBILITY` value here.**
  - `responsibility ∈ {GC, CLIENT, SUBCONTRACTOR, SUPPLIER, SHARED, UNKNOWN}`.
  - `action_role ∈ {SUPPLY, INSTALL, DESIGN, INSPECT, COORDINATE, DEMOLISH,
    REPAIR}`.
  - Example: *Supply shower glass* = `INCLUDED / CLIENT / SUPPLY`; *Install shower
    glass* = `INCLUDED / GC / INSTALL`. Explicit exclusion = `EXCLUDED`. Exterior
    planning = `PROPOSED`/`UNRESOLVED`.
- **Files:** `db/models/sow.py`, `db/migrations.py`, `ai/sow_ingest.py`.
- **Schema:** new `sow_version`; replace `uq_sow_item_project_item_code` with a
  context-scoped partial index; `SowItem.sow_version_id` (nullable in transition);
  the three scope-axis columns.
- **Migration/backfill:** assign existing pilot SowItems to their context (signed
  inclusions/exclusions → 923_INTERIOR; exterior planning rows → EXTERIOR);
  OHP/contingency rows demoted out of scope (pricing policy, not physical work).
  Idempotent.
- **Compatibility:** `SOW_Item_Ref` resolution becomes context-aware; legacy
  unscoped items still resolve project-wide until migrated.
- **Risk:** **highest-churn slice** — item_code/ref coupling (#6+#9) lands here
  together, deliberately.
- **Prereq:** SC-2 (+ this scope-axis decision). **Unlocks:** SC-6.

### SC-6 — migrate SOW/quote consumers incrementally
- Files: `ai/sow_ingest.py` (takes a context; replace scoped to context),
  `ai/quote_document_resolver.py`, `subcontractor_quote_ingest.py`
  (context-aware package/vendor + ref). Callers without a context fall back to
  project-level. **Prereq:** SC-5. **Unlocks:** SC-7.

### SC-7 — context-aware financial/report surfaces (+ budget-uniqueness decision)
- **Budget-uniqueness decision (correction #6) — made HERE, not assumed in
  SC-1:** first decide whether
  - (a) a `BudgetSnapshot` belongs to **exactly one** `ScopeContext` (then lines
    inherit context and `(snapshot, division)` **remains sufficient**), or
  - (b) a `BudgetSnapshot` may **intentionally span** contexts (then lines need
    `(snapshot, context, division)`).
  Record the chosen option and only then touch `uq_budget_snapshot_line_division`.
- Files: `ai/green_sheet.py` (optional `scope_context_ref`), `web/ui_views.py`
  (contexts surfaced; explicit "all contexts" fold), `db/models/finance.py` (only
  if option (b)), serializers. No-context call = today's project aggregate,
  relabelled as an explicit all-contexts fold. **Prereq:** SC-6. **Unlocks:** SC-8.

### SC-8 — retire/constrain legacy project-level assumptions
- `Project.contract_amount` project-level interpretation retired; contract lives
  on a context's governing agreement; reconcile the Monday round-trip (removes the
  SC-0.5 guard by superseding it). **Prereq:** all consumers migrated.
  **Unlocks:** WorkRequirement station.

---

## E. PILOT RECONCILIATION (define contexts; do NOT merge or delete data)

| Context (`context_key`) | Evidence (in DB) | Authority | Amount |
|---|---|---|---|
| **923_INTERIOR** | `SOW 923 Rockland`, `Final SOW.pdf`, `ACCEPTED QUOTE`, Estimate #25008 | **signed scope** (highest) | **$66,539.65** pre-tax |
| **927_UNIT** | `927 QUOTE`, `927 Av. Rockland – Pour construction` | quote/estimate; **contract authority NOT established** | ~$191,843.68 pre-tax |
| **EXTERIOR** | `SOW - EXTERIOR`, `EXTERIOR QUOTE (NOT STARTED)`, landscape | planning / quote-seeking; **not approved base contract** | ~$4k (indicative) |

- **They are one project** — resources shared; contexts partition scope &
  authority, not cost-sharing.
- **Do NOT delete/rewrite the 111 SowItems while planning.** The mixed rows *are*
  the migration evidence. When cleanup runs (SC-5), using the **three axes**:
  - signed **inclusions** → 923_INTERIOR, `scope_state=INCLUDED`;
  - signed **exclusions** → `scope_state=EXCLUDED`;
  - **client-supplied** → `scope_state=INCLUDED, responsibility=CLIENT`
    (**not** a scope_state; distinct from exclusion);
  - **exterior planning** → EXTERIOR, `scope_state=PROPOSED`/`UNRESOLVED`;
  - estimate-derived **OHP/contingency** → cost-policy, **not** physical SOW work
    items (retained as pricing-policy evidence, removed from scope).

---

## F. CI / CHANGE DISCIPLINE (every implementation slice)

Clean git start → record baseline targeted + full-suite status → **backup real
pilot DB before any migration/backfill** → schema works on both `create_all` and
existing-SQLite ALTER paths → backfills idempotent → no broad renames / unrelated
cleanup → **one writer path per entity** → parsers stay free of DB
identity/business logic → targeted tests first, full suite before commit →
**manually inspect the real pilot DB after mutation** → verify no duplicate /
financial double-count / **all pre-existing counts unchanged** → update
`PROJECT_STATE.md` + `HANDOFF.md` with distilled completed reality only → one
logical slice per commit → push only when green + verified.

### Migration ledger

| Legacy assumption | Transitional compatibility | Target replacement | Retirement condition |
|---|---|---|---|
| `Project.contract_amount` = the project number | **SC-0.5 guard** so Monday can't clobber it; labelled "signed contract on file (923)" | context/agreement-owned contract amount | retire project-level interpretation when ui_views + serializers + askbot + Monday all read context/agreement amounts (SC-8) |
| Monday owns `Project.contract_amount` (read+write) | SC-0.5 minimal guard | Monday field maps to a context's agreement, or is decoupled | when contract lives on the agreement (SC-8) |
| `Document` context = absence of value | `context_resolution_state` distinguishes `LEGACY_UNSCOPED` vs `UNRESOLVED` vs `RESOLVED` vs `NOT_APPLICABLE` | `RESOLVED` with `scope_context_id` | when binding is complete for a project |
| `item_code` unique per project | latent (only 1 SOW ingested) | unique per `(project, context)` | when a 2nd context SOW is ingested (lands SC-5, must precede that ingest) |
| `SOW_Item_Ref` resolves per project | resolves per project while codes globally unique | resolves per context | with the uniqueness change (SC-5) |
| `BudgetSnapshotLine` unique `(snapshot, division)` | one context has budget today | **decided in SC-7**: keep `(snapshot,division)` if snapshot-per-context, else `(snapshot,context,division)` | SC-7 decision |
| `report_green_sheet` = whole-project | no-context call = explicit all-contexts fold | optional `scope_context_ref` | when finance UI surfaces contexts (SC-7) |
| SowItem/SowPackage own by `project_id` | project-level (no context FK yet) | owned via context/SowVersion | when SOW consumers migrated (SC-5/6) |

---

## G. PRE-MORTEM (failure modes already visible — see, don't solve, in SC-1)

1. **Monday clobber (highest, active):** next `monday_demo.py pull` overwrites
   the containment value — handled as **SC-0.5** before SC-1.
2. **Quote/package resolvers receive only `project_id`** — context-blind; must not
   silently bind a 927 quote to a 923 package (SC-6).
3. **`item_code` project-uniqueness (#6)** — collides when a 2nd-context SOW
   arrives; must change *before* that ingest (SC-5).
4. **`SOW_Item_Ref` ambiguity (#9)** across contexts — couples to #3.
5. **`BudgetSnapshotLine (snapshot, division)` (#12)** — do **not** pre-lock a new
   uniqueness in SC-1; the snapshot-per-context vs snapshot-spanning decision is
   SC-7.
6. **PO numbering stays project-level (#11)** while commitments become
   context-aware — intended; reports attribute a PO to its context via the
   quote/package, not the number.
7. **`FinancialLineItem.sow_item_id`** app-level-only FK on the real DB — context
   inheritance rides on it; verify integrity before relying on it.
8. **Drive attribution (#15/#16):** "one folder = one project" stays; context uses
   a **registered** mapping, not "first subfolder". Organizational folders
   (`SOW/`, `quotes/`, …) must never become contexts. NULL `folder_path` → quarantine.
9. **Aliases resolve 923 & 927 to one project** — correct; nothing infers
   *context* from an alias.
10. **Reports aggregating unrelated contexts** — only explicit folds allowed.
11. **111 SowItems duplicated during backfill** — SC-2 binds **Documents only**;
    no re-parenting until SC-5.
12. **`contract_amount` double-count** — one level authoritative at a time.
13. **NULL-context ambiguity** — solved by `context_resolution_state`;
    `LEGACY_UNSCOPED` ≠ `UNRESOLVED` even when both have NULL FK.
14. **Context inference drifting into LLM guessing** — forbidden; registered
    deterministic mapping or `UNRESOLVED`.
15. **Generated Drive artifacts re-entering ingestion** — future write-back risk
    (origin=ALTA + checksum guard); noted, not solved here.

---

## The smallest stable seam (the answer, restated)

**SC-1** is the whole foundation: an additive `ScopeContext` table
(`UNIQUE(project_id, context_key)`, no context-level authority) plus **two
`Document` columns** — `scope_context_id` (nullable) and `context_resolution_state`
(`LEGACY_UNSCOPED` default). **SC-2** binds the pilot's Documents deterministically
via a registered folder map (quarantining the rest as `UNRESOLVED`). No other
table gets a context FK, no scope rows move, no report changes. Every later
station (SowVersion, quotes, budget, reports, WorkRequirement) attaches context
*when its own slice establishes the ownership model* — zero forced migration,
zero behaviour change on day one. **SC-0.5** protects the containment value first.
