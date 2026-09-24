"""
THE CONDUCTOR — runs the screen end to end.

The public data doorway is ``data.py``. ``market_data/`` owns acquisition and
cache health, ``universe/`` owns symbol membership, and ``context/`` owns market
regime. ``screening/`` coordinates evaluation, payload assembly, and archiving;
``telemetry/`` records stage timings. This package holds no strategy opinion.

Public API:
    run_screener -> (ranked_results_df, market_data, tickers)

``run_screener`` is re-exported LAZILY (PEP 562): the eager import dragged
``screener`` -> ``engine_alpha.evaluation`` -> the whole reading engine into
every ``core.pipeline.*`` import — including the FastAPI boot path, which
must stay engine-free (a backend restart must never pay the pandas/scipy
engine import, and engine import failures must never block the journal).
"""


def __getattr__(name):
    if name == "run_screener":
        from core.pipeline.screening.screener import run_screener
        return run_screener
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = ["run_screener"]
