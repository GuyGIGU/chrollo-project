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
# The ELAPSED-WINDOW columns come FIRST so they appear first in every report.
MFE_COLS = ["mfe_to_date", "mfe_20d", "mfe_60d"]
MAE_COLS = ["mae_to_date", "mae_20d", "mae_60d"]
FWD_RETURN_COLS = [
    "ret_to_date",
    "fwd_return_1d",
    "fwd_return_5d",
    "fwd_return_10d",
    "fwd_return_20d",
    "fwd_return_60d",
]
# mfe_to_date is the PRIMARY headline: the window-agnostic elapsed-window edge that
# is ALWAYS populated as soon as a setup has any forward bar, so the report is
# never "stuck on no mature data". The fixed mfe_20d / mfe_60d are SECONDARY and
# shown as they mature.
HEADLINE_MFE_COL = "mfe_to_date"
SECONDARY_MFE_COLS = ["mfe_20d", "mfe_60d"]
ELAPSED_BARS_COL = "bars_to_date"
ABNORMAL_COL = "abnormal_ret_to_date"
# The one unbiased standalone-edge basis. Seed / manual rows are a hand-picked
# winners gallery and re-scans carry survivorship bias.
UNBIASED_SOURCE = "screener"
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
    block["headline_mfe_col"] = HEADLINE_MFE_COL
    # Elapsed-window context: how many forward bars the elapsed read averages over,
    # plus the abnormal (excess-vs-SPY) elapsed return when it has been computed.
    if ELAPSED_BARS_COL in df.columns:
        block["bars_to_date"] = describe(df[ELAPSED_BARS_COL])
    if ABNORMAL_COL in df.columns:
        block["abnormal"] = describe(df[ABNORMAL_COL])
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


def headline_edge(df: pd.DataFrame, source_basis: str = UNBIASED_SOURCE) -> dict:
    """The bias-safe headline edge — computed on ONE explicit source basis.

    Bias-safety is enforced by CONSTRUCTION: the headline is always computed on the
    ``source_basis`` subset (default ``'screener'`` = the unbiased standalone-edge
    read), never on a silently-mixed frame. Seed / manual rows are a hand-picked
    winners gallery; if any are present in the input they are EXCLUDED from the
    headline and flagged, never averaged in.

    The headline metric is the ELAPSED-WINDOW ``mfe_to_date`` (window-agnostic, so
    always populated) — the fixed ``mfe_20d`` / ``mfe_60d`` are reported as
    secondary, maturing reads.

    Returns the headline metrics PLUS machine-readable provenance flags:
        source_basis        the basis the headline was computed on ('screener')
        unbiased            True iff source_basis is the unbiased basis
        contaminated_input  True iff the input frame contained non-basis rows
                            (seed / manual / re-scan) that were excluded
        n_input             rows in the input frame (before the basis filter)
        n_unbiased          rows on the headline basis
        headline_mfe_col / _median / _n   the elapsed-window headline
        secondary_mfe       {col: describe(...)} for the maturing fixed windows
        bars_to_date        describe() of the elapsed-window bar counts
        abnormal            describe() of the excess-vs-SPY elapsed return
    """
    n_input = len(df)
    if "source" in df.columns:
        basis_df = df[df["source"] == source_basis]
        contaminated = bool((df["source"] != source_basis).any())
    else:
        # No source column -> can't prove the basis; treat as the basis itself but
        # flag that we could not verify provenance.
        basis_df = df
        contaminated = False

    block = edge_block(basis_df)
    return {
        "source_basis": source_basis,
        "unbiased": source_basis == UNBIASED_SOURCE,
        "contaminated_input": contaminated,
        "n_input": n_input,
        "n_unbiased": len(basis_df),
        "headline_mfe_col": HEADLINE_MFE_COL,
        "headline_mfe_median": block.get("headline_mfe_median"),
        "headline_mfe_n": block.get("headline_mfe_n", 0),
        "secondary_mfe": {c: block["mfe"][c] for c in SECONDARY_MFE_COLS
                          if c in block.get("mfe", {})},
        "bars_to_date": block.get("bars_to_date"),
        "abnormal": block.get("abnormal"),
    }


def build_edge_report(df: pd.DataFrame, source_basis: str = UNBIASED_SOURCE) -> dict:
    """Assemble the screener-side edge report sliced by tier, setup_type, horizon.

    Returns a nested dict:
        {
          "headline": headline_edge,   # BIAS-SAFE: screener basis + flags
          "overall": edge_block,       # descriptive, on whatever was passed in
          "by_tier": {tier: edge_block, ...},
          "by_setup_type": {type: edge_block, ...},
        }
    The ``headline`` is the only number to quote as THE edge — it is computed on the
    unbiased ``source_basis`` and carries contamination flags. ``overall`` and the
    slices stay descriptive over the input frame (so a ``--source seed`` run can
    still inspect that gallery), but they are never THE edge.

    Horizon slicing is INSIDE each edge_block (mfe/mae/fwd_return keyed by horizon
    column), so every slice carries every horizon.
    """
    return {
        "headline": headline_edge(df, source_basis=source_basis),
        "overall": edge_block(df),
        "by_tier": slice_by(df, "tier"),
        "by_setup_type": slice_by(df, "setup_type"),
    }
