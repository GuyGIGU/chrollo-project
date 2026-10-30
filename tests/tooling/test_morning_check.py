"""The morning check (go-live plan task 9): a scanned night checks itself.

The morning after a night, one command replays the scan's own copied panel with the reader that scanned it, applies
the market-cap floor the way the scan did (its own recorded removals: no network), and says whether the night's
fires equal the replay, whether every fire is in the archive under that night's engine stamp (read READ-ONLY), and
which charts the scan could not read. A ledger beside the archive grows one line a night: "clean" or the named
difference. Throwaway files only: a tiny panel, a temp archive at ``CHROLLO_DB_PATH``.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
import sqlite3

import numpy as np
import pandas as pd
import pytest

from tools.ops import morning_check as morning

NIGHT = "2026-10-08"
HOLE = "a trading day is missing from the middle: 1 session(s) between 2026-03-02 and 2026-03-04"


# --------------------------------------------------------------------------- #
# Throwaway files: a tiny panel, the scan's payload, an archive                #
# --------------------------------------------------------------------------- #
def _panel(tmp_path, tickers=("AAA", "BBB", "CCC")) -> tuple[str, str]:
    rng = np.random.default_rng(20261010)
    days = pd.bdate_range(end=pd.Timestamp(NIGHT), periods=320)
    frames = {}
    for i, ticker in enumerate((*tickers, "SPY", "QQQ")):
        close = 50.0 + i + np.cumsum(rng.normal(0.05, 0.6, len(days)))
        frames[ticker] = pd.DataFrame({"Open": close, "High": close + 0.8, "Low": close - 0.8, "Close": close,
                                       "Volume": 2_000_000.0}, index=days)
    source = tmp_path / "source"
    source.mkdir()
    panel = source / "market_data_cache_5y.parquet"
    pd.concat(frames, axis=1).to_parquet(panel)
    meta = source / "cache_meta.json"
    meta.write_text(json.dumps({"last_session": NIGHT}), encoding="utf-8")
    return str(panel), str(meta)


def _payload(tmp_path, *, stamp, shown=("BBB",), removed=("AAA",), not_read=(), archived=None,
             night_day=NIGHT) -> str:
    context = {"market_cap_floor": {"checked": len(shown) + len(removed), "refused": len(removed), "unknown": 0,
                                    "refused_tickers": list(removed)},
               "_scan_metrics": {"counts": {"evaluated_tickers": 3}}}
    if not_read:
        context["not_read"] = [{"ticker": t, "rule": "frame", "reason": HOLE} for t in not_read]
    if archived is not None:
        context["archived"] = archived
    path = tmp_path / "screener_data.json"
    path.write_text(json.dumps({
        "chart_data": {t: {} for t in shown}, "ordered_tickers": list(shown), "market_context": context,
        "scan_identity": {"scan_date": night_day, "universe_type": "us_equities", "engine_config_version": stamp},
    }), encoding="utf-8")
    return str(path)


def _archive(tmp_path, monkeypatch, rows) -> str:
    db = tmp_path / "archive.db"
    with sqlite3.connect(db) as conn:
        conn.execute("CREATE TABLE setup_archive (ticker TEXT, scan_date TEXT, universe_type TEXT, source TEXT, "
                     "engine_config_version TEXT)")
        conn.executemany("INSERT INTO setup_archive VALUES (?, ?, 'us_equities', 'screener', ?)",
                         [(t, NIGHT, s) for t, s in rows])
    conn.close()
    monkeypatch.setenv("CHROLLO_DB_PATH", str(db))
    return str(db)


def _sha(path) -> str:
    return hashlib.sha256(open(path, "rb").read()).hexdigest()


@pytest.fixture()
def outside_the_slot(monkeypatch):
    monkeypatch.setattr(morning, "now_et", lambda: dt.datetime(2026, 10, 9, 7, 30))


@pytest.fixture()
def new_stamp():
    return morning._version()


def _scripted_reader(monkeypatch, fires=(), not_read=(), crashed=()):
    """The replay's reads, scripted per ticker (the reader itself is exercised by the last test)."""
    def read(ticker, df, spy, breadth):
        return {"ticker": ticker, "fired": ticker in fires, "crashed": ticker in crashed,
                "not_read": HOLE if ticker in not_read else None}
    monkeypatch.setattr(morning, "read_new", read)


def _run(tmp_path, panel, meta, payload) -> tuple[int, str]:
    out = tmp_path / "morning"
    code = morning.main([str(out), "--panel", panel, "--meta", meta, "--payload", payload, "--workers", "0"])
    return code, str(out)


def _ledger(out) -> list[str]:
    return open(os.path.join(out, "ledger.txt"), encoding="utf-8").read().splitlines()


# --------------------------------------------------------------------------- #
# The clock                                                                    #
# --------------------------------------------------------------------------- #
def test_the_slot_is_the_scans_hour_and_the_two_after_it():
    from config import settings

    hour = int(settings.SCAN_SCHEDULE_HOUR_ET)
    day = dt.datetime(2026, 10, 9, 0, 0)
    assert not morning.in_scan_slot(day.replace(hour=hour - 1, minute=59))
    assert morning.in_scan_slot(day.replace(hour=hour, minute=0))
    assert morning.in_scan_slot(day.replace(hour=hour + 1, minute=59))
    assert not morning.in_scan_slot(day.replace(hour=hour + 2, minute=0))


def test_it_refuses_inside_the_scan_slot(monkeypatch, tmp_path):
    from config import settings

    monkeypatch.setattr(morning, "now_et", lambda: dt.datetime(2026, 10, 9, int(settings.SCAN_SCHEDULE_HOUR_ET), 30))
    out = tmp_path / "morning"
    assert morning.main([str(out)]) == 2
    assert not out.exists(), "a refused morning writes nothing"


# --------------------------------------------------------------------------- #
# A clean night                                                                #
# --------------------------------------------------------------------------- #
def test_a_clean_night_says_clean_and_lists_the_charts_not_read(tmp_path, monkeypatch, outside_the_slot, new_stamp):
    panel, meta = _panel(tmp_path)
    payload = _payload(tmp_path, stamp=new_stamp, shown=("BBB",), removed=("AAA",), not_read=("CCC",))
    db = _archive(tmp_path, monkeypatch, [("BBB", new_stamp)])
    _scripted_reader(monkeypatch, fires=("AAA", "BBB"), not_read=("CCC",))
    archive_before = _sha(db)

    code, out = _run(tmp_path, panel, meta, payload)

    assert code == 0
    assert _sha(db) == archive_before, "the archive is read, never written"
    assert _ledger(out) == [f"{NIGHT} new {new_stamp[:8]} clean"]
    board = open(os.path.join(out, "nights", f"{NIGHT}.txt"), encoding="utf-8").read()
    assert "CCC" in board and HOLE in board, "the charts not read are listed, with the reason"
    record = json.load(open(os.path.join(out, "nights", f"{NIGHT}.json"), encoding="utf-8"))
    assert record["reader"] == "new" and record["differences"] == []
    # The floor was applied from the scan's own recorded removals (AAA fired in the replay, the floor took it out).
    assert record["floor"] == {"from": "the scan's recorded removals", "removed": ["AAA"]}


# --------------------------------------------------------------------------- #
# Every difference, named                                                      #
# --------------------------------------------------------------------------- #
def test_a_fire_the_screen_lacks_and_an_archive_row_under_another_stamp_are_named(
        tmp_path, monkeypatch, outside_the_slot, new_stamp):
    panel, meta = _panel(tmp_path)
    payload = _payload(tmp_path, stamp=new_stamp, shown=("BBB",), removed=())
    _archive(tmp_path, monkeypatch, [("BBB", "0ldst4mp" + "0" * 56)])
    _scripted_reader(monkeypatch, fires=("BBB", "CCC"))

    code, out = _run(tmp_path, panel, meta, payload)

    assert code == 1
    [line] = _ledger(out)
    assert line.startswith(f"{NIGHT} new {new_stamp[:8]} NOT CLEAN")
    assert "in the replay, not on the screen: CCC" in line
    assert "archived under another engine stamp: BBB" in line


def test_a_fire_missing_from_the_archive_and_a_not_read_mismatch_are_named(
        tmp_path, monkeypatch, outside_the_slot, new_stamp):
    panel, meta = _panel(tmp_path)
    payload = _payload(tmp_path, stamp=new_stamp, shown=("AAA", "BBB"), removed=(), not_read=("CCC",))
    _archive(tmp_path, monkeypatch, [("AAA", new_stamp)])
    _scripted_reader(monkeypatch, fires=("AAA", "BBB"))

    code, out = _run(tmp_path, panel, meta, payload)

    assert code == 1
    [line] = _ledger(out)
    assert "not in the archive: BBB" in line
    assert "not read by the scan, read by the replay: CCC" in line


def test_a_stamp_this_tree_does_not_give_is_named(tmp_path, monkeypatch, outside_the_slot):
    panel, meta = _panel(tmp_path)
    stranger = "deadbeef" + "0" * 56
    payload = _payload(tmp_path, stamp=stranger, shown=(), removed=())
    _archive(tmp_path, monkeypatch, [])
    _scripted_reader(monkeypatch)

    code, out = _run(tmp_path, panel, meta, payload)

    assert code == 1
    [line] = _ledger(out)
    assert line.startswith(f"{NIGHT} ? deadbeef NOT CLEAN") and "is not this tree's" in line


def test_an_undo_night_is_named_not_clean(tmp_path, monkeypatch, outside_the_slot, new_stamp):
    panel, meta = _panel(tmp_path)
    payload = _payload(tmp_path, stamp=new_stamp, shown=(), removed=(), archived=False)
    _archive(tmp_path, monkeypatch, [])
    _scripted_reader(monkeypatch)

    code, out = _run(tmp_path, panel, meta, payload)

    assert code == 1
    assert "not archived" in _ledger(out)[0]


def test_a_panel_of_another_night_is_not_replayed(tmp_path, monkeypatch, outside_the_slot, new_stamp):
    panel, meta = _panel(tmp_path)
    payload = _payload(tmp_path, stamp=new_stamp, shown=(), removed=(), night_day="2026-10-09")
    _archive(tmp_path, monkeypatch, [])
    reads = []
    monkeypatch.setattr(morning, "read_new", lambda *a: reads.append(a) or {})

    code, out = _run(tmp_path, panel, meta, payload)

    assert code == 1 and reads == [], "a panel of another night is named, never read"
    assert "the market data on disk ends 2026-10-08" in _ledger(out)[0]


def test_the_archive_is_opened_read_only(tmp_path, monkeypatch, outside_the_slot, new_stamp):
    """A read-only connection never creates a file: a missing archive is named, and stays missing."""
    panel, meta = _panel(tmp_path)
    payload = _payload(tmp_path, stamp=new_stamp, shown=("BBB",), removed=())
    missing = tmp_path / "no_archive.db"
    monkeypatch.setenv("CHROLLO_DB_PATH", str(missing))
    _scripted_reader(monkeypatch, fires=("BBB",))

    code, out = _run(tmp_path, panel, meta, payload)

    assert code == 1 and "the archive could not be read" in _ledger(out)[0]
    assert not missing.exists()


# --------------------------------------------------------------------------- #
# The ledger                                                                   #
# --------------------------------------------------------------------------- #
def test_the_ledger_grows_one_line_a_night_and_counts_the_clean_run(tmp_path):
    ledger = str(tmp_path / "ledger.txt")
    morning.write_ledger(ledger, "2026-10-12 new aaaaaaaa clean")
    morning.write_ledger(ledger, "2026-10-13 new aaaaaaaa NOT CLEAN - in the replay, not on the screen: X")
    morning.write_ledger(ledger, "2026-10-14 new aaaaaaaa clean")
    morning.write_ledger(ledger, "2026-10-15 new aaaaaaaa clean")
    # A second check of the same night replaces its line: one line a night.
    morning.write_ledger(ledger, "2026-10-15 new aaaaaaaa clean")
    lines = open(ledger, encoding="utf-8").read().splitlines()
    assert [l.split(" ", 1)[0] for l in lines] == ["2026-10-12", "2026-10-13", "2026-10-14", "2026-10-15"]
    assert morning.clean_run(lines) == 2


# --------------------------------------------------------------------------- #
# The real reader on the tiny panel                                            #
# --------------------------------------------------------------------------- #
def test_the_real_reader_replays_the_tiny_panel(tmp_path, monkeypatch, outside_the_slot, new_stamp):
    """No scripted reads: the scan's own worker reads the copied panel. In this seeded random walk the
    reader fires on CCC alone, so a screen that showed CCC, archived under this tree's stamp, is clean;
    the same screen without CCC is not."""
    panel, meta = _panel(tmp_path)
    payload = _payload(tmp_path, stamp=new_stamp, shown=("CCC",), removed=())
    _archive(tmp_path, monkeypatch, [("CCC", new_stamp)])
    before = _sha(panel)

    code, out = _run(tmp_path, panel, meta, payload)

    assert _sha(panel) == before, "only the copy is read"
    record = json.load(open(os.path.join(out, "nights", f"{NIGHT}.json"), encoding="utf-8"))
    assert record["read"] == 3 and record["replay_fires"] == ["CCC"]
    assert code == 0 and _ledger(out) == [f"{NIGHT} new {new_stamp[:8]} clean"]

    _payload(tmp_path, stamp=new_stamp, shown=(), removed=())
    code, out = _run(tmp_path, panel, meta, payload)
    assert code == 1 and "in the replay, not on the screen: CCC" in _ledger(out)[0]
