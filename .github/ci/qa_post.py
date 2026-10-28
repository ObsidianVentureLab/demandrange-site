"""Post-build QA (F15): run against a finished build directory before shipping.

    python -B qa_post.py <build-dir>

Read-only: it never writes to the build or to the source tree, and it is not part
of the published output. It fails (exit 1) if
  * any built HTML page contains the marker text 'F15-REVIEW-LINE', or
  * any built HTML page has a [data-f15] element at all (strict: the count must be 0).
The template byline (content_review_stage) is the only review line a page should
carry and it has no data-f15 attribute, so any [data-f15] element in the output is
a hand-written F15 review line left in a source fragment.
"""
import sys
from pathlib import Path
from bs4 import BeautifulSoup

MARKER = 'F15-REVIEW-LINE'


def scan(build):
    build = Path(build)
    pages = sorted(p for p in build.rglob('*.html') if p.is_file())
    if not pages:
        raise SystemExit('qa_post: no HTML pages under ' + str(build))
    failures, marker_hits, data_f15 = [], 0, 0
    for page in pages:
        rel = page.relative_to(build).as_posix()
        text = page.read_text(encoding='utf-8')
        hits = text.count(MARKER)
        if hits:
            marker_hits += hits
            failures.append(f'{rel}: contains {MARKER!r} ({hits}x)')
        count = len(BeautifulSoup(text, 'html.parser').select('[data-f15]'))
        data_f15 += count
        if count:
            failures.append(f'{rel}: {count} [data-f15] element(s) (must be 0)')
    return pages, failures, marker_hits, data_f15


def main(argv):
    if len(argv) != 2:
        raise SystemExit('usage: python -B qa_post.py <build-dir>')
    pages, failures, marker_hits, data_f15 = scan(argv[1])
    for line in failures:
        print('FAIL:', line)
    status = 'FAIL' if failures else 'PASS'
    print(f'qa_post {status}: {len(pages)} HTML pages; {MARKER} hits {marker_hits}; '
          f'[data-f15] elements {data_f15} total (must be 0); pages with any: '
          f'{sum(1 for f in failures if "[data-f15]" in f)}')
    return 1 if failures else 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
