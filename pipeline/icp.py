"""Ideal-customer-profile brief (JSON) -> validated spec -> Apollo organization-search filters.

The JSON mirrors the public worksheet `industrial-ideal-customer-profile-worksheet.csv`: the
brief is a set of rules, not an account list. Only the rules Apollo can filter on are mapped;
everything else (site activity, regulator evidence, group matching) stays with the analyst.
"""
from dataclasses import dataclass, asdict
import json
import re
from pathlib import Path

MAX_REQUESTED_VOLUME = 50_000          # Apollo display limit (500 pages x 100)
EMPLOYEE_RANGE = re.compile(r'^\d{1,7},\d{1,7}$')
SIC_CODE = re.compile(r'^\d{2,4}$')
NAICS_CODE = re.compile(r'^\d{2,6}(-\d{2,6})?$')
DOMAIN = re.compile(r'^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?(?:\.[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?)+$')


class ICPError(ValueError):
    """The brief cannot be turned into a search; the message says which field and why."""


def normalise_domain(value):
    text = str(value or '').strip().lower()
    text = re.sub(r'^[a-z]+://', '', text)
    text = text.split('/')[0].split('?')[0].split('#')[0]
    text = text.lstrip('@')
    if text.startswith('www.'):
        text = text[4:]
    return text


def _strings(data, key, *, lower=False):
    raw = data.get(key, [])
    if raw is None:
        raw = []
    if isinstance(raw, str):
        raw = [raw]
    if not isinstance(raw, list) or not all(isinstance(item, str) for item in raw):
        raise ICPError(f'{key}: must be a list of strings')
    items = []
    for item in raw:
        item = ' '.join(item.split())
        if lower:
            item = item.lower()
        if item and item not in items:
            items.append(item)
    return tuple(items)


@dataclass(frozen=True)
class ICPSpec:
    brief_id: str
    brief_version: str
    supplier_range: str
    counting_unit: str = 'company'
    territory_locations: tuple = ()
    excluded_locations: tuple = ()
    sic_codes: tuple = ()
    excluded_sic_codes: tuple = ()
    naics_codes: tuple = ()
    excluded_naics_codes: tuple = ()
    industries: tuple = ()
    keywords: tuple = ()
    excluded_keywords: tuple = ()
    employee_ranges: tuple = ()
    excluded_domains: tuple = ()
    requested_volume: int = 100
    exclusion_reference_version: str = ''
    notes: str = ''

    def validate(self):
        if not self.brief_id or not re.fullmatch(r'[A-Za-z0-9._-]{1,64}', self.brief_id):
            raise ICPError('brief_id: required; letters, digits, ., _ or - only (max 64)')
        if not self.brief_version:
            raise ICPError('brief_version: required (the brief must be versioned before research)')
        if not self.supplier_range:
            raise ICPError('supplier_range: required')
        if self.counting_unit != 'company':
            raise ICPError("counting_unit: only 'company' is supported; Apollo returns companies, not facilities")
        if not isinstance(self.requested_volume, int) or not 1 <= self.requested_volume <= MAX_REQUESTED_VOLUME:
            raise ICPError(f'requested_volume: integer between 1 and {MAX_REQUESTED_VOLUME}')
        if not any([self.territory_locations, self.sic_codes, self.naics_codes, self.industries, self.keywords]):
            raise ICPError('at least one positive filter is required: territory_locations, sic_codes, naics_codes, industries or keywords')
        for item in self.employee_ranges:
            if not EMPLOYEE_RANGE.match(item):
                raise ICPError(f'employee_ranges: {item!r} must look like "min,max", e.g. "50,200"')
            low, high = (int(part) for part in item.split(','))
            if low > high:
                raise ICPError(f'employee_ranges: {item!r} has min greater than max')
        for key, codes, pattern in (('sic_codes', self.sic_codes, SIC_CODE), ('excluded_sic_codes', self.excluded_sic_codes, SIC_CODE),
                                    ('naics_codes', self.naics_codes, NAICS_CODE), ('excluded_naics_codes', self.excluded_naics_codes, NAICS_CODE)):
            for code in codes:
                if not pattern.match(code):
                    raise ICPError(f'{key}: {code!r} is not a valid code')
        for domain in self.excluded_domains:
            if not DOMAIN.match(domain):
                raise ICPError(f'excluded_domains: {domain!r} is not a bare domain (use example.com)')
        if len(self.excluded_domains) > 1000:
            raise ICPError('excluded_domains: Apollo accepts at most 1000 excluded websites per request')
        if len(self.excluded_keywords) > 150:
            raise ICPError('excluded_keywords: Apollo accepts at most 150 excluded keywords')
        return self

    def to_apollo_params(self):
        """Filters for POST /api/v1/mixed_companies/search (array keys carry the [] suffix)."""
        params = {}

        def put(key, values):
            if values:
                params[key] = list(values)
        put('organization_locations[]', self.territory_locations)
        put('organization_not_locations[]', self.excluded_locations)
        put('organization_sic_codes[]', self.sic_codes)
        put('not_organization_sic_codes[]', self.excluded_sic_codes)
        put('organization_naics_codes[]', self.naics_codes)
        put('not_organization_naics_codes[]', self.excluded_naics_codes)
        put('organization_industries[]', self.industries)
        put('q_organization_keyword_tags[]', self.keywords)
        put('q_not_organization_keyword_tags[]', self.excluded_keywords)
        put('organization_num_employees_ranges[]', self.employee_ranges)
        put('not_organization_websites_list[]', self.excluded_domains)
        return params

    def as_dict(self):
        data = asdict(self)
        return {k: (list(v) if isinstance(v, tuple) else v) for k, v in data.items()}


def from_dict(data):
    if not isinstance(data, dict):
        raise ICPError('brief: top-level JSON value must be an object')
    known = set(ICPSpec.__dataclass_fields__)
    unknown = sorted(set(data) - known)
    if unknown:
        raise ICPError('brief: unknown fields ' + ', '.join(unknown) + ' (worksheet rules Apollo cannot filter on belong in "notes")')
    volume = data.get('requested_volume', 100)
    if isinstance(volume, bool) or not isinstance(volume, int):
        raise ICPError('requested_volume: must be an integer')
    spec = ICPSpec(
        brief_id=str(data.get('brief_id', '')).strip(),
        brief_version=str(data.get('brief_version', '')).strip(),
        supplier_range=' '.join(str(data.get('supplier_range', '')).split()),
        counting_unit=str(data.get('counting_unit', 'company')).strip().lower(),
        territory_locations=_strings(data, 'territory_locations'),
        excluded_locations=_strings(data, 'excluded_locations'),
        sic_codes=_strings(data, 'sic_codes'),
        excluded_sic_codes=_strings(data, 'excluded_sic_codes'),
        naics_codes=_strings(data, 'naics_codes'),
        excluded_naics_codes=_strings(data, 'excluded_naics_codes'),
        industries=_strings(data, 'industries', lower=True),
        keywords=_strings(data, 'keywords'),
        excluded_keywords=_strings(data, 'excluded_keywords'),
        employee_ranges=tuple(item.replace(' ', '') for item in _strings(data, 'employee_ranges')),
        excluded_domains=tuple(dict.fromkeys(normalise_domain(d) for d in _strings(data, 'excluded_domains'))),
        requested_volume=volume,
        exclusion_reference_version=str(data.get('exclusion_reference_version', '')).strip(),
        notes=str(data.get('notes', '')).strip(),
    )
    return spec.validate()


def load_icp(path):
    path = Path(path)
    try:
        data = json.loads(path.read_text(encoding='utf-8'))
    except FileNotFoundError:
        raise ICPError(f'brief: file not found: {path}')
    except json.JSONDecodeError as error:
        raise ICPError(f'brief: {path.name} is not valid JSON ({error.msg} at line {error.lineno})')
    return from_dict(data)
