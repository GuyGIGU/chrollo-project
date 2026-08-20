"""Read-only per-ticker candle service for the Watchlist page.

Serves Daily/Weekly/Monthly candles for ANY ticker the parquet price cache
holds — deliberately independent of watchlist membership (unstarring a name
must not break the chart currently on screen) and of scan-artifact presence
(a clean chart is the correct answer for a ticker the engine has not read).
Candles come from the ONE shared builder (core.pipeline.candles — the EC-3
fold with the scan writer), so this path cannot drift from the scan payload's
candle shape. Engine-read material (rails, LPS spans, structure coloring) is
deliberately ABSENT from this service: the wire carries verdicts only from
the scan artifact (EC-28), and this endpoint must never become a second,
half-faithful serializer of the read.

Universe resolution follows the caller-supplied pin key when one is given
(EC-37 — the stored pin decides which panel serves), else searches the closed
registry in its declared scan order (US-Stocks first). An unknown key
degrades into that search — the registry's refusal is absorbed, never raised
out of a read.

Degrade vocabulary (closed sets — every "no candles" outcome is a NAMED
operational verdict, always HTTP 200, so the frontend can tell a data gap
from a bug):
- ticker status: "ok" | "no_cache" (no readable panel could serve — file
  absent or torn mid-rewrite; retryable) | "unknown_ticker" (readable panels
  exist, none holds the name) | "no_drawable_bars" (a panel holds it but
  every row cleaned away — delisted/quarantined history).
- frame status: "ok" | "empty" (nothing drawable at that timeframe — for
  weekly/monthly this is the honest "history too thin" answer while daily
  still serves).

Read discipline (the panel is a 100MB+ multi-ticker parquet a scan rewrites
by temp-file + os.replace, which on Windows FAILS against a reader holding
the file open — core/pipeline/cache.py retries for a bounded ~5s):
- NEVER hydrate the whole panel: ticker membership comes from a footer-only
  schema read, and frames from a column-pruned read of that ticker's five
  OHLCV columns (batched into one read per universe for the strip).
- Read AT MOST once per panel per request, with the shortest possible hold;
  an unreadable/torn file is an operational degrade, never a raise.
- Both caches (membership sets, per-ticker frames) are keyed to the panel
  file's on-disk identity (path + mtime_ns + size) — never a clock — so a
  scan or manual download that rewrites the file invalidates them by
  construction, including write paths outside any invalidation seam.

Every public return passes to_json_safe at this service's single exit: the
builders emit floats straight off the cache, and one NaN cell would 500 the
whole response at Starlette's allow_nan=False boundary (the scan file pays
the same quarantine at write time).

Core/engine imports are lazy inside functions, per the backend's established
discipline for heavy scan-side chains.
"""
from __future__ import annotations

import ast
import logging
import os
import threading
from collections import OrderedDict

logger = logging.getLogger("chrollo.candles")

# Timeframe keys of the full envelope, in display order.
FRAME_KEYS = ("daily", "weekly", "monthly")

# Closed verdict vocabularies (the wire's Literal types mirror these; the
# endpoint test battery pins the two in agreement).
TICKER_STATUSES = ("ok", "no_cache", "unknown_ticker", "no_drawable_bars")
FRAME_STATUSES = ("ok", "empty")

# Bounded at watchlist scale: tens of tickers across three universes, each
# cached frame ~5y of daily OHLCV (~50 KB). Never the hydrated panel.
_FRAME_CACHE_MAX = 96

_lock = threading.Lock()
# (universe.key, ticker) -> (identity, cleaned frame)
_frame_cache: "OrderedDict[tuple[str, str], tuple[tuple, object]]" = OrderedDict()
# universe.key -> (identity, frozenset of panel tickers, flat: bool)
_panel_tickers_cache: dict[str, tuple[tuple, frozenset, bool]] = {}


def _frame_payload(candles, volumes, last_bar_date: str | None) -> dict:
    """One frame's wire block, with the forming-last-bar mark resolved
    server-side (EC-5/EC-28 — the frontend never re-derives it).

    The resampler labels a bucket with its period END date (W-FRI / month
    end) and keeps the still-forming period as the final bar, so mid-week
    the last weekly/monthly candle carries a date beyond the last traded
    session — the NORMAL case, not an edge. A bucket whose end label lies
    beyond the ticker's own last session is honestly marked forming; the
    same comparison makes a completed daily bar False by construction.
    """
    forming = None
    if candles and last_bar_date:
        forming = candles[-1]["time"] > last_bar_date
    return {
        "status": "ok" if candles else "empty",
        "forming_last_bar": forming,
        "candles": candles,
        "volumes": volumes,
    }


def _read_cache_meta(universe) -> dict:
    """Advisory provenance from the cache meta json.

    The meta and the parquet are replaced as two SEPARATE atomic writes, so a
    reader can momentarily see one generation of each — these stamps are
    advisory display facts, never a basis to refuse a read.
    """
    import json

    _cache_file, meta_file = universe.cache_paths()
    try:
        with open(meta_file, encoding="utf-8") as fh:
            meta = json.load(fh)
    except Exception as exc:
        # Advisory only, but a PERMANENTLY corrupt meta should not be
        # invisible — one debug line names the parse failure.
        logger.debug("candles: cache meta unreadable %s: %r", universe.key, exc)
        return {}
    return meta if isinstance(meta, dict) else {}


def _panel_identity(universe) -> tuple | None:
    """The panel file's on-disk identity, or None when it does not exist."""
    cache_file, _meta_file = universe.cache_paths()
    try:
        stat = os.stat(cache_file)
    except OSError:
        return None
    return (cache_file, stat.st_mtime_ns, stat.st_size)


def _tickers_from_schema_names(names) -> frozenset:
    """Ticker set from a panel's flattened ('TICKER', 'Field') column names."""
    tickers = set()
    for name in names:
        if isinstance(name, str) and name.startswith("('"):
            try:
                tickers.add(ast.literal_eval(name)[0])
            except (ValueError, SyntaxError):
                continue
    return frozenset(tickers)


def _panel_tickers(universe, identity):
    """(tickers-in-panel, flat, readable) via a footer-only schema read,
    identity-cached.

    ``flat`` is True for a single-level panel (no ticker tuples but OHLCV
    columns present) — served by an unpruned read of the whole (tiny) file.
    ``readable`` is False only when the schema itself could not be read
    (torn/locked mid-rewrite) — an operational state, never a raise.
    """
    cached = _panel_tickers_cache.get(universe.key)
    if cached is not None and cached[0] == identity:
        return cached[1], cached[2], True
    try:
        import pyarrow.parquet as pq

        names = pq.read_schema(identity[0]).names
    except Exception as exc:  # torn/locked/corrupt mid-rewrite — operational
        # The repr rides the log line: a PERSISTENT programmer error (bad
        # engine setting, pyarrow API drift) must be distinguishable from the
        # expected transient replace race (EC-6: degrade, but never blind).
        logger.warning("candles: unreadable panel schema %s: %r",
                       universe.key, exc)
        return frozenset(), False, False
    tickers = _tickers_from_schema_names(names)
    flat = not tickers and "Close" in names
    with _lock:
        _panel_tickers_cache[universe.key] = (identity, tickers, flat)
    return tickers, flat, True


def _clean_ticker_frame(df):
    """Shared prep (clean_daily_frame) + drop a frame with nothing drawable."""
    from core.pipeline.candles import clean_daily_frame

    frame = clean_daily_frame(df)
    return frame if len(frame) else None


def _read_ticker_frames(universe, tickers: list[str], identity):
    """ONE column-pruned parquet read for a batch of tickers in one universe.

    Returns ``({ticker: cleaned frame}, read_ok)``; tickers whose cleaned
    frame has nothing drawable are absent from the dict. The single read call
    is the whole file hold; a replace racing us surfaces as an exception and
    degrades to ``({}, False)`` (the next request self-heals under the new
    identity).
    """
    import pandas as pd

    from config import settings

    cache_file = identity[0]
    wanted = [
        f"('{ticker}', '{field}')"
        for ticker in tickers
        for field in ("Open", "High", "Low", "Close", "Volume")
    ]
    try:
        panel = pd.read_parquet(
            cache_file, engine=settings.PARQUET_ENGINE, columns=wanted)
    except Exception as exc:  # replaced/torn mid-read — operational
        logger.warning("candles: pruned panel read failed %s: %r",
                       universe.key, exc)
        return {}, False
    if hasattr(panel.index, "tz") and panel.index.tz is not None:
        panel.index = panel.index.tz_localize(None)
    out: dict[str, object] = {}
    for ticker in tickers:
        if ticker not in panel.columns.get_level_values(0):
            continue
        frame = _clean_ticker_frame(panel[ticker])
        if frame is None:
            continue
        out[ticker] = frame
        with _lock:
            _frame_cache[(universe.key, ticker)] = (identity, frame)
            _frame_cache.move_to_end((universe.key, ticker))
            while len(_frame_cache) > _FRAME_CACHE_MAX:
                _frame_cache.popitem(last=False)
    return out, True


def _read_flat_frame(universe, ticker: str, identity):
    """Single-level panel fallback: the whole (tiny) file, sliced structurally.

    Returns ``(frame_or_None, member, readable)`` — three distinguishable
    facts, never one conflating None: an unreadable file must degrade to the
    retryable verdict, a held-but-cleaned-away name to the dead-history one,
    and an absent name to unknown (the closed vocabulary's whole contract).
    """
    import pandas as pd

    from config import settings

    try:
        panel = pd.read_parquet(identity[0], engine=settings.PARQUET_ENGINE)
    except Exception as exc:
        logger.warning("candles: unreadable flat panel %s: %r",
                       universe.key, exc)
        return None, False, False
    if hasattr(panel.index, "tz") and panel.index.tz is not None:
        panel.index = panel.index.tz_localize(None)
    if isinstance(panel.columns, pd.MultiIndex):
        if ticker not in panel.columns.get_level_values(0):
            return None, False, True
        return _clean_ticker_frame(panel[ticker]), True, True
    if "Close" not in panel.columns:
        return None, False, True
    return _clean_ticker_frame(panel), True, True


def _candidate_universes(universe_key: str | None) -> list:
    """Pin-first (EC-37), then the closed registry in declared scan order.

    An unknown pin key is absorbed into the deterministic search, never
    raised out of a read.
    """
    from core.pipeline.universe import all_universes, resolve_universe

    ordered = []
    if universe_key:
        try:
            ordered.append(resolve_universe(universe_key))
        except ValueError:
            logger.info("candles: unknown universe key %r — falling back to search",
                        universe_key)
    for universe in all_universes():
        if not any(u.key == universe.key for u in ordered):
            ordered.append(universe)
    return ordered


def _aggregate_status(saw_readable: bool, saw_member: bool,
                      read_failed: bool) -> str:
    """The named no-candles verdict for one ticker after the full search.

    Precedence — the RETRYABLE verdict wins over the definitive one: a member
    whose data read failed degrades to "no_cache", because a failed read can
    never certify dead history; "no_drawable_bars" is asserted only after a
    SUCCESSFUL read found nothing drawable. Any failed read without
    membership evidence is likewise "no_cache"; "unknown_ticker" only when
    every readable panel denied membership.
    """
    if saw_member:
        return "no_cache" if read_failed else "no_drawable_bars"
    if read_failed or not saw_readable:
        return "no_cache"
    return "unknown_ticker"


def _resolve_frames(tickers: list[str], pins: dict | None = None):
    """THE resolution walk, shared by the single-ticker envelope and the
    batch — one implementation, so the two routes cannot file different
    verdicts for the same name (the review's finding 5).

    Per-ticker semantics (identical to the old single walk): pin-first
    candidates (EC-37), first panel that actually SERVES the name wins, and
    the search continues past a universe whose read failed or whose rows
    cleaned away — a dual-listed name may still be servable elsewhere.

    Batching: panel data reads are grouped into ONE pruned read per universe
    per round (the footer-parse cost dominates, so 60 names cost one). A
    round's failed read marks its tickers retryable and lets them continue
    the walk next round; identities are re-checked per round, so a
    mid-rewrite race degrades to the retryable verdict and self-heals under
    the new identity on the next request.

    Returns ``(served, statuses)``: ``served[ticker] = (universe, frame)``;
    ``statuses[ticker]`` names the verdict for every ticker not served.
    """
    pins = pins or {}
    state = {
        ticker: {"saw_readable": False, "saw_member": False,
                 "read_failed": False, "tried": set()}
        for ticker in tickers
    }
    served: dict[str, tuple] = {}
    pending = list(tickers)
    while pending:
        by_universe: dict[str, tuple[object, list[str]]] = {}
        for ticker in pending:
            facts = state[ticker]
            for universe in _candidate_universes(pins.get(ticker)):
                if universe.key in facts["tried"]:
                    continue
                identity = _panel_identity(universe)
                if identity is None:
                    facts["tried"].add(universe.key)
                    continue
                # Unlocked point-read beside locked mutation: safe because a
                # single dict get is GIL-atomic in CPython — a compound
                # operation here would need the lock.
                cached = _frame_cache.get((universe.key, ticker))
                if cached is not None and cached[0] == identity:
                    with _lock:
                        if (universe.key, ticker) in _frame_cache:
                            _frame_cache.move_to_end((universe.key, ticker))
                    served[ticker] = (universe, cached[1])
                    break
                members, flat, readable = _panel_tickers(universe, identity)
                facts["saw_readable"] = facts["saw_readable"] or readable
                if not readable:
                    # A failed schema read can never certify absence: without
                    # the retryable fact this universe would count as a clean
                    # membership denial and the ticker could aggregate to the
                    # terminal "unknown_ticker" (_aggregate_status's contract).
                    facts["read_failed"] = True
                    facts["tried"].add(universe.key)
                    continue
                if flat:
                    frame, member, flat_readable = _read_flat_frame(
                        universe, ticker, identity)
                    facts["tried"].add(universe.key)
                    facts["saw_member"] = facts["saw_member"] or member
                    facts["read_failed"] = facts["read_failed"] or not flat_readable
                    if frame is not None:
                        served[ticker] = (universe, frame)
                        break
                    continue
                if ticker in members:
                    facts["saw_member"] = True
                    entry = by_universe.setdefault(universe.key, (universe, []))
                    entry[1].append(ticker)
                    break
                facts["tried"].add(universe.key)

        # Execute this round's batched reads — one pruned read per universe.
        pending = []
        for universe, wanted in by_universe.values():
            identity = _panel_identity(universe)
            if identity is None:
                # Vanished between membership and read: retryable, and the
                # walk continues into the remaining universes next round.
                for ticker in wanted:
                    state[ticker]["read_failed"] = True
                    state[ticker]["tried"].add(universe.key)
                    pending.append(ticker)
                continue
            got, read_ok = _read_ticker_frames(universe, wanted, identity)
            for ticker in wanted:
                state[ticker]["tried"].add(universe.key)
                if ticker in got:
                    served[ticker] = (universe, got[ticker])
                    continue
                if not read_ok:
                    state[ticker]["read_failed"] = True
                pending.append(ticker)

    statuses = {
        ticker: _aggregate_status(
            state[ticker]["saw_readable"], state[ticker]["saw_member"],
            state[ticker]["read_failed"])
        for ticker in tickers if ticker not in served
    }
    return served, statuses


def _serving_universe_and_frame(ticker: str, universe_key: str | None):
    """One ticker through the shared walk.

    Returns ``(universe, frame, status)``; universe/frame are None unless
    status is "ok".
    """
    served, statuses = _resolve_frames([ticker], {ticker: universe_key})
    if ticker in served:
        universe, frame = served[ticker]
        return universe, frame, "ok"
    return None, None, statuses[ticker]


def ticker_candles(ticker: str, universe_key: str | None = None) -> dict:
    """The full envelope for one ticker: Daily/Weekly/Monthly in one response.

    One request returns all three frames so the page's panes can never
    momentarily disagree about which ticker they show.
    """
    from core.pipeline.candles import chart_candles
    from core.pipeline.json_safety import to_json_safe

    universe, frame, status = _serving_universe_and_frame(ticker, universe_key)
    if frame is None:
        return {
            "ticker": ticker,
            "universe": None,
            "status": status,
            "source": "cache",
            "price_series": None,
            "cache_last_modified": None,
            "last_bar_date": None,
            "frames": {key: _frame_payload([], [], None) for key in FRAME_KEYS},
        }
    # The ticker's OWN last valid session — the cleaned frame's final row —
    # never the panel-wide newest date (a quarantined name trails empties
    # while the rest of the panel keeps advancing).
    last_bar_date = str(frame.index[-1])[:10]
    meta = _read_cache_meta(universe)
    # Coerce the advisory meta quotes: the wire model type-pins these as
    # str|None, and a drifted/hand-edited meta value must degrade its own
    # field, never 500 the envelope through response validation.
    price_series = meta.get("price_series")
    last_modified = meta.get("last_modified")
    price_series = price_series if isinstance(price_series, str) else None
    last_modified = last_modified if isinstance(last_modified, str) else None
    tf_set = chart_candles(frame)
    return to_json_safe({
        "ticker": ticker,
        "universe": universe.key,
        "status": "ok",
        # Resolved provenance facts: this envelope is the FRESH CACHE basis,
        # distinguishable on the wire from the replay route's frozen snapshot
        # — the engine overlay's rails are absolute price levels computed at
        # scan time, and the page can only be honest about drawing them if it
        # can detect a basis mismatch.
        "source": "cache",
        "price_series": price_series,
        "cache_last_modified": last_modified,
        "last_bar_date": last_bar_date,
        "frames": {
            "daily": _frame_payload(
                tf_set["candles"], tf_set["volumes"], last_bar_date),
            "weekly": _frame_payload(
                tf_set["weekly_candles"], tf_set["weekly_volumes"],
                last_bar_date),
            "monthly": _frame_payload(
                tf_set["monthly_candles"], tf_set["monthly_volumes"],
                last_bar_date),
        },
    })


def batch_candles(tickers: list[str], pins: dict | None = None) -> dict:
    """Daily candles for the watchlist card grid, one batch.

    Resolution runs through THE shared walk (`_resolve_frames`) — the same
    per-ticker semantics as the single-ticker envelope, pins included
    (EC-37), so a name's card and its big chart can never draw from
    different panels or file different verdicts. Uses the SAME daily builder
    at the SAME cap as the scan artifact's cards, so a clean card and a
    screener card can never disagree on the window or a bar. Each ticker
    carries its own named verdict; a name with no drawable rows never
    degrades the rest, and a mid-rewrite race degrades only to the
    retryable verdict.
    """
    from core.pipeline.candles import daily_candles
    from core.pipeline.json_safety import to_json_safe

    served, statuses = _resolve_frames(tickers, pins)
    out: dict[str, dict] = {}
    for ticker in tickers:
        if ticker in served:
            _universe, frame = served[ticker]
            candles, volumes, _show = daily_candles(frame)
            out[ticker] = {"status": "ok", "candles": candles, "volumes": volumes}
        else:
            out[ticker] = {
                "status": statuses[ticker], "candles": [], "volumes": [],
            }
    return to_json_safe({"tickers": out})
