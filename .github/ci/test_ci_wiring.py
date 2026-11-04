"""Static tests that the secret scan stays pinned and wired into the blocking site-checks job.

    python3 -B .github/ci/test_ci_wiring.py

Stdlib only; reads files, runs nothing. Guards against the gitleaks step being dropped, made
non-blocking, or switched to an unpinned/unverified download (launch checklist S4).
"""
import re
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
SCRIPT = (HERE / 'gitleaks.sh').read_text(encoding='utf-8')
WORKFLOW = (REPO / '.github' / 'workflows' / 'site-checks.yml').read_text(encoding='utf-8')


class GitleaksScript(unittest.TestCase):
    def test_version_and_checksum_pinned(self):
        self.assertRegex(SCRIPT, r'(?m)^GITLEAKS_VERSION="\d+\.\d+\.\d+"$')
        self.assertRegex(SCRIPT, r'(?m)^GITLEAKS_SHA256="[0-9a-f]{64}"')

    def test_checksum_verified_before_use(self):
        check = SCRIPT.index('sha256sum -c')
        self.assertLess(SCRIPT.index('curl '), check)
        self.assertLess(check, SCRIPT.index('tar -xzf'))

    def test_strict_and_failing(self):
        self.assertIn('set -euo pipefail', SCRIPT)
        self.assertIn('--exit-code 1', SCRIPT)
        self.assertIn('--redact', SCRIPT)

    def test_download_only_from_github_releases(self):
        urls = re.findall(r'https://[^\s"]+', SCRIPT)
        self.assertTrue(urls)
        for u in urls:
            self.assertTrue(u.startswith('https://github.com/gitleaks/gitleaks/releases/download/'), u)


class Workflow(unittest.TestCase):
    def test_scan_step_present_and_blocking(self):
        self.assertIn('run: bash .github/ci/gitleaks.sh .', WORKFLOW)
        self.assertNotIn('continue-on-error', WORKFLOW)

    def test_full_history_checkout(self):
        self.assertRegex(WORKFLOW, r'fetch-depth:\s*0')

    def test_runs_on_prs_and_pushes_to_main(self):
        self.assertRegex(WORKFLOW, r'pull_request:\s*\n\s*branches:\s*\[main\]')
        self.assertRegex(WORKFLOW, r'push:\s*\n\s*branches:\s*\[main\]')

    def test_no_secrets_used(self):
        self.assertNotIn('secrets.', WORKFLOW)


if __name__ == '__main__':
    unittest.main(verbosity=2)
