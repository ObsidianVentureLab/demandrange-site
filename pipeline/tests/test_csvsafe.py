import unittest

from pipeline import csvsafe


class Neutralise(unittest.TestCase):
    def test_formula_shaped_text_gets_an_apostrophe(self):
        for value in ('=HYPERLINK("http://x.example")', '+SUM(A1)', '-SUM(A1)', '@cmd', '\tx', '\rx', '=', '-', '+'):
            self.assertEqual(csvsafe.neutralise(value), "'" + value, value)

    def test_numbers_phones_and_plain_text_are_untouched(self):
        for value in ('+353 1 555 0000', '-5', '+1 (212) 555-0100', '-12.5', 'Acme Ltd', '', 'a=b', '2026-11-04', "'already quoted"):
            self.assertEqual(csvsafe.neutralise(value), value, value)

    def test_none_and_non_strings(self):
        self.assertEqual(csvsafe.neutralise(None), '')
        self.assertEqual(csvsafe.neutralise(12), '12')
        self.assertEqual(csvsafe.neutralise(-3), '-3')

    def test_idempotent(self):
        once = csvsafe.neutralise('=1+1')
        self.assertEqual(csvsafe.neutralise(once), once)


if __name__ == '__main__':
    unittest.main()
