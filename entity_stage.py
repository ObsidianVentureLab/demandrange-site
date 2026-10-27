"""Week-1 SEO entity stage: site-wide locale, Organization/ProfessionalService/
WebSite JSON-LD and the llms.txt / logo.png discovery assets.

Runs last in apply_foundation, after every page body and metadata is final, so
each page node is built from the page's own staged <title>, description and
canonical. All data lives in foundation/entity.json; this module only places it.
Internal URLs stay in pre-clean .html form here; clean_urls rewrites them.
The pinned legacy route is never touched (it is a retained, hashed asset).
"""
from pathlib import Path
from html import unescape
import json
import re
import shutil
from urllib.parse import urlsplit

HERE = Path(__file__).resolve().parent
CONTENT = HERE / 'foundation'
ASSETS = ('llms.txt', 'logo.png')
LEGACY = 'pumps-flow-control.html'
SCRIPT_OPEN = '<script type="application/ld+json" id="dr-entity">\n'


def _one(pattern, text, what, route):
    found = re.findall(pattern, text)
    if len(found) != 1:
        raise ValueError(f'Entity stage: {route}: expected one {what}, found {len(found)}')
    return found[0]


def entity_script(data, route, title, description, canonical):
    site = data['site']
    page = {
        '@type': data['page_types'].get(route, 'WebPage'),
        '@id': canonical + '#webpage', 'url': canonical, 'name': unescape(title),
        'description': unescape(description), 'inLanguage': data['html_lang'],
        'isPartOf': {'@id': data['website']['@id']},
        ('about' if route in data['about_routes'] else 'publisher'): {'@id': data['organization']['@id']},
        'primaryImageOfPage': {'@id': data['organization']['logo']['@id']} if route == 'index.html'
            else {'@type': 'ImageObject', 'url': data['page_image']},
    }
    graph = {'@context': 'https://schema.org', '@graph': [data['organization'], data['website'], page]}
    body = json.dumps(graph, ensure_ascii=False, separators=(',', ':')).replace('</', '<\\/')
    if not canonical.startswith(site + '/'):
        raise ValueError('Entity stage: off-site canonical ' + canonical)
    return SCRIPT_OPEN + body + '\n</script>\n'


def apply_entity(output):
    data = json.loads((CONTENT / 'entity.json').read_text(encoding='utf-8'))
    lang, locale = data['html_lang'], data['og_locale']
    skip = set(data['no_entity_routes'])
    for path in sorted(output.glob('*.html')):
        route = path.name
        if route == LEGACY:
            continue
        text = path.read_text(encoding='utf-8')
        if 'id="dr-entity"' in text or 'og:locale' in text:
            raise ValueError('Entity stage: ' + route + ' already carries entity/locale markup')
        text, n = re.subn(r'<html lang="en"', '<html lang="' + lang + '"', text, count=1)
        if n != 1:
            raise ValueError('Entity stage: ' + route + ': html lang anchor missing')
        site_name = _one(r'<meta property="og:site_name" content="[^"]*">', text, 'og:site_name', route)
        text = text.replace(site_name, site_name + '\n  <meta property="og:locale" content="' + locale + '">', 1)
        if route not in skip:
            title = _one(r'<title>([^<]*)</title>', text, 'title', route)
            description = _one(r'<meta name="description" content="([^"]*)"', text, 'description', route)
            canonical = _one(r'<link rel="canonical" href="([^"]*)"', text, 'canonical', route)
            if text.count('</head>') != 1:
                raise ValueError('Entity stage: ' + route + ': head anchor count')
            text = text.replace('</head>', entity_script(data, route, title, description, canonical) + '</head>', 1)
        path.write_text(text, encoding='utf-8')
    for name in ASSETS:
        shutil.copy2(CONTENT / 'seo' / name, output / name)
    # llms.txt is hand-authored: every same-site link must name a staged page.
    pages = {p.name for p in output.glob('*.html')}
    for url in re.findall(r'https://demandrange\.com[^\s)\]]*', (output / 'llms.txt').read_text(encoding='utf-8')):
        path = urlsplit(url).path.strip('/')
        if path.endswith('.html') or (path and path + '.html' not in pages):
            raise ValueError('Entity stage: llms.txt link has no clean public route: ' + url)
