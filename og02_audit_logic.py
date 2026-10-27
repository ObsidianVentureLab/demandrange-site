"""Fiction-only OG02 classifier. No network or source-rights automation.
Run: python -B validate_audit.py [--assets PATH] [--output PATH]
Writes only beside this script. Review source statements separately from declared gates.
"""
from pathlib import Path
from collections import Counter
from datetime import datetime, timezone
import argparse, copy, csv, hashlib, json, re
ROOT=Path(__file__).resolve().parent
GATES=('identity','activity','territory','exclusions','source_use','evidence_consistency')
CLASSES=('fit_matched_lookalike','opportunity_signal')
DISPOSITIONS=('duplicate','include','hold','reject')
BRIEF_ID='FIC-BRIEF-01'; BRIEF_VERSION='1'; RULESET='OG02-HOLD-FIRST-1'
FICTION='WHOLLY FICTIONAL TEACHING DATA — NOT REAL PROSPECTS OR CLIENT DATA'
SOURCE_USE='Simulated internal review and retention, and customer-facing evidence-summary sharing within this invented exercise only; no real-data permission.'
COLUMNS=('fiction_label','row_id','supplied_name','supplied_unit','company_key','site_keys','group_key','identity','activity','territory','exclusions','source_use','evidence_consistency','evidence_id','evidence_text','source_url','source_publication_date','source_review_date','project_status','project_evidence_text','canonical_row_id','dedup_evidence','next_check','brief_id','brief_version')
class Invalid(ValueError): pass
def require(test,message):
    if not test: raise Invalid(message)
def loadcsv(path):
    with path.open(newline='',encoding='utf-8') as f:
        reader=csv.DictReader(f)
        require(reader.fieldnames is not None and len(reader.fieldnames)==len(set(reader.fieldnames)),'missing or duplicate CSV headers')
        return list(reader)
def validate_contract(schema,policy):
    require(policy.get('accepted_unit')=='company' and schema.get('accepted_unit')=='company','accepted unit must be company')
    require(policy.get('score_override_allowed') is False,'score override forbidden')
    for key,value in {'brief_id':BRIEF_ID,'brief_version':BRIEF_VERSION,'ruleset_id':RULESET}.items():
        require(policy.get(key)==schema.get(key)==value,f'unsupported or inconsistent {key}')
    require(schema.get('version')==2 and schema.get('fiction_only') is True,'unsupported schema version or fiction scope')
    require(policy.get('decision_order')==['duplicate','hold','reject','include'],'unsupported decision order')
    for key,value in {
        'fiction_label':FICTION,
        'required_activity':'Manufacture complete food-packaging machinery',
        'territory':'Production in Republic of Ireland',
        'duplicate_scope':'Within this supplied batch only; no global database or CRM duplicate claim',
        'signal_definition':'Invented proposed additional production/assembly space at a company already meeting account rules',
        'source_use_boundary':SOURCE_USE,
    }.items(): require(policy.get(key)==value,f'unsupported policy {key}; revise brief and implementation together')
    require(set(schema.get('columns',{}))==set(COLUMNS),'unsupported schema columns')
    vocabularies={
        'supplied_unit':['company','brand','site'],
        'identity':['pass','unknown','conflict'],
        'activity':['pass','fail','unknown','conflict'],
        'territory':['pass','fail','unknown','conflict'],
        'exclusions':['pass','fail','unknown','conflict'],
        'source_use':['pass','fail','unknown','conflict'],
        'evidence_consistency':['pass','conflict'],
        'project_status':['not_assessed_not_required','no_qualifying_signal_in_bounded_review','qualifying_signal_identified'],
    }
    for key,values in vocabularies.items():
        require(schema['columns'][key].get('enum')==values,f'unsupported schema enum {key}')
    patterns={
        'row_id':r'FIC-R[0-9]{2}', 'company_key':r'FIC-C[0-9]{2}|',
        'site_keys':r'(FIC-S[0-9]{2})(\|FIC-S[0-9]{2})*|',
        'group_key':r'FIC-G[0-9]{2}|', 'evidence_id':r'FIC-E[0-9]{2}',
        'canonical_row_id':r'FIC-R[0-9]{2}|',
    }
    for key,value in patterns.items():
        require(schema['columns'][key].get('pattern')==value,f'unsupported schema pattern {key}')
    for key,value in {'fiction_label':FICTION,'brief_id':BRIEF_ID,'brief_version':BRIEF_VERSION,'source_url':'','source_publication_date':'','source_review_date':''}.items():
        require(schema['columns'][key].get('const')==value,f'schema {key}: required constant missing')

def classify(rows,schema,policy):
    validate_contract(schema,policy)
    require(bool(rows),'empty batch is not acceptance')
    columns=schema['columns']; byid={}; anchors={}; siteowners={}
    for r in rows:
        require(set(r)==set(columns),'exact columns required; extra fields/score forbidden')
        for field,rules in columns.items():
            value=r[field]
            require(isinstance(value,str),f'{field}: string required')
            if 'const' in rules: require(value==rules['const'],f'{field}: constant mismatch')
            if 'enum' in rules: require(value in rules['enum'],f'{field}: invalid enum')
            if 'pattern' in rules: require(re.fullmatch(rules['pattern'],value) is not None,f'{field}: invalid pattern')
            if 'prefix' in rules: require(value.startswith(rules['prefix']),f'{field}: missing prefix')
            require(not value.lstrip().startswith(('=','+','-','@')),f'{field}: CSV formula prefix forbidden')
            require(not re.search(r'https?://|\b[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}\b',value),'live URL/contact in fiction row')
        require(r['row_id'] not in byid,'duplicate row_id'); byid[r['row_id']]=r
        require((r['identity']=='pass')==bool(r['company_key']),'resolved company key requires identity pass')
        if r['identity']!='pass':
            require(all(r[k] in ('unknown','conflict') for k in ('activity','territory','exclusions')),'unresolved identity retains company-specific gate pass/fail')
        if any(r[k]=='conflict' for k in GATES if k!='evidence_consistency'):
            require(r['evidence_consistency']=='conflict','conflicted gate requires evidence_consistency conflict')
        require(bool(r['evidence_text'].removeprefix('Invented evidence: ').strip()),'empty evidence card')
        require(bool(r['project_evidence_text'])==(r['project_status']=='qualifying_signal_identified'),'signal evidence/status mismatch')
        if r['project_evidence_text']:
            require(r['project_evidence_text'].startswith('Invented signal: ') and bool(r['project_evidence_text'].removeprefix('Invented signal: ').strip()),'signal label or substance missing')
        if not r['canonical_row_id']:
            require(not r['dedup_evidence'],'dedup evidence without pointer')
            if r['company_key']: anchors.setdefault(r['company_key'],[]).append(r['row_id'])
        sites=r['site_keys'].split('|') if r['site_keys'] else []
        require(len(sites)==len(set(sites)),'repeated site inside row')
        for site in sites: siteowners.setdefault(site,set()).add(r['company_key'] or 'UNRESOLVED')
    require(len({r['evidence_id'] for r in rows})==len(rows),'evidence IDs must be unique')
    require(all(len(v)==1 for v in anchors.values()),'company has multiple anchors; site/company double count')
    require(all(len(v)==1 for v in siteowners.values()),'site attributed to multiple or unresolved companies')
    outcomes=[]
    for r in rows:
        target=r['canonical_row_id']
        if target:
            require(target in byid,'duplicate target missing'); t=byid[target]
            require(target!=r['row_id'] and not t['canonical_row_id'],'duplicate self/cycle/chain forbidden')
            require(r['identity']=='pass' and bool(r['company_key']) and r['company_key']==t['company_key'],'duplicate needs same resolved company')
            require(t['identity']=='pass' and bool(t['company_key']),'duplicate target must resolve company')
            note=r['dedup_evidence']
            require(bool(note.strip()),'duplicate attribution evidence missing')
            require(note.startswith('Invented attribution: ') and r['company_key'] in note and target in note,'duplicate attribution must name exact company and anchor; human semantic review still required')
            require(all(r[k]==t[k] for k in GATES+('project_status','project_evidence_text')),'duplicate contains conflicting gates; consolidate and resolve first')
            decision='duplicate'
        elif any(r[k] in ('unknown','conflict') for k in GATES): decision='hold'
        elif any(r[k]=='fail' for k in GATES): decision='reject'
        else:
            require(bool(r['company_key']) and r['identity']=='pass','included anchor must resolve company')
            decision='include'
        if decision=='hold': require(bool(r['next_check'].strip()),'hold needs next verification question')
        research_class=('opportunity_signal' if r['project_status']=='qualifying_signal_identified' else 'fit_matched_lookalike') if decision=='include' else ''
        outcomes.append({'row_id':r['row_id'],'disposition':decision,'research_class':research_class})
    return outcomes

def reconcile(rows,outcomes,declared_counts=None,declared_classes=None):
    rowids=[r['row_id'] for r in rows]; outids=[o['row_id'] for o in outcomes]
    require(len(rowids)==len(set(rowids)),'duplicate input row IDs')
    require(len(outids)==len(set(outids)) and set(outids)==set(rowids),'outcomes must cover each supplied row ID exactly once')
    byid={r['row_id']:r for r in rows}; included=[]
    for o in outcomes:
        require(o['disposition'] in DISPOSITIONS,'invalid outcome disposition')
        if o['disposition']=='include':
            require(o['research_class'] in CLASSES,'included outcome needs known class')
            r=byid[o['row_id']]
            require(bool(r['company_key']) and not r['canonical_row_id'],'included outcome must be company anchor')
            included.append(r['company_key'])
        else: require(o['research_class']=='','nonincluded outcome must have blank class')
    require(len(included)==len(set(included)),'included company double count')
    c=Counter(o['disposition'] for o in outcomes)
    counts={'supplied':len(rows),**{d:c[d] for d in DISPOSITIONS}}
    require(counts['supplied']==sum(counts[d] for d in DISPOSITIONS),'reconciliation does not balance')
    cc=Counter(o['research_class'] for o in outcomes if o['disposition']=='include')
    classes={k:cc[k] for k in CLASSES}
    require(sum(classes.values())==counts['include'],'class reconciliation does not balance')
    if declared_counts is not None: require(counts==declared_counts,'declared counts differ')
    if declared_classes is not None: require(classes==declared_classes,'declared classes differ')
    return counts,classes

def validate_answers(rows,outcomes,answers):
    require(len(answers)==len(rows),'answer count mismatch')
    require(len({a['row_id'] for a in answers})==len(answers),'duplicate answer row')
    index={a['row_id']:a for a in answers}; records={r['row_id']:r for r in rows}
    require(set(index)==set(records),'answer row IDs differ')
    for o in outcomes:
        a=index[o['row_id']]; r=records[o['row_id']]
        for k in ('disposition','research_class'): require(a[k]==o[k],f'answer {k} differs for {o["row_id"]}')
        require(bool(a['reason'].strip()),'answer reason missing')
        for k in ('fiction_label','brief_id','brief_version','canonical_row_id','next_check'): require(a[k]==r[k],f'answer {k} differs')

def included_view(rows,outcomes):
    included=[]; byid={r['row_id']:r for r in rows}
    for o in outcomes:
        if o['disposition']!='include': continue
        r=byid[o['row_id']]; members=[m for m in rows if m['company_key']==r['company_key']]
        included.append({'fiction_label':r['fiction_label'],'brief_id':r['brief_id'],'brief_version':r['brief_version'],'company_key':r['company_key'],'anchor_row_id':r['row_id'],'member_row_ids':'|'.join(sorted(m['row_id'] for m in members)),'site_keys':'|'.join(sorted({s for m in members for s in m['site_keys'].split('|') if s})),'research_class':o['research_class']})
    return sorted(included,key=lambda r:r['company_key'])

def run_negative(fixture,rows,schema,policy,answers):
    rows=copy.deepcopy(rows); schema=copy.deepcopy(schema); policy=copy.deepcopy(policy); answers=copy.deepcopy(answers)
    for change in fixture.get('row_changes',[]): next(r for r in rows if r['row_id']==change['row_id']).update(change['set'])
    policy.update(fixture.get('policy_changes',{}))
    for change in fixture.get('answer_changes',[]): next(a for a in answers if a['row_id']==change['row_id']).update(change['set'])
    try:
        outcome=classify(rows,schema,policy); validate_answers(rows,outcome,answers)
        reconcile(rows,outcome,fixture.get('declared_counts'),fixture.get('declared_classes'))
    except Invalid as exc:
        require(fixture['expect_error'] in str(exc),f'wrong failure in {fixture["id"]}: {exc}')
        return {'id':fixture['id'],'passed':True,'observed_error':str(exc)}
    raise Invalid('negative fixture was accepted: '+fixture['id'])

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--assets',type=Path,default=ROOT/'assets'); ap.add_argument('--output',type=Path,default=ROOT/'validation-results.json'); args=ap.parse_args()
    require(args.output.resolve().is_relative_to(ROOT),'output must remain beside validator')
    assets=args.assets; rows=loadcsv(assets/'industrial-audit-fictional-batch.csv')
    schema=json.loads((assets/'industrial-audit-schema.json').read_text()); policy=json.loads((assets/'industrial-audit-policy.json').read_text())
    answers=loadcsv(assets/'industrial-audit-answer-key.csv')
    outcomes=classify(rows,schema,policy); validate_answers(rows,outcomes,answers)
    counts,classes=reconcile(rows,outcomes,policy['expected_counts'],policy['expected_classes'])
    shuffled=classify(list(reversed(rows)),schema,policy)
    require(sorted(shuffled,key=lambda r:r['row_id'])==sorted(outcomes,key=lambda r:r['row_id']),'row order changes decisions')
    negatives=[run_negative(f,rows,schema,policy,answers) for f in json.loads((ROOT/'negative-fixtures.json').read_text())]
    try: classify(loadcsv(assets/'industrial-audit-blank-rows.csv'),schema,policy)
    except Invalid: blank_rejected=True
    else: raise Invalid('blank template incorrectly accepted')
    includes=included_view(rows,outcomes)
    require(len(includes)==counts['include'],'included company uniqueness failed')
    fieldnames=['fiction_label','brief_id','brief_version','company_key','anchor_row_id','member_row_ids','site_keys','research_class']
    with (ROOT/'included-company-view.csv').open('w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=fieldnames); w.writeheader(); w.writerows(includes)
    result={'status':'PASS','executed_at_utc':datetime.now(timezone.utc).isoformat(),'counts':counts,'classes':classes,'negative_fixture_count':len(negatives),'negative_tests':negatives,'blank_template_rejected':blank_rejected,'derived_outcomes':outcomes,'included_view':includes,'input_sha256':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(assets.iterdir())},'validator_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'limits':'Declared fictional states only. Reconciliation checks accounting, not evidence truth or semantic support; classify and answer checks must precede it. No rights, legal, technical, delivery or outreach approval.'}
    args.output.write_text(json.dumps(result,indent=2,ensure_ascii=False)+'\n'); print(json.dumps({'status':result['status'],'counts':counts,'classes':classes,'negative_fixture_count':len(negatives)}))
if __name__=='__main__': main()
