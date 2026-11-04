# pipeline — ICP brief → Apollo company candidates (P2) → ZeroBounce verification (P3) → per-client export (P4)

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
APOLLO_API_KEY=... python -m pipeline prospects --brief BRIEF.json --out out/ --live --credit-budget 3
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

## P3: email verification with ZeroBounce (`verify`, `credits`)
Input: any CSV with an email column (`--email-column`, or the first of `email`, `work_email`,
`email_address`, `contact_email`). Output: the same rows plus `zb_status`, `zb_sub_status`,
`zb_free_email`, `zb_did_you_mean`, `zb_mx_found`, `zb_domain_age_days`, `zb_processed_at`,
`verification_decision`, `verified_at`, `verification_source`, and a manifest (input/output sha256,
batches, credits charged, counts by status and decision, API errors, stop reason).

```
python -m pipeline verify --input LIST.csv --out out/                                   # dry run: counts + max credits
python -m pipeline verify --input LIST.csv --out out/ --fixture pipeline/examples/zerobounce-results-fixture.json
ZEROBOUNCE_API_KEY=... python -m pipeline credits --live                                # balance, not charged
ZEROBOUNCE_API_KEY=... python -m pipeline verify --input LIST.csv --out out/ --live --credit-budget 50
```

- **Same safety defaults as P2:** offline unless `--live`/`--fixture`; key from `ZEROBOUNCE_API_KEY`
  only, sent in the request body (never a URL) and redacted from errors; `--credit-budget` (default 0)
  reserves one credit per address before each batch; a budget stop still writes every row, marking the
  rest `not_verified` / `review`.
- **Credits:** 1 per address; ZeroBounce never charges for `unknown` results, so the charged count can
  be below the reserved count. `credits --live` shows the balance without spending.
- **Decisions:** `keep` = valid; `drop` = invalid, spamtrap, abuse, do_not_mail, or a local syntax
  failure (not sent); `review` = catch-all, unknown, not verified. The analyst confirms before P4 delivery.
- **Data residency:** default host is `api-eu.zerobounce.net`; `api.zerobounce.net` and `api-us…`
  process in the United States (`--base-url` to change). Addresses are personal data: keep inputs
  and outputs outside the repository, and verify only lists with a lawful basis for the outreach.
- **Dedup:** each normalised address (trimmed, lower-cased) is verified once and mapped back to every row.
- **First live check without spending:** ZeroBounce's sandbox addresses (e.g. `valid@example.com`,
  `invalid@example.com`, `catch_all@example.com`, see docs "Sandbox Mode") return fixed results and
  cost nothing; run them with `--live --credit-budget 1` to confirm the key and host (batches shrink to
  the remaining budget, so one address is sent). `--base-url` only accepts the three documented
  ZeroBounce hosts (`api`, `api-us`, `api-eu` .zerobounce.net); the key is never sent anywhere else.
- Facts relied on (zerobounce.net/docs, checked 3 Nov 2026): `POST /v2/validatebatch` JSON
  `{api_key, email_batch:[{email_address, ip_address}]}` → `{email_batch:[…], errors:[…]}`; statuses
  valid, invalid, catch-all, unknown, spamtrap, abuse, do_not_mail; `GET/POST /v2/getcredits` →
  `{Credits}` (-1 = invalid key); batches above ~200 belong to the bulk file API; rate limits apply.

## P4: per-client export for manual delivery (`export`)
Builds `<out>/<client-slug>/<export-id>/` with a CSV (UTF-8 with BOM, every value quoted text), an
optional `.xlsx` (standard-library SpreadsheetML, every cell an inline string so identifiers keep
leading zeros and nothing is reinterpreted), a client-facing `README.txt` and `MANIFEST.json`
(inputs with sha256 and linked source manifests, selection applied, columns, per-file sha256).
Nothing is sent: Sean delivers the folder by hand.

```
python -m pipeline export --input out/list-verified.csv --out deliveries/ --client "Client Ltd" \
  --brief-ref BRIEF-2026-11-v1 --dictionary-version DICT-v1 --export-version EXPORT-v1 \
  [--include-decisions keep,review] [--drop-columns zb_sub_status,zb_domain_age_days] [--dedupe-on work_email] [--xlsx]
```

- Rows with a `verification_decision` are filtered to `keep` by default; `--include-decisions` widens that.
- `brief_ref`, `dictionary_version`, `export_version`, `export_id`, `exported_at` and `client_ref` are stamped on
  every row (the lesson of `foundation/handover-*.csv`: versions travel with the data, blank is not "none").
- CSV cells starting with `=`, `@`, or a `+`/`-` that is not a phone/signed number get a leading apostrophe
  (formula injection guard, as in Code.gs); the XLSX needs none because every cell is an inline string.
- `--include-decisions` must name at least one value; an empty list is a usage error, never an empty delivery.
- Several input CSVs may be combined when they share one header; a non-empty target folder is refused.
- `fiction_notice` columns are dropped unless `--keep-fiction-notice` (fixtures only).

## Tests
```
python -B -m unittest discover -s pipeline/tests -t .
```
97 tests, standard library only; no dependencies to audit. CI: `.github/workflows/pipeline-tests.yml`.
