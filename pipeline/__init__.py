"""Demand Range list pipeline: ICP brief -> Apollo organization candidates -> review-ready files.

Company-level only. Apollo output is a *candidate* list for analyst research, never an
accepted account list, and never a list of named people. No module here makes a network
call unless an ApolloClient or a ZeroBounceClient is created with live=True and its API key
environment variable is set; tests use an injected fake transport.
"""
__all__ = ['icp', 'apollo', 'prospects', 'zerobounce', 'verify', 'export', 'cli']
__version__ = '0.3.0'
