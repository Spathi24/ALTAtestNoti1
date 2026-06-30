# Refoundation — Build Blueprint (preliminary context for the next instance)

Companion to `docs/MEETING_SYNTHESIS_financial_refoundation.md` (the plan; READ IT
FIRST). This maps the plan's new entities onto **exactly where and how** they slot
into the current repo, so a fresh instance with less context can execute precisely
**once the conventions in plan §12 are settled with the owner**. This is a map, not
code — nothing here is built yet, by design (the working practices / SOP conventions
come before heavy implementation).

> Status 2026-06-26: evidence refactor Slices 1–8 COMPLETE, parser capped.
> **§12 conventions SETTLED 2026-06-30** — see `docs/MEETING_SYNTHESIS_financial_refoundation.md §12`
> and the PROJECT_STATE.md REFOUNDATION PLAN section for full detail.
> Build is unblocked pending the mock template Drive (plan §5/§10.2, process-first, no schema).
> Build freeze still applies until mock Drive is built and the pilot SOW exists.

---

## Working practices (how we build this — agreed posture)

1. **Structure & traceability over prediction.** Every cost traces SOW item →
   package → quote → PO → budget line → actual. The Alta-number estimator (plan §11)
   is parked until ~20–50 clean projects produce takeoff-quantity inputs + actuals.
2. **Additive, slice-by-slice, on the pilot (923 Rockland).** Each step ships
   something usable; keep the suite green; lint before continuing; one dedicated
   plan+state doc per initiative (this file + the meeting doc).
3. **LLM is an advisor → `Proposal` gate.** Quote selection, side classification,
   anomaly flags are AI-advisory; a human decides. Never auto-mutate the ledger.
4. **Flag, never silently sort.** Anything the system can't place → surfaces for a
   human (reuse `Proposal` + `ReconciliationIssue` + ledger-health). Already the
   pattern of Slice 8.
5. **Deterministic-first.** With templated SOP inputs the deterministic grid parser
   is the PRIMARY path; the evidence/LLM tolerance (Docling/XlsxParser/LLM) is the
   FALLBACK for legacy + third-party/supplier docs. Don't expand tolerance as primary.
6. **The value is the line-item material/labour split**, not aggregate totals
   (totals already live in the sheets; the per-trade breakdown feeds the pipeline).

---

## Invariants that bind any new code (do not violate)

- **SOW = contract boundary.** Inside SOW → original contract price. Outside SOW →
  a tracked `ChangeOrder` (what/why/trade/added cost/added time/approval). Never
  silently absorbed into the budget.
- **Material spec is part of scope** (drives material+labour assumption); store it
  on the SOW item.
- **Client never sees internal numbers.** Client estimate = budget + markup; the
  real numbers never leak. Two number sets.
- **Takeoff (quantities) vs site-visit (conditions/risk) stay SEPARATE.** Takeoff →
  estimator inputs; site-visit → exclusions/contingency, not clean quantities.
- **Cross-doc rollups must not double-count.** A SOW restating its accepted quote is
  the SAME money (the Rockland $66,539.65 × 2 = the bogus $361k). Slice 8's
  `detect_duplicate_total_issues` already flags this; new aggregation must respect it.
- **One status vocabulary** (pending/selected/rejected/awarded …) — a deterministic
  read, never guessed. The "accepted/verified/1/2/3" guessing is retired by SOP.

---

## Entity → repo mapping (build order follows plan §10)

Legend: **NEW** model · **EXTEND** existing · **VIEW** (computed, no table) · **REUSE**.

§12 conventions settled 2026-06-30 — blocking questions are now resolved. See
`docs/MEETING_SYNTHESIS_financial_refoundation.md §12` for full detail.

| Entity | Action | Where | Key fields | FK / reuse | §12 status |
|---|---|---|---|---|---|
| `Project.project_code` | EXTEND | `db/models/work.py` + migration `_add_missing_columns` | `project_code` YYYYNNN, `display_name`, `legacy_job_number`, `aliases` (JSON) | internal hash/id unchanged; Drive attribution updates to project_code | ✓ format settled (#7) |
| `SowItem` | NEW | `db/models/` new `sow.py` | description, `division_code` (CSI), `included` bool, `material_spec` (JSON), `package_id`, optional `sow_item_id` FK on FinancialLineItem | → Project, → SowPackage; CSI vocab in `ai/financial_divisions.py` | ✓ granularity settled (#5): SowItem coarser than FinancialLineItem |
| `SowPackage` | NEW | `db/models/sow.py` | trade/`division_code`, drawings/notes refs, status | → Project; has many SowItem | ✓ |
| `SubcontractorQuote` | NEW | `db/models/finance.py` (near ledger) | vendor_id, package_id, amount, coverage, exclusions, assumptions, materials_incl, quote_date, `status` (pending/recommended/selected/rejected/awarded), **`evidence_span_id`** | → SowPackage, → Vendor, **→ EvidenceSpan (already built)** | ✓ status vocab + selection rule settled (#3) |
| Green sheet | VIEW | `ai/` report fn | per trade-line: Alta vs quotes vs selected vs actual | computed over FinancialLineItem + SubcontractorQuote | ✓ |
| `BudgetSnapshot` (+lines) | NEW | `db/models/finance.py` | frozen targets per line/unit; immutable; carries markup metadata | → Project, → FinancialLineItem | ✓ markup model settled (#2): line factor × 1.15 global |
| `PurchaseOrder` | NEW | `db/models/finance.py` | `project_code`, `po_number` (YYYYNNN-PPP, auto), package_id, vendor_id, `trade_type`, `purchase_type`, `contract_amount`, terms, budget_line_id, status | → SowPackage, → Vendor; **emits ContractObligation** | ✓ PO↔obligation settled (#4) |
| `ChangeOrder` | NEW | generalize `ai/extras_grid.py` → `db/models/` | what changed, why-not-original, trade/package, added_cost, added_time, client_approval_status | → Project, → SowItem/package | ✓ |
| `FinancialLineItem.purchase_type` | EXTEND | `db/models/finance.py` + migration | enum: vendor/supplier/home_depot/hourly/transportation | — | ✓ |
| `FinancialLineItem.cost_status` | EXTEND | `db/models/finance.py` + migration | enum: estimated/quoted/committed/actual | — | ✓ |
| `FinancialLineItem.sow_item_id` | EXTEND | `db/models/finance.py` + migration | nullable FK → SowItem | — | ✓ |
| `FinancialLineItem.line_markup_factor` | EXTEND | `db/models/finance.py` + migration | float, default 1.0; client price = internal × factor; subtotal × 1.15 = final | — | ✓ markup model (#2) |
| Variable cost tolerance flags | LOGIC | `ai/` or ledger-health | warn > 3% / > 1 wk; hard > 5% / > 2 wk; mandatory job code on HD/labour | reuse ledger-health surface | ✓ thresholds settled (#6) |
| Quote-vs-actual variance | VIEW | `ai/` report fn | diffs across cost_status columns per line | computed | ✓ |
| Alta-number estimator | PARKED | `ai/` (later) | regularized least squares (plan §11) | inputs = takeoff quantities (NEW capture); targets = actuals via POs/variance | needs §11 data (~20–50 clean projects) |

**Reuse as-is (do not rebuild):** 13-entity core + `ExternalId`; `Project` join
nucleus; evidence spine `DocumentParse`/`EvidenceSpan` (+ `evidence_span_id` already
on FinancialLineItem / grid rows / obligations) — this is the provenance layer for
`SubcontractorQuote`; CSI vocab `ai/financial_divisions.py`; deterministic grid
parser (`financial_grid.parse_financial_grid_rows`) + populator; `homedepot` spine
(purchase type 3); Telegram/labour intake (type 4); `Proposal` gate;
`ReconciliationIssue` (Slice 8) for flagging; `Vendor.payment_terms`.

---

## Migration discipline reminder (so the next instance doesn't trip)

Every new table needs BOTH a SQLAlchemy model (for `create_all`) AND a DDL block
wired into `db/migrations.py::ensure_sqlite_schema` in FK-dependency order; export
it from `db/models/__init__.py` (`__all__` is RUF022-sorted). New nullable columns
on an existing table → add to the model AND the table's `_add_missing_columns`
dict AND (for consistency) the CREATE DDL. Apply to the real DB by invoking
`ensure_sqlite_schema(get_engine())`. The real `project_db.sqlite` only gets new
tables when the migration is invoked.

## First build step when unblocked (plan §10.3, pilot 923 Rockland)

SOW → packages → SubcontractorQuote on the pilot: read the templated SOW + per-trade
quotes into `SowItem` / `SowPackage` / `SubcontractorQuote` (+ `FinancialLineItem`),
compare by **coverage not just price**, mark one `selected`, freeze a `BudgetSnapshot`.
Reuse the grid parser + CSI vocab + the evidence links already in place. Gate of done:
owner/PM opens ALTA (not Drive) to see real-vs-quoted per trade + spend vs budget on
the pilot, it's right, and they come back next week unprompted.
