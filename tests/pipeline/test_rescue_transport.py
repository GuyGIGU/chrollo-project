"""The rescue lanes' transport + cost instrument (consolidation-method
Task 10): the composing cost twin (``evaluate_ticker_with_rescue_stats``),
the conductor sink, and the ``rescue_lane_worker_s`` ScanTimer pseudo-phase —
the instrument BOTH rescue flip rows gate their cost bound on.

Pins: flags-off the twin contributes nothing (empty sink, no row, no keys);
a full-refusal frame books ONE escalation with its wall-time and outcome; a
converting frame (EGBN, the banked A/B's own name) books ``elected`` while
the fire rides the base verbatim; a crashed base evaluation contributes
nothing; the REAL conductor publishes the block + the pseudo-phase only on
nights the lane ran.
"""
from __future__ import annotations

import sys

import numpy as np
import pandas as pd
import pytest

from _paths import REPO_ROOT as ROOT
sys.path.insert(0, str(ROOT))

from config import settings
from engine_alpha import evaluation
from engine_alpha.evaluation import evaluate_ticker_with_rescue_stats
from tools.regression.marks_corpus import _FROZEN_BREADTH
from tools.regression.marks_corpus import _load_fixture as _load_marks_fixture
from core.calibration.replay import fixture_frame, flag_capture

pytestmark = pytest.mark.regression


def _refusing_frame(n=300):
    """A steady riser: passes every universe filter, seeds no climax->AR
    anchors (no 5% reaction ever prints), so the walk is a FULL refusal and
    the armed escalation runs — and also refuses."""
    closes = 15.0 * (1.005 ** np.arange(n))
    idx = pd.bdate_range("2025-01-02", periods=n)
    return pd.DataFrame({"Open": closes, "High": closes * 1.004,
                         "Low": closes * 0.996, "Close": closes,
                         "Volume": np.full(n, 2_000_000.0)}, index=idx)


def _verdict(base):
    """The fire verdict under whatever lane triples the ladder wrapped it in."""
    while isinstance(base, tuple):
        base = base[0]
    return base


def test_flags_off_the_twin_contributes_nothing():
    assert settings.CONTRACTION_RESCUE_ENABLED is False
    assert settings.BAR_POSTURE_RESCUE_ENABLED is False
    base, row, stats = evaluate_ticker_with_rescue_stats(
        "RISER", _refusing_frame(), 0.0, _FROZEN_BREADTH)
    assert row is None and stats == {}
    # The sink is always disarmed after the call.
    from engine_alpha.structure.narrative import reader as narrative
    assert narrative._rescue_sink is None


def test_full_refusal_books_one_escalation_with_cost(monkeypatch):
    monkeypatch.setattr(settings, "BAR_POSTURE_RESCUE_ENABLED", True)
    base, row, stats = evaluate_ticker_with_rescue_stats(
        "RISER", _refusing_frame(), 0.0, _FROZEN_BREADTH)
    result = _verdict(base)
    assert result is None, "the riser must stay a structural refusal"
    assert row == {"ticker": "RISER", "escalated": ["s_test_bar_posture"],
                   "outcome": "refused"}
    assert stats["rescue_walks"] == 1
    assert stats["rescue_elected"] == 0
    assert stats["rescue_ms"] >= 0.0


def test_conversion_books_elected_and_the_fire_rides_the_base(monkeypatch):
    monkeypatch.setattr(settings, "BAR_POSTURE_RESCUE_ENABLED", True)
    frames, baseline = _load_marks_fixture()
    e = next(x for x in baseline["setups"] if x["key"] == "EGBN:2026-01-15")
    sliced = fixture_frame(frames, e["key"], "EGBN").loc[
        :pd.Timestamp("2026-01-07")]
    base, row, stats = evaluate_ticker_with_rescue_stats(
        "EGBN", sliced, 0.0, _FROZEN_BREADTH)
    result = _verdict(base)
    assert isinstance(result, dict), "the banked conversion must fire"
    assert row["outcome"] == "elected"
    assert stats["rescue_elected"] == 1 and stats["rescue_walks"] == 1


def test_a_nested_arm_never_clobbers_the_paying_sink():
    """The seam's own law: the FIRST armer owns the booking. A nested arm is
    refused (loudly) instead of silently displacing the paying walk's sink,
    and every scope restores what it found rather than blanking it."""
    from engine_alpha.structure.narrative import reader as narrative

    outer: dict = {}
    with narrative.rescue_sink(outer):
        assert narrative._rescue_sink is outer
        inner: dict = {}
        with narrative.rescue_sink(inner):
            assert narrative._rescue_sink is outer      # never displaced
        with narrative.rescue_sink(None):
            assert narrative._rescue_sink is None       # the dark-read seam
        assert narrative._rescue_sink is outer          # restored, not blanked
        assert inner == {}, "the refused arm must contribute nothing"
    assert narrative._rescue_sink is None


def test_crashed_base_contributes_nothing(monkeypatch):
    monkeypatch.setattr(settings, "BAR_POSTURE_RESCUE_ENABLED", True)
    # Route the ladder through the plain evaluation so the fake below IS the
    # walk (the twin's default rung; the live near-miss twin would otherwise
    # run the real chain).
    monkeypatch.setattr(settings, "NEAR_MISS_LANE_ENABLED", False)

    def crashing_eval(ticker, df, *a, **k):
        # Book into the armed sink first — proving partial telemetry from an
        # aborted read is still refused — then crash the walk.
        from engine_alpha.structure.narrative import reader as narrative
        if narrative._rescue_sink is not None:
            narrative._rescue_sink["rescue_walks"] = 1
            narrative._rescue_sink["rescue_ms"] = 1.0
        return evaluation.EVAL_ERROR

    monkeypatch.setattr(evaluation, "_evaluate_ticker", crashing_eval)
    base, row, stats = evaluate_ticker_with_rescue_stats(
        "BOOM", _refusing_frame(), 0.0, _FROZEN_BREADTH)
    assert row is None and stats == {}, (
        "an aborted walk is incomplete evidence — it must contribute nothing")


class _InlineFuture:
    def __init__(self, fn, *args):
        self._result = fn(*args)

    def result(self):
        return self._result


class _InlinePool:
    def __init__(self, *a, **k):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def submit(self, fn, *args):
        return _InlineFuture(fn, *args)


def test_conductor_publishes_the_lane_block_and_pseudo_phase(monkeypatch):
    """The REAL run_screener + worker ladder, lane armed on a refusing frame:
    the attempt row lands in the published block, the counters ride, and the
    summed in-worker cost records as its own pseudo-phase — present ONLY
    because the lane ran."""
    import core.pipeline.screening.screener as screener_module

    df = _refusing_frame()

    class _Provider:
        def fetch(self, tickers, universe=None):
            return df

    monkeypatch.setattr(screener_module, "ProcessPoolExecutor", _InlinePool)
    monkeypatch.setattr(screener_module, "as_completed",
                        lambda futures: iter(list(futures)))
    monkeypatch.setattr(screener_module, "get_tickers", lambda *a, **k: ["AAA"])
    monkeypatch.setattr(screener_module, "get_provider", lambda: _Provider())
    monkeypatch.setattr(
        screener_module, "get_market_context",
        lambda data, frames, *a, **k: {"spy_6m_return": 0.0, "breadth_pct": 1.0})
    monkeypatch.setattr(screener_module, "persist_scan_metrics",
                        lambda metrics, universe=None: None)

    with flag_capture(BAR_POSTURE_RESCUE_ENABLED=True,
                      NEAR_MISS_LANE_ENABLED=False):
        _results, _data, _tickers, market_context = screener_module.run_screener()

    block = market_context["rescue_lane"]
    assert [r["ticker"] for r in block["attempts"]] == ["AAA"]
    assert block["attempts"][0]["outcome"] == "refused"
    assert block["counts"]["rescue_walks"] == 1
    metrics = market_context["_scan_metrics"]
    assert "rescue_lane_worker_s" in metrics["phases_s"]


def test_rescue_rung_wraps_the_watch_and_near_miss_rungs(monkeypatch):
    """The full ladder the conductor builds with every rung armed: the rescue
    cost twin OUTERMOST (it wrapped the species twin until that lane was
    deleted, final method build step 12), the watch twin (build step 8) under
    it, the near-miss twin innermost. Each sink gets its own rung's output,
    unwrapped in that order, off the ONE paying read of the refusing frame."""
    import core.pipeline.screening.screener as screener_module

    df = _refusing_frame()

    class _Provider:
        def fetch(self, tickers, universe=None):
            return df

    monkeypatch.setattr(screener_module, "ProcessPoolExecutor", _InlinePool)
    monkeypatch.setattr(screener_module, "as_completed",
                        lambda futures: iter(list(futures)))
    monkeypatch.setattr(screener_module, "get_tickers", lambda *a, **k: ["AAA"])
    monkeypatch.setattr(screener_module, "get_provider", lambda: _Provider())
    monkeypatch.setattr(
        screener_module, "get_market_context",
        lambda data, frames, *a, **k: {"spy_6m_return": 0.0, "breadth_pct": 1.0})
    monkeypatch.setattr(screener_module, "persist_scan_metrics",
                        lambda metrics, universe=None: None)

    near_miss_sink = {"rows": [], "stats": {}}
    with flag_capture(BAR_POSTURE_RESCUE_ENABLED=True,
                      LPS_LEAVES_ELECTION_ENABLED=True,
                      NEAR_MISS_LANE_ENABLED=True):
        _results, _data, _tickers, market_context = screener_module.run_screener(
            near_miss_sink=near_miss_sink)

    block = market_context["rescue_lane"]
    assert [r["ticker"] for r in block["attempts"]] == ["AAA"]
    assert block["counts"]["rescue_walks"] == 1
    watch = market_context["watch"]
    assert sum(watch["counts"].values()) == 1, watch["counts"]
    assert set(watch["counts"]) <= set(evaluation.WATCH_WIRE_STATES) | {
        "below the floor"}, watch["counts"]
    assert "lane_errored" not in near_miss_sink["stats"], near_miss_sink["stats"]


def test_dark_scan_metrics_carry_no_rescue_phase(monkeypatch):
    """Flags dark: no rescue block, no pseudo-phase — the persisted metrics
    stay byte-identical (EC-8's flag-off surface includes scan metrics)."""
    import core.pipeline.screening.screener as screener_module

    df = _refusing_frame()

    class _Provider:
        def fetch(self, tickers, universe=None):
            return df

    monkeypatch.setattr(screener_module, "ProcessPoolExecutor", _InlinePool)
    monkeypatch.setattr(screener_module, "as_completed",
                        lambda futures: iter(list(futures)))
    monkeypatch.setattr(screener_module, "get_tickers", lambda *a, **k: ["AAA"])
    monkeypatch.setattr(screener_module, "get_provider", lambda: _Provider())
    monkeypatch.setattr(
        screener_module, "get_market_context",
        lambda data, frames, *a, **k: {"spy_6m_return": 0.0, "breadth_pct": 1.0})
    monkeypatch.setattr(screener_module, "persist_scan_metrics",
                        lambda metrics, universe=None: None)

    with flag_capture(NEAR_MISS_LANE_ENABLED=False):
        _results, _data, _tickers, market_context = screener_module.run_screener()

    assert "rescue_lane" not in market_context
    assert "rescue_lane_worker_s" not in market_context["_scan_metrics"]["phases_s"]
