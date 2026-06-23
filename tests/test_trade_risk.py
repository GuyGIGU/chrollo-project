import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = ROOT / "webapp" / "backend"
sys.path.insert(0, str(ROOT))
sys.path.insert(1, str(BACKEND_DIR))

from services.trade_risk import evaluate_open_trade


def trade(**overrides):
    base = {
        "id": 1,
        "opening_date": "2026-06-01",
        "direction": "LONG",
        "ticker": "MSFT",
        "entry_price": 100,
        "stop_loss": 90,
        "quantity": 10,
        "remaining_qty": None,
        "closing_date": None,
        "pnl": None,
    }
    base.update(overrides)
    return SimpleNamespace(**base)


def test_evaluate_open_trade_matches_long_stop_bands():
    warning = evaluate_open_trade(trade(), 95)
    danger = evaluate_open_trade(trade(), 92)
    breached = evaluate_open_trade(trade(), 89)

    assert warning.stop_tone == "warning"
    assert warning.r_to_stop == pytest.approx(0.5)
    assert warning.dist_to_stop_pct == pytest.approx((95 - 90) / 95 * 100)
    assert danger.stop_tone == "danger"
    assert danger.r_to_stop == pytest.approx(0.2)
    assert breached.stop_tone == "breached"
    assert breached.r_to_stop == pytest.approx(-0.1)


def test_evaluate_open_trade_builds_target_ladder_and_next_target():
    row = evaluate_open_trade(trade(t1_price=110, t2_price=120), 108)

    assert row.next_target.label == "T1"
    assert row.target_ladder[0].hit is False
    assert row.target_ladder[0].r_to_target == pytest.approx(0.2)
    assert row.target_ladder[0].pct_to_target == pytest.approx((110 - 108) / 108 * 100)

    hit = evaluate_open_trade(trade(t1_price=110, t2_price=120), 112)
    assert hit.target_ladder[0].hit is True
    assert hit.target_ladder[0].is_next is False
    assert hit.next_target.label == "T2"
    assert hit.next_target.r_to_target == pytest.approx(0.8)


def test_evaluate_open_trade_handles_short_stop_and_target_distance():
    row = evaluate_open_trade(
        trade(direction="SHORT", stop_loss=110, t1_price=90),
        95,
    )

    assert row.direction == "SHORT"
    assert row.r_to_stop == pytest.approx(1.5)
    assert row.dist_to_stop_pct == pytest.approx((110 - 95) / 95 * 100)
    assert row.next_target.label == "T1"
    assert row.next_target.r_to_target == pytest.approx(0.5)


def test_evaluate_open_trade_uses_remaining_qty_for_partial_status():
    row = evaluate_open_trade(trade(remaining_qty=5), 105)

    assert row.position == 5
    assert row.status == "partial"
    assert row.r_to_stop == pytest.approx(1.5)


def test_evaluate_open_trade_ignores_closed_or_unusable_risk_rows():
    assert evaluate_open_trade(trade(stop_loss=0), 105) is None
    assert evaluate_open_trade(trade(entry_price=90, stop_loss=90), 105) is None
    assert evaluate_open_trade(trade(closing_date="2026-06-10"), 105) is None
    assert evaluate_open_trade(trade(pnl=10), 105) is None
    assert evaluate_open_trade(trade(), None) is None
