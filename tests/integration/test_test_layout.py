"""The suite's folder layout is load-bearing, so it is pinned here.

Test modules live in category folders under ``tests/`` (``engine/``,
``backend/``, ...) with no ``__init__.py``, so pytest's default import mode
imports each one by its bare basename. That has two consequences that stay
silent until they bite:

* two test files with the same basename collide at collection;
* ``conftest.py`` puts ``tests/`` itself on ``sys.path``, so a subfolder named
  like a real top-level package (``tools`` has no ``__init__.py``, so it is a
  namespace package) can merge with or shadow the real one.

And a ``test_*.py`` left loose in ``tests/`` undoes the layout it sits in.
"""
from collections import Counter

from _paths import BACKEND_DIR, REPO_ROOT, TESTS_DIR

# Data folders: they hold committed baselines and fixtures, never tests.
_DATA_DIRS = {"baselines", "fixtures"}


def _test_files():
    return sorted(TESTS_DIR.rglob("test_*.py"))


def _top_level_importables():
    """Every name importable from the repo root or the backend dir.

    Read off the filesystem so a new top-level package is covered the day it
    lands: any directory with an identifier name imports (a plain directory
    is a namespace package), and so does any ``.py`` file.
    """
    names = set()
    for base in (REPO_ROOT, BACKEND_DIR):
        for entry in base.iterdir():
            if entry.is_dir() and entry.name.isidentifier():
                names.add(entry.name)
            elif entry.suffix == ".py":
                names.add(entry.stem)
    names.discard("__pycache__")
    return names


def test_the_scan_finds_the_suite():
    """Guard the guards: an empty scan would pass every check below."""
    assert len(_test_files()) >= 150, (
        f"found only {len(_test_files())} test files under {TESTS_DIR}")


def test_every_test_basename_is_unique():
    counts = Counter(path.name for path in _test_files())
    duplicates = sorted(name for name, n in counts.items() if n > 1)
    assert not duplicates, (
        "test basenames must be unique across tests/ (pytest imports each by "
        f"its bare name): {duplicates}")


def test_no_tests_subfolder_shadows_a_top_level_name():
    importables = _top_level_importables()
    # Guard the guard: the set must really be read off the tree.
    assert {"tools", "core", "config", "engine_alpha", "domains"} <= importables
    folders = [d for d in TESTS_DIR.rglob("*")
               if d.is_dir() and d.name != "__pycache__"]
    clashes = sorted(d.relative_to(REPO_ROOT).as_posix() for d in folders
                     if d.name in importables)
    assert not clashes, (
        "a tests/ subfolder named like a top-level importable can merge with "
        f"or shadow the real package; rename it: {clashes}")


def test_every_test_file_sits_in_a_category_folder():
    misplaced = sorted(
        path.relative_to(REPO_ROOT).as_posix() for path in _test_files()
        if path.parent.parent != TESTS_DIR or path.parent.name in _DATA_DIRS)
    assert not misplaced, (
        "every test file belongs in a category folder directly under tests/ "
        f"(engine/, backend/, ...), never loose in tests/: {misplaced}")
