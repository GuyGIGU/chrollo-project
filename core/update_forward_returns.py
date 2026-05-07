"""
Forward return updater — backfills forward returns, MFE/MAE, and trigger status
for archived setups that are old enough to have outcome data.

Run manually:
    python -m core.update_forward_returns

Or schedule via Windows Task Scheduler for nightly updates.
"""
from __future__ import annotations

import logging
import os
import sys
from datetime import datetime, timedelta

import numpy as np
import pandas as pd
import yfinance as yf

_PROJECT_ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

_BACKEND_DIR = os.path.join(_PROJECT_ROOT, "webapp", "backend")
if _BACKEND_DIR not in sys.path:
    sys.path.append(_BACKEND_DIR)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("chrollo.fwd_returns")


def _trading_days_since(scan_date_str: str) -> int:
    """Rough estimate of trading days elapsed since scan_date."""
    delta = (datetime.today() - datetime.strptime(scan_date_str, "%Y-%m-%d")).days
    return int(delta * 5 / 7)  # rough business day estimate


def _compute_returns(
    fwd_df: pd.DataFrame,
    scan_close: float,
    trigger_price: float | None,
    direction: str = "long",
    s_level: float | None = None,
    vol_50_at_scan: float | None = None,
) -> dict:
    """Compute forward returns, MFE, MAE, and trigger status from forward price data.

    Args:
        fwd_df: DataFrame of OHLCV data AFTER the scan date.
        scan_close: The closing price on the scan date.
        trigger_price: The trigger price for the setup (if LPS/REBOUND).
        direction: 'long' (all our setups are long-biased).
        s_level: Box support level — used as the stop reference for R-multiple.
            R = MFE / risk_pct, where risk_pct = (entry − s_level × 0.97) / entry.
            (LPS_HOLD_TOLERANCE = 0.97; same buffer the screener uses.)
        vol_50_at_scan: 50d avg volume at the scan bar — used to compute
            ``trigger_volume_ratio`` (volume on the trigger day vs. 50d avg).

    Returns:
        Dict of return fields ready to write to the archive.
    """
    if fwd_df.empty or scan_close <= 0:
        return {}

    closes = fwd_df["Close"]
    if hasattr(closes, "columns"):
        closes = closes.iloc[:, 0]
    closes = closes.values.astype(float)

    highs = fwd_df["High"]
    if hasattr(highs, "columns"):
        highs = highs.iloc[:, 0]
    highs = highs.values.astype(float)

    lows = fwd_df["Low"]
    if hasattr(lows, "columns"):
        lows = lows.iloc[:, 0]
    lows = lows.values.astype(float)

    volumes = fwd_df["Volume"] if "Volume" in fwd_df.columns else None
    if volumes is not None:
        if hasattr(volumes, "columns"):
            volumes = volumes.iloc[:, 0]
        volumes = volumes.values.astype(float)

    result: dict = {}

    # Forward returns at various horizons
    for n, key in [(1, "fwd_return_1d"), (5, "fwd_return_5d"),
                   (10, "fwd_return_10d"), (20, "fwd_return_20d"),
                   (60, "fwd_return_60d")]:
        if len(closes) >= n:
            result[key] = round((closes[n - 1] - scan_close) / scan_close, 5)

    # Risk per share (long) — entry minus stop. Stop = s_level × 0.97
    # (matches the screener's LPS_HOLD_TOLERANCE buffer). If s_level is missing
    # or the stop sits above entry (degenerate), R-multiple stays None.
    risk_pct = None
    if s_level and s_level > 0:
        stop = s_level * 0.97
        if scan_close > stop:
            risk_pct = (scan_close - stop) / scan_close

    # MFE / MAE at 20d and 60d. Also stamp the bar index/date the extreme hit
    # so the chart can plot a marker.
    for n, suffix in [(20, "20d"), (60, "60d")]:
        if len(highs) >= n:
            window_highs = highs[:n]
            window_lows = lows[:n]
            mfe_idx = int(np.argmax(window_highs))
            mae_idx = int(np.argmin(window_lows))
            mfe = (window_highs[mfe_idx] - scan_close) / scan_close
            mae = (window_lows[mae_idx] - scan_close) / scan_close
            result[f"mfe_{suffix}"] = round(float(mfe), 5)
            result[f"mae_{suffix}"] = round(float(mae), 5)
            if suffix == "20d":
                result["mfe_20d_date"] = str(fwd_df.index[mfe_idx])[:10]
                result["mae_20d_date"] = str(fwd_df.index[mae_idx])[:10]
            if risk_pct and risk_pct > 0:
                result[f"r_multiple_{suffix}"] = round(float(mfe / risk_pct), 3)

    # Trigger check + volume confirmation on the trigger bar
    if trigger_price and trigger_price > 0:
        triggered = False
        trigger_date = None
        trigger_idx = -1
        for i in range(len(highs)):
            if highs[i] >= trigger_price:
                triggered = True
                trigger_date = str(fwd_df.index[i])[:10]
                trigger_idx = i
                break
        result["triggered"] = 1 if triggered else 0
        result["trigger_date"] = trigger_date

        if (triggered and trigger_idx >= 0 and volumes is not None
                and vol_50_at_scan and vol_50_at_scan > 0):
            v = float(volumes[trigger_idx])
            result["trigger_volume_ratio"] = round(v / vol_50_at_scan, 3)

    return result


def update_forward_returns(min_age_days: int = 5, force: bool = False) -> int:
    """Update forward returns for all archived setups old enough.

    Args:
        min_age_days: Only update setups at least this many calendar days old.
        force: If True, re-compute even for setups that already have returns.

    Returns:
        Number of setups updated.
    """
    from sqlalchemy.orm import sessionmaker

    from archive_models import SetupArchive
    from database import make_sqlite_engine

    db_path = os.path.join(_BACKEND_DIR, "trading_journal.db")
    engine = make_sqlite_engine(db_path)
    SetupArchive.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine, autoflush=False)
    session = Session()

    # Find setups needing updates
    cutoff = (datetime.today() - timedelta(days=min_age_days)).strftime("%Y-%m-%d")
    query = session.query(SetupArchive).filter(SetupArchive.scan_date <= cutoff)
    if not force:
        # Update rows that are either missing the 1d return (never computed)
        # OR missing r_multiple_20d (existing rows from before the new
        # columns were added — backfill on the next run).
        from sqlalchemy import or_
        query = query.filter(
            or_(
                SetupArchive.fwd_return_1d.is_(None),
                SetupArchive.r_multiple_20d.is_(None),
            )
        )

    setups = query.all()
    if not setups:
        log.info("No setups need forward return updates.")
        session.close()
        return 0

    log.info(f"Updating forward returns for {len(setups)} setups...")

    # Group by ticker to batch-download
    ticker_setups: dict[str, list] = {}
    for s in setups:
        ticker_setups.setdefault(s.ticker, []).append(s)

    # Find the date range we need
    all_tickers = list(ticker_setups.keys())
    earliest = min(s.scan_date for s in setups)
    start = pd.Timestamp(earliest)
    end = pd.Timestamp.now() + pd.Timedelta(days=2)

    log.info(f"Downloading data for {len(all_tickers)} tickers from {start.date()} to {end.date()}...")
    raw = yf.download(
        all_tickers,
        start=start.strftime("%Y-%m-%d"),
        end=end.strftime("%Y-%m-%d"),
        group_by="ticker",
        threads=True,
        progress=False,
    )

    updated = 0
    for ticker, setup_list in ticker_setups.items():
        try:
            if len(all_tickers) == 1:
                df = raw.dropna()
            else:
                df = raw[ticker].dropna()
        except (KeyError, AttributeError):
            log.warning(f"  No data for {ticker}, skipping.")
            continue

        if df.empty:
            continue

        for setup in setup_list:
            scan_ts = pd.Timestamp(setup.scan_date)

            # Get the close on scan_date
            mask_on = df.index <= scan_ts
            if not mask_on.any():
                continue
            scan_idx = df.index[mask_on][-1]

            scan_close_series = df.loc[scan_idx, "Close"]
            if hasattr(scan_close_series, "iloc"):
                scan_close = float(scan_close_series.iloc[0])
            else:
                scan_close = float(scan_close_series)

            # Forward data: everything AFTER the scan date
            fwd_df = df[df.index > scan_ts]
            if fwd_df.empty:
                continue

            # Vol_50 at the scan bar — used for trigger-day volume ratio.
            hist_df = df[df.index <= scan_ts]
            vol_50_at_scan = None
            if "Volume" in hist_df.columns and len(hist_df) >= 50:
                vol_series = hist_df["Volume"]
                if hasattr(vol_series, "columns"):
                    vol_series = vol_series.iloc[:, 0]
                vol_50_at_scan = float(vol_series.tail(50).mean())

            returns = _compute_returns(
                fwd_df, scan_close, setup.trigger_price,
                s_level=setup.s_level, vol_50_at_scan=vol_50_at_scan,
            )
            if not returns:
                continue

            for key, val in returns.items():
                setattr(setup, key, val)
            updated += 1

    session.commit()
    session.close()
    log.info(f"Updated forward returns for {updated} setups.")
    return updated


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Update forward returns for archived setups")
    parser.add_argument("--min-age", type=int, default=5, help="Min calendar days since scan_date")
    parser.add_argument("--force", action="store_true", help="Re-compute even if already populated")
    args = parser.parse_args()

    update_forward_returns(min_age_days=args.min_age, force=args.force)
