'use strict';

const FORM = Object.freeze({
  formVersion: '2026-09-11-v1',
  privacyVersion: '2026-09-11-v1',
  consentVersion: '2026-09-11-v1',
  serviceModel: 'hybrid_10_90_target',
  minCompletionMs: 2500,
  maxFormAgeMs: 4 * 60 * 60 * 1000,
  industries: Object.freeze([
    'Automotive', 'General manufacturing', 'Electronics manufacturing',
    'Process manufacturing', 'Aerospace & defence', 'Machinery & equipment',
    'Construction', 'Waste management', 'Utilities & energy', 'Mining, oil & gas'
  ]),
  regions: Object.freeze(['EMEA', 'NAM', 'LATAM', 'APAC', 'ANZ']),
  seniority: Object.freeze(['Entry', 'Manager', 'Director', 'VP', 'C-Suite']),
  fields: Object.freeze([
    'form_version', 'privacy_notice_version', 'consent_text_version',
    'source_page', 'submission_token', 'form_load_ms', 'website_confirm',
    'asset_ref', 'campaign_ref', 'full_name', 'work_email', 'company_name',
    'company_website', 'phone_number', 'product_or_service', 'industries',
    'regions', 'specific_countries', 'seniority', 'additional_context',
    'email_acknowledgement', 'phone_contact'
  ]),
  columns: Object.freeze([
    'submission_id', 'submitted_at_utc', 'form_version', 'privacy_notice_version',
    'consent_text_version', 'service_model', 'source_page', 'asset_ref',
    'campaign_ref', 'submission_token_hash', 'full_name', 'work_email',
    'company_name', 'company_website', 'phone_number', 'product_or_service',
    'industries', 'target_regions', 'specific_countries', 'job_seniority',
    'email_response_requested', 'phone_contact_opt_in', 'additional_context',
    'intake_status', 'assigned_owner', 'first_response_at_utc', 'outcome',
    'retention_review_at', 'notification_state', 'notification_attempts',
    'notification_last_error'
  ])
});

function doGet() {
  return resultPage_('Quote requests', 'Please submit a request from demandrange.com/request-a-quote.html.', false);
}

function doPost(e) {
  const properties = PropertiesService.getScriptProperties();
  if (String(properties.getProperty('PAUSED')).toLowerCase() !== 'false') {
    return resultPage_('Requests temporarily paused', 'Please email partners@demandrange.com instead.', false);
  }

  let request;
  try {
    request = parseAndValidate_(e || {}, Date.now());
  } catch (error) {
    console.warn('quote_request_rejected:' + safeLog_(error && error.message));
    return resultPage_('We could not accept that request', 'Please review the form or email partners@demandrange.com.', false);
  }

  if (request.honeypot) {
    console.warn('quote_request_honeypot');
    return resultPage_('Request received', 'Thank you. If the scope appears relevant, the team will respond in writing.', true);
  }

  let receipt;
  try {
    receipt = persist_(request, properties);
  } catch (error) {
    console.error('quote_request_storage_failed:' + safeLog_(error && error.message));
    return resultPage_('We could not save that request', 'Nothing was accepted. Please email partners@demandrange.com.', false);
  }

  if (!receipt.duplicate) {
    const notification = notify_(receipt, request, properties);
    updateNotification_(receipt, notification);
  }

  return resultPage_(
    receipt.duplicate ? 'Request already received' : 'Request received',
    'Reference ' + receipt.submissionId + '. Demand Range will review the scope and respond in writing. No quote or coverage commitment is created by submission.',
    true
  );
}

function parseAndValidate_(event, nowMs) {
  const parameters = event.parameters || {};
  const keys = Object.keys(parameters);
  const unknown = keys.filter(function (key) { return FORM.fields.indexOf(key) === -1; });
  if (unknown.length) throw new Error('unknown_fields');

  function values(name) {
    const value = parameters[name];
    if (value === undefined || value === null) return [];
    return (Array.isArray(value) ? value : [value]).map(function (item) { return String(item); });
  }
  function one(name) {
    const found = values(name);
    if (found.length > 1) throw new Error('repeated_single:' + name);
    return found.length ? found[0] : '';
  }

  const honeypot = normalize_(one('website_confirm'), 200);
  const formVersion = one('form_version');
  const privacyVersion = one('privacy_notice_version');
  const consentVersion = one('consent_text_version');
  const sourcePage = one('source_page');
  if (formVersion !== FORM.formVersion || privacyVersion !== FORM.privacyVersion || consentVersion !== FORM.consentVersion) throw new Error('version_mismatch');
  if (sourcePage !== 'request-a-quote.html') throw new Error('source_page');

  const token = one('submission_token');
  if (!/^[A-Za-z0-9_-]{16,80}$/.test(token)) throw new Error('submission_token');
  const loaded = Number(one('form_load_ms'));
  if (!Number.isFinite(loaded) || Math.floor(loaded) !== loaded) throw new Error('form_load_ms');
  const elapsed = nowMs - loaded;
  if (elapsed < FORM.minCompletionMs || elapsed > FORM.maxFormAgeMs) throw new Error('completion_time');

  const fullName = requiredText_(one('full_name'), 'full_name', 2, 100);
  const workEmail = requiredText_(one('work_email'), 'work_email', 3, 254).toLowerCase();
  if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(workEmail)) throw new Error('work_email');
  const companyName = requiredText_(one('company_name'), 'company_name', 2, 150);
  const companyWebsite = optionalText_(one('company_website'), 'company_website', 300);
  if (companyWebsite && !/^https?:\/\/[^\s]+$/i.test(companyWebsite)) throw new Error('company_website');
  const phoneNumber = optionalText_(one('phone_number'), 'phone_number', 40);
  if (phoneNumber && !/^[+()\d\s.\/-]{7,40}$/.test(phoneNumber)) throw new Error('phone_number');
  const product = requiredText_(one('product_or_service'), 'product_or_service', 3, 500);
  const countries = optionalText_(one('specific_countries'), 'specific_countries', 300);
  const context = optionalText_(one('additional_context'), 'additional_context', 1000);
  const assetRef = boundedRef_(one('asset_ref'));
  const campaignRef = boundedRef_(one('campaign_ref'));
  const industries = enumValues_(values('industries'), FORM.industries, 'industries');
  const regions = enumValues_(values('regions'), FORM.regions, 'regions');
  const seniority = enumValues_(values('seniority'), FORM.seniority, 'seniority');
  if (!industries.length || !regions.length || !seniority.length) throw new Error('required_selection');
  const emailAcknowledgement = boolean_(one('email_acknowledgement'), 'email_acknowledgement');
  const phoneContact = optionalBoolean_(one('phone_contact'), 'phone_contact');
  if (!emailAcknowledgement) throw new Error('email_acknowledgement');
  if (phoneContact && !phoneNumber) throw new Error('phone_required');
  if (phoneNumber && !phoneContact) throw new Error('phone_permission_required');

  return {
    honeypot: Boolean(honeypot), token: token, formVersion: formVersion,
    privacyVersion: privacyVersion, consentVersion: consentVersion,
    sourcePage: sourcePage, assetRef: assetRef, campaignRef: campaignRef,
    fullName: fullName, workEmail: workEmail, companyName: companyName,
    companyWebsite: companyWebsite, phoneNumber: phoneNumber, product: product,
    industries: industries, regions: regions, seniority: seniority,
    countries: countries, context: context, emailAcknowledgement: true,
    phoneContact: phoneContact
  };
}

function persist_(request, properties) {
  const spreadsheetId = properties.getProperty('SPREADSHEET_ID');
  if (!spreadsheetId) throw new Error('spreadsheet_not_configured');
  const mode = properties.getProperty('MODE') === 'production' ? 'production' : 'test';
  const sheetName = mode === 'production' ? 'Raw Responses' : 'Synthetic QA';
  const spreadsheet = SpreadsheetApp.openById(spreadsheetId);
  const sheet = spreadsheet.getSheetByName(sheetName);
  if (!sheet) throw new Error('sheet_missing:' + sheetName);
  assertHeaders_(sheet);

  const lock = LockService.getScriptLock();
  lock.waitLock(10000);
  try {
    const tokenHash = sha256_(request.token);
    const tokenColumn = FORM.columns.indexOf('submission_token_hash') + 1;
    if (sheet.getLastRow() > 1) {
      const existing = sheet.getRange(2, tokenColumn, sheet.getLastRow() - 1, 1).createTextFinder(tokenHash).matchEntireCell(true).findNext();
      if (existing) {
        const idColumn = FORM.columns.indexOf('submission_id') + 1;
        return {duplicate: true, submissionId: String(sheet.getRange(existing.getRow(), idColumn).getValue()), sheet: sheet, row: existing.getRow()};
      }
    }

    const submittedAt = new Date();
    const retentionMonths = boundedInteger_(properties.getProperty('RETENTION_MONTHS') || '24', 1, 84);
    const retention = new Date(submittedAt.getTime());
    retention.setUTCMonth(retention.getUTCMonth() + retentionMonths);
    const submissionId = 'DRQ-' + Utilities.getUuid().replace(/-/g, '').slice(0, 12).toUpperCase();
    const rowObject = {
      submission_id: submissionId,
      submitted_at_utc: submittedAt.toISOString(),
      form_version: FORM.formVersion,
      privacy_notice_version: FORM.privacyVersion,
      consent_text_version: FORM.consentVersion,
      service_model: FORM.serviceModel,
      source_page: request.sourcePage,
      asset_ref: request.assetRef,
      campaign_ref: request.campaignRef,
      submission_token_hash: tokenHash,
      full_name: sheetSafe_(request.fullName),
      work_email: sheetSafe_(request.workEmail),
      company_name: sheetSafe_(request.companyName),
      company_website: sheetSafe_(request.companyWebsite),
      phone_number: sheetSafe_(request.phoneNumber),
      product_or_service: sheetSafe_(request.product),
      industries: request.industries.join('|'),
      target_regions: request.regions.join('|'),
      specific_countries: sheetSafe_(request.countries),
      job_seniority: request.seniority.join('|'),
      email_response_requested: true,
      phone_contact_opt_in: request.phoneContact,
      additional_context: sheetSafe_(request.context),
      intake_status: 'new', assigned_owner: '', first_response_at_utc: '', outcome: '',
      retention_review_at: retention.toISOString(),
      notification_state: 'pending', notification_attempts: 0, notification_last_error: ''
    };
    sheet.appendRow(FORM.columns.map(function (column) { return rowObject[column]; }));
    SpreadsheetApp.flush();
    return {duplicate: false, submissionId: submissionId, sheet: sheet, row: sheet.getLastRow()};
  } finally {
    lock.releaseLock();
  }
}

function notify_(receipt, request, properties) {
  const url = properties.getProperty('NOTIFICATION_WEBHOOK_URL') || '';
  const secret = properties.getProperty('NOTIFICATION_WEBHOOK_SECRET') || '';
  if (!url || !secret) return {state: 'pending_configuration', attempts: 0, error: 'Miranda notification webhook is not configured'};
  if (!/^https:\/\//i.test(url)) return {state: 'failed', attempts: 0, error: 'Notification URL must use HTTPS'};
  const event = {
    event_type: 'demandrange.quote_request.received',
    event_id: receipt.submissionId,
    received_at_utc: new Date().toISOString(),
    submission_id: receipt.submissionId,
    company_name: request.companyName,
    industries: request.industries,
    target_regions: request.regions,
    assigned_owner: 'unassigned'
  };
  const body = JSON.stringify(event);
  const signature = bytesToHex_(Utilities.computeHmacSha256Signature(body, secret, Utilities.Charset.UTF_8));
  for (let attempt = 1; attempt <= 3; attempt++) {
    try {
      const response = UrlFetchApp.fetch(url, {
        method: 'post', contentType: 'application/json', payload: body,
        headers: {'X-DR-Event-Id': receipt.submissionId, 'X-DR-Signature': 'sha256=' + signature},
        muteHttpExceptions: true, followRedirects: false
      });
      const code = response.getResponseCode();
      if (code >= 200 && code < 300) return {state: 'delivered', attempts: attempt, error: ''};
      if (code < 500 && code !== 429) return {state: 'failed', attempts: attempt, error: 'Webhook HTTP ' + code};
    } catch (error) {
      if (attempt === 3) return {state: 'failed', attempts: attempt, error: safeLog_(error && error.message)};
    }
    Utilities.sleep(attempt * 500);
  }
  return {state: 'failed', attempts: 3, error: 'Webhook retries exhausted'};
}

function updateNotification_(receipt, notification) {
  try {
    const stateColumn = FORM.columns.indexOf('notification_state') + 1;
    receipt.sheet.getRange(receipt.row, stateColumn, 1, 3).setValues([[
      notification.state,
      notification.attempts,
      String(notification.error || '').slice(0, 240)
    ]]);
  } catch (error) {
    console.error('notification_state_update_failed:' + safeLog_(error && error.message));
  }
}

function setupSpreadsheet() {
  const properties = PropertiesService.getScriptProperties();
  const spreadsheetId = properties.getProperty('SPREADSHEET_ID');
  if (!spreadsheetId) throw new Error('Set SPREADSHEET_ID in Script Properties first.');
  const spreadsheet = SpreadsheetApp.openById(spreadsheetId);
  ['Raw Responses', 'Synthetic QA'].forEach(function (name) {
    const sheet = spreadsheet.getSheetByName(name) || spreadsheet.insertSheet(name);
    if (sheet.getLastRow() === 0) sheet.appendRow(FORM.columns);
    assertHeaders_(sheet);
    protectOwnerOnly_(sheet, name + ' is restricted intake data');
  });
  const queue = spreadsheet.getSheetByName('Working Queue') || spreadsheet.insertSheet('Working Queue');
  if (queue.getLastRow() === 0) queue.appendRow(['submission_id', 'submitted_at_utc', 'company_name', 'intake_status', 'assigned_owner', 'first_response_at_utc', 'outcome']);
  const taxonomies = spreadsheet.getSheetByName('Taxonomies') || spreadsheet.insertSheet('Taxonomies');
  taxonomies.clearContents();
  taxonomies.getRange(1, 1, 1, 4).setValues([['Industries', 'Regions', 'Seniority', 'Statuses']]);
  const max = Math.max(FORM.industries.length, FORM.regions.length, FORM.seniority.length, 8);
  const rows = [];
  const statuses = ['new', 'triage_in_progress', 'needs_information', 'quote_preparation', 'quote_sent', 'not_a_fit', 'withdrawn', 'closed'];
  for (let i = 0; i < max; i++) rows.push([FORM.industries[i] || '', FORM.regions[i] || '', FORM.seniority[i] || '', statuses[i] || '']);
  taxonomies.getRange(2, 1, rows.length, 4).setValues(rows);
  protectOwnerOnly_(taxonomies, 'Controlled taxonomies');
  const config = spreadsheet.getSheetByName('Config') || spreadsheet.insertSheet('Config');
  config.clearContents();
  config.getRange(1, 1, 6, 2).setValues([
    ['key', 'value'], ['form_version', FORM.formVersion], ['privacy_notice_version', FORM.privacyVersion],
    ['consent_text_version', FORM.consentVersion], ['service_model', FORM.serviceModel], ['setup_at_utc', new Date().toISOString()]
  ]);
  protectOwnerOnly_(config, 'Non-secret release configuration');
  SpreadsheetApp.flush();
}

function protectOwnerOnly_(sheet, description) {
  const existing = sheet.getProtections(SpreadsheetApp.ProtectionType.SHEET).filter(function (item) { return item.getDescription() === description; });
  const protection = existing[0] || sheet.protect().setDescription(description);
  const owner = Session.getEffectiveUser();
  protection.addEditor(owner);
  const otherEditors = protection.getEditors().filter(function (editor) { return editor.getEmail() !== owner.getEmail(); });
  if (otherEditors.length) protection.removeEditors(otherEditors);
  if (protection.canDomainEdit()) protection.setDomainEdit(false);
}

function assertHeaders_(sheet) {
  if (sheet.getLastRow() < 1) throw new Error('headers_missing');
  const headers = sheet.getRange(1, 1, 1, FORM.columns.length).getDisplayValues()[0];
  if (headers.join('\u001f') !== FORM.columns.join('\u001f')) throw new Error('headers_do_not_match_schema');
}

function enumValues_(items, allowed, name) {
  const unique = [];
  items.forEach(function (raw) {
    if (String(raw).length > 100) throw new Error(name);
    const item = normalize_(raw, 100);
    if (!item || allowed.indexOf(item) === -1) throw new Error(name);
    if (unique.indexOf(item) === -1) unique.push(item);
  });
  return allowed.filter(function (item) { return unique.indexOf(item) !== -1; });
}
function requiredText_(value, name, min, max) { const raw = String(value || ''); if (raw.length > max) throw new Error(name); const text = normalize_(raw, max); if (text.length < min) throw new Error(name); return text; }
function optionalText_(value, name, max) { const raw = String(value || ''); if (raw.length > max) throw new Error(name); return normalize_(raw, max); }
function normalize_(value, max) { return String(value || '').replace(/\r\n?/g, '\n').replace(/[\t ]+/g, ' ').trim().slice(0, max); }
function boundedRef_(value) { const text = String(value || ''); if (text.length > 64 || !/^[A-Za-z0-9._-]*$/.test(text)) throw new Error('attribution_ref'); return text; }
function boolean_(value, name) { if (['on', 'true', '1'].indexOf(value) !== -1) return true; throw new Error(name); }
function optionalBoolean_(value, name) { if (!value) return false; if (['on', 'true', '1'].indexOf(value) !== -1) return true; throw new Error(name); }
function boundedInteger_(value, min, max) { const number = Number(value); if (!Number.isInteger(number) || number < min || number > max) throw new Error('integer_range'); return number; }
function sheetSafe_(value) { const text = String(value || ''); return /^[=+\-@]/.test(text) ? "'" + text : text; }
function sha256_(value) { return bytesToHex_(Utilities.computeDigest(Utilities.DigestAlgorithm.SHA_256, value, Utilities.Charset.UTF_8)); }
function bytesToHex_(bytes) { return bytes.map(function (byte) { const value = byte < 0 ? byte + 256 : byte; return ('0' + value.toString(16)).slice(-2); }).join(''); }
function safeLog_(value) { return String(value || '').replace(/[\r\n]/g, ' ').slice(0, 180); }
function escapeHtml_(value) { return String(value || '').replace(/[&<>"']/g, function (char) { return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[char]; }); }
function resultPage_(title, message, success) {
  const safeTitle = escapeHtml_(title);
  const safeMessage = escapeHtml_(message);
  const accent = success ? '#2c7a5b' : '#ff4f32';
  return HtmlService.createHtmlOutput('<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>'+safeTitle+' | Demand Range</title><style>body{margin:0;background:#f5f6f7;color:#111820;font-family:Arial,sans-serif}.wrap{max-width:680px;margin:10vh auto;padding:32px}.card{background:#fff;border:1px solid #cbd1d6;box-shadow:10px 10px 0 #e8ebee;padding:clamp(28px,6vw,56px)}.rule{width:42px;height:4px;background:'+accent+';margin-bottom:28px}h1{font-size:clamp(34px,7vw,54px);line-height:1;margin:0 0 20px}p{font-size:17px;line-height:1.6;color:#4b5762}a{display:inline-block;margin-top:14px;background:#111820;color:#fff;padding:14px 20px;text-decoration:none;font-weight:bold}</style></head><body><main class="wrap"><section class="card"><div class="rule"></div><h1>'+safeTitle+'</h1><p>'+safeMessage+'</p><a href="https://demandrange.com/">Return to Demand Range</a></section></main></body></html>').setTitle(safeTitle + ' | Demand Range');
}

if (typeof globalThis !== 'undefined') {
  globalThis.__DEMANDRANGE_TEST__ = {FORM: FORM, parseAndValidate_: parseAndValidate_, sheetSafe_: sheetSafe_, enumValues_: enumValues_};
}
