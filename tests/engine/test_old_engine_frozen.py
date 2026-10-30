"""The old chart reader is FROZEN until the flip — a guard, not a promise.

Task 7 of the two-eyes-reader build. The new reader starts from COPIES of the old engine's proven pieces, and
those copies change from here on purpose. The originals may not: the old engine is still the one the nightly
scan runs, its tests are pinned, and a rewrite that quietly edits the old engine while measuring itself against
it is how the last three attempts ended up measuring the old engine wearing a new name.

So every file of the old chart reader is fingerprinted, as it stood at the freeze base (61c88cc; it was
cd87fcc until the port onto main's layout on Sat 26/09/2026 moved every frozen path and the base with it), in
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

from _paths import REPO_ROOT
import glob
import hashlib
import json
import os

_ROOT = str(REPO_ROOT)
_MANIFEST = os.path.join(_ROOT, "tests", "baselines", "old_engine_freeze.json")

#: What "the old chart reader" is, file by file. Structure and scoring whole, and the four modules outside them
#: that are old-engine behaviour: the eval chain, the stability read, the frame trim and the election identity.
_FROZEN_TREES = ("engine_alpha/structure", "engine_alpha/scoring")
_FROZEN_FILES = ("engine_alpha/evaluation.py", "engine_alpha/stability.py", "engine_alpha/frames.py",
                 "engine_alpha/election_identity.py")
# The new reader's judge belongs in scoring; none of the frozen legacy files imports it.
_NEW_READER_SCORING = {"engine_alpha/scoring/clarity.py"}
_NEW_READER_SETTINGS = {
    "CLARITY_SWING_FULL_SHARE", "CLARITY_RAIL_FULL_ERROR", "CLARITY_RAIL_ZERO_ERROR",
}


def _fingerprint(path: str) -> str:
    with open(os.path.join(_ROOT, path), "rb") as f:
        return hashlib.sha256(f.read().replace(b"\r\n", b"\n")).hexdigest()


def _frozen_paths_now() -> list[str]:
    paths = set(_FROZEN_FILES)
    for tree in _FROZEN_TREES:
        for p in glob.glob(os.path.join(_ROOT, tree, "**", "*.py"), recursive=True):
            paths.add(os.path.relpath(p, _ROOT).replace(os.sep, "/"))
    return sorted(paths - _NEW_READER_SCORING)


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
    assert pinned["base"] == "61c88cc"
    assert len(pinned["files"]) >= 47, "the frozen set shrank"
    for p in pinned["files"]:
        assert p in _FROZEN_FILES or p.startswith(_FROZEN_TREES), f"{p} is fingerprinted but not frozen"


def _old_reader_settings_digest() -> str:
    """The engine's version stamp with the new reader's own entries left out: every knob the old reader reads
    (detection, scoring, the derived registries), and nothing the new reader's tuning moves."""
    from engine_alpha.freeze.manifest import collect_manifest

    # FUND_* (2026-10-12): the fundamentals sheet and grade, read after the chart by the scan's post-pass; neither
    # reader reads them, so they are no old-reader knob (the FUNDAMENTALS_* switches predate the seal and stay in).
    old = {key: value for key, value in collect_manifest().items()
           if not key.startswith(("TWO_EYES", "FUND_")) and key not in _NEW_READER_SETTINGS}
    return hashlib.sha256(json.dumps(old, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def test_the_old_chart_readers_knobs_have_not_moved_since_the_freeze():
    """Freezing the old reader's FILES does not freeze its KNOBS: a threshold in config/engine.py or a weight in
    config/scoring.py moves its reading with every file above unchanged. The version stamp would rotate, but it
    also carries the new reader's numbers, so its "engine config changed" advisory is lit for a reason that is
    not the old reader's (council review 2026-10-09, finding 1). This pins the stamp without those entries."""
    with open(_MANIFEST, encoding="utf-8") as f:
        pinned = json.load(f)["settings_sha256"]
    assert _old_reader_settings_digest() == pinned, (
        "an old-reader knob moved (config/engine.py, config/scoring.py or a registry the version stamp hashes): "
        "the old chart reader is frozen until the flip. If this is the flip itself, retire this guard with the "
        "file guard above.")


def test_the_knob_guard_sees_a_moved_knob(monkeypatch):
    """The guard's teeth: one old-reader knob moved, and the digest moves with it."""
    from config import settings
    from engine_alpha.freeze.manifest import ENGINE_SETTINGS_KEYS

    before = _old_reader_settings_digest()
    knob = next(k for k in ENGINE_SETTINGS_KEYS
                if not k.startswith("TWO_EYES") and k not in _NEW_READER_SETTINGS
                and isinstance(getattr(settings, k), (int, float))
                and not isinstance(getattr(settings, k), bool))
    monkeypatch.setattr(settings, knob, getattr(settings, knob) + 1)
    assert _old_reader_settings_digest() != before, f"moving {knob} did not move the digest"


def test_the_new_readers_clarity_settings_do_not_move_the_old_readers_identity(monkeypatch):
    # The three scales live in two_eyes_numbers since Fri 30/10/2026 (the TWO_EYES block, left out above).
    from engine_alpha import two_eyes_numbers

    before = _old_reader_settings_digest()
    for name in _NEW_READER_SETTINGS:
        with monkeypatch.context() as patch:
            patch.setattr(two_eyes_numbers, name, getattr(two_eyes_numbers, name) + .01)
            assert _old_reader_settings_digest() == before, name
