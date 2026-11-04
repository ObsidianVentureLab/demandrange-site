"""Keep real lists and outputs out of the repository (QA PR-FIXES-r2).

This repository is public, and anything that reaches main is served at demandrange.com. So every CLI path
that can hold real data (briefs, input lists, output folders, the client database) must sit outside any
git work tree that holds this pipeline. The only exception is the fictional fixtures under
pipeline/examples/, which inputs may name (fixture replay, tests).

A path is refused when it, or any of its parents, is a git work tree (".git" dir or worktree file) that
contains pipeline/__init__.py, i.e. a checkout of this repository. Symlinks are resolved first, so a link
from outside into the checkout is refused too.
"""
from pathlib import Path


class InsideRepoError(ValueError):
    """A data path points inside a checkout of this repository."""


def _checkout_root(path):
    for parent in (path, *path.parents):
        if (parent / '.git').exists() and (parent / 'pipeline' / '__init__.py').is_file():
            return parent
    return None


def refuse_inside_repo(path, flag, *, allow_examples=False):
    """Return the resolved path, or raise InsideRepoError naming `flag` if it lies inside a checkout.

    allow_examples=True lets an *input* name a fixture under <checkout>/pipeline/examples/.
    Output paths (--out, --db) never get that exception.
    """
    resolved = Path(path).expanduser().resolve()
    root = _checkout_root(resolved)
    if root is None:
        return resolved
    if allow_examples and resolved.is_relative_to(root / 'pipeline' / 'examples'):
        return resolved
    raise InsideRepoError(
        f'{flag} {path} is inside the repository checkout {root}: real lists and outputs must live outside '
        f'it (this repo is public). Use a folder such as ~/dr-data/ instead'
        + ('' if not allow_examples else '; only the fictional fixtures under pipeline/examples/ may be read from here'))
