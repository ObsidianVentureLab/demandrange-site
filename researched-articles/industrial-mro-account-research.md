---
status: production-integration-candidate-not-published
version: '1.0'
created: '2026-10-14'
intended_route: industrial-mro-account-research.html
title: 'Industrial MRO account research: follow the service scope, not the label'
meta_title: 'Industrial MRO Account Research | Demand Range'
meta_description: 'Separate inspection, repair, parts provision and replenishment in industrial maintenance research. Work a fictional service chain and use a blank scope worksheet.'
content_type: original-analyst-method
---

# Industrial MRO account research: follow the service scope, not the label

For a parts supplier researching maintenance, repair and overhaul (MRO), the useful question is not simply “Who services this equipment?” It is **what crosses the service boundary, who provides it, and which responsibility is still unestablished?** A report, a repaired customer-owned assembly and a supplied spare assembly are different outputs.

This proposed research method is not an industry standard, market-demand finding or maintenance instruction. The service chain below is entirely fictional. It identifies no real prospects, installed equipment or purchasing opportunities.

[Open the blank MRO scope worksheet](industrial-sales-resources.html#mro-scope-download)

## Define the service output

Start with a brief: “Research businesses performing [specific work] on [equipment family] in [territory], where [parts-provision responsibility] is required.” Decide whether that means an operator-side maintenance route, repair with parts provision, or a stocking channel. Use the existing [ICP guide](industrial-ideal-customer-profile.html) for identity, territory and exclusions; do not recreate those rules from an MRO keyword.

For each service description, ask what arrives, what work is performed and what leaves. Does the provider return a finding, the same repaired assembly, another assembly to take its place, or separately supplied parts? Record whether the description concerns a general capability, an agreed scope or a completed job. None automatically establishes the others.

Keep these working distinctions explicit:

- **Equipment operation:** running the relevant equipment; not necessarily inspecting it or procuring its parts.
- **Inspection:** examining or reporting within a stated scope; not evidence of a fault, repair commission or parts order.
- **Repair or overhaul:** record the actual described work. Do not expand “repair” into a complete overhaul or assume either includes new parts.
- **Provision of spares:** supplying a part or assembly to take the place of another. Separate provision from fitting, technical approval and the decision to replace.
- **Stocking and replenishment:** holding specified stock and responsibility for replacing consumed stock are separate questions. Neither follows from supplying a repair once.

These are research distinctions, not technical or contractual definitions. Where the description is broad, return a narrower question rather than supplying an imagined service package.

## Work the fictional service chain

All organisations, scope notes and outcomes here are invented. They describe one teaching arrangement, not a typical industry model. The supplier's question is whether a service provider's scope includes providing parts to be fitted; stockholding is a separate optional question. No repair is presented as currently needed or available.

<dl>
<dt>Operator O — the starting boundary</dt>
<dd><p>An invented note assigns operation of a fictional handling line to O. It assigns neither equipment ownership nor maintenance purchasing. Retain the operating relationship. Do not infer the line's component inventory or nominate O as the parts buyer.</p></dd>
<dt>Inspector I — inspection-only output</dt>
<dd><p>I receives access to that line and returns an inspection report. Its stipulated scope expressly excludes repair and parts provision. I is outside this parts-providing service route for this arrangement, even if inspection itself is relevant to another brief. The report's existence establishes no fault or remedial order.</p></dd>
<dt>Workshop R — repair with client-supplied parts</dt>
<dd><p>R receives a customer-owned assembly and a client-supplied parts kit, performs the specified repair labour, and returns the assembly. Its scope excludes obtaining the kit. Preserve the repair capability but exclude this arrangement from a route requiring R to provide parts. The note does not identify who purchased the kit; do not convert “client-supplied” into an attributed order.</p></dd>
<dt>Service Provider S — parts provision expressly included</dt>
<dd><p>A separate scope note assigns S both repair labour and provision of the specified parts to be fitted to an assembly. That supports the parts-provision boundary for S's arrangement, not independent product choice, an installed fleet or a new order. Retain this boundary for research; full account acceptance still needs the agreed checks.</p></dd>
</dl>

The notes do not describe a confirmed referral from I to R or S. Their common teaching context is not evidence of a commercial relationship between providers. Keep R and S as alternative service arrangements, not successive stages of a real job.

## Follow the unresolved parts question

Add another invented note for **S only**: the client approves the part model and S places the order. Ordering is now supported for that scope. Supplier selection remains unestablished: the note does not say whether S chooses the seller or follows a nomination. Ask that exact question rather than treating ordering as complete purchasing authority.

A further invented description says S offers spare assemblies. It says nothing about stock on hand, ownership of stored items, minimum holdings or responsibility for replenishment. Keep all of those unknown. An offering can be investigated without describing it as an available stock line. Parts availability and availability of an order to a new supplier are also different unknowns.

**Counterfactual:** if S's first note merely said “repair support”, its parts-provision status would change to unknown. Hold that route condition; do not turn missing detail into an exclusion. Conversely, R's explicit client-supplied-kit restriction cannot be cleared by a generic “spares” page unless evidence resolves the same arrangement and period.

A useful next check is a permitted scope description identifying who obtains the parts and any selection restriction. For a stocking brief, request separate evidence of the relevant holding and replenishment responsibility. If the agreed bounded review cannot establish it, return the gap; do not infer repeat demand from a single service description.

## Keep six conclusions independent

1. **Account fit:** does the company meet the authorised activity, territory and exclusion rules? A relevant service capability can support fit without a live maintenance event.
2. **Current maintenance need:** is a specific present task evidenced? Capability, an inspection service or an old completed repair does not supply that fact.
3. **Installed-base evidence:** which assets, if any, are actually attributed to the relevant operation and period? A supported assembly in one job does not establish a fleet, model count or serviceable market.
4. **Parts compatibility:** leave suitability unassessed by this method. A product-family match cannot resolve interfaces, specifications or engineering approval.
5. **Purchasing authority:** separate model approval, supplier selection and order placement for the exact parts scope. A service label answers none of them automatically.
6. **Availability:** keep stock availability, service capacity and an open purchasing route separate. None follows from account fit or parts provision.

Do not derive equipment life, inspection frequency, maintenance intervals, failures or renewal timing from this chain. The output is a research handover, not a diagnosis, engineering selection or prediction of buying intent.

## Use the blank scope worksheet

The [header-only CSV in the resource library](industrial-sales-resources.html#mro-scope-download) has zero data rows, no contacts, formulas or automatic decisions. Fictional examples stay in this article. Import as UTF-8 text; keep completed copies locally and do not enable formula interpretation for pasted content.

**One row is one fact or open question about one service boundary**, not one company or maintenance event. Use additional rows for separate evidence, responsibilities or conflicting statements. Every field is defined below:

- `record_id`: unique row identifier. `company_id`: resolved or explicitly provisional company reference. `scope_id`: shared identifier for the particular service arrangement. Repeated IDs here do not add accounts.
- `brief_version`: governing research brief. `record_context`: working research or clearly labelled fictional practice. `service_scope`: the operation, equipment-family question, location and relevant period; mark unknowns rather than inventing an asset.
- `scope_basis`: capability, agreed scope, completed job or unknown. `input_boundary`: what is received. `output_boundary`: what is returned or provided. Keep each conditional until evidenced.
- `fact_name`: the single assertion tested, such as inspection scope, repair work, parts provision, stockholding, replenishment, model approval or order placement. Use separate rows for each of the six conclusions above.
- `fact_status`: supported, explicit_negative, unknown, conflict or not_assessed. `permitted_observation`: the narrowly supported fact, not your sales inference; leave empty when unknown or reuse is unresolved.
- `evidence_reference`: exact item and section, or a permitted controlled reference. `source_stated_date`: date actually supplied by the source, otherwise blank. `checked_date`: actual review date, not a freshness claim. `source_use_status`: intended-use review outcome and any restriction.
- `responsibility_limit`: express exclusions or approval constraints. `research_implication`: your bounded interpretation. `next_question`: the missing link. `stopping_rule`: the agreed check boundary and what stays held if unresolved.

A positive or negative finding needs its own supporting reference. Preserve competing evidence separately under the same scope ID. Never paste restricted manuals, customer asset registers, confidential work orders or personal details; public visibility alone does not clear reuse.

## Hand over the boundary, not a presumed buyer

Try: “Investigate [service activity/territory] accounts for [parts family]. Establish the service output and parts-provision boundary. Separate client-supplied materials, approval, selection, ordering and replenishment. Return unresolved questions without inferring installed assets or current need.”

Demand Range's service describes company-level research against an agreed brief, with contacts and outreach separately scoped.[1] Its methodology separates observations, interpretations and unknowns.[2] These references provide offer context only, not validation of this proposed MRO method or its fictional cases.

Review the [industrial account-research service](industrial-lead-research.html), inspect the [fictional account sample](sample-account-research.html), or [request a scoped quote](request-a-quote.html).

Share only non-sensitive range and scope questions. This worksheet grants no source-use or outreach permission and promises no leads, availability or commercial outcome.

## Sources

[1] https://demandrange.com/industrial-lead-research.html — Demand Range: company-level research service and scope
[2] https://demandrange.com/methodology.html — Demand Range: observations, interpretation and unknowns
