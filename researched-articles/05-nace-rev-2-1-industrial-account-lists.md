---
status: production-integration-candidate-not-published
version: '1.0'
created: '2026-10-27'
intended_route: nace-rev-2-1-industrial-account-lists.html
title: 'NACE Rev. 2.1 manufacturing codes: what changed and how to fix your industrial account lists'
meta_title: NACE Rev. 2.1 Manufacturing Codes | Demand Range
meta_description: What NACE Rev. 2.1 changes in manufacturing (Section C) and how to map old NACE Rev. 2 codes to new ones in industrial account lists without losing accounts.
content_type: original-analyst-method
---


# NACE Rev. 2.1 manufacturing codes: what changed for industrial account lists

**Short answer:** NACE Rev. 2.1 is the EU's updated activity classification, set by Regulation (EU) 2023/137. It is being phased into official statistics from 1 January 2025 through to 2031, and it has 22 sections instead of 21. Most manufacturing (Section C) codes are unchanged. A handful of classes your target list may depend on were split, merged or redefined, so map old codes with Eurostat's correspondence tables and review those classes by hand.

## 1. Section C changes that matter for industrial suppliers

Regulation (EU) 2023/137 sets NACE Rev. 2.1 and its 22 sections, and Eurostat's methodology describes the phase-in from 2025 to 2031.[1][2] Eurostat's correspondence tables map old codes to new ones.[3]

The table below is a summary; the Eurostat methodology document is the authoritative source.[2]

| Area | What changed (summary) | What to do in your list |
|---|---|---|
| Division 14 (wearing apparel) | Restructured | Remap any apparel targets |
| 16.1 (sawmilling) | Split into 16.11 and 16.12 | Decide which part fits your ICP |
| 20.51 | Now covers liquid biofuels; explosives, glues and essential oils moved to 20.59 | Re-check chemical sub-segments |
| 22.23 (plastic builders' ware) | Split into 22.23, 22.24 and 22.25 | Remap plastics targets |
| 25.21 (central heating radiators and boilers) | Merged with 25.30 | Combine the two lists |
| Group 25.6 (treatment and coating of metals; machining) | Restructured | Review every machining and coating account |
| 26.8 (magnetic and optical media) | Merged into 26.7 | Minor for most industrial lists |
| Additive manufacturing | Given its own class in division 28 | New segment to test |
| Division 31 (furniture) | Consolidated into 31.00 | Simplify furniture filters |

Check each row against the Eurostat publication before you recode production data.[2]

## 2. A safe recoding process

1. **Export** your account list with the current NACE Rev. 2 or UK SIC 2007 code on each row.
2. **Join** it to Eurostat's NACE Rev. 2 → Rev. 2.1 correspondence table.[3]
3. **Flag one-to-many rows,** where one old class maps to several new ones. These need a human decision, usually from the company's website or its register filing.
4. **Keep both codes** during the transition. National registers and statistics move at different speeds; Germany, for example, runs WZ 2025 alongside WZ 2008.[4]
5. **Re-run your ideal customer profile filters** against the new codes, and compare account counts before and after.

> **Fictional example:** A fictional coatings supplier targets NACE 25.61 (treatment and coating of metals). After recoding, a fictional set of its accounts falls into restructured classes under group 25.6. The supplier reviews each one by hand, keeps both codes in its CRM, and updates its ICP filter so no accounts are silently dropped. *This example is fictional and only illustrates the method.*

## 3. UK and Irish lists

- **UK:** Companies House records use UK SIC 2007, which is derived from NACE Rev. 2.[5] Don't assume a UK code matches a NACE Rev. 2.1 code.
- **Ireland:** check which NACE version each dataset uses. For the Irish manufacturing base, see our [Irish manufacturing account research](irish-manufacturing-account-research.html) guide.

## 4. Codes are a starting point, not a list

Activity codes are self-declared and often out of date. Use them to build a first cut. Then confirm each account with evidence: products on the website, permits (see the EU Industrial Emissions Portal guide), tenders and hiring. Our [industrial ideal customer profile](industrial-ideal-customer-profile.html) and [prospect list maintenance](industrial-prospect-list-maintenance.html) guides cover that step.

## How Demand Range helps

Demand Range builds and maintains industrial account lists with verified activity, named roles and the evidence for each row, mapped to the classification you use. See [industrial lead research](industrial-lead-research.html), [request a quote](request-a-quote.html) or email partners@demandrange.com.

## Sources

[1] https://eur-lex.europa.eu/eli/reg_del/2023/137/oj — Commission Delegated Regulation (EU) 2023/137 (NACE Rev. 2.1)
[2] https://ec.europa.eu/eurostat/web/products-manuals-and-guidelines/w/ks-gq-24-007 — Eurostat, NACE Rev. 2.1 methodology (KS-GQ-24-007)
[3] https://ec.europa.eu/eurostat/web/nace/correspondence-tables — Eurostat, NACE correspondence tables
[4] https://www.destatis.de/DE/Methoden/Klassifikationen/Gueter-Wirtschaftsklassifikationen/klassifikation-wz-2025.html — Destatis (Statistisches Bundesamt), Klassifikation der Wirtschaftszweige, Ausgabe 2025 (WZ 2025)
[5] https://resources.companieshouse.gov.uk/sic/ — Companies House, UK SIC 2007 codes
