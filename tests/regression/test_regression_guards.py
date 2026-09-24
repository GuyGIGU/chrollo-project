"""End-to-end regression-guard test wired into pytest/CI.

The headline shadow-output guard (``tools.regression.shadow_diff.check_baseline``) was
previously MANUAL-ONLY: CI ran compileall + pytest but never the drift guard,
so a change that silently altered a canonical screener output could pass CI.

This module runs the REAL guard end-to-end against the COMMITTED baseline and
frozen fixture, so any canonical-field drift fails the default pytest run (and
therefore CI). It is fully OFFLINE and deterministic: ``check_baseline`` reads
the committed ``tests/baselines/shadow_baseline.json`` and replays the frozen
``shadow_fixture.parquet`` through the per-ticker pipeline on the fired-policy
WINDOW the marks ratchet grades (the last ten trading days ending at the frozen
day, ``tools.replay.fired_window_walk``; final method build step 1,
2026-09-13). No network, no live archive DB, no parquet cache.

The real replay is paid ONCE through a module-scoped fixture; the window
semantics (first/last fire day, fire-day count, the last fire's fields, the
drop of a never-firing ticker) are proven on fakes in well under a second each.

The sibling seed-recall guard (``core.archive.seed_recall``) is intentionally
NOT run here: its ``--check`` needs the archive SQLite DB and ``--fresh`` needs
the network, so it lives as a separate (network-annotated) CI step instead.
"""
from __future__ import annotations

import os

import pandas as pd
import pytest

# Import path (`from tools.regression.shadow_diff import ...`) is already exercised by the
# existing suite (tests/integration/test_guards.py, tests/scoring/test_scoring.py, etc.), so pytest's
# rootdir is on sys.path and this import resolves without extra bootstrapping.
from tools.regression import shadow_diff
from core.calibration.replay import fired_window_sessions

pytestmark = pytest.mark.regression


@pytest.fixture(scope="module")
def shadow_verdict() -> bool:
    """The REAL window replay of the whole fixture against the committed
    baseline, paid once per module (37 tickers x 10 days)."""
    return shadow_diff.check_baseline()


def _one_fixture_ticker():
    """One fixture ticker and the ISO days ``run_fixture`` walks for it."""
    frames, scalars = shadow_diff._load_fixture()
    tickers = [t for t in scalars["tickers"] if t in frames]
    assert tickers, "fixture has no frames to exercise"
    ticker = tickers[0]
    sessions, _note = fired_window_sessions(frames[ticker], frames[ticker].index[-1], [])
    return ticker, [ts.date().isoformat() for ts in sessions]


def _fire(score: float) -> dict:
    return {"Setup": "LPS", "Score": score, "Tier": "A", "Base Len": 30,
            "Box Width": 0.1, "LPS Length": 3, "_R": 10.0, "_S": 9.0,
            "_trigger_price": 10.1}


def test_shadow_baseline_and_fixture_are_committed():
    """The guard is meaningless if its inputs are missing.

    Fail LOUDLY (never skip) if the committed baseline or frozen fixture has
    gone missing -- a silent skip would let real drift sail through CI.
    """
    assert os.path.exists(shadow_diff._BASELINE_PATH), (
        f"Missing committed shadow baseline at {shadow_diff._BASELINE_PATH}; "
        "run `python -m tools.regression.shadow_diff --capture` and commit it."
    )
    assert os.path.exists(shadow_diff._FIXTURE_PARQUET), (
        f"Missing frozen shadow fixture at {shadow_diff._FIXTURE_PARQUET}; "
        "run `python -m tools.regression.shadow_diff --build-fixture` and commit it."
    )
    assert os.path.exists(shadow_diff._FIXTURE_SCALARS), (
        f"Missing frozen fixture scalars at {shadow_diff._FIXTURE_SCALARS}; "
        "run `python -m tools.regression.shadow_diff --build-fixture` and commit it."
    )


def test_shadow_output_guard_no_drift(shadow_verdict):
    """Replay the frozen fixture through the live pipeline; assert NO drift.

    ``check_baseline()`` returns True iff every canonical output field of every
    frozen ticker's LAST window fire, its first/last fire day and fire-day
    count, and the displayed ranking match the committed baseline. Offline +
    deterministic: it reads only committed files and runs the per-ticker
    pipeline in-memory.
    """
    assert shadow_verdict is True, (
        "Shadow-output guard drifted: a canonical screener output (or a fire "
        "day inside the fired window) changed against the committed baseline. "
        "Re-run `python -m tools.regression.shadow_diff --check` locally to see the exact "
        "ticker/field, then either fix the regression or, if the change is "
        "intended, re-capture the baseline."
    )


def test_run_fixture_drops_eval_error_without_raising(monkeypatch):
    """A swallowed eval crash (EVAL_ERROR sentinel) must be DROPPED, not crash.

    ``_evaluate_ticker`` returns the ``EVAL_ERROR`` enum (not ``None``) when the
    eval chain throws and is swallowed. ``EVAL_ERROR`` has no ``.get`` method, so
    if the window walk treated it as a firing result ``run_fixture`` would call
    ``canonical_fields(EVAL_ERROR)`` -> AttributeError, crashing the CI drift
    guard. This forces one fixture ticker's eval to return EVAL_ERROR on every
    window day (every other ticker cleanly rejects, no real eval paid) and
    asserts ``run_fixture`` completes gracefully, dropping it.

    Bite proof: make ``tools.replay.fired_window_walk`` file EVAL_ERROR under
    ``fires`` and this test raises AttributeError.
    """
    from engine_alpha.evaluation import EVAL_ERROR

    poisoned, _days = _one_fixture_ticker()

    def fake_eval(ticker, df, *args, **kwargs):
        return EVAL_ERROR if ticker == poisoned else None

    # run_fixture calls the name bound in the shadow_diff module namespace.
    monkeypatch.setattr(shadow_diff, "_evaluate_ticker", fake_eval)

    snapshot = shadow_diff.run_fixture()  # must NOT raise

    assert poisoned not in snapshot["fields"], (
        "EVAL_ERROR ticker leaked into the canonical fields instead of being dropped"
    )
    assert poisoned not in snapshot["ranking"], (
        "EVAL_ERROR ticker leaked into the ranking instead of being dropped"
    )


# ----------------------------------------------------------------------------
# The window semantics (build step 1): proven on fakes, no real engine.
# ----------------------------------------------------------------------------
def test_run_fixture_records_a_fire_on_a_non_final_window_day(monkeypatch):
    """The one-day blind spot, closed: a ticker that fires only on an EARLIER
    day of its window (clean on the frozen day) is a firing ticker, with that
    day as its first AND last fire."""
    ticker, days = _one_fixture_ticker()
    assert len(days) >= 4, f"{ticker}: window too short to pick a non-final day: {days}"
    chosen = days[-4]

    def fire_on_chosen_day(tk, sliced, *args, **kwargs):
        if tk == ticker and sliced.index[-1].date().isoformat() == chosen:
            return _fire(88.8)
        return None

    monkeypatch.setattr(shadow_diff, "_evaluate_ticker", fire_on_chosen_day)
    snapshot = shadow_diff.run_fixture()

    assert list(snapshot["fields"]) == [ticker]
    rec = snapshot["fields"][ticker]
    assert rec["first_fire"] == chosen
    assert rec["last_fire"] == chosen
    assert rec["fire_days"] == 1
    assert rec["Score"] == 88.8
    assert snapshot["ranking"] == [ticker]


def test_run_fixture_pins_first_and_last_fire_and_keeps_the_last_fires_fields(monkeypatch):
    """Two fire days: ``first_fire`` is the earlier, ``last_fire`` the later,
    ``fire_days`` counts both, and the canonical fields are the LAST fire's
    (the most recent night the pick appeared)."""
    ticker, days = _one_fixture_ticker()
    early, last = days[-4], days[-1]
    scores = {early: 50.0, last: 60.0}

    def fire_twice(tk, sliced, *args, **kwargs):
        day = sliced.index[-1].date().isoformat()
        if tk == ticker and day in scores:
            return _fire(scores[day])
        return None

    monkeypatch.setattr(shadow_diff, "_evaluate_ticker", fire_twice)
    rec = shadow_diff.run_fixture()["fields"][ticker]

    assert (rec["first_fire"], rec["last_fire"], rec["fire_days"]) == (early, last, 2)
    assert rec["Score"] == 60.0, "the canonical fields must come from the LAST fire"


def test_run_fixture_drops_a_ticker_with_no_fire_in_the_window(monkeypatch):
    """No fire on any window day -> not a firing ticker (as a non-firing
    ticker always was): absent from fields and ranking."""
    ticker, _days = _one_fixture_ticker()
    monkeypatch.setattr(shadow_diff, "_evaluate_ticker", lambda *a, **k: None)
    snapshot = shadow_diff.run_fixture()
    assert ticker not in snapshot["fields"]
    assert snapshot["fields"] == {} and snapshot["ranking"] == []


def test_diff_reads_a_fire_that_moved_a_day_earlier_as_drift():
    """A fire that moves one day earlier leaves every canonical field of the
    last fire unchanged - the window record alone must read as drift."""
    canonical = shadow_diff.canonical_fields(_fire(100.0))
    baseline = {"fields": {"AAA": {**canonical, "first_fire": "2026-06-04",
                                   "last_fire": "2026-06-05", "fire_days": 2}},
                "ranking": ["AAA"]}
    current = {"fields": {"AAA": {**canonical, "first_fire": "2026-06-03",
                                  "last_fire": "2026-06-05", "fire_days": 3}},
               "ranking": ["AAA"]}
    ok, lines = shadow_diff.diff_against_baseline(current, baseline)
    assert ok is False
    assert any("AAA.first_fire: 2026-06-04 -> 2026-06-03" in line for line in lines), lines
    assert any("AAA.fire_days: 2 -> 3" in line for line in lines), lines


def test_diff_reads_a_last_fire_that_moved_a_day_earlier_as_drift():
    """The LAST fire day is frozen too: a pick whose most recent night moved
    from the frozen day to the day before reads as drift on last_fire."""
    canonical = shadow_diff.canonical_fields(_fire(100.0))
    baseline = {"fields": {"AAA": {**canonical, "first_fire": "2026-06-03",
                                   "last_fire": "2026-06-05", "fire_days": 3}},
                "ranking": ["AAA"]}
    current = {"fields": {"AAA": {**canonical, "first_fire": "2026-06-03",
                                  "last_fire": "2026-06-04", "fire_days": 2}},
               "ranking": ["AAA"]}
    ok, lines = shadow_diff.diff_against_baseline(current, baseline)
    assert ok is False
    assert any("AAA.last_fire: 2026-06-05 -> 2026-06-04" in line for line in lines), lines


def test_frozen_day_view_keeps_only_the_frozen_day_fires():
    """The one-day view the flag-ON twins (other test modules) compare their
    frozen-day replay against: a ticker whose LAST fire is an earlier window
    day is not a frozen-day fire and leaves the view; the window record
    leaves the fields; the ranking is restricted in place."""
    idx = pd.date_range("2026-06-01", periods=5, freq="B")
    frames = {"AAA": pd.DataFrame({"Close": 1.0}, index=idx),
              "BBB": pd.DataFrame({"Close": 1.0}, index=idx)}
    canonical = shadow_diff.canonical_fields(_fire(100.0))
    snapshot = {"fields": {
        "AAA": {**canonical, "first_fire": "2026-06-03", "last_fire": "2026-06-05", "fire_days": 2},
        "BBB": {**canonical, "first_fire": "2026-06-03", "last_fire": "2026-06-04", "fire_days": 2},
    }, "ranking": ["BBB", "AAA"]}
    view = shadow_diff.frozen_day_view(snapshot, frames)
    assert view == {"fields": {"AAA": canonical}, "ranking": ["AAA"]}
