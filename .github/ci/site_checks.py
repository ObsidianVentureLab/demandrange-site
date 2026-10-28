"""Output-only checks for the built Demand Range site (this repo holds built output only).

    python -B .github/ci/site_checks.py [site-root]      (default: repo root)

Stdlib only, read-only. Exit 1 on any failure. Checks:
  1. HTML: every page parses, starts with <!doctype html>, has <html lang>, exactly one
     <title>, at most one canonical, no duplicate id attributes.
  2. Internal links: every href/src that points inside the site (relative, root-relative or
     https://demandrange.com/...) resolves to a file in the output, using clean-URL mapping
     ('about' -> about.html, '/' -> index.html), and any #fragment exists as an id/name on the
     target page. Links to the retired redirect stubs are failures.
  3. sitemap.xml / llms.txt / robots.txt: every sitemap <loc> and every demandrange.com link in
     llms.txt resolves; the sitemap lists exactly the indexable pages (no noindex pages, no stubs,
     no 404); canonical of each sitemap page equals its <loc>; robots.txt points at the sitemap.
  4. Brand: no 'Demand.Range' variants (DemandRange, Demand-Range, Demand.Range, Demand_Range)
     in any text file or .xlsx member.
  5. Retired stubs: the 3 meta-refresh stub files exist, are noindex and point at their targets.
  6. Served-surface guard: outside .github/ no tooling files (.py/.yml/.yaml/.md/.sh/.ipynb)
     and no dot-directories other than .well-known (GitHub Pages serves dot-dirs; only .git
     and .github are excluded from the deployed site).
F15 ([data-f15] = 0, no F15-REVIEW-LINE) is checked separately by qa_post.py (strict, bs4).
"""
import re
import sys
import zipfile
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlsplit, unquote

SITE = 'https://demandrange.com'
STUBS = {
    'pumps-flow-control.html': 'markets',
    'irish-prtr-industrial-account-research.html': 'irish-environmental-register-evidence#prtr-returns',
    'campaign-activation.html': 'methodology#what-is-out-of-scope',
}
TEXT_EXT = {'.html', '.txt', '.csv', '.json', '.xml', '.css', '.svg', '.js', ''}
TOOLING_EXT = {'.py', '.yml', '.yaml', '.md', '.sh', '.ipynb'}
BRAND_BAD = re.compile(r'Demand(?:[._\-/\u00b7]|)Range|DEMAND(?:[._\-/\u00b7]|)RANGE')
SKIP_SCHEMES = ('mailto:', 'tel:', 'javascript:', 'data:')


class Page(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.ids, self.dup_ids, self.links = set(), set(), []
        self.titles = self.canonicals = 0
        self.canonical = self.lang = self.refresh = None
        self.noindex = False

    def handle_starttag(self, tag, attrs):
        a = {k: (v or '') for k, v in attrs}
        for key in ('id', 'name') if tag in ('a',) else ('id',):
            if a.get(key):
                if key == 'id' and a[key] in self.ids:
                    self.dup_ids.add(a[key])
                self.ids.add(a[key])
        if tag == 'html':
            self.lang = a.get('lang')
        elif tag == 'title':
            self.titles += 1
        elif tag == 'link' and 'canonical' in a.get('rel', '').split():
            self.canonicals += 1
            self.canonical = a.get('href')
        elif tag == 'meta':
            if a.get('name', '').lower() == 'robots' and 'noindex' in a.get('content', '').lower():
                self.noindex = True
            if a.get('http-equiv', '').lower() == 'refresh':
                self.refresh = a.get('content', '')
        for attr in ('href', 'src'):
            if a.get(attr) and not (tag == 'link' and 'canonical' in a.get('rel', '').split()):
                if not (tag == 'link' and a.get('rel') in ('preconnect', 'dns-prefetch')):
                    self.links.append(a[attr])


def resolve(root, files, base_rel, url):
    """Return (target_rel or None, fragment) for an internal URL; ('EXTERNAL', None) otherwise."""
    if url.startswith(SKIP_SCHEMES):
        return 'EXTERNAL', None
    if url.startswith('#'):
        return base_rel, url[1:]
    parts = urlsplit(url)
    if parts.scheme or parts.netloc:
        if parts.netloc.lower() not in ('demandrange.com', 'www.demandrange.com'):
            return 'EXTERNAL', None
        path = parts.path or '/'
    else:
        path = parts.path
        if not path.startswith('/'):
            base_dir = base_rel.rsplit('/', 1)[0] + '/' if '/' in base_rel else ''
            path = '/' + base_dir + path
    path = unquote(path).lstrip('/')
    if path == '' or path.endswith('/'):
        path += 'index.html'
    for cand in (path, path + '.html'):
        if cand in files:
            return cand, parts.fragment or None
    return None, parts.fragment


def main(argv):
    root = Path(argv[1] if len(argv) > 1 else '.').resolve()
    fails = []
    files = {}
    for p in root.rglob('*'):
        rel = p.relative_to(root).as_posix()
        top = rel.split('/')[0]
        if top in ('.git', '.github') or not p.is_file():  # .git may be a dir or a file (worktree/submodule)
            continue
        files[rel] = p
    if 'index.html' not in files:
        raise SystemExit(f'site_checks: no index.html under {root}')

    # 6. served-surface guard
    for rel in files:
        top = rel.split('/')[0]
        if top.startswith('.') and top not in ('.well-known', '.nojekyll'):
            fails.append(f'{rel}: dot-path outside .github/ would be publicly served')
        if Path(rel).suffix.lower() in TOOLING_EXT:
            fails.append(f'{rel}: tooling file outside .github/ would be publicly served')

    # 1. parse pages
    pages = {}
    for rel in sorted(r for r in files if r.endswith('.html')):
        text = files[rel].read_text(encoding='utf-8')
        pg = Page()
        try:
            pg.feed(text)
            pg.close()
        except Exception as e:  # html.parser is lenient; this is a hard parse error
            fails.append(f'{rel}: parse error {e}')
            continue
        pages[rel] = (pg, text)
        if not text.lstrip().lower().startswith('<!doctype html>'):
            fails.append(f'{rel}: missing <!doctype html>')
        if not pg.lang:
            fails.append(f'{rel}: <html> has no lang')
        if pg.titles != 1:
            fails.append(f'{rel}: {pg.titles} <title> elements (must be 1)')
        if pg.canonicals > 1:
            fails.append(f'{rel}: {pg.canonicals} canonical links')
        if pg.dup_ids:
            fails.append(f'{rel}: duplicate ids {sorted(pg.dup_ids)[:5]}')

    # 2. internal links + fragments
    nlinks = 0
    for rel, (pg, _) in pages.items():
        for url in pg.links:
            target, frag = resolve(root, files, rel, url)
            if target == 'EXTERNAL':
                continue
            nlinks += 1
            if target is None:
                fails.append(f'{rel}: broken internal link {url!r}')
            elif target in STUBS and rel not in STUBS:
                fails.append(f'{rel}: links to retired redirect stub {url!r}')
            elif frag and target.endswith('.html') and frag not in pages[target][0].ids:
                fails.append(f'{rel}: missing fragment {url!r} (no id {frag!r} in {target})')

    # 5. stubs
    for stub, dest in STUBS.items():
        if stub not in pages:
            fails.append(f'{stub}: retired redirect stub missing from output')
            continue
        pg = pages[stub][0]
        if not pg.noindex:
            fails.append(f'{stub}: stub is not noindex')
        m = re.search(r'url=(\S+)', pg.refresh or '')
        if not m or m.group(1).strip('\'"') != dest:
            fails.append(f'{stub}: meta refresh {pg.refresh!r} != url={dest}')

    # 3. sitemap / llms / robots
    sm = files.get('sitemap.xml')
    locs = re.findall(r'<loc>([^<]+)</loc>', sm.read_text(encoding='utf-8')) if sm else []
    if not locs:
        fails.append('sitemap.xml: missing or empty')
    in_sitemap = set()
    for loc in locs:
        target, _ = resolve(root, files, 'index.html', loc)
        if target in (None, 'EXTERNAL'):
            fails.append(f'sitemap.xml: <loc> {loc} does not resolve to a page')
            continue
        in_sitemap.add(target)
        pg = pages.get(target, (None,))[0]
        if pg and pg.noindex:
            fails.append(f'sitemap.xml: lists noindex page {target}')
        if pg and pg.canonical and pg.canonical != loc:
            fails.append(f'{target}: canonical {pg.canonical} != sitemap <loc> {loc}')
    if len(in_sitemap) != len(locs):
        fails.append('sitemap.xml: duplicate <loc> entries')
    indexable = {r for r, (pg, _) in pages.items() if not pg.noindex and r != '404.html'}
    for r in sorted(indexable - in_sitemap):
        fails.append(f'sitemap.xml: indexable page {r} not listed')
    llms = files.get('llms.txt')
    if not llms:
        fails.append('llms.txt: missing')
    else:
        for url in re.findall(r'https://(?:www\.)?demandrange\.com[^\s)\]>"\']*', llms.read_text(encoding='utf-8')):
            url = url.rstrip('.,;:')
            target, _ = resolve(root, files, 'index.html', url)
            if target is None:
                fails.append(f'llms.txt: {url} does not resolve')
            elif target in STUBS:
                fails.append(f'llms.txt: {url} points at a retired stub')
    rb = files.get('robots.txt')
    if not rb or f'Sitemap: {SITE}/sitemap.xml' not in rb.read_text(encoding='utf-8'):
        fails.append('robots.txt: missing or no Sitemap line')

    # 4. brand over text files and xlsx members
    scanned = 0
    for rel, p in sorted(files.items()):
        ext = p.suffix.lower()
        blobs = []
        if ext in TEXT_EXT:
            blobs.append((rel, p.read_text(encoding='utf-8', errors='replace')))
        elif ext == '.xlsx':
            with zipfile.ZipFile(p) as z:
                for n in z.namelist():
                    blobs.append((f'{rel}!{n}', z.read(n).decode('utf-8', 'replace')))
        for name, text in blobs:
            scanned += 1
            for m in sorted(set(BRAND_BAD.findall(text))):
                fails.append(f'{name}: brand variant {m!r} (must be "Demand Range")')

    for f in fails:
        print('FAIL:', f)
    status = 'FAIL' if fails else 'PASS'
    print(f'site_checks {status}: {len(files)} files, {len(pages)} HTML pages, {nlinks} internal '
          f'links, {len(locs)} sitemap URLs, {scanned} text blobs scanned, {len(fails)} failure(s)')
    return 1 if fails else 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
