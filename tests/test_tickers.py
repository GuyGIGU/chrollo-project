import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from core.pipeline.tickers import get_tickers


def test_get_tickers_filters_and_rewrites_cached_universe(tmp_path):
    csv_path = tmp_path / "tickers.csv"
    pd.DataFrame({
        "Ticker": [
            "AAPL",
            "GOOGL",
            "msft",
            "BRK.B",
            "ABCDE",
            "TSLA",
            "TSLA",
            "F",
        ]
    }).to_csv(csv_path, index=False)

    tickers = get_tickers(str(csv_path))

    assert tickers == ["AAPL", "MSFT", "TSLA", "F"]
    rewritten = pd.read_csv(csv_path)["Ticker"].tolist()
    assert rewritten == tickers
