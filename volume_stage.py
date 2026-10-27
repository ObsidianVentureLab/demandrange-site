"""Three distinct volume guides and four blank educational worksheets."""
import json
import shutil
from foundation_stage import CONTENT,metadata,page_main,shared_shell,block,once
PAGES={
 'food':'irish-food-beverage-company-research.html',
 'icp':'industrial-ideal-customer-profile.html',
 'lookalike':'industrial-lookalike-account-research.html',
 'tender':'etenders-industrial-supplier-opportunities.html',
}
DOWNLOADS=('exclusion-boundary-review-blank.csv','industrial-mro-scope-worksheet.csv','research-priority-queue-blank.csv','oem-component-route-blank.csv','channel-screening-blank.csv','channel-screening-fictional.csv','programme-correction-register-blank.csv','programme-correction-register-fictional.csv','territory-rule-blank.csv','territory-rule-fictional.csv','pharma-description-answer-key.csv','pharma-description-fictional-cards.csv','pharma-description-worksheet.csv','industrial-sample-comparison-fictional.csv','handover-after-expected-fictional.csv','handover-after-prepared-corrupt-fictional.csv','handover-before-fictional.csv','handover-expected-decisions.csv','handover-field-map-worksheet.csv','industrial-evidence-conflict-answer-key.csv','industrial-evidence-conflict-cards.csv','industrial-evidence-conflict-worksheet.csv','water-wastewater-buyer-route-worksheet.csv','water-wastewater-buyer-route-fictional-cases.csv',
 'identity-entities-blank.csv',
 'identity-entities-fictional.csv',
 'identity-mapping-blank.csv',
 'identity-mapping-fictional.csv',
 'identity-evidence-blank.csv',
 'identity-evidence-fictional.csv',
 'irish-food-beverage-segmentation-worksheet.csv',
 'irish-food-beverage-segmentation-fictional-cases.csv',
 'industrial-research-acceptance-checklist.csv',
 'industrial-ideal-customer-profile-worksheet.csv',
 'industrial-lookalike-comparison-worksheet.csv',
 'industrial-tender-triage-worksheet.csv',
 'industrial-research-effort-worksheet.csv',
)
def apply_volume(output):
    shell=(output/'industrial-lead-research.html').read_text()
    for key,route in PAGES.items():
        data=json.loads((CONTENT/('volume-'+key+'-metadata.json')).read_text())
        text=metadata(shell,data,route)
        text=shared_shell(block(text,r'<main\b.*?</main>',page_main('volume-'+key)),route)
        (output/route).write_text(text)
    for name in DOWNLOADS:shutil.copy2(CONTENT/name,output/name)
    sitemap=output/'sitemap.xml'
    sitemap.write_text(once(sitemap.read_text(),'</urlset>',''.join('  <url><loc>https://demandrange.com/'+route+'</loc></url>\n' for route in PAGES.values())+'</urlset>'))
