"""Minimal Apollo.io organization-search client.

- Endpoint: POST https://api.apollo.io/api/v1/mixed_companies/search (x-api-key header).
- 100 results per page max; 1 credit per page; display limit 50,000 records (500 pages).
- The key is read from the environment only when live=True and is never logged, printed
  or placed in exception text. Default is live=False: without an injected transport every
  call raises LiveDisabled; with an injected transport (fixture replay) no key is needed
  and nothing leaves the process.
- `transport(method, url, headers, body) -> (status, parsed_json_or_text)` is injectable
  so tests never touch the network.
"""
from dataclasses import dataclass
import json
import os
import time
import urllib.error
import urllib.request

API_KEY_ENV = 'APOLLO_API_KEY'
BASE_URL = 'https://api.apollo.io/api/v1'
ORG_SEARCH_PATH = '/mixed_companies/search'
MAX_PER_PAGE = 100
MAX_PAGES = 500
USER_AGENT = 'demandrange-pipeline/0.1 (+https://demandrange.com)'


class ApolloError(Exception):
    """Non-retryable API failure. Messages never contain the API key."""


class LiveDisabled(ApolloError):
    """The client was created with live=False (the default); no request is sent."""


class ApolloAuthError(ApolloError):
    """Missing or rejected credentials."""


class ApolloRateLimited(ApolloError):
    """HTTP 429 persisted beyond the retry budget."""


class BudgetExceeded(ApolloError):
    """The next request would spend more credits than allowed."""


@dataclass(frozen=True)
class SearchPage:
    page: int
    per_page: int
    total_entries: int
    total_pages: int
    organizations: tuple
    partial_results_only: bool = False


def urllib_transport(method, url, headers, body, timeout=30):
    data = json.dumps(body).encode('utf-8') if body is not None else None
    request = urllib.request.Request(url, data=data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310 (https only, fixed host)
            status, payload = response.status, response.read()
    except urllib.error.HTTPError as error:
        status, payload = error.code, error.read()
    text = payload.decode('utf-8', 'replace')
    try:
        return status, json.loads(text)
    except json.JSONDecodeError:
        return status, text


def refusing_transport(method, url, headers, body):
    raise LiveDisabled('ApolloClient was created with live=False; no request was sent to ' + url)


class FixtureTransport:
    """Replays canned organization-search pages (synthetic data) instead of calling Apollo.

    `pages` is a list of response payloads; page N of a request is served from pages[N-1].
    A request for a page that is not in the fixture gets an empty 200 page so pagination
    logic can be exercised end to end. Every request is recorded in `calls` for assertions.
    """

    def __init__(self, pages):
        if not isinstance(pages, list) or not all(isinstance(p, dict) for p in pages):
            raise ApolloError('fixture: "pages" must be a list of response objects')
        self.pages = pages
        self.calls = []

    @classmethod
    def from_file(cls, path):
        with open(path, encoding='utf-8') as handle:
            data = json.load(handle)
        if not isinstance(data, dict) or 'pages' not in data:
            raise ApolloError('fixture: top-level object must have a "pages" list')
        return cls(data['pages'])

    def __call__(self, method, url, headers, body):
        self.calls.append({'method': method, 'url': url, 'body': dict(body or {})})
        page = int((body or {}).get('page', 1))
        if 1 <= page <= len(self.pages):
            return 200, self.pages[page - 1]
        total = sum(len(p.get('organizations') or []) for p in self.pages)
        return 200, {'organizations': [], 'partial_results_only': False,
                     'pagination': {'page': page, 'per_page': int((body or {}).get('per_page', MAX_PER_PAGE)),
                                    'total_entries': total, 'total_pages': len(self.pages)}}


class ApolloClient:
    def __init__(self, *, live=False, transport=None, api_key_env=API_KEY_ENV, credit_budget=0,
                 max_retries=3, sleep=time.sleep, base_url=BASE_URL):
        self.live = bool(live)
        self.api_key_env = api_key_env
        self.credit_budget = int(credit_budget)
        self.credits_used = 0
        self.requests_made = 0
        self.max_retries = int(max_retries)
        self._sleep = sleep
        self.base_url = base_url.rstrip('/')
        if not self.live:
            self._key = None
            self.transport = transport or refusing_transport
            return
        key = os.environ.get(api_key_env, '')
        if not key.strip():
            raise ApolloAuthError(f'{api_key_env} is not set; export it in the environment (never in a file or argument)')
        self._key = key.strip()
        self.transport = transport or urllib_transport

    # -- helpers -------------------------------------------------------------------------------
    def _redact(self, text):
        text = str(text)
        return text.replace(self._key, '[REDACTED]') if self._key else text

    def _headers(self):
        headers = {'Content-Type': 'application/json', 'Accept': 'application/json',
                   'Cache-Control': 'no-cache', 'User-Agent': USER_AGENT}
        if self._key:
            headers['x-api-key'] = self._key
        return headers

    def _charge(self, credits=1):
        if self.credits_used + credits > self.credit_budget:
            raise BudgetExceeded(f'credit budget of {self.credit_budget} would be exceeded '
                                 f'(used {self.credits_used}, next request needs {credits}); raise --credit-budget deliberately')
        self.credits_used += credits

    def _refund(self, credits=1):
        # Apollo serves no page on an auth/plan rejection, so the reserved credit was not spent.
        self.credits_used = max(0, self.credits_used - credits)

    # -- API ---------------------------------------------------------------------------------------
    def search_organizations(self, params, page=1, per_page=MAX_PER_PAGE):
        if self.transport is refusing_transport:
            raise LiveDisabled('live=False and no replay transport: organization search not sent (dry run)')
        if not 1 <= int(per_page) <= MAX_PER_PAGE:
            raise ApolloError(f'per_page must be 1..{MAX_PER_PAGE}')
        if not 1 <= int(page) <= MAX_PAGES:
            raise ApolloError(f'page must be 1..{MAX_PAGES} (Apollo display limit)')
        body = dict(params)
        body['page'] = int(page)
        body['per_page'] = int(per_page)
        url = self.base_url + ORG_SEARCH_PATH
        self._charge(1)
        attempt = 0
        while True:
            attempt += 1
            try:
                status, payload = self.transport('POST', url, self._headers(), body)
            except LiveDisabled:
                raise
            except (OSError, ValueError) as error:  # transport/network failure: redact, retry, wrap
                if attempt > self.max_retries:
                    raise ApolloError('transport failure: ' + self._redact(error)) from None
                self._sleep(2 ** attempt)
                continue
            self.requests_made += 1
            if status == 200 and isinstance(payload, dict):
                return self._parse(payload, page, per_page)
            if status == 401:
                self._refund(1)
                raise ApolloAuthError(f'Apollo rejected the key in {self.api_key_env} (HTTP 401)')
            if status == 403:
                self._refund(1)
                raise ApolloError('Apollo returned HTTP 403: endpoint needs a paid plan or master API key: ' + self._redact(_detail(payload)))
            if status == 429 or 500 <= status < 600:
                if attempt > self.max_retries:
                    if status == 429:
                        raise ApolloRateLimited('rate limited after %d attempts: %s' % (attempt, self._redact(_detail(payload))))
                    raise ApolloError('Apollo HTTP %d after %d attempts' % (status, attempt))
                self._sleep(2 ** attempt)
                continue
            raise ApolloError('Apollo HTTP %d: %s' % (status, self._redact(_detail(payload))[:300]))

    def _parse(self, payload, page, per_page):
        pagination = payload.get('pagination') or {}
        organizations = payload.get('organizations') or []
        if not isinstance(organizations, list):
            raise ApolloError('unexpected response: organizations is not a list')
        return SearchPage(
            page=int(pagination.get('page', page)),
            per_page=int(pagination.get('per_page', per_page)),
            total_entries=int(pagination.get('total_entries', len(organizations))),
            total_pages=int(pagination.get('total_pages', 1)),
            organizations=tuple(o for o in organizations if isinstance(o, dict)),
            partial_results_only=bool(payload.get('partial_results_only', False)),
        )


def _detail(payload):
    if isinstance(payload, dict):
        details = payload.get('error_details')
        if isinstance(details, dict) and details.get('message'):
            return str(details['message'])
        return str(payload.get('error') or payload.get('message') or '')
    return str(payload or '')[:300]
