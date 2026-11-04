import copy
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
EXAMPLES = ROOT / 'pipeline' / 'examples'
BRIEF_PATH = EXAMPLES / 'brief-fixture.json'
RESPONSES_PATH = EXAMPLES / 'apollo-organizations-fixture.json'
FAKE_KEY = 'not-a-real-key-test-fixture-0000'


def brief(**overrides):
    data = json.loads(BRIEF_PATH.read_text(encoding='utf-8'))
    data.update(overrides)
    return data


def response_pages():
    return copy.deepcopy(json.loads(RESPONSES_PATH.read_text(encoding='utf-8'))['pages'])


class ScriptedTransport:
    """Returns (status, payload) tuples in order; raises the item instead if it is an Exception."""

    def __init__(self, *responses):
        self.responses = list(responses)
        self.calls = []

    def __call__(self, method, url, headers, body):
        self.calls.append({'method': method, 'url': url, 'headers': dict(headers), 'body': dict(body)})
        item = self.responses.pop(0)
        if isinstance(item, Exception):
            raise item
        return item
