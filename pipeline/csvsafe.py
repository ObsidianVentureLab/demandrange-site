"""Spreadsheet formula guard for CSV files that analysts or clients open in Excel/Sheets.

Provider-controlled text (company names, descriptions, keywords, URLs) can begin with =, +, -
or @, which a spreadsheet would run as a formula. `neutralise` prefixes such values with an
apostrophe so they display as text. Signed numbers and phone numbers (+353 1 555, -5) are left
untouched. Used by the candidate CSV (P2) and the client delivery CSV (P4).
"""
import re

FORMULA_PREFIXES = ('=', '+', '-', '@', '\t', '\r')
# "+353 1 555 0000", "-5", "+1 (212) 555-0100": sign followed only by digits and number punctuation.
NUMERIC_SIGNED = re.compile(r'^[+-][\d\s().\-]*\d[\d\s().\-]*$')
GUARD_NOTE = 'values beginning with =, @ or a non-numeric + or - carry a leading apostrophe so a spreadsheet shows them as text'


def neutralise(value):
    """Return `value` as text, prefixed with an apostrophe when a spreadsheet would run it as a formula."""
    text = '' if value is None else str(value)
    if text.startswith(FORMULA_PREFIXES) and not NUMERIC_SIGNED.match(text):
        return "'" + text
    return text
