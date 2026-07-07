# UI Refoundation — plan + rules + state

Dedicated plan+state doc for the new ground-up financial UI (owner directive
2026-07-04; contract expanded 2026-07-07). Linked from `PROJECT_STATE.md`. This
is working memory + the **UI initiative contract**, NOT a backend architecture
duplicate and NOT a new authority doc — CLAUDE.md still wins; the financial
authority is `docs/MEETING_SYNTHESIS_financial_refoundation.md`; the target
architecture is `docs/architecture/FINANCIAL_SPINE_MAP.md`.

## What this UI is (the doctrine, corrected 2026-07-07)

The UI is the **operator control surface over canonical project state** — not
merely a dashboard. The product requirement is now explicit: the system must
extract or infer structured project parameters from messy inputs, **expose those
values visibly, let the operator correct/configure them, and propagate accepted
changes through the financial model.**

Two simultaneous levels:
- **Level 1 — operator/controller view** (what a PM/owner opens): the project's
  financial controller state + the health of each part of the data graph.
- **Level 2 — canonical state inspector/editor** (what the operator needs to fix
  reality): every *domain parameter* that affects downstream state is
  inspectable, and human-owned/AI-inferred parameters are correctable.

Derived controller outputs (EFC, headroom, margin, green-sheet totals) are
**read-only and recompute from canonical state** — never directly edited.

## Preserved rules (still good, do not drop)

1. **Honest provenance on every page** (the single most important rule — the old
   UI lost trust by looking done while hollow).
2. **Same app, no new tech.** FastAPI + Jinja2 + htmx + vanilla CSS. No React/SPA
   rewrite; no second app; no big-bang shell replacement.
3. **Numbers come from `ai/` report functions**, surfaced verbatim; UI
   composition in `ui_views`, **never financial calculation in templates.**
4. **One feature flag per surface**, default-on only once real + tested.
5. **Verify live**, not just tests — every UI slice ends with a real browser
   screenshot (preview harness) + web tests.
6. **Fixed-vs-variable honesty** — any cost view states when Home Depot + hourly
   labour are not yet in the numbers.
7. **Mount, don't fork** — new surfaces migrate onto the shell one verified slice
   at a time; old quarantined pages stay 404 behind their flags.

## CORRECTED rule — read-only is a stage, not the target doctrine

**Old rule (too narrow to be the target):** "Read-only until a write is
explicitly commissioned."

**New rule:**
> Read-only is the FIRST STAGE of each new domain surface. Controlled mutation is
> added only after the read model and the domain command are proven. The target
> UI must expose and allow correction of **human-owned or inferred canonical
> state**. Derived values remain non-editable and recompute from canonical state.

Critical lifecycle transitions remain explicit domain actions, never free-form
edits: **select quote · award PO · approve change order · rebaseline budget ·
confirm/reject AI proposal.** AI remains an adviser through the Proposal gate,
never a silent database actor.

## UI invariants (bind every UI slice; no schema/enums added by this doc)

### 1. Missing parameters are VISIBLE
A required domain parameter that is NULL/unknown renders as `UNSET` /
`UNRESOLVED` / `NEEDS INPUT` — **never omitted because it is missing.** Each
entity type will define a field contract (`REQUIRED / OPTIONAL / DERIVED /
NOT_APPLICABLE`) so the UI can show completeness ("SOW data completeness: 92% — 7
required fields unresolved across 5 items") and let AI *suggest* values for
unresolved required fields (confirm / edit / reject-leave-unresolved).

### 2. Two independent provenance axes
- **Environment / data availability:** `MOCK` · `LIVE` · `EMPTY` (keep the old
  badge).
- **Semantic provenance / trust:** `SOURCE` · `HUMAN_CONFIRMED` · `DERIVED` ·
  `AI_INFERRED` · `MODEL_PREDICTED` · `UNRESOLVED` · `STALE`.

`LIVE + SOURCE` and `LIVE + MODEL_PREDICTED` are radically different trust states
and must look different. Reuse existing repo states where equivalent
(e.g. `context_resolution_state`, `cost_status`, Proposal status) rather than
inventing enums.

### 3. Canonical parameters must be inspectable
The UI must eventually expose the parameters that affect downstream state (as
each entity is built) — examples: **ScopeContext** (key/label/kind/binding
state); **source/authority** (document role, active/superseded/conflicting,
evidence); **SowVersion/SowItem** (version state, scope_state, responsibility,
action_role, trade/CSI, material spec, qty/unit); **WorkRequirement** (cost
archetype, qty/unit, status, evidence/confidence); **Estimate** (origin,
input/mode, qty source, material/labour, uncertainty); **Tendering** (package,
quote status, coverage, exclusions, assumptions, vendor); **Budget/control**
(snapshot, margin/policy, reserve basis, allowable cost, rebaseline history);
**Execution** (purchase type, source event, observed amount/hours, allocation
method + confidence, unresolved cost); **Change/exception** (scope-change vs
execution-exception, cause, billable/responsibility, linked demand). This is a
*visibility contract*, not a mandate to build all schema now.

### 4. Edit the CAUSE, never the derived total
A computed EFC/headroom/margin/green-sheet total is read-only. Clicking it shows
its components; the operator edits a **canonical cause** (e.g. a WorkRequirement
remaining quantity). Accepted change → validate → persist through **one domain
command/writer** → invalidate + recompute affected derived outputs → htmx-refresh
affected panels. High-impact changes show an **impact preview** (current vs
projected EFC + affected panels) before APPLY. Immutable stays immutable:
`BudgetSnapshot` rebaselines to a new snapshot; historical evidence is preserved;
actuals are corrected via an explicit correction/match/reversal path, never
silently overwritten. AI-driven changes still go through the Proposal gate.

### 5. VISIBLE-SURFACE GATE (binding product rule)
> No new major canonical entity or controller stage is considered
> product-complete while it is observable only through SQL, CLI, tests, or
> Python. A schema/ingestion slice may be backend-only initially, but **no more
> than ONE dependent slice may proceed before an operator-visible inspection
> surface exists** for the newly created state.

The surface may start as a small read-only inspector in the new UI shell — not a
polished flagship. Examples: `ScopeContext` → a context inspector (contexts,
document bindings, unresolved count); `WorkRequirement` → a requirement
inspector; `CostAllocation` → an allocation inspector (weights + confidence);
forecast-to-complete → an FTC/EFC/headroom/margin panel. This rule exists to
prevent the project's historical backend-only scope drift ("built · tests pass ·
nobody can see it · next feature starts").

### 6. Financial Command Center target
The per-project Financial Command Center stays the flagship. Its eventual top
controller state must make room for: contract/client price (with explicit
context/aggregate meaning) · allowable internal cost · budget · quoted · open
commitment · actual · forecast-to-complete · expected final cost · headroom ·
forecast margin · forecast confidence/data health. Below it, organize the product
around the **actual controller flow**, each block showing the health of its part
of the data graph:

```
SCOPE & EVIDENCE → WORK REQUIRED → ESTIMATE & BUDGET →
TENDER / FULFILMENT → EXECUTION COST → FORECAST / CONTROL
```

plus **scope changes** and **execution exceptions** as distinct feedback paths.
The green-sheet already separates quoted/committed/actual rather than summing
lifecycle states, and is a computed controller view — keep that.

## Revised target slice order (conceptual — do NOT build all now)

Portfolio is no longer second; the project-level controller is nowhere near
semantically exhausted. UI visibility follows the financial spine:

```
U0  UI domain contract (provenance axes, mutation doctrine, visible-surface gate,
    parameter-completeness rules)   <-- THIS document is the first cut of U0
U1  Financial Command Center summary (existing read-only work remains valid)
U1.5 ScopeContext + evidence inspector (minimal visible surface for ScopeContext)
U2  Scope + WorkRequirement inspector/editor (all scope axes + missing params)
U3  Estimate + budget assumptions (qty source, estimator mode, margin/reserve)
U4  Tendering + quote coverage (coverage, exclusions, assumptions, select/award)
U5  Execution cost + allocations/labour (commitments, HD, labour, missing-labour,
    probabilistic allocations)
U6  Forecast/control (FTC, EFC, headroom, margin, breaches, recommendations)
U7  Changes/exceptions (scope delta, change order, execution exception)
U8  Portfolio controller (explicit aggregation across projects/contexts)
```

Slice boundaries may shift with domain implementation; the rule is that UI
visibility tracks the spine, not a portfolio shell built over an opaque
project-level controller.

## Completed / state

- 2026-07-04: initiative opened; Slice U1 (Financial Command Center,
  `/projects/{id}/finance`, flag `finance_home`) built read-only.
- 2026-07-05: real SOW scope card + honest signed-contract line on U1 (LIVE on
  the real DB).
- 2026-07-07: doctrine expanded to operator-control-surface; read-only rule
  corrected; invariants 1–6 + visible-surface gate + revised slice order added
  (documentation only, no code this pass).
- **Next visible-surface obligation:** per the gate, once SC-2 binds pilot
  contexts, a minimal **ScopeContext/evidence inspector (U1.5)** must appear
  before ScopeContext work expands into SOW ownership (SC-5+).
