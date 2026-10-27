# Demand Range quote-request form

Status: staged implementation; not deployed.

## Model

The page implements the approved internal 10% opportunity-signal / 90% fit-matched lookalike direction as a target mix. It does not promise exact fulfilment, intent, conversion or MQL status.

## Source files

- `form_schema.json` — canonical fields, limits, taxonomies and raw-sheet columns.
- `request-a-quote.template.html` — generated-page template; never copy directly into the public repository.
- `quote-form.css` / `client.js` — styles and reviewed inline behavior injected by `build_site.py`.
- `apps-script/Code.gs` — validation, dedupe, append and sanitized-notification backend.
- `tests/` — fictional `.example` fixtures and local validation tests.

## Build boundary

`build_site.py` emits the page only when passed an explicit `--quote-endpoint https://script.google.com/macros/s/<deployment-id>/exec`. A normal build without the flag preserves the current non-form site.

Do not publish a test placeholder. Production still requires an authenticated Workspace owner to create/read back the restricted Sheet and deploy Apps Script, notification-route configuration, privacy approval and exact publication authority.
