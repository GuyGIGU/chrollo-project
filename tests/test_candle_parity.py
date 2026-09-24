"""The fold's keeper (EC-3): ONE synthetic daily frame pushed through BOTH
candle wire paths — the scan-payload extraction (core/pipeline/screening/dashboard, driven
exactly as tests/test_dashboard_wire.py drives it) and the watchlist candle
endpoint — asserting the Daily/Weekly/Monthly candle and volume lists are
VALUE-equal: same date strings, same prices, same volumes, same caps.

Assertions are on outputs only — never on which module called which — so the
shared builder (core/pipeline/market_data/candles.py) can be refactored freely while any
second, drifting copy of a builder fails loudly here.

The frame carries the features that make drift visible:
- the REAL cache dtypes (float32 prices, nullable Int64 volume — what
  core/pipeline/market_data/cache.py's optimizer actually stores; a dtype-divergent
  path shows immediately),
- an all-NaN session mid-history (dropped by the shared price-subset prep)
  and a Volume-only-NaN session inside the daily window (KEPT, volume
  coerced to 0 — a real traded bar must never vanish over damaged volume),
- a partial final week (ends mid-week → forming weekly/monthly tail bars),
- length crossing EVERY tail cap (daily 300, weekly 110, monthly 60),
- and the BATCH leg: the card grid's producer serves the identical daily
  window (the review's finding 2 — cap parity pinned where the caps engage).

Deliberately NOT tested here: live divergence on the forming bar between a
days-old scan artifact and the fresh cache — that is correct behavior, not a
parity violation, and this test's single-fixture design cannot confuse the
two. Resample correctness anchors (hand-derived weekly extremes) live in
tests/test_htf.py and tests/test_candles_router.py.
"""
from __future__ import annotations

import sys
from collections import OrderedDict
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = ROOT / "webapp" / "backend"
sys.path.insert(0, str(ROOT))
sys.path.insert(1, str(BACKEND_DIR))

from core.pipeline.universe import descriptor as universe_mod  # noqa: E402
from core.pipeline.screening import dashboard as dashboard_module  # noqa: E402
from domains.market_data import watchlist_candles as wc  # noqa: E402

# 1700 business days ending mid-week (2026-08-12 is a Wednesday): crosses the
# 300-daily / 110-weekly / 60-monthly caps, ends on a partial week and month.
N_DAYS = 1700


def _awkward_frame() -> pd.DataFrame:
    idx = pd.bdate_range(end="2026-08-12", periods=N_DAYS, name="Date")
    step = np.arange(N_DAYS, dtype="float64")
    frame = pd.DataFrame({
        "Open": 20.0 + step * 0.01,
        "High": 20.6 + step * 0.01,
        "Low": 19.7 + step * 0.01,
        "Close": 20.3 + step * 0.01,
        "Volume": 1_000_000.0 + step * 13.0,
    }, index=idx).astype({
        # The REAL cache dtypes (core/pipeline/market_data/cache.py optimizer): float32
        # prices, nullable Int64 volume — the endpoint leg must read the
        # substrate production actually serves.
        "Open": "float32", "High": "float32", "Low": "float32",
        "Close": "float32", "Volume": "Int64",
    })
    # An all-NaN session mid-history: dropped whole (no prices = no bar).
    frame.iloc[500] = np.nan
    # Volume-only damage: mid-history AND inside the visible daily window —
    # both are real traded bars and must SURVIVE with volume coerced to 0.
    frame.iloc[800, frame.columns.get_loc("Volume")] = np.nan
    frame.iloc[-3, frame.columns.get_loc("Volume")] = np.nan
    return frame


def _scan_row(ticker: str) -> dict:
    """The minimal results row _extract_chart_data needs (the
    tests/test_dashboard_wire.py mold)."""
    return {
        "Ticker": ticker, "Tier": "A", "Score": 100, "Setup": "LPS",
        "Current Price": 30.0, "_trigger_price": 30.5, "_R": 30.0, "_S": 25.0,
        "_base_len": 8, "_lps_len": 2, "_lps_offset": 0,
        "_r_anchor_bar": 2, "_s_anchor_bar": 3, "_sub_scores": {},
    }


@pytest.fixture()
def endpoint_panel(monkeypatch, tmp_path):
    monkeypatch.setattr(
        universe_mod.Universe, "cache_paths",
        lambda self: (str(tmp_path / f"{self.key}.parquet"),
                      str(tmp_path / f"{self.key}.json")))
    monkeypatch.setattr(wc, "_frame_cache", OrderedDict())
    monkeypatch.setattr(wc, "_panel_tickers_cache", {})
    return tmp_path


def test_scan_payload_and_endpoint_candles_are_value_equal(
        monkeypatch, endpoint_panel):
    frame = _awkward_frame()

    # Path 1 — the scan writer, driven like test_dashboard_wire drives it.
    # Two tickers so the real multi-ticker panel branch (data[ticker]) runs.
    panel = pd.concat({"TPX": frame, "TOTHER": frame * 2.0}, axis=1)
    monkeypatch.setattr(dashboard_module, "_sector_etf_for_ticker",
                        lambda *_args: None)
    results = pd.DataFrame([_scan_row("TPX"), _scan_row("TOTHER")])
    scan_entry = dashboard_module._extract_chart_data(
        panel, results, ["TPX", "TOTHER"])["TPX"]

    # Path 2 — the endpoint, reading the SAME frame from a real tmp parquet.
    panel.to_parquet(endpoint_panel / "us_stocks.parquet")
    env = wc.ticker_candles("TPX")
    assert env["status"] == "ok"

    # Value equality, list for list. Any second builder that drifts one cap,
    # one rounding, or one calendar rule apart fails here.
    assert env["frames"]["daily"]["candles"] == scan_entry["candles"]
    assert env["frames"]["daily"]["volumes"] == scan_entry["volumes"]
    assert env["frames"]["weekly"]["candles"] == scan_entry["weekly_candles"]
    assert env["frames"]["weekly"]["volumes"] == scan_entry["weekly_volumes"]
    assert env["frames"]["monthly"]["candles"] == scan_entry["monthly_candles"]
    assert env["frames"]["monthly"]["volumes"] == scan_entry["monthly_volumes"]

    # The caps actually engaged (the frame is longer than every cap) — from
    # the ONE settings home on both paths.
    from config import settings
    assert len(scan_entry["candles"]) == settings.DASHBOARD_CHART_DAYS
    assert len(scan_entry["weekly_candles"]) == settings.DASHBOARD_CHART_WEEKS
    assert len(scan_entry["monthly_candles"]) == settings.DASHBOARD_CHART_MONTHS

    # The awkward features engaged: the all-NaN session is absent from both
    # paths identically (equality above); the Volume-only-NaN session inside
    # the window SURVIVED as a real bar with volume coerced to 0 — deleting
    # it would silently shift last_bar_date and every forming verdict; and
    # the mid-week end marks the endpoint's weekly + monthly tail bars
    # forming.
    damaged = [v for v in env["frames"]["daily"]["volumes"]
               if v["time"] == str(frame.index[-3])[:10]]
    assert damaged and damaged[0]["value"] == 0.0
    assert env["frames"]["weekly"]["forming_last_bar"] is True
    assert env["frames"]["monthly"]["forming_last_bar"] is True
    assert env["last_bar_date"] == "2026-08-12"

    # The BATCH leg (finding 2): the card grid's producer — through the SAME
    # over-cap frame — serves the identical daily window at the identical
    # cap. This is the exact axis that already diverged once (the removed
    # 130-bar strip window); re-introducing any tail-N split fails here.
    batch = wc.batch_candles(["TPX"])
    assert batch["tickers"]["TPX"]["status"] == "ok"
    assert batch["tickers"]["TPX"]["candles"] == env["frames"]["daily"]["candles"]
    assert batch["tickers"]["TPX"]["volumes"] == env["frames"]["daily"]["volumes"]
    assert len(batch["tickers"]["TPX"]["candles"]) == settings.DASHBOARD_CHART_DAYS
