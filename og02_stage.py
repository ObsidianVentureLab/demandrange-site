"""Original OG02 article; exact contextual insertions, no shell redesign."""
import json
import shutil
from foundation_stage import CONTENT, metadata, shared_shell, block, once

ROUTE = 'industrial-prospect-list-audit.html'
AUDIT_CSS = '#worked-batch .table-wrap[aria-describedby="audit-table-instructions"] th { color: var(--ink-2); }'
# Programme A service/sample owners; manufacturing owns discovery, then hands
# the reader to the distinct supplied-batch task at its bounded-review section.
LINKS = {
    'industrial-lead-research.html': ('quality', '<p><a href="methodology.html">Read the research method</a></p>', '<p id="og02-audit-link">Checking a supplied list? <a href="industrial-prospect-list-audit.html">Audit a fictional prospect batch</a> for company counts, duplicates and unresolved evidence before accepting its handoff.</p>'),
    'sample-account-research.html': ('template', '<p>A real record needs permitted sources, current identity and fit evidence, applicable data controls and the agreed review/release checks. Downloading or completing a worksheet does not clear source rights or authorise outreach.</p>', '<p id="og02-audit-link">To check more than one record, use the <a href="industrial-prospect-list-audit.html">worked batch audit and acceptance worksheets</a> to reconcile company counts, duplicates, holds and rejections.</p>'),
    'irish-manufacturing-account-research.html': ('bounded-review', '<p>Keep included, held and rejected records separate. Reconcile included company counts after deduplication; give each hold one next verification question. Stop at the agreed research boundary and disclose unresolved coverage rather than filling a quota with weaker matches.</p>', '<p id="og02-audit-link">Once a batch has been assembled, <a href="industrial-prospect-list-audit.html">work through the fictional prospect-list audit</a> to preserve site evidence, resolve duplicate references and reconcile its company-level handoff.</p>'),
    'industrial-sales-resources.html': ('review-quality', '<p>Use a worked exercise before accepting a batch or treating every spreadsheet row as a distinct company.</p>', '<p id="og02-audit-link"><a href="industrial-prospect-list-audit.html">Work through the fictional industrial prospect-list audit</a>, then use its batch, answer key and acceptance worksheets to challenge duplicates, holds and inclusion reasons.</p>'),
}

def apply_og02(output):
    data = json.loads((CONTENT / 'og02-metadata.json').read_text())
    # Copy the existing reviewed shell, then replace only this new main/metadata.
    text = metadata((output / 'industrial-lead-research.html').read_text(), data, ROUTE)
    main = (CONTENT / 'og02.fragment.html').read_text()
    text = shared_shell(block(text, r'<main\b.*?</main>', main), ROUTE)
    (output / ROUTE).write_text(text)
    css = output / 'styles.css'
    css.write_text(css.read_text() + '\n' + AUDIT_CSS + '\n')
    for name in data['public_asset_mapping'].values():
        shutil.copy2(CONTENT / name, output / name)
    for route, (_, anchor, insertion) in LINKS.items():
        page = output / route
        page.write_text(once(page.read_text(), anchor, anchor + insertion))
    sitemap = output / 'sitemap.xml'
    sitemap.write_text(once(sitemap.read_text(), '</urlset>',
        '  <url><loc>https://demandrange.com/' + ROUTE + '</loc></url>\n</urlset>'))
