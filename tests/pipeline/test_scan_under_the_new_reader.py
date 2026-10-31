"""The walking skeleton: one fire, read by the reader, through the whole scan (go-live plan, task 2).

His ALB (the sealed fixture's bars, cut to Tue 07/04/2026, a day it fires) goes through the scan's own conductor,
`run_screener`, with a fake provider (prices and market cap) and the throwaway archive: the read, the $300M floor on
the fires after the read, and one archive row written by the real writer with the network cut off.

The pool: the scan's `ProcessPoolExecutor` is swapped for an in-process pool, as every scan test in this suite does.
What the real pool needs of the worker, that it pickles by name, is checked on its own below.

Never the live archive, never a booted app.
"""
from __future__ import annotations

import pickle
import sys

import pandas as pd
import pytest

from _paths import REPO_ROOT as ROOT
BACKEND_DIR = ROOT / "webapp" / "backend"
for _p in (str(ROOT), str(BACKEND_DIR)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import core.pipeline.screening.screener as screener_module  # noqa: E402
from config import settings  # noqa: E402

CHART = "ALB:2026-04-13"
FIRE_DAY = "2026-04-07"
BIG = 5e9          # far above the $300M floor
SMALL = 250e6      # under it


class _InlineFuture:
    def __init__(self, fn, *args):
        self._result = fn(*args)

    def result(self):
        return self._result


class _InlinePool:
    def __init__(self, max_workers=None):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def submit(self, fn, *args):
        return _InlineFuture(fn, *args)


def _alb() -> pd.DataFrame:
    from core.calibration.replay import load_sealed_fixture

    frames, _ = load_sealed_fixture()
    return frames[CHART].loc[:pd.Timestamp(FIRE_DAY)]


@pytest.fixture()
def scan(monkeypatch):
    """`run_screener` over his ALB alone; returns ``scan(cap)``.

    A one-ticker universe: the provider hands back the bare frame, as a download of one symbol does
    (the scan's frame prep reads a one-ticker panel as that frame; a two-level panel of one ticker
    would reach the reader with its columns still nested, and the reader would count it a crash)."""
    def run(cap: float, panel=None):
        panel = _alb() if panel is None else panel

        class Provider:
            def fetch(self, tickers, universe=None):
                return panel

            def market_cap(self, ticker):
                return cap

        monkeypatch.setattr(screener_module, "get_tickers", lambda *a, **k: ["ALB"])
        monkeypatch.setattr(screener_module, "get_provider", lambda: Provider())
        monkeypatch.setattr(screener_module, "eligible_tickers_for", lambda tickers, **k: list(tickers))
        monkeypatch.setattr(screener_module, "get_market_context",
                            lambda data, frames, *a, **k: {"spy_6m_return": 0.0, "breadth_pct": None})
        monkeypatch.setattr(screener_module, "persist_scan_metrics", lambda metrics, universe=None: None)
        monkeypatch.setattr(screener_module, "ProcessPoolExecutor", _InlinePool)
        monkeypatch.setattr(screener_module, "as_completed", lambda futures: list(futures))
        monkeypatch.setattr(settings, "FUNDAMENTALS_ENABLED", False)
        return screener_module.run_screener()

    return run


@pytest.fixture()
def scratch_archive(tmp_path, monkeypatch):
    """The real `archive_scan_results` against a throwaway file, every network call stubbed."""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    import archive_models
    import database
    from core.archive import writer as writer_mod

    engine = create_engine(f"sqlite:///{tmp_path / 'scratch_archive.db'}")
    archive_models.SetupArchive.metadata.create_all(bind=engine)
    monkeypatch.setattr(database, "make_sqlite_engine", lambda *a, **k: engine)
    monkeypatch.setattr(archive_models, "resolve_sector_etf", lambda t: (True, ""))
    monkeypatch.setattr(archive_models, "get_market_context", lambda d: {})
    monkeypatch.setattr(archive_models, "get_sector_trend", lambda *a, **k: None)
    monkeypatch.setattr(writer_mod, "load_sector_etf_cache", lambda *a, **k: {})
    monkeypatch.setattr(writer_mod, "save_sector_etf_cache", lambda *a, **k: None)

    def archive(results_df):
        written = writer_mod.archive_scan_results(results_df, scan_date_str=FIRE_DAY, enable=True)
        session = sessionmaker(bind=engine)()
        try:
            return written, session.query(archive_models.SetupArchive).all()
        finally:
            session.close()

    yield archive
    engine.dispose()


def test_the_new_reader_reads_his_alb_through_the_whole_scan(scan, scratch_archive, capsys):
    from engine_alpha.stamp import manifest_hash

    results_df, _, _, market_context = scan(BIG)

    log = capsys.readouterr().out
    assert log.count(f"Chart reader: {settings.TWO_EYES_RULESET}") == 1, "the night's ruleset is named once"
    assert "near_miss_lane" not in market_context and "near_miss_lane" not in market_context["_scan_metrics"]["counts"]

    assert list(results_df["Ticker"]) == ["ALB"], "the reader fires on his ALB that day"
    fire = results_df.iloc[0]
    assert "_wire_two_eyes" in results_df.columns, "the fire carries the reader's block"
    assert market_context["market_cap_floor"] == {
        "checked": 1, "refused": 0, "unknown": 0, "refused_tickers": []}
    assert fire["_market_cap"] == BIG

    written, rows = scratch_archive(results_df)
    assert written == 1 and len(rows) == 1
    row = rows[0]
    assert row.ticker == "ALB" and row.scan_date == FIRE_DAY
    assert row.engine_config_version == manifest_hash(), "the night's engine stamp"
    assert row.two_eyes_parent_r_price is not None and row.two_eyes_parent_s_price is not None
    assert row.two_eyes_parent_opened_date is not None
    assert row.two_eyes_has_mini in (0, 1), "the new reader looked for a mini (NULL = never looked)"


def test_the_floor_takes_a_new_reader_fire_under_300m_after_the_read(scan):
    results_df, _, _, market_context = scan(SMALL)
    assert results_df.empty
    assert market_context["market_cap_floor"] == {
        "checked": 1, "refused": 1, "unknown": 0, "refused_tickers": ["ALB"]}


def test_the_scans_worker_is_the_doors_own_and_pickles_by_name(monkeypatch):
    """What the real process pool needs: a module-level function it can send to a spawned worker, and an answer it
    can send back (a chart the reader would not read comes back as a record, named, by value). The scan submits
    ``gate.scan_read`` itself: substituting it is how every scan test here fakes the read."""
    from engine_alpha import gate

    assert pickle.loads(pickle.dumps(gate.scan_read)) is gate.scan_read
    seen = []

    def spy(ticker, df, spy_6m, breadth):
        seen.append((ticker, len(df)))
        return None

    monkeypatch.setattr(gate, "scan_read", spy)
    monkeypatch.setattr(screener_module, "ProcessPoolExecutor", _InlinePool)
    monkeypatch.setattr(screener_module, "as_completed", lambda futures: list(futures))
    results, errored = screener_module._evaluate_frames({"ALB": _alb()}, 0.0, None)
    assert (results, errored) == ([], 0) and seen == [("ALB", len(_alb()))]
    refused = gate.NotRead("ALB", "a trading day is missing from the middle", "a trading day is missing ...")
    assert pickle.loads(pickle.dumps(refused)) == refused


# --------------------------------------------------------------------------- #
# The live screen under the new reader (go-live plan task 3)                  #
# --------------------------------------------------------------------------- #
STOCK_KEYS = ("_stage2_ma_stack_pass", "_stage2_ma200_slope_1m_pct", "_stage2_52w_low_pct",
              "_stage2_trend_pass_count", "_stage2_trend_pass")
LEADERSHIP_KEYS = ("rs_rating", "stage2_trend_pass_count", "stage2_52w_low_pct", "stage2_ma200_slope_1m_pct",
                   "dollar_volume_50d")


def _card(monkeypatch, results_df, data) -> dict:
    from core.pipeline.screening import dashboard

    monkeypatch.setattr(dashboard, "_sector_etf_for_ticker", lambda *_a: None)
    return dashboard._extract_chart_data(data, results_df, ["ALB"])["ALB"]


def test_a_fire_carries_the_stocks_read(scan, monkeypatch):
    """His ALB on Tue 07/04/2026: the trend template on the fire (Minervini's seven, all passed, on the frame the
    door admitted) and the leadership cells on the card, pinned to the numbers the old reader's fire carried that
    day (the old reader retired Fri 30/10/2026; these were equal on both readers while it lived)."""
    new_df, new_data, _, _ = scan(BIG)
    assert "_wire_two_eyes" in new_df.columns

    fire = new_df.iloc[0]
    assert {k: fire[k] for k in STOCK_KEYS} == {
        "_stage2_ma_stack_pass": True, "_stage2_ma200_slope_1m_pct": 10.9013, "_stage2_52w_low_pct": 2.5106,
        "_stage2_trend_pass_count": 7, "_stage2_trend_pass": True}
    assert round(fire["_adr_pct"], 2) == 4.99

    card = _card(monkeypatch, new_df, new_data)
    assert "two_eyes" in card
    assert {k: card[k] for k in LEADERSHIP_KEYS} == {
        "rs_rating": 50.0,      # a one-stock universe: the stock sits at its own median
        "stage2_trend_pass_count": 7, "stage2_52w_low_pct": 2.5106,
        "stage2_ma200_slope_1m_pct": 10.9013, "dollar_volume_50d": 423037043}


def _with_a_day_missing() -> pd.DataFrame:
    """His ALB with one trading day deleted from the middle: what a halted name's frame looks like to the reader."""
    frame = _alb()
    return frame.drop(frame.index[len(frame) // 2])


def test_a_chart_the_new_reader_refuses_is_listed_by_name_and_reason_apart_from_crashes(scan, capsys):
    """27 charts on Thu 08/10/2026, every one a trading day missing from the middle: counted as swallowed crashes,
    they raised "possible silent winner drop" with their names lost. Now the night's record lists each by name and
    reason, apart from crashes, and the crash count (the alert's input) stays clean. The chart is not repaired."""
    results_df, _, _, market_context = scan(BIG, panel=_with_a_day_missing())

    assert results_df.empty, "a refused chart is not read, and not repaired"
    listed = market_context["not_read"]
    assert [(r["ticker"], r["rule"]) for r in listed] == [("ALB", "a trading day is missing from the middle")]
    assert listed[0]["reason"].startswith("a trading day is missing from the middle: 1 session(s) between ")
    counts = market_context["_scan_metrics"]["counts"]
    assert counts["not_read_tickers"] == 1 and counts["not_read"] == listed
    assert "errored_tickers" not in counts, "a refusal is not a swallowed crash: it may not raise the crash alert"
    log = capsys.readouterr().out
    assert "Charts not read: 1" in log and "ALB" in log.split("Charts not read: 1", 1)[1]


def test_a_real_crash_under_the_new_reader_is_still_a_crash(scan, monkeypatch):
    from engine_alpha import reader

    monkeypatch.setattr(reader, "read",
                        lambda ticker, df, **k: reader.crashed(ticker, None, "ZeroDivisionError: boom"))
    results_df, _, _, market_context = scan(BIG)
    assert results_df.empty
    assert market_context["_scan_metrics"]["counts"]["errored_tickers"] == 1, "the crash alert still hears it"
    assert "not_read" not in market_context and "not_read_tickers" not in market_context["_scan_metrics"]["counts"]

