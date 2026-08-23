# Demand Range website

Dependency-free static GitHub Pages site for `demandrange.com`, positioned around analyst-led Industrial Opportunity Intelligence.

## Routes

- `index.html` — homepage
- `opportunity-intelligence.html` — core intelligence service
- `campaign-activation.html` — human-reviewed activation approach
- `pumps-flow-control.html` — initial pumps, valves and flow-control wedge
- `methodology.html` — evidence, scoring and data principles
- `sample-opportunity.html` — clearly fictional opportunity brief
- `about.html` — company direction and staged build model
- `contact.html` — non-transmitting mailto contact route
- `privacy.html`, `cookies.html`, `terms.html` — legal notices

Shared presentation is in `styles.css`; `build_site.py` regenerates the 11 HTML routes. The site uses no external fonts, scripts, analytics, tracking, transmitting forms or embeds.

## Local build and checks

```bash
python3 build_site.py
python3 qa_static.py
python3 -m http.server 8000
```

Open `http://127.0.0.1:8000/` for local rendering. Review `IMPLEMENTATION_NOTES.md` for the route map, claims gate, rollback and recorded test evidence.

## Deployment mechanics

- GitHub Pages source remains the repository root.
- `CNAME` remains `demandrange.com`.
- `.nojekyll` remains present.
- `robots.txt` and `sitemap.xml` describe the static routes.

No deployment, DNS or public action should occur without explicit publication approval and a final legal/commercial review.
