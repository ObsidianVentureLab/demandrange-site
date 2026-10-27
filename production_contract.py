"""Offline baseline compatibility contract; not a deployment/approval controller.

Pins are frozen values copied from the reviewed public baseline, not computed
from the current client/schema at validation time. Changing this manifest needs
independent review of the entire candidate. It is not a same-host trust boundary.
"""
from pathlib import Path
import hashlib
import json
import csv
import re
from urllib.parse import urlsplit
import xml.etree.ElementTree as ET
from bs4 import BeautifulSoup
from site_guards import unique_object, validate_manifest

HERE = Path(__file__).resolve().parent
SOURCE = HERE / 'redesign-20260905-source'
QUOTE_ROUTE = 'request-a-quote.html'


def require(condition, message):
    # Explicit exceptions remain active with python -O.
    if not condition:
        raise ValueError(message)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate_quote_endpoint(endpoint):
    if not endpoint:
        return None
    require(isinstance(endpoint, str), 'Quote endpoint must be an exact URL string')
    require(not any(c.isspace() or ord(c) < 32 or ord(c) == 127 for c in endpoint),
            'Quote endpoint must not contain whitespace or control characters')
    parts = urlsplit(endpoint)
    require(parts.scheme == 'https', 'Quote endpoint must use HTTPS')
    require(parts.netloc == 'script.google.com',
            'Quote endpoint must use the exact script.google.com host without credentials or a port')
    require(re.fullmatch(r'(?:/macros/s/|/a/macros/demandrange\.com/s/)[A-Za-z0-9_-]{20,200}/exec', parts.path),
            'Quote endpoint must be a reviewed Apps Script /exec URL')
    require('?' not in endpoint and '#' not in endpoint,
            'Quote endpoint must not contain query or fragment data')
    require('TEST_DEPLOYMENT_ID' not in endpoint and '{{' not in endpoint,
            'Placeholder quote endpoint cannot be built')
    return endpoint


def no_symlink_path(path):
    for part in (path, *path.parents):
        require(not part.is_symlink(), 'Symlink path is not allowed: ' + str(part))


def file_set(root):
    no_symlink_path(root)
    require(root.is_dir(), 'Missing directory: ' + str(root))
    paths = list(root.rglob('*'))
    require(not any(p.is_symlink() for p in paths), 'Symlink in source/output tree')
    require(all(p.is_dir() or p.is_file() for p in paths), 'Non-regular source/output entry')
    return {p.relative_to(root).as_posix() for p in paths if p.is_file()}


def check_file_set(root, expected):
    actual = file_set(root)
    missing, extra = set(expected) - actual, actual - set(expected)
    require(not missing and not extra,
            f'File manifest mismatch: missing={sorted(missing)} unexpected={sorted(extra)}')


def load_contract(mode, endpoint):
    require(mode in {'production', 'fixture'}, 'Explicit supported mode required')
    manifest_path = HERE / 'production-manifest.json'
    no_symlink_path(manifest_path)
    contract = json.loads(manifest_path.read_text(encoding='utf-8'), object_pairs_hook=unique_object)
    validate_manifest(contract)
    # Production is the default and can NEVER be inferred from discovered output.
    if mode == 'production':
        require(bool(endpoint), 'Production endpoint required before output mutation or QA')
    validate_quote_endpoint(endpoint)
    matches = bool(endpoint) and hashlib.sha256(endpoint.encode()).hexdigest() == contract['quote_endpoint_sha256']
    if mode == 'production':
        require(matches, 'Quote endpoint does not match the exact reviewed endpoint')
        for name, expected in contract['protected_sources'].items():
            path = HERE / name
            no_symlink_path(path)
            require(path.is_file() and digest(path) == expected, 'Protected source drift: ' + name)
        from foundation_stage import quote_template
        composed = quote_template((HERE / 'quote-form/request-a-quote.template.html').read_text())
        require(hashlib.sha256(composed.encode()).hexdigest() == contract['proposed_effective_quote_template_sha256'],
                'Protected composed quote template drift; independent proposed-pin review required')
    else:
        require(not matches, 'Fixture mode cannot use the reviewed production endpoint')
    return contract


def expected_files(contract, mode, endpoint):
    return set(contract['public_files']) - ({QUOTE_ROUTE, *contract['generator_managed_files']} if mode == 'fixture' and not endpoint else set())


def preflight_source(contract):
    # README is deliberately not published; every other input must be declared.
    expected = set(contract['public_files']) - {QUOTE_ROUTE} - set(contract['generator_managed_files'])
    check_file_set(SOURCE, expected | set(contract['excluded_source_files']))
    check_retained(SOURCE, contract)
    file_set(HERE / 'foundation')  # Includes new generator inputs in symlink checks.
    for name in contract['safe_downloads']:
        validate_csv(HERE / 'foundation' / name, contract['safe_downloads'][name])
    from og02_guards import validate_assets
    validate_assets(HERE / 'foundation')


def check_retained(root, contract):
    for name, expected in contract['retained_assets'].items():
        path = root / name
        require(path.is_file() and digest(path) == expected, 'Retained asset drift: ' + name)


def validate_csv(path, declaration):
    no_symlink_path(path)
    require(path.is_file() and digest(path) == declaration['sha256'], 'Declared CSV byte drift: ' + path.name)
    rows = list(csv.reader(path.open(encoding='utf-8', newline='')))
    require(rows and rows[0] == declaration['columns'], 'CSV schema drift: ' + path.name)
    require(len(rows) - 1 == declaration['data_rows'], 'CSV row count drift: ' + path.name)
    if 'blank_value_column' in declaration:
        idx = rows[0].index(declaration['blank_value_column'])
        require(all(len(row) > idx and row[idx] == '' for row in rows[1:]), 'Worksheet values must remain blank')
    if 'unique_field_column' in declaration:
        idx = rows[0].index(declaration['unique_field_column'])
        names = [row[idx] for row in rows[1:] if len(row) > idx]
        require(len(names) == len(rows)-1 and all(names) and len(set(names)) == len(names), 'Worksheet field names must be unique')
    for row in rows:
        require(len(row) == len(rows[0]), 'CSV row width mismatch')
        for cell in row:
            require(not any(ord(c) < 32 or 127 <= ord(c) <= 159 for c in cell), 'CSV control-character risk')
            require(not cell.lstrip().startswith(('=', '+', '-', '@')), 'CSV spreadsheet formula risk')
            require(not re.search(r'https?://|[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}', cell, re.I), 'CSV live URL/contact risk')


def clean_output_path(output):
    # Do not resolve away symlinks before inspecting the caller-supplied path.
    output = Path(output).absolute()
    no_symlink_path(output)
    output = output.resolve()
    require(output != HERE and HERE not in output.parents and output not in HERE.parents,
            'Output must not overlap tooling/source directories')
    require(output.parent.is_dir(), 'Output parent must already exist')
    require(not output.exists() or (output.is_dir() and not any(output.iterdir())),
            'Output must be absent or empty; refusing to overwrite/delete existing files')
    return output


def validate_output(root, contract, mode, endpoint):
    root = Path(root).absolute()
    check_file_set(root, expected_files(contract, mode, endpoint))
    check_retained(root, contract)
    for name, declaration in contract['safe_downloads'].items():
        if name in expected_files(contract, mode, endpoint):
            validate_csv(root / name, declaration)
    if mode == 'production' or endpoint:
        from og02_guards import validate_assets
        validate_assets(root)
    if mode == 'production':
        require(digest(root / QUOTE_ROUTE) == contract['quote_output_sha256'],
                'Protected quote output differs from the proposed candidate pin (not release acceptance)')
        homepage = BeautifulSoup((root / 'index.html').read_text(encoding='utf-8'), 'html.parser')
        ctas = homepage.select('a.header-cta')
        require(len(ctas) == 1 and ctas[0].get('href') == QUOTE_ROUTE
                and ctas[0].get_text(' ', strip=True) == 'Request a quote',
                'Homepage quote CTA must link directly to request-a-quote.html')
    sitemap = ET.parse(root / 'sitemap.xml')
    ns = {'s': 'http://www.sitemaps.org/schemas/sitemap/0.9'}
    actual = [el.text for el in sitemap.findall('s:url/s:loc', ns)]
    expected = set(contract['sitemap_urls'])
    if mode == 'fixture' and not endpoint:
        expected.remove('https://demandrange.com/' + QUOTE_ROUTE)
        expected -= {'https://demandrange.com/' + r for r in contract['generator_managed_files']}
    require(len(actual) == len(expected) and set(actual) == expected,
            'Sitemap exact membership/uniqueness mismatch')
    return root
