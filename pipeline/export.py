"""Verified or candidate CSV(s) -> one per-client delivery folder: cleaned CSV, optional XLSX,
MANIFEST.json and a plain-text README. Nothing is sent; Sean delivers the folder manually.

Rules learned from foundation/handover-*.csv: every value stays text (identifiers keep leading
zeros, dates are not reinterpreted), Unicode survives, and the brief/dictionary/export versions
travel with every row. In the CSV, cells that a spreadsheet would execute as a formula are
neutralised; the XLSX needs no guard because every cell is written as an inline string.
"""
from dataclasses import dataclass, field
import csv
import datetime as _dt
import hashlib
import io
import json
import re
import zipfile
from pathlib import Path
from xml.sax.saxutils import escape

from . import __version__
from .csvsafe import neutralise  # shared with the P2 candidate CSV

SLUG = re.compile(r'[^a-z0-9-]+')
VERSION_RE = re.compile(r'^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$')
DECISION_COLUMN = 'verification_decision'
DECISION_RANK = {'keep': 0, 'review': 1, 'drop': 2}   # dedupe preference; anything else ranks after
STAMP_COLUMNS = ('client_ref', 'brief_ref', 'dictionary_version', 'export_version', 'export_id', 'exported_at')
INTERNAL_DEFAULT_DROP = ('fiction_notice',)   # kept when --keep-fiction-notice; fixtures carry it on purpose


class ExportError(ValueError):
    """The export cannot be produced; the message says why."""


@dataclass
class Export:
    client: str
    client_name: str
    brief_ref: str
    dictionary_version: str
    export_version: str
    export_id: str
    exported_at: str
    columns: list
    rows: list = field(default_factory=list)
    inputs: list = field(default_factory=list)
    decisions_included: tuple = ()
    rows_read: int = 0
    rows_excluded_by_decision: int = 0
    decision_filtered: bool = False   # the input had verification_decision, so --include-decisions applied
    duplicates_dropped: int = 0
    columns_dropped: tuple = ()


def slugify(name):
    slug = SLUG.sub('-', str(name or '').strip().lower()).strip('-')
    if not slug:
        raise ExportError('client: a non-empty name is required')
    return slug[:64]


def check_version(label, value, required=True):
    value = str(value or '').strip()
    if not value:
        if required:
            raise ExportError(f'{label}: required (record the agreed version; blank does not mean none)')
        return ''
    if not VERSION_RE.match(value):
        raise ExportError(f'{label}: {value!r} may only contain letters, digits, ., _ or -')
    return value


def _decision_rank(row):
    return DECISION_RANK.get((row.get(DECISION_COLUMN) or '').strip().lower(), len(DECISION_RANK))


def read_inputs(paths):
    inputs, columns, rows = [], None, []
    for path in paths:
        path = Path(path)
        try:
            raw = path.read_bytes()
        except FileNotFoundError:
            raise ExportError(f'input: file not found: {path}')
        try:
            text = raw.decode('utf-8-sig')
        except UnicodeDecodeError:
            raise ExportError(f'input: {path.name} is not UTF-8')
        reader = csv.DictReader(io.StringIO(text, newline=''))   # not splitlines(): keeps newlines inside quoted cells
        header = list(reader.fieldnames or [])
        if not header:
            raise ExportError(f'input: {path.name} has no header row')
        if columns is None:
            columns = header
        elif header != columns:
            raise ExportError(f'input: {path.name} header differs from the first file; export one schema per delivery')
        file_rows = [dict(r) for r in reader]
        for row in file_rows:
            if None in row:
                raise ExportError(f'input: {path.name} has a row with more cells than the header')
        rows.extend(file_rows)
        manifest = path.with_name(path.stem + '.manifest.json')
        inputs.append({'file': path.name, 'sha256': hashlib.sha256(raw).hexdigest(), 'rows': len(file_rows),
                       'source_manifest': manifest.name if manifest.exists() else None,
                       'source_manifest_sha256': hashlib.sha256(manifest.read_bytes()).hexdigest() if manifest.exists() else None})
    if not inputs:
        raise ExportError('input: at least one CSV is required')
    return inputs, columns, rows


def build(paths, *, client, brief_ref, dictionary_version, export_version, export_id=None, decisions=('keep',),
          drop_columns=(), keep_fiction_notice=False, dedupe_on=None, now=None):
    moment = now or _dt.datetime.now(_dt.timezone.utc)
    exported_at = moment.strftime('%Y-%m-%dT%H:%M:%SZ')
    client_slug = slugify(client)
    brief_ref = check_version('brief_ref', brief_ref)
    dictionary_version = check_version('dictionary_version', dictionary_version)
    export_version = check_version('export_version', export_version)
    export_id = check_version('export_id', export_id or moment.strftime('%Y%m%dT%H%M%SZ'))
    inputs, columns, rows = read_inputs(paths)
    clash = [c for c in STAMP_COLUMNS if c in columns]
    if clash:
        raise ExportError('input: already contains export columns ' + ', '.join(clash) + '; export from the un-stamped file')
    decisions = tuple(d.strip().lower() for d in decisions if d.strip())
    if not decisions:
        raise ExportError('--include-decisions: at least one verification_decision value is required (e.g. keep or keep,review)')
    result = Export(client_slug, ' '.join(str(client).split()), brief_ref, dictionary_version, export_version, export_id,
                    exported_at, [], inputs=inputs, decisions_included=decisions, rows_read=len(rows))
    if DECISION_COLUMN in columns:
        kept = [r for r in rows if (r.get(DECISION_COLUMN) or '').strip().lower() in decisions]
        result.rows_excluded_by_decision = len(rows) - len(kept)
        result.decision_filtered = True
        rows = kept
    elif decisions != ('keep',):
        raise ExportError(f'--include-decisions given but the input has no {DECISION_COLUMN} column')
    drop = set(drop_columns)
    if not keep_fiction_notice:
        drop.update(INTERNAL_DEFAULT_DROP)
    missing = sorted(d for d in drop_columns if d not in columns)
    if missing:
        raise ExportError('--drop-columns: not in the input: ' + ', '.join(missing))
    result.columns_dropped = tuple(c for c in columns if c in drop)
    out_columns = [c for c in columns if c not in drop]
    if not out_columns:
        raise ExportError('every column was dropped; nothing to deliver')
    if dedupe_on:
        if dedupe_on not in out_columns:
            raise ExportError(f'--dedupe-on: column {dedupe_on!r} not in the output columns')
        # Keep one row per key: the one with the best verification decision (keep < review < other),
        # first seen on ties, so a `review` row cannot displace a later `keep` row for the same address.
        best, unique = {}, []
        for row in rows:
            key = ' '.join(str(row.get(dedupe_on) or '').split()).lower()
            if not key:
                unique.append(row)
                continue
            if key in best:
                result.duplicates_dropped += 1
                index = best[key]
                if _decision_rank(row) < _decision_rank(unique[index]):
                    unique[index] = row
                continue
            best[key] = len(unique)
            unique.append(row)
        rows = unique
    result.columns = out_columns + list(STAMP_COLUMNS)
    stamp = {'client_ref': client_slug, 'brief_ref': brief_ref, 'dictionary_version': dictionary_version,
             'export_version': export_version, 'export_id': export_id, 'exported_at': exported_at}
    for row in rows:
        out = {c: ('' if row.get(c) is None else str(row.get(c))) for c in out_columns}
        out.update(stamp)
        result.rows.append(out)
    return result


# -- writers -----------------------------------------------------------------------------------
def _col_name(index):
    name = ''
    index += 1
    while index:
        index, rem = divmod(index - 1, 26)
        name = chr(65 + rem) + name
    return name


def write_xlsx(path, columns, rows, sheet_name='Delivery'):
    """Minimal .xlsx (SpreadsheetML) with every cell as an inline string: no type inference,
    no leading-zero loss, no dates reinterpreted. Standard library only."""
    def cell(ref, value):
        text = escape(str(value), {'"': '&quot;'})
        text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f]', '', text)
        space = ' xml:space="preserve"' if text != text.strip() or '  ' in text else ''
        return f'<c r="{ref}" t="inlineStr"><is><t{space}>{text}</t></is></c>'
    lines = ['<?xml version="1.0" encoding="UTF-8" standalone="yes"?>',
             '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData>']
    for r, values in enumerate([columns] + [[row.get(c, '') for c in columns] for row in rows], start=1):
        cells = ''.join(cell(f'{_col_name(i)}{r}', v) for i, v in enumerate(values))
        lines.append(f'<row r="{r}">{cells}</row>')
    lines.append('</sheetData></worksheet>')
    sheet_xml = '\n'.join(lines)
    workbook = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
                'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
                f'<sheets><sheet name="{escape(sheet_name)}" sheetId="1" r:id="rId1"/></sheets></workbook>')
    wb_rels = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
               '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
               '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>'
               '</Relationships>')
    rels = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>'
            '</Relationships>')
    content_types = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                     '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
                     '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
                     '<Default Extension="xml" ContentType="application/xml"/>'
                     '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
                     '<Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
                     '</Types>')
    fixed = (1980, 1, 1, 0, 0, 0)   # reproducible archive: same input -> same bytes
    with zipfile.ZipFile(path, 'w', zipfile.ZIP_DEFLATED) as archive:
        for name, data in (('[Content_Types].xml', content_types), ('_rels/.rels', rels), ('xl/workbook.xml', workbook),
                           ('xl/_rels/workbook.xml.rels', wb_rels), ('xl/worksheets/sheet1.xml', sheet_xml)):
            info = zipfile.ZipInfo(name, date_time=fixed)
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, data.encode('utf-8'))


def _readme(result, csv_name, xlsx_name):
    lines = [
        f'Demand Range: list delivery for {result.client_name}',
        f'Export {result.export_id} (export version {result.export_version}), prepared {result.exported_at}',
        f'Brief reference: {result.brief_ref}',
        f'Field dictionary version: {result.dictionary_version}',
        '',
        'Files',
        f'  {csv_name}  — UTF-8 CSV (with byte-order mark so spreadsheets read accents correctly); every value is text.',
    ]
    if xlsx_name:
        lines.append(f'  {xlsx_name} — the same rows as a workbook; all cells are text, so identifiers keep leading zeros.')
    lines += ['  MANIFEST.json — row counts, column list and SHA-256 checksums for the files above.', '',
              f'Rows delivered: {len(result.rows)}']
    if result.decision_filtered:
        lines.append('Verification decisions included: ' + ', '.join(result.decisions_included)
                     + f' ({result.rows_excluded_by_decision} rows with other decisions were left out)')
    lines += ['', 'Columns', *(f'  {c}' for c in result.columns), '',
              'Notes',
              '  In the CSV, values that begin with =, @ or a non-numeric + or - carry a leading apostrophe so a',
              '  spreadsheet shows them as text; phone numbers and signed numbers are untouched.',
              '  The brief, dictionary and export versions on every row identify exactly what was agreed and produced;',
              '  quote them in any query about this delivery.',
              '  This file is delivered manually by Demand Range; it is not an automated mailing and nothing in it has been sent.']
    return '\n'.join(lines) + '\n'


def write_delivery(result, out_dir, *, xlsx=False):
    out_dir = Path(out_dir) / result.client / result.export_id
    if out_dir.exists():
        if not out_dir.is_dir():
            raise ExportError(f'output path already exists and is not a folder: {out_dir}')
        if any(out_dir.iterdir()):
            raise ExportError(f'output folder already exists and is not empty: {out_dir} (use a new --export-id)')
    try:
        out_dir.mkdir(parents=True, exist_ok=True)
    except (NotADirectoryError, FileExistsError) as error:
        raise ExportError(f'output path cannot be created (a file is in the way): {out_dir}') from error
    base = f'{result.client}-{result.export_id}'
    csv_path = out_dir / (base + '.csv')
    with csv_path.open('w', encoding='utf-8-sig', newline='') as handle:
        writer = csv.DictWriter(handle, fieldnames=result.columns, lineterminator='\r\n', quoting=csv.QUOTE_ALL)
        # Header names come from the input files, so they get the same guard as the values.
        writer.writerow({c: neutralise(c) for c in result.columns})
        writer.writerows({c: neutralise(v) for c, v in row.items()} for row in result.rows)
    files = {csv_path.name: csv_path}
    xlsx_path = None
    if xlsx:
        xlsx_path = out_dir / (base + '.xlsx')
        write_xlsx(xlsx_path, result.columns, result.rows)
        files[xlsx_path.name] = xlsx_path
    readme_path = out_dir / 'README.txt'
    readme_path.write_text(_readme(result, csv_path.name, xlsx_path.name if xlsx_path else None), encoding='utf-8')
    files[readme_path.name] = readme_path
    manifest = {
        'tool': 'demandrange-pipeline', 'tool_version': __version__,
        'client_ref': result.client, 'client_name': result.client_name, 'brief_ref': result.brief_ref, 'dictionary_version': result.dictionary_version,
        'export_version': result.export_version, 'export_id': result.export_id, 'exported_at': result.exported_at,
        'inputs': result.inputs,
        'selection': {'decisions_included': list(result.decisions_included) if result.decision_filtered else None,
                      'rows_read': result.rows_read, 'rows_excluded_by_decision': result.rows_excluded_by_decision,
                      'duplicates_dropped': result.duplicates_dropped, 'columns_dropped': list(result.columns_dropped)},
        'rows_delivered': len(result.rows), 'columns': result.columns,
        'files': {name: {'sha256': hashlib.sha256(path.read_bytes()).hexdigest(), 'bytes': path.stat().st_size} for name, path in files.items()},
        'delivery': 'manual by Demand Range; no automated sending',
    }
    manifest_path = out_dir / 'MANIFEST.json'
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    return out_dir, manifest
