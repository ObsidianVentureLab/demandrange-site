# 0003. Prospecting tooling, the site generator and the quote backend live in a private repository

Status: **Accepted, wider scope** (decided 2026-11-05)
Date: 2026-11-04, amended 2026-11-05

## Context
Internal tools for building client account lists have been written on draft branches of this repository: company search from an ideal-customer brief, email verification, CSV/XLSX export with a manifest for manual delivery, and a small client database. They handle business contact data (personal data under GDPR) and client delivery files.

This repository is public, and anything that reaches `main` is published at demandrange.com (ADR 0001). DR QA has ruled that the `pipeline/` tree must never reach `main`.

The 5 Nov audit found two more things that belong with the tooling. First, the site generator that builds `main` lives off-repo on the release machine, and the in-repo generator line (`source/*`) is an orphan 20 rounds behind it. Second, the quote-form backend source and the internal working notes sit on that same orphan line, in public.

## Decision
- Create one **private** repository. Its name is kept out of this public record. Creating it needs Sean's GitHub admin rights.
- Move into it, with history:
  - the pipeline (`ws/dr-apollo-prospects` → `ws/dr-client-db`, PRs #59–62);
  - the `source/*` generator line, plus the off-repo generator tree imported as its new main line, so `main` here can be rebuilt from Git;
  - the quote-form backend and its tests (PRs #56, #73, #74);
  - the source CI and internal notes (`CONSOLIDATION.md`, `IMPLEMENTATION_NOTES.md`; PR #58).
- This public repository keeps built output and output-only CI. Releases arrive as built output from the private repository.
- Until the move, the draft PRs stay drafts and are never merged into `main`.
- Guards in place, or arriving with this ADR:
  - `.gitignore` entries for CLI output folders and database files;
  - a CI data guard on the pipeline branches (outputs, database files, non-reserved email domains in fixtures);
  - **`served_data_guard.py` on `main`**, which fails on any real email address in anything Pages serves;
  - tests that run with the network blocked.
- Correction: the CLI path guard refuses paths only inside a checkout that contains `pipeline/`. It does **not** protect a checkout of `main`. The private repository fixes this by refusing any path inside any git work tree.
- On `main`, `served_guard.py` (PR #69) blocks `pipeline/`, database files and Apps Script sources from ever being served.
- Paid provider calls (company search, email verification) stay off by default, behind an explicit flag and a hard credit cap, and need Sean's yes with a stated amount. Apollo's cap must also count retries before any live run (audit INT-02).
- Database: no SQLite client database for now. The Google Sheet is the record until there are about 20 clients.

## Consequences
- Personal data, client files and internal notes never sit in a public repository, even by accident.
- `main` becomes reproducible from Git, in the private repository.
- Two repositories to keep in step: shared conventions (branch rules, gitleaks, protection settings) must be applied to both.
- After the copy is verified, the moved branches here are closed and deleted. Their `refs/pull/*` heads stay public, because only GitHub Support can remove them. They hold no secrets and no real personal data, so no Support request is planned.

## Still open
1. Retention period, allowed columns and lawful-basis wording for prospect data. These are needed before the first live run, and they depend on naming the operating entity.
