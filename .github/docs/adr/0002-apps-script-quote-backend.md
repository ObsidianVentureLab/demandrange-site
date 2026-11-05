# 0002. Quote requests go to a Google Apps Script web app that writes to a restricted Sheet

Status: Accepted (records the existing setup)
Date: 2026-11-04

## Context
The static site (ADR 0001) has no server of its own, but `/request-a-quote` has to accept enquiries. The volume is small, the business already runs on Google Workspace, and enquiries contain personal data (a business contact's name and work email), so where they are stored and who can read them matters more than features.

## Decision
- The form posts to a Google Apps Script **web app**. The handler validates every field against an allow-list, rejects anything else, de-duplicates, and appends the enquiry to a **restricted Google Sheet** (named editors only). Statuses run new → quote sent → closed.
- The handler's allowed values (regions, industries, seniority, privacy-notice version, consent version) must match what the live form sends. Regions are `IE`, `UK`, `EU`; the older `EMEA`, `NAM`, `LATAM`, `APAC`, `ANZ` stay accepted for compatibility. Accepted privacy-notice versions are `2026-09-11-v1` and `2026-10-28-v1`, and the submitted version is recorded with the enquiry.
- A drift-guard test (in the handler PR, #56) fails CI if the form's checkbox values or version fields are not a subset of the handler's and the form schema's lists.
- Runtime switches are Script Properties, not code: `MODE` (production or test), `PAUSED`, `RETENTION_MONTHS`, and an optional HMAC-signed notification webhook (`NOTIFICATION_WEBHOOK_URL`, `NOTIFICATION_WEBHOOK_SECRET`), which is not configured.
- **Only Sean deploys.** A handler change is prepared and tested in a pull request, then Sean pastes it into the existing Apps Script project and publishes it as a **new version of the existing deployment**, so the web-app URL in the form does not change. Agents never run `clasp push` or deploy, and never send test submissions to production.

## Consequences
- No server, no database and no extra cost; access control is Google Workspace's.
- The deployed script is not in Git. The repository holds the reviewed source, and its sha256 is recorded in the redeploy package so the deployed copy can be checked by hand. A fix is only live once Sean has redeployed it, so release notes must say when a fix is waiting on a redeploy.
- Form and handler can drift (this happened with the region list), which is why the drift-guard test exists and why form changes and handler changes travel in the same PR.
- Enquiry notification is still open: Sheet change notifications (no code) or the signed webhook to a receiver. That is Sean's decision.
