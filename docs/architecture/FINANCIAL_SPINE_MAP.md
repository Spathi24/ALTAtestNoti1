# ALTA Financial Spine — Architecture Map (data-flow reference)

**Status:** living map, agreed 2026-07-07. Not an authority mandate — the
authority doc is [`../MEETING_SYNTHESIS_financial_refoundation.md`](../MEETING_SYNTHESIS_financial_refoundation.md).
Companion diagram: [`alta_financial_spine.ump`](alta_financial_spine.ump)
(paste into <https://cruise.umple.org/umpleonline/> to render).

This file exists so that as we build, we can point at one picture and ask:
*"is the data flowing exactly how we want?"* It distills the ProjectInfo1 and
EstimatorDocumentation analyses into (a) the flow, (b) what is already built vs
what must change, and (c) how we reconcile the messy pilot.

---

## 0. The one sentence

> ALTA is not fundamentally an estimator. It is a **closed-loop project-cost
> controller.** A *planning loop* (SOW → work → estimate → budget) and an
> *execution loop* (POs, Home Depot, labour, invoices) continuously reconcile
> against each other and forecast the final cost and margin.

Canonical object graph (many-to-many where reality is many-to-many):

```
Evidence → ScopeContext → SowVersion → SowItem → WorkRequirement
                                          ├─(estimate)→ EstimateLine  ⇄  coverage(M:N)
                                          └─(tender)→   Package → Quote → PO
                                                                    │
        HomeDepot / Labour / Invoices ───→ CostEvent ⇄ allocation(M:N) → WorkRequirement
                                                                    │
                                                    forecast-to-complete → budget/margin loop
```

**Two rules that pay for the whole redesign:**
1. **Fixed vs variable is a property of *fulfilment*, not of scope.** The same
   "repair floor" work requirement can be a $3,000 subcontract *or* 18 hourly
   hours + $1,100 of Home Depot material. So the fixed/variable split lives on
   the **CostEvent / PurchaseType**, never on the SowItem.
2. **There is no SOW↔estimate bijection.** One estimate line prices many SOW
   items and vice-versa. Forcing a single `SOW_Item_Ref` or an `Included=Y/N`
   boolean destroys information. Model it as a coverage relation with provenance.

---

## 1. The pipeline, in plain English

**Planning loop (the left branch):**
1. **Discover & register** every Drive file → `Document` (name, checksum, folder). *[BUILT]*
2. **Resolve authority** per (scope context, document role): signed beats draft,
   supersession beats mtime — *flag conflicts, never silently pick newest.* *[TARGET]*
3. **Parse** (deterministic grid first, LLM fallback) → evidence spans with
   page/sheet/row provenance. *[BUILT]*
4. **Normalize / atomize** the SOW → versioned, approved `SowItem`s, splitting
   SUPPLY from INSTALL and INCLUDED from EXCLUDED. *[BUILT, needs MODIFY]*
5. **Decompose** each SowItem into `WorkRequirement`s (the quantities of work
   that must actually happen). *[TARGET — the missing layer]*
6. **Estimate** each requirement's material/labour cost distribution (scope
   gates existence; takeoff gives magnitude). *[TARGET — parked estimator]*
7. **Derive budget**: client price → target margin → allowable internal cost →
   immutable `BudgetSnapshot` (B = fixed + variable allowance + risk reserve). *[BUILT]*

**Tendering (the right branch):**
8. Group tenderable requirements into `SowPackage`s. *[BUILT]*
9. Ingest competing `SubcontractorQuote`s; compare **by coverage**, not price
   alone. *[BUILT — coverage matrix is TARGET]*
10. Human **selects** (intent) → **awards** a `PurchaseOrder` (commitment). *[BUILT]*

**Execution loop (the right, during the job):**
11. `CostEvent` stream: POs/invoices (fixed, deterministic allocation) + Home
    Depot (variable, *probabilistic* allocation over requirements) + hourly
    labour (observed ≤ true; estimate the missing part). *[BUILT streams, TARGET unification]*
12. **Forecast-to-complete** → expected final cost → headroom → margin. *[TARGET]*
13. **Green sheet** renders the controller state (budget/quoted/committed/actual
    **+ EFC/headroom/forecast-margin**). It is a *computed view*, never a table. *[BUILT, extend]*

**Feedback loops:**
- **Scope change** (client changes the SOW) → `ScopeDelta` → Change Order.
- **Execution exception** (roof caves in — scope did *not* change) →
  `ProjectException(cause)` → supplemental cost demand. **Different path.** *[TARGET]*

---

## 2. BUILT vs MODIFY vs TARGET (the differentiation you asked for)

| Concept | Status | Where / what changes |
|---|---|---|
| `Project`, `Client`, `Vendor` | **BUILT** | join nucleus, `code=YYYYNNN` |
| `Document` → `DocumentParse` → `EvidenceSpan` | **BUILT** | evidence/provenance layer works |
| `SowPackage` / `SowItem` (scope) | **BUILT** | `ai/sow_ingest.py`; 111 real items on pilot |
| `SubcontractorQuote` (+status vocab) | **BUILT** | pending→recommended→selected→awarded |
| `PurchaseOrder` (one writer of committed cost) | **BUILT** | award = commitment |
| `BudgetSnapshot` / lines (immutable) | **BUILT** | rebaseline = new snapshot |
| `FinancialLineItem` (`cost_status`,`purchase_type`) | **BUILT** | the money ledger, both axes present |
| `ContractObligation`, Home Depot, Labour intake | **BUILT** | streams exist and validate |
| Green sheet (computed) | **BUILT** | extend with EFC/headroom/margin |
| `SowItem.included : bool` | **MODIFY** | → `ScopeState` enum + `Responsibility` + `ActionRole` (boolean is lossy — conflates excluded / client-supplied / proposed / unresolved) |
| `SowItem` hangs off `Project` | **MODIFY** | → hang off `SowVersion` under a `ScopeContext` |
| `FinancialLineItem` as the only cost row | **MODIFY** | converge toward `CostEvent` + `CostAllocation` |
| **`ScopeContext` / segment** | **TARGET** | *#1 gap* — Project is too coarse (pilot proves it) |
| **`SowVersion`** (versioned, stateful) | **TARGET** | draft→proposed→approved→signed→superseded |
| **`WorkRequirement`** | **TARGET** | *the missing conceptual layer* between SOW and procurement |
| **`SourceAuthorityDecision`** | **TARGET** | rank & flag conflicts; don't "newest wins" |
| **`EstimateLine` + `EstimateLineCoverage` (M:N)** | **TARGET** | historical estimate as original evidence; coverage matrix |
| **`CostArchetype`** | **TARGET** | stable cross-project cost type the estimator learns on |
| **`CostEvent` + `CostAllocation`** | **TARGET** | unify fixed (deterministic) + variable (probabilistic) |
| **`ProjectException` / cost-demand** | **TARGET** | damage/rework ≠ change order |
| **Estimator** (scope-gated, uncertainty-aware) | **TARGET (parked)** | see `EstimatorDocumentation.pdf`; do not build until we reach it |
| **Drive write-back** (`ALTA/` subfolder, materialized views) | **TARGET (gated)** | needs the risk go/no-go; generated files carry `origin=ALTA`+checksum so we never re-ingest our own output |

Nothing already built **contradicts** these guidelines — the plan is additive.
The two real shape-changes are `included:bool → ScopeState` and inserting
`WorkRequirement` between `SowItem` and cost. Everything else is new layers.

---

## 3. My two cents (where I agree, where I'd nuance)

- **Agree, strongly:** the WorkRequirement layer and the ScopeContext layer are
  the two additions that make everything else stop being special-cased. They are
  worth doing before the estimator.
- **Agree:** keep the historical estimate as *immutable original evidence* with
  its own provenance class; a model prediction must never overwrite it. This is
  the same discipline our reconciliation auditor already follows on the ledger.
- **Nuance / sequencing:** we are under a **build freeze** and one-slice
  discipline. These are real, but they are *layers to grow into*, not a rewrite
  to do at once. The order that saves time fastest: **ScopeContext → clean the
  pilot's three segments → WorkRequirement → CostEvent unification → forecast →
  estimator.** Each is one slice with a visible delta.
- **Caution on the estimator:** it needs actual internal cost across ~20+ clean
  projects to train. We have ~1. Until then it is a Tier-C scope-only prior with
  honest, wide error bars — useful as a *sanity band*, not a number to trust.
  Keep it parked; don't let its elegance pull us off the traceability work.
- **One thing to lock now (owner's point about over/under-fitting):** future
  projects must land in a **known folder + filename shape** so we never re-infer
  structure. The SOP format is the cheapest possible win — it removes an entire
  class of guessing.

---

## 4. Pilot 2026001 — reconciling the messy real project

2026001 ("923-927 Rockland") is **three scope contexts under one client**:

| Segment | Evidence in DB | Authority | Number |
|---|---|---|---|
| **A — 923 interior** | `SOW 923 Rockland`, `Final SOW.pdf`, `ACCEPTED QUOTE`, `Estimate #25008` | **SIGNED** | **$66,539.65** pre-tax |
| **B — 927 unit** | `927 QUOTE`, `927 Av. Rockland – Pour construction` | quote only | ~$191,843.68 |
| **C — exterior** | `SOW - EXTERIOR`, `EXTERIOR QUOTE (NOT STARTED)` | not started | ~$4k |

**Decisions (2026-07-07):**
- `Project.contract_amount` is set to **$66,539.65** (segment A only — the one
  signed contract). It is **not** the whole project and the UI must say so.
- Segments B and C are **held separate**, not merged, until the `ScopeContext`
  layer exists. This is deliberately-not-ingested, recorded here and in
  `PROJECT_STATE.md`.
- The 111 ingested `SowItem`s currently mix segment A scope with exterior
  (segment C) planning rows and estimate-derived policy rows (contingency, OHP).
  That mixing is the `ScopeState`/`ScopeContext` cleanup work, not a data loss.
- **This pilot is the hard case, on purpose.** Future projects get one SOP
  format; we validate on this mess so we don't overfit to a friendly fixture.

---

## 5. Where each source lives

- Authority / philosophy: `../MEETING_SYNTHESIS_financial_refoundation.md`,
  `../REFOUNDATION_BUILD_NOTES.md`, `../../CLAUDE.md`.
- This map + diagram: `docs/architecture/`.
- Estimator math (parked): `EstimatorDocumentation.pdf` → to be distilled into
  its own slice doc when we reach step 6.
- Distilled decisions & working memory: repo-root `PROJECT_STATE.md`.
