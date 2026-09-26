"""Equity-curve and R-multiple-histogram analytics endpoints for the Dashboard charts."""
from __future__ import annotations

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
