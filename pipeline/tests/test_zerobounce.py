import os
import unittest
from unittest import mock

from pipeline import zerobounce as zb
from pipeline.tests.support import FAKE_KEY, ScriptedTransport

ADDRS = ['a@x-fixture.example', 'b@x-fixture.example']


def ok_payload(statuses, errors=()):
    return 200, {'email_batch': [{'address': a, 'status': s, 'sub_status': '', 'free_email': False, 'firstname': 'Should', 'lastname': 'Drop'}
                                 for a, s in statuses], 'errors': list(errors)}


class OfflineDefaults(unittest.TestCase):
    def test_default_client_sends_nothing_and_reads_no_key(self):
        with mock.patch.dict(os.environ, {zb.API_KEY_ENV: FAKE_KEY}):
            client = zb.ZeroBounceClient(credit_budget=10)
        self.assertIsNone(client._key)
        with self.assertRaises(zb.LiveDisabled):
            client.validate_batch(ADDRS)
        with self.assertRaises(zb.LiveDisabled):
            client.get_credits()
        self.assertEqual((client.credits_used, client.requests_made), (0, 0))

    def test_live_without_env_key_fails_before_any_request(self):
        env = {k: v for k, v in os.environ.items() if k != zb.API_KEY_ENV}
        with mock.patch.dict(os.environ, env, clear=True):
            with self.assertRaisesRegex(zb.ZeroBounceAuthError, zb.API_KEY_ENV):
                zb.ZeroBounceClient(live=True, credit_budget=5)

    def test_https_only_and_eu_default(self):
        self.assertEqual(zb.DEFAULT_BASE_URL, 'https://api-eu.zerobounce.net')
        with self.assertRaises(zb.ZeroBounceError):
            zb.ZeroBounceClient(base_url='http://api-eu.zerobounce.net')

    def test_fixture_transport_replays_and_defaults_unknown(self):
        transport = zb.FixtureTransport({'A@X-fixture.example': {'status': 'valid'}}, credits=7)
        client = zb.ZeroBounceClient(transport=transport, credit_budget=5)
        result = client.validate_batch(['a@x-fixture.example', 'zzz@x-fixture.example'])
        self.assertEqual([r['status'] for r in result.results], ['valid', 'unknown'])
        self.assertEqual(result.results[1]['sub_status'], 'not_in_fixture')
        self.assertEqual(result.charged, 1, 'unknown results are not charged')
        self.assertEqual(client.credits_used, 1)
        self.assertEqual(client.get_credits(), 7)
        self.assertNotIn('api_key', transport.calls[0]['body'])

    def test_fixture_shape_checked(self):
        with self.assertRaises(zb.ZeroBounceError):
            zb.FixtureTransport(['not', 'a', 'map'])
        with self.assertRaises(zb.ZeroBounceError):
            zb.FixtureTransport({'a@b.example': 'not-a-dict'})


class LiveClientWithFakeTransport(unittest.TestCase):
    def setUp(self):
        self.sleeps = []

    def client(self, *responses, budget=10, retries=2, base_url=zb.DEFAULT_BASE_URL):
        transport = ScriptedTransport(*responses)
        with mock.patch.dict(os.environ, {zb.API_KEY_ENV: FAKE_KEY}):
            client = zb.ZeroBounceClient(live=True, transport=transport, credit_budget=budget, max_retries=retries,
                                         sleep=lambda s: self.sleeps.append(s), base_url=base_url)
        return client, transport

    def test_batch_request_shape_key_in_body_not_url(self):
        client, transport = self.client(ok_payload([(ADDRS[0], 'valid'), (ADDRS[1], 'invalid')]))
        result = client.validate_batch(ADDRS)
        call = transport.calls[0]
        self.assertEqual(call['method'], 'POST')
        self.assertEqual(call['url'], 'https://api-eu.zerobounce.net/v2/validatebatch')
        self.assertNotIn(FAKE_KEY, call['url'])
        self.assertEqual(call['body']['api_key'], FAKE_KEY)
        self.assertEqual(call['body']['email_batch'], [{'email_address': a, 'ip_address': None} for a in ADDRS])
        self.assertEqual(call['headers']['Content-Type'], 'application/json')
        self.assertEqual([r['status'] for r in result.results], ['valid', 'invalid'])
        self.assertEqual(set(result.results[0]), set(zb.RESULT_FIELDS), 'only the allow-listed fields are kept')
        self.assertEqual(result.charged, 2)

    def test_results_are_matched_by_address_and_missing_ones_are_unknown(self):
        client, _ = self.client(ok_payload([(ADDRS[1].upper(), 'valid')]))
        result = client.validate_batch(ADDRS)
        self.assertEqual(result.results[0]['status'], 'unknown')
        self.assertEqual(result.results[0]['sub_status'], 'missing_from_response')
        self.assertEqual(result.results[1]['status'], 'valid')
        self.assertEqual(client.credits_used, 1)

    def test_unknown_results_are_not_charged_and_errors_are_returned(self):
        client, _ = self.client(ok_payload([(ADDRS[0], 'unknown'), (ADDRS[1], 'catch-all')], errors=[{'error': 'x', 'email_address': ADDRS[0]}]))
        result = client.validate_batch(ADDRS)
        self.assertEqual(result.charged, 1)
        self.assertEqual(len(result.errors), 1)

    def test_unrecognised_status_becomes_unknown(self):
        client, _ = self.client(ok_payload([(ADDRS[0], 'Weird')]))
        self.assertEqual(client.validate_batch(ADDRS[:1]).results[0]['status'], 'unknown')

    def test_budget_reserves_a_credit_per_address_before_sending(self):
        client, transport = self.client(ok_payload([(ADDRS[0], 'valid')]), budget=1)
        client.validate_batch(ADDRS[:1])
        with self.assertRaisesRegex(zb.BudgetExceeded, 'credit budget of 1'):
            client.validate_batch(ADDRS[1:])
        self.assertEqual(len(transport.calls), 1)

    def test_zero_budget_blocks_the_first_batch(self):
        client, transport = self.client(budget=0)
        with self.assertRaises(zb.BudgetExceeded):
            client.validate_batch(ADDRS)
        self.assertEqual(transport.calls, [])

    def test_batch_size_limit_and_empty_batch(self):
        client, transport = self.client(budget=1000)
        with self.assertRaises(zb.ZeroBounceError):
            client.validate_batch(['a%d@x.example' % i for i in range(zb.MAX_BATCH + 1)])
        self.assertEqual(client.validate_batch([]).results, ())
        self.assertEqual(transport.calls, [])

    def test_200_with_error_body_is_auth_or_api_error_and_redacted(self):
        client, _ = self.client((200, {'error': 'Invalid API key or your account ran out of credits ' + FAKE_KEY}))
        with self.assertRaises(zb.ZeroBounceAuthError) as caught:
            client.validate_batch(ADDRS)
        self.assertNotIn(FAKE_KEY, str(caught.exception))
        client, _ = self.client((200, {'error': 'something else'}))
        with self.assertRaises(zb.ZeroBounceError):
            client.validate_batch(ADDRS)
        self.assertEqual(client.credits_used, 0, 'a failed batch charges nothing')

    def test_http_401_403_not_retried(self):
        for status in (401, 403):
            client, _ = self.client((status, 'denied'))
            with self.assertRaises(zb.ZeroBounceAuthError):
                client.validate_batch(ADDRS)
        self.assertEqual(self.sleeps, [])

    def test_429_and_5xx_retry_then_succeed(self):
        client, _ = self.client((429, {'error': 'slow'}), (502, 'bad'), ok_payload([(ADDRS[0], 'valid')]))
        client.validate_batch(ADDRS[:1])
        self.assertEqual(self.sleeps, [2, 4])
        self.assertEqual(client.requests_made, 3)
        self.assertEqual(client.credits_used, 1)

    def test_429_beyond_retries(self):
        client, _ = self.client(*([(429, {})] * 3), retries=2)
        with self.assertRaises(zb.ZeroBounceRateLimited):
            client.validate_batch(ADDRS)

    def test_transport_errors_retried_and_redacted(self):
        client, _ = self.client(OSError('reset ' + FAKE_KEY), OSError('again ' + FAKE_KEY), OSError('third ' + FAKE_KEY), retries=2)
        with self.assertRaises(zb.ZeroBounceError) as caught:
            client.validate_batch(ADDRS)
        self.assertNotIn(FAKE_KEY, str(caught.exception))
        self.assertEqual(client.retries, 2, 'counted so the manifest can flag possible double charging')

    def test_malformed_payloads(self):
        client, _ = self.client((200, {'email_batch': 'nope'}))
        with self.assertRaises(zb.ZeroBounceError):
            client.validate_batch(ADDRS)
        client, _ = self.client((200, 'text'))
        with self.assertRaises(zb.ZeroBounceError):
            client.validate_batch(ADDRS)

    def test_get_credits_posts_form_body_and_handles_invalid_key(self):
        client, transport = self.client((200, {'Credits': '1234'}))
        self.assertEqual(client.get_credits(), 1234)
        call = transport.calls[0]
        self.assertEqual(call['url'], 'https://api-eu.zerobounce.net/v2/getcredits')
        self.assertEqual(call['headers']['Content-Type'], 'application/x-www-form-urlencoded')
        self.assertEqual(call['body'], {'api_key': FAKE_KEY})
        self.assertEqual(client.credits_used, 0)
        client, _ = self.client((200, {'Credits': '-1'}))
        with self.assertRaises(zb.ZeroBounceAuthError):
            client.get_credits()
        client, _ = self.client((200, {'Credits': 'abc'}))
        with self.assertRaises(zb.ZeroBounceError):
            client.get_credits()

    def test_unknown_hosts_are_refused_before_any_request(self):
        for bad in ('https://api.zerobounce.net.example', 'https://zerobounce.net', 'https://api-eu.zerobounce.net:8443',
                    'https://api-eu.zerobounce.net/v2', 'https://api-eu.zerobounce.net?x=1'):
            with self.assertRaisesRegex(zb.ZeroBounceError, 'host one of'):
                self.client((200, {'Credits': '1'}), base_url=bad)
        self.assertEqual(self.sleeps, [])

    def test_all_documented_hosts_are_accepted(self):
        for good in zb.ALLOWED_HOSTS:
            client, transport = self.client((200, {'Credits': '1'}), base_url='https://' + good)
            self.assertEqual(client.base_url, 'https://' + good)

    def test_us_base_url_is_honoured(self):
        client, transport = self.client((200, {'Credits': '1'}), base_url=zb.US_BASE_URL + '/')
        client.get_credits()
        self.assertEqual(transport.calls[0]['url'], 'https://api-us.zerobounce.net/v2/getcredits')


class UrllibTransport(unittest.TestCase):
    def test_live_default_transport_is_blocked_by_the_test_guard(self):
        with mock.patch.dict(os.environ, {zb.API_KEY_ENV: FAKE_KEY}):
            client = zb.ZeroBounceClient(live=True, credit_budget=1)
        self.assertIs(client.transport, zb.urllib_transport)
        with self.assertRaisesRegex(AssertionError, 'network call attempted'):
            client.validate_batch(ADDRS[:1])

    def test_urllib_transport_encodes_form_and_json(self):
        seen = {}

        class Response:
            status = 200
            def read(self):
                return b'{"Credits": "5"}'
            def __enter__(self):
                return self
            def __exit__(self, *exc):
                return False

        def fake_urlopen(request, timeout=None):
            seen['data'] = request.data
            seen['ct'] = request.get_header('Content-type')
            return Response()
        with mock.patch('urllib.request.urlopen', fake_urlopen):
            zb.urllib_transport('POST', 'https://api-eu.zerobounce.net/v2/getcredits',
                                {'Content-Type': 'application/x-www-form-urlencoded'}, {'api_key': 'k'})
            self.assertEqual(seen['data'], b'api_key=k')
            zb.urllib_transport('POST', 'https://api-eu.zerobounce.net/v2/validatebatch',
                                {'Content-Type': 'application/json'}, {'a': 1})
            self.assertEqual(seen['data'], b'{"a": 1}')


if __name__ == '__main__':
    unittest.main()
