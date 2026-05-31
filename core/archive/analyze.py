"""
Archive analysis tool - the measuring stick for the screener.

A standalone, read-only CLI that reads the `setup_archive` table and produces a
human-readable report answering the questions that actually matter for tuning:

  1. SAMPLE COMPOSITION & BIAS - what kind of data do we have, and which
     analyses are currently *valid*? (Critical: a seed-only archive is a
     winners-only gallery - trigger/win rates are meaningless until live
     non-winners accrue. The tool detects this and says so loudly.)
  2. WINNER FINGERPRINT - the structural profile of the setups in the archive
     (median / IQR / range of every structural feature, segmented by tier and
     setup_type). On seed data this is the "what does a clean tight setup look
     like" profile to bias toward. This is the analysis that IS valid now.
  3. SEGMENTED PERFORMANCE - forward returns / R-multiples / trigger rate by
     tier, setup_type, zone, inner-vs-outer, tightness bucket, breadth regime,
     SPY trend. Becomes discriminative as losers accrue; shown now with caveat.
  4. PREDICTOR CORRELATIONS - every sub-score AND structural feature correlated
     against fwd_20d / fwd_60d / r_multiple_20d, ranked by |corr|. Extends the
     webapp /calibration endpoint (7 core sub-scores) to the full feature set,
     including the Phase-1 additions.
  5. PRIME-DIRECTIVE TEST - is TIGHTNESS predictive? Isolates box_width /
     atr_ratio / tightness_ratio / lps_descent_frac. When losers exist, splits
     tight-tertile vs loose-tertile and compares mean forward return.

Usage:
    python -m core.archive.analyze                 # full report to stdout
    python -m core.archive.analyze --md report.md  # also write a markdown copy
    python -m core.archive.analyze --source screener   # restrict to live scans
    python -m core.archive.analyze --min-rows 30   # raise the stat-validity bar

Read-only: never writes to the DB.
"""
from __future__ import annotations

import argparse
import os
import sqlite3
from typing import Optional

import numpy as np
import pandas as pd

# ------------------------------------------------------------------
# Paths & loading
# ------------------------------------------------------------------
_PROJECT_ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
_DB_PATH = os.path.join(_PROJECT_ROOT, "webapp", "backend", "trading_journal.db")

# Structural features (the "picture" - produced by the Visual Structure Engine).
STRUCTURAL_FEATURES = [
    "box_width", "base_length", "touches", "r_touches", "s_touches",
    "atr_ratio", "lps_length", "breach_days", "vol_contraction",
    "tightness_ratio", "lps_descent_frac", "r_touch_vol_z", "s_touch_vol_z",
    "dist_52w_high_pct", "excess_return_6m", "rs_vs_sector_pct", "breadth_pct",
    "bars_since_bc", "descent_length",
    "contraction_count", "contraction_quality", "final_contraction_depth",
    "support_slope_atr", "ascending_support_quality",
]

# Sub-scores (the Scoring Engine decomposition).
SUB_SCORES = [
    "score_box_tightness", "score_touch_density", "score_oscillation",
    "score_atr_squeeze", "score_lps_tightness", "score_vol_contraction",
    "score_base_age", "score_uptrend_bonus", "score_rs_bonus",
    "score_high_proximity", "score_breadth_bonus", "score_contraction",
    "score_ascending_support",
]

# Outcome targets (filled by update_forward_returns).
OUTCOME_TARGETS = ["fwd_return_20d", "fwd_return_60d", "r_multiple_20d"]

# Tightness features specifically - the prime directive.
TIGHTNESS_FEATURES = ["box_width", "atr_ratio", "tightness_ratio",
                      "lps_descent_frac", "contraction_quality"]


def load_archive(source: Optional[str] = None) -> pd.DataFrame:
    """Read the setup_archive table into a DataFrame (read-only)."""
    if not os.path.exists(_DB_PATH):
        raise FileNotFoundError(f"Archive DB not found at {_DB_PATH}")
    con = sqlite3.connect(_DB_PATH)
    try:
        df = pd.read_sql_query("SELECT * FROM setup_archive", con)
    finally:
        con.close()
    if source:
        df = df[df["source"] == source].copy()
    return df


# ------------------------------------------------------------------
# Formatting helpers
# ------------------------------------------------------------------
_LINES: list[str] = []


def emit(line: str = "") -> None:
    """Collect a report line (printed + optionally written to markdown)."""
    _LINES.append(line)


def header(title: str) -> None:
    emit()
    emit("=" * 72)
    emit(f"  {title}")
    emit("=" * 72)


def subhdr(title: str) -> None:
    emit()
    emit(f"-- {title} " + "-" * max(0, 68 - len(title)))


def fmt(v, pct: bool = False, nd: int = 2) -> str:
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return "-"
    if pct:
        return f"{v * 100:+.1f}%"
    return f"{v:.{nd}f}"


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


# ------------------------------------------------------------------
# Section 1 - sample composition & bias detection
# ------------------------------------------------------------------
def section_composition(df: pd.DataFrame, min_rows: int) -> dict:
    """Report what we have and decide which analyses are statistically valid."""
    header("1. SAMPLE COMPOSITION & BIAS DETECTION")
    n = len(df)
    emit(f"Total rows: {n}")
    if n == 0:
        emit("Archive is empty - nothing to analyze.")
        return {"valid_outcome": False, "valid_corr": False}

    by_source = df["source"].fillna("unknown").value_counts().to_dict()
    by_tier = df["tier"].fillna("?").value_counts().to_dict()
    by_type = df["setup_type"].fillna("?").value_counts().to_dict()
    emit(f"By source:     {by_source}")
    emit(f"By tier:       {by_tier}")
    emit(f"By setup_type: {by_type}")
    emit(f"Date range:    {df['scan_date'].min()} -> {df['scan_date'].max()}")

    with_ret = df["fwd_return_20d"].notna().sum()
    emit(f"With fwd_return_20d: {with_ret} / {n}")

    # Trigger-rate bias check. Seeds are hand-picked winners -> ~100% triggered.
    triggered = pd.to_numeric(df["triggered"], errors="coerce")
    trig_rate = triggered.mean() if triggered.notna().any() else None
    live = df[df["source"] == "screener"]
    n_live = len(live)

    subhdr("Validity verdict")
    valid_outcome = True
    valid_corr = True

    if trig_rate is not None and trig_rate > 0.97:
        emit("!  Trigger rate ~= 100% - this archive is a WINNERS-ONLY gallery")
        emit("   (seed/manual setups are selected because they worked). Win-rate,")
        emit("   trigger-rate and expectancy numbers are NOT discriminative yet.")
        emit("   -> Section 2 (winner fingerprint) IS valid.")
        emit("   -> Sections 3-5 (outcome perf, correlations, tightness test) need")
        emit("     LIVE non-winner rows (source='screener') before they mean anything.")
        valid_outcome = False
        valid_corr = False

    if n_live < min_rows:
        emit(f"!  Only {n_live} live (source='screener') rows - below the {min_rows}-row")
        emit("   bar for stable correlations / segment stats. Treat 3-5 as directional.")
        valid_corr = valid_corr and (n_live >= min_rows)

    if valid_outcome and valid_corr:
        emit("OK  Sample looks adequate for outcome + correlation analysis.")

    # ── Data-quality flags ─────────────────────────────────────────
    # (a) Placeholder contamination: legacy BREAKOUT seed rows were written
    #     with BREAKOUT_DEFAULT_TIGHTNESS (0.70) / _VOL_CONTRACTION (0.50)
    #     instead of measured values. They poison the fingerprint and any
    #     correlation. Detect a suspicious mass of identical values.
    subhdr("Data-quality flags")
    flagged = False
    for col, placeholder in (("tightness_ratio", 0.70), ("vol_contraction", 0.50)):
        if col not in df.columns:
            continue
        vals = pd.to_numeric(df[col], errors="coerce").dropna()
        if len(vals) == 0:
            continue
        share = float((np.isclose(vals, placeholder)).mean())
        if share >= 0.15:
            n_ph = int(np.isclose(vals, placeholder).sum())
            emit(f"!  {col}: {n_ph} rows ({share*100:.0f}%) exactly == {placeholder} "
                 f"-> looks like BREAKOUT placeholder defaults, not measured values.")
            emit(f"   These contaminate the fingerprint/correlations. Consider "
                 f"--source screener or excluding setup_type=BREAKOUT.")
            flagged = True
    # (b) Implausible base-length outliers = likely anchor mis-detection
    #     (the exact structure-accuracy failure mode we care about).
    if "base_length" in df.columns:
        bl = pd.to_numeric(df["base_length"], errors="coerce")
        outliers = df[bl > 250]
        if len(outliers):
            tk = ", ".join(f"{r.ticker}({int(r.base_length)})" for r in outliers.itertuples())
            emit(f"!  {len(outliers)} setup(s) with base_length > 250 bars (~1yr+): {tk}")
            emit("   Almost certainly anchor mis-detection picking an over-long window.")
            flagged = True
    if not flagged:
        emit("OK  No placeholder contamination or base-length outliers detected.")

    return {"valid_outcome": valid_outcome, "valid_corr": valid_corr,
            "n_live": n_live, "trig_rate": trig_rate}


# ------------------------------------------------------------------
# Section 2 - winner structural fingerprint
# ------------------------------------------------------------------
def _fingerprint_table(df: pd.DataFrame, features: list[str]) -> None:
    emit(f"{'feature':<20}{'n':>4}{'median':>10}{'q25':>10}{'q75':>10}{'min':>10}{'max':>10}")
    emit("-" * 74)
    for f in features:
        if f not in df.columns:
            continue
        d = describe_col(df[f])
        if d["n"] == 0:
            continue
        emit(f"{f:<20}{d['n']:>4}{fmt(d['median']):>10}{fmt(d['q25']):>10}"
             f"{fmt(d['q75']):>10}{fmt(d['min']):>10}{fmt(d['max']):>10}")


def section_fingerprint(df: pd.DataFrame) -> None:
    """Structural profile of the archived setups - valid even on winners-only data."""
    header("2. WINNER STRUCTURAL FINGERPRINT")
    emit("The structural profile of setups in the archive. On seed/winners data this")
    emit("is the 'what a clean tight setup looks like' template to bias toward.")

    subhdr("All setups")
    _fingerprint_table(df, STRUCTURAL_FEATURES)

    # By setup type - LPS vs REBOUND vs BREAKOUT may have distinct profiles.
    for stype in sorted(df["setup_type"].dropna().unique()):
        sub = df[df["setup_type"] == stype]
        if len(sub) < 3:
            continue
        subhdr(f"setup_type = {stype}  (n={len(sub)})")
        _fingerprint_table(sub, TIGHTNESS_FEATURES + ["base_length", "touches",
                                                      "vol_contraction", "dist_52w_high_pct"])

    # By tier - does the engine's S-tier actually correspond to tighter structure?
    for tier in ["S", "A", "B", "C", "D"]:
        sub = df[df["tier"] == tier]
        if len(sub) < 3:
            continue
        subhdr(f"tier = {tier}  (n={len(sub)})")
        _fingerprint_table(sub, TIGHTNESS_FEATURES + ["base_length", "touches", "score"])


# ------------------------------------------------------------------
# Section 3 - segmented performance
# ------------------------------------------------------------------
def _perf_row(sub: pd.DataFrame) -> dict:
    ret20 = pd.to_numeric(sub["fwd_return_20d"], errors="coerce").dropna()
    ret60 = pd.to_numeric(sub["fwd_return_60d"], errors="coerce").dropna()
    rmult = pd.to_numeric(sub["r_multiple_20d"], errors="coerce").dropna()
    trig = pd.to_numeric(sub["triggered"], errors="coerce").dropna()
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


def _print_segments(df: pd.DataFrame, by: str, label: Optional[str] = None,
                    order: Optional[list] = None) -> None:
    label = label or by
    if by not in df.columns:
        return
    subhdr(f"By {label}")
    emit(f"{label:<16}{'n':>4}{'med20d':>9}{'avg20d':>9}{'med60d':>9}"
         f"{'win%':>7}{'trig%':>7}{'avgR':>7}{'expR':>7}")
    emit("-" * 76)
    keys = order if order else sorted([k for k in df[by].dropna().unique()], key=str)
    for k in keys:
        sub = df[df[by] == k]
        if sub.empty:
            continue
        r = _perf_row(sub)
        emit(f"{str(k):<16}{r['n']:>4}{fmt(r['med_20d'], pct=True):>9}"
             f"{fmt(r['avg_20d'], pct=True):>9}{fmt(r['med_60d'], pct=True):>9}"
             f"{fmt(r['win_rate'], pct=True):>7}{fmt(r['trig_rate'], pct=True):>7}"
             f"{fmt(r['avg_rmult']):>7}{fmt(r['exp_r']):>7}")


def _bucket(df: pd.DataFrame, col: str, n_buckets: int = 3) -> pd.Series:
    """Quantile-bucket a numeric column into labelled tertiles/quartiles."""
    vals = pd.to_numeric(df[col], errors="coerce")
    try:
        labels = {3: ["low", "mid", "high"], 4: ["q1", "q2", "q3", "q4"]}[n_buckets]
        return pd.qcut(vals, n_buckets, labels=labels, duplicates="drop")
    except (ValueError, KeyError):
        return pd.Series([None] * len(df), index=df.index)


def section_performance(df: pd.DataFrame, valid: bool) -> None:
    header("3. SEGMENTED PERFORMANCE")
    if not valid:
        emit("!  Outcome metrics below are computed on winners-biased data -")
        emit("   read the SHAPE (relative differences between segments), not the")
        emit("   absolute win/trigger rates. They become trustworthy with live data.")

    _print_segments(df, "tier", order=["S", "A", "B", "C", "D"])
    _print_segments(df, "setup_type")
    if "lps_zone_type" in df.columns and df["lps_zone_type"].notna().any():
        _print_segments(df, "lps_zone_type", label="zone")
    if "phase_d_inner" in df.columns and df["phase_d_inner"].notna().any():
        _print_segments(df, "phase_d_inner", label="inner_box(0/1)")
    if "spy_trend" in df.columns and df["spy_trend"].notna().any():
        _print_segments(df, "spy_trend", label="spy_trend")

    # Tightness bucket - the prime-directive segment.
    df = df.copy()
    df["_tight_bucket"] = _bucket(df, "box_width", 3)
    if df["_tight_bucket"].notna().any():
        _print_segments(df, "_tight_bucket", label="box_width", order=["low", "mid", "high"])

    # Breadth regime, if present.
    if "breadth_pct" in df.columns and df["breadth_pct"].notna().any():
        df["_breadth_bucket"] = _bucket(df, "breadth_pct", 3)
        if df["_breadth_bucket"].notna().any():
            _print_segments(df, "_breadth_bucket", label="breadth", order=["low", "mid", "high"])


# ------------------------------------------------------------------
# Section 4 - predictor correlations
# ------------------------------------------------------------------
def section_correlations(df: pd.DataFrame, valid: bool) -> None:
    header("4. PREDICTOR CORRELATIONS vs FORWARD OUTCOMES")
    if not valid:
        emit("!  Correlations need outcome VARIANCE to mean anything. On winners-only")
        emit("   data every setup 'worked', so correlations here are near-noise.")
        emit("   Shown for plumbing-verification; revisit once live losers accrue.")

    candidates = SUB_SCORES + STRUCTURAL_FEATURES
    for target in OUTCOME_TARGETS:
        if target not in df.columns or df[target].notna().sum() < 8:
            continue
        rows = []
        for feat in candidates:
            if feat not in df.columns:
                continue
            c = safe_corr(df[feat], df[target])
            if c is not None:
                rows.append((feat, c))
        if not rows:
            continue
        rows.sort(key=lambda x: abs(x[1]), reverse=True)
        subhdr(f"vs {target}  (top predictors by |corr|)")
        emit(f"{'feature':<24}{'corr':>8}")
        emit("-" * 32)
        for feat, c in rows[:15]:
            flag = "  *" if abs(c) >= 0.30 else ""
            emit(f"{feat:<24}{c:>+8.3f}{flag}")


# ------------------------------------------------------------------
# Section 5 - prime-directive: is tightness predictive?
# ------------------------------------------------------------------
def section_tightness(df: pd.DataFrame, valid: bool) -> None:
    header("5. PRIME-DIRECTIVE TEST - IS TIGHTNESS PREDICTIVE?")
    emit("The engine's core thesis: tighter, cleaner structure -> better outcomes.")
    emit("This isolates the tightness features and tests that claim directly.")

    if not valid:
        emit()
        emit("!  Cannot test the claim yet - needs live winners AND losers so there")
        emit("   is outcome variance to separate tight-good from loose-bad.")
        emit("   Until then, here is the tightness-feature distribution among the")
        emit("   archived (mostly winning) setups - i.e. the values that tend to win:")
        subhdr("Tightness-feature distribution (archived setups)")
        _fingerprint_table(df, TIGHTNESS_FEATURES)
        return

    # With outcome variance: tight tertile vs loose tertile forward return.
    target = "fwd_return_20d"
    for feat in TIGHTNESS_FEATURES:
        if feat not in df.columns:
            continue
        d = df[[feat, target]].copy()
        d[feat] = pd.to_numeric(d[feat], errors="coerce")
        d[target] = pd.to_numeric(d[target], errors="coerce")
        d = d.dropna()
        if len(d) < 12:
            continue
        # For box_width / atr_ratio / tightness_ratio, LOWER = tighter.
        # For lps_descent_frac, HIGHER = cleaner. Normalize direction so
        # "tight" is always the better-thesis end.
        ascending_is_tight = feat in ("box_width", "atr_ratio", "tightness_ratio")
        d = d.sort_values(feat, ascending=ascending_is_tight)
        tert = max(4, len(d) // 3)
        tight = d.head(tert)[target]
        loose = d.tail(tert)[target]
        diff = tight.mean() - loose.mean()
        subhdr(f"{feat}: tight-tertile vs loose-tertile {target}")
        emit(f"  tight (n={len(tight)}): mean {fmt(tight.mean(), pct=True)}   "
             f"loose (n={len(loose)}): mean {fmt(loose.mean(), pct=True)}")
        verdict = "supports thesis OK" if diff > 0 else "CONTRADICTS thesis X"
        emit(f"  edge from tightness: {fmt(diff, pct=True)}  -> {verdict}")


# ------------------------------------------------------------------
# Orchestrator
# ------------------------------------------------------------------
def run(source: Optional[str] = None, min_rows: int = 30, md_path: Optional[str] = None) -> None:
    _LINES.clear()
    df = load_archive(source=source)

    header("CHROLLO ARCHIVE ANALYSIS")
    emit(f"DB: {_DB_PATH}")
    if source:
        emit(f"Filtered to source = '{source}'")

    comp = section_composition(df, min_rows)
    section_fingerprint(df)
    section_performance(df, comp["valid_outcome"])
    section_correlations(df, comp["valid_corr"])
    section_tightness(df, comp["valid_outcome"])

    header("END OF REPORT")

    report = "\n".join(_LINES)
    print(report)

    if md_path:
        out = md_path if os.path.isabs(md_path) else os.path.join(_PROJECT_ROOT, md_path)
        with open(out, "w", encoding="utf-8") as f:
            f.write("```\n" + report + "\n```\n")
        print(f"\n[report written to {out}]")


def main() -> None:
    ap = argparse.ArgumentParser(description="Analyze the Chrollo setup archive.")
    ap.add_argument("--source", default=None,
                    help="Restrict to a source: screener / seed / manual")
    ap.add_argument("--min-rows", type=int, default=30,
                    help="Min live rows for correlation/outcome validity (default 30)")
    ap.add_argument("--md", default=None, help="Also write a markdown copy to this path")
    args = ap.parse_args()
    run(source=args.source, min_rows=args.min_rows, md_path=args.md)


if __name__ == "__main__":
    main()
