"""The best gain after each save: the operator's sheet's "% Best Diff" columns
(his Watchlist reference, Fri 23/10/2026).

Read off his sheet, 210 of 210 values to the hundredth (the 35 of its names
the price cache holds, through Thu 22/10): the basis is the HIGH of the day
before the add, his buy-stop trigger, and the add day is the first trading day
after it. "Since add" is the best high from the add day to the last bar; "N
days" is the best high from the add day through N calendar days later, that day
included, so a young save's longer windows show its best so far.

In Chrollo the day before the add is the saved scan's own day: a star is a
click on that scan (basis_scan_date, which a typed-in ticker has too; the pin
on saves older than it). save_date is a UTC stamp that falls on the scan day
itself after a late-night review, so it is never the reference. A save with no
scan, or with no bar since its scan, is a null, never a substitute. A
measurement for display; nothing here judges a setup.
"""
from __future__ import annotations

WINDOW_DAYS = (60, 30, 14, 7, 2)
FIELDS = ("since_add", *(f"d{days}" for days in WINDOW_DAYS))


def best_gains(frame, scan_date: str | None) -> dict:
    """The six gains for one save over its cleaned daily frame (None where not measurable)."""
    import pandas as pd

    out = dict.fromkeys(FIELDS)
    if frame is None or not scan_date:
        return out
    highs = frame["High"].copy()
    highs.index = pd.to_datetime(highs.index)
    day = pd.Timestamp(scan_date)
    before, after = highs[highs.index <= day], highs[highs.index > day]
    if before.empty or after.empty:
        return out
    basis, add_day = float(before.iloc[-1]), after.index[0]
    out["since_add"] = _gain(after.max(), basis)
    for days in WINDOW_DAYS:
        out[f"d{days}"] = _gain(after[after.index <= add_day + pd.Timedelta(days=days)].max(), basis)
    return out


def _gain(high, basis: float) -> float:
    return round(float(high) / basis - 1, 6)


def price_facts(frame, scan_date: str | None, session_day: str) -> dict:
    """The facts the weekly list's live columns divide by (his second sheet):
    ``basis`` = the scan day's high (% Diff since add = last / basis - 1);
    ``prev_close`` = the close of the last bar before ``session_day``, the
    trading day the live quote belongs to (Change %); ``dist_52w_high`` =
    the engine's own 52-week measure at the last close (-0.07 = 7% below)."""
    import pandas as pd
    from engine_alpha.metrics import distance_to_52w_high_pct

    out = {"basis": None, "prev_close": None, "dist_52w_high": None}
    if frame is None or frame.empty:
        return out
    index = pd.to_datetime(frame.index)
    if scan_date:
        before = frame["High"][index <= pd.Timestamp(scan_date)]
        out["basis"] = None if before.empty else float(before.iloc[-1])
    closes = frame["Close"][index < pd.Timestamp(session_day)]
    out["prev_close"] = None if closes.empty else float(closes.iloc[-1])
    out["dist_52w_high"] = distance_to_52w_high_pct(frame["High"], float(frame["Close"].iloc[-1]))
    return out


def for_watches(rows, session_day: str) -> dict:
    """Per save: the six gains, the price facts, the ticker's last bar, and a status word.

    The day before the add is the save's basis scan (the scan on screen when it
    was saved, pinned or not; the pin for saves older than that column).
    status: "ok" | "no_pin" (saved without a scan: no day to measure from) |
    "no_bar_since_scan" (nothing has traded since the saved scan yet) | the
    chart reader's own verdict when it serves no bars ("no_cache",
    "unknown_ticker", "no_drawable_bars").
    """
    from domains.market_data.watchlist_candles import daily_frames
    from domains.watchlist.ledger import universe_key_for_type

    frames, statuses = daily_frames(
        [row.ticker for row in rows],
        {row.ticker: universe_key_for_type(row.pin_universe_type) for row in rows},
    ) if rows else ({}, {})
    out = {}
    for row in rows:
        frame = frames.get(row.ticker)
        scan_date = row.basis_scan_date or row.pin_scan_date
        gains = best_gains(frame, scan_date)
        if frame is None:
            status = statuses[row.ticker]
        elif not scan_date:
            status = "no_pin"
        else:
            status = "ok" if gains["since_add"] is not None else "no_bar_since_scan"
        last_bar = None if frame is None else str(frame.index[-1])[:10]
        out[row.ticker] = {"status": status, "last_bar_date": last_bar, **gains,
                           **price_facts(frame, scan_date, session_day)}
    return out
