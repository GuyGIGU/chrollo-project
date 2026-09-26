"""The old chart reader is FROZEN until the flip — a guard, not a promise.

Task 7 of the two-eyes-reader build. The new reader starts from COPIES of the old engine's proven pieces, and
those copies change from here on purpose. The originals may not: the old engine is still the one the nightly
scan runs, its tests are pinned, and a rewrite that quietly edits the old engine while measuring itself against
it is how the last three attempts ended up measuring the old engine wearing a new name.

So every file of the old chart reader is fingerprinted, as it stood at the freeze base (cd87fcc), in
tests/baselines/old_engine_freeze.json, and this fails on any edit, any added file and any removed file. The
fingerprint is of the text with line endings normalised: Windows checks the tree out with CRLF and the CI's
one-commit checkout with LF, and a byte hash would fail one of them for nothing. A git ref would not do either
— the CI checkout carries one commit, and the base is not in it.

Two files under engine_alpha/ are deliberately NOT frozen: freeze/manifest.py, the version stamp's list of
settings, which grows with every new switch (the two-eyes reader's own two are in it); and the door
(reader.py), which routes between the two readers. The flip retires this guard and the fingerprint file
together.
"""
from __future__ import annotations

import glob
import hashlib
import json
import os

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_MANIFEST = os.path.join(_ROOT, "tests", "baselines", "old_engine_freeze.json")

#: What "the old chart reader" is, file by file. Structure and scoring whole, and the four modules outside them
#: that are old-engine behaviour: the eval chain, the stability read, the frame trim and the election identity.
_FROZEN_TREES = ("engine_alpha/structure", "engine_alpha/scoring")
_FROZEN_FILES = ("engine_alpha/evaluation.py", "engine_alpha/stability.py", "engine_alpha/frames.py",
                 "engine_alpha/election_identity.py")


def _fingerprint(path: str) -> str:
    with open(os.path.join(_ROOT, path), "rb") as f:
        return hashlib.sha256(f.read().replace(b"\r\n", b"\n")).hexdigest()


def _frozen_paths_now() -> list[str]:
    paths = set(_FROZEN_FILES)
    for tree in _FROZEN_TREES:
        for p in glob.glob(os.path.join(_ROOT, tree, "**", "*.py"), recursive=True):
            paths.add(os.path.relpath(p, _ROOT).replace(os.sep, "/"))
    return sorted(paths)


def test_the_old_chart_reader_has_not_moved_since_the_freeze():
    with open(_MANIFEST, encoding="utf-8") as f:
        pinned = json.load(f)["files"]
    now = _frozen_paths_now()
    added = sorted(set(now) - set(pinned))
    removed = sorted(set(pinned) - set(now))
    edited = sorted(p for p in set(now) & set(pinned) if _fingerprint(p) != pinned[p])
    assert not (added or removed or edited), (
        "the old chart reader is frozen until the flip (two-eyes-reader task 7): "
        f"edited {edited}, added {added}, removed {removed}. The new reader's pieces are COPIES in "
        "engine_alpha/two_eyes/ — change those. If this edit is the flip itself, retire this guard and "
        "tests/baselines/old_engine_freeze.json in the same change.")


def test_the_freeze_covers_every_file_it_names_and_nothing_else():
    """The fingerprint file and this test's own list of what is frozen must agree, or a new frozen path would
    be checked against nothing and pass."""
    with open(_MANIFEST, encoding="utf-8") as f:
        pinned = json.load(f)
    assert pinned["base"] == "cd87fcc"
    assert len(pinned["files"]) >= 40, "the frozen set shrank"
    for p in pinned["files"]:
        assert p in _FROZEN_FILES or p.startswith(_FROZEN_TREES), f"{p} is fingerprinted but not frozen"
