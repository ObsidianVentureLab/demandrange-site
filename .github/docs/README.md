# Project records (not served)

This folder sits under `.github/`, which GitHub Pages does not publish (checked: `/.github/...` returns 404 on demandrange.com). Markdown anywhere else in this repository would be published, and `site_checks.py` check 6 fails the build if it finds any.

Even so, the repository is public, so everything here is written to be public-safe: no personal data, no internal host names or file paths, no secrets, no deployment URLs, and no names other than "Sean".

- `adr/`: architecture decision records, one decision per file, numbered, never renumbered. A superseded ADR stays in place with its status changed to `Superseded by NNNN`.
- `CHANGELOG.md`: what each release changed on the served site, newest first. It lives here rather than at the repository root for the same reason (a root `CHANGELOG.md` would be published).

ADR template:

```
# NNNN. Title
Status: Proposed | Accepted | Superseded by NNNN
Date: YYYY-MM-DD
## Context
## Decision
## Consequences
```
