#!/usr/bin/env python3
"""Build DemandRange's supplied redesign into an explicitly named public tree.

Canonical source remains outside the published repository. The source directory
combines the unmodified user export with retained production assets. All intake
repairs are explicit here; never hand-edit generated HTML/CSS. Prior generator
and production snapshot: files/site-redesign/2026-09-05/{tooling-before,production-before.zip}.
"""
from pathlib import Path
import argparse
import hashlib
import html
import json
import re
import shutil
import os
import subprocess
import sys
import tempfile
from foundation_stage import apply_foundation, quote_template

from production_contract import (
    clean_output_path, load_contract, preflight_source, require,
    validate_output, validate_quote_endpoint,
)

HERE = Path(__file__).resolve().parent
SOURCE = HERE / 'redesign-20260905-source'
QUOTE = HERE / 'quote-form'
FORM_VERSION = '2026-09-11-v1'
PRIVACY_VERSION = '2026-09-11-v1'
CONSENT_VERSION = '2026-09-11-v1'

def replace_once(text, old, new):
    require(text.count(old) == 1, f'Expected exactly one match: {old[:100]}')
    return text.replace(old, new, 1)

def render(name, text):
    if name.endswith('.html') and name != 'pumps-flow-control.html':
        import re
        # Keep the full service names in content; concise desktop labels avoid
        # clipping with ordinary system-font fallbacks on Windows/Linux/macOS.
        text = re.sub(r'(<nav class="primary-nav"[^>]*>)(.*?)(</nav>)', lambda m: m[1] + m[2].replace('>Opportunity Intelligence</a>', '>Intelligence</a>').replace('>Campaign Activation</a>', '>Activation</a>') + m[3], text)
        if name == 'sample-opportunity.html':
            for table, label in [('table class="t-dated"', 'Fictional evidence trail'), ('table class="t-score"', 'Illustrative opportunity score'), ('table', 'Illustrative buying committee')]:
                text = replace_once(text, '<div class="table-wrap"><' + table + '>', '<div class="table-wrap" tabindex="0" role="region" aria-label="' + label + '; scroll horizontally to view all columns"><' + table + '>')
        text = text.replace('<div class="table-wrap">', '<div class="table-wrap" tabindex="0" role="region" aria-label="Data table; scroll horizontally to view all columns">')
    if name == 'styles.css':
        text += '''

/* Intake repairs: fit the real navigation, including 320px screens. */
.header-inner{gap:16px}
.primary-nav{gap:16px}
.legal h2[id],.article h2[id],[id]{scroll-margin-top:100px}
.cell .recovery-heading{font-size:22px;line-height:1.15;margin-bottom:18px}
@media (max-width:720px){
 .table-wrap::before{content:"Scroll horizontally to view all columns";display:block;font-family:var(--f-display);font-size:13px;color:var(--ink-2);margin-bottom:12px}
}
@media (max-width:600px){
 .header-inner{gap:8px}
 .site-header .brand{gap:8px}
 .site-header .brand-text{font-size:16px}
 .menu{margin-left:0}
 .menu summary{width:40px;height:40px;padding:10px;gap:0;font-size:0;justify-content:center}
}
'''
    if name == 'privacy.html':
        text = replace_once(text, 'If you are in the EU and are unhappy with how personal data is handled, you may have the right to complain to your local supervisory authority.', 'If you are in Ireland or the EU and are unhappy with how personal data is handled, you may have the right to complain to the Irish Data Protection Commission or your local supervisory authority. See <a href="https://www.dataprotection.ie/" rel="noopener noreferrer">dataprotection.ie</a>.')
        text = replace_once(text, 'Technical logs follow relevant infrastructure settings.', 'Technical logs follow relevant infrastructure settings. The <code>dr-theme</code> colour preference stays in your browser until you change it or clear this site\'s browser storage; it is not sent to Demand Range.')
    if name == 'terms.html':
        text = replace_once(text, 'the laws of the jurisdiction in which Demand Range is established', 'the laws of Ireland')
    if name in {'privacy.html', 'cookies.html', 'terms.html'}:
        text = replace_once(text, 'Last updated: 23 August 2026', 'Last updated: 5 September 2026')
    if name == 'cookies.html':
        text = replace_once(text, 'Remembering the chosen colour theme between pages', 'Remembering the chosen colour theme between pages. Key: <code>dr-theme</code>; retained until you change the preference or clear this site\'s browser storage')
        text = replace_once(text, 'Because the current site code does not set non-essential cookies or tracking tags, a consent banner would not provide a meaningful optional-cookie choice.', 'The site has no analytics, advertising or tracking choices to present in a banner. The only site-code storage is the colour preference you explicitly request using the light/dark toggle; it is used solely to remember that choice. You can change it with the toggle or clear it using your browser\'s site-data controls. Any additional storage or tracking will be reviewed before it is introduced.')
    if name == 'index.html':
        text = replace_once(text, '<span class="inf">Inference:</span> packages may still be open', '<span class="inf">Unknown:</span> package availability not verified')
    if name == '404.html':
        for heading in ['Intelligence', 'Company', 'Legal']:
            text = replace_once(text, f'<h3>{heading}</h3>', f'<h2 class="recovery-heading">{heading}</h2>')
        # Pages serves this document at arbitrary missing/nested URLs. Relative
        # paths would otherwise break styles, navigation and the favicon.
        import re
        text = re.sub(r'href="((?!https?:|mailto:|#|/)[^"]+)"', r'href="/\1"', text)
    return text

def enable_quote_form(output, endpoint):
    endpoint = validate_quote_endpoint(endpoint)
    require(endpoint is not None, 'Quote endpoint required')
    template = (QUOTE / 'request-a-quote.template.html').read_text(encoding='utf-8')
    template = quote_template(template)
    client = (QUOTE / 'client.js').read_text(encoding='utf-8').strip()
    replacements = {
        '{{FORM_ENDPOINT}}': html.escape(endpoint, quote=True),
        '{{FORM_VERSION}}': FORM_VERSION,
        '{{PRIVACY_VERSION}}': PRIVACY_VERSION,
        '{{CONSENT_VERSION}}': CONSENT_VERSION,
        '{{QUOTE_FORM_SCRIPT}}': client,
    }
    for marker, value in replacements.items():
        template = replace_once(template, marker, value)
    require(all(marker not in template for marker in replacements), 'Unresolved quote-form template marker')
    (output / 'request-a-quote.html').write_text(template, encoding='utf-8')

    styles = output / 'styles.css'
    styles.write_text(styles.read_text(encoding='utf-8') + (QUOTE / 'quote-form.css').read_text(encoding='utf-8'), encoding='utf-8')

    # Make the approved request route discoverable while retaining Contact and email fallbacks.
    for page in sorted(output.glob('*.html')):
        if page.name in {'request-a-quote.html', '404.html', 'pumps-flow-control.html'}:
            continue
        text = page.read_text(encoding='utf-8')
        header_cta = '<a class="btn btn-primary header-cta" href="contact.html">Map my market</a>'
        if header_cta in text:
            text = replace_once(text, header_cta, '<a class="btn btn-primary header-cta" href="request-a-quote.html">Request a quote</a>')
        footer_contact = '<a href="contact.html">Contact</a><a href="mailto:partners@demandrange.com">partners@demandrange.com</a>'
        if footer_contact in text:
            text = replace_once(text, footer_contact, '<a href="request-a-quote.html">Request a quote</a><a href="contact.html">Contact</a><a href="mailto:partners@demandrange.com">partners@demandrange.com</a>')
        page.write_text(text, encoding='utf-8')

    contact_path = output / 'contact.html'
    contact = contact_path.read_text(encoding='utf-8')
    contact = replace_once(contact, '<h1>Bring one market you want to understand better.</h1>', '<h1>Tell us who you need to reach.</h1>')
    contact = replace_once(contact, 'Tell us what you sell, where you sell it and which facility changes could make an opportunity commercially worthwhile. We will tell you whether an analyst-led Opportunity Intelligence Sprint is a fit.', 'Tell us what you sell, the industries and regions that matter, and whether you need a blended lead programme or a narrower evidence-led review.')
    contact = replace_once(contact, '<h2>No web form. No tracking.</h2>', '<h2>Request a written scope online.</h2>')
    contact = replace_once(contact, 'This static site does not transmit form data. Use your own email client to contact Demand Range, and include only non-sensitive information needed for an initial conversation.', 'Use the structured request page to define your target market and preferred response route. The separate email route remains available for a short non-sensitive enquiry.')
    contact = replace_once(contact, '<a class="btn btn-light" href="mailto:partners@demandrange.com?subject=Industrial%20Opportunity%20Intelligence%20working%20session">Request a working session</a>', '<a class="btn btn-light" href="request-a-quote.html">Request a scope &amp; quote</a>')
    contact_path.write_text(contact, encoding='utf-8')

    privacy_path = output / 'privacy.html'
    privacy = privacy_path.read_text(encoding='utf-8')
    privacy = privacy.replace('Privacy notice for the static Demand Range website and email enquiries about Industrial Opportunity Intelligence.', 'Privacy notice for the Demand Range website, quote-request form and business enquiries.')
    privacy = replace_once(privacy, 'Last updated: 5 September 2026 · Website privacy notice', 'Last updated: 11 September 2026 · Website privacy notice · Version 2026-09-11-v1')
    privacy = replace_once(privacy, 'This notice explains how Demand Range handles personal data connected with this public website and email enquiries about Industrial Opportunity Intelligence.', 'This notice explains how Demand Range handles personal data connected with this public website, its quote-request form and business enquiries.')
    privacy = replace_once(privacy, '<div class="notice"><strong>Important:</strong> this website has no transmitting form. Please do not send sensitive personal data, passwords, credentials, confidential client files, suppression lists or live campaign data in a first email enquiry.</div>', '<div class="notice"><strong>Important:</strong> the quote-request page transmits the information you choose to submit to a restricted business intake record. Do not provide sensitive personal data, passwords, credentials, confidential customer files, suppression lists or live campaign data.</div>')
    privacy = replace_once(privacy, 'This notice covers the public website at <code>demandrange.com</code> and email enquiries sent to Demand Range.', 'This notice covers the public website at <code>demandrange.com</code>, the quote-request form and email enquiries sent to Demand Range.')
    privacy = replace_once(privacy, '<li>Name, work email, company, role and business contact details.</li><li>Enquiry text, product category, target market, facility context, commercial range and research challenge.</li><li>Follow-up correspondence and meeting notes you choose to share.</li>', '<li>Name, work email, company, optional company website and optional phone number.</li><li>Products or services, selected target industries, regions, countries, job-seniority preferences and additional enquiry context.</li><li>Your request for an email response, optional permission for phone contact, attribution references supplied in the approved page URL, and the form/privacy wording version.</li><li>Follow-up correspondence and meeting notes you choose to share.</li>')
    privacy = replace_once(privacy, '<li>Respond to enquiries and assess whether the service may be a fit.</li><li>Prepare non-sensitive follow-up materials and an initial working scope.</li>', '<li>Receive and respond to quote requests and assess whether a proposed industrial lead programme may be a fit.</li><li>Prepare a proposed written scope and commercial terms, prevent duplicate/abusive submissions and manage the enquiry queue.</li>')
    privacy = replace_once(privacy, 'Provider categories may include website hosting/source control, domain/DNS/security, email/productivity, internal operations and professional advisers or authorities where required.', 'Provider categories may include website hosting/source control, domain/DNS/security, Google Workspace services used for restricted form processing and records, email/productivity, internal operations, and professional advisers or authorities where required.')
    privacy = replace_once(privacy, 'Some infrastructure or email providers may process data outside the European Economic Area.', 'Some infrastructure, form-processing or email providers may process data outside the European Economic Area.')
    privacy = replace_once(privacy, 'Ordinary enquiry correspondence is reviewed and retained only while useful for the relationship or a legitimate business record, with a target review period of up to 24 months after the last meaningful interaction unless legal, tax, accounting, security or dispute needs require longer.', 'Quote requests and ordinary enquiry correspondence are reviewed and retained only while useful for the relationship or a legitimate business record, with a target review period of up to 24 months after the last meaningful interaction unless legal, tax, accounting, security or dispute needs require longer. Synthetic test records are segregated from live requests.')
    privacy_path.write_text(privacy, encoding='utf-8')

    sitemap_path = output / 'sitemap.xml'
    sitemap = sitemap_path.read_text(encoding='utf-8')
    sitemap = replace_once(sitemap, '  <url><loc>https://demandrange.com/contact.html</loc></url>', '  <url><loc>https://demandrange.com/request-a-quote.html</loc></url>\n  <url><loc>https://demandrange.com/contact.html</loc></url>')
    sitemap_path.write_text(sitemap, encoding='utf-8')


def render_tree(output, quote_endpoint, contract):
    built_paths = set()
    for source in sorted(SOURCE.rglob('*')):
        if not source.is_file():
            continue
        relative = source.relative_to(SOURCE)
        if relative.as_posix() in contract['excluded_source_files']:
            continue
        target = output / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        if source.suffix in {'.html', '.css', '.md'}:
            target.write_text(render(relative.as_posix(), source.read_text()), encoding='utf-8')
        else:
            shutil.copy2(source, target)
        built_paths.add(relative.as_posix())
    if quote_endpoint:
        enable_quote_form(output, quote_endpoint)
        built_paths.add('request-a-quote.html')
    if quote_endpoint:
        apply_foundation(output)
    built_paths = {p.relative_to(output).as_posix() for p in output.rglob('*') if p.is_file()}
    return {relative: hashlib.sha256((output / relative).read_bytes()).hexdigest() for relative in sorted(built_paths)}


def source_inventory():
    from production_contract import file_set
    return {name: hashlib.sha256((HERE / name).read_bytes()).hexdigest()
            for name in sorted(file_set(HERE))
            if '__pycache__' not in Path(name).parts}


def output_inventory(root):
    from production_contract import file_set
    return {name: hashlib.sha256((root / name).read_bytes()).hexdigest()
            for name in sorted(file_set(root))}


def build(output, quote_endpoint=None, mode='production'):
    # No output mutation before configuration/input checks. A post-promotion
    # exception can leave complete output: reconcile it, never retry blindly.
    frozen_sources = source_inventory()
    contract = load_contract(mode, quote_endpoint)
    output = clean_output_path(output)
    preflight_source(contract)
    with tempfile.TemporaryDirectory(prefix='.demandrange-build-', dir=output.parent) as temp:
        staged = Path(temp) / 'public'
        staged.mkdir()
        manifest = render_tree(staged, quote_endpoint, contract)
        validate_output(staged, contract, mode, quote_endpoint)
        command = [sys.executable, '-B', str(HERE / 'qa_static.py'), '--root', str(staged), '--mode', mode]
        if quote_endpoint:
            command += ['--quote-endpoint', quote_endpoint]
        result = subprocess.run(command, text=True, capture_output=True, timeout=120,
                                env={**os.environ, 'PYTHONDONTWRITEBYTECODE': '1'})
        require(result.returncode == 0, 'Staged static QA failed:\n' + result.stdout + result.stderr)
        require(source_inventory() == frozen_sources, 'Source changed during build; reviewed inputs invalidated')
        require(output_inventory(staged) == manifest, 'Output changed after rendering/QA')
        # Keep every original contract/static assertion above. Only then apply
        # URL-span edits, with raw alias checks and exact/invertible byte proof.
        clean_report = None
        if mode == 'production':
            from clean_urls import apply_clean_urls
            legacy = Path(temp) / 'validated-legacy'
            shutil.copytree(staged, legacy)
            clean_report = apply_clean_urls(staged, legacy, contract)
            manifest = output_inventory(staged)
        # Recheck immediately before promotion; never merge with stale output.
        clean_output_path(output)
        os.replace(staged, output)
        require(output_inventory(output) == manifest and source_inventory() == frozen_sources,
                'OUTPUT MAY EXIST: post-promotion integrity failure; reconcile before retry')
    print(json.dumps({'output': str(output), 'mode': mode,
                      'production_mode': mode == 'production', 'release_authorised': False,
                      'note': 'Local build/QA only; independent release review still required',
                      'original_static_qa': result.stdout.strip(),
                      'clean_url_qa': clean_report,
                      'files': len(manifest), 'quote_form': bool(quote_endpoint), 'manifest': manifest}, indent=2))

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--quote-endpoint', help='Exact reviewed endpoint required in production; synthetic endpoint optional in fixture mode')
    parser.add_argument('--mode', choices=['production', 'fixture'], default='production',
                        help='Production is default; no-form/synthetic fixtures require explicit fixture mode')
    parsed = parser.parse_args()
    try:
        build(parsed.output, parsed.quote_endpoint, parsed.mode)
    except (ValueError, OSError) as error:
        parser.exit(1, f'FAIL: {error}\n')
