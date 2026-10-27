"""Final lossless URL-only stage; physical files and original guards stay intact.

Run only AFTER the full legacy production contract and qa_static.py pass.
The raw clean tree is independently checked and compared byte-for-byte with
this explicit transform of that validated legacy tree. No inverse laundering.
"""
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlsplit
import hashlib
import html
import json
import re
import xml.etree.ElementTree as ET
from bs4 import BeautifulSoup
from production_contract import file_set, require
from site_guards import unique_html_attributes

ORIGIN = 'https://demandrange.com'
LEGACY = 'pumps-flow-control.html'
ATTR = re.compile(r'''([^\s=<>/'"]+)\s*=\s*(?:"([^"]*)"|'([^']*)'|([^\s>]+))''')
JSON_STRING = re.compile(r'"(?:\\.|[^"\\])*"')


def route_map(names):
    routes = {name: '/' if name == 'index.html' else '/' + name[:-5]
              for name in names if name.endswith('.html')}
    require(all('/' not in name for name in routes), 'Only reviewed flat HTML routes supported')
    require(len(set(routes.values())) == len(routes), 'Clean alias collision')
    return routes


def clean_url(value, routes):
    """Change only known local HTML paths; retain opaque query/fragment bytes."""
    path, *tail = re.split(r'(?=[?#])', value, maxsplit=1)
    suffix = tail[0] if tail else ''
    if path.startswith(ORIGIN + '/'):
        prefix, name = ORIGIN, path[len(ORIGIN) + 1:]
    elif path.startswith('//') or urlsplit(path).scheme:
        return value  # External sources are opaque, including external .html.
    else:
        prefix, name = ('', path[1:]) if path.startswith('/') else (None, path)
    if name not in routes:
        return value
    target = routes[name]
    if prefix is None and target != '/':
        target = target[1:]
    return (prefix or '') + target + suffix


def apply_edits(text, edits):
    """Patch exact lexical spans without HTML/JSON/XML reserialization."""
    result, cursor, offset = [], 0, 0
    for edit in sorted(edits, key=lambda e: e['start']):
        a, b = edit['start'], edit['end']
        require(a >= cursor and text[a:b] == edit['old'], 'Overlapping or stale URL edit')
        result.extend([text[cursor:a], edit['new']])
        edit['output_start'] = a + offset
        edit['output_end'] = a + offset + len(edit['new'])
        offset += len(edit['new']) - len(edit['old'])
        cursor = b
    result.append(text[cursor:])
    output = ''.join(result)
    inverse = output
    for edit in sorted(edits, key=lambda e: e['output_start'], reverse=True):
        a, b = edit['output_start'], edit['output_end']
        require(inverse[a:b] == edit['new'], 'Inverse URL preimage mismatch')
        inverse = inverse[:a] + edit['old'] + inverse[b:]
    require(inverse == text, 'URL transform did not invert exactly')
    return output


class URLSpans(HTMLParser):
    def __init__(self, text, name, routes):
        super().__init__(convert_charrefs=False)
        self.text, self.name, self.routes = text, name, routes
        self.lines = [0] + [m.end() for m in re.finditer('\n', text)]
        self.edits, self.json_start = [], None

    def position(self):
        line, col = self.getpos()
        return self.lines[line - 1] + col

    def add(self, start, end, new, kind):
        old = self.text[start:end]
        if old != new:
            self.edits.append(dict(start=start, end=end, old=old, new=new, kind=kind))

    def handle_starttag(self, tag, attrs):
        attrs = unique_html_attributes(attrs)
        raw, pos = self.get_starttag_text(), self.position()
        selected = set()
        if tag == 'a' and 'download' not in attrs:
            selected.add('href')
        if tag == 'link' and set((attrs.get('rel') or '').lower().split()) & {'canonical', 'alternate'}:
            selected.add('href')
        if tag == 'meta' and (attrs.get('property') or attrs.get('name')) in {'og:url', 'twitter:url'}:
            selected.add('content')
        refresh = tag == 'meta' and (attrs.get('http-equiv') or '').lower() == 'refresh'
        if refresh:
            require(self.name == LEGACY, 'Unexpected redirect outside pinned legacy route')
            selected.add('content')
        for match in ATTR.finditer(raw):
            if match[1].lower() not in selected:
                continue
            group = next(i for i in (2, 3, 4) if match[i] is not None)
            start, end = match.span(group)
            value = match[group]
            if refresh:
                target = re.fullmatch(r'(0; url=)([^\s]+)', value)
                require(target is not None, 'Unexpected legacy refresh syntax')
                new = target[1] + clean_url(target[2], self.routes)
            else:
                new = clean_url(value, self.routes)
            self.add(pos + start, pos + end, new, tag + ':' + match[1].lower())
        if tag == 'script' and attrs.get('type') == 'application/ld+json':
            self.json_start = pos + len(raw)

    handle_startendtag = handle_starttag

    def handle_endtag(self, tag):
        if tag != 'script' or self.json_start is None:
            return
        start, end = self.json_start, self.position()
        text = self.text[start:end]
        json.loads(text)  # Do not touch malformed structured data.
        for token in JSON_STRING.finditer(text):
            if text[token.end():].lstrip().startswith(':'):
                continue  # Object keys are never URLs.
            value = json.loads(token[0])
            new = clean_url(value, self.routes) if value.startswith(ORIGIN + '/') else value
            if new != value:
                self.add(start + token.start(), start + token.end(),
                         json.dumps(new, ensure_ascii=False), 'jsonld:url')
        self.json_start = None


def transform(name, data, routes):
    if name.endswith('.html'):
        text = data.decode('utf-8')
        parser = URLSpans(text, name, routes)
        parser.feed(text)
        parser.close()
        edits = parser.edits
    elif name == 'sitemap.xml':
        text = data.decode('utf-8')
        ET.fromstring(text)
        edits = []
        for match in re.finditer(r'<loc>([^<]+)</loc>', text):
            new = clean_url(match[1], routes)
            if new != match[1]:
                edits.append(dict(start=match.start(1), end=match.end(1),
                                  old=match[1], new=new, kind='sitemap:loc'))
    else:
        return data, []
    return apply_edits(text, edits).encode('utf-8'), edits


def validate_raw(root, contract):
    """Read final raw bytes; resolve clean aliases, IDs, canonical/OG and sitemap."""
    root = Path(root)
    names = file_set(root)
    require(names == set(contract['public_files']), 'Raw clean public inventory mismatch')
    routes = route_map(names)
    reverse = {value: name for name, value in routes.items()}
    soups = {name: BeautifulSoup((root / name).read_bytes(), 'html.parser') for name in routes}
    ids = {name: {node['id'] for node in soup.select('[id]')} for name, soup in soups.items()}
    checked = 0

    def resolve(value, current, page_only=False):
        nonlocal checked
        require(isinstance(value, str) and '\\' not in value and not any(c.isspace() or ord(c) < 32 for c in value), 'Unsafe raw URL')
        parts = urlsplit(value)
        if parts.scheme or parts.netloc:
            if parts.hostname != 'demandrange.com':
                return None  # Original QA + exact byte-delta comparison bind external URLs.
            require(parts.scheme == 'https' and parts.netloc == 'demandrange.com', 'Wrong internal URL scheme/authority')
        path = parts.path
        require(not path.startswith('//') and '//' not in path, 'Double slash in internal path')
        require(unquote(path) == path and not any(p in {'.', '..'} for p in path.split('/')), 'Encoded/dot internal alias')
        require(not path.endswith('.html'), 'Raw .html public reference remains')
        if not path:
            target = current
        elif path in reverse:
            target = reverse[path]
        elif '/' + path in reverse:
            target = reverse['/' + path]
        else:
            target = path.lstrip('/')
            require(not page_only and target in names and not target.endswith('.html'), 'Missing native alias/target: ' + value)
        require(target in names, 'Missing target: ' + value)
        if parts.fragment and target in ids:
            require(unquote(parts.fragment) in ids[target], 'Missing fragment: ' + value)
        checked += 1
        return target

    structured_count = 0
    for name, soup in soups.items():
        text = (root / name).read_text(encoding='utf-8')
        parser = URLSpans(text, name, routes)
        parser.feed(text)
        parser.close()
        require(not parser.edits, name + ': clean transform must be idempotent')
        canonical = soup.select('link[rel="canonical"]')
        expected = ORIGIN + (routes['markets.html'] if name == LEGACY else routes[name])
        if name == '404.html':
            require(not canonical, '404 must have no canonical')
            require(soup.select_one('meta[name="robots"]')['content'] == 'noindex', '404 noindex lost')
        else:
            require(len(canonical) == 1 and canonical[0].get('href') == expected, name + ': alias/canonical mismatch')
        # The recovery page deliberately identifies the site root socially,
        # but has no canonical of its own; retain that existing contract.
        social_expected = ORIGIN + '/' if name == '404.html' else expected
        for meta in soup.select('meta[property="og:url"],meta[name="twitter:url"]'):
            require(meta.get('content') == social_expected, name + ': social URL mismatch')
            resolve(meta['content'], name, True)
        for node in soup.select('[href], [src]'):
            value = node.get('href') if node.has_attr('href') else node['src']
            resolve(value, name, node.name == 'link' and 'canonical' in node.get('rel', []))
        for script in soup.select('script[type="application/ld+json"]'):
            structured_count += 1
            def walk(value, key=None):
                if isinstance(value, dict):
                    for child_key, child in value.items(): walk(child, child_key)
                elif isinstance(value, list):
                    for child in value: walk(child, key)
                elif isinstance(value, str) and urlsplit(value).hostname == 'demandrange.com':
                    # JSON-LD @id values are node identifiers (#organization,
                    # #webpage, #service), not HTML anchors: the page part must
                    # still resolve, but the fragment need not be an element id.
                    resolve(value.split('#', 1)[0] if key == '@id' else value, name)
            walk(json.loads(script.get_text()))
        refresh = soup.select('meta[http-equiv="refresh"]')
        if name == LEGACY:
            require(len(refresh) == 1 and refresh[0]['content'] == '0; url=markets', 'Legacy refresh target changed')
            require(soup.select_one('meta[name="robots"]')['content'] == 'noindex', 'Legacy noindex lost')
            require(resolve('markets', name, True) == 'markets.html', 'Legacy target unresolved')
        else:
            require(not refresh, 'Unknown redirect introduced')
        if name == '404.html':
            for node in soup.select('[href]'):
                value = node['href']
                if not urlsplit(value).scheme and not value.startswith('#'):
                    require(value.startswith('/'), 'Nested 404 navigation must remain root-relative')
    locations = [node.text for node in ET.parse(root / 'sitemap.xml').findall('{*}url/{*}loc')]
    expected = {ORIGIN + routes[name] for name in routes if name not in {'404.html', LEGACY}}
    require(set(locations) == expected and len(locations) == len(expected), 'Clean sitemap membership/uniqueness mismatch')
    for value in locations:
        resolve(value, 'index.html', True)
    return dict(html_files=len(routes), sitemap_urls=len(locations), resolved_internal_references=checked,
                structured_data_blocks=structured_count, unknown_redirects=0, physical_files=len(names))


def validate_delta(root, baseline, contract):
    """No arbitrary candidate change can hide behind URL normalization."""
    root, baseline = Path(root), Path(baseline)
    names = file_set(baseline)
    require(file_set(root) == names == set(contract['public_files']), 'URL-only file inventory differs')
    routes, rows = route_map(names), []
    for name in sorted(names):
        before, actual = (baseline / name).read_bytes(), (root / name).read_bytes()
        expected, edits = transform(name, before, routes)
        require(actual == expected, 'Non-URL or incorrect URL delta: ' + name)
        rows.append(dict(path=name, baseline_sha256=hashlib.sha256(before).hexdigest(),
                         candidate_sha256=hashlib.sha256(actual).hexdigest(), edits=edits))
    return dict(raw=validate_raw(root, contract), changed_files=sum(bool(r['edits']) for r in rows),
                url_edits=sum(len(r['edits']) for r in rows), inverse_byte_equality=True, files=rows)


def apply_clean_urls(root, baseline, contract):
    routes = route_map(file_set(baseline))
    for name in sorted(file_set(baseline)):
        before = (baseline / name).read_bytes()
        after, _ = transform(name, before, routes)
        require((root / name).read_bytes() == before, 'Pre-transform staged bytes drift: ' + name)
        if after != before:
            (root / name).write_bytes(after)
    return validate_delta(root, baseline, contract)
