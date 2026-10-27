INDUSTRIAL PROSPECT-LIST AUDIT — EDUCATIONAL ASSET PACK

FICTION NOTICE
Every row in the fictional batch and answer key is wholly invented, including its company/site identifiers, evidence text and project signal. These are not anonymised client data, real prospects or service results. No people, phone numbers or email addresses are supplied. Fictional source URLs, publication dates and review dates are blank; FIC-E identifiers are evidence-card labels, not citations.

START HERE
1. Read the exercise policy: FIC-BRIEF-01 version 1, ruleset OG02-HOLD-FIRST-1. Match that brief/version across the batch, answer key and schema. The accepted unit is one company manufacturing complete food-packaging machinery in the Republic of Ireland. No active project is required. Changing a criterion requires reassessment under a new version, not relabelling old results.
2. Inspect industrial-audit-fictional-batch.csv. Apply the gate rules without looking at the answer key. Source-use passes stipulate simulated internal review, retention and customer-facing summary sharing only. Internal access does not itself permit customer sharing: see FIC-R11. In FIC-R09 and FIC-R13 the operator is unresolved, so company-specific activity, territory and exclusion gates remain unknown pending attribution and rechecking.
3. Mark confirmed surplus references as duplicate and point to the retained company anchor. Preserve additional site evidence. Do not merge separate companies just because they share a group.
4. Hold material unknowns/conflicts, including unresolved company attribution. Otherwise reject positive failures; include only a resolved company anchor with every required gate passed. The conservative teaching policy puts unresolved material gates before rejection, even alongside a known failure. This is NOT universal policy: real briefs must agree their stopping/rejection rules. No score override exists. Preserve supplied_unit: an originally supplied brand or site may anchor a company once identity and all attributable company gates are established.
5. Check industrial-audit-answer-key.csv. Supplied 14 = duplicate 2 + include 4 + hold 5 + reject 3. Included 4 = industry-matched 3 + signal 1. Verify exactly one outcome for each original row ID; repeated and missing IDs can hide behind balanced totals. These are deliberately constructed exercise counts, not a benchmark or a demonstration of the 90/10 target. Included does not mean approved for delivery.
6. Complete industrial-audit-blank-worksheet.csv: scope, acceptance counts, class counts, hold ownership and release decision. It contains usable instructions and input fields. Blank means unknown, not zero.

FILES
industrial-audit-fictional-batch.csv: fourteen labelled input rows with invented evidence.
industrial-audit-answer-key.csv: per-row answer, rationale, class, duplicate pointer and next question.
industrial-audit-blank-worksheet.csv: blank manual scope/reconciliation/effort/handoff worksheet. Adapt only within an authorised workflow; not live-data approval.
industrial-audit-blank-rows.csv: five blank fictional-practice rows. Keep the fiction notice; replace the other blanks with your own invented exercise. This unfinished template must fail the fiction validator until completed.
industrial-audit-field-dictionary.csv: complete column definitions and allowed values.
industrial-audit-schema.json: self-contained educational CSV contract; custom declared schema, NOT JSON Schema draft 2020-12.
industrial-audit-policy.json: explicit fictional brief, within-batch boundary and expected counts for the supplied exercise only. Expected counts are not defaults for another batch.

EDITING
Import UTF-8 comma-separated CSV. Treat identifiers as text. A pipe separates multiple site IDs. There are no spreadsheet formulas, macros, external connections or automatic refresh. Keep the original input, evidence cards, supplied labels, units and row IDs. Each confirmed duplicate points directly to a resolved company anchor, not another duplicate; the anchor may be held or rejected. A site is supporting detail, not another company. Shared group membership does not prove common company identity. This small fixture permits at most one company per site ID; real shared-site relationships need a different reviewed contract.

Duplicate rows mirror the consolidated account assessment. If FIC-R03 reveals an unresolved activity contradiction, preserve both source statements, record the assessment separately, mark activity=conflict and evidence_consistency=conflict on FIC-R01, FIC-R02 and FIC-R03, and add the next verification question on FIC-R01. R01 is hold; R02/R03 remain duplicate only while same-company identity is confirmed. Any conflicted gate requires evidence_consistency=conflict, not a stale pass. A stale mismatch is refused rather than silently discarded. If identity becomes uncertain, withdraw the affected duplicate pointers/company attribution and hold the unresolved candidates. Do not manufacture equal passes to silence a checker.

The schema is a readable custom contract, not an app or a standard JSON Schema validator. No executable software is included in these eight public downloads. Review the exercise manually; internal author/reviewer checks do not verify natural-language truth, source rights or release authority. A fabricated attribution containing the right identifiers is still fabricated; human evidence review remains necessary. Blank practice rows are a separate fictional exercise: do not carry the supplied worked batch's expected counts into it.

EFFORT WORKSHEET
Enter nonnegative buyer-owned review and correction minutes. Enter measured or estimated in the respective basis fields. Total is known only if both inputs are known; any estimated input makes the result estimated. Minutes per included company is total / included only for a positive included-company count; otherwise not calculable. These are workload inputs, not ROI or performance predictions. Worksheet brief_version, input_batch_version and decision_policy must be recorded before combining counts.

BOUNDARIES
An included company is not a verified buyer, approved contact, marketing-qualified lead or technically validated equipment match. Source-use passes in this fiction do not establish permissions for real data. Real work requires evidence, relevant dates, applicable access/use terms, exclusions and independent review under the agreed brief. This pack grants no GDPR clearance or outreach authority. Research class and disposition are different fields; held/rejected/duplicate rows receive no included class.

ORIGIN
Original analyst-authored rules and wholly invented evidence. No external company data, competitor prose, imagery or directory rows reproduced. Related service/method pages provide offer context, not evidence for fictional companies.
