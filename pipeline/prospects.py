"""ICP spec + Apollo client -> deduplicated company candidates -> CSV + manifest.

The output is a *candidate* list for analyst research. Every row carries
review_state=candidate_not_reviewed; nothing here decides fit, and no person-level data is
requested or written (company-level fields only, no phone numbers).
"""
from dataclasses import dataclass, field
import csv
import datetime as _dt
import hashlib
import json
import math
import re
from pathlib import Path

from . import __version__
from .apollo import MAX_PAGES, MAX_PER_PAGE, ORG_SEARCH_PATH, BudgetExceeded
from .icp import normalise_domain

CSV_COLUMNS = (
    'candidate_id', 'review_state', 'data_mode', 'brief_id', 'brief_version',
    'apollo_organization_id', 'company_name', 'primary_domain', 'website_url', 'linkedin_url',
    'industry', 'keywords', 'estimated_num_employees', 'founded_year',
    'city', 'state', 'country', 'short_description', 'retrieved_at', 'source',
)
REVIEW_STATE = 'candidate_not_reviewed'
SOURCE = 'apollo:' + ORG_SEARCH_PATH.strip('/')
FIXTURE_MODE = 'fixture'
LIVE_MODE = 'live'
FICTION_NOTICE = 'WHOLLY FICTIONAL FIXTURE DATA; NO REAL COMPANIES, NO EVIDENCE OR ACCEPTANCE'
SAFE_NAME = re.compile(r'[^A-Za-z0-9._-]+')


@dataclass
class Collection:
    records: list = field(default_factory=list)
    pages_fetched: int = 0
    total_entries: int = 0
    total_pages: int = 0
    partial_results_only: bool = False
    duplicates_dropped: int = 0
    excluded_locally: int = 0
    stopped_reason: str = ''


def plan(spec, per_page=MAX_PER_PAGE):
    """Pages/credits the request needs if every page is full and unique; no request is made.

    Duplicates and locally excluded domains can push the real count above min_pages, so the
    client's credit budget, not this estimate, is the hard stop.
    """
    per_page = max(1, min(int(per_page), MAX_PER_PAGE))
    pages = min(math.ceil(spec.requested_volume / per_page), MAX_PAGES)
    return {'requested_volume': spec.requested_volume, 'per_page': per_page,
            'min_pages': pages, 'min_credits': pages, 'hard_page_limit': MAX_PAGES,
            'params': spec.to_apollo_params()}


def _text(value):
    if value is None:
        return ''
    if isinstance(value, (list, tuple)):
        return '; '.join(_text(v) for v in value if _text(v))
    return ' '.join(str(value).split())


def normalise_organization(org, spec, *, data_mode, retrieved_at):
    domain = normalise_domain(org.get('primary_domain') or org.get('website_url') or '')
    return {
        'candidate_id': '',
        'review_state': REVIEW_STATE,
        'data_mode': data_mode,
        'brief_id': spec.brief_id,
        'brief_version': spec.brief_version,
        'apollo_organization_id': _text(org.get('id')),
        'company_name': _text(org.get('name')),
        'primary_domain': domain,
        'website_url': _text(org.get('website_url')),
        'linkedin_url': _text(org.get('linkedin_url')),
        'industry': _text(org.get('industry')),
        'keywords': _text(org.get('keywords')),
        'estimated_num_employees': _text(org.get('estimated_num_employees')),
        'founded_year': _text(org.get('founded_year')),
        'city': _text(org.get('city')),
        'state': _text(org.get('state')),
        'country': _text(org.get('country')),
        'short_description': _text(org.get('short_description'))[:500],
        'retrieved_at': retrieved_at,
        'source': SOURCE,
    }


def collect(spec, client, *, per_page=MAX_PER_PAGE, data_mode=LIVE_MODE, now=None):
    """Page through Apollo until requested_volume unique companies are collected or results end."""
    retrieved_at = (now or _dt.datetime.now(_dt.timezone.utc)).strftime('%Y-%m-%dT%H:%M:%SZ')
    params = spec.to_apollo_params()
    excluded = set(spec.excluded_domains)
    seen_ids, seen_domains = set(), set()
    result = Collection()
    per_page = max(1, min(int(per_page), MAX_PER_PAGE))
    page = 1
    while True:
        try:
            response = client.search_organizations(params, page=page, per_page=per_page)
        except BudgetExceeded as error:
            result.stopped_reason = 'credit budget reached: ' + str(error)
            if page == 1:
                raise
            break
        result.pages_fetched += 1
        result.total_entries = response.total_entries
        result.total_pages = response.total_pages
        result.partial_results_only = result.partial_results_only or response.partial_results_only
        for org in response.organizations:
            record = normalise_organization(org, spec, data_mode=data_mode, retrieved_at=retrieved_at)
            key_id, key_domain = record['apollo_organization_id'], record['primary_domain']
            if (key_id and key_id in seen_ids) or (key_domain and key_domain in seen_domains):
                result.duplicates_dropped += 1
                continue
            if key_id:
                seen_ids.add(key_id)
            if key_domain:
                seen_domains.add(key_domain)
            if key_domain and key_domain in excluded:
                result.excluded_locally += 1
                continue
            result.records.append(record)
            if len(result.records) >= spec.requested_volume:
                result.stopped_reason = 'requested_volume reached'
                break
        if result.stopped_reason:
            break
        if not response.organizations:
            result.stopped_reason = 'empty page'
            break
        if page >= response.total_pages:
            result.stopped_reason = 'last page reached'
            break
        if page >= MAX_PAGES:
            result.stopped_reason = 'Apollo display limit (500 pages) reached'
            break
        page += 1
    for index, record in enumerate(result.records, start=1):
        record['candidate_id'] = f'{index:04d}'
    return result


def _safe(name):
    return SAFE_NAME.sub('-', name).strip('-') or 'brief'


def write_outputs(result, spec, out_dir, *, data_mode, client=None, per_page=MAX_PER_PAGE, now=None):
    """Write <brief>-candidates.csv and manifest.json into out_dir; return both paths."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    stem = f'{_safe(spec.brief_id)}-{_safe(spec.brief_version)}-candidates'
    csv_path = out_dir / (stem + '.csv')
    manifest_path = out_dir / (stem + '.manifest.json')
    with csv_path.open('w', encoding='utf-8', newline='') as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_COLUMNS, lineterminator='\n')
        writer.writeheader()
        for record in result.records:
            writer.writerow({column: record.get(column, '') for column in CSV_COLUMNS})
    generated_at = (now or _dt.datetime.now(_dt.timezone.utc)).strftime('%Y-%m-%dT%H:%M:%SZ')
    manifest = {
        'tool': 'demandrange-pipeline', 'tool_version': __version__, 'generated_at': generated_at,
        'data_mode': data_mode,
        'fiction_notice': FICTION_NOTICE if data_mode == FIXTURE_MODE else None,
        'brief': spec.as_dict(),
        'apollo': {'endpoint': SOURCE, 'params': spec.to_apollo_params(), 'per_page': per_page,
                   'pages_fetched': result.pages_fetched, 'total_entries_reported': result.total_entries,
                   'total_pages_reported': result.total_pages, 'partial_results_only': result.partial_results_only,
                   'credits_used': getattr(client, 'credits_used', result.pages_fetched),
                   'requests_made': getattr(client, 'requests_made', result.pages_fetched)},
        'counts': {'candidates': len(result.records), 'duplicates_dropped': result.duplicates_dropped,
                   'excluded_locally': result.excluded_locally},
        'stopped_reason': result.stopped_reason,
        'output': {'csv': csv_path.name, 'columns': list(CSV_COLUMNS),
                   'sha256': hashlib.sha256(csv_path.read_bytes()).hexdigest()},
        'review_state': REVIEW_STATE,
        'note': 'Candidates for analyst research against the full ICP brief; not an accepted account list and not for delivery as-is.',
    }
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=False) + '\n', encoding='utf-8')
    return csv_path, manifest_path
