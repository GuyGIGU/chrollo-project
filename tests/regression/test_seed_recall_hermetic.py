"""Plumbing guard for the hermetic offline seed-recall gate.

The hermetic guard (``core.archive.seed_recall.hermetic_check_baseline``) replays
a COMMITTED OHLCV fixture (``tests/baselines/seed_recall_fixture.parquet`` — every
active seed winner's frozen frames + SPY) through the SAME ``_scan_back_seeds``
fold the live recall uses, entirely offline, and fails if a known winner the
engine used to re-find is now missed. It is the sibling of the ``tools.regression.shadow_diff``
guard, but over the curated winners via the seed twin ``_evaluate_at_date``.

The FULL replay runs the eval chain ~700× (52 winners × the -WINDOW_BACK/+WINDOW_FWD
scan-back) and takes several minutes — too slow for the default suite, so it lives
as the dedicated **"Hermetic seed-recall regression guard" CI step**
(``python -m core.archive.seed_recall --hermetic-check``), the hard offline gate.

This module keeps the plumbing honest on EVERY test run, cheaply: it asserts the
fixture + baseline are committed, that the frozen baseline faithfully mirrors the
live fresh-recall baseline (so the offline guard is a true stand-in for the network
one), and that the guard actually FAILS when a winner is dropped — all without
paying the multi-minute replay.
"""
from __future__ import annotations

import json
import os

import pytest

from core.archive import seed_recall

pytestmark = pytest.mark.regression

_FRESH_BASELINE = seed_recall._BASELINE_PATH


def _miss_set(baseline: dict) -> set:
    return {(m["ticker"], m["trigger_date"]) for m in baseline.get("misses", [])}


def _load(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def test_hermetic_fixture_and_baseline_are_committed():
    """The guard is meaningless if its inputs are missing.

    Fail LOUDLY (never skip) if the committed fixture or baseline has gone
    missing -- a silent skip would let a real seed-winner drop sail through CI.
    """
    assert os.path.exists(seed_recall._HERMETIC_FIXTURE), (
        f"Missing frozen seed fixture at {seed_recall._HERMETIC_FIXTURE}; run "
        "`python -m core.archive.seed_recall --build-fixture` (network) and commit it."
    )
    assert os.path.exists(seed_recall._HERMETIC_BASELINE), (
        f"Missing hermetic recall baseline at {seed_recall._HERMETIC_BASELINE}; run "
        "`python -m core.archive.seed_recall --hermetic-capture` and commit it."
    )


def test_hermetic_baseline_mirrors_live_fresh_recall():
    """The frozen offline baseline must match the live fresh-recall baseline.

    This is what makes the hermetic guard a faithful stand-in for the (advisory,
    network) fresh guard: the frozen fixture reproduces the SAME fired/miss split
    the live path produces. Identical miss-sets + fired counts prove the
    ``_scan_back_seeds`` fold and the parquet round-trip introduced no drift.
    Instant: it only reads the two committed baseline JSONs (no engine run — the
    full replay is the ``--hermetic-check`` CI step).
    """
    assert os.path.exists(_FRESH_BASELINE), "committed fresh baseline is missing"
    fresh = _load(_FRESH_BASELINE)
    herm = _load(seed_recall._HERMETIC_BASELINE)

    assert herm.get("basis") == "hermetic"
    assert herm["fired"] == fresh["fired"], (
        f"hermetic fired={herm['fired']} != fresh fired={fresh['fired']}; the frozen "
        "fixture no longer mirrors the live recall — rebuild + re-capture it."
    )
    assert _miss_set(herm) == _miss_set(fresh), (
        "hermetic and fresh baselines disagree on WHICH winners miss; the frozen "
        "fixture drifted from the live path — rebuild + re-capture it."
    )
    # The gate is only worth its runtime if it actually protects a real set of winners.
    assert herm["fired"] >= 25, f"suspiciously few protected winners ({herm['fired']})"


def test_hermetic_guard_bites_when_a_winner_is_dropped(monkeypatch):
    """Bite proof: the guard must FAIL when the engine stops re-finding winners.

    Force the offline replay to return no fires (as a detector regression that
    threw on every seed would) and assert ``hermetic_check_baseline`` returns
    False against the REAL committed baseline. Without this, a guard that always
    returned True would look green while protecting nothing. Exercises the real
    baseline file + the real diff, but skips the multi-minute engine replay.
    """
    monkeypatch.setattr(seed_recall, "hermetic_replay", lambda *a, **k: {})
    assert seed_recall.hermetic_check_baseline() is False, (
        "hermetic_check_baseline returned True even though every winner was "
        "dropped — the guard is not actually gating on recall regressions."
    )
