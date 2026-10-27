'use strict';
// LOCAL MOCK TESTS ONLY. Executes actual Code.gs + OwnerQA.gs against fake Google services.
const assert = require('assert');
const fs = require('fs');
const path = require('path');
const vm = require('vm');
const crypto = require('crypto');
const root = path.resolve(__dirname, '..');
const backend = fs.readFileSync(path.join(root, 'apps-script/Code.gs'), 'utf8');
const helper = fs.readFileSync(path.join(root, 'owner-qa/OwnerQA.gs'), 'utf8');
const owner = 'owner@fixture.example';
const fixtureId = 'LocalMockSpreadsheetIdOnly123';

function environment(options = {}) {
  const properties = {MODE: 'test', PAUSED: 'true', SPREADSHEET_ID: fixtureId, OWNER_QA_EMAIL: owner, ...options.properties};
  const logs = [];
  const writes = [];
  let networkCalls = 0;
  let book;
  const protectionFor = (name, description) => ({
    getDescription: () => description,
    isWarningOnly: () => Boolean(options.warningProtection),
    canDomainEdit: () => Boolean(options.domainEdit),
    getUnprotectedRanges: () => options.openRange ? [{}] : [],
    getEditors: () => (options.extraEditor ? [owner, 'other@fixture.example'] : [owner])
      .map(email => ({getEmail: () => email}))
  });
  class Sheet {
    constructor(name, columns, description) {
      this.name = name;
      this.rows = [Array.from(columns)];
      this.protections = description && !options.noProtection ? [protectionFor(name, description)] : [];
    }
    getName() { return this.name; }
    getLastRow() { return this.rows.length; }
    getProtections() { return this.protections; }
    appendRow(values) {
      if (options.storageFailure) throw new Error('MOCK_STORAGE_UNAVAILABLE');
      writes.push({sheet: this.name, method: 'appendRow'});
      const row = Array.from(values);
      if (options.corruptReadback) row[this.rows[0].indexOf('target_regions')] = 'CORRUPTED';
      this.rows.push(row);
    }
    getRange(startRow, startColumn, rowCount = 1, columnCount = 1) {
      const sheet = this;
      return {
        getDisplayValues() {
          return Array.from({length: rowCount}, (_, r) =>
            Array.from({length: columnCount}, (_, c) =>
              String(sheet.rows[startRow + r - 1]?.[startColumn + c - 1] ?? '')));
        },
        getValue() { return sheet.rows[startRow - 1]?.[startColumn - 1] ?? ''; },
        setValues(values) {
          writes.push({sheet: sheet.name, method: 'setValues'});
          values.forEach((row, r) => row.forEach((value, c) => {
            if (!sheet.rows[startRow + r - 1]) sheet.rows[startRow + r - 1] = [];
            sheet.rows[startRow + r - 1][startColumn + c - 1] = value;
          }));
        },
        createTextFinder(text) {
          return {
            matchEntireCell() { return this; },
            findNext() {
              for (let row = startRow; row < startRow + rowCount; row++) {
                if (String(sheet.rows[row - 1]?.[startColumn - 1] ?? '') === text) {
                  return {getRow: () => row};
                }
              }
              return null;
            }
          };
        }
      };
    }
  }
  const context = {
    console: {log: text => logs.push(String(text)), warn() {}, error() {}},
    PropertiesService: {getScriptProperties: () => ({getProperty: key => properties[key] ?? null})},
    Session: {getEffectiveUser: () => ({getEmail: () => options.owner || owner})},
    SpreadsheetApp: {
      ProtectionType: {SHEET: 'SHEET'},
      openById: id => { assert.equal(id, fixtureId); return book; },
      flush() {}
    },
    LockService: {getScriptLock: () => ({waitLock() {}, releaseLock() {}})},
    Utilities: {
      DigestAlgorithm: {SHA_256: 'sha256'}, Charset: {UTF_8: 'utf8'},
      computeDigest: (algorithm, value) => Array.from(crypto.createHash('sha256').update(value).digest()),
      getUuid: () => crypto.randomUUID()
    },
    UrlFetchApp: {fetch() { networkCalls++; throw new Error('NETWORK_NOT_ALLOWED_IN_OWNER_TEST'); }}
  };
  vm.createContext(context);
  vm.runInContext(backend, context, {filename: 'Code.gs'});
  vm.runInContext(helper, context, {filename: 'OwnerQA.gs'});
  const columns = context.__DEMANDRANGE_TEST__.FORM.columns;
  const sheets = {
    'Raw Responses': new Sheet('Raw Responses', columns, 'Raw Responses is restricted intake data'),
    'Synthetic QA': new Sheet('Synthetic QA', columns, 'Synthetic QA is restricted intake data'),
    'Working Queue': new Sheet('Working Queue', ['submission_id']),
    'Taxonomies': new Sheet('Taxonomies', ['Industries'], 'Controlled taxonomies'),
    'Config': new Sheet('Config', ['key', 'value'], 'Non-secret release configuration')
  };
  if (options.badHeaders) sheets['Synthetic QA'].rows[0][0] = 'renamed_header';
  if (options.missingTab) delete sheets.Config;
  book = {getSheetByName: name => sheets[name] || null};
  return {context, sheets, writes, logs, properties, run: () => context.runOwnerStorageTest(),
    networkCalls: () => networkCalls};
}

const cases = [];
function test(name, fn) { fn(); cases.push({name, passed: true}); }

test('fictional row readback, duplicate suppression and idempotent rerun', () => {
  const env = environment();
  const originalProperties = {...env.properties};
  const first = env.run();
  assert.equal(first.result, 'PASS_EDITOR_STORAGE_ONLY');
  assert.equal(first.new_test_row_added, true);
  assert.equal(first.notification, 'NOT_ATTEMPTED');
  assert.equal(env.sheets['Synthetic QA'].getLastRow(), 2);
  const second = env.run();
  assert.equal(second.request_id, first.request_id);
  assert.equal(second.new_test_row_added, false);
  assert.equal(env.sheets['Synthetic QA'].getLastRow(), 2);
  assert.equal(env.sheets['Raw Responses'].getLastRow(), 1);
  assert(env.writes.every(write => write.sheet === 'Synthetic QA'));
  assert.equal(env.networkCalls(), 0);
  assert.deepStrictEqual(env.properties, originalProperties);
  assert.equal(env.logs.length, 2);
});

const blocked = [
  ['production mode', {properties: {MODE: 'production'}}, /MODE must be exactly test/],
  ['unpaused collection', {properties: {PAUSED: 'false'}}, /PAUSED must be exactly true/],
  ['missing pause value', {properties: {PAUSED: null}}, /PAUSED must be exactly true/],
  ['full URL instead of ID', {properties: {SPREADSHEET_ID: 'https://docs.google.com/spreadsheets/d/example/edit'}}, /bare ID/],
  ['wrong executing account', {owner: 'other@fixture.example'}, /configured owner account/],
  ['missing owner configuration', {properties: {OWNER_QA_EMAIL: null}}, /OWNER_QA_EMAIL script property/],
  ['changed headers', {badHeaders: true}, /headers_do_not_match_schema/],
  ['missing required tab', {missingTab: true}, /Missing setup tab/],
  ['missing protection', {noProtection: true}, /Expected protection missing/],
  ['warning-only protection', {warningProtection: true}, /Protection needs review/],
  ['domain-wide edit protection', {domainEdit: true}, /Protection needs review/],
  ['unprotected range', {openRange: true}, /Protection needs review/],
  ['additional protected-tab editor', {extraEditor: true}, /Unexpected protected-tab editor/]
];
for (const [name, options, pattern] of blocked) {
  test('blocks before writing: ' + name, () => {
    const env = environment(options);
    assert.throws(env.run, pattern);
    assert.equal(env.writes.length, 0);
    assert.equal(env.logs.length, 0);
    assert.equal(env.networkCalls(), 0);
  });
}

test('storage error does not report PASS or attempt an alert', () => {
  const env = environment({storageFailure: true});
  assert.throws(env.run, /MOCK_STORAGE_UNAVAILABLE/);
  assert.equal(env.logs.length, 0);
  assert.equal(env.networkCalls(), 0);
  assert.equal(env.sheets['Raw Responses'].getLastRow(), 1);
});

test('corrupted saved scope fails readback without reporting PASS', () => {
  const env = environment({corruptReadback: true});
  assert.throws(env.run, /Stored scope fields mismatch/);
  assert.equal(env.logs.length, 0);
  assert.equal(env.networkCalls(), 0);
  assert(env.writes.every(write => write.sheet === 'Synthetic QA'));
});

const report = {status: 'LOCAL_MOCK_TESTS_PASSED', live_google_tested: false,
  passed: cases.length, cases};
fs.writeFileSync(path.join(root, 'owner-qa/local-test-results.json'), JSON.stringify(report, null, 2) + '\n');
console.log(JSON.stringify(report));
