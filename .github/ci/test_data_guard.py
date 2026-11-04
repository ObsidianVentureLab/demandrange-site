import importlib.util
import sys
import unittest
from pathlib import Path

spec = importlib.util.spec_from_file_location('data_guard', Path(__file__).with_name('data_guard.py'))
data_guard = importlib.util.module_from_spec(spec)
spec.loader.exec_module(data_guard)


def run(files):
    return data_guard.check(list(files), lambda path: files[path])


class DataGuard(unittest.TestCase):
    def test_fixtures_code_and_docs_pass(self):
        files = {'pipeline/cli.py': 'x', 'pipeline/README.md': 'ops@alpha-fixture.example',
                 'pipeline/examples/emails-fixture.csv': 'email\na@x.example\nb@demo.invalid\nc@example.com\nd@mail.example.org\n',
                 'pipeline/examples/brief-fixture.json': '{}', '.gitignore': 'out/', 'index.html': '<a href="mailto:partners@demandrange.com">',
                 'foundation/handover-fictional.csv': 'a,b'}
        self.assertEqual(run(files), [])

    def test_output_folders_and_databases_fail(self):
        for path in ('out/list-verified.csv', 'pipeline/out/x.json', 'deliveries/client/E1/MANIFEST.json',
                     'any/deliveries/c/list.csv', 'clients.sqlite', 'pipeline/examples/x.db', 'a/clients.sqlite-wal',
                     'b.db-shm', 'c.sqlite3-journal'):
            with self.subTest(path=path):
                self.assertEqual(len(run({path: ''})), 1)

    def test_data_files_under_pipeline_outside_examples_fail(self):
        for path in ('pipeline/real-list.csv', 'pipeline/tests/candidates.xlsx', 'pipeline/notes/brief.json'):
            with self.subTest(path=path):
                self.assertIn('outside pipeline/examples/', run({path: ''})[0])

    def test_a_real_looking_email_in_a_fixture_fails(self):
        problems = run({'pipeline/examples/emails-fixture.csv': 'email\nok@x.example\njane@realco.ie\nx@examples.com\n'})
        self.assertEqual(len(problems), 1)
        self.assertIn('examples.com, realco.ie', problems[0])

    def test_reserved_domains(self):
        for domain in ('x.example', 'A.EXAMPLE', 'demo.invalid', 'h.test', 'localhost', 'example.com', 'mail.example.net'):
            self.assertTrue(data_guard.reserved(domain), domain)
        for domain in ('examples.com', 'example.co', 'demandrange.com', 'notexample.com', 'gmail.com'):
            self.assertFalse(data_guard.reserved(domain), domain)


if __name__ == '__main__':
    unittest.main(argv=sys.argv[:1])
