"""Structured Markdown articles, rendered with the existing foundation shell.
Local human-review candidate only. No changes to quote, legal or claim guards.
"""
from pathlib import Path
import json
import re
import shutil
from html import escape
from urllib.parse import urlsplit
import markdown
import yaml
from bs4 import BeautifulSoup
from foundation_stage import metadata, shared_shell, block, once, page_main

HERE = Path(__file__).resolve().parent
CONTENT = HERE / 'researched-articles'


def article_fragment(record):
    raw = (CONTENT / record['artifact']).read_text(encoding='utf-8')
    _, front, body = raw.split('---', 2)
    meta = yaml.safe_load(front)
    assert meta['intended_route'].lstrip('/') == record['route']
    assert meta['title'] == record['title']
    assert meta['meta_description'] == record['meta_description']
    assert meta['meta_title'] == record['meta_title']
    prose, sources = body.rsplit('## Sources', 1)
    citations = []
    # Source lines first; an optional plain-prose note may follow after a blank
    # line (no links or citation markers). Anything else is still rejected.
    source_block, _, note = sources.strip().partition('\n\n')
    for line in source_block.splitlines():
        m = re.fullmatch(r'\[(\d+)\] (https://\S+) — (.+)', line)
        if m:
            citations.append((m[1], m[2], m[3]))
        elif line.strip():
            raise ValueError('Unsupported source line: ' + line)
    note = note.strip()
    if note and (re.search(r'\[\d+\]|https?://|\]\(|<a\b', note) or re.match(r'\[\d+\] ', note)):
        raise ValueError('Unsupported source note: ' + note)
    ids = {ident for ident, _, _ in citations}
    assert set(re.findall(r'\[(\d+)\]', prose)) == ids
    prose = re.sub(r'\[(\d+)\]', lambda m: '<a href="#source-' + m[1] + '">[' + m[1] + ']</a>', prose)
    # These are editorial checklists, not added form controls.
    prose = prose.replace('- [ ] ', '- ☐ ')
    doc = BeautifulSoup(markdown.markdown(prose, extensions=['tables']), 'html.parser')
    result = BeautifulSoup('<main></main>', 'html.parser')
    main = result.main
    section = result.new_tag('section', id=record['key'] + '-intro')
    eyebrow = result.new_tag('p'); eyebrow.string = record.get('eyebrow', 'Research guide · Source evidence and limits')
    section.append(eyebrow); main.append(section)
    for node in list(doc.contents):
        if getattr(node, 'name', None) == 'h2':
            ident = re.sub(r'[^a-z0-9]+', '-', node.get_text().lower()).strip('-')
            section = result.new_tag('section', id=ident); main.append(section)
        section.append(node.extract())
    for table in result.select('table'):
        for th in table.select('thead th'): th['scope'] = 'col'
    for anchor in result.select('a[href]'):
        href = anchor['href']; parts = urlsplit(href)
        if parts.netloc == 'demandrange.com':
            anchor['href'] = parts.path.lstrip('/') + ('#' + parts.fragment if parts.fragment else '')
        elif href == 'https://creativecommons.org/licenses/by/4.0/':
            # Keep the licence text and make its external destination conform to
            # the existing exact source-list navigation contract.
            anchor['href'] = '#source-licence'
    section = result.new_tag('section', id='sources')
    title = result.new_tag('h2'); title.string = 'Sources'; section.append(title)
    ol = result.new_tag('ol', attrs={'class':'source-list'})
    for ident, url, title in citations + ([('licence', 'https://creativecommons.org/licenses/by/4.0/', 'Creative Commons Attribution 4.0 International licence')] if record.get('include_cc_licence', True) else []):
        li = result.new_tag('li', id='source-' + ident)
        if ident.isdigit(): li['value'] = ident
        a = result.new_tag('a', id='source-link-' + ident, href=url, rel='noopener noreferrer')
        a.string = title; li.append(a); ol.append(li)
    section.append(ol)
    if note:
        for node in list(BeautifulSoup(markdown.markdown(note), 'html.parser').contents):
            section.append(node.extract())
    main.append(section)
    return result


MAX_ARTICLES = 25


def apply_researched_articles(output):
    records = json.loads((CONTENT / 'articles.json').read_text())['articles']
    # Cap, not an exact count: 11 original guides + 4 batch-1 pages + 6
    # SEO/GEO guides (released over two days) + 4 content-batch pages
    # (27 Oct 2026; released one at a time). Exact route coverage is still
    # pinned by production-manifest.json public_files/page_routes.
    assert 1 <= len(records) <= MAX_ARTICLES and len({r['route'] for r in records}) == len(records)
    shell = (output / 'industrial-lead-research.html').read_text()
    for record in records:
        doc = article_fragment(record)
        text = metadata(shell, {'title':record['meta_title'], 'meta_description':record['meta_description']}, record['route'])
        text = shared_shell(block(text, r'<main\b.*?</main>', page_main(record['key'], doc)), record['route'])
        (output / record['route']).write_text(text, encoding='utf-8')
        # Optional pinned downloads that belong to an article (e.g. a CSV);
        # each must also be pinned in production-manifest.json safe_downloads.
        for name in record.get('downloads', []):
            shutil.copy2(HERE / 'foundation' / name, output / name)
    sitemap = output / 'sitemap.xml'
    sitemap.write_text(once(sitemap.read_text(), '</urlset>', ''.join('  <url><loc>https://demandrange.com/' + r['route'] + '</loc></url>\n' for r in records) + '</urlset>'))
