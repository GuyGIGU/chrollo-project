"""Parity + behavior guard for the backend live-risk port.

This is the cutover gate for Trade Enrich — Layer A: it pins ``services.trade_risk``
(the Python single source of truth) against the JavaScript oracle it was ported
from (``webapp/frontend/src/utils/tradeTableUtils.js``). Every case mirrored from
``tradeTableUtils.test.js`` must hold BEFORE any frontend consumer is swapped, so
no displayed number silently changes — except the two settled additions
(planned_stop R-basis, pnlPct / distToStopR).

The module is loaded hermetically via importlib (it is stdlib-only) so the test
needs no ``sys.path`` surgery and cannot trip the backend-cwd ``config`` shadow.
Floats are compared with an absolute tolerance (price-derived ratios near O(1));
nulls are asserted with identity.
"""
import importlib.util
import math
from pathlib import Path

import pytest

_MOD_PATH = (
    Path(__file__).resolve().parent.parent
    / "webapp" / "backend" / "services" / "trade_risk.py"
)
_spec = importlib.util.spec_from_file_location("trade_risk_under_test", _MOD_PATH)
trade_risk = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(trade_risk)

derive_trade_risk = trade_risk.derive_trade_risk
build_open_risk_summary = trade_risk.build_open_risk_summary
is_option_symbol = trade_risk.is_option_symbol


BASE_TRADE = {
    "id": 1,
    "opening_date": "2026-06-01",
    "direction": "LONG",
    "ticker": "MSFT",
    "entry_price": 100,
    "stop_loss": 90,
    "quantity": 10,
    "commissions": 0,
    "pnl": None,
    "actions_json": None,
}


def _approx(value, expected):
    assert value is not None
    assert math.isclose(value, expected, abs_tol=1e-6), f"{value} should equal {expected}"


# --- parity with tradeTableUtils.test.js ---------------------------------------

def test_long_live_stop_distance_and_next_target():
    row = derive_trade_risk(
        {**BASE_TRADE, "t1_price": 110, "t2_price": 120}, live_price=105, live_source="yf",
    )
    _approx(row["rValue"], 0.5)
    _approx(row["rToStop"], 1.5)
    _approx(row["distToStopPct"], (105 - 90) / 105 * 100)
    assert row["nextTarget"]["label"] == "T1"
    _approx(row["distToTargetPct"], (110 - 105) / 105 * 100)
    assert row["targetLadder"][0]["isNext"] is True


def test_next_target_advances_after_prior_hit():
    row = derive_trade_risk(
        {**BASE_TRADE, "t1_price": 110, "t2_price": 120}, live_price=112, live_source="yf",
    )
    assert row["targetLadder"][0]["hit"] is True
    assert row["targetLadder"][0]["isNext"] is False
    assert row["nextTarget"]["label"] == "T2"
    _approx(row["distToTargetPct"], (120 - 112) / 112 * 100)


def test_short_trade_stop_and_target_distance():
    row = derive_trade_risk(
        {**BASE_TRADE, "direction": "SHORT", "stop_loss": 110, "t1_price": 90},
        live_price=95, live_source="yf",
    )
    _approx(row["rValue"], 0.5)
    _approx(row["rToStop"], 1.5)
    _approx(row["distToStopPct"], (110 - 95) / 95 * 100)
    assert row["nextTarget"]["label"] == "T1"
    _approx(row["distToTargetPct"], (95 - 90) / 95 * 100)


def test_empty_risk_fields_without_stop_or_targets():
    row = derive_trade_risk({**BASE_TRADE, "stop_loss": 0}, live_price=105, live_source="yf")
    assert row["rValue"] is None
    assert row["rToStop"] is None
    assert row["distToStopPct"] is None
    assert row["distToStopR"] is None
    assert row["nextTarget"] is None
    assert row["targetLadder"] == []


def test_partial_position_keeps_price_based_r_to_stop():
    row = derive_trade_risk(
        {
            **BASE_TRADE,
            "actions_json": '[{"side": "SELL", "quantity": 5, "price": 110, "date": "2026-06-05"}]',
        },
        live_price=105, live_source="yf",
    )
    assert row["openQty"] == 5
    assert row["status"] == "partial"
    _approx(row["rValue"], 0.75)
    # Price-based: (105 - 90) / (100 - 90) = 1.5, independent of the +50 booked.
    _approx(row["rToStop"], 1.5)


# --- new behavior: planned_stop R-basis, pnlPct, distToStopR --------------------

def test_r_multiple_anchors_to_planned_stop_distance_to_working_stop():
    # Stop trailed up to 95; original planned risk was entry->90.
    row = derive_trade_risk(
        {**BASE_TRADE, "stop_loss": 95, "planned_stop": 90}, live_price=110, live_source="yf",
    )
    # R-multiple uses the ORIGINAL risk (entry 100 -> planned 90 = 10): 100/(10*10) = 1.0
    _approx(row["rValue"], 1.0)
    # Distance-to-stop uses the CURRENT working stop (95): both % and R.
    _approx(row["distToStopPct"], (110 - 95) / 110 * 100)
    _approx(row["rToStop"], (110 - 95) / (100 - 95))  # 15 / 5 = 3.0
    _approx(row["distToStopR"], (110 - 95) / (100 - 95))
    _approx(row["stopVal"], 95)
    _approx(row["plannedStopVal"], 90)


def test_planned_stop_falls_back_to_working_stop_when_absent():
    # No planned_stop -> R basis is the working stop, identical to the JS oracle.
    row = derive_trade_risk({**BASE_TRADE, "t1_price": 110}, live_price=105, live_source="yf")
    _approx(row["rValue"], 0.5)
    _approx(row["plannedStopVal"], 90)


def test_pnl_pct_is_consistent_with_pnl_dollars():
    row = derive_trade_risk(BASE_TRADE, live_price=105, live_source="yf")
    _approx(row["pnl"], 50.0)            # (105-100)*10
    _approx(row["pnlPct"], 5.0)          # 50 / (100*10) * 100
    _approx(row["totalWorth"], 1000.0)


# --- degraded / null-price behavior --------------------------------------------

def test_missing_live_price_degrades_to_null_exit():
    row = derive_trade_risk({**BASE_TRADE, "t1_price": 110}, live_price=None, live_source=None)
    assert row["currentExit"] is None
    assert row["currentExitSource"] is None
    assert row["distToStopPct"] is None
    assert row["rToStop"] is None
    # Price-independent fields still derive from the entry/fills.
    assert row["status"] == "open"
    _approx(row["stopPct"], 10.0)        # |100-90|/100*100


def test_no_field_is_nan_or_inf_on_degenerate_input():
    # zero entry + zero stop: every numeric must be finite-or-None, never NaN/inf.
    row = derive_trade_risk(
        {**BASE_TRADE, "entry_price": 0, "stop_loss": 0}, live_price=0, live_source="yf",
    )
    for key, value in row.items():
        if isinstance(value, float):
            assert math.isfinite(value), f"{key} leaked a non-finite float: {value}"


# --- option multiplier + symbol parity -----------------------------------------

def test_option_symbol_detection_three_formats():
    assert is_option_symbol("AAPL 16JAN26 150 C") is True       # human
    assert is_option_symbol("AAPL  260116C00150000") is True     # IBKR local
    assert is_option_symbol("AAPL260116C00150000") is True       # OCC compact
    assert is_option_symbol("AAPL") is False
    assert is_option_symbol("") is False
    assert is_option_symbol(None) is False


# --- aggregate summary ---------------------------------------------------------

def test_full_closed_cycle_books_a_realized_win():
    # SELL-all closes the cycle from stored fills (no live price needed).
    row = derive_trade_risk(
        {**BASE_TRADE, "actions_json": '[{"side": "SELL", "quantity": 10, "price": 115, "date": "2026-06-09"}]'},
        live_price=None, live_source=None,
    )
    assert row["status"] == "win"
    _approx(row["pnl"], 150.0)         # (115 - 100) * 10, realized
    _approx(row["rValue"], 1.5)        # 150 / (10 * 10); planned falls back to stop_loss
    assert row["position"] == 0


def test_short_trade_planned_stop_basis():
    # SHORT entry 100, stop trailed to 105, original planned 110, live 95.
    row = derive_trade_risk(
        {**BASE_TRADE, "direction": "SHORT", "stop_loss": 105, "planned_stop": 110},
        live_price=95, live_source="yf",
    )
    _approx(row["rValue"], 0.5)        # pnl (100-95)*10=50 over original risk |100-110|*10=100
    _approx(row["distToStopPct"], (105 - 95) / 95 * 100)   # to the WORKING stop
    _approx(row["rToStop"], (105 - 95) / (105 - 100))      # 10 / 5 = 2.0, working basis
    _approx(row["plannedStopVal"], 110)
    _approx(row["stopVal"], 105)


def test_non_object_actions_json_degrades_without_crashing():
    # A valid array of non-object cells must be dropped, not raise (Leach P2).
    row = derive_trade_risk(
        {**BASE_TRADE, "actions_json": '[1, 2, "BUY"]'}, live_price=105, live_source="yf",
    )
    assert row["status"] == "open"     # falls back to the entry opener
    _approx(row["pnl"], 50.0)


def test_open_risk_summary_concrete_tone_counts():
    rows = [
        derive_trade_risk(BASE_TRADE, live_price=105, live_source="yf"),               # rToStop 1.5 -> no tone
        derive_trade_risk({**BASE_TRADE, "id": 2}, live_price=94, live_source="yf"),   # rToStop 0.4 -> warning
        derive_trade_risk({**BASE_TRADE, "id": 3}, live_price=92, live_source="yf"),   # rToStop 0.2 -> danger
        derive_trade_risk({**BASE_TRADE, "id": 4}, live_price=89, live_source="yf"),   # rToStop -0.1 -> breached
        # a fully closed trade must NOT count toward open risk
        derive_trade_risk(
            {**BASE_TRADE, "id": 5, "actions_json": '[{"side": "SELL", "quantity": 10, "price": 103}]'},
            live_price=None, live_source=None,
        ),
    ]
    summary = build_open_risk_summary(rows)
    assert summary["nOpen"] == 4       # the closed row is excluded
    assert summary["nPriced"] == 4
    assert summary["nWarning"] == 1
    assert summary["nDanger"] == 1
    assert summary["nBreached"] == 1
    assert summary["nAtRisk"] == 3
    _approx(summary["totalUnrealizedPnl"], (105 + 94 + 92 + 89 - 4 * 100) * 10)
