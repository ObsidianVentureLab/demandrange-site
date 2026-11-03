"""Tests for drift_report.py.   python3 -B .github/ci/test_drift_report.py"""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import drift_report  # noqa: E402


def make_tree(root, files):
    for rel, content in files.items():
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(content if isinstance(content, bytes) else content.encode('utf-8'))


class DriftReportTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='dr-drift-')
        self.built = Path(self.tmp.name) / 'built'
        self.ref = Path(self.tmp.name) / 'ref'
        make_tree(self.built, {
            'index.html': '<!doctype html>\n<title>A</title>\n<p>same</p>\n',
            'about.html': '<!doctype html>\n<title>About</title>\n<p>old line</p>\n<p>kept</p>\n',
            'styles.css': 'body{}',
            'only-built.html': 'x',
            'logo.png': b'\x89PNG\x00\x01',
            '.github/workflows/x.yml': 'ignored',
        })
        make_tree(self.ref, {
            'index.html': '<!doctype html>\n<title>A</title>\n<p>same</p>\n',
            'about.html': '<!doctype html>\n<title>About</title>\n<p>new line</p>\n<p>kept</p>\n<p>added</p>\n',
            'styles.css': 'body{}',
            'only-ref.csv': 'a,b',
            'logo.png': b'\x89PNG\x00\x02',
            'CNAME': 'demandrange.com',
            '.git/HEAD': 'ref: refs/heads/main',
        })

    def tearDown(self):
        self.tmp.cleanup()

    def test_counts_and_lists(self):
        r = drift_report.compare(self.built, self.ref)
        self.assertEqual(r['counts'], {'identical': 2, 'differing': 2, 'only_built': 1, 'only_reference': 2})
        self.assertEqual(r['only_built'], ['only-built.html'])
        self.assertEqual(r['only_reference'], ['CNAME', 'only-ref.csv'])
        self.assertEqual(r['identical'], ['index.html', 'styles.css'])
        self.assertTrue(r['has_drift'])
        by_file = {d['file']: d for d in r['differing']}
        self.assertEqual(by_file['about.html']['lines'], {'added': 2, 'removed': 1})
        self.assertNotIn('lines', by_file['logo.png'])

    def test_ignores_dot_dirs_and_custom_ignore(self):
        r = drift_report.compare(self.built, self.ref)
        self.assertFalse(any(f.startswith('.github') or f.startswith('.git/') for f in r['only_built'] + r['only_reference']))
        r2 = drift_report.compare(self.built, self.ref, ignore=('.git', '.github', 'CNAME'))
        self.assertEqual(r2['only_reference'], ['only-ref.csv'])

    def test_identical_trees_have_no_drift(self):
        r = drift_report.compare(self.ref, self.ref)
        self.assertFalse(r['has_drift'])
        self.assertIn('No drift', drift_report.markdown(r))

    def test_markdown_mentions_everything(self):
        md = drift_report.markdown(drift_report.compare(self.built, self.ref))
        for needle in ('| 2 | 2 | 1 | 2 |', '`about.html`', '+2 / -1', 'binary', '`only-ref.csv`', '`only-built.html`'):
            self.assertIn(needle, md)

    def test_cli_exit_codes_and_outputs(self):
        out_md, out_json = Path(self.tmp.name) / 'r.md', Path(self.tmp.name) / 'r.json'
        base = [sys.executable, '-B', str(HERE / 'drift_report.py'), '--built', str(self.built), '--reference', str(self.ref),
                '--markdown', str(out_md), '--json', str(out_json)]
        ok = subprocess.run(base, capture_output=True, text=True, timeout=60)
        self.assertEqual(ok.returncode, 0, ok.stderr)
        self.assertIn('drift=yes', ok.stdout)
        self.assertEqual(json.loads(out_json.read_text())['counts']['differing'], 2)
        self.assertIn('## Drift', out_md.read_text())
        strict = subprocess.run(base + ['--fail-on-drift'], capture_output=True, text=True, timeout=60)
        self.assertEqual(strict.returncode, 1)
        same = subprocess.run([sys.executable, '-B', str(HERE / 'drift_report.py'), '--built', str(self.ref), '--reference', str(self.ref), '--fail-on-drift'],
                              capture_output=True, text=True, timeout=60)
        self.assertEqual(same.returncode, 0, same.stderr)

    def test_missing_directory_fails(self):
        with self.assertRaises(SystemExit):
            drift_report.compare(self.built, Path(self.tmp.name) / 'nope')


if __name__ == '__main__':
    unittest.main(verbosity=1)
