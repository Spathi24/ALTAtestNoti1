# ALTA Demo Run Notes

Date: 2026-06-19

This walkthrough record is intentionally observational. It does not create a
fix list, backlog, redesign, or feature plan.

## Evidence Used

- Static inspection of the default-visible FastAPI routes, UI service functions,
  templates, feature flags, and existing tests.
- README and CHANGELOG context for why field notes, proposals, RAG, ledger
  health, and margins exist.
- Focused verification passed: `164 passed, 1 warning` using
  `PYTHONPATH=src python -m pytest tests/test_features.py tests/test_web_phase_a.py tests/test_web_phase_b.py tests/test_web_search.py tests/test_web_margins.py tests/test_web_financials.py tests/test_web_phase_d.py tests/test_web_phase_d1.py -q --basetemp=.pytest-tmp -p no:cacheprovider`.
- No live LLM, Gmail, Telegram, Monday write, or connector refresh was run.
- Live field-note submit, proposal accept, and live ledger-health GET were not
  exercised because they have known side effects.

## Walkthrough Observations

### Dashboard

Observation: The dashboard now opens on a briefing plus a small project/task/doc
summary, not every experimental tool. PM-facing admin links and value-caught
chrome are hidden by default.

Impact: Medium. It is a stronger opener than the old tool pile, but the page
still says "money, scope, schedule, and missing paperwork" even though some
money/commitment branches are quarantined from the demo surface.

Suggested owner decision: Keep as the opening surface if the demo story is
"ALTA finds cross-system issues." If the demo story is "work one project," start
from Projects instead.

### Projects

Observation: The Projects page lets a PM find Rockland by name without knowing a
UUID. The default action path now points toward the visible finance story rather
than legacy financials.

Impact: Low. This is the cleanest bridge from portfolio view to the Rockland
demo path.

Suggested owner decision: Keep in the demo.

### Rockland Project Detail

Observation: Project detail is the central demo surface: identity, overview,
tasks, documents, proposals, typed field note, margins, and ledger health are
reachable from one page. Legacy finance, labour, Gantt, proposal generation,
and task date editing are hidden by default.

Impact: Medium. It proves the canonical spine, but it still exposes internal
concepts such as canonical IDs, dateless task counts, extraction status, and
ledger-health language.

Suggested owner decision: Keep as the main demo surface, but decide whether the
PM is meant to see the identity/debug material during the live demo.

### Documents And Search

Observation: Documents are browseable by folder and document detail exposes
metadata plus extracted text. Search is read-only against embedded chunks, but a
real query can call an embedding provider if configured.

Impact: Medium. This is one of the most concrete proof points that the app reads
Drive/contracts instead of just syncing Monday.

Suggested owner decision: Keep search in the demo with a prepared query. Avoid
ad hoc queries unless embedding spend and answer quality are acceptable.

### Ask

Observation: `/ask` is safe for canned questions, but no-match questions route
to the fast LLM and optional RAG context. That can spend tokens and introduce
answer-quality risk.

Impact: High. Ask can impress quickly, but it is also the easiest visible
surface to drift into an unscripted AI demo.

Suggested owner decision: Keep only with scripted canned/RAG questions. Do not
use open-ended questions in the adoption demo unless token spend and answer
quality are explicitly accepted.

### Typed Field Note

Observation: The typed field-note form is visible and aligned with the active
adaptation story. Submitting it calls OpenAI structured extraction, may retrieve
RAG context, writes `FieldNote` rows, and creates/supersedes pending proposals.

Impact: High. This is the most important adoption story, but it is not a free
UI action. It costs tokens and changes local DB state.

Suggested owner decision: Keep as the demo's central action only if the run is
approved to spend tokens, or use pre-seeded pending proposals to demonstrate the
review loop without submitting a live note.

### Proposals

Observation: Proposal list/detail/reject are local DB flows. Accept is a real
write-back path: the route builds the Monday connector, writes to Monday first,
then updates canonical DB state only after a successful external write.

Impact: High. The review screen is demo-safe; the Accept button is not safe to
click casually.

Suggested owner decision: Keep proposal review in the demo. Do not perform live
Accept unless the owner explicitly approves a Monday write or the writeback is
stubbed.

### Ledger Health

Observation: Ledger health explains why margins are sparse and which documents
were parsed, skipped, unsupported, or reconcile-failed. However, the GET route
replays the ledger populator and deletes/inserts `FinancialLineItem` rows.

Impact: High. The page is operationally useful, but it violates the mental model
that GET is read-only and uses finance/audit terms that may pull the demo into
implementation details.

Suggested owner decision: Do not lead with Ledger health in a PM demo. Keep it
as an operator fallback if someone asks why the margins are incomplete.

### Margins

Observation: Margins is read-only and uses the newer division-keyed
`FinancialLineItem` ledger. It tells the intended finance story better than the
legacy financial summary, while honestly showing sparse coverage when cost data
is missing.

Impact: Medium. It is the right visible finance surface, but data coverage must
be treated as part of the story rather than hidden.

Suggested owner decision: Keep if Rockland has enough ledger rows to make the
trade-level view meaningful. Otherwise, mention it only after explaining data
coverage.

## Decision Table

| Surface | Keep in demo? | Why | Risk |
|---|---|---|---|
| Dashboard | yes | Opens with the constrained briefing instead of the full tool pile. | Can still read/filter hidden money and commitment categories internally; may feel broad. |
| Projects | yes | Lets a PM reach Rockland by name without knowing IDs. | Portfolio list can distract if many non-demo projects are visible. |
| Ask | yes, scripted | Canned/RAG questions can prove the DB/doc layer quickly. | Open-ended no-match questions can spend tokens and produce weak answers. |
| Typed field note | yes, controlled | Best proof of active adaptation: note -> proposal. | OpenAI spend, local DB writes, proposal quality risk. |
| Proposals | yes, review only | Human approval loop is core and visible. | Accept can write to Monday; stale/low-quality proposals can distract. |
| Ledger health | no for PM-led demo | Useful explanation surface, not the main value story. | GET mutates local ledger rows; finance language is implementation-heavy. |
| Margins | yes | Shows the new canonical finance story by trade/division. | Sparse ledger coverage can make the page look weaker than the system is. |

## Stop Point

The audit stops here. The next owner decision is which of the "yes, scripted" or
"yes, controlled" surfaces are allowed in the actual live demo run.
