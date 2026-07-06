# UI Refoundation — plan + rules + state

Dedicated plan+state doc for the new ground-up financial UI (owner directive
2026-07-04). Linked from `PROJECT_STATE.md`. This is working memory, NOT a
new authority doc — keep it honest and current; CLAUDE.md still wins.

## The decision (what "new ground-up UI" means and does NOT mean)

Build a **new, cohesive financial UI section** for the refoundation spine
(SOW → quote → PO → budget → green-sheet), with its own clean design language,
that becomes the **shell we mount improved older surfaces onto over time**.

**IN scope (this initiative):**
- A new design language (self-contained CSS + layout), intentional and
  product-grade, not a re-skin of the classless pico defaults.
- A per-project **Financial Command Center** as the flagship page: the whole
  money story on one screen (budget → quoted → committed → actual → variance,
  plus tendering / selected quotes), the meeting's mental model made visible.
- Honest-by-construction: every screen states provenance (MOCK / LIVE / EMPTY),
  names what's missing to light a panel up, never implies more than the data
  proves. (The green-sheet page already does this; the new UI raises the bar.)
- Read-only first. Same shape as the proven `green_sheet`/`margins` routes:
  route → `ui_views` service → template; numbers come from `ai/` report
  functions, never computed in templates.
- Its own feature flag, isolated. Old pages keep working untouched.

**OUT of scope (do NOT do, this is where UIs go to die):**
- NO new tech stack. Stay FastAPI + Jinja2 + htmx + vanilla CSS. No React/SPA
  rewrite (violates the "no new tech until SQL/stack actually limits us"
  architecture invariant and every incremental-discipline lesson).
- NO rehabbing the old quarantined pages (`finance_legacy`, `monday_gantt`)
  as part of this — they stay 404'd behind their flags. Mount-later, not now.
- NO write/mutation routes in the first slices (no forms, no state changes).
  The spine's writes happen through the CLI/ingesters, gated; the UI shows.
- NO replacing the whole app shell in one go. The new design language seeds
  the shell; existing routes get migrated onto it one deliberate slice at a
  time, each verified, never a big-bang cutover.

## Rules (bind every UI slice)

1. **Honest provenance on every page.** A visible badge: mock/demo data, live
   real data, or empty-with-reason. Never let a clean render imply real,
   validated numbers. This is the single most important rule — the old UI lost
   trust precisely by looking done while being hollow.
2. **Read-only until a write is explicitly commissioned.** Pure views over
   report functions.
3. **One flag per new surface.** Default-on only once the surface is real and
   tested; isolated from every other page.
4. **Numbers come from `ai/` report functions** (`report_green_sheet`, etc.),
   surfaced verbatim; UI composition lives in `ui_views`, not templates.
5. **Verify live, not just via tests.** Every UI slice ends with a real browser
   screenshot (preview harness) as proof, plus web tests.
6. **Fixed-vs-variable honesty.** Any cost view states that Home Depot + hourly
   labour are not in the fixed-cost spine numbers until they are unified.
7. **Mount, don't fork.** New surface lives in the SAME FastAPI app; no second
   app, no duplicate infra (features.py gate + Jinja + the demo harness pattern
   are fine as-is).

## Build order (slices — one per session, each demoable)

- **Slice U1 — Financial Command Center (per project).** New design language +
  the flagship page unifying green-sheet + tendering into one honest screen.
  Route `/projects/{id}/finance`, flag `finance_home`. ← STARTED 2026-07-04.
- Slice U2 — mount the portfolio view (a finance home across projects) on the
  new language.
- Slice U3+ — migrate margins / ledger-health onto the new shell, retire the
  scattered tabs once parity is proven. (Deferred; do not start early.)

## State

- 2026-07-04: initiative opened; Slice U1 in progress.
