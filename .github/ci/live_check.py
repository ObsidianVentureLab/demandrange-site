"""Daily live-site check for demandrange.com (build brief launch checklist M3).

    python3 -B .github/ci/live_check.py [--base https://demandrange.com] [--repo .] [--min-cert-days 14]

Read-only GETs against our own site, nothing else:
  1. each page in PAGES returns HTTP 200 (redirects followed, final URL must stay on --base host);
  2. the live /sitemap.xml is byte-identical (sha256) to sitemap.xml in the checked-out main,
     i.e. GitHub Pages is serving what main says it should;
  3. the TLS certificate for the --base host is valid for at least --min-cert-days more days.

Prints one line per check and exits 0 (all pass) or 1 (any failure), so a failed scheduled run
shows up as a failed workflow. Stdlib only. No secrets, no cookies, no form submissions.
"""
import argparse
import hashlib
import socket
import ssl
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit

PAGES = ('/', '/request-a-quote', '/contact', '/privacy', '/cookies', '/terms', '/sitemap.xml', '/robots.txt')
USER_AGENT = 'demandrange-site-live-check (GitHub Actions)'
TIMEOUT = 20
ATTEMPTS = 3
RETRY_SLEEP = 5


class _NoForeignRedirect(urllib.request.HTTPRedirectHandler):
    def __init__(self, host):
        self.host = host

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if urlsplit(newurl).hostname != self.host:
            raise urllib.error.HTTPError(newurl, code, f'redirect off-site to {urlsplit(newurl).hostname}', headers, fp)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def fetch(url, timeout=TIMEOUT, context=None):
    """GET url -> (status, body bytes). Redirects only within the same host. Raises on network error."""
    host = urlsplit(url).hostname
    handlers = [_NoForeignRedirect(host)]
    if context is not None:
        handlers.append(urllib.request.HTTPSHandler(context=context))
    opener = urllib.request.build_opener(*handlers)
    req = urllib.request.Request(url, headers={'User-Agent': USER_AGENT, 'Cache-Control': 'no-cache'})
    try:
        with opener.open(req, timeout=timeout) as resp:
            return resp.status, resp.read()
    except urllib.error.HTTPError as e:
        return e.code, b''


def fetch_retry(url, fetcher=fetch, attempts=ATTEMPTS, sleep=RETRY_SLEEP):
    """Retry transient failures (network errors, 5xx). Returns (status or None, body, error text)."""
    last = None
    for i in range(attempts):
        try:
            status, body = fetcher(url)
            if status < 500:
                return status, body, None
            last = f'HTTP {status}'
        except (OSError, ValueError) as e:  # URLError, timeouts, TLS errors are OSError
            last = f'{type(e).__name__}: {e}'
        if i + 1 < attempts:
            time.sleep(sleep)
    return None, b'', last


def check_pages(base, fetcher=fetch, sleep=RETRY_SLEEP):
    results = []
    for path in PAGES:
        url = base.rstrip('/') + path
        status, _, err = fetch_retry(url, fetcher, sleep=sleep)
        ok = status == 200
        results.append((ok, f'{path} -> {status if status is not None else err}'))
    return results


def check_sitemap(base, repo, fetcher=fetch, sleep=RETRY_SLEEP):
    local = Path(repo) / 'sitemap.xml'
    if not local.is_file():
        return False, f'sitemap: no sitemap.xml in {repo}'
    want = hashlib.sha256(local.read_bytes()).hexdigest()
    status, body, err = fetch_retry(base.rstrip('/') + '/sitemap.xml', fetcher, sleep=sleep)
    if status != 200:
        return False, f'sitemap: live fetch failed ({status if status is not None else err})'
    got = hashlib.sha256(body).hexdigest()
    if got != want:
        return False, f'sitemap: live {got[:8]} != main {want[:8]} (Pages not serving main, or a deploy is in flight)'
    return True, f'sitemap: live == main ({want[:8]})'


def peer_cert(host, port=443, timeout=TIMEOUT):
    ctx = ssl.create_default_context()  # verifies chain + hostname; a bad cert raises here
    with socket.create_connection((host, port), timeout=timeout) as sock:
        with ctx.wrap_socket(sock, server_hostname=host) as tls:
            return tls.getpeercert()


def cert_days_left(cert, now=None):
    not_after = datetime.fromtimestamp(ssl.cert_time_to_seconds(cert['notAfter']), tz=timezone.utc)
    now = now or datetime.now(timezone.utc)
    return (not_after - now).total_seconds() / 86400, not_after


def check_cert(host, min_days, getter=peer_cert, now=None):
    try:
        cert = getter(host)
    except (OSError, ssl.SSLError, ValueError) as e:
        return False, f'cert: {host} TLS handshake/verification failed ({type(e).__name__}: {e})'
    try:
        days, not_after = cert_days_left(cert, now)
    except (KeyError, ValueError, TypeError) as e:
        return False, f'cert: unreadable notAfter ({e})'
    ok = days >= min_days
    return ok, f'cert: {host} valid until {not_after:%Y-%m-%d} ({days:.0f} days, minimum {min_days})'


def run(base, repo, min_days, fetcher=fetch, cert_getter=peer_cert, now=None, sleep=RETRY_SLEEP):
    parts = urlsplit(base)
    if parts.scheme != 'https' or not parts.hostname:
        raise SystemExit(f'live_check: --base must be an https URL, got {base!r}')
    results = check_pages(base, fetcher, sleep=sleep)
    results.append(check_sitemap(base, repo, fetcher, sleep=sleep))
    results.append(check_cert(parts.hostname, min_days, cert_getter, now))
    return results


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--base', default='https://demandrange.com')
    ap.add_argument('--repo', default='.')
    ap.add_argument('--min-cert-days', type=int, default=14)
    args = ap.parse_args(argv)
    results = run(args.base, args.repo, args.min_cert_days)
    for ok, line in results:
        print(('PASS ' if ok else 'FAIL ') + line)
    failed = sum(1 for ok, _ in results if not ok)
    print(f'live_check: {len(results) - failed}/{len(results)} passed')
    return 1 if failed else 0


if __name__ == '__main__':
    sys.exit(main())
