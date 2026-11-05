"""Served-data guard: fail if any file GitHub Pages would serve carries a real email address.

    python -B .github/ci/served_data_guard.py <site-root>

The site is public the moment main changes, so a prospect or client list committed by
mistake (a CSV, an XLSX, a JSON export, a page) would be published at demandrange.com.
This scans every served file and fails (exit 1) on any email address whose domain is not
on the allow-list: Demand Range's own domain plus the reserved example domains
(RFC 2606 / RFC 6761). It reports file paths and domains only, never the address.

Served = every file under the root except .git/ and .github/ (Pages does not publish
.github/). Text files are read as UTF-8 (errors replaced). XLSX/DOCX/ODS and other
zip-based files are scanned through their XML and text parts. PDFs and images are not
text-searchable here and are listed as unscanned so a reviewer can see them.

Read-only: it never writes to the tree. Standard library only.
"""
import re
import sys
import zipfile
from pathlib import Path

ALLOWED_DOMAINS = {'demandrange.com', 'example.com', 'example.net', 'example.org'}
ALLOWED_SUFFIXES = ('.example', '.invalid', '.test', '.localhost')
SKIP_DIRS = {'.git', '.github'}
ZIP_TYPES = {'.xlsx', '.xlsm', '.docx', '.pptx', '.ods', '.odt', '.zip'}
UNSCANNED_TYPES = {'.pdf', '.png', '.jpg', '.jpeg', '.gif', '.webp', '.ico', '.woff', '.woff2'}
ZIP_MEMBER_TYPES = ('.xml', '.rels', '.txt', '.csv', '.json')
EMAIL = re.compile(r'[A-Za-z0-9._%+-]+@([A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,})')


def allowed(domain):
    d = domain.lower().rstrip('.')
    return d in ALLOWED_DOMAINS or d.endswith(ALLOWED_SUFFIXES)


def domains_in(text):
    return {m.group(1).lower() for m in EMAIL.finditer(text)}


def served_files(root):
    for path in sorted(root.rglob('*')):
        rel = path.relative_to(root)
        if not path.is_file() or rel.parts[0] in SKIP_DIRS:
            continue
        yield rel, path


def file_domains(path):
    """Return (domains found, scanned?) for one file."""
    suffix = path.suffix.lower()
    if suffix in UNSCANNED_TYPES:
        return set(), False
    if suffix in ZIP_TYPES:
        found = set()
        try:
            with zipfile.ZipFile(path) as z:
                for name in z.namelist():
                    if name.lower().endswith(ZIP_MEMBER_TYPES):
                        found |= domains_in(z.read(name).decode('utf-8', 'replace'))
        except zipfile.BadZipFile:
            return set(), False
        return found, True
    return domains_in(path.read_bytes().decode('utf-8', 'replace')), True


def scan(root):
    root = Path(root)
    if not root.is_dir():
        raise SystemExit('served_data_guard: not a directory: ' + str(root))
    failures, unscanned, files = [], [], 0
    for rel, path in served_files(root):
        files += 1
        found, scanned = file_domains(path)
        if not scanned:
            unscanned.append(rel.as_posix())
            continue
        bad = sorted(d for d in found if not allowed(d))
        if bad:
            failures.append('%s: email address(es) at %s' % (rel.as_posix(), ', '.join(bad)))
    return files, failures, unscanned


def main(argv):
    if len(argv) != 2:
        raise SystemExit('usage: served_data_guard.py <site-root>')
    files, failures, unscanned = scan(argv[1])
    for line in failures:
        print('FAIL ' + line)
    if unscanned:
        print('note: %d served file(s) not text-scanned (PDF/images): %s'
              % (len(unscanned), ', '.join(unscanned[:10]) + (' ...' if len(unscanned) > 10 else '')))
    status = 'FAIL' if failures else 'PASS'
    print('served_data_guard %s: %d served files, %d failure(s)' % (status, files, len(failures)))
    return 1 if failures else 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
