# ALTA — Meeting Synthesis & Action Plan
### Financial re-foundation, v2 (meeting transcript + 2 whiteboards + PM pre-construction pipeline + Alta-number estimator)
Updated 2026‑06‑29. Supersedes v1.

This turns the loose re-foundation meeting **plus** the PM's full pre-construction
pipeline into a decision-dense plan you can build from. It is written *against the
current repo state* (evidence refactor, `FinancialLineItem` ledger, build freeze,
Home Depot + Telegram spines) so you can see what's new, what changes, what you
already have, and what to leave alone.

**What changed since v1:** a PM supplied the full intake→award pipeline that sits
*upstream* of the green sheet — **Scope of Work (SOW) as the contract spine**,
**SOW packaging for tendering**, **takeoff vs site-visit as two sources of truth**,
**quote-coverage comparison (not just price)**, and the **estimated→committed→actual
cost lifecycle**. Your own **Alta-number estimator** (vector/regularized-least-squares
spec) is captured in §11. None of it contradicts v1; it *extends the front of the
spine* and sharpens the data model.

> **Through-line both the owner and the PM state independently:** the estimator is
> NOT the center of the product. **Structure and traceability are.** Every cost must
> trace to a SOW item; every SOW item to a package; every package to a quote; every
> accepted quote to a PO; every PO to a budget line and an actual. Prediction is a
> late-stage convenience that the structure earns.

---

## 0. The one shift (read this first)

The meeting re-points ALTA. Until now the product spine was the **weekly
cross-project report** (passive truth layer), and finance was explicitly
"NOT portfolio-useful yet." The owner has now named the new #1:

> Financing → costing → receivables is "the first win." Build *one* finance thing
> that works, prove it on the pilot, then move to timeline/cameras.

And the deeper realization the owner stated out loud:

> "This is not just a software issue. This is a data issue — the AI will not work
> without the data."

So this is two projects, not one:

1. **A data-discipline layer (SOPs):** job numbers, coded filenames, SOW templates,
   a mock template Drive, POs for every transaction. *This is what unblocks the AI.*
2. **A financial-control pipeline** that consumes that clean input:
   Intake → SOW → packages → Green Sheet/Alta → Tendering → Award/PO → spend
   tracking + quote‑vs‑actual.

Stated plainly so you stop worrying it's a teardown: **your core schema is mostly
right.** `FinancialLineItem` already carries `unit / division (CSI) / side /
amount_type / status` — that anticipates much of this. The reorg mostly changes the
**input side** (how data arrives) and adds a **SOW/package + PO + variance** layer on
top of the ledger you have. It does *not* require redesigning the 13-entity core.

---

## 1. The canonical pipeline (full pre-construction → during-project spine)

v1 captured green-sheet→PO. The PM supplies the front end. The complete flow:

```
INTAKE                 SCOPING                 PRE-COST                TENDERING
receive job        ->  plans -> takeoff   ->   establish SOW      ->   send SOW packages
collect info           site visit              + material spec         to subs (by trade)
(desc, reqs,           (two SOURCES of         |                       |
 plans, photos,         truth, see §3)         SOW = contract          gather quotes
 measurements,                                 boundary; split         AGAINST the SOW
 budget exp.,                                  into per-trade          |
 constraints,                                  PACKAGES                compare quotes by
 timeline)                                     |                       COVERAGE not just $
   |                                           internal estimate       (diminish liability
   v                                           ("Alta cost") seeds      for work not done)
go / no-go filter:                             green-sheet entry #1     |
client prelim budget                           |                        v
vs rough estimate ----------------------------+                       AWARD
(out of range -> stop)                                                 selected quote ->
                                                                       awarded contract ->
                                                                       PURCHASE ORDER
                                                                       (committed cost)
                                                                          |
DURING PROJECT                                                            v
ready to start once MAJOR contracts awarded  <---------------------------+
ask for / lock timeline
   |
   v
track: BUDGET vs COMMITTED (POs) vs ACTUAL   ->   saving / over + forecast-to-complete
items outside SOW -> CHANGE ORDERS (tracked, never silent)
   |
   +--- feedback: quote-vs-actual variance  ->  trains the Alta number (§11)
```

Two framings to hold at once:
- **Financial states** of any line item: **Estimated** (Alta cost) → **Quoted**
  (sub quotes collected) → **Committed** (PO awarded) → **Actual** (spend booked).
  See §7.
- **The green sheet is the ledger view of this**: per trade-line it shows
  Alta cost vs each quote vs the selected/awarded amount vs actual — the variance
  loop lives here.

The client only ever sees a derived **client estimate** (= budget + markup); the
internal real numbers never leak to them.

---

## 2. SOW is the structural backbone (the PM's central point)

The Scope of Work is not descriptive text — it is the **contract boundary** and the
join key for the whole financial spine.

- **SOW = contract terms.** Used in two directions:
  - *To the client* — justifies the price (what's included), gives the estimate
    legitimacy.
  - *To subs* — becomes the **quote package** they price against (not a vague
    project description, which is what produces bad quotes, missing work, disputes,
    uncontrolled extras).
- **Included vs excluded is explicit.** Anything inside the SOW belongs to the
  original contract price. **Anything outside becomes a tracked change order** — it
  must never silently leak into the original budget. A change order captures: what
  changed, why it wasn't in the original, which trade/package, added cost, added
  time, client-approval status.
- **Material specification is part of scope.** Same work category, different
  material grade = different cost (cheap ceramic vs large-format porcelain). The
  spec, not just the verb, drives the labour+material assumption.
- **SOW splits into per-trade packages.** Plumbing / electrical / tile / drywall /
  paint / flooring / carpentry / HVAC … each package = only that trade's scope,
  materials, notes, drawings. Subs quote their package, not the whole job.
- **Package → quote → selected quote → awarded contract → PO.** The PO commits money
  against a specific scope package and links back to: project, trade/package,
  SOW items, vendor, committed amount, budget line, contract terms, status.

**The system rule that falls out of this:** *every cost comes from a defined SOW
item; every SOW item belongs to a package; every package can be quoted; every
accepted quote becomes a PO; every PO is tracked against budget and actual.* That is
the financial-control spine — prioritize it over prediction.

---

## 3. Two sources of truth: takeoff vs site visit

The PM is explicit that these are **separate** inputs and the system should keep them
separate:

- **Plans → takeoff = measured QUANTITIES.** Square footage, wall/floor/tile areas,
  door & fixture counts, linear footage, material quantities, scope quantities by
  trade. These are the **estimator inputs** (the `SF, RM, CH, BR…` of §11).
- **Site visit = condition MODIFIERS / risk.** Access difficulty, demo complexity,
  existing damage/rot, hidden plumbing/electrical, material-handling, parking/loading,
  occupied vs vacant, floor/wall condition, site-specific risk. These become
  **exclusions, warnings, risk adjustments, and contingency** — NOT clean quantities.

Design consequence: takeoff feeds the parametric estimate; site-visit findings feed
**exclusions on the SOW + contingency/risk**, and should be stored as structured
condition notes against the project/SOW, not folded blindly into a single number.

---

## 4. The four purchase types + cost-aggregation identity

From whiteboard #2. Every dollar out the door is one of these; tracking strategy
differs per type:

| # | Type | Drives | Predictable? | How it's tracked | Status in repo |
|---|------|--------|--------------|------------------|----------------|
| 1 (Fixed) | **Fixed-cost subcontractor** (vendor) | Scope of work | Yes | PO + trade-specific contract; reconcile to budget line | Ledger exists; PO/contract NEW |
| 2 (Fixed) | **Fixed-cost supplier** | Material supply | Yes | PO (one-off, no contract); reconcile to budget line | Ledger exists; PO NEW |
| 3 (Variable) | **Home Depot / Rona** ‼ | Variable small purchases | **No** | Flag + monitor; *tolerance*, not line-item precision | **Built** (`homedepot` spine) |
| 4 (Variable) | **Hourly work** ‼ | Variable scope | **No** | Worker logs job# via bot; monitor | **Built** (Telegram/labour intake) |

**Cost-aggregation identity (your note):**
```
TC = Σ(FC)  +  Σ_over_types_i ( VC_per_unit_i × Q_i )
```
Total cost = sum of the fixed commitments (types 1–2, locked by PO) plus, for each
variable type i (types 3–4), the per-unit variable cost times its quantity. The fixed
side is reconciled to the penny against the budget; the variable side is the watched,
tolerance-bucketed leak.

Key distinctions the meeting nailed down:
- **Vendor vs supplier:** a *vendor* does work (± supplies material) → needs a
  contract with trade-specific terms (also how you hold subs accountable: "no
  contract = nothing to hold them to"). A *supplier* is material-only → one-off, no
  contract.
- **Transportation gets its own code** (different tax treatment).
- **Types 3 & 4 are the leaks** (owner's #1/#2 worries). The point is *not* to force
  every Home Depot nail onto a line item — it's a **tolerance bucket**: capture
  against job#, flag anomalies, and use the **schedule timeline** to narrow "what was
  this purchase for?" from ~20 candidates to ~4.

---

## 5. Data discipline = the real unlock (SOPs, not code)

None of the AI works without this. Process deliverables for the company, captured in
a ~10-page SOP + a **mock template Drive**, before/alongside the code.

- **[SOP] Job numbers for everything.** Retire project names ("Tanya", "Rockland")
  → every project = a job number, entered **at the till** for every purchase
  (physical labels for the crew). "It's a rule."
- **[SOP] SOW + package templates.** A canonical SOW template (included/excluded +
  material spec) and per-trade package format, so subs always quote the same shape.
- **[SOP] Line-item codes.** Each line item gets a code = **CSI MasterFormat trade
  code** + **purchase-type code** (vendor / supplier / transportation). The **PM
  enters the code into the Drive file title** (strict titling) — subs won't follow
  your scheme themselves.
- **[SOP] One homogeneous status convention.** The "accepted / verified / 1 / 2 / 3"
  mess is *the* reason the AI picked the wrong quote. One status vocabulary
  everywhere (`pending` / `selected` / `rejected` / `awarded` …); names don't matter,
  consistency does. The green sheet needs an explicit **pending** state.
- **[SOP] The mock Drive.** A fake project folder that is the template for
  everything: mock SOW, packages, quotes, green sheet, POs, budget — exactly how real
  ones will look. Teaches the AI the structure *and* tells the company how to input.
- **[Design principle] "Shrink variability, widen tolerance."** Standardize inputs
  (SOP) *and* keep the parser tolerant of residual mess + legacy/third-party docs.
- **[Requirement] Flag, never silently sort.** If the AI doesn't understand a
  doc/purchase, surface it for a human — nothing silently mis-filed. (Reuse the
  `Proposal` / ledger-health "needs attention" surface.)

---

## 6. Data model: new + extended entities (for Claude Code)

The PM's implied object list mapped onto the existing schema. This is the concrete
"modify the structure" payload.

| Conceptual object | Recommendation | Key fields / notes | Relationships |
|---|---|---|---|
| **Project** | **Extend** (exists, join nucleus) | add `job_number` (canonical, replaces name-based id) | parent of everything below |
| **SOW item** | **NEW** `SowItem` | description, trade/`division_code` (CSI), `included` (bool), `material_spec`, package_id | → Project, → SowPackage |
| **Material spec** | **NEW** field/JSON on `SowItem` (not its own table yet) | grade/level + assumptions; drives cost | embedded in SowItem |
| **SOW package** | **NEW** `SowPackage` | trade/`division_code`, drawings/notes refs, status | → Project, has many SowItem |
| **Internal estimate / Alta cost** | **Reuse** `FinancialLineItem` (`status='estimated'`) | the §11 estimator output seeds these | → SowItem, → Project |
| **Green sheet** | **VIEW/report**, not a table | per trade-line: Alta vs quotes vs selected vs actual | computed over FinancialLineItem + quotes |
| **Subcontractor quote** | **NEW** `SubcontractorQuote` (this *is* the green-sheet entry) | vendor_id, package_id, amount, coverage/exclusions/assumptions, materials_incl, quote_date, `status` (pending/selected/rejected), evidence_span_id | → SowPackage, → Vendor, → EvidenceSpan |
| **Quote comparison** | **VIEW/report**, not a table | coverage-vs-price matrix against the package SOW | computed |
| **Budget (snapshot)** | **NEW** `BudgetSnapshot` (+ lines) or a frozen `status='budget'` cut of FinancialLineItem | locked targets per line/unit; immutable once frozen | → Project, → FinancialLineItem |
| **Purchase Order** | **NEW** `PurchaseOrder` | project#, `po_number` (auto from project#), package_id, vendor_id, `trade_type`, `purchase_type`, `contract_amount`, generated contract terms, budget_line_id, status | → SowPackage, → Vendor, → budget line; **emits** ContractObligation(s) |
| **Awarded contract** | **Reuse/extend** `ContractObligation` | emitted by PO award; payment/penalty terms | ← PurchaseOrder |
| **Change order** | **NEW** `ChangeOrder` (generalize `extras_grid.py`) | what changed, why not original, trade/package, added_cost, added_time, client_approval_status | → Project, → SowItem/package |
| **Timeline** | **Reuse** Monday schedule fields on `Task` + an intake timeline field on Project | start/finish expectations captured at intake | → Project, → Task |
| **Purchase-type tag** | **Extend** `FinancialLineItem` | add `purchase_type` (vendor/supplier/home_depot/hourly/transportation) and `cost_status` (estimated/quoted/committed/actual) | — |

Reuse as-is: 13-entity core + `ExternalId`; CSI vocab in `ai/financial_divisions.py`
(trade codes for packages); `homedepot` ledger (type 3); Telegram/labour intake
(type 4); evidence spine (`DocumentParse`/`EvidenceSpan`) for quote provenance;
`Proposal` gate for AI-advisory selection/flagging; `Vendor` (has `payment_terms`).

---

## 7. Cost lifecycle: estimated → committed → actual

A clean status machine the PM's flow implies; model it as `cost_status` on the
line-item ledger so a single trade-line can report all four side by side:

```
ESTIMATED      QUOTED                 COMMITTED            ACTUAL
Alta cost   -> sub quotes collected -> PO awarded       -> spend booked
(§11)          (green sheet)          (contract signed)    (POs paid + variable
                                                            HD/hourly attributed)
```
- The **variance report** is just differences across these columns per line item.
- "Ready to start" = the **major** packages have reached COMMITTED — not merely that
  an ESTIMATED number exists.

---

## 8. Requirements (tagged + prioritized)

Tags: **[NEW]** build · **[REWORK]** existing changes · **[REUSE]** already have ·
**[SOP]** process · **[CONFIRM]** decide with owner first · **[PARKED]** later.

### A. Scope spine (front end — new from the PM)
- **[NEW] SOW + items + material spec** per project (included/excluded; the contract
  boundary).
- **[NEW] SOW packaging** by trade for tendering.
- **[NEW] Quote intake + coverage comparison.** Track per package: which subs
  received it, amount, **coverage, exclusions, assumptions, materials, missing
  work**, date, status. Comparison is **coverage-aware**, not cheapest-only —
  "diminishes our liability for work not done."
- **[NEW] Change-order control.** Anything outside SOW becomes a tracked change
  order; never silently absorbed.
- **[REWORK] Intake capture** (incl. timeline + client prelim budget) and a **go/no-go
  filter**: if rough estimate is out of the client's range, don't tender.

### B. Core financial spine
- **[NEW] Purchase Order entity + form.** project#, PO# (auto), trade type, purchase
  type, contract amount; generates the right contract (vendor terms; suppliers none);
  links to a budget line; emits obligations.
- **[REWORK] Green Sheet workflow.** Collect all quotes per trade-line, mark one
  selected. Expressible as `SubcontractorQuote` rows + `FinancialLineItem`
  `status`; needs the per-trade "collect & choose" view and the **pending** state.
- **[NEW] Budget snapshot.** Carried/selected numbers frozen as per-line-item targets.
- **[NEW] Spend tracking: saving/over + forecast-to-complete** (budget vs committed
  vs actual, per line/trade/unit). The daily-driver output.
- **[NEW] Quote-vs-actual variance** per line item (the owner-stated #1 costing
  output; feeds the Alta number). *Whose time: owner/PM at quoting — "how accurate
  were we last time."*
- **[CONFIRM] Client-facing vs internal numbers (markup).** Two number sets + profit
  target; client never sees real numbers. Confirm the markup model.

### C. The four-type tracking
- **[REUSE] Home Depot (type 3).** Built + validated (190 txns). Wire job#-at-till so
  attribution stops being ~47% unresolved.
- **[REUSE] Hourly/labour (type 4).** Telegram intake built + live; **blocked on
  adoption** — job#-on-every-message SOP is what unblocks it.
- **[NEW] `purchase_type` + `cost_status`** first-class on the ledger.
- **[NEW] Schedule×purchase cross-reference** (timing-based attribution helper for
  the variable buckets — a date-window join, not a subsystem).

### D. Receivables / payables (lighter, mostly later)
- **[CONFIRM/PARKED] Receivables trigger.** Costing should trigger billing milestones
  ("we get paid way too long after we deserve it") — finance × scheduling; note,
  don't build yet.
- **[REWORK] Invoice direction.** "Invoice" is ambiguous (we invoice clients;
  suppliers invoice us) — the classifier must resolve direction (the 3940
  supplier-worksheet-as-revenue bug; evidence layer + role classifier is the fix in
  flight).

---

## 9. What the Drive reorg overwrites / re-ranks (honest impact)

- **Re-ranked, not deleted — parsing-tolerance heroics.** Much of the evidence
  refactor (XlsxParser header-detection, Docling table recovery, LLM tolerance for
  "really disorganized data") exists to survive the *current* mess. With templated
  inputs, the **deterministic grid parser becomes the main path**; the tolerance work
  becomes the **fallback for legacy + third-party supplier docs**. Keep it; demote it.
- **Rework: project attribution.** Today derived from `folder_path` / `category` /
  `parent_folder_id`. Job-number filenames + a reorganized tree mean the attribution +
  `category` derivation in the Drive connector and `docs.py` logic update to the new
  convention.
- **Rework: "which quote is accepted?"** Currently guessed among accepted/verified/
  1/2/3. Under the status SOP this becomes a **deterministic read of the status
  label** — delete the guessing heuristics once the convention lands.
- **Net-new (not in schema yet):** SOW/items/packages, SubcontractorQuote, Purchase
  Order, Budget snapshot, ChangeOrder, `purchase_type`/`cost_status`, quote-vs-actual
  variance, client-vs-internal markup, the Alta-number store.
- **Untouched (do not relitigate):** 13-entity core + `ExternalId`; Project as join
  nucleus; LLM-as-advisor → `Proposal` gate; SQL/SQLite; the evidence spine tables.

---

## 10. The plan (proposed ~1.5-week sequence)

Ordered so each step ships something usable on the **pilot (923 Rockland / the
"Tanya" first-floor job)**, where *you* control the data.

1. **Settle conventions (with owner/PM) — day 1–2, [SOP/CONFIRM].** Job-number
   format; SOW + package templates; line-item code scheme (CSI trade + purchase type +
   transportation); one status vocabulary; strict file-title pattern; markup model;
   usage-gate sentence.
2. **Build the mock template Drive — day 2–3, [SOP].** Mock SOW, packages, quotes,
   green sheet, POs, budget — the canonical shapes parser + company both learn from.
3. **SOW → packages → green sheet → budget on the pilot — day 3–6, [NEW/REWORK].**
   Read templated SOW + quotes per trade into `SowItem`/`SubcontractorQuote`/
   `FinancialLineItem`, compare by coverage, select, freeze a budget snapshot. Reuse
   the grid parser + CSI vocab.
4. **Purchase Order entity + budget link — day 5–8, [NEW].** Form → PO# → contract
   generation (vendor) → link to budget line → emit obligations → COMMITTED status.
5. **Spend tracking + quote-vs-actual on the pilot — day 7–10, [NEW].** Budget vs
   committed vs actual, saving/over, forecast, variance view. **This is the demo.**
6. Throughout: keep types 3 & 4 (Home Depot, hourly) feeding the same job#, and route
   anything outside SOW to a ChangeOrder.

**Definition of done (the gate):** the owner/PM opens ALTA — not Drive — to see, on
the pilot, real-vs-quoted per trade and current spend vs budget; it's right; and they
come back next week unprompted.

---

## 11. PARKED scope (incl. the Alta-number estimator)

The owner was firm — *"I want one thing that works"* — and the PM independently says
**structure over prediction**. Hold the line (matches the existing BUILD FREEZE).
Documented here so it slots in cleanly later, NOT to build now.

**Parked items:** cameras / attendance / timeline tracking (owner's explicit "next
step after finance works"); compliance system (CCQ / Quebec paperwork — separate
product, not costing); logistics/procurement for the company's own real-estate builds.

### The Alta-number estimator (your spec — build LATER, after ~20–50 clean projects)

A minimally-assumed, **line-item-level** parametric estimator using interpretable
geometric/count quantity proxies. Its inputs are exactly the **takeoff quantities**
(§3); site-visit conditions are handled as exclusions/contingency, not as model
inputs. Its per-line-item output **is the Alta cost = green-sheet entry #1**, and the
**quote-vs-actual variance loop (§7) is what trains it**. Per-line-item is preferred
over a single total estimate (fewer compounding layers).

Variables (per line item `i`):
```
SF = square feet (area)        RM = number of rooms
CH = ceiling height            BR = number of bathrooms

Line-item cost:
  LI_i = a_i·SF + b_i·RM + c_i·(CH·√(SF·RM)) + d_i·BR + e_i

  a_i·SF              area-driven cost
  b_i·RM              room-count-driven cost
  c_i·CH·√(SF·RM)     perimeter / wall-area proxy
  d_i·BR              bathroom / wet-service proxy
  e_i                 base setup / fixed minimum

Vector form:
  x   = [ SF, RM, CH·√(SF·RM), BR, 1 ]
  β_i = [ a_i, b_i, c_i, d_i, e_i ]ᵀ
  LI_i = x · β_i

Fit per line item across past projects:
  y_i = [ actual LI_i (project 1), actual LI_i (project 2), actual LI_i (project 3), … ]ᵀ

Regularized least squares — IMPORTANT, small dataset:
  β_i = (XᵀX + λD)⁻¹ Xᵀ y_i
  D   = diag(1, 1, 1, 1, 0)        # intercept e_i is NOT regularized
```

Multi-unit scaling (`UN` = number of units, `UN > 1`):
```
  TotalLI_i = ĤLI_i = k_i · (UN)^(q_i) · LI_i + p_i

  Non-linearity heuristic limits:
    0.80 ≤ q_i ≤ 1.1
    -e_i · k_i · (UN)^(q_i) ≤ p_i

  Simpler linear version (if q_i = 1.00):
    TotalLI_i = ĤLI_i = k_i · UN · LI_i + p_i
```
*(Behaviour of these systems / the solving method is still open — treat `q_i` as a
fitted parameter within the bounds, or pin `q_i = 1` for the linear version, until
there's data to choose.)*

Total estimate (kept for reference only — **too many layers of estimation to be
reliable** vs the per-line-item estimator above):
```
  TotalEstimate = Σ_i TotalLI_i + VC_adjustments + overhead + profit + contingency
```

**When this is eventually built:** it consumes takeoff quantities → emits per-line-item
Alta costs → seeds green-sheet entry #1 → the actuals booked via POs/variance feed
`y_i` → `β_i` is refit. Until then, the Alta cost is entered by hand; the structure
(§1–§7) is what earns the estimator.

---

## 12. Open questions to settle with the owner/PM BEFORE building

1. **Usage-gate sentence** for the *financial* spine (CLAUDE.md still has it "being
   whiteboarded" — the whiteboards may be it; confirm).
2. **Markup model:** per-line %, global %, or target-profit backsolve from budget?
3. **Quote selection rule:** cheapest vs best-coverage — manual, or AI-proposed? (Keep
   human-selected, AI-advisory — matches the Proposal invariant. Coverage check is
   mandatory regardless.)
4. **PO ↔ `ContractObligation`:** new `PurchaseOrder` that *emits* obligations (lean
   yes), vs extending obligations directly.
5. **SOW granularity:** is a SOW item == a `FinancialLineItem` line, or coarser (one
   SOW item → several ledger lines)? Determines the FK direction.
6. **Tolerance threshold for types 3 & 4:** what $ / % of a job may live in the
   "unassigned variable" bucket before it flags?
7. **Legacy data:** old projects seed the Alta number later but are pre-SOP — confirm
   read-only history, not retro-fitted.

---

*Sources: meeting transcript (Alta_main_software_plan_meeting.pdf) + two whiteboard
photos + PM pre-construction pipeline summary + owner's Alta-number estimator spec,
read against CLAUDE.md / PROJECT_STATE.md / HANDOFF.md / CHANGELOG.md and the current
models. Personal/funding tangents in the transcript are intentionally excluded.*
