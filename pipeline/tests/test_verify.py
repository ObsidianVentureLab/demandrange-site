import csv
import datetime as dt
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from pipeline import verify, zerobounce as zb
from pipeline.tests.support import EXAMPLES

EMAILS = EXAMPLES / 'emails-fixture.csv'
RESULTS = EXAMPLES / 'zerobounce-results-fixture.json'
NOW = dt.datetime(2026, 11, 3, 12, 0, tzinfo=dt.timezone.utc)


def replay_client(budget=100):
    return zb.ZeroBounceClient(transport=zb.FixtureTransport.from_file(RESULTS), credit_budget=budget)


class Reading(unittest.TestCase):
    def test_detects_email_column(self):
        rows, columns, column = verify.read_rows(EMAILS)
        self.assertEqual(column, 'work_email')
        self.assertEqual(len(rows), 9)
        self.assertEqual(columns[0], 'fiction_notice')

    def test_errors(self):
        with self.assertRaisesRegex(verify.VerifyError, 'not found'):
            verify.read_rows('/nonexistent.csv')
        with self.assertRaisesRegex(verify.VerifyError, 'not in header'):
            verify.read_rows(EMAILS, 'nope')
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / 'x.csv'
            p.write_text('name,phone\nA,1\n', encoding='utf-8')
            with self.assertRaisesRegex(verify.VerifyError, 'no email column'):
                verify.read_rows(p)
            p.write_text('email,zb_status\na@b.example,valid\n', encoding='utf-8')
            with self.assertRaisesRegex(verify.VerifyError, 'already contains'):
                verify.read_rows(p)
            p.write_text('', encoding='utf-8')
            with self.assertRaisesRegex(verify.VerifyError, 'no header'):
                verify.read_rows(p)

    def test_plan_counts_unique_sendable(self):
        rows, _, column = verify.read_rows(EMAILS)
        self.assertEqual(verify.plan(rows, column), {'rows': 9, 'unique_addresses': 7, 'sendable': 6,
                                                      'skipped_local_syntax': 1, 'max_credits': 6, 'batches': 1})


class Verifying(unittest.TestCase):
    def test_fixture_end_to_end(self):
        rows, columns, column = verify.read_rows(EMAILS)
        client = replay_client()
        result = verify.verify_rows(rows, columns, column, client, data_mode=verify.FIXTURE_MODE, now=NOW)
        by_ref = {r['contact_ref']: r for r in result.rows}
        self.assertEqual(by_ref['C-0001']['verification_decision'], 'keep')
        self.assertEqual(by_ref['C-0002']['zb_status'], 'valid', 'duplicate address (case/space) verified once, mapped back')
        self.assertEqual(by_ref['C-0004']['verification_decision'], 'drop')
        self.assertEqual(by_ref['C-0006']['zb_status'], 'skipped_local_syntax')
        self.assertEqual(by_ref['C-0007']['zb_sub_status'], 'empty')
        self.assertEqual(by_ref['C-0008']['verification_decision'], 'drop')
        self.assertEqual(by_ref['C-0009']['verification_decision'], 'review')
        self.assertEqual(by_ref['C-0003']['zb_mx_found'], 'true')
        self.assertEqual(by_ref['C-0001']['verified_at'], '2026-11-03T12:00:00Z')
        self.assertEqual(by_ref['C-0001']['verification_source'], 'fixture')
        self.assertEqual((result.sent, result.batches, client.credits_used), (6, 1, 6))
        self.assertEqual(result.columns, columns + list(verify.ADDED_COLUMNS))
        self.assertTrue(all('firstname' not in r for r in result.rows))

    def test_batching_and_budget_stop_keeps_rows(self):
        rows, columns, column = verify.read_rows(EMAILS)
        client = replay_client(budget=4)
        result = verify.verify_rows(rows, columns, column, client, batch_size=2, data_mode=verify.FIXTURE_MODE)
        self.assertEqual(result.batches, 2)
        self.assertEqual(result.sent, 4)
        self.assertEqual(result.not_verified, 2)
        self.assertTrue(result.stopped_reason.startswith('credit budget reached'))
        unverified = [r for r in result.rows if r['zb_status'] == 'not_verified']
        self.assertEqual(len(unverified), 2)
        self.assertTrue(all(r['verification_decision'] == 'review' for r in unverified))
        self.assertEqual(len(result.rows), 9, 'every input row is written')

    def test_budget_smaller_than_batch_shrinks_the_batch(self):
        rows, columns, column = verify.read_rows(EMAILS)
        client = replay_client(budget=1)
        result = verify.verify_rows(rows, columns, column, client, batch_size=100, data_mode=verify.FIXTURE_MODE)
        self.assertEqual((result.batches, result.sent), (1, 1), 'a --credit-budget 1 first check sends exactly one address')
        self.assertLessEqual(client.credits_used, 1)
        self.assertTrue(result.stopped_reason.startswith('credit budget reached'))
        self.assertEqual(len(result.rows), 9, 'every input row is written')
        self.assertEqual(client.requests_made, 1)

    def test_zero_budget_raises_before_sending(self):
        rows, columns, column = verify.read_rows(EMAILS)
        client = replay_client(budget=0)
        with self.assertRaises(zb.BudgetExceeded):
            verify.verify_rows(rows, columns, column, client)
        self.assertEqual(client.requests_made, 0)

    def test_provider_text_cannot_run_as_a_spreadsheet_formula(self):
        # ZeroBounce-controlled values get the P2 formula guard; the analyst's own input column does not.
        canned = {'a@formula.example': {'status': 'valid', 'sub_status': '@cmd', 'did_you_mean': '=HYPERLINK("x")',
                                        'processed_at': '-not a date', 'domain_age_days': -5}}
        client = zb.ZeroBounceClient(transport=zb.FixtureTransport(canned), credit_budget=10)
        rows = [{'email': 'a@formula.example', 'note': '=SUM(1)'}]
        result = verify.verify_rows(rows, ['email', 'note'], 'email', client, data_mode=verify.FIXTURE_MODE, now=NOW)
        out = result.rows[0]
        self.assertEqual(out['zb_sub_status'], "'@cmd")
        self.assertEqual(out['zb_did_you_mean'], "'=HYPERLINK(\"x\")")
        self.assertEqual(out['zb_processed_at'], "'-not a date")
        self.assertEqual(out['zb_domain_age_days'], '-5', 'signed numbers stay numbers')
        self.assertEqual(out['zb_status'], 'valid')
        self.assertEqual(out['note'], '=SUM(1)', 'input columns are written back unchanged')
        for column in verify.ADDED_COLUMNS:
            self.assertNotRegex(out[column], r'^[=@+]', column)

    def test_dedupe_keeps_first_seen_order_and_sends_each_address_once(self):
        rows = [{'email': e} for e in ('Zed@x.example', 'amy@x.example', ' zed@X.example ', 'bob@x.example', 'AMY@x.example', '')]
        transport = zb.FixtureTransport({})
        client = zb.ZeroBounceClient(transport=transport, credit_budget=10)
        result = verify.verify_rows(rows, ['email'], 'email', client, data_mode=verify.FIXTURE_MODE, now=NOW)
        sent = [item['email_address'] for item in transport.calls[0]['body']['email_batch']]
        self.assertEqual(sent, ['zed@x.example', 'amy@x.example', 'bob@x.example'])
        self.assertEqual((result.unique_addresses, result.sent, len(result.rows)), (3, 3, 6))
        self.assertEqual(result.rows[5]['zb_sub_status'], 'empty')

    def test_live_source_label(self):
        rows, columns, column = verify.read_rows(EMAILS)
        result = verify.verify_rows(rows, columns, column, replay_client(), data_mode=verify.LIVE_MODE)
        self.assertEqual(result.rows[0]['verification_source'], 'zerobounce:v2/validatebatch')


class Writing(unittest.TestCase):
    def test_csv_and_manifest(self):
        rows, columns, column = verify.read_rows(EMAILS)
        client = replay_client()
        result = verify.verify_rows(rows, columns, column, client, data_mode=verify.FIXTURE_MODE, now=NOW)
        with tempfile.TemporaryDirectory() as tmp:
            csv_path, manifest_path = verify.write_outputs(result, EMAILS, tmp, data_mode=verify.FIXTURE_MODE, client=client, credit_budget=100, now=NOW)
            self.assertEqual(csv_path.name, 'emails-fixture-verified.csv')
            with csv_path.open(encoding='utf-8', newline='') as handle:
                written = list(csv.DictReader(handle))
            self.assertEqual(len(written), 9)
            self.assertEqual(list(written[0]), result.columns)
            manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
            self.assertEqual(manifest['output']['sha256'], hashlib.sha256(csv_path.read_bytes()).hexdigest())
            self.assertEqual(manifest['input']['sha256'], hashlib.sha256(EMAILS.read_bytes()).hexdigest())
            self.assertEqual(manifest['counts']['by_decision'], {'drop': 5, 'keep': 3, 'review': 1})
            self.assertEqual(manifest['zerobounce']['credits_charged'], 6)
            self.assertEqual(manifest['zerobounce']['base_url'], 'https://api-eu.zerobounce.net')
            self.assertEqual(manifest['fiction_notice'], verify.FICTION_NOTICE)
            self.assertIn('apostrophe', manifest['output']['formula_guard'])
            self.assertEqual(manifest['zerobounce']['credit_budget'], 100)
            self.assertNotIn('api_key', manifest_path.read_text(encoding='utf-8'))


if __name__ == '__main__':
    unittest.main()
