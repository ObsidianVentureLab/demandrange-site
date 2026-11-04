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
- `live/request-a-quote.html` — byte-for-byte snapshot of the page served from `main`; a test input, never a build input (see `live/README.md`).

## Regions taxonomy

The live page offers three regions, posted as the values `IE`, `UK` and `EU` (labels in
`form_schema.json` → `fields.regions.labels`). The handler's `FORM.regions` and the template's
checkboxes must match this list exactly; `tests/test_regions.js` reads the values out of the live
snapshot, the template, the schema and `Code.gs` and fails if any of the four disagree.

The earlier worldwide values (`EMEA`, `NAM`, `LATAM`, `APAC`, `ANZ`) are kept in
`fields.regions.legacy_values` / `FORM.legacyRegions`. The handler still accepts them
(`FORM.acceptedRegions` = form values followed by legacy values) so older fixtures, the Taxonomies
tab and any in-flight submission keep validating, but they are never rendered on the page.
Matching is exact: values are trimmed of surrounding whitespace but not case-folded, so `ie`,
`Ireland` or `GB` are rejected.

Run from this directory: `node tests/test_regions.js`, `node tests/test_local.js`,
`node tests/test_manifest.js`, `node tests/test_owner_qa.js`, `python3 -m unittest tests.test_endpoint`.

## Build boundary

`build_site.py` emits the page only when passed an explicit `--quote-endpoint https://script.google.com/macros/s/<deployment-id>/exec`. A normal build without the flag preserves the current non-form site.

Do not publish a test placeholder. Production still requires an authenticated Workspace owner to create/read back the restricted Sheet and deploy Apps Script, notification-route configuration, privacy approval and exact publication authority.
