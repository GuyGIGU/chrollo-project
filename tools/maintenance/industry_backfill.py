"""Fill the industry cache for the scanned universe (his group read, Fri 23/10/2026).

The nightly scan remembers the industry of every name that fires (its
fundamentals sheet names it); the rest of the universe is asked ONCE here,
through the project's throttled provider door, so "N of M in the group" counts
the universe and not only the names that fired. Resumable: a name already in
the cache is never asked again (a name the vendor gives no industry is kept as
such, so funds and shells are not re-asked every run). A probe every 100 names
catches Yahoo's silent throttle (a known name coming back empty stops the run).

    python -m tools.maintenance.industry_backfill [--cache PATH] [--limit N] [--seed MAP.json]

``--seed`` merges a ticker -> {"sector", "industry"} map (a measuring session's
own pull) before asking the vendor for anything.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
import time

from core.fundamentals import industry

PROBE = "AAPL"
PROBE_EVERY = 100
SAVE_EVERY = 25


def seed(cache: dict, seed_map: dict, as_of: str) -> int:
    """Merge a measuring session's map; the cache's own entries stand. Returns how many were added."""
    added = 0
    for ticker, entry in seed_map.items():
        if ticker in cache or not isinstance(entry, dict):
            continue
        cache[ticker] = {"sector": entry.get("sector"), "industry": entry.get("industry") or None, "as_of": as_of}
        added += 1
    return added


def backfill(tickers, cache: dict, info, *, as_of: str, save=lambda: None, log=print,
             probe: str = PROBE, probe_every: int = PROBE_EVERY, save_every: int = SAVE_EVERY) -> dict:
    """Ask ``info(ticker)`` for every ticker the cache lacks; write what comes back.
    Returns the counts; ``stopped`` names the throttle when the probe came back empty."""
    todo = [t for t in tickers if t not in cache]
    counts = {"todo": len(todo), "asked": 0, "named": 0, "empty": 0, "stopped": None}
    started = time.time()

    def ask(ticker):
        try:
            return info(ticker) or {}
        except Exception as e:  # one vendor miss costs itself
            log(f"  [industry skip {ticker}] {type(e).__name__}: {e}")
            return {}

    for n, ticker in enumerate(todo, 1):
        data = ask(ticker)
        name = data.get("industry") or None
        cache[ticker] = {"sector": data.get("sector"), "industry": name, "as_of": as_of}
        counts["asked"] += 1
        counts["named" if name else "empty"] += 1
        if n % save_every == 0:
            save()
            log(f"  {n}/{len(todo)} {ticker} -> {name}  {time.time() - started:.0f}s")
        if n % probe_every == 0 and not (ask(probe).get("industry")):
            counts["stopped"] = f"throttled: {probe} came back without an industry after {n} names"
            log("  " + counts["stopped"])
            break
    save()
    return counts


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--cache", default=industry.cache_path(), help="the industry cache (default: output/)")
    parser.add_argument("--limit", type=int, default=None, help="ask at most N names this run")
    parser.add_argument("--seed", default=None, help="a ticker -> {sector, industry} JSON map to merge first")
    parser.add_argument("--tickers", default=None, help="the universe CSV (default: config/tickers.csv)")
    args = parser.parse_args(argv)

    from core.pipeline.market_data.providers import get_provider
    from core.pipeline.universe.tickers import get_cached_tickers

    as_of = dt.date.today().isoformat()
    cache = industry.load_cache(args.cache)
    if args.seed:
        with open(args.seed, "r", encoding="utf-8") as f:
            print(f"seeded {seed(cache, json.load(f), as_of)} names from {args.seed}")
        industry.save_cache(cache, args.cache)
    universe = get_cached_tickers(args.tickers)
    tickers = universe
    if args.limit is not None:
        tickers = [t for t in tickers if t not in cache][:args.limit]
    provider = get_provider()
    counts = backfill(tickers, cache, provider.info, as_of=as_of,
                      save=lambda: industry.save_cache(cache, args.cache))
    known = sum(1 for t in universe if industry.industry_of(cache, t))
    print(f"done: asked {counts['asked']} of {counts['todo']} (named {counts['named']}, empty {counts['empty']}); "
          f"the cache names an industry for {known} of the universe -> {args.cache}")
    if counts["stopped"]:
        print(counts["stopped"] + "; run again later to continue")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
