"""Per-ticker D/W/M candle wire for the Watchlist page.

A price-history resource, NOT a watchlist route: it serves any ticker the
parquet price cache holds, regardless of stars or scan membership (tying it
to watchlist state would 404 the chart the moment the operator unstars the
name on screen). Thin router — the decisions live in
services/watchlist_candles.py. Engine-read material never rides this wire
(EC-28: the overlay comes only from the scan artifact).
"""
from __future__ import annotations

import logging
from typing import Dict, List, Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from marks_validity import TICKER_RE
from routers.calibration import require_same_app
from routers.watchlist import valid_symbol
from services import watchlist_candles

router = APIRouter(prefix="/candles", tags=["candles"])
logger = logging.getLogger("chrollo.candles")

# Response-size bound for the batch route: the card grid serves a watchlist
# (tens of names), and each universe costs a pruned panel read — an unbounded
# list would let one request occupy the threadpool for the whole box.
BATCH_MAX_TICKERS = 60


# The two closed verdict vocabularies (mirrors watchlist_candles.TICKER_STATUSES /
# FRAME_STATUSES; the endpoint test battery pins the pairs in agreement). Every
# no-candles outcome is a NAMED verdict on a 200 — never a 500 (EC-6), so the
# frontend can tell a data gap from a bug.
TickerStatus = Literal["ok", "no_cache", "unknown_ticker", "no_drawable_bars"]
FrameStatus = Literal["ok", "empty"]


class FrameOut(BaseModel):
    """One timeframe's candle arrays — shape-identical to the scan payload's
    candle/volume dicts (the shared builder is the single producer). "empty"
    in practice co-occurs only with a non-ok ticker status: the resampler
    yields at least one bucket for any nonempty cleaned frame, so a servable
    ticker fills all three frames (the router battery pins the pairing).
    ``forming_last_bar`` is resolved server-side: True when the final
    bucket's end label lies beyond the ticker's last traded session
    (mid-week, the weekly/monthly tail bar is a partial period — the NORMAL
    case, marked so the operator never reads a two-session "month" as
    finished)."""

    status: FrameStatus
    forming_last_bar: bool | None
    candles: List[Dict]
    volumes: List[Dict]


class TickerCandlesOut(BaseModel):
    """The selected-ticker envelope, with provenance as resolved facts: which
    universe's panel served it, the cache's price-series regime, and the
    ticker's OWN last-bar date — so the page can stamp data age honestly and
    detect a basis mismatch against scan-artifact overlays."""

    ticker: str
    # The registry key of the universe whose panel served the candles; None
    # when no cached universe holds the ticker.
    universe: str | None
    status: TickerStatus
    # This wire is always the FRESH CACHE basis — distinguishable from the
    # replay route's frozen snapshot envelope.
    source: Literal["cache"]
    price_series: str | None
    cache_last_modified: str | None
    last_bar_date: str | None
    frames: Dict[str, FrameOut]


class BatchTickerOut(BaseModel):
    """One card cell: the ticker's own named verdict + daily candles at the
    SAME cap the scan artifact's cards use (full-window parity — the grid's
    clean cards and screener cards can never disagree on the window). A dead
    name degrades its one cell, never the batch."""

    status: TickerStatus
    candles: List[Dict]
    volumes: List[Dict]


class BatchCandlesOut(BaseModel):
    tickers: Dict[str, BatchTickerOut]


@router.get("/", response_model=BatchCandlesOut,
            dependencies=[Depends(require_same_app)])
def get_batch_candles(tickers: str = Query(..., min_length=1),
                      pins: str | None = None):
    """Batched daily-only candles for the card grid, one round trip, at the
    scan-card cap.

    Symbols failing the strict grammar are dropped (the live-prices batch
    precedent) — they can never reach a lookup; an over-cap batch is refused
    loudly rather than silently truncated. ``pins`` carries the stored
    per-ticker pin keys (EC-37) as comma-separated TICKER:key pairs —
    pair-keyed, not positional, so it survives the grammar drop and dedup;
    a malformed pair or unknown key degrades into the deterministic search
    exactly like the single-ticker route's ``universe`` param."""
    symbols = []
    for raw in tickers.split(","):
        sym = raw.strip().upper()
        if sym and TICKER_RE.match(sym) and sym not in symbols:
            symbols.append(sym)
    if len(symbols) > BATCH_MAX_TICKERS:
        raise HTTPException(status_code=400, detail={
            "class": "too_many_tickers",
            "message": f"At most {BATCH_MAX_TICKERS} tickers per batch",
        })
    pin_map: Dict[str, str] = {}
    for raw in (pins.split(",") if pins else []):
        sym, sep, key = raw.strip().partition(":")
        sym = sym.strip().upper()
        if sep and key and sym in symbols:
            pin_map[sym] = key.strip()
    return watchlist_candles.batch_candles(symbols, pin_map)


@router.get("/{ticker}", response_model=TickerCandlesOut,
            dependencies=[Depends(require_same_app)])
def get_ticker_candles(ticker: str, universe: str | None = Query(None)):
    """The selected-ticker envelope: all three timeframes in one response.

    ``universe`` is the stored pin's registry KEY (EC-37 — the pin decides
    which panel serves); it is resolved only through the closed registry and
    an unknown value degrades into the deterministic search, so no request
    string can ever influence a filesystem path."""
    sym = valid_symbol(ticker)
    return watchlist_candles.ticker_candles(sym, universe)
