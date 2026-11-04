# pipeline — ICP brief → Apollo company candidates (P2)

Company-level candidate generation for Demand Range research briefs. Input is a JSON brief
mirroring `foundation/industrial-ideal-customer-profile-worksheet.csv`; output is a CSV of
*candidates for analyst research* plus a manifest. Nothing here decides fit, verifies emails
or contacts anyone, and no person-level data is requested.

## Safety defaults
- **No network by default.** `python -m pipeline prospects` without `--live`/`--fixture` is a dry
  run: it prints the Apollo filters and the minimum pages/credits and sends nothing.
- **Key from the environment only.** `--live` reads `APOLLO_API_KEY`; it is never written to
  files, output, logs or error text (error bodies are redacted).
- **Budget before every request.** `--credit-budget N` (default 0) is checked before each page;
  Apollo charges 1 credit per page of up to 100 companies. `--live` without a budget stops before
  the first request. When the budget trips mid-run the rows already collected are still written.
- **Tests never touch the network**: `pipeline/tests/__init__.py` replaces `urllib.request.urlopen`
  with a function that raises, and every test uses an injected fake transport.
- Fixture data under `pipeline/examples/` is wholly fictional (`.example` domains).

## Usage
```
python -m pipeline validate  --brief pipeline/examples/brief-fixture.json
python -m pipeline prospects --brief pipeline/examples/brief-fixture.json --out out/          # dry run
python -m pipeline prospects --brief BRIEF.json --out out/ --fixture pipeline/examples/apollo-organizations-fixture.json
read -rs APOLLO_API_KEY && export APOLLO_API_KEY   # typed at the prompt: not an argument, not in shell history
python -m pipeline prospects --brief BRIEF.json --out out/ --live --credit-budget 3
```
Exit codes: 0 ok, 2 brief/usage error, 3 Apollo error (auth, rate limit, budget, plan).

## Brief fields (JSON)
Required: `brief_id`, `brief_version`, `supplier_range`, at least one positive filter.
Filters mapped to Apollo `POST /api/v1/mixed_companies/search`:

| brief field | Apollo parameter |
|---|---|
| `territory_locations` / `excluded_locations` | `organization_locations[]` / `organization_not_locations[]` |
| `sic_codes` / `excluded_sic_codes` | `organization_sic_codes[]` / `not_organization_sic_codes[]` |
| `naics_codes` / `excluded_naics_codes` | `organization_naics_codes[]` / `not_organization_naics_codes[]` |
| `industries` | `organization_industries[]` |
| `keywords` / `excluded_keywords` (≤150) | `q_organization_keyword_tags[]` / `q_not_organization_keyword_tags[]` |
| `employee_ranges` (`"min,max"`) | `organization_num_employees_ranges[]` |
| `excluded_domains` (≤1000, bare domains) | `not_organization_websites_list[]` |

`requested_volume` (1–50,000, Apollo's display limit), `counting_unit` (only `company`),
`exclusion_reference_version`, `notes`. Unknown fields are rejected so worksheet rules Apollo
cannot filter on (site activity, regulator evidence, group matching) are not silently dropped;
they belong in `notes` and with the analyst.

## Output
`<brief_id>-<brief_version>-candidates.csv` with fixed columns (`candidate_id`, `review_state`,
`data_mode`, brief ids, Apollo id, name, domain, URLs, industry, keywords, headcount, founded
year, city/state/country, short description, `retrieved_at`, `source`) and
`...-candidates.manifest.json` (brief, filters sent, pages/credits used, counts of duplicates
dropped and locally excluded domains, stop reason, CSV sha256). Every row is
`review_state=candidate_not_reviewed`. Duplicates are dropped by Apollo id and by normalised
domain; `excluded_domains` are also enforced locally as a safety net.

## Facts the client relies on (docs.apollo.io, "Organization Search", checked 3 Nov 2026)
Endpoint `POST https://api.apollo.io/api/v1/mixed_companies/search`, header `x-api-key`,
1 credit per page, 100 results per page, 50,000-record display limit (500 pages), response
`organizations` + `pagination{page,per_page,total_entries,total_pages}` + `partial_results_only`.
HTTP 403 means the plan/key lacks access to this endpoint; 429/5xx are retried with backoff.

**Retries and real spend.** A transport failure (connection reset, timeout, malformed body) is
retried up to 3 times without charging the budget again, because the client cannot tell whether
the request reached Apollo. If it did, Apollo charged it. Worst case, real spend per page is
1 + retries credits, so a `--credit-budget 1` first run can cost up to 4 credits. The manifest
records `apollo.transport_retries`; when it is non-zero, compare with Apollo's usage page.

## Tests
```
python -B -m unittest discover -s pipeline/tests -t .
```
Standard library only; no dependencies to audit. CI: `.github/workflows/pipeline-tests.yml`.
