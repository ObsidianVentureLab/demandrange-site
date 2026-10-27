'use strict';
const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');
const { URL, URLSearchParams } = require('url');

const SITE = process.env.QUOTE_QA_SITE || '/tmp/demandrange-quote-qa/request-a-quote.html';
const OUT = process.env.QUOTE_QA_OUT ? path.resolve(process.env.QUOTE_QA_OUT) : path.resolve(__dirname, 'qa-output');
const ENDPOINT = process.env.QUOTE_QA_ENDPOINT || 'https://script.google.com/macros/s/AKfycbxSyntheticQuoteQa000000000000000000000000/exec';
fs.mkdirSync(OUT, {recursive: true});

let assertionCount = 0;
function assert(condition, message) {
  if (!condition) throw new Error(message);
  assertionCount += 1;
}

(async () => {
  const browser = await chromium.launch({headless: true});
  const results = [];
  const viewports = [
    {name: 'desktop', width: 1440, height: 900},
    {name: 'mobile', width: 390, height: 844},
    {name: 'mobile-320', width: 320, height: 760},
  ];
  for (const viewport of viewports) {
    const context = await browser.newContext({viewport});
    const page = await context.newPage();
    const consoleErrors = [];
    const pageErrors = [];
    const externalBeforeSubmit = [];
    page.on('console', msg => { if (msg.type() === 'error') consoleErrors.push(msg.text()); });
    page.on('pageerror', error => pageErrors.push(error.message));
    page.on('request', request => {
      const url = request.url();
      if (!url.startsWith('file://') && url !== ENDPOINT) externalBeforeSubmit.push(url);
    });
    await page.goto('file://' + SITE + '?asset_ref=approved_asset-01&campaign_ref=bad%20value<script>', {waitUntil: 'load'});
    await page.waitForTimeout(150);
    const geometry = await page.evaluate(() => ({
      scrollWidth: document.documentElement.scrollWidth,
      clientWidth: document.documentElement.clientWidth,
      h1: document.querySelectorAll('h1').length,
      forms: document.querySelectorAll('form').length,
      details: document.querySelectorAll('details.multi').length,
      endpoint: document.querySelector('form').action,
      asset: document.querySelector('[name="asset_ref"]').value,
      campaign: document.querySelector('[name="campaign_ref"]').value,
    }));
    assert(geometry.scrollWidth <= geometry.clientWidth + 1, viewport.name + ': horizontal overflow');
    assert(geometry.h1 === 1 && geometry.forms === 1 && geometry.details === 3, viewport.name + ': structure mismatch');
    assert(geometry.endpoint === ENDPOINT, viewport.name + ': endpoint mismatch');
    assert(geometry.asset === 'approved_asset-01', viewport.name + ': asset attribution mismatch');
    assert(geometry.campaign === 'badvaluescript', viewport.name + ': campaign sanitisation mismatch');
    assert(externalBeforeSubmit.length === 0, viewport.name + ': external request before submission');

    await page.screenshot({path: path.join(OUT, viewport.name + '-light-full.png'), fullPage: true});
    await page.click('.theme-toggle');
    assert(await page.getAttribute('html', 'data-theme') === 'dark', viewport.name + ': theme toggle failed');
    await page.screenshot({path: path.join(OUT, viewport.name + '-dark-top.png'), fullPage: false});
    await page.click('.theme-toggle');

    // Keyboard-open the first native details control and select one value.
    const industrySummary = page.locator('details.multi').nth(0).locator('summary');
    await industrySummary.focus();
    await page.keyboard.press('Enter');
    assert(await page.locator('details.multi').nth(0).getAttribute('open') !== null, viewport.name + ': keyboard details open failed');
    const firstIndustry = page.locator('input[name="industries"]').nth(0);
    await firstIndustry.focus();
    await page.keyboard.press('Space');
    assert(await firstIndustry.isChecked(), viewport.name + ': keyboard checkbox failed');
    assert((await page.locator('details.multi').nth(0).locator('.selection-summary').textContent()).includes('Automotive'), viewport.name + ': selected summary failed');
    if (viewport.name !== 'desktop') {
      await page.locator('details.multi').nth(0).scrollIntoViewIfNeeded();
      await page.screenshot({path: path.join(OUT, viewport.name + '-dropdown.png'), fullPage: false});
    }

    // Empty submit must remain on page and expose linked errors without any POST.
    await page.evaluate(() => { document.querySelector('[name="form_load_ms"]').value = String(Date.now() - 3000); });
    await page.click('button[type="submit"]');
    assert(await page.locator('#form-errors').isVisible(), viewport.name + ': error summary missing');
    assert((await page.locator('.field-error:visible').count()) >= 5, viewport.name + ': field errors missing');

    // Conditional phone rule: supplied number requires explicit phone permission.
    await page.fill('#full-name', 'Alex Example');
    await page.fill('#work-email', 'alex@example.com');
    await page.fill('#company-name', 'Example Process Systems Ltd');
    await page.fill('#company-website', 'https://example.com');
    await page.fill('#phone-number', '+353 1 555 0100');
    await page.fill('#product-service', 'Industrial pumps and flow-control systems');
    await page.locator('details.multi').nth(1).locator('summary').click();
    await page.check('input[name="regions"][value="EMEA"]');
    await page.locator('details.multi').nth(2).locator('summary').click();
    await page.check('input[name="seniority"][value="Director"]');
    await page.check('#email-ack');
    await page.click('button[type="submit"]');
    assert((await page.locator('#phone_number-error').textContent()).includes('Choose phone contact'), viewport.name + ': phone permission rule missing');
    await page.check('#phone-contact');

    let postBody = null;
    await page.route('https://script.google.com/**', async route => {
      postBody = route.request().postData() || '';
      await route.fulfill({status: 200, contentType: 'text/html', body: '<!doctype html><title>Synthetic receipt</title><h1>Received</h1>'});
    });
    await Promise.all([
      page.waitForURL('https://script.google.com/**'),
      page.click('button[type="submit"]')
    ]);
    assert(postBody, viewport.name + ': valid form did not POST');
    const posted = new URLSearchParams(postBody);
    assert(posted.get('work_email') === 'alex@example.com', viewport.name + ': work email not posted');
    assert(posted.getAll('industries').includes('Automotive'), viewport.name + ': industries not posted');
    assert(posted.get('email_acknowledgement') === 'on' && posted.get('phone_contact') === 'on', viewport.name + ': contact choices not posted');
    assert((posted.get('submission_token') || '').length >= 16, viewport.name + ': token missing');
    assert(consoleErrors.length === 0, viewport.name + ': console errors ' + consoleErrors.join('; '));
    assert(pageErrors.length === 0, viewport.name + ': page errors ' + pageErrors.join('; '));
    results.push({viewport, geometry, consoleErrors, pageErrors, postedFields: Array.from(posted.keys()).length});
    await context.close();
  }
  await browser.close();
  const report = {status: 'PASS_LOCAL_INTERCEPTED_ONLY', viewports: results, assertions: assertionCount, endpoint: ENDPOINT, note: 'Endpoint was intercepted; no Google write occurred.'};
  fs.writeFileSync(path.join(OUT, 'interaction-results.json'), JSON.stringify(report, null, 2));
  console.log(`PASS: ${results.length} viewports; ${assertionCount} executed interaction/geometry assertions; validation, keyboard controls, theme, attribution and intercepted synthetic POST passed; no live Google write`);
})().catch(error => { console.error(error.stack || error); process.exit(1); });
