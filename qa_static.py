#!/usr/bin/env python3
"""Offline static QA for Demand Range (requires beautifulsoup4)."""
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlsplit
import re
import sys
import xml.etree.ElementTree as ET

import argparse
import hashlib
import json
from bs4 import BeautifulSoup
from claim_context import claim_scan_text
from site_guards import check_html_resources, check_css, approved_reference, unique_html_attributes
from production_contract import load_contract, validate_output, validate_quote_endpoint

args = argparse.ArgumentParser()
args.add_argument('--root', type=Path, required=True)
args.add_argument('--quote-endpoint', help='Exact reviewed endpoint required in production')
args.add_argument('--mode', choices=['production', 'fixture'], default='production')
parsed = args.parse_args()
QUOTE_ENDPOINT = parsed.quote_endpoint
HERE = Path(__file__).resolve().parent
try:
    CONTRACT = load_contract(parsed.mode, QUOTE_ENDPOINT)
    ROOT = validate_output(parsed.root, CONTRACT, parsed.mode, QUOTE_ENDPOINT)
except (ValueError, OSError, ET.ParseError) as error:
    args.exit(1, f'FAIL: {error}\n')
ALLOWED_THEME_SCRIPTS = {
    '7d3e02eedd2b4c2212e1f453c1da361f49d104321b64051b7fbdfc4e295815b0',
    'b653ecd363040827e01ed78c26dd12fe693f7c24bbc5d501b382e3471002e9c9',
}
QUOTE_SCRIPT_HASH = CONTRACT['quote_inline_script_sha256']
HAS_QUOTE = parsed.mode == 'production' or bool(QUOTE_ENDPOINT)
ROUTES = [r for r in CONTRACT['page_routes'] if HAS_QUOTE or r not in {'request-a-quote.html', *CONTRACT['generator_managed_files']}]

class AuditParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.tags = []
        self.ids = []
        self.links = []
        self.resource_urls = []
        self.headings = []
        self.h1_count = 0
        self.has_main = False
        self.has_nav = False
        self.has_footer = False
        self.has_skip = False
        self.lang = None
        self.title_depth = 0
        self.title_text = ""
        self.meta = {}
        self.forms = 0
        self.scripts = 0
        self.iframes = 0
        self.images_missing_alt = 0
        self.details = 0
        self.summaries = 0
    def handle_starttag(self, tag, attrs):
        attrs = unique_html_attributes(attrs)
        self.tags.append(tag)
        if tag == "html": self.lang = attrs.get("lang")
        if "id" in attrs: self.ids.append(attrs["id"])
        if tag == "a":
            href = attrs.get("href", "")
            self.links.append(href)
            if "skip-link" in (attrs.get("class") or ""): self.has_skip = True
        if tag in {"link", "script", "img", "iframe", "source", "video", "audio"}:
            is_canonical = tag == "link" and "canonical" in (attrs.get("rel") or "").split()
            url = attrs.get("href") or attrs.get("src")
            if url and not is_canonical: self.resource_urls.append(url)
        if tag == "main": self.has_main = True
        if tag == "nav": self.has_nav = True
        if tag == "footer": self.has_footer = True
        if tag == "form": self.forms += 1
        if tag == "script": self.scripts += 1
        if tag == "iframe": self.iframes += 1
        if tag == "img" and "alt" not in attrs: self.images_missing_alt += 1
        if tag == "details": self.details += 1
        if tag == "summary": self.summaries += 1
        if re.fullmatch(r"h[1-6]", tag):
            level = int(tag[1])
            self.headings.append(level)
            if level == 1: self.h1_count += 1
        if tag == "title": self.title_depth += 1
        if tag == "meta":
            key = attrs.get("name") or attrs.get("property")
            if key: self.meta[key] = attrs.get("content", "")
    def handle_endtag(self, tag):
        if tag == "title" and self.title_depth: self.title_depth -= 1
    def handle_data(self, data):
        if self.title_depth: self.title_text += data

errors = []
ENTITY_CORE = set()
checks = 0
parsers = {}

def check(condition, message):
    global checks
    checks += 1
    if not condition: errors.append(message)

for route in ROUTES:
    path = ROOT / route
    check(path.is_file(), f"{route}: missing route")
    if not path.is_file(): continue
    text = path.read_text(encoding="utf-8")
    p = AuditParser(); p.feed(text); p.close(); parsers[route] = p
    check(text.lower().startswith("<!doctype html>"), f"{route}: missing HTML5 doctype")
    check(p.lang == "en-IE", f"{route}: html lang must be en-IE")
    if 'property="og:site_name"' in text:
        check(text.count('<meta property="og:locale" content="en_IE">') == 1, f"{route}: og:locale must be en_IE exactly once")
    check(bool(p.title_text.strip()), f"{route}: missing title")
    check(bool(p.meta.get("description", "").strip()), f"{route}: missing meta description")
    check(p.meta.get("viewport") == "width=device-width, initial-scale=1", f"{route}: invalid viewport")
    check(p.h1_count == 1, f"{route}: expected exactly one h1, found {p.h1_count}")
    check(p.has_main and p.has_nav and p.has_footer and p.has_skip, f"{route}: missing main/nav/footer/skip-link landmark")
    check(len(p.ids) == len(set(p.ids)), f"{route}: duplicate IDs")
    check(p.forms == (1 if route == 'request-a-quote.html' else 0), f"{route}: unexpected form count {p.forms}")
    soup = BeautifulSoup(text, 'html.parser')
    try:
        check_html_resources(text, ROOT, route, QUOTE_ENDPOINT, CONTRACT.get('external_reference_policy'))
        check(True, route + ': resource subset')
        if HAS_QUOTE:
            from og02_guards import validate_page
            validate_page(soup, route, ROOT)
            check(True, route + ': exact OG02 link/content scope')
    except ValueError as error:
        check(False, str(error))
    canonicals = soup.select('link[rel="canonical"]')
    if route == '404.html':
        # A noindex recovery document served at arbitrary missing URLs is not
        # an indexable route: preserve the baseline's deliberate no-canonical.
        check(not canonicals, '404.html: recovery document must not claim a canonical')
        if parsed.mode == 'production':
            recovery_og = soup.find('meta', property='og:description')
            check(recovery_og is not None and recovery_og.get('content') == 'The requested page could not be found on the Demand Range website.', '404.html: reviewed recovery metadata required')
            check('everything on this site' not in text, '404.html: incomplete directory cannot claim completeness')
    else:
        expected_canonical = 'https://demandrange.com/' if route == 'index.html' else 'https://demandrange.com/' + route
        check(len(canonicals) == 1 and canonicals[0].get('href') == expected_canonical,
              f'{route}: canonical must be unique and self-referencing')
    # Structured data is non-executable: exactly one reviewed-shape JSON-LD
    # block (#dr-entity, in <head>) per indexable page, none on 404. It is
    # validated structurally below; every executable script stays hash-pinned.
    entity_scripts = [s for s in soup.find_all('script') if s.get('type') == 'application/ld+json']
    scripts = [s for s in soup.find_all('script') if s.get('type') != 'application/ld+json']
    if route == '404.html':
        check(not entity_scripts, '404.html: recovery document must not carry JSON-LD')
    else:
        entity_ok = False
        if len(entity_scripts) == 1:
            node = entity_scripts[0]
            raw = node.get_text()
            try:
                data = json.loads(raw)
                graph = {n.get('@id'): n for n in data['@graph']}
                page_node = graph.get(expected_canonical + '#webpage')
                description = soup.find('meta', attrs={'name': 'description'})
                entity_ok = (set(node.attrs) == {'type', 'id'} and node.get('id') == 'dr-entity' and node.parent.name == 'head'
                    and '</' not in raw and set(data) == {'@context', '@graph'} and data['@context'] == 'https://schema.org'
                    and len(data['@graph']) == 3 and len(graph) == 3
                    and 'https://demandrange.com/#organization' in graph and 'https://demandrange.com/#website' in graph
                    and page_node is not None and page_node.get('url') == expected_canonical
                    and page_node.get('name') == soup.title.get_text()
                    and description is not None and page_node.get('description') == description.get('content')
                    and page_node.get('inLanguage') == 'en-IE')
                ENTITY_CORE.add(json.dumps([graph['https://demandrange.com/#organization'], graph['https://demandrange.com/#website']], sort_keys=True))
            except (ValueError, KeyError, TypeError, AttributeError):
                entity_ok = False
        check(entity_ok, f"{route}: JSON-LD must be one #dr-entity head block matching this page's canonical, title and description")
    script_hashes = [hashlib.sha256(s.get_text().encode()).hexdigest() for s in scripts if not s.get('src')]
    expected_hashes = ALLOWED_THEME_SCRIPTS | ({QUOTE_SCRIPT_HASH} if route == 'request-a-quote.html' else set())
    expected_script_count = 3 if route == 'request-a-quote.html' else 2
    check(p.iframes == 0, f"{route}: iframe found")
    check(len(scripts) == expected_script_count and all(not s.get('src') for s in scripts) and set(script_hashes) == expected_hashes, f"{route}: unexpected script; only reviewed inline scripts are allowed")
    check(not any(k.lower().startswith('on') for el in soup.find_all() for k in el.attrs), f"{route}: unexpected inline event handler")
    for field in ['og:image', 'twitter:image']:
        check(p.meta.get(field) == 'https://demandrange.com/og-image.png', f'{route}: social image metadata missing')
    check(p.images_missing_alt == 0, f"{route}: image missing alt")
    for download in soup.select('a[href$=".csv"]'):
        check(download['href'] in CONTRACT['safe_downloads'] and download.has_attr('download'), f'{route}: undeclared or non-download CSV')
    if route == 'irish-manufacturing-account-research.html':
        check((ROOT / "styles.css").read_text().count('#discovery .table-wrap[aria-labelledby="source-purpose"] th { color: var(--ink-2); }') == 1, "OG01: exact matrix-scoped header contrast correction required")
        check([a['href'] for a in soup.select('a[href$=".csv"]')] == ['OG01-Evidence_Question_Log.csv'], 'OG01: exact evidence-question download required')
        matrix = soup.select_one('#discovery .table-wrap[role="region"][tabindex="0"][aria-labelledby="source-purpose"][aria-describedby="source-purpose-scroll"]')
        check(matrix is not None and len(matrix.select('tbody tr')) == 5 and len(matrix.select('thead th[scope="col"]')) == 3 and len(matrix.select('tbody th[scope="row"]')) == 5, 'OG01: five-question accessible decision matrix required')
    expected_details = 4 if route == 'request-a-quote.html' else 1
    check(p.details == p.summaries == expected_details, f"{route}: details/summary mismatch")
    for prev, cur in zip(p.headings, p.headings[1:]):
        check(cur <= prev + 1, f"{route}: heading level jumps h{prev} to h{cur}")
    for resource in p.resource_urls:
        parts = urlsplit(resource)
        check(not parts.scheme and not resource.startswith("//"), f"{route}: external resource {resource}")
        target = unquote(parts.path).lstrip('/')
        if target:
            check((ROOT / target).is_file(), f"{route}: missing resource {target}")

for route, p in parsers.items():
    for href in p.links:
        if not href:
            errors.append(f"{route}: empty href"); continue
        parts = urlsplit(href)
        if parts.scheme in {"mailto", "http", "https"}:
            if parts.scheme == "mailto":
                check(parts.path == "partners@demandrange.com", f"{route}: unexpected mailto target {parts.path}")
            else:
                check(href == "https://www.dataprotection.ie/" or all(approved_reference(a, route, CONTRACT["external_reference_policy"]) for a in BeautifulSoup((ROOT / route).read_text(), "html.parser").find_all("a", href=href)), f"{route}: unexpected external link {href}")
            continue
        check(not href.startswith("/") or route == '404.html', f"{route}: unexpected root-relative internal link {href}")
        target_name = unquote(parts.path).lstrip('/') or route
        target = ROOT / target_name
        check(target.is_file(), f"{route}: broken link {href}")
        if parts.fragment and target_name in parsers:
            check(parts.fragment in parsers[target_name].ids, f"{route}: missing fragment {href}")

all_html = "\n".join((ROOT / r).read_text(encoding="utf-8") for r in ROUTES)
contextual_claim_text = claim_scan_text(all_html)
for pattern, label in [
    (r"EUR\s*2[,\s]?750", "unapproved launch price"),
    (r"\bVAT\b", "VAT language"),
    (r"\breplacement\b", "replacement language"),
    (r"See industrial demand before it becomes obvious", "unvalidated predictive hero claim"),
    (r"public and licensed evidence", "unqualified licensed-source claim"),
    (r"\btenant separation\b", "unverified current tenant-separation claim"),
    (r"verified business contact data", "unverified current contact-data claim"),
    (r"\b(?:central|global) suppression\b", "unverified current suppression-control claim"),
    (r"\binstant quote\b", "instant-quote promise"),
    (r"\bguaranteed (?:quote|conversion|meeting|pipeline|revenue)\b", "guaranteed commercial outcome"),
    (r"\bmarketing qualified leads?\b|\bMQLs?\b", "unsupported MQL claim"),
    (r"fonts\.googleapis|fonts\.gstatic", "external font"),
    (r"googletagmanager|google-analytics|segment\.com|hotjar", "analytics/tracking"),
]:
    scan = all_html if label in {'external font', 'analytics/tracking'} else contextual_claim_text
    check(re.search(pattern, scan, re.I) is None, f"claim/dependency gate: found {label}")
check("analyst-led" in all_html.lower(), "claim gate: analyst-led wording missing")
check('It is not a self-service platform' in (ROOT / 'terms.html').read_text(), 'claim gate: live-software boundary missing')
check('Any future software or client-data processing would require tested customer isolation' in (ROOT / 'privacy.html').read_text(), 'claim gate: future-system requirements boundary missing')
check("not represented here as operating" in all_html.lower() or "does not represent those controls as operating" in all_html.lower(), "claim gate: unverified-control boundary missing")
check("client shares" in all_html.lower() or "client supplies" in all_html.lower(), "claim gate: feedback dependency missing")
check("fictional throughout" in (ROOT / "sample-opportunity.html").read_text(encoding="utf-8").lower(), "sample: repeated fictional warning missing")

check((ROOT / "CNAME").read_text(encoding="utf-8").strip() == "demandrange.com", "CNAME changed or invalid")
check((ROOT / ".nojekyll").is_file(), ".nojekyll missing")
check((ROOT / "styles.css").is_file(), "styles.css missing")
ET.parse(ROOT / "sitemap.xml")
sitemap = (ROOT / "sitemap.xml").read_text(encoding="utf-8")
for route in ROUTES:
    if route == '404.html':
        check('https://demandrange.com/404.html' not in sitemap, '404 must not appear in sitemap')
        check(parsers[route].meta.get('robots') == 'noindex', '404 must be noindex')
        continue
    expected = "https://demandrange.com/" if route == "index.html" else f"https://demandrange.com/{route}"
    check(expected in sitemap, f"sitemap missing {route}")

notice_date = '11 September 2026' if HAS_QUOTE else '5 September 2026'
for route in ['privacy.html', 'cookies.html', 'terms.html']:
    expected_date = notice_date if route == 'privacy.html' else ('30 September 2026' if HAS_QUOTE else '5 September 2026')
    check(f'Last updated: {expected_date}' in (ROOT / route).read_text(), f'{route}: notice date not current')
check('https://www.dataprotection.ie/' in (ROOT / 'privacy.html').read_text(), 'Irish DPC complaint route missing')
check('laws of Ireland' in (ROOT / 'terms.html').read_text(), 'Irish governing law changed')
check('dr-theme' in (ROOT / 'cookies.html').read_text() and 'clear this site' in (ROOT / 'cookies.html').read_text(), 'theme storage disclosure missing')
check((ROOT / 'DemandRange_Sample_Opportunity_Brief.pdf').read_bytes().startswith(b'%PDF'), 'sample PDF missing/invalid')
check((ROOT / 'og-image.png').read_bytes().startswith(b'\x89PNG\r\n\x1a\n'), 'social preview image missing/invalid')
check('url=markets.html' in (ROOT / 'pumps-flow-control.html').read_text(), 'legacy redirect missing')
for policy in ['security.txt', 'mta-sts.txt']:
    check((ROOT / '.well-known' / policy).is_file(), f'{policy}: existing policy missing')
css = (ROOT / 'styles.css').read_text()
try:
    check_css(css)
    check(True, 'CSS resource subset')
except ValueError as error:
    check(False, str(error))
check(not re.search(r'@import|url\(\s*[\"\']?https?://', css), 'external CSS resource')
check('prefers-reduced-motion' in css, 'reduced-motion support missing')
check(not any(p.suffix in {'.py', '.js', '.json', '.zip', '.env', '.md'} and p.relative_to(ROOT).as_posix() not in CONTRACT['safe_documents'] for p in ROOT.rglob('*') if p.is_file()), 'internal tooling, private Markdown or secret file in public tree; only exact pinned OG02 JSON documents excepted')

if HAS_QUOTE:
    check(bool(QUOTE_ENDPOINT), 'quote form present but --quote-endpoint was not supplied to QA')
    schema = json.loads((HERE / 'quote-form' / 'form_schema.json').read_text(encoding='utf-8'))
    quote_text = (ROOT / 'request-a-quote.html').read_text(encoding='utf-8')
    quote = BeautifulSoup(quote_text, 'html.parser')
    form = quote.find('form', id='quote-request-form')
    check(form is not None, 'quote: canonical form missing')
    if form is not None:
        check(str(form.get('method') or '').lower() == 'post', 'quote: form method must be POST')
        check(str(form.get('action') or '') == QUOTE_ENDPOINT, 'quote: action does not match the reviewed endpoint')
        check(form.get('novalidate') is not None, 'quote: reviewed custom/native validation boundary missing')
        names = {str(field.get('name')) for field in form.find_all(['input', 'textarea', 'select']) if field.get('name')}
        expected_names = set(schema['fields']) | set(schema['hidden_fields'])
        check(names == expected_names, f'quote: field-name mismatch missing={sorted(expected_names-names)} extra={sorted(names-expected_names)}')
        check(not any(field.has_attr('checked') for field in form.find_all('input')), 'quote: checkbox must not be preselected')
        check(not form.find_all('iframe'), 'quote: iframe found')
        for name, expected in [('industries', schema['fields']['industries']['values']), ('regions', schema['fields']['regions']['values']), ('seniority', schema['fields']['seniority']['values'])]:
            actual = [str(field.get('value') or '') for field in form.find_all('input', attrs={'name': name, 'type': 'checkbox'})]
            check(actual == expected, f'quote: {name} taxonomy/order mismatch')
        for field in form.find_all(['input', 'textarea']):
            if str(field.get('type') or '') == 'hidden' or str(field.get('aria-hidden') or '') == 'true':
                continue
            field_id = str(field.get('id') or '')
            has_label = bool(field.find_parent('label') or (field_id and form.find('label', attrs={'for': field_id})))
            check(has_label, f"quote: field lacks label {field.get('name')}")
        for fieldset in form.find_all('fieldset'):
            check(fieldset.find('legend') is not None, f"quote: fieldset lacks legend {fieldset.get('id')}")
    check('10% opportunity-signal leads' in quote_text and '90% industry-matched leads (Look Alike)' in quote_text, 'quote: approved 10/90 target is missing')
    check('Target mix, not a guaranteed allocation' in quote_text and 'These percentages are a planning target.' in quote_text, 'quote: non-guarantee boundary missing')
    check('{{' not in quote_text and 'TEST_DEPLOYMENT_ID' not in quote_text, 'quote: unresolved placeholder present')
    check(validate_quote_endpoint(QUOTE_ENDPOINT) == QUOTE_ENDPOINT and quote_text.count(QUOTE_ENDPOINT or '') == 1, 'quote: reviewed exact endpoint not bound once')
    for route in ['terms.html', 'campaign-activation.html', 'privacy.html']:
        check('no transmitting form' not in (ROOT / route).read_text().lower(), f'{route}: stale no-form assertion')
    cookies = (ROOT / 'cookies.html').read_text()
    for fact in ['dr-theme', 'form-processing endpoint', 'It does not write browser storage.', 'asset_ref', 'campaign_ref']:
        check(fact in cookies, 'cookies: missing verified technical disclosure ' + fact)
    sample = BeautifulSoup((ROOT / 'sample-account-research.html').read_text(), 'html.parser')
    for section in ['accepted-account', 'paired-signal', 'rejected-account']:
        node = sample.find(id=section)
        check(node is not None and 'Fictional example' in node.get_text(), 'sample: missing fictional worked class ' + section)
    check(set(a['href'] for a in sample.select('a[href$=".csv"]')) == {n for n in CONTRACT['safe_downloads'] if n.startswith('account-research-')}, 'sample: declared download set mismatch')
    privacy_text = (ROOT / 'privacy.html').read_text(encoding='utf-8')
    check('this website has no transmitting form' not in privacy_text.lower(), 'privacy: stale no-form claim remains')
    for phrase in ['quote-request form', 'Google Workspace', 'optional phone number', 'Version 2026-09-11-v1']:
        check(phrase.lower() in privacy_text.lower(), f'privacy: missing form disclosure {phrase}')
else:
    check(QUOTE_ENDPOINT is None, 'QA endpoint supplied but the quote form is absent')

check(len(ENTITY_CORE) == 1, 'JSON-LD Organization/WebSite nodes must be identical on every page')
if errors:
    print(f"FAIL: {len(errors)} error(s) across {checks} assertions")
    for error in errors: print(f"- {error}")
    sys.exit(1)
form_summary = '1 allowlisted quote form' if HAS_QUOTE else '0 forms'
print(f"PASS ({parsed.mode}; local only): {len(ROUTES)} full pages + pinned legacy redirect; {checks} assertions plus production-contract checks; 0 broken internal links/fragments; supported resource subset checked; {form_summary}; only hash-allowlisted inline scripts; claims and legal safeguards passed")
