"""Demand Range list pipeline: ICP brief -> Apollo organization candidates -> review-ready files.

Company-level only. Apollo output is a *candidate* list for analyst research, never an
accepted account list, and never a list of named people. No module here makes a network
call unless an ApolloClient is created with live=True and the API key environment variable
is set; tests use an injected fake transport.
"""
__all__ = ['icp', 'apollo', 'prospects', 'zerobounce', 'verify', 'cli']
__version__ = '0.2.0'
