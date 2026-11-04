# Changelog

What changed on demandrange.com and in this repository's CI, newest first. One entry per merged pull request to `main` (merging is the deploy, ADR 0001). Dates are merge dates (UTC). The short sha is the merge commit on `main`.

Started on 2026-11-04. Entries before r20 are summarised from the merged pull-request titles, so they are less detailed.

## Unreleased (open pull requests, not live)
- **r23** (#68): UK SIC page freshness recount; content fixes 55, 57, 58, 59 and 60 (lead-generation re-angle, FAQ step-5 resources note, prioritisation link hub and sources, inbound links to the hub, duplicate FAQ questions removed).
- **Dataset structured data** (#67): nested `isBasedOn` sources on `/eu-industrial-enterprises-by-country` typed as CreativeWork rather than Dataset, plus a CI rule for Dataset fields. The matching generator change must ship with it.
- **PR preview follow-up** (#65): preview artifact includes hidden files, never follows symlinks, top-level `_site` output, PR head sha stamp.
- **CI: served-bundle guard** (#69): blocks source trees, Apps Script files, database files, keys and internal docs from ever being served.
- **CI: daily live-site check** (#70): key pages return 200, the live sitemap equals `main`, and the TLS certificate has at least 14 days left.
- **Quote-form handler fix** (#56, on a source branch): handler and schema accept the live form's regions `IE`/`UK`/`EU`. Live only after Sean redeploys the Apps Script (ADR 0002).

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
