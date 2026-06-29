"""Statistical guards for the backtest harness: multiple-testing haircut + SPY.

Two pure helpers, no I/O:

  * ``multiple_testing_haircut`` — when the harness asks many questions at once
    (does tier S beat random? tier A? LPS vs REBOUND? each horizon?), some will
    look significant by chance. This applies a Benjamini-Hochberg FDR correction
    (default) or a Bonferroni correction to a set of p-values, so a "significant"
    slice has survived a haircut. No such logic existed in the codebase before, so
    this is a standard, conservative implementation.
  * ``abnormal_return`` — the screener fires in up and down tapes alike, so raw
    MFE conflates the setup with the market. Abnormal return subtracts the
    same-window SPY move from each setup's outcome ("excess MFE over just owning
    the index"), isolating the setup-specific edge.

Both are NaN-safe and deterministic.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Sequence

import numpy as np
import pandas as pd


# ─────────────────────────────────────────────────────────────────────────────
# Multiple-testing haircut
# ─────────────────────────────────────────────────────────────────────────────
@dataclass(frozen=True)
class HaircutEntry:
    label: str
    p_value: float
    p_adjusted: float
    significant: bool


def multiple_testing_haircut(
    pvalues: dict[str, float],
    alpha: float = 0.05,
    method: str = "fdr_bh",
) -> list[HaircutEntry]:
    """Adjust a set of labelled p-values for multiple comparisons.

    Args:
        pvalues: {label: raw_p}. NaN/None p-values are carried through as
            non-significant (they were untestable, not significant).
        alpha: family-wise / false-discovery target.
        method: 'fdr_bh' (Benjamini-Hochberg, default — controls the expected
            false-discovery rate, the right tool when scanning many slices) or
            'bonferroni' (controls family-wise error, stricter).

    Returns entries sorted by raw p-value ascending. ``p_adjusted`` is the
    corrected p; ``significant`` is ``p_adjusted <= alpha``.
    """
    items = list(pvalues.items())
    # Split testable (finite p) from untestable (None/NaN).
    testable = [(lab, float(p)) for lab, p in items
                if p is not None and not (isinstance(p, float) and np.isnan(p))]
    untestable = [lab for lab, p in items
                  if p is None or (isinstance(p, float) and np.isnan(p))]

    entries: list[HaircutEntry] = []
    m = len(testable)
    if m > 0:
        testable.sort(key=lambda x: x[1])  # ascending raw p
        ps = np.array([p for _, p in testable], dtype=float)

        if method == "bonferroni":
            adj = np.minimum(ps * m, 1.0)
        elif method == "fdr_bh":
            # BH step-up: p_adj[i] = min over k>=i of (m/(k+1)) * p[k], capped at 1.
            ranks = np.arange(1, m + 1)
            raw_adj = ps * m / ranks
            # enforce monotonicity from the largest p downward
            adj = np.minimum.accumulate(raw_adj[::-1])[::-1]
            adj = np.minimum(adj, 1.0)
        else:
            raise ValueError(f"unknown method {method!r} (use 'fdr_bh' or 'bonferroni')")

        for (lab, p), pa in zip(testable, adj):
            entries.append(HaircutEntry(lab, p, float(pa), bool(pa <= alpha)))

    for lab in untestable:
        entries.append(HaircutEntry(lab, float("nan"), float("nan"), False))

    return entries


# ─────────────────────────────────────────────────────────────────────────────
# Abnormal return vs SPY
# ─────────────────────────────────────────────────────────────────────────────
def abnormal_return(
    setup_returns: Sequence[float],
    spy_returns: Sequence[float],
) -> Optional[float]:
    """Median excess return of setups over the same-window SPY move.

    Both sequences are aligned element-wise (setup i and spy i cover the same
    window). Returns the median of (setup − spy), NaN-safe; None if no aligned,
    finite pairs exist.
    """
    s = pd.to_numeric(pd.Series(list(setup_returns)), errors="coerce")
    m = pd.to_numeric(pd.Series(list(spy_returns)), errors="coerce")
    n = min(len(s), len(m))
    if n == 0:
        return None
    s, m = s.iloc[:n], m.iloc[:n]
    diff = (s - m).dropna()
    if diff.empty:
        return None
    return float(diff.median())


def abnormal_return_frame(
    df: pd.DataFrame,
    setup_col: str,
    spy_col: str,
) -> dict:
    """Abnormal-return summary from two columns of a frame.

    ``spy_col`` is the same-window SPY return for each row (the caller must have
    joined it in — it is not stored in the archive by default). Returns
    {n, median_setup, median_spy, abnormal_median} with None where unavailable.
    """
    if setup_col not in df.columns or spy_col not in df.columns:
        return {"n": 0, "median_setup": None, "median_spy": None,
                "abnormal_median": None,
                "reason": f"missing column(s): need '{setup_col}' and '{spy_col}'."}
    s = pd.to_numeric(df[setup_col], errors="coerce")
    m = pd.to_numeric(df[spy_col], errors="coerce")
    mask = s.notna() & m.notna()
    if mask.sum() == 0:
        return {"n": 0, "median_setup": None, "median_spy": None,
                "abnormal_median": None,
                "reason": "no aligned non-NaN (setup, SPY) pairs."}
    s, m = s[mask], m[mask]
    return {
        "n": int(mask.sum()),
        "median_setup": float(s.median()),
        "median_spy": float(m.median()),
        "abnormal_median": float((s - m).median()),
        "reason": None,
    }
