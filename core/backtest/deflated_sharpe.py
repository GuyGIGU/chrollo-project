"""Deflated Sharpe Ratio, expected-maximum-Sharpe benchmark, and PBO.

When you try MANY candidate configs (tier cuts × sub-score sorts × horizons) and
report the best, the best Sharpe is inflated by selection alone — some config
looks good by luck. This module quantifies and corrects that.

  * ``expected_max_sharpe`` — the **False Strategy Theorem** noise ceiling: the
    Sharpe you'd expect the BEST of N trials to reach even if every true edge is
    zero. Beating zero is not enough; you must beat this.
  * ``deflated_sharpe_ratio`` — the **DSR**: P(true SR > threshold) for the
    selected strategy, correcting for (1) selection over N trials [via the
    expected-max threshold], (2) non-normal skew/kurtosis, and (3) sample length.
    DSR > 0.95 is the "credible" bar.
  * ``pbo_cscv`` — **Probability of Backtest Overfitting** via Combinatorially
    Symmetric Cross-Validation: the fraction of IS/OOS splits where the best
    in-sample config underperforms the median out-of-sample.

All non-annualized (per-observation) Sharpes — keep the returns series and the
threshold in the SAME units. Pure, NaN-safe, deterministic.

Refs: Bailey & López de Prado, *The Deflated Sharpe Ratio* (2014); *The
Probability of Backtest Overfitting* (Bailey, Borwein, López de Prado, Zhu 2015);
Lo (2002) / Mertens (2002) for the non-normal Sharpe estimator variance.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from itertools import combinations
from typing import Optional, Sequence

import numpy as np

try:
    from scipy.stats import norm, skew as _skew, kurtosis as _kurtosis
    _HAVE_SCIPY = True
except Exception:  # pragma: no cover - scipy is a project dep, but stay defensive
    _HAVE_SCIPY = False

EULER_GAMMA = 0.5772156649015329  # Euler-Mascheroni constant (gamma)


# ─────────────────────────────────────────────────────────────────────────────
# Normal CDF / PPF (scipy if present, else a stable fallback)
# ─────────────────────────────────────────────────────────────────────────────
def _norm_cdf(x: float) -> float:
    if _HAVE_SCIPY:
        return float(norm.cdf(x))
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def _norm_ppf(p: float) -> float:
    """Inverse standard-normal CDF. scipy when available; else Acklam's rational
    approximation (max abs error ~1.15e-9), good enough for the FST benchmark."""
    if _HAVE_SCIPY:
        return float(norm.ppf(p))
    if p <= 0.0:
        return -math.inf
    if p >= 1.0:
        return math.inf
    # Acklam's algorithm.
    a = [-3.969683028665376e+01, 2.209460984245205e+02, -2.759285104469687e+02,
         1.383577518672690e+02, -3.066479806614716e+01, 2.506628277459239e+00]
    b = [-5.447609879822406e+01, 1.615858368580409e+02, -1.556989798598866e+02,
         6.680131188771972e+01, -1.328068155288572e+01]
    c = [-7.784894002430293e-03, -3.223964580411365e-01, -2.400758277161838e+00,
         -2.549732539343734e+00, 4.374664141464968e+00, 2.938163982698783e+00]
    d = [7.784695709041462e-03, 3.224671290700398e-01, 2.445134137142996e+00,
         3.754408661907416e+00]
    plow, phigh = 0.02425, 1 - 0.02425
    if p < plow:
        q = math.sqrt(-2 * math.log(p))
        return (((((c[0]*q+c[1])*q+c[2])*q+c[3])*q+c[4])*q+c[5]) / \
               ((((d[0]*q+d[1])*q+d[2])*q+d[3])*q+1)
    if p > phigh:
        q = math.sqrt(-2 * math.log(1 - p))
        return -(((((c[0]*q+c[1])*q+c[2])*q+c[3])*q+c[4])*q+c[5]) / \
                ((((d[0]*q+d[1])*q+d[2])*q+d[3])*q+1)
    q = p - 0.5
    r = q * q
    return (((((a[0]*r+a[1])*r+a[2])*r+a[3])*r+a[4])*r+a[5])*q / \
           (((((b[0]*r+b[1])*r+b[2])*r+b[3])*r+b[4])*r+1)


# ─────────────────────────────────────────────────────────────────────────────
# Sharpe moments
# ─────────────────────────────────────────────────────────────────────────────
@dataclass(frozen=True)
class SharpeStats:
    sr: Optional[float]     # per-observation Sharpe (mean / std, ddof=1)
    t_obs: int              # number of return observations
    skew: float             # sample skewness of returns
    kurt: float             # sample kurtosis (NON-excess; normal = 3.0)

    def as_dict(self) -> dict:
        return {"sr": self.sr, "t_obs": self.t_obs, "skew": self.skew, "kurt": self.kurt}


def sharpe_stats(returns: Sequence[float]) -> SharpeStats:
    """Per-observation Sharpe + higher moments of a return series, NaN-safe."""
    r = np.asarray([x for x in returns if x is not None], dtype=float)
    r = r[~np.isnan(r)]
    n = int(r.size)
    if n < 2:
        return SharpeStats(sr=None, t_obs=n, skew=0.0, kurt=3.0)
    sd = float(r.std(ddof=1))
    sr = float(r.mean() / sd) if sd > 0 else None
    if _HAVE_SCIPY:
        sk = float(_skew(r, bias=False))
        ku = float(_kurtosis(r, fisher=False, bias=False))  # non-excess
    else:
        mean = r.mean()
        m2 = np.mean((r - mean) ** 2)
        m3 = np.mean((r - mean) ** 3)
        m4 = np.mean((r - mean) ** 4)
        sk = float(m3 / m2 ** 1.5) if m2 > 0 else 0.0
        ku = float(m4 / m2 ** 2) if m2 > 0 else 3.0
    return SharpeStats(sr=sr, t_obs=n, skew=sk, kurt=ku)


# ─────────────────────────────────────────────────────────────────────────────
# False Strategy Theorem — expected maximum Sharpe under the null
# ─────────────────────────────────────────────────────────────────────────────
def expected_max_sharpe(n_trials: int, var_across_trials: float) -> float:
    """Expected maximum (per-observation) Sharpe of N zero-edge trials.

    SR0 = sqrt(V) * [ (1-gamma)*Z^-1(1 - 1/N) + gamma*Z^-1(1 - 1/(N*e)) ]

    where V = variance of the Sharpe estimates ACROSS the N trials, gamma =
    Euler-Mascheroni, Z^-1 = normal quantile, e = Euler's number. This is the
    noise ceiling the observed best-of-N must clear.
    """
    if n_trials < 1 or var_across_trials < 0:
        return float("nan")
    if n_trials == 1:
        return 0.0
    sqrt_v = math.sqrt(var_across_trials)
    z1 = _norm_ppf(1.0 - 1.0 / n_trials)
    z2 = _norm_ppf(1.0 - 1.0 / (n_trials * math.e))
    return float(sqrt_v * ((1.0 - EULER_GAMMA) * z1 + EULER_GAMMA * z2))


def variance_across_trials(trial_sharpes: Sequence[float]) -> float:
    """Sample variance (ddof=1) of the candidate configs' Sharpe estimates.

    This is the ``V`` the False Strategy Theorem needs — the spread of Sharpes
    across everything you tried. Requires >= 2 finite trial Sharpes.
    """
    s = np.asarray([x for x in trial_sharpes if x is not None], dtype=float)
    s = s[~np.isnan(s)]
    if s.size < 2:
        return float("nan")
    return float(s.var(ddof=1))


# ─────────────────────────────────────────────────────────────────────────────
# Deflated Sharpe Ratio
# ─────────────────────────────────────────────────────────────────────────────
@dataclass(frozen=True)
class DSRResult:
    dsr: Optional[float]          # P(true SR > sr0), corrected
    sr: Optional[float]           # observed per-observation Sharpe
    sr0: float                    # deflation threshold (expected-max-Sharpe)
    t_obs: int
    skew: float
    kurt: float
    n_trials: Optional[int]
    significant: Optional[bool]   # dsr > alpha_bar (default 0.95)
    reason: Optional[str]

    def as_dict(self) -> dict:
        return {
            "dsr": self.dsr, "sr": self.sr, "sr0": self.sr0, "t_obs": self.t_obs,
            "skew": self.skew, "kurt": self.kurt, "n_trials": self.n_trials,
            "significant": self.significant, "reason": self.reason,
        }


def deflated_sharpe_ratio(
    returns: Sequence[float],
    sr0: Optional[float] = None,
    n_trials: Optional[int] = None,
    var_across_trials: Optional[float] = None,
    alpha_bar: float = 0.95,
) -> DSRResult:
    """Deflated Sharpe Ratio for a strategy's return series.

    DSR = Z[ (SR - SR0) * sqrt(T-1) / sqrt(1 - g3*SR + (g4-1)/4 * SR^2) ]

    where SR = observed per-observation Sharpe, SR0 = deflation threshold, T =
    #observations, g3 = skew, g4 = kurtosis (non-excess). SR0 is either passed
    directly OR derived via the False Strategy Theorem from (n_trials,
    var_across_trials). DSR is the probability the TRUE Sharpe exceeds SR0 after
    correcting for selection, skew/kurtosis, and sample length.
    """
    st = sharpe_stats(returns)
    if sr0 is None:
        if n_trials is not None and var_across_trials is not None and n_trials >= 1:
            sr0 = expected_max_sharpe(n_trials, var_across_trials)
        else:
            sr0 = 0.0
    if st.sr is None or st.t_obs < 2:
        return DSRResult(None, st.sr, float(sr0), st.t_obs, st.skew, st.kurt,
                         n_trials, None, "need >= 2 finite returns with non-zero variance")
    if sr0 is not None and (isinstance(sr0, float) and math.isnan(sr0)):
        return DSRResult(None, st.sr, float("nan"), st.t_obs, st.skew, st.kurt,
                         n_trials, None, "expected-max-Sharpe threshold is undefined (need >= 2 trials)")
    denom_var = 1.0 - st.skew * st.sr + ((st.kurt - 1.0) / 4.0) * st.sr ** 2
    if denom_var <= 0:
        return DSRResult(None, st.sr, float(sr0), st.t_obs, st.skew, st.kurt,
                         n_trials, None, "non-normal variance term <= 0 (heavy tails vs SR); DSR undefined")
    z = (st.sr - sr0) * math.sqrt(st.t_obs - 1) / math.sqrt(denom_var)
    dsr = _norm_cdf(z)
    return DSRResult(float(dsr), st.sr, float(sr0), st.t_obs, st.skew, st.kurt,
                     n_trials, bool(dsr > alpha_bar), None)


# ─────────────────────────────────────────────────────────────────────────────
# Probability of Backtest Overfitting — CSCV
# ─────────────────────────────────────────────────────────────────────────────
def pbo_cscv(perf_matrix: np.ndarray, n_splits: int = 16) -> dict:
    """Probability of Backtest Overfitting via Combinatorially Symmetric CV.

    ``perf_matrix`` is (T_observations x N_trials): column j = trial j's
    per-observation performance (e.g. per-date portfolio returns). The rows are
    split into ``n_splits`` (even) contiguous blocks; for every way of choosing
    half the blocks as in-sample (the rest out-of-sample), the best in-sample
    trial's OUT-of-sample relative rank gives a logit; PBO is the fraction of
    splits whose logit <= 0 (best-IS underperforms the OOS median).

    Returns {pbo, n_combos, n_trials, reason}. PBO near 0 = robust selection;
    PBO > 0.5 = the "winner" is likely an overfit artifact.
    """
    M = np.asarray(perf_matrix, dtype=float)
    if M.ndim != 2 or M.shape[1] < 2:
        return {"pbo": None, "n_combos": 0, "n_trials": 0,
                "reason": "need a (T x N>=2) performance matrix"}
    if n_splits % 2 != 0 or n_splits < 2:
        return {"pbo": None, "n_combos": 0, "n_trials": int(M.shape[1]),
                "reason": "n_splits must be even and >= 2"}
    T, N = M.shape
    if T < n_splits:
        return {"pbo": None, "n_combos": 0, "n_trials": int(N),
                "reason": f"need >= n_splits ({n_splits}) observations, have {T}"}
    # Contiguous blocks (drop a small remainder so blocks are equal-sized).
    block = T // n_splits
    blocks = [M[i * block:(i + 1) * block, :] for i in range(n_splits)]
    idx = list(range(n_splits))
    logits: list[float] = []
    for is_sel in combinations(idx, n_splits // 2):
        oos_sel = [i for i in idx if i not in is_sel]
        is_perf = np.concatenate([blocks[i] for i in is_sel], axis=0).mean(axis=0)
        oos_perf = np.concatenate([blocks[i] for i in oos_sel], axis=0).mean(axis=0)
        n_star = int(np.argmax(is_perf))               # best trial in-sample
        # OOS rank of the IS winner (1..N); relative rank in (0,1).
        order = np.argsort(oos_perf)                    # ascending
        oos_rank = int(np.where(order == n_star)[0][0]) + 1
        omega = oos_rank / (N + 1.0)
        omega = min(max(omega, 1e-6), 1 - 1e-6)
        logits.append(math.log(omega / (1.0 - omega)))
    if not logits:
        return {"pbo": None, "n_combos": 0, "n_trials": int(N),
                "reason": "no CSCV combinations produced"}
    pbo = float(np.mean([1.0 if lam <= 0 else 0.0 for lam in logits]))
    return {"pbo": pbo, "n_combos": len(logits), "n_trials": int(N), "reason": None}
