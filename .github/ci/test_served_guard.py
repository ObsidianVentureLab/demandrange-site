"""Tests for served_guard.py (the never-publish guard on the GitHub Pages tree).

    python3 -B .github/ci/test_served_guard.py

Stdlib only. Builds synthetic site trees in temp dirs (fixture names only, no real data) and
also asserts that this repository's own served tree passes.
"""
import io
import os
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(HERE))
import served_guard  # noqa: E402


class Tree:
    def __init__(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.add('index.html', '<!doctype html><html lang="en"><title>x</title></html>')
        self.add('CNAME', 'example.invalid\n')
        self.add('.nojekyll', '')

    def add(self, rel, text='x', data=None):
        p = self.root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        if data is not None:
            p.write_bytes(data)
        else:
            p.write_text(text, encoding='utf-8')
        return p

    def problems(self):
        return served_guard.problems(self.root)

    def close(self):
        self._tmp.cleanup()


class GuardTest(unittest.TestCase):
    def setUp(self):
        self.t = Tree()
        self.addCleanup(self.t.close)

    def assertFlagged(self, rel, needle, **kw):
        self.t.add(rel, **kw)
        hits = [p for p in self.t.problems() if p.startswith(rel + ':')]
        self.assertTrue(hits, f'{rel} was not flagged')
        self.assertIn(needle, hits[0])

    def test_minimal_site_passes(self):
        self.t.add('styles.css', 'a{}')
        self.t.add('data/list.csv', 'a,b\n')
        self.t.add('.well-known/security.txt', 'Contact: mailto:security@example.invalid\n')
        self.t.add('robots.txt', 'User-agent: *\n')
        self.t.add('sample.pdf', data=b'%PDF-1.4\n')
        self.assertEqual(self.t.problems(), [])

    def test_git_and_github_dirs_are_not_served(self):
        self.t.add('.github/ci/anything.py', 'print(1)')
        self.t.add('.github/workflows/x.yml', 'on: push')
        self.assertEqual(self.t.problems(), [])

    def test_forbidden_directories_at_any_depth(self):
        for rel in ('pipeline/cli.txt', 'quote-form/README.txt', 'foundation/entity.json',
                    'out/acme/list.csv', 'deliveries/acme/list.csv', 'a/b/pipeline/x.csv'):
            with self.subTest(rel=rel):
                self.assertFlagged(rel, 'forbidden directory')

    def test_apps_script_files(self):
        self.assertFlagged('Code.gs', 'forbidden file type')
        self.assertFlagged('appsscript.json', 'forbidden file name')
        self.assertFlagged('form_schema.json', 'forbidden file name')

    def test_database_files_and_sidecars(self):
        for rel in ('clients.sqlite', 'clients.sqlite3', 'clients.db', 'clients.db-wal',
                    'clients.db-shm', 'clients.sqlite-journal', 'CLIENTS.DB'):
            with self.subTest(rel=rel):
                self.assertFlagged(rel, 'forbidden file type')

    def test_sqlite_content_under_innocent_name(self):
        self.assertFlagged('report.csv', 'SQLite database content',
                           data=served_guard.SQLITE_MAGIC + b'\x10\x00rest')

    def test_secrets_and_keys(self):
        for rel in ('.env', 'prod.env', 'server.pem', 'deploy.key', 'id_ed25519', 'cert.p12'):
            with self.subTest(rel=rel):
                self.assertFlagged(rel, 'forbidden')

    def test_python_caches_and_editor_leftovers(self):
        for rel in ('x.pyc', 'page.html.orig', 'page.html.bak', 'notes.swp', 'page.html~', 'run.log'):
            with self.subTest(rel=rel):
                self.assertFlagged(rel, 'forbidden')

    def test_internal_docs(self):
        self.assertFlagged('CONSOLIDATION.md', 'forbidden file name')
        self.assertFlagged('production-manifest.json', 'forbidden file name')

    def test_unknown_type_fails_allow_list(self):
        for rel in ('notes.docx', 'archive.zip', 'tool.exe', 'Makefile', 'dump.parquet'):
            with self.subTest(rel=rel):
                self.assertFlagged(rel, 'not on the served allow-list')

    def test_bare_names_only_allowed_at_top(self):
        self.assertFlagged('sub/CNAME', 'not on the served allow-list')

    def test_dotfile_is_not_a_suffix(self):
        self.assertFlagged('.htpasswd', 'not on the served allow-list')

    @unittest.skipUnless(hasattr(os, 'symlink'), 'no symlinks')
    def test_symlink_flagged(self):
        target = self.t.add('real.html', '<!doctype html>')
        os.symlink(target, self.t.root / 'link.html')
        hits = [p for p in self.t.problems() if p.startswith('link.html:')]
        self.assertTrue(hits and 'symlink' in hits[0])

    def test_main_exit_codes(self):
        with redirect_stdout(io.StringIO()) as out:
            self.assertEqual(served_guard.main(['x', str(self.t.root)]), 0)
        self.assertIn('PASS', out.getvalue())
        self.t.add('pipeline/zerobounce.txt')
        with redirect_stdout(io.StringIO()) as out:
            self.assertEqual(served_guard.main(['x', str(self.t.root)]), 1)
        self.assertIn('FAIL pipeline/zerobounce.txt', out.getvalue())

    def test_bad_root(self):
        with tempfile.TemporaryDirectory() as d, redirect_stdout(io.StringIO()):
            self.assertEqual(served_guard.main(['x', d]), 2)

    def test_cli_subprocess(self):
        r = subprocess.run([sys.executable, '-B', str(HERE / 'served_guard.py'), str(self.t.root)],
                           capture_output=True, text=True, timeout=60)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)


class ThisRepository(unittest.TestCase):
    def test_repository_served_tree_passes(self):
        self.assertEqual(served_guard.problems(REPO), [])


if __name__ == '__main__':
    unittest.main(verbosity=2)
