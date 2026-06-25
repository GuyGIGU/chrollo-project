"""Unit tests for the PIP (Perceptually Important Points) swing skeleton.

Pure-function contract only — PIP is measure-only and nothing live consumes it.
"""
import numpy as np

from core.structure.pip import pip_indices, pip_pivots, pip_skeleton


def test_pip_indices_picks_biggest_swing_first():
    # Two humps; the index-4 spike (10) dwarfs the index-1/7 bumps (3).
    P = [0, 3, 0, 0, 10, 0, 0, 3, 0]
    idx = pip_indices(P, n_points=3)
    # order = [endpoint0, endpointN-1, most-important-interior]
    assert idx[0] == 0 and idx[1] == len(P) - 1
    assert idx[2] == 4                       # the tallest deviation is chosen first


def test_pip_indices_multi_resolution_is_nested():
    P = [0, 3, 0, 1, 10, 1, 0, 6, 0, 2, 0]
    coarse = pip_indices(P, n_points=4)
    fine = pip_indices(P, n_points=7)
    # Greedy global pick is target-independent -> the coarse skeleton is an exact
    # prefix of the fine one (top-K subset of top-(K+1)).
    assert fine[:len(coarse)] == coarse
    assert set(coarse).issubset(set(fine))


def test_pip_pivots_alternate_and_snap_to_high_low():
    # P (hl2) zigzags; High = P+0.5, Low = P-0.5 so snap is observable.
    P = np.array([0.0, 5.0, 1.0, 6.0, 0.0])
    highs = P + 0.5
    lows = P - 0.5
    zz = pip_pivots(highs, lows, n_points=5)

    assert len(zz) >= 3
    kinds = [k for _, k, _ in zz]
    assert all(kinds[i] != kinds[i + 1] for i in range(len(kinds) - 1))  # strict alternation
    for bar, kind, price in zz:
        if kind == "peak":
            assert price == highs[bar]      # peaks snap to the High
        else:
            assert price == lows[bar]       # valleys snap to the Low


def test_pip_pivots_flat_series_is_empty():
    flat = np.full(20, 50.0)
    assert pip_pivots(flat, flat, n_points=10) == []


def test_pip_pivots_too_few_bars_is_empty():
    assert pip_pivots(np.array([10.0, 11.0]), np.array([9.0, 10.0]), n_points=5) == []


def test_pip_indices_dist_min_limits_selection():
    # One large swing (index 4) + tiny wiggles. A dist_min above the wiggles'
    # relative size keeps only the dominant turn, fewer than the n_points cap.
    P = [0, 0.2, 0, 0.1, 10, 0.1, 0, 0.2, 0]
    idx = pip_indices(P, n_points=8, dist_min=0.30)
    assert 4 in idx                          # the dominant turn survives
    assert len(idx) < 8                       # the floor stopped it before the cap


def test_pip_skeleton_returns_each_level():
    rng = np.linspace(0, 1, 60)
    highs = 100 + 10 * np.sin(rng * 12) + 0.5
    lows = 100 + 10 * np.sin(rng * 12) - 0.5
    import pandas as pd
    df = pd.DataFrame({"High": highs, "Low": lows})
    sk = pip_skeleton(df, levels=(5, 15, 30))
    assert set(sk.keys()) == {5, 15, 30}
    # finer levels resolve at least as many turning points as coarser ones
    assert len(sk[30]) >= len(sk[5]) >= 2
