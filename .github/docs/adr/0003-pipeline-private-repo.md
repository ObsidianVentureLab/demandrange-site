# 0003. Prospecting and client-delivery tooling lives in a private repository

Status: **Proposed, waiting for Sean's decision**
Date: 2026-11-04

## Context
Internal tools for building client account lists have been written on draft branches of this repository: company search from an ideal-customer brief, email verification, CSV/XLSX export with a manifest for manual delivery, and a small client database. They handle business contact data (personal data under GDPR) and client delivery files.

This repository is public, and anything that reaches `main` is published at demandrange.com (ADR 0001). DR QA has ruled that the `pipeline/` tree must never reach `main`.

## Decision (proposed)
- Move the tooling, with its history and its CI workflow, to a **private** repository. Creating it needs Sean's GitHub admin rights.
- Until then the draft PRs stay drafts and are never merged into `main`. They carry these guards:
  - `.gitignore` entries for CLI output folders and database files;
  - CLIs that refuse to read or write data paths inside any checkout of this repository;
  - a CI data guard that fails on committed outputs, database files, or non-reserved email domains in fixtures;
  - tests that run with the network blocked, so no paid API call can happen in CI.
- On `main`, `served_guard.py` (PR #69, not yet merged) blocks `pipeline/`, database files and Apps Script sources from ever being served.
- Paid provider calls (company search, email verification) stay off by default, behind an explicit flag and a hard credit cap, and need Sean's yes with a stated amount.

## Consequences
- Personal data and client files never sit in a public repository, even by accident.
- Two repositories to keep in step: shared conventions (branch rules, gitleaks, protection settings) must be applied to both.
- Closing the old draft PRs in this repository is Sean's call. Until then they stay open, each with a pointer to the new home.

## Open points for Sean
1. Approve the private repository (name and visibility).
2. Database: SQLite now, Postgres later if volumes grow (recommended), or Postgres now.
3. Retention period, allowed columns and lawful-basis wording for prospect data.
