"""Test package. Importing it disables urllib network access for the whole test process."""
import urllib.request


def _forbid_network(*args, **kwargs):
    raise AssertionError('network call attempted during tests: ' + repr(args[:1]))


urllib.request.urlopen = _forbid_network
