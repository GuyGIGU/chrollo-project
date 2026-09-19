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
  6. SIGNAL EDGE & SUBTRACTION CANDIDATES (Stage 1) - rank-associates every
     scoring sub-score with realized outcome (barrier_win / r_multiple / fwd
     return) and flags each as BENEFICIAL / INERT / HARMFUL via an n-aware
     noise floor. The actionable shortlist for "subtract harmful signals".
     Read-only: flags candidates, never changes a weight.

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

from core.archive.db_path import archive_db_path
from core.archive.episodes import SetupRow, build_episodes, canonical_ids
from core.archive.outcomes import HORIZON_BARS
from core.backtest.edge_report import TAIL_MFE_COL, TAIL_THRESHOLDS
from core.pipeline.universe import DEFAULT_UNIVERSE_TYPE
from engine_alpha.scoring import taxonomy

# ------------------------------------------------------------------
# Paths & loading
# ------------------------------------------------------------------
_PROJECT_ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
_DB_PATH = archive_db_path()

# Structural features (the "picture" - produced by the Visual Structure Engine).
STRUCTURAL_FEATURES = [
    "box_width", "base_length", "touches", "r_touches", "s_touches",
    "atr_ratio", "lps_length", "breach_days", "vol_contraction",
    "tightness_ratio", "lps_descent_frac", "r_touch_vol_z", "s_touch_vol_z",
    "dist_52w_high_pct", "excess_return_6m", "rs_vs_sector_pct", "breadth_pct",
    "bars_since_bc", "descent_length",
    "inner_reaction_pct", "inner_reaction_bars",
    "contraction_count", "contraction_quality", "final_contraction_depth",
    "contraction_vol_trend",
    "base_median_spread_atr", "base_p80_spread_atr",
    "base_median_spread_pct_box", "base_tight_bar_pct",
    "support_slope_atr", "ascending_support_quality",
    "eq_r_touches", "eq_s_touches",
    "eq_r_touch_thirds", "eq_s_touch_thirds",
    "eq_lower_dwell", "eq_mid_dwell", "eq_upper_dwell", "eq_coverage",
    "trav_n_full_traversals", "trav_n_swings",
    "trav_top_dead_space", "trav_bottom_dead_space",
    "trav_rail_reaches_high", "trav_rail_reaches_low", "trav_max_swing_frac",
    "trav_last_support_frac", "trav_coil_floor_pos",
    "adr_pct",
    # Region (bin) features (Stage 2A — "where am I in the base?")
    "bin_a_bars", "bin_a_range_pct", "bin_a_volume_ratio",
    "bin_b_range_pct", "bin_b_volume_ratio",
    "bin_b_cog_end", "bin_b_cog_crossings", "bin_b_cog_rng", "bin_b_cog_corr",
    "bin_c_present", "bin_c_undercut_atr", "bin_c_recovery_bars",
    "bin_c_time_loc", "bin_c_spring_vol_z",
    "bin_d_bars", "bin_d_range_pct", "bin_d_volume_ratio",
    "bin_d_support_slope_atr", "bin_d_higher_low_frac",
    "bin_d_ascending_support_quality",
    "bin_lps_bars", "lps_position_in_box",
    "bin_d_vs_b_range_ratio", "bin_d_vs_b_volume_ratio",
    "bin_d_vs_b_support_quality_delta",
    "lps_stretch_atr", "lps_stretch_box",
    "lps_anchor_bar", "lps_low_bar",
    "lps_swing_depth_pct", "lps_swing_depth_atr", "lps_swing_depth_box",
    "last_supper_pullback_from_extension_pct",
    "last_supper_source_box_age", "last_supper_reclaim_quality",
    # Minervini Stage-2 trend template (raw context)
    "stage2_ma_stack_pass", "stage2_ma200_slope_1m_pct",
    "stage2_52w_low_pct", "stage2_trend_pass_count", "stage2_trend_pass",
    # HTF (higher-timeframe) re-accumulation context — does HTF alignment predict outcome?
    "htf_w_stage2", "htf_w_in_consol", "htf_w_reaccum", "htf_w_daily_nested", "htf_w_box_width",
    "htf_m_stage2", "htf_m_in_consol", "htf_m_reaccum", "htf_m_daily_nested", "htf_m_box_width",
]

# The two-axis read — mirrors engine_alpha.structure.Structure.horizontal / .vertical.
# A daily chart is read along two axes; splitting the fingerprint by axis lets the
# edge analysis ask WHICH ONE separates winners from losers (the validation
# question). Every column here is already archived (core/archive/writer.py) — these
# are groupings of the existing fingerprint, not new data.
#   HORIZONTAL = structure along the TIME axis: how long the base runs, how often
#     each rail is tested, and whether the swings travel the range rail-to-rail.
HORIZONTAL_FEATURES = [
    "base_length", "r_touches", "s_touches",
    "eq_r_touches", "eq_s_touches", "eq_r_touch_thirds", "eq_s_touch_thirds",
    "breach_days", "lps_length", "bin_lps_bars", "lps_position_in_box",
    "lps_anchor_bar", "lps_low_bar", "last_supper_source_box_age",
    "trav_n_full_traversals", "trav_n_swings",
    "trav_rail_reaches_high", "trav_rail_reaches_low", "trav_last_support_frac",
    "bin_c_time_loc", "bin_d_bars",
]
#   VERTICAL = magnitudes along the PRICE axis: rail levels / range height, the
#     Phase-C undercut depth, and the right-side breakout thrust.
VERTICAL_FEATURES = [
    "box_width", "tightness_ratio", "atr_ratio",
    "lps_descent_frac", "bin_c_undercut_atr",
    "lps_stretch_atr", "lps_stretch_box",
    "lps_swing_depth_pct", "lps_swing_depth_atr", "lps_swing_depth_box",
    "last_supper_pullback_from_extension_pct", "last_supper_reclaim_quality",
    "trav_top_dead_space", "trav_bottom_dead_space", "trav_max_swing_frac",
    "trav_coil_floor_pos",
    "final_contraction_depth", "bin_d_vs_b_range_ratio",
]

# Sub-scores (the Scoring Engine decomposition) — sourced from the ONE registry
# (engine_alpha/scoring/taxonomy.py) so a new/renamed/dropped sub-score can't silently
# drift out of the correlation + signal-edge analysis. Same 14 columns, same order.
SUB_SCORES = taxonomy.archive_columns()

# Outcome targets (filled by update_forward_returns).
OUTCOME_TARGETS = ["fwd_return_20d", "fwd_return_60d", "r_multiple_20d"]

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

# Tightness features specifically - the prime directive.
TIGHTNESS_FEATURES = ["box_width", "atr_ratio", "tightness_ratio",
                      "lps_descent_frac", "contraction_quality",
                      "base_median_spread_atr", "base_tight_bar_pct",
                      "bin_d_vs_b_range_ratio",
                      "bin_d_ascending_support_quality",
                      "trav_n_full_traversals", "trav_top_dead_space"]

# ── The Phase-A anchor family — measurements that move with the READER ───────
# These describe the climax->AR span, so their value is a function of where the
# engine puts the automatic reaction, not only of what the chart did. Two
# mechanisms move that anchor with no chart changing: the always-on
# climax-terminality repair (a "climax" price out-ran re-anchors to the box's own
# run-up extreme) and the dark AR_FIRST_REACTION_ENABLED tighten, whose entire
# flip IS a re-anchor — 101 of 335 firing overlays, re-measured 2026-08-31
# against the re-keyed climax (was 100 of 291 on 2026-08-13).
#
# strategy_alpha.md states the consequence — "the engine_config_version rotation
# partitions the bin_a_*/bars_since_bc/descent_length archive seam" — and
# flag_ledger.md names taking that partition HERE as the AR flip's blocking
# precondition. Nothing was taking it: the family sat in STRUCTURAL_FEATURES and
# was pooled over every epoch in the archive, so the blend read as a measurement
# rather than as an artifact of when each row was written.
#
# Within one epoch they are a variable. Across two they are an average of two
# different questions. So across a seam they are withheld from the pooled tables
# and reported on the CURRENT epoch alone, named.
PHASE_A_ANCHOR_FEATURES = ("bin_a_bars", "bin_a_range_pct", "bin_a_volume_ratio",
                           "bars_since_bc", "descent_length",
                           # Power-Play species numerics (program Task 7):
                           # anchor-family FROM BIRTH — the clock and the pole
                           # measurement are anchor-identity-derived, so they
                           # join the epoch partition in the same change that
                           # created the columns, never retroactively.
                           "pp_clock", "pp_pole_gain")


def engine_epochs(df: pd.DataFrame) -> list:
    """The distinct engine epochs present. Unversioned rows (the pre-versioning
    archive) count as their own epoch "?" — they were written by an engine too,
    just one that did not stamp itself, and folding them into a versioned pool
    is the same blend by a quieter route. Mirrors section_composition's fillna."""
    if "engine_config_version" not in df.columns:
        return []
    return sorted(df["engine_config_version"].fillna("?").astype(str).unique())


def current_epoch(df: pd.DataFrame):
    """The epoch that produced the MOST RECENT rows — the one whose numbers
    describe today's reader. Config hashes carry no ordering, so recency comes
    from the data: the epoch holding the latest scan_date. Deliberately NOT the
    largest epoch, which on this archive is an old pre-versioning one."""
    if "engine_config_version" not in df.columns or "scan_date" not in df.columns:
        return None
    known = df[df["engine_config_version"].notna()]
    if known.empty:
        return None
    latest = known.groupby("engine_config_version")["scan_date"].max()
    return None if latest.empty else str(latest.idxmax())


def anchor_seam(df: pd.DataFrame) -> bool:
    """True when the population spans an engine seam, so the Phase-A anchor
    family may not be pooled."""
    return len(engine_epochs(df)) > 1


def load_archive(source: Optional[str] = None,
                 universe_type: Optional[str] = DEFAULT_UNIVERSE_TYPE) -> pd.DataFrame:
    """Read the setup_archive table into a DataFrame (read-only).

    universe_type: scope to one universe ('us_equities' / 'us_sectors' /
        'commodities_etf'). Defaults to 'us_equities' so the ETF/sector rows that
        also archive under source='screener' can't contaminate the headline stats
        (matches the backend + core/backtest/loader.py scoping). Ignored on a
        pre-migration DB that lacks the column.
    """
    if not os.path.exists(_DB_PATH):
        raise FileNotFoundError(f"Archive DB not found at {_DB_PATH}")
    # mode=ro URI: the tool's read-only contract enforced by the connection
    # itself (same pattern as seed_recall.load_seed_rows) — a future write
    # attempt errors loudly instead of holding by discipline alone.
    con = sqlite3.connect(f"file:{_DB_PATH}?mode=ro", uri=True)
    try:
        df = pd.read_sql_query("SELECT * FROM setup_archive", con)
    finally:
        con.close()
    if source:
        df = df[df["source"] == source].copy()
    if universe_type is not None and "universe_type" in df.columns:
        df = df[df["universe_type"] == universe_type].copy()
    return df


def dedup_to_episodes(df: pd.DataFrame) -> pd.DataFrame:
    """Collapse continuation re-flags to one canonical (first-seen) row per episode.

    The screener re-flags a persisting base every day it holds, so the raw
    setup_archive carries many continuation rows for one logical setup. Counting
    each as an independent observation inflates n and biases every correlation /
    edge verdict toward whatever the long-persisting bases happened to do — a base
    seen 15 days that then ran contributes 15 correlated points, not 1. (The
    inflation is real but often modest: e.g. score_rs_bonus vs durable_win moves
    only ~-0.20 -> -0.18 under dedup and stays HARMFUL; the larger swing to INERT
    that some cuts show is target/cohort-specific — notably vs fwd_return_20d on a
    single matured cohort — not a general guarantee that dedup neutralizes a
    signal. Dedup fixes n-inflation; it does not by itself de-confound regime.)

    Reuses the SAME first-seen grouper the archive episode table and the
    ``/calibration`` canonical path use (``core.archive.episodes``), so this stays
    in lock-step with them. The kept row is each episode's first-seen anchor — the
    correct entry date, carrying its own (non-stale) forward returns.

    Degrades gracefully: returns the frame unchanged if it is empty or lacks the
    identity columns episodes needs (an older/partial DB).
    """
    needed = {"id", "ticker", "scan_date", "setup_type"}
    if df.empty or not needed.issubset(df.columns):
        return df
    universe = (df["universe_type"].fillna(DEFAULT_UNIVERSE_TYPE)
                if "universe_type" in df.columns
                else pd.Series(DEFAULT_UNIVERSE_TYPE, index=df.index))
    rows = [
        SetupRow(id=int(i), ticker=str(t), scan_date=str(d),
                 setup_type=str(s), universe_type=str(u))
        for i, t, d, s, u in zip(df["id"], df["ticker"], df["scan_date"],
                                 df["setup_type"], universe)
    ]
    keep = canonical_ids(build_episodes(rows))
    return df[df["id"].isin(keep)].copy()


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


# ------------------------------------------------------------------
# Section 1 - sample composition & bias detection
# ------------------------------------------------------------------
def section_composition(df: pd.DataFrame, min_rows: int) -> dict:
    """Report what we have and decide which analyses are statistically valid."""
    header("1. SAMPLE COMPOSITION & BIAS DETECTION")
    n = len(df)
    emit(f"Total setups (episodes): {n}")
    if n == 0:
        emit("Archive is empty - nothing to analyze.")
        return {"valid_outcome": False, "valid_corr": False}

    by_source = df["source"].fillna("unknown").value_counts().to_dict()
    by_tier = df["tier"].fillna("?").value_counts().to_dict()
    by_type = df["setup_type"].fillna("?").value_counts().to_dict()
    emit(f"By source:     {by_source}")
    emit(f"By tier:       {by_tier}")
    # Epoch honesty (task 14): stored tier/score MEAN different things across
    # an engine_config_version seam. Post-flip this shows two epochs, and
    # every tier/score slice below then blends incompatible scales — the
    # badge says so loudly (per-epoch partitioned analytics are flip-window
    # work; pre-flip this is a single-epoch no-op).
    if "engine_config_version" in df.columns:
        epochs = {str(v)[:12]: int(n) for v, n in
                  df["engine_config_version"].fillna("?").value_counts().items()}
        emit(f"By engine epoch: {epochs}")
        if len(epochs) > 1:
            emit("*** MIXED-EPOCH POPULATION: tier/score slices below blend "
                 "incompatible scoring scales — read them per-epoch. ***")
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
    #     with literal tightness/volume placeholders (0.70 / 0.50) instead of
    #     measured values. They poison the fingerprint and any correlation.
    #     Detect a suspicious mass of identical values.
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


def _anchor_family(df: pd.DataFrame) -> None:
    """The Phase-A anchor family, reported on the current epoch alone.

    Withholding it from the pooled table would delete a measurement the operator
    has; reporting it pooled would state a blend as a fact. Reporting it scoped,
    and saying which scope, is the only honest third option."""
    epoch = current_epoch(df)
    subhdr("Phase-A anchor family - NOT pooled (measures the climax->AR span)")
    emit("These move when the ENGINE re-anchors, not only when the chart does:")
    emit("the climax-terminality repair, and the dark AR_FIRST_REACTION_ENABLED")
    emit("tighten. This archive spans more than one engine epoch, so pooling them")
    emit("would average two different measurements of the same word.")
    if epoch is None:
        emit("No versioned rows here - the family is withheld with nothing to scope")
        emit("it to. Re-run once the archive carries engine_config_version.")
        return
    sub = df[df["engine_config_version"] == epoch]
    emit(f"Scoped to the CURRENT epoch {epoch[:12]} (n={len(sub)}, "
         f"{sub['scan_date'].min()} -> {sub['scan_date'].max()}):")
    if len(sub) < EDGE_MIN_N:
        emit(f"!  n < {EDGE_MIN_N}: read this as a shape, not a distribution. An "
             "epoch rotates on")
        emit("   every weight change, so a fresh one is thin until scans accrue.")
    # Only the family members the frame actually carries: the pp_* names are
    # NULL outside the rows the retired species lane wrote (2026-08-19 to 2026-09-19).
    _fingerprint_table(sub, [f for f in PHASE_A_ANCHOR_FEATURES
                             if f in sub.columns])


def section_fingerprint(df: pd.DataFrame) -> None:
    """Structural profile of the archived setups - valid even on winners-only data."""
    header("2. WINNER STRUCTURAL FINGERPRINT")
    emit("The structural profile of setups in the archive. On seed/winners data this")
    emit("is the 'what a clean tight setup looks like' template to bias toward.")

    subhdr("All setups")
    seam = anchor_seam(df)
    _fingerprint_table(df, [f for f in STRUCTURAL_FEATURES
                            if not (seam and f in PHASE_A_ANCHOR_FEATURES)])
    if seam:
        _anchor_family(df)

    # The two-axis read (mirrors Structure.horizontal / .vertical): split the
    # fingerprint into time-axis structure vs price-axis magnitude, so the edge
    # analysis can see which axis separates winners from losers.
    subhdr("Horizontal axis - time structure (duration, rail tests, traversal)")
    _fingerprint_table(df, HORIZONTAL_FEATURES)
    subhdr("Vertical axis - price magnitude (rails/height, undercut, thrust)")
    _fingerprint_table(df, VERTICAL_FEATURES)

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
        _print_segments(df, "phase_d_inner", label="inner_exists(0/1)")
    if "lps_in_inner" in df.columns and df["lps_in_inner"].notna().any():
        _print_segments(df, "lps_in_inner", label="lps_in_inner(0/1)")
    if "lps_swing_type" in df.columns and df["lps_swing_type"].notna().any():
        _print_segments(df, "lps_swing_type", label="lps_swing")
    if "inner_source" in df.columns and df["inner_source"].notna().any():
        _print_segments(df, "inner_source", label="inner_source")
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
    if anchor_seam(df):
        # Correlating a two-population blend against outcomes reports the seam,
        # not the chart — and it would report it as a predictor.
        candidates = [f for f in candidates if f not in PHASE_A_ANCHOR_FEATURES]
        emit(f"!  Withheld across an engine seam: {', '.join(PHASE_A_ANCHOR_FEATURES)}")
        emit("   (the Phase-A anchor family - see section 2 for its scoped read)")
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
        ascending_is_tight = feat in ("box_width", "atr_ratio", "tightness_ratio",
                                      "bin_d_vs_b_range_ratio")
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
# Section 6 - signal edge & subtraction candidates (Stage 1)
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

    primary = None
    for t in targets:
        if t in df.columns and pd.to_numeric(df[t], errors="coerce").notna().sum() >= min_n:
            primary = t
            break

    prim_vals = pd.to_numeric(df[primary], errors="coerce") if primary else None
    n_primary = int(prim_vals.notna().sum()) if primary else 0
    noise = max(0.15, 1.0 / np.sqrt(n_primary - 3)) if n_primary > 4 else None

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
        m_noise = max(0.15, 1.0 / np.sqrt(m_n - 3)) if m_n > 4 else None
        m_verdict = _verdict(mc, m_noise)
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


def section_signal_edge(df: pd.DataFrame, valid: bool) -> None:
    header("6. SIGNAL EDGE & SUBTRACTION CANDIDATES (Stage 1)")
    emit("Each scoring sub-score is meant to REWARD a setup. This ranks them by")
    emit("rank-association with realized outcome and flags the ones that don't")
    emit("earn their points: HARMFUL (negative) or INERT (near-zero). These are")
    emit("subtraction CANDIDATES only — re-weighting is a separate guarded step.")

    enriched = derive_outcomes(df)
    edge = signal_edge(enriched)

    # Win-quality composition — durable vs cash-grab, the operator's distinction.
    if "win_quality" in enriched.columns and enriched["win_quality"].notna().any():
        wq = enriched["win_quality"].value_counts().to_dict()
        n_dur, n_cg = wq.get("durable", 0), wq.get("cash_grab", 0)
        gaps = pd.to_numeric(enriched["bars_target_to_stop"], errors="coerce").dropna()
        subhdr("Win quality (durable vs cash-grab)")
        emit(f"  durable wins: {n_dur}   cash-grab wins: {n_cg} "
             f"(round-trip to stop within {CASH_GRAB_MAX_BARS} bars of target)")
        if len(gaps):
            emit(f"  median bars target->stop among round-trips: {fmt(gaps.median())}")

    if edge["primary_target"] is None:
        emit()
        emit("!  No outcome column has enough labelled rows yet (need durable_win /")
        emit("   barrier_win / r_multiple_20d / fwd_return_20d). Backfill, then re-run.")
        return

    emit()
    minority = (f", minority class={edge['n_minority']}" if edge.get("is_binary") else "")
    emit(f"Primary outcome: {edge['primary_target']}  (n={edge['n_primary']}{minority}, "
         f"noise floor |r| < {fmt(edge['noise_floor'])})")

    # Hard adequacy gate: refuse to emit verdicts on data that can't support
    # them. This is the structural defence against acting on a winners-only
    # mirage (e.g. "tightness is harmful" computed across 38 hand-picked wins).
    if not edge["verdicts_trustworthy"]:
        emit()
        emit("!  VERDICTS WITHHELD — the sample can't support harmful/inert calls.")
        if edge.get("is_binary"):
            emit(f"   Need >= {EDGE_MIN_N} labelled pairs AND >= {EDGE_MIN_MINORITY} of the "
                 f"minority class (e.g. losers).")
            emit(f"   Have n={edge['n_primary']}, minority class={edge['n_minority']}.")
        else:
            emit(f"   Need >= {EDGE_MIN_N} labelled pairs. Have n={edge['n_primary']}.")
        emit("   Re-run once live, mixed-outcome rows (winners AND losers) accrue.")
        return

    emit()
    pct = int(round(MAGNITUDE_THRESHOLD * 100))
    emit(f"{'sub-score':<26}{'n':>4}{'rank_r':>9}  {'verdict':<11}"
         f"{'mag_r':>8}  {f'vs P(MFE>={pct}%)':<12}")
    emit("-" * 76)
    for r in edge["rows"]:
        mark = "  <-- DISAGREE" if r.get("verdict_disagrees") else ""
        emit(f"{r['feature']:<26}{r['n']:>4}{fmt(r['primary_corr']):>9}  {r['verdict']:<11}"
             f"{fmt(r.get('magnitude_corr')):>8}  {r.get('magnitude_verdict',''):<12}{mark}")

    harmful = [r["feature"] for r in edge["rows"] if r["verdict"] == "harmful"]
    inert = [r["feature"] for r in edge["rows"] if r["verdict"] == "inert"]
    subhdr("Subtraction shortlist")
    emit(f"  HARMFUL (down-weight / zero): {', '.join(harmful) if harmful else '(none)'}")
    emit(f"  INERT   (candidate to trim):  {', '.join(inert) if inert else '(none)'}")

    # The primary target is PATH-sensitive; the magnitude column is not. Where they
    # disagree in sign the shortlist above is not a finding on its own — the signal
    # offers more and holds it less, and which of those the operator is paid for is
    # HIS call, not this tool's. Printed loudly because acting on half of it is
    # exactly how rs/uptrend went to zero (docs/rs_uptrend_reopen_2026-09-08.md).
    split = [r["feature"] for r in edge["rows"] if r.get("verdict_disagrees")]
    if split:
        subhdr("!  TARGET DISAGREEMENT — do not act on the shortlist for these")
        emit(f"  {', '.join(split)}")
        emit(f"  '{edge['primary_target']}' resolves on whichever barrier is hit FIRST")
        emit(f"  (a stop 3% under support); P(MFE>={pct}%) asks only what the setup")
        emit("  ever OFFERED, and needs no label so it keeps the rows the barrier")
        emit("  gate drops. Where they split, the signal reaches further and holds")
        emit("  it worse — or one target sees value the other cannot. Rule which")
        emit("  one you are paid for BEFORE down-weighting anything above.")


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


# ------------------------------------------------------------------
# Orchestrator
# ------------------------------------------------------------------
def run(source: Optional[str] = None, min_rows: int = 30, md_path: Optional[str] = None,
        dedup: bool = True) -> None:
    _LINES.clear()
    raw = load_archive(source=source)
    df = dedup_to_episodes(raw) if dedup else raw

    header("CHROLLO ARCHIVE ANALYSIS")
    emit(f"DB: {_DB_PATH}")
    if source:
        emit(f"Filtered to source = '{source}'")
    if dedup:
        n_removed = len(raw) - len(df)
        emit(f"Episode dedup: {len(raw)} raw rows -> {len(df)} episodes "
             f"({n_removed} continuation re-flags collapsed to the first-seen anchor).")
        emit("All sections below run on EPISODES (one row per logical setup) via the same")
        emit("first-seen grouping the archive episode table + /calibration use — raw")
        emit("continuation re-flags would inflate n and bias every correlation / edge verdict.")
    else:
        emit("!! --no-dedup: continuation re-flags NOT collapsed; stats are inflated (debug only).")

    comp = section_composition(df, min_rows)
    section_fingerprint(df)
    section_performance(df, comp["valid_outcome"])
    section_correlations(df, comp["valid_corr"])
    section_tightness(df, comp["valid_outcome"])
    section_signal_edge(df, comp["valid_corr"])

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
    ap.add_argument("--no-dedup", action="store_true",
                    help="Do NOT collapse continuation re-flags to episodes (debug; inflates stats)")
    args = ap.parse_args()
    run(source=args.source, min_rows=args.min_rows, md_path=args.md, dedup=not args.no_dedup)


if __name__ == "__main__":
    main()
