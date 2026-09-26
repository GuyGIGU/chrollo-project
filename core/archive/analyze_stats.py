"""The numbers behind the archive report card. Nothing here prints.

Descriptive statistics, correlations, segment performance, the tightness split,
the derived outcome columns and the Stage-1 signal-edge classifier, each a pure
function of an archive frame. ``core.archive.analyze_report`` turns them into
text; ``suggested_weights`` serves the backend's /calibration panel.
"""
from __future__ import annotations

from typing import Optional

import numpy as np
import pandas as pd

from core.archive.analyze_features import SUB_SCORES
from core.archive.outcomes import HORIZON_BARS
from core.backtest.edge_report import TAIL_MFE_COL, TAIL_THRESHOLDS

# A win that round-trips to the stop within this many bars of first touching a
# profit target is a "cash-grab" — it spiked into profit then collapsed before
# there was time to lock in a swing. (Operator's call: ~1 trading week.)
CASH_GRAB_MAX_BARS = 5

# Sample-adequacy gate for the Stage-1 signal-edge verdicts. Below these, the
# tool REFUSES to label signals harmful/inert (it would just be fitting noise /
# a winners-only gallery). Binary outcomes also need both classes represented.
EDGE_MIN_N = 25          # minimum labelled pairs
EDGE_MIN_MINORITY = 8    # minimum of the minority class (e.g. losers) for a binary outcome

# The magnitude target: did the setup ever OFFER this much, regardless of the
# path it took getting there. Threshold and column both imported from the one
# home (EC-3) so this can never drift from what the edge report publishes.
MAGNITUDE_THRESHOLD = TAIL_THRESHOLDS[0]
MAGNITUDE_TARGET = "mfe_tail"

# Edge targets for the Stage-1 signal-edge / subtraction analysis, in priority
# order. The first one with enough non-null rows is the "primary" the verdicts
# are based on. durable_win (a win that HELD, not a cash-grab) is the truest
# success outcome; barrier_win (any win vs loss/timeout) is the looser fallback,
# then realized R, then the raw 20d return.
EDGE_TARGETS = ["durable_win", "barrier_win", "r_multiple_20d", "fwd_return_20d",
                MAGNITUDE_TARGET]

# The MAGNITUDE cross-check. Every target above is PATH-sensitive: durable_win and
# barrier_win resolve on whichever barrier is touched first, so a name that dips
# through a stop 3% under support and then runs is scored a failure; fwd_return_20d
# asks only where it closed on day 20. The operator manages exits by eye and sells
# into strength, so a verdict returned against those alone can be right about the
# path and wrong about him. Measured 2026-09-08 on the pre-demotion cohort, the two
# families DISAGREE IN SIGN on identical rows for the two terms that were zeroed on
# this analysis: score_rs_bonus reads -0.141 against durable_win and +0.091 against
# P(MFE>=25%); score_uptrend_bonus -0.091 and +0.150.
# The primary is deliberately UNCHANGED — swapping it would silently rewrite every
# standing verdict. Instead the disagreement is surfaced per row, because the
# disagreement IS the finding: it means "this signal offers more and holds it less."
# Threshold imported, never re-declared (EC-3) — see docs/rs_uptrend_reopen_2026-09-08.md.

# The tightness features where LOWER = tighter. For the rest (lps_descent_frac,
# the quality scores) HIGHER = cleaner, so "tight" is always the better-thesis end.
_LOWER_IS_TIGHTER = ("box_width", "atr_ratio", "tightness_ratio", "bin_d_vs_b_range_ratio")


# ------------------------------------------------------------------
# Descriptive statistics and correlations
# ------------------------------------------------------------------
def describe_col(s: pd.Series) -> dict:
    """Return median / IQR / min / max / n for a numeric series, NaN-safe."""
    vals = pd.to_numeric(s, errors="coerce").dropna()
    if vals.empty:
        return {"n": 0, "median": None, "q25": None, "q75": None, "min": None, "max": None}
    return {
        "n": int(vals.shape[0]),
        "median": float(vals.median()),
        "q25": float(vals.quantile(0.25)),
        "q75": float(vals.quantile(0.75)),
        "min": float(vals.min()),
        "max": float(vals.max()),
    }


def safe_corr(x: pd.Series, y: pd.Series, min_n: int = 8) -> Optional[float]:
    """Pearson correlation, NaN-safe; None if too few pairs or no variance."""
    xx = pd.to_numeric(x, errors="coerce")
    yy = pd.to_numeric(y, errors="coerce")
    mask = xx.notna() & yy.notna()
    if mask.sum() < min_n:
        return None
    xv, yv = xx[mask], yy[mask]
    if xv.std() == 0 or yv.std() == 0:
        return None
    return float(np.corrcoef(xv, yv)[0, 1])


def safe_rank_corr(x: pd.Series, y: pd.Series, min_n: int = 8) -> Optional[float]:
    """Spearman rank correlation (Pearson on ranks), NaN-safe.

    Rank-based so it is robust to the heavy-tailed, outlier-prone outcome
    distributions in a thin archive (one 8R winner shouldn't dominate a Pearson
    fit). None if too few pairs or no variance.
    """
    xx = pd.to_numeric(x, errors="coerce")
    yy = pd.to_numeric(y, errors="coerce")
    mask = xx.notna() & yy.notna()
    if mask.sum() < min_n:
        return None
    xr, yr = xx[mask].rank(), yy[mask].rank()
    if xr.std() == 0 or yr.std() == 0:
        return None
    return float(np.corrcoef(xr, yr)[0, 1])


def ranked_correlations(df: pd.DataFrame, candidates: list,
                        target: str) -> list[tuple[str, float]]:
    """(feature, Pearson corr vs ``target``) for every candidate the frame
    carries, strongest |corr| first. A feature too thin or too flat to
    correlate is left out."""
    rows = []
    for feat in candidates:
        if feat not in df.columns:
            continue
        c = safe_corr(df[feat], df[target])
        if c is not None:
            rows.append((feat, c))
    rows.sort(key=lambda x: abs(x[1]), reverse=True)
    return rows


# ------------------------------------------------------------------
# Segment performance and the tightness split
# ------------------------------------------------------------------
def _perf_row(sub: pd.DataFrame) -> dict:
    ret20 = pd.to_numeric(sub["fwd_return_20d"], errors="coerce").dropna()
    ret60 = pd.to_numeric(sub["fwd_return_60d"], errors="coerce").dropna()
    rmult = pd.to_numeric(sub["r_multiple_20d"], errors="coerce").dropna()
    # Trigger-rate maturity gate: the fires' updater stamps triggered=0 from the
    # FIRST forward bar and lets the nightly recompute converge it, so 0 means
    # "not YET (as of last maturation)", not "never". Averaging those
    # still-maturing zeros deflates every recent segment's trigger rate. A row
    # counts here only once its verdict is final: triggered=1 (a touch is final
    # the moment it happens) or triggered=0 with the full horizon elapsed
    # (bars_to_date >= HORIZON_BARS). Reporter-side predicate only — the stored
    # column keeps its two-state write semantics untouched.
    trig = pd.to_numeric(sub["triggered"], errors="coerce")
    if "bars_to_date" in sub.columns:
        bars = pd.to_numeric(sub["bars_to_date"], errors="coerce")
        trig = trig[(trig == 1) | (bars >= HORIZON_BARS)]
    else:  # pre-migration DB: no maturity info — the ungated legacy mean
        trig = trig.dropna()
    win_rate = (ret20 > 0).mean() if len(ret20) else None
    # Expectancy in R: win_rate*avg_win + (1-wr)*avg_loss
    exp_r = None
    if len(rmult):
        wins = rmult[rmult > 0]
        losses = rmult[rmult <= 0]
        wr = len(wins) / len(rmult)
        aw = wins.mean() if len(wins) else 0.0
        al = losses.mean() if len(losses) else 0.0
        exp_r = wr * aw + (1 - wr) * al
    return {
        "n": len(sub),
        "med_20d": ret20.median() if len(ret20) else None,
        "avg_20d": ret20.mean() if len(ret20) else None,
        "med_60d": ret60.median() if len(ret60) else None,
        "win_rate": win_rate,
        "trig_rate": trig.mean() if len(trig) else None,
        "avg_rmult": rmult.mean() if len(rmult) else None,
        "exp_r": exp_r,
    }


def _bucket(df: pd.DataFrame, col: str) -> pd.Series:
    """Quantile-bucket a numeric column into low / mid / high tertiles; all
    None when the values cannot be split (a constant column, say)."""
    vals = pd.to_numeric(df[col], errors="coerce")
    try:
        return pd.qcut(vals, 3, labels=["low", "mid", "high"], duplicates="drop")
    except ValueError:
        return pd.Series([None] * len(df), index=df.index)


def tight_vs_loose(df: pd.DataFrame, feat: str,
                   target: str) -> Optional[tuple[pd.Series, pd.Series]]:
    """``target`` on the tightest and the loosest tertile of ``feat`` (at least
    4 rows each), or None below 12 paired rows."""
    d = df[[feat, target]].copy()
    d[feat] = pd.to_numeric(d[feat], errors="coerce")
    d[target] = pd.to_numeric(d[target], errors="coerce")
    d = d.dropna()
    if len(d) < 12:
        return None
    d = d.sort_values(feat, ascending=feat in _LOWER_IS_TIGHTER)
    tert = max(4, len(d) // 3)
    return d.head(tert)[target], d.tail(tert)[target]


# ------------------------------------------------------------------
# Outcomes and signal edge (Stage 1)
# ------------------------------------------------------------------
def _num_col(df: pd.DataFrame, name: str) -> pd.Series:
    """Numeric view of a column, or an all-NaN series if the column is absent."""
    if name in df.columns:
        return pd.to_numeric(df[name], errors="coerce")
    return pd.Series(np.nan, index=df.index)


def derive_outcomes(df: pd.DataFrame,
                    cash_grab_max_bars: int = CASH_GRAB_MAX_BARS) -> pd.DataFrame:
    """Return a copy with derived outcome columns the edge analysis needs.

    barrier_win: 1.0 if the triple-barrier label is 'win', 0.0 if 'loss' or
        'timeout', NaN if unlabelled. (Timeouts are non-wins — the setup didn't
        deliver inside the horizon.)

    win_quality / durable_win / bars_target_to_stop — the "did the win HOLD?"
        refinement. The barrier code records the first bar each line is touched
        independently, so on a win we already know whether the stop was *also*
        tagged later and how many bars after the profit target that happened:
          bars_target_to_stop = days_to_stop − (first profit-target bar)
        A win whose stop round-trip lands within ``cash_grab_max_bars`` is a
        'cash_grab' (spiked into profit then collapsed before there was time to
        lock in a swing); otherwise the win is 'durable'.
          durable_win: 1.0 = durable win; 0.0 = cash-grab / loss / timeout;
                       NaN = unlabelled.
        Degrades gracefully: if the days_to_* columns are absent (outcomes not
        yet backfilled), every win is treated as durable (we can't know better),
        so durable_win collapses to barrier_win until the timing data exists.
    """
    df = df.copy()
    if "barrier_label" not in df.columns:
        return df

    norm = df["barrier_label"].map(
        lambda v: v.strip().lower() if isinstance(v, str) else None
    )
    df["barrier_win"] = norm.map({"win": 1.0, "loss": 0.0, "timeout": 0.0})

    is_win = norm.eq("win")
    d_target = pd.concat([_num_col(df, "days_to_2_5r"),
                          _num_col(df, "days_to_15pct")], axis=1).min(axis=1)
    d_stop = _num_col(df, "days_to_stop")
    gap = d_stop - d_target
    has_roundtrip = is_win & d_stop.notna() & d_target.notna()
    cash_grab = has_roundtrip & (gap <= cash_grab_max_bars)

    df["bars_target_to_stop"] = gap.where(has_roundtrip)

    wq = pd.Series([None] * len(df), index=df.index, dtype=object)
    wq[is_win & ~cash_grab] = "durable"
    wq[cash_grab] = "cash_grab"
    df["win_quality"] = wq

    durable = pd.Series(np.nan, index=df.index)
    durable[norm.isin(["win", "loss", "timeout"])] = 0.0
    durable[is_win & ~cash_grab] = 1.0
    df["durable_win"] = durable

    # The magnitude cross-check: 1.0 if the setup ever offered the threshold move
    # inside the fixed window, 0.0 if it matured and did not, NaN if not yet
    # matured. Needs NO label, so it keeps the rows the barrier gate drops — and
    # it is blind to path, which is exactly what makes it disagree with the
    # barrier targets and worth reporting beside them.
    if TAIL_MFE_COL in df.columns:
        mfe = _num_col(df, TAIL_MFE_COL)
        df[MAGNITUDE_TARGET] = (mfe >= MAGNITUDE_THRESHOLD).astype(float).where(mfe.notna())
    else:
        df[MAGNITUDE_TARGET] = pd.Series(np.nan, index=df.index)
    return df


def _primary_target(df: pd.DataFrame, targets: list, min_n: int) -> Optional[str]:
    """The first target with at least ``min_n`` labelled rows, or None."""
    for t in targets:
        if t in df.columns and pd.to_numeric(df[t], errors="coerce").notna().sum() >= min_n:
            return t
    return None


def _noise_floor(n: int) -> Optional[float]:
    """The |r| a rank correlation on n pairs must clear to count as signal:
    ~1/sqrt(n-3), floored at 0.15. None when n is too small to say."""
    return max(0.15, 1.0 / np.sqrt(n - 3)) if n > 4 else None


def _verdict(corr: Optional[float], noise: Optional[float]) -> str:
    """The one verdict rule, shared by the primary and the magnitude cross-check
    so the two can never be judged on different arithmetic (EC-3)."""
    if corr is None or noise is None:
        return "unknown"
    if corr <= -noise:
        return "harmful"
    if corr >= noise:
        return "beneficial"
    return "inert"


def signal_edge(df: pd.DataFrame, targets: Optional[list] = None,
                min_n: int = 8) -> dict:
    """Pure: classify each scoring sub-score by its rank-association with outcome.

    Every sub-score is *meant* to be a positive contributor (the engine rewards
    higher values). So against a higher-is-better outcome:
        negative association  -> HARMFUL  (the points actively misrank)
        near-zero association -> INERT    (spends score/ranking influence for
                                           nothing; dilutes the real signal)
        positive association  -> BENEFICIAL (keep)
    "Near-zero" is defined by an n-aware noise floor (~1/sqrt(n-3), floored at
    0.15) so we never call a signal harmful on what is statistically noise.

    This NEVER changes a weight — it only flags subtraction candidates. The
    actual re-weighting is a separate, reviewed, guarded step.

    Returns: {primary_target, n_primary, noise_floor, rows: [...]} where each
    row is {feature, n, corr_by_target (dict), primary_corr, verdict}.
    Sorted most-harmful first.
    """
    targets = targets or EDGE_TARGETS
    primary = _primary_target(df, targets, min_n)

    prim_vals = pd.to_numeric(df[primary], errors="coerce") if primary else None
    n_primary = int(prim_vals.notna().sum()) if primary else 0
    noise = _noise_floor(n_primary)

    # Is the outcome binary (a win/loss flag)? If so, verdicts need BOTH classes
    # present — a winners-only gallery (no losers) can't tell harmful from good.
    nonnull = prim_vals.dropna() if primary is not None else pd.Series([], dtype=float)
    is_binary = len(nonnull) > 0 and set(pd.unique(nonnull)) <= {0.0, 1.0}
    n_minority = (int(min((nonnull == 1).sum(), (nonnull == 0).sum()))
                  if is_binary else None)

    trustworthy = n_primary >= EDGE_MIN_N
    if is_binary:
        trustworthy = trustworthy and n_minority >= EDGE_MIN_MINORITY

    rows = []
    for feat in SUB_SCORES:
        if feat not in df.columns:
            continue
        feat_vals = pd.to_numeric(df[feat], errors="coerce")
        # n = the PAIRED sample actually used in the primary correlation (rows
        # with both the sub-score and the outcome), not the sub-score's own
        # count — otherwise a 38-pair correlation looks like 933 and overstates
        # its power.
        nn = (int((feat_vals.notna() & prim_vals.notna()).sum())
              if primary else int(feat_vals.notna().sum()))
        if int(feat_vals.notna().sum()) == 0:
            continue
        corr_by = {}
        for t in targets:
            if t in df.columns:
                corr_by[t] = safe_rank_corr(df[feat], df[t], min_n=min_n)
        pc = corr_by.get(primary) if primary else None
        verdict = _verdict(pc, noise)
        # The magnitude cross-check, judged on its OWN noise floor (its n differs
        # from the primary's — it keeps the rows the barrier gate drops).
        mc = corr_by.get(MAGNITUDE_TARGET)
        m_n = (int((feat_vals.notna() & pd.to_numeric(
            df[MAGNITUDE_TARGET], errors="coerce").notna()).sum())
            if MAGNITUDE_TARGET in df.columns else 0)
        m_verdict = _verdict(mc, _noise_floor(m_n))
        # Flag whenever the two targets would lead to DIFFERENT ACTION — a sign
        # flip, or one clearing its noise floor while the other does not. Both
        # cases mean the shortlist's recommendation depends on which target was
        # picked, which is the whole thing this column exists to expose.
        # ("unknown" is absence of evidence, not disagreement.)
        disagrees = ("unknown" not in (verdict, m_verdict)
                     and verdict != m_verdict)
        rows.append({
            "feature": feat, "n": nn, "corr_by_target": corr_by,
            "primary_corr": pc, "verdict": verdict,
            "magnitude_corr": mc, "magnitude_n": m_n,
            "magnitude_verdict": m_verdict, "verdict_disagrees": disagrees,
        })

    # Most-harmful first (most negative primary_corr); unknowns sink to the end.
    rows.sort(key=lambda r: (r["primary_corr"] is None,
                             r["primary_corr"] if r["primary_corr"] is not None else 0.0))
    return {"primary_target": primary, "n_primary": n_primary,
            "noise_floor": noise, "is_binary": is_binary, "n_minority": n_minority,
            "verdicts_trustworthy": trustworthy, "rows": rows}


# ------------------------------------------------------------------
# Suggested re-weighting (advisory) — router-only: the /calibration
# panel is the sole caller; the CLI analysis flags candidates but
# does not re-weight.
# ------------------------------------------------------------------
def suggested_weights(df: pd.DataFrame, corr_20d: dict, corr_60d: dict,
                      current_weights: dict) -> dict:
    """Pure: an ADVISORY re-weighting table for the /calibration panel.

    Blends |corr| across the 20d + 60d horizons, floors weak signals at 0.02 so
    one noisy archive can't zero a sub-score, and re-normalizes to preserve the
    current total point cap. It NEVER applies a weight — it is a suggestion the
    operator reads and hand-edits ``config/settings.py`` to act on.

    Gated by the SAME adequacy + minority-class guard the Stage-1 signal-edge
    analysis uses (``signal_edge(...)["verdicts_trustworthy"]``): on a winners-
    only gallery, or too few matured/labelled rows, it returns NO suggestion
    (``weights=[]``) instead of a table fit to noise. This replaces the weaker
    ``n >= 30`` gate the router used to inline. It is router-only: the CLI
    analysis flags candidate sub-scores but does not itself re-weight.

    Args:
        df: episode-level frame the suggestion is built from (the matured rows
            feeding ``corr_20d``/``corr_60d``); the adequacy gate runs on it.
        corr_20d / corr_60d: {sub-score short-name -> Pearson corr vs fwd return}
            already computed by the caller (passed in so the values stay identical).
        current_weights: {sub-score short-name -> current point cap}.

    Returns:
        ``{"weights": [ {name, current, suggested, delta, avg_abs_corr}, ... ],
        "basis": str}``. ``weights`` is empty and ``basis`` is
        ``"insufficient_data"`` when the sample can't support a suggestion.
    """
    edge = signal_edge(derive_outcomes(df))
    if not edge["verdicts_trustworthy"]:
        return {"weights": [], "basis": "insufficient_data"}

    total_cap = sum(current_weights.values())
    # If the 60d sample is too small for stable correlations, fall back to 20d
    # only — otherwise the 60d zeros dilute every sub-score symmetrically and
    # produce a deceptively even suggestion.
    n_with_60d = (int(pd.to_numeric(df["fwd_return_60d"], errors="coerce").notna().sum())
                  if "fwd_return_60d" in df.columns else 0)
    use_60d = n_with_60d >= 15
    basis = "20d+60d_avg" if use_60d else "20d_only"

    avg_abs_corr = {}
    for k in current_weights:
        c20 = abs(corr_20d.get(k, 0.0) or 0.0)
        if use_60d:
            c60 = abs(corr_60d.get(k, 0.0) or 0.0)
            blended = (c20 + c60) / 2
        else:
            blended = c20
        # Floor so a single sub-score at ~0 corr isn't zeroed by one noisy archive.
        avg_abs_corr[k] = max(blended, 0.02)
    norm = sum(avg_abs_corr.values()) or 1.0

    weights = []
    for k, current in current_weights.items():
        suggested = round(total_cap * (avg_abs_corr[k] / norm), 1)
        weights.append({
            "name": k,
            "current": current,
            "suggested": suggested,
            "delta": round(suggested - current, 1),
            "avg_abs_corr": round(avg_abs_corr[k], 4),
        })
    return {"weights": weights, "basis": basis}
