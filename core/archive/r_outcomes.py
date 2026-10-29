"""The archive scored in R by the operator's rolling LPS rule (his words, Sat 24/10/2026).

The percent ruler (``mfe_20d``, P(+25%)) scores the stock's volatility: a quiet name never
reaches +25% in 20 trading days, so quiet setups read as losers. Measured 2026-10-24 on
6,046 episodes, quiet names reach 2R as often as wild ones. This module stores the same
measure per archived row, beside the percent columns, never instead of them.

His rule, implemented exactly (the study ``r_scale_v3.py`` validated against his reading):

* From the fire night walk forward one trading day at a time while the Low holds. The Low
  is the LPS low: the lowest low the LPS has printed so far. At the fire night it is the
  lowest low of the reader's LPS through the fire day (the LPS's first day found by the
  reader's own receding-run rule above the day the archived trigger names, capped at 5
  days; the fire day's own run when no high matches the trigger).
* Each day, yesterday is the last LPS day so far: its high is today's trigger, one cent
  under its low is today's stop. The day that takes out yesterday's high is the BUY DAY
  (entry = that high + one cent, or the open on a gap above it). A day that stays under
  yesterday's high while the Low holds makes the LPS one day longer.
* A close under the Low before any trigger = the LPS FAILED. Nothing within 10 trading
  days = NEVER TRIGGERED. 1R = entry minus stop.
* A fire day whose own high already took out the day before's high (the screener fired on
  a breakout day) is bought at the next open only if that open sits at or under the fire
  day's high (the stop a cent under the day before the fire day's low); otherwise FIRED
  LATE, counted apart.
* After a fail, follow 15 trading days for a close back above the Low: the reclaim day
  (his "last supper" is the undercut). The rule runs again from the reclaim day, the Low
  reset to the reclaim day's low, for a SECOND TRADE scored like the first.

Scoring per bought trade, on 20 and 60 trading days from the buy day (day 1): MFE in R;
the outcome in R, -1R when the stop is hit before the window's high; the best R made before
the stop (P(>=kR) reads this column, so a gain made after the stop never counts); the raw
gain from the entry beside it; the mechanical trade's R (-1R on any stop in the window, else
the close of the window). All of it stored as nullable columns on ``setup_archive``; a row
without bars in the price cache stays NULL, never an error.

Price history comes from the parquet cache, not a download: the walk needs the bars BEFORE
the fire day too, and the cache is the as-traded panel the reader itself read.

Run manually (idempotent; ``--force`` recomputes every row):
    python -m core.archive.r_outcomes [--force] [--cache PATH]
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

from core.archive.db_path import archive_db_path  # noqa: E402

log = logging.getLogger("chrollo.r_outcomes")

CENT = 0.01
#: Trading days from the fire night (or the reclaim day) within which the trigger must come.
TRIGGER_DAYS = 10
#: Trading days a failed LPS is followed for a close back above the Low.
SUPPER_DAYS = 15
WINDOWS = (20, 60)
#: The reader's cap on the LPS window, in trading days (two_eyes_numbers.LPS_MAX_BARS).
LPS_MAX_DAYS = 5
#: How far back the nightly pass re-measures (the 60-day window plus the second trade).
MAX_SCAN_AGE_DAYS = 200

STATUS_BOUGHT = "bought"
STATUS_FAILED = "failed"
STATUS_FIRED_LATE = "fired late"
STATUS_NEVER = "never triggered"
STATUS_OPEN = "open"            # the walk is not over yet; never stored

SUPPER_LAST = "last supper"
SUPPER_TRUE_FAILURE = "true failure"
SUPPER_OPEN = "open"

_TRADE_FACTS = ("mfe", "outcome", "stop_first", "best_before_stop", "gain", "exit")


def trade_columns(prefix: str, with_gain: bool = True) -> list[str]:
    """The per-window columns one trade writes (``r_mfe_20d`` ...)."""
    facts = _TRADE_FACTS if with_gain else tuple(f for f in _TRADE_FACTS if f != "gain")
    return [f"{prefix}_{fact}_{n}d" for n in WINDOWS for fact in facts]


#: Every column this module writes, in the order the model declares them. A row is
#: reset to None on each of them before a measure, so a re-measure never leaves a
#: stale fact behind.
R_COLUMNS = (
    ["r_status", "r_lps_first_day", "r_low_at_fire", "r_buy_date", "r_days_to_buy",
     "r_entry", "r_stop", "r_risk_pct", "r_gap_open"]
    + trade_columns("r")
    + ["r_fail_date", "r_supper", "r_reclaim_date",
       "r2_status", "r2_buy_date", "r2_entry", "r2_stop", "r2_risk_pct"]
    + trade_columns("r2", with_gain=False)
    + ["r_measured_through"]
)


# ───────────────────────────────────────────────────────────────── the LPS at the fire
def recedes(h, l, bar: int) -> bool:
    """A receding day: a lower high or a lower low than the day before."""
    return bar >= 1 and bool(h[bar] < h[bar - 1] or l[bar] < l[bar - 1])


def run_top(h, l, end: int) -> int:
    """The day before the run of receding days that ends on ``end``."""
    bar = int(end)
    while recedes(h, l, bar):
        bar -= 1
    return bar


def window_top(h, l, end: int) -> int:
    """The run's top, or the highest day inside the last ``LPS_MAX_DAYS`` when the run is longer."""
    top = run_top(h, l, end)
    if end - top + 1 <= LPS_MAX_DAYS:
        return top
    return max(range(end - LPS_MAX_DAYS + 1, end), key=lambda b: (h[b], b))


def lps_first_day(h, l, fire: int, trigger: float) -> int:
    """The LPS's first day: the receding run above the day the archived trigger names
    (within 7 days, 0.3%), capped; else the run ending on the fire day (the fire day alone
    when it did not recede)."""
    for b in range(fire, max(fire - 7, 0), -1):
        if np.isfinite(h[b]) and abs(h[b] - trigger) <= 0.003 * trigger:
            return min(window_top(h, l, b) + 1, b)
    if not recedes(h, l, fire):
        return fire
    return window_top(h, l, fire) + 1


# ───────────────────────────────────────────────────────────────── the rolling rule
def walk(o, h, l, c, start: int, low0: float, horizon: int, last_bar: int):
    """The rolling rule from the night of ``start``.

    Returns ``(status, day, entry, stop, low)``: ``bought`` with the buy day, its entry and
    stop; ``failed`` with the day that closed under the Low; ``never triggered``; or
    ``open`` when the bars run out before the rule decided.
    """
    low = float(low0)
    for d in range(start + 1, start + horizon + 1):
        if d > last_bar:
            return STATUS_OPEN, None, None, None, low
        trigger, stop = h[d - 1], l[d - 1] - CENT
        if not (np.isfinite(h[d]) and np.isfinite(c[d]) and np.isfinite(trigger)):
            return STATUS_OPEN, None, None, None, low
        if h[d] > trigger:
            entry = max(trigger + CENT, float(o[d])) if np.isfinite(o[d]) else trigger + CENT
            return STATUS_BOUGHT, d, float(entry), float(stop), low
        if c[d] < low:
            return STATUS_FAILED, d, None, None, low
        low = min(low, float(l[d]))
    return STATUS_NEVER, None, None, None, low


def score_trade(h, l, c, buy: int, entry: float, stop: float, last_bar: int,
                prefix: str = "r", with_gain: bool = True) -> dict:
    """One bought trade on each window from the buy day (day 1). A window that has not
    matured writes nothing for itself."""
    risk = entry - stop
    out = {f"{prefix}_risk_pct": risk / entry}
    for n in WINDOWS:
        end = buy + n - 1
        if end > last_bar:
            continue
        wh, wl, wc = h[buy:end + 1], l[buy:end + 1], c[buy:end + 1]
        if not np.isfinite(wh).any():
            continue
        mfe_bar = int(np.nanargmax(wh))
        mfe_r = float((wh[mfe_bar] - entry) / risk)
        under = np.where(wl <= stop)[0]
        stop_bar = int(under[0]) if under.size else None
        # The stop and the window's high on ONE bar: the bar does not say which printed first, so the stop
        # counts first (the gain before the stop is read off the bars before it, as `best_before_stop` and
        # `exit` already do; review 2026-10-29).
        stop_first = stop_bar is not None and stop_bar <= mfe_bar
        if stop_bar is None:
            best_before_stop = mfe_r
        elif stop_bar == 0:
            best_before_stop = -1.0        # stopped on the buy day: nothing was made first
        else:
            best_before_stop = float((np.nanmax(wh[:stop_bar]) - entry) / risk)
        out[f"{prefix}_mfe_{n}d"] = mfe_r
        out[f"{prefix}_outcome_{n}d"] = -1.0 if stop_first else mfe_r
        out[f"{prefix}_stop_first_{n}d"] = int(stop_first)
        out[f"{prefix}_best_before_stop_{n}d"] = best_before_stop
        if with_gain:
            out[f"{prefix}_gain_{n}d"] = float((wh[mfe_bar] - entry) / entry)
        close_r = float((wc[-1] - entry) / risk) if np.isfinite(wc[-1]) else None
        out[f"{prefix}_exit_{n}d"] = -1.0 if stop_bar is not None else close_r
    return out


def _day(dates, i) -> str:
    return str(dates[i])[:10]


def score_episode(o, h, l, c, dates, fire: int, trigger: float) -> dict:
    """Every R fact for one archived row, one key per column in ``R_COLUMNS`` (None where
    the fact does not apply). Returns ``{}`` when the fire day has no close or the row
    names no trigger; the status stays None while the walk is not over."""
    last_bar = len(dates) - 1
    if fire < 1 or not np.isfinite(c[fire]):
        return {}
    if not (trigger and np.isfinite(trigger) and trigger > 0):
        return {}
    first = lps_first_day(h, l, fire, float(trigger))
    lows = l[first:fire + 1]
    if not np.isfinite(lows).any():
        return {}
    low0 = float(np.nanmin(lows))
    out = dict.fromkeys(R_COLUMNS)
    out.update({"r_lps_first_day": _day(dates, first), "r_low_at_fire": low0,
                "r_measured_through": _day(dates, last_bar)})

    # the fire day as a breakout day: bought at the next open, or fired late
    if np.isfinite(h[fire - 1]) and h[fire] > h[fire - 1]:
        nxt = fire + 1
        if nxt > last_bar:
            return out
        if np.isfinite(o[nxt]) and o[nxt] <= h[fire] and o[nxt] > l[fire - 1] - CENT:
            entry, stop = float(o[nxt]), float(l[fire - 1]) - CENT
            out.update({"r_status": STATUS_BOUGHT, "r_buy_date": _day(dates, nxt), "r_days_to_buy": 1,
                        "r_gap_open": 1, "r_entry": entry, "r_stop": stop})
            out.update(score_trade(h, l, c, nxt, entry, stop, last_bar))
        else:
            out["r_status"] = STATUS_FIRED_LATE
        return out

    status, d, entry, stop, low = walk(o, h, l, c, fire, low0, TRIGGER_DAYS, last_bar)
    if status == STATUS_OPEN:
        return out
    out["r_status"] = status
    if status == STATUS_BOUGHT:
        out.update({"r_buy_date": _day(dates, d), "r_days_to_buy": d - fire,
                    "r_gap_open": int(np.isfinite(o[d]) and o[d] > h[d - 1] + CENT),
                    "r_entry": entry, "r_stop": stop})
        out.update(score_trade(h, l, c, d, entry, stop, last_bar))
        return out
    if status != STATUS_FAILED:
        return out

    out["r_fail_date"] = _day(dates, d)
    reclaim = None
    for r in range(d + 1, min(d + SUPPER_DAYS, last_bar) + 1):
        if np.isfinite(c[r]) and c[r] > low:
            reclaim = r
            break
    if reclaim is None:
        out["r_supper"] = SUPPER_TRUE_FAILURE if d + SUPPER_DAYS <= last_bar else SUPPER_OPEN
        return out
    out.update({"r_supper": SUPPER_LAST, "r_reclaim_date": _day(dates, reclaim)})
    status2, d2, entry2, stop2, _ = walk(o, h, l, c, reclaim, float(l[reclaim]), TRIGGER_DAYS, last_bar)
    if status2 == STATUS_OPEN:
        return out
    out["r2_status"] = status2
    if status2 == STATUS_BOUGHT:
        out.update({"r2_buy_date": _day(dates, d2), "r2_entry": entry2, "r2_stop": stop2})
        out.update(score_trade(h, l, c, d2, entry2, stop2, last_bar, prefix="r2", with_gain=False))
    return out


# ───────────────────────────────────────────────────────────────── the bars
_FIELDS = ("Open", "High", "Low", "Close")


def default_cache_path() -> str:
    """The US-stocks price cache the screener reads and rewrites nightly."""
    from core.pipeline.universe.descriptor import default_universe
    return default_universe().cache_paths()[0]


def load_cache_bars(tickers, cache_path: str | None = None):
    """``({ticker: ndarray[n_days, 4] of O/H/L/C}, DatetimeIndex)`` from the parquet cache,
    for the tickers the cache holds. A ticker it lacks is simply absent."""
    import pyarrow.parquet as pq

    path = cache_path or default_cache_path()
    names = set(pq.ParquetFile(path).schema_arrow.names)
    columns, have = [], []
    for t in sorted(set(tickers)):
        keys = [f"('{t}', '{f}')" for f in _FIELDS]
        if all(k in names for k in keys):
            columns += keys
            have.append(t)
    if not have:
        return {}, pd.read_parquet(path, columns=[]).index
    wide = pd.read_parquet(path, columns=columns)
    bars = {}
    for t in have:
        if isinstance(wide.columns, pd.MultiIndex):
            frame = wide[t][list(_FIELDS)]
        else:
            frame = wide[[f"('{t}', '{f}')" for f in _FIELDS]]
        bars[t] = frame.to_numpy(dtype=float)
    return bars, wide.index


def fire_day(dates, scan_date: str):
    """The last cache day on or before the scan date, or None when the cache starts later."""
    pos = int(dates.searchsorted(pd.Timestamp(scan_date), side="right")) - 1
    return pos if pos >= 0 else None


def measure_row(setup, bars: dict, dates) -> bool:
    """Write this module's columns on one ORM row from the bars. Returns whether the row
    had bars to measure; a row without them is left exactly as it was."""
    arr = bars.get(setup.ticker)
    if arr is None or len(dates) == 0:
        return False
    fire = fire_day(dates, setup.scan_date)
    if fire is None:
        return False
    o, h, l, c = arr.T
    facts = score_episode(o, h, l, c, dates, fire, setup.trigger_price)
    for column in R_COLUMNS:
        setattr(setup, column, facts.get(column))
    return True


def update_r_outcomes(force: bool = False, cache_path: str | None = None,
                      max_scan_age_days: int = MAX_SCAN_AGE_DAYS) -> int:
    """Measure every archived row by the rolling rule and store the result.

    Idempotent: the walk is recomputed from the cache each run and written in full, so a
    second run writes the same values. Without ``force`` only rows scanned within
    ``max_scan_age_days`` are re-measured (their windows, or their second trade, may still
    be maturing); ``force`` re-measures the whole archive. Returns rows measured.
    """
    from sqlalchemy.orm import sessionmaker

    from archive_models import SetupArchive
    from core.archive.forward_returns import _ensure_model_columns
    from database import make_sqlite_engine

    engine = make_sqlite_engine(archive_db_path())
    SetupArchive.metadata.create_all(bind=engine)
    _ensure_model_columns(engine)
    session = sessionmaker(bind=engine, autoflush=False)()
    try:
        query = session.query(SetupArchive)
        if not force:
            oldest = (datetime.today() - timedelta(days=max_scan_age_days)).strftime("%Y-%m-%d")
            query = query.filter(SetupArchive.scan_date >= oldest)
        setups = query.all()
        if not setups:
            log.info("No archived rows to measure in R.")
            return 0
        bars, dates = load_cache_bars({s.ticker for s in setups}, cache_path)
        measured = sum(measure_row(s, bars, dates) for s in setups)
        session.commit()
    finally:
        session.close()
        engine.dispose()
    log.info("R outcomes: %d of %d rows measured (%d tickers in the cache).",
             measured, len(setups), len(bars))
    return measured


def run_r_maturation(force: bool = False) -> int:
    """The R pass as a CONTAINED passenger of the nightly maturation: it never owns the
    fires' run status. Returns rows measured, or -1 on a contained failure."""
    try:
        n = update_r_outcomes(force=force)
        print(f"R outcomes measured: {n} row(s).", flush=True)
        return n
    except Exception as exc:  # noqa: BLE001 — passenger isolation
        log.exception("R outcome pass failed (fires' run unaffected)")
        print(f"R outcome pass FAILED: {type(exc).__name__}: {exc}", flush=True)
        return -1


if __name__ == "__main__":
    import argparse

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    parser = argparse.ArgumentParser(description="Score the archive in R by the rolling LPS rule")
    parser.add_argument("--force", action="store_true", help="Re-measure every row, not only the recent ones")
    parser.add_argument("--cache", default=None, help="Price cache parquet (default: the US-stocks cache)")
    args = parser.parse_args()
    print(f"Measured {update_r_outcomes(force=args.force, cache_path=args.cache)} row(s).")
