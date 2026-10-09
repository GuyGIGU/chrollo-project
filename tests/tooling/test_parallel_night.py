"""One real scan night, read by both readers (task 15 of the two-eyes-reader build).

The plan's Done-when names it as the approval pack's last piece: *"a real scan night replayed by BOTH readers on a
COPIED panel, outside the scan slot, into side files only, with fires, the tally of state words and the wall
clock"*. Each clause is a test here: the slot is refused by the clock, only the copy is read and the source is left
byte for byte, nothing is written outside the folder named, every ticker is read by both readers through the one
door, the words add up, and each reader keeps its own wall clock.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import os

import numpy as np
import pandas as pd
import pytest

from tools.calibration import parallel_night as night


# --------------------------------------------------------------------------- #
# The slot                                                                     #
# --------------------------------------------------------------------------- #
def test_the_slot_is_the_scans_hour_and_the_two_after_it():
    from config import settings

    hour = int(settings.SCAN_SCHEDULE_HOUR_ET)
    day = dt.datetime(2026, 10, 9)
    assert not night.in_scan_slot(day.replace(hour=hour - 1, minute=59))
    assert night.in_scan_slot(day.replace(hour=hour, minute=0))
    assert night.in_scan_slot(day.replace(hour=hour + 1, minute=59))
    assert not night.in_scan_slot(day.replace(hour=hour + 2, minute=0))


def test_it_refuses_to_start_inside_the_slot(monkeypatch, tmp_path):
    from config import settings

    monkeypatch.setattr(night, "now_et", lambda: dt.datetime(2026, 10, 9, int(settings.SCAN_SCHEDULE_HOUR_ET), 30))
    out = tmp_path / "night"
    assert night.main([str(out), "--panel", str(tmp_path / "missing.parquet")]) != 0
    assert not out.exists(), "a refused night writes nothing"


# --------------------------------------------------------------------------- #
# A small panel, shaped as the scan's cache is                                 #
# --------------------------------------------------------------------------- #
def _panel(tmp_path) -> tuple[str, str]:
    """Two tickers and the two index symbols, 320 trading days, the cache's (ticker, field) columns; a meta file
    with no ledgers beside it (every ticker eligible)."""
    rng = np.random.default_rng(20261009)
    days = pd.bdate_range(end=pd.Timestamp("2026-10-08"), periods=320)
    frames = {}
    for i, ticker in enumerate(("AAA", "BBB", "SPY", "QQQ")):
        close = 50.0 + i + np.cumsum(rng.normal(0.05, 0.6, len(days)))
        frames[ticker] = pd.DataFrame({"Open": close, "High": close + 0.8, "Low": close - 0.8, "Close": close,
                                       "Volume": 2_000_000.0}, index=days)
    data = pd.concat(frames, axis=1)
    source = tmp_path / "source"
    source.mkdir()
    panel = source / "market_data_cache_5y.parquet"
    data.to_parquet(panel)
    meta = source / "cache_meta.json"
    meta.write_text(json.dumps({"last_session": "2026-10-08"}), encoding="utf-8")
    return str(panel), str(meta)


def _sha(path: str) -> str:
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


@pytest.fixture()
def outside_the_slot(monkeypatch):
    monkeypatch.setattr(night, "now_et", lambda: dt.datetime(2026, 10, 9, 7, 30))


def test_it_reads_a_copy_and_writes_side_files_only(tmp_path, outside_the_slot, monkeypatch):
    from core.pipeline.context import market_context

    # The scan's market-context helper writes a cache file wherever its setting points: it must point into OUT.
    writes = []
    real_write = market_context._write_meta
    monkeypatch.setattr(market_context, "_write_meta",
                        lambda path, payload: writes.append(os.path.abspath(path)) or real_write(path, payload))
    panel, meta = _panel(tmp_path)
    before = (_sha(panel), os.path.getmtime(panel))
    out = tmp_path / "night"
    summary = night.replay(panel, str(out), meta=meta, workers=0)

    assert (_sha(panel), os.path.getmtime(panel)) == before, "the source panel is left byte for byte"
    copy = summary["panel"]["copy"]
    assert os.path.dirname(os.path.dirname(copy)) == str(out) and _sha(copy) == before[0]
    assert summary["panel"]["sha256"] == before[0]
    assert writes and all(os.path.commonpath([path, str(out)]) == str(out) for path in writes), writes
    written = sorted(os.path.relpath(os.path.join(root, f), out) for root, _, files in os.walk(out) for f in files)
    assert written == sorted([os.path.join("panel", "market_data_cache_5y.parquet"),
                              os.path.join("panel", "cache_meta.json"), os.path.join("panel", "market_context.json"),
                              "night.json", "night.txt"])
    assert not (tmp_path / "source" / "night.json").exists()
    on_disk = json.loads((out / "night.json").read_text(encoding="utf-8"))
    assert on_disk["night"] == "2026-10-08" and on_disk["panel"]["sha256"] == before[0]
    # EC-46: a sidecar is stamped with the engine's version under each reader.
    assert on_disk["readers"]["old"]["engine_config_version"] != on_disk["readers"]["new"]["engine_config_version"]


def test_only_the_copy_is_read(tmp_path, outside_the_slot, monkeypatch):
    """The source is moved away the moment it is copied: a night that still opened it would fall over."""
    panel, meta = _panel(tmp_path)
    real_copy = night.copy_panel

    def copy_then_hide(source, meta_file, out_dir):
        copied = real_copy(source, meta_file, out_dir)
        os.replace(source, source + ".hidden")
        os.replace(meta_file, meta_file + ".hidden")
        return copied

    monkeypatch.setattr(night, "copy_panel", copy_then_hide)
    summary = night.replay(panel, str(tmp_path / "night"), meta=meta, workers=0)
    assert summary["readers"]["old"]["read"] == 2


def test_both_readers_read_every_ticker_and_the_words_add_up(tmp_path, outside_the_slot):
    panel, meta = _panel(tmp_path)
    summary = night.replay(panel, str(tmp_path / "night"), meta=meta, workers=0)
    old, new = summary["readers"]["old"], summary["readers"]["new"]
    assert old["read"] == new["read"] == 2, "every ticker is read by both readers, the index symbols by neither"
    # The door's own stamp: each pass was read by the reader it is named for, never the other under its name.
    assert (old["answered_by"], new["answered_by"]) == (["old"], ["new"])
    for reader in (old, new):
        assert reader["read"] == len(reader["fires"]) + reader["silent"] + reader["failed"]
        assert reader["wall_clock_s"] > 0
        assert len(reader["slowest"]) <= 5
    # The new reader's words: every read it made has one, a failed read has none.
    assert sum(new["states"].values()) == new["read"] - new["failed"]
    assert set(new["states"]) <= set(night.STATE_WORDS)
    assert "states" not in old, "the old reader shows no word: his ten words are the new reader's"


def test_the_two_readers_fires_are_compared_name_by_name():
    def row(ticker, fired, **extra):
        return {"ticker": ticker, "fired": fired, "failed": False, "seconds": 0.1, "tier": "S" if fired else None,
                "score": 90.0 if fired else None, "trigger": 10.0 if fired else None, **extra}

    old = [row("AAA", True), row("BBB", True), row("CCC", False)]
    hole = "a trading day is missing from the middle: 1 session(s) between 2026-03-02 and 2026-03-04"
    new = [row("AAA", True, state="fired"), row("BBB", False, state="crossed"),
           row("CCC", True, state="fired"),
           {"ticker": "DDD", "fired": False, "failed": True, "seconds": 0.2, "why": hole},
           {"ticker": "EEE", "fired": False, "failed": True, "seconds": 0.2, "why": hole}]
    summary = night.summarize(old, 1.5, new, 2.5)
    assert summary["both"] == ["AAA"] and summary["old_only"] == ["BBB"] and summary["new_only"] == ["CCC"]
    assert summary["readers"]["new"]["states"] == {"fired": 2, "crossed": 1}
    assert summary["readers"]["new"]["failed"] == 2 and summary["readers"]["new"]["silent"] == 1
    # Each failed read keeps the reader's own sentence, and the night counts them by the rule that refused them.
    assert summary["readers"]["new"]["failures"] == [["DDD", hole], ["EEE", hole]]
    assert summary["readers"]["new"]["failure_reasons"] == {"a trading day is missing from the middle": 2}
    assert summary["readers"]["old"]["tiers"] == {"S": 2} and summary["readers"]["new"]["tiers"] == {"S": 2}
    assert (summary["readers"]["old"]["wall_clock_s"], summary["readers"]["new"]["wall_clock_s"]) == (1.5, 2.5)
    board = night.format_board(summary)
    assert "both readers fire on 1" in board and "the new reader alone on 1" in board
    assert "a trading day is missing from the middle 2" in board


def test_it_never_writes_under_a_sealed_directory(tmp_path, outside_the_slot):
    from tools._bootstrap import _PROJECT_ROOT

    panel, meta = _panel(tmp_path)
    with pytest.raises(ValueError, match="sealed"):
        night.replay(panel, os.path.join(_PROJECT_ROOT, "tests", "baselines", "night"), meta=meta, workers=0)
