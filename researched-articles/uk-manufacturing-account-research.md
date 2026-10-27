---
status: "production-integration-candidate-not-published"
version: "1.0"
created: "2026-10-27"
intended_route: "uk-manufacturing-account-research.html"
title: "How to build a list of UK manufacturers that fits your brief"
meta_title: "How to Build a List of UK Manufacturers | Demand Range"
meta_description: "How to build a list of UK manufacturers: pull candidates from Companies House by SIC 2007 code, confirm the operating site from regulator registers, and record include, hold or reject for each company."
content_type: "week1-batch1-port-of-704b5eb"
---

# How to build a list of UK manufacturers that fits your brief

<strong>Start from a written brief, pull candidate companies from Companies House using SIC 2007 codes in Section C (Manufacturing), then confirm each company's operating site and activity from a second source before it goes on the list.</strong> The SIC code is chosen by the company when it files, and the registered office is often an accountant's or head office address, so neither proves that production happens at a site.

The useful output is not a row count. It is an include, hold or reject decision for every candidate, with the reason and the source. Worked companies on this page are fictional.

[Request a written scope](request-a-quote.html) · [Download the blank account template (CSV)](account-research-template.csv)

## Define the UK brief before searching

<p>Write down four things before you open a register:</p>

<dl class="research-ledger">
<dt>Activity</dt><dd>What the customer must do for your product to matter: “pasteurises liquid milk”, not “food”. An activity can be tested against a source; a sector label cannot.</dd>
<dt>Territory</dt><dd>England, Scotland, Wales and Northern Ireland are covered by one company register but by different environmental regulators. Say which nations are in scope and whether the test is the registered office or the operating site.</dd>
<dt>Counting unit</dt><dd>Company or site. A group with three plants can be one account, three sites or four records; decide before counting.</dd>
<dt>Exclusions</dt><dd>Existing customers, distributors without production, service-only firms, dormant companies or anything else your team will reject on sight.</dd>
</dl>

<p>The <a href="industrial-ideal-customer-profile.html">ideal customer profile guide</a> has a blank worksheet for this step.</p>

## Pull candidates from Companies House

<p>Companies House makes the public data it holds on companies available free of charge, without registration, including the registered office address, company status and nature of business (SIC) codes.[1] Three routes are useful:</p>

<ul>
<li><strong>Advanced search</strong> on the Find and update company information service, filtered by nature of business, status and location.</li>
<li><strong>The Public Data API</strong>, whose advanced company search accepts several <code>sic_codes</code> in one query and returns up to 5,000 results per request.[2]</li>
<li><strong>The Free Company Data Product</strong>, a monthly CSV snapshot of basic data on live companies on the register.[3]</li>
</ul>

<p>Companies House uses a condensed list of SIC 2007 codes; Section C covers manufacturing, with five-digit codes such as <strong>10511</strong> (liquid milk and cream production).[4] The underlying UK SIC 2007 classification is maintained by the Office for National Statistics.[5]</p>

<p>Two limits matter. First, the code is the company's own choice when it files, so a manufacturer can carry a holding-company or wholesale code and a trader can carry a manufacturing one. Second, location filters match the <strong>registered office</strong>, which may be a head office, an accountant or a formation agent rather than the plant. Treat this step as a candidate pool, not a list.</p>

## Confirm the operating site and activity

<p>For each candidate, look for a second, independent source that ties the company to a site and an activity:</p>

<dl class="research-ledger">
<dt>The company's own site pages</dt><dd>Named plant addresses, process descriptions and capability statements. Record the date you saw them.</dd>
<dt>England: Environment Agency</dt><dd>Public registers including environmental permits for industrial installations, searchable by name, address and permit.[6]</dd>
<dt>Scotland, Wales and Northern Ireland</dt><dd>SEPA, Natural Resources Wales and DAERA (for NIEA permits) publish their own registers and data.[7][8][9]</dd>
<dt>Major-hazard sites in Great Britain</dt><dd>HSE's public information search covers establishments subject to COMAH 2015.[10] Northern Ireland is regulated separately.</dd>
</dl>

<p>A permit shows that a regulated activity is authorised at a site. It does not show what equipment is installed, whether the activity is running today or who buys for it. Record what the source says and keep your inference in a separate field.</p>

## Include, hold or reject every candidate

<dl class="research-ledger">
<dt>Include</dt><dd>Identity is confirmed on the register, the company is active, and a dated source ties the stated activity to an in-scope site.</dd>
<dt>Hold</dt><dd>The company looks relevant but the site or activity is unconfirmed, for example a holding company whose subsidiaries may operate the plant. Write the next check.</dd>
<dt>Reject</dt><dd>A source states something that fails the brief: dissolved, dormant, resale only, out-of-scope nation. Record that reason, not “not a fit”.</dd>
</dl>

<p>A hold is not a reject. Rejecting for missing evidence silently shrinks your market; holding keeps the question visible. The same method applied to Ireland is in the <a href="irish-manufacturing-account-research.html">Irish manufacturing account-research guide</a>.</p>

## A worked example (fictional)

<p><strong>Brief (fictional):</strong> a supplier of hygienic valves wants dairy processors with a production site in Scotland or Northern Ireland. Exclude wholesalers and existing customers. Count each site once.</p>

<dl class="research-ledger">
<dt>Company A — SIC 10511, registered office in Glasgow</dt><dd>Website names a creamery in Ayrshire and describes pasteurising and bottling. <strong>Include</strong> the Ayrshire site, citing the website and its review date.</dd>
<dt>Company B — SIC 70100 (activities of head offices), registered office in Belfast</dt><dd>Group pages mention two dairy plants operated by subsidiaries. <strong>Hold</strong>: map the subsidiaries and their sites before counting.</dd>
<dt>Company C — SIC 46330 (wholesale of dairy products)</dt><dd>Website describes distribution only, with no processing site. <strong>Reject</strong> for the stated reason: resale only.</dd>
<dt>Company D — SIC 10512, status dormant</dt><dd><strong>Reject</strong>: dormant on the register. Note it in case it becomes active again.</dd>
</dl>

<p>Companies A to D are invented for illustration and are not real companies, clients or prospects.</p>

## Record the decisions in a reusable worksheet

<p>Use the free <a download="" href="account-research-template.csv">account-research template (CSV)</a>. It keeps the company or site, fit reason, source reference, publication and review dates, observed fact, inference, unknowns, decision and next check in separate columns. The <a href="account-research-field-dictionary.csv" download="">field dictionary (CSV)</a> explains each column, and the <a href="sample-account-research.html">fictional sample</a> shows completed records.</p>

<p>If you are reviewing a list someone else built, start from the <a href="industrial-sales-resources.html#review-quality">list-review guides</a> instead.</p>

## Frequently asked questions

<dl>
<dt>How do I get a list of UK manufacturing companies?</dt><dd>Search Companies House by SIC 2007 codes in Section C (Manufacturing) using its free advanced search, Public Data API or monthly Free Company Data Product. Then confirm each candidate's operating site and activity from a second source, such as the company's website or an environmental permit register, before adding it.</dd>
<dt>Which SIC codes cover manufacturing in the UK?</dt><dd>Section C of the UK SIC 2007 covers manufacturing, using two-digit divisions 10 to 33. Companies House uses a condensed list of five-digit codes, for example 10511 for liquid milk and cream production.</dd>
<dt>Is the Companies House address the factory?</dt><dd>Not necessarily. Companies House records the registered office, which can be a head office, an accountant or a formation agent. Confirm the operating site separately.</dd>
<dt>Is Companies House data free?</dt><dd>Yes. Companies House makes the public data it holds on companies available free of charge, including through its website, API and a free monthly bulk snapshot of live companies.</dd>
<dt>Does a SIC code prove what a company makes?</dt><dd>No. The company chooses its own SIC code when filing. Use it to find candidates, then confirm the activity from a dated source.</dd>
<dt>Are Northern Ireland companies on Companies House?</dt><dd>Yes, Northern Ireland companies are on the Companies House register, but environmental permits there are handled by DAERA's Northern Ireland Environment Agency, and HSE's COMAH search covers Great Britain.</dd>
<dt>What about sole traders and partnerships?</dt><dd>Most are not on the Companies House register, so a register-based list will miss them. If small unincorporated businesses matter to your brief, plan other sources.</dd>
</dl>

## Sources

[1] https://www.gov.uk/guidance/searching-the-companies-house-register — GOV.UK — Searching the Companies House register
[2] https://developer-specs.company-information.service.gov.uk/companies-house-public-data-api/reference/search/advanced-company-search — Companies House Public Data API — Advanced search for a company
[3] https://download.companieshouse.gov.uk/en_output.html — Companies House — Free Company Data Product
[4] https://resources.companieshouse.gov.uk/sic/ — Companies House — Nature of business: SIC codes (condensed SIC 2007 list)
[5] https://www.ons.gov.uk/methodology/classificationsandstandards/ukstandardindustrialclassificationofeconomicactivities/uksic2007 — Office for National Statistics — UK SIC 2007
[6] https://environment.data.gov.uk/public-register/view/index — Environment Agency — Public registers online
[7] https://www.sepa.org.uk/environment/environmental-data/ — SEPA — Environmental data
[8] https://naturalresources.wales/permits-and-permissions/check-for-a-permit-licence-or-exemption/?lang=en — Natural Resources Wales — Check for a permit, licence or exemption
[9] https://www.daera-ni.gov.uk/articles/public-registers — DAERA (Northern Ireland) — Public registers
[10] https://www.hse.gov.uk/comah/comah-establishments.htm — HSE — Public information on establishments subject to COMAH 2015

Sources were checked on <strong>27 October 2026</strong>. Companies House, ONS, Environment Agency and HSE material is Crown copyright, used under the Open Government Licence v3.0 where applicable. No register exports or real company records are reproduced here; the method and fictional cases are Demand Range's own work.
