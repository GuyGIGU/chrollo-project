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
    from core.pipeline.evaluation import EVAL_ERROR

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
