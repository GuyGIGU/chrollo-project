"""Unit tests for core.backtest.deflated_sharpe — FST / DSR / PBO."""
import math

import numpy as np

from core.backtest import deflated_sharpe as ds


def test_norm_helpers_roundtrip():
    assert abs(ds._norm_cdf(0.0) - 0.5) < 1e-9
    assert abs(ds._norm_ppf(0.975) - 1.959963985) < 1e-4
    assert abs(ds._norm_cdf(1.959963985) - 0.975) < 1e-4
    # ppf/cdf are inverses
    for p in (0.01, 0.2, 0.5, 0.8, 0.99):
        assert abs(ds._norm_cdf(ds._norm_ppf(p)) - p) < 1e-6


def test_expected_max_sharpe_grows_with_n_and_zero_for_one_trial():
    assert ds.expected_max_sharpe(1, 1.0) == 0.0
    vals = [ds.expected_max_sharpe(n, 1.0) for n in (2, 10, 100, 1000)]
    # Monotonically increasing in the number of trials.
    assert all(b > a for a, b in zip(vals, vals[1:]))
    # Known reference point: N=10, V=1 -> ~1.57 (hand-computed from the FST formula).
    assert abs(ds.expected_max_sharpe(10, 1.0) - 1.574) < 0.02


def test_expected_max_sharpe_scales_with_sqrt_variance():
    a = ds.expected_max_sharpe(50, 1.0)
    b = ds.expected_max_sharpe(50, 4.0)   # 2x sqrt(V)
    assert abs(b - 2.0 * a) < 1e-9


def test_dsr_high_for_strong_series_low_when_threshold_above_sr():
    rng = np.random.default_rng(0)
    # Strongly positive-Sharpe series (mean 0.01, sd 0.01 -> SR ~ 1 per obs), T=200.
    r = 0.01 + 0.01 * rng.standard_normal(200)
    strong = ds.deflated_sharpe_ratio(r, sr0=0.0)
    assert strong.dsr is not None and strong.dsr > 0.95 and strong.significant is True
    # Raising the deflation threshold above the observed SR drives DSR below 0.5.
    high_bar = ds.deflated_sharpe_ratio(r, sr0=strong.sr + 0.5)
    assert high_bar.dsr is not None and high_bar.dsr < 0.5
    assert high_bar.significant is False


def test_dsr_matches_closed_form():
    r = list(np.linspace(-0.01, 0.03, 50))   # deterministic, mild positive drift
    st = ds.sharpe_stats(r)
    sr0 = 0.05
    denom = 1.0 - st.skew * st.sr + ((st.kurt - 1.0) / 4.0) * st.sr ** 2
    z = (st.sr - sr0) * math.sqrt(st.t_obs - 1) / math.sqrt(denom)
    expected = ds._norm_cdf(z)
    got = ds.deflated_sharpe_ratio(r, sr0=sr0)
    assert got.dsr is not None and abs(got.dsr - expected) < 1e-9


def test_dsr_uses_fst_threshold_when_trials_given():
    r = list(0.01 + 0.005 * np.sin(np.linspace(0, 20, 120)))
    trials = [0.1, 0.4, -0.2, 0.35, 0.05, -0.1]
    v = ds.variance_across_trials(trials)
    sr0 = ds.expected_max_sharpe(len(trials), v)
    a = ds.deflated_sharpe_ratio(r, n_trials=len(trials), var_across_trials=v)
    b = ds.deflated_sharpe_ratio(r, sr0=sr0)
    assert a.dsr is not None and abs(a.dsr - b.dsr) < 1e-9
    assert abs(a.sr0 - sr0) < 1e-12


def test_dsr_degrades_gracefully_on_thin_input():
    out = ds.deflated_sharpe_ratio([0.01], sr0=0.0)
    assert out.dsr is None and out.reason is not None


def test_pbo_zero_for_a_dominant_trial():
    # Trial 3 is uniformly best in every observation -> best IS is always best OOS.
    rng = np.random.default_rng(1)
    T, N = 64, 4
    M = rng.standard_normal((T, N)) * 0.01
    M[:, 3] += 1.0   # dominant column, everywhere
    out = ds.pbo_cscv(M, n_splits=8)
    assert out["pbo"] == 0.0
    assert out["n_trials"] == 4 and out["n_combos"] > 0


def test_pbo_one_when_is_winner_is_oos_loser():
    # Construct a matrix where the best-in-sample trial is engineered to be the
    # worst out-of-sample on every symmetric split: first-half rows favor trial 0,
    # second-half rows favor trial 1, and the split IS={first blocks}/OOS={second}
    # (and its mirror) flip the ranking.
    T = 8
    M = np.zeros((T, 2))
    M[:T // 2, 0] = 1.0   # trial 0 great in first half
    M[:T // 2, 1] = 0.0
    M[T // 2:, 0] = 0.0
    M[T // 2:, 1] = 1.0   # trial 1 great in second half
    out = ds.pbo_cscv(M, n_splits=2)
    # With 2 splits, the two symmetric combos each pick an IS winner that loses OOS.
    assert out["pbo"] == 1.0


def test_pbo_guards_bad_shapes():
    assert ds.pbo_cscv(np.zeros((10, 1)))["pbo"] is None      # need N>=2
    assert ds.pbo_cscv(np.zeros((4, 3)), n_splits=3)["pbo"] is None   # odd splits
    assert ds.pbo_cscv(np.zeros((4, 3)), n_splits=8)["pbo"] is None   # T < n_splits
