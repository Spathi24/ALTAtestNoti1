# Project Log Image Ingestion — Spec + Build Status

**Status: MVP BUILT 2026-06-17.** All six priority steps shipped:
(1) classifier route, (2) DB tables, (3) vision structured extractor,
(4) deterministic hours validation, (5) CSV export + Drive-scanner skip,
(6) idempotent dedup. Code: `ai/project_log_extraction.py`,
`ai/project_log_export.py`, `db/models/project_log.py`, the fork in
`ai/email_intake.py`, and the `project-logs` / `poll-mail --no-project-logs`
CLI. ~120 tests across `tests/test_project_log.py`,
`tests/test_project_log_email.py`, plus the generated-folder skip test in
`tests/test_gdrive_connector.py`. **Not yet exercised on a real emailed sheet**
(needs OPENAI_API_KEY + gmail-auth) — that is the adoption step. Deferred:
PDF rendering to image, fuzzy employee matching, employee profile UI, analytics.

Original plan below (kept for reference). Decided 2026-06-17: built *after*
financial Phase 1d (Ledger Health).

A real ALTA Project Log sheet is going to be emailed in (images/PDF). This is an
**immediate-use, adoption-driven** feature — a usable labour-log archive, NOT a
payroll/timekeeping system.

---

## What this is (and is NOT)

A standardized paper form, titled **ALTA PROJECT LOG**, photographed/scanned and
emailed in. It records worker attendance/time at a job site:

```
Site Name (top box)
Table: Date | Name | Time Arrived | Time Left | Lunch Hours | Total Hours | Supervisor Signature
```

It is **a structured labour/time log**. It is **NOT**:
- a field note (do not route through field-note extraction)
- a financial document
- a source for inferring tasks/work activity (it only records who/where/when/hours/signature)

---

## Critical design rule (do not violate)

**The canonical DB is the source of truth. Write it directly during email
ingestion, THEN mirror/export to Drive for humans.** Do NOT rely on "push to
Drive and wait for Drive sync" — that creates delay, duplicate risk, and a loop
where generated CSVs get re-ingested as new raw documents.

Generated outputs live under a generated-reports folder the Drive scanner
**skips**, e.g. `/ALTA Generated Reports/Project Logs/...`.

---

## What ALREADY EXISTS in the repo (reuse — ~70% of the plumbing)

| Spec need | Existing |
|---|---|
| Email transport + dedup | `ai/email_intake.py` — Gmail poller, `EmailIngest` dedup by `gmail_message_id`, idempotent, N7 outbound-only |
| Vision extraction | `ai/field_note_extraction.py` — `_load_image_b64`, OpenAI `image_url` data-URL blocks (`detail="low"`; bump to **`high`** to read a handwritten grid) |
| Attachment storage + image detection | `email_intake._store_attachment`, `field_note_extraction._IMAGE_EXTS` |
| Project/site resolution | `email_intake._resolve_project_id` — plus-tag → worker default → env |
| Employee/Person table | **`Worker` model already exists** (display_name, email, phone_gateway_email, verified, active, default_project_id) — REUSE as "Employee"; do not build a parallel table |
| Direct-DB-write pattern | already how `EmailIngest`/field notes work |

**Genuinely new work:** (1) a **classifier branch** in `email_intake._process_one`
(today every email goes straight to field-notes — no fork); (2) two tables
(`ProjectLogSubmission` / `ProjectLogEntry`); (3) a vision prompt + strict-JSON
schema for the time table; (4) deterministic hours validation; (5) Drive
CSV/Excel export + generated-folder skip rule; (6) optional `WorkerAlias`.

Estimate: **1–2 focused sessions**, not the 3–4 the spec length implies.

---

## Classification rule

Before field-note extraction, classify the attachment/image. If it contains
`ALTA PROJECT LOG` and/or a table with columns ~
`Date | Name | Time Arrived | Time Left | Lunch Hours | Total Hours | Supervisor Signature`:

```
document_type = "project_log"  → route to ProjectLogExtractor
```

If uncertain:
```
ingestion_status = "quarantined"
ingestion_reason = "low_confidence_project_log_classification"
```
Never silently process as a field note.

**Pipeline:** email intake → attachment classifier → if project_log:
ProjectLogExtractor → deterministic validation → canonical DB write →
Drive/CSV/Excel export → audit/review status.

---

## Extraction strategy (controlled hybrid)

1. **Preprocess (deterministic, Pillow/OpenCV, optional):** rotate/deskew,
   detect page boundary, perspective-correct, crop to table, contrast. Fixed
   table geometry is OK after deskew if the layout is stable.
2. **Structured vision extraction → strict JSON only.** Model must NOT invent
   missing values; blank cells → `null`. Shape:

```json
{
  "document_type": "project_log",
  "site_name": "raw site name from top box",
  "classification_confidence": 0.0,
  "rows": [
    {"row_index": 1, "date": "YYYY-MM-DD or null", "name": "raw or null",
     "time_arrived": "HH:MM or null", "time_left": "HH:MM or null",
     "lunch_hours": 0.0, "total_hours_reported": 0.0,
     "supervisor_signature_present": true, "confidence": 0.0,
     "raw_notes": "anything ambiguous"}
  ]
}
```

3. **Deterministic validation (code, not model):** normalize date/times/lunch/
   total; compute `computed_total = time_left - time_arrived - lunch_hours`;
   compare to reported total within tolerance → `hours_mismatch`; flag missing
   date/name/time/total; discard blank rows. **Store both reported and computed;
   never overwrite reported silently.** The model extracts; code validates.

---

## Canonical DB shape

### ProjectLogSubmission (one row per submitted form/image)
```
id, project_id (nullable), site_name_raw, site_name_resolved (nullable),
source_email_message_id, source_attachment_filename, source_attachment_hash,
source_image_uri / drive_file_id, received_at, processed_at,
document_type="project_log",
classification_method = deterministic | vision_llm | manual,
classification_confidence,
ingestion_status = parsed | quarantined | failed | skipped,
ingestion_reason (nullable), extractor_version, raw_extraction_json
```

### ProjectLogEntry (one row per filled worker/time row)
```
id, submission_id, project_id (nullable), site_name_raw, site_name_resolved,
work_date (nullable),
employee_name_raw,            # NEVER discard, even if unresolved
employee_id (nullable),        # FK to Worker
employee_match_confidence (nullable),
employee_match_method = exact | alias | fuzzy | manual | unresolved,
time_arrived, time_left, lunch_hours,
total_hours_reported (nullable), total_hours_computed (nullable),
hours_mismatch (bool),
supervisor_signature_present (bool),   # present/absent, NOT interpreted as text
row_index, confidence, missing_fields_json, source_bbox_json (nullable),
source_meta_json, created_at
```

Do not require perfect project/employee resolution on first pass. Store raw,
resolve later.

### Employee layer (reuse `Worker`; add alias if low-friction)
`Worker` already exists — use it. Add `WorkerAlias` only if simple:
```
id, employee_id (→Worker), alias_text, source = manual|project_log|email_roster|imported,
confidence, created_at
```
Handwritten "Mike / Michael / M. Smith / Michel" may all map to one Worker later.

---

## Resolution

**Site/project priority:** (1) Site Name field → (2) email plus-address →
(3) subject/body hints → (4) sender roster default → (5) manual.
If unresolved: `project_id=null`, `ingestion_status="quarantined"`,
`ingestion_reason="unknown_site"`, still keep raw extraction.

**Employee priority:** (1) exact Worker.display_name/legal_name → (2) exact
WorkerAlias → (3) high-confidence fuzzy → (4) manual → (5) leave unresolved
(`employee_id=null`, `employee_match_method="unresolved"`). **A wrong match is
worse than unresolved.**

---

## Dedup
Key: `source_email_message_id + attachment_hash` (or `sha256(image bytes)` if
email metadata missing). Reprocessing the same attachment updates/replaces the
prior `ProjectLogSubmission` + entries idempotently.

## Statuses / reasons
`parsed | quarantined | failed | skipped`; reasons:
`low_confidence_project_log_classification, unknown_site, empty_form,
no_rows_detected, unreadable_image, validation_failed, duplicate_attachment,
parse_error`. An empty form is not an error → `skipped / empty_form`.

## Drive export
Append a human-readable file per site/project, e.g.
`/ALTA Generated Reports/Project Logs/{site_or_project}/project_log_entries.{csv,xlsx}`.
Columns: Received At, Source File, Site Name, Resolved Project, Date, Name,
Time Arrived, Time Left, Lunch Hours, Total Hours Reported, Total Hours
Computed, Hours Mismatch, Supervisor Signature Present, Confidence, Review
Status. **These generated files MUST NOT be re-ingested** — Drive scanner skips
`/ALTA Generated Reports/`.

---

## Acceptance criteria (MVP)
1. ALTA Project Log image classified as `project_log`. 2. Does NOT enter the
field-note pipeline. 3. Site Name extracted when present. 4. Filled rows →
`ProjectLogEntry`. 5. Blank rows ignored. 6. Missing fields stored null, not
invented. 7. Reported + computed hours both preserved. 8. Mismatches flagged.
9. Supervisor signature stored present/absent. 10. Raw image provenance
preserved. 11. Duplicate reprocessing idempotent. 12. Written directly to
canonical DB. 13. Project/site CSV/Excel updated in Drive. 14. Generated exports
not re-ingested. 15. Low-confidence images quarantined, not misprocessed.
Employee-layer: every nonblank row stores `employee_name_raw`; confident match
sets `employee_id`, else null + still stored; aliases map variants; basic
grouped-hours report works by raw name and by employee_id; no LLM for basic
rollups.

## Scope cuts (defer)
Payroll approval; perfect handwriting ID; treating it as financial/field-note;
inferring tasks; Drive-sync-as-DB-path; employee profile UI; productivity/value
scoring; trade inference; LLM pattern analysis. **Build employee LINKAGE now,
analytics later.** Same canonical DB (joins to Project/Document/Email/FieldNote/
MondayTask/FinancialLineItem); do not split storage prematurely.

## Implementation priority
1. Attachment classifier route (project_log vs field_note) →
2. DB tables (+ reuse Worker, optional WorkerAlias) →
3. Vision structured extractor →
4. Deterministic hours validation →
5. Drive export (+ generated-folder skip) →
6. Duplicate handling.

## Basic rollup views (deterministic SQL/Python, after ingestion works)
Hours by employee; hours by employee+project; daily attendance by project.
LLM (later) only summarizes computed facts — never invents productivity claims.

## Privacy
Employee data: preserve provenance per row; never delete raw source; avoid
uncertain matches; restrict employee report access if roles exist; log manual
corrections; distinguish raw vs reviewed/approved. This is a labour-log archive
+ reporting substrate, not payroll approval.
