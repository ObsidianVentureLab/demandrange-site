# Stage 5 — searchable client database: design (P5)

Status: proposal plus a minimal, tested SQLite implementation (`pipeline/clientdb.py`, CLI `python -m pipeline db`).
Decision for Sean at the end.

## What exists today
The only system of record is the restricted Google Sheet written by the quote-form Apps Script: one tab
of raw submissions (31 columns, `quote-form/form_schema.json` → `raw_response_columns`), triage fields
(`intake_status`, `assigned_owner`, `first_response_at_utc`, `outcome`, `retention_review_at`) edited
by hand, and controlled Taxonomies/Config tabs. Briefs (P2 JSON), verified lists (P3) and deliveries (P4)
are files on disk with manifests. Nothing joins "this client asked for X, we agreed brief Y, we delivered
list Z on date D".

## Goals
1. Answer in one query: who is this client, what did they ask, which brief was agreed, what was delivered
   and when, and what is due for retention review.
2. Import from the Sheet export without changing the Sheet or the Apps Script (the Sheet stays the
   intake system; the database is downstream).
3. Idempotent and auditable: re-importing the same export is a no-op; every delivery row points at a
   manifest sha256; every request row records which import wrote it.
4. Zero infrastructure and zero new accounts for now; a clean path to Postgres later.
5. Personal data stays minimal and local: the database file lives outside the repository and is never
   committed; no new personal fields are collected beyond the Sheet's.

## Why SQLite first (and the Postgres path)
- One operator, a few hundred requests a year, file-based backups: SQLite (standard library) is enough
  and removes hosting, credentials and cost. WAL mode, foreign keys on.
- The schema uses only portable SQL (TEXT/INTEGER, CHECK constraints, composite keys). Moving to Postgres
  is `pg_dump`-free: run the same DDL (adjust `INSERT OR REPLACE` to `ON CONFLICT`), copy rows. Do this
  when a second operator needs concurrent writes or when a hosted dashboard is wanted.
- Full-text search: v1 uses `LIKE` over a few columns (works on every SQLite build). If volume grows,
  add an FTS5 virtual table over `requests` in a schema migration (`meta.schema_version` exists for that).

## Schema (v1)
| table | key | purpose |
|---|---|---|
| `meta` | key | schema_version, created_at, tool_version |
| `clients` | `client_ref` (slug; the same value P4 stamps) | name, website_domain, status prospect/active/dormant/closed, notes |
| `requests` | `submission_id` | all 31 Sheet columns as TEXT exactly as exported + `client_ref`, `imported_at`, `import_sha256` |
| `imports` | `import_sha256` | one row per Sheet export file processed (rows read/new/updated) |
| `briefs` | `brief_ref` | client, version, supplier_range, status draft/agreed/superseded, sha256 of the brief JSON |
| `deliveries` | (`client_ref`, `export_id`) | from P4 MANIFEST.json: brief/dictionary/export versions, exported_at, rows, columns, manifest sha256, folder (the absolute local path at record time, so it names a workstation; blank or rewrite it before the database is shared or migrated); `delivered_at`/`delivered_via` set by hand when Sean has sent it |
| `delivery_files` | (…, kind, file_name) | input and output files of each delivery with sha256 |

Client linkage on import: `clients.client_ref = slugify(company_name)`, `website_domain` from
`company_website` or the work-email domain. This is deliberately simple; mismatched spellings make two
clients, which the operator merges by editing (a `merge-client` command is a listed follow-up).
No automatic matching on people's names.

## Data protection notes
- The requests table is personal data (names, work emails, phone numbers). Keep the `.sqlite` file in a
  restricted location with the same access rule as the Sheet; back it up with the same care; never put it
  in Git, a shared drive without access control, or a ticket. The repository `.gitignore` refuses
  `*.sqlite`, `*.sqlite3`, `*.db` and their `-wal`/`-shm` sidecars as a backstop; the rule is still to keep
  the file outside the checkout entirely.
- `retention-due` lists requests whose `retention_review_at` has passed, so the Sheet's retention rule
  (`RETENTION_MONTHS`) can be applied in both places. Deletion itself is a manual, logged decision.
- Imports store exactly what the Sheet exported; no enrichment of people. Company-level enrichment
  (P2) and verification (P3) stay in their own files and are referenced only by sha256.
- Search output is for the operator's terminal; it is not exposed over a network.

## Operating procedure (manual, no automation yet)
1. `python -m pipeline db --db /secure/path/demandrange.sqlite init`
2. In the Sheet: File → Download → CSV of the Raw Responses tab → `db import-sheet export.csv`
   (repeatable; changed triage fields are updated by `submission_id`).
3. `db add-brief --brief-ref … --client-ref … --status agreed --file brief.json` when a brief is agreed.
4. After `python -m pipeline export …`: `db record-delivery <folder>/MANIFEST.json`.
5. After sending by hand: `db mark-delivered --client-ref … --export-id … --via "…"`.
6. `db search <term>`, `db client <ref>`, `db retention-due`, `db summary`.

## Not in v1 (follow-ups, each small)
- `merge-client`, client notes editing, CSV export of a client's history.
- FTS5 search; a read-only local web page (stdlib http.server) if a UI is wanted.
- Automatic Sheet export (would need a Google API credential; an account action for Sean).
- Postgres deployment.

## Decision for Sean
Accept SQLite-first as above (recommended: nothing to host, nothing to pay, same SQL later), or go
straight to a hosted Postgres (needs an account, credentials handling and a backup plan before any
personal data is loaded).
