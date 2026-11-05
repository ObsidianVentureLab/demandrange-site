"""Tests for served_data_guard.py. Standard library only.

    python -B .github/ci/test_served_data_guard.py
"""
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import served_data_guard as g  # noqa: E402


def write(root, rel, text):
    p = Path(root, rel)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding='utf-8')
    return p


class ServedDataGuardTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = self.tmp.name

    def tearDown(self):
        self.tmp.cleanup()

    def test_own_and_reserved_domains_pass(self):
        write(self.root, 'index.html', '<a href="mailto:partners@demandrange.com">x</a>')
        write(self.root, 'sample.csv', 'name,email\nA,a@acme.example\nB,b@example.org\nC,c@x.invalid\n')
        files, failures, _ = g.scan(self.root)
        self.assertEqual(files, 2)
        self.assertEqual(failures, [])

    def test_real_domain_in_root_csv_fails(self):
        write(self.root, 'leads-acme-2026-11.csv', 'email\njane@realco.ie\n')
        _, failures, _ = g.scan(self.root)
        self.assertEqual(len(failures), 1)
        self.assertIn('leads-acme-2026-11.csv', failures[0])
        self.assertIn('realco.ie', failures[0])
        self.assertNotIn('jane', failures[0])  # never print the address itself

    def test_real_domain_in_page_and_json_fail(self):
        write(self.root, 'about.html', 'contact someone@gmail.com')
        write(self.root, 'data/export.json', '{"e": "x@corp.co.uk"}')
        _, failures, _ = g.scan(self.root)
        self.assertEqual(len(failures), 2)

    def test_xlsx_parts_are_scanned(self):
        p = Path(self.root, 'list.xlsx')
        with zipfile.ZipFile(p, 'w') as z:
            z.writestr('xl/sharedStrings.xml', '<sst><si><t>buyer@plant-operator.de</t></si></sst>')
        _, failures, _ = g.scan(self.root)
        self.assertEqual(len(failures), 1)
        self.assertIn('plant-operator.de', failures[0])

    def test_github_and_git_dirs_are_not_served(self):
        write(self.root, '.github/ci/fixture.csv', 'e\nreal@realco.ie\n')
        write(self.root, '.git/config', 'email = someone@realco.ie')
        files, failures, _ = g.scan(self.root)
        self.assertEqual(files, 0)
        self.assertEqual(failures, [])

    def test_well_known_is_served_and_scanned(self):
        write(self.root, '.well-known/security.txt', 'Contact: mailto:security@realco.ie')
        _, failures, _ = g.scan(self.root)
        self.assertEqual(len(failures), 1)

    def test_pdf_listed_as_unscanned(self):
        Path(self.root, 'sample.pdf').write_bytes(b'%PDF-1.7 not text')
        files, failures, unscanned = g.scan(self.root)
        self.assertEqual((files, failures, unscanned), (1, [], ['sample.pdf']))

    def test_main_exit_codes(self):
        write(self.root, 'ok.csv', 'e\na@demandrange.com\n')
        self.assertEqual(g.main(['x', self.root]), 0)
        write(self.root, 'bad.csv', 'e\nb@realco.ie\n')
        self.assertEqual(g.main(['x', self.root]), 1)


if __name__ == '__main__':
    unittest.main(verbosity=1)
