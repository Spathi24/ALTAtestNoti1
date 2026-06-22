# ALTA Demo Path Audit

Date: 2026-06-19

This is a factual map of the default-visible demo path after feature-flag
quarantine. It documents what the app does when a PM follows the visible path.
It does not propose fixes, redesigns, or new product work.

## Guardrails

- No schema, model, parser, extraction, route, template, or test behavior was
  changed for this audit.
- No live API, LLM, Gmail, Telegram, or Monday write was approved or triggered.
- Rockland is validation context only. Product logic must not hardcode the
  Rockland UUID.
- "Visible" means visible with committed feature defaults. It does not mean
  side-effect-free.

## Default Visible Path

```text
/ -> /projects -> /projects/{rockland_id}
   -> /documents/{document_id}
   -> /search
   -> /ask
   -> POST /projects/{project_id}/field-note
   -> /proposals -> /proposals/{proposal_id}
   -> /projects/{project_id}/margins
   -> /projects/{project_id}/ledger-health
```

## Route And Side-Effect Map

| Surface | URL / action | Handler | Main services | Tables read | Tables written | External / token spend | Main failure modes | Existing coverage |
|---|---|---|---|---|---|---|---|---|
| Dashboard | `GET /` | `create_app.dashboard` | `attention_briefing`, `value_caught`, `dashboard_summary`, `recent_pending_proposals` | `Project`, `Task`, `Document`, `DocumentText`, `Proposal`, `Deal`, `Lead`; briefing/value functions may also read `FinancialRecord` and `ContractObligation` before UI filtering | none | none | empty DB, noisy briefing, hidden categories still read internally | `tests/test_web_phase_a.py`, `tests/test_web_briefing.py` |
| Projects | `GET /projects` | `projects_index` | `project_list_rows` | `Project`, `Task`, `Document`, `Client`, `Proposal` | none | none | empty DB, project list too broad for demo | `tests/test_web_phase_b.py` |
| Project detail | `GET /projects/{project_id}` | `project_show` | `project_detail`, canned reports, proposal list enrichment | `Project`, `Client`, `Task`, `Document`, `DocumentText`, `Invoice`, `DailyLog`, `ExternalId`, `Proposal`; currently also computes legacy money-line inputs from `FinancialRecord` / commitments even when hidden | none | none | bad UUID, unknown project, page carries more sections than the demo story needs | `tests/test_web_phase_b.py`, `tests/test_web_phase_d1.py`, `tests/test_web_financials.py`, `tests/test_web_margins.py` |
| Document detail | `GET /documents/{document_id}` | `document_show` | `document_detail` | `Document`, `DocumentText`, `Project`, `Proposal` | none | none | bad UUID, missing document, huge extracted text | `tests/test_web_phase_b.py` |
| Search | `GET /search?q=...&project=...` | `search` | `search_documents`, `embedding_coverage`, `retrieve_chunks` | `DocumentChunk` / RAG tables, `Document`, `Project` | none | Query embedding if provider is configured; no chat LLM | empty query, unembedded corpus, no embedding provider, embedding/search exception | `tests/test_web_search.py` |
| Ask page | `GET /ask` | `ask_index` | template render only | none | none | none | disabled feature returns 404 | `tests/test_web_phase_d1.py` |
| Ask submit | `POST /ask` | `ask_submit` | `AiAssistant.ask`; on no canned match, `answer_with_llm` with optional RAG | Canned reports read project/task/document/finance data by report; no-match path can read DB snapshot and RAG chunks | none | Fast LLM call on no-match; optional query embedding / RAG spend | empty question, no provider, bad provider, low answer quality, token spend surprise | `tests/test_web_phase_d1.py`, `tests/test_ai_assistant.py`, `tests/test_askbot_assertive_prompt.py` |
| Typed field note | `POST /projects/{project_id}/field-note` | `project_field_note_submit` | `submit_field_note`, `OpenAIFieldNoteExtractor`, `ingest_field_note` | `Project`, `Task`, optional RAG chunks | `FieldNote`, `Proposal`; may supersede prior pending proposals | OpenAI structured-output call; optional embedding/RAG spend | missing API key, extraction failure, vague note, unknown project, proposal quality risk | `tests/test_field_note.py`, route-adjacent checks in `tests/test_web_phase_d1.py` |
| Proposal list | `GET /proposals` | `proposals_index` | `proposal_queue`, `list_proposals` | `Proposal`, enriched target `Task` / `Project` data | none | none | invalid status filter, empty queue | `tests/test_web_phase_b.py` |
| Proposal detail | `GET /proposals/{proposal_id}` | `proposal_show` | `proposal_detail`, `get_proposal_detail` | `Proposal`, target `Task` / `Project`, source doc refs | none | none | bad UUID, missing proposal, stale state | `tests/test_web_phase_b.py`, `tests/test_web_phase_d.py` |
| Proposal accept | `POST /proposals/{proposal_id}/accept` | `proposal_accept` | `build_monday_writeback`, `accept_proposal` | `Organization`, `Proposal`, target `Task` or `Project` | `Proposal`; may update/create `Task` or dependencies after external write succeeds | Monday write via `sync_back` or `create_task` | missing token/org, connector build failure, Monday write failure, stale proposal, unsupported field | `tests/test_web_phase_d.py`, `tests/test_field_note.py` |
| Proposal reject | `POST /proposals/{proposal_id}/reject` | `proposal_reject` | `reject_proposal` | `Proposal` | `Proposal` status/reason fields | none | stale proposal, bad UUID, missing proposal | `tests/test_web_phase_d.py` |
| Margins | `GET /projects/{project_id}/margins` | `project_margins_show` | `project_division_margins`, `report_division_margins` | `Project`, `FinancialLineItem`, `Document` | none | none | empty ledger, sparse data, revenue-only interpretation | `tests/test_web_margins.py`, `tests/test_division_margins.py` |
| Ledger health | `GET /projects/{project_id}/ledger-health` | `project_ledger_health_show` | `project_ledger_health`, `report_ledger_health`, `populate_ledger_for_document` | `Project`, `Document`, `DocumentText`, existing `FinancialLineItem` | `FinancialLineItem` delete+insert per parsed document; committed when request finishes | none | GET route mutates local ledger, confusing finance terms, parse/reconcile unsupported docs | `tests/test_web_margins.py`, `tests/test_ledger_health.py` |

## Hidden Or Blocked By Default

| Surface | Default behavior | Notes |
|---|---|---|
| Legacy financial summary | hidden in project nav; route returns 404 unless `PROJECT_DB_FEATURE_FINANCE_LEGACY=true` | Old `FinancialRecord` path remains for transition, not demo story. |
| Gantt | hidden; route returns 404 unless `PROJECT_DB_FEATURE_MONDAY_GANTT=true` | Deterministic and useful, but not default demo. |
| Labour / Telegram intake | hidden; labour route and CLI are feature-gated | Valuable pilot path, quarantined from PM demo. |
| Proposal generation buttons | hidden; generation routes require `PROJECT_DB_FEATURE_PROPOSAL_GENERATION=true` | Prevents accidental LLM spend. |
| Manual task date edit | hidden; task edit routes require `PROJECT_DB_FEATURE_TASK_DATE_EDIT=true` | Prevents accidental Monday write path from task table. |
| Admin nav | hidden by `admin_nav=false` | Direct `/doctor` and `/db` routes remain operator tools, not PM-facing navigation. |

## Startup / Background Side Effects

`project_db serve` starts a background refresh by default. That calls connector
refresh and incremental embedding unless launched with `--no-refresh`. For demo
audit or PM walkthrough work, prefer:

```bash
project_db serve --no-refresh
```

or use TestClient/static inspection. This avoids unexpected Monday/Drive sync or
embedding spend while inspecting the UI.

## Rockland Validation Boundary

Use Rockland only as an operator-selected validation target, for example:

```powershell
$env:PROJECT_DB_DEMO_PROJECT='923-927 Rockland'
```

or:

```powershell
$env:PROJECT_DB_DEMO_PROJECT_ID='94d15ea83f8a47289f504af3a6b005b6'
```

Do not commit either value as normal product logic.
