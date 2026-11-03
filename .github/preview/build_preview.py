"""Build a preview copy of the served site tree.

    python3 .github/preview/build_preview.py --source . --output _site [--allow-index]

This repository holds the built site; GitHub Pages serves `main` as-is. A preview is the
same tree with three differences so it can never be mistaken for, or indexed as, the live
site:
  * `.git`, `.github` and `CNAME` are left out (a CNAME in a preview would try to claim
    demandrange.com on any GitHub Pages host);
  * `robots.txt` disallows everything (the Sitemap line is kept so site_checks still passes)
    and a Cloudflare/Netlify-style `_headers` file adds `X-Robots-Tag: noindex` — unless
    `--allow-index` is passed;
  * `_preview.json` records the source commit and build time.
Stdlib only, read-only on the source tree. Exit 1 on any problem.
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

EXCLUDED_TOP = {'.git', '.github', 'CNAME'}
SITEMAP_LINE = 'Sitemap: https://demandrange.com/sitemap.xml'
ROBOTS_NOINDEX = 'User-agent: *\nDisallow: /\n\n' + SITEMAP_LINE + '\n'
HEADERS_NOINDEX = '/*\n  X-Robots-Tag: noindex, nofollow, noarchive\n'


def git_sha(source):
    try:
        out = subprocess.run(['git', '-C', str(source), 'rev-parse', 'HEAD'], check=True,
                             capture_output=True, text=True, timeout=20).stdout.strip()
        return out if len(out) == 40 else None
    except (OSError, subprocess.SubprocessError):
        return None


def build(source, output, noindex=True):
    source, output = Path(source).resolve(), Path(output).resolve()
    if not (source / 'index.html').is_file():
        raise SystemExit(f'build_preview: no index.html under {source}')
    if output == source or source in output.parents:
        raise SystemExit('build_preview: output must not be inside the source tree')
    if output.exists():
        if not (output / '_preview.json').is_file():
            raise SystemExit(f'build_preview: refusing to overwrite {output}: not a previous preview build')
        shutil.rmtree(output)
    output.mkdir(parents=True)
    copied = 0
    for entry in sorted(source.iterdir()):
        if entry.name in EXCLUDED_TOP or entry.is_symlink():
            continue
        if entry.is_dir():
            shutil.copytree(entry, output / entry.name, symlinks=False)
            copied += sum(1 for p in (output / entry.name).rglob('*') if p.is_file())
        else:
            shutil.copy2(entry, output / entry.name)
            copied += 1
    if noindex:
        (output / 'robots.txt').write_text(ROBOTS_NOINDEX, encoding='utf-8')
        (output / '_headers').write_text(HEADERS_NOINDEX, encoding='utf-8')
    stamp = {
        'preview': True,
        'noindex': noindex,
        'source_commit': os.environ.get('GITHUB_SHA') or git_sha(source),
        'pull_request': os.environ.get('PR_NUMBER') or None,
        'built_at_utc': datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        'files': copied,
        'note': 'Preview build. Not the live site. Not for indexing or sharing outside review.',
    }
    (output / '_preview.json').write_text(json.dumps(stamp, indent=2) + '\n', encoding='utf-8')
    return stamp


def main(argv):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--source', default='.')
    parser.add_argument('--output', required=True)
    parser.add_argument('--allow-index', action='store_true', help='keep the live robots.txt; no noindex header')
    args = parser.parse_args(argv[1:])
    stamp = build(args.source, args.output, noindex=not args.allow_index)
    print(json.dumps(stamp))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
