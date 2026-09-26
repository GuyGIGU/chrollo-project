"""The archive report card's text: its six sections and their formatting.

Each ``section_*`` function appends lines to ``_LINES``; ``core.archive.analyze``
clears the buffer, runs the sections in order and prints the joined report.
Column lists come from ``analyze_features`` and the statistics from
``analyze_stats``; this module decides what to say about them.
"""
from __future__ import annotations

from typing import Optional

import numpy as np
import pandas as pd

from core.archive.analyze_features import (
    HORIZONTAL_FEATURES,
    OUTCOME_TARGETS,
    PHASE_A_ANCHOR_FEATURES,
    STRUCTURAL_FEATURES,
    SUB_SCORES,
    TIGHTNESS_FEATURES,
    VERTICAL_FEATURES,
    anchor_seam,
    current_epoch,
)
from core.archive.analyze_stats import (
    CASH_GRAB_MAX_BARS,
    EDGE_MIN_MINORITY,
    EDGE_MIN_N,
    MAGNITUDE_THRESHOLD,
    _bucket,
    _perf_row,
    derive_outcomes,
    describe_col,
    ranked_correlations,
    signal_edge,
    tight_vs_loose,
)

# The magnitude threshold as a whole percent, for the P(MFE>=N%) labels.
_MAGNITUDE_PCT = int(round(MAGNITUDE_THRESHOLD * 100))

# Segment columns printed only when the archive carries them with a value:
# (column, label in the table).
_OPTIONAL_SEGMENTS = (
    ("lps_zone_type", "zone"),
    ("phase_d_inner", "inner_exists(0/1)"),
    ("lps_in_inner", "lps_in_inner(0/1)"),
    ("lps_swing_type", "lps_swing"),
    ("inner_source", "inner_source"),
    ("spy_trend", "spy_trend"),
)

# Tertile-bucketed segments: tightness (the prime-directive segment), then the
# breadth regime.
_TERTILE_SEGMENTS = (("box_width", "box_width"), ("breadth_pct", "breadth"))


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
    n_live = len(df[df["source"] == "screener"])

    valid_outcome, valid_corr = _validity_verdict(trig_rate, n_live, min_rows)
    _data_quality_flags(df)
    return {"valid_outcome": valid_outcome, "valid_corr": valid_corr,
            "n_live": n_live, "trig_rate": trig_rate}


def _validity_verdict(trig_rate: Optional[float], n_live: int,
                      min_rows: int) -> tuple[bool, bool]:
    """Say which analyses the sample supports: (valid_outcome, valid_corr)."""
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
        valid_corr = False

    if valid_outcome and valid_corr:
        emit("OK  Sample looks adequate for outcome + correlation analysis.")
    return valid_outcome, valid_corr


def _data_quality_flags(df: pd.DataFrame) -> None:
    subhdr("Data-quality flags")
    flagged = False
    # (a) Placeholder contamination: legacy BREAKOUT seed rows were written
    #     with literal tightness/volume placeholders (0.70 / 0.50) instead of
    #     measured values. They poison the fingerprint and any correlation.
    #     Detect a suspicious mass of identical values.
    for col, placeholder in (("tightness_ratio", 0.70), ("vol_contraction", 0.50)):
        if col not in df.columns:
            continue
        vals = pd.to_numeric(df[col], errors="coerce").dropna()
        if len(vals) == 0:
            continue
        hits = np.isclose(vals, placeholder)
        share = float(hits.mean())
        if share >= 0.15:
            emit(f"!  {col}: {int(hits.sum())} rows ({share*100:.0f}%) exactly == {placeholder} "
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


def section_performance(df: pd.DataFrame, valid: bool) -> None:
    header("3. SEGMENTED PERFORMANCE")
    if not valid:
        emit("!  Outcome metrics below are computed on winners-biased data -")
        emit("   read the SHAPE (relative differences between segments), not the")
        emit("   absolute win/trigger rates. They become trustworthy with live data.")

    _print_segments(df, "tier", order=["S", "A", "B", "C", "D"])
    _print_segments(df, "setup_type")
    for col, label in _OPTIONAL_SEGMENTS:
        if col in df.columns and df[col].notna().any():
            _print_segments(df, col, label=label)

    for col, label in _TERTILE_SEGMENTS:
        if col not in df.columns or not df[col].notna().any():
            continue
        bucketed = df.assign(_tertile=_bucket(df, col))
        if bucketed["_tertile"].notna().any():
            _print_segments(bucketed, "_tertile", label=label, order=["low", "mid", "high"])


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
        rows = ranked_correlations(df, candidates, target)
        if not rows:
            continue
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
        split = tight_vs_loose(df, feat, target)
        if split is None:
            continue
        tight, loose = split
        diff = tight.mean() - loose.mean()
        subhdr(f"{feat}: tight-tertile vs loose-tertile {target}")
        emit(f"  tight (n={len(tight)}): mean {fmt(tight.mean(), pct=True)}   "
             f"loose (n={len(loose)}): mean {fmt(loose.mean(), pct=True)}")
        verdict = "supports thesis OK" if diff > 0 else "CONTRADICTS thesis X"
        emit(f"  edge from tightness: {fmt(diff, pct=True)}  -> {verdict}")


# ------------------------------------------------------------------
# Section 6 - signal edge & subtraction candidates (Stage 1)
# ------------------------------------------------------------------
def section_signal_edge(df: pd.DataFrame, valid: bool) -> None:
    header("6. SIGNAL EDGE & SUBTRACTION CANDIDATES (Stage 1)")
    emit("Each scoring sub-score is meant to REWARD a setup. This ranks them by")
    emit("rank-association with realized outcome and flags the ones that don't")
    emit("earn their points: HARMFUL (negative) or INERT (near-zero). These are")
    emit("subtraction CANDIDATES only — re-weighting is a separate guarded step.")

    enriched = derive_outcomes(df)
    edge = signal_edge(enriched)
    _win_quality(enriched)

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
        _verdicts_withheld(edge)
        return

    _verdict_table(edge)
    _subtraction_shortlist(edge)
    _target_disagreement(edge)


def _win_quality(enriched: pd.DataFrame) -> None:
    """Durable vs cash-grab wins — the operator's distinction."""
    if "win_quality" not in enriched.columns or not enriched["win_quality"].notna().any():
        return
    wq = enriched["win_quality"].value_counts().to_dict()
    n_dur, n_cg = wq.get("durable", 0), wq.get("cash_grab", 0)
    gaps = pd.to_numeric(enriched["bars_target_to_stop"], errors="coerce").dropna()
    subhdr("Win quality (durable vs cash-grab)")
    emit(f"  durable wins: {n_dur}   cash-grab wins: {n_cg} "
         f"(round-trip to stop within {CASH_GRAB_MAX_BARS} bars of target)")
    if len(gaps):
        emit(f"  median bars target->stop among round-trips: {fmt(gaps.median())}")


def _verdicts_withheld(edge: dict) -> None:
    emit()
    emit("!  VERDICTS WITHHELD — the sample can't support harmful/inert calls.")
    if edge.get("is_binary"):
        emit(f"   Need >= {EDGE_MIN_N} labelled pairs AND >= {EDGE_MIN_MINORITY} of the "
             f"minority class (e.g. losers).")
        emit(f"   Have n={edge['n_primary']}, minority class={edge['n_minority']}.")
    else:
        emit(f"   Need >= {EDGE_MIN_N} labelled pairs. Have n={edge['n_primary']}.")
    emit("   Re-run once live, mixed-outcome rows (winners AND losers) accrue.")


def _verdict_table(edge: dict) -> None:
    emit()
    emit(f"{'sub-score':<26}{'n':>4}{'rank_r':>9}  {'verdict':<11}"
         f"{'mag_r':>8}  {f'vs P(MFE>={_MAGNITUDE_PCT}%)':<12}")
    emit("-" * 76)
    for r in edge["rows"]:
        mark = "  <-- DISAGREE" if r.get("verdict_disagrees") else ""
        emit(f"{r['feature']:<26}{r['n']:>4}{fmt(r['primary_corr']):>9}  {r['verdict']:<11}"
             f"{fmt(r.get('magnitude_corr')):>8}  {r.get('magnitude_verdict',''):<12}{mark}")


def _subtraction_shortlist(edge: dict) -> None:
    harmful = [r["feature"] for r in edge["rows"] if r["verdict"] == "harmful"]
    inert = [r["feature"] for r in edge["rows"] if r["verdict"] == "inert"]
    subhdr("Subtraction shortlist")
    emit(f"  HARMFUL (down-weight / zero): {', '.join(harmful) if harmful else '(none)'}")
    emit(f"  INERT   (candidate to trim):  {', '.join(inert) if inert else '(none)'}")


def _target_disagreement(edge: dict) -> None:
    """The primary target is PATH-sensitive; the magnitude column is not. Where
    they disagree in sign the shortlist is not a finding on its own — the signal
    offers more and holds it less, and which of those the operator is paid for
    is HIS call, not this tool's. Printed loudly because acting on half of it is
    exactly how rs/uptrend went to zero (docs/rs_uptrend_reopen_2026-09-08.md)."""
    split = [r["feature"] for r in edge["rows"] if r.get("verdict_disagrees")]
    if not split:
        return
    subhdr("!  TARGET DISAGREEMENT — do not act on the shortlist for these")
    emit(f"  {', '.join(split)}")
    emit(f"  '{edge['primary_target']}' resolves on whichever barrier is hit FIRST")
    emit(f"  (a stop 3% under support); P(MFE>={_MAGNITUDE_PCT}%) asks only what the setup")
    emit("  ever OFFERED, and needs no label so it keeps the rows the barrier")
    emit("  gate drops. Where they split, the signal reaches further and holds")
    emit("  it worse — or one target sees value the other cannot. Rule which")
    emit("  one you are paid for BEFORE down-weighting anything above.")
