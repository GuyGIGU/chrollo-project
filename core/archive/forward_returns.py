"""
Forward return updater — backfills forward returns, MFE/MAE, and trigger status
for archived setups that are old enough to have outcome data.

Run manually:
    python -m core.archive.forward_returns

Or schedule via Windows Task Scheduler for nightly updates.
"""
from __future__ import annotations

import logging
import os
import sys
from datetime import datetime, timedelta

import numpy as np
import pandas as pd

_PROJECT_ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

_BACKEND_DIR = os.path.join(_PROJECT_ROOT, "webapp", "backend")
if _BACKEND_DIR not in sys.path:
    sys.path.append(_BACKEND_DIR)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("chrollo.fwd_returns")


def _ticker_frame(raw: pd.DataFrame, ticker: str) -> pd.DataFrame:
    if raw is None or raw.empty:
        return pd.DataFrame()
    if isinstance(raw.columns, pd.MultiIndex):
        try:
            return raw[ticker].dropna()
        except KeyError:
            return pd.DataFrame()
    return raw.dropna()


# ── Outcome math — single source of truth ────────────────────────────────────
# The triple-barrier labelling, the elapsed-window edge metric, and the geometry
# constants all live in core.archive.outcomes so the column we STORE and the edge
# the harness REPORTS are computed in exactly one place (no divergent
# re-derivation). compute_barrier_events is re-exported here for back-compat with
# any caller / test that imported it from this module.
from core.archive.outcomes import (  # noqa: E402
    HORIZON_BARS as FORWARD_RETURN_HORIZON_BARS,
    STOP_TOLERANCE,
    TARGET_PCT,
    TARGET_R_MULTIPLE,
    compute_barrier_events,
    compute_elapsed_outcome,
    window_return,
)

BARRIER_HORIZON_DAYS = FORWARD_RETURN_HORIZON_BARS
FORWARD_RETURN_DOWNLOAD_DAYS = 120  # calendar buffer to capture 60 market sessions
FORWARD_RETURN_MAX_SCAN_AGE_DAYS = FORWARD_RETURN_DOWNLOAD_DAYS

# SPY is fetched in the same batch as the setups so abnormal_ret_to_date (the bias
# control on the elapsed-window return) can be computed offline against the same
# forward window. Kept as a module constant so a test can monkeypatch the symbol.
SPY_TICKER = "SPY"


def _cap_forward_window(fwd_df: pd.DataFrame) -> pd.DataFrame:
    """Keep outcome math inside the archive's fixed 60-bar forward window."""
    if fwd_df is None or fwd_df.empty:
        return fwd_df
    return fwd_df.iloc[:FORWARD_RETURN_HORIZON_BARS]


def _spy_window_return(
    spy_df: pd.DataFrame, scan_ts: pd.Timestamp, n_bars: int
) -> float | None:
    """SPY's close-to-close return over the SAME ``n_bars`` forward window.

    Anchored to SPY's close on/at the scan bar and measured to SPY's close on the
    setup's last available forward bar, so the abnormal return subtracts a
    market move over an identical elapsed horizon. Returns ``None`` when SPY data
    is missing or the scan bar can't be located (-> abnormal_ret_to_date None).
    """
    if spy_df is None or getattr(spy_df, "empty", True) or n_bars <= 0:
        return None
    on = spy_df.index <= scan_ts
    if not on.any():
        return None
    spy_close = spy_df["Close"]
    if hasattr(spy_close, "columns"):
        spy_close = spy_close.iloc[:, 0]
    base = float(spy_close.loc[spy_df.index[on][-1]])
    fwd = spy_close[spy_df.index > scan_ts]
    if fwd.empty:
        return None
    return window_return(fwd.values.astype(float).tolist(), base, bars=n_bars)


def _compute_returns(
    fwd_df: pd.DataFrame,
    scan_close: float,
    trigger_price: float | None,
    direction: str = "long",
    s_level: float | None = None,
    vol_50_at_scan: float | None = None,
    spy_window_return: float | None = None,
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
        spy_window_return: SPY's close-to-close return over the SAME elapsed
            forward window — subtracted from ``ret_to_date`` to give
            ``abnormal_ret_to_date`` (the bias control). ``None`` -> abnormal None.

    Returns:
        Dict of return fields ready to write to the archive. Always includes the
        ELAPSED-WINDOW outcome (mfe_to_date / mae_to_date / ret_to_date /
        bars_to_date / abnormal_ret_to_date) computed over however many forward
        bars exist — never gated on a full 20/60 window.
    """
    fwd_df = _cap_forward_window(fwd_df)
    if fwd_df is None or fwd_df.empty or scan_close <= 0:
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
        if triggered and trigger_idx >= 0:
            result["days_to_trigger"] = trigger_idx + 1  # 1-based bar count

        if (triggered and trigger_idx >= 0 and volumes is not None
                and vol_50_at_scan and vol_50_at_scan > 0):
            v = float(volumes[trigger_idx])
            result["trigger_volume_ratio"] = round(v / vol_50_at_scan, 3)

    # Triple-barrier outcome label (path events + derived win/loss/timeout),
    # anchored to the scan close so it shares the existing MFE/MAE/R frame.
    barrier = compute_barrier_events(highs, lows, scan_close, s_level)
    if len(highs) < FORWARD_RETURN_HORIZON_BARS and barrier.get("barrier_label") == "timeout":
        barrier["barrier_label"] = None
    result.update(barrier)

    # Elapsed-window outcome — the window-agnostic edge metric. Measured over
    # however many forward bars exist (capped at the 60-bar horizon), recomputed
    # every run as the window grows. NEVER gated on a full fixed window, so the
    # backtest report reads an edge today instead of waiting months. Same single
    # source of truth (core.archive.outcomes) the harness reads, so the stored
    # column and the reported edge can never diverge.
    result.update(compute_elapsed_outcome(
        highs, lows, closes, scan_close, spy_window_return=spy_window_return,
    ))

    return result


# Outcome columns added after the initial schema. create_all() only creates
# missing TABLES, not missing COLUMNS on an existing table, so we ALTER them in
# on demand (idempotent — a duplicate-column error means it already exists).
_OUTCOME_COLUMNS: dict[str, str] = {
    "days_to_trigger": "INTEGER",
    "days_to_2_5r":    "INTEGER",
    "days_to_15pct":   "INTEGER",
    "days_to_stop":    "INTEGER",
    "barrier_label":   "TEXT",
    "win_barrier":     "TEXT",
    # Elapsed-window outcome (window-agnostic edge metric). Nullable; the daily
    # job recomputes them every run as the forward window grows.
    "mfe_to_date":          "REAL",
    "mae_to_date":          "REAL",
    "ret_to_date":          "REAL",
    "bars_to_date":         "INTEGER",
    "abnormal_ret_to_date": "REAL",
}


def _ensure_outcome_columns(engine) -> None:
    """Add post-schema outcome columns to setup_archive if they don't exist yet."""
    from sqlalchemy import inspect, text

    inspector = inspect(engine)
    if "setup_archive" not in inspector.get_table_names():
        return  # create_all will handle a fresh table
    existing = {col["name"] for col in inspector.get_columns("setup_archive")}
    with engine.begin() as conn:
        for name, sql_type in _OUTCOME_COLUMNS.items():
            if name not in existing:
                conn.execute(text(f"ALTER TABLE setup_archive ADD COLUMN {name} {sql_type}"))


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
    _ensure_outcome_columns(engine)
    Session = sessionmaker(bind=engine, autoflush=False)
    session = Session()

    # Find setups needing updates
    cutoff = (datetime.today() - timedelta(days=min_age_days)).strftime("%Y-%m-%d")
    query = session.query(SetupArchive).filter(SetupArchive.scan_date <= cutoff)
    if not force:
        oldest_cutoff = (
            datetime.today() - timedelta(days=FORWARD_RETURN_MAX_SCAN_AGE_DAYS)
        ).strftime("%Y-%m-%d")
        query = query.filter(SetupArchive.scan_date >= oldest_cutoff)
        # Update rows that are still maturing through the 60-bar window. A row is
        # re-touched while ANY fixed-window field is still null OR its elapsed
        # window can still grow (bars_to_date is null or < the 60-bar horizon), so
        # the window-agnostic edge metric recomputes every run as the bars
        # accumulate. The scan_date >= oldest_cutoff bound above caps re-touching:
        # once a row ages past the download window it drops out regardless, so
        # this never re-downloads the whole archive forever.
        from sqlalchemy import or_
        query = query.filter(
            or_(
                SetupArchive.fwd_return_1d.is_(None),
                SetupArchive.fwd_return_5d.is_(None),
                SetupArchive.fwd_return_10d.is_(None),
                SetupArchive.fwd_return_20d.is_(None),
                SetupArchive.fwd_return_60d.is_(None),
                SetupArchive.r_multiple_20d.is_(None),
                SetupArchive.r_multiple_60d.is_(None),
                SetupArchive.barrier_label.is_(None),
                SetupArchive.bars_to_date.is_(None),
                SetupArchive.bars_to_date < FORWARD_RETURN_HORIZON_BARS,
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
    latest_needed = max(
        pd.Timestamp(s.scan_date) + pd.Timedelta(days=FORWARD_RETURN_DOWNLOAD_DAYS)
        for s in setups
    )
    end = min(pd.Timestamp.now() + pd.Timedelta(days=2), latest_needed)

    start_str = start.strftime("%Y-%m-%d")
    end_str = end.strftime("%Y-%m-%d")
    # SPY rides in the same batch so abnormal_ret_to_date (the bias control on the
    # elapsed return) is computed against the SAME forward window, offline, with no
    # extra fetch. De-duped so a setup ON SPY itself doesn't double-list it.
    download_tickers = list(dict.fromkeys([*all_tickers, SPY_TICKER]))
    log.info(f"Downloading data for {len(all_tickers)} tickers (+SPY) from {start.date()} to {end.date()}...")
    from core.pipeline.downloads import _batched_download
    raw = _batched_download(
        download_tickers,
        {"start": start_str, "end": end_str, "auto_adjust": True},
        "Forward returns",
    )

    # SPY forward frame, sliced per setup to the setup's elapsed window. If SPY
    # didn't come back, abnormal_ret_to_date stays None (never a crash).
    try:
        spy_df = _ticker_frame(raw, SPY_TICKER)
    except (KeyError, AttributeError):
        spy_df = pd.DataFrame()

    updated = 0
    for ticker, setup_list in ticker_setups.items():
        try:
            df = _ticker_frame(raw, ticker)
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

            # SPY's return over the SAME elapsed forward window (capped at 60
            # bars to match the setup's window) — the abnormal-return baseline.
            n_fwd_bars = min(len(_cap_forward_window(fwd_df)), FORWARD_RETURN_HORIZON_BARS)
            spy_window_return = _spy_window_return(spy_df, scan_ts, n_fwd_bars)

            returns = _compute_returns(
                fwd_df, scan_close, setup.trigger_price,
                s_level=setup.s_level, vol_50_at_scan=vol_50_at_scan,
                spy_window_return=spy_window_return,
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
