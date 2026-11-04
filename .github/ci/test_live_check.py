"""Tests for live_check.py. No external network: a localhost HTTP server and injected fakes.

    python3 -B .github/ci/test_live_check.py
"""
import hashlib
import io
import ssl
import sys
import tempfile
import threading
import unittest
from contextlib import redirect_stdout
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest import mock

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(HERE))
import live_check  # noqa: E402

SITEMAP = b'<?xml version="1.0"?><urlset><url><loc>https://example.invalid/</loc></url></urlset>\n'
NOW = datetime(2026, 11, 4, 12, 0, tzinfo=timezone.utc)


def cert_until(dt):
    return {'notAfter': dt.strftime('%b %d %H:%M:%S %Y GMT')}


class Handler(BaseHTTPRequestHandler):
    routes = {}
    seen = []

    def do_GET(self):  # noqa: N802
        Handler.seen.append((self.path, self.headers.get('User-Agent')))
        status, body, loc = Handler.routes.get(self.path, (404, b'nope', None))
        self.send_response(status)
        if loc:
            self.send_header('Location', loc)
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *a):
        pass


class LocalServer(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.httpd = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        cls.base = f'http://127.0.0.1:{cls.httpd.server_address[1]}'
        cls.thread = threading.Thread(target=cls.httpd.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown()
        cls.httpd.server_close()

    def setUp(self):
        Handler.seen = []
        Handler.routes = {p: (200, b'ok', None) for p in live_check.PAGES}
        Handler.routes['/sitemap.xml'] = (200, SITEMAP, None)
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        (Path(self.tmp.name) / 'sitemap.xml').write_bytes(SITEMAP)

    def test_all_pages_200(self):
        res = live_check.check_pages(self.base, sleep=0)
        self.assertTrue(all(ok for ok, _ in res), res)
        self.assertEqual(len(res), len(live_check.PAGES))
        self.assertTrue(all(ua == live_check.USER_AGENT for _, ua in Handler.seen))

    def test_404_fails_without_retry(self):
        Handler.routes['/request-a-quote'] = (404, b'', None)
        res = dict((line.split(' ')[0], ok) for ok, line in live_check.check_pages(self.base, sleep=0))
        self.assertFalse(res['/request-a-quote'])
        self.assertEqual(sum(1 for p, _ in Handler.seen if p == '/request-a-quote'), 1)

    def test_5xx_retried_then_fails(self):
        Handler.routes['/'] = (503, b'', None)
        res = live_check.check_pages(self.base, sleep=0)
        self.assertFalse(res[0][0])
        self.assertIn('HTTP 503', res[0][1])
        self.assertEqual(sum(1 for p, _ in Handler.seen if p == '/'), live_check.ATTEMPTS)

    def test_same_host_redirect_followed(self):
        Handler.routes['/request-a-quote'] = (301, b'', '/request-a-quote/')
        Handler.routes['/request-a-quote/'] = (200, b'ok', None)
        res = dict((line.split(' ')[0], ok) for ok, line in live_check.check_pages(self.base, sleep=0))
        self.assertTrue(res['/request-a-quote'])

    def test_offsite_redirect_not_followed(self):
        Handler.routes['/'] = (302, b'', 'http://elsewhere.invalid/')
        res = live_check.check_pages(self.base, sleep=0)
        self.assertFalse(res[0][0])
        self.assertIn('302', res[0][1])

    def test_sitemap_match(self):
        ok, line = live_check.check_sitemap(self.base, self.tmp.name, sleep=0)
        self.assertTrue(ok, line)
        self.assertIn(hashlib.sha256(SITEMAP).hexdigest()[:8], line)

    def test_sitemap_mismatch(self):
        Handler.routes['/sitemap.xml'] = (200, SITEMAP + b'<!-- stale -->', None)
        ok, line = live_check.check_sitemap(self.base, self.tmp.name, sleep=0)
        self.assertFalse(ok)
        self.assertIn('!= main', line)

    def test_sitemap_missing_live_or_local(self):
        Handler.routes['/sitemap.xml'] = (404, b'', None)
        self.assertFalse(live_check.check_sitemap(self.base, self.tmp.name, sleep=0)[0])
        with tempfile.TemporaryDirectory() as empty:
            ok, line = live_check.check_sitemap(self.base, empty, sleep=0)
        self.assertFalse(ok)
        self.assertIn('no sitemap.xml', line)


class Retry(unittest.TestCase):
    def test_network_error_then_success(self):
        calls = []

        def flaky(url):
            calls.append(url)
            if len(calls) < 2:
                raise OSError('connection reset')
            return 200, b'x'
        self.assertEqual(live_check.fetch_retry('https://h.invalid/', flaky, sleep=0), (200, b'x', None))
        self.assertEqual(len(calls), 2)

    def test_network_error_every_time(self):
        def down(url):
            raise TimeoutError('timed out')
        status, _, err = live_check.fetch_retry('https://h.invalid/', down, sleep=0)
        self.assertIsNone(status)
        self.assertIn('TimeoutError', err)


class Cert(unittest.TestCase):
    def test_valid_cert(self):
        ok, line = live_check.check_cert('h.invalid', 14, lambda h: cert_until(NOW + timedelta(days=75)), NOW)
        self.assertTrue(ok, line)
        self.assertIn('2027-01-18', line)

    def test_cert_expiring_soon(self):
        ok, line = live_check.check_cert('h.invalid', 14, lambda h: cert_until(NOW + timedelta(days=5)), NOW)
        self.assertFalse(ok)
        self.assertIn('5 days', line)

    def test_cert_expired(self):
        self.assertFalse(live_check.check_cert('h.invalid', 14, lambda h: cert_until(NOW - timedelta(days=1)), NOW)[0])

    def test_handshake_failure(self):
        def bad(h):
            raise ssl.SSLCertVerificationError('hostname mismatch')
        ok, line = live_check.check_cert('h.invalid', 14, bad, NOW)
        self.assertFalse(ok)
        self.assertIn('verification failed', line)

    def test_unreadable_cert(self):
        self.assertFalse(live_check.check_cert('h.invalid', 14, lambda h: {}, NOW)[0])


class RunAndMain(unittest.TestCase):
    def test_https_only(self):
        with self.assertRaises(SystemExit):
            live_check.run('http://demandrange.com', '.', 14)

    def test_main_exit_codes(self):
        good = [(True, 'a'), (True, 'b')]
        with mock.patch.object(live_check, 'run', return_value=good), redirect_stdout(io.StringIO()) as out:
            self.assertEqual(live_check.main([]), 0)
        self.assertIn('2/2 passed', out.getvalue())
        with mock.patch.object(live_check, 'run', return_value=good + [(False, 'c')]), \
                redirect_stdout(io.StringIO()) as out:
            self.assertEqual(live_check.main([]), 1)
        self.assertIn('FAIL c', out.getvalue())

    def test_run_wires_all_checks(self):
        def fetcher(url):
            return 200, SITEMAP
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / 'sitemap.xml').write_bytes(SITEMAP)
            res = live_check.run('https://h.invalid', d, 14, fetcher=fetcher,
                                 cert_getter=lambda h: cert_until(NOW + timedelta(days=60)), now=NOW, sleep=0)
        self.assertEqual(len(res), len(live_check.PAGES) + 2)
        self.assertTrue(all(ok for ok, _ in res), res)


class PageListDrift(unittest.TestCase):
    def test_every_monitored_page_exists_in_repo(self):
        for path in live_check.PAGES:
            with self.subTest(path=path):
                name = 'index.html' if path == '/' else path.lstrip('/')
                self.assertTrue((REPO / name).is_file() or (REPO / (name + '.html')).is_file(),
                                f'{path} is monitored but not in the repo')


if __name__ == '__main__':
    unittest.main(verbosity=2)
