import csv
import datetime as dt
import hashlib
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from pipeline import apollo, icp, prospects
from pipeline.tests.support import FAKE_KEY, brief, response_pages

NOW = dt.datetime(2026, 11, 3, 12, 0, tzinfo=dt.timezone.utc)


def replay_client(budget=apollo.MAX_PAGES, pages=None):
    transport = apollo.FixtureTransport(pages if pages is not None else response_pages())
    return apollo.ApolloClient(transport=transport, credit_budget=budget), transport


class Collecting(unittest.TestCase):
    def test_fixture_end_to_end_dedupes_and_excludes(self):
        spec = icp.from_dict(brief())
        client, transport = replay_client()
        result = prospects.collect(spec, client, data_mode=prospects.FIXTURE_MODE, now=NOW)
        self.assertEqual([r['apollo_organization_id'] for r in result.records],
                         ['fx-org-0001', 'fx-org-0002', 'fx-org-0004', 'fx-org-0006', 'fx-org-0007'])
        self.assertEqual([r['candidate_id'] for r in result.records], ['0001', '0002', '0003', '0004', '0005'])
        self.assertEqual(result.duplicates_dropped, 2, 'duplicate id and duplicate www. domain')
        self.assertEqual(result.excluded_locally, 1)
        self.assertEqual(result.pages_fetched, 3)
        self.assertEqual(result.stopped_reason, 'requested_volume reached')
        self.assertEqual(transport.calls[0]['body']['organization_locations[]'], ['Ireland', 'United Kingdom'])
        self.assertTrue(all(r['review_state'] == 'candidate_not_reviewed' for r in result.records))
        self.assertTrue(all(r['retrieved_at'] == '2026-11-03T12:00:00Z' for r in result.records))

    def test_repeated_excluded_domain_counts_as_excluded_not_duplicate(self):
        spec = icp.from_dict(brief())
        pages = response_pages()
        first = pages[0]['organizations']
        excluded = next(o for o in first if o['primary_domain'] == 'excluded-fixture.example')
        first.insert(first.index(excluded) + 1, dict(excluded, id='fx-org-0003-again'))
        client, _ = replay_client(pages=pages)
        result = prospects.collect(spec, client, data_mode=prospects.FIXTURE_MODE, now=NOW)
        self.assertEqual((result.excluded_locally, result.duplicates_dropped), (2, 2))
        self.assertNotIn('excluded-fixture.example', [r['primary_domain'] for r in result.records])

    def test_stops_at_requested_volume_without_fetching_more_pages(self):
        spec = icp.from_dict(brief(requested_volume=2))
        client, transport = replay_client()
        result = prospects.collect(spec, client, data_mode=prospects.FIXTURE_MODE)
        self.assertEqual(len(result.records), 2)
        self.assertEqual(len(transport.calls), 1)
        self.assertEqual(client.credits_used, 1)

    def test_stops_at_last_page_when_short(self):
        spec = icp.from_dict(brief(requested_volume=40))
        client, transport = replay_client()
        result = prospects.collect(spec, client, data_mode=prospects.FIXTURE_MODE)
        self.assertEqual(len(result.records), 5)
        self.assertEqual(result.stopped_reason, 'last page reached')
        self.assertEqual(len(transport.calls), 3)

    def test_budget_stops_collection_but_keeps_rows(self):
        spec = icp.from_dict(brief(requested_volume=40))
        client, transport = replay_client(budget=2)
        result = prospects.collect(spec, client, data_mode=prospects.FIXTURE_MODE)
        self.assertEqual(len(result.records), 3)
        self.assertTrue(result.stopped_reason.startswith('credit budget reached'))
        self.assertEqual(client.credits_used, 2)

    def test_budget_of_zero_raises_before_any_request(self):
        spec = icp.from_dict(brief())
        client, transport = replay_client(budget=0)
        with self.assertRaises(apollo.BudgetExceeded):
            prospects.collect(spec, client)
        self.assertEqual(transport.calls, [])

    def test_empty_first_page(self):
        spec = icp.from_dict(brief())
        client, _ = replay_client(pages=[{'organizations': [], 'pagination': {'total_pages': 0, 'total_entries': 0}}])
        result = prospects.collect(spec, client)
        self.assertEqual(result.records, [])
        self.assertEqual(result.stopped_reason, 'empty page')

    def test_normalisation_drops_phone_and_flattens_lists(self):
        spec = icp.from_dict(brief())
        org = response_pages()[0]['organizations'][0]
        record = prospects.normalise_organization(org, spec, data_mode='fixture', retrieved_at='t')
        self.assertEqual(set(record), set(prospects.CSV_COLUMNS))
        self.assertEqual(record['keywords'], 'process plant; pumps')
        self.assertEqual(record['estimated_num_employees'], '120')
        self.assertNotIn('+000', json.dumps(record))
        self.assertEqual(record['primary_domain'], 'alpha-fixture.example')

    def test_plan_reports_minimum_pages(self):
        spec = icp.from_dict(brief(requested_volume=250))
        p = prospects.plan(spec)
        self.assertEqual((p['min_pages'], p['min_credits'], p['per_page']), (3, 3, 100))
        for bad in (0, 101, 1000, -1, 'ten', None):
            with self.subTest(per_page=bad), self.assertRaisesRegex(apollo.ApolloError, 'per_page'):
                prospects.plan(spec, per_page=bad)
        self.assertEqual(prospects.plan(spec, per_page=2)['per_page'], 2)
        with self.assertRaisesRegex(apollo.ApolloError, 'per_page'):
            prospects.collect(spec, replay_client()[0], per_page=1000)
        self.assertEqual(prospects.plan(icp.from_dict(brief(requested_volume=50_000)))['min_pages'], 500)


class Writing(unittest.TestCase):
    def test_csv_and_manifest(self):
        spec = icp.from_dict(brief())
        client, _ = replay_client()
        result = prospects.collect(spec, client, data_mode=prospects.FIXTURE_MODE, now=NOW)
        with tempfile.TemporaryDirectory() as tmp:
            csv_path, manifest_path = prospects.write_outputs(result, spec, Path(tmp) / 'nested', data_mode=prospects.FIXTURE_MODE,
                                                              client=client, now=NOW)
            self.assertEqual(csv_path.name, 'DEMO-BRIEF-A-v1-candidates.csv')
            with csv_path.open(encoding='utf-8', newline='') as handle:
                rows = list(csv.DictReader(handle))
            self.assertEqual(len(rows), 5)
            self.assertEqual(list(rows[0]), list(prospects.CSV_COLUMNS))
            self.assertEqual(rows[0]['data_mode'], 'fixture')
            manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
            self.assertEqual(manifest['output']['sha256'], hashlib.sha256(csv_path.read_bytes()).hexdigest())
            self.assertEqual(manifest['counts'], {'candidates': 5, 'duplicates_dropped': 2, 'excluded_locally': 1})
            self.assertEqual(manifest['apollo']['credits_used'], 3)
            self.assertEqual(manifest['apollo']['params'], spec.to_apollo_params())
            self.assertEqual(manifest['fiction_notice'], prospects.FICTION_NOTICE)
            self.assertEqual(manifest['generated_at'], '2026-11-03T12:00:00Z')
            self.assertEqual(manifest['review_state'], 'candidate_not_reviewed')

    def test_apollo_text_cannot_run_as_a_formula_in_the_candidate_csv(self):
        pages = response_pages()
        first = pages[0]['organizations'][0]
        first['name'] = '=HYPERLINK("http://evil.example")'
        first['short_description'] = '-SUM(A1:A9)'
        first['keywords'] = ['@cmd', 'pumps']
        first['primary_phone'] = {'number': '+353 1 555 0000'}
        spec = icp.from_dict(brief())
        client, _ = replay_client(pages=pages)
        result = prospects.collect(spec, client, data_mode=prospects.FIXTURE_MODE, now=NOW)
        with tempfile.TemporaryDirectory() as tmp:
            csv_path, manifest_path = prospects.write_outputs(result, spec, tmp, data_mode=prospects.FIXTURE_MODE, client=client, now=NOW)
            with csv_path.open(encoding='utf-8', newline='') as handle:
                rows = list(csv.DictReader(handle))
            poisoned = [r for r in rows if r['apollo_organization_id'] == first['id']][0]
            self.assertEqual(poisoned['company_name'], "'=HYPERLINK(\"http://evil.example\")")
            self.assertEqual(poisoned['short_description'], "'-SUM(A1:A9)")
            self.assertTrue(poisoned['keywords'].startswith("'@cmd"), poisoned['keywords'])
            self.assertEqual(poisoned['primary_domain'], 'alpha-fixture.example', 'ordinary values are untouched')
            manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
            self.assertIn('apostrophe', manifest['output']['formula_guard'])
            self.assertEqual(manifest['apollo']['retries'], 0)

    def test_live_mode_manifest_has_no_fiction_notice_and_never_the_key(self):
        spec = icp.from_dict(brief())
        pages = response_pages()
        with mock.patch.dict(os.environ, {apollo.API_KEY_ENV: FAKE_KEY}):
            client = apollo.ApolloClient(live=True, transport=apollo.FixtureTransport(pages), credit_budget=5)
        result = prospects.collect(spec, client, data_mode=prospects.LIVE_MODE)
        with tempfile.TemporaryDirectory() as tmp:
            csv_path, manifest_path = prospects.write_outputs(result, spec, tmp, data_mode=prospects.LIVE_MODE, client=client)
            blob = csv_path.read_text(encoding='utf-8') + manifest_path.read_text(encoding='utf-8')
            self.assertNotIn(FAKE_KEY, blob)
            self.assertIsNone(json.loads(manifest_path.read_text(encoding='utf-8'))['fiction_notice'])

    def test_filenames_are_sanitised(self):
        spec = icp.from_dict(brief(brief_version='2026/11/03 draft'))
        with tempfile.TemporaryDirectory() as tmp:
            csv_path, _ = prospects.write_outputs(prospects.Collection(), spec, tmp, data_mode='fixture')
            self.assertEqual(csv_path.name, 'DEMO-BRIEF-A-2026-11-03-draft-candidates.csv')
            self.assertEqual(csv_path.read_text(encoding='utf-8').count('\n'), 1, 'header only')


if __name__ == '__main__':
    unittest.main()
