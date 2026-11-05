# 0001. The site is static, built off-repo, and served by GitHub Pages from `main`

Status: Accepted (records the existing setup)
Date: 2026-11-04

## Context
demandrange.com is a content site: industrial account-research guides, open-data pages and CSV downloads, a quote form and legal pages. It needs to be fast, cheap, auditable and hard to break. The team ships in numbered releases (r1 to r22 so far) that DR QA & Fact-Check signs off before anything goes live.

## Decision
- This repository holds **built output only**. GitHub Pages serves `main` as-is (`.nojekyll`, custom domain via `CNAME`); `.git` and `.github` are not published.
- The page generator and its build-time checks live outside this repository. Each release is generated from a pinned source tree plus QA-approved patches, and every patch script's exit code and output sha256 values are checked against QA's expected values before the release PR is opened. A mismatch stops the release.
- **A merge to `main` is a deploy.** Nothing reaches `main` except through a reviewed pull request that DR QA has signed off.
- Every PR to `main` runs `site-checks` (HTML, internal links and fragments, sitemap/llms consistency, brand spelling, retired stubs, served surface, strict F15) and `pr-preview` (a noindex copy of the site as a workflow artifact; there is no staging host).
- No third-party scripts, trackers or embeds. The only form is the quote form (ADR 0002).

## Consequences
- Hosting costs nothing and there is no server to patch for the public site.
- Anything committed outside `.github/` is public at demandrange.com. Tooling, source, data and internal docs must never land on `main`. `site_checks.py` check 6 enforces this in CI, and `served_guard.py` (PR #69, not yet merged) widens it to source trees, Apps Script files, database files and keys.
- Because the generator is off-repo, CI can check the output but cannot rebuild it. A drift check against the source tree is proposed in the source-consolidation PR and waits on a decision about which source branch is canonical.
- A bad merge is live within minutes. Rolling back means a revert PR, which goes through the same checks.
