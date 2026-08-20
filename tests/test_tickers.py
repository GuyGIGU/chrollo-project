import os
import sys
import time
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import core.pipeline.tickers as tickers_module
from core.pipeline import ticker_admission
from config import settings


def test_filter_tickers_skips_special_issues_but_keeps_real_five_letter_names():
    tickers, stats = ticker_admission.screen_symbols(
        ["AAPL", "GOOGL", "GTERR", "AACBU", "AACIW", "BRK.B", "TOOLONG", "ECHO", "aapl"],
        {"ECHO"},
    )

    assert tickers == ["AAPL", "GOOGL"]
    assert stats["special_issue"] == 3
    assert stats["manual_skip"] == 1
    assert stats["invalid"] == 2
    assert stats["duplicate"] == 1


def test_load_skiplist_ignores_comments_and_normalizes_symbols(tmp_path):
    path = tmp_path / "ticker_skiplist.txt"
    path.write_text(
        "# known dead symbols\n"
        "gterr  # rights issue\n"
        "\n"
        "echo\n",
        encoding="utf-8",
    )

    assert tickers_module._load_skiplist(str(path)) == {"GTERR", "ECHO"}


def test_get_tickers_filters_cached_csv_before_returning(tmp_path, monkeypatch):
    csv_path = tmp_path / "tickers.csv"
    pd.DataFrame({"Ticker": ["AAPL", "GOOGL", "GTERR", "AACIW", "SKIPME"]}).to_csv(
        csv_path, index=False
    )
    monkeypatch.setattr(settings, "TICKER_CACHE_MAX_AGE_DAYS", 999, raising=False)
    monkeypatch.setattr(tickers_module, "_load_skiplist", lambda: {"SKIPME"})

    assert tickers_module.get_tickers(str(csv_path)) == ["AAPL", "GOOGL"]


def test_get_tickers_uses_stale_csv_when_ftp_refresh_fails(tmp_path, monkeypatch):
    csv_path = tmp_path / "tickers.csv"
    pd.DataFrame({"Ticker": ["AAPL", "GOOGL", "MSFT"]}).to_csv(csv_path, index=False)
    stale = time.time() - 30 * 24 * 3600
    os.utime(csv_path, (stale, stale))
    monkeypatch.setattr(settings, "TICKER_CACHE_MAX_AGE_DAYS", 1, raising=False)
    monkeypatch.setattr(tickers_module, "_load_skiplist", lambda: set())

    real_read_csv = pd.read_csv

    def fail_ftp_read_csv(path, *args, **kwargs):
        if isinstance(path, str) and path.startswith("ftp://"):
            raise OSError("FTP unreachable")
        return real_read_csv(path, *args, **kwargs)

    monkeypatch.setattr(tickers_module.pd, "read_csv", fail_ftp_read_csv)

    assert tickers_module.get_tickers(str(csv_path)) == ["AAPL", "GOOGL", "MSFT"]
