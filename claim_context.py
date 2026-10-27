"""Narrow claim context masking. Never treat an arbitrary 'no' prefix as safe."""
import re
from bs4 import BeautifulSoup

# Exact reviewed negative or written-scope sentences, not token-level exemptions.
SAFE_SENTENCES = frozenset({
    'There is no guaranteed revenue.',
    'This is not an instant quote.',
    'These are not marketing qualified leads.',
    'These are not MQLs.',
    'Volume, timing, price and any replacement terms belong in that written scope.',
    'Review cadence, acceptance rules and any correction or replacement terms are agreed for the work.',
    'There is no standard turnaround or replacement window promised on this page.',
    'Acceptance, replacement windows and any replacement limits are agreed in writing.',
})

def claim_scan_text(html):
    soup = BeautifulSoup(html, 'html.parser')
    # Scan ordinary visible leaf blocks independently so a heading does not turn
    # the next paragraph into a sentence continuation. Attributes/scripts remain
    # checked by the unchanged dependency, script and inline-handler gates.
    for el in soup.find_all(['p','li','h1','h2','h3','h4','h5','h6','dt','dd','td','th','div']):
        if el.find(['p','li','h1','h2','h3','h4','h5','h6','dt','dd','td','th','div']): continue
        text = ' '.join(el.get_text(' ',strip=True).split())
        sentences = re.split(r'(?<=[.!?])\s+', text)
        if any(s in SAFE_SENTENCES for s in sentences):
            el.clear()
            el.append(' '.join(s for s in sentences if s not in SAFE_SENTENCES))
    return soup.get_text(' ', strip=True)
