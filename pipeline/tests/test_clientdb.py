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
            with clientdb.ClientDB(path) as db:
                self.assertEqual(db.init(now=NOW), 1)
                self.assertEqual(db.init(), 1)
                self.assertEqual(db.summary()['counts'], {'clients': 0, 'requests': 0, 'briefs': 0, 'deliveries': 0, 'imports': 0})
            with clientdb.ClientDB(path) as db:
                self.assertEqual(db.schema_version(), 1)
            with clientdb.ClientDB(Path(tmp) / 'empty.sqlite') as db:
                with self.assertRaisesRegex(clientdb.ClientDBError, 'not initialised'):
                    db.schema_version()

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
        self.assertEqual(db.summary()['counts']['requests'], 0, 'a failed import writes nothing')


class BriefsAndDeliveries(unittest.TestCase):
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

    def test_client_not_found(self):
        with self.assertRaises(clientdb.ClientDBError):
            fresh_db().client('nobody')


if __name__ == '__main__':
    unittest.main()
