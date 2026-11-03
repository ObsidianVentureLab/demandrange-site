import unittest

from pipeline import icp
from pipeline.tests.support import brief


class BriefLoading(unittest.TestCase):
    def test_example_brief_validates_and_maps_to_apollo_params(self):
        spec = icp.from_dict(brief())
        params = spec.to_apollo_params()
        self.assertEqual(params['organization_locations[]'], ['Ireland', 'United Kingdom'])
        self.assertEqual(params['organization_not_locations[]'], ['Northern Ireland'])
        self.assertEqual(params['organization_sic_codes[]'], ['3561'])
        self.assertEqual(params['organization_naics_codes[]'], ['333914'])
        self.assertEqual(params['organization_industries[]'], ['industrial automation', 'machinery'])
        self.assertEqual(params['q_organization_keyword_tags[]'], ['process plant', 'food processing'])
        self.assertEqual(params['q_not_organization_keyword_tags[]'], ['distributor'])
        self.assertEqual(params['organization_num_employees_ranges[]'], ['50,200', '201,1000'])
        self.assertEqual(params['not_organization_websites_list[]'], ['excluded-fixture.example', 'another-excluded.example'])
        self.assertNotIn('page', params)
        for key in params:
            self.assertTrue(key.endswith('[]'), key)

    def test_empty_filters_are_omitted(self):
        spec = icp.from_dict(brief(excluded_locations=[], excluded_keywords=None, employee_ranges=[]))
        params = spec.to_apollo_params()
        self.assertNotIn('organization_not_locations[]', params)
        self.assertNotIn('q_not_organization_keyword_tags[]', params)
        self.assertNotIn('organization_num_employees_ranges[]', params)

    def test_normalisation(self):
        spec = icp.from_dict(brief(industries=['  Machinery ', 'machinery'], employee_ranges=['50, 200'],
                                   excluded_domains=['HTTPS://WWW.Foo.Example/x?y', 'foo.example', '@bar.example']))
        self.assertEqual(spec.industries, ('machinery',))
        self.assertEqual(spec.employee_ranges, ('50,200',))
        self.assertEqual(spec.excluded_domains, ('foo.example', 'bar.example'))

    def test_load_from_file_errors_are_specific(self):
        with self.assertRaisesRegex(icp.ICPError, 'file not found'):
            icp.load_icp('/nonexistent/brief.json')


class BriefRejections(unittest.TestCase):
    def assert_rejects(self, pattern, **overrides):
        with self.assertRaisesRegex(icp.ICPError, pattern):
            icp.from_dict(brief(**overrides))

    def test_identity_fields(self):
        self.assert_rejects('brief_id', brief_id='')
        self.assert_rejects('brief_id', brief_id='has space')
        self.assert_rejects('brief_version', brief_version='')
        self.assert_rejects('supplier_range', supplier_range='  ')

    def test_counting_unit_must_be_company(self):
        self.assert_rejects('counting_unit', counting_unit='facility')

    def test_requested_volume_bounds_and_type(self):
        self.assert_rejects('requested_volume', requested_volume=0)
        self.assert_rejects('requested_volume', requested_volume=icp.MAX_REQUESTED_VOLUME + 1)
        self.assert_rejects('requested_volume', requested_volume='100')
        self.assert_rejects('requested_volume', requested_volume=True)

    def test_at_least_one_positive_filter(self):
        self.assert_rejects('positive filter', territory_locations=[], sic_codes=[], naics_codes=[], industries=[], keywords=[])

    def test_codes_ranges_domains(self):
        self.assert_rejects('employee_ranges', employee_ranges=['50-200'])
        self.assert_rejects('min greater than max', employee_ranges=['500,200'])
        self.assert_rejects('sic_codes', sic_codes=['35A1'])
        self.assert_rejects('naics_codes', naics_codes=['3339141234'])
        self.assert_rejects('excluded_domains', excluded_domains=['not a domain'])
        self.assert_rejects('excluded_domains', excluded_domains=['localhost'])

    def test_apollo_request_limits(self):
        self.assert_rejects('at most 1000', excluded_domains=[f'd{i}.example' for i in range(1001)])
        self.assert_rejects('at most 150', excluded_keywords=[f'kw{i}' for i in range(151)])

    def test_unknown_fields_and_wrong_types(self):
        self.assert_rejects('unknown fields primary_customer_role', primary_customer_role='operator')
        self.assert_rejects('must be a list of strings', keywords=[1, 2])
        with self.assertRaisesRegex(icp.ICPError, 'top-level'):
            icp.from_dict(['not', 'an', 'object'])


if __name__ == '__main__':
    unittest.main()
