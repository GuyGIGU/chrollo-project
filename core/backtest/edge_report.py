"""Screener-side edge report from STORED archive outcome columns.

Pure (DataFrame in, dicts out) so it is trivially unit-testable and never touches
I/O. Computes the standalone-edge summary the harness reports:

  * MFE / MAE distributions (median + IQR + min/max + n) — **MFE is the HEADLINE
    edge metric**. The operator manages exits discretionarily, so realized R
    conflates the screener with the human exit; MFE ("max favorable excursion =
    what the setup made available") isolates the screener's contribution.
  * Barrier-label distribution (win / loss / timeout shares) — reuses the labels
    written by ``core.archive.forward_returns.compute_barrier_events``.
  * Forward-return distributions at every stored horizon (1/5/10/20/60d).

Every distribution can be sliced by **tier**, **setup_type**, and **horizon**.
All stats are NaN-safe and use the MEDIAN (not the mean) as the headline, because
MFE is heavy-tailed in a thin archive (one 8R excursion shouldn't dominate).
"""
from __future__ import annotations

from typing import Optional

import numpy as np
import pandas as pd

# Stored MFE/MAE horizons and forward-return horizons (match the archive schema
# written by core/archive/forward_returns.py). MFE is the headline.
MFE_COLS = ["mfe_20d", "mfe_60d"]
MAE_COLS = ["mae_20d", "mae_60d"]
FWD_RETURN_COLS = [
    "fwd_return_1d",
    "fwd_return_5d",
    "fwd_return_10d",
    "fwd_return_20d",
    "fwd_return_60d",
]
# MFE_20d is the headline horizon: 20 bars is mature enough to capture a swing yet
# the most-populated long-ish window in a young archive.
HEADLINE_MFE_COL = "mfe_20d"
BARRIER_LABELS = ["win", "loss", "timeout"]


def _num(s: pd.Series) -> pd.Series:
    return pd.to_numeric(s, errors="coerce")


def describe(series: pd.Series) -> dict:
    """Median / IQR / mean / min / max / n for a numeric series, NaN-safe."""
    vals = _num(series).dropna()
    if vals.empty:
        return {"n": 0, "median": None, "mean": None, "q25": None,
                "q75": None, "min": None, "max": None}
    return {
        "n": int(vals.shape[0]),
        "median": float(vals.median()),
        "mean": float(vals.mean()),
        "q25": float(vals.quantile(0.25)),
        "q75": float(vals.quantile(0.75)),
        "min": float(vals.min()),
        "max": float(vals.max()),
    }


def barrier_distribution(df: pd.DataFrame) -> dict:
    """win/loss/timeout counts + shares from the stored ``barrier_label`` column.

    Timeout is a non-win (the setup did not deliver inside the 60-bar horizon).
    A row whose label is None is unresolved (still maturing) and excluded from the
    shares but reported as ``n_unlabelled``.
    """
    if "barrier_label" not in df.columns:
        return {"n_labelled": 0, "n_unlabelled": len(df), "counts": {}, "shares": {}}
    norm = df["barrier_label"].map(
        lambda v: v.strip().lower() if isinstance(v, str) else None
    )
    labelled = norm.dropna()
    counts = {lab: int((labelled == lab).sum()) for lab in BARRIER_LABELS}
    n = int(labelled.shape[0])
    shares = {lab: (counts[lab] / n if n else None) for lab in BARRIER_LABELS}
    return {
        "n_labelled": n,
        "n_unlabelled": int(norm.isna().sum()),
        "counts": counts,
        "shares": shares,
        "win_rate": (counts["win"] / n if n else None),
    }


def edge_block(df: pd.DataFrame) -> dict:
    """The full edge summary for one (sub)set of episodes.

    Headline = median MFE at the headline horizon. Also returns every stored
    MFE/MAE/forward-return distribution and the barrier-label split.
    """
    block: dict = {"n": len(df)}
    block["mfe"] = {c: describe(df[c]) for c in MFE_COLS if c in df.columns}
    block["mae"] = {c: describe(df[c]) for c in MAE_COLS if c in df.columns}
    block["fwd_return"] = {
        c: describe(df[c]) for c in FWD_RETURN_COLS if c in df.columns
    }
    block["barrier"] = barrier_distribution(df)
    headline = block["mfe"].get(HEADLINE_MFE_COL, {})
    block["headline_mfe_median"] = headline.get("median")
    block["headline_mfe_n"] = headline.get("n", 0)
    return block


def slice_by(df: pd.DataFrame, column: str, min_n: int = 1) -> dict:
    """Edge block per distinct value of ``column`` (e.g. tier / setup_type).

    Groups with fewer than ``min_n`` rows are still returned (so the report can
    show how thin they are) — the caller decides whether to trust them.
    """
    out: dict = {}
    if column not in df.columns:
        return out
    for key in sorted(df[column].dropna().unique(), key=str):
        sub = df[df[column] == key]
        if len(sub) < min_n:
            continue
        out[str(key)] = edge_block(sub)
    return out


def build_edge_report(df: pd.DataFrame) -> dict:
    """Assemble the screener-side edge report sliced by tier, setup_type, horizon.

    Returns a nested dict:
        {
          "overall": edge_block,
          "by_tier": {tier: edge_block, ...},
          "by_setup_type": {type: edge_block, ...},
        }
    Horizon slicing is INSIDE each edge_block (mfe/mae/fwd_return keyed by horizon
    column), so every slice carries every horizon.
    """
    return {
        "overall": edge_block(df),
        "by_tier": slice_by(df, "tier"),
        "by_setup_type": slice_by(df, "setup_type"),
    }
