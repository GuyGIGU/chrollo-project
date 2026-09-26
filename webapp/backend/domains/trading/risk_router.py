"""Read-only live open-trade risk endpoint (Trade Enrich — Layer A).

A thin GET over ``domains.trading.risk`` (the pure, single-source-of-truth risk
math). It loads OPEN trades, resolves a live price per ticker from the EXISTING
IBKR snapshot (no new broker connection) with a yfinance fallback, derives the
risk overlay off the event loop (plain ``def`` → Starlette threadpool), and
returns per-trade rows + an aggregate open-risk summary.

Disciplines baked in (from the council plan):
  * The SQLite read is released BEFORE the multi-second price fetch, so a slow
    Yahoo lookup never holds a read transaction open against the live SSE/import
    writer (single-writer + WAL).
  * The price resolution is wrapped in a short-TTL coalesce so rapid/overlapping
    polls don't re-hit the snapshot + provider each time.
  * The provider leg is skipped while a scan is running and de-dups tickers to a
    single ``latest_price`` call; a missing/stale quote degrades a row to a null
    ``currentExit`` (never a 500, never a silent zero).
  * Only a per-ticker price is projected out of the snapshot — the raw snapshot
    (account summary, connection params) never reaches the response.
"""
from __future__ import annotations

import logging
import math
import threading
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter
from pydantic import BaseModel

import models
from database import SessionLocal
from domains.ibkr import get_ibkr_service
from services import scan_status
from domains.trading import risk as risk_math

router = APIRouter(prefix="/live-risk", tags=["live-risk"])
_log = logging.getLogger("chrollo.trade_risk")

# Only the yfinance provider leg is expensive (per-symbol serial network) — coalesce
# IT across rapid/overlapping polls. The IBKR snapshot is a cheap in-memory copy,
# read FRESH every request so the connection/stale state is never frozen by a cache.
_PROVIDER_TTL_SECONDS = 10.0
_provider_lock = threading.Lock()
_provider_cache: Dict[str, Any] = {"at": 0.0, "key": None, "value": None}

# Negative-result quarantine: a symbol the provider answered with NO quote
# (delisted/unknown) is not re-asked on every ~20s poll — each miss costs two
# yfinance ERROR log lines and multi-second latency, forever, for a symbol that
# will never price. A miss re-qualifies after the TTL so a transient Yahoo
# failure can't mute a live ticker for the whole session; options past their
# expiry are skipped outright (they can never price again).
_MISS_QUARANTINE_SECONDS = 3600.0
_miss_cache: Dict[str, float] = {}  # SYMBOL -> monotonic time of the last miss

# Mirror read_trades' implicit bound — a personal journal, not an unbounded table.
_OPEN_TRADE_LIMIT = 500

_TRADE_FIELDS = (
    "id", "ticker", "direction", "entry_price", "stop_loss", "planned_stop",
    "quantity", "commissions", "pnl", "exit_price", "closing_date", "opening_date",
    "actions_json",
)


class TargetRung(BaseModel):
    index: int
    label: str
    price: Optional[float]
    qty: Optional[float]
    hit: bool
    isNext: bool
    distToTargetPct: Optional[float]
    rToTarget: Optional[float]


class RiskRow(BaseModel):
    distToStopPct: Optional[float]
    distToStopR: Optional[float]
    distToTargetPct: Optional[float]
    direction: str
    entryVwap: Optional[float]
    exitDate: Optional[str]
    isLong: bool
    multiplier: float
    nextTarget: Optional[TargetRung]
    openQty: Optional[float]
    pnl: Optional[float]
    pnlPct: Optional[float]
    position: Optional[float]
    riskDistance: Optional[float]
    riskQty: Optional[float]
    rValue: Optional[float]
    rToStop: Optional[float]
    status: str
    stopPct: Optional[float]
    stopRiskTone: Optional[str]
    stopVal: Optional[float]
    plannedStopVal: Optional[float]
    targetLadder: List[TargetRung]
    totalExit: Optional[float]
    totalWorth: Optional[float]
    currentExit: Optional[float]
    currentExitSource: Optional[str]


class OpenRiskSummary(BaseModel):
    nOpen: int
    nPriced: int
    totalUnrealizedPnl: Optional[float]
    nBreached: int
    nDanger: int
    nWarning: int
    nAtRisk: int


class LiveRiskResponse(BaseModel):
    rows: Dict[int, RiskRow]
    summary: OpenRiskSummary
    at: str
    stale: bool


# Plain ``def`` on purpose: the snapshot read + provider lookup are blocking, so
# Starlette dispatches this to the threadpool and never stalls the event loop.
@router.get("/", response_model=LiveRiskResponse)
def get_live_risk() -> dict:
    trades = _load_open_trades()
    tickers = sorted({t["ticker"].upper() for t in trades if t.get("ticker")})
    price_map, stale = _resolve_prices(tickers)

    rows: Dict[int, dict] = {}
    for trade in trades:
        symbol = str(trade.get("ticker") or "").upper()
        price, source = price_map.get(symbol, (None, None))
        rows[trade["id"]] = risk_math.derive_trade_risk(trade, live_price=price, live_source=source)

    summary = risk_math.build_open_risk_summary(list(rows.values()))
    return {
        "rows": rows,
        "summary": summary,
        "at": datetime.now(timezone.utc).isoformat(),
        "stale": stale,
    }


def _load_open_trades() -> List[Dict[str, Any]]:
    """Load open-candidate trades and detach them to plain dicts, THEN close the
    session — so the read connection is released before any price fetch.

    Open predicate mirrors the FE: ``pnl IS NULL`` AND (``closing_date`` null or
    empty) AND a ticker present. ``IS NULL`` (not truthiness) keeps it correct
    over the nullable ``pnl`` column; the empty-string ``closing_date`` arm
    matches the FE's ``!closing_date`` falsy check. Final open/partial refinement
    is left to the ledger-derived ``status`` the consumers filter on.
    """
    from sqlalchemy import or_

    db = SessionLocal()
    try:
        query = (
            db.query(models.TradeLog)
            .filter(models.TradeLog.pnl.is_(None))
            .filter(or_(models.TradeLog.closing_date.is_(None), models.TradeLog.closing_date == ""))
            .filter(models.TradeLog.ticker.isnot(None))
            .filter(models.TradeLog.ticker != "")
            .order_by(models.TradeLog.opening_date.desc(), models.TradeLog.id.desc())
            .limit(_OPEN_TRADE_LIMIT)
        )
        return [_trade_to_dict(row) for row in query.all()]
    finally:
        db.close()


def _trade_to_dict(trade: models.TradeLog) -> Dict[str, Any]:
    data = {field: getattr(trade, field, None) for field in _TRADE_FIELDS}
    for index in range(1, 6):
        data[f"t{index}_price"] = getattr(trade, f"t{index}_price", None)
        data[f"t{index}_qty"] = getattr(trade, f"t{index}_qty", None)
    return data


def _resolve_prices(tickers: List[str]) -> tuple[Dict[str, tuple], bool]:
    """Return ``{TICKER: (price, source)}`` plus a fresh ``stale`` flag.

    The IBKR snapshot (prices + connection state) is read fresh each call; only
    the expensive yfinance leg is TTL-coalesced.
    """
    result, stale = _ibkr_price_map()
    missing = [ticker for ticker in tickers if ticker not in result]
    result.update(_provider_price_map(missing))
    return result, stale


def _ibkr_price_map() -> tuple[Dict[str, tuple], bool]:
    """Per-ticker IBKR price + a fresh ``stale`` flag from the existing snapshot
    (no new connection). A failed/contract-drifted read degrades to stale + logs."""
    result: Dict[str, tuple] = {}
    try:
        snap = get_ibkr_service().snapshot()
    except Exception:
        _log.warning("trade-risk: IBKR snapshot read failed; treating feed as stale", exc_info=True)
        return result, True
    stale = bool(snap.get("stale") or snap.get("session_competition") or not snap.get("connected", False))
    positions = snap.get("portfolio") or snap.get("positions") or []
    for position in positions:
        symbol = str(position.get("symbol") or "").upper()
        price = _positive_finite(position.get("market_price"))
        if symbol and price is not None:
            result[symbol] = (price, "ibkr")
    return result, stale


def _provider_price_map(missing: List[str]) -> Dict[str, tuple]:
    """TTL-coalesced yfinance fallback for tickers the snapshot didn't price.
    Skipped while a scan holds the provider; expired-option and quarantined
    symbols are filtered out before the fetch. Returns a COPY so callers can't
    mutate the shared cache."""
    if _scan_is_running():
        return {}
    missing = [symbol for symbol in missing if _provider_askable(symbol)]
    if not missing:
        return {}
    key = ",".join(missing)
    now = time.monotonic()
    with _provider_lock:
        cached = _provider_cache
        if cached["key"] == key and cached["value"] is not None and (now - cached["at"]) < _PROVIDER_TTL_SECONDS:
            return dict(cached["value"])

    value = _fetch_provider_prices(missing)
    with _provider_lock:
        _provider_cache["key"] = key
        _provider_cache["value"] = value
        _provider_cache["at"] = time.monotonic()
    return dict(value)


def _provider_askable(symbol: str) -> bool:
    """False for symbols the provider must not be asked: an option past its
    expiry can never price again; a recent no-quote miss waits out the TTL."""
    expiry = risk_math.option_expiry(symbol)
    if expiry is not None and expiry < datetime.now(timezone.utc).date():
        return False
    with _provider_lock:
        missed_at = _miss_cache.get(symbol)
    return missed_at is None or (time.monotonic() - missed_at) >= _MISS_QUARANTINE_SECONDS


def _fetch_provider_prices(missing: List[str]) -> Dict[str, tuple]:
    result: Dict[str, tuple] = {}
    try:
        from core.pipeline.market_data.providers import get_provider

        quotes = get_provider().latest_price(missing) or {}
    except Exception:
        # Whole-call failure = transient (network/import); don't quarantine.
        _log.warning("trade-risk: provider latest_price failed for %d ticker(s)", len(missing), exc_info=True)
        return result
    for ticker in missing:
        price = _positive_finite(quotes.get(ticker))
        if price is not None:
            result[ticker] = (price, "yf")
    misses = [ticker for ticker in missing if ticker not in result]
    if misses:
        now = time.monotonic()
        with _provider_lock:
            for ticker in misses:
                _miss_cache[ticker] = now
        _log.info(
            "trade-risk: no provider quote for %s; quarantined for %.0f min",
            ",".join(misses), _MISS_QUARANTINE_SECONDS / 60,
        )
    return result


def _positive_finite(value: Any) -> Optional[float]:
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if (math.isfinite(number) and number > 0) else None


def _scan_is_running() -> bool:
    try:
        latest = scan_status.latest_run()
    except Exception:
        return False
    return (latest or {}).get("status") == "running"
