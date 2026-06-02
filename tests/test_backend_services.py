import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = ROOT / "webapp" / "backend"
sys.path.insert(0, str(ROOT))
sys.path.insert(1, str(BACKEND_DIR))

from webapp.backend.routers.position_calculator import calculate_position
from webapp.backend.services.journal_stats import calculate_journal_stats


def trade(pnl, entry_price=10, stop_loss=9, quantity=100):
    return SimpleNamespace(
        pnl=pnl,
        entry_price=entry_price,
        stop_loss=stop_loss,
        quantity=quantity,
    )


def test_calculate_journal_stats_handles_empty_list():
    stats = calculate_journal_stats([])

    assert stats["total_trades"] == 0
    assert stats["total_pnl"] == 0
    assert stats["profit_factor"] == 0


def test_calculate_journal_stats_summarizes_wins_losses_and_r_multiple():
    stats = calculate_journal_stats([
        trade(200, entry_price=10, stop_loss=9, quantity=100),
        trade(-50, entry_price=20, stop_loss=19, quantity=50),
        trade(None),
    ])

    assert stats["total_pnl"] == 150
    assert stats["win_rate"] == pytest.approx(33.33)
    assert stats["profit_factor"] == 4
    assert stats["r_multiple_total"] == 1
    assert stats["avg_win"] == 200
    assert stats["avg_loss"] == -50
    assert stats["winning_trades"] == 1
    assert stats["losing_trades"] == 1


def test_calculate_position_returns_size_from_risk_distance():
    result = calculate_position(risk_amount=100, entry_price=20, stop_price=18)

    assert result == {
        "shares": 50,
        "stop_distance": 2,
        "position_size": 1000,
    }


@pytest.mark.parametrize(
    ("risk_amount", "entry_price", "stop_price"),
    [(0, 20, 18), (100, 0, 18), (100, 20, 20)],
)
def test_calculate_position_rejects_invalid_inputs(risk_amount, entry_price, stop_price):
    with pytest.raises(HTTPException):
        calculate_position(risk_amount=risk_amount, entry_price=entry_price, stop_price=stop_price)
