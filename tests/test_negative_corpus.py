"""Negative-corpus precision gate wired into pytest/CI.

The shadow guard (``tools.shadow_diff``) freezes only previously-FIRING tickers
and seed-recall (``core.archive.seed_recall``) only fails on LOST winners, so
the guard net was one-directional: a change that made junk setups fire
universe-wide passed every gate. This module runs the REAL negative-corpus
guard (``tools.negative_corpus.check_corpus``) end-to-end against the COMMITTED
fixture: operator/dissection-labeled must-NOT-fire charts, each verified
non-firing + baseline-passing at freeze time, replayed through the per-ticker
pipeline. Any case that starts firing fails the default pytest run (and CI).

Fully OFFLINE and deterministic - reads only the committed
``tests/baselines/negative_corpus.parquet`` + ``negative_corpus_meta.json``.
"""
from __future__ import annotations

import os

import pytest

from tools import negative_corpus

pytestmark = pytest.mark.regression


def test_negative_fixture_and_meta_are_committed():
    """The guard is meaningless if its inputs are missing.

    Fail LOUDLY (never skip) if the committed fixture or meta has gone missing
    -- a silent skip would reopen the precision blind spot.
    """
    assert os.path.exists(negative_corpus._FIXTURE_PARQUET), (
        f"Missing frozen negative corpus at {negative_corpus._FIXTURE_PARQUET}; "
        "run `python -m tools.negative_corpus --build-fixture` and commit it."
    )
    assert os.path.exists(negative_corpus._FIXTURE_META), (
        f"Missing negative-corpus meta at {negative_corpus._FIXTURE_META}; "
        "run `python -m tools.negative_corpus --build-fixture` and commit it."
    )


def test_negative_corpus_still_rejects_every_case():
    """Replay every frozen must-NOT-fire frame; assert each cleanly rejects.

    ``check_corpus()`` returns True iff every labeled junk case still produces
    no setup (None) - a fire, an eval crash, or a missing frame all fail.
    """
    assert negative_corpus.check_corpus() is True, (
        "Negative-corpus guard failed: a labeled must-NOT-fire chart fires (or "
        "crashes) under the current engine. Re-run `python -m tools.negative_corpus "
        "--check` to see which case, then either fix the precision regression or, "
        "if the fire is a deliberate recall change, re-eyeball and re-freeze that "
        "case individually."
    )


def test_negative_corpus_still_rejects_every_case_flag_on(monkeypatch):
    """Two-form guard (Event Map Task 9): the holding-shelf completion form
    widens LPS acceptance, so replay the SAME committed junk corpus with
    LPS_HOLDING_SHELF_ENABLED forced ON — a second completion form must not
    make labeled junk fire."""
    from config import settings

    monkeypatch.setattr(settings, "LPS_HOLDING_SHELF_ENABLED", True)
    assert negative_corpus.check_corpus() is True, (
        "Negative-corpus guard failed with the holding-shelf form ON: the "
        "second completion form makes a labeled must-NOT-fire chart fire. "
        "Tighten the shelf predicate (position/monotone/length gates) before "
        "any flip."
    )


def test_negative_corpus_still_rejects_every_case_story_pool_on(monkeypatch):
    """Story-pool guard (Event Map program Task 9): the last-resort story
    rung widens BOX acceptance for occupancy-killed candidates, so replay the
    SAME committed junk corpus with STORY_POOL_ENABLED forced ON — the ruled
    narrative form must not make labeled junk fire. The census named the
    exposure this pins: RLGT is the one pool-REACHABLE junk case (every
    candidate dies at occupancy), and KWR/NVT/GOOD carry parsing sentences
    behind standing ordinary elections."""
    from config import settings

    monkeypatch.setattr(settings, "STORY_POOL_ENABLED", True)
    assert negative_corpus.check_corpus() is True, (
        "Negative-corpus guard failed with the story pool ON: a labeled "
        "must-NOT-fire chart fires through the ruled admission form. Run "
        "`python -m tools.negative_corpus --check` to name the case; the "
        "admission form / in-pool gates must own it before any flip."
    )


def test_negative_corpus_still_rejects_every_case_miss_lanes_on(monkeypatch):
    """Miss-program guard (2026-08-28): the contraction rescue widens BOX
    acceptance on full-refusal frames and the 50-day dip exception widens the
    universe DOOR, so replay the SAME committed junk corpus with BOTH lanes
    forced ON — neither lane may make labeled junk fire. (Measured clean at
    build time: all 18 cases reject; docs/miss_program_2026-08.md.)"""
    from config import settings

    monkeypatch.setattr(settings, "CONTRACTION_RESCUE_ENABLED", True)
    monkeypatch.setattr(settings, "SMA50_DIP_EXCEPTION_ENABLED", True)
    assert negative_corpus.check_corpus() is True, (
        "Negative-corpus guard failed with the miss-program lanes ON: a "
        "labeled must-NOT-fire chart fires through the contraction rescue or "
        "the dip exception. Run `python -m tools.negative_corpus --check` to "
        "name the case; the lane must own it before any flip."
    )


def test_meta_cases_all_have_frames():
    """Fixture integrity: every labeled case has a frame in the parquet.

    A meta/parquet mismatch would surface inside check_corpus as a failure, but
    this pins the direct cause when someone hand-edits one file and not the
    other.
    """
    frames, meta = negative_corpus._load_fixture()
    missing = [c["ticker"] for c in meta["cases"]
               if c["ticker"] not in frames or frames[c["ticker"]].empty]
    assert not missing, f"meta cases without fixture frames: {missing}"
    assert len(meta["cases"]) >= 15, (
        f"suspiciously small corpus ({len(meta['cases'])} cases) - the gate is "
        "only worth wiring if it protects the documented junk classes"
    )


def test_negative_gate_bites_when_a_case_fires(monkeypatch):
    """Bite proof: the guard must FAIL when a corpus case starts firing.

    Force one case's eval to return a firing result dict and assert
    ``check_corpus`` returns False against the REAL committed fixture. Without
    this, a guard that always returned True would look green while protecting
    nothing.

    Bite proof of the bite proof: revert check_corpus's ``result is not None``
    branch and this test fails.
    """
    _frames, meta = negative_corpus._load_fixture()
    poisoned = meta["cases"][0]["ticker"]

    # Non-poisoned cases return None (a clean reject) without paying the real
    # eval - the bite proof only needs the poisoned case to reach the guard.
    def fake_eval(ticker, df, *args, **kwargs):
        if ticker == poisoned:
            return {"Setup": "LPS", "Score": 120.0, "Tier": "S"}
        return None

    # check_corpus calls the name bound in the negative_corpus module namespace.
    monkeypatch.setattr(negative_corpus, "_evaluate_ticker", fake_eval)

    assert negative_corpus.check_corpus() is False, (
        "check_corpus returned True even though a must-NOT-fire case fired - "
        "the guard is not actually gating on precision regressions."
    )


def test_negative_gate_bites_on_eval_error(monkeypatch):
    """An eval CRASH on a corpus frame must FAIL the gate, not pass as a
    rejection.

    The corpus documents "the engine cleanly rejects this junk"; EVAL_ERROR is
    neither a rejection nor a fire - treating it as a pass would let a change
    that crashes on (and thereby hides) junk charts keep the gate green.
    """
    from engine_alpha.evaluation import EVAL_ERROR

    _frames, meta = negative_corpus._load_fixture()
    poisoned = meta["cases"][0]["ticker"]

    def fake_eval(ticker, df, *args, **kwargs):
        if ticker == poisoned:
            return EVAL_ERROR
        return None

    monkeypatch.setattr(negative_corpus, "_evaluate_ticker", fake_eval)

    assert negative_corpus.check_corpus() is False, (
        "check_corpus returned True even though a corpus frame crashed the eval "
        "chain - a crash must fail the gate loudly."
    )
