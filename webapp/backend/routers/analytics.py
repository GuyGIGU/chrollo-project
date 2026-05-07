"""Aggregation endpoints for the Dashboard AnalyticsPanel + equity curve charts."""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

import models
from database import get_db

router = APIRouter(prefix="/analytics", tags=["analytics"])


def _closed_trades(db: Session) -> List[models.TradeLog]:
    return (
        db.query(models.TradeLog)
        .filter(models.TradeLog.pnl.isnot(None))
        .all()
    )


def _parse_date(s: Optional[str]) -> Optional[datetime]:
    if not s:
        return None
    s = s.strip()
    if not s:
        return None
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            continue
    try:
        return datetime.fromisoformat(s)
    except Exception:
        return None


def _summarize(pnls: List[float]) -> Dict[str, Any]:
    if not pnls:
        return {
            "count": 0, "wins": 0, "losses": 0, "win_rate": 0.0,
            "total_pnl": 0.0, "avg_pnl": 0.0, "avg_win": 0.0, "avg_loss": 0.0,
            "profit_factor": 0.0,
        }
    wins = [p for p in pnls if p > 0]
    losses = [p for p in pnls if p < 0]
    total_wins = sum(wins)
    total_losses = abs(sum(losses))
    return {
        "count": len(pnls),
        "wins": len(wins),
        "losses": len(losses),
        "win_rate": round(len(wins) / len(pnls) * 100, 2),
        "total_pnl": round(sum(pnls), 2),
        "avg_pnl": round(sum(pnls) / len(pnls), 2),
        "avg_win": round(total_wins / len(wins), 2) if wins else 0.0,
        "avg_loss": round(-total_losses / len(losses), 2) if losses else 0.0,
        "profit_factor": round(total_wins / total_losses, 2) if total_losses > 0 else (round(total_wins, 2) if total_wins > 0 else 0.0),
    }


@router.get("/by-tag")
def by_tag(db: Session = Depends(get_db)) -> List[Dict[str, Any]]:
    rows: Dict[int, Dict[str, Any]] = {}
    for trade in _closed_trades(db):
        for tag in trade.tags:
            bucket = rows.setdefault(tag.id, {"tag_id": tag.id, "name": tag.name, "category": tag.category, "color": tag.color, "pnls": []})
            bucket["pnls"].append(float(trade.pnl))
    out = []
    for bucket in rows.values():
        pnls = bucket.pop("pnls")
        out.append({**bucket, **_summarize(pnls)})
    out.sort(key=lambda r: r["total_pnl"], reverse=True)
    return out


@router.get("/by-symbol")
def by_symbol(db: Session = Depends(get_db)) -> List[Dict[str, Any]]:
    rows: Dict[str, List[float]] = defaultdict(list)
    for trade in _closed_trades(db):
        if not trade.ticker:
            continue
        rows[trade.ticker.upper()].append(float(trade.pnl))
    out = [{"symbol": sym, **_summarize(pnls)} for sym, pnls in rows.items()]
    out.sort(key=lambda r: r["total_pnl"], reverse=True)
    return out


@router.get("/by-hour")
def by_hour(db: Session = Depends(get_db)) -> List[Dict[str, Any]]:
    """Bucket closed trades by the hour their opening_date falls in.

    Manual entries that only store a date will fall under hour 0. Hours with no trades are omitted.
    """
    rows: Dict[int, List[float]] = defaultdict(list)
    for trade in _closed_trades(db):
        dt = _parse_date(trade.opening_date)
        if dt is None:
            continue
        rows[dt.hour].append(float(trade.pnl))
    out = [{"hour": h, **_summarize(rows[h])} for h in sorted(rows)]
    return out


_DOW_NAMES = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


@router.get("/by-day-of-week")
def by_day_of_week(db: Session = Depends(get_db)) -> List[Dict[str, Any]]:
    rows: Dict[int, List[float]] = defaultdict(list)
    for trade in _closed_trades(db):
        dt = _parse_date(trade.opening_date)
        if dt is None:
            continue
        rows[dt.weekday()].append(float(trade.pnl))
    out = []
    for dow in range(7):
        out.append({"day_of_week": dow, "day_name": _DOW_NAMES[dow], **_summarize(rows.get(dow, []))})
    return out


@router.get("/equity-curve")
def equity_curve(db: Session = Depends(get_db)) -> List[Dict[str, Any]]:
    """Cumulative realized P&L ordered by closing_date (fallback opening_date).

    Keyed by round-trip close time, realized P&L only — matches spec from plan.
    """
    trades = _closed_trades(db)
    points = []
    for t in trades:
        dt = _parse_date(t.closing_date) or _parse_date(t.opening_date)
        if dt is None:
            continue
        points.append((dt, float(t.pnl), t.id, t.ticker))
    points.sort(key=lambda x: x[0])
    out = []
    cum = 0.0
    for dt, pnl, tid, ticker in points:
        cum += pnl
        out.append({
            "date": dt.isoformat(),
            "pnl": round(pnl, 2),
            "cumulative_pnl": round(cum, 2),
            "trade_id": tid,
            "ticker": ticker,
        })
    return out


@router.get("/drawdown")
def drawdown(db: Session = Depends(get_db)) -> Dict[str, Any]:
    curve = equity_curve(db)
    if not curve:
        return {"series": [], "max_drawdown": 0.0, "max_drawdown_pct": 0.0}
    peak = 0.0
    series = []
    max_dd = 0.0
    max_dd_pct = 0.0
    for pt in curve:
        cum = pt["cumulative_pnl"]
        if cum > peak:
            peak = cum
        dd = cum - peak
        dd_pct = (dd / peak * 100) if peak > 0 else 0.0
        if dd < max_dd:
            max_dd = dd
            max_dd_pct = dd_pct
        series.append({"date": pt["date"], "drawdown": round(dd, 2), "drawdown_pct": round(dd_pct, 2)})
    return {"series": series, "max_drawdown": round(max_dd, 2), "max_drawdown_pct": round(max_dd_pct, 2)}


@router.get("/r-multiple-histogram")
def r_multiple_histogram(
    db: Session = Depends(get_db),
    bin_width: float = Query(0.5, ge=0.1, le=5.0),
    max_bin: float = Query(5.0, ge=1.0, le=20.0),
) -> Dict[str, Any]:
    """Bin (pnl / initial_risk_dollars) across all closed trades.

    Uses planned_stop when available, otherwise falls back to stop_loss.
    Trades with zero or missing risk are excluded and counted in `skipped`.
    """
    trades = _closed_trades(db)
    r_values: List[float] = []
    skipped = 0
    for t in trades:
        stop = t.planned_stop if t.planned_stop is not None else t.stop_loss
        if stop is None or t.entry_price is None or not t.quantity:
            skipped += 1
            continue
        risk_dlr = abs(t.entry_price - stop) * t.quantity
        if risk_dlr <= 0:
            skipped += 1
            continue
        r_values.append(t.pnl / risk_dlr)

    # Build symmetric bins: [-max_bin, -max_bin+bin_width, ..., max_bin]
    bins: Dict[str, int] = {}
    edges = []
    x = -max_bin
    while x < max_bin + 1e-9:
        edges.append(round(x, 3))
        x += bin_width
    for lo, hi in zip(edges[:-1], edges[1:]):
        bins[f"{lo:.2f}"] = 0

    under = 0
    over = 0
    for r in r_values:
        if r < -max_bin:
            under += 1
            continue
        if r >= max_bin:
            over += 1
            continue
        # Find bin index
        idx = int((r + max_bin) / bin_width)
        idx = max(0, min(idx, len(edges) - 2))
        lo = edges[idx]
        bins[f"{lo:.2f}"] = bins.get(f"{lo:.2f}", 0) + 1

    series = []
    for lo, hi in zip(edges[:-1], edges[1:]):
        series.append({"bin_start": lo, "bin_end": hi, "count": bins[f"{lo:.2f}"]})

    avg_r = round(sum(r_values) / len(r_values), 3) if r_values else 0.0
    return {
        "series": series,
        "under_min": under,
        "over_max": over,
        "skipped": skipped,
        "total": len(r_values),
        "avg_r": avg_r,
    }
