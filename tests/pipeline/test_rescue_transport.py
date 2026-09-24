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
    result = base[0]
    if isinstance(result, tuple):
        result = result[0]
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
    result = base[0]
    if isinstance(result, tuple):
        result = result[0]
    assert isinstance(result, dict), "the banked conversion must fire"
    assert row["outcome"] == "elected"
    assert stats["rescue_elected"] == 1 and stats["rescue_walks"] == 1


def _baseline_fire_frame():
    """A marked setup whose PAYING read elects at BASELINE — no escalation, so
    the sink stays empty unless something else books into it."""
    frames, baseline = _load_marks_fixture()
    e = next(x for x in baseline["setups"]
             if x["status"] == "hit" and x["key"].startswith("VLO"))
    sliced = fixture_frame(frames, e["key"], e["ticker"]).loc[
        :pd.Timestamp(e["first_fire"])]
    return e["ticker"], sliced, float(e["spy_6m_return"])


def test_the_species_lanes_dark_read_books_nothing(monkeypatch):
    """Council review 2026-09-01, finding 1, under the exact planned flag pair
    (bar-posture armed, the power-play preset live): the species lane runs its
    own scoped second read, which escalates the SAME armed form — and the
    sink's booking is last-write-wins over summed wall-time. A ticker whose
    PAYING read elects while that dark read fully refuses must produce NO
    attempt row and NO rescue milliseconds, or the attempts sheet and the cost
    bound BOTH flip rulings are read from describe the dark read.

    The stand-in's anti-vacuity evidence is RECORDED here and judged in the
    body below, never asserted in place: the stand-in runs inside
    ``evaluate_ticker_with_power_play``'s except-Exception, which eats an
    assertion raised there and leaves this test green on a stand-in that
    never escalated at all (round-two completeness critic, 2026-09-01)."""
    monkeypatch.setattr(settings, "BAR_POSTURE_RESCUE_ENABLED", True)
    monkeypatch.setattr(settings, "POWER_PLAY_PRESET_ENABLED", True)
    from engine_alpha.structure.narrative import reader as narrative
    from engine_alpha.structure.narrative import read_structure

    dark_frame = _refusing_frame()
    seen: dict = {}

    def _scoped_dark_read(_df):
        # Stands in for species_watch's scoped read (the real one runs under
        # the power-play window override): a FULL refusal, which arms the
        # escalation. Its own probe sink records whether the read really did
        # escalate — the body asserts on it, out of reach of the swallow.
        prep, _reason = evaluation._prepare_eval_frame_with_reason(dark_frame)
        pdf = prep["df"]
        atr = float(evaluation.structure_atr_row(pdf)["ATR_10"])
        probe: dict = {}
        with narrative.rescue_sink(probe):
            seen["read"] = read_structure(pdf, atr)
        seen["probe"] = dict(probe)
        return None, {"pp_watched": 1}

    monkeypatch.setattr(evaluation, "species_watch", _scoped_dark_read)
    ticker, sliced, spy = _baseline_fire_frame()
    base, row, stats = evaluate_ticker_with_rescue_stats(
        ticker, sliced, spy, _FROZEN_BREADTH)
    result = base[0]
    if isinstance(result, tuple):
        result = result[0]
    # The lane's OWN counters are state the swallow cannot eat: a stand-in
    # that raised books pp_errored and never books pp_watched.
    pp_stats = base[2]
    assert "pp_errored" not in pp_stats, (
        f"the species lane swallowed the stand-in: {pp_stats}")
    assert pp_stats.get("pp_watched") == 1, (
        f"the stand-in dark read never completed: {pp_stats}")
    assert seen["read"] is None, "the stand-in read must be a full refusal"
    assert seen["probe"].get("rescue_walks") == 1, (
        "the stand-in read did not escalate — the pin below proves nothing "
        "unless the dark read really does book into whatever sink it finds")
    assert isinstance(result, dict), "the paying read must elect at baseline"
    assert row is None and stats == {}, (
        "the species lane's dark read booked into the paying walk's sink")


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
    # walk (the live nm/species twins would otherwise run the real chain).
    monkeypatch.setattr(settings, "NEAR_MISS_LANE_ENABLED", False)
    monkeypatch.setattr(settings, "POWER_PLAY_PRESET_ENABLED", False)

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
