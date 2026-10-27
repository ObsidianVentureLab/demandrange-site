#!/usr/bin/env python3
"""Validate raw clean output against a freshly rendered, fully legacy-validated tree.

The existing qa_static.py and production_contract.py remain untouched. This
entrypoint runs BOTH the complete original suite and the strict raw clean checks;
it never sends a normalized arbitrary candidate to the old validators.
"""
from pathlib import Path
import argparse
import json
import os
import subprocess
import sys
import tempfile
from build_site import render_tree, source_inventory
from production_contract import load_contract, preflight_source, validate_output, require
from clean_urls import validate_delta


def verify(root, endpoint, mode='production'):
    here = Path(__file__).resolve().parent
    frozen = source_inventory()
    contract = load_contract(mode, endpoint)
    require(mode == 'production', 'Clean URL verification currently requires full production inventory')
    preflight_source(contract)
    with tempfile.TemporaryDirectory(prefix='.clean-url-baseline-', dir=Path(root).absolute().parent) as tmp:
        baseline = Path(tmp) / 'public'
        baseline.mkdir()
        render_tree(baseline, endpoint, contract)
        validate_output(baseline, contract, mode, endpoint)
        result = subprocess.run([sys.executable, '-B', str(here / 'qa_static.py'), '--root', str(baseline),
                                 '--mode', mode, '--quote-endpoint', endpoint], text=True, capture_output=True,
                                timeout=120, env={**os.environ, 'PYTHONDONTWRITEBYTECODE': '1'})
        require(result.returncode == 0, 'Original static QA failed:\n' + result.stdout + result.stderr)
        report = validate_delta(Path(root), baseline, contract)
        require(source_inventory() == frozen, 'Source changed during clean QA')
        report['original_static_qa'] = result.stdout.strip()
        report['release_authorised'] = False
        return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--quote-endpoint', required=True)
    args = parser.parse_args()
    try:
        print(json.dumps(verify(args.root, args.quote_endpoint), indent=2))
    except (ValueError, OSError) as error:
        parser.exit(1, f'FAIL: {error}\n')
