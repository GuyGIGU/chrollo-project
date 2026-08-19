"""The conductor-level fundamentals post-pass (Power-Play program Task 12).

The advisory fetch used to sit INSIDE the evaluation workers
(``evaluation._attach_advisory_metadata``), where the process-global rate
bucket multiplies outbound rate by worker count and fragments 429-cooldowns
across processes. This module moves it to the CONDUCTOR: one process, one
shared throttle (the provider's own), a serial bounded loop over the FIRING
results only — never the whole universe. It is THE advisory assembly: the
old per-ticker builder (``advisory.per_ticker_advisory``) is retired
(2026-08-17 review, EC-3 — one assembly, one owner); the primitives
(``advisory._trailing_return``) stay where they were.

Contracts (the honest-at-the-vendor-seam rules):

* **Explicit as-of for everything filing-gated.** Every metrics call passes
  the ticker's own scan as-of (its frame's last bar). The ``as_of=None``
  legacy path skips the filing-lag gate BY DESIGN and must never feed an
  archived write — a ticker with no derivable as-of is a LOUD per-ticker
  refusal, counted, never a silent skip. THE ONE EXCEPTION is the RS line:
  it is price-local and reads the provider's CURRENT candles (no as-of, not
  filing-gated) — its as-of discipline is the post-close scan itself, stated
  here so the headline rule cannot be read as covering it.
* **Attempted-vs-populated counters, per scan, per half.** The return value
  distinguishes "flag off" (``None`` — the whole block absent) from
  "attempted, all failed" (counters present with ``populated == 0``), and the
  RS-line half carries its own ``rs_attempted``/``rs_populated`` pair — a
  0-of-N silence on either half must be visible (2026-08-17 review, Ramírez).
  Counters ride the scan metrics (the health surface) and the structured
  result line.
* **Reporting-event cache — facts only.** Fundamentals change on filings, not
  days: the four filing-gated metrics are reused while ``as_of <
  next_earnings`` (no new report can have landed) and refetched otherwise —
  keyed on the FACT, never a wall-clock TTL (EC-25). An entry is written ONLY
  when the fetch actually holds metrics: a vendor outage is never persisted
  as a filing-gated fact frozen until the next earnings date (2026-08-17
  review, Ramírez + McKinney independently). ``days_to_earnings`` is
  recomputed arithmetically from the cached next-earnings date; the
  price-local fields (trailing return, RS line) are never cached.
* **Containment (EC-20), at every layer this passenger rides.** Per-ticker: a
  counted swallow (``errored``) so one bad row never costs the loop. Cache
  trust: the loader validates each on-disk entry's shape and drops malformed
  ones loudly (the cache lives in ``output/`` — the default tool-report
  directory), and the cached replay copies ONLY the ``_fund_`` namespace, so
  no on-disk content can reach a result key this module does not own
  (2026-08-17 review, Hunt). The conductor seam adds its own narrow catch.
  Programmer errors still surface — via the counters/stderr in production,
  via the raise in the battery. Zero new supply chain: the pinned yfinance
  through the one provider seam (AP-4).
"""
from __future__ import annotations

import json
import os
import sys

import pandas as pd

CACHE_BASENAME = "fundamentals_cache.json"


def _flag(name: str, default=False):
    try:
        from config import settings
        return getattr(settings, name, default)
    except Exception:  # pragma: no cover - settings import guard
        return default


def _cache_path() -> str:
    from core.pipeline.cache import _project_root
    return os.path.join(_project_root(), "output", CACHE_BASENAME)


def _load_cache(path: str) -> tuple[dict, int]:
    """The cache file, shape-validated per entry. Any unreadable file or
    malformed entry degrades to a cold (re)fetch with a printed refusal —
    never a raise, never trusted verbatim."""
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
    except FileNotFoundError:
        return {}, 0
    except (OSError, json.JSONDecodeError) as e:
        print(f"  [fundamentals cache] unreadable ({type(e).__name__}: {e}) "
              "— cold fetch", file=sys.stderr)
        return {}, 0
    if not isinstance(data, dict):
        print("  [fundamentals cache] not a dict — cold fetch", file=sys.stderr)
        return {}, 0
    cache: dict = {}
    dropped = 0
    for ticker, entry in data.items():
        if (isinstance(entry, dict)
                and isinstance(entry.get("as_of"), str)
                and isinstance(entry.get("next_earnings"), str)
                and isinstance(entry.get("fund_fields"), dict)):
            cache[ticker] = entry
        else:
            dropped += 1
            print(f"  [fundamentals cache] dropped malformed entry "
                  f"{ticker!r}", file=sys.stderr)
    return cache, dropped


def _days_between(as_of, nxt_iso):
    """Calendar days from ``as_of`` to the next-earnings date — pure
    arithmetic on the one already-fetched fact, NEVER a second provider call
    for the same date (2026-08-17 review, Performance). Negative/unparseable
    degrades to None (a past date is not a forward warning)."""
    if not nxt_iso:
        return None
    try:
        delta = (pd.Timestamp(nxt_iso) - pd.Timestamp(as_of)).days
    except (TypeError, ValueError):
        return None
    return int(delta) if delta >= 0 else None


def _fund_fields_fresh(ticker: str, as_of, provider) -> tuple[dict, str | None]:
    """The four filing-gated metrics + the next-earnings fact, fetched fresh.
    Returns ``(fields, next_earnings_iso)``; failures degrade to empty."""
    from core.fundamentals import metrics

    fields: dict = {}
    try:
        m = metrics.compute_metrics(ticker, as_of=as_of, provider=provider)
        for key in ("eps_growth_yoy", "sales_growth_yoy",
                    "eps_growth_accel", "earnings_surprise"):
            if m.get(key) is not None:
                fields[f"_fund_{key}"] = round(float(m[key]), 6)
    except Exception:
        pass                          # vendor miss -> absent keys, counted below
    nxt = None
    try:
        raw = provider.earnings_date(ticker)
        if raw:
            nxt = str(pd.Timestamp(raw).date())
    except Exception:
        nxt = None
    dte = _days_between(as_of, nxt)
    if dte is not None:
        fields["_days_to_earnings"] = dte
    return fields, nxt


def _fund_fields_cached(entry: dict, as_of) -> dict:
    """Reuse under the no-new-filing rule; days-to-earnings recomputed.
    ONLY the ``_fund_`` namespace replays from disk — the fresh path is the
    authority on which keys this module may write onto a paying row."""
    fields = {k: v for k, v in entry["fund_fields"].items()
              if isinstance(k, str) and k.startswith("_fund_")}
    dte = _days_between(as_of, entry.get("next_earnings"))
    if dte is not None:
        fields["_days_to_earnings"] = dte
    return fields


def attach_fundamentals_post_pass(results: list, ticker_frames: dict,
                                  *, provider=None,
                                  cache_path: str | None = None) -> dict | None:
    """Attach the advisory fields to the FIRING results, conductor-side.

    Returns ``None`` when every advisory flag is off (byte-identical scans);
    otherwise the attempted-vs-populated counter block. Mutates result dicts
    in place (the ``_``-prefixed keys the writers/dashboard already consume).
    """
    fundamentals_on = bool(_flag("FUNDAMENTALS_ENABLED"))
    rs_line_on = bool(_flag("RS_LINE_ENABLED"))
    if not (fundamentals_on or rs_line_on):
        return None
    from core.fundamentals.advisory import _trailing_return

    if provider is None:
        from core.pipeline.providers import get_provider
        provider = get_provider()

    path = cache_path or _cache_path()
    cache, dropped = _load_cache(path) if fundamentals_on else ({}, 0)
    counts = {"attempted": 0, "populated": 0, "cache_hits": 0,
              "refused_no_as_of": 0, "rs_attempted": 0, "rs_populated": 0,
              "errored": 0}
    if dropped:
        counts["cache_dropped"] = dropped

    for result in results:
        ticker = result.get("Ticker") or result.get("ticker")
        if not ticker:
            continue
        try:
            df = ticker_frames.get(ticker)
            as_of = df.index[-1] if df is not None and len(df) else None
            if as_of is None:
                # The as_of=None path skips the filing-lag gate BY DESIGN and
                # can never feed an archived write — refuse LOUDLY, per ticker.
                counts["refused_no_as_of"] += 1
                print(f"  [fundamentals refuse {ticker}] no derivable as-of — "
                      "the ungated legacy path never feeds an archived row",
                      file=sys.stderr)
                continue

            fields: dict = {}
            rs_lookback = int(_flag("RS_RATING_LOOKBACK", 252) or 252)
            tr = _trailing_return(df, rs_lookback)
            if tr is not None:
                fields["_rs_trailing_return"] = round(float(tr), 6)

            if fundamentals_on:
                counts["attempted"] += 1
                as_of_iso = str(pd.Timestamp(as_of).date())
                entry = cache.get(ticker)
                reusable = (isinstance(entry, dict)
                            and entry.get("next_earnings")
                            and entry.get("as_of")
                            and entry["as_of"] <= as_of_iso
                            and as_of_iso < entry["next_earnings"])
                if reusable:
                    fund = _fund_fields_cached(entry, as_of)
                    counts["cache_hits"] += 1
                else:
                    fund, nxt = _fund_fields_fresh(ticker, as_of, provider)
                    if nxt and any(k.startswith("_fund_") for k in fund):
                        # Only a fetch that actually HOLDS metrics becomes a
                        # cached fact — an outage frozen until the next
                        # earnings date is the alarm without the recovery.
                        cache[ticker] = {
                            "as_of": as_of_iso, "next_earnings": nxt,
                            "fund_fields": {k: v for k, v in fund.items()
                                            if k != "_days_to_earnings"}}
                if any(k.startswith("_fund_") for k in fund):
                    counts["populated"] += 1
                fields.update(fund)

            if rs_line_on:
                counts["rs_attempted"] += 1
                try:
                    from core.regime.rs_line import compute_rs_line
                    rs = compute_rs_line(ticker, provider=provider)
                    if rs.get("latest") is not None:
                        fields["_rs_line_latest"] = rs["latest"]
                        counts["rs_populated"] += 1
                    if rs.get("rs_line_new_high") is not None:
                        fields["_rs_line_new_high"] = bool(rs["rs_line_new_high"])
                except Exception as e:
                    print(f"  [rs-line skip {ticker}] {type(e).__name__}: {e}",
                          file=sys.stderr)

            result.update(fields)
        except Exception as e:
            # Per-ticker containment (EC-20): one bad row/frame/cache entry
            # costs its own ticker, counted — never the loop, never the scan.
            counts["errored"] += 1
            print(f"  [fundamentals skip {ticker}] {type(e).__name__}: {e}",
                  file=sys.stderr)

    counts["failed"] = counts["attempted"] - counts["populated"]
    if fundamentals_on:
        try:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w", encoding="utf-8") as fh:
                json.dump(cache, fh)
        except OSError as e:
            print(f"  [fundamentals cache] not persisted: {e}", file=sys.stderr)
    return counts
