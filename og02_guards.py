"""Fail-closed OG02 assets, declared exercise logic and exact local link scopes.
The byte pins are separate from the editable production manifest. Neither these
checks nor arithmetic constitute independent semantic/rights/release approval.
"""
from collections import Counter
import csv
import hashlib
import json
import math
import posixpath
import re
from urllib.parse import urlsplit, unquote
from bs4 import BeautifulSoup
from site_guards import need, unique_object
from og02_download_pins import OG02_DOWNLOADS
from og02_stage import ROUTE, LINKS, AUDIT_CSS
from og02_audit_logic import classify, reconcile, validate_answers, loadcsv, Invalid

NOTICE = 'WHOLLY FICTIONAL TEACHING DATA — NOT REAL PROSPECTS OR CLIENT DATA'
DOCUMENTS = {n:d for n,d in OG02_DOWNLOADS.items() if d['format'] != 'csv'}
CSV_PINS = {n:{k:v for k,v in d.items() if k != 'format'} for n,d in OG02_DOWNLOADS.items() if d['format']=='csv'}

def validate_declarations(contract):
    need(contract.get('safe_documents') == DOCUMENTS, 'OG02 exact JSON/TXT declarations changed')
    need(set(DOCUMENTS) == {n for n in contract['public_files'] if n.endswith(('.json','.txt')) and not n.startswith('.well-known/') and n!='robots.txt'}, 'OG02 document coverage mismatch')
    for name,decl in CSV_PINS.items():
        need(contract['safe_downloads'].get(name)==decl, 'OG02 exact CSV declaration changed: '+name)
    need(set(OG02_DOWNLOADS) | {ROUTE} <= set(contract['generator_managed_files']), 'OG02 generated coverage missing')
    need(ROUTE in contract['page_routes'], 'OG02 audited route missing')

def strict_json(path):
    def invalid_constant(value): raise ValueError('Nonfinite JSON value: '+value)
    def finite_float(value):
        number = float(value)
        if not math.isfinite(number): invalid_constant(value)
        return number
    return json.loads(path.read_text(encoding='utf-8'), object_pairs_hook=unique_object, parse_constant=invalid_constant, parse_float=finite_float)

def validate_contents(root):
    """Semantic structure independent of hashes, also used by mutation tests."""
    schema = strict_json(root/'industrial-audit-schema.json')
    policy = strict_json(root/'industrial-audit-policy.json')
    need(type(schema) is dict and set(schema)==set(['accepted_unit', 'brief_id', 'brief_version', 'columns', 'cross_field_rules', 'fiction_only', 'format', 'ruleset_id', 'schema_name', 'version']), 'OG02 schema keys')
    need(type(schema['version']) is int and schema['version']==2 and schema['fiction_only'] is True and schema['accepted_unit']=='company', 'OG02 fiction-only schema required')
    need(type(schema['columns']) is dict and list(schema['columns'])==CSV_PINS['industrial-audit-fictional-batch.csv']['columns'], 'OG02 exact schema columns')
    need(schema['columns']['fiction_label'].get('const')==NOTICE, 'OG02 schema fiction label')
    need(all(schema['columns'][k].get('const')=='' for k in ['source_url','source_publication_date','source_review_date']), 'OG02 fictional source fields blank')
    need(type(schema['cross_field_rules']) is list and len(schema['cross_field_rules'])==11 and all(type(x) is str and x for x in schema['cross_field_rules']), 'OG02 cross-field rules')
    need(type(policy) is dict and set(policy)==set(['accepted_unit', 'brief_id', 'brief_version', 'decision_order', 'duplicate_assessment', 'duplicate_scope', 'expected_classes', 'expected_counts', 'expected_counts_scope', 'fiction_label', 'identity_dependency', 'policy_scope', 'required_activity', 'ruleset_id', 'score_override_allowed', 'signal_definition', 'source_use_boundary', 'supplied_unit_handling', 'territory']), 'OG02 policy keys')
    need(policy['fiction_label']==NOTICE and policy['accepted_unit']=='company' and policy['score_override_allowed'] is False, 'OG02 policy fiction/unit/override')
    for key, fields in [('expected_counts',{'supplied','duplicate','include','hold','reject'}),('expected_classes',{'fit_matched_lookalike','opportunity_signal'})]:
        need(type(policy[key]) is dict and set(policy[key])==fields and all(type(x) is int and x>=0 for x in policy[key].values()), 'OG02 policy integer counts')
    for name,d in CSV_PINS.items():
        with (root/name).open(newline='',encoding='utf-8') as f: rows=list(csv.reader(f, strict=True))
        need(rows and rows[0]==d['columns'] and len(rows)-1==d['data_rows'] and all(len(row)==len(rows[0]) for row in rows), 'OG02 CSV shape: '+name)
        for row in rows:
            for cell in row:
                need(not any(ord(c)<32 or 127<=ord(c)<=159 for c in cell), 'OG02 CSV control character')
                need(not cell.lstrip().startswith(('=','+','-','@')), 'OG02 CSV formula')
        if 'fiction_label' in rows[0]:
            i=rows[0].index('fiction_label')
            need(all(row[i]==NOTICE for row in rows[1:]), 'OG02 standalone fiction label: '+name)
    batch=loadcsv(root/'industrial-audit-fictional-batch.csv'); answers=loadcsv(root/'industrial-audit-answer-key.csv')
    outcomes=classify(batch,schema,policy); validate_answers(batch,outcomes,answers)
    counts,classes=reconcile(batch,outcomes,policy['expected_counts'],policy['expected_classes'])
    blank=loadcsv(root/'industrial-audit-blank-rows.csv')
    need(all(all(v=={'fiction_label':NOTICE,'brief_id':'FIC-BRIEF-01','brief_version':'1'}.get(k,'') for k,v in row.items()) for row in blank), 'OG02 unfinished fiction template must be blank')
    try: classify(blank,schema,policy)
    except Invalid: pass
    else: raise ValueError('OG02 unfinished template accepted')
    worksheet=loadcsv(root/'industrial-audit-blank-worksheet.csv')
    need(len({r['field'] for r in worksheet})==len(worksheet) and all(r['instructions'] for r in worksheet), 'OG02 worksheet instructions/fields')
    expected={'accepted_unit':'company','notice':'EDUCATIONAL BLANK WORKSHEET — NOT A LIVE-DATA APPROVAL'}
    need(all(r['value']==expected.get(r['field'],'') for r in worksheet), 'OG02 worksheet values/defaults')
    dictionary=loadcsv(root/'industrial-audit-field-dictionary.csv')
    need([r['field'] for r in dictionary]==list(schema['columns']), 'OG02 dictionary schema coverage')
    for name in OG02_DOWNLOADS:
        text=(root/name).read_text(encoding='utf-8')
        need(not re.search(r'https?://|[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}',text,re.I), 'OG02 live URL/contact in fiction pack')
    readme=(root/'industrial-audit-README.txt').read_text()
    need('FICTION NOTICE' in readme and 'not anonymised client data' in readme and 'NOT JSON Schema' in readme, 'OG02 standalone instructions/fiction boundary')
    return counts,classes

def validate_assets(root):
    need({p.name for p in root.glob('industrial-audit*')}==set(OG02_DOWNLOADS), 'OG02 undeclared source/download filename')
    for name,d in OG02_DOWNLOADS.items():
        path=root/name
        need(path.is_file() and not path.is_symlink() and hashlib.sha256(path.read_bytes()).hexdigest()==d['sha256'], 'OG02 declared asset byte drift: '+name)
    return validate_contents(root)

def guarded_local_identity(value):
    """Recognise guarded root targets despite aliases; never approve the alias.

    This supported site has root-level HTML routes, no base element and no
    URL-bearing CSS. Generic resource guards separately reject nonlocal URLs,
    backslashes and controls. Decode before normalising so encoded dots and
    slashes cannot evade the narrower OG02 recognition boundary.
    """
    parts = urlsplit(value)
    if parts.scheme or parts.netloc or not parts.path:
        return None
    return posixpath.normpath('/' + unquote(parts.path).lstrip('/')).lstrip('/')


def validate_page(soup,route,root):
    # New asset navigation is allowed only from the reviewed article, never as
    # a blanket resource or any-page reference exception.
    for node in soup.select('[src], link[href]'):
        value=node.get('src') or node.get('href')
        need(guarded_local_identity(value) not in OG02_DOWNLOADS, 'OG02 download used as resource')
    links=[a for a in soup.select('a[href]') if guarded_local_identity(a['href']) in OG02_DOWNLOADS]
    if route!=ROUTE:
        need(not links, 'OG02 asset reference on wrong route')
    else:
        need((root/'styles.css').read_text().count(AUDIT_CSS)==1, 'OG02 scoped header contrast rule missing')
        expected=Counter({name:1 for name in OG02_DOWNLOADS})
        expected.update(['industrial-audit-blank-worksheet.csv','industrial-audit-fictional-batch.csv','industrial-audit-answer-key.csv'])
        need(Counter(a['href'] for a in links)==expected, 'OG02 exact download-link coverage')
        need(all(a.get('download') == '' and a.find_parent('main') and not a.find_parent('nav') for a in links), 'OG02 download attribute/containment')
        need(links[0].attrs == {'class':['btn','btn-secondary'], 'download':'', 'href':'industrial-audit-blank-worksheet.csv'} and all(a.attrs == {'href':a['href'], 'download':''} for a in links[1:]), 'OG02 exact download attributes')
        external_context=['irish-manufacturing-account-research.html','methodology.html#classes','industrial-lead-research.html#research-approach','sample-account-research.html','request-a-quote.html']
        other=[a['href'] for a in soup.main.select('a[href]') if not a['href'].startswith('#') and a['href'] not in OG02_DOWNLOADS]
        need(other==external_context, 'OG02 contextual reference changed or cross-bound')
        region=soup.select_one('.table-wrap[role="region"][tabindex="0"][aria-label="Fictional batch decisions"][aria-describedby="audit-table-instructions"]')
        need(region is not None and soup.find(id='audit-table-instructions') and 'scroll the table horizontally' in soup.find(id='audit-table-instructions').get_text(), 'OG02 accessible table region/hint')
        need(len(soup.select('table'))==1 and len(region.select('thead th[scope="col"]'))==4, 'OG02 table header coverage')
        rows=region.select('tbody tr'); answers=loadcsv(root/'industrial-audit-answer-key.csv')
        need(len(rows)==len(answers)==14, 'OG02 table row coverage')
        for row,answer in zip(rows,answers):
            cells=row.find_all(['th','td'],recursive=False)
            need(len(cells)==4 and cells[0].get('scope')=='row' and cells[0].get_text()==answer['row_id'] and cells[2].get_text().lower()==answer['disposition'], 'OG02 table/answer mismatch')
        counts,classes=validate_contents(root)
        expected_sum=f"{counts['supplied']} = {counts['duplicate']} + {counts['include']} + {counts['hold']} + {counts['reject']}."
        expected_classes=f"{counts['include']} = {classes['fit_matched_lookalike']} industry-matched + {classes['opportunity_signal']} opportunity-signal"
        need(expected_sum in soup.main.get_text() and expected_classes in soup.main.get_text(), 'OG02 article reconciliation drift')
        need('Wholly fictional teaching exercise.' in soup.main.get_text() and 'All rows below are fictional.' in soup.main.get_text(), 'OG02 page fiction labels')
    incoming=[a for a in soup.select('a[href]') if guarded_local_identity(a['href']) == ROUTE]
    if route in LINKS:
        section,_,markup=LINKS[route]
        expected=BeautifulSoup(markup,'html.parser').p
        nodes=soup.select('#og02-audit-link')
        need(len(nodes)==len(incoming)==1 and str(nodes[0])==str(expected) and nodes[0].find_parent('section').get('id')==section, 'OG02 incoming contextual link changed')
    else:
        need(not incoming, 'OG02 incoming link on undeclared route')
