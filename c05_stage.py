"""Compose the accepted C05 markdown with inherited editorial components."""
import json
import re
import shutil
from html import escape
from bs4 import BeautifulSoup
from foundation_stage import CONTENT, metadata, page_main, shared_shell, block, once

ROUTE = 'irish-manufacturing-account-research.html'

def apply_c05(output):
    data = json.loads((CONTENT / 'c05-metadata.json').read_text())
    text = metadata((output / 'industrial-lead-research.html').read_text(), data, ROUTE)
    main = page_main('c05')
    for caption_id in ('manufacturing-size-caption', 'manufacturing-activity-caption'):
        old_open = ('<div aria-label="Data table; scroll horizontally to view all columns" '
                    'class="table-wrap" role="region" tabindex="0"><table><caption id="' + caption_id + '">')
        new_open = ('<div aria-labelledby="' + caption_id + '" '
                    'class="table-wrap" role="region" tabindex="0"><table><caption id="' + caption_id + '">')
        main = once(main, old_open, new_open)
    main = once(main, 'aria-label="Data table; scroll horizontally to view all columns"',
                'aria-labelledby="source-purpose" aria-describedby="source-purpose-scroll"')
    main = once(main, '</nav>', '<a href="#source-purpose">Source questions</a></nav>')
    text = shared_shell(block(text, r'<main\b.*?</main>', main), ROUTE)
    (output / ROUTE).write_text(text)
    shutil.copy2(CONTENT / 'OG01-Evidence_Question_Log.csv', output / 'OG01-Evidence_Question_Log.csv')
    # A01: normal-text contrast for this matrix only, in both existing themes.
    css = output / 'styles.css'
    css.write_text(css.read_text() + '\n#discovery .table-wrap[aria-labelledby="source-purpose"] th { color: var(--ink-2); }\n#manufacturing-market-context th { color: var(--ink-2); white-space: normal; }\n')
    sitemap = output / 'sitemap.xml'
    sitemap.write_text(once(sitemap.read_text(), '</urlset>',
        '  <url><loc>https://demandrange.com/' + ROUTE + '</loc></url>\n</urlset>'))
