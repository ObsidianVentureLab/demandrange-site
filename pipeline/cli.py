"""Command line: `python -m pipeline <command>`.

    validate  --brief FILE                      check a brief and print the Apollo filters
    prospects --brief FILE --out DIR [--fixture FILE | --live --credit-budget N]
    verify    --input CSV  --out DIR [--email-column NAME] [--fixture FILE | --live --credit-budget N]
    credits   --live                            ZeroBounce credit balance (not charged)
    export    --input CSV [CSV...] --client NAME --brief-ref R --dictionary-version D --export-version E --out DIR [--xlsx]
    db        --db FILE init | import-sheet CSV | record-delivery MANIFEST | mark-delivered | search TERM | client REF | retention-due | summary

Default is a dry run: the plan (filters/addresses, max credits) is printed and nothing is sent.
--fixture replays a canned response file offline. --live needs the provider key in the
environment (APOLLO_API_KEY / ZEROBOUNCE_API_KEY) and an explicit --credit-budget; the budget
defaults to 0, so a live run without a budget stops before the first request.
"""
import argparse
import json
import sys

from . import apollo, clientdb, export, icp, prospects, verify, zerobounce

EXIT_OK, EXIT_USAGE, EXIT_PROVIDER = 0, 2, 3   # 3 = any provider (Apollo, ZeroBounce) error


def build_parser():
    parser = argparse.ArgumentParser(prog='python -m pipeline', description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest='command', required=True)

    validate = sub.add_parser('validate', help='validate an ICP brief and print the Apollo filters')
    validate.add_argument('--brief', required=True, help='ICP brief JSON file')

    run = sub.add_parser('prospects', help='build a candidate company list from a brief')
    run.add_argument('--brief', required=True, help='ICP brief JSON file')
    run.add_argument('--out', required=True, help='output directory for the CSV and manifest')
    run.add_argument('--per-page', type=int, default=apollo.MAX_PER_PAGE, help='results per page (1-100)')
    mode = run.add_mutually_exclusive_group()
    mode.add_argument('--fixture', help='replay this canned response file instead of calling Apollo')
    mode.add_argument('--live', action='store_true',
                      help=f'call Apollo for real (key from ${apollo.API_KEY_ENV}; requires --credit-budget)')
    run.add_argument('--credit-budget', type=int, default=0,
                     help='maximum Apollo credits (pages) this run may spend; default 0 = none')

    ver = sub.add_parser('verify', help='verify the email column of a CSV with ZeroBounce')
    ver.add_argument('--input', required=True, help='CSV with an email column')
    ver.add_argument('--out', required=True, help='output directory for the verified CSV and manifest')
    ver.add_argument('--email-column', help='column holding the address (default: first of email, work_email, email_address, contact_email)')
    ver.add_argument('--batch-size', type=int, default=zerobounce.MAX_BATCH, help=f'addresses per request (1-{zerobounce.MAX_BATCH})')
    ver.add_argument('--base-url', default=zerobounce.DEFAULT_BASE_URL,
                     help='ZeroBounce API host; default is the EU endpoint, api-us.zerobounce.net processes in the United States')
    vmode = ver.add_mutually_exclusive_group()
    vmode.add_argument('--fixture', help='replay this canned results file instead of calling ZeroBounce')
    vmode.add_argument('--live', action='store_true',
                       help=f'call ZeroBounce for real (key from ${zerobounce.API_KEY_ENV}; requires --credit-budget)')
    ver.add_argument('--credit-budget', type=int, default=0,
                     help='maximum ZeroBounce credits (addresses) this run may charge; default 0 = none')

    cred = sub.add_parser('credits', help='print the ZeroBounce credit balance (needs --live; not charged)')
    cred.add_argument('--live', action='store_true', help=f'call ZeroBounce (key from ${zerobounce.API_KEY_ENV})')
    cred.add_argument('--base-url', default=zerobounce.DEFAULT_BASE_URL)

    exp = sub.add_parser('export', help='build a per-client delivery folder (CSV, optional XLSX, README, MANIFEST); nothing is sent')
    exp.add_argument('--input', required=True, nargs='+', help='one or more CSVs with the same header (e.g. a verified list)')
    exp.add_argument('--out', required=True, help='deliveries root; the folder <out>/<client>/<export-id>/ is created')
    exp.add_argument('--client', required=True, help='client name; slugified for folder and file names')
    exp.add_argument('--brief-ref', required=True, help='agreed brief reference, e.g. DEMO-BRIEF-A-v1')
    exp.add_argument('--dictionary-version', required=True, help='field dictionary version, e.g. DEMO-DICT-v1')
    exp.add_argument('--export-version', required=True, help='output format version, e.g. DEMO-EXPORT-v1')
    exp.add_argument('--export-id', help='delivery identifier (default: UTC timestamp)')
    exp.add_argument('--include-decisions', default='keep',
                     help='comma list of verification_decision values to deliver (default keep; e.g. keep,review)')
    exp.add_argument('--drop-columns', default='', help='comma list of columns to leave out (e.g. zb_sub_status,zb_domain_age_days)')
    exp.add_argument('--dedupe-on', help='drop later rows whose value in this column repeats (case-insensitive)')
    exp.add_argument('--keep-fiction-notice', action='store_true', help='keep a fiction_notice column (fixtures only)')
    exp.add_argument('--xlsx', action='store_true', help='also write an .xlsx workbook (all cells text)')

    db = sub.add_parser('db', help='searchable client database (SQLite file outside the repo; holds personal data)')
    db.add_argument('--db', required=True, help='SQLite file path (create with: db --db FILE init)')
    dbsub = db.add_subparsers(dest='db_command', required=True)
    dbsub.add_parser('init', help='create or upgrade the schema')
    imp = dbsub.add_parser('import-sheet', help='import the Sheet\'s Raw Responses CSV export (idempotent)')
    imp.add_argument('csv')
    rec = dbsub.add_parser('record-delivery', help='record a P4 export folder from its MANIFEST.json')
    rec.add_argument('manifest')
    mark = dbsub.add_parser('mark-delivered', help='note that Sean sent a recorded export (manual step)')
    mark.add_argument('--client-ref', required=True)
    mark.add_argument('--export-id', required=True)
    mark.add_argument('--via', required=True, help='how it was sent, e.g. "email to named contact, 3 Nov"')
    brief = dbsub.add_parser('add-brief', help='register an agreed brief for a client')
    brief.add_argument('--brief-ref', required=True)
    brief.add_argument('--client-ref', required=True)
    brief.add_argument('--brief-version', default='')
    brief.add_argument('--supplier-range', default='')
    brief.add_argument('--status', default='draft', choices=['draft', 'agreed', 'superseded'])
    brief.add_argument('--file', help='brief JSON to fingerprint (sha256 recorded)')
    srch = dbsub.add_parser('search', help='search clients, requests and deliveries')
    srch.add_argument('term')
    cl = dbsub.add_parser('client', help='show one client with requests, briefs and deliveries')
    cl.add_argument('client_ref')
    ret = dbsub.add_parser('retention-due', help='requests whose retention_review_at is today or earlier')
    ret.add_argument('--on', help='YYYY-MM-DD (default today)')
    dbsub.add_parser('summary', help='row counts and requests by status')
    return parser


def _emit(data, stream=None):
    (stream or sys.stdout).write(json.dumps(data, indent=2) + '\n')


def cmd_validate(args):
    spec = icp.load_icp(args.brief)
    _emit({'ok': True, 'brief': spec.as_dict(), 'plan': prospects.plan(spec)})
    return EXIT_OK


def cmd_prospects(args):
    spec = icp.load_icp(args.brief)
    the_plan = prospects.plan(spec, per_page=args.per_page)
    if not args.live and not args.fixture:
        _emit({'ok': True, 'dry_run': True, 'sent': False, 'plan': the_plan,
               'hint': 'add --fixture FILE to replay canned data, or --live --credit-budget N to call Apollo'})
        return EXIT_OK
    if args.live:
        if args.credit_budget < 1:
            _emit({'ok': False, 'error': '--live requires --credit-budget N (N >= 1); nothing was sent'}, sys.stderr)
            return EXIT_USAGE
        client = apollo.ApolloClient(live=True, credit_budget=args.credit_budget)
        data_mode = prospects.LIVE_MODE
        sys.stderr.write(f'live run: at most {args.credit_budget} credit(s) will be spent '
                         f'(at least {the_plan["min_credits"]} needed for {spec.requested_volume} companies)\n')
    else:
        transport = apollo.FixtureTransport.from_file(args.fixture)
        budget = args.credit_budget if args.credit_budget > 0 else apollo.MAX_PAGES  # replay costs nothing
        client = apollo.ApolloClient(live=False, transport=transport, credit_budget=budget)
        data_mode = prospects.FIXTURE_MODE
    result = prospects.collect(spec, client, per_page=args.per_page, data_mode=data_mode)
    csv_path, manifest_path = prospects.write_outputs(result, spec, args.out, data_mode=data_mode,
                                                      client=client, per_page=args.per_page)
    _emit({'ok': True, 'dry_run': False, 'data_mode': data_mode, 'candidates': len(result.records),
           'pages_fetched': result.pages_fetched, 'credits_used': client.credits_used,
           'stopped_reason': result.stopped_reason, 'csv': str(csv_path), 'manifest': str(manifest_path)})
    return EXIT_OK


def cmd_verify(args):
    rows, columns, email_column = verify.read_rows(args.input, args.email_column)
    the_plan = verify.plan(rows, email_column)
    the_plan['email_column'] = email_column
    if not args.live and not args.fixture:
        _emit({'ok': True, 'dry_run': True, 'sent': False, 'plan': the_plan,
               'hint': 'add --fixture FILE to replay canned results, or --live --credit-budget N to call ZeroBounce'})
        return EXIT_OK
    if args.live:
        if args.credit_budget < 1:
            _emit({'ok': False, 'error': '--live requires --credit-budget N (N >= 1); nothing was sent'}, sys.stderr)
            return EXIT_USAGE
        client = zerobounce.ZeroBounceClient(live=True, credit_budget=args.credit_budget, base_url=args.base_url)
        data_mode = verify.LIVE_MODE
        sys.stderr.write(f'live run against {client.base_url}: at most {args.credit_budget} credit(s) will be charged '
                         f'({the_plan["sendable"]} addresses to send; unknown results are not charged)\n')
    else:
        transport = zerobounce.FixtureTransport.from_file(args.fixture)
        budget = args.credit_budget if args.credit_budget > 0 else the_plan['sendable']
        client = zerobounce.ZeroBounceClient(live=False, transport=transport, credit_budget=budget, base_url=args.base_url)
        data_mode = verify.FIXTURE_MODE
    result = verify.verify_rows(rows, columns, email_column, client, batch_size=args.batch_size, data_mode=data_mode)
    csv_path, manifest_path = verify.write_outputs(result, args.input, args.out, data_mode=data_mode,
                                                   client=client, credit_budget=args.credit_budget)
    _emit({'ok': True, 'dry_run': False, 'data_mode': data_mode, 'rows': len(result.rows),
           'addresses_sent': result.sent, 'credits_charged': client.credits_used,
           'skipped_local_syntax': result.skipped_local_syntax, 'not_verified': result.not_verified,
           'stopped_reason': result.stopped_reason, 'csv': str(csv_path), 'manifest': str(manifest_path)})
    return EXIT_OK


def cmd_credits(args):
    if not args.live:
        _emit({'ok': False, 'error': 'credits needs --live; nothing was sent'}, sys.stderr)
        return EXIT_USAGE
    client = zerobounce.ZeroBounceClient(live=True, base_url=args.base_url)
    _emit({'ok': True, 'base_url': client.base_url, 'credits': client.get_credits()})
    return EXIT_OK


def cmd_export(args):
    result = export.build(
        args.input, client=args.client, brief_ref=args.brief_ref, dictionary_version=args.dictionary_version,
        export_version=args.export_version, export_id=args.export_id,
        decisions=tuple(args.include_decisions.split(',')),
        drop_columns=tuple(c.strip() for c in args.drop_columns.split(',') if c.strip()),
        keep_fiction_notice=args.keep_fiction_notice, dedupe_on=args.dedupe_on)
    folder, manifest = export.write_delivery(result, args.out, xlsx=args.xlsx)
    _emit({'ok': True, 'folder': str(folder), 'rows_delivered': manifest['rows_delivered'],
           'rows_read': result.rows_read, 'rows_excluded_by_decision': result.rows_excluded_by_decision,
           'duplicates_dropped': result.duplicates_dropped, 'files': sorted(manifest['files']),
           'delivery': manifest['delivery']})
    return EXIT_OK


def cmd_db(args):
    import datetime as _dt
    with clientdb.ClientDB(args.db) as db:
        if args.db_command == 'init':
            _emit({'ok': True, 'db': args.db, 'schema_version': db.init()})
            return EXIT_OK
        db.schema_version()  # fails clearly when not initialised
        if args.db_command == 'import-sheet':
            _emit({'ok': True, **db.import_sheet_export(args.csv)})
        elif args.db_command == 'record-delivery':
            _emit({'ok': True, **db.record_delivery(args.manifest)})
        elif args.db_command == 'mark-delivered':
            db.mark_delivered(args.client_ref, args.export_id, delivered_via=args.via)
            _emit({'ok': True, 'client_ref': args.client_ref, 'export_id': args.export_id, 'delivered_via': args.via})
        elif args.db_command == 'add-brief':
            db.add_brief(args.brief_ref, args.client_ref, brief_version=args.brief_version, supplier_range=args.supplier_range,
                         status=args.status, brief_path=args.file)
            _emit({'ok': True, 'brief_ref': args.brief_ref, 'client_ref': args.client_ref})
        elif args.db_command == 'search':
            _emit({'ok': True, **db.search(args.term)})
        elif args.db_command == 'client':
            _emit({'ok': True, **db.client(args.client_ref)})
        elif args.db_command == 'retention-due':
            on = _dt.date.fromisoformat(args.on) if args.on else None
            _emit({'ok': True, 'on': (on or _dt.date.today()).isoformat(), 'due': db.retention_due(on)})
        else:
            _emit({'ok': True, **db.summary()})
    return EXIT_OK


COMMANDS = {'validate': cmd_validate, 'prospects': cmd_prospects, 'verify': cmd_verify, 'credits': cmd_credits,
            'export': cmd_export, 'db': cmd_db}


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return COMMANDS[args.command](args)
    except icp.ICPError as error:
        _emit({'ok': False, 'error': 'brief rejected: ' + str(error)}, sys.stderr)
        return EXIT_USAGE
    except (verify.VerifyError, export.ExportError, clientdb.ClientDBError) as error:
        _emit({'ok': False, 'error': 'input rejected: ' + str(error)}, sys.stderr)
        return EXIT_USAGE
    except (apollo.ApolloError, zerobounce.ZeroBounceError) as error:
        _emit({'ok': False, 'error': type(error).__name__ + ': ' + str(error)}, sys.stderr)
        return EXIT_PROVIDER
