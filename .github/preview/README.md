# Site preview / staging

**Today there is no staging.** GitHub Pages serves `main` as-is at https://demandrange.com/
(Pages source: branch `main`, path `/`, custom domain via `CNAME`). The moment a PR is merged
it is live. This directory adds a review step that happens *before* that, without any new
account, hosting setting or spend.

## What exists now (no action needed)

The `pr-preview` workflow (`.github/workflows/pr-preview.yml`) runs on every PR into `main`:

1. Runs `.github/ci/test_preview.py` (build + server tests, and `site_checks.py` over the
   preview tree).
2. Builds a preview copy with `build_preview.py`: the served tree **minus** `.git`, `.github`
   and `CNAME`, **plus** a `robots.txt` that disallows crawling, a `_headers` file with
   `X-Robots-Tag: noindex`, and `_preview.json` (commit, PR, time). The commit is the PR head
   (not the merge commit GitHub builds for `pull_request` runs), so it matches the branch.
3. Lists the changed pages in the job summary (Checks tab → `pr-preview` → Summary).
4. Uploads `site-preview-pr-<n>` as a workflow artifact (kept 14 days).

To review: download the artifact from the run, unzip, then

```
python3 serve.py _site
```

and open http://127.0.0.1:8000/. `serve.py` reproduces GitHub Pages' clean URLs (`/about` →
`about.html`, `/` → `index.html`, unknown → `404.html`), refuses dot-paths and traversal, and
sends `X-Robots-Tag: noindex` on every response. Python 3 standard library only. It listens on
127.0.0.1 only; `--bind` exists for the rare case of reviewing from another device on the same
network, and should stay at the default otherwise (the tree is a pre-release copy of the site).

The workflow needs only `contents: read`; it does not comment on the PR, deploy anything or
use secrets.

## Hosted preview URLs — what Sean would have to enable

All of these need an account action that this workstream does not take. Nothing below is
configured; the repo is ready for each.

### Option A (recommended): Cloudflare Pages, Git integration, previews only

Free tier; one preview URL per branch (`<branch>.<project>.pages.dev`) plus a deployment
status on each PR. Steps (Cloudflare dashboard, ~10 minutes):

1. Workers & Pages → Create → Pages → **Connect to Git** → authorise the Cloudflare Pages
   GitHub App for **only** `ObsidianVentureLab/demandrange-site`.
2. Project name: e.g. `demandrange-site-preview`.
3. Build settings: Framework preset **None**; Build command
   `python3 .github/preview/build_preview.py --source . --output _site`;
   Build output directory `_site`.
4. Settings → Builds & deployments → **Production branch**: set to a branch that does not
   exist (e.g. `never-deploy-production`) so Cloudflare never publishes a "production" copy
   of the site; **Preview branches**: *All non-production branches* (or *Custom* with
   `ws/*`, `source/*`, `release/*`).
5. Do **not** add a custom domain. The `*.pages.dev` previews already carry
   `X-Robots-Tag: noindex` from the generated `_headers`, and `robots.txt` disallows all.
6. Optional: Settings → Access policy to require a Cloudflare Access login for the preview
   project (free for up to 50 users), if previews should not be public.

Nothing in the repo changes for this; the build script already writes `_headers` and
excludes `CNAME`. The live site stays on GitHub Pages.

### Option B: Netlify (Deploy Previews)

Same shape: connect the repo, build command as above, publish directory `_site`, "Stop
builds" for the production branch or set the production branch to a non-existent name,
enable Deploy Previews for PRs. Netlify honours `_headers` too. Free tier covers it.

### Option C: GitHub-only staging site

GitHub Pages hosts one site per repository, so a staging copy needs a second **public**
repository (Pages on a private repo requires a paid plan), e.g.
`ObsidianVentureLab/demandrange-site-staging`, with Pages enabled from GitHub Actions. The
`pr-preview` workflow would then need a fine-grained token (`contents: write` on the staging
repo only) stored as an Actions secret, and a step that pushes `_site` to it. More moving
parts, one URL shared by all PRs, and a token to rotate; only worth it if a third-party host
is unacceptable.

### Not recommended

- A `staging` branch served by the same Pages site: Pages serves one branch; switching the
  source branch takes the live site down. 
- Keeping `CNAME` in a preview: any GitHub-hosted preview would attempt to claim
  `demandrange.com`.

## Files

| File | Purpose |
|---|---|
| `build_preview.py` | Produce the preview tree (stdlib, read-only on the source) |
| `serve.py` | Local server with Pages-style clean URLs |
| `../ci/test_preview.py` | 16 tests: exclusions, byte-identical copies, noindex, overwrite guard, `site_checks` on the preview, URL mapping, 404, traversal, HEAD |
| `../workflows/pr-preview.yml` | The PR workflow |

Everything under `.github/` is outside the deployed site (`site_checks.py` served-surface guard).
