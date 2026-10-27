"""Local URL-shape regressions; no network calls or deployment acceptance."""
from pathlib import Path
import importlib.util
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
spec = importlib.util.spec_from_file_location('quote_site_builder', ROOT / 'build_site.py')
assert spec is not None and spec.loader is not None
builder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)

ID = 'AKfycbx_V5pOH_ojUs9l2C4fZuRgGSqEAjzoe3b2_1Kwhux0K7-XiKYPaXZNIiQyh7wSv9QfkQ'
DOMAIN_URL = 'https://script.google.com/a/macros/demandrange.com/s/' + ID + '/exec'
# A distinct format fixture only: this is NOT a repaired/replacement deployment URL.
GENERIC_FIXTURE = 'https://script.google.com/macros/s/AKfycbxLocalShapeFixture000000000000000/exec'

class EndpointShapeTests(unittest.TestCase):
    def test_exact_supplied_domain_url_is_preserved(self):
        self.assertEqual(builder.validate_quote_endpoint(DOMAIN_URL), DOMAIN_URL)

    def test_generic_format_fixture_is_preserved(self):
        self.assertEqual(builder.validate_quote_endpoint(GENERIC_FIXTURE), GENERIC_FIXTURE)

    def test_absence_is_allowed_by_shape_helper_only(self):
        self.assertIsNone(builder.validate_quote_endpoint(None))
        self.assertIsNone(builder.validate_quote_endpoint(''))

    def test_rejects_unreviewed_shapes(self):
        bad = [
            DOMAIN_URL.replace('https://', 'http://'),
            DOMAIN_URL.replace('script.google.com', 'example.invalid'),
            DOMAIN_URL.replace('script.google.com', 'user@script.google.com'),
            DOMAIN_URL.replace('script.google.com', 'script.google.com:443'),
            DOMAIN_URL.replace('demandrange.com/s/', 'other.example/s/'),
            DOMAIN_URL.replace('/exec', '/dev'),
            DOMAIN_URL + '/', DOMAIN_URL + '?', DOMAIN_URL + '?mode=test',
            DOMAIN_URL + '#', DOMAIN_URL + '#fragment',
            ' ' + DOMAIN_URL, DOMAIN_URL + '\n',
            DOMAIN_URL.replace('/s/', '/s/extra/'),
            'https://script.google.com/macros/s/TEST_DEPLOYMENT_ID/exec',
        ]
        for value in bad:
            with self.subTest(value=value):
                with self.assertRaises((AssertionError, ValueError)):
                    builder.validate_quote_endpoint(value)

if __name__ == '__main__':
    unittest.main()
