import contextlib
import io
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from pipeline import apollo, cli
from pipeline.tests.support import BRIEF_PATH, FAKE_KEY, RESPONSES_PATH


def run(*argv):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = cli.main(list(argv))
    return code, out.getvalue(), err.getvalue()


class Validate(unittest.TestCase):
    def test_ok(self):
        code, out, err = run('validate', '--brief', str(BRIEF_PATH))
        self.assertEqual(code, 0)
        data = json.loads(out)
        self.assertTrue(data['ok'])
        self.assertEqual(data['plan']['min_credits'], 1)

    def test_bad_brief(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'bad.json'
            path.write_text('{"brief_id": "X"}', encoding='utf-8')
            code, out, err = run('validate', '--brief', str(path))
        self.assertEqual(code, cli.EXIT_USAGE)
        self.assertIn('brief rejected', err)
        self.assertEqual(out, '')


class Prospects(unittest.TestCase):
    def test_default_is_dry_run_and_writes_nothing(self):
        with tempfile.TemporaryDirectory() as tmp:
            code, out, err = run('prospects', '--brief', str(BRIEF_PATH), '--out', tmp)
            self.assertEqual(code, 0)
            self.assertEqual(os.listdir(tmp), [])
        data = json.loads(out)
        self.assertTrue(data['dry_run'])
        self.assertFalse(data['sent'])
        self.assertIn('organization_locations[]', data['plan']['params'])

    def test_fixture_replay_writes_outputs(self):
        with tempfile.TemporaryDirectory() as tmp:
            code, out, err = run('prospects', '--brief', str(BRIEF_PATH), '--out', tmp, '--fixture', str(RESPONSES_PATH))
            self.assertEqual(code, 0, err)
            data = json.loads(out)
            self.assertEqual((data['data_mode'], data['candidates'], data['credits_used']), ('fixture', 5, 3))
            self.assertEqual(sorted(os.listdir(tmp)), ['DEMO-BRIEF-A-v1-candidates.csv', 'DEMO-BRIEF-A-v1-candidates.manifest.json'])

    def test_unwritable_out_path_is_a_usage_error_not_a_traceback(self):
        with tempfile.TemporaryDirectory() as tmp:
            blocker = Path(tmp) / 'file.txt'
            blocker.write_text('in the way', encoding='utf-8')
            code, out, err = run('prospects', '--brief', str(BRIEF_PATH), '--out', str(blocker / 'out'), '--fixture', str(RESPONSES_PATH))
        self.assertEqual(code, cli.EXIT_USAGE)
        self.assertEqual(out, '')
        self.assertFalse(json.loads(err)['ok'])
        self.assertIn('file error', err)

    def test_fixture_with_explicit_budget_is_capped(self):
        with tempfile.TemporaryDirectory() as tmp:
            code, out, err = run('prospects', '--brief', str(BRIEF_PATH), '--out', tmp, '--fixture', str(RESPONSES_PATH), '--credit-budget', '1')
            self.assertEqual(code, 0, err)
            data = json.loads(out)
            self.assertEqual(data['credits_used'], 1)
            self.assertTrue(data['stopped_reason'].startswith('credit budget reached'))

    def test_per_page_out_of_range_is_rejected_before_anything_runs(self):
        for bad in ('0', '101', '1000', '-5', 'ten'):
            with self.subTest(per_page=bad), tempfile.TemporaryDirectory() as tmp:
                err = io.StringIO()
                with contextlib.redirect_stderr(err), self.assertRaises(SystemExit) as stop:
                    cli.main(['prospects', '--brief', str(BRIEF_PATH), '--out', tmp, '--fixture', str(RESPONSES_PATH), '--per-page', bad])
                self.assertEqual(stop.exception.code, cli.EXIT_USAGE)
                self.assertIn('--per-page', err.getvalue())
                self.assertEqual(os.listdir(tmp), [], 'nothing written')

    def test_per_page_in_range_reaches_plan_requests_and_manifest_unchanged(self):
        with tempfile.TemporaryDirectory() as tmp:
            code, out, err = run('prospects', '--brief', str(BRIEF_PATH), '--out', tmp, '--fixture', str(RESPONSES_PATH), '--per-page', '2')
            self.assertEqual(code, 0, err)
            manifest = json.loads((Path(tmp) / 'DEMO-BRIEF-A-v1-candidates.manifest.json').read_text(encoding='utf-8'))
            self.assertEqual(manifest['apollo']['per_page'], 2)

    def test_live_without_budget_sends_nothing(self):
        with tempfile.TemporaryDirectory() as tmp, mock.patch.dict(os.environ, {apollo.API_KEY_ENV: FAKE_KEY}):
            code, out, err = run('prospects', '--brief', str(BRIEF_PATH), '--out', tmp, '--live')
            self.assertEqual(code, cli.EXIT_USAGE)
            self.assertIn('--credit-budget', err)
            self.assertEqual(os.listdir(tmp), [])

    def test_live_without_key_fails_cleanly_and_never_prints_a_key(self):
        env = {k: v for k, v in os.environ.items() if k != apollo.API_KEY_ENV}
        with tempfile.TemporaryDirectory() as tmp, mock.patch.dict(os.environ, env, clear=True):
            code, out, err = run('prospects', '--brief', str(BRIEF_PATH), '--out', tmp, '--live', '--credit-budget', '1')
        self.assertEqual(code, cli.EXIT_PROVIDER)
        self.assertIn(apollo.API_KEY_ENV, err)
        self.assertIn('ApolloAuthError', err)

    def test_live_with_key_is_blocked_by_the_test_network_guard(self):
        with tempfile.TemporaryDirectory() as tmp, mock.patch.dict(os.environ, {apollo.API_KEY_ENV: FAKE_KEY}):
            with self.assertRaisesRegex(AssertionError, 'network call attempted') as caught:
                run('prospects', '--brief', str(BRIEF_PATH), '--out', tmp, '--live', '--credit-budget', '1')
            self.assertEqual(os.listdir(tmp), [])
        self.assertNotIn(FAKE_KEY, str(caught.exception))

    def test_live_and_fixture_are_exclusive(self):
        with self.assertRaises(SystemExit):
            run('prospects', '--brief', str(BRIEF_PATH), '--out', 'x', '--live', '--fixture', str(RESPONSES_PATH))

    def test_bad_fixture_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            bad = Path(tmp) / 'fixture.json'
            bad.write_text('{"nope": 1}', encoding='utf-8')
            code, out, err = run('prospects', '--brief', str(BRIEF_PATH), '--out', tmp, '--fixture', str(bad))
        self.assertEqual(code, cli.EXIT_PROVIDER)
        self.assertIn('pages', err)


from pipeline import zerobounce as _zb  # noqa: E402
from pipeline.tests.support import EXAMPLES as _EXAMPLES  # noqa: E402

EMAILS_PATH = _EXAMPLES / 'emails-fixture.csv'
ZB_RESULTS_PATH = _EXAMPLES / 'zerobounce-results-fixture.json'


class Verify(unittest.TestCase):
    def test_default_is_dry_run(self):
        with tempfile.TemporaryDirectory() as tmp:
            code, out, err = run('verify', '--input', str(EMAILS_PATH), '--out', tmp)
            self.assertEqual(code, 0, err)
            self.assertEqual(os.listdir(tmp), [])
        data = json.loads(out)
        self.assertTrue(data['dry_run'])
        self.assertEqual(data['plan']['sendable'], 6)
        self.assertEqual(data['plan']['email_column'], 'work_email')

    def test_fixture_replay(self):
        with tempfile.TemporaryDirectory() as tmp:
            code, out, err = run('verify', '--input', str(EMAILS_PATH), '--out', tmp, '--fixture', str(ZB_RESULTS_PATH), '--batch-size', '4')
            self.assertEqual(code, 0, err)
            data = json.loads(out)
            self.assertEqual((data['rows'], data['addresses_sent'], data['credits_charged']), (9, 6, 6))
            self.assertEqual(sorted(os.listdir(tmp)), ['emails-fixture-verified.csv', 'emails-fixture-verified.manifest.json'])

    def test_fixture_manifest_records_the_budget_actually_enforced(self):
        for argv, expected in (((), 6), (('--credit-budget', '4'), 4)):
            with self.subTest(argv=argv), tempfile.TemporaryDirectory() as tmp:
                code, out, err = run('verify', '--input', str(EMAILS_PATH), '--out', tmp, '--fixture', str(ZB_RESULTS_PATH), *argv)
                self.assertEqual(code, 0, err)
                manifest = json.loads((Path(tmp) / 'emails-fixture-verified.manifest.json').read_text(encoding='utf-8'))
                self.assertEqual(manifest['zerobounce']['credit_budget'], expected, 'fixture mode defaults the budget to the sendable count')
                self.assertLessEqual(manifest['zerobounce']['credits_charged'], expected)

    def test_provider_error_mid_run_writes_partial_outputs_and_exits_3(self):
        from pipeline.tests.support import ScriptedTransport
        ok = (200, {'email_batch': [], 'errors': []})   # first batch: all addresses come back unknown (uncharged)
        scripted = ScriptedTransport(ok, _zb.ZeroBounceError('ZeroBounce HTTP 503 after 3 attempts'))
        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(_zb.FixtureTransport, 'from_file', staticmethod(lambda path: scripted)):
            code, out, err = run('verify', '--input', str(EMAILS_PATH), '--out', tmp, '--fixture', str(Path(tmp) / 'ignored.json'), '--batch-size', '1')
            self.assertEqual(code, cli.EXIT_PROVIDER, err)
            self.assertEqual(sorted(os.listdir(tmp)), ['emails-fixture-verified.csv', 'emails-fixture-verified.manifest.json'], 'partial outputs written')
            manifest = json.loads((Path(tmp) / 'emails-fixture-verified.manifest.json').read_text(encoding='utf-8'))
        data = json.loads(out)
        self.assertFalse(data['ok'])
        self.assertIn('HTTP 503', data['error'])
        self.assertEqual((data['addresses_sent'], data['not_verified']), (1, 5))
        self.assertEqual(manifest['counts']['not_verified'], 5)
        self.assertIn('HTTP 503', manifest['zerobounce']['provider_error'])

    def test_live_without_budget_sends_nothing(self):
        with tempfile.TemporaryDirectory() as tmp, mock.patch.dict(os.environ, {_zb.API_KEY_ENV: FAKE_KEY}):
            code, out, err = run('verify', '--input', str(EMAILS_PATH), '--out', tmp, '--live')
            self.assertEqual(code, cli.EXIT_USAGE)
            self.assertIn('--credit-budget', err)

    def test_live_without_key_fails_cleanly(self):
        env = {k: v for k, v in os.environ.items() if k != _zb.API_KEY_ENV}
        with tempfile.TemporaryDirectory() as tmp, mock.patch.dict(os.environ, env, clear=True):
            code, out, err = run('verify', '--input', str(EMAILS_PATH), '--out', tmp, '--live', '--credit-budget', '1')
        self.assertEqual(code, cli.EXIT_PROVIDER)
        self.assertIn(_zb.API_KEY_ENV, err)

    def test_live_with_key_hits_the_network_guard_before_writing(self):
        with tempfile.TemporaryDirectory() as tmp, mock.patch.dict(os.environ, {_zb.API_KEY_ENV: FAKE_KEY}):
            with self.assertRaisesRegex(AssertionError, 'network call attempted'):
                run('verify', '--input', str(EMAILS_PATH), '--out', tmp, '--live', '--credit-budget', '6')
            self.assertEqual(os.listdir(tmp), [])

    def test_bad_input(self):
        with tempfile.TemporaryDirectory() as tmp:
            code, out, err = run('verify', '--input', str(EMAILS_PATH), '--out', tmp, '--email-column', 'nope')
        self.assertEqual(code, cli.EXIT_USAGE)
        self.assertIn('input rejected', err)


class Credits(unittest.TestCase):
    def test_requires_live(self):
        code, out, err = run('credits')
        self.assertEqual(code, cli.EXIT_USAGE)
        self.assertIn('--live', err)

    def test_live_without_key(self):
        env = {k: v for k, v in os.environ.items() if k != _zb.API_KEY_ENV}
        with mock.patch.dict(os.environ, env, clear=True):
            code, out, err = run('credits', '--live')
        self.assertEqual(code, cli.EXIT_PROVIDER)
        self.assertNotIn(FAKE_KEY, err)


if __name__ == '__main__':
    unittest.main()
