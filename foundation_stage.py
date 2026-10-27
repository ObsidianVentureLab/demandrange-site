"""Late, generator-managed foundation stage. No writes outside the staged tree.
Legacy render/quote-privacy replacements run first, preserving their anchors.
Only markup outside the commissioned quote controls/scripts is transformed.
"""
from pathlib import Path
from html import escape
import json
import re
import shutil
from bs4 import BeautifulSoup

HERE = Path(__file__).resolve().parent
CONTENT = HERE / 'foundation'
DOWNLOADS = ('account-research-template.csv', 'account-research-field-dictionary.csv', 'account-research-fictional-examples.csv')
NEW_ROUTES = ('industrial-lead-research.html', 'sample-account-research.html')


def once(text, old, new):
    if text.count(old) != 1:
        raise ValueError('Foundation anchor count: ' + old[:100])
    return text.replace(old, new, 1)


def block(text, pattern, replacement):
    text, n = re.subn(pattern, lambda m: replacement(m) if callable(replacement) else replacement, text, flags=re.S)
    if n != 1:
        raise ValueError('Foundation block count: ' + pattern)
    return text


def inner(node):
    return ''.join(map(str, node.contents))


def metadata(text, data, route):
    text = block(text, r'<title>.*?</title>', '<title>' + escape(data['title']) + '</title>')
    for key, value in [('description', data['meta_description']), ('og:title', data['title']), ('og:description', data['meta_description']), ('twitter:title', data['title']), ('twitter:description', data['meta_description'])]:
        pattern = r'<meta (?:name|property)="' + key + r'" content="[^"]*"\s*/?>'
        if re.search(pattern, text):
            attr = 'property' if key.startswith('og:') else 'name'
            text = block(text, pattern, '<meta ' + attr + '="' + key + '" content="' + escape(value, quote=True) + '">')
    url = 'https://demandrange.com/' + ('' if route == 'index.html' else route)
    text = block(text, r'<link rel="canonical" href="[^"]*"\s*/?>', '<link rel="canonical" href="' + url + '">')
    text = re.sub(r'(<meta property="og:url" content=")[^"]*', lambda m: m[1] + url, text)
    return text


def shared_shell(text, route):
    d = json.loads((CONTENT / 'shared-copy.json').read_text())
    prefix = '/' if route == '404.html' else ''
    def links(items):
        return ''.join('<a href="' + prefix + x['href'] + '"' + (' aria-current="page"' if x['href'] == route else '') + '>' + escape(x['text']) + '</a>' for x in items)
    text = block(text, r'(<div class="meta-strip"(?: role="region" aria-label="Site overview")?><div class="wrap">).*?(</div></div>)', lambda m: m[1] + '<span class="led">' + d['top_strip'][0] + '</span><span>' + d['top_strip'][1] + '</span>' + m[2])
    text = text.replace('<div class="meta-strip">', '<div class="meta-strip" role="region" aria-label="Site overview">')
    text = block(text, r'(<span class="brand-text">Demand Range<small>).*?(</small>)', lambda m: m[1] + d['wordmark_descriptor'] + m[2])
    brand_name = escape('Demand Range—' + d['wordmark_descriptor'] + ' home', quote=True)
    text = block(text, r'(<a class="brand" href="/?index\.html" aria-label=")(?:Demand Range home|' + re.escape(brand_name) + r')(">)', lambda m: m[1] + brand_name + m[2])
    text = block(text, r'(<nav class="primary-nav"[^>]*>).*?(</nav>)', lambda m: m[1] + links(d['primary_navigation']) + m[2])
    mobile = d['primary_navigation'] + [{'text':'Contact','href':'contact.html'}, d['primary_cta']]
    text = block(text, r'<summary aria-label="(?:Open site navigation|Menu)">', '<summary aria-label="Menu">')
    text = block(text, r'(<nav class="menu-panel"[^>]*>).*?(</nav>)', lambda m: m[1] + links(mobile) + m[2])
    text = block(text, r'<a class="btn btn-primary header-cta"[^>]*>.*?</a>', '<a class="btn btn-primary header-cta" href="' + ('#quote-form' if route == 'request-a-quote.html' else prefix + 'request-a-quote.html') + '">Request a quote</a>')
    text = block(text, r'(<div class="footer-brand">.*?<p>).*?(</p></div>)', lambda m: m[1] + escape(d['footer_description']) + m[2])
    cols = ''.join('<div class="footer-col"><h2>' + escape(g['heading']) + '</h2>' + links(g['links']) + ('<a href="mailto:partners@demandrange.com">partners@demandrange.com</a>' if i == 1 else '') + '</div>' for i,g in enumerate(d['footer_groups']))
    text = block(text, r'<div class="footer-col">.*?</div>\s*<div class="footer-col">.*?</div>\s*<div class="footer-col">.*?</div>', cols)
    text = block(text, r'(<div class="footer-bottom"><span>.*?</span><span>).*?(</span></div>)', lambda m: m[1] + escape(d['footer_strapline']) + m[2])
    return text


def fragment(key):
    return BeautifulSoup((CONTENT / (key + '.fragment.html')).read_text(), 'html.parser')


def style_body(node):
    # Transform semantic definitions into an editorial evidence ledger.
    for dl in node.select('dl'):
        dl['class'] = ['research-ledger']
    for table in node.select('table'):
        wrap = BeautifulSoup('<div class="table-wrap" tabindex="0" role="region" aria-label="Data table; scroll horizontally to view all columns"></div>', 'html.parser').div
        table.wrap(wrap)
    for a in node.select('a[href$=".csv"]'):
        a['download'] = ''
    # Group the deliberately paired classes and evidence layers, not all prose.
    headings = node.find_all('h3', recursive=False)
    if len(headings) in (2,3) and node.get('id') in {'lead-mix','classes','evidence','sectors','routes'}:
        grid = BeautifulSoup('<div class="research-cards"></div>', 'html.parser').div
        first = headings[0]
        first.insert_before(grid)
        for heading in headings:
            card = BeautifulSoup('<div class="research-card"></div>', 'html.parser').div
            following = heading.find_next_sibling()
            card.append(heading.extract())
            # Only the first description belongs to a card; subsequent caveats stay full-width.
            if following and following.name == 'p':
                card.append(following.extract())
            grid.append(card)
    return node


def page_main(key, document=None):
    doc = fragment(key) if document is None else document
    sections = doc.select('section')
    hero = sections[0]
    eyebrow = hero.find('p').extract()
    title = hero.h1.extract()
    for p in hero.find_all('p', recursive=False):
        p['class'] = ['lede' if p == hero.find('p') else 'research-intro-note']
        if p.find('a'):
            p['class'] = ['actions']
            for child in list(p.children):
                if getattr(child, 'name', None) != 'a': child.extract()
            for i,a in enumerate(p.find_all('a')):
                a['class'] = ['btn', 'btn-primary' if i == 0 else 'btn-secondary']
    for a in hero.select('a[href$=".csv"]'): a['download'] = ''
    out = '<main id="main" class="foundation-main"><section class="foundation-hero" id="' + hero['id'] + '"><div class="wrap foundation-hero-grid"><div><p class="label label-accent">' + inner(eyebrow) + '</p>' + str(title) + '</div><div class="foundation-intro">' + inner(hero) + '</div></div></section>'
    short = {'lead-mix':'Research classes','research-brief':'The brief','examples':'Examples','scope':'Written scope','enquiry':'Next step','example-brief':'Example brief','accepted-account':'Account fit','paired-signal':'Project signal','rejected-account':'Rejection','template':'Downloads','next-step':'Next step'}
    nav = ''.join('<a href="#' + s['id'] + '">' + escape(short.get(s['id'], s['id'].replace('-',' ').capitalize())) + '</a>' for s in sections[1:])
    out += '<div class="wrap"><nav class="foundation-jump" aria-label="On this page">' + nav + '</nav></div>'
    for n,section in enumerate(sections[1:],1):
        heading = section.h2.extract()
        style_body(section)
        out += '<section class="foundation-section" id="' + section['id'] + '"><div class="wrap foundation-grid"><div class="foundation-heading"><span class="label">' + f'{n:02d} / ' + escape(short.get(section['id'], section['id'].replace('-',' '))) + '</span>' + str(heading) + '</div><div class="foundation-prose">' + inner(section) + '</div></div></section>'
    return out + '</main>'


def quote_template(text):
    """Compose copy-only template before marker substitution; controls stay raw."""
    data = next(p for p in json.loads((CONTENT/'foundation-copy.json').read_text())['pages'] if p['key'] == 'request-a-quote')
    doc = fragment('request-a-quote')
    intro = doc.select_one('#request-a-quote-intro')
    eyebrow = intro.p.extract(); title = intro.h1.extract()
    paragraphs = intro.find_all('p')
    paragraphs[0]['class'] = ['lede']
    hero = '<section class="quote-hero"><div class="wrap quote-hero-grid"><div><span class="label">' + inner(eyebrow) + '</span>' + str(title) + inner(intro) + '</div><div class="hero-process">'
    next_section = doc.select_one('#quote-next')
    hero += str(next_section.h2) + '<ol>' + ''.join('<li><b>' + f'{i:02d}' + '</b><span>' + inner(li) + '</span></li>' for i,li in enumerate(next_section.select('li'),1)) + '</ol></div></div></section>'
    text = block(text, r'<section class="quote-hero">.*?</section>', hero)
    mix = doc.select_one('#quote-mix')
    headings = mix.select('h3')
    cards = ''.join('<div class="mix-item"><span>Target mix</span><strong>' + inner(h) + '</strong>' + str(h.find_next_sibling('p')) + '</div>' for h in headings)
    last = mix.find_all('p')[-1]
    cards += '<div class="mix-item"><span>Important boundary</span><strong>' + inner(mix.h2) + '</strong>' + str(last) + '</div>'
    text = block(text, r'<section class="mix-band">.*?</section>', '<section class="mix-band"><div class="wrap mix-grid">' + cards + '</div></section>')
    scope = doc.select_one('#quote-scope'); scope['class'] = ['quote-scope-clarification']
    text = once(text, '<section class="quote-section" id="quote-form">', '<section class="quote-scope-band"><div class="wrap">' + str(scope) + '</div></section>\n<section class="quote-section" id="quote-form">')
    return shared_shell(metadata(text, data, 'request-a-quote.html'), 'request-a-quote.html')


def ancillary(text, route):
    if route == '404.html':
        text = once(text, 'Demand Range connects industrial suppliers to the decision-makers behind upcoming facility and infrastructure projects.', 'The requested page could not be found on the Demand Range website.')
        text = once(text, 'The pages below cover everything on this site.', 'The pages below can help you return to the site.')
    patches = json.loads((CONTENT/'alignment-patches.json').read_text())['patches']
    for patch in patches:
        if patch['route'].lstrip('/') != route: continue
        text = metadata(text, patch, route)
        main = BeautifulSoup(re.search(r'<main\b.*?</main>', text, re.S)[0], 'html.parser')
        if patch['h1_action'].startswith('Replace'): main.h1.string = patch['h1']
        for item in patch['replacements']:
            matches = [e for e in main.find_all(['p','a','h2','div']) if item['old'] in e.get_text(' ',strip=True)]
            # The exact anchor is the smallest matching element.
            matches = [e for e in matches if not any(x in matches for x in e.find_all(['p','a','h2','div']))]
            if len(matches) != 1: raise ValueError('Ancillary anchor: ' + item['old'])
            old = matches[0]; new = BeautifulSoup(item['html'], 'html.parser')
            if item['action'] == 'insert_after_not_replace':
                for el in reversed(list(new.contents)): old.insert_after(el)
            else:
                first = new.find()
                if old.get('class'): first['class'] = old['class']
                old.replace_with(new)
        text = block(text, r'<main\b.*?</main>', str(main))
    return text


def legal_facts(text, route):
    descriptor = 'a B2B brand providing analyst-led Industrial Opportunity Intelligence for suppliers of industrial equipment, technology and services.'
    aligned = 'a B2B brand providing analyst-led industrial lead research and market intelligence for suppliers of industrial equipment, technology and services.'
    if route in {'terms.html','privacy.html'}: text = once(text, descriptor, aligned)
    if route in {'terms.html', 'cookies.html'}:
        text = once(text, 'Last updated: 5 September 2026', 'Last updated: 30 September 2026')
    if route == 'terms.html':
        text = once(text, 'The website has no transmitting form, and the first email route is not intended for sensitive personal data, special-category data, live client files, suppression lists, passwords, API keys or confidential material.', 'The quote-request page transmits the information you choose to submit to a restricted business intake record. Do not provide sensitive personal data, passwords, credentials, confidential customer files, suppression lists or live campaign data. The first email route is not intended for sensitive personal data, special-category data, live client files, suppression lists, passwords, API keys or confidential material.')
        # Purpose, liability, governing law, legal bases, retention and dates remain unchanged.
    if route == 'cookies.html':
        text = once(text, 'a small inline script for the light/dark theme toggle.', 'inline scripts for the light/dark theme toggle and the quote-request form. The quote client validates entries, sets a per-page submission token and load time in form fields, and reads the optional <code>asset_ref</code> and <code>campaign_ref</code> URL values into hidden fields. It does not write browser storage.')
        text = once(text, 'The pages do not request external fonts, images, scripts, analytics or embedded forms.', 'The pages do not request external fonts, images, scripts or analytics. The quote form is part of the page, not an embedded third-party form. On a valid submission, the browser sends the information you choose to submit to the configured Google Workspace form-processing endpoint; see the <a href="privacy.html">Privacy Notice</a> for enquiry processing.')
        text = once(text, 'nothing is transmitted to Demand Range or any third party.', 'the theme preference is not transmitted to Demand Range or any third party. This theme behaviour is separate from submitting a quote request.')
        text = once(text, 'Any future analytics, advertising, embedded forms, chat, session replay or other non-essential tracking', 'Any future analytics, advertising, third-party embedded forms, chat, session replay or other non-essential tracking')
    return text


def apply_foundation(output):
    pages = json.loads((CONTENT/'foundation-copy.json').read_text())['pages']
    shell = (output/'index.html').read_text()
    for data in pages:
        if data['key'] == 'request-a-quote': continue
        route = 'index.html' if data['route'] == '/' else data['route'].lstrip('/')
        text = (output/route).read_text() if (output/route).exists() else shell
        text = metadata(text, data, route)
        text = block(text, r'<main\b.*?</main>', page_main(data['key']))
        (output/route).write_text(text)
    for path in sorted(output.glob('*.html')):
        if path.name in {'pumps-flow-control.html','request-a-quote.html'}: continue
        text = path.read_text()
        text = ancillary(text, path.name)
        text = legal_facts(text, path.name)
        text = shared_shell(text, path.name)
        (path).write_text(text)
    for filename in DOWNLOADS: shutil.copy2(CONTENT/filename, output/filename)
    path = output/'sitemap.xml'
    path.write_text(once(path.read_text(), '</urlset>', ''.join('  <url><loc>https://demandrange.com/' + route + '</loc></url>\n' for route in NEW_ROUTES) + '</urlset>'))
    path = output/'styles.css'
    path.write_text(path.read_text() + '\n' + (CONTENT/'foundation.css').read_text())
    from c04_stage import apply_c04
    apply_c04(output)
    from c05_stage import apply_c05
    apply_c05(output)
    from resources_stage import apply_resources
    apply_resources(output)
    from og02_stage import apply_og02
    apply_og02(output)
    from og07_stage import apply_og07
    apply_og07(output)
    from volume_stage import apply_volume
    apply_volume(output)
    from researched_articles_stage import apply_researched_articles
    apply_researched_articles(output)
