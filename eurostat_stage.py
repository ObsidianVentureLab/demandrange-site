"""Eurostat data page extension: a static table generated from the pinned CSV.

The page itself is a researched article (eu-industrial-enterprises-by-country.md,
record "extension": "eurostat"); this module supplies the sections that follow
its prose (country/sector index, the full 868-row table and the citation block)
and the table CSS. The article record copies the CSV byte-for-byte; the table
only formats the published values (thousands separators, a typographic minus)
and never computes, imputes or rounds. No script is added: the country and
sector indexes are plain links.
"""
import csv
import re
from html import escape
from bs4 import BeautifulSoup
from foundation_stage import CONTENT

ROUTE = 'eu-industrial-enterprises-by-country.html'
ASSET = 'eu-industrial-enterprises-by-country-nace-2023.csv'
SLOT = '<div id="eurostat-table-slot"></div>'
COLUMNS = [  # (CSV column, table header, short flag label)
    ('enterprises_total', 'Enterprises, total', 'Total'),
    ('enterprises_10_19_persons', '10–19', '10–19'),
    ('enterprises_20_49_persons', '20–49', '20–49'),
    ('enterprises_50_249_persons', '50–249', '50–249'),
    ('enterprises_250plus_persons', '250+', '250+'),
    ('persons_employed', 'Persons employed', 'Persons employed'),
    ('net_turnover_eur_million', 'Net turnover (EUR m)', 'Turnover'),
    ('gross_investment_machinery_equipment_eur_million', 'Machinery and equipment investment (EUR m)', 'Investment'),
]
HEADER = ['country_code', 'country', 'nace_r2_code', 'nace_r2_activity', 'reference_year',
          *[c for c, _, _ in COLUMNS], 'eurostat_flags']
EU = 'EU27_2020'
# The only negative value in the file; footnoted as published (brief, 27 Oct 2026).
FOOTNOTES = {('FI', 'B', 'gross_investment_machinery_equipment_eur_million'): ('-12.43', 'fn-fi-b-investment')}
NUMBER = re.compile(r'-?[0-9]+(?:\.[0-9]+)?')


def display(value):
    if value == '':
        return ''
    if not NUMBER.fullmatch(value):
        raise ValueError('Eurostat stage: non-numeric value ' + value)
    whole, _, frac = value.lstrip('-').partition('.')
    return ('−' if value.startswith('-') else '') + f'{int(whole):,}' + ('.' + frac if frac else '')


def slug(code):
    return 'eu27' if code == EU else code.lower()


def flags(text):
    if not text:
        return ''
    labels = {c: short for c, _, short in COLUMNS}
    out = []
    for item in text.split('; '):
        column, _, flag = item.partition('=')
        if column not in labels or flag not in {'C', 'e'}:
            raise ValueError('Eurostat stage: unexpected flag ' + item)
        out.append(labels[column] + ': ' + flag)
    return '; '.join(out)


def load_rows():
    with (CONTENT / ASSET).open(encoding='utf-8', newline='') as handle:
        reader = csv.reader(handle)
        header = next(reader)
        if header != HEADER:
            raise ValueError('Eurostat stage: CSV header drift')
        rows = [dict(zip(header, r)) for r in reader]
    if len(rows) != 868 or {r['reference_year'] for r in rows} != {'2023'}:
        raise ValueError('Eurostat stage: CSV row/year drift')
    return rows


def table_html(rows):
    geos = list(dict.fromkeys(r['country_code'] for r in rows))
    geos = [EU] + [g for g in geos if g != EU]  # EU-27 aggregate first, then Eurostat protocol order
    names = {r['country_code']: ('EU-27 aggregate' if r['country_code'] == EU else r['country']) for r in rows}
    sectors = list(dict.fromkeys((r['nace_r2_code'], r['nace_r2_activity']) for r in rows))
    by_geo = {g: [r for r in rows if r['country_code'] == g] for g in geos}
    if any([(r['nace_r2_code'], r['nace_r2_activity']) for r in by_geo[g]] != sectors for g in geos):
        raise ValueError('Eurostat stage: every geography must list the same activities in order')
    used = set()
    out = ['<h3 id="country-index">Jump to a country</h3><ul class="eurostat-index">']
    out += ['<li><a href="#country-' + slug(g) + '">' + escape(names[g]) + '</a></li>' for g in geos]
    out += ['</ul><h3 id="sector-index">Jump to a sector (EU-27 rows)</h3><ul class="eurostat-index">']
    out += ['<li><a href="#eu27-' + code.lower() + '">' + escape(code) + ' ' + escape(label) + '</a></li>' for code, label in sectors]
    out.append('</ul>')
    head = ('<thead><tr><th scope="col">NACE Rev. 2 activity</th>'
            + ''.join('<th scope="col">' + escape(h) + '</th>' for _, h, _ in COLUMNS)
            + '<th scope="col">Eurostat flags</th></tr></thead>')
    for g in geos:
        cap = 'caption-' + slug(g)
        title = names[g] + ('' if g == EU else ' (' + g + ')')
        out.append('<h3 id="country-' + slug(g) + '">' + escape(title) + '</h3>')
        out.append('<div aria-labelledby="' + cap + '" class="table-wrap" role="region" tabindex="0"><table class="eurostat-table"><caption id="'
                   + cap + '">' + escape(title) + ': industrial enterprises by NACE activity and size band, 2023</caption>' + head + '<tbody>')
        for r in by_geo[g]:
            cells = []
            for column, _, _ in COLUMNS:
                value = r[column]
                cell = escape(display(value))
                note = FOOTNOTES.get((g, r['nace_r2_code'], column))
                if note:
                    if value != note[0]:
                        raise ValueError('Eurostat stage: footnoted value drift')
                    used.add(note)
                    cell += '<sup><a href="#' + note[1] + '" id="' + note[1] + '-ref">1</a></sup>'
                elif value.startswith('-'):
                    raise ValueError('Eurostat stage: unreviewed negative value')
                cells.append('<td>' + cell + '</td>')
            out.append('<tr id="' + slug(g) + '-' + r['nace_r2_code'].lower() + '"><th scope="row">' + escape(r['nace_r2_code'] + ' ' + r['nace_r2_activity'])
                       + '</th>' + ''.join(cells) + '<td>' + escape(flags(r['eurostat_flags'])) + '</td></tr>')
        out.append('</tbody></table></div>')
    if used != set(FOOTNOTES.values()):
        raise ValueError('Eurostat stage: footnote not placed')
    out.append('<p id="fn-fi-b-investment" class="eurostat-footnote"><a href="#fn-fi-b-investment-ref">1</a> Finland, B Mining and quarrying, gross investment in machinery and equipment: value as published by Eurostat (−12.43). Negative values can arise from national reporting adjustments; Eurostat publishes it without a flag.</p>')
    return ''.join(out)


CSS = ('\n.eurostat-index{display:flex;flex-wrap:wrap;gap:6px 18px;list-style:none;padding-left:0}'
       '\n.eurostat-index li{margin:0}'
       '\n#full-data-table .foundation-grid{grid-template-columns:minmax(0,1fr)}'
       '\n.eurostat-table td{text-align:right;font-variant-numeric:tabular-nums;white-space:nowrap}'
       '\n.eurostat-table td:last-child{text-align:left;white-space:normal;min-width:12em}'
       '\n.eurostat-table th[scope="row"]{min-width:16em;white-space:normal}\n')


def article_sections():
    """The sections appended after the article prose, table slot filled."""
    html = (CONTENT / 'eurostat-dataset.fragment.html').read_text(encoding='utf-8')
    if html.count(SLOT) != 1:
        raise ValueError('Eurostat stage: table slot missing')
    return BeautifulSoup(html.replace(SLOT, table_html(load_rows())), 'html.parser')


def apply_eurostat(output):
    if not (output / ROUTE).is_file() or not (output / ASSET).is_file():
        raise ValueError('Eurostat stage: article page or CSV missing')
    css = output / 'styles.css'
    css.write_text(css.read_text() + CSS)
