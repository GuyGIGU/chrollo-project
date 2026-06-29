"""Null / base-rate model: is the screener's MFE better than random selection?

The archive records FIRING setups only (no denominator), and the eligible
universe's outcomes are NOT stored. So this module cannot fabricate a baseline —
it consumes an INJECTABLE ``universe_returns`` dataset (the per-name MFE outcomes
of the day's *eligible* universe) supplied by the caller. If that dataset is
absent the harness reports the data dependency rather than inventing a baseline.

Headline statistic:
    edge = median(screener MFE) − median(null-draw MFE)
where each null draw selects, for each scan day, the SAME NUMBER of names the
screener fired that day, uniformly at random from that day's eligible universe.
This is a permutation/Monte-Carlo base rate: "if I'd thrown darts at the same
universe on the same days, picking the same count, how would I have done?"

A bootstrap CI on the edge is produced with a SEEDED RNG so the result is
deterministic (re-runs reproduce byte-for-byte — a hard project requirement).

Pure: no DB, no network, no global state. The caller assembles
``universe_returns`` (offline if it has the data; otherwise the orchestrator owns
the universe fetch — see ``UniverseData.required_columns``).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import numpy as np
import pandas as pd

# Default Monte-Carlo / bootstrap sizes. Modest by default so the CLI is fast on a
# young archive; the caller can raise them.
DEFAULT_N_DRAWS = 2000
DEFAULT_BOOTSTRAP = 2000
DEFAULT_SEED = 1337
DEFAULT_METRIC_COL = "mfe_20d"


@dataclass(frozen=True)
class NullModelResult:
    """Outcome of the screener-vs-null comparison."""

    available: bool                 # False = the universe dataset was insufficient
    reason: Optional[str]           # why unavailable (a data-dependency message)
    metric_col: str
    n_screener: int                 # screener episodes with a metric value
    screener_median: Optional[float]
    null_median: Optional[float]    # median across Monte-Carlo null draws
    edge: Optional[float]           # screener_median − null_median (the headline)
    ci_low: Optional[float]         # bootstrap CI on the edge
    ci_high: Optional[float]
    p_value: Optional[float]        # fraction of null draws whose median >= screener
    n_draws: int
    ci_level: float

    def as_dict(self) -> dict:
        return {
            "available": self.available,
            "reason": self.reason,
            "metric_col": self.metric_col,
            "n_screener": self.n_screener,
            "screener_median": self.screener_median,
            "null_median": self.null_median,
            "edge": self.edge,
            "ci_low": self.ci_low,
            "ci_high": self.ci_high,
            "p_value": self.p_value,
            "n_draws": self.n_draws,
            "ci_level": self.ci_level,
        }


def _unavailable(metric_col: str, reason: str, n_screener: int = 0) -> NullModelResult:
    return NullModelResult(
        available=False, reason=reason, metric_col=metric_col,
        n_screener=n_screener, screener_median=None, null_median=None,
        edge=None, ci_low=None, ci_high=None, p_value=None,
        n_draws=0, ci_level=0.0,
    )


# The columns an injected universe_returns frame MUST carry. Documented so the
# orchestrator (which owns the network/universe fetch) knows exactly what to build.
UNIVERSE_REQUIRED_COLUMNS = ("scan_date", "ticker", DEFAULT_METRIC_COL)


def validate_universe(
    universe_returns: Optional[pd.DataFrame], metric_col: str = DEFAULT_METRIC_COL
) -> Optional[str]:
    """Return None if usable, else a human reason string (the data dependency).

    The harness defers, rather than fabricates, when this returns a reason.
    """
    if universe_returns is None:
        return (
            "No universe_returns dataset supplied. The archive stores FIRING "
            "setups only; the eligible universe's outcomes are not recorded. "
            "Provide a frame with columns "
            f"{('scan_date', 'ticker', metric_col)} (the per-name outcome of the "
            "day's eligible universe) — the orchestrator owns this offline/network "
            "fetch."
        )
    missing = [c for c in ("scan_date", "ticker", metric_col)
               if c not in universe_returns.columns]
    if missing:
        return f"universe_returns is missing required column(s): {missing}."
    if universe_returns.empty:
        return "universe_returns is empty."
    if pd.to_numeric(universe_returns[metric_col], errors="coerce").notna().sum() == 0:
        return f"universe_returns has no usable (non-NaN) {metric_col} values."
    return None


def _daily_counts(screener: pd.DataFrame) -> dict[str, int]:
    """How many names the screener fired per scan_date (with a usable metric)."""
    counts: dict[str, int] = {}
    for d, sub in screener.groupby("scan_date"):
        counts[str(d)] = int(len(sub))
    return counts


def run_null_model(
    screener: pd.DataFrame,
    universe_returns: Optional[pd.DataFrame],
    metric_col: str = DEFAULT_METRIC_COL,
    n_draws: int = DEFAULT_N_DRAWS,
    n_bootstrap: int = DEFAULT_BOOTSTRAP,
    ci_level: float = 0.95,
    seed: int = DEFAULT_SEED,
) -> NullModelResult:
    """Compare screener-median MFE vs random same-count draws from the universe.

    Args:
        screener: episode-collapsed screener rows. Must carry ``scan_date`` and
            ``metric_col``. Rows with a NaN metric are dropped from the comparison.
        universe_returns: per-name eligible-universe outcomes; columns
            (scan_date, ticker, metric_col). If insufficient, the result is
            ``available=False`` carrying the data-dependency reason.
        n_draws: Monte-Carlo null draws (each reconstructs a full pseudo-portfolio
            by drawing, per day, the screener's daily count from that day's
            universe).
        n_bootstrap: bootstrap resamples of the per-day edge for the CI.
        ci_level: e.g. 0.95 → 2.5/97.5 percentile CI.
        seed: RNG seed for determinism.

    The null draw is done WITHOUT replacement within a day when the universe is
    large enough, else WITH replacement (so a thin day can't crash the draw).
    """
    reason = validate_universe(universe_returns, metric_col)
    n_scr_all = 0
    if metric_col in screener.columns:
        n_scr_all = int(pd.to_numeric(screener[metric_col], errors="coerce").notna().sum())
    if reason is not None:
        return _unavailable(metric_col, reason, n_screener=n_scr_all)

    if "scan_date" not in screener.columns or metric_col not in screener.columns:
        return _unavailable(
            metric_col,
            f"screener frame lacks 'scan_date' or '{metric_col}'.",
            n_screener=n_scr_all,
        )

    scr = screener[["scan_date", metric_col]].copy()
    scr[metric_col] = pd.to_numeric(scr[metric_col], errors="coerce")
    scr = scr.dropna(subset=[metric_col])
    scr["scan_date"] = scr["scan_date"].astype(str)
    if scr.empty:
        return _unavailable(
            metric_col, f"no screener rows with a usable {metric_col}.",
            n_screener=0,
        )

    uni = universe_returns[["scan_date", "ticker", metric_col]].copy()
    uni[metric_col] = pd.to_numeric(uni[metric_col], errors="coerce")
    uni = uni.dropna(subset=[metric_col])
    uni["scan_date"] = uni["scan_date"].astype(str)

    # Per-day universe metric pools, restricted to days the screener actually
    # fired AND the universe covers. A screener day with no universe coverage is
    # dropped from BOTH sides so the comparison stays apples-to-apples.
    uni_pools: dict[str, np.ndarray] = {
        str(d): sub[metric_col].to_numpy()
        for d, sub in uni.groupby("scan_date")
    }
    counts = _daily_counts(scr)
    usable_days = [d for d in counts if d in uni_pools and len(uni_pools[d]) > 0]
    if not usable_days:
        return _unavailable(
            metric_col,
            "no scan_date overlaps between screener and universe_returns "
            "(can't compare same-day draws).",
            n_screener=n_scr_all,
        )

    # Restrict screener to usable days for an apples-to-apples median.
    scr_used = scr[scr["scan_date"].isin(usable_days)]
    screener_median = float(scr_used[metric_col].median())
    n_screener = int(len(scr_used))

    rng = np.random.default_rng(seed)

    def _one_draw() -> np.ndarray:
        """One pseudo-portfolio: per usable day, draw that day's screener count
        from that day's universe pool. Returns the concatenated metric values."""
        picks: list[np.ndarray] = []
        for d in usable_days:
            pool = uni_pools[d]
            k = counts[d]
            if k <= 0:
                continue
            replace = k > len(pool)
            idx = rng.choice(len(pool), size=k, replace=replace)
            picks.append(pool[idx])
        return np.concatenate(picks) if picks else np.array([])

    null_medians = np.empty(n_draws, dtype=float)
    for i in range(n_draws):
        draw = _one_draw()
        null_medians[i] = float(np.median(draw)) if draw.size else np.nan
    null_medians = null_medians[~np.isnan(null_medians)]
    if null_medians.size == 0:
        return _unavailable(
            metric_col, "every null draw was empty (universe too thin).",
            n_screener=n_screener,
        )

    null_median = float(np.median(null_medians))
    edge = screener_median - null_median

    # One-sided permutation p-value: fraction of null portfolios whose median
    # MFE is >= the screener's. Small p = the screener beats darts.
    p_value = float((null_medians >= screener_median).mean())

    # Bootstrap CI on the edge: resample the screener metric values (with
    # replacement) and recompute (boot_median − null_median). Captures the
    # screener-side sampling uncertainty against the fixed null baseline.
    scr_vals = scr_used[metric_col].to_numpy()
    boot_edges = np.empty(n_bootstrap, dtype=float)
    for i in range(n_bootstrap):
        bs = rng.choice(scr_vals, size=len(scr_vals), replace=True)
        boot_edges[i] = float(np.median(bs)) - null_median
    alpha = (1.0 - ci_level) / 2.0
    ci_low = float(np.quantile(boot_edges, alpha))
    ci_high = float(np.quantile(boot_edges, 1.0 - alpha))

    return NullModelResult(
        available=True, reason=None, metric_col=metric_col,
        n_screener=n_screener, screener_median=screener_median,
        null_median=null_median, edge=edge, ci_low=ci_low, ci_high=ci_high,
        p_value=p_value, n_draws=int(null_medians.size), ci_level=ci_level,
    )
