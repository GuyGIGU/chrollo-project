"""Service-shape guards for webapp.backend.services.market_data (Track C / C2).

The chart routes were refactored to route their single-symbol fetch + candle
shaping through this service instead of calling yfinance raw. These tests pin
that the service reproduces the EXACT payload the routes built inline before the
refactor — same fields, same colors, same int-vs-float volume, same row-skipping
— so the refactor is behavior-preserving. The provider is mocked; no network.
"""
import sys
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = ROOT / "webapp" / "backend"
sys.path.insert(0, str(ROOT))
sys.path.insert(1, str(BACKEND_DIR))

from webapp.backend.services import market_data as md_service


def _flat_ohlcv(rows):
    """Single-level-column OHLCV frame (the shape the provider returns after its
    MultiIndex flatten)."""
    idx = pd.to_datetime([r["time"] for r in rows])
    return pd.DataFrame(
        {
            "Open": [r["open"] for r in rows],
            "High": [r["high"] for r in rows],
            "Low": [r["low"] for r in rows],
            "Close": [r["close"] for r in rows],
            "Volume": [r["volume"] for r in rows],
        },
        index=idx,
    )


# ── Reference shapers: verbatim copies of the pre-refactor inline route logic ──
def _ref_ui_chart(raw):
    """The /market-data/chart route's original inline candle/volume builder."""
    def _is_number(value):
        import math
        try:
            return value is not None and math.isfinite(float(value))
        except (TypeError, ValueError):
            return False

    candles, volumes = [], []
    for timestamp, row in raw.iterrows():
        values = {name: row.get(name) for name in ("Open", "High", "Low", "Close")}
        if not all(_is_number(value) for value in values.values()):
            continue
        date = timestamp.strftime("%Y-%m-%d")
        close = float(values["Close"])
        candles.append({
            "time": date, "open": float(values["Open"]), "high": float(values["High"]),
            "low": float(values["Low"]), "close": close,
        })
        volume = row.get("Volume")
        if _is_number(volume):
            volumes.append({
                "time": date, "value": float(volume),
                "color": "rgba(95, 184, 130, 0.28)" if close >= float(values["Open"]) else "rgba(238, 99, 82, 0.28)",
            })
    return candles, volumes


def _ref_archive_chart(raw):
    """The archive setup-chart route's original inline candle/volume builder."""
    candles, volumes = [], []
    for dt, row in raw.iterrows():
        dt_str = dt.strftime("%Y-%m-%d")
        o = float(row["Open"]); h = float(row["High"]); l = float(row["Low"]); c = float(row["Close"])
        v = int(row["Volume"])
        candles.append({"time": dt_str, "open": o, "high": h, "low": l, "close": c})
        color = "rgba(38, 166, 154, 0.5)" if c >= o else "rgba(239, 83, 80, 0.5)"
        volumes.append({"time": dt_str, "value": v, "color": color})
    return candles, volumes


# ── chart_candles parity ───────────────────────────────────────────────────
def test_chart_candles_matches_ui_route_shape():
    raw = _flat_ohlcv([
        {"time": "2026-06-01", "open": 10.0, "high": 11.0, "low": 9.5, "close": 10.8, "volume": 1000},
        {"time": "2026-06-02", "open": 10.8, "high": 11.2, "low": 10.1, "close": 10.2, "volume": 1500},
    ])
    got = md_service.chart_candles(
        raw, up_color="rgba(95, 184, 130, 0.28)", down_color="rgba(238, 99, 82, 0.28)",
        require_finite=True, volume_as_int=False,
    )
    assert got == _ref_ui_chart(raw)
    # Up bar then down bar → green then red.
    _, volumes = got
    assert volumes[0]["color"] == "rgba(95, 184, 130, 0.28)"
    assert volumes[1]["color"] == "rgba(238, 99, 82, 0.28)"
    assert isinstance(volumes[0]["value"], float)


def test_chart_candles_ui_skips_nonfinite_rows():
    raw = _flat_ohlcv([
        {"time": "2026-06-01", "open": 10.0, "high": 11.0, "low": 9.5, "close": 10.8, "volume": 1000},
        {"time": "2026-06-02", "open": np.nan, "high": 11.2, "low": 10.1, "close": 10.2, "volume": 1500},
    ])
    candles, volumes = md_service.chart_candles(
        raw, up_color="g", down_color="r", require_finite=True, volume_as_int=False,
    )
    # The NaN-open row is dropped from both lists, exactly as the UI route did.
    assert candles == _ref_ui_chart(raw)[0]
    assert len(candles) == 1


def test_chart_candles_matches_archive_route_shape():
    raw = _flat_ohlcv([
        {"time": "2026-06-01", "open": 10.0, "high": 11.0, "low": 9.5, "close": 10.8, "volume": 1000},
        {"time": "2026-06-02", "open": 10.8, "high": 11.2, "low": 10.1, "close": 10.2, "volume": 1500},
    ])
    got = md_service.chart_candles(
        raw, up_color="rgba(38, 166, 154, 0.5)", down_color="rgba(239, 83, 80, 0.5)",
        require_finite=False, volume_as_int=True,
    )
    assert got == _ref_archive_chart(raw)
    _, volumes = got
    assert isinstance(volumes[0]["value"], int)  # archive route cast volume to int


# ── daily_candle_frame / latest_prices route through the provider ──────────
def test_daily_candle_frame_delegates_to_provider(monkeypatch):
    captured = {}

    def fake_get_provider():
        def daily_candles(symbol, days, *, start=None, end=None, auto_adjust=False):
            captured.update(symbol=symbol, days=days, start=start, end=end, auto_adjust=auto_adjust)
            return "FRAME"
        return SimpleNamespace(daily_candles=daily_candles)

    monkeypatch.setattr(md_service, "get_provider", fake_get_provider)
    out = md_service.daily_candle_frame("AAA", 200, start="2026-01-01", end="2026-06-01", auto_adjust=True)

    assert out == "FRAME"
    assert captured == {"symbol": "AAA", "days": 200, "start": "2026-01-01",
                        "end": "2026-06-01", "auto_adjust": True}


def test_latest_prices_delegates_to_provider(monkeypatch):
    captured = {}

    def fake_get_provider():
        def latest_price(symbols):
            captured["symbols"] = symbols
            return {"AAA": 1.0}
        return SimpleNamespace(latest_price=latest_price)

    monkeypatch.setattr(md_service, "get_provider", fake_get_provider)
    out = md_service.latest_prices(["AAA", "BBB"])

    assert out == {"AAA": 1.0}
    assert captured["symbols"] == ["AAA", "BBB"]


# ── Route-level: chart endpoint still returns the same JSON shape ──────────
def test_chart_route_returns_expected_payload(monkeypatch):
    from webapp.backend.routers import market_data as md_router

    raw = _flat_ohlcv([
        {"time": "2026-06-01", "open": 10.0, "high": 11.0, "low": 9.5, "close": 10.8, "volume": 1000},
    ])
    monkeypatch.setattr(md_router, "daily_candle_frame", lambda *a, **k: raw)

    payload = md_router.chart("aapl", days=180)

    assert payload["symbol"] == "AAPL"
    assert payload["candles"] == [
        {"time": "2026-06-01", "open": 10.0, "high": 11.0, "low": 9.5, "close": 10.8}
    ]
    assert payload["volumes"][0]["value"] == 1000.0
    assert payload["volumes"][0]["color"] == "rgba(95, 184, 130, 0.28)"
