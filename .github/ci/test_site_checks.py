"""Unit tests for site_checks.dataset_problems (JSON-LD Dataset field rule, check 7).

    python3 -B .github/ci/test_site_checks.py

Stdlib only. Also asserts every built page in this repository passes the rule.
"""
import json
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(HERE))
import site_checks  # noqa: E402

DESC = 'A' * 60
GOOD = {'@type': 'Dataset', 'name': 'x', 'description': DESC,
        'license': 'https://creativecommons.org/licenses/by/4.0/', 'creator': {'@id': 'https://demandrange.com/#organization'}}


def page(data):
    return f'<!doctype html><html><head><script type="application/ld+json">{json.dumps(data)}</script></head></html>'


class DatasetRule(unittest.TestCase):
    def test_complete_dataset_passes(self):
        self.assertEqual(site_checks.dataset_problems(page({'@context': 'https://schema.org', '@graph': [GOOD]})), [])

    def test_creative_work_sources_pass(self):
        d = dict(GOOD, isBasedOn=[{'@type': 'CreativeWork', 'name': 'Eurostat', 'url': 'https://ec.europa.eu/x'}])
        self.assertEqual(site_checks.dataset_problems(page(d)), [])

    def test_nested_dataset_without_fields_fails(self):
        # the shape Google Search Console flagged: isBasedOn items typed Dataset with name/url/identifier only
        d = dict(GOOD, isBasedOn=[{'@type': 'Dataset', 'name': 'Eurostat', 'url': 'https://ec.europa.eu/x'}])
        problems = site_checks.dataset_problems(page({'@graph': [d]}))
        self.assertEqual(len(problems), 3, problems)
        self.assertTrue(any('description' in p for p in problems))
        self.assertTrue(any('missing license' in p for p in problems))
        self.assertTrue(any('missing creator' in p for p in problems))

    def test_type_list_and_description_bounds(self):
        for desc, ok in (('A' * 49, False), ('A' * 50, True), ('A' * 5000, True), ('A' * 5001, False), (None, False)):
            d = dict(GOOD, **{'@type': ['Dataset', 'CreativeWork']})
            d['description'] = desc
            self.assertEqual(site_checks.dataset_problems(page(d)) == [], ok, desc and len(desc))

    def test_empty_license_or_creator_fails(self):
        self.assertTrue(site_checks.dataset_problems(page(dict(GOOD, license=''))))
        self.assertTrue(site_checks.dataset_problems(page(dict(GOOD, creator={}))))

    def test_non_string_type_does_not_crash(self):
        for bad in ({'@id': 'x'}, [{'@id': 'x'}, 'Dataset'], 7, None):
            with self.subTest(type=bad):
                problems = site_checks.dataset_problems(page({'@type': bad, 'name': 'x'}))
                # a dict/number @type is not a Dataset; 'Dataset' alongside it in a list still is
                expect_dataset = isinstance(bad, list)
                self.assertEqual(bool(problems), expect_dataset, problems)
        self.assertEqual(site_checks._types({'@type': [{'a': 1}, 'Dataset', 3]}), {'Dataset'})

    def test_invalid_json_fails(self):
        html = '<script type="application/ld+json">{"@type": "Dataset",</script>'
        self.assertTrue(site_checks.dataset_problems(html))

    def test_built_pages_pass(self):
        pages = sorted(REPO.glob('*.html'))
        self.assertTrue(pages)
        bad = {p.name: site_checks.dataset_problems(p.read_text(encoding='utf-8')) for p in pages}
        self.assertEqual({k: v for k, v in bad.items() if v}, {})
        text = (REPO / 'eu-industrial-enterprises-by-country.html').read_text(encoding='utf-8')
        self.assertIn('"@type":"Dataset"', text)  # the rule is actually exercised on a real Dataset page


if __name__ == '__main__':
    unittest.main(verbosity=2)
