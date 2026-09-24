"""One chart's state word, on demand (the final method, points 22 and 24; build step 12).

The scan's payload lists the fires and, once the method flips, the watch lane; every other chart the operator
looks at (a starred name the scan did not list, a ticker he types) gets its ONE state word from the same table
here, read off the cached frame by the same evaluation chain the scan ran: "not scanned" with the door's leg
named in plain words and the distance to it in daily ranges (point 24: "not scanned: under the 50-day
average"), or the lines the walk found and their facts (the rails, the open day, the age, the turns at each
rail). Never on thousands of rows: one ticker per call, from the watchlist and the ticker page only.

Read-only: the cache is read the way the watchlist candles read it, no download, no archive write, no scan.
"""
from __future__ import annotations

import logging

from config import settings
from engine_alpha import evaluation
from engine_alpha.structure.indicators import calculate_atr
from services import watchlist_candles

logger = logging.getLogger("chrollo.chart_state")

# The door's legs in his words (apply_baseline_filters_with_reason names the first failing gate).
DOOR_WORDS = {
    "bars": "fewer than 200 trading days of history",
    "price": f"under the {settings.MIN_PRICE:g} dollar price floor",
    "vol50": "under the 50-day volume floor",
    "sma50": "under the 50-day average",
    "sma200": "under the 200-day average",
    "yoy": f"down more than {abs(settings.MIN_YEARLY_RETURN) * 100:.0f} percent over the year",
}
FRAME_WORDS = {
    "unknown": "not in any scanned universe",
    "dead": "no bars left in the cache",
    "unreadable": "the cache could not be read",
}


def _door_distance(frame, leg: str):
    """How far under the average the last close sits, in daily ranges (ATR_10), for the two average legs."""
    window = {"sma50": 50, "sma200": 200}.get(leg)
    if window is None or len(frame) < max(window, 11):
        return None
    close = float(frame["Close"].iloc[-1])
    average = float(frame["Close"].rolling(window=window).mean().iloc[-1])
    atr = float(calculate_atr(frame, 10).iloc[-1])
    if not atr or atr != atr or atr <= 0:
        return None
    return round((average - close) / atr, 2)


def read_chart_state(ticker: str, universe_key: str | None = None) -> dict:
    """The state word and its facts for one ticker, from the cached frame."""
    ticker = ticker.strip().upper()
    _universe, frame, status = watchlist_candles._serving_universe_and_frame(ticker, universe_key)
    if frame is None:
        return {"ticker": ticker, "as_of": None, "state": "not scanned",
                "why": FRAME_WORDS.get(status, status), "distance_ranges": None, "close": None}
    watch: dict = {}
    try:
        result = evaluation._run_eval_chain(ticker, frame, 0.0, None, watch=watch)
    except Exception as exc:  # noqa: BLE001 - the read never raises at the operator
        logger.warning("chart state %s: %r", ticker, exc)
        return {"ticker": ticker, "as_of": str(frame.index[-1].date()), "state": "no lines",
                "why": "the read failed", "distance_ranges": None,
                "close": round(float(frame["Close"].iloc[-1]), 4)}
    state = evaluation.watch_verdict(watch, isinstance(result, dict))
    out = {"ticker": ticker, "as_of": str(frame.index[-1].date()), "state": state,
           "why": watch.get("why"), "distance_ranges": None,
           "close": round(float(frame["Close"].iloc[-1]), 4)}
    if state == "not scanned":
        leg = watch.get("why")
        out["why"] = DOOR_WORDS.get(leg, leg)
        out["distance_ranges"] = _door_distance(frame, leg)
        return out
    if watch.get("df") is not None and watch.get("unit") and (watch.get("structure") is not None
                                                                or watch.get("box") is not None):
        row = evaluation._lane_row(ticker, watch, state, floor=0)
        if row is not None:
            for key in ("R", "S", "open", "age", "turns_at_r", "turns_at_s", "days", "forming"):
                if key in row:
                    out[key] = row[key]
    return out
