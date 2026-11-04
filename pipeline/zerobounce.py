"""Minimal ZeroBounce email-validation client (API v2, batch endpoint).

- Endpoint: POST {base_url}/v2/validatebatch, JSON body {"api_key": ..., "email_batch": [{"email_address": ...}]}.
  The key travels in the request body, never in a URL, and is never logged or placed in error text.
- Credits: 1 per validated address; "unknown" results are not charged (ZeroBounce docs). The budget is a hard
  cap: one credit per address is reserved before a batch is sent and is never refunded, whatever comes back
  (a missing, empty or unrecognised result still counts). credits_used is only the provider-side estimate.
- Default base URL is the EU endpoint (api-eu.zerobounce.net); the default api.zerobounce.net servers
  are in the United States. Override with base_url for other residency choices.
- Default is live=False: without an injected transport every call raises LiveDisabled; with an
  injected transport (fixture replay) no key is needed and nothing leaves the process.
- Credits: POST {base_url}/v2/getcredits with a form-encoded body, so the key stays out of the URL.
  ZeroBounce's v2-credit-balance doc states the endpoint accepts POST with the GET parameters as
  application/x-www-form-urlencoded from 3 September 2026 (re-checked 4 Nov 2026). Not charged.
  Credits == -1 means the key is invalid.
- Batch items send "ip_address": null, the form shown in ZeroBounce's own example request.
- base_url must be one of the three documented ZeroBounce hosts (ALLOWED_HOSTS); a typo can never
  send the key elsewhere.
"""
from dataclasses import dataclass
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request

API_KEY_ENV = 'ZEROBOUNCE_API_KEY'
EU_BASE_URL = 'https://api-eu.zerobounce.net'
US_BASE_URL = 'https://api-us.zerobounce.net'
DEFAULT_BASE_URL = EU_BASE_URL
ALLOWED_HOSTS = ('api.zerobounce.net', 'api-us.zerobounce.net', 'api-eu.zerobounce.net')
BATCH_PATH = '/v2/validatebatch'
CREDITS_PATH = '/v2/getcredits'
MAX_BATCH = 100
USER_AGENT = 'demandrange-pipeline/0.2 (+https://demandrange.com)'

STATUSES = ('valid', 'invalid', 'catch-all', 'unknown', 'spamtrap', 'abuse', 'do_not_mail')
# Decision the list step records for each status; the analyst can override "review" rows.
DECISIONS = {'valid': 'keep', 'invalid': 'drop', 'spamtrap': 'drop', 'abuse': 'drop', 'do_not_mail': 'drop',
             'catch-all': 'review', 'unknown': 'review'}
RESULT_FIELDS = ('address', 'status', 'sub_status', 'free_email', 'did_you_mean', 'mx_found', 'domain_age_days', 'processed_at')


class ZeroBounceError(Exception):
    """Non-retryable API failure. Messages never contain the API key."""


class LiveDisabled(ZeroBounceError):
    """The client was created with live=False (the default) and has no replay transport."""


class ZeroBounceAuthError(ZeroBounceError):
    """Missing or rejected credentials, or the account has no credits."""


class ZeroBounceRateLimited(ZeroBounceError):
    """HTTP 429 persisted beyond the retry budget."""


class BudgetExceeded(ZeroBounceError):
    """The next batch could spend more credits than allowed."""


@dataclass(frozen=True)
class BatchResult:
    results: tuple          # one dict per requested address, in request order, RESULT_FIELDS only
    errors: tuple           # error entries ZeroBounce returned for individual addresses
    charged: int            # credits charged (= results whose status is not "unknown")


def urllib_transport(method, url, headers, body, timeout=90):
    if body is None:
        data = None
    elif headers.get('Content-Type', '').startswith('application/x-www-form-urlencoded'):
        data = urllib.parse.urlencode(body).encode('utf-8')
    else:
        data = json.dumps(body).encode('utf-8')
    request = urllib.request.Request(url, data=data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310 (https only, fixed hosts)
            status, payload = response.status, response.read()
    except urllib.error.HTTPError as error:
        status, payload = error.code, error.read()
    text = payload.decode('utf-8', 'replace')
    try:
        return status, json.loads(text)
    except json.JSONDecodeError:
        return status, text


def refusing_transport(method, url, headers, body):
    raise LiveDisabled('ZeroBounceClient was created with live=False; no request was sent to ' + url)


class FixtureTransport:
    """Replays canned validation results keyed by lower-cased address; never touches the network.

    File shape: {"results": {"addr@example": {"status": ..., "sub_status": ..., ...}}, "credits": 123}.
    Addresses missing from the fixture come back as status "unknown" / sub_status "not_in_fixture".
    """

    def __init__(self, results, credits=0):
        if not isinstance(results, dict) or not all(isinstance(v, dict) for v in results.values()):
            raise ZeroBounceError('fixture: "results" must map addresses to result objects')
        self.results = {str(k).strip().lower(): v for k, v in results.items()}
        self.credits = credits
        self.calls = []

    @classmethod
    def from_file(cls, path):
        with open(path, encoding='utf-8') as handle:
            data = json.load(handle)
        if not isinstance(data, dict) or 'results' not in data:
            raise ZeroBounceError('fixture: top-level object must have a "results" map')
        return cls(data['results'], data.get('credits', 0))

    def __call__(self, method, url, headers, body):
        # Recorded for tests; the key is dropped so a fixture injected into a live client never holds it in memory.
        recorded = {k: v for k, v in body.items() if k != 'api_key'} if isinstance(body, dict) else body
        self.calls.append({'method': method, 'url': url, 'body': json.loads(json.dumps(recorded)) if recorded is not None else None})
        if url.endswith(CREDITS_PATH):
            return 200, {'Credits': str(self.credits)}
        batch = []
        for item in (body or {}).get('email_batch', []):
            address = str(item.get('email_address', ''))
            canned = self.results.get(address.strip().lower())
            if canned is None:
                canned = {'status': 'unknown', 'sub_status': 'not_in_fixture'}
            result = {'address': address, 'status': 'unknown', 'sub_status': '', 'free_email': False, 'did_you_mean': None,
                      'mx_found': None, 'domain_age_days': None, 'processed_at': '2026-01-01 00:00:00.000'}
            result.update(canned)
            batch.append(result)
        return 200, {'email_batch': batch, 'errors': []}


def _detail(payload):
    if isinstance(payload, dict):
        return str(payload.get('error') or payload.get('message') or payload.get('Message') or '')
    return str(payload or '')[:300]


class ZeroBounceClient:
    def __init__(self, *, live=False, transport=None, api_key_env=API_KEY_ENV, credit_budget=0,
                 max_retries=3, sleep=time.sleep, base_url=DEFAULT_BASE_URL):
        self.live = bool(live)
        self.api_key_env = api_key_env
        self.credit_budget = int(credit_budget)
        self.credits_used = 0          # estimate: results ZeroBounce reports as charged (status not "unknown")
        # Hard cap: one credit per address sent, reserved before the request and never refunded, so a
        # missing/empty/unrecognised response cannot let the run send more than credit_budget addresses.
        self.credits_reserved = 0
        self.requests_made = 0
        self.retries = 0   # retried requests (transport failure or HTTP 429/5xx)
        # Addresses re-sent after a failed attempt. ZeroBounce may have processed (and charged) the first
        # attempt, so these count against the budget as well: credits_reserved + credits_at_risk <= credit_budget.
        self.credits_at_risk = 0
        self.max_retries = int(max_retries)
        self._sleep = sleep
        self.base_url = base_url.rstrip('/')
        if not self.base_url.startswith('https://'):
            raise ZeroBounceError('base_url must use https')
        host = urllib.parse.urlsplit(self.base_url)
        if host.hostname not in ALLOWED_HOSTS or host.path or host.query or host.fragment or host.port:
            raise ZeroBounceError('base_url must be exactly https://<host> with host one of ' + ', '.join(ALLOWED_HOSTS)
                                  + ' (the API key is only ever sent to ZeroBounce)')
        if not self.live:
            self._key = None
            self.transport = transport or refusing_transport
            return
        key = os.environ.get(api_key_env, '')
        if not key.strip():
            raise ZeroBounceAuthError(f'{api_key_env} is not set; export it in the environment (never in a file or argument)')
        self._key = key.strip()
        self.transport = transport or urllib_transport

    # -- helpers -------------------------------------------------------------------------------
    def _redact(self, text):
        text = str(text)
        return text.replace(self._key, '[REDACTED]') if self._key else text

    def _headers(self, content_type='application/json'):
        return {'Content-Type': content_type, 'Accept': 'application/json', 'User-Agent': USER_AGENT}

    @property
    def worst_case_spend(self):
        """Credits reserved for every address sent plus re-sent attempts; never above credit_budget."""
        return self.credits_reserved + self.credits_at_risk

    def _reserve_retry(self, reserve, why):
        """Before re-sending a batch: the first attempt is already reserved and may have been charged, and the
        retry may cost `reserve` again. Stop here if the hard cap cannot cover the retry as well."""
        if reserve and self.worst_case_spend + reserve > self.credit_budget:
            raise BudgetExceeded(f'credit budget of {self.credit_budget} is a hard cap: re-sending this batch of {reserve} '
                                 f'after {why} could charge up to {reserve} more credit(s) (reserved {self.credits_reserved}, '
                                 f'at risk {self.credits_at_risk}); stopped before the retry')
        self.credits_at_risk += reserve
        self.retries += 1

    def _send(self, path, body, content_type='application/json', reserve=0):
        if self.transport is refusing_transport:
            raise LiveDisabled('live=False and no replay transport: nothing sent (dry run)')
        url = self.base_url + path
        attempt = 0
        while True:
            attempt += 1
            try:
                status, payload = self.transport('POST', url, self._headers(content_type), body)
            except LiveDisabled:
                raise
            except (OSError, ValueError) as error:
                if attempt > self.max_retries:
                    raise ZeroBounceError('transport failure: ' + self._redact(error)) from None
                self._reserve_retry(reserve, 'a transport failure')
                self._sleep(2 ** attempt)
                continue
            self.requests_made += 1
            if status == 200:
                if isinstance(payload, dict) and payload.get('error') and not payload.get('email_batch'):
                    message = self._redact(payload['error'])
                    if 'api key' in message.lower() or 'credit' in message.lower():
                        raise ZeroBounceAuthError(f'ZeroBounce rejected the request: {message} (key env {self.api_key_env})')
                    raise ZeroBounceError('ZeroBounce error: ' + message[:300])
                return payload
            if status in (401, 403):
                raise ZeroBounceAuthError(f'ZeroBounce HTTP {status}: ' + self._redact(_detail(payload))[:200])
            if status == 429 or 500 <= status < 600:
                if attempt > self.max_retries:
                    if status == 429:
                        raise ZeroBounceRateLimited('rate limited after %d attempts: %s' % (attempt, self._redact(_detail(payload))[:200]))
                    raise ZeroBounceError('ZeroBounce HTTP %d after %d attempts' % (status, attempt))
                self._reserve_retry(reserve, 'HTTP %d' % status)
                self._sleep(2 ** attempt)
                continue
            raise ZeroBounceError('ZeroBounce HTTP %d: %s' % (status, self._redact(_detail(payload))[:300]))

    # -- API -----------------------------------------------------------------------------------
    def get_credits(self):
        """Remaining credit balance (not charged). -1 from the API means the key is invalid."""
        body = {'api_key': self._key} if self._key else {}
        payload = self._send(CREDITS_PATH, body, 'application/x-www-form-urlencoded')
        try:
            credits = int(str((payload or {}).get('Credits', '')).strip())
        except (ValueError, AttributeError):
            raise ZeroBounceError('unexpected getcredits response: ' + self._redact(payload)[:200]) from None
        if credits < 0:
            raise ZeroBounceAuthError(f'ZeroBounce reports an invalid API key in {self.api_key_env} (Credits=-1)')
        return credits

    def validate_batch(self, addresses):
        addresses = [str(a) for a in addresses]
        if not addresses:
            return BatchResult((), (), 0)
        if len(addresses) > MAX_BATCH:
            raise ZeroBounceError(f'batch too large: {len(addresses)} > {MAX_BATCH}')
        if self.worst_case_spend + len(addresses) > self.credit_budget:
            raise BudgetExceeded(f'credit budget of {self.credit_budget} could be exceeded '
                                 f'(reserved {self.credits_reserved}, at risk {self.credits_at_risk}, this batch may charge up to '
                                 f'{len(addresses)}); raise --credit-budget deliberately')
        body = {'email_batch': [{'email_address': a, 'ip_address': None} for a in addresses]}
        if self._key:
            body['api_key'] = self._key
        # Reserved before sending and never refunded: whatever the response holds, these were sent.
        self.credits_reserved += len(addresses)
        payload = self._send(BATCH_PATH, body, reserve=len(addresses))
        if not isinstance(payload, dict) or not isinstance(payload.get('email_batch'), list):
            raise ZeroBounceError('unexpected validatebatch response (no email_batch list)')
        by_address = {}
        for item in payload['email_batch']:
            if isinstance(item, dict):
                by_address[str(item.get('address', '')).strip().lower()] = item
        results = []
        for address in addresses:
            item = by_address.get(address.strip().lower())
            if item is None:
                item = {'address': address, 'status': 'unknown', 'sub_status': 'missing_from_response'}
            results.append(_pick(item, address))
        charged = sum(1 for r in results if r['status'] != 'unknown')
        self.credits_used += charged
        errors = tuple(e for e in (payload.get('errors') or []) if isinstance(e, dict))
        return BatchResult(tuple(results), errors, charged)


def _pick(item, address):
    status = str(item.get('status') or 'unknown').strip().lower()
    if status not in STATUSES:
        status = 'unknown'
    picked = {'address': address, 'status': status, 'sub_status': str(item.get('sub_status') or '').strip().lower()}
    for key in ('free_email', 'did_you_mean', 'mx_found', 'domain_age_days', 'processed_at'):
        picked[key] = item.get(key)
    return picked
