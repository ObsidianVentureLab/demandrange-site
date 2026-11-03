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

console.log('PASS: ' + assertions + ' region-contract assertions; live form, template, schema and Code.gs agree; IE/UK/EU and legacy values accepted; bad values rejected');
