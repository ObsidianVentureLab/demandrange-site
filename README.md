# Demand Range website

Static GitHub Pages site for `demandrange.com`.

Files:
- `index.html` — homepage
- `privacy.html` — website privacy notice
- `terms.html` — legal notice / terms
- `robots.txt` — crawler policy pointing to sitemap
- `sitemap.xml` — public sitemap for the homepage
- `favicon.svg` — lightweight Demand Range favicon
- `CNAME` — custom domain for GitHub Pages

Deployment:
- GitHub Pages source: `main` branch, `/` root
- Custom domain: `demandrange.com`

Operational note: live campaign work, outbound activity, and mailbox setup remain separate from this static website deployment.

Pre-deploy checks:
- Parse `index.html`, `privacy.html`, and `terms.html`.
- Scan for placeholder/rough copy, Cloudflare email-protection artifacts, unapproved guarantees, and overbroad compliance claims.
- Verify internal anchors, privacy/terms links, canonical URL, favicon, robots, sitemap, and `mailto:partners@demandrange.com` CTAs.
- Push only after reviewing the git diff, then verify the live `https://demandrange.com/` endpoint and GitHub Pages state.
