"""
THE CONDUCTOR — runs the screen end to end.

This package owns data loading (``data.py``) and the orchestration that wires
the Structure Engine and the Scoring Engine together for every ticker
(``screener.py``). It holds no strategy opinion of its own.

Public API:
    run_screener -> (ranked_results_df, market_data, tickers)
"""
from core.pipeline.screener import run_screener

__all__ = ["run_screener"]
