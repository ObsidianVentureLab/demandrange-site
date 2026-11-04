import csv
import datetime as dt
import hashlib
import json
import re
import tempfile
import unittest
import zipfile
from pathlib import Path

from pipeline import export, verify, zerobounce as zb
from pipeline.tests.support import EXAMPLES

EMAILS = EXAMPLES / 'emails-fixture.csv'
RESULTS = EXAMPLES / 'zerobounce-results-fixture.json'
NOW = dt.datetime(2026, 11, 3, 12, 0, tzinfo=dt.timezone.utc)
VERSIONS = dict(brief_ref='DEMO-BRIEF-A-v1', dictionary_version='DEMO-DICT-v1', export_version='DEMO-EXPORT-v1')


def verified_csv(tmp):
    rows, columns, column = verify.read_rows(EMAILS)
    client = zb.ZeroBounceClient(transport=zb.FixtureTransport.from_file(RESULTS), credit_budget=100)
    result = verify.verify_rows(rows, columns, column, client, data_mode=verify.FIXTURE_MODE, now=NOW)
    csv_path, _ = verify.write_outputs(result, EMAILS, tmp, data_mode=verify.FIXTURE_MODE, client=client, now=NOW)
    return csv_path


def plain_csv(tmp, text, name='list.csv'):
    path = Path(tmp) / name
    path.write_text(text, encoding='utf-8')
    return path


class Building(unittest.TestCase):
    def test_keep_only_by_default_and_stamps_every_row(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = export.build([verified_csv(tmp)], client='Demo Client Ltd', export_id='E1', now=NOW, **VERSIONS)
        self.assertEqual(result.client, 'demo-client-ltd')
        self.assertEqual(result.client_name, 'Demo Client Ltd')
        self.assertEqual(len(result.rows), 3)
        self.assertEqual(result.rows_excluded_by_decision, 6)
        self.assertNotIn('fiction_notice', result.columns, 'fixture notice dropped by default')
        self.assertEqual(result.columns[-6:], list(export.STAMP_COLUMNS))
        self.assertTrue(all(r['brief_ref'] == 'DEMO-BRIEF-A-v1' and r['export_id'] == 'E1' and r['exported_at'] == '2026-11-03T12:00:00Z' for r in result.rows))
        self.assertEqual(result.inputs[0]['source_manifest'], 'emails-fixture-verified.manifest.json')

    def test_include_review_and_dedupe(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = export.build([verified_csv(tmp)], client='x', decisions=('keep', 'review'), dedupe_on='work_email', **VERSIONS)
        self.assertEqual(len(result.rows), 3)
        self.assertEqual(result.duplicates_dropped, 1)
        self.assertEqual(sorted(r['verification_decision'] for r in result.rows), ['keep', 'keep', 'review'])

    def test_dedupe_prefers_the_best_decision_over_the_first_row_seen(self):
        text = ('work_email,full_name,verification_decision\r\n'
                'A@x.example,Review First,review\r\n'
                'a@x.example ,Keep Later,keep\r\n'
                'b@x.example,Drop Row,drop\r\n'
                'b@x.example,Review Row,review\r\n'
                ',No Key One,keep\r\n'
                ',No Key Two,keep\r\n')
        with tempfile.TemporaryDirectory() as tmp:
            result = export.build([plain_csv(tmp, text)], client='x', decisions=('keep', 'review', 'drop'), dedupe_on='work_email', **VERSIONS)
        names = [r['full_name'] for r in result.rows]
        self.assertEqual(names, ['Keep Later', 'Review Row', 'No Key One', 'No Key Two'], 'best decision wins; blank keys are never merged')
        self.assertEqual(result.duplicates_dropped, 2)

    def test_dedupe_ties_keep_the_first_row(self):
        text = 'work_email,full_name,verification_decision\r\na@x.example,First,keep\r\na@x.example,Second,keep\r\n'
        with tempfile.TemporaryDirectory() as tmp:
            result = export.build([plain_csv(tmp, text)], client='x', dedupe_on='work_email', **VERSIONS)
        self.assertEqual([r['full_name'] for r in result.rows], ['First'])

    def test_selection_is_recorded_even_when_the_decision_column_is_dropped(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = export.build([verified_csv(tmp)], client='x', drop_columns=('verification_decision',), **VERSIONS)
            self.assertNotIn('verification_decision', result.columns)
            out_dir, manifest = export.write_delivery(result, Path(tmp) / 'deliveries')
            readme = (out_dir / 'README.txt').read_text(encoding='utf-8')
        self.assertEqual(manifest['selection']['decisions_included'], ['keep'])
        self.assertGreater(manifest['selection']['rows_excluded_by_decision'], 0)
        self.assertIn('Verification decisions included: keep', readme)

    def test_no_selection_record_when_the_input_has_no_decision_column(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = export.build([plain_csv(tmp, 'work_email,full_name\r\na@x.example,A\r\n')], client='x', **VERSIONS)
            out_dir, manifest = export.write_delivery(result, Path(tmp) / 'deliveries')
            readme = (out_dir / 'README.txt').read_text(encoding='utf-8')
        self.assertIsNone(manifest['selection']['decisions_included'])
        self.assertNotIn('Verification decisions included', readme)

    def test_keep_fiction_notice_and_drop_columns(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = export.build([verified_csv(tmp)], client='x', keep_fiction_notice=True, drop_columns=('zb_domain_age_days',), **VERSIONS)
        self.assertIn('fiction_notice', result.columns)
        self.assertNotIn('zb_domain_age_days', result.columns)
        self.assertEqual(result.columns_dropped, ('zb_domain_age_days',))

    def test_text_is_preserved_and_formulas_neutralised_in_csv_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = plain_csv(tmp, 'record_id,note,amount\n0007,"café, ""équipement""",=SUM(A1)\n0008,+353 1 555,-5\n'
                                  '0009,@handle,2001-02-03\n0010,-SUM(A1),+1 (555) 010-0100\n0011,\t=cmd,-1.5\n')
            result = export.build([path], client='x', export_id='E1', **VERSIONS)
            values = [(r['record_id'], r['note'], r['amount']) for r in result.rows]
            self.assertEqual(values, [('0007', 'café, "équipement"', '=SUM(A1)'), ('0008', '+353 1 555', '-5'),
                                      ('0009', '@handle', '2001-02-03'), ('0010', '-SUM(A1)', '+1 (555) 010-0100'),
                                      ('0011', '\t=cmd', '-1.5')], 'built rows keep the original text')
            folder, _ = export.write_delivery(result, Path(tmp) / 'out', xlsx=True)
            with open(folder / 'x-E1.csv', encoding='utf-8-sig', newline='') as handle:
                rows = {r['record_id']: r for r in csv.DictReader(handle)}
            self.assertEqual((rows['0007']['amount'], rows['0008']['note'], rows['0008']['amount']), ("'=SUM(A1)", '+353 1 555', '-5'))
            self.assertEqual((rows['0009']['note'], rows['0010']['note'], rows['0010']['amount']), ("'@handle", "'-SUM(A1)", '+1 (555) 010-0100'))
            self.assertEqual((rows['0011']['note'], rows['0011']['amount']), ("'\t=cmd", '-1.5'))
            with zipfile.ZipFile(folder / 'x-E1.xlsx') as archive:
                sheet = archive.read('xl/worksheets/sheet1.xml').decode('utf-8')
            self.assertIn('<t>=SUM(A1)</t>', sheet, 'XLSX inline strings carry no apostrophe')
            self.assertNotIn("'=SUM", sheet)
            self.assertNotIn('<f>', sheet, 'no formula cells in the workbook')

    def test_header_names_get_the_formula_guard_too(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = plain_csv(tmp, 'record_id,=cmd,@who,-5\n0007,a,b,c\n')
            result = export.build([path], client='x', export_id='E1', **VERSIONS)
            folder, _ = export.write_delivery(result, Path(tmp) / 'out', xlsx=True)
            with open(folder / 'x-E1.csv', encoding='utf-8-sig', newline='') as handle:
                header = next(csv.reader(handle))
            self.assertEqual(header[:4], ['record_id', "'=cmd", "'@who", '-5'])
            with zipfile.ZipFile(folder / 'x-E1.xlsx') as archive:
                self.assertIn('<t>=cmd</t>', archive.read('xl/worksheets/sheet1.xml').decode('utf-8'), 'XLSX header is an inline string, no apostrophe')

    def test_newlines_inside_quoted_cells_survive_build_and_delivery(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = plain_csv(tmp, 'record_id,note\r\n0007,"line one\nline two"\r\n0008,"tail\r\n"\r\n')
            result = export.build([path], client='x', export_id='E1', **VERSIONS)
            self.assertEqual([r['note'] for r in result.rows], ['line one\nline two', 'tail\r\n'])
            folder, _ = export.write_delivery(result, Path(tmp) / 'out', xlsx=True)
            with open(folder / 'x-E1.csv', encoding='utf-8-sig', newline='') as handle:
                rows = list(csv.DictReader(handle))
            self.assertEqual([r['note'] for r in rows], ['line one\nline two', 'tail\r\n'], 'delivered CSV round-trips the cell')
            with zipfile.ZipFile(folder / 'x-E1.xlsx') as archive:
                sheet = archive.read('xl/worksheets/sheet1.xml').decode('utf-8')
            self.assertIn('<t>line one\nline two</t>', sheet)

    def test_empty_decisions_is_an_error_not_an_empty_delivery(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(export.ExportError, 'include-decisions'):
                export.build([verified_csv(tmp)], client='x', decisions=('', ' '), **VERSIONS)

    def test_errors(self):
        with tempfile.TemporaryDirectory() as tmp:
            good = plain_csv(tmp, 'a,b\n1,2\n')
            other = plain_csv(tmp, 'a,c\n1,2\n', 'other.csv')
            with self.assertRaisesRegex(export.ExportError, 'header differs'):
                export.build([good, other], client='x', **VERSIONS)
            with self.assertRaisesRegex(export.ExportError, 'not found'):
                export.build([Path(tmp) / 'nope.csv'], client='x', **VERSIONS)
            with self.assertRaisesRegex(export.ExportError, 'client'):
                export.build([good], client='   ', **VERSIONS)
            with self.assertRaisesRegex(export.ExportError, 'brief_ref: required'):
                export.build([good], client='x', brief_ref='', dictionary_version='D', export_version='E')
            with self.assertRaisesRegex(export.ExportError, 'export_version'):
                export.build([good], client='x', brief_ref='B', dictionary_version='D', export_version='has space')
            with self.assertRaisesRegex(export.ExportError, 'no verification_decision'):
                export.build([good], client='x', decisions=('keep', 'review'), **VERSIONS)
            with self.assertRaisesRegex(export.ExportError, '--drop-columns'):
                export.build([good], client='x', drop_columns=('zzz',), **VERSIONS)
            with self.assertRaisesRegex(export.ExportError, '--dedupe-on'):
                export.build([good], client='x', dedupe_on='zzz', **VERSIONS)
            stamped = plain_csv(tmp, 'a,export_id\n1,2\n', 'stamped.csv')
            with self.assertRaisesRegex(export.ExportError, 'already contains export columns'):
                export.build([stamped], client='x', **VERSIONS)
            with self.assertRaisesRegex(export.ExportError, 'no header'):
                export.build([plain_csv(tmp, '', 'empty.csv')], client='x', **VERSIONS)
            with self.assertRaisesRegex(export.ExportError, 'every column was dropped'):
                export.build([good], client='x', drop_columns=('a', 'b'), **VERSIONS)
            plain = plain_csv(tmp, 'a,b\n1,2\n', 'p.csv')
            self.assertEqual(export.build([plain, good], client='x', **VERSIONS).rows_read, 2, 'several files with one schema')


class Writing(unittest.TestCase):
    def test_delivery_folder_csv_xlsx_readme_manifest(self):
        with tempfile.TemporaryDirectory() as tmp:
            src = plain_csv(tmp, 'record_id,company,note\n0007,Fictional Pumps Alpha Ltd,café\n0008,Beta,=1+1\n')
            result = export.build([src], client='Demo Client', export_id='E1', now=NOW, **VERSIONS)
            folder, manifest = export.write_delivery(result, Path(tmp) / 'deliveries', xlsx=True)
            self.assertEqual(folder, Path(tmp) / 'deliveries' / 'demo-client' / 'E1')
            names = sorted(p.name for p in folder.iterdir())
            self.assertEqual(names, ['MANIFEST.json', 'README.txt', 'demo-client-E1.csv', 'demo-client-E1.xlsx'])
            raw = (folder / 'demo-client-E1.csv').read_bytes()
            self.assertTrue(raw.startswith(b'\xef\xbb\xbf'), 'BOM for spreadsheet Unicode handling')
            with (folder / 'demo-client-E1.csv').open(encoding='utf-8-sig', newline='') as handle:
                rows = list(csv.DictReader(handle))
            self.assertEqual(rows[0]['record_id'], '0007')
            self.assertEqual(rows[0]['note'], 'café')
            self.assertEqual(rows[1]['note'], "'=1+1")
            self.assertEqual(list(rows[0]), result.columns)
            with zipfile.ZipFile(folder / 'demo-client-E1.xlsx') as archive:
                self.assertIsNone(archive.testzip())
                sheet = archive.read('xl/worksheets/sheet1.xml').decode('utf-8')
                self.assertEqual(sheet.count('t="inlineStr"'), len(result.columns) * 3, 'header + 2 rows, every cell a text cell')
                texts = re.findall(r'<t[^>]*>([^<]*)</t>', sheet)
                self.assertIn('0007', texts)
                self.assertIn('caf&#233;', texts + [t.encode('ascii', 'xmlcharrefreplace').decode() for t in texts])
                self.assertIn('[Content_Types].xml', archive.namelist())
            readme = (folder / 'README.txt').read_text(encoding='utf-8')
            self.assertIn('Demo Client', readme)
            self.assertIn('DEMO-BRIEF-A-v1', readme)
            self.assertIn('not an automated mailing', readme)
            self.assertEqual(manifest['rows_delivered'], 2)
            self.assertEqual(manifest['client_ref'], 'demo-client')
            for name, info in manifest['files'].items():
                self.assertEqual(info['sha256'], hashlib.sha256((folder / name).read_bytes()).hexdigest())
            self.assertEqual(json.loads((folder / 'MANIFEST.json').read_text(encoding='utf-8'))['delivery'], 'manual by Demand Range; no automated sending')
            with self.assertRaisesRegex(export.ExportError, 'already exists'):
                export.write_delivery(result, Path(tmp) / 'deliveries', xlsx=False)

    def test_file_in_the_way_of_the_delivery_folder_is_an_export_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            src = plain_csv(tmp, 'a,b\n1,2\n')
            result = export.build([src], client='x', export_id='E1', **VERSIONS)
            root = Path(tmp) / 'deliveries'
            (root / 'x').mkdir(parents=True)
            (root / 'x' / 'E1').write_text('not a folder', encoding='utf-8')
            with self.assertRaisesRegex(export.ExportError, 'not a folder'):
                export.write_delivery(result, root)
            (root / 'x' / 'E1').unlink()
            (root / 'x').rmdir()
            (root / 'x').write_text('file where the client folder should be', encoding='utf-8')
            with self.assertRaisesRegex(export.ExportError, 'file is in the way'):
                export.write_delivery(result, root)

    def test_xlsx_is_reproducible(self):
        with tempfile.TemporaryDirectory() as tmp:
            a, b = Path(tmp) / 'a.xlsx', Path(tmp) / 'b.xlsx'
            export.write_xlsx(a, ['x', 'y'], [{'x': '1', 'y': ' two  spaces '}])
            export.write_xlsx(b, ['x', 'y'], [{'x': '1', 'y': ' two  spaces '}])
            self.assertEqual(a.read_bytes(), b.read_bytes())
            with zipfile.ZipFile(a) as archive:
                self.assertIn('xml:space="preserve"', archive.read('xl/worksheets/sheet1.xml').decode('utf-8'))

    def test_xlsx_drops_xml_invalid_code_points_and_parses(self):
        """QA B61-3: U+FFFF (and friends) made sheet1.xml malformed, so Excel refused the workbook."""
        from xml.etree import ElementTree
        bad = 'a\uffffb\ufffec\ud800d\x01e\x0bf'
        kept = 'tab\there\nline\u2028sep \U0001F600 \ufffd'
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'x.xlsx'
            export.write_xlsx(path, ['h\uffff', 'k'], [{'h\uffff': bad, 'k': kept}], sheet_name='S\ufffe')
            with zipfile.ZipFile(path) as archive:
                sheet = ElementTree.fromstring(archive.read('xl/worksheets/sheet1.xml'))
                ElementTree.fromstring(archive.read('xl/workbook.xml'))
        ns = {'m': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
        texts = [t.text for t in sheet.iterfind('.//m:t', ns)]
        self.assertEqual(texts, ['h', 'k', 'abcdef', kept])

    def test_column_names(self):
        self.assertEqual([export._col_name(i) for i in (0, 25, 26, 27, 701, 702)], ['A', 'Z', 'AA', 'AB', 'ZZ', 'AAA'])


if __name__ == '__main__':
    unittest.main()
