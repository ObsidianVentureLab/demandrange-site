# Changelog

What changed on demandrange.com and in this repository's CI, newest first. One entry per merged pull request to `main` (merging is the deploy, ADR 0001). Dates are merge dates (UTC). The short sha is the merge commit on `main`.

Started on 2026-11-04. Entries before r20 are summarised from the merged pull-request titles, so they are less detailed.

## Unreleased (open pull requests, not live)
- **Privacy notice 2026-11-06-v1** (#79, draft, gated):
  - one lawful basis per purpose;
  - named service providers and a definite transfer mechanism;
  - retention as it actually runs;
  - discloses the Google-hosted form confirmation page.

  Merge only after the quote backend that accepts version `2026-11-06-v1` is deployed and the retention job is enabled.
- **Quote-form handler fix** (#56, on a source branch): the handler and schema accept the live form's regions `IE`/`UK`/`EU`. Live only once Sean redeploys the Apps Script (ADR 0002).

## 2026-11-05: merge run (11 PRs, each pinned to its commit; main green and Pages deployed after each)
- **ADR corrections** (#78, 22b638d8): ADR 0002 no longer claims the deployed handler's sha256 is recorded. ADR 0003 is accepted, with wider scope.
- **ADR log 0001–0003** (#71, 7d8ca354): records the static Pages site, the Apps Script quote backend and the move of internal tooling to a private repository.
- **CI: live-check time limit** (#77, 4d3bae0d): the live job gets 15 minutes, so a slow site is reported rather than killed.
- **CI: PR preview ships no code** (#76, 9cc073f3): the preview artifact holds site files only. Reviewers serve it with `serve.py` from their own checkout of `main`.
- **CI: served-data guard** (#75, c29be0e4): site checks fail if any served file contains an email address outside demandrange.com and the reserved example domains.
- **PR preview follow-up** (#65, f9e3abb4): the preview artifact includes hidden files, never follows symlinks, outputs a top-level `_site`, and stamps the PR head sha.
- **r23** (#68, f6a97382):
  - UK SIC page recounted from the 1 November 2026 Companies House snapshot;
  - content fixes 55, 57, 58, 59 and 60: the lead-generation re-angle, an FAQ step-5 resources note, the prioritisation link hub and its sources, inbound links to the hub, and duplicate FAQ questions removed.
- **CI: daily live-site check** (#70, 4c63f339): key pages return 200, the live sitemap equals `main`, and the TLS certificate has at least 14 days left.
- **Dataset structured data** (#67, 4ad64354):
  - nested `isBasedOn` sources on `/eu-industrial-enterprises-by-country` are typed as CreativeWork rather than Dataset;
  - a CI rule for Dataset fields.

  The matching generator change must ship with it.
- **CI: served-bundle guard** (#69, 83628400): blocks source trees, Apps Script files, database files, keys and internal docs from ever being served.
- **CI: blocking full-history secret scan** (#72, 1b5df9bf): gitleaks, pinned and checksum-verified, runs over the full history on every PR and push to `main`.

## r22 (2026-11-04, #66, 3aea7f18)
- `/european-chemical-manufacturer-research`: coverage wording.
- `/eu-industrial-enterprises-by-country`: new licence README sidecar for the CSV download; the data CSV itself is unchanged.

## r21 (2026-11-04, #63, 9734495a)
- Fix 53 Rev 3: `/sample-account-research` GEO and freshness updates.
- Fix 54: `/industrial-sales-resources` regrouped.

## CI: PR preview (2026-11-04, #57, 4addefd5)
- Every PR to `main` builds a noindex preview of the site as a workflow artifact (there is no staging host). `.github/` only; served output unchanged.

## r20 (2026-11-03, #55, e4608791)
- New and revised pages from the r19/r19b writing round; fixes 49 to 52 (Rev 2).

## r19 (2026-11-03, #54, 6d7ace45)
- `/request-a-quote`: FAQ from fix 39 rendered on the page.

## r18 (2026-11-03, #53, 417f815a)
- Fixes 20, 28, 32, 39 and 42 to 48; `llms.txt` update.

## r17 (2026-11-03, #52, 6c04604d)
- Review-date guard (F15/F27); Organization description; fixes 26 to 41; Rev 3 pages.

## 2026-10-28
- r16 (#51, 318f3498): revisions on 12 pages; "How Demand Range helps" label.
- r15 (#49, 864016e1): key facts and FAQ additions on 8 pages.
- r14 (#50, c53c9f15): sitemap `lastmod` taken from reviewed dates.
- CI: output-only site checks (#48, 7868813c).
- r13 (#47), r12 (#46), r11 (#45), r10 (#44), r9 (#43), round 8 (#42), 7b (#41), 6c (#40), 5 (#39), chem v1.3 (#38), 4b (#37): QA-cleared content releases (account prioritisation, Irish and German industry codes, EU food plants, MRO, EPC/EPCM, eTenders, NACE Rev. 2.1, CPV licence, contact page and others).

## 2026-10-27
- Releases 3 and 4 (#35, #36), the Eurostat dataset page (#33), Organization `sameAs` (#34), SEO/GEO guides 1 and 2 (#30, #32), batch 1 (#29) and week 1 entity schema, brand spelling, `en-IE` and `llms.txt` (#28).
