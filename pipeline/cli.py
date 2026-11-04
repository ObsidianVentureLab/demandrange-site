"""Command line: `python -m pipeline <command>`.

    validate  --brief FILE                      check a brief and print the Apollo filters
    prospects --brief FILE --out DIR [--fixture FILE | --live --credit-budget N]
    verify    --input CSV  --out DIR [--email-column NAME] [--fixture FILE | --live --credit-budget N]
    credits   --live                            ZeroBounce credit balance (not charged)
    export    --input CSV [CSV...] --client NAME --brief-ref R --dictionary-version D --export-version E --out DIR [--xlsx]

Default is a dry run: the plan (filters/addresses, max credits) is printed and nothing is sent.
--fixture replays a canned response file offline. --live needs the provider key in the
environment (APOLLO_API_KEY / ZEROBOUNCE_API_KEY) and an explicit --credit-budget; the budget
defaults to 0, so a live run without a budget stops before the first request.
"""
import argparse
import json
import sys

from . import apollo, export, icp, pathguard, prospects, verify, zerobounce

EXIT_OK, EXIT_USAGE, EXIT_PROVIDER = 0, 2, 3   # 3 = any provider (Apollo, ZeroBounce) error


def _per_page(text):
    """argparse type for --per-page: one check (prospects.check_per_page) shared with the library, so the
    plan, every request and the manifest all carry the same number (rejected rather than silently clamped)."""
    try:
        return prospects.check_per_page(text)
    except apollo.ApolloError as error:
        raise argparse.ArgumentTypeError(str(error))


def build_parser():
    parser = argparse.ArgumentParser(prog='python -m pipeline', description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest='command', required=True)

    validate = sub.add_parser('validate', help='validate an ICP brief and print the Apollo filters')
    validate.add_argument('--brief', required=True, help='ICP brief JSON file')

    run = sub.add_parser('prospects', help='build a candidate company list from a brief')
    run.add_argument('--brief', required=True, help='ICP brief JSON file')
    run.add_argument('--out', required=True, help='output directory for the CSV and manifest')
    run.add_argument('--per-page', type=_per_page, default=apollo.MAX_PER_PAGE,
                     help=f'results per page (1-{apollo.MAX_PER_PAGE}); out-of-range values are rejected')
    mode = run.add_mutually_exclusive_group()
    mode.add_argument('--fixture', help='replay this canned response file instead of calling Apollo')
    mode.add_argument('--live', action='store_true',
                      help=f'call Apollo for real (key from ${apollo.API_KEY_ENV}; requires --credit-budget)')
    run.add_argument('--credit-budget', type=int, default=0,
                     help='maximum Apollo credits (pages) this run may spend; default 0 = none. With --fixture, '
                          f'0 means no page cap (replay costs nothing; at most {apollo.MAX_PAGES} pages)')

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
    exp.add_argument('--dedupe-on', help='one row per value of this column (case-insensitive); the row with the best verification_decision is kept')
    exp.add_argument('--keep-fiction-notice', action='store_true', help='keep a fiction_notice column (fixtures only)')
    exp.add_argument('--xlsx', action='store_true', help='also write an .xlsx workbook (all cells text)')
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
        sys.stderr.write(f'live run against {client.base_url}: at most {args.credit_budget} credit(s) can be charged, '
                         f'retries included (hard cap; {the_plan["sendable"]} addresses to send; unknown results are not charged)\n')
    else:
        transport = zerobounce.FixtureTransport.from_file(args.fixture)
        budget = args.credit_budget if args.credit_budget > 0 else the_plan['sendable']
        client = zerobounce.ZeroBounceClient(live=False, transport=transport, credit_budget=budget, base_url=args.base_url)
        data_mode = verify.FIXTURE_MODE
    result = verify.verify_rows(rows, columns, email_column, client, batch_size=args.batch_size, data_mode=data_mode)
    # client.credit_budget is the budget actually enforced (fixture mode defaults it to the sendable count
    # when --credit-budget is 0), so the manifest never records 0 for a run that verified addresses.
    csv_path, manifest_path = verify.write_outputs(result, args.input, args.out, data_mode=data_mode,
                                                   client=client, credit_budget=client.credit_budget)
    report = {'ok': not result.provider_error, 'dry_run': False, 'data_mode': data_mode, 'rows': len(result.rows),
              'addresses_sent': result.sent, 'credits_charged': client.credits_used, 'credits_reserved': client.credits_reserved,
              'credits_at_risk': client.credits_at_risk,
              'skipped_local_syntax': result.skipped_local_syntax, 'not_verified': result.not_verified,
              'stopped_reason': result.stopped_reason, 'csv': str(csv_path), 'manifest': str(manifest_path)}
    if result.provider_error:
        # The files above hold every row (verified ones kept, the rest marked provider_error); exit 3 so a
        # script notices, with the paths in the report rather than lost in a traceback.
        report['error'] = result.provider_error
        _emit(report)
        return EXIT_PROVIDER
    _emit(report)
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


COMMANDS = {'validate': cmd_validate, 'prospects': cmd_prospects, 'verify': cmd_verify, 'credits': cmd_credits, 'export': cmd_export}


# Data paths every sub-command may take. Inputs may name the fictional fixtures under pipeline/examples/;
# outputs never point inside the checkout (see pathguard). Later sub-commands add their names here.
INPUT_PATH_ARGS = ('brief', 'fixture', 'input', 'file', 'csv', 'manifest')
OUTPUT_PATH_ARGS = ('out', 'db')


def guard_paths(args):
    """Refuse data paths inside the repository before anything is read or written."""
    for name in INPUT_PATH_ARGS + OUTPUT_PATH_ARGS:
        value = getattr(args, name, None)
        for item in (value if isinstance(value, (list, tuple)) else [value]):   # export --input takes several
            if isinstance(item, str) and item:
                pathguard.refuse_inside_repo(item, '--' + name.replace('_', '-'), allow_examples=name in INPUT_PATH_ARGS)


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        guard_paths(args)
        return COMMANDS[args.command](args)
    except pathguard.InsideRepoError as error:
        _emit({'ok': False, 'error': 'path refused: ' + str(error)}, sys.stderr)
        return EXIT_USAGE
    except icp.ICPError as error:
        _emit({'ok': False, 'error': 'brief rejected: ' + str(error)}, sys.stderr)
        return EXIT_USAGE
    except (verify.VerifyError, export.ExportError) as error:
        _emit({'ok': False, 'error': 'input rejected: ' + str(error)}, sys.stderr)
        return EXIT_USAGE
    except (apollo.ApolloError, zerobounce.ZeroBounceError) as error:
        _emit({'ok': False, 'error': type(error).__name__ + ': ' + str(error)}, sys.stderr)
        return EXIT_PROVIDER
    except OSError as error:   # unreadable input or unwritable --out path (provider I/O is wrapped above)
        _emit({'ok': False, 'error': 'file error: ' + str(error)}, sys.stderr)
        return EXIT_USAGE
