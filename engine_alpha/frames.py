"""Frame-window helpers owned by the engine.

``_trim_to_period`` is the engine's own daily-structure windowing rule (the
2y trim every evaluation runs behind), relocated here from the download
plumbing so the pure frame->reading chain never imports the yfinance stack.
The download/cache side imports it back from here — one implementation
(EC-3), engine-owned because the trim defines what the reader SEES.
"""
from __future__ import annotations

import pandas as pd


def _trim_to_period(data: pd.DataFrame, period: str) -> pd.DataFrame:
    """Trim DataFrame index to the trailing period window (e.g., '2y')."""
    if data.empty:
        return data
    if period.endswith('y'):
        years = int(period[:-1])
        cutoff = data.index.max() - pd.Timedelta(days=365 * years + 5)
    elif period.endswith('mo'):
        months = int(period[:-2])
        cutoff = data.index.max() - pd.Timedelta(days=30 * months + 2)
    else:
        return data
    return data.loc[data.index >= cutoff]
