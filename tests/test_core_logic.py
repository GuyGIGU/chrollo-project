import math
import sys
from pathlib import Path

import pandas as pd
import pytest
from fastapi import HTTPException

ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = ROOT / "webapp" / "backend"
sys.path.insert(0, str(ROOT))
sys.path.insert(1, str(BACKEND_DIR))

from core.structure.lps import detect_lps
from webapp.backend.routers.market_data import _clean_symbol, _is_number
from webapp.backend.routers.portfolio import _flatten_summary


def test_lps_trigger_uses_last_lps_bar_high():
    df = pd.DataFrame([
        {"High": 118, "Low": 115, "Close": 116, "Spread": 1, "Volume": 900, "Vol_50": 1000},
        {"High": 117, "Low": 115, "Close": 116, "Spread": 1, "Volume": 900, "Vol_50": 1000},
        {"High": 116, "Low": 115, "Close": 116, "Spread": 1, "Volume": 900, "Vol_50": 1000},
        {"High": 116, "Low": 115, "Close": 116, "Spread": 1, "Volume": 900, "Vol_50": 1000},
        {"High": 110, "Low": 106, "Close": 107, "Spread": 2, "Volume": 500, "Vol_50": 1000},
        {"High": 107, "Low": 103, "Close": 106, "Spread": 1, "Volume": 500, "Vol_50": 1000},
    ])

    result = detect_lps(
        df=df,
        latest=df.iloc[-1],
        sup_avg=100,
        res_avg=110,
        atr_val=2,
        base_range_threshold=10,
        base_len=20,
        swing_complete_idx=2,
    )

    assert result["trigger_price"] == 107


def test_flatten_summary_sums_numeric_values_and_ignores_unknown_tags():
    summary = {
        "DU1": {
            "NetLiquidation": {"value": "1000.50", "currency": "USD"},
            "AvailableFunds": {"value": "250", "currency": "USD"},
            "Ignored": {"value": "999", "currency": "USD"},
        },
        "DU2": {
            "NetLiquidation": {"value": "99.50", "currency": "USD"},
            "AvailableFunds": {"value": "not-ready", "currency": "USD"},
        },
    }

    flattened = _flatten_summary(summary)

    assert flattened["values"]["NetLiquidation"] == 1100
    assert flattened["values"]["AvailableFunds"] == 250
    assert "Ignored" not in flattened["values"]
    assert flattened["currency"]["NetLiquidation"] == "USD"
    assert flattened["raw"] == summary


@pytest.mark.parametrize(
    ("raw_symbol", "clean_symbol"),
    [("pep", "PEP"), (" brk.b ", "BRK.B"), ("abc-1", "ABC-1")],
)
def test_clean_symbol_accepts_supported_ticker_shapes(raw_symbol, clean_symbol):
    assert _clean_symbol(raw_symbol) == clean_symbol


@pytest.mark.parametrize("raw_symbol", ["", "../secrets", "AAPL$", "TOO-LONG-SYMBOL-123"])
def test_clean_symbol_rejects_unsafe_values(raw_symbol):
    with pytest.raises(HTTPException):
        _clean_symbol(raw_symbol)


@pytest.mark.parametrize("value", [0, "12.5", 7.0])
def test_is_number_accepts_finite_numeric_values(value):
    assert _is_number(value)


@pytest.mark.parametrize("value", [None, "nope", math.inf, math.nan])
def test_is_number_rejects_non_finite_values(value):
    assert not _is_number(value)
