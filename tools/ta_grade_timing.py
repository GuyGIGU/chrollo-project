"""Per-fire timing of the TA-grade measurement block — the COMMITTED EC-8
cost instrument (2026-08-08 review, finding 10: the task-8 numbers' harness
was machine-local, so the flip checklist's cost-certification step was
re-runnable only on the machine that produced them; EC-16).

Times the one expensive charter measurement — ``measure_trend_bases``, the
bounded box-walk — over every FIRING shadow-fixture ticker at the
worst-case right-edge start (the same protocol as the task-8 evidence:
median 0.31 ms / max 0.54 ms per fire). Scan-line diffs are worthless at
~40% nightly variance; this dedicated per-fire timing is the honest
instrument. Read-only; nothing persists.

Usage (ChrolloDashboard venv python, from repo root):
    python -m tools.ta_grade_timing
"""
from __future__ import annotations

import statistics
import time

try:
    from tools._bootstrap import configure_path
except ModuleNotFoundError:
    from _bootstrap import configure_path

configure_path(backend=True)

from engine_alpha.evaluation import EVAL_ERROR                 # noqa: E402
from engine_alpha.structure.events.market_structure import (          # noqa: E402
    measure_trend_bases,
)
from tools import shadow_diff                                  # noqa: E402


def _mean_true_range(df, period: int = 14) -> float:
    """A plain ATR proxy for the timing run — the walk's COST is driven by
    the brick enumeration, not the ATR's exact value."""
    highs, lows, closes = df["High"], df["Low"], df["Close"]
    prev_close = closes.shift(1)
    tr = (highs - lows).combine(
        (highs - prev_close).abs(), max).combine(
        (lows - prev_close).abs(), max)
    value = float(tr.tail(period).mean())
    return value if value > 0 else 1.0


def main() -> int:
    frames, scalars = shadow_diff._load_fixture()
    spy = float(scalars.get("spy_6m_return", 0.0))
    breadth = scalars.get("breadth_pct")
    breadth = float(breadth) if breadth is not None else None

    per_fire_ms = []
    for ticker in scalars["tickers"]:
        df = frames.get(ticker)
        if df is None:
            continue
        result = shadow_diff._evaluate_ticker(ticker, df, spy, breadth)
        if result is None or result is EVAL_ERROR:
            continue
        atr = _mean_true_range(df)
        # Worst-case protocol: the elected start at the frame's right edge
        # maximizes the walkable sub-frame (the task-8 basis).
        start = time.perf_counter()
        measure_trend_bases(df, atr, elected_start_bar=len(df) - 1,
                            elected_width=0.05)
        per_fire_ms.append((time.perf_counter() - start) * 1000.0)

    if not per_fire_ms:
        print("no shadow-fixture ticker fires — the fixture rotted")
        return 1
    per_fire_ms.sort()
    n = len(per_fire_ms)
    p90 = per_fire_ms[min(n - 1, int(0.9 * n))]
    print(f"measure_trend_bases per-fire timing over {n} firing fixture "
          "tickers (worst-case right-edge start):")
    print(f"  median {statistics.median(per_fire_ms):.2f} ms   "
          f"p90 {p90:.2f} ms   max {max(per_fire_ms):.2f} ms")
    print(f"  ~{max(per_fire_ms) * 300 / 1000:.1f} s worst-case per 300-fire "
          "scan — compare against the evaluation-phase budget "
          "(task-8 evidence: median 0.31 / max 0.54 ms).")
    return 0


if __name__ == "__main__":
    import sys

    sys.exit(main())
