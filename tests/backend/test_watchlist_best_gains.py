"""The Watchlist's best-gain columns (his sheet's "% Best Diff", Fri 23/10/2026).

The calculation runs on a hand-built frame whose window edges fall on bars;
the route runs for real against a throwaway in-memory DB and a REAL parquet
panel in tmp_path, through the one seam the candle tests use
(Universe.cache_paths) — never the live cache, never a booted app.
"""
from __future__ import annotations

import sys
from collections import OrderedDict
from datetime import datetime

import pandas as pd
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from _paths import REPO_ROOT as ROOT
BACKEND_DIR = ROOT / "webapp" / "backend"
sys.path.insert(0, str(ROOT))
sys.path.insert(1, str(BACKEND_DIR))

import models  # noqa: E402
from core.pipeline.universe import descriptor as universe_mod  # noqa: E402
from domains.market_data import watchlist_candles as wc  # noqa: E402
from domains.watchlist import router as watchlist  # noqa: E402
from domains.watchlist.best_gains import FIELDS, best_gains  # noqa: E402

# Business days to Fri 23/10/2026, every high 100 and every close 99.5 except
# the named highs. Saved on the scan of Wed 01/07: the basis is that day's
# high (100), the add day is Thu 02/07, and the windows run through 04/07 (2),
# 09/07 (7), 16/07 (14), 01/08 (30) and 31/08 (60), each end day included. The
# first bar past each end carries a higher high that must not count.
HIGHS = {
    "2026-06-30": 500.0,   # before the scan day: not the basis
    "2026-07-02": 110.0,   # the add day itself, inside 2 days
    "2026-07-06": 115.0,   # past 2 days
    "2026-07-09": 120.0,   # the 7-day end, included
    "2026-07-10": 125.0,   # past 7 calendar days (inside 7 trading days)
    "2026-07-16": 130.0,   # the 14-day end, included
    "2026-07-17": 135.0,   # past 14 days
    "2026-07-31": 140.0,   # inside 30 days
    "2026-08-03": 145.0,   # past 30 days
    "2026-08-31": 150.0,   # the 60-day end, included
    "2026-09-01": 160.0,   # past 60 days
    "2026-09-15": 200.0,   # the best since the add
    "2026-10-21": 104.0,
    "2026-10-22": 102.0,
    "2026-10-23": 103.0,
}


def _frame():
    idx = pd.bdate_range("2026-06-01", "2026-10-23", name="Date")
    high = pd.Series(100.0, index=idx)
    for day, value in HIGHS.items():
        high[pd.Timestamp(day)] = value
    return pd.DataFrame({"Open": 99.0, "High": high, "Low": 98.0, "Close": 99.5, "Volume": 1000.0}, index=idx)


def test_each_window_is_the_best_high_from_the_add_day_against_the_scan_days_high():
    assert best_gains(_frame(), "2026-07-01") == {
        "since_add": 1.0, "d60": 0.5, "d30": 0.4, "d14": 0.3, "d7": 0.2, "d2": 0.1}


def test_a_young_save_shows_its_best_so_far_in_every_window():
    """Saved on Tue 20/10's scan: three trading days since, so every window holds them all
    (his HNGE: 21.24% since add, in 60 and in 30 days)."""
    assert best_gains(_frame(), "2026-10-20") == dict.fromkeys(FIELDS, 0.04)


def test_a_best_high_under_the_basis_is_negative_not_hidden():
    assert best_gains(_frame(), "2026-10-21")["since_add"] == round(103.0 / 104.0 - 1, 6)


@pytest.mark.parametrize("day", ["2026-10-23", None, ""])
def test_no_scan_day_or_no_bar_since_is_null_never_a_substitute(day):
    assert best_gains(_frame(), day) == dict.fromkeys(FIELDS)


def test_no_frame_is_null():
    assert best_gains(None, "2026-07-01") == dict.fromkeys(FIELDS)


# ── the route, end to end ───────────────────────────────────────────────────

@pytest.fixture()
def db():
    engine = create_engine("sqlite:///:memory:")
    models.Base.metadata.create_all(bind=engine)
    sess = sessionmaker(bind=engine)()
    yield sess
    sess.close()
    engine.dispose()


@pytest.fixture()
def panel(monkeypatch, tmp_path):
    """A real us_stocks parquet panel holding NVDA and MSFT, behind the candle tests' one seam.
    Returns the list of daily_frames calls the route made."""
    def fake_cache_paths(self):
        d = tmp_path / self.key
        d.mkdir(exist_ok=True)
        return (str(d / "panel.parquet"), str(d / "meta.json"))

    monkeypatch.setattr(universe_mod.Universe, "cache_paths", fake_cache_paths)
    monkeypatch.setattr(wc, "_frame_cache", OrderedDict())
    monkeypatch.setattr(wc, "_panel_tickers_cache", {})
    (tmp_path / "us_stocks").mkdir()
    pd.concat({"NVDA": _frame(), "MSFT": _frame()}, axis=1).to_parquet(tmp_path / "us_stocks" / "panel.parquet")
    asked = []
    real = wc.daily_frames
    monkeypatch.setattr(wc, "daily_frames", lambda tickers, pins=None: asked.append((sorted(tickers), pins)) or real(tickers, pins))
    return asked


def _watch(db, ticker, scan_date=None):
    pinned = scan_date is not None
    db.add(models.Watchlist(ticker=ticker, save_date="2026-07-02", saved_at=datetime(2026, 7, 2, 6),
                            origin="user", pin_scan_date=scan_date,
                            pin_universe_type="us_equities" if pinned else None,
                            pin_setup_type="LPS" if pinned else None,
                            pin_engine_config_version="manifest-abc" if pinned else None))
    db.commit()


def test_the_route_measures_each_active_save_and_names_every_gap(db, panel):
    _watch(db, "NVDA", "2026-07-01")
    _watch(db, "MSFT", "2026-10-23")    # saved on the panel's last bar
    _watch(db, "ZZZZ", "2026-07-01")    # not in any panel
    _watch(db, "AAPL")                  # starred without a scan
    out = {t: watchlist.BestGainsOut(**v).model_dump() for t, v in watchlist.watchlist_best_gains(db).items()}
    assert out["NVDA"] == {"status": "ok", "last_bar_date": "2026-10-23", "since_add": 1.0,
                           "d60": 0.5, "d30": 0.4, "d14": 0.3, "d7": 0.2, "d2": 0.1}
    assert out["MSFT"] == {"status": "no_bar_since_scan", "last_bar_date": "2026-10-23", **dict.fromkeys(FIELDS)}
    assert out["ZZZZ"] == {"status": "unknown_ticker", "last_bar_date": None, **dict.fromkeys(FIELDS)}
    assert out["AAPL"] == {"status": "no_pin", "last_bar_date": None, **dict.fromkeys(FIELDS)}
    # One batched read, for the pinned saves only, each from its own pinned panel.
    assert panel == [(["MSFT", "NVDA", "ZZZZ"], {"NVDA": "us_stocks", "MSFT": "us_stocks", "ZZZZ": "us_stocks"})]


def test_an_unpinned_watchlist_reads_no_panel(db, panel):
    _watch(db, "AAPL")
    assert watchlist.watchlist_best_gains(db)["AAPL"]["status"] == "no_pin"
    assert panel == []
