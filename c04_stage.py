"""Revised C04 composition; JRC prose summaries, pending parent final review."""
import json
import shutil
from foundation_stage import CONTENT, metadata, page_main, shared_shell, block, once

ROUTE = 'pump-flow-control-prospecting.html'
WORKSHEET = 'pump-flow-control-supplier-fit-worksheet.csv'

def apply_c04(output):
    data = json.loads((CONTENT/'c04-metadata.json').read_text())
    text = metadata((output/'industrial-lead-research.html').read_text(), data, ROUTE)
    main = page_main('c04')
    main = once(main, 'aria-label="Data table; scroll horizontally to view all columns"',
                'aria-labelledby="matrix-heading" aria-describedby="matrix-scroll-hint" aria-label="Application-fit and route matrix; scroll horizontally to view all columns"')
    text = shared_shell(block(text, r'<main\b.*?</main>', main), ROUTE)
    (output/ROUTE).write_text(text)
    shutil.copy2(CONTENT/WORKSHEET, output/WORKSHEET)
    sitemap = output/'sitemap.xml'
    sitemap.write_text(once(sitemap.read_text(), '</urlset>', '  <url><loc>https://demandrange.com/' + ROUTE + '</loc></url>\n</urlset>'))
    css = output/'styles.css'
    css.write_text(css.read_text() + '\n' + (CONTENT/'c04.css').read_text())
