import datetime as dt
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from pipeline import clientdb, export
from pipeline.tests.support import EXAMPLES

SHEET = EXAMPLES / 'sheet-export-fixture.csv'
NOW = dt.datetime(2026, 11, 3, 12, 0, tzinfo=dt.timezone.utc)
VERSIONS = dict(brief_ref='DEMO-BRIEF-A-v1', dictionary_version='DEMO-DICT-v1', export_version='DEMO-EXPORT-v1')


def fresh_db():
    db = clientdb.ClientDB(':memory:')
    db.init(now=NOW)
    return db


class Schema(unittest.TestCase):
    def test_init_is_idempotent_and_versioned(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'c.sqlite'
            with clientdb.ClientDB(path, create=True) as db:
                self.assertEqual(db.init(now=NOW), 1)
                self.assertEqual(db.init(), 1)
                self.assertEqual(db.summary()['counts'], {'clients': 0, 'requests': 0, 'briefs': 0, 'deliveries': 0, 'imports': 0})
            with clientdb.ClientDB(path) as db:
                self.assertEqual(db.schema_version(), 1)
            with self.assertRaisesRegex(clientdb.ClientDBError, 'not initialised'):
                clientdb.ClientDB(Path(tmp) / 'empty.sqlite')
            self.assertFalse((Path(tmp) / 'empty.sqlite').exists(), 'opening without init must not create a file')
            with clientdb.ClientDB(Path(tmp) / 'empty.sqlite', create=True) as db:
                with self.assertRaisesRegex(clientdb.ClientDBError, 'not initialised'):
                    db.schema_version()

    def test_a_missing_database_directory_is_never_created(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'typo' / 'c.sqlite'
            for create in (True, False):
                with self.assertRaisesRegex(clientdb.ClientDBError, 'directory does not exist'):
                    clientdb.ClientDB(path, create=create)
            self.assertFalse(path.parent.exists())

    def test_utc_today_follows_the_utc_clock(self):
        late = dt.datetime(2026, 11, 3, 23, 30, tzinfo=dt.timezone(dt.timedelta(hours=-5)))   # 04:30Z on 4 Nov
        self.assertEqual(clientdb.utc_today(late), dt.date(2026, 11, 4))
        self.assertEqual(clientdb.utc_today(), dt.datetime.now(dt.timezone.utc).date())

    def test_requests_table_mirrors_the_sheet_columns(self):
        db = fresh_db()
        columns = [r['name'] for r in db.connection.execute('PRAGMA table_info(requests)')]
        for column in clientdb.SHEET_COLUMNS:
            self.assertIn(column, columns)
        self.assertEqual(len(clientdb.SHEET_COLUMNS), 31)


class SheetImport(unittest.TestCase):
    def test_import_links_clients_and_is_idempotent(self):
        db = fresh_db()
        first = db.import_sheet_export(SHEET, now=NOW)
        self.assertEqual((first['rows_read'], first['rows_new'], first['rows_updated']), (3, 3, 0))
        again = db.import_sheet_export(SHEET, now=NOW)
        self.assertEqual(again['skipped'], 'already imported')
        self.assertEqual(db.summary()['counts']['clients'], 2, 'two requests from one fictional company share a client')
        alpha = db.client('fictional-pumps-alpha-ltd')
        self.assertEqual(alpha['client']['website_domain'], 'alpha-fixture.example')
        self.assertEqual([r['submission_id'] for r in alpha['requests']], ['FX-0001', 'FX-0003'])
        beta = db.client('fictional-seals-beta-plc')
        self.assertEqual(beta['client']['website_domain'], 'beta-fixture.example', 'domain from the work email when no website')
        row = db.connection.execute("SELECT * FROM requests WHERE submission_id = 'FX-0002'").fetchone()
        self.assertEqual(row['additional_context'], 'WHOLLY FICTIONAL: café, "équipement" — Unicode probe.')
        self.assertEqual(row['submission_token_hash'], '0' * 63 + '2', 'text kept exactly')
        self.assertEqual(row['import_sha256'], first['sha256'])

    def test_changed_rows_are_updated_by_submission_id(self):
        db = fresh_db()
        db.import_sheet_export(SHEET, now=NOW)
        with tempfile.TemporaryDirectory() as tmp:
            edited = Path(tmp) / 'export2.csv'
            edited.write_text(SHEET.read_text(encoding='utf-8').replace('FX-0001,2026-10-29T09:15:00.000Z', 'FX-0001,2026-10-29T09:15:00.000Z').replace(',new,,,,2028-10-29,', ',quote_sent,sean,2026-11-01T10:00:00.000Z,,2028-10-29,'), encoding='utf-8')
            result = db.import_sheet_export(edited, now=NOW)
        self.assertEqual((result['rows_new'], result['rows_updated']), (0, 1))
        self.assertEqual(db.connection.execute("SELECT intake_status FROM requests WHERE submission_id = 'FX-0001'").fetchone()[0], 'quote_sent')

    def test_blanked_company_name_keeps_the_client_link(self):
        db = fresh_db()
        db.import_sheet_export(SHEET, now=NOW)
        with tempfile.TemporaryDirectory() as tmp:
            edited = Path(tmp) / 'export3.csv'
            edited.write_text(SHEET.read_text(encoding='utf-8').replace('Fictional Seals Beta plc', ''), encoding='utf-8')
            result = db.import_sheet_export(edited, now=NOW)
        self.assertEqual(result['rows_updated'], 1)
        row = db.connection.execute("SELECT client_ref, company_name FROM requests WHERE submission_id = 'FX-0002'").fetchone()
        self.assertEqual((row['client_ref'], row['company_name']), ('fictional-seals-beta-plc', ''))

    def test_newlines_inside_quoted_cells_survive_the_import(self):
        db = fresh_db()
        text = SHEET.read_text(encoding='utf-8')
        header, first = text.split('\n')[0], text.split('\n')[1]
        edited = first.replace('WHOLLY FICTIONAL: demo request for the client database fixture.',
                               '"WHOLLY FICTIONAL: line one\nline two, with a comma"')
        self.assertNotEqual(edited, first)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'export.csv'
            path.write_text(header + '\n' + edited + '\n', encoding='utf-8')
            result = db.import_sheet_export(path, now=NOW)
        self.assertEqual(result['rows_read'], 1)
        row = db.connection.execute("SELECT additional_context FROM requests WHERE submission_id = 'FX-0001'").fetchone()
        self.assertEqual(row[0], 'WHOLLY FICTIONAL: line one\nline two, with a comma', 'text exactly as exported')

    def test_import_errors(self):
        db = fresh_db()
        with tempfile.TemporaryDirectory() as tmp:
            bad = Path(tmp) / 'bad.csv'
            bad.write_text('submission_id,company_name\nX,Y\n', encoding='utf-8')
            with self.assertRaisesRegex(clientdb.ClientDBError, 'missing columns'):
                db.import_sheet_export(bad)
            header = SHEET.read_text(encoding='utf-8').splitlines()[0]
            bad.write_text(header + '\n' + ','.join([''] * 31) + '\n', encoding='utf-8')
            with self.assertRaisesRegex(clientdb.ClientDBError, 'no submission_id'):
                db.import_sheet_export(bad)
            values = SHEET.read_text(encoding='utf-8').splitlines()[1].replace(',new,', ',bogus,')
            bad.write_text(header + '\n' + values + '\n', encoding='utf-8')
            with self.assertRaisesRegex(clientdb.ClientDBError, 'unknown intake_status'):
                db.import_sheet_export(bad)
            with self.assertRaisesRegex(clientdb.ClientDBError, 'not found'):
                db.import_sheet_export(Path(tmp) / 'nope.csv')
            # a failure on a later row must not leave the earlier rows (or their clients) committed
            lines = SHEET.read_text(encoding='utf-8').splitlines()
            lines[3] = lines[3].replace(',needs_information,', ',bogus,')
            bad.write_text('\n'.join(lines) + '\n', encoding='utf-8')
            with self.assertRaisesRegex(clientdb.ClientDBError, 'row 3 has unknown intake_status'):
                db.import_sheet_export(bad)
            self.assertFalse(db.connection.in_transaction)
        counts = db.summary()['counts']
        self.assertEqual((counts['requests'], counts['clients'], counts['imports']), (0, 0, 0), 'a failed import writes nothing, whichever row fails')


class BriefsAndDeliveries(unittest.TestCase):
    def test_malformed_manifest_contents_are_a_clear_error(self):
        db = fresh_db()
        good = {'tool': 'demandrange-pipeline', 'client_ref': 'x', 'brief_ref': 'B', 'dictionary_version': 'd1', 'export_version': 'e1',
                'export_id': 'E1', 'exported_at': '2026-11-03T12:00:00Z', 'rows_delivered': 1, 'columns': ['a'],
                'files': {'x-E1.csv': {'sha256': '0' * 64}}, 'inputs': [{'file': 'in.csv', 'sha256': '0' * 64, 'rows': 1}]}
        bad_cases = {'rows_delivered': 'many', 'inputs': [{'file': 'in.csv'}], 'files': {'x-E1.csv': 'not-an-object'}, 'inputs ': None}
        with tempfile.TemporaryDirectory() as tmp:
            for key, value in bad_cases.items():
                manifest = dict(good)
                manifest[key.strip()] = value
                path = Path(tmp) / 'MANIFEST.json'
                path.write_text(json.dumps(manifest), encoding='utf-8')
                with self.subTest(key=key), self.assertRaisesRegex(clientdb.ClientDBError, 'malformed contents'):
                    db.record_delivery(path, now=NOW)
        self.assertEqual(db.summary()['counts'], dict(db.summary()['counts'], clients=0, deliveries=0), 'nothing written')

    def test_record_delivery_from_a_real_manifest_and_mark_delivered(self):
        db = fresh_db()
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / 'list.csv'
            src.write_text('record_id,company\n0007,Fictional Pumps Alpha Ltd\n', encoding='utf-8')
            result = export.build([src], client='Fictional Pumps Alpha Ltd', export_id='E1', now=NOW, **VERSIONS)
            folder, manifest = export.write_delivery(result, Path(tmp) / 'd', xlsx=True)
            recorded = db.record_delivery(folder / 'MANIFEST.json', now=NOW)
            self.assertEqual(recorded['client_ref'], 'fictional-pumps-alpha-ltd')
            self.assertEqual(recorded['rows_delivered'], 1)
            again = db.record_delivery(folder / 'MANIFEST.json', now=NOW)
            self.assertEqual(again['manifest_sha256'], recorded['manifest_sha256'])
            files = db.connection.execute("SELECT kind, file_name FROM delivery_files ORDER BY kind, file_name").fetchall()
            self.assertEqual([tuple(f) for f in files], [('input', 'list.csv'), ('output', 'README.txt'), ('output', 'fictional-pumps-alpha-ltd-E1.csv'), ('output', 'fictional-pumps-alpha-ltd-E1.xlsx')])
            db.add_brief('DEMO-BRIEF-A-v1', 'fictional-pumps-alpha-ltd', brief_version='v1', status='agreed', brief_path=src, now=NOW)
            db.mark_delivered('fictional-pumps-alpha-ltd', 'E1', delivered_via='email to named contact', now=NOW)
            view = db.client('fictional-pumps-alpha-ltd')
            self.assertEqual(view['deliveries'][0]['delivered_at'], '2026-11-03T12:00:00Z')
            # re-recording the same manifest keeps the manual send record (both fields)
            db.record_delivery(folder / 'MANIFEST.json', now=NOW)
            view = db.client('fictional-pumps-alpha-ltd')
            self.assertEqual((view['deliveries'][0]['delivered_at'], view['deliveries'][0]['delivered_via']),
                             ('2026-11-03T12:00:00Z', 'email to named contact'))
            self.assertEqual(view['briefs'][0]['status'], 'agreed')
            # a different manifest reusing the export id is refused
            (folder / 'MANIFEST.json').write_text(json.dumps(dict(manifest, rows_delivered=99)), encoding='utf-8')
            with self.assertRaisesRegex(clientdb.ClientDBError, 'different manifest'):
                db.record_delivery(folder / 'MANIFEST.json')
            (folder / 'MANIFEST.json').write_text('{"tool": "other"}', encoding='utf-8')
            with self.assertRaisesRegex(clientdb.ClientDBError, 'not a pipeline export manifest'):
                db.record_delivery(folder / 'MANIFEST.json')
        with self.assertRaisesRegex(clientdb.ClientDBError, 'not found'):
            db.mark_delivered('nobody', 'E1', delivered_via='x')
        with self.assertRaisesRegex(clientdb.ClientDBError, 'not found'):
            db.add_brief('B', 'nobody')


class SearchAndRetention(unittest.TestCase):
    def test_search_across_tables(self):
        db = fresh_db()
        db.import_sheet_export(SHEET, now=NOW)
        hit = db.search('seals')
        self.assertEqual([c['client_ref'] for c in hit['clients']], ['fictional-seals-beta-plc'])
        self.assertEqual({r['submission_id'] for r in hit['requests']}, {'FX-0001', 'FX-0002'}, 'company name and product text both match')
        self.assertEqual(db.search('équipement')['requests'][0]['submission_id'], 'FX-0002')
        self.assertEqual(db.search("'; DROP TABLE requests; --")['requests'], [])
        self.assertEqual(db.summary()['counts']['requests'], 3)
        with self.assertRaisesRegex(clientdb.ClientDBError, 'two characters'):
            db.search('a')

    def test_retention_due(self):
        db = fresh_db()
        db.import_sheet_export(SHEET, now=NOW)
        due = db.retention_due(on=dt.date(2026, 11, 3))
        self.assertEqual([d['submission_id'] for d in due], ['FX-0003'])
        self.assertEqual(db.retention_due(on=dt.date(2025, 1, 1)), [])

    def test_search_wildcards_are_literal(self):
        db = fresh_db()
        db.upsert_client('Hundred Percent Ltd', now=NOW)
        db.upsert_client('a_b Ltd', now=NOW)
        db.upsert_client('axb Ltd', now=NOW)
        self.assertEqual([c['name'] for c in db.search('a_b')['clients']], ['a_b Ltd'], '_ must not match any character')
        self.assertEqual(db.search('100%')['clients'], [], '% must not match everything')
        self.assertEqual(db.search('%%')['clients'], [])
        self.assertEqual([c['name'] for c in db.search('Hundred')['clients']], ['Hundred Percent Ltd'])

    def test_add_brief_with_a_missing_file_is_a_clear_error(self):
        db = fresh_db()
        db.upsert_client('Fictional Client', now=NOW)
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(clientdb.ClientDBError, 'file not found'):
                db.add_brief('B-1', 'fictional-client', brief_path=Path(tmp) / 'missing.json', now=NOW)
            with self.assertRaisesRegex(clientdb.ClientDBError, 'file not found'):
                db.add_brief('B-1', 'fictional-client', brief_path=tmp, now=NOW)
        self.assertEqual(db.summary()['counts']['briefs'], 0)

    def test_add_brief_keeps_its_client_and_created_at(self):
        db = fresh_db()
        db.upsert_client('Fictional Client', now=NOW)
        db.upsert_client('Other Client', now=NOW)
        db.add_brief('B-1', 'fictional-client', brief_version='v1', status='draft', now=NOW)
        later = NOW + dt.timedelta(days=2)
        db.add_brief('B-1', 'fictional-client', brief_version='v2', status='agreed', now=later)
        row = db.connection.execute('SELECT client_ref, brief_version, status, created_at FROM briefs WHERE brief_ref = ?', ('B-1',)).fetchone()
        self.assertEqual(dict(row), {'client_ref': 'fictional-client', 'brief_version': 'v2', 'status': 'agreed', 'created_at': '2026-11-03T12:00:00Z'})
        with self.assertRaisesRegex(clientdb.ClientDBError, "already belongs to client 'fictional-client'"):
            db.add_brief('B-1', 'other-client', status='agreed', now=later)
        self.assertEqual([b['brief_ref'] for b in db.client('fictional-client')['briefs']], ['B-1'])
        self.assertEqual(db.client('other-client')['briefs'], [])

    def test_client_not_found(self):
        with self.assertRaises(clientdb.ClientDBError):
            fresh_db().client('nobody')


if __name__ == '__main__':
    unittest.main()
