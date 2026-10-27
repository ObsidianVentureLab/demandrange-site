'use strict';
// Static permission regression; not a substitute for Google authorization QA.
const assert = require('assert');
const fs = require('fs');
const path = require('path');
const root = path.resolve(__dirname, '..');
const manifest = JSON.parse(fs.readFileSync(path.join(root, 'apps-script', 'appsscript.json'), 'utf8'));
const source = fs.readFileSync(path.join(root, 'apps-script', 'Code.gs'), 'utf8');
const expected = [
  'https://www.googleapis.com/auth/spreadsheets',
  'https://www.googleapis.com/auth/script.external_request',
  'https://www.googleapis.com/auth/userinfo.email'
];
assert.equal(manifest.timeZone, 'Europe/Dublin');
assert.equal(manifest.runtimeVersion, 'V8');
assert(Array.isArray(manifest.oauthScopes), 'Explicit OAuth scopes required');
if (source.includes('Session.getEffectiveUser(')) {
  assert(manifest.oauthScopes.includes(expected[2]),
    'Session.getEffectiveUser requires userinfo.email for owner protection setup');
}
assert.deepStrictEqual([...manifest.oauthScopes].sort(), [...expected].sort(),
  'Review both missing permissions and unexpected scope expansion');
console.log('PASS: manifest scope regression; live Google authorization remains unverified');
