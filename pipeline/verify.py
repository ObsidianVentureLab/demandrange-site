"""CSV with an email column -> ZeroBounce verification -> same rows + zb_* columns, decision, manifest.

Addresses are normalised (trimmed, lower-cased), verified once each, and never written anywhere
other than the output directory. Local syntax failures are not sent (they would cost nothing but
also add nothing). A credit-budget stop keeps every row: unverified ones are marked as such.
"""
from dataclasses import dataclass, field
import csv
import datetime as _dt
import hashlib
import json
import re
from pathlib import Path

from . import __version__
from .zerobounce import DECISIONS, MAX_BATCH, BATCH_PATH, BudgetExceeded

EMAIL_RE = re.compile(r"^[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?(?:\.[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?)+$")
CANDIDATE_EMAIL_COLUMNS = ('email', 'work_email', 'email_address', 'contact_email')
ADDED_COLUMNS = ('zb_status', 'zb_sub_status', 'zb_free_email', 'zb_did_you_mean', 'zb_mx_found',
                 'zb_domain_age_days', 'zb_processed_at', 'verification_decision', 'verified_at', 'verification_source')
FIXTURE_MODE, LIVE_MODE = 'fixture', 'live'
FICTION_NOTICE = 'WHOLLY FICTIONAL FIXTURE DATA; NO REAL PEOPLE OR ADDRESSES'
SAFE_NAME = re.compile(r'[^A-Za-z0-9._-]+')


class VerifyError(ValueError):
    """The input cannot be verified; the message says why."""


@dataclass
class Verification:
    rows: list = field(default_factory=list)
    columns: list = field(default_factory=list)
    email_column: str = ''
    unique_addresses: int = 0
    sent: int = 0
    skipped_local_syntax: int = 0
    not_verified: int = 0
    batches: int = 0
    api_errors: list = field(default_factory=list)
    stopped_reason: str = ''


def normalise_email(value):
    return ' '.join(str(value or '').split()).strip().lower()


def read_rows(path, email_column=None):
    path = Path(path)
    try:
        with path.open(encoding='utf-8-sig', newline='') as handle:
            reader = csv.DictReader(handle)
            columns = list(reader.fieldnames or [])
            rows = [dict(row) for row in reader]
    except FileNotFoundError:
        raise VerifyError(f'input: file not found: {path}')
    except UnicodeDecodeError:
        raise VerifyError(f'input: {path.name} is not UTF-8')
    if not columns:
        raise VerifyError(f'input: {path.name} has no header row')
    if email_column is None:
        email_column = next((c for c in columns if c.strip().lower() in CANDIDATE_EMAIL_COLUMNS), None)
        if email_column is None:
            raise VerifyError('input: no email column found; pass --email-column (looked for ' + ', '.join(CANDIDATE_EMAIL_COLUMNS) + ')')
    if email_column not in columns:
        raise VerifyError(f'input: column {email_column!r} not in header {columns}')
    clash = [c for c in ADDED_COLUMNS if c in columns]
    if clash:
        raise VerifyError('input: already contains verification columns ' + ', '.join(clash) + '; verify the original file')
    return rows, columns, email_column


def plan(rows, email_column):
    addresses = {normalise_email(r.get(email_column)) for r in rows}
    addresses.discard('')
    sendable = sorted(a for a in addresses if EMAIL_RE.match(a))
    return {'rows': len(rows), 'unique_addresses': len(addresses), 'sendable': len(sendable),
            'skipped_local_syntax': len(addresses) - len(sendable), 'max_credits': len(sendable),
            'batches': -(-len(sendable) // MAX_BATCH)}


def _remaining_budget(client, default):
    budget = getattr(client, 'credit_budget', None)
    if budget is None:
        return default
    return max(0, int(budget) - int(getattr(client, 'credits_used', 0)))


def verify_rows(rows, columns, email_column, client, *, batch_size=MAX_BATCH, data_mode=LIVE_MODE, now=None):
    verified_at = (now or _dt.datetime.now(_dt.timezone.utc)).strftime('%Y-%m-%dT%H:%M:%SZ')
    batch_size = max(1, min(int(batch_size), MAX_BATCH))
    result = Verification(columns=list(columns) + list(ADDED_COLUMNS), email_column=email_column)
    addresses = []
    for row in rows:
        address = normalise_email(row.get(email_column))
        if address and address not in addresses:
            addresses.append(address)
    result.unique_addresses = len(addresses)
    outcome = {}
    sendable = []
    for address in addresses:
        if EMAIL_RE.match(address):
            sendable.append(address)
        else:
            outcome[address] = {'status': 'skipped_local_syntax', 'sub_status': 'failed_local_syntax_check', 'decision': 'drop'}
            result.skipped_local_syntax += 1
    start = 0
    while start < len(sendable):
        # Never ask for more than the budget can still cover: a first live check with
        # --credit-budget 1 sends one address instead of failing on a full-size batch.
        size = min(batch_size, _remaining_budget(client, batch_size))
        batch = sendable[start:start + size]
        try:
            if not batch:
                raise BudgetExceeded(f'credit budget of {client.credit_budget} reached (used {client.credits_used}); '
                                     f'{len(sendable) - start} address(es) left unverified')
            response = client.validate_batch(batch)
        except BudgetExceeded as error:
            result.stopped_reason = 'credit budget reached: ' + str(error)
            if start == 0:
                raise
            break
        result.batches += 1
        result.sent += len(batch)
        start += len(batch)
        result.api_errors.extend(dict(e) for e in response.errors)
        for item in response.results:
            outcome[item['address']] = dict(item, decision=DECISIONS.get(item['status'], 'review'))
    for address in sendable:
        if address not in outcome:
            outcome[address] = {'status': 'not_verified', 'sub_status': 'credit_budget_reached', 'decision': 'review'}
            result.not_verified += 1
    if not result.stopped_reason:
        result.stopped_reason = 'all addresses processed'
    source = ('zerobounce:' + BATCH_PATH.strip('/')) if data_mode == LIVE_MODE else 'fixture'
    for row in rows:
        address = normalise_email(row.get(email_column))
        info = outcome.get(address, {'status': 'skipped_local_syntax', 'sub_status': 'empty', 'decision': 'drop'})
        out = dict(row)
        out.update({
            'zb_status': info.get('status', ''), 'zb_sub_status': info.get('sub_status', ''),
            'zb_free_email': _flag(info.get('free_email')), 'zb_did_you_mean': _text(info.get('did_you_mean')),
            'zb_mx_found': _flag(info.get('mx_found')), 'zb_domain_age_days': _text(info.get('domain_age_days')),
            'zb_processed_at': _text(info.get('processed_at')), 'verification_decision': info.get('decision', 'review'),
            'verified_at': verified_at, 'verification_source': source,
        })
        result.rows.append(out)
    return result


def _flag(value):
    if value is None or value == '':
        return ''
    if isinstance(value, str):
        return value.strip().lower() if value.strip().lower() in ('true', 'false') else value
    return 'true' if value else 'false'


def _text(value):
    return '' if value is None else ' '.join(str(value).split())


def _safe(name):
    return SAFE_NAME.sub('-', name).strip('-') or 'list'


def write_outputs(result, input_path, out_dir, *, data_mode, client=None, credit_budget=None, now=None):
    input_path = Path(input_path)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    stem = _safe(input_path.stem) + '-verified'
    csv_path = out_dir / (stem + '.csv')
    manifest_path = out_dir / (stem + '.manifest.json')
    with csv_path.open('w', encoding='utf-8', newline='') as handle:
        writer = csv.DictWriter(handle, fieldnames=result.columns, lineterminator='\n', extrasaction='ignore')
        writer.writeheader()
        writer.writerows(result.rows)
    statuses, decisions = {}, {}
    for row in result.rows:
        statuses[row['zb_status']] = statuses.get(row['zb_status'], 0) + 1
        decisions[row['verification_decision']] = decisions.get(row['verification_decision'], 0) + 1
    generated_at = (now or _dt.datetime.now(_dt.timezone.utc)).strftime('%Y-%m-%dT%H:%M:%SZ')
    manifest = {
        'tool': 'demandrange-pipeline', 'tool_version': __version__, 'generated_at': generated_at,
        'data_mode': data_mode, 'fiction_notice': FICTION_NOTICE if data_mode == FIXTURE_MODE else None,
        'input': {'file': input_path.name, 'sha256': hashlib.sha256(input_path.read_bytes()).hexdigest(),
                  'rows': len(result.rows), 'email_column': result.email_column},
        'zerobounce': {'base_url': getattr(client, 'base_url', None), 'batches': result.batches, 'addresses_sent': result.sent,
                       'credit_budget': credit_budget, 'credits_charged': getattr(client, 'credits_used', None),
                       'requests_made': getattr(client, 'requests_made', None), 'api_errors': result.api_errors},
        'counts': {'unique_addresses': result.unique_addresses, 'skipped_local_syntax': result.skipped_local_syntax,
                   'not_verified': result.not_verified, 'by_status': dict(sorted(statuses.items())),
                   'by_decision': dict(sorted(decisions.items()))},
        'stopped_reason': result.stopped_reason,
        'output': {'csv': csv_path.name, 'columns': list(result.columns), 'sha256': hashlib.sha256(csv_path.read_bytes()).hexdigest()},
        'note': 'Decisions: keep=valid; drop=invalid/spamtrap/abuse/do_not_mail or local syntax failure; review=catch-all/unknown/not verified. The analyst confirms before any delivery.',
    }
    manifest_path.write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')
    return csv_path, manifest_path
