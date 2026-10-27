# request-a-quote — integration copy draft

Status: draft for parent review; not independent acceptance or publication.

- Route: `/request-a-quote.html`
- Purpose: Clarify what a request asks DemandRange to assess without changing the commissioned intake.
- Integration mode: COPY-ONLY PATCH: metadata + hero + pre-form explanation/model cards. Never replace the whole main element or alter the form/client/schema/backend.
- Exact title: **Request an Industrial Research Quote | DemandRange**
- Exact meta description: Request a written scope for industrial account research. State your market and territory preferences; fields, coverage and deliverables are assessed before agreement.
- Exact H1: **Request a lead programme scope & quote.**
- Eyebrow: Written scope first
- Public copy: `request-a-quote.fragment.html` (unstyled content fragment, not a website template)

## Section / link map

- `quote-next` — What happens next
- `quote-mix` — Target mix, not a guaranteed allocation
- `quote-scope` — Scope clarification

- [Review the company-level service](industrial-lead-research.html)
- [View a fictional sample before submitting](sample-account-research.html)

## Source / decision provenance (internal; do not publish)

- PLAN §23 and REVIEW R09 explicitly require quote consistency while retaining endpoint, fields, versions and server validation.
- Retain the existing H1. Use the shared brand descriptor in shared-copy.json instead of the quote-specific “Industrial lead programmes” wordmark suffix.
- The fragment contains no form. Integrate only its identified copy slots; preserve the existing safety warning, submission notice, privacy link/permissions, field labels/options/required state and success/error handling verbatim.

- `quote-next`: BASELINE request-a-quote.html What happens next; PLAN §23. Baseline anchor: What happens next
- `quote-mix`: BRAND §2 and homepage model bank; PLAN §23; BASELINE request-a-quote.html target cards. Baseline anchor: 10% opportunity-signalled
- `quote-scope`: PLAN §23 quote-copy consistency; §25 private intake; REVIEW R09; BRAND §2. Baseline anchor: Give us enough to assess the brief.

## Claims checklist for integration review

- [ ] Company-level research is the default described here; named-contact delivery is not agreed or implied.
- [ ] Industry fit and project evidence remain separate; no automatic MQL, buying-intent, buyer-access or open-package claim.
- [ ] Any 90/10 wording is a target with written scope; no guaranteed volume, timing, price, replacement SLA or outcome.
- [ ] Ireland is the focus; other geography is assessed, not promised.
- [ ] No real client outcome, personal contact, named reviewer, legal entity or compliance certification is invented.
- [ ] Source/customer-use rights and release authority remain separate from a research/QA decision.

## Pending / integration risks

Do not rename required job-seniority fields or remove global-region options. The caveat explains those existing preferences. No live form submission, backend verification or new intake acceptance has been performed in this drafting lane. Parent owns exact-client and route regression checks.
