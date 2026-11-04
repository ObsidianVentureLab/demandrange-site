"""Served-bundle guard: fail if anything that must never be public would be served by GitHub Pages.

    python3 -B .github/ci/served_guard.py [ROOT]

GitHub Pages serves this repository's `main` as-is (with .nojekyll), minus `.git` and `.github`.
site_checks.py check 6 already rejects tooling extensions (.py/.yml/.md/.sh/.ipynb) and stray
dot-directories. This guard adds the rest of the "never publish" list (build brief item 3.6,
launch-checklist S5), so a mistaken retarget or merge of a tooling/pipeline branch fails CI:

  1. Allow-list of served file types: anything outside SERVED_EXT (plus the two bare files
     CNAME and .nojekyll) fails, so a new kind of file needs a deliberate change here.
  2. Forbidden paths: the generator / pipeline / quote-form source trees and CLI output folders
     (pipeline/, quote-form/, foundation/, out/, deliveries/, ...) at any depth.
  3. Forbidden names: Apps Script sources and manifests (*.gs, appsscript.json, .clasp.json),
     the quote-form schema, env/key material, SQLite/DB files and their -wal/-shm/-journal
     sidecars, Python caches, internal docs (CONSOLIDATION.md etc.).
  4. Content sniff: any file that starts with the SQLite header, whatever its name.

Stdlib only, read-only. Exit 0 = clean, 1 = violations (listed), 2 = bad root.
"""
import re
import sys
from pathlib import Path

EXCLUDED_TOP = {'.git', '.github'}  # not part of the Pages deployment
BARE_ALLOWED = {'CNAME', '.nojekyll'}  # top-level only
SERVED_EXT = {
    '.html', '.css', '.js', '.json', '.txt', '.xml', '.csv', '.pdf', '.xlsx',
    '.svg', '.png', '.jpg', '.jpeg', '.webp', '.gif', '.ico', '.avif',
    '.woff', '.woff2', '.webmanifest',
}
FORBIDDEN_DIRS = {
    'pipeline', 'quote-form', 'apps-script', 'foundation', 'out', 'deliveries', 'exports',
    'node_modules', '__pycache__', 'tests', 'scripts', 'adr',
}
FORBIDDEN_NAMES = {
    'appsscript.json', '.clasp.json', '.clasprc.json', 'form_schema.json',
    'consolidation.md', 'implementation_notes.md', 'deployment.md', 'redeploy.md',
    'production-manifest.json', 'articles.json',
}
FORBIDDEN_NAME_RE = re.compile(
    r'''(
        \.gs$ | \.py[cod]?$ | \.sqlite3?$ | \.db3?$ | \.sqlite3?-(wal|shm|journal)$ | \.db-(wal|shm|journal)$
      | \.(pem|key|p12|pfx|crt|der|kdbx|ovpn)$ | ^\.env(\..*)?$ | \.env$ | ^id_(rsa|dsa|ecdsa|ed25519)
      | \.(bak|orig|rej|swp|log|tmp)$ | ~$
    )''', re.X | re.I)
SQLITE_MAGIC = b'SQLite format 3\x00'


def served_files(root):
    """Every regular file Pages would serve, as POSIX paths relative to root."""
    out = []
    for p in sorted(root.rglob('*')):
        rel = p.relative_to(root)
        if rel.parts[0] in EXCLUDED_TOP:
            continue
        if p.is_symlink():
            out.append(rel.as_posix())  # reported below: Pages would follow/serve it
            continue
        if p.is_file():
            out.append(rel.as_posix())
    return out


def problems(root):
    root = Path(root)
    found = []
    for rel in served_files(root):
        path = root / rel
        parts = rel.split('/')
        name = parts[-1]
        why = []
        if path.is_symlink():
            why.append('symlink in served tree')
        bad_dirs = [d for d in parts[:-1] if d.lower() in FORBIDDEN_DIRS]
        if bad_dirs:
            why.append(f'inside forbidden directory {bad_dirs[0]}/')
        if name.lower() in FORBIDDEN_NAMES:
            why.append('forbidden file name')
        if FORBIDDEN_NAME_RE.search(name):
            why.append('forbidden file type')
        suffix = Path(name).suffix.lower() if not name.startswith('.') or name.count('.') > 1 else ''
        if not (len(parts) == 1 and name in BARE_ALLOWED) and not rel.startswith('.well-known/') \
                and suffix not in SERVED_EXT:
            why.append(f'file type {suffix or "(none)"} is not on the served allow-list')
        if not path.is_symlink():
            try:
                with open(path, 'rb') as fh:
                    if fh.read(len(SQLITE_MAGIC)) == SQLITE_MAGIC:
                        why.append('SQLite database content')
            except OSError as e:
                why.append(f'unreadable ({e.strerror})')
        if why:
            found.append(f'{rel}: ' + '; '.join(why))
    return found


def main(argv):
    root = Path(argv[1] if len(argv) > 1 else '.').resolve()
    if not (root / 'index.html').is_file():
        print(f'served_guard: no index.html under {root}', file=sys.stderr)
        return 2
    found = problems(root)
    for line in found:
        print(f'FAIL {line}')
    n = len(served_files(root))
    if found:
        print(f'served_guard: {len(found)} file(s) must not be publicly served (of {n})')
        return 1
    print(f'served_guard: PASS ({n} served files checked)')
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
