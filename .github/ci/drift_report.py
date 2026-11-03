"""Drift report: compare a tree built from this source with a reference tree (normally `main`).

    python3 .github/ci/drift_report.py --built <dir> --reference <dir> \
        [--markdown out.md] [--json out.json] [--ignore .git,.github] [--fail-on-drift]

Read-only, stdlib only. Lists files only in one tree, files whose bytes differ (with a
line-level +/- count for text files), and identical files. Exit 0 unless --fail-on-drift is
given and any drift exists. The report is evidence for the consolidation decision; it does
not change either tree.
"""
import argparse
import difflib
import json
import sys
from pathlib import Path

TEXT_SUFFIXES = {'.html', '.css', '.js', '.txt', '.xml', '.json', '.csv', '.svg', '.md', ''}
MAX_TEXT_BYTES = 2_000_000


def files_under(root, ignore):
    root = Path(root).resolve()
    if not root.is_dir():
        raise SystemExit(f'drift_report: not a directory: {root}')
    out = {}
    for p in root.rglob('*'):
        if not p.is_file():
            continue
        rel = p.relative_to(root).as_posix()
        if rel.split('/')[0] in ignore:
            continue
        out[rel] = p
    return out


def line_delta(a, b):
    try:
        ta = a.read_text(encoding='utf-8').splitlines()
        tb = b.read_text(encoding='utf-8').splitlines()
    except UnicodeDecodeError:
        return None
    added = removed = 0
    for line in difflib.unified_diff(ta, tb, lineterm='', n=0):
        if line.startswith('+') and not line.startswith('+++'):
            added += 1
        elif line.startswith('-') and not line.startswith('---'):
            removed += 1
    return {'added': added, 'removed': removed}


def compare(built, reference, ignore=('.git', '.github')):
    b, r = files_under(built, set(ignore)), files_under(reference, set(ignore))
    only_built = sorted(set(b) - set(r))
    only_reference = sorted(set(r) - set(b))
    identical, differing = [], []
    for rel in sorted(set(b) & set(r)):
        pb, pr = b[rel], r[rel]
        if pb.read_bytes() == pr.read_bytes():
            identical.append(rel)
            continue
        entry = {'file': rel, 'built_bytes': pb.stat().st_size, 'reference_bytes': pr.stat().st_size}
        if Path(rel).suffix.lower() in TEXT_SUFFIXES and max(entry['built_bytes'], entry['reference_bytes']) <= MAX_TEXT_BYTES:
            entry['lines'] = line_delta(pb, pr)
        differing.append(entry)
    return {
        'built': str(Path(built).resolve()), 'reference': str(Path(reference).resolve()),
        'ignored_top_level': sorted(ignore),
        'counts': {'identical': len(identical), 'differing': len(differing),
                   'only_built': len(only_built), 'only_reference': len(only_reference)},
        'has_drift': bool(differing or only_built or only_reference),
        'only_built': only_built, 'only_reference': only_reference,
        'differing': differing, 'identical': identical,
    }


def markdown(report):
    c = report['counts']
    lines = ['## Drift: source build vs reference', '',
             f"Built: `{report['built']}`  ", f"Reference: `{report['reference']}`  ",
             f"Ignored top-level entries: {', '.join('`'+i+'`' for i in report['ignored_top_level']) or 'none'}", '',
             '| Identical | Differing | Only in build | Only in reference |', '|---:|---:|---:|---:|',
             f"| {c['identical']} | {c['differing']} | {c['only_built']} | {c['only_reference']} |", '']
    if not report['has_drift']:
        lines += ['**No drift.** The build reproduces the reference byte for byte.', '']
        return '\n'.join(lines)
    if report['differing']:
        lines += ['### Differing files', '', '| File | Build bytes | Reference bytes | Lines +/- |', '|---|---:|---:|---|']
        for d in report['differing']:
            delta = d.get('lines')
            text = f"+{delta['added']} / -{delta['removed']}" if delta else 'binary'
            lines.append(f"| `{d['file']}` | {d['built_bytes']} | {d['reference_bytes']} | {text} |")
        lines.append('')
    if report['only_reference']:
        lines += ['### Only in reference (missing from the build)', ''] + [f'- `{f}`' for f in report['only_reference']] + ['']
    if report['only_built']:
        lines += ['### Only in build (not in reference)', ''] + [f'- `{f}`' for f in report['only_built']] + ['']
    return '\n'.join(lines)


def main(argv):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--built', required=True)
    parser.add_argument('--reference', required=True)
    parser.add_argument('--markdown')
    parser.add_argument('--json')
    parser.add_argument('--ignore', default='.git,.github', help='comma-separated top-level names to ignore')
    parser.add_argument('--fail-on-drift', action='store_true')
    args = parser.parse_args(argv[1:])
    ignore = tuple(i for i in args.ignore.split(',') if i)
    report = compare(args.built, args.reference, ignore)
    md = markdown(report)
    if args.markdown:
        Path(args.markdown).write_text(md + '\n', encoding='utf-8')
    if args.json:
        Path(args.json).write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    c = report['counts']
    print(f"drift_report: identical={c['identical']} differing={c['differing']} only_built={c['only_built']} "
          f"only_reference={c['only_reference']} drift={'yes' if report['has_drift'] else 'no'}")
    return 1 if (args.fail_on_drift and report['has_drift']) else 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
