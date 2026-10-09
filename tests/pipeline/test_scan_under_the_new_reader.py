"""The walking skeleton: one fire, read by the new reader, through the whole scan (go-live plan, task 2).

His ALB (the sealed fixture's bars, cut to Tue 07/04/2026, a day both readers fire) goes through the scan's own
conductor, `run_screener`, with a fake provider (prices and market cap) and the throwaway archive: the read, the
$300M floor on the fires after the read, and one archive row written by the real writer with the network cut off.
The switch is forced on inside the test only (it measures, it decides nothing); switched off, the same scan reads
the old way.

The pool: the scan's `ProcessPoolExecutor` is swapped for an in-process pool, as every scan test in this suite does
(tests/pipeline/test_near_miss_wiring.py, test_rescue_transport.py). A spawned worker would read the switch from the
config file, never from this test's patch. What the real pool needs of the worker, that it pickles by name, is
checked on its own below.

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
    """`run_screener` over his ALB alone; returns ``scan(cap, near_miss_sink)``.

    A one-ticker universe: the provider hands back the bare frame, as a download of one symbol does
    (the scan's frame prep reads a one-ticker panel as that frame; a two-level panel of one ticker
    would reach the reader with its columns still nested, and both readers would count it a crash)."""
    panel = _alb()

    def run(cap: float, near_miss_sink=None):
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
        return screener_module.run_screener(near_miss_sink=near_miss_sink)

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


def _new_reader(monkeypatch):
    monkeypatch.setattr(settings, "TWO_EYES_READER_ENABLED", True, raising=False)


def test_the_new_reader_reads_his_alb_through_the_whole_scan(scan, scratch_archive, monkeypatch, capsys):
    from engine_alpha.freeze.manifest import manifest_hash

    _new_reader(monkeypatch)
    assert settings.NEAR_MISS_LANE_ENABLED, "the near-miss lane is live; this test proves it goes quiet"
    sink = {"rows": [], "stats": {}}
    results_df, _, _, market_context = scan(BIG, near_miss_sink=sink)

    log = capsys.readouterr().out
    assert log.count("Chart reader: new") == 1, "the night's reader is named once"
    assert log.count("Near-miss lane: off under the new reader") == 1, "the quiet lane is said once"
    assert market_context["near_miss_lane"] == "off under the new reader"
    assert market_context["_scan_metrics"]["counts"]["near_miss_lane"] == "off under the new reader"
    assert sink == {"rows": [], "stats": {}}, "no old-chain twin ran beside the new reader"

    assert list(results_df["Ticker"]) == ["ALB"], "the new reader fires on his ALB that day"
    fire = results_df.iloc[0]
    assert "_wire_two_eyes" in results_df.columns, "the fire is the new reader's, not the old engine's"
    assert market_context["market_cap_floor"] == {
        "checked": 1, "refused": 0, "unknown": 0, "refused_tickers": []}
    assert fire["_market_cap"] == BIG

    written, rows = scratch_archive(results_df)
    assert written == 1 and len(rows) == 1
    row = rows[0]
    assert row.ticker == "ALB" and row.scan_date == FIRE_DAY
    assert row.engine_config_version == manifest_hash(), "the night's engine stamp, switch on"
    assert row.two_eyes_parent_r_price is not None and row.two_eyes_parent_s_price is not None
    assert row.two_eyes_parent_opened_date is not None
    assert row.two_eyes_has_mini in (0, 1), "the new reader looked for a mini (NULL = never looked)"


def test_the_floor_takes_a_new_reader_fire_under_300m_after_the_read(scan, monkeypatch):
    _new_reader(monkeypatch)
    results_df, _, _, market_context = scan(SMALL)
    assert results_df.empty
    assert market_context["market_cap_floor"] == {
        "checked": 1, "refused": 1, "unknown": 0, "refused_tickers": ["ALB"]}


def test_with_the_switch_off_the_same_scan_reads_the_old_way(scan, scratch_archive, monkeypatch, capsys):
    from engine_alpha.freeze.manifest import manifest_hash

    monkeypatch.setattr(settings, "TWO_EYES_READER_ENABLED", False, raising=False)
    sink = {"rows": [], "stats": {}}
    results_df, _, _, market_context = scan(BIG, near_miss_sink=sink)
    off_stamp = manifest_hash()     # after the scan's own settings (the fundamentals switch is in the stamp)

    log = capsys.readouterr().out
    assert log.count("Chart reader: old") == 1
    assert "Near-miss lane: off" not in log and "near_miss_lane" not in market_context
    assert "near_miss_lane" not in market_context["_scan_metrics"]["counts"]
    assert "records" in sink["stats"], "the live near-miss lane ran beside the old reader"
    assert list(results_df["Ticker"]) == ["ALB"]
    assert "_wire_two_eyes" not in results_df.columns

    written, rows = scratch_archive(results_df)
    assert written == 1
    row = rows[0]
    assert row.engine_config_version == off_stamp
    assert row.two_eyes_parent_r_price is None and row.two_eyes_has_mini is None

    _new_reader(monkeypatch)
    assert manifest_hash() != off_stamp, "the two readers' nights carry different stamps"


@pytest.mark.parametrize("flags, lane", [
    ({"LPS_LEAVES_ELECTION_ENABLED": True}, "watch lane"),
    ({"CONTRACTION_RESCUE_ENABLED": True}, "rescue lanes"),
    ({"BAR_POSTURE_RESCUE_ENABLED": True}, "rescue lanes"),
])
def test_a_dark_lane_switched_on_under_the_new_reader_refuses_the_scan_by_name(monkeypatch, flags, lane):
    """At the start of the scan, before a price is fetched: never a silent old-engine read."""
    from engine_alpha import reader

    class Untouchable:
        def fetch(self, tickers, universe=None):
            raise AssertionError("prices were fetched before the lane was refused")

    _new_reader(monkeypatch)
    for name, value in flags.items():
        monkeypatch.setattr(settings, name, value)
    monkeypatch.setattr(screener_module, "get_tickers", lambda *a, **k: ["ALB"])
    monkeypatch.setattr(screener_module, "get_provider", lambda: Untouchable())
    with pytest.raises(reader.LaneRefused) as refused:
        screener_module.run_screener()
    assert lane in str(refused.value) and next(iter(flags)) in str(refused.value)


def test_the_new_readers_scan_worker_is_the_doors_own_and_pickles_by_name(monkeypatch):
    """What the real process pool needs: a module-level function it can send to a spawned worker."""
    from engine_alpha import reader

    _new_reader(monkeypatch)
    worker = reader.scan_worker(near_miss_lane=False, watch_lane=False, rescue_lane=False)
    assert worker is reader.evaluate_ticker
    assert pickle.loads(pickle.dumps(worker)) is reader.evaluate_ticker
