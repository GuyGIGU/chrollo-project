"""The refusal-naming read + the knob pair table (consolidation-method
Task 15): hermetic pins on the ONE implementation the workbench serves and
the instrument delegates to.

* the leg table derives from ``GATE_LEGS`` (all 15, registry order, each
  record carrying measured + threshold as numbers);
* THE blocking leg is the FIRST refusal in the ladder's own order, rendered
  through the one operator-language vocabulary;
* unreadable geometry returns None whole (the three-state law — never a
  fabricated diagnosis);
* the CRASH leg decides exactly as the election gate decides — same
  NaN-skipping minimum, same multiplication form (council review 2026-09-01,
  finding 8: the re-typed twin named crash as THE blocking leg on windows the
  real ladder passes);
* the episode read is served in plain trading words, always a closed value;
* the what-if flip list derives from the registry's own comparison (EC-43).
"""
from __future__ import annotations

import sys

import numpy as np
import pandas as pd
import pytest

from _paths import REPO_ROOT as ROOT
sys.path.insert(0, str(ROOT))

from config import settings
from engine_alpha.structure.box.box_gates import GATE_LEGS, _validate_base_quality
from engine_alpha.structure.metrics.base import _episode_summary, mark_refusal_read


def _flat_window(n=40, close=105.0, spread=0.5):
    closes = np.full(n, close)
    idx = pd.bdate_range("2026-01-05", periods=n)
    return pd.DataFrame({"Open": closes, "High": closes + spread,
                         "Low": closes - spread, "Close": closes,
                         "Volume": np.full(n, 1e6)}, index=idx)


def _crash_ok(read):
    """The mirror's crash verdict, off the served leg table."""
    return next(rec for rec in read["legs"] if rec["leg"] == "crash")["ok"]


def _gate_crash_ok(win, R, S, atr):
    """The ELECTION GATE's own crash verdict, read from the real function:
    ``_validate_base_quality`` returns a NULL residence dict exactly when it
    rejected on width or crash, so with the width leg known to pass, a
    non-None ``eq`` IS "crash passed". No third typing of the predicate."""
    _r, _s, eq, _valid = _validate_base_quality(win, R, S, atr)
    return eq is not None


def test_unreadable_geometry_returns_none_whole():
    win = _flat_window()
    assert mark_refusal_read(win, 100.0, 110.0, 1.0) is None      # R <= S
    assert mark_refusal_read(win, 110.0, 100.0, None) is None     # no ATR
    assert mark_refusal_read(win, 110.0, 100.0, float("nan")) is None
    assert mark_refusal_read(win.iloc[0:0], 110.0, 100.0, 1.0) is None


def test_leg_table_is_the_registry_in_ladder_order():
    read = mark_refusal_read(_flat_window(), 110.0, 100.0, 1.0)
    assert read is not None
    assert [rec["leg"] for rec in read["legs"]] == [s.leg for s in GATE_LEGS]
    for rec in read["legs"]:
        assert "measured" in rec and "threshold" in rec
        assert isinstance(rec["ok"], bool)


def test_blocking_leg_is_the_first_refusal_in_ladder_order():
    # A flat mid-box window: width/window/respect/crash all pass, the rails
    # are never touched — the FIRST refusing leg in the ladder is r_touches,
    # and it must be THE named one (the EGBN pattern: one leg, his value vs
    # the floor), spoken in the operator-language vocabulary.
    read = mark_refusal_read(_flat_window(), 110.0, 100.0, 1.0)
    by_leg = {rec["leg"]: rec for rec in read["legs"]}
    for leg in ("width", "window", "respect_share", "respect_run", "crash"):
        assert by_leg[leg]["ok"], f"{leg} should pass on the flat window"
    assert not by_leg["r_touches"]["ok"]
    assert read["blocking_leg"]["leg"] == "r_touches"
    assert read["refused_legs"][0] == "r_touches"
    assert isinstance(read["blocking_sentence"], str)
    assert read["blocking_sentence"]


def test_the_sentence_rides_the_read():
    read = mark_refusal_read(_flat_window(), 110.0, 100.0, 1.0)
    assert isinstance(read["sentence"], str)          # may be "" (no episodes)
    assert isinstance(read["completed_s"], int)
    assert isinstance(read["completed_r"], int)
    assert isinstance(read["terminal_r_engagement"], bool)


# ── the crash leg decides as the gate decides (finding 8) ────────────────────


def test_crash_leg_agrees_with_the_gate_on_a_nan_low():
    """A damaged-data window — one NaN low, every real low far above the crash
    floor. The gate's pandas ``.min()`` SKIPS the NaN and passes; the retired
    ``np.min`` twin propagated it and named crash as THE blocking leg on
    exactly the windows the operator most needs the truth about."""
    win = _flat_window()
    win.loc[win.index[7], "Low"] = np.nan
    R, S, atr = 110.0, 100.0, 1.0
    read = mark_refusal_read(win, R, S, atr)
    assert _gate_crash_ok(win, R, S, atr) is True
    assert _crash_ok(read) is True
    assert "crash" not in read["refused_legs"]
    assert read["blocking_leg"]["leg"] != "crash"


def test_crash_leg_agrees_with_the_gate_on_a_real_crash():
    win = _flat_window()
    R, S, atr = 110.0, 100.0, 1.0
    win.loc[win.index[9], "Low"] = S * settings.CRASH_FILTER_MULT - 1.0
    read = mark_refusal_read(win, R, S, atr)
    assert _gate_crash_ok(win, R, S, atr) is False
    assert _crash_ok(read) is False
    assert read["blocking_leg"]["leg"] == "crash"   # first refusal in the ladder


def test_crash_leg_agrees_with_the_gate_at_the_razor_edge():
    """A low sitting EXACTLY on the gate's boundary. The gate refuses on
    ``low < S * mult``, so the boundary itself PASSES — and the division form
    the mirror used to carry flips it: at S=12.00 today, (S*0.70)/S rounds to
    0.6999999999999998, one ulp under the floor. Same arithmetic, same
    verdict, on both sides of the edge."""
    R, S, atr = 13.0, 12.0, 0.25
    edge = S * settings.CRASH_FILTER_MULT
    win = _flat_window(close=12.5, spread=0.5)
    win.loc[win.index[11], "Low"] = edge
    read = mark_refusal_read(win, R, S, atr)
    assert _gate_crash_ok(win, R, S, atr) is True
    assert _crash_ok(read) is True

    below = win.copy()
    below.loc[below.index[11], "Low"] = np.nextafter(edge, 0.0)
    read_below = mark_refusal_read(below, R, S, atr)
    assert _gate_crash_ok(below, R, S, atr) is False
    assert _crash_ok(read_below) is False


# ── the episode read speaks plain trading words (finding 3 / Dodds P3) ───────


def test_episode_summary_is_always_a_closed_plain_words_value():
    assert _episode_summary(0, 0) == "no completed tests yet"
    assert _episode_summary(1, 0) == "1 completed test at resistance"
    assert _episode_summary(0, 2) == "2 completed tests at support"
    assert _episode_summary(2, 1) == "2 completed tests at resistance, 1 at support"


def test_the_read_serves_the_summary_beside_the_raw_tape():
    """The raw profile tape stays for machine consumers; the plain-words
    clause is the one an operator surface may render, and it is NEVER empty
    (the no-episodes state is a value here, not a client-side fallback)."""
    read = mark_refusal_read(_flat_window(), 110.0, 100.0, 1.0)
    assert isinstance(read["sentence"], str)
    assert read["episode_summary"]
    assert read["episode_summary"] == _episode_summary(read["completed_r"],
                                                       read["completed_s"])


def test_what_if_flip_list_derives_from_the_registry(monkeypatch):
    from tools.calibration.knob_pair_table import what_if_flips

    rows = [
        {"ticker": "EGBN", "as_of": "2026-01-07", "legs": [
            {"leg": "lower_dwell", "measured": 0.118, "threshold": 0.15,
             "ok": False}]},
        {"ticker": "VLO", "as_of": "2026-03-02", "legs": [
            {"leg": "lower_dwell", "measured": 0.30, "threshold": 0.15,
             "ok": True}]},
    ]
    flips = what_if_flips(rows, "lower_dwell", 0.10)
    assert flips["newly_admitted"] == ["EGBN@2026-01-07 (0.12)"]
    assert flips["newly_refused"] == []
    flips = what_if_flips(rows, "lower_dwell", 0.35)
    assert flips["newly_admitted"] == []
    assert flips["newly_refused"] == ["VLO@2026-03-02 (0.30)"]
    with pytest.raises(KeyError):
        what_if_flips(rows, "not_a_leg", 0.1)


def test_the_flip_list_prints_formatted_numbers_never_a_raw_float():
    """The flip list is the exact artifact a threshold ruling is read from, so
    every number in it rides the shared formatter — the proposed floor and all
    its flipped marks as ONE block (council review 2026-09-01, finding 3;
    completeness pass 2026-09-01 — the raw float was deferred and left
    unpinned, then the pair form collapsed distinct marks). Three shapes: an
    ugly float rounds to the native quantum, a hinge mark widens rather than
    read as the proposal itself — and the floor widens with it, so the printed
    line is never arithmetically impossible — and a counted leg stays a
    count."""
    from tools.calibration.knob_pair_table import what_if_flips

    ugly = [{"ticker": "VLO", "as_of": "2026-03-02", "legs": [
        {"leg": "lower_dwell", "measured": 0.1 + 0.2, "threshold": 0.15,
         "ok": True}]}]
    assert repr(0.1 + 0.2) == "0.30000000000000004"      # what a raw print gave
    assert what_if_flips(ugly, "lower_dwell", 0.35)["newly_refused"] == [
        "VLO@2026-03-02 (0.30)"]

    hinge = [{"ticker": "HNG", "as_of": "2026-02-10", "legs": [
        {"leg": "lower_dwell", "measured": 0.1449, "threshold": 0.10,
         "ok": True}]}]
    hinge_flips = what_if_flips(hinge, "lower_dwell", 0.145)
    assert hinge_flips["newly_refused"] == [
        "HNG@2026-02-10 (0.1449)"]                       # never "(0.14)" -> 0.14
    assert hinge_flips["proposed_shown"] == "0.1450"     # the floor, same block

    counted = [{"ticker": "WIN", "as_of": "2026-02-11", "legs": [
        {"leg": "window", "measured": 41, "threshold": 30, "ok": True}]}]
    assert what_if_flips(counted, "window", 45)["newly_refused"] == [
        "WIN@2026-02-11 (41)"]                           # never "41.00"
