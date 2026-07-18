"""Per-ticker evaluation pass for the screener pipeline."""
from __future__ import annotations

import sys
from enum import Enum
from typing import Optional

import pandas as pd

from config import settings
from engine_alpha.scoring import calculate_tier, score_setup
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
from engine_alpha.structure.metrics import base_swing_skeleton
from engine_alpha.structure.narrative import read_structure
from engine_alpha.structure.phase_d import (
    drawn_support_tests,
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


def apply_baseline_filters_with_reason(
    df: pd.DataFrame,
) -> tuple[Optional[tuple[pd.DataFrame, float]], Optional[tuple[str, dict]]]:
    """The universe baseline gate, reasoned — ONE implementation of the gate.

    Returns ``((df, yearly_return), None)`` on pass, or ``(None, (gate,
    samples))`` naming the FIRST failing gate with the sampled values. Gate
    order price -> Vol_50 -> SMA50 -> SMA200 -> YoY is the contract: first-fail
    names the reason. Comparison forms are verbatim doctrine — a NaN sample
    passes its ``<`` gate (never add isfinite hardening here).
    """
    if len(df) < 200:
        return None, ("bars", {"bars": len(df)})

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
    if latest['Close'] < settings.MIN_PRICE: return None, ("price", samples)
    if latest['Vol_50'] < settings.MIN_VOLUME_50D: return None, ("vol50", samples)
    if latest['Close'] < latest['SMA_50']: return None, ("sma50", samples)
    if latest['Close'] < latest['SMA_200']: return None, ("sma200", samples)
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
    `detect_lps` re-samples at `eval_idx` (offset 0..3 bars back). The
    values can diverge for low-liquidity tickers; that's intentional so
    each gate has its own consistent denominator.
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
        "max_swing_frac": equilibrium["max_swing_frac"] or 1.0,
        "dwell_asymmetry": abs(dwell_balance["upper_dwell"] - dwell_balance["lower_dwell"]),
        "has_spring": bool(bins.get("bin_c_present")),
    }


def _prepare_eval_frame(df: pd.DataFrame) -> Optional[dict]:
    baseline = apply_baseline_filters(df)
    if baseline is None:
        return None
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
    }


def _resolve_structure_context(df: pd.DataFrame, latest) -> Optional[dict]:
    # Parent (outer) is the base of record; inner is the nested companion. One
    # chronological A->B->(C?)->D narrative is the structure source of truth.
    # ONE ATR sample serves the walk, atr_ratio, and atr_for_zone below — the
    # box-carried equilibrium read is coherent with eval-time measures because
    # they share this row, structurally, not by twin expressions.
    atr_eval = df.iloc[-settings.STRUCTURE_ATR_SAMPLE_OFFSET]
    structure = read_structure(df, float(atr_eval['ATR_10']))
    if structure is None:
        return None

    boxes = _structure_to_boxes(structure, len(df))
    base_len, res_avg, sup_avg, box_width, r_touches, s_touches, breach_days, \
        r_anchor_bar, s_anchor_bar, bc_anchor_bar, phase_b_start_bar, \
        is_inner_box = boxes["parent"]
    inner = boxes["inner"]

    if base_len == 0:
        return None

    atr_ratio = atr_eval['ATR_10'] / atr_eval['ATR_50']

    if latest['Close'] < (sup_avg * settings.CRASH_FILTER_MULT):
        return None
    if latest['Close'] >= (res_avg * settings.EXTENSION_FILTER_MULT):
        return None

    base_df = df.iloc[-base_len:]
    atr_for_zone = float(atr_eval['ATR_10'])
    base_range_threshold = lps_range_threshold(base_df, atr_for_zone)
    phase_b_start = len(df) - base_len
    swing_complete_idx = phase_b_start + max(r_anchor_bar, s_anchor_bar)

    return {
        "structure": structure,
        "base_len": base_len,
        "res_avg": res_avg,
        "sup_avg": sup_avg,
        "box_width": box_width,
        "r_touches": r_touches,
        "s_touches": s_touches,
        "breach_days": breach_days,
        "r_anchor_bar": r_anchor_bar,
        "s_anchor_bar": s_anchor_bar,
        "bc_anchor_bar": bc_anchor_bar,
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
    r_touch_vol_z, s_touch_vol_z = measure_touch_volume(
        base_df, res_avg, sup_avg, atr_for_zone
    )
    # The calibrated base-window swing skeleton, computed ONCE — the
    # contraction and support-slope reads consume the same election.
    skeleton = base_swing_skeleton(base_df)
    return {
        "r_touch_vol_z": r_touch_vol_z,
        "s_touch_vol_z": s_touch_vol_z,
        "contraction": measure_contractions(base_df, skeleton=skeleton),
        "bar_compression": measure_bar_compression(
            base_df, res_avg - sup_avg, atr_for_zone
        ),
        "support": measure_support_slope(base_df, atr_for_zone, skeleton=skeleton),
        "dwell_balance": measure_dwell_balance(base_df, res_avg, sup_avg, atr_for_zone),
        # Measured once at box election (bricks.validate_equilibrium) on the
        # same window/rails/ATR; carried on the brick, never re-measured here.
        "equilibrium": equilibrium,
        # Gate-margin telemetry (measure-first): the elected box against the
        # respect gate's band and the dead-space gate's own close residence —
        # archived raw so threshold debates open with distributions, never
        # anecdotes. Never gates, never scores.
        "gate_margins": measure_gate_margins(base_df, res_avg, sup_avg,
                                             atr_for_zone),
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

    spring_recovery_bar = bins.get("bin_c_recovery_bar")
    lps_draw_floor = (
        spring_recovery_bar if spring_recovery_bar is not None
        else v_tip_bar if v_tip_bar is not None
        else phase_d_start_bar
    )
    drawn_lps_tests = drawn_support_tests(
        lps_tests,
        right_floor_bar=lps_draw_floor,
        min_descent_frac=settings.LPS_DRAW_MIN_DESCENT_FRAC,
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
        "drawn_lps_tests": drawn_lps_tests,
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

    # E3 puzzle-quality: read the L2 Wyckoff puzzle by REUSING the bricks the engine
    # already elected onto the Structure. read_structure ran find_spring / find_lps
    # once and parked the winners on structure.spring / structure.lps (the LPS may be
    # the tighter INNER-box election). Injecting those makes the scored narrative
    # describe the spring/LPS that ACTUALLY fired — not a fresh parent-box
    # re-detection, which would mis-describe (and understate completeness for) an
    # inner-box setup. structure.box is the parent geometry frame (absolute anchors);
    # the elected LPS carries absolute df bars translated by -box.start_bar
    # (inner ⊆ parent, so no rebasing). Computed ONLY when the flag is on (flag-off
    # pays zero cost); single call site so both eval-twins inherit it. Reusing the
    # elected bricks also drops two redundant detector passes per fire.
    narrative = None
    if settings.PUZZLE_SCORE_ENABLED:
        _struct = structure_ctx["structure"]
        narrative = assemble_box_narrative(
            df, _struct.box, structure_ctx["atr_for_zone"],
            spring=_struct.spring, lps=_struct.lps,
        )

    score_result = score_setup(
        structure_ctx["box_width"],
        structure_ctx["r_touches"],
        structure_ctx["s_touches"],
        structure_ctx["res_avg"],
        structure_ctx["sup_avg"],
        base_df,
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

    # Puzzle grades for surfacing (the A/B + a future "why ranked" chip) — present
    # ONLY when the flag is on (narrative computed); flag-off this is {} and the
    # spread into the result dict adds nothing -> byte-identical.
    puzzle_fields = (
        {
            "_puzzle_completeness": int(narrative["completeness"]),
            "_puzzle_chronology": narrative["chronology"],
            "_puzzle_upthrust_terminal": bool(narrative["upthrust_terminal"]),
        }
        if narrative is not None else {}
    )

    # Event Map stage-1 (measure-only): the stamped whole-frame swing map + role
    # labels for FIRES, reusing the elected bricks — the puzzle-read placement.
    # No scan-time consumer yet (archive columns / overlay payload are later
    # Event Map stages); this stages the compute so its cost is measurable and
    # emits only underscore diagnostics. Import + computation live strictly
    # inside the flag: flag-off pays zero cost and spreads {} -> byte-identical.
    event_map_fields = {}
    if settings.EVENT_MAP_ENABLED:
        from engine_alpha.structure.event_map import read_role_labels, read_swing_map
        _struct = structure_ctx["structure"]
        _tape = read_swing_map(df, _struct.box, structure_ctx["atr_for_zone"])
        _roles = read_role_labels(
            df, _struct.box, structure_ctx["atr_for_zone"],
            spring=_struct.spring, lps=_struct.lps,
        )
        event_map_fields = {
            "_event_map_n_swings": int(_tape["n_swings"]),
            "_event_map_pre_box_trend": _tape["pre_box"]["trend_state"],
            "_event_map_n_labels": int(_roles["n_labels"]),
            "_event_map_n_committed": sum(
                1 for lbl in _roles["labels"] if not lbl["in_progress"]),
        }

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

    return {
        "trend": trend,
        "adr_value": adr_value,
        "adr_quality": adr_quality,
        "score_result": score_result,
        "score": score,
        "tier": calculate_tier(score, structure_ctx["box_width"]),
        "htf_ctx": htf_ctx,
        "puzzle_fields": puzzle_fields,
        "event_map_fields": event_map_fields,
        "stability_fields": stability_fields,
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

    return {
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
        '_dist_52w_high_pct': (float(rel_ctx["dist_52w_high_pct"])
                               if rel_ctx["dist_52w_high_pct"] is not None else None),
        '_excess_return_6m': float(rel_ctx["excess_return_6m"]),
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
        '_lps_tests': phase_ctx["drawn_lps_tests"],
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
        '_eq_close_lower_dwell': gate_margins['close_lower_dwell'],
        '_eq_close_mid_dwell': gate_margins['close_mid_dwell'],
        '_eq_close_upper_dwell': gate_margins['close_upper_dwell'],
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
        **score_ctx.get("puzzle_fields", {}),   # E3: empty flag-off -> byte-identical
        **score_ctx.get("event_map_fields", {}),  # Event Map: empty flag-off -> byte-identical
        **score_ctx.get("stability_fields", {}),  # election stability: empty flag-off -> byte-identical
    }


def _run_eval_chain(ticker: str, df: pd.DataFrame,
                    spy_6m_return: float = 0.0,
                    breadth_pct: Optional[float] = None) -> Optional[dict]:
    """The single numeric evaluation chain shared by the live screener
    (`_evaluate_ticker`) and the seed/replay path
    (`core.archive.seed._evaluate_at_date`).

    Returns the canonical result dict, or None on a structural reject. It may RAISE
    on a degenerate frame; callers wrap it with the standard skip-guard. Keeping this
    as one function is what makes "replay at T == live at T" true by construction
    rather than by a recall test.
    """
    prepared = _prepare_eval_frame(df)
    if prepared is None:
        return None

    eval_df = prepared["df"]
    structure_ctx = _resolve_structure_context(eval_df, prepared["latest"])
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


def _attach_advisory_metadata(ticker: str, df: pd.DataFrame, result: dict) -> None:
    """Attach flag-gated ADVISORY (fundamentals / RS-line / days-to-earnings)
    metadata onto an ALREADY-BUILT firing result, in place.

    Deliberately OUTSIDE ``_run_eval_chain``: the canonical numeric chain (shared
    with the seed/shadow path) must stay byte-identical, so this runs only on the
    live wrapper, only after a setup has fired, and only when an advisory flag is
    ON. With all flags OFF ``per_ticker_advisory`` returns ``{}`` and makes zero
    provider calls — so flags-OFF output is unchanged (shadow guard). The fields
    it adds are ``_``-prefixed advisory metadata the writer/dashboard surface as
    tag-chip data; they NEVER feed Score/Tier or any geometric veto. Any failure
    is swallowed so the advisory layer can never drop or break a real setup."""
    try:
        from core.fundamentals.advisory import per_ticker_advisory

        extra = per_ticker_advisory(ticker, df)
        if extra:
            result.update(extra)
    except Exception as e:  # advisory must never fail a firing setup
        print(f"  [advisory skip {ticker}] {type(e).__name__}: {e}", file=sys.stderr)


def _evaluate_ticker(ticker: str, df: pd.DataFrame,
                     spy_6m_return: float = 0.0,
                     breadth_pct: Optional[float] = None) -> Optional[dict]:
    """
    Evaluate a single ticker through all screening phases.
    Returns a result dict if the ticker passes, or None if filtered out.
    This is a top-level function so it can be pickled by ProcessPoolExecutor.
    """
    try:
        result = _run_eval_chain(ticker, df, spy_6m_return, breadth_pct)
    except (KeyError, ValueError, IndexError, TypeError, ZeroDivisionError, AttributeError) as e:
        print(f"  [skip {ticker}] {type(e).__name__}: {e}", file=sys.stderr)
        # Return the error sentinel — NOT None — so the caller can distinguish a
        # swallowed eval crash from a genuine structural reject and count it.
        return EVAL_ERROR
    if result is not None:
        _attach_advisory_metadata(ticker, df, result)
    return result
