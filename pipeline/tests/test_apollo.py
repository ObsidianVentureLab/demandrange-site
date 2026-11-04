import io
import os
import unittest
from unittest import mock

from pipeline import apollo
from pipeline.tests.support import FAKE_KEY, ScriptedTransport, response_pages

PARAMS = {'organization_locations[]': ['Ireland']}


def page_payload(n, ids, total_pages=1):
    return 200, {'organizations': [{'id': i, 'name': i, 'primary_domain': i + '.example'} for i in ids],
                 'pagination': {'page': n, 'per_page': 100, 'total_entries': len(ids), 'total_pages': total_pages}}


class OfflineDefaults(unittest.TestCase):
    def test_default_client_sends_nothing_and_reads_no_key(self):
        with mock.patch.dict(os.environ, {apollo.API_KEY_ENV: FAKE_KEY}):
            client = apollo.ApolloClient()
        self.assertIsNone(client._key)
        with self.assertRaises(apollo.LiveDisabled):
            client.search_organizations(PARAMS)
        self.assertEqual(client.credits_used, 0)
        self.assertEqual(client.requests_made, 0)

    def test_live_without_env_key_fails_before_any_request(self):
        env = {k: v for k, v in os.environ.items() if k != apollo.API_KEY_ENV}
        with mock.patch.dict(os.environ, env, clear=True):
            with self.assertRaisesRegex(apollo.ApolloAuthError, apollo.API_KEY_ENV):
                apollo.ApolloClient(live=True, credit_budget=5)
        with mock.patch.dict(os.environ, {apollo.API_KEY_ENV: '   '}):
            with self.assertRaises(apollo.ApolloAuthError):
                apollo.ApolloClient(live=True, credit_budget=5)

    def test_replay_transport_needs_no_key_and_sends_no_key_header(self):
        transport = apollo.FixtureTransport(response_pages())
        client = apollo.ApolloClient(transport=transport, credit_budget=3)
        page = client.search_organizations(PARAMS, page=2)
        self.assertEqual(page.page, 2)
        self.assertEqual(len(page.organizations), 3)
        self.assertEqual(transport.calls[0]['body']['page'], 2)
        self.assertEqual(client.credits_used, 1)

    def test_fixture_transport_serves_empty_page_past_the_end(self):
        transport = apollo.FixtureTransport(response_pages())
        client = apollo.ApolloClient(transport=transport, credit_budget=10)
        page = client.search_organizations(PARAMS, page=9)
        self.assertEqual(page.organizations, ())
        self.assertEqual(page.total_pages, 3)

    def test_fixture_file_shape_is_checked(self):
        with self.assertRaises(apollo.ApolloError):
            apollo.FixtureTransport({'pages': []})
        with self.assertRaises(apollo.ApolloError):
            apollo.FixtureTransport(['not a dict'])


class LiveClientWithFakeTransport(unittest.TestCase):
    def client(self, *responses, budget=10, retries=2):
        transport = ScriptedTransport(*responses)
        with mock.patch.dict(os.environ, {apollo.API_KEY_ENV: FAKE_KEY}):
            client = apollo.ApolloClient(live=True, transport=transport, credit_budget=budget,
                                         max_retries=retries, sleep=lambda s: self.sleeps.append(s))
        return client, transport

    def setUp(self):
        self.sleeps = []

    def test_request_shape(self):
        client, transport = self.client(page_payload(1, ['a']))
        client.search_organizations(PARAMS, page=1, per_page=50)
        call = transport.calls[0]
        self.assertEqual(call['method'], 'POST')
        self.assertEqual(call['url'], 'https://api.apollo.io/api/v1/mixed_companies/search')
        self.assertEqual(call['headers']['x-api-key'], FAKE_KEY)
        self.assertEqual(call['headers']['Content-Type'], 'application/json')
        self.assertEqual(call['body'], {'organization_locations[]': ['Ireland'], 'page': 1, 'per_page': 50})
        self.assertEqual(client.credits_used, 1)
        self.assertEqual(client.requests_made, 1)

    def test_page_and_per_page_bounds(self):
        client, _ = self.client()
        for kwargs in ({'per_page': 0}, {'per_page': 101}, {'page': 0}, {'page': apollo.MAX_PAGES + 1}):
            with self.assertRaises(apollo.ApolloError):
                client.search_organizations(PARAMS, **kwargs)
        self.assertEqual(client.credits_used, 0)

    def test_budget_is_charged_before_sending(self):
        client, transport = self.client(page_payload(1, ['a']), page_payload(2, ['b']), budget=1)
        client.search_organizations(PARAMS, page=1)
        with self.assertRaisesRegex(apollo.BudgetExceeded, 'credit budget of 1'):
            client.search_organizations(PARAMS, page=2)
        self.assertEqual(len(transport.calls), 1)
        self.assertEqual(client.credits_used, 1)

    def test_zero_budget_blocks_the_first_request(self):
        client, transport = self.client(page_payload(1, ['a']), budget=0)
        with self.assertRaises(apollo.BudgetExceeded):
            client.search_organizations(PARAMS)
        self.assertEqual(transport.calls, [])

    def test_401_and_403_are_not_retried(self):
        client, transport = self.client((401, {'error': 'nope'}))
        with self.assertRaisesRegex(apollo.ApolloAuthError, '401'):
            client.search_organizations(PARAMS)
        self.assertEqual(client.credits_used, 0, 'a rejected key serves no page: reserved credit is released')
        client, transport = self.client((403, {'error_details': {'message': 'plan'}}))
        with self.assertRaisesRegex(apollo.ApolloError, '403.*plan'):
            client.search_organizations(PARAMS)
        self.assertEqual(client.credits_used, 0, 'a plan rejection serves no page: reserved credit is released')
        self.assertEqual(self.sleeps, [])

    def test_other_http_errors_keep_the_charge(self):
        client, transport = self.client((404, {'error': 'gone'}))
        with self.assertRaisesRegex(apollo.ApolloError, '404'):
            client.search_organizations(PARAMS)
        self.assertEqual(client.credits_used, 1, 'unexpected statuses stay conservatively counted')

    def test_429_and_5xx_retry_with_backoff_then_succeed(self):
        client, transport = self.client((429, {'error': 'slow down'}), (503, 'bad gateway'), page_payload(1, ['a']))
        page = client.search_organizations(PARAMS)
        self.assertEqual([o['id'] for o in page.organizations], ['a'])
        self.assertEqual(self.sleeps, [2, 4])
        self.assertEqual(client.credits_used, 1, 'retries of one page cost one credit')
        self.assertEqual(client.requests_made, 3)

    def test_429_beyond_retry_budget(self):
        client, _ = self.client(*([(429, {'error': 'x'})] * 3), retries=2)
        with self.assertRaises(apollo.ApolloRateLimited):
            client.search_organizations(PARAMS)

    def test_transport_exceptions_are_retried_and_redacted(self):
        client, _ = self.client(OSError('connection reset while sending ' + FAKE_KEY),
                                OSError('again ' + FAKE_KEY), OSError('and again ' + FAKE_KEY), retries=2)
        with self.assertRaises(apollo.ApolloError) as caught:
            client.search_organizations(PARAMS)
        self.assertNotIn(FAKE_KEY, str(caught.exception))
        self.assertIn('[REDACTED]', str(caught.exception))

    def test_error_bodies_echoing_the_key_are_redacted(self):
        client, _ = self.client((400, {'error': 'bad key ' + FAKE_KEY}))
        with self.assertRaises(apollo.ApolloError) as caught:
            client.search_organizations(PARAMS)
        self.assertNotIn(FAKE_KEY, str(caught.exception))

    def test_malformed_success_payloads(self):
        client, _ = self.client((200, {'organizations': 'not-a-list'}))
        with self.assertRaises(apollo.ApolloError):
            client.search_organizations(PARAMS)
        client, _ = self.client((200, {}))
        page = client.search_organizations(PARAMS)
        self.assertEqual(page.organizations, ())
        self.assertEqual(page.total_pages, 1)
        client, _ = self.client((200, 'text/html body'))
        with self.assertRaises(apollo.ApolloError):
            client.search_organizations(PARAMS)


class UrllibTransport(unittest.TestCase):
    def test_default_live_transport_is_urllib_and_tests_block_it(self):
        with mock.patch.dict(os.environ, {apollo.API_KEY_ENV: FAKE_KEY}):
            client = apollo.ApolloClient(live=True, credit_budget=1)
        self.assertIs(client.transport, apollo.urllib_transport)
        with self.assertRaisesRegex(AssertionError, 'network call attempted'):
            client.search_organizations(PARAMS)

    def test_urllib_transport_parses_http_errors(self):
        import urllib.error
        class Response:
            status = 200
            def read(self):
                return b'{"organizations": []}'
            def __enter__(self):
                return self
            def __exit__(self, *exc):
                return False
        with mock.patch('urllib.request.urlopen', return_value=Response()):
            status, payload = apollo.urllib_transport('POST', 'https://api.apollo.io/api/v1/x', {}, {'a': 1})
        self.assertEqual((status, payload), (200, {'organizations': []}))
        error = urllib.error.HTTPError('https://api.apollo.io/api/v1/x', 429, 'Too Many', {}, io.BytesIO(b'rate limited'))
        with mock.patch('urllib.request.urlopen', side_effect=error):
            status, payload = apollo.urllib_transport('POST', 'https://api.apollo.io/api/v1/x', {}, None)
        self.assertEqual((status, payload), (429, 'rate limited'))


if __name__ == '__main__':
    unittest.main()
