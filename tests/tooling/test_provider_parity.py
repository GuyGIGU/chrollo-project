import sys

import numpy as np
import pandas as pd

from _paths import REPO_ROOT as ROOT
sys.path.insert(0, str(ROOT))

from tools.audits.provider_parity import _adjustment_fingerprint, price_parity, verdict


def _panel(close_by_ticker: dict) -> pd.DataFrame:
    """Build a canonical (ticker, field) panel from a {ticker: close-array} map."""
    idx = pd.date_range("2024-01-01", periods=120, freq="B")
    frames = {}
    for ticker, close in close_by_ticker.items():
        c = pd.Series(close, index=idx, dtype="float64")
        frames[ticker] = pd.DataFrame(
            {"Open": c, "High": c * 1.01, "Low": c * 0.99, "Close": c, "Volume": 1000.0}
        )
    return pd.concat(frames, axis=1)


def test_price_parity_separates_clean_from_adjustment_mismatch():
    base = np.linspace(100.0, 140.0, 120)
    left = _panel({"AAA": base, "BBB": base * 2.0})
    right = _panel({"AAA": base, "BBB": base})  # BBB right is a constant 0.5x of left
    res = price_parity(left, right, ["AAA", "BBB"])
    by = {r["ticker"]: r["verdict"] for r in res["rows"]}
    assert by["AAA"] == "clean"
    assert by["BBB"] == "adjustment_mismatch"


def test_price_parity_reports_missing_side():
    base = np.linspace(10.0, 12.0, 120)
    left = _panel({"AAA": base, "BBB": base})
    right = _panel({"AAA": base})
    res = price_parity(left, right, ["AAA", "BBB"])
    assert res["missing"] == ["BBB"]
    assert [r["ticker"] for r in res["rows"]] == ["AAA"]


def test_adjustment_fingerprint_detects_constant_ratio():
    idx = pd.date_range("2024-01-01", periods=50, freq="B")
    c = pd.Series(np.linspace(10.0, 20.0, 50), index=idx)
    drift, is_constant = _adjustment_fingerprint(c, c * 0.5)
    assert is_constant
    assert abs(drift - 0.5) < 1e-9


def test_adjustment_fingerprint_ignores_noise():
    idx = pd.date_range("2024-01-01", periods=50, freq="B")
    c = pd.Series(np.linspace(10.0, 20.0, 50), index=idx)
    # Tiny non-constant jitter is not a systematic adjustment offset.
    jitter = c * (1.0 + np.linspace(-0.0001, 0.0001, 50))
    drift, _ = _adjustment_fingerprint(c, jitter)
    assert drift < 0.005


def test_verdict_fails_on_adjustment_mismatch():
    price = {"rows": [{"ticker": "X", "verdict": "adjustment_mismatch"}]}
    ok, reasons = verdict(price, {"drift": False})
    assert not ok and reasons


def test_verdict_fails_on_engine_drift():
    price = {"rows": [{"ticker": "X", "verdict": "clean"}]}
    ok, _ = verdict(price, {"drift": True})
    assert not ok


def test_verdict_passes_when_clean():
    price = {"rows": [{"ticker": "X", "verdict": "clean"}]}
    ok, reasons = verdict(price, {"drift": False})
    assert ok and not reasons
