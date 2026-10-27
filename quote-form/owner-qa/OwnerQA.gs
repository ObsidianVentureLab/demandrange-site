'use strict';

/**
 * Owner-only EDITOR storage check, v1. Not deployed HTTP/form/notification QA.
 * Add as a separate OwnerQA.gs file beside the unchanged Code.gs.
 * Run runOwnerStorageTest from the editor, not setupSpreadsheet.
 * Requires MODE=test and PAUSED=true. Never changes those properties.
 * Writes/reuses one fictional row in Synthetic QA; never sends an alert.
 * Do not redeploy this test helper with the public production application.
 */
function runOwnerStorageTest() {
  const properties = PropertiesService.getScriptProperties();
  ownerQARequire_(properties.getProperty('MODE') === 'test', 'MODE must be exactly test');
  ownerQARequire_(properties.getProperty('PAUSED') === 'true', 'PAUSED must be exactly true');
  const spreadsheetId = properties.getProperty('SPREADSHEET_ID') || '';
  ownerQARequire_(/^[A-Za-z0-9_-]+$/.test(spreadsheetId), 'SPREADSHEET_ID must be a bare ID');
  const ownerEmail = String(Session.getEffectiveUser().getEmail()).toLowerCase();
  ownerQARequire_(ownerEmail === 'sean@demandrange.com', 'Run from the intended Sean account');
  ownerQARequire_(FORM.formVersion === '2026-09-11-v1', 'Unexpected form version; stop for review');

  const book = SpreadsheetApp.openById(spreadsheetId);
  const tabs = {};
  ['Raw Responses', 'Synthetic QA', 'Working Queue', 'Taxonomies', 'Config'].forEach(function (name) {
    tabs[name] = book.getSheetByName(name);
    ownerQARequire_(Boolean(tabs[name]), 'Missing setup tab: ' + name);
  });
  const raw = tabs['Raw Responses'];
  const qa = tabs['Synthetic QA'];
  assertHeaders_(raw);
  assertHeaders_(qa);
  ownerQAProtection_(raw, 'Raw Responses is restricted intake data', ownerEmail);
  ownerQAProtection_(qa, 'Synthetic QA is restricted intake data', ownerEmail);
  ownerQAProtection_(tabs.Taxonomies, 'Controlled taxonomies', ownerEmail);
  ownerQAProtection_(tabs.Config, 'Non-secret release configuration', ownerEmail);
  const rawRowsBefore = raw.getLastRow();
  const qaRowsBefore = qa.getLastRow();

  const payload = {
    form_version: FORM.formVersion,
    privacy_notice_version: FORM.privacyVersion,
    consent_text_version: FORM.consentVersion,
    source_page: 'request-a-quote.html',
    submission_token: 'DRQ_OWNER_STORAGE_QA_20260911_V1',
    form_load_ms: String(Date.now() - 3000),
    website_confirm: '',
    asset_ref: 'owner-storage-qa',
    campaign_ref: '',
    full_name: 'Synthetic QA Contact',
    work_email: 'quote-test@demandrange-qa.example',
    company_name: 'Synthetic QA Company - NOT A LEAD',
    company_website: '',
    phone_number: '',
    product_or_service: 'Fictional pump enquiry for setup testing only',
    industries: ['Utilities & energy'],
    regions: ['EMEA'],
    specific_countries: '',
    seniority: ['Manager'],
    additional_context: 'Fictional setup test. Do not contact or quote. No notification attempted.',
    email_acknowledgement: 'true',
    phone_contact: ''
  };
  const parameters = {};
  Object.keys(payload).forEach(function (key) {
    parameters[key] = Array.isArray(payload[key]) ? payload[key] : [payload[key]];
  });
  const invalid = JSON.parse(JSON.stringify(parameters));
  invalid.work_email = [''];
  let rejected = false;
  try { parseAndValidate_({parameters: invalid}, Date.now()); } catch (error) { rejected = true; }
  ownerQARequire_(rejected, 'Missing email unexpectedly passed validation');
  const request = parseAndValidate_({parameters: parameters}, Date.now());

  // Fixed test-only routing prevents a concurrent property change routing this
  // fixture to production. One month is a TEST-row review marker, not a policy.
  const testValues = {SPREADSHEET_ID: spreadsheetId, MODE: 'test', RETENTION_MONTHS: '1'};
  const testProperties = {getProperty: function (key) {
    return Object.prototype.hasOwnProperty.call(testValues, key) ? testValues[key] : null;
  }};
  ownerQARequire_(properties.getProperty('MODE') === 'test' && properties.getProperty('PAUSED') === 'true',
    'Test settings changed; stop');
  const receipt = persist_(request, testProperties);
  ownerQARequire_(receipt.sheet.getName() === 'Synthetic QA', 'Unexpected receipt destination');
  let row = ownerQARow_(qa, receipt.row);
  ownerQARequire_(row.submission_id === receipt.submissionId &&
    row.submission_token_hash === sha256_(payload.submission_token), 'Stored identity mismatch');
  ownerQARequire_(row.full_name === payload.full_name && row.work_email === payload.work_email &&
    row.company_name === payload.company_name, 'Stored fictional fields mismatch');
  ownerQARequire_(row.industries === 'Utilities & energy' && row.target_regions === 'EMEA' &&
    row.job_seniority === 'Manager' && row.service_model === FORM.serviceModel,
    'Stored scope fields mismatch');
  ownerQARequire_(row.phone_number === '', 'Unexpected phone value in test row');

  // Mark this fixture so an operator will not treat it as a missed live alert.
  updateNotification_(receipt, {state: 'not_tested_owner_qa', attempts: 0,
    error: 'Fictional editor storage test; notification deliberately not attempted.'});
  SpreadsheetApp.flush();
  row = ownerQARow_(qa, receipt.row);
  ownerQARequire_(row.notification_state === 'not_tested_owner_qa' &&
    row.notification_attempts === '0', 'Test notification marker did not persist');

  const duplicate = persist_(request, testProperties);
  ownerQARequire_(duplicate.duplicate === true && duplicate.submissionId === receipt.submissionId,
    'Replay was not deduplicated');
  ownerQARequire_(qa.getLastRow() === qaRowsBefore + (receipt.duplicate ? 0 : 1),
    'Unexpected Synthetic QA row-count change');
  ownerQARequire_(raw.getLastRow() === rawRowsBefore, 'Raw Responses row count changed');
  ownerQARequire_(properties.getProperty('MODE') === 'test' && properties.getProperty('PAUSED') === 'true',
    'Test settings changed during execution; review before continuing');

  const summary = {
    result: 'PASS_EDITOR_STORAGE_ONLY',
    request_id: receipt.submissionId,
    test_row: receipt.row,
    new_test_row_added: !receipt.duplicate,
    duplicate_suppressed: true,
    missing_email_rejected: true,
    raw_row_count_unchanged: true,
    collection_remains_paused: true,
    notification: 'NOT_ATTEMPTED',
    not_tested: ['deployed HTTP POST', 'website form', 'alert delivery', 'outage recovery']
  };
  console.log(JSON.stringify(summary));
  return summary;
}

function ownerQARequire_(condition, message) {
  if (!condition) throw new Error('OWNER_QA_STOP: ' + message);
}
function ownerQARow_(sheet, rowNumber) {
  const values = sheet.getRange(rowNumber, 1, 1, FORM.columns.length).getDisplayValues()[0];
  const row = {};
  FORM.columns.forEach(function (key, index) { row[key] = values[index]; });
  return row;
}
function ownerQAProtection_(sheet, description, ownerEmail) {
  const found = sheet.getProtections(SpreadsheetApp.ProtectionType.SHEET).filter(function (item) {
    return item.getDescription() === description;
  });
  ownerQARequire_(found.length === 1, 'Expected protection missing or duplicated: ' + sheet.getName());
  const protection = found[0];
  ownerQARequire_(!protection.isWarningOnly() && !protection.canDomainEdit() &&
    protection.getUnprotectedRanges().length === 0, 'Protection needs review: ' + sheet.getName());
  ownerQARequire_(protection.getEditors().every(function (editor) {
    return String(editor.getEmail()).toLowerCase() === ownerEmail;
  }), 'Unexpected protected-tab editor: ' + sheet.getName());
}
