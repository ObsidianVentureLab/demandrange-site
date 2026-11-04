"""Tests for the preview build and the clean-URL preview server.

    python3 -B .github/ci/test_preview.py

Stdlib only. Builds a preview of this repository into a temp dir, checks what is left out
and what is added, runs site_checks.py against the result, then serves it on an ephemeral
localhost port and exercises the GitHub-Pages-style URL mapping.
"""
import http.client
import json
import os
import subprocess
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from unittest import mock

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
PREVIEW = REPO / '.github' / 'preview'
sys.path.insert(0, str(PREVIEW))
sys.path.insert(0, str(HERE))
import build_preview  # noqa: E402
import serve  # noqa: E402
import site_checks  # noqa: E402


def tracked_files(repo):
    """Committed (plus staged) files relative to the repo root; working-tree walk if git is unavailable."""
    try:
        out = subprocess.run(['git', '-C', str(repo), 'ls-files', '-z'], capture_output=True, check=True).stdout
        names = {n.decode('utf-8') for n in out.split(b'\0') if n}
        if names:
            return {n for n in names if (repo / n).is_file()}
    except (OSError, subprocess.SubprocessError):
        pass
    return {p.relative_to(repo).as_posix() for p in repo.rglob('*') if p.is_file() and p.relative_to(repo).parts[0] != '.git'}


class PreviewBuildTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory(prefix='dr-preview-test-')
        cls.out = Path(cls.tmp.name) / '_site'
        cls.stamp = build_preview.build(REPO, cls.out)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_excludes_repo_plumbing_and_cname(self):
        for name in ('.git', '.github', 'CNAME'):
            self.assertFalse((self.out / name).exists(), name + ' must not be in a preview')
        self.assertTrue((self.out / 'index.html').is_file())
        self.assertTrue((self.out / '404.html').is_file())
        self.assertTrue((self.out / '.nojekyll').is_file(), 'served dot-file kept')
        self.assertTrue((self.out / '.well-known').is_dir(), 'served dot-dir kept')

    def test_copies_every_served_file(self):
        # Compare against the committed tree (git ls-files), so stray untracked files in a local
        # checkout do not change what this test asserts; fall back to the working tree without git.
        expected = {rel for rel in tracked_files(REPO) if rel.split('/', 1)[0] not in ('.git', '.github', 'CNAME')}
        untracked_copied = {p.relative_to(self.out).as_posix() for p in self.out.rglob('*') if p.is_file()} - expected - {'_headers', '_preview.json'}
        actual = {p.relative_to(self.out).as_posix() for p in self.out.rglob('*') if p.is_file()} - untracked_copied
        self.assertEqual(actual - expected, {'_headers', '_preview.json'})
        self.assertEqual(expected - actual, set())
        for rel in sorted(expected - {'robots.txt'}):
            self.assertEqual((REPO / rel).read_bytes(), (self.out / rel).read_bytes(), rel + ' changed')

    def test_output_may_not_be_an_ancestor_of_the_source(self):
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / 'a' / 'b'
            src.mkdir(parents=True)
            (src / 'index.html').write_text('<!doctype html><title>x</title>', encoding='utf-8')
            with self.assertRaises(SystemExit):
                build_preview.build(src, Path(tmp) / 'a')
            with self.assertRaises(SystemExit):
                build_preview.build(src, src / 'out')

    def test_noindex_by_default(self):
        robots = (self.out / 'robots.txt').read_text(encoding='utf-8')
        self.assertIn('Disallow: /', robots)
        self.assertIn('Sitemap: https://demandrange.com/sitemap.xml', robots)
        self.assertIn('X-Robots-Tag: noindex', (self.out / '_headers').read_text(encoding='utf-8'))
        stamp = json.loads((self.out / '_preview.json').read_text(encoding='utf-8'))
        self.assertTrue(stamp['preview'] and stamp['noindex'])
        self.assertEqual(stamp['files'], len([p for p in self.out.rglob('*') if p.is_file()]) - 2)

    def test_stamp_names_the_pr_head_not_the_merge_commit(self):
        head, merge = 'a' * 40, 'b' * 40
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.dict(os.environ, {'PREVIEW_SOURCE_SHA': head, 'GITHUB_SHA': merge, 'PR_NUMBER': '57'}):
                stamp = build_preview.build(REPO, Path(tmp) / 'site')
            self.assertEqual((stamp['source_commit'], stamp['pull_request']), (head, '57'))
            with mock.patch.dict(os.environ, {'GITHUB_SHA': merge}, clear=False):
                os.environ.pop('PREVIEW_SOURCE_SHA', None)
                self.assertEqual(build_preview.build(REPO, Path(tmp) / 'site2')['source_commit'], merge, 'falls back to GITHUB_SHA outside a PR')

    def test_allow_index_keeps_live_robots(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / 'site'
            build_preview.build(REPO, out, noindex=False)
            self.assertEqual((out / 'robots.txt').read_bytes(), (REPO / 'robots.txt').read_bytes())
            self.assertFalse((out / '_headers').exists())
            self.assertFalse(json.loads((out / '_preview.json').read_text())['noindex'])

    def test_refuses_to_overwrite_non_preview_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / 'precious'
            out.mkdir()
            (out / 'keep.txt').write_text('x')
            with self.assertRaises(SystemExit):
                build_preview.build(REPO, out)
            self.assertTrue((out / 'keep.txt').exists())
            # A previous preview build is replaced cleanly.
            build_preview.build(REPO, Path(tmp) / 'p')
            (Path(tmp) / 'p' / 'stale.html').write_text('x')
            build_preview.build(REPO, Path(tmp) / 'p')
            self.assertFalse((Path(tmp) / 'p' / 'stale.html').exists())

    def test_refuses_output_inside_source(self):
        with self.assertRaises(SystemExit):
            build_preview.build(REPO, REPO / '_site_should_not_exist')
        self.assertFalse((REPO / '_site_should_not_exist').exists())

    def test_cli_runs(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = subprocess.run([sys.executable, '-B', str(PREVIEW / 'build_preview.py'), '--source', str(REPO),
                                     '--output', str(Path(tmp) / 'out')], capture_output=True, text=True, timeout=120,
                                    env={**os.environ, 'PR_NUMBER': '0'})
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads(result.stdout)['pull_request'], '0')

    def test_preview_passes_site_checks(self):
        # Same output-only checks the main branch runs; the preview must not break them.
        from io import StringIO
        import contextlib
        buf = StringIO()
        with contextlib.redirect_stdout(buf):
            code = site_checks.main(['site_checks', str(self.out)])
        self.assertEqual(code, 0, buf.getvalue())
        self.assertIn('site_checks PASS', buf.getvalue())


class PreviewServerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory(prefix='dr-preview-serve-')
        cls.out = Path(cls.tmp.name) / '_site'
        build_preview.build(REPO, cls.out)
        cls.server = serve.make_server(cls.out, '127.0.0.1', 0)
        cls.port = cls.server.server_address[1]
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.tmp.cleanup()

    def get(self, path, method='GET'):
        conn = http.client.HTTPConnection('127.0.0.1', self.port, timeout=10)
        conn.request(method, path)
        response = conn.getresponse()
        body = response.read()
        conn.close()
        return response.status, dict((k.lower(), v) for k, v in response.getheaders()), body

    def test_root_is_index(self):
        status, headers, body = self.get('/')
        self.assertEqual(status, 200)
        self.assertEqual(body, (self.out / 'index.html').read_bytes())
        self.assertTrue(headers['content-type'].startswith('text/html'))
        self.assertIn('noindex', headers['x-robots-tag'])

    def test_clean_url_maps_to_html(self):
        status, _, body = self.get('/about')
        self.assertEqual(status, 200)
        self.assertEqual(body, (self.out / 'about.html').read_bytes())
        status, _, body = self.get('/about?x=1')
        self.assertEqual(status, 200)
        self.assertEqual(body, (self.out / 'about.html').read_bytes())

    def test_explicit_html_and_assets(self):
        status, _, body = self.get('/about.html')
        self.assertEqual(status, 200)
        self.assertEqual(body, (self.out / 'about.html').read_bytes())
        status, headers, body = self.get('/styles.css')
        self.assertEqual(status, 200)
        self.assertTrue(headers['content-type'].startswith('text/css'))
        self.assertEqual(body, (self.out / 'styles.css').read_bytes())
        status, headers, _ = self.get('/sitemap.xml')
        self.assertEqual(status, 200)
        status, headers, _ = self.get('/.well-known/security.txt')
        self.assertEqual(status, 200, 'served dot-dir must resolve')

    def test_missing_page_is_custom_404(self):
        status, _, body = self.get('/no-such-page')
        self.assertEqual(status, 404)
        self.assertEqual(body, (self.out / '404.html').read_bytes())

    def test_traversal_and_dotfiles_refused(self):
        for path in ('/../CNAME', '/..%2F..%2Fetc/passwd', '/.git/config', '/.github/workflows/site-checks.yml', '/%2e%2e/'):
            status, _, body = self.get(path)
            self.assertEqual(status, 404, path)
            self.assertEqual(body, (self.out / '404.html').read_bytes(), path)

    def test_head_has_no_body(self):
        status, headers, body = self.get('/', method='HEAD')
        self.assertEqual(status, 200)
        self.assertEqual(body, b'')
        self.assertEqual(int(headers['content-length']), (self.out / 'index.html').stat().st_size)

    def test_resolve_unit(self):
        self.assertEqual(serve.resolve(self.out, '/')[0], (self.out / 'index.html'))
        self.assertEqual(serve.resolve(self.out, '/markets')[0], (self.out / 'markets.html'))
        self.assertEqual(serve.resolve(self.out, '/markets/')[1], 404)
        self.assertEqual(serve.resolve(self.out, '/%00')[1], 404)


if __name__ == '__main__':
    unittest.main(verbosity=1)
