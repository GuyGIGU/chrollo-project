"""Cause-before-effect veto bite-proof wired into pytest/CI.

``CAUSE_BEFORE_EFFECT_VETO_ENABLED`` is live on main but shipped without a
regression guard - nothing red if a future change silently defeated it. This
module runs the REAL bite-proof (``tools.regression.cause_veto_corpus.check_corpus``)
against the COMMITTED fixture: the census-defining MIDD frame, replayed BOTH
directions - the veto ON must reject it, the veto OFF must fire it. A change
that defeats the veto reds the ON direction; a change that makes the frame
reject for an unrelated reason (so the case guards nothing) reds the OFF
direction.

Fully OFFLINE and deterministic - reads only the committed
``tests/baselines/cause_veto_corpus.parquet`` + ``cause_veto_corpus_meta.json``.
"""
from __future__ import annotations

import os

import pytest

from engine_alpha.evaluation import EVAL_ERROR
from tools.regression import cause_veto_corpus

pytestmark = pytest.mark.regression


def test_cause_veto_fixture_and_meta_are_committed():
    """The guard is meaningless if its inputs are missing - fail LOUDLY (never
    skip), a silent skip reopens the blind spot the veto has no other net for."""
    assert os.path.exists(cause_veto_corpus._FIXTURE_PARQUET), (
        f"Missing cause-veto fixture at {cause_veto_corpus._FIXTURE_PARQUET}; "
        "run `python -m tools.regression.cause_veto_corpus --build-fixture` and commit it."
    )
    assert os.path.exists(cause_veto_corpus._FIXTURE_META), (
        f"Missing cause-veto meta at {cause_veto_corpus._FIXTURE_META}; "
        "run `python -m tools.regression.cause_veto_corpus --build-fixture` and commit it."
    )


def test_veto_still_bites_both_directions():
    """Replay every frozen frame: the veto ON rejects AND the veto OFF fires.

    ``check_corpus()`` returns True iff the veto is what suppresses each case -
    a fire with the veto on (veto defeated), a no-fire with it off (case guards
    nothing), an eval crash, or a missing frame all fail.
    """
    assert cause_veto_corpus.check_corpus() is True, (
        "Cause-veto bite-proof failed: the live veto no longer suppresses the "
        "frozen MIDD-class frame (or the frame no longer fires without it). "
        "Re-run `python -m tools.regression.cause_veto_corpus --check` to see which direction."
    )


def test_meta_cases_all_have_frames():
    """Fixture integrity: every case has a frame in the parquet - pins the
    direct cause when someone hand-edits one file and not the other."""
    frames, meta = cause_veto_corpus._load_fixture()
    missing = [c["ticker"] for c in meta["cases"]
               if c["ticker"] not in frames or frames[c["ticker"]].empty]
    assert not missing, f"meta cases without fixture frames: {missing}"
    assert meta["cases"], "empty cause-veto corpus - the guard protects nothing"


def test_bite_fails_when_the_veto_stops_suppressing(monkeypatch):
    """ON-direction bite proof: if a frame FIRES with the veto on, the guard
    must FAIL. Force the eval to fire and assert ``check_corpus`` is False
    against the REAL committed fixture - a guard that always returned True would
    look green while protecting nothing.

    Bite proof of the bite proof: revert check_corpus's ``on is not None``
    branch and this test fails.
    """
    def fake_eval(ticker, df, *args, **kwargs):
        # Fires in BOTH directions -> the OFF half is satisfied, so the failure
        # is unambiguously the veto-defeated ON half.
        return {"Setup": "LPS", "Score": 120.0, "Tier": "S"}

    monkeypatch.setattr(cause_veto_corpus, "_evaluate_ticker", fake_eval)
    assert cause_veto_corpus.check_corpus() is False, (
        "check_corpus returned True even though the frame fired with the veto ON "
        "- the guard is not actually gating on the veto still biting."
    )


def test_bite_fails_when_the_frame_no_longer_fires(monkeypatch):
    """OFF-direction bite proof: if a frame does NOT fire even with the veto
    off, it would guard nothing (it rejects for some unrelated reason), so the
    guard must FAIL rather than pass a hollow case."""
    def fake_eval(ticker, df, *args, **kwargs):
        return None  # never fires -> the OFF half is violated

    monkeypatch.setattr(cause_veto_corpus, "_evaluate_ticker", fake_eval)
    assert cause_veto_corpus.check_corpus() is False, (
        "check_corpus returned True even though the frame no longer fires with "
        "the veto OFF - a case that fires only via some other gate guards nothing."
    )


def test_bite_fails_on_eval_error(monkeypatch):
    """An eval CRASH on the bite-proof frame must FAIL the gate, not pass: a
    crash is neither a rejection nor a fire, so it proves nothing about the veto."""
    def fake_eval(ticker, df, *args, **kwargs):
        return EVAL_ERROR

    monkeypatch.setattr(cause_veto_corpus, "_evaluate_ticker", fake_eval)
    assert cause_veto_corpus.check_corpus() is False, (
        "check_corpus returned True even though the eval chain crashed on the "
        "bite-proof frame - a crash must fail the gate loudly."
    )
