"""Calibration marking surface — chart lookup + marks CRUD.

The chart lookup is the first backend surface fed by free-typed operator
input: strict validation at the boundary (reject, never sanitize past
case/whitespace normalization), every vendor read through the one market-data
doorway (inherits the provider's hang bound + shared rate-limit bucket), and
every operational failure mapped to a DISTINCT, renderable answer — degrade,
never 500 (EC-6 pattern). The payload carries the point-in-time provenance a
saved mark must echo (data regime, engine config version, the as-of bar's
close): marks are born on the exact frame the operator looked at, never
re-stamped after the fact.

Marks CRUD joins this router in Task 4 (PLAN-calibration-at-scale.md).
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, Query

from marks_validity import TICKER_RE, parse_iso_date

router = APIRouter(prefix="/calibration", tags=["calibration"])
logger = logging.getLogger("chrollo.calibration")

_LOOKBACK_DAYS = 900   # calendar lead-in behind the as-of bar (~2y of sessions + margin)
_FORWARD_DAYS = 45     # hindsight context after it (archive-chart precedent)
_DATE_FLOOR = "2000-01-01"
_SHORT_FRAME_BARS = 300  # below this the engine's 2y frame is visibly truncated


def _refuse(status: int, reason_class: str, message: str, ticker: str, as_of: str):
    """One structured log line per degraded outcome class, then the refusal."""
    logger.info("chart %s ticker=%s as_of=%s: %s", reason_class, ticker, as_of, message)
    raise HTTPException(status_code=status,
                        detail={"class": reason_class, "message": message})


@router.get("/chart")
def calibration_chart(ticker: str = Query(...), as_of: str = Query(...)):
    """Daily candles for any ticker anchored at any historical as-of date."""
    symbol = ticker.strip().upper()
    if not TICKER_RE.match(symbol):
        _refuse(400, "bad_ticker",
                "ticker must be 1-10 chars of A-Z, 0-9, '.' or '-'", symbol, as_of)
    as_of_dt = parse_iso_date(as_of)
    if as_of_dt is None:
        _refuse(400, "bad_date", "as_of must be exactly YYYY-MM-DD", symbol, as_of)
    if as_of < _DATE_FLOOR:
        _refuse(400, "bad_date", f"as_of before the {_DATE_FLOOR} floor", symbol, as_of)
    if as_of_dt.date() > datetime.now(timezone.utc).date():
        _refuse(400, "future_date", "as_of is in the future", symbol, as_of)

    import pandas as pd

    from core.pipeline.downloads import _price_regime, price_auto_adjust  # noqa: PLC0415 — lazy, yfinance-heavy chain
    from core.freeze.manifest import manifest_hash  # noqa: PLC0415
    from services.market_data import chart_candles, daily_candle_frame

    as_of_ts = pd.Timestamp(as_of)
    start = (as_of_ts - pd.Timedelta(days=_LOOKBACK_DAYS)).strftime("%Y-%m-%d")
    end = (as_of_ts + pd.Timedelta(days=_FORWARD_DAYS)).strftime("%Y-%m-%d")
    raw = daily_candle_frame(symbol, 0, start=start, end=end,
                             auto_adjust=price_auto_adjust())
    if raw.empty:
        _refuse(404, "no_data",
                "vendor returned nothing — unknown/delisted ticker, or a vendor "
                "outage / drained rate bucket; retry once before distrusting the "
                "ticker", symbol, as_of)

    frame = raw[raw.index <= as_of_ts]
    if frame.empty:
        first = raw.index[0].strftime("%Y-%m-%d")
        _refuse(404, "no_bars_at_date",
                f"history for {symbol} starts {first}, after the requested as-of",
                symbol, as_of)

    as_of_session = frame.index[-1].strftime("%Y-%m-%d")
    anchor_close = frame.iloc[-1]["Close"]
    try:
        anchor_close = float(anchor_close)
    except (TypeError, ValueError):
        anchor_close = float("nan")
    if not (anchor_close == anchor_close and anchor_close > 0):  # NaN-safe
        _refuse(404, "no_data", f"no finite close on {as_of_session}", symbol, as_of)

    warnings = []
    if as_of_session != as_of:
        warnings.append(f"{as_of} is not a session; resolved to {as_of_session}")
    if len(frame) < _SHORT_FRAME_BARS:
        warnings.append(f"short history ({len(frame)} bars): the engine's 2y frame "
                        "is truncated here — marks may grade edge-uncertain")

    candles, volumes = chart_candles(
        raw,
        up_color="rgba(38, 166, 154, 0.5)",
        down_color="rgba(239, 83, 80, 0.5)",
        require_finite=True,
        volume_as_int=True,
    )
    return {
        "ticker": symbol,
        "as_of": as_of,
        "as_of_session": as_of_session,
        "anchor_close": anchor_close,
        "bar_count": int(len(frame)),
        "forward_bars": int((raw.index > as_of_ts).sum()),
        "frame_start": raw.index[0].strftime("%Y-%m-%d"),
        "frame_end": raw.index[-1].strftime("%Y-%m-%d"),
        "data_regime": _price_regime(),
        "engine_config_version": manifest_hash(),
        "warnings": warnings,
        "candles": candles,
        "volumes": volumes,
    }
