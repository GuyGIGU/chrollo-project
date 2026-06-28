"""Probe safe Yahoo Finance download throughput.

This is a read-only benchmark: it does not write the market-data cache or the
admission/quarantine ledgers. It samples active-ready tickers and downloads a
small recent window through the same bounded yfinance path the scanner uses.

Example:
    python tools/yahoo_rate_probe.py --sample-size 400 --trials 8:10,12:16,16:20
"""
from __future__ import annotations

import argparse
import contextlib
import io
import json
import random
import time
from pathlib import Path

try:  # works under both `python -m tools.yahoo_rate_probe` and `python tools/yahoo_rate_probe.py`
    from tools._bootstrap import configure_path
except ModuleNotFoundError:
    from _bootstrap import configure_path

configure_path()

ROOT = Path(__file__).resolve().parents[1]

from config import settings
from core.pipeline import downloads, rate_limit
from core.pipeline.fetch_health import present_tickers
from core.pipeline.ticker_admission import load_admission


def _active_ready_symbols(path: Path) -> list[str]:
    store = load_admission(str(path))
    symbols = [
        symbol
        for symbol, entry in store.items()
        if isinstance(entry, dict) and entry.get("status") == "active_ready"
    ]
    return sorted(symbols)


def _parse_trials(raw: str) -> list[tuple[float, int]]:
    trials: list[tuple[float, int]] = []
    for item in raw.split(","):
        if not item.strip():
            continue
        rate_text, workers_text = item.split(":", 1)
        trials.append((float(rate_text), int(workers_text)))
    if not trials:
        raise ValueError("At least one trial is required, e.g. 8:10,12:16")
    return trials


def _sample(symbols: list[str], n: int, seed: int) -> list[str]:
    if n >= len(symbols):
        return symbols
    rng = random.Random(seed)
    return sorted(rng.sample(symbols, n))


def _period_arg(args) -> dict:
    if args.start or args.end:
        if not args.start or not args.end:
            raise ValueError("--start and --end must be passed together")
        return {"start": args.start, "end": args.end}
    return {"period": args.period}


def _run_trial(symbols: list[str], rate: float, workers: int, period_or_dates: dict) -> dict:
    settings.YAHOO_RATE_LIMIT_ENABLED = True
    settings.YAHOO_RATE_LIMIT_PER_SEC = rate
    settings.YAHOO_RATE_LIMIT_BURST = max(float(getattr(settings, "YAHOO_RATE_LIMIT_BURST", 15)), rate * 2)
    settings.YAHOO_DOWNLOAD_WORKERS = workers
    rate_limit.reset_for_test()

    stderr_buffer = io.StringIO()
    start = time.perf_counter()
    with contextlib.redirect_stderr(stderr_buffer):
        panel = downloads._batched_download(
            symbols,
            period_or_dates,
            f"Probe {rate:g}/s {workers}w",
        )
    duration = time.perf_counter() - start
    returned = present_tickers(panel)
    missing = sorted(set(symbols) - returned)
    stderr_text = stderr_buffer.getvalue()
    stderr_lines = stderr_text.strip().splitlines()
    rate_limit_hits = sum(
        1
        for line in stderr_lines
        if "YFRateLimitError" in line or "Too Many Requests" in line or "Rate limited" in line
    )
    return {
        "rate_per_sec": rate,
        "workers": workers,
        "requested": len(symbols),
        "returned": len(returned),
        "return_ratio": round(len(returned) / len(symbols), 4) if symbols else 0.0,
        "duration_s": round(duration, 2),
        "symbols_per_sec": round(len(symbols) / duration, 2) if duration > 0 else None,
        "rate_limit_hits": rate_limit_hits,
        "stderr_sample": stderr_lines[-3:],
        "missing_sample": missing[:20],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Probe Yahoo download throughput safely.")
    parser.add_argument("--sample-size", type=int, default=400)
    parser.add_argument("--seed", type=int, default=20260626)
    parser.add_argument("--trials", default="8:10,12:16,16:20,20:24")
    parser.add_argument("--period", default="1mo")
    parser.add_argument("--start")
    parser.add_argument("--end")
    parser.add_argument("--cooldown", type=float, default=15.0)
    parser.add_argument("--admission", default=str(ROOT / getattr(settings, "TICKER_ADMISSION_FILENAME", "ticker_admission.json")))
    args = parser.parse_args()

    symbols = _active_ready_symbols(Path(args.admission))
    if not symbols:
        raise SystemExit(f"No active_ready symbols found in {args.admission}")
    sample = _sample(symbols, args.sample_size, args.seed)
    period_or_dates = _period_arg(args)
    trials = _parse_trials(args.trials)

    print(json.dumps({
        "sample_size": len(sample),
        "active_ready_total": len(symbols),
        "period_or_dates": period_or_dates,
        "trials": [{"rate_per_sec": r, "workers": w} for r, w in trials],
    }), flush=True)

    results = []
    for i, (rate, workers) in enumerate(trials):
        if i > 0 and args.cooldown > 0:
            print(f"Cooling down {args.cooldown:g}s...", flush=True)
            time.sleep(args.cooldown)
        result = _run_trial(sample, rate, workers, period_or_dates)
        results.append(result)
        print("YAHOO_RATE_PROBE:" + json.dumps(result), flush=True)

    healthy = [r for r in results if r["return_ratio"] >= 0.995 and r["rate_limit_hits"] == 0]
    best = max(healthy, key=lambda r: r["symbols_per_sec"]) if healthy else None
    print("YAHOO_RATE_PROBE_SUMMARY:" + json.dumps({
        "best_healthy": best,
        "results": results,
    }), flush=True)


if __name__ == "__main__":
    main()
