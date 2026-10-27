"""Small fail-closed gates for this static site's supported syntax.
No external-CSS/resource features are needed by the reviewed foundation.
Unsupported features are rejected, not incompletely parsed or called safe.
"""
from pathlib import PurePosixPath
from html.parser import HTMLParser
import re
from urllib.parse import urlsplit, unquote
from bs4 import BeautifulSoup


def need(value, message):
    if not value:
        raise ValueError(message)


def unique_object(pairs):
    out = {}
    for key, value in pairs:
        need(key not in out, 'Duplicate manifest key: ' + key)
        out[key] = value
    return out


def path_name(value):
    need(type(value) is str and bool(re.fullmatch(r'[A-Za-z0-9._/-]+', value)), 'Invalid manifest path')
    p = PurePosixPath(value)
    need(not p.is_absolute() and str(p) == value and '..' not in p.parts and value != '.', 'Noncanonical manifest path')
    return value


def digest_string(value):
    need(type(value) is str and bool(re.fullmatch(r'[0-9a-f]{64}', value)), 'Invalid manifest digest')


def validate_manifest(c):
    need(type(c) is dict, 'Manifest root must be an object')
    need(type(c.get('contract_version')) is int and c['contract_version'] == 1, 'Unsupported production contract version')
    lists = ['public_files','page_routes','sitemap_urls','excluded_source_files','generator_managed_files']
    for key in lists:
        v = c.get(key)
        need(type(v) is list and all(type(a) is str for a in v), 'Invalid manifest list: ' + key)
        need(len(v) == len(set(v)), 'Duplicate manifest entry: ' + key)
        if key != 'sitemap_urls':
            for name in v: path_name(name)
    public, routes = set(c['public_files']), set(c['page_routes'])
    need({'index.html','404.html','request-a-quote.html'} <= routes, 'Required audited route missing')
    legacy = {'pumps-flow-control.html'}
    need({s for s in public if s.endswith('.html')} == routes | legacy and not (routes & legacy), 'Manifest HTML audit coverage mismatch')
    need(all(r.endswith('.html') for r in routes), 'Non-HTML audited route')
    expected_map = {'https://demandrange.com/' + ('' if r == 'index.html' else r) for r in routes if r != '404.html'}
    need(set(c['sitemap_urls']) == expected_map, 'Manifest sitemap/route mismatch')
    need(set(c['generator_managed_files']) <= public, 'Generated files outside public manifest')
    need(not (set(c['excluded_source_files']) & public), 'Excluded source is public')
    for key in ['protected_sources','retained_assets']:
        need(type(c.get(key)) is dict and bool(c[key]), 'Invalid manifest pin map: ' + key)
        for name, sha in c[key].items(): path_name(name); digest_string(sha)
    need(legacy <= set(c['retained_assets']), 'Legacy route must be pinned')
    need(set(c['retained_assets']) <= public, 'Retained pin outside public manifest')
    need({'quote-form/client.js','quote-form/form_schema.json','quote-form/request-a-quote.template.html','quote-form/quote-form.css'} <= set(c['protected_sources']), 'Required quote source pins missing')
    for key in ['quote_endpoint_sha256','quote_output_sha256','quote_inline_script_sha256','proposed_effective_quote_template_sha256','baseline_source_output_bundle_sha256']:
        digest_string(c.get(key))
    need(type(c.get('public_base_sha')) is str and bool(re.fullmatch(r'[0-9a-f]{40}',c['public_base_sha'])), 'Invalid base commit')
    need(type(c.get('versions')) is dict and all(c['versions'].get(k) == '2026-09-11-v1' for k in ['form_version','privacy_version','consent_version']), 'Unreviewed form versions')
    need(type(c.get('safe_downloads')) is dict, 'Invalid download map')
    need(set(c['safe_downloads']) == {n for n in public if n.endswith('.csv')}, 'CSV coverage mismatch')
    from og02_guards import validate_declarations
    validate_declarations(c)
    for name, d in c['safe_downloads'].items():
        path_name(name); need(type(d) is dict, 'Invalid CSV declaration')
        digest_string(d.get('sha256'))
        cols = d.get('columns')
        need(type(cols) is list and bool(cols) and all(type(s) is str and s for s in cols) and len(cols)==len(set(cols)), 'Invalid CSV columns')
        need(type(d.get('data_rows')) is int and d['data_rows'] >= 0, 'Invalid CSV count')

    from reference_policy import REVIEWED_REFERENCES
    policy = c.get('external_reference_policy')
    need(type(policy) is dict and set(policy) == {'routes','source_use_status'}, 'Invalid exact reference policy')
    need(type(policy['source_use_status']) is str and bool(policy['source_use_status']), 'Missing source-use status')
    # Frozen route + section + list + item + anchor + opaque href equality.
    # This permits the reviewed PDF query ONLY at that one navigation target.
    need(policy['routes'] == REVIEWED_REFERENCES, 'Reference policy differs from exact reviewed declarations')
    need(set(policy['routes']) <= routes, 'Reference policy route missing')
    for name,d in c['safe_downloads'].items():
        for key in ['blank_value_column','unique_field_column']:
            if key in d: need(type(d[key]) is str and d[key] in d['columns'], 'Invalid worksheet column rule')


def approved_reference(anchor, route, policy):
    if not policy or anchor.name != 'a': return False
    declaration = policy.get('routes', {}).get(route)
    if not declaration: return False
    target = declaration['anchors'].get(anchor.get('id'))
    if not target or anchor.get('href') != target['href']: return False
    item = anchor.find_parent('li')
    listing = anchor.find_parent(declaration['list_tag'])
    section = anchor.find_parent('section')
    return (item is not None and item.get('id') == target['item_id']
            and listing is not None and item.parent is listing
            and listing.get('class') == [declaration['list_class']]
            and section is not None and section.get('id') == declaration['section_id']
            and listing.find_parent('section') is section
            and anchor.find_parent('main') is not None
            and set(anchor.attrs) == {'id','href','rel'}
            and bool(anchor.get_text(' ', strip=True))
            and anchor.get('rel') == ['noopener','noreferrer'])


def check_css(css):
    # Deliberately strict subset. No CSS URLs/imports/image sources or escape
    # sequences are needed here; do not try to regex-parse arbitrary CSS URLs.
    need('\\' not in css, 'Unsupported CSS escape')
    compact = re.sub(r'/\*.*?\*/', '', css, flags=re.S)
    need(not re.search(r'@\s*import\b|(?:url|(?:-webkit-)?image-set|image|src|expression)\s*\(', compact, re.I), 'Unsupported CSS resource/function')
    need(not re.search(r'(?:^|[;{])\s*(?:behavior|-moz-binding)\s*:', compact, re.I), 'Unsupported CSS binding')


def unique_html_attributes(attrs):
    """Reject browser/parser first-vs-last ambiguity before dict conversion."""
    names = [name.lower() for name, _ in attrs]
    need(len(names) == len(set(names)), 'Duplicate HTML attribute')
    return dict(attrs)


class UniqueAttributeParser(HTMLParser):
    def handle_starttag(self, tag, attrs):
        unique_html_attributes(attrs)
    handle_startendtag = handle_starttag


def check_html_resources(text, root, route, endpoint, reference_policy=None):
    parser = UniqueAttributeParser(convert_charrefs=True)
    parser.feed(text)
    parser.close()
    soup = BeautifulSoup(text, 'html.parser')
    need(not soup.find(['base','object','embed','iframe','frame','frameset','style']), route + ': unsupported resource/navigation element')
    declaration = (reference_policy or {}).get('routes', {}).get(route)
    if declaration:
        sections = soup.find_all('section', id=declaration['section_id'])
        need(len(sections) == 1, route + ': exact reference section missing or duplicated')
        for ident, target in declaration['anchors'].items():
            nodes = soup.find_all(id=ident)
            items = soup.find_all(id=target['item_id'])
            need(len(items) == 1 and len(nodes) == 1 and approved_reference(nodes[0], route, reference_policy), route + ': exact reference anchor missing or changed')
    for e in soup.find_all():
        if e.name == 'meta':
            need(not e.has_attr('http-equiv'), route + ': unexpected meta directive')
        if e.has_attr('style'):
            check_css(str(e['style']))
        for attr in ['srcset','imagesrcset','srcdoc','poster','background','ping','manifest','formaction','xlink:href','data','codebase','archive']:
            need(not e.has_attr(attr), route + ': unsupported resource attribute ' + attr)
        if e.has_attr('action'):
            need(e.name == 'form' and route == 'request-a-quote.html' and e['action'] == endpoint, route + ': unsupported form action')
        if e.has_attr('href'):
            need(e.name in {'a','link'}, route + ': unsupported href element')
            href = str(e['href'])
            need('\\' not in href and not any(ord(c) < 32 for c in href), route + ': unsafe URL syntax')
            h = urlsplit(href)
            if e.name == 'a':
                need((not h.scheme and not h.netloc) or (h.scheme == 'mailto' and h.path == 'partners@demandrange.com') or href == 'https://www.dataprotection.ie/' or approved_reference(e, route, reference_policy), route + ': unsupported navigation URL')
        for key, value in e.attrs.items():
            if re.search(r'url\s*\(', str(value), re.I):
                local = re.fullmatch(r'url\(#([A-Za-z0-9_-]+)\)', str(value))
                need(key in {'filter','fill','stroke','clip-path','mask'} and local is not None and soup.find(id=local.group(1)) is not None, route + ': unsupported attribute resource function')
        if e.has_attr('src'):
            need(e.name == 'img', route + ': unsupported src element')
        if e.name == 'link':
            rel = e.get('rel') or []
            need(rel in [['canonical'],['stylesheet'],['icon']], route + ': unsupported link relation')
        url = e.get('src') or (e.get('href') if e.name == 'link' and e.get('rel') != ['canonical'] else None)
        if url is not None:
            need(type(url) is str, route + ': malformed URL attribute')
            url = str(url)
            parts = urlsplit(url)
            need(not parts.scheme and not parts.netloc and '\\' not in url and not parts.query, route + ': nonlocal resource')
            name = unquote(parts.path).lstrip('/')
            path_name(name)
            need((root / name).is_file(), route + ': missing local resource')
