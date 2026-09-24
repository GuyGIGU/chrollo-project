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
  * ``_evaluate_frames`` returns the sentinel count in-band ``(results, errored)``,
    never appends sentinels to results, and a structural reject is NOT counted as
    an error while a normal fire is unaffected.
  * The count surfaces in the metrics formatter and drives the alert decision.
  * The scan-runner parses the count back out of the SCAN_RESULT_JSON channel —
    reading the PRIMARY universe's count on a multi-universe run.

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

import engine_alpha.evaluation as evaluation
import core.pipeline.screening.screener as screener
import core.pipeline.telemetry.scan_metrics as scan_metrics


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
    results, errored = screener._evaluate_frames(frames, 0.0, None)

    # The fire is kept; neither the reject nor the error is appended.
    assert results == [fire]
    # Exactly ONE errored ticker — the structural reject is NOT counted as errored.
    assert errored == 1


def test_evaluate_frames_clean_run_reports_zero_errored(monkeypatch):
    monkeypatch.setattr(screener, "ProcessPoolExecutor", _SyncExecutor)
    monkeypatch.setattr(screener, "as_completed", _as_completed_passthrough)

    def _fake_eval(ticker, df, spy, breadth):
        return None if ticker == "REJECT" else {"Ticker": ticker, "Score": 1}

    monkeypatch.setattr(screener, "_evaluate_ticker", _fake_eval)

    frames = {"A": _price_frame(), "REJECT": _price_frame(), "B": _price_frame()}
    results, errored = screener._evaluate_frames(frames, 0.0, None)

    assert len(results) == 2  # both fires kept
    assert errored == 0       # no swallowed crash


def test_evaluate_frames_count_is_per_call_not_carried_over(monkeypatch):
    # The count is returned in-band (no module global), so each call reports its
    # OWN errored count with no stale carry-over from a prior call.
    monkeypatch.setattr(screener, "ProcessPoolExecutor", _SyncExecutor)
    monkeypatch.setattr(screener, "as_completed", _as_completed_passthrough)
    monkeypatch.setattr(
        screener, "_evaluate_ticker",
        lambda t, df, spy, breadth: evaluation.EVAL_ERROR,
    )
    _, errored = screener._evaluate_frames({"X": _price_frame()}, 0.0, None)
    assert errored == 1
    # A subsequent clean call reports 0 — the prior 1 does not leak forward.
    monkeypatch.setattr(
        screener, "_evaluate_ticker",
        lambda t, df, spy, breadth: {"Ticker": t, "Score": 1},
    )
    _, errored = screener._evaluate_frames({"Y": _price_frame()}, 0.0, None)
    assert errored == 0


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


def test_parse_scan_result_reads_errored_from_json_channel():
    scan_runner = _load_scan_runner()
    output = (
        "some earlier line\n"
        'SCAN_RESULT_JSON:{"n_setups": 1, "n_archived": 1, "n_errored": 4}\n'
    )
    n_setups, n_errored = scan_runner._parse_scan_result(output)
    assert n_setups == 1
    assert n_errored == 4


def test_parse_scan_result_defaults_errored_to_zero_when_key_absent():
    # An older child (or clean scan) omits n_errored; a swallowed-crash count is a
    # tripwire, so "unknown" means "no known crashes" -> 0 (never a phantom alert).
    scan_runner = _load_scan_runner()
    n_setups, n_errored = scan_runner._parse_scan_result(
        'SCAN_RESULT_JSON:{"n_setups": 5, "n_archived": 5}\n'
    )
    assert n_setups == 5
    assert n_errored == 0


def test_parse_scan_result_none_setups_when_payload_absent():
    scan_runner = _load_scan_runner()
    n_setups, n_errored = scan_runner._parse_scan_result("no result line here\n")
    assert n_setups is None
    assert n_errored == 0


def test_multi_universe_errored_reads_primary_not_last_universe():
    """Regression for the multi-universe silent-drop bug.

    On the scheduled --all-universes run US-Stocks (the PRIMARY) runs FIRST and
    prints its errored count onto the ONE SCAN_RESULT_JSON line; small ETF
    universes run LAST and print their own "Scan timing: ... errored=0" line at the
    very bottom of stdout. The alert must see the PRIMARY count (N), not the last
    universe's 0.

    This asserts the JSON-channel value the alert consumes is N. It FAILS against
    the old reversed(splitlines()) scrape of the "errored=" timing line (which
    returns the LAST universe's 0) and PASSES with the SCAN_RESULT_JSON fix.
    """
    scan_runner = _load_scan_runner()
    # Primary (US-Stocks) errored=3, threaded onto SCAN_RESULT_JSON. A later ETF
    # universe's timing line (errored=0) is the LAST timing line in stdout.
    primary_json = 'SCAN_RESULT_JSON:{"n_setups": 12, "n_archived": 12, "n_errored": 3}'
    primary_timing = scan_metrics.format_scan_metrics({
        "total_s": 1.0, "phases_s": {},
        "counts": {"universe_tickers": 500, "evaluated_tickers": 480,
                   "setups": 12, "errored_tickers": 3},
    })
    etf_timing = scan_metrics.format_scan_metrics({
        "total_s": 0.2, "phases_s": {},
        "counts": {"universe_tickers": 11, "evaluated_tickers": 11, "setups": 0},
    })
    # Stdout order: primary universe first (JSON + its timing), ETF universe last.
    output = "\n".join([primary_timing, primary_json, "Scanning ETF universe...", etf_timing]) + "\n"

    _, n_errored = scan_runner._parse_scan_result(output)
    assert n_errored == 3, "alert must read the PRIMARY universe's errored count, not the last universe's 0"

    # The old reversed-scrape read the LAST "errored=" timing line — prove that
    # would have returned the ETF's 0, i.e. the exact bug this fix removes.
    def _old_reversed_scrape(text: str):
        for line in reversed(text.splitlines()):
            if line.startswith("Scan timing:"):
                for token in line.split():
                    stripped = token.rstrip(",")
                    if stripped.startswith("errored="):
                        return int(stripped[len("errored="):])
        return None

    assert _old_reversed_scrape(output) == 0  # the masked-bug behaviour
