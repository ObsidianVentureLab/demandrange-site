"""CI guard: no real prospect/verification/delivery/client data may be committed (lead's #59-#62 item).

This repository is public, and anything that reaches main is served at demandrange.com. Until the pipeline
moves to a private repository, this check runs on every pipeline push. It fails when a TRACKED file
  - sits under out/, pipeline/out/ or a deliveries/ folder (CLI output locations), or
  - is a database file (*.sqlite, *.sqlite3, *.db and their -wal/-shm/-journal sidecars), or
  - is a data file (.csv .tsv .xlsx .xls .json .jsonl .sqlite ...) under pipeline/ outside pipeline/examples/, or
  - is a pipeline/examples/ fixture containing an email address whose domain is not reserved for
    documentation (RFC 2606/6761: .example, .invalid, .test, .localhost, example.com/.net/.org).
.gitignore and the CLI's in-repo path refusal are the first two lines of defence; this is the third.
Usage: python -B .github/ci/data_guard.py [repo_root]   (exit 1 lists every offending path)
"""
import re
import subprocess
import sys
from pathlib import PurePosixPath

DB_SUFFIXES = ('.sqlite', '.sqlite3', '.db')
SIDECARS = ('', '-wal', '-shm', '-journal')
DATA_SUFFIXES = {'.csv', '.tsv', '.xlsx', '.xls', '.json', '.jsonl', '.ndjson', '.parquet', '.sqlite', '.sqlite3', '.db'}
EMAIL = re.compile(r'[A-Za-z0-9._%+-]+@([A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*)')
RESERVED_TLDS = ('example', 'invalid', 'test', 'localhost')
RESERVED_DOMAINS = ('example.com', 'example.net', 'example.org')


def reserved(domain):
    d = domain.lower().rstrip('.')
    return d.rsplit('.', 1)[-1] in RESERVED_TLDS or any(d == r or d.endswith('.' + r) for r in RESERVED_DOMAINS)


def path_problem(path):
    p = PurePosixPath(path)
    parts = p.parts
    name = p.name.lower()
    if parts[:1] == ('out',) or parts[:2] == ('pipeline', 'out') or 'deliveries' in parts[:-1]:
        return 'CLI output folder'
    if any(name.endswith(s + c) for s in DB_SUFFIXES for c in SIDECARS):
        return 'database file'
    if parts[:1] == ('pipeline',) and parts[:2] != ('pipeline', 'examples') and p.suffix.lower() in DATA_SUFFIXES:
        return 'data file outside pipeline/examples/'
    return None


def fixture_problem(path, text):
    if not path.startswith('pipeline/examples/'):
        return None
    bad = sorted({m.group(1) for m in EMAIL.finditer(text) if not reserved(m.group(1))})
    return ('non-reserved email domain(s): ' + ', '.join(bad)) if bad else None


def check(files, read):
    problems = []
    for path in files:
        why = path_problem(path)
        if why is None:
            try:
                why = fixture_problem(path, read(path))
            except UnicodeDecodeError:
                why = 'binary file in pipeline/examples/' if path.startswith('pipeline/examples/') else None
        if why:
            problems.append(f'{path}: {why}')
    return problems


def main(root='.'):
    files = subprocess.run(['git', '-C', root, 'ls-files', '-z'], check=True, capture_output=True).stdout.decode('utf-8').split('\0')
    files = [f for f in files if f]
    problems = check(files, lambda p: open(f'{root}/{p}', encoding='utf-8').read())
    for line in problems:
        print('FAIL: ' + line)
    print(f'data_guard {"FAIL" if problems else "PASS"}: {len(files)} tracked files, {len(problems)} problem(s)')
    return 1 if problems else 0


if __name__ == '__main__':
    sys.exit(main(*sys.argv[1:2]))
