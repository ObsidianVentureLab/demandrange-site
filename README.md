# Demand Range website

Dependency-free static GitHub Pages site for `demandrange.com`, positioned around analyst-led Industrial Opportunity Intelligence.

## Routes

- `index.html` — homepage
- `opportunity-intelligence.html` — core intelligence service
- `campaign-activation.html` — human-reviewed activation approach
- `markets.html` — industrial markets
- `methodology.html` — evidence, scoring and data principles
- `sample-opportunity.html` — clearly fictional opportunity brief and downloadable PDF
- `about.html` — company direction and staged build model
- `contact.html` — email contact route; no transmitting form
- `privacy.html`, `cookies.html`, `terms.html` — legal notices
- `404.html` — branded missing-page response
- `pumps-flow-control.html` — retained redirect to Markets

## Source and checks

This repository contains generated public files only. The maintained source,
`build_site.py` generator and QA tools are in the internal site-tooling workspace,
not this public repository. Do not hand-edit generated HTML/CSS.

The September 2026 redesign uses system fonts and local assets. Two small inline
scripts provide an optional light/dark toggle. The `dr-theme` preference is saved
locally only after the visitor uses the toggle. No analytics, advertising tags,
third-party scripts, transmitting forms or embeds are installed.

Before publication: rebuild from source, check all routes and anchors, validate
desktop/mobile layouts in both themes, exercise menu/theme interactions, and
verify the downloaded sample remains a clearly fictional demonstration.

## Deployment

GitHub Pages serves `main` at the repository root. `CNAME` remains
`demandrange.com`; `.nojekyll`, the sitemap, old-route redirect, PDF, social image
and `.well-known` policies are retained. Tooling and QA evidence stay private.

Publication requires owner approval and passing checks. After pushing, match the
Pages build to the exact commit and verify production routes and content. Keep
the prior production commit as the rollback point.
