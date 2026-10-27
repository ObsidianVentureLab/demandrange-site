"""OG07: a distinct maintenance task using the existing reviewed page shell."""
import json
import shutil
from foundation_stage import CONTENT, metadata, page_main, shared_shell, block, once
from og02_stage import LINKS as AUDIT_LINKS

ROUTE = 'industrial-prospect-list-maintenance.html'
ASSET = 'industrial-prospect-review-log.csv'
LINKS = {
    'irish-manufacturing-account-research.html': '<p id="og07-maintenance-link">Already have an account list? Use the <a href="industrial-prospect-list-maintenance.html">industrial prospect-list refresh checklist</a> to review company, site and brief changes without losing the earlier evidence.</p>',
    'industrial-lead-research.html': '<p id="og07-maintenance-link">Maintaining an existing shortlist? See <a href="industrial-prospect-list-maintenance.html">when to refresh an industrial prospect list</a>, with worked retain, hold, correct and remove decisions and a blank review log.</p>',
}

def apply_og07(output):
    data = json.loads((CONTENT / 'og07-metadata.json').read_text())
    text = metadata((output / 'industrial-lead-research.html').read_text(), data, ROUTE)
    text = shared_shell(block(text, r'<main\b.*?</main>', page_main('og07')), ROUTE)
    (output / ROUTE).write_text(text)
    shutil.copy2(CONTENT / ASSET, output / ASSET)
    for route, insertion in LINKS.items():
        page = output / route
        anchor = AUDIT_LINKS[route][2]
        page.write_text(once(page.read_text(), anchor, anchor + insertion))
    sitemap = output / 'sitemap.xml'
    sitemap.write_text(once(sitemap.read_text(), '</urlset>',
        '  <url><loc>https://demandrange.com/' + ROUTE + '</loc></url>\n</urlset>'))
