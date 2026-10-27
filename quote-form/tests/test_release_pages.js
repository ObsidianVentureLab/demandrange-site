'use strict';
// Local .test-origin rendering only; no public hosting or live submissions.
const {chromium} = require('playwright');
const fs = require('fs');
const path = require('path');
const assert = require('assert');
assert(process.env.QUOTE_QA_ROOT && process.env.QUOTE_QA_OUT, 'Explicit candidate and evidence directories required');
const root = path.resolve(process.env.QUOTE_QA_ROOT);
const out = path.resolve(process.env.QUOTE_QA_OUT);
const origin = 'https://demandrange-release.test';
const pages = fs.readdirSync(root).filter(name => name.endsWith('.html')).sort();
const viewports = [{width:1440,height:900},{width:390,height:844}];
const mime = {'.html':'text/html','.css':'text/css','.svg':'image/svg+xml','.png':'image/png','.jpg':'image/jpeg','.webp':'image/webp','.ico':'image/x-icon','.pdf':'application/pdf'};
fs.mkdirSync(out,{recursive:true});
(async () => {
 const browser = await chromium.launch({headless:true});
 const results = [];
 try {
  for (const viewport of viewports) {
   for (const name of pages) {
    const context = await browser.newContext({viewport});
    const errors = [], external = [];
    await context.route('**/*',async route => {
     const url = new URL(route.request().url());
     if (url.origin !== origin) { external.push(url.origin); return route.abort(); }
     let relative;
     try { relative = decodeURIComponent(url.pathname); } catch { return route.fulfill({status:400,body:'Invalid path'}); }
     const file = path.resolve(root,'.'+relative);
     if (!file.startsWith(root+path.sep) || !fs.existsSync(file) || !fs.statSync(file).isFile()) {
      return route.fulfill({status:404,body:'Missing local QA resource'});
     }
     return route.fulfill({status:200,contentType:mime[path.extname(file)]||'application/octet-stream',body:fs.readFileSync(file)});
    });
    const page = await context.newPage();
    page.on('pageerror',e => errors.push(e.message));
    page.on('console',m => { if(m.type()==='error') errors.push(m.text()); });
    await page.goto(origin+'/'+name,{waitUntil:'networkidle'});
    const state = await page.evaluate(() => ({url:location.href,ready:document.readyState,
      width:innerWidth,scrollWidth:document.documentElement.scrollWidth,clientWidth:document.documentElement.clientWidth}));
    assert(state.url.startsWith(origin+'/') && state.ready==='complete' && state.width===viewport.width,'Unexpected/stale capture state');
    assert(state.scrollWidth<=state.clientWidth+1,'Overflow '+name+' '+viewport.width);
    assert.deepStrictEqual(errors,[],'Browser errors '+name);
    assert.deepStrictEqual(external,[],'External request attempted '+name);
    const capture=name.replace('.html','')+'-'+viewport.width+'.png';
    await page.screenshot({path:path.join(out,capture),fullPage:true});
    results.push({route:name,viewport:viewport.width,...state,capture,errors,external});
    await context.close();
   }
  }
  assert.equal(results.length,pages.length*viewports.length);
  assert.equal(new Set(results.map(r=>r.route+':'+r.viewport)).size,results.length);
  fs.writeFileSync(path.join(out,'results.json'),JSON.stringify({status:'PASS_LOCAL_RENDER_ONLY',pages,viewports,
    captures:results.length,live_published:false,results},null,2)+'\n');
  console.log(JSON.stringify({status:'PASS_LOCAL_RENDER_ONLY',pages:pages.length,captures:results.length,live_published:false}));
 } finally { await browser.close(); }
})().catch(error=>{console.error(error);process.exit(1);});
