'use strict';
const assert = require('assert');
const fs = require('fs');
const path = require('path');
const vm = require('vm');

const ROOT = path.resolve(__dirname, '..');
const code = fs.readFileSync(path.join(ROOT, 'apps-script', 'Code.gs'), 'utf8');
const fixture = JSON.parse(fs.readFileSync(path.join(__dirname, 'valid_submission.json'), 'utf8'));
const schema = JSON.parse(fs.readFileSync(path.join(ROOT, 'form_schema.json'), 'utf8'));
const context = {console};
vm.createContext(context);
vm.runInContext(code, context, {filename: 'Code.gs'});
const api = context.__DEMANDRANGE_TEST__;
assert(api, 'Test export missing');

function fresh() {
  const payload = JSON.parse(JSON.stringify(fixture));
  payload.form_load_ms = String(Date.now() - 3000);
  return payload;
}
function event(payload) {
  const parameters = {};
  Object.entries(payload).forEach(([key, value]) => { parameters[key] = Array.isArray(value) ? value : [String(value)]; });
  return {parameters};
}
function accept(payload) { return api.parseAndValidate_(event(payload), Date.now()); }
function reject(label, mutate) {
  const payload = fresh(); mutate(payload);
  assert.throws(() => accept(payload), undefined, label);
}

const valid = accept(fresh());
assert.equal(valid.companyName, 'Example Process Systems Ltd');
assert.deepEqual(Array.from(valid.industries), ['Process manufacturing', 'Utilities & energy']);
assert.deepEqual(Array.from(valid.seniority), ['Manager', 'Director']);
assert.equal(valid.phoneContact, true);

reject('missing name', p => { p.full_name = ''; });
reject('oversize name', p => { p.full_name = 'X'.repeat(101); });
reject('malformed email', p => { p.work_email = 'not-an-email'; });
reject('unsafe URL', p => { p.company_website = 'javascript:alert(1)'; });
reject('unknown industry', p => { p.industries = ['Unknown']; });
reject('missing region', p => { p.regions = []; });
reject('unknown seniority', p => { p.seniority = ['Owner']; });
reject('phone permission without phone', p => { p.phone_number = ''; });
reject('phone without permission', p => { p.phone_contact = ''; });
reject('missing email acknowledgement', p => { p.email_acknowledgement = ''; });
reject('unknown field', p => { p.admin = 'true'; });
reject('wrong version', p => { p.form_version = 'old'; });
reject('too fast', p => { p.form_load_ms = String(Date.now() - 100); });
reject('stale form', p => { p.form_load_ms = String(Date.now() - (5 * 60 * 60 * 1000)); });
reject('invalid attribution', p => { p.asset_ref = '<script>'; });

const unordered = fresh();
unordered.industries = ['Utilities & energy', 'Automotive', 'Utilities & energy'];
assert.deepEqual(Array.from(accept(unordered).industries), ['Automotive', 'Utilities & energy']);
assert.equal(api.sheetSafe_('=HYPERLINK("https://example.com")').startsWith("'="), true);
assert.equal(api.sheetSafe_('+353 1 555 0100').startsWith("'+"), true);
assert.equal(api.sheetSafe_('<script>alert(1)</script>'), '<script>alert(1)</script>');

assert.equal(schema.fields.industries.values.length, 10);
assert.equal(schema.fields.regions.values.length, 5);
assert.equal(schema.fields.seniority.values.length, 5);
assert.deepEqual(Array.from(api.FORM.columns), schema.raw_response_columns);
assert.equal(api.FORM.serviceModel, 'hybrid_10_90_target');
console.log('PASS: 21 backend/schema assertions; validation, enum allowlists, consent boundaries and formula neutralisation passed');
