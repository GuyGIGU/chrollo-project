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
* end-to-end on the corpus: the rescue converts EGBN, stamped
  ``elected_pool='story'`` with the self-naming contraction profile. The
  operator ruled TWO conversions ("BOTH have setups on these days so yeah",
  2026-08-19); the second, PKE:2026-02-24, left when he deleted that drawing and
  redrew the setup at 2026-04-07, which now fires at baseline (2026-09-08).

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
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

from _paths import REPO_ROOT as ROOT
sys.path.insert(0, str(ROOT))

from config import settings
from core.pipeline.screening.screener import _evaluate_ticker
from engine_alpha.evaluation import apply_baseline_filters_with_reason
from engine_alpha.structure.events.event_map import (
    ADMISSION_FORM_RESISTANCE_CONTRACTION,
)
from engine_alpha.structure.narrative.reader import Structure, read_structure
from tools.regression import shadow_diff
from tools.regression.marks_corpus import _FROZEN_BREADTH
from tools.regression.marks_corpus import _load_fixture as _load_marks_fixture
from core.calibration.replay import fixture_frame

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
    """Full refusal on the baseline walk; a complete story once the
    resistance-contraction form arrives in the walk's EXPLICIT armed-form
    roster (consolidation-method Task 4 — the rescue hands the roster down,
    never a settings mutation) — the scripted shape of a contraction-rescue
    conversion."""

    def find_root_swing(self, df, search_from_bar, atr):
        if search_from_bar == 0:
            self.walks += 1
        if search_from_bar > 10:
            return None
        return SimpleNamespace(climax_bar=10, ar_bar=20, R=110.0, S=100.0)

    def validate_equilibrium(self, df, root, atr, trace=None, forms=None):
        if forms is None or ADMISSION_FORM_RESISTANCE_CONTRACTION not in forms:
            return None
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
    """Elects the same complete story regardless of the armed roster."""

    def validate_equilibrium(self, df, root, atr, trace=None, forms=None):
        return SimpleNamespace(S=100.0, R=110.0, start_bar=20, box_width=0.10)


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
        "the rescue must arm the roster it hands down, never the settings "
        "flag — a mutated flag means the retired override smuggle returned")


def test_rescue_trace_stamps_the_second_pass(monkeypatch):
    monkeypatch.setattr(settings, "CONTRACTION_RESCUE_ENABLED", True)
    trace: list = []
    s = read_structure(None, 1.0, bricks=_FormSensitiveBricks(), trace=trace)
    assert isinstance(s, Structure)
    assert trace, "the rescue pass should narrate its walk"
    stamped = [rec for rec in trace if rec.get("pass") == "contraction_rescue"]
    assert stamped, "every second-pass trace record carries the rescue stamp"
    assert any("pass" not in rec for rec in trace), (
        "the baseline walk narrates its refusal too — unstamped")
    first = trace.index(stamped[0])
    assert all(rec.get("pass") == "contraction_rescue"
               for rec in trace[first:]), (
        "the rescue stamp must partition the tape: everything after the "
        "first stamped record belongs to the second pass")
    assert trace[-1]["outcome"] == "complete"
    assert trace[-1].get("pass") == "contraction_rescue"


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
    # PKE:2026-02-24 was the second ruled conversion. The operator DELETED that
    # drawing and redrew the setup at 2026-04-07, which the engine now fires at
    # BASELINE (tier B, first fire 2026-03-26) — so PKE no longer needs rescuing
    # and its half of this guard retired with the mark on 2026-09-08, when the
    # standard began following his current drawings.
    # RECORDED, because it is a real loss and not housekeeping: the
    # contraction-rescue flag is still dark awaiting his ruling (docs/asks.md),
    # and the ruling he gave it — "BOTH have setups on these days so yeah",
    # 2026-08-19 — cited both specimens. Half its end-to-end evidence is gone.
    for key, fire_day, tier in [("EGBN:2026-01-15", "2026-01-07", "A")]:
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


# ──────────────── lane 3: the ceiling-rest LPS exception (2026-08-29) ───────

def test_ceiling_rest_lets_nok_fire_end_to_end(monkeypatch):
    """NOK@2026-02-17 (sealed expected-miss): the walk elects his box at his
    exact resistance and dies at ONE leg — the after-SOS rest that launched
    above R. With the ceiling-rest exception on (rest 0.241 ATR under R,
    drawn-cluster bar 0.3 — junk ENIC sits at 0.314 and is pinned rejecting
    in test_negative_corpus), the 2026-02-13 session completes and fires
    tier B through the ordinary strict pool."""
    frames, baseline = _load_marks_fixture()
    e = next(x for x in baseline["setups"] if x["key"] == "NOK:2026-02-17")
    assert e["status"] == "miss"
    sliced = fixture_frame(frames, e["key"], "NOK").loc[
        :pd.Timestamp("2026-02-13")]

    monkeypatch.setattr(settings, "LPS_CEILING_REST_ENABLED", False)
    off = _evaluate_ticker("NOK", sliced, 0.0, _FROZEN_BREADTH)
    assert not isinstance(off, dict)

    monkeypatch.setattr(settings, "LPS_CEILING_REST_ENABLED", True)
    on = _evaluate_ticker("NOK", sliced, 0.0, _FROZEN_BREADTH)
    assert isinstance(on, dict), "NOK's ceiling-rest conversion no longer fires"
    assert on["_elected_pool"] == "strict"
    assert on["Tier"] == "B"


def _ceiling_rest_frame(rest_low: float):
    """A launched-above-R window resting at ``rest_low``: 24 quiet bars just
    above R, then a 3-bar giveback (highs 106/104/102 descending, lows
    descending into the rest). Window low is always the LAST bar's low, so
    every scanned window reaches the launch-above-resistance leg with
    support_low = rest_low."""
    n = 27
    highs = [101.8] * (n - 3) + [106.0, 104.0, 102.0]
    lows = [100.8] * (n - 3) + [101.0, 100.2, rest_low]
    closes = [101.2] * (n - 3) + [103.0, 101.0, min(100.9, rest_low + 1.0)]
    idx = pd.bdate_range("2026-01-05", periods=n)
    return pd.DataFrame({"Open": closes, "High": highs, "Low": lows,
                         "Close": closes, "Volume": [1e6] * n}, index=idx)


def test_ceiling_rest_razor_sanctions_just_inside_and_refuses_just_outside(monkeypatch):
    """The 0.3-ATR razor at unit grain (council review 2026-08-30, Beck): a
    rest just INSIDE the band is sanctioned (the launch-refusal leg does not
    fire) and a rest just OUTSIDE stays refused — each side construction-
    verified from the frame + settings (the lane-2 self-verifying pattern),
    so a drifted construction or a moved razor fails loudly. The corpus-wide
    ENIC boolean cannot carry this alone: if ENIC ever refuses at an earlier
    leg, the razor's refusing side would lose its only witness silently."""
    from engine_alpha.structure.lps.detection import detect_lps_candidates

    sup_avg, res_avg, atr = 90.0, 100.0, 2.0
    box_height = res_avg - sup_avg
    razor = settings.LPS_CEILING_REST_MAX_BELOW_R_ATR * atr
    inside_low = res_avg - 0.25 * atr          # 0.5 under R, inside the band
    outside_low = res_avg - 0.65 * atr         # 1.3 under R, outside it

    def _launch_rejects(rest_low, flag):
        df = _ceiling_rest_frame(rest_low)
        # Construction checks BEFORE the verdict (self-verifying):
        whigh = float(df["High"].iloc[-3:].max())
        assert (whigh - res_avg) / box_height > settings.LPS_INSIDE_HIGH_EXTENSION_BOX_MAX
        assert (whigh - res_avg) / atr > settings.LPS_INSIDE_HIGH_EXTENSION_ATR_MAX
        assert float(df["Low"].iloc[-1]) == rest_low
        assert sup_avg < rest_low < res_avg     # the INSIDE zone
        monkeypatch.setattr(settings, "LPS_CEILING_REST_ENABLED", flag)
        _cands, rejects = detect_lps_candidates(
            df, df.iloc[-1], sup_avg, res_avg, atr,
            base_range_threshold=1.2 * atr, base_len=25,
            swing_complete_idx=0, offset_max=1, diagnose=True)
        return rejects["window launched above resistance"]

    assert 0 < res_avg - inside_low < razor, "construction drifted"
    assert res_avg - outside_low > razor, "construction drifted"

    # Flag ON: the razor separates the pair.
    assert _launch_rejects(inside_low, True) == 0, (
        "a rest inside the razor must be sanctioned by the exception")
    assert _launch_rejects(outside_low, True) >= 1, (
        "a rest outside the razor must stay refused — the razor widened")
    # Flag OFF: the inside rest is refused exactly as before (inert lane).
    assert _launch_rejects(inside_low, False) >= 1


# ──────────────── lane 4: the bottoming-base lane (2026-08-29) ──────────────

def _v_recovery_frame():
    """An MDT-shaped tape: a high plateau still inside the 200-day window, a
    deep decline, then a young base whose close has reclaimed the 50-day but
    still sits under the 200-day."""
    n = 260
    closes = np.empty(n)
    closes[:160] = 13.0
    closes[160:200] = np.linspace(13.0, 8.0, 40)
    closes[200:] = np.linspace(8.2, 8.7, 60)
    return _ohlcv(closes)


def test_bottoming_lane_opens_the_sma200_leg_and_the_next_leg_still_gates(monkeypatch):
    df = _v_recovery_frame()
    close = df["Close"]
    sma50 = float(close.rolling(50).mean().iloc[-1])
    sma200 = float(close.rolling(200).mean().iloc[-1])
    assert sma50 <= float(close.iloc[-1]) < sma200, "construction drifted"

    monkeypatch.setattr(settings, "BOTTOMING_BASE_LANE_ENABLED", False)
    result, reason = apply_baseline_filters_with_reason(df)
    assert result is None and reason[0] == "sma200"

    # Flag on: the sma200 leg opens — and the frame's own deep-decline YoY
    # then refuses, proving the legs BEHIND the exception still gate.
    monkeypatch.setattr(settings, "BOTTOMING_BASE_LANE_ENABLED", True)
    result, reason = apply_baseline_filters_with_reason(df)
    assert result is None and reason[0] == "yoy", (
        "the exception must open exactly the sma200 leg, nothing more")


def test_bottoming_lane_requires_the_50d_reclaimed(monkeypatch):
    """A frame under BOTH smas can only reach the sma200 leg through the dip
    exception — and the bottoming condition (close >= SMA_50) must refuse it
    there. The two door lanes can never chain into admitting a chart that is
    under both rails."""
    monkeypatch.setattr(settings, "BOTTOMING_BASE_LANE_ENABLED", True)
    monkeypatch.setattr(settings, "SMA50_DIP_EXCEPTION_ENABLED", True)
    df = _v_recovery_frame()
    # A shallow, fresh dip under the 50-day: the dip exception admits it past
    # the sma50 leg; the bottoming exception must then refuse at sma200.
    sma50 = float(df["Close"].rolling(50).mean().iloc[-1])
    df.iloc[-1, df.columns.get_loc("Close")] = sma50 - 0.05
    df.iloc[-1, df.columns.get_loc("Low")] = sma50 - 0.15
    since, gap, atr = _door_margins(df)
    assert since is not None and 0 < since <= settings.SMA50_DIP_MAX_SESSIONS
    assert 0 < gap <= settings.SMA50_DIP_MAX_ATR * atr, "construction drifted"
    result, reason = apply_baseline_filters_with_reason(df)
    assert result is None and reason[0] == "sma200"


def test_bottoming_lane_opens_the_seeding_gate_under_the_same_condition(monkeypatch):
    """The sma200 rule's SECOND layer: collect_root_anchors refuses to seed
    any frame under its 200-bar SMA (`below_trend_sma`). The lane opens both
    layers together — same flag, same reclaimed-50-day condition."""
    from engine_alpha.structure.box.box_primitives import collect_root_anchors

    df = _v_recovery_frame()

    monkeypatch.setattr(settings, "BOTTOMING_BASE_LANE_ENABLED", False)
    trace: list = []
    assert collect_root_anchors(df, settings.MIN_BASE_DAYS, trace) == []
    assert any(r.get("leg") == "below_trend_sma" for r in trace)

    monkeypatch.setattr(settings, "BOTTOMING_BASE_LANE_ENABLED", True)
    trace = []
    collect_root_anchors(df, settings.MIN_BASE_DAYS, trace)
    assert not any(r.get("leg") == "below_trend_sma" for r in trace), (
        "the seeding gate must defer to the lane when the 50-day is reclaimed")

    # 50-day NOT reclaimed: the seeding gate stays shut even with the flag on.
    df2 = _v_recovery_frame()
    sma50 = float(df2["Close"].rolling(50).mean().iloc[-1])
    df2.iloc[-1, df2.columns.get_loc("Close")] = sma50 - 0.5
    trace = []
    assert collect_root_anchors(df2, settings.MIN_BASE_DAYS, trace) == []
    assert any(r.get("leg") == "below_trend_sma" for r in trace)


def test_bottoming_lane_never_seeds_a_nan_sma200_frame(monkeypatch):
    """A frame whose 200-bar mean is uncomputable is trend-UNKNOWN, not a
    bottoming base: the lane may open ONLY the known-below leg (council
    review 2026-08-30, McKinney — NaN-fail-closed doctrine). 60 bars: the
    50-bar mean is finite and reclaimed, the 200-bar mean is NaN."""
    from engine_alpha.structure.box.box_primitives import collect_root_anchors

    n = 60
    closes = np.linspace(10.0, 12.0, n)
    df = _ohlcv(closes)
    assert np.isnan(float(df["Close"].rolling(200).mean().iloc[-1]))
    sma50 = float(df["Close"].rolling(50).mean().iloc[-1])
    assert np.isfinite(sma50) and float(df["Close"].iloc[-1]) >= sma50

    monkeypatch.setattr(settings, "BOTTOMING_BASE_LANE_ENABLED", True)
    trace: list = []
    collect_root_anchors(df, settings.MIN_BASE_DAYS, trace)
    assert any(r.get("leg") == "below_trend_sma" for r in trace), (
        "a NaN-sma200 frame gained seeding rights through the lane")


def test_bottoming_lane_lets_mdt_fire_end_to_end(monkeypatch):
    """MDT@2026-07-14 — the ruled conversion itself, pinned through the real
    cascade (EC-17; council review 2026-08-30, Beck: the lane's core promise
    had no guard). The committed fixture is MDT's daily frame sliced to the
    census fire day (worktree 5y cache, edge 2026-08-27; MDT is not one of
    the sealed 33 marks, so the sealed corpus stays untouched — the
    cause_veto/power_play dedicated-fixture precedent). Flag off the sma200
    door refuses; flag on the frame elects R 82.83 — the operator's drawn
    resistance to the penny — and fires tier S through the ordinary strict
    pool."""
    fixture = ROOT / "tests" / "baselines" / "bottoming_base_fixture.parquet"
    df = pd.read_parquet(fixture, engine=settings.PARQUET_ENGINE)
    assert len(df) == 1227, "fixture basis drifted — rebuild deliberately"
    assert str(df.index[-1])[:10] == "2026-07-14"

    monkeypatch.setattr(settings, "BOTTOMING_BASE_LANE_ENABLED", False)
    off = _evaluate_ticker("MDT", df, 0.0, _FROZEN_BREADTH)
    assert not isinstance(off, dict)

    monkeypatch.setattr(settings, "BOTTOMING_BASE_LANE_ENABLED", True)
    on = _evaluate_ticker("MDT", df, 0.0, _FROZEN_BREADTH)
    assert isinstance(on, dict), "MDT's bottoming conversion no longer fires"
    assert on["_elected_pool"] == "strict"
    assert on["Tier"] == "S"
    assert on["_R"] == pytest.approx(82.83, abs=0.005)


def test_ceiling_rest_verdict_truth_table(monkeypatch):
    """The extracted pure judgment's ruling-sourced truth table
    (consolidation-method Task 11): the drawn class admits, the razor's
    boundary pair holds by name (NOK 0.241 IN, ENIC 0.314 OUT — the stated
    ~0.06-ATR razor each side), and the EC-54 rows fail closed — a missing
    or non-finite ATR refuses, and the dark flag refuses everything."""
    from engine_alpha.structure.lps.detection import _ceiling_rest_verdict

    R, atr = 100.0, 1.0
    monkeypatch.setattr(settings, "LPS_CEILING_REST_ENABLED", True)
    assert settings.LPS_CEILING_REST_MAX_BELOW_R_ATR == 0.3
    # The drawn class (rest depth in ATRs under R, per the ruling record).
    for depth in (0.010, 0.087, 0.148, 0.241):     # DSGN / MATX / MSGS / NOK
        assert _ceiling_rest_verdict(R - depth * atr, R, atr) is True, depth
    # The nearest labeled junk stays out.
    assert _ceiling_rest_verdict(R - 0.314 * atr, R, atr) is False  # ENIC
    # EC-54: affirmatively qualified — bad ATR refuses, never admits.
    assert _ceiling_rest_verdict(R - 0.1, R, None) is False
    assert _ceiling_rest_verdict(R - 0.1, R, float("nan")) is False
    assert _ceiling_rest_verdict(R - 0.1, R, 0.0) is False
    # Dark: the flag refuses everything (byte-identical lane).
    monkeypatch.setattr(settings, "LPS_CEILING_REST_ENABLED", False)
    assert _ceiling_rest_verdict(R - 0.010, R, atr) is False
