"""Per-ticker evaluation pass for the screener pipeline."""
from __future__ import annotations

import sys
from enum import Enum
from typing import Optional

import pandas as pd

from config import settings
from engine_alpha.scoring import score_setup
from engine_alpha.scoring.scoring import _ramp
from engine_alpha.structure import (
    adr_pct,
    calculate_atr,
    descent_tail_rejects,
    distance_to_52w_high_pct,
    assemble_box_narrative,
    detect_lps_tests,
    lps_range_threshold,
    measure_bar_compression,
    measure_phases,
    measure_contractions,
    measure_dwell_balance,
    measure_equilibrium,
    measure_gate_margins,
    measure_support_slope,
    measure_touch_volume,
    read_htf_context,
    scope_consolidation,
    trend_template,
)
from engine_alpha.scoring import taxonomy as _taxonomy
from engine_alpha.scoring.scoring import compose_ta_grade
from engine_alpha.structure import line_words
from engine_alpha.structure.market_structure import measure_trend_bases
from engine_alpha.structure.metrics import (
    OUTSIDE_BAR_MEASURES,
    base_rail_touches,
    base_swing_skeleton,
    measure_lps_contraction,
    measure_story_richness,
    traversals_per_20d,
)
from engine_alpha.structure.narrative import read_structure
from engine_alpha.structure.phase_d import (
    final_v_tip_bar,
    support_test_evidence_starts,
)
from engine_alpha.frames import _trim_to_period


# Distinct return sentinel for the skip-guard's caught-exception branch. A plain
# ``None`` return means a *legitimate structural reject* (the engine looked and
# saw no setup); ``EVAL_ERROR`` means the eval chain *threw* and was swallowed —
# a fundamentally different, alert-worthy event (a regression that raises on a
# SUBSET of tickers silently drops real winners on an otherwise-green build).
# The consumer (``screener._evaluate_frames``) counts these separately and never
# appends them to results (same drop behaviour as ``None``), so the flags-OFF
# scoring path stays byte-identical — this only makes the two skips DISTINGUISHABLE.
#
# It MUST be an Enum member, not a bare ``object()``: ``_evaluate_ticker`` runs in
# a ProcessPoolExecutor worker and its return value crosses the process boundary
# via pickle. A bare ``object()`` unpickles to a NEW instance, so ``is`` identity
# would fail in the parent and the count would silently stay 0. Enum members
# pickle by qualified name and round-trip to the SAME singleton, so ``result is
# EVAL_ERROR`` holds across processes.
class _EvalSkip(Enum):
    ERROR = "error"


EVAL_ERROR = _EvalSkip.ERROR


def _sma50_dip_admits(df: pd.DataFrame) -> bool:
    """The 50-day dip exception (``SMA50_DIP_EXCEPTION_ENABLED``, dark —
    miss program 2026-08-28). Consulted ONLY on the sma50-refusal branch:
    admit the refusal into chart reading when the dip under the 50-day is a
    bounded, recent event that has already recovered to the rail — the last
    close at/above SMA_50 printed within ``SMA50_DIP_MAX_SESSIONS``, and the
    close now sits within ``SMA50_DIP_MAX_ATR`` ATR_10 below it (the ATR is
    the operator's ruler; a percent here would re-invent a second yardstick).
    The SMA_200 and YoY legs still gate behind it, so a downtrend can never
    enter through a dip. Flag off -> False, byte-identical."""
    if not settings.SMA50_DIP_EXCEPTION_ENABLED:
        return False
    above = (df['Close'] >= df['SMA_50']).values
    hits = above.nonzero()[0]
    if not len(hits):
        return False                      # never above the 50-day: not a dip
    if (len(above) - 1 - int(hits[-1])) > settings.SMA50_DIP_MAX_SESSIONS:
        return False
    atr = calculate_atr(df, 10).iloc[-1]
    if pd.isna(atr) or float(atr) <= 0:
        return False
    gap = float(df['SMA_50'].iloc[-1]) - float(df['Close'].iloc[-1])
    return gap <= settings.SMA50_DIP_MAX_ATR * float(atr)


def apply_baseline_filters_with_reason(
    df: pd.DataFrame,
) -> tuple[Optional[tuple[pd.DataFrame, float]], Optional[tuple[str, dict]]]:
    """The universe baseline gate, reasoned — ONE implementation of the gate.

    Returns ``((df, yearly_return), None)`` on pass, or ``(None, (gate,
    samples))`` naming the FIRST failing gate with the sampled values. Gate
    order price -> Vol_50 -> SMA50 -> SMA200 -> YoY is the contract: first-fail
    names the reason. Comparison forms are verbatim doctrine — a NaN sample
    passes its ``<`` gate (never add isfinite hardening here).

    The price floor runs BEFORE the rolling enrichment: Close at the latest bar
    reads off the raw frame, so a sub-``MIN_PRICE`` ticker skips the copy and
    the three rolling windows entirely. Its reject samples therefore carry only
    ``close`` — the one value that exists (and the one its consumer reads).
    """
    if len(df) < 200:
        return None, ("bars", {"bars": len(df)})

    close = df['Close'].iloc[-1]
    if close < settings.MIN_PRICE:
        return None, ("price", {"close": close})

    df = df.copy()
    df['SMA_50'] = df['Close'].rolling(window=50).mean()
    df['SMA_200'] = df['Close'].rolling(window=200).mean()
    df['Vol_50'] = df['Volume'].rolling(window=50).mean()

    df['Spread'] = df['High'] - df['Low']

    latest = df.iloc[-1]
    one_year_ago_idx = max(0, len(df) - 252)
    one_year_ago = df.iloc[one_year_ago_idx]

    yearly_return = (latest['Close'] - one_year_ago['Close']) / one_year_ago['Close']

    samples = {"close": latest['Close'], "vol_50": latest['Vol_50'],
               "sma_50": latest['SMA_50'], "sma_200": latest['SMA_200'],
               "yearly_return": yearly_return}
    if latest['Vol_50'] < settings.MIN_VOLUME_50D: return None, ("vol50", samples)
    if latest['Close'] < latest['SMA_50'] and not _sma50_dip_admits(df):
        return None, ("sma50", samples)
    # The bottoming-base lane (BOTTOMING_BASE_LANE_ENABLED, dark — operator
    # ruling 2026-08-29, MDT): an sma200 refusal enters chart reading when
    # the 50-day is reclaimed. The lane's second half opens the anchor
    # seeding gate under the same flag+condition (collect_root_anchors).
    # NaN SMA_50 fails the >= closed — the exception never rides missing data.
    if latest['Close'] < latest['SMA_200'] and not (
            settings.BOTTOMING_BASE_LANE_ENABLED
            and latest['Close'] >= latest['SMA_50']):
        return None, ("sma200", samples)
    if yearly_return < settings.MIN_YEARLY_RETURN: return None, ("yoy", samples)

    return (df, float(yearly_return)), None


def apply_baseline_filters(df: pd.DataFrame) -> Optional[tuple[pd.DataFrame, float]]:
    """
    Enrich the DataFrame with rolling indicators and apply universe-level
    filters (price, volume, trend, yearly return).

    Returns ``(df, yearly_return)`` if the ticker passes, or ``None`` if
    filtered out. yearly_return is returned (not recomputed downstream) so
    the scorer reuses the exact same value the gate used.

    Vol_50 sample timing: this gate samples Vol_50 at the latest bar, while
    `detect_lps` re-samples at `eval_idx` (offsets 0 to
    LPS_SCAN_OFFSET_MAX - 1 bars back). The values can diverge for
    low-liquidity tickers; that's intentional so each gate has its own
    consistent denominator.
    """
    result, _ = apply_baseline_filters_with_reason(df)
    return result


def _structure_to_boxes(s, n: int) -> dict:
    """Adapt a narrative ``Structure`` to the ``detect_boxes`` output shape so the
    rest of the pipeline consumes it unchanged.

    Brick anchors are ABSOLUTE (df-positional); the legacy parent tuple wants
    them REBASED to the box start, because downstream recomputes
    ``swing_complete_idx = start + max(r_anchor, s_anchor)``. ``bc_anchor_bar``
    (slot 9) carries the already-resolved-local climax — the narrative path skips
    ``_resolve_phase_a_swing`` and reads ``structure.climax_bar`` directly.
    The inner dict is ``select_inner_box``'s own (``InnerBox.detection``, stored
    at election, anchors already box-relative) — no inverse map to keep in sync.
    """
    pbs = int(s.phase_b_start_bar)
    base_len = n - pbs
    box = s.box
    parent = (
        base_len, float(s.R), float(s.S), float(s.box_width),
        int(box.r_touches), int(box.s_touches), int(box.breach_days),
        int(box.r_anchor_bar) - pbs, int(box.s_anchor_bar) - pbs,
        int(s.climax_bar), pbs,
        # is_inner_box (slot 11): the PARENT box is never itself the inner box, so this
        # is always False. Both the live chain and the seed path read it via
        # structure_ctx["is_inner_box"] and feed it to measure_phases, so they pass an
        # identical False by construction — the live/seed convergence on this flag is
        # inert. If a future change makes this a real flag, the shared _run_eval_chain
        # moves live + seed together and seed-recall owns the attributable delta.
        False,
    )
    inner = s.inner.detection if s.inner is not None else None
    return {"parent": parent, "inner": inner}


def _lps_result_from_brick(lps) -> dict:
    """The ``detect_lps`` result dict of the walk's elected ``Lps`` brick. The
    inner-first-then-parent Phase-D election runs ONCE, in ``read_structure``;
    evaluation consumes the winner and never re-detects. The brick carries the
    detector's own dict (``Lps.detection``, stored at election), so there is no
    field-by-field inverse map to keep in sync with the detector."""
    return lps.detection


def descent_tail_drops(frame, parent_equilibrium, box_width, inner, lps_in_inner, atr):
    """Width-aware descent-tail gate on the ACTIVE box — the inner box's own
    equilibrium read when the LPS re-anchored there (so a clean promotable
    inner survives, e.g. QUAD), else the parent's (drops CHCT/DGII). Folded so
    the live + seed paths gate identically. ``parent_equilibrium`` is the
    already computed parent ``measure_equilibrium`` result."""
    if lps_in_inner and inner is not None:
        gate_eq = measure_equilibrium(
            frame.iloc[-inner["base_len"]:], inner["R"], inner["S"], atr)
        gate_width = float(inner["box_width"])
    else:
        gate_eq = parent_equilibrium
        gate_width = box_width
    return descent_tail_rejects(gate_eq.get("last_support_time_pos"),
                                gate_eq.get("low_position_in_box"), gate_width)


def score_equilibrium_args(equilibrium, dwell_balance, bins) -> dict:
    """The four box-relative swing facts ``score_setup`` needs from the measure
    layer. Folded so the live + seed paths feed the scorer identically."""
    return {
        "traversal_density": (equilibrium["n_full_traversals"] / equilibrium["n_swings"]
                              if equilibrium["n_swings"] else 0.0),
        # None (no measurable swing) reads as 1.0 — the no-penalty neutral for the
        # overshoot dock, which only fires above 1.0. Explicit None-check: a falsy
        # `or` would also swallow a measured 0.0 into the fabricated neutral.
        "max_swing_frac": (float(equilibrium["max_swing_frac"])
                           if equilibrium["max_swing_frac"] is not None else 1.0),
        "dwell_asymmetry": abs(dwell_balance["upper_dwell"] - dwell_balance["lower_dwell"]),
        "has_spring": bool(bins.get("bin_c_present")),
    }


def _prepare_eval_frame_with_reason(
    df: pd.DataFrame,
) -> tuple[Optional[dict], Optional[tuple[str, dict]]]:
    """The eval-frame prep, reasoned — ONE implementation (the reasonless
    ``_prepare_eval_frame`` derives from it, mirroring the baseline-gate pair
    above, so no caller can ever obtain a verdict by a path that lacks the
    reason). Returns ``(prep, None)`` on pass or ``(None, (gate, samples))``
    naming the FIRST failing universe gate. The reason is inert evidence —
    additive data on the refusal branch only; no election, gate, or scoring
    path may ever read it (geometry is the only veto)."""
    baseline, reason = apply_baseline_filters_with_reason(df)
    if baseline is None:
        return None, reason
    full_df, yearly_return = baseline

    # Keep the full (up to 5y) frame for HTF resampling, but run the DAILY
    # structure read on a stable trailing window so deepening the cache for HTF
    # does NOT feed the oldest-first root walk extra history and drift it.
    daily_df = _trim_to_period(full_df, settings.DAILY_STRUCTURE_PERIOD).copy()
    latest = daily_df.iloc[-1]
    daily_df['ATR_10'] = calculate_atr(daily_df, 10)
    daily_df['ATR_50'] = calculate_atr(daily_df, 50)

    return {
        "full_df": full_df,
        "df": daily_df,
        "latest": latest,
        "yearly_return": yearly_return,
        # The UNPREPARED input, kept by reference for the election-stability
        # probe (flag-dark): its backward shifts must re-run THIS twin on the
        # same raw frame, never a lightweight re-prep of the filtered one.
        "raw_df": df,
    }, None


def _prepare_eval_frame(df: pd.DataFrame) -> Optional[dict]:
    prep, _ = _prepare_eval_frame_with_reason(df)
    return prep


def structure_atr_row(df: pd.DataFrame):
    """THE evaluation-time ATR sample row (STRUCTURE_ATR_SAMPLE_OFFSET back
    from the right edge). One implementation for the live chain, the species
    probe, and the stability probe (EC-3): the sampled bar must be the same
    bar everywhere structurally — retyped twin expressions were the exact
    class the frame_digest/ohlcv_digest split shipped."""
    return df.iloc[-int(settings.STRUCTURE_ATR_SAMPLE_OFFSET)]


def _resolve_structure_context(df: pd.DataFrame, latest,
                               near_miss=None) -> Optional[dict]:
    # Parent (outer) is the base of record; inner is the nested companion. One
    # chronological A->B->(C?)->D narrative is the structure source of truth.
    # ONE ATR sample serves the walk, atr_ratio, and atr_for_zone below — the
    # box-carried equilibrium read is coherent with eval-time measures because
    # they share this row, structurally, not by twin expressions.
    atr_eval = structure_atr_row(df)
    # Election-trace capture (flag-dark): the trace rides the ONE walk that
    # elects the published box — same-run by construction, never a re-run.
    # None keeps the call byte-identical (the trace plumbing's no-op contract).
    trace = [] if settings.ELECTION_TRACE_EXPORT_ENABLED else None
    structure = read_structure(df, float(atr_eval['ATR_10']),
                               near_miss=near_miss, trace=trace)
    if structure is None:
        return None

    boxes = _structure_to_boxes(structure, len(df))
    base_len, res_avg, sup_avg, box_width, r_touches, s_touches, breach_days, \
        r_anchor_bar, s_anchor_bar, _bc_anchor_bar, phase_b_start_bar, \
        is_inner_box = boxes["parent"]
    inner = boxes["inner"]

    if base_len == 0:
        return None

    atr_ratio = atr_eval['ATR_10'] / atr_eval['ATR_50']

    if latest['Close'] < (sup_avg * settings.CRASH_FILTER_MULT) \
            and not settings.DEPTH_CAPS_GRADED_ENABLED:    # point 8 (step 7, dark)
        return None
    if latest['Close'] >= (res_avg * settings.EXTENSION_FILTER_MULT):
        return None

    base_df = df.iloc[-base_len:]
    atr_for_zone = float(atr_eval['ATR_10'])
    base_range_threshold = lps_range_threshold(base_df, atr_for_zone)
    # phase_b_start_bar IS len(df) - base_len by construction (base_len =
    # n - pbs in _structure_to_boxes): ONE derivation, two ctx names kept
    # for the two consumer families.
    phase_b_start = phase_b_start_bar
    swing_complete_idx = phase_b_start + max(r_anchor_bar, s_anchor_bar)

    return {
        "structure": structure,
        "election_trace": trace,
        "base_len": base_len,
        "res_avg": res_avg,
        "sup_avg": sup_avg,
        "box_width": box_width,
        "r_touches": r_touches,
        "s_touches": s_touches,
        "breach_days": breach_days,
        "r_anchor_bar": r_anchor_bar,
        "s_anchor_bar": s_anchor_bar,
        "phase_b_start_bar": phase_b_start_bar,
        "is_inner_box": is_inner_box,
        "inner": inner,
        "atr_ratio": atr_ratio,
        "base_df": base_df,
        "atr_for_zone": atr_for_zone,
        "phase_b_start": phase_b_start,
        "parent_ctx": (
            sup_avg, res_avg, base_range_threshold, base_len, swing_complete_idx,
        ),
    }


def _resolve_lps_context(df: pd.DataFrame, latest, structure_ctx: dict) -> Optional[dict]:
    # A returned Structure is a COMPLETE story, so structure.lps always exists;
    # the walk already ran the inner-first-then-parent election.
    structure = structure_ctx["structure"]
    lps_result = _lps_result_from_brick(structure.lps)
    lps_in_inner = structure.lps_in_inner

    # The ACTIVE box's LPS frame (detect_lps_tests reads it below): the inner
    # rails when the walk elected the inner-box LPS, else the parent context.
    inner = structure_ctx["inner"]
    if lps_in_inner:
        inner_base_df = df.iloc[-inner["base_len"]:]
        inner_swing_complete = inner["start_bar"] + max(
            inner["r_anchor_bar"], inner["s_anchor_bar"])
        inner_rt = lps_range_threshold(inner_base_df,
                                       structure_ctx["atr_for_zone"])
        lps_context = (inner["S"], inner["R"], inner_rt,
                       inner["base_len"], inner_swing_complete)
    else:
        lps_context = structure_ctx["parent_ctx"]

    trigger_price = lps_result['trigger_price']
    current_price = latest['Close']
    distance_to_trigger = (trigger_price - current_price) / current_price
    if distance_to_trigger <= 0:
        return None

    lps_tests = detect_lps_tests(
        df, latest, lps_context[0], lps_context[1],
        structure_ctx["atr_for_zone"], lps_context[2], lps_context[3], lps_context[4],
    )

    return {
        "lps_result": lps_result,
        "lps_in_inner": lps_in_inner,
        "lps_context": lps_context,
        "setup_state": lps_result['setup_type'],
        "lps_length": lps_result['length'],
        "lps_offset": lps_result['offset'],
        "trigger_price": trigger_price,
        "current_price": current_price,
        "vol_contraction": lps_result['vol_contraction'],
        "tightness_ratio": lps_result['tightness_ratio'],
        "lps_tests": lps_tests,
    }


def _relative_strength_context(df: pd.DataFrame, current_price, spy_6m_return: float) -> dict:
    dist_52w_high_pct = distance_to_52w_high_pct(df['High'], current_price)

    rs_lookback = settings.RS_LOOKBACK_BARS
    if len(df) > rs_lookback:
        stock_6m_return = (
            float(current_price) / float(df['Close'].iloc[-rs_lookback - 1]) - 1.0
        )
    else:
        stock_6m_return = 0.0
    return {
        "dist_52w_high_pct": dist_52w_high_pct,
        "excess_return_6m": stock_6m_return - spy_6m_return,
    }


def _measure_base_context(base_df: pd.DataFrame, res_avg: float,
                          sup_avg: float, atr_for_zone: float,
                          equilibrium: dict) -> dict:
    # THE touch predicate and the calibrated base-window swing skeleton, each
    # computed ONCE for this (window, rails, ATR): the touch-volume, dwell and
    # gate-margin reads share the masks; the contraction and support-slope
    # reads share the skeleton.
    rail_touches = base_rail_touches(base_df, res_avg, sup_avg, atr_for_zone)
    skeleton = base_swing_skeleton(base_df)
    r_touch_vol_z, s_touch_vol_z = measure_touch_volume(
        base_df, res_avg, sup_avg, atr_for_zone, rail_touches=rail_touches
    )
    return {
        "r_touch_vol_z": r_touch_vol_z,
        "s_touch_vol_z": s_touch_vol_z,
        "contraction": measure_contractions(base_df, skeleton=skeleton),
        "bar_compression": measure_bar_compression(
            base_df, res_avg - sup_avg, atr_for_zone
        ),
        "support": measure_support_slope(base_df, atr_for_zone, skeleton=skeleton),
        "dwell_balance": measure_dwell_balance(base_df, res_avg, sup_avg, atr_for_zone,
                                               rail_touches=rail_touches),
        # Measured once at box election (bricks.validate_equilibrium) on the
        # same window/rails/ATR; carried on the brick, never re-measured here.
        "equilibrium": equilibrium,
        # Gate-margin telemetry (measure-first): the elected box against the
        # respect gate's band and the dead-space gate's own close residence —
        # archived raw so threshold debates open with distributions, never
        # anecdotes. Never gates, never scores.
        "gate_margins": measure_gate_margins(base_df, res_avg, sup_avg,
                                             atr_for_zone,
                                             rail_touches=rail_touches),
    }


def _phase_d_context(df: pd.DataFrame, structure_ctx: dict, lps_ctx: dict) -> dict:
    structure = structure_ctx["structure"]
    inner = structure_ctx["inner"]
    lps_result = lps_ctx["lps_result"]
    lps_tests = lps_ctx["lps_tests"]
    lps_context = lps_ctx["lps_context"]

    # Phase A is already the resolved LOCAL root swing (resolve_phase_a brick).
    bc_anchor_bar, phase_a_end_bar = int(structure.climax_bar), int(structure.ar_bar)
    phase_d_start_bar = int(inner["start_bar"]) if inner is not None else None
    phase_d_evidence_starts = (
        {"support_tests": None, "sos_reclaim": None, "rising_support": None}
        if inner is not None
        else support_test_evidence_starts(
            lps_tests, structure_ctx["phase_b_start"], structure_ctx["base_len"]
        )
    )
    support_test_start_bar = phase_d_evidence_starts["support_tests"]
    v_tip_bar = (
        None if inner is not None
        else final_v_tip_bar(
            df, structure_ctx["phase_b_start"], structure_ctx["base_len"]
        )
    )

    bins = measure_phases(
        df,
        bc_anchor_bar=bc_anchor_bar,
        phase_b_start_bar=structure_ctx["phase_b_start_bar"],
        base_len=structure_ctx["base_len"],
        is_inner_box=structure_ctx["is_inner_box"],
        lps_offset=lps_ctx["lps_offset"],
        lps_length=lps_ctx["lps_length"],
        R=structure_ctx["res_avg"],
        S=structure_ctx["sup_avg"],
        atr_val=structure_ctx["atr_for_zone"],
        phase_d_start_bar=phase_d_start_bar,
        support_test_start_bar=support_test_start_bar,
        sos_reclaim_start_bar=phase_d_evidence_starts["sos_reclaim"],
        rising_support_start_bar=phase_d_evidence_starts["rising_support"],
        phase_a_end_bar=phase_a_end_bar,
        lps_R=lps_context[1],
        lps_S=lps_context[0],
        lps_anchor_bar=lps_result.get("lps_anchor_bar"),
        lps_low_bar=lps_result.get("lps_low_bar"),
        v_tip_bar=v_tip_bar,
        spring=structure.spring,
    )

    scope = scope_consolidation(
        df,
        bc_anchor_bar=bc_anchor_bar,
        phase_b_start_bar=structure_ctx["phase_b_start_bar"],
        base_len=structure_ctx["base_len"],
        is_inner_box=structure_ctx["is_inner_box"],
        lps_offset=lps_ctx["lps_offset"],
        lps_length=lps_ctx["lps_length"],
        lps_zone_type=lps_result.get("zone_type", "INSIDE"),
        atr_val=structure_ctx["atr_for_zone"],
        phase_d_start_bar=phase_d_start_bar,
        support_test_start_bar=support_test_start_bar,
        sos_reclaim_start_bar=phase_d_evidence_starts["sos_reclaim"],
        rising_support_start_bar=phase_d_evidence_starts["rising_support"],
        phase_a_end_bar=phase_a_end_bar,
        phase_c_recovery_bar=bins.get("bin_c_recovery_bar"),
        v_tip_bar=v_tip_bar,
        lps_zone_draw_min_descent=settings.LPS_DRAW_MIN_DESCENT_FRAC,
    )

    return {
        "bc_anchor_bar": bc_anchor_bar,
        "phase_a_end_bar": phase_a_end_bar,
        "phase_d_start_bar": phase_d_start_bar,
        "phase_d_evidence_starts": phase_d_evidence_starts,
        "support_test_start_bar": support_test_start_bar,
        "v_tip_bar": v_tip_bar,
        "bins": bins,
        "scope": scope,
        "phase_c_event_date": bins['bin_c_event_date'] or scope['phase_c_event_date'],
    }


def _score_eval_context(prepared: dict, structure_ctx: dict, lps_ctx: dict,
                        rel_ctx: dict, measurements: dict,
                        phase_ctx: dict, breadth_pct: Optional[float]) -> dict:
    df = prepared["df"]
    full_df = prepared["full_df"]
    base_df = structure_ctx["base_df"]
    bins = phase_ctx["bins"]
    contraction = measurements["contraction"]
    support = measurements["support"]

    trend = trend_template(df, dist_52w_high_pct=rel_ctx["dist_52w_high_pct"])
    adr_value = adr_pct(df, settings.ADR_WINDOW)
    # The ADR judgment is the scorer's one linear-ramp shape — ONE implementation
    # (_ramp); the unrounded [0,1] quality flows to eval-context and the wire.
    adr_quality = _ramp(adr_value, 0.0, settings.ADR_FULL_PCT, 1.0)

    # E3 setup-quality: read the L2 Wyckoff story by REUSING the bricks the engine
    # already elected onto the Structure. read_structure ran find_spring / find_lps
    # once and parked the winners on structure.spring / structure.lps (the LPS may be
    # the tighter INNER-box election). Injecting those makes the scored narrative
    # describe the spring/LPS that ACTUALLY fired — not a fresh parent-box
    # re-detection, which would mis-describe (and understate completeness for) an
    # inner-box setup. structure.box is the parent geometry frame (absolute anchors);
    # the elected LPS carries absolute df bars translated by -box.start_bar
    # (inner ⊆ parent, so no rebasing). Single call site so both eval-twins
    # inherit it. Reusing the elected bricks also drops two redundant detector
    # passes per fire.
    _struct = structure_ctx["structure"]
    narrative = assemble_box_narrative(
        df, _struct.box, structure_ctx["atr_for_zone"],
        spring=_struct.spring, lps=_struct.lps,
    )

    score_result = score_setup(
        structure_ctx["box_width"],
        structure_ctx["r_touches"],
        structure_ctx["s_touches"],
        structure_ctx["atr_ratio"],
        lps_ctx["tightness_ratio"],
        lps_ctx["vol_contraction"],
        structure_ctx["base_len"],
        prepared["yearly_return"],
        rel_ctx["excess_return_6m"],
        rel_ctx["dist_52w_high_pct"],
        breadth_pct,
        contraction['quality'],
        support['quality'],
        adr_quality,
        adr_value=adr_value,
        bar_compression=measurements["bar_compression"],
        narrative=narrative,
        **score_equilibrium_args(
            measurements["equilibrium"], measurements["dwell_balance"], bins
        ),
    )
    score = score_result['total']

    htf_ctx: dict = {}
    if settings.HTF_CONTEXT_ENABLED:
        daily_box = (structure_ctx["res_avg"], structure_ctx["sup_avg"])
        htf_ctx.update(read_htf_context(full_df, "weekly", daily_box=daily_box))
        htf_ctx.update(read_htf_context(full_df, "monthly", daily_box=daily_box))

    # Setup grades for surfacing (the A/B + a future "why ranked" chip) — present
    # only when the narrative produced a read; an abstaining narrative spreads {}
    # into the result dict and adds nothing.
    setup_fields = (
        {
            "_setup_completeness": int(narrative["completeness"]),
            "_setup_chronology": narrative["chronology"],
            "_setup_upthrust_terminal": bool(narrative["upthrust_terminal"]),
        }
        if narrative is not None else {}
    )

    # Event Map stage-1 (measure-only): the stamped whole-frame swing map + role
    # labels for FIRES, reusing the elected bricks — the story-read placement.
    # No scan-time consumer yet (archive columns / overlay payload are later
    # Event Map stages); this stages the compute so its cost is measurable and
    # emits only underscore diagnostics. Import + computation live strictly
    # inside the flag: flag-off pays zero cost and spreads {} -> byte-identical.
    event_map_fields = {}
    if settings.EVENT_MAP_ENABLED:
        from engine_alpha.structure.event_map import (
            episode_substrate_fields,
            read_role_labels,
            read_swing_map,
        )
        _struct = structure_ctx["structure"]
        _tape = read_swing_map(df, _struct.box, structure_ctx["atr_for_zone"])
        _roles = read_role_labels(
            df, _struct.box, structure_ctx["atr_for_zone"],
            spring=_struct.spring, lps=_struct.lps,
        )
        # Rail-episode substrate (Task 10): the ELECTED-geometry read — the
        # same READER the story pool consults but a DIFFERENT basis (elected
        # window + zone ATR vs the admission's candidate window + candidate
        # ATR), so the two may legally disagree (YPF: story-elected with
        # story_admitted=0). The evidence that admitted a story fire travels
        # separately in '_story_admission_profile'; the producer and the
        # tape's shape live in event_map beside the column family they feed.
        # Explicit zeros are evidence (NULL only when this block never ran).
        _win = df.iloc[int(_struct.box.start_bar):]
        event_map_fields = {
            "_event_map_n_swings": int(_tape["n_swings"]),
            "_event_map_pre_box_trend": _tape["pre_box"]["trend_state"],
            "_event_map_n_labels": int(_roles["n_labels"]),
            "_event_map_n_committed": sum(
                1 for lbl in _roles["labels"] if not lbl["in_progress"]),
            **episode_substrate_fields(_win, _struct.box.R, _struct.box.S,
                                       structure_ctx["atr_for_zone"]),
        }

    # The words on the line (final method build step 5, measure-only, dark): the
    # turn line's words over the elected box, carried as ONE JSON string and only
    # when a word flag is on. Nothing reads it: not the grade below, not the
    # archive writer, not the wire. Flag-off it reads five settings, computes
    # nothing and spreads {} -> byte-identical.
    line_words_fields = {}
    if line_words.any_word_enabled():
        _struct = structure_ctx["structure"]
        _words = line_words.read_line_words(
            df, _struct.box, structure_ctx["atr_for_zone"],
            lps=_struct.lps, inner=_struct.inner,
        )
        line_words_fields = {"_line_words_json": line_words.emitted(_words)}

    # The box's age from its first rail anchor (final method build step 6, measure-only, dark): carried only
    # with the 15-day floor on, so the young fires can be listed; nothing reads it. Flag-off {} -> byte-identical.
    base_age_fields = {}
    if settings.BASE_AGE_FROM_ANCHOR_ENABLED:
        _box = structure_ctx["structure"].box
        base_age_fields = {"_base_age_from_anchor":
                           int(len(df) - min(int(_box.r_anchor_bar), int(_box.s_anchor_bar)))}

    # The Technical Analysis Grade: the chapter composite over the SAME scored
    # terms plus the story scalars measured just above — computed HERE, in the
    # one shared eval chain, so live, seed, and the manual route produce
    # byte-identical grades by construction (never a second implementation).
    # Consumes the archived as-of scalars only (the event-map fields), never
    # the tape. Unconditional since the 2026-08-22 legacy retirement.
    _em_scalars = {k[1:]: v for k, v in event_map_fields.items()}
    _grade = compose_ta_grade(
        score_result,
        has_spring=bool(bins.get("bin_c_present")),
        event_map=_em_scalars or None,
        htf=htf_ctx or None,
        box_width=structure_ctx["box_width"],
    )
    # Archive-ready field names, mapped in this ONE place: the grade
    # family keeps its own names (_ta_grade*); per-term v2 points take
    # their registry column names (_score_<key>) so every writer maps
    # them by the same per-term literal route as their v1 siblings.
    # Family membership is DERIVED from the settled vocabulary — a
    # hand-typed twin tuple routed a future sixth compose output to a
    # lying _score_* name (2026-08-08 review, finding 4).
    ta_grade_fields = {
        ("_" + k) if k in _taxonomy.V2_RESULT_KEYS else ("_score_" + k): v
        for k, v in _grade.items()
    }
    # Wave-1 charter measurements (task 7) — pure folds over data already
    # in hand: the support-test staircase (lps_ctx carries the full
    # enumeration), the elected LPS window's bars, and row scalars.
    # Fires-only in the shared chain (unconditional since the 2026-08-22
    # retirement); measure-first — archived RAW, never gating, never
    # weighted until the operator's A/B.
    _n = len(df)
    _lps_len = int(lps_ctx["lps_length"])
    _lps_off = int(lps_ctx["lps_offset"])
    _win = (df.iloc[max(0, _n - _lps_off - _lps_len): _n - _lps_off]
            if _lps_len > 0 else df.iloc[0:0])
    _contr = measure_lps_contraction(
        lps_ctx.get("lps_tests"),
        _win["High"].tolist(), _win["Low"].tolist(),
        structure_ctx["atr_for_zone"],
    )
    _rich = measure_story_richness(
        setup_fields.get("_setup_completeness"),
        _em_scalars.get("event_map_completed_s"),
        _em_scalars.get("event_map_completed_r"),
        _em_scalars.get("event_map_alternations"),
        structure_ctx["base_len"],
    )
    # Wave-2 (task 8): the ONE bounded box-walk — base count + inter-base
    # width ratio together, on the up-segment-restricted sub-frame.
    _bases = measure_trend_bases(
        df, structure_ctx["atr_for_zone"],
        int(structure_ctx["structure"].box.start_bar),
        float(structure_ctx["box_width"]),
    )
    ta_grade_fields.update({
        "_lps_shrink_frac": _contr["lps_shrink_frac"],
        "_lps_window_classification": _contr["lps_window_classification"],
        "_story_richness_rate": _rich,
        "_trend_base_count": _bases["trend_base_count"],
        "_inter_base_width_ratio": _bases["inter_base_width_ratio"],
    })

    # Election stability (measure-only, flag-dark): does the elected reading
    # survive backward eval-day shifts? Real structures persist, junk flickers
    # (BODI 04-15 vs 04-16). Fires only; election stage only; raw diagnostics,
    # never a gate or a score. Import + compute strictly inside the flag —
    # flag-off pays zero cost and spreads {} -> byte-identical.
    stability_fields = {}
    if settings.ELECTION_STABILITY_ENABLED:
        from engine_alpha.stability import election_stability
        _probe = election_stability(prepared["raw_df"],
                                    structure_ctx["structure"], df)
        stability_fields = {
            "_stability_same_frac": _probe["same_frac"],
            "_stability_streak": int(_probe["streak"]),
            "_stability_probes": int(_probe["probes"]),
            "_stability_refused": int(_probe["refused"]),
        }

    # Strategy read (Surface the Read Task 13, flag-dark): two RAW
    # held-through-correction measures over facts the walk already resolved.
    # Import + compute strictly inside the flag: flag-off pays zero cost and
    # spreads {} -> byte-identical.
    strategy_fields = {}
    if settings.STRATEGY_READ_ENABLED:
        from engine_alpha.structure.strategy_read import strategy_read_fields
        strategy_fields = strategy_read_fields(df, structure_ctx["structure"])

    # Election-trace export (Surface the Read, flag-dark): the walk's own
    # narration, captured above from the SAME election that produced this box,
    # summarized to the compact date-anchored story — the raw trace never
    # leaves the engine. Import + compute strictly inside the flag: flag-off
    # pays zero cost and spreads {} -> byte-identical.
    trace_fields = {}
    if settings.ELECTION_TRACE_EXPORT_ENABLED:
        import json
        from engine_alpha.structure.trace_export import export_election_trace
        _exported = export_election_trace(structure_ctx.get("election_trace"), df)
        if _exported is not None:
            trace_fields = {
                "_election_trace": json.dumps(_exported, separators=(",", ":")),
            }

    return {
        "trend": trend,
        "adr_value": adr_value,
        "adr_quality": adr_quality,
        "score_result": score_result,
        "score": score,
        # The letter is derived from ta_grade against the TIER_*_STRUCT
        # ladder, resolved once inside compose_ta_grade so the wire, the archive
        # and the lens cannot disagree about it. (The legacy raw-sum ladder and
        # its TA_SCORE_V2 rollback retired at the 2026-08-22 consolidation —
        # the rollback had already stopped being faithful, council P1.)
        "tier": ta_grade_fields["_structure_tier"],
        "htf_ctx": htf_ctx,
        "setup_fields": setup_fields,
        "event_map_fields": event_map_fields,
        "line_words_fields": line_words_fields,
        "base_age_fields": base_age_fields,
        "ta_grade_fields": ta_grade_fields,
        "stability_fields": stability_fields,
        "trace_fields": trace_fields,
        "strategy_fields": strategy_fields,
    }


def _build_live_result(ticker: str, prepared: dict, structure_ctx: dict,
                       lps_ctx: dict, rel_ctx: dict, measurements: dict,
                       phase_ctx: dict, score_ctx: dict,
                       breadth_pct: Optional[float]) -> dict:
    df = prepared["df"]
    base_df = structure_ctx["base_df"]
    inner = structure_ctx["inner"]
    lps_result = lps_ctx["lps_result"]
    contraction = measurements["contraction"]
    bar_compression = measurements["bar_compression"]
    support = measurements["support"]
    dwell_balance = measurements["dwell_balance"]
    equilibrium = measurements["equilibrium"]
    gate_margins = measurements["gate_margins"]
    bins = phase_ctx["bins"]
    scope = phase_ctx["scope"]
    trend = score_ctx["trend"]

    result = {
        'Ticker': ticker,
        'Tier': score_ctx["tier"],
        'Setup': lps_ctx["setup_state"],
        'Score': score_ctx["score"],
        'Current Price': round(float(lps_ctx["current_price"]), 2),

        'Base Len': int(structure_ctx["base_len"]),
        'Box Width': float(structure_ctx["box_width"]),
        'Touches': int(structure_ctx["r_touches"] + structure_ctx["s_touches"]),
        'ATR Ratio': float(structure_ctx["atr_ratio"]),
        'LPS Length': int(lps_ctx["lps_length"]),
        'Breach Days': int(structure_ctx["breach_days"]),

        '_r_touches': int(structure_ctx["r_touches"]),
        '_s_touches': int(structure_ctx["s_touches"]),
        '_vol_contraction': float(lps_ctx["vol_contraction"]),
        '_tightness_ratio': float(lps_ctx["tightness_ratio"]),
        '_trigger_price': float(lps_ctx["trigger_price"]),
        '_sub_scores': score_ctx["score_result"],
        '_R': float(structure_ctx["res_avg"]),
        '_S': float(structure_ctx["sup_avg"]),
        '_base_len': int(structure_ctx["base_len"]),
        # Electing-pool provenance (closed set: strict/rescued/band/story) —
        # archived on every fire so a rescued cohort stays separable forever;
        # a story fire also carries the sentence that admitted it.
        '_elected_pool': str(structure_ctx["structure"].box.elected_pool),
        '_story_admission_profile': structure_ctx["structure"].box.story_admission_profile,
        '_lps_len': int(lps_ctx["lps_length"]),
        '_lps_offset': int(lps_ctx["lps_offset"]),
        '_r_anchor_bar': int(structure_ctx["r_anchor_bar"]),
        '_s_anchor_bar': int(structure_ctx["s_anchor_bar"]),
        '_bars_since_BC': int(len(df) - phase_ctx["bc_anchor_bar"]),
        '_descent_length': int(
            structure_ctx["phase_b_start_bar"] - phase_ctx["bc_anchor_bar"]
        ),
        '_phase_d_inner': bool(inner is not None),
        '_lps_in_inner': bool(lps_ctx["lps_in_inner"]),
        '_inner_R': float(inner['R']) if inner is not None else None,
        '_inner_S': float(inner['S']) if inner is not None else None,
        '_inner_box_width': float(inner['box_width']) if inner is not None else None,
        '_inner_start_bar': int(inner['start_bar']) if inner is not None else None,
        '_inner_source': inner.get('source') if inner is not None else None,
        '_inner_search_start_bar': (
            int(inner['search_start_bar']) if inner is not None else None
        ),
        '_inner_climax_bar': (int(inner['climax_bar'])
                              if inner is not None and inner.get('climax_bar') is not None
                              else None),
        '_inner_reaction_bar': (int(inner['reaction_bar'])
                                if inner is not None and inner.get('reaction_bar') is not None
                                else None),
        '_inner_reaction_pct': (float(inner['reaction_pct'])
                                if inner is not None and inner.get('reaction_pct') is not None
                                else None),
        '_inner_reaction_bars': (int(inner['reaction_bars'])
                                 if inner is not None and inner.get('reaction_bars') is not None
                                 else None),
        # The mini-consolidation POSITION (rails-are-areas ruling 2026-08-29/30:
        # the ruled FOUR-value closed set — touching_both joined 2026-08-30 —
        # at the ±0.5-ATR tolerance) + the raw signed distances it was banded
        # from (re-rulable offline, never by rescan). Labels operator-signed
        # 2026-08-30: the position token rides the wire (output/dashboard.py)
        # and fires the position chips; the raw distances stay archive-only.
        '_inner_position': inner.get('position') if inner is not None else None,
        '_inner_position_r_atr': (
            float(inner['position_distances']['r_atr'])
            if inner is not None and inner.get('position_distances') else None),
        '_inner_position_s_atr': (
            float(inner['position_distances']['s_atr'])
            if inner is not None and inner.get('position_distances') else None),
        '_dist_52w_high_pct': (float(rel_ctx["dist_52w_high_pct"])
                               if rel_ctx["dist_52w_high_pct"] is not None else None),
        '_excess_return_6m': float(rel_ctx["excess_return_6m"]),
        # Raw uptrend context (the demoted SCORE_UPTREND_BONUS ramp input) —
        # archived so the zero-weight signal stays measurable (measure-first).
        '_yearly_return': float(prepared["yearly_return"]),
        '_breadth_pct': float(breadth_pct) if breadth_pct is not None else None,
        '_r_touch_vol_z': measurements["r_touch_vol_z"],
        '_s_touch_vol_z': measurements["s_touch_vol_z"],
        '_lps_descent_frac': float(lps_result.get('descent_frac', 1.0)),
        '_lps_high_descent_frac': float(lps_result.get('high_descent_frac', 1.0)),
        '_lps_window_range_pct_box': float(lps_result.get('window_range_pct_box', 0.0)),
        '_lps_high_extension_box': float(lps_result.get('high_extension_box', 0.0)),
        '_lps_high_extension_atr': float(lps_result.get('high_extension_atr', 0.0)),
        '_lps_profile_unit': float(lps_result.get('profile_unit', 0.0)),
        '_lps_profile_unit_pct': float(lps_result.get('profile_unit_pct', 0.0)),
        '_lps_pullback_profile': float(lps_result.get('pullback_profile', 0.0)),
        '_lps_terminal_low_tolerance': float(lps_result.get('terminal_low_tolerance', 0.0)),
        '_lps_spread_expansion_profile': float(lps_result.get('spread_expansion_profile', 0.0)),
        '_lps_first_high': float(lps_result.get('first_high', 0.0)),
        '_lps_last_low': float(lps_result.get('last_low', 0.0)),
        '_lps_window_high': float(lps_result.get('window_high', 0.0)),
        '_lps_window_low': float(lps_result.get('window_low', 0.0)),
        '_lps_swing_type': lps_result.get('swing_type', 'terminal_valley'),
        '_lps_anchor_bar': (int(lps_result['lps_anchor_bar'])
                            if lps_result.get('lps_anchor_bar') is not None else None),
        '_lps_anchor_date': lps_result.get('lps_anchor_date'),
        '_lps_low_bar': (int(lps_result['lps_low_bar'])
                         if lps_result.get('lps_low_bar') is not None else None),
        '_lps_low_date': lps_result.get('lps_low_date'),
        '_lps_swing_depth_pct': lps_result.get('lps_swing_depth_pct'),
        '_lps_swing_depth_atr': lps_result.get('lps_swing_depth_atr'),
        '_lps_swing_depth_box': lps_result.get('lps_swing_depth_box'),
        '_lps_zone_type': lps_result.get('zone_type', 'INSIDE'),
        '_contraction_count': int(contraction['n_contractions']),
        '_contraction_quality': float(contraction['quality']),
        '_final_contraction_depth': (float(contraction['final_depth'])
                                     if contraction['final_depth'] is not None else None),
        '_contraction_vol_trend': (float(contraction['vol_trend'])
                                   if contraction['vol_trend'] is not None else None),
        '_base_median_spread_atr': bar_compression['median_spread_atr'],
        '_base_p80_spread_atr': bar_compression['p80_spread_atr'],
        '_base_median_spread_pct_box': bar_compression['median_spread_pct_box'],
        '_base_tight_bar_pct': float(bar_compression['tight_bar_pct']),
        '_support_slope_atr': (float(support['slope_atr'])
                               if support['slope_atr'] is not None else None),
        '_support_higher_low_frac': float(support['higher_low_frac']),
        '_ascending_support_quality': float(support['quality']),
        '_eq_r_touches': int(dwell_balance['r_touches']),
        '_eq_s_touches': int(dwell_balance['s_touches']),
        '_eq_r_touch_thirds': int(dwell_balance['r_touch_thirds']),
        '_eq_s_touch_thirds': int(dwell_balance['s_touch_thirds']),
        '_eq_lower_dwell': float(dwell_balance['lower_dwell']),
        '_eq_mid_dwell': float(dwell_balance['mid_dwell']),
        '_eq_upper_dwell': float(dwell_balance['upper_dwell']),
        '_eq_coverage': float(dwell_balance['coverage']),
        '_eq_respect_frac': gate_margins['respect_frac'],
        '_eq_engagement_respect_frac': gate_margins['engagement_respect_frac'],
        '_eq_max_excursion_atr': gate_margins['max_excursion_atr'],
        '_eq_close_lower_dwell': gate_margins['close_lower_dwell'],
        '_eq_close_mid_dwell': gate_margins['close_mid_dwell'],
        '_eq_close_upper_dwell': gate_margins['close_upper_dwell'],
        # The outside-bar vocabulary (engine-eyes Task 1): his four respect
        # forms named per bar / per run on the elected box — DESCRIPTORS,
        # archived raw, consulted by nothing. Keys derive from the ONE tuple.
        **{f'_eq_{key}': gate_margins[key] for key in OUTSIDE_BAR_MEASURES},
        '_eq_traversals_per_20d': traversals_per_20d(
            equilibrium['n_full_traversals'], len(base_df)),
        '_trav_n_full_traversals': int(equilibrium['n_full_traversals']),
        '_trav_n_swings': int(equilibrium['n_swings']),
        '_trav_top_dead_space': (float(equilibrium['top_dead_space'])
                                 if equilibrium['top_dead_space'] is not None else None),
        '_trav_bottom_dead_space': (float(equilibrium['bottom_dead_space'])
                                    if equilibrium['bottom_dead_space'] is not None else None),
        '_trav_rail_reaches_high': int(equilibrium['rail_reaches_high']),
        '_trav_rail_reaches_low': int(equilibrium['rail_reaches_low']),
        '_trav_max_swing_frac': (float(equilibrium['max_swing_frac'])
                                 if equilibrium['max_swing_frac'] is not None else None),
        '_trav_last_support_frac': (float(equilibrium['last_support_time_pos'])
                                    if equilibrium['last_support_time_pos'] is not None else None),
        '_trav_coil_floor_pos': (float(equilibrium['low_position_in_box'])
                                 if equilibrium['low_position_in_box'] is not None else None),
        '_adr_pct': float(score_ctx["adr_value"]),
        '_adr_quality': float(score_ctx["adr_quality"]),
        '_phase_a_start_date': scope['phase_a_start_date'],
        '_phase_a_end_date': scope['phase_a_end_date'],
        '_phase_b_start_date': scope['phase_b_start_date'],
        '_phase_d_start_date': scope['phase_d_start_date'],
        '_phase_c_event_date': phase_ctx["phase_c_event_date"],
        '_lps_zone_low': scope['lps_zone_low'],
        '_lps_zone_high': scope['lps_zone_high'],
        '_lps_zone_start_date': scope['lps_zone_start_date'],
        '_lps_zone_end_date': scope['lps_zone_end_date'],
        '_has_mini_consolidation': bool(scope['has_mini_consolidation']),
        '_scope_confidence': float(scope['scope_confidence']),
        '_bin_a_bars': bins['bin_a_bars'],
        '_bin_a_range_pct': bins['bin_a_range_pct'],
        '_bin_a_volume_ratio': bins['bin_a_volume_ratio'],
        '_bin_b_bars': bins['bin_b_bars'],
        '_bin_b_range_pct': bins['bin_b_range_pct'],
        '_bin_b_volume_ratio': bins['bin_b_volume_ratio'],
        '_bin_b_cog_end': bins['bin_b_cog_end'],
        '_bin_b_cog_crossings': bins['bin_b_cog_crossings'],
        '_bin_b_cog_rng': bins['bin_b_cog_rng'],
        '_bin_b_cog_corr': bins['bin_b_cog_corr'],
        '_bin_c_present': bins['bin_c_present'],
        '_bin_c_type': bins['bin_c_type'],
        '_bin_c_event_date': bins['bin_c_event_date'],
        '_bin_c_event_bar': bins['bin_c_event_bar'],
        '_bin_c_undercut_atr': bins['bin_c_undercut_atr'],
        '_bin_c_recovery_bars': bins['bin_c_recovery_bars'],
        '_bin_c_recovery_bar': bins['bin_c_recovery_bar'],
        '_bin_c_time_loc': bins['bin_c_time_loc'],
        '_bin_c_spring_vol_z': bins['bin_c_spring_vol_z'],
        '_bin_d_bars': bins['bin_d_bars'],
        '_bin_d_start_bar': bins['bin_d_start_bar'],
        '_bin_d_range_pct': bins['bin_d_range_pct'],
        '_bin_d_volume_ratio': bins['bin_d_volume_ratio'],
        '_bin_d_support_slope_atr': bins['bin_d_support_slope_atr'],
        '_bin_d_higher_low_frac': bins['bin_d_higher_low_frac'],
        '_bin_d_ascending_support_quality': bins['bin_d_ascending_support_quality'],
        '_bin_d_boundary_source': bins['bin_d_boundary_source'],
        '_phase_d_evidence_json': bins['phase_d_evidence_json'] or scope['phase_d_evidence_json'],
        '_bin_lps_bars': bins['bin_lps_bars'],
        '_lps_position_in_box': bins['lps_position_in_box'],
        '_bin_d_vs_b_range_ratio': bins['bin_d_vs_b_range_ratio'],
        '_bin_d_vs_b_volume_ratio': bins['bin_d_vs_b_volume_ratio'],
        '_bin_d_vs_b_support_quality_delta': bins['bin_d_vs_b_support_quality_delta'],
        '_lps_stretch_atr': bins['lps_stretch_atr'],
        '_lps_stretch_box': bins['lps_stretch_box'],
        '_last_supper_pullback_from_extension_pct': bins['last_supper_pullback_from_extension_pct'],
        '_last_supper_source_box_age': bins['last_supper_source_box_age'],
        '_last_supper_reclaim_quality': bins['last_supper_reclaim_quality'],
        '_last_supper_pivot_stretch_atr': bins['last_supper_pivot_stretch_atr'],
        '_last_supper_pivot_stretch_box': bins['last_supper_pivot_stretch_box'],
        '_last_supper_pullback_from_pivot_pct': bins['last_supper_pullback_from_pivot_pct'],
        '_last_supper_pivot_bars_back': bins['last_supper_pivot_bars_back'],
        '_stage2_ma_stack_pass': trend['stage2_ma_stack_pass'],
        '_stage2_ma200_slope_1m_pct': trend['stage2_ma200_slope_1m_pct'],
        '_stage2_52w_low_pct': trend['stage2_52w_low_pct'],
        '_stage2_trend_pass_count': trend['stage2_trend_pass_count'],
        '_stage2_trend_pass': trend['stage2_trend_pass'],
        '_base_close_start': float(base_df['Close'].iloc[0]),
        '_base_close_end': float(base_df['Close'].iloc[-1]),
        '_base_date_start': str(base_df.index[0])[:10],
        '_base_date_end': str(base_df.index[-1])[:10],
        **{f"_{_k}": _v for _k, _v in score_ctx["htf_ctx"].items()},
        **score_ctx.get("setup_fields", {}),   # E3: {} when the narrative abstained
        **score_ctx.get("event_map_fields", {}),  # Event Map: empty flag-off -> byte-identical
        **score_ctx.get("ta_grade_fields", {}),   # TA Grade v2: always present since the 2026-08-22 retirement
        **score_ctx.get("stability_fields", {}),  # election stability: empty flag-off -> byte-identical
        **score_ctx.get("trace_fields", {}),      # election-trace export: empty flag-off -> byte-identical
        **score_ctx.get("strategy_fields", {}),   # strategy read: empty flag-off -> byte-identical
        **score_ctx.get("line_words_fields", {}),  # words on the line: empty flag-off -> byte-identical
        **score_ctx.get("base_age_fields", {}),  # the age from the first anchor: empty flag-off -> byte-identical
    }
    # Fired tags: the chip verdicts resolved ONCE over the finished canonical
    # row — the SAME row both twins and all three writers consume, so
    # live/seed/manual chips can never diverge. (Always-on since the
    # 2026-08-22 retirement; the None guard covers degenerate rows only.)
    if result.get("_ta_grade") is not None:
        from engine_alpha.scoring.tags import resolve_fired_tags
        result["_fired_tags"] = resolve_fired_tags(result, prefixed=True)
    return result


def _run_eval_chain(ticker: str, df: pd.DataFrame,
                    spy_6m_return: float = 0.0,
                    breadth_pct: Optional[float] = None,
                    near_miss=None) -> Optional[dict]:
    """The single numeric evaluation chain shared by the live screener
    (`_evaluate_ticker`) and the seed/replay path
    (`core.archive.seed._evaluate_at_date`).

    Returns the canonical result dict, or None on a structural reject. It may RAISE
    on a degenerate frame; callers wrap it with the standard skip-guard. Keeping this
    as one function is what makes "replay at T == live at T" true by construction
    rather than by a recall test.

    ``near_miss``: the lane's refusal recorder, created by
    ``evaluate_ticker_with_near_miss`` (the only harvesting caller) and OWNED
    there — it must survive a structural reject (a refused evaluation is the
    lane's whole subject), which is why it is not constructed here. The plain
    entry and the seed/replay path pass nothing.
    """
    prepared = _prepare_eval_frame(df)
    if prepared is None:
        return None

    eval_df = prepared["df"]
    structure_ctx = _resolve_structure_context(eval_df, prepared["latest"],
                                               near_miss=near_miss)
    if structure_ctx is None:
        return None

    lps_ctx = _resolve_lps_context(eval_df, prepared["latest"], structure_ctx)
    if lps_ctx is None:
        return None

    rel_ctx = _relative_strength_context(
        eval_df, lps_ctx["current_price"], spy_6m_return
    )
    measurements = _measure_base_context(
        structure_ctx["base_df"],
        structure_ctx["res_avg"],
        structure_ctx["sup_avg"],
        structure_ctx["atr_for_zone"],
        structure_ctx["structure"].box.equilibrium,
    )

    if descent_tail_drops(
        eval_df,
        measurements["equilibrium"],
        structure_ctx["box_width"],
        structure_ctx["inner"],
        lps_ctx["lps_in_inner"],
        structure_ctx["atr_for_zone"],
    ):
        return None

    phase_ctx = _phase_d_context(eval_df, structure_ctx, lps_ctx)
    score_ctx = _score_eval_context(
        prepared, structure_ctx, lps_ctx, rel_ctx, measurements, phase_ctx, breadth_pct
    )

    return _build_live_result(
        ticker, prepared, structure_ctx, lps_ctx, rel_ctx,
        measurements, phase_ctx, score_ctx, breadth_pct
    )


def _evaluate_ticker(ticker: str, df: pd.DataFrame,
                     spy_6m_return: float = 0.0,
                     breadth_pct: Optional[float] = None) -> Optional[dict]:
    """
    Evaluate a single ticker through all screening phases.
    Returns a result dict if the ticker passes, or None if filtered out.
    This is a top-level function so it can be pickled by ProcessPoolExecutor.
    """
    # The lane records ONLY through evaluate_ticker_with_near_miss (the one
    # caller that harvests the map — review 2026-07-26 finding 14): the plain
    # entry never pays recorder work, in either flag state.
    return _run_guarded_chain(ticker, df, spy_6m_return, breadth_pct, None)


def _run_guarded_chain(ticker, df, spy_6m_return, breadth_pct, near_miss=None):
    """The chain under the standard skip-guard — folded once (EC-3) so the
    plain evaluation and the lane-carrying scan twin cannot drift."""
    try:
        result = _run_eval_chain(ticker, df, spy_6m_return, breadth_pct,
                                 near_miss=near_miss)
    except (KeyError, ValueError, IndexError, TypeError, ZeroDivisionError, AttributeError) as e:
        print(f"  [skip {ticker}] {type(e).__name__}: {e}", file=sys.stderr)
        # Return the error sentinel — NOT None — so the caller can distinguish a
        # swallowed eval crash from a genuine structural reject and count it.
        return EVAL_ERROR
    # The advisory (fundamentals/RS-line) attach moved to the CONDUCTOR
    # (core.fundamentals.post_pass, species program Task 12): the in-worker
    # call point multiplied outbound provider rate by worker count and
    # fragmented 429-cooldowns across processes. Flags-off output here was
    # already byte-identical, so the move changes nothing dark.
    return result


def evaluate_ticker_with_near_miss(ticker: str, df: pd.DataFrame,
                                   spy_6m_return: float = 0.0,
                                   breadth_pct: Optional[float] = None):
    """The scan-path twin of ``_evaluate_ticker`` used when the near-miss
    lane flag is on: returns ``(result, near_miss_rows, lane_stats)`` so the
    refusal cohort can cross the worker-pool boundary alongside the fire
    verdict. Flag-off it degrades to the plain evaluation with empty lane
    output — the screener only submits it under the flag, but the degrade
    keeps a mid-scan flag flip harmless. Top-level for pickling."""
    if not settings.NEAR_MISS_LANE_ENABLED:
        return _evaluate_ticker(ticker, df, spy_6m_return, breadth_pct), [], {}
    from engine_alpha.structure.near_miss import (  # noqa: PLC0415 — inside the flag
        NearMissRecorder, deferred_rows)
    recorder = NearMissRecorder()
    result = _run_guarded_chain(ticker, df, spy_6m_return, breadth_pct,
                                recorder)
    if result is EVAL_ERROR:
        # An aborted walk's refusal map is incomplete evidence — no lane rows
        # from a crashed evaluation (review 2026-07-26 findings 2/14); the
        # counter keeps the drop visible in the nightly stats print.
        return result, [], {"lane_errored": 1}
    try:
        rows, stats = deferred_rows(recorder, fired=isinstance(result, dict),
                                    scan_close=float(df["Close"].iloc[-1]))
    except Exception as e:  # noqa: BLE001 — the lane's contract is "never
        # touches the scan": ANY telemetry failure (including the sign-lock
        # tripwire, which stays loud in tests and the census) degrades to a
        # counted per-ticker drop, never a dead night (review finding 2).
        print(f"  [near-miss skip {ticker}] {type(e).__name__}: {e}",
              file=sys.stderr)
        return result, [], {"lane_errored": 1}
    scan_date = str(df.index[-1])[:10]
    for row in rows:
        row["ticker"] = ticker
        row["scan_date"] = scan_date
    return result, rows, stats


# ── The live species watch (the lane's core — Power-Play program Task 8) ────
# Lives HERE, beside the composed twin that is its only caller: structure
# measures (engine_alpha.structure.power_play owns the family + episode
# mechanics), the lane coordinates (2026-08-17 review, Fowler — the old
# structure-layer home forced a two-way lazy-import cycle).

# The publisher's closed-set status vocabulary — derived SERVER-SIDE in the
# lane twin; no client code may reconstruct it from null patterns (EC-28/33).
# The client label mirror (webapp/frontend/src/components/wireVocabulary.js
# POWER_PLAY_STATUS_LABELS) moves in the SAME change as this tuple.
PP_WIRE_STATUS = ("fired", "watched_ungraded", "not_watched_clock",
                  "refused_occupancy", "refused_story")

# How far back the LIVE lane looks for a watchable episode: the AR must sit
# inside this trailing window or the shelf is old news (the census, sweeping
# history, deliberately has no such bound).
LIVE_EPISODE_MAX_AR_AGE_BARS = 90


def wire_status(state: str, fired: bool) -> str:
    """One status token per watched ticker, resolved at the publisher side.
    Validates its own output: a ``PP_STATES`` widening that forgets this map
    must die HERE, loudly — the frontend renders unknown slugs verbatim by
    design, so a silent fall-through would never surface (2026-08-17 review,
    Fowler)."""
    if fired:
        token = "fired"
    elif state == "admitted_dark":
        token = "watched_ungraded"
    elif state == "refused_clock":
        token = "not_watched_clock"
    else:
        token = state                # refused_occupancy | refused_story
    if token not in PP_WIRE_STATUS:
        raise ValueError(
            f"pp_state {state!r} has no wire mapping — PP_WIRE_STATUS is the "
            f"closed publisher set ({'/'.join(PP_WIRE_STATUS)})")
    return token


def species_watch(df):
    """The per-ticker species watch — bounded to AT MOST ONE episode (the
    most recent with a live-window AR). Returns ``(watch, stats)``: ``watch``
    is ``None`` when there is nothing to record (no episode, not yet
    watchable, universe prep refused, or the read never framed the episode's
    shelf), else ``{"state", "clock", "fields", "payload"}`` where ``fields``
    feed ``power_play_fields`` and ``payload`` is the publisher row.
    Consulted ONLY by the lane twin under ``POWER_PLAY_PRESET_ENABLED``; the
    species election runs under the ONE window override + the shelf-form
    flag, scoped to this read.

    Refusal ATTRIBUTION is scoped to the episode (2026-08-17 review,
    McKinney): the trace is ROOT-level records (one per examined climax→AR
    root, the pair cascade nested under ``box_cascade``), and a refusal
    state is typed ONLY from the cascades of roots whose ``ar_bar`` is the
    episode's AR — "the cascade watched THIS shelf and said no, naming the
    leg." (The old flat any-record scan read the root level, which carries
    no verdicts, so ``refused_story`` was unreachable and every non-elected
    read typed ``refused_occupancy`` regardless of what killed it.) A
    cascade that elected a DIFFERENT base is not a refusal of the episode:
    the foreign election rides the payload as ``elected_other`` and the
    episode's own record is typed from its own roots' cascades. If the
    episode's shelf was never framed at all, nothing is recorded
    (``pp_shelf_unframed`` counts it) — never a fabricated refusal."""
    from engine_alpha.structure.htf import window_override  # noqa: PLC0415 — species-only
    from engine_alpha.structure.power_play import (  # noqa: PLC0415 — species-only
        first_legal_look, ticker_episodes)

    pole_gain = float(settings.POWER_PLAY_POLE_MIN_GAIN)
    pole_window = int(settings.POWER_PLAY_POLE_WINDOW_BARS)
    clock = int(settings.POWER_PLAY_WINDOWS["MIN_BASE_DAYS"])

    episodes = ticker_episodes("", df, pole_gain, pole_window)
    recent = [ep for ep in episodes
              if len(df) - ep["ar"] <= LIVE_EPISODE_MAX_AR_AGE_BARS]
    if not recent:
        return None, {}
    ep = recent[-1]                              # the bounded emission: one
    stats = {"pp_watched": 1}
    n = len(df)
    p_first = first_legal_look(ep, clock, df)
    fields = {"climax_date": ep["climax_date"], "ar_date": ep["ar_date"],
              "pole_gain": ep["gain"]}
    payload = {"climax": ep["climax_date"], "ar": ep["ar_date"],
               "breakout": ep["breakout_date"], "pole_gain": ep["gain"],
               "depth": ep["depth"], "clock": clock,
               "first_legal_look": (str(df.index[p_first].date())
                                    if p_first < n else None)}
    if p_first >= n:
        stats["pp_pending"] = 1                  # not yet watchable: no record
        return None, stats
    if ep["breakout"] is not None and p_first >= ep["breakout"]:
        stats["pp_refused_clock"] = 1            # even the species clock missed it
        return {"state": "refused_clock", "clock": clock,
                "fields": fields, "payload": payload}, stats

    prep, _reason = _prepare_eval_frame_with_reason(df)
    if prep is None:
        stats["pp_prep_refused"] = 1             # universe wall: out of scope
        return None, stats
    pdf = prep["df"]
    atr = float(structure_atr_row(pdf)["ATR_10"])
    trace: list = []
    override = dict(settings.POWER_PLAY_WINDOWS)
    override["POWER_PLAY_STORY_FORM_ENABLED"] = True
    override["BASE_AGE_FROM_ANCHOR_ENABLED"] = False   # the species keeps its own clock (step 12 retires the lane)
    with window_override(override):
        structure = read_structure(pdf, atr, trace=trace)

    def _raw_pos(pos_pdf: int):
        # Match in DATES — the prepared frame is 2y-trimmed, so positions
        # never compare across frames.
        if not (0 <= pos_pdf < len(pdf)):
            return None
        return int(df.index.searchsorted(pdf.index[pos_pdf]))

    if structure is not None and structure.box is not None:
        start = int(structure.box.start_bar)
        start_raw = _raw_pos(start)
        if start_raw is not None and abs(start_raw - ep["ar"]) <= 5:
            stats["pp_admitted_dark"] = 1
            R, S = float(structure.box.R), float(structure.box.S)
            shelf = pdf.iloc[start:]
            height = R - S
            tol = float(settings.TOUCH_TOLERANCE_ATR) * atr
            coverage = round(2.0 * tol / height, 4) if height > 0 else None
            fields.update(
                shelf_start_date=str(pdf.index[start].date()),
                shelf_end_date=str(pdf.index[-1].date()),
                shelf_bars=(int(len(shelf)) if height > 0 else None),
                lower_third_bars=(int((shelf["Close"] <= S + height / 3.0).sum())
                                  if height > 0 else None),
                zone_coverage=coverage,
                zone_collided=(int(coverage >= 1.0)
                               if coverage is not None else None))
            payload["elected"] = {"R": round(R, 4), "S": round(S, 4),
                                  "open": str(pdf.index[start].date())}
            return {"state": "admitted_dark", "clock": clock,
                    "fields": fields, "payload": payload}, stats
        # A foreign election is a FACT for the register, never a refusal of
        # the episode — the episode's own verdict comes from its own records.
        payload["elected_other"] = {"R": round(float(structure.box.R), 4),
                                    "S": round(float(structure.box.S), 4),
                                    "open": str(pdf.index[start].date())}

    if not trace:
        stats["pp_no_seed"] = 1                  # nothing seeded: Task 9's seam
        return None, stats
    # Scope by ROOT identity: the episode's roots name their AR explicitly
    # (±5 sessions covers the walk's own anchor jitter, the admission
    # match's tolerance).
    ep_recs = []
    for rec in trace:
        ar_pdf = rec.get("ar_bar")
        if ar_pdf is None:
            continue
        ar_raw = _raw_pos(int(ar_pdf))
        if ar_raw is None or abs(ar_raw - ep["ar"]) > 5:
            continue
        ep_recs.extend(c for c in (rec.get("box_cascade") or [])
                       if c.get("verdict") == "rejected")
    if not ep_recs:
        # The cascade ran but never framed the episode's shelf — an absent
        # examination, not a refusal; fabricating one is false attribution.
        stats["pp_shelf_unframed"] = 1
        return None, stats
    story = any(rec.get("stage") == "story" for rec in ep_recs)
    state = "refused_story" if story else "refused_occupancy"
    stats[f"pp_{state}"] = 1
    return {"state": state, "clock": clock,
            "fields": fields, "payload": payload}, stats


def evaluate_ticker_with_power_play(ticker: str, df: pd.DataFrame,
                                    spy_6m_return: float = 0.0,
                                    breadth_pct: Optional[float] = None):
    """The species-lane twin (Power-Play program Task 8): COMPOSES with the
    near-miss twin instead of replacing it — the base submission is exactly
    what the near-miss-aware path would have returned, and the species watch
    rides behind it. Returns ``(base, pp_row, pp_stats)`` where ``base`` is
    the near-miss triple (lane on) or the plain result (lane off);
    ``pp_row`` is the publisher's candidate row or ``None``; ``pp_stats``
    are the lane's counters (incl. ``pp_eval_ms``, the summed in-worker cost
    the ScanTimer pseudo-phase aggregates). Flag-off degrades to the base
    with empty lane output. A watched FIRE carries the archive family on its
    result row (the Task 7 producer picks it up); every lane failure is
    swallowed at this seam and counted — never converting a firing result
    into a drop (EC-20), and the error path keeps the counters already
    earned plus the elapsed time, so the EC-8 cost instrument stays honest
    on exactly the failing tickers (2026-08-17 review, Performance/Ramírez).
    Top-level for pickling."""
    import time  # noqa: PLC0415 — only the lane pays for it

    if settings.NEAR_MISS_LANE_ENABLED:
        base = evaluate_ticker_with_near_miss(ticker, df, spy_6m_return,
                                              breadth_pct)
        result = base[0]
    else:
        base = _evaluate_ticker(ticker, df, spy_6m_return, breadth_pct)
        result = base
    if not settings.POWER_PLAY_PRESET_ENABLED:
        return base, None, {}
    if result is EVAL_ERROR:
        # A crashed base evaluation is an UNKNOWN verdict, not a no-fire:
        # publishing a watch row would stamp a definitive-looking status on
        # a night the paying read never finished. The near-miss lane refuses
        # the same way — an aborted walk is incomplete evidence.
        return base, None, {"pp_base_errored": 1}
    t0 = time.perf_counter()
    stats: dict = {}
    row = None
    try:
        from engine_alpha.structure.power_play import power_play_fields  # noqa: PLC0415
        watch, w_stats = species_watch(df)
        stats.update(w_stats)
        if watch is not None:
            fired = isinstance(result, dict)
            row = dict(watch["payload"])
            row["ticker"] = ticker
            row["status"] = wire_status(watch["state"], fired)
            fields = power_play_fields(watch["state"], watch["clock"],
                                       **watch["fields"])
            if fired:
                result.update(fields)   # the fire row carries the family
    except Exception as e:  # noqa: BLE001 — the lane never touches the scan
        print(f"  [power-play skip {ticker}] {type(e).__name__}: {e}",
              file=sys.stderr)
        stats["pp_errored"] = 1
        row = None                      # a half-built row must not publish
    stats["pp_eval_ms"] = round((time.perf_counter() - t0) * 1000, 1)
    return base, row, stats
