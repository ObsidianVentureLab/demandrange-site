"""Resource directory built before the exact OG02 audit-link insertion."""
import json
from foundation_stage import CONTENT, metadata, page_main, shared_shell, block, once
ROUTE='industrial-sales-resources.html'
INSERTIONS={
 'index.html': ('<p>These examples demonstrate the format and reasoning, not real companies, client results or available work.</p>', '<p id="research-resource-directory">Working on your own prospect base? Browse the <a href="industrial-sales-resources.html">industrial sales research guides and free templates</a>, organised by the task you need to complete.</p>'),
 'industrial-lead-research.html': ('<p><a href="methodology.html">Read the research method</a></p>', '<p id="research-resource-directory">Choose the right tool for the job in our <a href="industrial-sales-resources.html">industrial sales research resource library</a>: discovery, customer routes, batch review, maintenance and example records.</p>'),
}
def apply_resources(output):
    data=json.loads((CONTENT/'resources-metadata.json').read_text())
    text=metadata((output/'industrial-lead-research.html').read_text(),data,ROUTE)
    text=shared_shell(block(text,r'<main\b.*?</main>',page_main('resources')),ROUTE)
    (output/ROUTE).write_text(text)
    for route,(anchor,insertion) in INSERTIONS.items():
        page=output/route
        replacement=anchor+insertion if route=='index.html' else insertion+anchor
        page.write_text(once(page.read_text(),anchor,replacement))
    sitemap=output/'sitemap.xml'
    sitemap.write_text(once(sitemap.read_text(),'</urlset>','  <url><loc>https://demandrange.com/'+ROUTE+'</loc></url>\n</urlset>'))
