"""The undo night: one command re-reads and re-shows a night, and archives nothing.

Go-live plan task 8. After a bad first night under the new reader, the undo
re-scans with the switch back off — and that re-scan must NOT archive, because
an archived re-scan of the same night would overwrite the evidence of the bad
one. The archive switch already exists as a setting; ``run_screener.py
--no-archive`` turns it off for that ONE process, says so on the record, and
edits no config file.

Hermetic: the screener and the dashboard writer are stubbed, and the archive
writers are replaced by spies that really write into a throwaway archive at
``CHROLLO_DB_PATH`` — so a leaked archive call changes the file's bytes, and the
control test proves the byte comparison can see one.
"""
from __future__ import annotations

import hashlib
import importlib
import json
import os
import sqlite3
import sys

import pandas as pd
import pytest

from _paths import REPO_ROOT as ROOT
sys.path.insert(0, str(ROOT))

import run_screener
from config import settings
from core.pipeline.screening import scan_job as sj


def _sha(path) -> str:
    return hashlib.sha256(open(path, "rb").read()).hexdigest()


def _seed_archive(path) -> None:
    """A throwaway archive with one row in each table the night could touch (the
    near-miss table is read-only history since the lane retired, and must stay so)."""
    with sqlite3.connect(path) as conn:
        conn.execute("CREATE TABLE setup_archive (ticker TEXT, scan_date TEXT)")
        conn.execute("CREATE TABLE near_miss_archive (ticker TEXT)")
        conn.execute("CREATE TABLE calibration_outcomes (mark_id INTEGER)")
        conn.execute("INSERT INTO setup_archive VALUES ('BAD', '2026-10-09')")
        conn.execute("INSERT INTO near_miss_archive VALUES ('BAD')")
        conn.execute("INSERT INTO calibration_outcomes VALUES (1)")
    conn.close()


def _wire_night(monkeypatch, tmp_path, results: pd.DataFrame) -> dict:
    db = tmp_path / "archive.db"
    _seed_archive(db)
    monkeypatch.setenv("CHROLLO_DB_PATH", str(db))
    # Restored at teardown whatever the command does to it in-process.
    monkeypatch.setattr(settings, "ARCHIVE_LIVE_SCANS", True)
    seen: dict = {"db": db, "dashboards": []}

    def _screener(mode="download", universe=None):
        return results, pd.DataFrame(), list(results.get("Ticker", [])), {"spy": 1}

    def _archive_spy(frame, scan_date_str=None, enable=False, universe=None, refused=None):
        if refused is not None:
            refused.update({"count": 0, "tickers": []})
        with sqlite3.connect(os.environ["CHROLLO_DB_PATH"]) as conn:
            conn.executemany("INSERT INTO setup_archive VALUES (?, ?)",
                             [(t, scan_date_str) for t in frame["Ticker"]])
        conn.close()
        return len(frame)

    monkeypatch.setattr(sj, "run_screener", _screener)
    monkeypatch.setattr(sj, "_passes_archive_freshness", lambda *a, **k: True)
    monkeypatch.setattr(sj, "_maybe_build_health_board", lambda *a, **k: None)
    monkeypatch.setattr(sj, "print_results", lambda *a, **k: None)
    monkeypatch.setattr(sj, "save_csv", lambda *a, **k: None)
    monkeypatch.setattr(sj, "print_finviz_url", lambda *a, **k: None)
    monkeypatch.setattr(sj, "archive_scan_results", _archive_spy)
    monkeypatch.setattr(
        sj, "generate_dashboard",
        lambda results_df, data, tickers, market_context, **k:
            seen["dashboards"].append((len(results_df), dict(market_context))))
    return seen


def _run(monkeypatch, *argv) -> None:
    monkeypatch.setattr(sys, "argv", ["run_screener.py", *argv])
    run_screener.main()


def _result_line(out: str) -> dict:
    line = next(l for l in out.splitlines() if l.startswith("SCAN_RESULT_JSON:"))
    return json.loads(line[len("SCAN_RESULT_JSON:"):])


_FIRED = pd.DataFrame({"Ticker": ["AAA", "BBB"]})
_EMPTY = pd.DataFrame()


@pytest.mark.parametrize("results", [_FIRED, _EMPTY], ids=["fires", "zero-fires"])
def test_the_undo_night_shows_the_read_and_leaves_the_archive_byte_identical(
        monkeypatch, tmp_path, capsys, results):
    seen = _wire_night(monkeypatch, tmp_path, results)
    config_files = [ROOT / "config" / "archive.py", ROOT / "config" / "settings.py"]
    before = _sha(seen["db"])
    config_before = [_sha(p) for p in config_files]

    _run(monkeypatch, "--cached", "--no-archive")

    out = capsys.readouterr().out
    # The archive: not one byte moved (fires, the near-miss history, calibration).
    assert _sha(seen["db"]) == before
    # The screen: rewritten with the re-read, and the payload says it is not archived.
    assert len(seen["dashboards"]) == 1
    n_shown, market_context = seen["dashboards"][0]
    assert n_shown == len(results)
    assert market_context.get("archived") is False
    assert market_context.get("spy") == 1          # the rest of the context rides unchanged
    # The record: the scan log says so, and so does the result line the service reads.
    assert "not archived" in out.lower()
    payload = _result_line(out)
    assert payload["archived"] is False
    assert payload["n_archived"] == 0
    assert payload["n_setups"] == len(results)
    # For THIS run only: no config file edited, the domain default still on.
    assert [_sha(p) for p in config_files] == config_before
    assert importlib.import_module("config.archive").ARCHIVE_LIVE_SCANS is True


def test_control_a_normal_night_does_write_the_archive(monkeypatch, tmp_path, capsys):
    """The byte comparison above can SEE an archive write: the same night without the
    flag changes the file — and its result line is byte-for-byte today's (no new key).
    Fires only: since the near-miss lane retired (Fri 30/10/2026) a zero-fire night
    writes nothing to the archive, so it has no write for the comparison to see."""
    results = _FIRED
    seen = _wire_night(monkeypatch, tmp_path, results)
    before = _sha(seen["db"])

    _run(monkeypatch, "--cached")

    out = capsys.readouterr().out
    assert _sha(seen["db"]) != before
    assert "archived" not in seen["dashboards"][0][1]
    assert "not archived" not in out.lower()
    assert "archived" not in _result_line(out)
