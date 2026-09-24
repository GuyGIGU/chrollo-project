# ============================================================================
# ⚠️  DO NOT DELETE — THIS MODULE IS LIVE, NOT RETIRED HTML RESIDUE  ⚠️
# ----------------------------------------------------------------------------
# The name `generate_dashboard` (and this module's old home, output/) LOOK like
# the retired static-HTML dashboard, but they are NOT. This module is the LIVE writer of
# the React frontend's data artifact and is on the hot path of every scan.
# A name-trusting dead-code sweep that deletes this file WILL break scan -> UI.
#
#   • Writes   output/screener_data.json  (+ per-universe variants) — the data
#     artifact the React frontend loads. No writer => the UI never updates.
#   • Called   on EVERY scan by core/pipeline/screening/scan_job.py (~lines 176 & 186).
#   • Exports  SECTOR_ETF_NAMES — imported by
#     webapp/backend/domains/screener/router.py for the sector drill-down.
#   • Coupled  to DASHBOARD_CHART_TIERS (tiering of the chart payload).
#   • Emits    the "UI update available on local webapp." stdout sentinel that
#     the frontend's scan stream waits on to reveal fresh results.
#
# Renaming the module/function is a DEFERRED nicety — do it deliberately and
# update ALL call sites + imports above; do not "clean it up" as dead code.
# ============================================================================
"""
Data export module for Wyckoff VCP/LPS Screener.

LIVE artifact writer — DO NOT DELETE (see banner above). Despite being named
generate_dashboard, this is the current, on-every-scan
writer of the React frontend's JSON data artifact (output/screener_data.json),
NOT the retired static-HTML dashboard. It also exports SECTOR_ETF_NAMES for the
sector drill-down and prints the "UI update available on local webapp." reveal
sentinel the frontend's scan stream watches. Removing or stubbing this module
silently breaks the scan -> UI pipeline.
"""
import os
import json
import math
import sys

from config import settings
from core.archive.writer import load_sector_etf_cache, save_sector_etf_cache
from core.pipeline.market_data.candles import chart_candles, clean_daily_frame, daily_candles
from core.pipeline.json_safety import to_json_safe
from core.pipeline.universe.descriptor import resolve_universe
from engine_alpha.scoring import taxonomy
from engine_alpha.structure.events.event_map import narrative_chart_fields
from engine_alpha.structure.context.htf import HTF_COLUMNS, chart_box
from engine_alpha.structure.box.trace_export import election_trace_chart_fields
from engine_alpha.scoring.tags import traversal_density_from_counts

PROJECT_ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', '..'))
BACKEND_DIR = os.path.join(PROJECT_ROOT, "webapp", "backend")
OUTPUT_DIR = os.path.join(PROJECT_ROOT, "output")
SECTOR_ETF_CACHE_PATH = os.path.join(OUTPUT_DIR, "sector_etf_cache.json")

SECTOR_ETF_NAMES = {
    "XLB": "Materials",
    "XLC": "Communication Services",
    "XLE": "Energy",
    "XLF": "Financials",
    "XLI": "Industrials",
    "XLK": "Technology",
    "XLP": "Consumer Staples",
    "XLRE": "Real Estate",
    "XLU": "Utilities",
    "XLV": "Health Care",
    "XLY": "Consumer Discretionary",
}


# Same on-disk cache the archive writer keeps; ONE implementation lives there
# (conventions.md EC-3) — these thin wrappers only bind this module's path.
def _load_sector_etf_cache():
    return load_sector_etf_cache(SECTOR_ETF_CACHE_PATH)


def _save_sector_etf_cache(cache):
    save_sector_etf_cache(cache, SECTOR_ETF_CACHE_PATH)


def _resolve_sector_etf(ticker):
    try:
        if BACKEND_DIR not in sys.path:
            sys.path.append(BACKEND_DIR)
        from archive_models import get_sector_etf
        return get_sector_etf(ticker) or ""
    except Exception:
        return ""


def _sector_etf_for_ticker(ticker, sector_etf_cache):
    normalized = str(ticker).upper()
    if normalized not in sector_etf_cache:
        sector_etf_cache[normalized] = _resolve_sector_etf(normalized)
        _save_sector_etf_cache(sector_etf_cache)
    return sector_etf_cache.get(normalized) or None


def _round_opt(value, digits):
    """Display-round a nullable scalar: None passes through (NULL = not
    measured — never coerced to a number at the wire)."""
    return None if value is None else round(float(value), digits)


def _json_safe(obj):
    """Recursively coerce NumPy/Pandas scalars and replace NaN/Inf with None.

    Starlette's JSONResponse serves /screener-data/ with allow_nan=False, so a
    single NaN/Inf anywhere in the payload makes the endpoint 500 — and the
    frontend silently stays on "Loading Screener Data...". Sanitizing here, at
    the one place the file is written, guarantees the served file is always
    serveable regardless of which metric produced a degenerate value.
    """
    return to_json_safe(obj)

def _extract_chart_data(data, results_df, tickers):
    """Extract OHLCV data as JSON-serializable dicts for each chartable ticker."""
    # Lazy: keeps output/ off core.pipeline.market_data.downloads at module load. Used to
    # reproduce the DAILY_STRUCTURE_PERIOD eval-frame length so inner-box bar
    # indices (which are positional in THAT frame) map onto the candle window.
    from core.pipeline.market_data.downloads import _trim_to_period
    chart_data = {}
    chart_candidates = results_df[results_df['Tier'].isin(settings.DASHBOARD_CHART_TIERS)]
    sector_etf_cache = _load_sector_etf_cache()
    
    for _, row in chart_candidates.iterrows():
        ticker = row['Ticker']
        try:
            # Multi-panel detection by column shape (the health board's
            # predicate) — a one-name MultiIndex panel still slices, and a
            # plain dict-of-frames (the cascade harness) slices too.
            columns = getattr(data, "columns", None)
            is_multi = columns is None or getattr(columns, "nlevels", 1) > 1
            df = clean_daily_frame(data[ticker] if is_multi else data)

            # The complete D/W/M candle set from the ONE shared builder
            # (core.pipeline.market_data.candles — the EC-3 fold with the watchlist candle
            # endpoint); weekly/monthly resample from the FULL daily history,
            # caps live in settings only.
            tf_set = chart_candles(df)
            candles, volumes, show_days = (
                tf_set['candles'], tf_set['volumes'], tf_set['show_days'])
            weekly_candles, weekly_volumes = (
                tf_set['weekly_candles'], tf_set['weekly_volumes'])
            monthly_candles, monthly_volumes = (
                tf_set['monthly_candles'], tf_set['monthly_volumes'])
            # Worked box geometry (R/S + start date) so the chart can anchor the
            # rails to the bars the box is born from, like the daily chart.
            weekly_box = chart_box(df, "weekly")
            monthly_box = chart_box(df, "monthly")
            # Inner-box bar indices (_inner_start_bar, _inner_climax_bar, ...) are
            # positional in the 2y DAILY_STRUCTURE_PERIOD eval frame the daily
            # structure read runs on (evaluation._prepare_eval_frame trims full_df
            # to that period), NOT this up-to-5y df. The visible candles are the
            # trailing show_days bars of BOTH frames, so map an eval-frame bar to a
            # candle index by subtracting the EVAL frame's own left offset. Using
            # len(df) here shifted the inner box ~(5y-2y) bars too far left (it
            # clamped to the chart's left edge — the "inner box past its boundaries"
            # bug); base_len-relative reads like the parent box were immune.
            eval_len = len(_trim_to_period(df, settings.DAILY_STRUCTURE_PERIOD))
            window_start_bar = eval_len - show_days
            def _local_bar(value):
                try:
                    return (
                        int(float(value)) - window_start_bar
                        if value is not None and math.isfinite(float(value))
                        else None
                    )
                except (TypeError, ValueError):
                    return None

            inner_start_local = _local_bar(row.get('_inner_start_bar'))
            # Draw the inner mini-consolidation's RIGHT edge at its last
            # structurally-anchored bar (eval end minus the reserved trigger/edge
            # bars) so the rails hug the coil; the parent box still runs to the last
            # bar. Display-only — no measurement / score / tier change. None when
            # there is no inner box (the frontend then draws to the chart edge).
            inner_end_local = (
                _local_bar(eval_len - 1 - settings.STRUCTURE_EDGE_SKIP_BARS)
                if inner_start_local is not None else None
            )
            
            # Sub-scores power the "why ranked" tag chips on the frontend
            # card. Emit the raw point values for every ALWAYS-EMITTED
            # registry term via the ONE named projection (task 9; the
            # hand-listed tuple was the 6th copy of the scoring vocabulary).
            # Flag-gated v2 term points ride the v2 block below instead —
            # see always_emitted_terms' docstring for why emitted_keys()
            # must never be substituted here.
            sub = row.get('_sub_scores') or {}
            sub_payload = {
                t.key: round(float(sub.get(t.key, 0) or 0), 2)
                for t in taxonomy.always_emitted_terms()
            }

            sector_etf = _sector_etf_for_ticker(ticker, sector_etf_cache)

            chart_data[ticker] = {
                'candles': candles,
                'volumes': volumes,
                'weekly_candles': weekly_candles,
                'weekly_volumes': weekly_volumes,
                'weekly_box': weekly_box,
                'monthly_candles': monthly_candles,
                'monthly_volumes': monthly_volumes,
                'monthly_box': monthly_box,
                'R': round(float(row['_R']), 2),
                'S': round(float(row['_S']), 2),
                'inner_R': row.get('_inner_R'),
                'inner_S': row.get('_inner_S'),
                'inner_box_width': row.get('_inner_box_width'),
                'inner_start_bar': inner_start_local,
                'inner_end_bar': inner_end_local,
                'inner_source': row.get('_inner_source'),
                # Position vocabulary (operator-signed labels 2026-08-30;
                # closed set, resolved engine-side — EC-28: the frontend only
                # looks the value up in wireVocabulary's POSITION_LABELS).
                'inner_position': row.get('_inner_position'),
                'inner_search_start_bar': _local_bar(row.get('_inner_search_start_bar')),
                'inner_climax_bar': _local_bar(row.get('_inner_climax_bar')),
                'inner_reaction_bar': _local_bar(row.get('_inner_reaction_bar')),
                'inner_reaction_pct': row.get('_inner_reaction_pct'),
                'inner_reaction_bars': row.get('_inner_reaction_bars'),
                'lps_in_inner': bool(row.get('_lps_in_inner', False)),
                'base_len': int(row['_base_len']),
                'lps_len': int(row['_lps_len']),
                'lps_offset': int(row['_lps_offset']),
                'r_anchor': int(row['_r_anchor_bar']),
                's_anchor': int(row['_s_anchor_bar']),
                'tier': row['Tier'],
                'score': row['Score'],
                'setup': row['Setup'],
                'sector_etf': sector_etf,
                'sector_name': SECTOR_ETF_NAMES.get(sector_etf) if sector_etf else None,
                # Price vs. breakout trigger — lets the frontend show / sort by
                # "% to trigger" (how much room is left before the entry fires).
                'price': round(float(row['Current Price']), 2),
                'trigger': round(float(row['_trigger_price']), 2),
                'sub_scores': sub_payload,
                'phase_d_inner': bool(row.get('_phase_d_inner', False)),
                # Volume-around-touches signature → drives no_supply /
                # spring_strength / heavy_resistance tags on the card.
                'r_touch_vol_z': row.get('_r_touch_vol_z'),
                's_touch_vol_z': row.get('_s_touch_vol_z'),
                # LPS shape detail (for tooltips / future analysis)
                'lps_descent_frac': row.get('_lps_descent_frac'),
                'lps_high_descent_frac': row.get('_lps_high_descent_frac'),
                'lps_window_range_pct_box': row.get('_lps_window_range_pct_box'),
                'lps_high_extension_box': row.get('_lps_high_extension_box'),
                'lps_high_extension_atr': row.get('_lps_high_extension_atr'),
                'lps_profile_unit': row.get('_lps_profile_unit'),
                'lps_profile_unit_pct': row.get('_lps_profile_unit_pct'),
                'lps_pullback_profile': row.get('_lps_pullback_profile'),
                'lps_terminal_low_tolerance': row.get('_lps_terminal_low_tolerance'),
                'lps_spread_expansion_profile': row.get('_lps_spread_expansion_profile'),
                'lps_first_high': row.get('_lps_first_high'),
                'lps_last_low': row.get('_lps_last_low'),
                'lps_window_high': row.get('_lps_window_high'),
                'lps_window_low': row.get('_lps_window_low'),
                'lps_swing_type': row.get('_lps_swing_type'),
                'lps_anchor_bar': row.get('_lps_anchor_bar'),
                'lps_anchor_date': row.get('_lps_anchor_date'),
                'lps_low_bar': row.get('_lps_low_bar'),
                'lps_low_date': row.get('_lps_low_date'),
                'lps_swing_depth_pct': row.get('_lps_swing_depth_pct'),
                'lps_swing_depth_atr': row.get('_lps_swing_depth_atr'),
                'lps_swing_depth_box': row.get('_lps_swing_depth_box'),
                'lps_zone_type': row.get('_lps_zone_type'),
                # VCP contraction footprint (for tooltips / tag)
                'contraction_count': row.get('_contraction_count'),
                'contraction_quality': row.get('_contraction_quality'),
                'final_contraction_depth': row.get('_final_contraction_depth'),
                'contraction_vol_trend': row.get('_contraction_vol_trend'),
                # Ascending-support / higher-lows footprint (for tooltips / tag)
                'support_slope_atr': row.get('_support_slope_atr'),
                'ascending_support_quality': row.get('_ascending_support_quality'),
                'higher_low_frac': row.get('_support_higher_low_frac'),
                'adr_pct': row.get('_adr_pct'),
                # Bin-B interior trajectory ("eyes inside the base") → drives the
                # interior CoG tooltip on the card. (The worked_equilibrium chip now
                # fires off traversal_density below, not these close-based crossings.)
                'bin_b_cog_end': row.get('_bin_b_cog_end'),
                'bin_b_cog_crossings': row.get('_bin_b_cog_crossings'),
                'bin_b_cog_rng': row.get('_bin_b_cog_rng'),
                'bin_b_cog_corr': row.get('_bin_b_cog_corr'),
                # Limb-traversal density (rail-to-rail swings / significant swings) →
                # drives the worked_equilibrium chip; the real two-sidedness
                # signal. ONE derivation shared with the chip rule (EC-3).
                'traversal_density': traversal_density_from_counts(
                    row.get('_trav_n_full_traversals'), row.get('_trav_n_swings')),
                # HTF (higher-timeframe) context — weekly/monthly Trend+Box read,
                # surfaced to the Screener Grid. Bare keys (htf_w_* / htf_m_*).
                **{c: row.get('_' + c) for c in HTF_COLUMNS},
                'bin_c_present': row.get('_bin_c_present'),
                'bin_c_type': row.get('_bin_c_type'),
                'bin_c_event_date': row.get('_bin_c_event_date'),
                'bin_c_event_bar': _local_bar(row.get('_bin_c_event_bar')),
                'bin_c_undercut_atr': row.get('_bin_c_undercut_atr'),
                'bin_c_recovery_bars': row.get('_bin_c_recovery_bars'),
                'bin_c_recovery_bar': _local_bar(row.get('_bin_c_recovery_bar')),
                'bin_c_time_loc': row.get('_bin_c_time_loc'),
                'bin_c_spring_vol_z': row.get('_bin_c_spring_vol_z'),
                'bin_d_start_bar': _local_bar(row.get('_bin_d_start_bar')),
                'bin_d_support_slope_atr': row.get('_bin_d_support_slope_atr'),
                'bin_d_higher_low_frac': row.get('_bin_d_higher_low_frac'),
                'bin_d_ascending_support_quality': row.get('_bin_d_ascending_support_quality'),
                'bin_d_vs_b_support_quality_delta': row.get('_bin_d_vs_b_support_quality_delta'),
                'bin_d_boundary_source': row.get('_bin_d_boundary_source'),
                'lps_stretch_atr': row.get('_lps_stretch_atr'),
                'lps_stretch_box': row.get('_lps_stretch_box'),
                'last_supper_pullback_from_extension_pct': row.get('_last_supper_pullback_from_extension_pct'),
                'last_supper_source_box_age': row.get('_last_supper_source_box_age'),
                'last_supper_reclaim_quality': row.get('_last_supper_reclaim_quality'),
                'phase_d_evidence_json': row.get('_phase_d_evidence_json'),
                # The narrative fact block (Surface the Read): the event_map
                # archive family projected onto the wire by the SAME extraction
                # both archive writers splat (one producer in event_map.py),
                # plus the electing-pool provenance. Absent-as-None when the
                # Event Map never ran (flag off): NULL means "not measured",
                # never zero — the frontend renders the two distinctly and
                # never re-derives a judgment from the tape.
                'elected_pool': row.get('_elected_pool'),
                'story_admission_profile': row.get('_story_admission_profile'),
                **narrative_chart_fields(row.get),
                **election_trace_chart_fields(row.get),
                # Phase-D scoping bands — consumed by the chart phase overlay.
                # Underscore-prefixed to match the keys chartPhaseOverlay.js reads.
                '_phase_a_start_date': row.get('_phase_a_start_date'),
                '_phase_a_end_date': row.get('_phase_a_end_date'),
                '_phase_b_start_date': row.get('_phase_b_start_date'),
                '_phase_d_start_date': row.get('_phase_d_start_date'),
                '_phase_c_event_date': row.get('_phase_c_event_date'),
                '_lps_zone_low': row.get('_lps_zone_low'),
                '_lps_zone_high': row.get('_lps_zone_high'),
                '_lps_zone_start_date': row.get('_lps_zone_start_date'),
                '_lps_zone_end_date': row.get('_lps_zone_end_date'),
                '_has_mini_consolidation': bool(row.get('_has_mini_consolidation', False)),
                '_scope_confidence': row.get('_scope_confidence'),
                # Advisory metadata (Lane E) — graded tag-chip data, NOT scored /
                # NOT a veto. Only present when the relevant flag is ON (else the
                # eval result carries no such key and these read None -> no chip).
                # Fundamentals are point-in-time (filing-lag gated). The held
                # frontend lane maps these to ⚡ RS Leader / Earnings Accel /
                # days-to-earnings chips.
                'fund_eps_growth_yoy': row.get('_fund_eps_growth_yoy'),
                'fund_sales_growth_yoy': row.get('_fund_sales_growth_yoy'),
                'fund_eps_growth_accel': row.get('_fund_eps_growth_accel'),
                'fund_earnings_surprise': row.get('_fund_earnings_surprise'),
                'days_to_earnings': row.get('_days_to_earnings'),
                'rs_rating': row.get('_rs_rating'),
                'rs_line_latest': row.get('_rs_line_latest'),
                'rs_line_new_high': row.get('_rs_line_new_high'),
                # ── Technical Analysis Grade v2 block (task 9) — key-ABSENT
                # while TA_SCORE_V2 is off (the setup_quality presence pattern; the
                # flag-off wire snapshot pins the absence). The wire carries
                # VERDICTS (EC-28): everything arrives resolved and
                # display-rounded here, once — the archive keeps the full
                # precision. Fixed arity only: chapters are the ruled named
                # scalars, warnings a small id→factor dict — never a
                # per-bar/per-term unbounded structure (the election-trace
                # payload hazard class). Wire names == archive column names
                # (the event_map family precedent).
                **({} if row.get('_ta_grade') is None else {
                    'ta_grade': round(float(row['_ta_grade']), 1),
                    'ta_grade_raw': round(float(row['_ta_grade_raw']), 2),
                    'ta_grade_chapters': {
                        ch: round(float(v), 2)
                        for ch, v in (row.get('_ta_grade_chapters') or {}).items()
                    },
                    'ta_grade_chapter_fractions': {
                        ch: round(float(v), 4)
                        for ch, v in (row.get('_ta_grade_chapter_fractions') or {}).items()
                    },
                    'ta_grade_warnings': row.get('_ta_grade_warnings') or {},
                    # The lens's LPS grade, resolved engine-side (EC-28; legacy
                    # retirement 2026-08-22). None = never measured.
                    'lps_grade_fraction': _round_opt(row.get('_lps_grade_fraction'), 4),
                    'score_spring': _round_opt(row.get('_score_spring'), 2),
                    'score_story_s_tests': _round_opt(row.get('_score_story_s_tests'), 2),
                    'score_story_r_rejections': _round_opt(row.get('_score_story_r_rejections'), 2),
                    'score_story_alternations': _round_opt(row.get('_score_story_alternations'), 2),
                    'score_story_terminal_posture': _round_opt(row.get('_score_story_terminal_posture'), 2),
                    'lps_shrink_frac': _round_opt(row.get('_lps_shrink_frac'), 4),
                    'lps_window_classification': row.get('_lps_window_classification'),
                    'story_richness_rate': _round_opt(row.get('_story_richness_rate'), 4),
                    'trend_base_count': row.get('_trend_base_count'),
                    'inter_base_width_ratio': _round_opt(row.get('_inter_base_width_ratio'), 4),
                    # The resolved chip verdicts (task 10) — the wire carries
                    # the parsed list; [] = resolved-nothing-fired, distinct
                    # from the key being absent flag-off.
                    'fired_tags': row.get('_fired_tags') or [],
                }),
            }
        except Exception as e:
            print(f"  Chart data error on {ticker}: {e}")
    
    return chart_data


def build_health_payload(members, unreadable, data, universe=None):
    """Assemble the ``health_board`` artifact section from classified members.

    ``members`` maps ticker -> ``core.pipeline.context.health_board.MemberHealth`` and
    ``unreadable`` is a list of ``{ticker, reason}`` (short_history / not_available
    / error). Emits ONE dict per member — the closed-set ``state``, the small
    scale-invariant sort fields, the box geometry (``R``/``S``/``base_len``, all
    ``None``/``0`` when there is no box so the reused card draws bare candles), and
    the daily candles/volumes — carrying NO score / tier / trigger / setup field
    (the "no buy language" contract, enforced at the emit site).

    A member whose candle extraction fails degrades into ``unreadable`` rather than
    tearing the section. The returned dict is added to the SAME per-universe
    artifact and rides the single atomic write in ``generate_dashboard`` (it is not
    written here); every value passes through that write's ``_json_safe`` chokepoint.
    """
    is_multi = getattr(data.columns, "nlevels", 1) > 1
    degraded = list(unreadable)
    member_rows = []
    for ticker, health in members.items():
        try:
            # The fold's shared prep — a documented consumer must never
            # re-type it (a bare dropna here silently diverges the day the
            # prep gains a step).
            frame = clean_daily_frame(data[ticker] if is_multi else data)
            candles, volumes, _ = daily_candles(frame)
        except Exception as exc:  # a member that can't render degrades honestly
            print(f"  Health chart error on {ticker}: {exc}")
            degraded.append({"ticker": ticker, "reason": "error"})
            continue
        etf = str(ticker).upper()
        member_rows.append({
            "ticker": etf,
            "name": SECTOR_ETF_NAMES.get(etf),  # friendly sector name when known, else None
            "state": health.state.value,        # exactly one closed-set state string
            "box_pos": health.box_pos,
            "breakout_extension": health.breakout_extension,
            "distance_to_high_pct": health.distance_to_high_pct,
            "R": health.R,
            "S": health.S,
            "base_len": int(health.base_len),
            "candles": candles,
            "volumes": volumes,
        })
    return {
        "members": member_rows,
        "unreadable": degraded,
        # Total members the board attempted this scan (classified + unreadable) so
        # the UI can say "29 members · 5 unavailable" without recomputing.
        "member_count": len(member_rows) + len(degraded),
    }


# ⚠️ LIVE — invoked on every scan by core/pipeline/screening/scan_job.py; writes the React
#    frontend's screener_data.json artifact. DO NOT delete as retired HTML residue.
def generate_dashboard(results_df, data=None, tickers=None, market_context=None,
                       universe=None, health_board=None, *, scan_date):
    """Extract chart data and export it as JSON for the React frontend.

    ``universe`` selects which artifact to write (``None`` = US-Stocks ->
    ``output/screener_data.json``, byte-identical to before); the path is resolved
    through the universe descriptor so the writer and the serving reader stay in
    lockstep on a single closed set of artifact names.

    ``scan_date`` is REQUIRED (council review 2026-08-05, finding 2): it is the
    SAME string ``archive_scan_results`` stamps (scan_job computes it once and
    threads it to both writers), so a verdict recorded against a payload row
    binds to the archive row's identity verbatim — (ticker, scan_date,
    universe_type) — never a client-derived date. An optional default here
    would let an ad-hoc caller publish a live-shaped payload with a null
    identity (EC-26's trap shape).
    """

    # Extract chart data if market data is provided. Skip on an empty result set:
    # an empty scan still writes a valid (empty) artifact so the universe reads as
    # "scanned, matched nothing" rather than "never scanned".
    chart_data = {}
    if data is not None and tickers is not None and not results_df.empty:
        chart_data = _extract_chart_data(data, results_df, tickers)
        print(f"\nExtracted {len(chart_data)} interactive chart models for React dashboard...", flush=True)

    ordered_tickers = []
    for _, row in results_df.iterrows():
        if row['Ticker'] in chart_data:
            ordered_tickers.append(row['Ticker'])

    json_path = resolve_universe(universe).artifact_path()
    os.makedirs(os.path.dirname(json_path), exist_ok=True)

    # Provenance for the concordance loop: the archive identity key's scan-level
    # half plus the engine version that produced this read. Lazy import mirrors
    # the writer's own manifest_hash call site.
    from engine_alpha.freeze.manifest import manifest_hash
    payload_body = {
        "chart_data": chart_data,
        "ordered_tickers": ordered_tickers,
        "market_context": market_context or {},
        "scan_identity": {
            "scan_date": scan_date,
            "universe_type": resolve_universe(universe).universe_type,
            "engine_config_version": manifest_hash(),
        },
    }
    # The health-board section rides this SAME atomic write. Added ONLY when the
    # caller passed one (flag on, non-equities universe) — absent otherwise, so the
    # flag-off / us_equities artifact is byte-identical to before.
    if health_board is not None:
        payload_body["health_board"] = health_board
    payload = _json_safe(payload_body)
    tmp_path = json_path + ".tmp"
    try:
        with open(tmp_path, 'w', encoding='utf-8') as f:
            json.dump(payload, f, allow_nan=False)
        os.replace(tmp_path, json_path)
    except Exception:
        try:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
        except OSError:
            pass
        raise
    
    # flush=True so the webapp's scan stream receives these sentinels immediately
    # — the frontend reveals results on "UI update available" without waiting for
    # the slow archive step that runs after this.
    print(f"Data exported to: {json_path}", flush=True)
    print("UI update available on local webapp.", flush=True)
