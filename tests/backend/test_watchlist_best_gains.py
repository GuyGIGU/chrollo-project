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
from domains.watchlist.best_gains import FIELDS, best_gains, price_facts  # noqa: E402

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


WEEK = "2026-06-29"
NO_FACTS = {"basis": None, "prev_close": None, "dist_52w_high": None}


def _watch(db, ticker, scan_date=None, basis_scan_date=None):
    pinned = scan_date is not None
    db.add(models.Watchlist(ticker=ticker, save_date="2026-07-02", saved_at=datetime(2026, 7, 2, 6),
                            origin="user", pin_scan_date=scan_date, week_start=WEEK,
                            basis_scan_date=basis_scan_date,
                            pin_universe_type="us_equities" if pinned else None,
                            pin_setup_type="LPS" if pinned else None,
                            pin_engine_config_version="manifest-abc" if pinned else None))
    db.commit()


@pytest.fixture()
def friday(monkeypatch):
    """The live quote belongs to Fri 23/10: Change % divides by Thursday's close."""
    monkeypatch.setattr(watchlist, "_session_day", lambda: "2026-10-23")


def test_the_route_measures_each_save_of_the_week_and_names_every_gap(db, panel, friday):
    _watch(db, "NVDA", "2026-07-01")
    _watch(db, "MSFT", "2026-10-23")    # saved on the panel's last bar
    _watch(db, "ZZZZ", "2026-07-01")    # not in any panel
    _watch(db, "AAPL")                  # saved with no scan at all, and no price history
    out = {t: watchlist.BestGainsOut(**v).model_dump()
           for t, v in watchlist.watchlist_best_gains(db, week=WEEK).items()}
    facts = {"prev_close": 99.5, "dist_52w_high": round((99.5 - 500.0) / 500.0, 12)}
    out["NVDA"]["dist_52w_high"] = round(out["NVDA"]["dist_52w_high"], 12)
    out["MSFT"]["dist_52w_high"] = round(out["MSFT"]["dist_52w_high"], 12)
    assert out["NVDA"] == {"status": "ok", "last_bar_date": "2026-10-23", "since_add": 1.0,
                           "d60": 0.5, "d30": 0.4, "d14": 0.3, "d7": 0.2, "d2": 0.1,
                           "basis": 100.0, **facts}
    assert out["MSFT"] == {"status": "no_bar_since_scan", "last_bar_date": "2026-10-23",
                           **dict.fromkeys(FIELDS), "basis": 103.0, **facts}
    assert out["ZZZZ"] == {"status": "unknown_ticker", "last_bar_date": None, **dict.fromkeys(FIELDS), **NO_FACTS}
    assert out["AAPL"] == {"status": "unknown_ticker", "last_bar_date": None, **dict.fromkeys(FIELDS), **NO_FACTS}
    # One batched read for every save of the week, each from its own pinned panel.
    assert panel == [(["AAPL", "MSFT", "NVDA", "ZZZZ"],
                      {"NVDA": "us_stocks", "MSFT": "us_stocks", "ZZZZ": "us_stocks", "AAPL": None})]


def test_a_typed_in_ticker_measures_from_the_scan_on_screen_when_it_was_saved(db, panel, friday):
    """Not in the scan, so no pin: the basis is still the day before the add."""
    _watch(db, "NVDA", basis_scan_date="2026-07-01")
    _watch(db, "MSFT")                  # a legacy save with no scan: price facts only
    out = watchlist.watchlist_best_gains(db, week=WEEK)
    assert out["NVDA"]["status"] == "ok"
    assert (out["NVDA"]["since_add"], out["NVDA"]["basis"]) == (1.0, 100.0)
    assert out["MSFT"]["status"] == "no_pin"
    assert (out["MSFT"]["since_add"], out["MSFT"]["basis"], out["MSFT"]["prev_close"]) == (None, None, 99.5)


def test_change_divides_by_the_close_before_the_quotes_trading_day():
    frame = _frame()
    frame.loc[pd.Timestamp("2026-10-22"), "Close"] = 101.0
    frame.loc[pd.Timestamp("2026-10-23"), "Close"] = 103.0
    assert price_facts(frame, "2026-07-01", "2026-10-23")["prev_close"] == 101.0  # Friday's quote
    assert price_facts(frame, "2026-07-01", "2026-10-26")["prev_close"] == 103.0  # Monday's quote
    # The 52-week distance is the engine's own, at the last close.
    assert price_facts(frame, None, "2026-10-26")["dist_52w_high"] == (103.0 - 500.0) / 500.0
    assert price_facts(frame, None, "2026-10-26")["basis"] is None


def test_a_weekend_quote_belongs_to_friday():
    from datetime import datetime as dt
    assert watchlist._session_day(dt(2026, 10, 24, 12)) == "2026-10-23"  # Saturday
    assert watchlist._session_day(dt(2026, 10, 25, 12)) == "2026-10-23"  # Sunday
    assert watchlist._session_day(dt(2026, 10, 27, 12)) == "2026-10-27"  # Tuesday


def test_before_the_open_the_quote_still_belongs_to_the_last_session():
    """Pre-market the quote is the last close: Change % is that session's move, never 0.00%."""
    from datetime import datetime as dt
    assert watchlist._session_day(dt(2026, 10, 27, 9, 29)) == "2026-10-26"  # Tuesday pre-open
    assert watchlist._session_day(dt(2026, 10, 27, 9, 30)) == "2026-10-27"  # the open
    assert watchlist._session_day(dt(2026, 10, 26, 8, 0)) == "2026-10-23"  # Monday pre-open: Friday
