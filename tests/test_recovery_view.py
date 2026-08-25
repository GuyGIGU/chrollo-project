"""The recovery view's battery (story-chain program Task 7).

Pins the stated conventions: prefix-true shakeout low (the edge reserve is
honored), committed-only intervening tests (the causality stamps), inclusive
band edges on the operator's own destination vocabulary, all-None refusals,
and the pivots reuse seam. The numeric band edges are v1 first-cuts — the
raw operands ride the result precisely so the census can re-band offline.
"""
import numpy as np
import pandas as pd

from engine_alpha.structure.event_map import (
    RECOVERY_CHARACTERS,
    RECOVERY_DESTINATIONS,
    read_recovery_view,
)
from engine_alpha.structure.pivots import _find_pivots

R, S, ATR = 110.0, 100.0, 2.0     # parent rails; tol = 2.0, min_amp = 1.5


def _frame(closes, *, band=1.0):
    idx = pd.bdate_range("2025-01-02", periods=len(closes))
    c = np.asarray(closes, dtype=float)
    return pd.DataFrame({"Open": c, "High": c + band, "Low": c - band,
                         "Close": c, "Volume": np.full(len(c), 1e6)}, index=idx)


def _staircase_frame():
    """Undercut at bar 10, shakeout low 94 at bar 12, a two-leg recovery
    with one committed test valley (bar 18), back above the floor."""
    return _frame([105.0] * 10                     # the box era
                  + [97.0, 96.0, 95.0]             # undercut -> low 94 @ bar 12
                  + [98.0, 100.0, 101.0, 102.0]    # leg 1
                  + [100.0, 98.5, 100.0]           # the test valley @ bar 18
                  + [102.0, 104.0, 106.0, 106.0]   # leg 2 -> high 107 @ bar 22
                  + [104.0] * 4                    # the read edge (close 104)
                  + [104.0] * 5)                   # the reserve


def test_staircase_recovery_back_inside():
    out = read_recovery_view(_staircase_frame(), R, S, 10, ATR)
    assert out["character"] == "staircase"
    assert out["destination"] == "back_inside"
    assert out["shakeout_low_bar"] == 12
    assert out["shakeout_low"] == 94.0
    assert out["n_intervening_valleys"] == 1
    assert out["recovery_frac"] > 1.0             # raw, unclamped by design
    assert out["character"] in RECOVERY_CHARACTERS
    assert out["destination"] in RECOVERY_DESTINATIONS


def test_one_swing_recovery_sitting_below():
    df = _frame([105.0] * 10 + [96.0, 95.0, 94.0]           # low 93 @ bar 12
                + [95.0, 96.0, 97.0, 98.0, 99.0]            # one direct leg
                + [98.0] * 4 + [98.0] * 5)
    out = read_recovery_view(df, R, S, 10, ATR)
    assert out["character"] == "one_swing"
    assert out["n_intervening_valleys"] == 0
    assert out["destination"] == "sitting_below"  # 98: above 95, below the floor


def test_no_recovery_at_the_bottom():
    df = _frame([105.0] * 10 + [95.0, 93.0, 92.0]           # low 91 @ bar 12
                + [92.5] * 8 + [92.5] * 5)
    out = read_recovery_view(df, R, S, 10, ATR)
    assert out["character"] == "none"
    assert out["destination"] == "at_the_bottom"


def test_band_edges_are_inclusive_as_stated():
    # the read edge exactly AT the old floor: back inside (inclusive)
    at_floor = _frame([105.0] * 10 + [96.0, 95.0, 94.0]     # low 93
                      + [95.0, 97.0, 99.0, 101.0]           # recovers past S
                      + [100.0] * 4 + [100.0] * 5)
    assert read_recovery_view(at_floor, R, S, 10, ATR)["destination"] == "back_inside"
    # the read edge exactly at shakeout_low + tol: still at the bottom
    at_seam = _frame([105.0] * 10 + [96.0, 95.0, 94.0]      # low 93; seam 95
                     + [94.0, 95.5, 96.5, 96.0]
                     + [95.0] * 4 + [95.0] * 5)
    assert read_recovery_view(at_seam, R, S, 10, ATR)["destination"] == "at_the_bottom"


def test_edge_reserve_never_moves_the_shakeout_low():
    df = _staircase_frame()
    df.iloc[-2, df.columns.get_loc("Low")] = 80.0           # deeper low, in reserve
    out = read_recovery_view(df, R, S, 10, ATR)
    assert out["shakeout_low"] == 94.0                      # prefix truth holds


def test_refusals_are_all_none_never_fabricated():
    never_under = _frame([105.0] * 30)                      # floor never broken
    out = read_recovery_view(never_under, R, S, 10, ATR)
    assert out["character"] is None and out["destination"] is None
    bad_atr = read_recovery_view(_staircase_frame(), R, S, 10, 0.0)
    assert bad_atr["character"] is None
    too_late = read_recovery_view(_staircase_frame(), R, S, 10 ** 6, ATR)
    assert too_late["character"] is None


def test_nan_bars_refuse_instead_of_fabricating():
    """Unreadable bars fail CLOSED (the depth guard's own direction): a NaN
    recovery high or read-edge close refuses the view, and the readability
    companion counts unreadable closes too."""
    df = _staircase_frame()
    df.iloc[22, df.columns.get_loc("High")] = np.nan    # argmax lands on it
    assert read_recovery_view(df, R, S, 10, ATR)["character"] is None
    df = _staircase_frame()
    edge = len(df) - 6                                  # eval_end - 1 (skip 5)
    df.iloc[edge, df.columns.get_loc("Close")] = np.nan
    assert read_recovery_view(df, R, S, 10, ATR)["character"] is None
    df = _staircase_frame()
    df.iloc[15, df.columns.get_loc("Close")] = np.nan   # mid-window close
    assert read_recovery_view(df, R, S, 10, ATR)["nan_bars"] == 1


def test_pivots_reuse_seam_matches_the_internal_walk():
    df = _staircase_frame()
    highs = df["High"].values.astype(float)
    lows = df["Low"].values.astype(float)
    walked = _find_pivots(highs, lows, 1)
    a = read_recovery_view(df, R, S, 10, ATR)
    b = read_recovery_view(df, R, S, 10, ATR, pivots=walked)
    assert a == b
