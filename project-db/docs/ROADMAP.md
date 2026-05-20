# ALTA Roadmap

**Date:** 2026-05-14
**Authority:** [`STRATEGY.md`](STRATEGY.md). This roadmap is the execution
plan for the strategy; if they disagree, STRATEGY.md wins.

**Reading guide:** Phases are sequential. Don't start phase N+1 work until
phase N has produced visible value to a PM. Items inside a phase can be
parallelized.

---

## Phase 0 — Foundation (DONE, do not redo)

The plumbing is built. Do not redesign it. Document it if confused; do not
rewrite.

- [x] Canonical schema: 13 entities + ExternalId bridge
- [x] Identity resolver: exact + fuzzy match, NoMatcher default
- [x] Monday connector: full board/item read, column extraction, write-back via `sync_back`
- [x] Monday mirror-column overlay: pulls task status/timeline from linked portfolio items
- [x] Google Drive connector: 750 documents, full metadata, recursive walk to depth 20
- [x] Folder→Project linking via civic-number + substring match (300 of 750 docs linked)
- [x] Drive delta sync via `changes.list` cursor
- [x] OAuth Desktop auth flow (`project_db gdrive-auth`)
- [x] One consolidated SQLite location, absolute path in `.env`
- [x] Test suite (was 131; grew to 250+ through Phases 1 and 2)

---

## Phase 1 — The Brain Foundation (DONE 2026-05-15)

Goal: every Drive document with parseable content has indexed text tied to
its canonical Project, and there is a place to store LLM proposals without
mutating canonical fields.

- [x] `DocumentText` SQLAlchemy model: `document_id` (FK), `extracted_text` (TEXT), `extraction_method`, `extracted_at`, `token_count`
- [x] `ensure_sqlite_schema` migration for both `DocumentText` and `Proposal`
- [x] `pymupdf`, `python-docx`, `openpyxl` added under `[content]` optional deps
- [x] `gdrive/extractors.py` with one function per mime type (PDF / DOCX / XLSX / Google Docs / Google Sheets); lazy imports so the codebase loads without the libs
- [x] Wired extractors into `GDriveConnector` (`extract_content` flag, default off — CLI is primary entry). 10 MB cap. Trashed docs skipped. Unsupported mime auto-`skipped-mime`.
- [x] `project_db extract-content [--project] [--overwrite] [--limit]` CLI; idempotent; periodic commits; Ctrl-C handling
- [x] `Proposal` SQLAlchemy model with all fields + ProposalStatus enum
- [x] **Bonus:** Drive sync reconciliation soft-marks vanished files (was insert-only before)
- [x] **Bonus:** SQLite FK enforcement turned on (`PRAGMA foreign_keys=ON`); CASCADE now actually works
- [x] Tests: 60+ across the three new files (`test_phase1_models`, `test_gdrive_extractors`, partial coverage in `test_gdrive_enhancements`)

**Phase 1 exit test — PASSED:** ran `project_db extract-content` over the
full 750-doc tree. **457 documents** with non-empty text, every one with
a token_count. Spot-check on real contract text (Petro.docx, Tony Estimate.pdf,
Alta Construction Group - contract.pdf) confirms readable output.

---

## Phase 2 — Tier-1 AI (deterministic reports, no LLM) — DONE 2026-05-15

Goal: PMs have at least three queries they hit daily that they couldn't
run before, with zero AI involved. This builds trust before introducing
probabilistic outputs.

- [x] `project_overview` — one-screen snapshot (tasks, docs, invoices, logs, client, external IDs)
- [x] `docs_for_project` — every Document with folder_path, size, modified date, ordered by folder
- [x] `tasks_without_dates [--project]` — Monday tasks missing start/end/due dates
- [x] `missing_documents` — projects with zero contract-shaped docs (PDF / Google Doc / DOCX)
- [x] `budget_vs_contract` — regex `$amounts` from extracted contract text vs Monday budget; flags >15% divergence. Regex swaps for LLM extraction in Phase 3 (same output shape).
- [x] All wired through `project_db ask "..."` with natural-language project-ref extraction (UUID or "project <name>")
- [x] `ask "help"` lists every routed pattern for non-technical users
- [x] 46 new tests; reports importable from `project_db.ai.views` for Phase-3 LLM tool layer

**Phase 2 exit test — PASSED:** all 5 reports verified against the live DB.
- `tasks_without_dates` → 137 dateless tasks surfaced
- `missing_documents` → 1 PROPOSED project flagged
- `project_overview` → real Project (Rockland: 1 task, 18 docs, 0 invoices)
- `docs_for_project` → 18 docs for Rockland with folder_path context
- `budget_vs_contract` → 5768-5770 St Laurent contracts produced real $ extractions; the report honestly returns `divergence_pct=null` when Monday budget is unset rather than fabricating

---

## Phase 3 — Tier-2 AI (LLM proposals)

Goal: the LLM reads a project's contract text plus its current Monday
state and produces structured suggestions that land in the `Proposal`
table. Nothing is auto-written to Monday.

**Refined plan (2026-05-15):** target architecture is a local model
(Qwen / DeepSeek / MiniMax tier) on dedicated hardware (Mac mini),
with optional Anthropic provider for prototyping while the box is
being set up.  Build provider-agnostic infrastructure FIRST.

**Session 3a — Provider abstraction + context assembler (DONE 2026-05-16)**
- [x] `LLMProvider` interface in `ai/providers/base.py`.  OpenAI Chat
      Completions shape canonical; `complete_json` retry helper on base.
- [x] `MockLLMProvider` (deterministic, for tests)
- [x] `AnthropicProvider` (real, for prototyping pre-hardware)
- [x] `OpenAICompatibleProvider` (Ollama/vLLM/llama.cpp — zero new code
      when local hardware arrives)
- [x] `get_default_provider()` env-var resolver
- [x] `assemble_project_context(session, project_id)` — full join,
      configurable token budget, evicts doc bodies oldest-first
- [x] 41 new tests
- [ ] ~~Monday `activity_logs(from, to)` delta-sync~~ — moved to start
      of 3b so 3a stayed model-layer-focused

**Session 3b part 1 — Proposal engine (DONE 2026-05-17)**
- [x] `generate_timeline_proposals()` — context → LLM → validated `Proposal` rows
- [x] Timeline-extraction prompt (instruction-at-tail; LLM references tasks by integer index, never UUID)
- [x] Per-item validation: index range, date parse, end≥start, confidence clamp; bad items recorded not raised
- [x] Auto-supersede prior PENDING proposals for the same `(entity_type, entity_id, field_name)`
- [x] `list_proposals()` / `get_proposal_detail()` read side
- [x] CLI: `propose timelines`, `proposals list`, `proposals show`
- [x] 32 tests on MockLLMProvider; live-verified on 923 Rockland
- [x] ~~Monday delta sync~~ — already shipped in Session 3a (`sync monday --delta`)

**Session 3b part 2 — Approval actions + remaining prompts**
- [x] CLI: `proposals reject <id> [--reason] [--by]` — pure DB, PENDING-only guard (DONE 2026-05-18)
- [ ] CLI: `proposals accept <id>` — Monday write-back via `MondayConnector.sync_back`.
      NOTE: sync_back commits its own session — accept must write Monday
      FIRST, flip proposal status only on a True return.  Plan a
      `--dry-run` flag so the reviewer can preview the write.
- [ ] Prompt: scope reconciliation — `{scope_item, in_monday: bool, suggested_task_title, confidence}`
- [ ] Prompt: anomaly detection — `{anomaly_type, description, severity}`
- [ ] CLI: `propose scope / anomalies / all <project>`
- [ ] Tests: accept→write-back (mocked Monday client), double-accept idempotency

**Session 3b note:** prompt *quality* is unvalidated until a real model
(Claude API / Mac mini) is behind the provider.  The engine is built
and fully tested against `MockLLMProvider`; quality tuning is a
deliberate later pass, not a gap.

**Session 3c — Fine-tuning corpus + personality + local backend**
- [ ] `project_db export-corpus` — DocumentText + Monday data dumped as
      JSONL suitable for continued pretraining / fine-tuning
- [ ] `prompts/personality.yaml` — tone/style variables injected into the
      system prompt at runtime (formal / casual / verbose etc.)
- [ ] `LocalProvider` (OpenAI-compat HTTP) — plugs in when hardware ready;
      single config-line swap to flip from Anthropic → local

**Open design decisions before Session 3a (need user input):**
1. Provider API shape (recommended: OpenAI Chat Completions)
2. Structured-output strategy: ask-and-parse retries, `response_format=json_object`,
   or grammar-constrained decoding via vLLM/llama.cpp
3. Run Anthropic as the real provider during 3a/3b while hardware is sourced?
4. Fine-tuning corpus scope: contracts only, or contracts + Monday history
   + folder structures + civic mappings?

**Phase 3 exit test:** running `project_db propose all <project_id>` on
the 923 Rockland project produces at least one timeline proposal and one
scope flag that survives human review.

---

## Phase 4 — Approval Workflow

Goal: there is a clean human-in-the-loop pipeline from "LLM proposed X" to
"X is now reflected in Monday." This is what turns the LLM from a toy into
operational tooling.

- [ ] CLI: `project_db proposals list [--status pending] [--project <id>]` — table view of open proposals
- [ ] CLI: `project_db proposals show <proposal_id>` — full proposal detail incl. source document excerpts
- [ ] CLI: `project_db proposals accept <proposal_id>` — flips status to accepted, triggers Monday write-back via existing `sync_back`
- [ ] CLI: `project_db proposals reject <proposal_id> [--reason "..."]`
- [ ] Auto-supersede: if a new proposal lands for the same `(entity_id, field_name)`, mark the old pending one as `superseded`
- [ ] Audit log: every accept/reject writes to a `ProposalDecision` table (or extend Proposal with `decided_*` columns — already in schema above)
- [ ] Add tests: accept-flow writes back to Monday (mocked client), reject-flow doesn't, superseded handling, idempotency on double-accept

**Phase 4 exit test:** accept a real timeline proposal on a real project,
verify the Monday item gets the proposed dates without any manual
intervention.

---

## Phase 5 — Adoption

Goal: get the system into a PM's hands and verify it changes how they
work. This is where success or failure is determined.

- [ ] Pick one PM, one project. Run the full pipeline daily for two weeks.
- [ ] `project_db daily <project_id>` — single command that runs sync + content extraction + proposals + prints any new flags
- [ ] Optional Slack / email digest of new proposals (only if PM asks for it)
- [ ] Iterate on prompt quality based on actual rejection rate
- [ ] Decision point at 4-6 weeks: is it being used? Continue if yes. Stop or pivot if no.

**Phase 5 exit test:** the PM is opening ALTA before opening Monday at
least three times a week. If not, see STRATEGY.md §7.

---

## Future architecture notes (post-Phase-5)

These are user-articulated directions worth preserving so future
sessions don't re-derive them.  Not committed work; not next; not now.

**Dual-model architecture.**  Two configured providers running in
parallel:

  - **Fast** (small local model / Haiku tier): conversational
    layer for `ask`, query routing, simple Q&A.
  - **Deep** (big local model / Opus tier): proposal generation,
    contract-vs-Monday reconciliation, anomaly detection.

They share state through the canonical DB (`ProjectContext`,
`Proposal` table), not through token windows.  Already enabled by
the `LLMProvider` interface -- just instantiate two providers and
config-switch which one a given call uses.  Likely env-var pattern:
`LLM_PROVIDER_FAST` + `LLM_PROVIDER_DEEP`.

**RAG layer.**  Vector embeddings over `DocumentText` for
similarity-based retrieval.  Complements `assemble_project_context`
rather than replacing it: the assembler grabs structured canonical
spine (tasks / invoices / dates), RAG grabs fuzzy text chunks
("the deadline clause" in a 100-page contract).  Both feed the
same prompt.  Will need `pgvector` (= Postgres migration) or
`sqlite-vec` extension first.

**Domain-pretrained / fine-tuned local model.**  Continued
pretraining on the company corpus (DocumentText + Monday history
+ folder structures + civic mappings) so the model speaks our
internal language out of the box.  The exporter is Session 3c;
the actual fine-tuning happens on the dedicated hardware
(Mac mini / dedicated GPU box) and is not a code task in this
repo.

---

## Deferred (per STRATEGY.md — explicitly NOT next)

These are real items but they are plumbing-not-brain. Do not pick them up
until Phase 5 is in a known-good state.

- [ ] CompanyCam connector (photos)
- [ ] QuickBooks live test + invoice sync
- [ ] Webhook receivers (replaces polling on Monday) — note: `create_webhook` is a scriptable mutation in the live Monday API; the actual blocker is hosting a public HTTPS endpoint
- [ ] Monday `activity_logs(from, to)`-based delta sync — lightweight, no hosting needed; reasonable to fold into a Phase-3 session
- [ ] Postgres + Alembic migrations
- [ ] `pgvector` for semantic document search
- [ ] Text-to-SQL natural language layer
- [ ] Multi-tenant / multi-org support
- [ ] Resource / crew scheduling

---

## How to use this roadmap

When tempted to start work on something, check it against three rules:

1. Is it in the current phase? If no, postpone.
2. Does it directly serve the Phase exit test? If no, drop scope.
3. Does it contradict an operating principle in STRATEGY.md? If yes, stop.

The roadmap is a contract with the strategy, not a wishlist.
