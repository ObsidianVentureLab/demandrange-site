# Apps Script deployment — owner handoff

Status: code prepared; Google authentication and production deployment pending.

## Manifest correction — v0.3

The v0.2 manifest omitted `https://www.googleapis.com/auth/userinfo.email`, required by `Session.getEffectiveUser()` in `protectOwnerOnly_`. Use the corrected manifest from v0.3; an owner who already pasted Code.gs only needs to replace appsscript.json, save, then run setupSpreadsheet and review the renewed permissions. This added permission reads the executing account's email identity; it does not grant inbox-reading or email-sending access. Do not remove sheet-protection code to bypass the error.

The earlier setup may have created Raw Responses and its headers before stopping at owner identification; verify the final tabs/protections after rerun. Rerunning setup preserves intake rows but rewrites the controlled Taxonomies and Config tabs, so it is for this new dedicated Sheet, not an instruction to reset a populated operational workbook.

Run `node tests/test_manifest.js` and `node tests/test_local.js` from the quote-form directory before handoff. These local tests do not verify Google authorization or live storage/notifications. Reference: https://developers.google.com/apps-script/reference/base/session#geteffectiveuser

## Required owner actions

1. Sign in to the intended Demand Range Google Workspace account.
2. Create a private spreadsheet named `DemandRange — Quote Requests — Restricted`.
3. Create a standalone Apps Script project owned by the same Workspace owner.
4. Add `Code.gs` and `appsscript.json` from this directory.
5. In Script Properties set:
   - `SPREADSHEET_ID` — exact ID segment between `/d/` and `/edit` in the restricted Google Sheet URL, not the full URL or Apps Script project ID.
   - `MODE` — `test` for synthetic acceptance, then `production` only after approval.
   - `PAUSED` — `true` until synthetic acceptance passes.
   - `RETENTION_MONTHS` — approved integer; code defaults to 24 only when omitted.
   - `NOTIFICATION_WEBHOOK_URL` — optional HTTPS Miranda receiver; required before claiming Miranda alerts live.
   - `NOTIFICATION_WEBHOOK_SECRET` — optional HMAC secret paired with that receiver. Never put it in Git, the Sheet or website JavaScript.
6. Run `setupSpreadsheet()` once and verify tabs/headers/protections manually. Restrict sharing to named editors; never use “anyone with the link”.
7. Deploy a test web app executing as the owner. Keep public/anonymous access disabled until all synthetic tests and privacy approval pass.
8. Set `PAUSED=false`, submit only the `.example` fixture, verify exactly one Synthetic QA row, then test duplicate and invalid payloads.
9. After approval, set `MODE=production`, freeze a numbered deployment version and provide the exact `/exec` URL to Miranda for the site build.

## Blocked security choice

The backend supports a sanitized HMAC-signed notification webhook. No Telegram bot token belongs in this Apps Script. The public receiver and secret route must be separately approved/configured before notifications are called live.

## Release rule

Do not publish the page until the exact production URL, private Sheet readback, notification receipt, privacy wording and GitHub Pages release have passed together.
