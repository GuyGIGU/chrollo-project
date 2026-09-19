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
from engine_alpha.structure.pivots import turn_line, turn_line_floors, turns_at_rails
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
    """Width-aware descent-tail read on the ACTIVE box — the inner box's own
    equilibrium read when the LPS re-anchored there (so a clean promotable
    inner survives, e.g. QUAD), else the parent's (drops DGII; it also dropped
    CHCT, which he ruled a valid setup on Sun 13/09/2026: under the final method
    the tail is a comment on the fire, build step 12). Folded so
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


def _named_legs(words: dict) -> list:
    """(first bar, last bar) of every named leg on the map (point 21): the spring's dip and its recovery to the
    support area, the upthrust's climb and its crash back, THE SOS's leg, each last supper's dig."""
    legs = []
    pc = words.get("phase_c")
    if pc:
        legs.append((pc.get("start_bar"), pc.get("reach_bar") or pc.get("tip_bar")))
    up = words.get("the_upthrust")
    if up:
        legs.append((up.get("swing_bar"), up.get("back_bar") or up.get("top_bar")))
    sos = words.get("the_sos")
    if sos:
        legs.append((sos.get("launch_bar"), sos.get("top_bar")))
    for supper in words.get("last_suppers") or []:
        legs.append((supper.get("top_bar"), supper.get("low_bar")))
    return [(int(a), int(b)) for a, b in legs if a is not None and b is not None]


def _largest_limb(line, start, R, S):
    """The largest swing between consecutive committed turns of the line at or after ``start``, as a fraction
    of the box's height, with its two bars: ``(fraction, first bar, last bar)``; None with fewer than two turns."""
    turns = [(int(b), float(p)) for (b, k, p, know) in line if know is not None and int(b) >= int(start)]
    best = None
    for (b0, p0), (b1, p1) in zip(turns, turns[1:]):
        frac = abs(p1 - p0) / (float(R) - float(S))
        if best is None or frac > best[0]:
            best = (frac, b0, b1)
    return best


def _ledger_reads(df: pd.DataFrame, structure_ctx: dict, words) -> dict:
    """The grade ledger's reads (the final method, build step 12, point 21), on the elected box and the ONE
    turn line: the box's height in daily ranges, the committed turns at each rail, the LPS window's mean bar
    spread in ranges, the box's largest limb on the line and whether it is a named leg on the map (``words``,
    the line words' record, or None when no word is read: then nothing is named). The unit is the box's
    frozen one when the box's end froze it (step 11), else the read day's ATR_10."""
    structure = structure_ctx["structure"]
    box = structure.box
    unit = float(getattr(structure, "unit", None) or structure_ctx["atr_for_zone"])
    R, S = float(structure_ctx["res_avg"]), float(structure_ctx["sup_avg"])
    highs, lows = df["High"].to_numpy(dtype=float), df["Low"].to_numpy(dtype=float)
    line = turn_line(highs, lows, turn_line_floors(df, unit))
    turns = turns_at_rails(line, int(box.start_bar), R, S, settings.LINE_WORD_AREA_ATR * unit)
    window = None
    lps = structure.lps
    if lps is not None and int(lps.end_bar) > int(lps.start_bar):
        a, b = int(lps.start_bar), int(lps.end_bar)                  # end exclusive
        window = float((highs[a:b] - lows[a:b]).mean() / unit)
    out = {"height_ranges": (R - S) / unit, "turns": turns, "window_spread_ranges": window,
           "largest_limb_named": None}
    limb = _largest_limb(line, box.start_bar, R, S)
    if limb is not None:
        out["max_swing_frac"] = float(limb[0])
        if words is not None:
            out["largest_limb_named"] = any(not (limb[2] < a or limb[1] > b) for a, b in _named_legs(words))
    return out


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
    from the right edge). One implementation for the live chain, the retired species
    probe, and the stability probe (EC-3): the sampled bar must be the same
    bar everywhere structurally — retyped twin expressions were the exact
    class the frame_digest/ohlcv_digest split shipped."""
    return df.iloc[-int(settings.STRUCTURE_ATR_SAMPLE_OFFSET)]


def _resolve_structure_context(df: pd.DataFrame, latest,
                               near_miss=None, watch=None) -> Optional[dict]:
    # Parent (outer) is the base of record; inner is the nested companion. One
    # chronological A->B->(C?)->D narrative is the structure source of truth.
    # ONE ATR sample serves the walk, atr_ratio, and atr_for_zone below — the
    # box-carried equilibrium read is coherent with eval-time measures because
    # they share this row, structurally, not by twin expressions.
    atr_eval = structure_atr_row(df)
    # Election-trace capture (flag-dark): the trace rides the ONE walk that
    # elects the published box — same-run by construction, never a re-run.
    # None keeps the call byte-identical (the trace plumbing's no-op contract).
    # The watch recorder (build step 8, flag-dark) types its state word off the SAME walk's trace; the
    # export keeps its own flag below, so a watched fire never carries a trace it did not ask for.
    trace = [] if (settings.ELECTION_TRACE_EXPORT_ENABLED or watch is not None) else None
    structure = read_structure(df, float(atr_eval['ATR_10']),
                               near_miss=near_miss, trace=trace)
    if watch is not None:
        watch.update(unit=float(atr_eval['ATR_10']), trace=trace)
        if structure is None:
            watch.update(_walk_refused_state(trace))
        else:
            watch["structure"] = structure
    if structure is None:
        return None

    boxes = _structure_to_boxes(structure, len(df))
    base_len, res_avg, sup_avg, box_width, r_touches, s_touches, breach_days, \
        r_anchor_bar, s_anchor_bar, _bc_anchor_bar, phase_b_start_bar, \
        is_inner_box = boxes["parent"]
    inner = boxes["inner"]

    if base_len == 0:
        if watch is not None:
            watch.update(state="no lines", why="empty box")
        return None

    atr_ratio = atr_eval['ATR_10'] / atr_eval['ATR_50']

    if latest['Close'] < (sup_avg * settings.CRASH_FILTER_MULT) \
            and not settings.DEPTH_CAPS_GRADED_ENABLED:    # point 8 (step 7, dark)
        if watch is not None:
            watch.update(_chart_state(df, structure, watch["unit"], trace, why="crash floor"))
        return None
    if latest['Close'] >= (res_avg * settings.EXTENSION_FILTER_MULT) \
            and not settings.BOX_END_ENABLED:            # build step 11: the box's end decides, dark
        if watch is not None:
            watch.update(_chart_state(df, structure, watch["unit"], trace, why="extension veto"))
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
        "election_trace": trace if settings.ELECTION_TRACE_EXPORT_ENABLED else None,
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


def _resolve_lps_context(df: pd.DataFrame, latest, structure_ctx: dict,
                         watch=None) -> Optional[dict]:
    # The walk already ran the inner-first-then-parent election. Flag-off a
    # returned Structure is a COMPLETE story and structure.lps always exists.
    structure = structure_ctx["structure"]
    if structure.lps is None:
        # Build step 8 (point 22, dark): the walk may return a box with no LPS yet. It never fires; its
        # state word (lines, no LPS yet / the open right edge / crossed) rides the watch lane.
        if watch is not None:
            watch.update(_chart_state(df, structure, structure_ctx["atr_for_zone"], watch.get("trace")))
        return None
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
        if watch is not None:
            watch.update(state="crossed")            # the trigger is behind: the buy day, or later
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

    # The words on the line (final method build step 5, measure-only, dark): the
    # turn line's words over the elected box, carried as ONE JSON string and only
    # when a word flag is on. Nothing reads it but the grade ledger's pardon below
    # (build step 12, dark): not the archive writer, not the wire. Flag-off it reads
    # six settings, computes nothing and spreads {} -> byte-identical.
    line_words_fields, _words = {}, None
    if line_words.any_word_enabled():
        _words = line_words.read_line_words(
            df, _struct.box, structure_ctx["atr_for_zone"],
            lps=_struct.lps, inner=_struct.inner,
        )
        line_words_fields = {"_line_words_json": line_words.emitted(_words)}

    # The grade ledger's reads (final method build step 12, dark): flag-off {} -> byte-identical.
    ledger_kw = _ledger_reads(df, structure_ctx, _words) if settings.GRADE_LEDGER_ENABLED else {}
    equilibrium_kw = score_equilibrium_args(
        measurements["equilibrium"], measurements["dwell_balance"], bins
    )
    equilibrium_kw.update(ledger_kw)

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
        **equilibrium_kw,
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

    # The box's age from its first rail anchor (final method build step 6, measure-only, dark): carried only
    # with the 15-day floor on, so the young fires can be listed; nothing reads it. Flag-off {} -> byte-identical.
    base_age_fields = {}
    if settings.BASE_AGE_FROM_ANCHOR_ENABLED:
        _box = structure_ctx["structure"].box
        base_age_fields = {"_base_age_from_anchor":
                           int(len(df) - min(int(_box.r_anchor_bar), int(_box.s_anchor_bar)))}
    base_age_fields.update(_trend_run_fields(structure_ctx["structure"]))

    # The grade ledger's reads on the wire (build step 12, dark): flag-off {} -> byte-identical.
    turns = ledger_kw.get("turns")
    ledger_fields = ({"_height_ranges": ledger_kw.get("height_ranges"),
                      "_turns_at_r": (int(turns[0]) if turns else None),
                      "_turns_at_s": (int(turns[1]) if turns else None),
                      "_window_spread_ranges": ledger_kw.get("window_spread_ranges"),
                      "_largest_limb_named": ledger_kw.get("largest_limb_named")}
                     if ledger_kw else {})

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
        height_ranges=ledger_kw.get("height_ranges"),
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
        "ledger_fields": ledger_fields,
        "ta_grade_fields": ta_grade_fields,
        "stability_fields": stability_fields,
        "trace_fields": trace_fields,
        "strategy_fields": strategy_fields,
    }


def _trend_run_fields(structure) -> dict:
    """Build step 10 (dark): the run the climax ended, as inert facts on the fire row (the trend-context grade
    is step 12's). Flag-off {} -> byte-identical."""
    if not settings.CLIMAX_FIRST_WALK_ENABLED:
        return {}
    run = getattr(structure, "trend", None) or {}
    return {"_trend_run_ranges": run.get("ranges"), "_trend_run_days": run.get("days")}


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
        **score_ctx.get("ledger_fields", {}),  # the grade ledger's reads: empty flag-off -> byte-identical
        **({"_descent_tail": measurements["descent_tail"]} if measurements.get("descent_tail") is not None
           else {}),  # the descent tail as a comment (build step 12): absent flag-off -> byte-identical
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
                    near_miss=None, watch=None) -> Optional[dict]:
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

    ``watch``: the watch lane's recorder (build step 8, ``LPS_LEAVES_ELECTION_ENABLED``), a dict the chain
    fills at the exit it takes with the chart's ONE state word (``WATCH_WIRE_STATES``) and the facts the lane
    row needs; owned by ``evaluate_ticker_with_watch``. None (every flag-off caller) = byte-identical.
    """
    if watch is None:
        prepared = _prepare_eval_frame(df)
    else:
        prepared, reason = _prepare_eval_frame_with_reason(df)
        if prepared is None:
            watch.update(state="not scanned", why=reason[0])     # the door's leg, named (point 24)
    if prepared is None:
        return None

    eval_df = prepared["df"]
    if watch is not None:
        watch["df"] = eval_df                    # the frame the walk's bars index (the lane row reads it)
    structure_ctx = _resolve_structure_context(eval_df, prepared["latest"],
                                               near_miss=near_miss, watch=watch)
    if structure_ctx is None:
        return None

    lps_ctx = _resolve_lps_context(eval_df, prepared["latest"], structure_ctx,
                                   watch=watch)
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

    descent_tail = descent_tail_drops(
        eval_df,
        measurements["equilibrium"],
        structure_ctx["box_width"],
        structure_ctx["inner"],
        lps_ctx["lps_in_inner"],
        structure_ctx["atr_for_zone"],
    )
    if descent_tail and not settings.LPS_LEAVES_ELECTION_ENABLED:
        if watch is not None:
            watch.update(state="no lines", why="descent tail")
        return None
    # Build step 12 (point 22, under the states switch): the descent tail is a COMMENT on the fire, never a
    # refusal. The gate was validated on 2026-06-19 against a box recipe the method replaced, and its named
    # specimen CHCT was ruled a valid setup on his eye (Sun 13/09/2026, the decisions record); the fact rides
    # the row as ``_descent_tail`` so the chip can say it. Flag-off the refusal stands and the key is absent.
    measurements["descent_tail"] = bool(descent_tail) if settings.LPS_LEAVES_ELECTION_ENABLED else None

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
                     breadth_pct: Optional[float] = None,
                     watch=None) -> Optional[dict]:
    """
    Evaluate a single ticker through all screening phases.
    Returns a result dict if the ticker passes, or None if filtered out.
    This is a top-level function so it can be pickled by ProcessPoolExecutor.
    """
    # The lane records ONLY through evaluate_ticker_with_near_miss (the one
    # caller that harvests the map — review 2026-07-26 finding 14): the plain
    # entry never pays recorder work, in either flag state.
    return _run_guarded_chain(ticker, df, spy_6m_return, breadth_pct, None,
                              watch=watch)


def _run_guarded_chain(ticker, df, spy_6m_return, breadth_pct, near_miss=None,
                       watch=None):
    """The chain under the standard skip-guard — folded once (EC-3) so the
    plain evaluation and the lane-carrying scan twin cannot drift."""
    try:
        result = _run_eval_chain(ticker, df, spy_6m_return, breadth_pct,
                                 near_miss=near_miss, watch=watch)
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
                                   breadth_pct: Optional[float] = None,
                                   watch=None):
    """The scan-path twin of ``_evaluate_ticker`` used when the near-miss
    lane flag is on: returns ``(result, near_miss_rows, lane_stats)`` so the
    refusal cohort can cross the worker-pool boundary alongside the fire
    verdict. Flag-off it degrades to the plain evaluation with empty lane
    output — the screener only submits it under the flag, but the degrade
    keeps a mid-scan flag flip harmless. Top-level for pickling."""
    if not settings.NEAR_MISS_LANE_ENABLED:
        return _evaluate_ticker(ticker, df, spy_6m_return, breadth_pct,
                                watch=watch), [], {}
    from engine_alpha.structure.near_miss import (  # noqa: PLC0415 — inside the flag
        NearMissRecorder, deferred_rows)
    recorder = NearMissRecorder()
    result = _run_guarded_chain(ticker, df, spy_6m_return, breadth_pct,
                                recorder, watch=watch)
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


# ── The watch lane (the final method, build step 8: the LPS leaves the election) ──
# Point 22: every chart the door admits carries ONE state word from ONE table; the "no LPS yet" charts sit in
# a watch lane apart from the leaderboard, behind a display floor that touches no fire. The words are his
# (the state table of docs/final_method_2026-09.md point 22, and precedence row 5 of point 6 for the open
# right edge); the wire carries them verbatim, never a slug the frontend must translate. Two are step 11's
# ("root candidate, unconfirmed", "broke down"): on the table, never typed before the hand-over exists.
WATCH_WIRE_STATES = ("fired", "crossed", "lines, no LPS yet", "forming N of 15",
                     "root candidate, unconfirmed", "beyond R, undetermined",
                     "under S, undetermined", "broke down", "not scanned", "no lines")
# The states whose chart the lane shows: lines and no fire.
WATCH_LANE_STATES = ("lines, no LPS yet", "forming N of 15", "beyond R, undetermined",
                     "under S, undetermined")


def _right_edge_run(df, R, S, area):
    """Precedence row 5 of point 6 (the open right edge): the run of WHOLE bars beyond a rail's area, counted
    back from today (his whole-bar respect, R7). ``("beyond R", n)``, ``("under S", n)`` or ``None``."""
    lows = df["Low"].to_numpy(dtype=float)
    highs = df["High"].to_numpy(dtype=float)
    n = 0
    for low in lows[::-1]:
        if not low > R + area:
            break
        n += 1
    if n:
        return "beyond R", n
    n = 0
    for high in highs[::-1]:
        if not high < S - area:
            break
        n += 1
    if n:
        return "under S", n
    return None


def _lps_was_bought(trace) -> bool:
    """Did the elected root's LPS detector refuse its window as bought (a later high crossed the trigger, the
    buy-day clause of R18)? Read off the walk's own trace record for that root, never a second detection."""
    if not trace:
        return False
    rejects = trace[-1].get("lps_rejects") or {}
    return any("bought" in reason for pool in rejects.values() for reason in pool)


def _chart_state(df, structure, unit, trace, why=None) -> dict:
    """ONE state word for a chart with lines and no fire (build step 8, point 22). The right edge first (row
    5: a run of whole bars beyond a rail's area is "beyond R, undetermined" / "under S, undetermined" with
    its length in trading days); then a box with no LPS reads "crossed" when the walk's own LPS rejects say
    the window was bought and "lines, no LPS yet" otherwise; a box with an LPS the chain refused to read
    reads "crossed" (the extension veto: the close far over R, the trigger behind it) or "under S,
    undetermined" (the crash floor). ``why`` names a refusal a later step retires (steps 10 to 12)."""
    area = float(settings.LINE_WORD_AREA_ATR) * float(unit)
    out = {"why": why} if why else {}
    child = getattr(structure, "child", None)
    if child:
        # Build step 11, precedence row 4: a child root candidate after the breakout, not yet confirmed by a
        # later turn at its anchors; the parent stays the operative box.
        out.update(state="root candidate, unconfirmed", child=dict(child))
        return out
    edge = _right_edge_run(df, float(structure.R), float(structure.S), area)
    if edge is not None:
        out.update(state=f"{edge[0]}, undetermined", days=int(edge[1]))
    elif structure.lps is None:
        out["state"] = "crossed" if _lps_was_bought(trace) else "lines, no LPS yet"
    else:
        out["state"] = "under S, undetermined" if why == "crash floor" else "crossed"
    return out


def _walk_refused_state(trace) -> dict:
    """The state word of a chart the walk refused, read off its own trace: "forming N of 15" when a box was
    too young (the oldest such box: its age and its rails ride along), else "no lines" with the last root's
    outcome as the why (no_box; cause_absent until step 10 folds the veto into a trend fact)."""
    ended = [r for r in (trace or []) if r.get("outcome") == "ended"]
    if ended and ended[-1] is next((r for r in reversed(trace) if r.get("box")), None):
        # Build step 11: the last box the walk found had ended; a breakdown with nothing after it is "broke
        # down", a hand-over with no child box yet is no lines with the reason named.
        kind = (ended[-1].get("end") or {}).get("kind")
        return ({"state": "broke down", "end": dict(ended[-1]["end"])} if kind == "breakdown"
                else {"state": "no lines", "why": "handed over", "end": dict(ended[-1]["end"])})
    forming = [r for r in (trace or []) if r.get("outcome") == "forming"]
    if forming:
        rec = max(forming, key=lambda r: int(r["forming"]["age"]))
        return {"state": "forming N of 15", "forming": dict(rec["forming"]), "box": dict(rec["box"])}
    why = trace[-1].get("outcome") if trace else "no root"
    return {"state": "no lines", "why": why}


def watch_verdict(watch: dict, fired: bool) -> str:
    """The chart's one state word, resolved at the publisher: a fire is "fired"; otherwise the word the chain
    recorded at its exit. Validates its own output against the closed table, loudly (as ``wire_status``)."""
    state = "fired" if fired else (watch.get("state") or "no lines")
    if state not in WATCH_WIRE_STATES:
        raise ValueError(
            f"chart state {state!r} is not on the table ({' / '.join(WATCH_WIRE_STATES)})")
    return state


def _lane_row(ticker: str, watch: dict, state: str, floor: Optional[int] = None) -> Optional[dict]:
    """The watch lane's row for a chart with lines and no fire, or None below the display floor:
    ``WATCH_LANE_MIN_TURNS_PER_RAIL`` committed turns of the line inside each rail's area, from the box start
    (point 22: two at each rail). The floor touches no fire; it only decides what the lane shows. ``floor``
    overrides the setting (the ticker page's state read passes 0: one chart he asked about shows its facts
    however few turns it has, build step 12)."""
    from engine_alpha.structure.pivots import (  # noqa: PLC0415 — inside the flag
        turn_line, turn_line_floors, turns_at_rails)
    df = watch["df"]
    n = len(df)
    unit = float(watch["unit"])
    structure = watch.get("structure")
    if structure is not None:
        box = structure.box
        R, S, start = float(structure.R), float(structure.S), int(box.start_bar)
        age = n - min(int(box.r_anchor_bar), int(box.s_anchor_bar))
    else:                                        # forming: the walk's trace brief of the young box
        brief = watch["box"]
        R, S, start = float(brief["R"]), float(brief["S"]), int(brief["start_bar"])
        age = int(watch["forming"]["age"])
    line = turn_line(df["High"].to_numpy(dtype=float), df["Low"].to_numpy(dtype=float),
                     turn_line_floors(df, unit))
    at_r, at_s = turns_at_rails(line, start, R, S, float(settings.LINE_WORD_AREA_ATR) * unit)
    floor = int(settings.WATCH_LANE_MIN_TURNS_PER_RAIL) if floor is None else int(floor)
    if at_r < floor or at_s < floor:
        return None
    row = {"ticker": ticker, "state": state, "R": round(R, 4), "S": round(S, 4),
           "open": str(df.index[start].date()), "age": int(age),
           "turns_at_r": int(at_r), "turns_at_s": int(at_s),
           "close": round(float(df["Close"].iloc[-1]), 4)}
    for key in ("days", "forming", "why"):
        if key in watch:
            row[key] = watch[key]
    return row


def evaluate_ticker_with_watch(ticker: str, df: pd.DataFrame,
                               spy_6m_return: float = 0.0,
                               breadth_pct: Optional[float] = None,
                               *, inner=None):
    """Build step 8's outer twin (point 22). ``inner`` is the ladder's own worker (the plain evaluation, the
    near-miss twin); the recorder rides that ONE paying read and the chart's state word
    is typed after it, never by a second walk. Returns ``(base, row, stats)``: ``base`` exactly what ``inner``
    returned, ``row`` the watch lane's row or None, ``stats`` the counts keyed by the state word itself.
    Flag-off degrades to the inner call with no recorder (byte-identical). Every lane failure is swallowed
    and counted, never converting a result into a drop (EC-20). Top-level for pickling (the screener binds
    ``inner`` with ``functools.partial``)."""
    inner = inner or _evaluate_ticker
    if not settings.LPS_LEAVES_ELECTION_ENABLED:
        return inner(ticker, df, spy_6m_return, breadth_pct), None, {}
    watch: dict = {}
    base = inner(ticker, df, spy_6m_return, breadth_pct, watch=watch)
    result = base[0] if isinstance(base, tuple) else base
    if result is EVAL_ERROR:
        return base, None, {"base errored": 1}   # an aborted read has no state word
    row, stats = None, {}
    try:
        state = watch_verdict(watch, fired=isinstance(result, dict))
        stats[state] = 1
        if state in WATCH_LANE_STATES:
            row = _lane_row(ticker, watch, state)
            if row is None:
                stats["below the floor"] = 1
    except Exception as e:  # noqa: BLE001 — the lane never touches the scan
        print(f"  [watch skip {ticker}] {type(e).__name__}: {e}", file=sys.stderr)
        stats["errored"] = 1
        row = None
    return base, row, stats
