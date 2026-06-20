"""Per-ticker evaluation pass for the screener pipeline."""
from __future__ import annotations

import sys
from typing import Optional

import pandas as pd

from config import settings
from core.scoring import calculate_tier, score_setup
from core.structure import (
    adr_pct,
    calculate_atr,
    descent_tail_rejects,
    detect_lps,
    detect_lps_tests,
    lps_range_threshold,
    measure_bar_compression,
    measure_bins,
    measure_contractions,
    measure_equilibrium,
    measure_support_slope,
    measure_touch_volume,
    measure_traversal,
    scope_consolidation,
    trend_template,
)
from core.structure.narrative import read_structure
from core.structure.phase_d import final_v_tip_bar, support_test_evidence_starts


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
    if len(df) < 200:
        return None

    df = df.copy()
    df['SMA_50'] = df['Close'].rolling(window=50).mean()
    df['SMA_200'] = df['Close'].rolling(window=200).mean()
    df['Vol_50'] = df['Volume'].rolling(window=50).mean()

    df['Spread'] = df['High'] - df['Low']

    latest = df.iloc[-1]
    one_year_ago_idx = max(0, len(df) - 252)
    one_year_ago = df.iloc[one_year_ago_idx]

    yearly_return = (latest['Close'] - one_year_ago['Close']) / one_year_ago['Close']

    if latest['Close'] < settings.MIN_PRICE: return None
    if latest['Vol_50'] < settings.MIN_VOLUME_50D: return None
    if latest['Close'] < latest['SMA_50']: return None
    if latest['Close'] < latest['SMA_200']: return None
    if yearly_return < settings.MIN_YEARLY_RETURN: return None

    return df, float(yearly_return)


def _structure_to_boxes(s, n: int) -> dict:
    """Adapt a narrative ``Structure`` to the ``detect_boxes`` output shape so the
    rest of the pipeline consumes it unchanged.

    Brick anchors are ABSOLUTE (df-positional); the legacy parent tuple / inner
    dict want them REBASED to their own box start, because downstream recomputes
    ``swing_complete_idx = start + max(r_anchor, s_anchor)``. ``bc_anchor_bar``
    (slot 9) carries the already-resolved-local climax — the narrative path skips
    ``_resolve_phase_a_swing`` and reads ``structure.climax_bar`` directly.
    """
    pbs = int(s.phase_b_start_bar)
    base_len = n - pbs
    box = s.box
    parent = (
        base_len, float(s.R), float(s.S), float(s.box_width),
        int(box.r_touches), int(box.s_touches), int(box.breach_days),
        int(box.r_anchor_bar) - pbs, int(box.s_anchor_bar) - pbs,
        int(s.climax_bar), pbs, False,
    )
    inner = None
    if s.inner is not None:
        i = s.inner
        istart = int(i.start_bar)
        inner = {
            "R": float(i.R), "S": float(i.S), "box_width": float(i.box_width),
            "base_len": int(i.base_len), "start_bar": istart,
            "r_touches": int(i.r_touches), "s_touches": int(i.s_touches),
            "r_anchor_bar": int(i.r_anchor_bar) - istart,
            "s_anchor_bar": int(i.s_anchor_bar) - istart,
            "source": i.source, "search_start_bar": int(i.search_start_bar),
            "climax_bar": i.climax_bar,
            "reaction_bar": i.reaction_bar, "reaction_pct": i.reaction_pct,
            "reaction_bars": i.reaction_bars,
        }
    return {"parent": parent, "inner": inner}


def select_active_lps(df, latest, parent, inner, atr):
    """Detect the active LPS, preferring the tighter inner box's LPS when it
    yields one (closer trigger / stop), else the parent's. Returns
    ``(lps_result, lps_in_inner, lps_context)``.

    Folded out of the live + seed eval paths so the inner-first-then-parent rule
    can never silently diverge. ``parent`` is
    ``(S, R, base_range_threshold, base_len, swing_complete_idx)``.
    """
    sup_avg, res_avg, base_range_threshold, base_len, swing_complete_idx = parent
    lps_result = None
    lps_in_inner = False
    lps_context = parent
    if inner is not None:
        inner_base_df = df.iloc[-inner["base_len"]:]
        inner_swing_complete = inner["start_bar"] + max(
            inner["r_anchor_bar"], inner["s_anchor_bar"])
        inner_rt = lps_range_threshold(inner_base_df, atr)
        inner_lps = detect_lps(
            df, latest, inner["S"], inner["R"], atr,
            inner_rt, inner["base_len"], inner_swing_complete,
        )
        if inner_lps:
            lps_result = inner_lps
            lps_in_inner = True
            lps_context = (inner["S"], inner["R"], inner_rt,
                           inner["base_len"], inner_swing_complete)
    if lps_result is None:
        lps_result = detect_lps(
            df, latest, sup_avg, res_avg, atr,
            base_range_threshold, base_len, swing_complete_idx,
        )
    return lps_result, lps_in_inner, lps_context


def descent_tail_drops(frame, parent_traversal, box_width, inner, lps_in_inner, atr):
    """Width-aware descent-tail gate on the ACTIVE box — the inner box's own
    traversal when the LPS re-anchored there (so a clean promotable inner
    survives, e.g. QUAD), else the parent's (drops CHCT/DGII). Folded so the
    live + seed paths gate identically. ``parent_traversal`` is the already
    computed parent ``measure_traversal`` result."""
    if lps_in_inner and inner is not None:
        gate_trav = measure_traversal(
            frame.iloc[-inner["base_len"]:], inner["R"], inner["S"], atr)
        gate_width = float(inner["box_width"])
    else:
        gate_trav = parent_traversal
        gate_width = box_width
    return descent_tail_rejects(gate_trav.get("last_support_frac"),
                                gate_trav.get("coil_floor_pos"), gate_width)


def score_traversal_args(traversal, equilibrium, bins) -> dict:
    """The four box-relative swing facts ``score_setup`` needs from the measure
    layer. Folded so the live + seed paths feed the scorer identically."""
    return {
        "traversal_density": (traversal["n_full_traversals"] / traversal["n_swings"]
                              if traversal["n_swings"] else 0.0),
        "max_swing_frac": traversal["max_swing_frac"] or 1.0,
        "dwell_asymmetry": abs(equilibrium["upper_dwell"] - equilibrium["lower_dwell"]),
        "has_spring": bool(bins.get("bin_c_present")),
    }


def _evaluate_ticker(ticker: str, df: pd.DataFrame,
                     spy_6m_return: float = 0.0,
                     breadth_pct: Optional[float] = None) -> Optional[dict]:
    """
    Evaluate a single ticker through all screening phases.
    Returns a result dict if the ticker passes, or None if filtered out.
    This is a top-level function so it can be pickled by ProcessPoolExecutor.
    """
    try:
        baseline = apply_baseline_filters(df)
        if baseline is None:
            return None
        df, yearly_return = baseline

        latest = df.iloc[-1]

        df['ATR_10'] = calculate_atr(df, 10)
        df['ATR_50'] = calculate_atr(df, 50)

        # Parent (outer) is the base of record; the inner box is the nested
        # companion — drawn separately and used to score the LPS when the LPS sits
        # inside it. See docs/structure_legend.md "Parent + Inner: the nested
        # range model (draw both)".
        # One chronological A->B->(C?)->D narrative is the structure source of
        # truth; it is adapted to the legacy box shape so the rest of the pass is
        # unchanged. The narrative always reads the oldest valid root swing by
        # construction, so there is no box-selection mode to choose.
        structure = read_structure(df, float(df.iloc[-6]['ATR_10']))
        if structure is None:
            return None
        boxes = _structure_to_boxes(structure, len(df))
        base_len, res_avg, sup_avg, box_width, r_touches, s_touches, breach_days, \
            r_anchor_bar, s_anchor_bar, bc_anchor_bar, phase_b_start_bar, \
            is_inner_box = boxes["parent"]
        inner = boxes["inner"]

        if base_len == 0:
            return None

        atr_eval = df.iloc[-6]
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

        # Use the inner box when it yields an LPS (tighter box -> closer trigger /
        # stop), else the parent. Only the LPS (trigger / zone / tightness /
        # setup type) follows the inner; the base above stays parent.
        parent_ctx = (sup_avg, res_avg, base_range_threshold, base_len, swing_complete_idx)
        lps_result, lps_in_inner, lps_context = select_active_lps(
            df, latest, parent_ctx, inner, atr_for_zone)

        if not lps_result:
            return None

        setup_state = lps_result['setup_type']
        lps_length = lps_result['length']
        lps_offset = lps_result['offset']
        trigger_price = lps_result['trigger_price']
        vol_contraction = lps_result['vol_contraction']
        tightness_ratio = lps_result['tightness_ratio']
        lps_tests = detect_lps_tests(
            df, latest, lps_context[0], lps_context[1],
            atr_for_zone, lps_context[2], lps_context[3], lps_context[4],
        )

        current_price = latest['Close']
        distance_to_trigger = (trigger_price - current_price) / current_price
        if distance_to_trigger <= 0:
            return None

        last_252 = df['High'].iloc[-min(252, len(df)):]
        max_252 = float(last_252.max()) if len(last_252) else 0.0
        dist_52w_high_pct = (
            (float(current_price) - max_252) / max_252 if max_252 > 0 else None
        )

        rs_lookback = settings.RS_LOOKBACK_BARS
        if len(df) > rs_lookback:
            stock_6m_return = (float(current_price) / float(df['Close'].iloc[-rs_lookback - 1]) - 1.0)
        else:
            stock_6m_return = 0.0
        excess_return_6m = stock_6m_return - spy_6m_return

        r_touch_vol_z, s_touch_vol_z = measure_touch_volume(
            base_df, res_avg, sup_avg, atr_for_zone
        )
        contraction = measure_contractions(base_df)
        bar_compression = measure_bar_compression(
            base_df, res_avg - sup_avg, atr_for_zone
        )
        support = measure_support_slope(base_df, atr_for_zone)
        equilibrium = measure_equilibrium(base_df, res_avg, sup_avg, atr_for_zone)
        traversal = measure_traversal(base_df, res_avg, sup_avg, atr_for_zone)

        # Descent-tail gate: drop a wide box that abandoned its support rail early
        # into dead space (CHCT/DGII); a clean promotable inner survives (QUAD).
        if descent_tail_drops(df, traversal, box_width, inner, lps_in_inner, atr_for_zone):
            return None

        # Phase A is already the resolved LOCAL root swing (resolve_phase_a brick);
        # no after-the-fact reconciliation needed.
        bc_anchor_bar, phase_a_end_bar = int(structure.climax_bar), int(structure.ar_bar)
        phase_d_start_bar = int(inner["start_bar"]) if inner is not None else None
        phase_d_evidence_starts = (
            {"support_tests": None, "sos_reclaim": None, "rising_support": None}
            if inner is not None
            else support_test_evidence_starts(lps_tests, phase_b_start, base_len)
        )
        support_test_start_bar = phase_d_evidence_starts["support_tests"]
        # The V-tip (final recovered low) is the Phase B->D divider. Used only
        # when there's no inner Phase-D box of record.
        v_tip_bar = (
            None if inner is not None
            else final_v_tip_bar(df, phase_b_start, base_len)
        )

        bins = measure_bins(
            df,
            bc_anchor_bar=bc_anchor_bar,
            phase_b_start_bar=phase_b_start_bar,
            base_len=base_len,
            is_inner_box=is_inner_box,
            lps_offset=lps_offset,
            lps_length=lps_length,
            R=res_avg,
            S=sup_avg,
            atr_val=atr_for_zone,
            phase_d_start_bar=phase_d_start_bar,
            support_test_start_bar=support_test_start_bar,
            sos_reclaim_start_bar=phase_d_evidence_starts["sos_reclaim"],
            rising_support_start_bar=phase_d_evidence_starts["rising_support"],
            phase_a_end_bar=phase_a_end_bar,
            lps_R=lps_context[1],
            lps_S=lps_context[0],
            v_tip_bar=v_tip_bar,
        )

        scope = scope_consolidation(
            df,
            bc_anchor_bar=bc_anchor_bar,
            phase_b_start_bar=phase_b_start_bar,
            base_len=base_len,
            is_inner_box=is_inner_box,
            lps_offset=lps_offset,
            lps_length=lps_length,
            lps_zone_type=lps_result.get("zone_type", "INSIDE"),
            atr_val=atr_for_zone,
            phase_d_start_bar=phase_d_start_bar,
            support_test_start_bar=support_test_start_bar,
            sos_reclaim_start_bar=phase_d_evidence_starts["sos_reclaim"],
            rising_support_start_bar=phase_d_evidence_starts["rising_support"],
            phase_a_end_bar=phase_a_end_bar,
            phase_c_recovery_bar=bins.get("bin_c_recovery_bar"),
            v_tip_bar=v_tip_bar,
        )

        trend = trend_template(df, dist_52w_high_pct=dist_52w_high_pct)

        adr_value = adr_pct(df, settings.ADR_WINDOW)
        adr_quality = (
            min(adr_value / settings.ADR_FULL_PCT, 1.0)
            if settings.ADR_FULL_PCT else 0.0
        )

        score_result = score_setup(
            box_width, r_touches, s_touches, res_avg, sup_avg, base_df,
            atr_ratio, tightness_ratio, vol_contraction, base_len, yearly_return,
            excess_return_6m, dist_52w_high_pct, breadth_pct,
            contraction['quality'], support['quality'], adr_quality,
            **score_traversal_args(traversal, equilibrium, bins),
        )
        score = score_result['total']
        tier = calculate_tier(score, box_width)

        phase_c_event_date = bins['bin_c_event_date'] or scope['phase_c_event_date']

        return {
            'Ticker': ticker,
            'Tier': tier,
            'Setup': setup_state,
            'Score': score,
            'Current Price': round(float(current_price), 2),

            'Base Len': int(base_len),
            'Box Width': float(box_width),
            'Touches': int(r_touches + s_touches),
            'ATR Ratio': float(atr_ratio),
            'LPS Length': int(lps_length),
            'Breach Days': int(breach_days),

            '_r_touches': int(r_touches),
            '_s_touches': int(s_touches),
            '_vol_contraction': float(vol_contraction),
            '_tightness_ratio': float(tightness_ratio),
            '_trigger_price': float(trigger_price),
            '_sub_scores': score_result,
            '_R': float(res_avg),
            '_S': float(sup_avg),
            '_base_len': int(base_len),
            '_lps_len': int(lps_length),
            '_lps_offset': int(lps_offset),
            '_r_anchor_bar': int(r_anchor_bar),
            '_s_anchor_bar': int(s_anchor_bar),
            '_bars_since_BC': int(len(df) - bc_anchor_bar),
            '_descent_length': int(phase_b_start_bar - bc_anchor_bar),
            '_phase_d_inner': bool(inner is not None),
            '_lps_in_inner': bool(lps_in_inner),
            '_inner_R': float(inner['R']) if inner is not None else None,
            '_inner_S': float(inner['S']) if inner is not None else None,
            '_inner_box_width': float(inner['box_width']) if inner is not None else None,
            '_inner_start_bar': int(inner['start_bar']) if inner is not None else None,
            '_inner_source': inner.get('source') if inner is not None else None,
            '_inner_search_start_bar': int(inner['search_start_bar']) if inner is not None else None,
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
            '_dist_52w_high_pct': float(dist_52w_high_pct) if dist_52w_high_pct is not None else None,
            '_excess_return_6m': float(excess_return_6m),
            '_breadth_pct': float(breadth_pct) if breadth_pct is not None else None,
            '_r_touch_vol_z': r_touch_vol_z,
            '_s_touch_vol_z': s_touch_vol_z,
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
            '_lps_tests': lps_tests,
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
            '_eq_r_touches': int(equilibrium['r_touches']),
            '_eq_s_touches': int(equilibrium['s_touches']),
            '_eq_r_touch_thirds': int(equilibrium['r_touch_thirds']),
            '_eq_s_touch_thirds': int(equilibrium['s_touch_thirds']),
            '_eq_lower_dwell': float(equilibrium['lower_dwell']),
            '_eq_mid_dwell': float(equilibrium['mid_dwell']),
            '_eq_upper_dwell': float(equilibrium['upper_dwell']),
            '_eq_coverage': float(equilibrium['coverage']),
            '_trav_n_full_traversals': int(traversal['n_full_traversals']),
            '_trav_n_swings': int(traversal['n_swings']),
            '_trav_top_dead_space': (float(traversal['top_dead_space'])
                                     if traversal['top_dead_space'] is not None else None),
            '_trav_bottom_dead_space': (float(traversal['bottom_dead_space'])
                                        if traversal['bottom_dead_space'] is not None else None),
            '_trav_rail_reaches_high': int(traversal['rail_reaches_high']),
            '_trav_rail_reaches_low': int(traversal['rail_reaches_low']),
            '_trav_max_swing_frac': (float(traversal['max_swing_frac'])
                                     if traversal['max_swing_frac'] is not None else None),
            '_trav_last_support_frac': (float(traversal['last_support_frac'])
                                        if traversal['last_support_frac'] is not None else None),
            '_trav_coil_floor_pos': (float(traversal['coil_floor_pos'])
                                     if traversal['coil_floor_pos'] is not None else None),
            '_adr_pct': float(adr_value),
            '_adr_quality': float(adr_quality),
            '_phase_a_start_date': scope['phase_a_start_date'],
            '_phase_a_end_date': scope['phase_a_end_date'],
            '_phase_b_start_date': scope['phase_b_start_date'],
            '_phase_d_start_date': scope['phase_d_start_date'],
            '_phase_c_event_date': phase_c_event_date,
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
            '_stage2_ma_stack_pass': trend['stage2_ma_stack_pass'],
            '_stage2_ma200_slope_1m_pct': trend['stage2_ma200_slope_1m_pct'],
            '_stage2_52w_low_pct': trend['stage2_52w_low_pct'],
            '_stage2_trend_pass_count': trend['stage2_trend_pass_count'],
            '_stage2_trend_pass': trend['stage2_trend_pass'],
            '_base_close_start': float(base_df['Close'].iloc[0]),
            '_base_close_end': float(base_df['Close'].iloc[-1]),
            '_base_date_start': str(base_df.index[0])[:10],
            '_base_date_end': str(base_df.index[-1])[:10],
        }

    except (KeyError, ValueError, IndexError, TypeError, ZeroDivisionError, AttributeError) as e:
        print(f"  [skip {ticker}] {type(e).__name__}: {e}", file=sys.stderr)
        return None
