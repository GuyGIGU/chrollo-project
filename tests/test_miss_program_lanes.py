"""Miss-program lane guards (2026-08-28) — the two dark lanes built for the
operator's six-miss ruling ("no reason at large for these to miss").

Lane 1 — the contraction rescue (``CONTRACTION_RESCUE_ENABLED``): when the
whole root walk elects NOTHING, ``read_structure`` re-walks once with the
species resistance-contraction form armed inside the story pool. The scope IS
the design — the 2026-08-19 global-flip refusal named three grounds (WCC's
2.2x-wider re-election, pinned hits firing earlier, the species passenger
invariant), and every one is unreachable when the rescue only runs on frames
that elect nothing. These guards pin that scope behaviorally:

* full refusal + flag off  -> ONE walk (byte-identical live path);
* an electing frame        -> ONE walk even with the flag on (never displaces);
* a cause-before-effect veto is doctrinal and FINAL — never rescued;
* the species lane's own scoped read (form already armed) is never re-walked;
* end-to-end on the sealed corpus: the rescue converts exactly the two
  operator-ruled conversions (EGBN/PKE, "BOTH have setups on these days so
  yeah", 2026-08-19), stamped ``elected_pool='story'`` with the self-naming
  contraction profile.

Lane 2 — the 50-day dip exception (``SMA50_DIP_EXCEPTION_ENABLED``): an sma50
universe refusal enters chart reading when the dip under the 50-day is
bounded, recent, and already recovered to within ``SMA50_DIP_MAX_ATR`` ATR_10
of the rail. The synthetic-frame guards are SELF-VERIFYING: each asserts the
constructed frame actually landed in the intended margin region (computed from
the frame itself) before asserting the gate's verdict, so a drifted
construction fails loudly instead of testing nothing. End-to-end: SKYT's
drawn spring dragged price under the 50-day and the exception lets its
2026-04-07 strict-pool election fire (tier S) — the door was that day's only
wall.

The junk-defense legs (both flags forced on over the committed must-NOT-fire
corpus) live in test_negative_corpus.py, its home.
"""
from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from config import settings
from core.pipeline.screener import _evaluate_ticker
from engine_alpha.evaluation import apply_baseline_filters_with_reason
from engine_alpha.structure.narrative import Structure, read_structure
from tools import shadow_diff
from tools.marks_corpus import _FROZEN_BREADTH
from tools.marks_corpus import _load_fixture as _load_marks_fixture
from tools.replay import fixture_frame

pytestmark = pytest.mark.regression


# ────────────────────────── lane 1: the contraction rescue ──────────────────

class _RefusingBricks:
    """Every walk refuses immediately; ``walks`` counts how many walks ran."""

    def __init__(self):
        self.walks = 0

    def find_root_swing(self, df, search_from_bar, atr):
        if search_from_bar == 0:
            self.walks += 1
        return None


class _FormSensitiveBricks(_RefusingBricks):
    """Full refusal with the species form off; a complete story with it on —
    the scripted shape of a contraction-rescue conversion."""

    def find_root_swing(self, df, search_from_bar, atr):
        if search_from_bar == 0:
            self.walks += 1
        if not settings.POWER_PLAY_STORY_FORM_ENABLED:
            return None
        if search_from_bar > 10:
            return None
        return SimpleNamespace(climax_bar=10, ar_bar=20, R=110.0, S=100.0)

    def validate_equilibrium(self, df, root, atr, trace=None):
        return SimpleNamespace(S=100.0, R=110.0, start_bar=20, box_width=0.10)

    def find_spring(self, df, box, atr):
        return None

    def find_inner_box(self, df, box, atr):
        return None

    def find_lps(self, df, box, atr, *, diagnose=False, start_floor_bar=None):
        lps = SimpleNamespace(start_bar=85)
        return (lps, None) if diagnose else lps

    def cause_maturity(self, df, box, atr, lps=None):
        return SimpleNamespace(matured=True, bridge_validated=True,
                               pre_box_trend="", box_trend="",
                               lps_tightness_ratio=0.0)

    def resolve_phase_a(self, df, root, box, atr, terminal_floor=None):
        return root.climax_bar, root.ar_bar


class _AlwaysElectingBricks(_FormSensitiveBricks):
    """Elects the same complete story regardless of the species form."""

    def find_root_swing(self, df, search_from_bar, atr):
        if search_from_bar == 0:
            self.walks += 1
        if search_from_bar > 10:
            return None
        return SimpleNamespace(climax_bar=10, ar_bar=20, R=110.0, S=100.0)


class _VetoedBricks(_AlwaysElectingBricks):
    """A complete story the cause-before-effect veto abstains."""

    def cause_maturity(self, df, box, atr, lps=None):
        return SimpleNamespace(matured=False, bridge_validated=False,
                               pre_box_trend="up", box_trend="up",
                               lps_tightness_ratio=0.99)


def test_flag_off_full_refusal_is_one_walk(monkeypatch):
    monkeypatch.setattr(settings, "CONTRACTION_RESCUE_ENABLED", False)
    bricks = _RefusingBricks()
    assert read_structure(None, 1.0, bricks=bricks) is None
    assert bricks.walks == 1, "flag off must stay a single walk (live path)"


def test_rescue_rewalks_a_full_refusal_with_the_form_armed(monkeypatch):
    monkeypatch.setattr(settings, "CONTRACTION_RESCUE_ENABLED", True)
    assert settings.POWER_PLAY_STORY_FORM_ENABLED is False
    bricks = _FormSensitiveBricks()
    s = read_structure(None, 1.0, bricks=bricks)
    assert isinstance(s, Structure), "the rescue walk should have elected"
    assert bricks.walks == 2
    assert settings.POWER_PLAY_STORY_FORM_ENABLED is False, (
        "the scoped override leaked — the species form flag must restore")


def test_rescue_trace_stamps_the_second_pass(monkeypatch):
    monkeypatch.setattr(settings, "CONTRACTION_RESCUE_ENABLED", True)
    trace: list = []
    s = read_structure(None, 1.0, bricks=_FormSensitiveBricks(), trace=trace)
    assert isinstance(s, Structure)
    assert trace, "the rescue pass should narrate its walk"
    assert all(rec.get("pass") == "contraction_rescue" for rec in trace), (
        "every second-pass trace record carries the rescue stamp")
    assert trace[-1]["outcome"] == "complete"


def test_rescue_never_runs_when_a_structure_elects(monkeypatch):
    monkeypatch.setattr(settings, "CONTRACTION_RESCUE_ENABLED", True)
    bricks = _AlwaysElectingBricks()
    s = read_structure(None, 1.0, bricks=bricks)
    assert isinstance(s, Structure)
    assert bricks.walks == 1, (
        "an electing frame must never be re-walked — the rescue is scoped to "
        "full refusals by construction")


def test_rescue_never_relitigates_a_cause_veto(monkeypatch):
    monkeypatch.setattr(settings, "CONTRACTION_RESCUE_ENABLED", True)
    monkeypatch.setattr(settings, "CAUSE_BEFORE_EFFECT_VETO_ENABLED", True)
    bricks = _VetoedBricks()
    assert read_structure(None, 1.0, bricks=bricks) is None
    assert bricks.walks == 1, (
        "a cause-before-effect abstention is doctrinal and final ('no setup "
        "at all') — the rescue must not re-walk it")


def test_rescue_skipped_when_the_form_is_already_armed(monkeypatch):
    """The species lane's scoped read arms the form itself — a second walk
    there would be the same walk twice."""
    monkeypatch.setattr(settings, "CONTRACTION_RESCUE_ENABLED", True)
    monkeypatch.setattr(settings, "POWER_PLAY_STORY_FORM_ENABLED", True)
    bricks = _RefusingBricks()
    assert read_structure(None, 1.0, bricks=bricks) is None
    assert bricks.walks == 1


def test_contraction_rescue_converts_the_ruled_misses_end_to_end(monkeypatch):
    """The lane's happy path through the REAL cascade on the sealed corpus:
    the two operator-ruled conversions fire with the flag on, stay silent with
    it off, elect through the story pool, and name the contraction behavior
    in their admitting sentence. Fire days are the frozen-frame harness A/B's
    (docs/miss_program_2026-08.md); tiers match the 2026-08-19 record."""
    frames, baseline = _load_marks_fixture()
    by_key = {e["key"]: e for e in baseline["setups"]}
    for key, fire_day, tier in [("EGBN:2026-01-15", "2026-01-07", "A"),
                                ("PKE:2026-02-24", "2026-02-18", "B")]:
        e = by_key[key]
        assert e["status"] == "miss", (
            f"{key} is no longer a sealed expected-miss — this guard and the "
            "ratchet need a deliberate re-pin")
        sliced = fixture_frame(frames, key, e["ticker"]).loc[
            :pd.Timestamp(fire_day)]

        monkeypatch.setattr(settings, "CONTRACTION_RESCUE_ENABLED", False)
        off = _evaluate_ticker(e["ticker"], sliced, 0.0, _FROZEN_BREADTH)
        assert not isinstance(off, dict), (
            f"{key}: fires WITHOUT the rescue — no longer a rescue "
            "conversion; re-pin this guard deliberately")

        monkeypatch.setattr(settings, "CONTRACTION_RESCUE_ENABLED", True)
        on = _evaluate_ticker(e["ticker"], sliced, 0.0, _FROZEN_BREADTH)
        assert isinstance(on, dict), (
            f"{key}: the rescue conversion no longer fires at {fire_day}")
        assert on["_elected_pool"] == "story"
        assert on["_story_admission_profile"].startswith("contracting"), (
            f"{key}: admitting sentence lost the behavior name — "
            f"{on['_story_admission_profile']!r}")
        assert on["Tier"] == tier


def test_rescue_keeps_an_ordinary_hit_byte_identical(monkeypatch):
    """Spot-check of the never-displaces law through the real cascade: an
    ordinary pinned hit evaluates canonically identical with the rescue on
    (the rescue can only run where the walk elected nothing)."""
    frames, baseline = _load_marks_fixture()
    e = next(x for x in baseline["setups"]
             if x["status"] == "hit" and x["key"].startswith("VLO"))
    sliced = fixture_frame(frames, e["key"], e["ticker"]).loc[
        :pd.Timestamp(e["first_fire"])]
    spy = float(e["spy_6m_return"])
    monkeypatch.setattr(settings, "CONTRACTION_RESCUE_ENABLED", False)
    off = _evaluate_ticker(e["ticker"], sliced, spy, _FROZEN_BREADTH)
    monkeypatch.setattr(settings, "CONTRACTION_RESCUE_ENABLED", True)
    on = _evaluate_ticker(e["ticker"], sliced, spy, _FROZEN_BREADTH)
    assert isinstance(off, dict) and isinstance(on, dict)
    assert shadow_diff.canonical_fields(off) == shadow_diff.canonical_fields(on)


# ────────────────────────── lane 2: the 50-day dip exception ────────────────

def _ohlcv(closes, vol=100_000.0):
    closes = np.asarray(closes, dtype=float)
    return pd.DataFrame(
        {"Open": closes, "High": closes + 0.10, "Low": closes - 0.10,
         "Close": closes, "Volume": vol},
        index=pd.bdate_range("2025-01-01", periods=len(closes)))


def _rising(n=260, start=8.0, step=0.02):
    return start + step * np.arange(n)


def _door_margins(df):
    """The frame's own sma50 margin facts, computed the way the gate does."""
    from engine_alpha.structure import calculate_atr

    close = df["Close"]
    sma50 = close.rolling(50).mean()
    above = (close >= sma50).values
    hits = above.nonzero()[0]
    since = len(above) - 1 - int(hits[-1]) if len(hits) else None
    atr = float(calculate_atr(df, 10).iloc[-1])
    gap = float(sma50.iloc[-1]) - float(close.iloc[-1])
    return since, gap, atr


def test_dip_exception_flag_off_refuses_sma50_unchanged():
    closes = _rising()
    closes[-6:] = closes[-7] - 0.55        # recent shallow dip under the 50d
    df = _ohlcv(closes)
    since, gap, atr = _door_margins(df)
    assert since is not None and 0 < since <= settings.SMA50_DIP_MAX_SESSIONS
    assert 0 < gap <= settings.SMA50_DIP_MAX_ATR * atr
    assert settings.SMA50_DIP_EXCEPTION_ENABLED is False
    result, reason = apply_baseline_filters_with_reason(df)
    assert result is None and reason[0] == "sma50"


def test_dip_exception_admits_a_recent_shallow_dip(monkeypatch):
    monkeypatch.setattr(settings, "SMA50_DIP_EXCEPTION_ENABLED", True)
    closes = _rising()
    closes[-6:] = closes[-7] - 0.55
    df = _ohlcv(closes)
    since, gap, atr = _door_margins(df)
    assert since is not None and 0 < since <= settings.SMA50_DIP_MAX_SESSIONS
    assert 0 < gap <= settings.SMA50_DIP_MAX_ATR * atr
    result, reason = apply_baseline_filters_with_reason(df)
    assert reason is None and result is not None, (
        "a bounded, recent, recovered dip must enter chart reading")


def test_dip_exception_refuses_a_deep_dip(monkeypatch):
    monkeypatch.setattr(settings, "SMA50_DIP_EXCEPTION_ENABLED", True)
    closes = _rising()
    closes[-6:] = closes[-7] - 1.60        # still far under the 50-day
    df = _ohlcv(closes)
    since, gap, atr = _door_margins(df)
    assert gap > settings.SMA50_DIP_MAX_ATR * atr, "construction drifted"
    result, reason = apply_baseline_filters_with_reason(df)
    assert result is None and reason[0] == "sma50"


def test_dip_exception_refuses_an_old_dip(monkeypatch):
    monkeypatch.setattr(settings, "SMA50_DIP_EXCEPTION_ENABLED", True)
    closes = _rising()
    # a 40-session sag, gently declining so the close stays under the 50-day
    closes[-40:] = closes[-41] - 0.55 - 0.005 * np.arange(40)
    df = _ohlcv(closes)
    since, gap, atr = _door_margins(df)
    assert since is not None and since > settings.SMA50_DIP_MAX_SESSIONS, (
        "construction drifted")
    assert gap > 0, "construction drifted (close must still sit under sma50)"
    result, reason = apply_baseline_filters_with_reason(df)
    assert result is None and reason[0] == "sma50"


def test_dip_exception_refuses_a_frame_never_above_the_50d(monkeypatch):
    monkeypatch.setattr(settings, "SMA50_DIP_EXCEPTION_ENABLED", True)
    closes = 14.0 - 0.02 * np.arange(260)   # monotone decline: never above
    df = _ohlcv(closes)
    since, _, _ = _door_margins(df)
    assert since is None, "construction drifted"
    result, reason = apply_baseline_filters_with_reason(df)
    assert result is None and reason[0] == "sma50"


def test_dip_exception_never_opens_the_sma200_leg(monkeypatch):
    """A dip exception is not a downtrend exception: a qualifying sma50 dip
    on a frame still under the 200-day is refused by the sma200 leg."""
    monkeypatch.setattr(settings, "SMA50_DIP_EXCEPTION_ENABLED", True)
    n = 260
    closes = np.empty(n)
    closes[:200] = np.linspace(20.0, 10.0, 200)      # long decline
    closes[200:] = np.linspace(10.0, 12.0, n - 200)  # young recovery
    closes[-4:] = closes[-5] - 1.0                   # fresh dip under the 50d
    df = _ohlcv(closes)
    since, gap, atr = _door_margins(df)
    assert since is not None and 0 < since <= settings.SMA50_DIP_MAX_SESSIONS
    assert 0 < gap <= settings.SMA50_DIP_MAX_ATR * atr
    sma200 = float(df["Close"].rolling(200).mean().iloc[-1])
    assert float(df["Close"].iloc[-1]) < sma200, "construction drifted"
    result, reason = apply_baseline_filters_with_reason(df)
    assert result is None and reason[0] == "sma200"


def test_dip_exception_lets_skyt_fire_end_to_end(monkeypatch):
    """SKYT@2026-04-13 (sealed expected-miss, stage universe-gate): the drawn
    spring dragged price under the 50-day; with the exception on, the
    2026-04-07 session elects a COMPLETE strict-pool structure and fires
    tier S — the universe door was that day's only wall."""
    frames, baseline = _load_marks_fixture()
    e = next(x for x in baseline["setups"] if x["key"] == "SKYT:2026-04-13")
    assert e["status"] == "miss" and e["stage"] == "universe-gate"
    sliced = fixture_frame(frames, e["key"], "SKYT").loc[
        :pd.Timestamp("2026-04-07")]

    monkeypatch.setattr(settings, "SMA50_DIP_EXCEPTION_ENABLED", False)
    off = _evaluate_ticker("SKYT", sliced, 0.0, _FROZEN_BREADTH)
    assert not isinstance(off, dict)

    monkeypatch.setattr(settings, "SMA50_DIP_EXCEPTION_ENABLED", True)
    on = _evaluate_ticker("SKYT", sliced, 0.0, _FROZEN_BREADTH)
    assert isinstance(on, dict), "SKYT's door conversion no longer fires"
    assert on["_elected_pool"] == "strict"
    assert on["Tier"] == "S"


def test_dip_exception_lets_st_fire_end_to_end(monkeypatch):
    """ST@2026-04-17: the 2026-04-06 session — the day before its drawn SOS
    ignites — is sma50-refused by −1.7% (0.38 ATR, 6 sessions since above);
    through the exception the pre-SOS shelf completes and fires tier S
    (strict pool). The harness grades the live mark converted on this fire."""
    frames, baseline = _load_marks_fixture()
    e = next(x for x in baseline["setups"] if x["key"] == "ST:2026-04-17")
    sliced = fixture_frame(frames, e["key"], "ST").loc[
        :pd.Timestamp("2026-04-06")]

    monkeypatch.setattr(settings, "SMA50_DIP_EXCEPTION_ENABLED", False)
    off = _evaluate_ticker("ST", sliced, 0.0, _FROZEN_BREADTH)
    assert not isinstance(off, dict)

    monkeypatch.setattr(settings, "SMA50_DIP_EXCEPTION_ENABLED", True)
    on = _evaluate_ticker("ST", sliced, 0.0, _FROZEN_BREADTH)
    assert isinstance(on, dict), "ST's door conversion no longer fires"
    assert on["_elected_pool"] == "strict"
    assert on["Tier"] == "S"
