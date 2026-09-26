import sys
from datetime import datetime, timedelta, timezone

import numpy as np
import pandas as pd

from _paths import REPO_ROOT as ROOT
sys.path.insert(0, str(ROOT))

from core.pipeline.universe import ticker_admission

UTC = timezone.utc
NOW = datetime(2026, 6, 25, 12, 0, tzinfo=UTC)


def _panel(close_by_ticker: dict[str, list[float]]) -> pd.DataFrame:
    idx = pd.date_range("2024-01-01", periods=max(len(v) for v in close_by_ticker.values()), freq="B")
    frames = {}
    for ticker, closes in close_by_ticker.items():
        padded = list(closes) + [np.nan] * (len(idx) - len(closes))
        frames[ticker] = pd.DataFrame({"Close": padded, "Volume": 1000}, index=idx)
    return pd.concat(frames, axis=1)


def test_screen_directory_rows_keeps_common_names_and_rejects_instruments():
    df = pd.DataFrame(
        [
            {"Symbol": "GOOGL", "Security Name": "Alphabet Inc. - Class A Common Stock"},
            {"Symbol": "ECHO", "Security Name": "EchoStar Corporation - Common stock"},
            {"Symbol": "GTERR", "Security Name": "Globa Terra Acquisition Corporation - Rights"},
            {"Symbol": "AACIW", "Security Name": "Armada Acquisition Corp. III - Warrant"},
            {
                "Symbol": "AGNCN",
                "Security Name": "AGNC Investment Corp. - Depositary Shares Each Representing a "
                                 "Preferred Stock",
            },
            {"Symbol": "AMPGZ", "Security Name": "Amplitech Group, Inc. - Series B Right"},
            {
                "Symbol": "AMX",
                "Security Name": "America Movil, S.A.B. de C.V. American Depositary Shares "
                                 "(each representing the right to receive shares)",
            },
        ]
    )

    tickers, stats, rejected = ticker_admission.screen_directory_rows(df)

    assert tickers == ["GOOGL", "ECHO", "AMX"]
    assert stats["special_issue"] == 2  # GTERR, AACIW
    assert stats["invalid_instrument"] == 2  # AGNCN, AMPGZ
    assert rejected["GTERR"]["reason"] == "special_issue_suffix"
    assert rejected["AGNCN"]["reason"] == "preferred"
    assert rejected["AMPGZ"]["reason"] == "rights"


def test_split_downloadable_respects_recheck_windows_and_indexes():
    store = {
        "YOUNG": {
            "status": ticker_admission.STATUS_YOUNG,
            "next_check": (NOW + timedelta(days=3)).isoformat(),
        },
        "EMPTY": {
            "status": ticker_admission.STATUS_EMPTY,
            "next_check": (NOW - timedelta(days=1)).isoformat(),
        },
        "BAD": {"status": ticker_admission.STATUS_INVALID},
    }

    active, skipped, counts = ticker_admission.split_downloadable(
        ["SPY", "READY", "YOUNG", "EMPTY", "BAD"],
        store,
        now=NOW,
        index_symbols=["SPY"],
    )

    assert active == ["SPY", "READY", "EMPTY"]
    assert skipped == ["YOUNG", "BAD"]
    assert counts == {
        ticker_admission.STATUS_YOUNG: 1,
        ticker_admission.STATUS_INVALID: 1,
    }


def test_record_history_results_classifies_ready_young_and_empty(monkeypatch):
    monkeypatch.setattr(ticker_admission.settings, "ADMISSION_MIN_HISTORY_BARS", 3, raising=False)
    monkeypatch.setattr(ticker_admission.settings, "ADMISSION_YOUNG_RECHECK_DAYS", 21, raising=False)
    monkeypatch.setattr(ticker_admission.settings, "ADMISSION_EMPTY_RECHECK_DAYS", 7, raising=False)
    panel = _panel({"READY": [1, 2, 3], "YOUNG": [1, 2]})

    store, summary = ticker_admission.record_history_results(
        {}, ["READY", "YOUNG", "EMPTY"], panel, now=NOW
    )

    assert summary == {
        ticker_admission.STATUS_READY: 1,
        ticker_admission.STATUS_YOUNG: 1,
        ticker_admission.STATUS_EMPTY: 1,
    }
    assert store["READY"]["status"] == ticker_admission.STATUS_READY
    assert store["YOUNG"]["status"] == ticker_admission.STATUS_YOUNG
    assert store["YOUNG"]["bars"] == 2
    assert store["EMPTY"]["status"] == ticker_admission.STATUS_EMPTY
