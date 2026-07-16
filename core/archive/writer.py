"""
Archive writer — persists screener results into the setup_archive table.

Called automatically after each screener run to build the historical record
of every signal the screener produces.  Market context (SPY trend, VIX,
sector) is fetched and attached to each record.
"""
from __future__ import annotations

import json
import logging
import os
import sys
from datetime import date

import pandas as pd

# Ensure project root is on path for imports
_PROJECT_ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

_BACKEND_DIR = os.path.join(_PROJECT_ROOT, "webapp", "backend")
if _BACKEND_DIR not in sys.path:
    sys.path.append(_BACKEND_DIR)

log = logging.getLogger("chrollo.archive")

# Persistent ticker -> sector-ETF map. Sector membership is stable, so we cache
# it to disk and only pay the (slow, hang-prone) yfinance .info lookup for
# tickers we have never resolved. Lives under output/ (gitignored — regenerable).
_SECTOR_ETF_CACHE_PATH = os.path.join(_PROJECT_ROOT, "output", "sector_etf_cache.json")


def _load_sector_etf_cache() -> dict:
    try:
        with open(_SECTOR_ETF_CACHE_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _save_sector_etf_cache(cache: dict) -> None:
    try:
        os.makedirs(os.path.dirname(_SECTOR_ETF_CACHE_PATH), exist_ok=True)
        with open(_SECTOR_ETF_CACHE_PATH, "w", encoding="utf-8") as f:
            json.dump(cache, f)
    except Exception:
        pass


# Columns added after the initial schema. SQLAlchemy's create_all only
# creates missing tables, not missing columns, so we ALTER TABLE on demand.
# Idempotent: ALTER TABLE ADD COLUMN is a no-op if the column already exists
# (we swallow the OperationalError it raises in that case).
from core.structure.htf import HTF_COLUMN_SQL, htf_archive_values

_NEW_COLUMNS: dict[str, str] = {
    "score_rs_bonus":       "FLOAT",
    "excess_return_6m":     "FLOAT",
    "breadth_pct":          "FLOAT",
    "bars_since_bc":        "INTEGER",
    "descent_length":       "INTEGER",
    "phase_d_inner":        "INTEGER",
    "lps_in_inner":         "INTEGER",
    "inner_source":         "TEXT",
    "inner_search_start_bar": "INTEGER",
    "inner_climax_bar":     "INTEGER",
    "inner_reaction_bar":   "INTEGER",
    "inner_reaction_pct":   "FLOAT",
    "inner_reaction_bars":  "INTEGER",
    # Phase-1 (volume signature + LPS shape/zone + new bonuses)
    "r_touch_vol_z":        "FLOAT",
    "s_touch_vol_z":        "FLOAT",
    "lps_descent_frac":     "FLOAT",
    "lps_zone_type":        "TEXT",
    "score_high_proximity": "FLOAT",
    "score_traversal_quality": "FLOAT",
    "score_breadth_bonus":  "FLOAT",
    # VCP progressive-contraction footprint
    "contraction_count":        "INTEGER",
    "contraction_quality":      "FLOAT",
    "final_contraction_depth":  "FLOAT",
    "contraction_vol_trend":    "FLOAT",
    "score_contraction":        "FLOAT",
    # Base bar-compression texture
    "base_median_spread_atr":      "FLOAT",
    "base_p80_spread_atr":         "FLOAT",
    "base_median_spread_pct_box":  "FLOAT",
    "base_tight_bar_pct":          "FLOAT",
    # Ascending support / higher-lows footprint
    "support_slope_atr":            "FLOAT",
    "ascending_support_quality":    "FLOAT",
    "score_ascending_support":      "FLOAT",
    # Worked-equilibrium occupancy footprint
    "eq_r_touches":                 "INTEGER",
    "eq_s_touches":                 "INTEGER",
    "eq_r_touch_thirds":            "INTEGER",
    "eq_s_touch_thirds":            "INTEGER",
    "eq_lower_dwell":               "FLOAT",
    "eq_mid_dwell":                 "FLOAT",
    "eq_upper_dwell":               "FLOAT",
    "eq_coverage":                  "FLOAT",
    # Gate-margin telemetry (plan task 2): the elected box against the ACTUAL
    # gates — respect band fraction + the dead-space gate's close residence.
    "eq_respect_frac":              "FLOAT",
    "eq_close_lower_dwell":         "FLOAT",
    "eq_close_mid_dwell":           "FLOAT",
    "eq_close_upper_dwell":         "FLOAT",
    # Limb-traversal read (raw, measure-first)
    "trav_n_full_traversals":       "INTEGER",
    "trav_n_swings":                "INTEGER",
    "trav_top_dead_space":          "FLOAT",
    "trav_bottom_dead_space":       "FLOAT",
    "trav_rail_reaches_high":       "INTEGER",
    "trav_rail_reaches_low":        "INTEGER",
    "trav_max_swing_frac":          "FLOAT",
    "trav_last_support_frac":       "FLOAT",
    "trav_coil_floor_pos":          "FLOAT",
    # ADR% absolute-volatility character
    "adr_pct":                      "FLOAT",
    "score_adr":                    "FLOAT",
    # Phase-D scoping layer (descriptive right-most-region bands)
    "scope_phase_a_date":           "TEXT",
    "scope_phase_b_date":           "TEXT",
    "scope_phase_d_date":           "TEXT",
    "scope_phase_c_date":           "TEXT",
    "scope_has_mini":               "INTEGER",
    "scope_confidence":             "FLOAT",
    # Region (bin) features (A/B/D/LPS size, range, volume + Last Supper)
    "bin_a_bars":                   "INTEGER",
    "bin_a_range_pct":              "FLOAT",
    "bin_a_volume_ratio":           "FLOAT",
    "bin_b_bars":                   "INTEGER",
    "bin_b_range_pct":              "FLOAT",
    "bin_b_volume_ratio":           "FLOAT",
    "bin_b_cog_end":                "FLOAT",
    "bin_b_cog_crossings":          "INTEGER",
    "bin_b_cog_rng":                "FLOAT",
    "bin_b_cog_corr":               "FLOAT",
    "bin_c_present":                "INTEGER",
    "bin_c_type":                   "TEXT",
    "bin_c_event_date":             "TEXT",
    "bin_c_event_bar":              "INTEGER",
    "bin_c_undercut_atr":           "FLOAT",
    "bin_c_recovery_bars":          "INTEGER",
    "bin_c_recovery_bar":           "INTEGER",
    "bin_c_time_loc":               "FLOAT",
    "bin_c_spring_vol_z":           "FLOAT",
    "bin_d_bars":                   "INTEGER",
    "bin_d_start_bar":              "INTEGER",
    "bin_d_range_pct":              "FLOAT",
    "bin_d_volume_ratio":           "FLOAT",
    "bin_d_support_slope_atr":      "FLOAT",
    "bin_d_higher_low_frac":        "FLOAT",
    "bin_d_ascending_support_quality": "FLOAT",
    "bin_d_boundary_source":        "TEXT",
    "phase_d_evidence_json":        "TEXT",
    "bin_lps_bars":                 "INTEGER",
    "lps_position_in_box":          "FLOAT",
    "bin_d_vs_b_range_ratio":       "FLOAT",
    "bin_d_vs_b_volume_ratio":      "FLOAT",
    "bin_d_vs_b_support_quality_delta": "FLOAT",
    "lps_stretch_atr":              "FLOAT",
    "lps_stretch_box":              "FLOAT",
    "lps_swing_type":               "TEXT",
    "lps_anchor_bar":               "INTEGER",
    "lps_anchor_date":              "TEXT",
    "lps_low_bar":                  "INTEGER",
    "lps_low_date":                 "TEXT",
    "lps_swing_depth_pct":          "FLOAT",
    "lps_swing_depth_atr":          "FLOAT",
    "lps_swing_depth_box":          "FLOAT",
    "last_supper_pullback_from_extension_pct": "FLOAT",
    "last_supper_source_box_age":   "INTEGER",
    "last_supper_reclaim_quality":  "FLOAT",
    # Minervini Stage-2 trend template (raw context)
    "stage2_ma_stack_pass":         "INTEGER",
    "stage2_ma200_slope_1m_pct":    "FLOAT",
    "stage2_52w_low_pct":           "FLOAT",
    "stage2_trend_pass_count":      "INTEGER",
    "stage2_trend_pass":            "INTEGER",
    # Market regime state (run-level context, observability only)
    "regime_state":                 "TEXT",
    "regime_breadth_50_pct":        "FLOAT",
    "regime_breadth_200_pct":       "FLOAT",
    "regime_distribution_days":     "INTEGER",
    "regime_spy_above_50":          "INTEGER",
    "regime_spy_above_200":         "INTEGER",
    "regime_spy_50d_slope_pct":     "FLOAT",
    "regime_qqq_above_50":          "INTEGER",
    "regime_qqq_above_200":         "INTEGER",
    "regime_qqq_50d_slope_pct":     "FLOAT",
}
# NOTE: the Lane E advisory columns (fund_*, days_to_earnings, rs_rating,
# rs_line_*, sector_rank_*) are intentionally NOT hand-listed here. Like
# engine_config_version, they are MODEL-ONLY adds: the backend's Track B
# auto-migration (startup._apply_model_add_columns) and this writer's own
# model-derived second pass in _ensure_new_columns ADD them from
# SetupArchive.__table__, so the model stays the single source and the
# _NEW_COLUMNS <= _MIGRATIONS guard (test_archive_writer_columns_are_modeled_
# and_migrated) stays satisfied without touching the legacy _MIGRATIONS list.
# NOTE: engine_config_version (the frozen-config stamp) is intentionally NOT in
# _NEW_COLUMNS. It is added to the live schema by Track B's model-derived
# auto-migration (webapp/backend/services/startup._apply_model_add_columns,
# which diffs SetupArchive.__table__ at backend boot) and by create_all on a
# fresh table — so the writer needs no hand-listed ALTER for it, and the
# _NEW_COLUMNS <= _MIGRATIONS guard (test_archive_writer_columns_are_modeled_
# and_migrated) stays satisfied without touching the legacy _MIGRATIONS list.

# HTF (higher-timeframe) context columns — single source of truth in
# core.structure.htf so the writer / model / migrations / seed stay in sync.
_NEW_COLUMNS.update(HTF_COLUMN_SQL)

# Event Map tape-summary columns — single source in core.structure.event_map.
# MODEL-ONLY schema adds (see archive_models.SetupArchive): deliberately NOT
# merged into _NEW_COLUMNS; the model-derived pass in _ensure_new_columns and
# the backend's Track B auto-migration ADD them.
from core.structure.event_map import event_map_archive_values


def _ensure_new_columns(engine) -> None:
    """Add post-schema columns to setup_archive if they don't exist yet.

    Two passes, both ADD-only and idempotent:
      1. the hand-listed ``_NEW_COLUMNS`` (legacy explicit SQL types);
      2. a MODEL-DERIVED diff — any column on SetupArchive.__table__ missing from
         the live table. This keeps the writer / seed paths self-sufficient on an
         existing table for MODEL-ONLY columns (e.g. engine_config_version, which
         is deliberately absent from _NEW_COLUMNS) when run standalone — i.e.
         before the backend's Track B auto-migration has booted. Mirrors
         startup.model_add_column_migrations; the model stays the single source.
    """
    from sqlalchemy import inspect, text

    from archive_models import SetupArchive as _Model

    inspector = inspect(engine)
    if "setup_archive" not in inspector.get_table_names():
        return  # create_all will handle it
    existing = {col["name"] for col in inspector.get_columns("setup_archive")}
    with engine.begin() as conn:
        for name, sql_type in _NEW_COLUMNS.items():
            if name not in existing:
                conn.execute(text(f"ALTER TABLE setup_archive ADD COLUMN {name} {sql_type}"))
                existing.add(name)
        for column in _Model.__table__.columns:
            if column.primary_key or column.name in existing:
                continue
            conn.execute(
                text(f"ALTER TABLE setup_archive ADD COLUMN {column.name} {column.type}")
            )
            existing.add(column.name)


def archive_scan_results(
    results_df: pd.DataFrame,
    scan_date_str: str | None = None,
    enable: bool = False,
    universe=None,
) -> int:
    """Persist every row in results_df to the setup_archive table.

    Gated by settings.ARCHIVE_LIVE_SCANS (passed in as ``enable``). Live
    archiving is the engine-validation strategy: every daily signal becomes
    part of the unbiased record whose forward returns measure the screener's
    real edge. enable=False only suppresses writes (e.g. ad-hoc/test scans).
    """
    if not enable:
        return 0

    if results_df is None or results_df.empty:
        log.info("No results to archive.")
        return 0

    from sqlalchemy.orm import sessionmaker

    import yfinance as yf
    from archive_models import SetupArchive, get_market_context, get_sector_etf, get_sector_trend
    from core.pipeline.universe import resolve_universe
    from database import make_sqlite_engine

    # Which universe these rows belong to (default us_stocks -> 'us_equities'),
    # stamped on every row and part of the upsert identity so the same symbol can
    # be archived independently per universe on one scan date.
    universe_type = resolve_universe(universe).universe_type

    def _rs_from_series(close, base_start, base_end,
                        stock_start_close: float, stock_end_close: float) -> float | None:
        """Stock base-window return minus sector ETF base-window return, using a
        PRE-DOWNLOADED ETF close series sliced to the base window (no per-ticker
        download). Positive = stock outperformed its sector during the base.
        """
        if close is None or not base_start or not base_end or stock_start_close <= 0:
            return None
        try:
            seg = close.loc[base_start:base_end]
            if len(seg) < 2:
                return None
            sec_ret = (float(seg.iloc[-1]) - float(seg.iloc[0])) / float(seg.iloc[0])
            stock_ret = (stock_end_close - stock_start_close) / stock_start_close
            return round(stock_ret - sec_ret, 5)
        except Exception:
            return None

    def _bool_int(value) -> int | None:
        if value is None:
            return None
        try:
            if pd.isna(value):
                return None
        except (TypeError, ValueError):
            pass
        return int(bool(value))

    scan_dt = scan_date_str or date.today().strftime("%Y-%m-%d")

    # Connect to the same DB the webapp uses. WAL + busy_timeout (set inside
    # make_sqlite_engine) keep us from blowing up if the backend holds a
    # short read lock while the scan tries to flush.
    db_path = os.path.join(_BACKEND_DIR, "trading_journal.db")
    engine = make_sqlite_engine(db_path)

    # Ensure the table exists
    from archive_models import SetupArchive as _M  # noqa: F811
    _M.metadata.create_all(bind=engine)
    _ensure_new_columns(engine)

    # autoflush=False: the loop below does an existence-check query on every
    # ticker, and autoflush would push pending UPDATEs through that query —
    # that's exactly the autoflush-during-query path that triggered the
    # original "database is locked" error. We commit explicitly at the end.
    Session = sessionmaker(bind=engine, autoflush=False)
    session = Session()

    # Frozen engine-config version stamped on every row written this run
    # (computed once — provenance only, never a computed engine field).
    from core.freeze.manifest import manifest_hash
    engine_config_version = manifest_hash()

    # Fetch market context once for the whole scan (hard-bounded internally).
    print(f"  Fetching market context for {scan_dt}...", flush=True)
    market_ctx = get_market_context(scan_dt)

    # ── Sector / RS enrichment: resolve once, batch once ─────────────────
    # The old code did 3 network round-trips PER TICKER (sector .info, sector
    # trend, RS-vs-sector download) — ~440 calls for a 150-ticker scan, which is
    # what made archiving crawl. Instead:
    #   1. ticker -> sector-ETF is cached to disk (sector membership is stable),
    #      so .info is only hit for tickers we've never resolved;
    #   2. each UNIQUE sector ETF is downloaded ONCE over the scan's whole base
    #      window and reused for every ticker in that sector;
    #   3. sector trend is computed once per unique ETF.
    rows = [r for _, r in results_df.iterrows() if r.get("Ticker")]

    print("  Resolving sector ETFs...", flush=True)
    sector_etf_cache = _load_sector_etf_cache()       # ticker -> "XLK" | "" (persisted)
    newly_resolved = False
    for r in rows:
        tk = str(r.get("Ticker"))
        if tk not in sector_etf_cache:
            sector_etf_cache[tk] = get_sector_etf(tk) or ""
            newly_resolved = True
    if newly_resolved:
        _save_sector_etf_cache(sector_etf_cache)

    unique_etfs: set[str] = set()
    starts: list[str] = []
    ends: list[str] = []
    for r in rows:
        etf = sector_etf_cache.get(str(r.get("Ticker")), "")
        if etf:
            unique_etfs.add(etf)
        if r.get("_base_date_start"):
            starts.append(r["_base_date_start"])
        if r.get("_base_date_end"):
            ends.append(r["_base_date_end"])

    # Batch-download each unique sector ETF ONCE over the global base window.
    etf_close: dict[str, "pd.Series"] = {}
    if unique_etfs and starts and ends:
        from core.pipeline.downloads import price_auto_adjust  # noqa: PLC0415 — call-site import; module-level would trip the backend config-shadow trap
        g_start, g_end = min(starts), max(ends)
        print(f"  Fetching {len(unique_etfs)} sector ETF series...", flush=True)
        for etf in unique_etfs:
            try:
                d = yf.download(etf, start=g_start, end=g_end, progress=False,
                                timeout=20, auto_adjust=price_auto_adjust())
                if d is not None and not d.empty:
                    c = d["Close"]
                    if hasattr(c, "columns"):
                        c = c.iloc[:, 0]
                    etf_close[etf] = c
            except Exception:
                pass

    # Sector trend once per unique ETF (not per ticker).
    sector_trend_memo: dict[str, str | None] = {
        etf: get_sector_trend(etf, scan_dt) for etf in unique_etfs
    }

    # Scan-wide ADVISORY sector ranking (Lane E). No-op + {} when
    # SECTOR_RANKING_ENABLED is OFF, so nothing is added to flags-OFF rows.
    from core.regime.scan_context import compute_scan_sector_ranking, sector_rank_fields
    sector_ranking = compute_scan_sector_ranking()

    def sector_rank_columns(sector_etf: str | None) -> dict:
        """Map the advisory ``_``-prefixed sector-rank fields to archive columns
        (``_sector_rank_pct`` -> ``sector_rank_pct``). Empty dict -> no values
        set (column stays NULL), so flags-OFF rows are untouched."""
        fields = sector_rank_fields(sector_etf, sector_ranking)
        return {k.lstrip("_"): v for k, v in fields.items()}

    written = 0
    for _, row in results_df.iterrows():
        ticker = row.get("Ticker", "")
        if not ticker:
            continue

        # Sector ETF + trend + RS — all served from the pre-built caches above
        # (zero per-ticker network calls).
        sector_etf = sector_etf_cache.get(ticker) or None
        sector_trend = sector_trend_memo.get(sector_etf) if sector_etf else None
        rs_vs_sector = _rs_from_series(
            etf_close.get(sector_etf) if sector_etf else None,
            row.get("_base_date_start"), row.get("_base_date_end"),
            float(row.get("_base_close_start") or 0),
            float(row.get("_base_close_end") or 0),
        )

        # Extract sub-scores
        sub = row.get("_sub_scores", {})
        if not isinstance(sub, dict):
            sub = {}

        # Upsert: check if record exists for this (ticker, scan_date, universe_type)
        existing = (
            session.query(SetupArchive)
            .filter_by(ticker=ticker, scan_date=scan_dt, universe_type=universe_type)
            .first()
        )

        values = dict(
            ticker=ticker,
            scan_date=scan_dt,
            setup_type=row.get("Setup", ""),
            tier=row.get("Tier", ""),
            score=float(row.get("Score", 0)),
            current_price=float(row.get("Current Price", 0)),
            r_level=float(row.get("_R", 0)),
            s_level=float(row.get("_S", 0)),
            trigger_price=float(row.get("_trigger_price", 0)),
            base_length=int(row.get("Base Len", 0)),
            box_width=float(row.get("Box Width", 0)),
            touches=int(row.get("Touches", 0)),
            r_touches=int(row.get("_r_touches", 0)),
            s_touches=int(row.get("_s_touches", 0)),
            atr_ratio=float(row.get("ATR Ratio", 0)),
            lps_length=int(row.get("LPS Length", 0)),
            breach_days=int(row.get("Breach Days", 0)),
            vol_contraction=float(row.get("_vol_contraction", 0)),
            tightness_ratio=float(row.get("_tightness_ratio", 0)),
            # Sub-scores
            score_box_tightness=sub.get("box_tightness"),
            score_touch_density=sub.get("touch_density"),
            score_traversal_quality=sub.get("traversal_quality"),
            score_atr_squeeze=sub.get("atr_squeeze"),
            score_lps_tightness=sub.get("lps_tightness"),
            score_vol_contraction=sub.get("vol_contraction"),
            score_base_age=sub.get("base_age"),
            score_uptrend_bonus=sub.get("uptrend_bonus"),
            score_rs_bonus=sub.get("rs_bonus"),
            score_high_proximity=sub.get("high_proximity"),
            score_breadth_bonus=sub.get("breadth_bonus"),
            # Volume-around-touches signature + LPS shape/zone detail
            r_touch_vol_z=row.get("_r_touch_vol_z"),
            s_touch_vol_z=row.get("_s_touch_vol_z"),
            lps_descent_frac=row.get("_lps_descent_frac"),
            lps_zone_type=row.get("_lps_zone_type"),
            # VCP contraction footprint
            contraction_count=row.get("_contraction_count"),
            contraction_quality=row.get("_contraction_quality"),
            final_contraction_depth=row.get("_final_contraction_depth"),
            contraction_vol_trend=row.get("_contraction_vol_trend"),
            score_contraction=sub.get("contraction"),
            # Base bar-compression texture
            base_median_spread_atr=row.get("_base_median_spread_atr"),
            base_p80_spread_atr=row.get("_base_p80_spread_atr"),
            base_median_spread_pct_box=row.get("_base_median_spread_pct_box"),
            base_tight_bar_pct=row.get("_base_tight_bar_pct"),
            # Ascending-support / higher-lows footprint
            support_slope_atr=row.get("_support_slope_atr"),
            ascending_support_quality=row.get("_ascending_support_quality"),
            score_ascending_support=sub.get("ascending_support"),
            # Worked-equilibrium occupancy metrics (raw, measure-first)
            eq_r_touches=row.get("_eq_r_touches"),
            eq_s_touches=row.get("_eq_s_touches"),
            eq_r_touch_thirds=row.get("_eq_r_touch_thirds"),
            eq_s_touch_thirds=row.get("_eq_s_touch_thirds"),
            eq_lower_dwell=row.get("_eq_lower_dwell"),
            eq_mid_dwell=row.get("_eq_mid_dwell"),
            eq_upper_dwell=row.get("_eq_upper_dwell"),
            eq_coverage=row.get("_eq_coverage"),
            eq_respect_frac=row.get("_eq_respect_frac"),
            eq_close_lower_dwell=row.get("_eq_close_lower_dwell"),
            eq_close_mid_dwell=row.get("_eq_close_mid_dwell"),
            eq_close_upper_dwell=row.get("_eq_close_upper_dwell"),
            # Limb-traversal read (raw, measure-first)
            trav_n_full_traversals=row.get("_trav_n_full_traversals"),
            trav_n_swings=row.get("_trav_n_swings"),
            trav_top_dead_space=row.get("_trav_top_dead_space"),
            trav_bottom_dead_space=row.get("_trav_bottom_dead_space"),
            trav_rail_reaches_high=row.get("_trav_rail_reaches_high"),
            trav_rail_reaches_low=row.get("_trav_rail_reaches_low"),
            trav_max_swing_frac=row.get("_trav_max_swing_frac"),
            trav_last_support_frac=row.get("_trav_last_support_frac"),
            trav_coil_floor_pos=row.get("_trav_coil_floor_pos"),
            # ADR% absolute-volatility character
            adr_pct=row.get("_adr_pct"),
            score_adr=sub.get("adr"),
            # Market context
            spy_trend=market_ctx.get("spy_trend"),
            vix_level=market_ctx.get("vix_level"),
            sector_etf=sector_etf,
            sector_trend=sector_trend,
            rs_vs_sector_pct=rs_vs_sector,
            dist_52w_high_pct=row.get("_dist_52w_high_pct"),
            excess_return_6m=row.get("_excess_return_6m"),
            breadth_pct=row.get("_breadth_pct"),
            regime_state=row.get("_regime_state"),
            regime_breadth_50_pct=row.get("_regime_breadth_50_pct"),
            regime_breadth_200_pct=row.get("_regime_breadth_200_pct"),
            regime_distribution_days=row.get("_regime_distribution_days"),
            regime_spy_above_50=_bool_int(row.get("_regime_spy_above_50")),
            regime_spy_above_200=_bool_int(row.get("_regime_spy_above_200")),
            regime_spy_50d_slope_pct=row.get("_regime_spy_50d_slope_pct"),
            regime_qqq_above_50=_bool_int(row.get("_regime_qqq_above_50")),
            regime_qqq_above_200=_bool_int(row.get("_regime_qqq_above_200")),
            regime_qqq_50d_slope_pct=row.get("_regime_qqq_50d_slope_pct"),
            bars_since_bc=row.get("_bars_since_BC"),
            # descent_length spans BC anchor → box start (the inner mini-AR pivot
            # selected by the cand_start trim in _phase_b_zigzag), not BC → original
            # AR low. Includes the early-chop drift between AR and the working box.
            descent_length=row.get("_descent_length"),
            phase_d_inner=int(bool(row.get("_phase_d_inner"))) if row.get("_phase_d_inner") is not None else None,
            lps_in_inner=int(bool(row.get("_lps_in_inner"))) if row.get("_lps_in_inner") is not None else None,
            inner_source=row.get("_inner_source"),
            inner_search_start_bar=row.get("_inner_search_start_bar"),
            inner_climax_bar=row.get("_inner_climax_bar"),
            inner_reaction_bar=row.get("_inner_reaction_bar"),
            inner_reaction_pct=row.get("_inner_reaction_pct"),
            inner_reaction_bars=row.get("_inner_reaction_bars"),
            # Phase-D scoping layer (descriptive right-most-region bands)
            scope_phase_a_date=row.get("_phase_a_start_date"),
            scope_phase_b_date=row.get("_phase_b_start_date"),
            scope_phase_d_date=row.get("_phase_d_start_date"),
            scope_phase_c_date=row.get("_phase_c_event_date"),
            scope_has_mini=(int(bool(row.get("_has_mini_consolidation")))
                            if row.get("_has_mini_consolidation") is not None else None),
            scope_confidence=row.get("_scope_confidence"),
            # Region (bin) features (A/B/D/LPS size, range, volume + Last Supper)
            bin_a_bars=row.get("_bin_a_bars"),
            bin_a_range_pct=row.get("_bin_a_range_pct"),
            bin_a_volume_ratio=row.get("_bin_a_volume_ratio"),
            bin_b_bars=row.get("_bin_b_bars"),
            bin_b_range_pct=row.get("_bin_b_range_pct"),
            bin_b_volume_ratio=row.get("_bin_b_volume_ratio"),
            bin_b_cog_end=row.get("_bin_b_cog_end"),
            bin_b_cog_crossings=row.get("_bin_b_cog_crossings"),
            bin_b_cog_rng=row.get("_bin_b_cog_rng"),
            bin_b_cog_corr=row.get("_bin_b_cog_corr"),
            bin_c_present=_bool_int(row.get("_bin_c_present")),
            bin_c_type=row.get("_bin_c_type"),
            bin_c_event_date=row.get("_bin_c_event_date"),
            bin_c_event_bar=row.get("_bin_c_event_bar"),
            bin_c_undercut_atr=row.get("_bin_c_undercut_atr"),
            bin_c_recovery_bars=row.get("_bin_c_recovery_bars"),
            bin_c_recovery_bar=row.get("_bin_c_recovery_bar"),
            bin_c_time_loc=row.get("_bin_c_time_loc"),
            bin_c_spring_vol_z=row.get("_bin_c_spring_vol_z"),
            bin_d_bars=row.get("_bin_d_bars"),
            bin_d_start_bar=row.get("_bin_d_start_bar"),
            bin_d_range_pct=row.get("_bin_d_range_pct"),
            bin_d_volume_ratio=row.get("_bin_d_volume_ratio"),
            bin_d_support_slope_atr=row.get("_bin_d_support_slope_atr"),
            bin_d_higher_low_frac=row.get("_bin_d_higher_low_frac"),
            bin_d_ascending_support_quality=row.get("_bin_d_ascending_support_quality"),
            bin_d_boundary_source=row.get("_bin_d_boundary_source"),
            phase_d_evidence_json=row.get("_phase_d_evidence_json"),
            bin_lps_bars=row.get("_bin_lps_bars"),
            lps_position_in_box=row.get("_lps_position_in_box"),
            bin_d_vs_b_range_ratio=row.get("_bin_d_vs_b_range_ratio"),
            bin_d_vs_b_volume_ratio=row.get("_bin_d_vs_b_volume_ratio"),
            bin_d_vs_b_support_quality_delta=row.get("_bin_d_vs_b_support_quality_delta"),
            lps_stretch_atr=row.get("_lps_stretch_atr"),
            lps_stretch_box=row.get("_lps_stretch_box"),
            lps_swing_type=row.get("_lps_swing_type"),
            lps_anchor_bar=row.get("_lps_anchor_bar"),
            lps_anchor_date=row.get("_lps_anchor_date"),
            lps_low_bar=row.get("_lps_low_bar"),
            lps_low_date=row.get("_lps_low_date"),
            lps_swing_depth_pct=row.get("_lps_swing_depth_pct"),
            lps_swing_depth_atr=row.get("_lps_swing_depth_atr"),
            lps_swing_depth_box=row.get("_lps_swing_depth_box"),
            last_supper_pullback_from_extension_pct=row.get("_last_supper_pullback_from_extension_pct"),
            last_supper_source_box_age=row.get("_last_supper_source_box_age"),
            last_supper_reclaim_quality=row.get("_last_supper_reclaim_quality"),
            # Minervini Stage-2 trend-template context (raw, no scoring)
            stage2_ma_stack_pass=(int(bool(row.get("_stage2_ma_stack_pass")))
                                  if row.get("_stage2_ma_stack_pass") is not None else None),
            stage2_ma200_slope_1m_pct=row.get("_stage2_ma200_slope_1m_pct"),
            stage2_52w_low_pct=row.get("_stage2_52w_low_pct"),
            stage2_trend_pass_count=row.get("_stage2_trend_pass_count"),
            stage2_trend_pass=(int(bool(row.get("_stage2_trend_pass")))
                               if row.get("_stage2_trend_pass") is not None else None),
            # HTF (higher-timeframe) context — same engine on weekly/monthly bars
            **htf_archive_values(row.get, prefixed=True),
            # Event Map tape summary — NULL when EVENT_MAP_ENABLED is off
            **event_map_archive_values(row.get, prefixed=True),
            # Advisory metadata (Lane E) — graded chips, NOT scored / NOT a veto.
            # Per-ticker fundamentals / RS-line / days-to-earnings come from the
            # eval result (set by core.fundamentals.advisory when the flags are on;
            # absent -> NULL). The universe RS rating was attached in the screener
            # post-pass; sector rank is resolved here from the scan-wide ranking.
            fund_eps_growth_yoy=row.get("_fund_eps_growth_yoy"),
            fund_sales_growth_yoy=row.get("_fund_sales_growth_yoy"),
            fund_eps_growth_accel=row.get("_fund_eps_growth_accel"),
            fund_earnings_surprise=row.get("_fund_earnings_surprise"),
            days_to_earnings=row.get("_days_to_earnings"),
            rs_rating=row.get("_rs_rating"),
            rs_line_latest=row.get("_rs_line_latest"),
            rs_line_new_high=_bool_int(row.get("_rs_line_new_high")),
            **sector_rank_columns(sector_etf),
            engine_config_version=engine_config_version,
            source="screener",
            universe_type=universe_type,
        )

        if existing:
            for k, v in values.items():
                setattr(existing, k, v)
        else:
            session.add(SetupArchive(**values))

        written += 1

    session.commit()
    session.close()

    print(f"  Archived {written} setups to setup_archive (date={scan_dt}).", flush=True)
    return written
