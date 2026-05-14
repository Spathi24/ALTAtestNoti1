# Google Drive Integration Plan

> **HISTORICAL — kept for context, no longer the source of truth.**
> The Google Drive connector is now live as of 2026-05-14. For the current
> state and forward plan see [`STRATEGY.md`](STRATEGY.md) and
> [`ROADMAP.md`](ROADMAP.md). This document is preserved because its
> *rationale* (using Drive contracts to fill gaps in Monday task data) is
> exactly what STRATEGY.md operationalizes; the implementation details below
> have largely been realized.

**Status:** Implemented 2026-05-14. 750 documents syncing, 300 linked to projects.
**Original owner notes:** next-up integration after we verify the QuickBooks connector live.
**Why this matters for our data-arbitration goal:** Drive contains the
contracts, scopes of work, and quotes that hold the timeline / budget /
deliverable detail Monday tasks are missing. Once Drive is syncing, an LLM
layer can read the scope-of-work for "923 Rockland", compare against the
14% of Monday tasks that have dates, and propose plausible durations for
the other 86%.

---

## 1. Auth: service account with domain-wide delegation

Use a **service account with domain-wide delegation (DWD)**, not OAuth user
consent. OAuth ties the refresh token to one human; if they leave, sync
breaks. A service account is headless: a JSON key in env, no consent UI,
no token expiry babysitting. An admin grants the account access org-wide
once via the Workspace Admin console (Security > API controls > Domain-wide
delegation). At runtime we impersonate (`subject=user@altagroup.com`) an
ops/admin user that's been added to every project shared drive.

Required scope for read-only metadata + content:

```
https://www.googleapis.com/auth/drive.readonly
```

This is the right one — broader than `drive.metadata.readonly`, narrower
than full `drive`. Avoid `drive.file`: it limits access to files the app
created or were picker-shared, which doesn't fit a sweep-everything sync.

Both `drive.readonly` and `drive.metadata.readonly` are **restricted
scopes**. For an internal-only OAuth client owned by our Workspace org the
CASA security assessment is waived; if we ever distribute it externally,
audit kicks in.

Docs:
- https://developers.google.com/workspace/drive/api/guides/api-specific-auth
- https://developers.google.com/identity/protocols/oauth2/service-account

---

## 2. API surface (Drive REST v3)

| Need | Endpoint | Notes |
|---|---|---|
| Recursive folder list | `files.list(q="'<folderId>' in parents and trashed=false")` | No native recursion. Paginate via `pageToken`. **Always** pass `supportsAllDrives=true&includeItemsFromAllDrives=true` or shared-drive items silently disappear. Use `fields="nextPageToken,files(id,name,mimeType,modifiedTime,size,md5Checksum,parents,driveId,webViewLink,trashed)"` to cut payload. |
| **Delta sync** | `changes.getStartPageToken` once, persist; then `changes.list(pageToken=...)` | **Headline win over Monday.** Returns everything modified, renamed, moved, or deleted. `newStartPageToken` becomes the next cursor. Pass `includeRemoved=true` to see deletions. (Monday API-Version 2026-07 has nothing like this.) |
| Read Google-native (Docs/Sheets) | `files.export(fileId, mimeType="application/pdf")` or `"text/plain"` | 10 MB export cap. Use text/plain for LLM ingestion. |
| Read binary (PDF, DOCX, DWG, JPG) | `files.get(fileId, alt='media')` | Streams. |
| Detect moves/renames/deletions | `changes.list` change entries include `removed: true` and updated `parents` | Already covered by delta sync. |

Rate limits: 1M quota units/min per project, 325k/user/min. `files.list` = 100 units, `files.get` = 5, downloads = 200. Wrap calls in exponential backoff on 403 `userRateLimitExceeded` and 429.

Docs:
- https://developers.google.com/workspace/drive/api/guides/search-files
- https://developers.google.com/workspace/drive/api/guides/manage-changes
- https://developers.google.com/workspace/drive/api/guides/manage-downloads
- https://developers.google.com/workspace/drive/api/guides/limits

---

## 3. What lands in `Document`

The existing canonical model is `Document(name, mime_type, url, storage_ref, project_id, deal_id, client_id)`. Per Drive file:

| Canonical field | Drive field |
|---|---|
| `name` | `name` |
| `mime_type` | `mimeType` |
| `url` | `webViewLink` |
| `storage_ref` | `id` (the stable Drive file id) |
| `project_id` | resolved via matcher in step 4 |

`ExternalId(source='GOOGLE_DRIVE', entity_type='Document', external_key=fileId)` maps the canonical UUID back to the Drive id.

Worth persisting outside the canonical row (sidecar table or a `meta` JSON
column when we add one): `modifiedTime`, `size`, `md5Checksum`, `parents[0]`,
`driveId`, `owners[0].emailAddress`. The **`md5Checksum`** is the cheap
"did content actually change" signal — short-circuit LLM re-extraction
on hits.

Consider one new canonical entity: **`Folder`** (or reuse `Document` with
a synthetic mime). Folder paths are how Drive encodes project membership;
preserving the tree lets us re-resolve project linkage when files move.

---

## 4. Linking Drive files to canonical Projects

Two-stage matcher:

1. **Folder-name match (primary, ~95% of cases).** Walk a configured root
   ("Active Projects", "Archive") one level deep. For each top-level
   subfolder, normalize the name (lowercase, strip punctuation, collapse
   whitespace, extract a leading civic number or hyphenated range like
   `5768-5770`). Match against `Project.name` and `Property.address` with
   the same normalizer. Cache the resolved `(driveFolderId → projectId)`
   in `ExternalId` so file syncs are O(1) thereafter.

2. **Content fallback.** For files under an unrecognized folder, run a
   lightweight address regex (`\b\d{2,5}\s+[A-Z][a-zA-Z\-' ]+\b`) over the
   first page of extracted text. Match candidates against `Property.address`.
   **Flag low-confidence (<0.8) matches as `needs_review` rather than
   auto-linking.** (Same principle as the existing connectors: no silent
   merges, ambiguous cases get a human.)

Don't try to be cleverer than that. The long tail of construction-doc
weirdness eats clever matchers.

---

## 5. Sample client skeleton

To go in `src/project_db/connectors/gdrive/client.py`:

```python
from __future__ import annotations
import os
from google.oauth2 import service_account
from googleapiclient.discovery import build

SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]

class GDriveClient:
    def __init__(self, impersonate: str | None = None):
        creds = service_account.Credentials.from_service_account_file(
            os.environ["GDRIVE_SA_KEY_PATH"], scopes=SCOPES,
        )
        sub = impersonate or os.environ.get("GDRIVE_IMPERSONATE")
        if sub:
            creds = creds.with_subject(sub)
        self.svc = build("drive", "v3", credentials=creds, cache_discovery=False)

    def list_folder(self, folder_id: str) -> list[dict]:
        out, token = [], None
        while True:
            resp = self.svc.files().list(
                q=f"'{folder_id}' in parents and trashed=false",
                fields="nextPageToken,files(id,name,mimeType,modifiedTime,size,md5Checksum,parents,webViewLink)",
                pageSize=1000, pageToken=token,
                supportsAllDrives=True, includeItemsFromAllDrives=True,
                corpora="allDrives",
            ).execute()
            out.extend(resp.get("files", []))
            token = resp.get("nextPageToken")
            if not token:
                return out
```

Add to `requirements-dev.txt`: `google-api-python-client`, `google-auth`.

---

## 6. Open questions and risks

- **Shared drives vs My Drive.** Biggest gotcha. Every `list/get/changes`
  call needs `supportsAllDrives=true` and `includeItemsFromAllDrives=true`;
  list calls also need `corpora="allDrives"` (or a specific `driveId`).
  Forget any one and items silently vanish — no error. The impersonated
  user must also be a member of each shared drive.

- **Permissions cliff.** Files outside the impersonated user's visibility
  are invisible — no 403, just absent. If a PM stores contracts in a
  personal subfolder they didn't share, you'll never see them. Pick an
  impersonation subject who's deliberately on every project drive, and
  audit gaps before relying on completeness.

- **Large binaries (CAD/DWG, big PDFs).** `files.get(alt=media)` streams
  fine, but a 200 MB DWG eats download quota (200 units each) and isn't
  LLM-readable. Gate by `size` and `mimeType`: store metadata for
  everything; only fetch bytes for `application/pdf`, Google-native docs,
  and `.docx`. Cap at ~25 MB; tag larger files `content_skipped`.

- **Export size cap.** `files.export` is hard-limited to 10 MB. A
  200-page scope-of-work Google Doc will fail at PDF export; fall back
  to `text/plain` (much smaller) or treat as `content_skipped`.

- **Token storage.** Service account JSON is a credential — keep it out
  of the repo. `GDRIVE_SA_KEY_PATH` env var pointing at a file outside
  the tree, or use a secret manager.

- **Naming collisions.** Two projects with the same civic number on
  different streets are a real risk in our data; folder-name match alone
  will misfile. Always run the content fallback as a confidence check on
  ambiguous folder names.

---

## Asymmetry summary vs Monday and QuickBooks

| Capability | Monday | QuickBooks | Google Drive |
|---|---|---|---|
| Delta sync | ❌ Removed in 2026-07 | ✅ `WHERE UpdatedTime >` | ✅ `changes.list` (best of three) |
| Auth complexity | Static token | OAuth + refresh dance | Service account JSON (simplest after first setup) |
| Unique hard parts | Mirror-column gymnastics | OAuth token expiry / realm IDs | Shared-drive flags, impersonation scoping, mime-type-conditional content reads |

Drive is the easiest of the three for ongoing sync once the initial
service-account + shared-drive plumbing is right.

---

## Phase plan for shipping the connector

1. **Plumbing (½ day):** Service account setup in Workspace admin, env vars,
   `pip install google-api-python-client google-auth`, smoke-test
   `GDriveClient.list_folder(root_id)` against one real project folder.
2. **Read-only metadata sync (1 day):** `GDriveConnector` that pulls every
   file under a configured root and upserts `Document` rows. Folder-name
   matcher for project linkage. `ExternalId` registration. Test suite
   following the Monday connector pattern.
3. **Delta sync via `changes.list` (½ day):** Persist `startPageToken` per
   organization. Daily cron does `changes.list` only. Move the full crawl
   to a manual `--reseed` flag.
4. **Content extraction for LLM (1–2 days):** Branch by mime type; export
   Google Docs to text; download PDFs and DOCX; skip everything else.
   Store extracted text on a sidecar table.
5. **Data arbitration v0 (open-ended):** LLM prompt that takes a Project
   + its extracted scope-of-work + its existing Monday tasks and proposes
   timelines for the tasks missing them. Surfaces as `Task.proposed_*`
   columns or a separate `TimelineProposal` entity — design later.
