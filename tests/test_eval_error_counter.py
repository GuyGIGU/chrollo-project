"""Hermetic tests for the eval-error counter + alert tripwire.

The eval skip-guard swallows a per-ticker eval-chain crash so one bad ticker
never fails the whole scan. Historically that swallow returned ``None`` — exactly
what a *legitimate structural reject* returns — so a regression that throws on a
SUBSET of tickers silently dropped real winners on an otherwise-green (exit 0)
build with no counter and no alert.

These tests pin the fix end-to-end WITHOUT touching the archive DB, the parquet
cache, a real scan, or the scoring math:

  * ``_evaluate_ticker`` returns the distinct ``EVAL_ERROR`` sentinel (not None)
    when the eval chain throws, and still returns None for a structural reject.
  * ``_evaluate_frames`` counts sentinels separately (``_LAST_EVAL_ERRORED``),
    never appends them to results, and a structural reject is NOT counted as an
    error while a normal fire is unaffected.
  * The count surfaces in the metrics formatter and drives the alert decision.
  * The scan-runner parses the count back out of stdout.

All fixtures are local + in-memory; no shared conftest fixtures are used.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import core.pipeline.evaluation as evaluation
import core.pipeline.screener as screener
import core.pipeline.scan_metrics as scan_metrics


# --------------------------------------------------------------------------- #
# Local helpers                                                               #
# --------------------------------------------------------------------------- #
class _SyncFuture:
    """Minimal Future stand-in: runs the callable eagerly, replays result()."""

    def __init__(self, fn, *args):
        try:
            self._value = fn(*args)
            self._exc = None
        except BaseException as exc:  # pragma: no cover - defensive
            self._value = None
            self._exc = exc

    def result(self):
        if self._exc is not None:
            raise self._exc
        return self._value


class _SyncExecutor:
    """Drop-in for ProcessPoolExecutor that runs everything in-process.

    Lets the test drive ``_evaluate_frames`` with a monkeypatched
    ``_evaluate_ticker`` (no pickling, no worker processes, fully hermetic) while
    exercising the real result-consumption / counting loop.
    """

    def __init__(self, *a, **k):
        self._futures = []

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def submit(self, fn, *args):
        fut = _SyncFuture(fn, *args)
        self._futures.append(fut)
        return fut


def _as_completed_passthrough(futures):
    # Real as_completed yields futures; our sync executor already ran them.
    return list(futures)


def _price_frame(n: int = 5) -> pd.DataFrame:
    idx = pd.date_range("2026-01-01", periods=n, freq="B")
    return pd.DataFrame({"Close": [1.0] * n, "Volume": [1] * n}, index=idx)


# --------------------------------------------------------------------------- #
# 1. The sentinel itself: crash -> EVAL_ERROR, structural reject -> None       #
# --------------------------------------------------------------------------- #
def test_evaluate_ticker_returns_sentinel_on_crash_not_none(monkeypatch):
    def _boom(*a, **k):
        raise ValueError("synthetic eval-chain crash")  # in the guard's except list

    monkeypatch.setattr(evaluation, "_run_eval_chain", _boom)
    out = evaluation._evaluate_ticker("BOOM", _price_frame())
    assert out is evaluation.EVAL_ERROR
    assert out is not None  # the whole point: distinguishable from a reject


def test_evaluate_ticker_structural_reject_stays_none(monkeypatch):
    monkeypatch.setattr(evaluation, "_run_eval_chain", lambda *a, **k: None)
    out = evaluation._evaluate_ticker("REJECT", _price_frame())
    assert out is None
    assert out is not evaluation.EVAL_ERROR


def test_eval_error_sentinel_survives_pickle_identity():
    # _evaluate_ticker runs in a worker process; the sentinel must round-trip to
    # the SAME singleton or the parent's `is EVAL_ERROR` check silently misses.
    import pickle

    assert pickle.loads(pickle.dumps(evaluation.EVAL_ERROR)) is evaluation.EVAL_ERROR


# --------------------------------------------------------------------------- #
# 2. _evaluate_frames counts sentinels separately from rejects and fires       #
# --------------------------------------------------------------------------- #
def test_evaluate_frames_counts_error_not_reject_and_keeps_fire(monkeypatch):
    monkeypatch.setattr(screener, "ProcessPoolExecutor", _SyncExecutor)
    monkeypatch.setattr(screener, "as_completed", _as_completed_passthrough)

    fire = {"Ticker": "FIRE", "Score": 42}

    def _fake_eval(ticker, df, spy, breadth):
        if ticker == "BOOM":
            return evaluation.EVAL_ERROR      # swallowed eval crash
        if ticker == "REJECT":
            return None                        # legitimate structural reject
        return fire                            # a normal fire

    monkeypatch.setattr(screener, "_evaluate_ticker", _fake_eval)

    frames = {
        "BOOM": _price_frame(),
        "REJECT": _price_frame(),
        "FIRE": _price_frame(),
    }
    results = screener._evaluate_frames(frames, 0.0, None)

    # The fire is kept; neither the reject nor the error is appended.
    assert results == [fire]
    # Exactly ONE errored ticker — the structural reject is NOT counted as errored.
    assert screener._LAST_EVAL_ERRORED == 1


def test_evaluate_frames_clean_run_reports_zero_errored(monkeypatch):
    monkeypatch.setattr(screener, "ProcessPoolExecutor", _SyncExecutor)
    monkeypatch.setattr(screener, "as_completed", _as_completed_passthrough)

    def _fake_eval(ticker, df, spy, breadth):
        return None if ticker == "REJECT" else {"Ticker": ticker, "Score": 1}

    monkeypatch.setattr(screener, "_evaluate_ticker", _fake_eval)

    frames = {"A": _price_frame(), "REJECT": _price_frame(), "B": _price_frame()}
    results = screener._evaluate_frames(frames, 0.0, None)

    assert len(results) == 2                 # both fires kept
    assert screener._LAST_EVAL_ERRORED == 0  # no swallowed crash


def test_evaluate_frames_resets_counter_each_call(monkeypatch):
    monkeypatch.setattr(screener, "ProcessPoolExecutor", _SyncExecutor)
    monkeypatch.setattr(screener, "as_completed", _as_completed_passthrough)
    monkeypatch.setattr(
        screener, "_evaluate_ticker",
        lambda t, df, spy, breadth: evaluation.EVAL_ERROR,
    )
    screener._evaluate_frames({"X": _price_frame()}, 0.0, None)
    assert screener._LAST_EVAL_ERRORED == 1
    # A subsequent clean call must reset the stale count to 0.
    monkeypatch.setattr(
        screener, "_evaluate_ticker",
        lambda t, df, spy, breadth: {"Ticker": t, "Score": 1},
    )
    screener._evaluate_frames({"Y": _price_frame()}, 0.0, None)
    assert screener._LAST_EVAL_ERRORED == 0


# --------------------------------------------------------------------------- #
# 3. The count surfaces in the metrics formatter                               #
# --------------------------------------------------------------------------- #
def test_formatter_shows_errored_count():
    metrics = {
        "total_s": 1.0, "phases_s": {},
        "counts": {"universe_tickers": 3, "evaluated_tickers": 3,
                   "setups": 1, "errored_tickers": 2},
    }
    assert "errored=2" in scan_metrics.format_scan_metrics(metrics)


def test_formatter_defaults_errored_to_zero_when_absent():
    # A clean scan omits errored_tickers from counts (byte-parity); formatter
    # still shows errored=0 so downstream parsing always has a token.
    metrics = {
        "total_s": 1.0, "phases_s": {},
        "counts": {"universe_tickers": 3, "evaluated_tickers": 3, "setups": 1},
    }
    assert "errored=0" in scan_metrics.format_scan_metrics(metrics)


# --------------------------------------------------------------------------- #
# 4. The alert decision + the scan-runner stdout parser                        #
# --------------------------------------------------------------------------- #
def _load_scan_runner():
    backend = ROOT / "webapp" / "backend"
    if str(backend) not in sys.path:
        sys.path.insert(0, str(backend))
    import services.scan_runner as scan_runner
    return scan_runner


def test_alert_decision_fires_on_errored_tickers():
    scan_runner = _load_scan_runner()
    # ok status, setups present, healthy fetch, but a swallowed eval crash -> alert.
    reason = scan_runner._alert_decision("ok", 5, None, True, True, errored_tickers=1)
    assert reason is not None
    assert "errored" in reason


def test_alert_decision_silent_when_no_errors():
    scan_runner = _load_scan_runner()
    # Zero errored + a healthy ok scan with setups -> no alert.
    assert scan_runner._alert_decision("ok", 5, None, True, True, errored_tickers=0) is None
    # None (no data / older child) -> no alert, prior behaviour preserved.
    assert scan_runner._alert_decision("ok", 5, None, True, True) is None


def test_parse_n_errored_round_trips_from_formatter_line():
    scan_runner = _load_scan_runner()
    line = scan_metrics.format_scan_metrics({
        "total_s": 1.0, "phases_s": {},
        "counts": {"universe_tickers": 3, "evaluated_tickers": 3,
                   "setups": 1, "errored_tickers": 4},
    })
    output = f"some earlier line\n{line}\nSCAN_RESULT_JSON:{{}}\n"
    assert scan_runner._parse_n_errored(output) == 4


def test_parse_n_errored_none_when_absent():
    scan_runner = _load_scan_runner()
    assert scan_runner._parse_n_errored("no timing line here\n") is None
