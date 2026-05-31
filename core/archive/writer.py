"""
Archive writer — persists screener results into the setup_archive table.

Called automatically after each screener run to build the historical record
of every signal the screener produces.  Market context (SPY trend, VIX,
sector) is fetched and attached to each record.
"""
from __future__ import annotations

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


# Columns added after the initial schema. SQLAlchemy's create_all only
# creates missing tables, not missing columns, so we ALTER TABLE on demand.
# Idempotent: ALTER TABLE ADD COLUMN is a no-op if the column already exists
# (we swallow the OperationalError it raises in that case).
_NEW_COLUMNS: dict[str, str] = {
    "score_rs_bonus":       "FLOAT",
    "excess_return_6m":     "FLOAT",
    "breadth_pct":          "FLOAT",
    "bars_since_bc":        "INTEGER",
    "descent_length":       "INTEGER",
    "phase_d_inner":        "INTEGER",
    # Phase-1 (volume signature + LPS shape/zone + new bonuses)
    "r_touch_vol_z":        "FLOAT",
    "s_touch_vol_z":        "FLOAT",
    "lps_descent_frac":     "FLOAT",
    "lps_zone_type":        "TEXT",
    "score_high_proximity": "FLOAT",
    "score_breadth_bonus":  "FLOAT",
    # VCP progressive-contraction footprint
    "contraction_count":        "INTEGER",
    "contraction_quality":      "FLOAT",
    "final_contraction_depth":  "FLOAT",
    "score_contraction":        "FLOAT",
}


def _ensure_new_columns(engine) -> None:
    """Add post-schema columns to setup_archive if they don't exist yet."""
    from sqlalchemy import inspect, text

    inspector = inspect(engine)
    if "setup_archive" not in inspector.get_table_names():
        return  # create_all will handle it
    existing = {col["name"] for col in inspector.get_columns("setup_archive")}
    with engine.begin() as conn:
        for name, sql_type in _NEW_COLUMNS.items():
            if name not in existing:
                conn.execute(text(f"ALTER TABLE setup_archive ADD COLUMN {name} {sql_type}"))


def archive_scan_results(
    results_df: pd.DataFrame,
    scan_date_str: str | None = None,
    enable: bool = False,
) -> int:
    """Persist every row in results_df to the setup_archive table.

    Disabled by default: the archive is a curated regression suite for
    seed/manual setups (see core/archive/seed.py and /archive/add-setup),
    not a log of every daily scan. Pass enable=True to opt back in.
    """
    if not enable:
        return 0

    if results_df is None or results_df.empty:
        log.info("No results to archive.")
        return 0

    from sqlalchemy.orm import sessionmaker

    import yfinance as yf
    from archive_models import SetupArchive, get_market_context, get_sector_etf, get_sector_trend
    from database import make_sqlite_engine

    def _rs_vs_sector(sector: str | None, base_start: str | None, base_end: str | None,
                      stock_start_close: float, stock_end_close: float) -> float | None:
        """Stock base-window return minus sector ETF base-window return.

        Positive = stock outperformed its sector during the base. RS leaders
        are statistically the breakouts that hold.
        """
        if not sector or not base_start or not base_end or stock_start_close <= 0:
            return None
        try:
            data = yf.download(
                sector, start=base_start, end=base_end, progress=False, timeout=20, auto_adjust=True,
            )
            if data is None or data.empty:
                return None
            close = data["Close"]
            if hasattr(close, "columns"):
                close = close.iloc[:, 0]
            if len(close) < 2:
                return None
            sec_ret = (float(close.iloc[-1]) - float(close.iloc[0])) / float(close.iloc[0])
            stock_ret = (stock_end_close - stock_start_close) / stock_start_close
            return round(stock_ret - sec_ret, 5)
        except Exception:
            return None

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

    # Fetch market context once for the whole scan
    print(f"  Fetching market context for {scan_dt}...", flush=True)
    market_ctx = get_market_context(scan_dt)

    # Cache sector lookups to avoid repeated API calls
    sector_cache: dict[str, tuple[str | None, str | None]] = {}

    written = 0
    for _, row in results_df.iterrows():
        ticker = row.get("Ticker", "")
        if not ticker:
            continue

        # Sector ETF + trend (cached per ticker)
        if ticker not in sector_cache:
            etf = get_sector_etf(ticker)
            trend = get_sector_trend(etf, scan_dt) if etf else None
            sector_cache[ticker] = (etf, trend)
        sector_etf, sector_trend = sector_cache[ticker]

        # RS vs sector during the base window. Endpoints come from the
        # screener; we just diff against the sector's performance over the
        # same dates.
        rs_vs_sector = _rs_vs_sector(
            sector_etf,
            row.get("_base_date_start"), row.get("_base_date_end"),
            float(row.get("_base_close_start") or 0),
            float(row.get("_base_close_end") or 0),
        )

        # Extract sub-scores
        sub = row.get("_sub_scores", {})
        if not isinstance(sub, dict):
            sub = {}

        # Upsert: check if record exists for this (ticker, scan_date)
        existing = (
            session.query(SetupArchive)
            .filter_by(ticker=ticker, scan_date=scan_dt)
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
            score_oscillation=sub.get("oscillation"),
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
            score_contraction=sub.get("contraction"),
            # Market context
            spy_trend=market_ctx.get("spy_trend"),
            vix_level=market_ctx.get("vix_level"),
            sector_etf=sector_etf,
            sector_trend=sector_trend,
            rs_vs_sector_pct=rs_vs_sector,
            dist_52w_high_pct=row.get("_dist_52w_high_pct"),
            excess_return_6m=row.get("_excess_return_6m"),
            breadth_pct=row.get("_breadth_pct"),
            bars_since_bc=row.get("_bars_since_BC"),
            # descent_length spans BC anchor → box start (the inner mini-AR pivot
            # selected by the cand_start trim in _phase_b_zigzag), not BC → original
            # AR low. Includes the early-chop drift between AR and the working box.
            descent_length=row.get("_descent_length"),
            phase_d_inner=int(bool(row.get("_phase_d_inner"))) if row.get("_phase_d_inner") is not None else None,
            source="screener",
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
