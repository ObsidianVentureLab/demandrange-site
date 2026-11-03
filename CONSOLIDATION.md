# Source-tree consolidation — state, evidence and the decision needed

*Prepared 3 November 2026 by the demandrange-site workstream. Nothing here is deployed.*

## Branch topology (verified with `git merge-base`)

- `main` (97 commits) holds **built output only**. GitHub Pages serves it as-is at demandrange.com.
- `origin/source/*` (6 branches) is an **orphan tree** with no common ancestor with `main`: the
  generator (`build_site.py`, `qa_static.py`, `production_contract.py`, the `foundation/` copy
  sources, `quote-form/` …). `source/sameas-wellfound` (27 Oct 2026 22:38 UTC) is the tip; every
  other `source/*` branch is an ancestor of it, so there is nothing to merge between them.
  Consolidation of `source/*` is therefore already a single line; this document is about the
  gap between that line and `main`.
- `release/*` branches are squash-merged copies of built output; `release/r20` has the same
  tree as `main`.
- `source/sameas-wellfound` corresponds to `main` PR #34 (27 Oct). **Everything after it on
  `main` — PRs #35 to #55, release rounds 3 to r20 (28 Oct–3 Nov) — was produced by a generator
  state that is not in this repository.** `.github/workflows/site-checks.yml` on `main` says so:
  "the generator and its qa_static/build checks run off-repo before each release".

## How far the source tree is behind `main` (measured)

A production build of `source/sameas-wellfound` + the regions fix (PR #56), with the live quote
endpoint, compared with the `main` tree (`.github/ci/drift_report.py`):

| Identical | Differing | Only in build | Only in main |
|---:|---:|---:|---:|
| 60 | 51 | 2 | 8 |

- Only in `main`: `what-is-industrial-account-research.html`, `irish-manufacturing-nace-codes.html`,
  `uk-sic-codes-manufacturing.html`, `eu-food-beverage-plant-research.html`,
  `demand-range-sample-opportunity-brief.pdf`, `eu-industrial-enterprises-by-country-nace-2024.csv`,
  `uk-sic-2007-manufacturing-codes.csv`, `industrial-icp-scoring-worksheet.csv`.
- Only in the build: the renamed/older `DemandRange_Sample_Opportunity_Brief.pdf` and the 2023 Eurostat CSV.
- All 47 HTML pages the build produces differ from `main` (copy revisions, FAQ sections, JSON-LD wording, sitemap `lastmod`).

`main`'s own output checks (`.github/ci/site_checks.py`) run on the source build: **148 failures** —
93 brand variants (`alternateName` "DemandRange"/"Demand.Range" in JSON-LD, removed on `main` in
week 1), 49 links to the three retired redirect stubs, and the stubs themselves not being noindex
redirects. These are rules `main` adopted after the source tree stopped.

## What this branch provides regardless of the decision

- `.github/workflows/source-checks.yml` on `source/*` and `ws/*`: unit tests; fixture-mode build
  (qa_static, 8 300+ assertions, production contract); production-mode build with the live
  endpoint read from `main` (protected pins must hold); `main`'s `site_checks.py` + `qa_post.py`
  on the output (**report-only** until the gap above is closed); W3C Nu HTML validation
  (`html5validator`, hash-pinned); drift report vs `main` in the job summary; gitleaks secret scan
  (pinned CLI, checksum verified, no licence key); builds and reports as artifacts.
- `.github/workflows/quote-form-tests.yml` (from PR #56): handler/schema/template/live-page contract.
- `.github/ci/`: `site_checks.py`, `qa_post.py` (copies of `main`), `drift_report.py` (+ tests),
  `gitleaks.sh`, hash-pinned requirements.

## Decision for Sean

The source tree cannot become authoritative again by merging branches; the missing 20 rounds of
generator state live outside the repo. Options:

1. **Recover the off-repo generator state used for r20 and push it as a `source/*` branch** (or
   hand the directory to the workstream). Then: re-run `source-checks`, expect the drift report
   to go to zero (or explain each remaining line), flip the report-only step to blocking, and from
   then on build every release from the repo. *Recommended*: it is the only path where
   `main` is reproducible and `quote-form/` (handler + schema + template) stays next to the pages.
2. **Declare `main` authoritative and retire `source/*`** except `quote-form/` (the Apps Script
   handler has no other home). The generator would be re-created later from `main`'s output if ever
   needed. Cheapest now; loses qa_static's 8 000+ content/legal assertions for future edits.
3. **Rebuild the gap inside the repo** by porting the r3–r20 changes into `foundation/` copy
   sources until the drift report is empty. Roughly 51 pages of copy diffs plus 8 new pages;
   estimated several days of careful work and still guesswork about the off-repo pipeline.

Until a choice is made, the workstream keeps `quote-form/` changes on `source/*`-based `ws/`
branches (as in PR #56) and leaves `main` untouched.
