"""Command line: `python -m pipeline <command>`.

    validate  --brief FILE                      check a brief and print the Apollo filters
    prospects --brief FILE --out DIR [--fixture FILE | --live --credit-budget N]

Default is a dry run: the plan (filters, max pages, max credits) is printed and nothing is
sent. --fixture replays a canned response file offline. --live needs the API key in the
APOLLO_API_KEY environment variable and an explicit --credit-budget; the budget defaults to
0, so a live run without a budget stops before the first request.
"""
import argparse
import json
import sys

from . import apollo, icp, prospects

EXIT_OK, EXIT_USAGE, EXIT_APOLLO = 0, 2, 3


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


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        if args.command == 'validate':
            return cmd_validate(args)
        return cmd_prospects(args)
    except icp.ICPError as error:
        _emit({'ok': False, 'error': 'brief rejected: ' + str(error)}, sys.stderr)
        return EXIT_USAGE
    except apollo.ApolloError as error:
        _emit({'ok': False, 'error': type(error).__name__ + ': ' + str(error)}, sys.stderr)
        return EXIT_APOLLO
    except OSError as error:   # unreadable input or unwritable --out path (provider I/O is wrapped above)
        _emit({'ok': False, 'error': 'file error: ' + str(error)}, sys.stderr)
        return EXIT_USAGE
