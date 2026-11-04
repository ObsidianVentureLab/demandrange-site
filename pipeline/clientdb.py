"""Minimal searchable client database (SQLite, standard library) for Stage 5.

Scope: clients, quote requests imported from the Google Sheet's "Raw Responses" CSV export, briefs,
and lists delivered (recorded from P4 MANIFEST.json files). Everything is stored as text exactly as
received; nothing is sent anywhere. The database file holds personal data (the quote requests), so it
lives outside the repository and is never committed. See CLIENT-DB-DESIGN.md for the rationale.
"""
import contextlib
import csv
import datetime as _dt
import hashlib
import io
import json
import os
import re
import sqlite3
from pathlib import Path

from . import __version__
from .export import slugify

SCHEMA_VERSION = 1
# The Sheet's Raw Responses header (quote-form/form_schema.json raw_response_columns). Imports require these.
SHEET_COLUMNS = (
    'submission_id', 'submitted_at_utc', 'form_version', 'privacy_notice_version', 'consent_text_version', 'service_model',
    'source_page', 'asset_ref', 'campaign_ref', 'submission_token_hash', 'full_name', 'work_email', 'company_name',
    'company_website', 'phone_number', 'product_or_service', 'industries', 'target_regions', 'specific_countries',
    'job_seniority', 'email_response_requested', 'phone_contact_opt_in', 'additional_context', 'intake_status',
    'assigned_owner', 'first_response_at_utc', 'outcome', 'retention_review_at', 'notification_state',
    'notification_attempts', 'notification_last_error',
)
INTAKE_STATUSES = ('new', 'triage_in_progress', 'needs_information', 'quote_preparation', 'quote_sent', 'not_a_fit', 'withdrawn', 'closed')
SEARCH_LIMIT = 50
# retention_review_at must be an ISO date or date-time (as Code.gs writes it); '15/01/2029' would compare
# wrongly as text in retention-due, so it is rejected on import instead of being stored.
ISO_DATE = re.compile(r'\d{4}-\d{2}-\d{2}(?:[T ]\d{2}:\d{2}(?::\d{2}(?:\.\d+)?)?(?:Z|[+-]\d{2}:?\d{2})?)?')
DB_MODE = 0o600   # the database and its -wal/-shm sidecars hold personal data: owner read/write only


def _iso_date_ok(text):
    if not ISO_DATE.fullmatch(text):
        return False
    try:
        _dt.date.fromisoformat(text[:10])
    except ValueError:
        return False
    return True

SCHEMA = f"""
CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS clients (
  client_ref      TEXT PRIMARY KEY,            -- slug, same value P4 stamps as client_ref
  name            TEXT NOT NULL,
  website_domain  TEXT NOT NULL DEFAULT '',
  status          TEXT NOT NULL DEFAULT 'prospect' CHECK (status IN ('prospect','active','dormant','closed')),
  notes           TEXT NOT NULL DEFAULT '',
  created_at      TEXT NOT NULL,
  updated_at      TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS requests (                -- one row per Sheet submission, text exactly as exported
  submission_id   TEXT PRIMARY KEY,
  client_ref      TEXT REFERENCES clients(client_ref),
  {', '.join(c + ' TEXT NOT NULL DEFAULT ' + chr(39) + chr(39) for c in SHEET_COLUMNS if c != 'submission_id')},
  imported_at     TEXT NOT NULL,
  import_sha256   TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS requests_client ON requests(client_ref);
CREATE INDEX IF NOT EXISTS requests_status ON requests(intake_status);
CREATE TABLE IF NOT EXISTS imports (
  import_sha256   TEXT PRIMARY KEY,
  file_name       TEXT NOT NULL,
  imported_at     TEXT NOT NULL,
  rows_read       INTEGER NOT NULL,
  rows_new        INTEGER NOT NULL,
  rows_updated    INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS briefs (
  brief_ref       TEXT PRIMARY KEY,
  client_ref      TEXT NOT NULL REFERENCES clients(client_ref),
  brief_version   TEXT NOT NULL DEFAULT '',
  supplier_range  TEXT NOT NULL DEFAULT '',
  status          TEXT NOT NULL DEFAULT 'draft' CHECK (status IN ('draft','agreed','superseded')),
  brief_sha256    TEXT NOT NULL DEFAULT '',
  created_at      TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS deliveries (              -- one row per P4 export folder (MANIFEST.json)
  client_ref      TEXT NOT NULL REFERENCES clients(client_ref),
  export_id       TEXT NOT NULL,
  brief_ref       TEXT NOT NULL,
  dictionary_version TEXT NOT NULL,
  export_version  TEXT NOT NULL,
  exported_at     TEXT NOT NULL,
  rows_delivered  INTEGER NOT NULL,
  columns_json    TEXT NOT NULL,
  manifest_sha256 TEXT NOT NULL,
  folder          TEXT NOT NULL,
  delivered_at    TEXT NOT NULL DEFAULT '',      -- set by hand when Sean has sent it; blank = prepared only
  delivered_via   TEXT NOT NULL DEFAULT '',
  recorded_at     TEXT NOT NULL,
  PRIMARY KEY (client_ref, export_id)
);
CREATE TABLE IF NOT EXISTS delivery_files (
  client_ref      TEXT NOT NULL,
  export_id       TEXT NOT NULL,
  kind            TEXT NOT NULL CHECK (kind IN ('input','output')),
  file_name       TEXT NOT NULL,
  sha256          TEXT NOT NULL,
  rows            INTEGER,
  PRIMARY KEY (client_ref, export_id, kind, file_name),
  FOREIGN KEY (client_ref, export_id) REFERENCES deliveries(client_ref, export_id)
);
"""


class ClientDBError(ValueError):
    """The operation cannot be performed; the message says why."""


def _now(now=None):
    return (now or _dt.datetime.now(_dt.timezone.utc)).astimezone(_dt.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')


def _domain(website, email):
    from .icp import normalise_domain
    domain = normalise_domain(website) if website else ''
    if not domain and email and '@' in email:
        domain = normalise_domain(email.rsplit('@', 1)[1])
    return domain


def utc_today(now=None):
    """The UTC calendar date; stored timestamps are UTC, so date filters and labels use it too."""
    return (now or _dt.datetime.now(_dt.timezone.utc)).astimezone(_dt.timezone.utc).date()


class ClientDB:
    def __init__(self, path, *, create=False):
        """Open an existing database file. ``create=True`` (``db init``) may create the file, never its
        directory: a mistyped --db path must not quietly become a new directory and an empty database."""
        self.path = Path(path)
        if str(self.path) != ':memory:':
            if not self.path.parent.is_dir():
                raise ClientDBError(f'database directory does not exist: {self.path.parent} (create it first, outside the checkout)')
            if not create and not self.path.exists():
                raise ClientDBError(f'database not initialised: {self.path} does not exist; run: db --db {self.path} init')
        on_disk = str(self.path) != ':memory:'
        previous = os.umask(0o077)   # anything SQLite creates while opening (file, -wal, -shm) is 0600
        try:
            self.connection = sqlite3.connect(str(self.path))
            self.connection.row_factory = sqlite3.Row
            try:
                self.connection.execute('PRAGMA foreign_keys = ON')
                self.connection.execute('PRAGMA journal_mode = WAL') if on_disk else None
            except sqlite3.DatabaseError as error:   # an existing file that is not a SQLite database
                self.connection.close()
                raise ClientDBError(f'{self.path} is not a SQLite database ({error})') from None
        finally:
            os.umask(previous)
        if on_disk:
            self._restrict_files()

    def _restrict_files(self):
        """0600 on the database and its WAL sidecars, including a file created earlier with a wider mode.
        SQLite gives sidecars created later the database file's own permissions."""
        for path in (self.path, Path(str(self.path) + '-wal'), Path(str(self.path) + '-shm')):
            if path.exists() and (path.stat().st_mode & 0o777) != DB_MODE:
                os.chmod(path, DB_MODE)

    def close(self):
        self.connection.close()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()

    # -- schema --------------------------------------------------------------------------------
    def init(self, now=None):
        with self.connection:
            self.connection.executescript(SCHEMA)
            self.connection.execute('INSERT OR IGNORE INTO meta(key, value) VALUES (?, ?)', ('schema_version', str(SCHEMA_VERSION)))
            self.connection.execute('INSERT OR IGNORE INTO meta(key, value) VALUES (?, ?)', ('created_at', _now(now)))
            self.connection.execute('INSERT OR REPLACE INTO meta(key, value) VALUES (?, ?)', ('tool_version', __version__))
        return self.schema_version()

    def schema_version(self):
        try:
            row = self.connection.execute("SELECT value FROM meta WHERE key = 'schema_version'").fetchone()
        except sqlite3.OperationalError:
            row = None
        if row is None:
            raise ClientDBError('database not initialised; run: db init')
        return int(row['value'])

    # -- clients -------------------------------------------------------------------------------
    @contextlib.contextmanager
    def _transaction(self):
        """Commit on success and roll back on error. Inside an open transaction (an import, a delivery
        record) this is a no-op so the outer block decides: a failure anywhere leaves nothing behind."""
        if self.connection.in_transaction:
            yield
            return
        with self.connection:
            self.connection.execute('BEGIN')
            yield

    def upsert_client(self, name, *, client_ref=None, website_domain='', status=None, notes=None, now=None):
        name = ' '.join(str(name or '').split())
        if not name:
            raise ClientDBError('client: name is required')
        ref = client_ref or slugify(name)
        stamp = _now(now)
        existing = self.connection.execute('SELECT * FROM clients WHERE client_ref = ?', (ref,)).fetchone()
        with self._transaction():
            if existing is None:
                self.connection.execute('INSERT INTO clients(client_ref, name, website_domain, status, notes, created_at, updated_at) VALUES (?,?,?,?,?,?,?)',
                                        (ref, name, website_domain or '', status or 'prospect', notes or '', stamp, stamp))
            else:
                self.connection.execute('UPDATE clients SET website_domain = CASE WHEN ? != \'\' THEN ? ELSE website_domain END, '
                                        'status = COALESCE(?, status), notes = COALESCE(?, notes), updated_at = ? WHERE client_ref = ?',
                                        (website_domain or '', website_domain or '', status, notes, stamp, ref))
        return ref

    def client(self, client_ref):
        row = self.connection.execute('SELECT * FROM clients WHERE client_ref = ?', (client_ref,)).fetchone()
        if row is None:
            raise ClientDBError(f'client {client_ref!r} not found')
        requests = self.connection.execute('SELECT submission_id, submitted_at_utc, intake_status, outcome, product_or_service FROM requests WHERE client_ref = ? ORDER BY submitted_at_utc', (client_ref,)).fetchall()
        briefs = self.connection.execute('SELECT brief_ref, brief_version, status, supplier_range FROM briefs WHERE client_ref = ? ORDER BY created_at', (client_ref,)).fetchall()
        deliveries = self.connection.execute('SELECT export_id, brief_ref, exported_at, rows_delivered, delivered_at, delivered_via FROM deliveries WHERE client_ref = ? ORDER BY exported_at', (client_ref,)).fetchall()
        return {'client': dict(row), 'requests': [dict(r) for r in requests], 'briefs': [dict(b) for b in briefs], 'deliveries': [dict(d) for d in deliveries]}

    # -- Sheet import --------------------------------------------------------------------------
    def import_sheet_export(self, path, *, now=None):
        """Import the Sheet's Raw Responses CSV export. Idempotent: re-importing the same file is a no-op;
        changed rows (e.g. intake_status edits) are updated by submission_id."""
        path = Path(path)
        try:
            raw = path.read_bytes()
        except FileNotFoundError:
            raise ClientDBError(f'import: file not found: {path}')
        sha = hashlib.sha256(raw).hexdigest()
        if self.connection.execute('SELECT 1 FROM imports WHERE import_sha256 = ?', (sha,)).fetchone():
            return {'file': path.name, 'sha256': sha, 'rows_read': 0, 'rows_new': 0, 'rows_updated': 0, 'skipped': 'already imported'}
        try:
            text = raw.decode('utf-8-sig')
        except UnicodeDecodeError:
            raise ClientDBError(f'import: {path.name} is not UTF-8')
        reader = csv.DictReader(io.StringIO(text, newline=''))   # not splitlines(): keeps newlines inside quoted cells
        header = list(reader.fieldnames or [])
        missing = [c for c in SHEET_COLUMNS if c not in header]
        if missing:
            raise ClientDBError('import: not a Raw Responses export; missing columns ' + ', '.join(missing))
        stamp = _now(now)
        new = updated = read = 0
        with self._transaction():   # one transaction for the whole file: a bad row N leaves rows 1..N-1 unwritten too
            for row in reader:
                read += 1
                # Stored exactly as exported (no whitespace collapsing or trimming). Only derived values are
                # normalised: the client name/ref and domain (upsert_client) and the search term.
                values = {c: str(row.get(c) or '') for c in SHEET_COLUMNS}
                if not values['submission_id'].strip():
                    raise ClientDBError(f'import: row {read} has no submission_id')
                if values['intake_status'] and values['intake_status'] not in INTAKE_STATUSES:
                    raise ClientDBError(f'import: row {read} has unknown intake_status {values["intake_status"]!r}')
                if values['retention_review_at'] and not _iso_date_ok(values['retention_review_at']):
                    raise ClientDBError(f'import: row {read} retention_review_at {values["retention_review_at"]!r} is not an ISO date '
                                        '(YYYY-MM-DD or an ISO date-time); nothing from this file was imported')
                client_ref = None
                if values['company_name'].strip():
                    client_ref = self.upsert_client(values['company_name'], website_domain=_domain(values['company_website'], values['work_email']), now=now)
                existing = self.connection.execute('SELECT * FROM requests WHERE submission_id = ?', (values['submission_id'],)).fetchone()
                if existing is None:
                    columns = list(SHEET_COLUMNS) + ['client_ref', 'imported_at', 'import_sha256']
                    self.connection.execute(f'INSERT INTO requests({", ".join(columns)}) VALUES ({", ".join("?" * len(columns))})',
                                            [values[c] for c in SHEET_COLUMNS] + [client_ref, stamp, sha])
                    new += 1
                else:
                    changed = {c: values[c] for c in SHEET_COLUMNS if c != 'submission_id' and existing[c] != values[c]}
                    client_ref = client_ref or existing['client_ref']   # a blanked company_name never unlinks the client
                    if changed:
                        sets = ', '.join(f'{c} = ?' for c in changed) + ', client_ref = ?, imported_at = ?, import_sha256 = ?'
                        self.connection.execute(f'UPDATE requests SET {sets} WHERE submission_id = ?',
                                                list(changed.values()) + [client_ref, stamp, sha, values['submission_id']])
                        updated += 1
            self.connection.execute('INSERT INTO imports(import_sha256, file_name, imported_at, rows_read, rows_new, rows_updated) VALUES (?,?,?,?,?,?)',
                                    (sha, path.name, stamp, read, new, updated))
        return {'file': path.name, 'sha256': sha, 'rows_read': read, 'rows_new': new, 'rows_updated': updated}

    # -- briefs and deliveries -----------------------------------------------------------------
    def add_brief(self, brief_ref, client_ref, *, brief_version='', supplier_range='', status='draft', brief_path=None, now=None):
        if not self.connection.execute('SELECT 1 FROM clients WHERE client_ref = ?', (client_ref,)).fetchone():
            raise ClientDBError(f'client {client_ref!r} not found; add it first')
        try:
            sha = hashlib.sha256(Path(brief_path).read_bytes()).hexdigest() if brief_path else ''
        except (FileNotFoundError, IsADirectoryError):
            raise ClientDBError(f'brief: file not found: {brief_path}')
        existing = self.connection.execute('SELECT client_ref, created_at FROM briefs WHERE brief_ref = ?', (brief_ref,)).fetchone()
        if existing and existing['client_ref'] != client_ref:
            raise ClientDBError(f'brief: {brief_ref} already belongs to client {existing["client_ref"]!r}; use a new brief ref for {client_ref!r}')
        # Re-adding the same brief updates its version/status/hash but keeps the original created_at.
        with self.connection:
            self.connection.execute('INSERT OR REPLACE INTO briefs(brief_ref, client_ref, brief_version, supplier_range, status, brief_sha256, created_at) VALUES (?,?,?,?,?,?,?)',
                                    (brief_ref, client_ref, brief_version, supplier_range, status, sha, existing['created_at'] if existing else _now(now)))
        return brief_ref

    def record_delivery(self, manifest_path, *, delivered_at='', delivered_via='', now=None):
        """Record a P4 export folder from its MANIFEST.json. The client is created if unknown."""
        manifest_path = Path(manifest_path)
        try:
            raw = manifest_path.read_bytes()
            manifest = json.loads(raw.decode('utf-8'))
        except FileNotFoundError:
            raise ClientDBError(f'delivery: file not found: {manifest_path}')
        except (UnicodeDecodeError, json.JSONDecodeError):
            raise ClientDBError(f'delivery: {manifest_path.name} is not a JSON manifest')
        required = ('client_ref', 'brief_ref', 'dictionary_version', 'export_version', 'export_id', 'exported_at', 'rows_delivered', 'columns', 'files', 'inputs')
        missing = [k for k in required if k not in manifest]
        if missing or manifest.get('tool') != 'demandrange-pipeline':
            raise ClientDBError('delivery: not a pipeline export manifest (missing ' + ', '.join(missing) + ')')
        sha = hashlib.sha256(raw).hexdigest()
        try:
            return self._record_delivery(manifest, manifest_path, sha, delivered_at=delivered_at, delivered_via=delivered_via, now=now)
        except (KeyError, TypeError, ValueError, AttributeError) as error:   # right keys, malformed contents
            raise ClientDBError(f'delivery: {manifest_path.name} has malformed contents ({type(error).__name__}: {error})') from None

    def _record_delivery(self, manifest, manifest_path, sha, *, delivered_at, delivered_via, now):
        client_ref = manifest['client_ref']
        existing = self.connection.execute('SELECT manifest_sha256 FROM deliveries WHERE client_ref = ? AND export_id = ?', (client_ref, manifest['export_id'])).fetchone()
        if existing and existing['manifest_sha256'] != sha:
            raise ClientDBError(f'delivery: export {manifest["export_id"]} for {client_ref} is already recorded with a different manifest; use a new export id')
        # Re-recording the same manifest must not erase a manual send record: keep the stored
        # delivered_at / delivered_via unless new values are given.
        previous = self.connection.execute('SELECT delivered_at, delivered_via FROM deliveries WHERE client_ref = ? AND export_id = ?',
                                           (client_ref, manifest['export_id'])).fetchone()
        keep_at = delivered_at or (previous['delivered_at'] if previous else '') or ''
        keep_via = delivered_via or (previous['delivered_via'] if previous else '') or ''
        with self._transaction():   # client upsert and delivery rows land together or not at all
            self.upsert_client(manifest.get('client_name') or client_ref, client_ref=client_ref, now=now)
            self.connection.execute('INSERT OR REPLACE INTO deliveries(client_ref, export_id, brief_ref, dictionary_version, export_version, exported_at, rows_delivered, columns_json, manifest_sha256, folder, delivered_at, delivered_via, recorded_at) '
                                    'VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)',
                                    (client_ref, manifest['export_id'], manifest['brief_ref'], manifest['dictionary_version'], manifest['export_version'],
                                     manifest['exported_at'], int(manifest['rows_delivered']), json.dumps(manifest['columns']), sha, str(manifest_path.parent),
                                     keep_at, keep_via, _now(now)))
            self.connection.execute('DELETE FROM delivery_files WHERE client_ref = ? AND export_id = ?', (client_ref, manifest['export_id']))
            for item in manifest['inputs']:
                self.connection.execute('INSERT INTO delivery_files VALUES (?,?,?,?,?,?)', (client_ref, manifest['export_id'], 'input', item['file'], item['sha256'], item.get('rows')))
            for name, info in manifest['files'].items():
                self.connection.execute('INSERT INTO delivery_files VALUES (?,?,?,?,?,?)', (client_ref, manifest['export_id'], 'output', name, info['sha256'], None))
        return {'client_ref': client_ref, 'export_id': manifest['export_id'], 'rows_delivered': int(manifest['rows_delivered']), 'manifest_sha256': sha}

    def mark_delivered(self, client_ref, export_id, *, delivered_via, now=None):
        with self.connection:
            cursor = self.connection.execute('UPDATE deliveries SET delivered_at = ?, delivered_via = ? WHERE client_ref = ? AND export_id = ?',
                                             (_now(now), ' '.join(str(delivered_via).split()), client_ref, export_id))
        if cursor.rowcount == 0:
            raise ClientDBError(f'delivery {export_id!r} for {client_ref!r} not found')

    # -- search --------------------------------------------------------------------------------
    def search(self, term, *, limit=SEARCH_LIMIT):
        term = ' '.join(str(term or '').split())
        if len(term) < 2:
            raise ClientDBError('search: give at least two characters')
        # % and _ are LIKE wildcards; escape them (with !) so a search for 100% or a_b is literal.
        escaped = term.replace('!', '!!').replace('%', '!%').replace('_', '!_')
        like = f'%{escaped}%'
        clients = self.connection.execute('SELECT client_ref, name, website_domain, status FROM clients WHERE name LIKE ? ESCAPE \'!\' OR client_ref LIKE ? ESCAPE \'!\' OR website_domain LIKE ? ESCAPE \'!\' ORDER BY name LIMIT ?',
                                          (like, like, like, limit)).fetchall()
        requests = self.connection.execute('SELECT submission_id, submitted_at_utc, client_ref, company_name, product_or_service, intake_status, outcome FROM requests '
                                           'WHERE company_name LIKE ? ESCAPE \'!\' OR product_or_service LIKE ? ESCAPE \'!\' OR additional_context LIKE ? ESCAPE \'!\' OR work_email LIKE ? ESCAPE \'!\' OR full_name LIKE ? ESCAPE \'!\' OR industries LIKE ? ESCAPE \'!\' OR target_regions LIKE ? ESCAPE \'!\' OR submission_id LIKE ? ESCAPE \'!\' '
                                           'ORDER BY submitted_at_utc DESC LIMIT ?', (like,) * 8 + (limit,)).fetchall()
        deliveries = self.connection.execute('SELECT client_ref, export_id, brief_ref, exported_at, rows_delivered, delivered_at FROM deliveries WHERE client_ref LIKE ? ESCAPE \'!\' OR brief_ref LIKE ? ESCAPE \'!\' OR export_id LIKE ? ESCAPE \'!\' ORDER BY exported_at DESC LIMIT ?',
                                             (like, like, like, limit)).fetchall()
        return {'term': term, 'clients': [dict(r) for r in clients], 'requests': [dict(r) for r in requests], 'deliveries': [dict(r) for r in deliveries]}

    def retention_due(self, on=None):
        # Stored timestamps are UTC, so compare against the UTC date, not the local one.
        today = (on or utc_today()).isoformat()
        rows = self.connection.execute('SELECT submission_id, client_ref, submitted_at_utc, intake_status, retention_review_at FROM requests '
                                       "WHERE retention_review_at != '' AND substr(retention_review_at, 1, 10) <= ? ORDER BY retention_review_at", (today,)).fetchall()
        return [dict(r) for r in rows]

    def summary(self):
        counts = {table: self.connection.execute(f'SELECT COUNT(*) FROM {table}').fetchone()[0] for table in ('clients', 'requests', 'briefs', 'deliveries', 'imports')}
        statuses = self.connection.execute('SELECT intake_status, COUNT(*) AS n FROM requests GROUP BY intake_status ORDER BY intake_status').fetchall()
        return {'schema_version': self.schema_version(), 'counts': counts, 'requests_by_status': {r['intake_status']: r['n'] for r in statuses}}
