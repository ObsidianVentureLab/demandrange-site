# Industrial Opportunity Intelligence — Implementation Notes

Date: 2026-08-23  
Worktree: `/root/miranda/files/strategy/demandrange-industrial-opportunity-intelligence-2026-08-23/worktrees/site-industrial`  
Base commit: `2fffea217411fd47c37ca777bf157f49ae15b7fd`  
Local branch: `industrial-intelligence-positioning`

## Route map

| Route | Purpose |
|---|---|
| `index.html` | Industrial Opportunity Intelligence homepage |
| `opportunity-intelligence.html` | Core analyst-led opportunity service and fit |
| `campaign-activation.html` | Human-reviewed campaign activation and boundaries |
| `pumps-flow-control.html` | Initial pumps, valves and flow-control playbook |
| `methodology.html` | Analyst workflow, scoring, data principles and learning limits |
| `sample-opportunity.html` | Repeatedly labelled fictional opportunity brief |
| `about.html` | Staged company direction: analyst service before software |
| `contact.html` | Non-transmitting `mailto:` contact path |
| `privacy.html` | Website and enquiry privacy notice |
| `cookies.html` | No-cookie/no-tracking posture |
| `terms.html` | Website and service boundaries |

Shared assets and operations:

- `styles.css` provides the responsive design system and accessibility states.
- `favicon.svg`, `CNAME`, `.nojekyll` and root GitHub Pages mechanics are preserved.
- `build_site.py` deterministically regenerates all 11 HTML pages.
- `qa_static.py` performs dependency-free structure, link, accessibility-oriented, dependency and claims checks.
- `sitemap.xml` lists all 11 routes; `robots.txt` continues to point to it.

All site links are relative except canonical URLs, the existing business `mailto:` address and the public Irish Data Protection Commission reference.

## Claims gate

Public-ready copy applies these constraints:

- The current offer is described as **analyst-led**, defined-scope research.
- The site makes no claim of a live platform, self-serve dashboard, continuous alerts or real-time/private buyer intent.
- Observed evidence, analyst inference and known unknowns are visually and verbally separated.
- Customer isolation, least-privilege access and prevention of customer-confidential leakage are presented only as **future-system requirements**, not as independently verified current controls.
- Outcome learning is explicitly conditional on the client sharing replies, call outcomes, qualification decisions or pipeline feedback.
- The source document's launch price, VAT treatment and opportunity-replacement offer are omitted from generated public HTML pending commercial approval.
- No customers, customer logos, case studies, performance metrics or guarantees were added.
- The sample organisation, project, evidence, dates, score and recommendations are labelled fictional at the page banner, hero and body.
- No transmitting form, analytics, cookies, third-party script, external font, embed or campaign processor was added.

## Rollback

No commit, push, pull, fetch, PR, merge, deployment, DNS change or other remote/public action was performed.

To discard this uncommitted local implementation and return the worktree to the starting commit, an authorised operator can run:

```bash
git reset --hard 2fffea217411fd47c37ca777bf157f49ae15b7fd
git clean -fd
```

Those destructive rollback commands were documented only and were **not** run.

## Tests run

### Build and Python syntax

Command:

```bash
python3 build_site.py
python3 -m py_compile build_site.py qa_static.py
```

Observed result:

```text
Built 11 HTML routes
```

Both commands exited `0`; `py_compile` produced no diagnostics.

### Static HTML, link, accessibility-oriented and claims QA

Command:

```bash
python3 qa_static.py
```

Observed result:

```text
PASS: 11 routes; 1192 assertions; 0 broken internal links/fragments; 0 external page resources; 0 forms/scripts/iframes; claims gate passed
```

The assertions cover HTML5 doctype, language, title, description, viewport, exactly one `h1`, landmarks, skip link, heading-level progression, duplicate IDs, mobile `details`/`summary`, missing image alternatives, all internal files/fragments, relative-link posture, resource locality, mail target, CNAME, `.nojekyll`, sitemap coverage and banned claim/dependency patterns.

### Local HTTP route smoke test

A temporary `python3 -m http.server 8765 --bind 127.0.0.1` server was used. Every requested page returned `200`, `text/html` and a non-trivial response body:

```text
/ status=200 type=text/html bytes=14001
/opportunity-intelligence.html status=200 type=text/html bytes=8494
/campaign-activation.html status=200 type=text/html bytes=8341
/pumps-flow-control.html status=200 type=text/html bytes=8223
/methodology.html status=200 type=text/html bytes=9661
/sample-opportunity.html status=200 type=text/html bytes=12202
/about.html status=200 type=text/html bytes=8064
/contact.html status=200 type=text/html bytes=6802
/privacy.html status=200 type=text/html bytes=10575
/cookies.html status=200 type=text/html bytes=7285
/terms.html status=200 type=text/html bytes=9343
PASS: 11/11 local HTTP routes returned 200 text/html
```

### Browser harness note

A desktop screenshot attempt through the available Hermes browser harness was rejected because the target was localhost/private. Full visual QA was subsequently completed with the local Playwright Chromium headless runtime: 22 full-page captures (11 routes × 1440px desktop and 390px mobile) showed zero horizontal overflow and zero console/page errors, and key pages passed manual vision review. Evidence: `../../qa/visual-20260823/`. The visual publication gate is satisfied; remaining gates are legal/claims review and explicit `APPROVE_PUBLISH`.

## Publication gates still outside this implementation

- Explicit publication approval.
- Founder/commercial review of final public scope and terms.
- Legal review and addition of verified operating-entity details when available.
- A visual desktop/mobile browser review in an environment permitted to load localhost.
