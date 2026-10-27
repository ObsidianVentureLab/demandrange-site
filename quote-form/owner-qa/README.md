# Owner-only quote storage check — v1

Status: **Locally tested; live owner execution pending.** This is a separate, editor-only diagnostic, not part of the public deployment pack. Source: `OwnerQA.gs`. Linked operational record: `/root/miranda/vault/02-Projects/DemandRange Quote Form and Lead Notification Plan - 2026-09-11.md`.

## Purpose and bounds

The owner-only Web app GET now displays the expected Quote requests page. This helper advances to actual Google Sheet storage verification without making the app public or unpausing web collection. It runs the existing parser and persistence functions directly from the editor. It is **not** a deployed HTTP POST or browser-form test and sends no notifications.

It requires Sean's executing identity, MODE exactly `test`, PAUSED exactly `true`, a bare spreadsheet ID, the expected form version, required tabs, exact Raw Responses/Synthetic QA headers and restricted whole-sheet protections. It stops before writing when those checks fail. The test properties passed to persistence are pinned to the test tab and original spreadsheet ID; no global properties are changed. A one-month review marker is used for the fictional fixture only, not as an approved business retention policy or automated deletion rule.

It creates or reuses one fixture identified by token `DRQ_OWNER_STORAGE_QA_20260911_V1` in Synthetic QA, checks stored identity/contact/scope values, marks notification state `not_tested_owner_qa`, checks duplicate suppression, and verifies Raw Responses row count is unchanged. No real person's contact details are supplied. Rerunning reuses the same fixture rather than deleting rows. A failed check can leave the labelled fixture for inspection; no failure should be described as a pass.

## Owner steps

1. In the existing Apps Script editor, click Files **+ → Script** and name it `OwnerQA`.
2. Replace only that new file's default contents with the complete provided OwnerQA text. Do not replace Code.gs or appsscript.json.
3. Save; choose `runOwnerStorageTest` from the function dropdown and Run once. Do not run setupSpreadsheet and do not redeploy.
4. If permissions/errors appear, stop and provide the screen; do not remove protections or alter MODE/PAUSED to force a pass.
5. On completion provide the execution-log result. Expected successful result label is `PASS_EDITOR_STORAGE_ONLY`, with notification `NOT_ATTEMPTED`. This is an expectation, not a recorded live result.
6. Inspect the marked fictional row in Synthetic QA as separate Sheet-side readback. A screenshot should contain only this fixture and headers, not real personal data.

Keep the helper out of later production deployments: remove the separate OwnerQA editor file after the test evidence is captured and before freezing a public release version. Do not delete or overwrite the intake backend. The current Version 1 deployment is unchanged by adding/saving an editor-only test file; no new deployment is needed for this editor test.

## Local verification

Commands from quote-form root:

```sh
node tests/test_owner_qa.js
node tests/test_manifest.js
node tests/test_local.js
```

Executed results: 15 local mock scenarios passed, alongside the manifest regression and existing backend/schema suite. The harness executes actual Code.gs plus OwnerQA.gs with explicit fake Google services; it verifies successful repeatable fixture handling, test-only writes, no property changes, no network calls, fail-closed mode/pause/identity/ID/header/protection checks, storage failure and corrupted-readback failures. Full mock report: `local-test-results.json`.

Google APIs, current deployed code, real HTTP POST, client form, notification receipt and outage recovery are not validated by those local tests. Do not substitute their output for Sean's live execution/readback. Canonical plan remains the source of truth for remaining activation gates.
