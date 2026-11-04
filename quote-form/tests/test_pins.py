"""Pin-consistency check for production-manifest.json (no endpoint, no network).

production_contract.load_contract() verifies the protected-source pins only in
production mode, which CI never runs (it has no reviewed endpoint). This test
recomputes the same digests from the working tree so a protected file edited
without a re-pin fails CI instead of failing the next production build.
It does not approve pins; re-pins still need the independent review step.
"""
import hashlib
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

PROTECTED_TEMPLATE = 'quote-form/request-a-quote.template.html'


def load_manifest():
    return json.loads((ROOT / 'production-manifest.json').read_text(encoding='utf-8'))


def digest_file(relative):
    return hashlib.sha256((ROOT / relative).read_bytes()).hexdigest()


class ProtectedSourcePins(unittest.TestCase):
    def test_every_protected_source_matches_its_pin(self):
        pins = load_manifest()['protected_sources']
        self.assertTrue(pins, 'manifest must declare protected sources')
        drift = {name: (expected, digest_file(name)) for name, expected in pins.items()
                 if digest_file(name) != expected}
        self.assertEqual(drift, {}, 'protected source edited without a manifest re-pin: ' + json.dumps(drift, indent=2))

    def test_quote_form_contract_files_are_protected(self):
        pins = load_manifest()['protected_sources']
        for required in ('quote-form/form_schema.json', 'quote-form/client.js', PROTECTED_TEMPLATE):
            self.assertIn(required, pins)

    def test_pins_are_lowercase_sha256_hex(self):
        for name, expected in load_manifest()['protected_sources'].items():
            self.assertRegex(expected, r'^[0-9a-f]{64}$', name)


class ComposedTemplatePin(unittest.TestCase):
    def test_composed_quote_template_matches_proposed_pin(self):
        from foundation_stage import quote_template
        composed = quote_template((ROOT / PROTECTED_TEMPLATE).read_text())
        actual = hashlib.sha256(composed.encode()).hexdigest()
        self.assertEqual(actual, load_manifest()['proposed_effective_quote_template_sha256'],
                         'composed quote template drifted from proposed_effective_quote_template_sha256')


if __name__ == '__main__':
    unittest.main()
