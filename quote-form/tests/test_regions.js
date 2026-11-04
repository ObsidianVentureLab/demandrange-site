'use strict';
// Regions contract: the live page, the template, form_schema.json and Code.gs must agree,
// and the handler must accept every value the live form can send (plus legacy values) while
// rejecting empty, unknown, label-text and case-mangled values. Local only; no Google calls.
const assert = require('assert');
const fs = require('fs');
const path = require('path');
const vm = require('vm');

const ROOT = path.resolve(__dirname, '..');
const read = (...parts) => fs.readFileSync(path.join(ROOT, ...parts), 'utf8');
const schema = JSON.parse(read('form_schema.json'));
const fixture = JSON.parse(read('tests', 'valid_submission.json'));
const context = {console};
vm.createContext(context);
vm.runInContext(read('apps-script', 'Code.gs'), context, {filename: 'Code.gs'});
const api = context.__DEMANDRANGE_TEST__;
assert(api, 'Test export missing');

let assertions = 0;
function check(condition, message) { if (!condition) throw new Error(message); assertions += 1; }

// Region checkboxes as rendered in an HTML document: [{value, label}] in document order.
function regionCheckboxes(html) {
  const pattern = /<input[^>]*\bname="regions"[^>]*>/g;
  return (html.match(pattern) || []).map(tag => {
    check(/\btype="checkbox"/.test(tag), 'regions control is not a checkbox: ' + tag);
    const value = (tag.match(/\bvalue="([^"]*)"/) || [])[1];
    const label = (tag.match(/\bdata-label="([^"]*)"/) || [])[1];
    check(typeof value === 'string' && value.length > 0, 'regions checkbox without value: ' + tag);
    return {value, label};
  });
}

function submit(regions) {
  const payload = JSON.parse(JSON.stringify(fixture));
  payload.form_load_ms = String(Date.now() - 3000);
  payload.regions = regions;
  const parameters = {};
  Object.entries(payload).forEach(([key, value]) => { parameters[key] = Array.isArray(value) ? value : [String(value)]; });
  return api.parseAndValidate_({parameters}, Date.now());
}
function accepted(regions) { return Array.from(submit(regions).regions); }
function rejected(regions, label) {
  assert.throws(() => submit(regions), /regions|required_selection/, label + ' was not rejected');
  assertions += 1;
}

// --- 1. Single source of truth: live page == template == schema == handler -------------------
const live = regionCheckboxes(read('live', 'request-a-quote.html'));
const template = regionCheckboxes(read('request-a-quote.template.html'));
const liveValues = live.map(r => r.value);
check(liveValues.length === 3, 'live form should offer exactly three regions, got ' + liveValues.join(','));
assert.deepStrictEqual(liveValues, ['IE', 'UK', 'EU'], 'live form region values changed; refresh the contract'); assertions += 1;
assert.deepStrictEqual(template.map(r => r.value), liveValues, 'template regions differ from the live page'); assertions += 1;
assert.deepStrictEqual(template.map(r => r.label), live.map(r => r.label), 'template region labels differ from the live page'); assertions += 1;
assert.deepStrictEqual(schema.fields.regions.values, liveValues, 'form_schema.json regions differ from the live page'); assertions += 1;
assert.deepStrictEqual(Object.keys(schema.fields.regions.labels), liveValues, 'schema labels keyed off a different region set'); assertions += 1;
live.forEach(r => { check(schema.fields.regions.labels[r.value] === r.label, 'schema label mismatch for ' + r.value); });
check(schema.fields.regions.max_selections === liveValues.length, 'max_selections must match the number of form options');
assert.deepStrictEqual(Array.from(api.FORM.regions), liveValues, 'Code.gs FORM.regions differs from the live page'); assertions += 1;
assert.deepStrictEqual(Array.from(api.FORM.legacyRegions), schema.fields.regions.legacy_values, 'Code.gs legacy list differs from schema'); assertions += 1;
assert.deepStrictEqual(Array.from(api.FORM.acceptedRegions), liveValues.concat(schema.fields.regions.legacy_values), 'accepted list must be form values followed by legacy values'); assertions += 1;
check(liveValues.every(v => !schema.fields.regions.legacy_values.includes(v)), 'a live value must not also be listed as legacy');
check(new Set(api.FORM.acceptedRegions).size === api.FORM.acceptedRegions.length, 'accepted regions contain duplicates');

// --- 2. Every value the live form can send is accepted, alone and in any combination ----------
liveValues.forEach(value => { assert.deepStrictEqual(accepted([value]), [value], value + ' rejected'); assertions += 1; });
assert.deepStrictEqual(accepted(liveValues), liveValues, 'all live regions together rejected'); assertions += 1;
assert.deepStrictEqual(accepted(['EU', 'IE']), ['IE', 'EU'], 'order should normalise to form order'); assertions += 1;
assert.deepStrictEqual(accepted(['UK', 'UK']), ['UK'], 'duplicate selection should collapse'); assertions += 1;

// --- 3. Legacy worldwide values remain accepted for compatibility -----------------------------
schema.fields.regions.legacy_values.forEach(value => { assert.deepStrictEqual(accepted([value]), [value], 'legacy ' + value + ' rejected'); assertions += 1; });
assert.deepStrictEqual(accepted(['EMEA', 'IE']), ['IE', 'EMEA'], 'mixed live + legacy rejected'); assertions += 1;

// --- 4. Bad, empty and case-mangled values are rejected ---------------------------------------
rejected([], 'empty selection');
rejected([''], 'blank value');
rejected(['ie'], 'lower-case IE');
rejected(['Uk'], 'mixed-case UK');
rejected(['eu'], 'lower-case EU');
rejected(['emea'], 'lower-case legacy');
rejected(['Ireland'], 'label text instead of value');
rejected(['United Kingdom (including Northern Ireland)'], 'long label text instead of value');
rejected(['GB'], 'ISO code the form never sends');
rejected(['GLOBAL'], 'unknown value');
rejected(['IE,UK'], 'comma-joined values');
rejected(['IE|UK'], 'pipe-joined values');
rejected(['IE', 'GLOBAL'], 'valid plus unknown');
rejected(['EMEA', 'nam'], 'legacy plus case-mangled legacy');
rejected(['X'.repeat(101)], 'oversize value');

// --- 5. Drift guard: every checkbox taxonomy and hidden version the page sends must be accepted -----
// Covers industries and seniority (not just regions) and the form/privacy/consent version fields, for
// both the live snapshot and the template as build_site.py renders it. A mismatch fails CI.
// Browsers decode attribute entities before submitting, so compare the decoded value.
const ENTITIES = {'&amp;': '&', '&lt;': '<', '&gt;': '>', '&quot;': '"', '&#39;': "'", '&apos;': "'"};
function decodeAttr(value) { return value.replace(/&(amp|lt|gt|quot|#39|apos);/g, m => ENTITIES[m]); }
function checkboxValues(html, name) {
  const pattern = new RegExp('<input[^>]*\\bname="' + name + '"[^>]*>', 'g');
  return (html.match(pattern) || []).map(tag => decodeAttr((tag.match(/\bvalue="([^"]*)"/) || [])[1]));
}
function hiddenValue(html, name) {
  const tag = (html.match(new RegExp('<input[^>]*\\bname="' + name + '"[^>]*>')) || [])[0];
  check(tag && /\btype="hidden"/.test(tag), name + ' hidden input missing');
  return (tag.match(/\bvalue="([^"]*)"/) || [])[1];
}
const buildSource = read('..', 'build_site.py');
function buildConstant(name) {
  const match = buildSource.match(new RegExp('^' + name + " = '([^']+)'$", 'm'));
  check(match, 'build_site.py does not define ' + name);
  return match[1];
}
const templateRendered = read('request-a-quote.template.html')
  .replace(/\{\{FORM_VERSION\}\}/g, buildConstant('FORM_VERSION'))
  .replace(/\{\{PRIVACY_VERSION\}\}/g, buildConstant('PRIVACY_VERSION'))
  .replace(/\{\{CONSENT_VERSION\}\}/g, buildConstant('CONSENT_VERSION'));
[['live page', read('live', 'request-a-quote.html')], ['template (rendered)', templateRendered]].forEach(([label, html]) => {
  const taxonomies = [['industries', api.FORM.industries, schema.fields.industries.values],
                      ['regions', api.FORM.acceptedRegions, schema.fields.regions.values.concat(schema.fields.regions.legacy_values)],
                      ['seniority', api.FORM.seniority, schema.fields.seniority.values]];
  taxonomies.forEach(([name, handlerValues, schemaValues]) => {
    const sent = checkboxValues(html, name);
    check(sent.length > 0, label + ': no ' + name + ' checkboxes found');
    sent.forEach(v => { check(Array.from(handlerValues).includes(v), label + ': ' + name + ' value ' + JSON.stringify(v) + ' is not accepted by Code.gs'); });
    sent.forEach(v => { check(schemaValues.includes(v), label + ': ' + name + ' value ' + JSON.stringify(v) + ' is not in form_schema.json'); });
  });
  check(hiddenValue(html, 'form_version') === api.FORM.formVersion, label + ': form_version differs from Code.gs');
  check(hiddenValue(html, 'form_version') === schema.hidden_fields.form_version.must_equal, label + ': form_version differs from schema');
  const privacy = hiddenValue(html, 'privacy_notice_version');
  check(Array.from(api.FORM.acceptedPrivacyVersions).includes(privacy), label + ': privacy_notice_version ' + privacy + ' is not accepted by Code.gs');
  check(schema.hidden_fields.privacy_notice_version.backend_accepts.includes(privacy), label + ': privacy_notice_version ' + privacy + ' is not in schema backend_accepts');
  check(hiddenValue(html, 'consent_text_version') === api.FORM.consentVersion, label + ': consent_text_version differs from Code.gs');
  check(hiddenValue(html, 'consent_text_version') === schema.hidden_fields.consent_text_version.must_equal, label + ': consent_text_version differs from schema');
  check(hiddenValue(html, 'source_page') === 'request-a-quote.html', label + ': source_page changed');
});
assert.deepStrictEqual(Array.from(api.FORM.acceptedPrivacyVersions), schema.hidden_fields.privacy_notice_version.backend_accepts, 'privacy allow-list differs between Code.gs and schema'); assertions += 1;
check(api.FORM.acceptedPrivacyVersions.includes(api.FORM.privacyVersion), 'current privacy version must be in its own allow-list');
check(api.FORM.acceptedPrivacyVersions.includes('2026-10-28-v1'), 'fixes/15 privacy version must stay accepted');
check(api.FORM.privacyVersion === schema.hidden_fields.privacy_notice_version.must_equal, 'current privacy version differs between Code.gs and schema');

console.log('PASS: ' + assertions + ' region-contract and drift-guard assertions; live form, template, schema and Code.gs agree on regions, industries, seniority and form/privacy/consent versions; IE/UK/EU and legacy values accepted; bad values rejected');
