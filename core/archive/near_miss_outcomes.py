"""Near-miss forward-outcome maturation (near-miss lane Task 10).

A second maturation pass over ``near_miss_archive`` that DELEGATES every
outcome number to ``core.archive.outcomes`` (one implementation — the
meaning of MFE can never fork between fires and near-misses) and REUSES
``forward_returns``' machinery: the two bounding devices verbatim (the
still-maturing re-touch predicate + the max-scan-age cutoff — a junk-heavy
cohort holds proportionally MORE dead tickers, so the age cap matters more
here, not less), the batched download, the SPY same-window baseline, and
the split-rescale guard (``would_be_trigger`` was stored on the scan-time
price scale; the freshly-downloaded series may sit on another).

The outcome clock anchors at FIRST refusal (``first_seen`` — the first-fire
analog for a non-fire cohort, per the Task-6 R-EPISODE ruling). Invoked by
``python -m core.archive.forward_returns`` inside the SAME scan_runs
maturation record, so the watchdog sees one nightly job, not two.
"""
from __future__ import annotations

import logging
import os
import sys
from datetime import datetime, timedelta

import pandas as pd

_PROJECT_ROOT = os.path.normpath(os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", ".."))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)
_BACKEND_DIR = os.path.join(_PROJECT_ROOT, "webapp", "backend")
if _BACKEND_DIR not in sys.path:
    sys.path.append(_BACKEND_DIR)

from core.archive.outcomes import HORIZON_BARS, compute_elapsed_outcome

log = logging.getLogger("chrollo.archive.near_miss")


def _col(frame: pd.DataFrame, name: str) -> pd.Series:
    col = frame[name]
    return col.iloc[:, 0] if hasattr(col, "columns") else col


def update_near_miss_outcomes(min_age_days: int = 5,
                              force: bool = False) -> int:
    """Fill/refresh the elapsed-window outcomes + the would-be trigger touch
    for every still-maturing cohort row. Returns rows updated."""
    from sqlalchemy import or_
    from sqlalchemy.orm import sessionmaker

    from archive_models import NearMissArchive
    from core.archive.forward_returns import (
        FORWARD_RETURN_DOWNLOAD_DAYS,
        FORWARD_RETURN_MAX_SCAN_AGE_DAYS,
        SPY_TICKER,
        _cap_forward_window,
        _price_scale_factor,
        _rescaled,
        _spy_window_return,
        _ticker_frame,
    )
    from core.archive.near_miss_writer import _ensure_table
    from database import make_sqlite_engine

    db_path = os.path.join(_BACKEND_DIR, "trading_journal.db")
    engine = make_sqlite_engine(db_path)
    _ensure_table(engine)
    Session = sessionmaker(bind=engine, autoflush=False)
    session = Session()

    cutoff = (datetime.today() - timedelta(days=min_age_days)).strftime("%Y-%m-%d")
    query = session.query(NearMissArchive).filter(
        NearMissArchive.first_seen <= cutoff)
    if not force:
        oldest_cutoff = (
            datetime.today() - timedelta(days=FORWARD_RETURN_MAX_SCAN_AGE_DAYS)
        ).strftime("%Y-%m-%d")
        query = query.filter(NearMissArchive.first_seen >= oldest_cutoff)
        query = query.filter(or_(
            NearMissArchive.bars_to_date.is_(None),
            NearMissArchive.bars_to_date < HORIZON_BARS,
        ))
    rows = query.all()
    if not rows:
        log.info("No near-miss rows need outcome updates.")
        session.close()
        return 0

    log.info("Updating near-miss outcomes for %d rows...", len(rows))
    by_ticker: dict[str, list] = {}
    for r in rows:
        by_ticker.setdefault(r.ticker, []).append(r)

    earliest = min(r.first_seen for r in rows)
    start = pd.Timestamp(earliest) - pd.Timedelta(days=5)
    latest_needed = max(
        pd.Timestamp(r.first_seen) + pd.Timedelta(days=FORWARD_RETURN_DOWNLOAD_DAYS)
        for r in rows)
    end = min(pd.Timestamp.now() + pd.Timedelta(days=2), latest_needed)

    from core.pipeline.downloads import _batched_download, price_auto_adjust
    raw = _batched_download(
        list(dict.fromkeys([*by_ticker, SPY_TICKER])),
        {"start": start.strftime("%Y-%m-%d"), "end": end.strftime("%Y-%m-%d"),
         "auto_adjust": price_auto_adjust()},
        "Near-miss outcomes",
    )
    try:
        spy_df = _ticker_frame(raw, SPY_TICKER)
    except (KeyError, AttributeError):
        spy_df = pd.DataFrame()

    updated = 0
    for ticker, ticker_rows in by_ticker.items():
        try:
            df = _ticker_frame(raw, ticker)
        except (KeyError, AttributeError):
            log.warning("  No data for %s, skipping.", ticker)
            continue
        if df.empty:
            continue
        for row in ticker_rows:
            scan_ts = pd.Timestamp(row.first_seen)
            mask_on = df.index <= scan_ts
            if not mask_on.any():
                continue
            close_cell = df.loc[df.index[mask_on][-1], "Close"]
            fresh_close = float(close_cell.iloc[0]
                                if hasattr(close_cell, "iloc") else close_cell)
            scale = _price_scale_factor(fresh_close, row.scan_close)

            fwd = df[df.index > scan_ts]
            if fwd.empty:
                continue
            capped = _cap_forward_window(fwd)
            fwd_end_ts = capped.index[-1] if capped is not None and not capped.empty else None
            spy_ret = _spy_window_return(spy_df, scan_ts, fwd_end_ts)

            highs = _col(fwd, "High").to_numpy(dtype=float)
            lows = _col(fwd, "Low").to_numpy(dtype=float)
            closes = _col(fwd, "Close").to_numpy(dtype=float)
            elapsed = compute_elapsed_outcome(
                highs, lows, closes, fresh_close, spy_window_return=spy_ret)
            for key, val in elapsed.items():
                setattr(row, key, val)

            trigger = _rescaled(row.would_be_trigger, scale)
            n = min(len(highs), HORIZON_BARS)
            hit = next((i for i in range(n) if highs[i] >= trigger), None) \
                if trigger is not None else None
            if hit is not None:
                row.triggered = 1
                row.trigger_date = str(fwd.index[hit])[:10]
            elif (elapsed.get("bars_to_date") or 0) >= HORIZON_BARS:
                row.triggered = 0
            updated += 1

    session.commit()
    session.close()
    log.info("Updated near-miss outcomes for %d rows.", updated)
    return updated
