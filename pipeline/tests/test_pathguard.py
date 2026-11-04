import contextlib
import io
import json
import os
import tempfile
import unittest
from pathlib import Path

from pipeline import cli, pathguard

REPO = Path(__file__).resolve().parents[2]
BRIEF = REPO / 'pipeline' / 'examples' / 'brief-fixture.json'


def fake_checkout(root):
    (root / '.git').mkdir()
    (root / 'pipeline' / 'examples').mkdir(parents=True)
    (root / 'pipeline' / '__init__.py').write_text('', encoding='utf-8')
    return root


def run(*argv):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = cli.main(list(argv))
    return code, out.getvalue(), err.getvalue()


class Guard(unittest.TestCase):
    def test_paths_outside_any_checkout_pass_resolved(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / 'out'
            self.assertEqual(pathguard.refuse_inside_repo(str(target), '--out'), target.resolve())

    def test_output_inside_a_checkout_is_refused_even_under_examples(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = fake_checkout(Path(tmp))
            for target in (root / 'out', root, root / 'pipeline' / 'examples' / 'x'):
                with self.assertRaisesRegex(pathguard.InsideRepoError, '--out'):
                    pathguard.refuse_inside_repo(str(target), '--out')

    def test_inputs_may_only_name_fixtures_under_examples(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = fake_checkout(Path(tmp))
            ok = root / 'pipeline' / 'examples' / 'brief.json'
            self.assertEqual(pathguard.refuse_inside_repo(str(ok), '--brief', allow_examples=True), ok.resolve())
            with self.assertRaisesRegex(pathguard.InsideRepoError, 'fictional fixtures'):
                pathguard.refuse_inside_repo(str(root / 'real-list.csv'), '--input', allow_examples=True)
            with self.assertRaises(pathguard.InsideRepoError, msg='../ cannot climb out of examples'):
                pathguard.refuse_inside_repo(str(root / 'pipeline' / 'examples' / '..' / 'x.csv'), '--input', allow_examples=True)

    def test_a_symlink_from_outside_into_a_checkout_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as elsewhere:
            root = fake_checkout(Path(tmp))
            link = Path(elsewhere) / 'out-link'
            link.symlink_to(root / 'out', target_is_directory=True)
            with self.assertRaises(pathguard.InsideRepoError):
                pathguard.refuse_inside_repo(str(link), '--out')

    def test_a_git_tree_without_this_pipeline_is_not_this_repo(self):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / '.git').mkdir()
            target = Path(tmp) / 'out'
            self.assertEqual(pathguard.refuse_inside_repo(str(target), '--out'), target.resolve())


@unittest.skipUnless((REPO / '.git').exists(), 'needs a git checkout (CI and local runs have one)')
class CliRefusesTheRealCheckout(unittest.TestCase):
    def test_out_inside_the_checkout_is_a_usage_error_and_writes_nothing(self):
        target = REPO / 'out-pathguard-test'
        self.assertFalse(target.exists())
        code, out, err = run('prospects', '--brief', str(BRIEF), '--out', str(target), '--fixture',
                             str(REPO / 'pipeline' / 'examples' / 'apollo-organizations-fixture.json'))
        self.assertEqual((code, out), (cli.EXIT_USAGE, ''))
        self.assertIn('path refused', json.loads(err)['error'])
        self.assertFalse(target.exists())

    def test_relative_out_from_inside_the_checkout_is_refused(self):
        cwd = os.getcwd()
        os.chdir(REPO)
        try:
            code, _, err = run('prospects', '--brief', str(BRIEF), '--out', 'out/')
        finally:
            os.chdir(cwd)
        self.assertEqual(code, cli.EXIT_USAGE)
        self.assertIn('--out out/', json.loads(err)['error'])

    def test_a_non_fixture_brief_inside_the_checkout_is_refused(self):
        code, _, err = run('validate', '--brief', str(REPO / 'pipeline' / 'README.md'))
        self.assertEqual(code, cli.EXIT_USAGE)
        self.assertIn('--brief', json.loads(err)['error'])

    def test_every_export_input_is_checked(self):
        with tempfile.TemporaryDirectory() as tmp:
            outside = Path(tmp) / 'a.csv'
            outside.write_text('email\n', encoding='utf-8')
            code, _, err = run('export', '--input', str(outside), str(REPO / 'pipeline' / 'README.md'),
                               '--out', str(Path(tmp) / 'd'), '--client', 'Demo', '--brief-ref', 'B-v1',
                               '--dictionary-version', 'D-v1', '--export-version', 'E-v1')
            self.assertFalse((Path(tmp) / 'd').exists())
        self.assertEqual(code, cli.EXIT_USAGE)
        self.assertIn('--input', json.loads(err)['error'])

    def test_db_inside_the_checkout_is_refused_and_not_created(self):
        target = REPO / 'clients-pathguard-test.sqlite'
        self.assertFalse(target.exists())
        code, _, err = run('db', '--db', str(target), 'init')
        self.assertEqual(code, cli.EXIT_USAGE)
        self.assertIn('--db', json.loads(err)['error'])
        self.assertFalse(target.exists())

    def test_fixture_brief_with_out_outside_is_accepted(self):
        with tempfile.TemporaryDirectory() as tmp:
            code, out, _ = run('prospects', '--brief', str(BRIEF), '--out', tmp)
        self.assertEqual(code, cli.EXIT_OK)
        self.assertTrue(json.loads(out)['dry_run'])


if __name__ == '__main__':
    unittest.main()
