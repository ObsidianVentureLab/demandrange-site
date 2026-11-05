'use strict';
// Offline only: execute the real doPost with in-memory Apps Script services.
const assert = require('assert/strict');
const crypto = require('crypto');
const fs = require('fs');
const path = require('path');
const vm = require('vm');

const root = path.resolve(__dirname, '..');
const source = fs.readFileSync(path.join(root, 'apps-script/Code.gs'), 'utf8');
const fixture = JSON.parse(fs.readFileSync(path.join(__dirname, 'valid_submission.json'), 'utf8'));
const webhook = 'https://notifications.example.invalid/quote';
const signingKey = 'fictional-local-test-key';

function environment(options = {}) {
  const properties = {
    PAUSED: 'false', MODE: 'test', SPREADSHEET_ID: 'OfflineMockSpreadsheet',
    NOTIFICATION_WEBHOOK_URL: webhook, NOTIFICATION_WEBHOOK_SECRET: signingKey,
    ...options.properties
  };
  const reads = [], writes = [], outbound = [], sleeps = [], logs = [];
  let opens = 0, signatures = 0, sheets;
  const context = {
    console: {
      warn: message => logs.push(String(message)),
      error: message => logs.push(String(message))
    },
    PropertiesService: {getScriptProperties: () => ({getProperty(key) {
      reads.push(key);
      return properties[key] ?? null;
    }})},
    SpreadsheetApp: {
      openById(id) {
        assert.equal(id, properties.SPREADSHEET_ID);
        opens++;
        return {getSheetByName: name => sheets[name] || null};
      },
      flush() {}
    },
    LockService: {getScriptLock: () => ({waitLock() {}, releaseLock() {}})},
    Utilities: {
      DigestAlgorithm: {SHA_256: 'sha256'}, Charset: {UTF_8: 'utf8'},
      computeDigest: (_algorithm, value) => Array.from(crypto.createHash('sha256').update(value).digest()),
      computeHmacSha256Signature(value, key) {
        signatures++;
        return Array.from(crypto.createHmac('sha256', key).update(value).digest());
      },
      getUuid: () => '00000000-0000-4000-8000-000000000001',
      sleep: ms => sleeps.push(ms)
    },
    UrlFetchApp: {
      fetch(url, config) {
        outbound.push({service: 'UrlFetchApp', url, config});
        const response = (options.responses || [204])[outbound.length - 1];
        if (response instanceof Error) throw response;
        assert.equal(typeof response, 'number', 'Unexpected extra outbound attempt');
        return {getResponseCode: () => response};
      },
      fetchAll(requests) { outbound.push({service: 'UrlFetchApp.fetchAll', requests}); return []; }
    },
    MailApp: {sendEmail: (...args) => outbound.push({service: 'MailApp', args})},
    GmailApp: {sendEmail: (...args) => outbound.push({service: 'GmailApp', args})},
    HtmlService: {createHtmlOutput: html => ({html, setTitle() { return this; }})}
  };
  vm.createContext(context);
  vm.runInContext(source, context, {filename: 'Code.gs'});
  const columns = Array.from(context.__DEMANDRANGE_TEST__.FORM.columns);
  class Sheet {
    constructor(name) { this.name = name; this.rows = [columns.slice()]; }
    getLastRow() { return this.rows.length; }
    appendRow(values) {
      if (options.storageFailure) throw new Error('MOCK_STORAGE_UNAVAILABLE');
      writes.push({sheet: this.name, method: 'appendRow', values: Array.from(values)});
      this.rows.push(Array.from(values));
      if (options.modeAfterAppend !== undefined) properties.MODE = options.modeAfterAppend;
    }
    getRange(startRow, startColumn, rowCount = 1, columnCount = 1) {
      const sheet = this;
      return {
        getDisplayValues: () => Array.from({length: rowCount}, (_, r) =>
          Array.from({length: columnCount}, (_, c) => String(sheet.rows[startRow + r - 1][startColumn + c - 1]))),
        getValue: () => sheet.rows[startRow - 1][startColumn - 1],
        setValues(values) {
          if (options.stateUpdateFailure) throw new Error('MOCK_STATE_UPDATE_UNAVAILABLE');
          writes.push({sheet: sheet.name, method: 'setValues'});
          values.forEach((row, r) => row.forEach((value, c) => {
            sheet.rows[startRow + r - 1][startColumn + c - 1] = value;
          }));
        },
        createTextFinder(text) {
          return {
            matchEntireCell(value) { assert.equal(value, true); return this; },
            findNext() {
              for (let row = startRow; row < startRow + rowCount; row++) {
                if (sheet.rows[row - 1][startColumn - 1] === text) return {getRow: () => row};
              }
              return null;
            }
          };
        }
      };
    }
  }
  sheets = {'Raw Responses': new Sheet('Raw Responses'), 'Synthetic QA': new Sheet('Synthetic QA')};
  function rowObject(values) { return Object.fromEntries(columns.map((column, i) => [column, values[i]])); }
  return {
    properties, reads, writes, outbound, sleeps, logs, sheets,
    opens: () => opens, signatures: () => signatures,
    row: name => rowObject(sheets[name].rows[1]),
    appended: () => rowObject(writes.find(write => write.method === 'appendRow').values),
    post(overrides = {}) {
      const payload = {...fixture, form_load_ms: String(Date.now() - 3000), ...overrides};
      const parameters = Object.fromEntries(Object.entries(payload).map(([key, value]) =>
        [key, Array.isArray(value) ? value.slice() : [String(value)]]));
      return context.doPost({parameters}).html;
    }
  };
}

let passed = 0;
function test(name, run) {
  try { run(); passed++; } catch (error) { error.message = name + ': ' + error.message; throw error; }
}
function notification(row, state, attempts, error = '') {
  assert.equal(row.notification_state, state);
  assert.equal(row.notification_attempts, attempts);
  assert.equal(row.notification_last_error, error);
}
function noOutbound(env) {
  assert.deepEqual(env.outbound, []);
  assert.deepEqual(env.sleeps, []);
  assert.equal(env.signatures(), 0);
}
function testWrite(env) {
  assert.match(env.post(), /<h1>Request received<\/h1>/);
  assert.equal(env.sheets['Synthetic QA'].getLastRow(), 2);
  assert.equal(env.sheets['Raw Responses'].getLastRow(), 1);
  assert(env.writes.every(write => write.sheet === 'Synthetic QA'));
  noOutbound(env);
  assert(!env.reads.some(key => key.startsWith('NOTIFICATION_WEBHOOK_')));
  notification(env.appended(), 'suppressed_test_mode', 0);
  notification(env.row('Synthetic QA'), 'suppressed_test_mode', 0);
  assert.equal(env.row('Synthetic QA').company_name, fixture.company_name);
  assert.equal(env.row('Synthetic QA').target_regions, 'IE|UK');
}

for (const mode of ['test', null, '', 'staging', 'PRODUCTION', ' production ']) {
  test('non-production mode suppresses configured webhook: ' + JSON.stringify(mode), () => {
    testWrite(environment({properties: {MODE: mode}}));
  });
}
for (const config of [
  {NOTIFICATION_WEBHOOK_URL: null, NOTIFICATION_WEBHOOK_SECRET: null},
  {NOTIFICATION_WEBHOOK_URL: 'http://notifications.example.invalid/quote'}
]) {
  test('test suppression precedes webhook configuration validation: ' + JSON.stringify(config), () => {
    testWrite(environment({properties: config}));
  });
}
test('suppression is already saved if notification state update fails', () => {
  const env = environment({stateUpdateFailure: true});
  testWrite(env);
  assert(env.logs.some(log => log.includes('notification_state_update_failed:')));
});
test('test receipt stays suppressed if MODE changes to production after append', () => {
  testWrite(environment({modeAfterAppend: 'production'}));
});
test('production receipt is suppressed if MODE changes to test before notification', () => {
  const env = environment({properties: {MODE: 'production'}, modeAfterAppend: 'test'});
  assert.match(env.post(), /<h1>Request received<\/h1>/);
  notification(env.row('Raw Responses'), 'suppressed_test_mode', 0);
  noOutbound(env);
});

for (const mode of ['test', 'production']) {
  for (const paused of ['true', 'TRUE', null, '', 'unexpected']) {
    test('paused doPost has no writes or sends: ' + mode + '/' + JSON.stringify(paused), () => {
      const env = environment({properties: {MODE: mode, PAUSED: paused}});
      assert.match(env.post(), /<h1>Requests temporarily paused<\/h1>/);
      assert.equal(env.opens(), 0);
      assert.deepEqual(env.writes, []);
      assert.equal(env.sheets['Synthetic QA'].getLastRow(), 1);
      assert.equal(env.sheets['Raw Responses'].getLastRow(), 1);
      noOutbound(env);
    });
  }
  test('duplicate doPost preserves row and notification state: ' + mode, () => {
    const env = environment({properties: {MODE: mode}});
    const sheet = mode === 'production' ? 'Raw Responses' : 'Synthetic QA';
    env.post();
    const original = {...env.row(sheet)};
    const writes = env.writes.length, outbound = env.outbound.length;
    assert.match(env.post(), /<h1>Request already received<\/h1>/);
    assert.deepEqual(env.row(sheet), original);
    assert.equal(env.sheets[sheet].getLastRow(), 2);
    assert.equal(env.writes.length, writes);
    assert.equal(env.outbound.length, outbound);
  });
  test('storage failure never sends: ' + mode, () => {
    const env = environment({properties: {MODE: mode}, storageFailure: true});
    assert.match(env.post(), /<h1>We could not save that request<\/h1>/);
    assert.deepEqual(env.writes, []);
    noOutbound(env);
  });
}

test('production retains raw intake, sanitized signed webhook and delivered state', () => {
  const env = environment({properties: {MODE: 'production'}});
  assert.match(env.post(), /<h1>Request received<\/h1>/);
  assert.equal(env.sheets['Raw Responses'].getLastRow(), 2);
  assert.equal(env.sheets['Synthetic QA'].getLastRow(), 1);
  assert(env.writes.every(write => write.sheet === 'Raw Responses'));
  notification(env.appended(), 'pending', 0);
  notification(env.row('Raw Responses'), 'delivered', 1);
  assert.equal(env.outbound.length, 1);
  assert.equal(env.signatures(), 1);
  assert.deepEqual(env.sleeps, []);
  const {service, url, config} = env.outbound[0];
  assert.equal(service, 'UrlFetchApp');
  assert.equal(url, webhook);
  assert.equal(config.method, 'post');
  assert.equal(config.contentType, 'application/json');
  assert.equal(config.muteHttpExceptions, true);
  assert.equal(config.followRedirects, false);
  const body = JSON.parse(config.payload), id = env.row('Raw Responses').submission_id;
  assert(Number.isFinite(Date.parse(body.received_at_utc)));
  assert.deepEqual(body, {
    event_type: 'demandrange.quote_request.received', event_id: id,
    received_at_utc: body.received_at_utc, submission_id: id,
    company_name: fixture.company_name, industries: fixture.industries,
    target_regions: fixture.regions, assigned_owner: 'unassigned'
  });
  assert.deepEqual({...config.headers}, {
    'X-DR-Event-Id': id,
    'X-DR-Signature': 'sha256=' + crypto.createHmac('sha256', signingKey).update(config.payload).digest('hex')
  });
});

for (const config of [
  {NOTIFICATION_WEBHOOK_URL: null},
  {NOTIFICATION_WEBHOOK_SECRET: null}
]) {
  test('production retains pending configuration: ' + Object.keys(config)[0], () => {
    const env = environment({properties: {MODE: 'production', ...config}});
    assert.match(env.post(), /<h1>Request received<\/h1>/);
    notification(env.row('Raw Responses'), 'pending_configuration', 0, 'Miranda notification webhook is not configured');
    noOutbound(env);
  });
}
test('production retains HTTPS requirement', () => {
  const env = environment({properties: {MODE: 'production', NOTIFICATION_WEBHOOK_URL: 'http://notifications.example.invalid/quote'}});
  env.post();
  notification(env.row('Raw Responses'), 'failed', 0, 'Notification URL must use HTTPS');
  noOutbound(env);
});
for (const [name, responses, state, error, sleeps] of [
  ['retry then success', [429, 503, 201], 'delivered', '', [500, 1000]],
  ['non-retryable response', [400], 'failed', 'Webhook HTTP 400', []],
  ['exhausted HTTP retries', [503, 503, 503], 'failed', 'Webhook retries exhausted', [500, 1000, 1500]],
  ['exhausted fetch errors', [new Error('MOCK_FETCH_FAILED'), new Error('MOCK_FETCH_FAILED'), new Error('MOCK_FETCH_FAILED')], 'failed', 'MOCK_FETCH_FAILED', [500, 1000]]
]) {
  test('production preserves ' + name, () => {
    const env = environment({properties: {MODE: 'production'}, responses});
    assert.match(env.post(), /<h1>Request received<\/h1>/);
    notification(env.row('Raw Responses'), state, responses.length, error);
    assert.equal(env.outbound.length, responses.length);
    assert.deepEqual(env.sleeps, sleeps);
  });
}

console.log('PASS: ' + passed + ' offline mocked doPost scenarios; test suppression, pause, deduplication and production notifications');
