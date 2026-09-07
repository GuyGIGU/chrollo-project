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
# Re-touch stragglers well past the 60-bar (~87 calendar day) fill point so a
# maturation gap (e.g. backend downtime) can't permanently abandon a row's
# fixed-window columns (fwd_return_60d / r_multiple_60d / mfe_60d) before they
# fill. Decoupled from — and wider than — the per-setup download buffer above; the
# re-touch predicate below only re-selects rows still missing a window, so
# fully-matured rows are never re-downloaded regardless of this cap. The cap only
# bounds re-download of rows that will never fill (dead / delisted tickers).
FORWARD_RETURN_MAX_SCAN_AGE_DAYS = 200

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
    spy_df: pd.DataFrame, scan_ts: pd.Timestamp, fwd_end_ts: pd.Timestamp | None
) -> float | None:
    """SPY's close-to-close return over the setup's SAME CALENDAR forward window.

    Anchored to SPY's close on/at the scan bar and measured to SPY's last close
    on or before ``fwd_end_ts`` (the setup's last available forward bar), so the
    abnormal return subtracts a market move over the IDENTICAL elapsed calendar
    horizon. Aligning by DATE — not by SPY's first-N-bars-by-position — is what
    keeps the baseline correct when the setup ticker dropped sessions (halt /
    thin / late listing) and so has fewer forward bars than SPY over the same
    span. Returns ``None`` when SPY data is missing or an endpoint can't be
    located (-> abnormal_ret_to_date None).
    """
    if spy_df is None or getattr(spy_df, "empty", True) or fwd_end_ts is None:
        return None
    on = spy_df.index <= scan_ts
    if not on.any():
        return None
    spy_close = spy_df["Close"]
    if hasattr(spy_close, "columns"):
        spy_close = spy_close.iloc[:, 0]
    base = float(spy_close.loc[spy_df.index[on][-1]])
    fwd = spy_close[(spy_df.index > scan_ts) & (spy_df.index <= fwd_end_ts)]
    if fwd.empty:
        return None
    return window_return(fwd.values.astype(float).tolist(), base)


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
        # All four trigger columns state one fact — write them in every branch
        # (None on the negative side) so a 1->0 recompute can't leave stale
        # days_to_trigger / trigger_volume_ratio behind (EC-23).
        result["triggered"] = 1 if triggered else 0
        result["trigger_date"] = trigger_date
        result["days_to_trigger"] = (
            trigger_idx + 1 if triggered and trigger_idx >= 0 else None  # 1-based bar count
        )
        result["trigger_volume_ratio"] = None
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


def _price_scale_factor(fresh_scan_close: float, stored_scan_close) -> float | None:
    """Factor mapping stored scan-time absolutes onto the downloaded price scale.

    THREE outcomes, because "I cannot explain this factor" is not "there was no
    adjustment":
      ``1.0``  the scales agree — same regime, no post-scan adjustment (also the
               answer when there is no stored close to compare against, which
               leaves the absolutes exactly as archived).
      ``f``    a usable factor; the absolutes rescale by it.
      ``None`` UNKNOWN. The implied factor is outside the plausible band, so a
               10-for-1 split or the 1-for-10 reverse splits routine among the
               sub-$5 names this screener scans cannot be told apart from a bad
               stored close. Returning 1.0 here used to assert the two series
               were on the SAME scale, and the caller then graded `triggered`,
               `barrier_label`, `days_to_*` and the R-multiples against a trigger
               and a stop an order of magnitude wrong — entering the edge record
               as a clean never-triggered timeout. Callers must leave every
               trigger- and stop-dependent column NULL on this outcome; the ratio
               metrics use the fresh close and stay valid.
    Snaps float noise to exactly 1.0."""
    try:
        stored = float(stored_scan_close)
    except (TypeError, ValueError):
        return 1.0
    if not (stored > 0 and fresh_scan_close > 0):
        return 1.0
    factor = fresh_scan_close / stored
    if not (0.2 <= factor <= 5.0):
        return None
    if abs(factor - 1.0) < 1e-3:
        return 1.0
    return factor


def _rescaled(value, factor: float | None):
    """``value * factor`` tolerant of None/garbage (returns the input as-is).

    An UNKNOWN factor (``None``) returns None: an absolute that cannot be placed
    on the fresh price scale is not knowable, and must never be passed through
    as if it were."""
    if factor is None:
        return None
    if value is None or factor == 1.0:
        return value
    try:
        return float(value) * factor
    except (TypeError, ValueError):
        return value


# Every column derived from a stored ABSOLUTE (trigger_price / s_level). On an
# unknown price scale these are unknowable, so they are stamped NULL rather than
# left carrying a previous pass's wrongly-scaled verdict.
_SCALE_DEPENDENT_NULLS: dict = {
    "triggered": None, "trigger_date": None, "days_to_trigger": None,
    "trigger_volume_ratio": None,
    "r_multiple_20d": None, "r_multiple_60d": None,
    "days_to_2_5r": None, "days_to_15pct": None, "days_to_stop": None,
    "barrier_label": None, "win_barrier": None,
}


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


def _ensure_model_columns(engine) -> None:
    """Bring ``setup_archive`` up to the FULL ``SetupArchive`` model schema.

    The standalone job (``python -m core.archive.forward_returns``) queries the
    ENTIRE ORM model, but the prod DB only gets its NON-outcome columns ALTERed in
    on backend boot (``startup._apply_model_add_columns``). When the standalone job
    runs against a DB the backend has not yet migrated, ``session.query(
    SetupArchive)`` crashes with ``no such column: setup_archive.<col>`` (e.g.
    ``engine_config_version``, the ``fund_*`` / ``rs_*`` / ``sector_*`` columns).
    So the archive jobs must be SELF-SUFFICIENT, not rely on the backend booting.

    Model-derived and ADD-only (idempotent): diff ``SetupArchive.__table__.columns``
    against the live table via SQLAlchemy ``inspect`` (``PRAGMA table_info``) and
    ``ALTER TABLE ... ADD COLUMN`` for each column the model declares but the DB
    lacks (nullable; the auto-increment PK is never ADDed). The model is the single
    source of truth — no hardcoded column list — so a new column on SetupArchive
    flows in on the next run with no hand-written migration. Mirrors
    ``startup.model_add_column_migrations`` / ``writer._ensure_new_columns``'s
    model-derived pass. Imported lazily (the model lives under the backend dir,
    mind the config/cwd boot collision). Calls ``_ensure_outcome_columns`` first so
    the legacy explicit outcome SQL types are preserved.
    """
    from sqlalchemy import inspect, text

    from archive_models import SetupArchive

    _ensure_outcome_columns(engine)

    inspector = inspect(engine)
    if "setup_archive" not in inspector.get_table_names():
        return  # create_all will handle a fresh table
    existing = {col["name"] for col in inspector.get_columns("setup_archive")}
    with engine.begin() as conn:
        for column in SetupArchive.__table__.columns:
            if column.primary_key or column.name in existing:
                continue
            conn.execute(
                text(f"ALTER TABLE setup_archive ADD COLUMN {column.name} {column.type}")
            )
            existing.add(column.name)


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
    # Ensure the FULL model schema before querying — not just the outcome subset.
    # The query below reads the entire SetupArchive model, so a DB the backend has
    # not yet migrated (missing engine_config_version / fund_* / etc.) would crash.
    # _ensure_model_columns is model-derived + idempotent and calls
    # _ensure_outcome_columns internally, keeping this job self-sufficient.
    _ensure_model_columns(engine)
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
        # once a row ages past FORWARD_RETURN_MAX_SCAN_AGE_DAYS it drops out
        # regardless, so this never re-downloads the whole archive forever.
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
    # Pad the download start back a few calendar days so the trading close ON or
    # BEFORE a non-trading-day earliest scan_date (weekend / market holiday) is
    # always in-frame. yfinance's `start` is INCLUSIVE, so without this the first
    # returned bar for a non-trading earliest date lands AFTER scan_ts, mask_on is
    # all-False, and that earliest row's scan_close can never resolve — it is
    # skipped on every run until it ages out (silent single-cohort data loss).
    start = pd.Timestamp(earliest) - pd.Timedelta(days=5)
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
    from core.pipeline.downloads import _batched_download, price_auto_adjust
    raw = _batched_download(
        download_tickers,
        {"start": start_str, "end": end_str, "auto_adjust": price_auto_adjust()},
        "Forward returns",
    )

    # SPY forward frame, sliced per setup to the setup's elapsed window. If SPY
    # didn't come back, abnormal_ret_to_date stays None (never a crash).
    try:
        spy_df = _ticker_frame(raw, SPY_TICKER)
    except (KeyError, AttributeError):
        spy_df = pd.DataFrame()

    updated = 0
    unknown_scale = 0
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

            # Cross-regime/adjustment guard: trigger_price and s_level were
            # stored on the SCAN-TIME price scale; the freshly-downloaded series
            # can sit on another (pre-cutover dividend-adjusted rows read under
            # the as-traded regime, or any post-scan split). Recover the one-bar
            # factor from the same scan close we just re-read vs the stored one
            # and rescale the absolutes onto the downloaded scale. All ratio
            # metrics already use the downloaded scan_close, so they need no fix.
            scale = _price_scale_factor(scan_close, getattr(setup, "current_price", None))

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

            # SPY's return over the setup's SAME CALENDAR forward window — aligned
            # by DATE to the setup's last available forward bar (capped at 60), so
            # a halted/thin setup with fewer bars than SPY still subtracts the
            # market move over its own horizon. The abnormal-return baseline.
            capped_fwd = _cap_forward_window(fwd_df)
            fwd_end_ts = (capped_fwd.index[-1]
                          if capped_fwd is not None and not capped_fwd.empty else None)
            spy_window_return = _spy_window_return(spy_df, scan_ts, fwd_end_ts)

            returns = _compute_returns(
                fwd_df, scan_close, _rescaled(setup.trigger_price, scale),
                s_level=_rescaled(setup.s_level, scale), vol_50_at_scan=vol_50_at_scan,
                spy_window_return=spy_window_return,
            )
            if not returns:
                continue
            if scale is None:
                # The scale is unexplainable, so every verdict that reads a
                # stored absolute is unknowable — write NULL, never a guess.
                returns.update(_SCALE_DEPENDENT_NULLS)
                unknown_scale += 1

            for key, val in returns.items():
                setattr(setup, key, val)
            updated += 1

    session.commit()
    session.close()
    log.info(f"Updated forward returns for {updated} setups.")
    if unknown_scale:
        # Loud, because a recurring refusal means a whole cohort is ungraded.
        log.warning(f"  {unknown_scale} setup(s) had an unexplainable price scale "
                    "(stored vs downloaded scan close); their trigger-, stop- and "
                    "R-dependent columns were left NULL rather than graded wrong.")
    return updated


def run_near_miss_maturation(min_age_days: int = 5, force: bool = False) -> int:
    """The near-miss lane's maturation pass, CONTAINED: a telemetry passenger
    must never own the shared maturation run's status — the fires' record
    stays ok even when the lane's dead-ticker-heavy cohort hits a download
    pathology (review 2026-07-26 finding 6). Returns rows updated, or -1 on a
    contained failure (printed + logged, never raised)."""
    try:
        from core.archive.near_miss_outcomes import update_near_miss_outcomes
        n = update_near_miss_outcomes(min_age_days=min_age_days, force=force)
        print(f"Near-miss outcomes updated: {n} row(s).", flush=True)
        return n
    except Exception as exc:  # noqa: BLE001 — passenger isolation
        log.exception("near-miss maturation failed (fires' run unaffected)")
        print(f"Near-miss maturation FAILED: {type(exc).__name__}: {exc}",
              flush=True)
        return -1


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Update forward returns for archived setups")
    parser.add_argument("--min-age", type=int, default=5, help="Min calendar days since scan_date")
    parser.add_argument("--force", action="store_true", help="Re-compute even if already populated")
    args = parser.parse_args()

    # Record this standalone (OS-scheduled) run in scan_runs (kind='maturation')
    # so a backend-INDEPENDENT nightly task is just as visible to the watchdog /
    # health surface as the in-process path — the whole point of moving the tick
    # off the FastAPI lifecycle. Best-effort bookkeeping: if the backend status
    # helpers can't be imported/opened, still run the maturation (never let the
    # scan_runs record block the actual work).
    _status = None
    _run_id = None
    try:
        from services import scan_status as _status
        _run_id = _status.start_run("os_task", kind="maturation")
    except Exception:
        _status = None
        _run_id = None
    try:
        _updated = update_forward_returns(min_age_days=args.min_age, force=args.force)
        # The near-miss cohort matures inside the SAME registered run (lane
        # Task 10): one nightly maturation job, one watchdog surface. Its
        # count is printed, not folded into n_setups (fires stay fires) — and
        # the call is CONTAINED, so a lane-only failure can never mark the
        # fires' committed maturation "failed" (review finding 6).
        run_near_miss_maturation(min_age_days=args.min_age, force=args.force)
        if _status is not None and _run_id is not None:
            _status.finish_run(_run_id, status="ok", n_setups=_updated)
    except Exception as _exc:
        if _status is not None and _run_id is not None:
            _status.finish_run(_run_id, status="failed", error=str(_exc))
        raise
