---
status: production-integration-candidate-not-published
version: '1.0'
created: '2026-10-27'
intended_route: eu-industrial-emissions-portal-research.html
title: Using the EU Industrial Emissions Portal to build a list of industrial facilities
meta_title: EU Industrial Emissions Portal Research | Demand Range
meta_description: Use the EEA Industrial Emissions Portal (E-PRTR and IED data) to find large industrial sites by country, sector and activity, then build a verified target list.
content_type: original-analyst-method
---


# Using the EU Industrial Emissions Portal to find industrial facilities

**Short answer:** the European Environment Agency's **Industrial Emissions Portal** is a free, public list of Europe's largest industrial installations. It is built from reporting under the Industrial Emissions Directive (2010/75/EU) and the E-PRTR Regulation (166/2006). Download the Industrial Reporting dataset (v16, February 2026, covering 2007–2024). Filter by country and activity, then add the operator company, named roles and a recent trigger to each facility. That gives an industrial supplier a verified, evidence-backed account list for process industries across the EU.

## 1. What's in the data

The portal and its Industrial Reporting downloads, including the v16 dataset, are published by the European Environment Agency.[1][2] The reporting behind them comes from the E-PRTR Regulation and the Industrial Emissions Directive.[3][4]

- **Facility identity:** name, address, coordinates, operator (parent company where reported) and activity code.
- **Activity:** the E-PRTR or IED activity the installation is regulated for, for example chemicals, energy, metals, minerals, paper, food and drink, waste and intensive livestock.
- **Releases and transfers:** pollutant releases to air and water, off-site transfers of waste and of pollutants in wastewater.
- **Large combustion plants:** fuel input and emissions for LCPs.

The installation and site identities come from the EU Registry on Industrial Sites, which links the reporting entities together.[1]

## 2. Step by step: from download to account list

1. **Download** the latest Industrial Reporting dataset from the EEA download page.[2] Use the facility table as your master list.
2. **Filter by country and activity.** For example, you might keep only mainland Europe's food and drink installations or the chemical installations in Benelux.
3. **Decide what a buying signal looks like for your product.** A wastewater transfer suggests on-site treatment, and that means pumps, dosing and instruments. A large combustion plant points to boilers, burners and heat recovery.
4. **Resolve the operator** to a legal entity in the national company register, and record the parent group.
5. **Add named roles:** site or plant manager, engineering manager, EHS lead, procurement.
6. **Add one current trigger** per account, such as a permit review, an expansion, a tender or a published investment.
7. **Track your work** in the free [account research template](account-research-template.csv).

> **Fictional example:** A fictional maker of membrane filtration skids filters the dataset for food and drink installations in two countries that report transfers of pollutants in wastewater. It ends up with a shortlist of large dairies and breweries, resolves each to its operating company, and finds the engineering manager at each site. *This example is fictional and only illustrates the method.*

## 3. Limits to plan for

- **Coverage:** only installations above the annex capacity thresholds. Use national registers and [NACE-based company lists](nace-rev-2-1-industrial-account-lists.html) for smaller manufacturers.
- **Time lag:** the February 2026 release runs to 2024,[2] so confirm the site is still operating.
- **Operator names** may be a site company, not the group that buys. Always resolve the group.
- **Regulatory change:** Regulation (EU) 2024/1244 replaces E-PRTR, with new reporting rules from reporting year 2027.[5][6] Fields and coverage will change, so recheck your filters after each release.

## 4. Country registers that add detail

National registers often carry permit documents and inspection records that the EU portal doesn't. In Ireland, the EPA publishes licence files and PRTR returns. See our guides to [Irish PRTR account research](irish-prtr-industrial-account-research.html) and [Irish environmental register evidence](irish-environmental-register-evidence.html). Chemical producers across the EU are covered in our [European chemical manufacturer research](european-chemical-manufacturer-research.html) guide.

## How Demand Range helps

Demand Range builds verified account lists from public industrial data like this. Each list records the facility, its operating company, named decision-makers and the evidence behind the row. See [industrial lead research](industrial-lead-research.html), [request a quote](request-a-quote.html) or email partners@demandrange.com.

## Sources

[1] https://industry.eea.europa.eu/ — European Environment Agency, European Industrial Emissions Portal
[2] https://industry.eea.europa.eu/download — European Environment Agency, Industrial Emissions Portal downloads (Industrial Reporting dataset v16, February 2026)
[3] https://eur-lex.europa.eu/eli/reg/2006/166/oj — Regulation (EC) No 166/2006 (E-PRTR)
[4] https://eur-lex.europa.eu/eli/dir/2010/75/oj — Directive 2010/75/EU (Industrial Emissions Directive)
[5] https://eur-lex.europa.eu/eli/reg/2024/1244/oj/eng — Regulation (EU) 2024/1244 (Industrial Emissions Portal Regulation)
[6] https://environment.ec.europa.eu/topics/industrial-emissions-and-safety/industrial-emissions-portal-regulation-iepr_en — European Commission, Industrial Emissions Portal Regulation (IEPR) overview
