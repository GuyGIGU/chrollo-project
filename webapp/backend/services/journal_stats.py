"""Trade journal aggregate metrics."""
from __future__ import annotations

import models

EMPTY_STATS = {
    "total_pnl": 0,
    "win_rate": 0,
    "profit_factor": 0,
    "r_multiple_total": 0,
    "avg_win": 0,
    "avg_loss": 0,
    "total_trades": 0,
    "winning_trades": 0,
    "losing_trades": 0,
}


def calculate_journal_stats(trades: list[models.TradeLog]) -> dict:
    if not trades:
        return EMPTY_STATS.copy()

    # A break-even trade (pnl == 0) is neither a win nor a loss — matches
    # routers/analytics._summarize so the journal and per-tag/symbol panels agree.
    winners = [trade for trade in trades if trade.pnl is not None and trade.pnl > 0]
    losers = [trade for trade in trades if trade.pnl is not None and trade.pnl < 0]

    total_wins = sum(trade.pnl for trade in winners)
    total_losses = abs(sum(trade.pnl for trade in losers))
    profit_factor = _profit_factor(total_wins, total_losses)

    return {
        "total_pnl": sum(trade.pnl for trade in trades if trade.pnl is not None),
        "win_rate": round(len(winners) / len(trades) * 100, 2),
        "profit_factor": round(profit_factor, 2),
        "r_multiple_total": round(_r_multiple_total(trades), 2),
        "avg_win": round(total_wins / len(winners), 2) if winners else 0,
        "avg_loss": round(-(total_losses / len(losers)), 2) if losers else 0,
        "total_trades": len(trades),
        "winning_trades": len(winners),
        "losing_trades": len(losers),
    }


def _profit_factor(total_wins: float, total_losses: float) -> float:
    if total_losses > 0:
        return total_wins / total_losses
    return total_wins if total_wins > 0 else 0


def _r_multiple_total(trades: list[models.TradeLog]) -> float:
    total = 0
    for trade in trades:
        if not _has_risk_fields(trade):
            continue
        risk_dollars = abs(trade.entry_price - trade.stop_loss) * trade.quantity
        if risk_dollars > 0:
            total += trade.pnl / risk_dollars
    return total


def _has_risk_fields(trade: models.TradeLog) -> bool:
    return (
        trade.pnl is not None
        and trade.entry_price > 0
        and trade.stop_loss > 0
        and trade.quantity > 0
    )
