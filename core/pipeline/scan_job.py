"""Reusable scan -> dashboard -> archive job."""
from __future__ import annotations

import os
import logging
from dataclasses import dataclass
from datetime import date, datetime

import pandas as pd
from config import settings
from core.archive.writer import archive_scan_results
from core.pipeline import run_screener
from core.pipeline.cache import _cache_paths, _read_meta, _weekly_refresh_due, _write_meta
from core.pipeline.data import get_provider, get_tickers
from core.pipeline.downloads import repair_latest_session_cache
from core.pipeline.file_lock import cache_lock
from core.pipeline.market_data_health import (
    DEGRADED_COVERAGE_STATES,
    REFRESH_FAILURE_STATES,
    clear_repair_state,
    compute_market_data_health,
    record_repair_attempt,
)
from core.pipeline.market_calendar import latest_completed_session
from core.pipeline.screener import CachedMarketDataError
from core.pipeline.universe import all_universes, resolve_universe
from output.dashboard import generate_dashboard
from output.terminal import print_finviz_url, print_results, save_csv

PROJECT_ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
log = logging.getLogger("chrollo.scan_job")


class StaleMarketDataError(RuntimeError):
    """Raised when a scan should not be archived because data is stale."""

    def __init__(self, message: str, n_setups: int | None = None):
        super().__init__(message)
        self.n_setups = n_setups


@dataclass
class ScanExportResult:
    n_setups: int
    n_archived: int
    # Tickers whose eval chain THREW and was swallowed by the skip-guard (distinct
    # from a structural reject). Threaded onto SCAN_RESULT_JSON for the alert
    # tripwire; 0 on a clean scan. Sourced from the run's own scan metrics so the
    # PRIMARY universe carries its OWN count.
    n_errored: int = 0
    # Species-lane counters (Power-Play program Task 8): None when the lane is
    # dark — the SCAN_RESULT_JSON line carries them as OPTIONAL keys, so the
    # flag-off line stays byte-identical and nothing new is stdout-scraped.
    power_play_counts: dict | None = None
    # Fundamentals attempted-vs-populated counters (program Task 12); same
    # optional-key contract.
    fundamentals_counts: dict | None = None


@dataclass
class DownloadOnlyResult:
    n_tickers: int
    latest_session: str | None
    expected_session: str
    coverage: str
    health_state: str = "healthy"
    coverage_detail: dict | None = None
    ready: bool = True
    partial: bool = False
    cooldown_until: str | None = None
    retry_reason: str | None = None
    help_needed: bool = False
    message: str | None = None


def _expected_session_date(now_et: datetime | None = None) -> str:
    expected = latest_completed_session(now_et)
    return expected.strftime("%Y-%m-%d")


def _last_bar_date(data: pd.DataFrame, tickers: list[str]) -> str | None:
    if data is None or data.empty:
        return None

    if isinstance(data.columns, pd.MultiIndex):
        symbols = list(data.columns.get_level_values(0).unique())
        preferred = settings.SPY_SYMBOL if settings.SPY_SYMBOL in symbols else None
        symbol = preferred or next((ticker for ticker in tickers if ticker in symbols), None)
        if symbol:
            try:
                close = data[symbol]["Close"].dropna()
                if not close.empty:
                    return pd.Timestamp(close.index[-1]).strftime("%Y-%m-%d")
            except Exception:
                pass

    valid = data.dropna(how="all")
    if valid.empty:
        return None
    return pd.Timestamp(valid.index[-1]).strftime("%Y-%m-%d")


def _archive_freshness(data: pd.DataFrame, tickers: list[str], universe=None) -> tuple[str, str | None]:
    """Non-raising archive-freshness classifier — the single decision the archive
    path branches on. Returns ``(status, message)``:

      ``'fresh'``             archive everything.
      ``'degraded_coverage'`` the latest session IS present but eligible universe-
                              wide coverage misses the archive bar (thin/halted
                              names, EOD publish lag). The panel is current, so
                              per-ticker-fresh setups ARE archivable — the caller
                              archives that subset instead of discarding the whole
                              cohort (the historical permanent-hole bug).
      ``'stale_session'``     the feed is a session behind, or the panel is
                              otherwise untrustworthy (shallow / NaN-wiped history)
                              — do not archive.

    ``_assert_fresh_for_archive`` delegates here, so the raising path (empty branch,
    cache mode) and the classifying path (non-empty download branch) can never
    diverge.
    """
    expected = _expected_session_date()
    last_bar = _last_bar_date(data, tickers)
    # Stale only if the data is OLDER than the latest completed session — i.e. the
    # feed is missing a session it should have. A bar that is current or newer
    # (e.g. today's forming bar during an intraday manual scan) is fine. ISO
    # "YYYY-MM-DD" strings compare chronologically, so "<" is correct here.
    _, meta_file = _cache_paths(universe)
    if last_bar is None or last_bar < expected:
        stale_msg = (
            f"stale market data: last bar {last_bar or 'none'}, expected >= {expected}"
        )
        # Behind is NEVER archivable — but it may still be READABLE. Without this
        # branch a cache-mode evaluation on a session_lag day aborts, so the operator
        # watches his leaderboard render and then vanish behind a red failure, while a
        # page reload shows it sitting there fine. Distinguish the two: the caller
        # tolerates `session_lag` in cache mode (dashboard refreshed, archive skipped)
        # and still aborts on a genuine stale session.
        if last_bar is not None and compute_market_data_health(
            data, tickers, expected_session=pd.Timestamp(expected), meta_file=meta_file,
            index_symbols=list(resolve_universe(universe).index_symbols),
        )["health_state"] == "session_lag":
            return "session_lag", stale_msg
        return "stale_session", stale_msg

    health = compute_market_data_health(
        data, tickers, expected_session=pd.Timestamp(expected), meta_file=meta_file,
        index_symbols=list(resolve_universe(universe).index_symbols),
    )
    if health["can_archive"]:
        return "fresh", None

    msg = (
        f"stale market data: {health['diagnosis']} "
        f"(eligible coverage {health['coverage']['eligible']['text']}, "
        f"raw coverage {health['coverage']['raw']['text']})"
    )
    # A CURRENT-session coverage shortfall (repairable / lagging / provider-limited)
    # is per-ticker archivable; a shallow/NaN-wiped panel or a genuinely stale
    # session is not — treat those as stale_session so they still abort.
    if health["health_state"] in DEGRADED_COVERAGE_STATES:
        return "degraded_coverage", msg
    return "stale_session", msg


def _assert_fresh_for_archive(data: pd.DataFrame, tickers: list[str], universe=None) -> None:
    """Raise ``StaleMarketDataError`` unless the panel is fresh enough to archive.

    Any non-``'fresh'`` status raises (a degraded-coverage day and a stale-session
    day both abort here), preserving the all-or-nothing behavior for callers that
    want it — the empty-results branch and cache mode. The non-empty download path
    consults ``_archive_freshness`` directly so it can partial-archive instead.
    """
    status, msg = _archive_freshness(data, tickers, universe)
    if status != "fresh":
        log.warning("Aborting archive write: %s", msg)
        error = StaleMarketDataError(msg)
        # Carry the classification so a caller can tell a readable-but-behind panel
        # from a genuinely stale one without re-matching diagnosis prose.
        error.freshness_status = status
        raise error


def _fresh_result_subset(
    results_df: pd.DataFrame, data: pd.DataFrame, tickers: list[str], universe=None
) -> tuple[pd.DataFrame, int]:
    """Split fired setups into the per-ticker-fresh subset (whose OWN ticker carries
    a close on the latest expected session) and the count dropped as stale.

    Archiving is per-ticker (upsert by ticker+scan_date+universe_type), so a ticker
    that individually has today's bar is a valid archive row even when the
    universe-wide coverage misses the 95% bar. A setup whose ticker lacks today's
    close was evaluated on a stale bar and is skipped so its scan_close stays
    aligned. Conservative: a malformed/empty panel drops everything (returns empty).
    """
    from core.pipeline.data_freshness import symbols_missing_closes_on

    expected = pd.Timestamp(_expected_session_date()).normalize()
    panel = data
    if getattr(panel.index, "tz", None) is not None:
        panel = panel.copy()
        panel.index = panel.index.tz_localize(None)
    result_syms = [str(t) for t in results_df["Ticker"].tolist()]
    missing = set(symbols_missing_closes_on(panel, result_syms, expected))
    fresh_mask = ~results_df["Ticker"].astype(str).isin(missing)
    fresh_df = results_df[fresh_mask]
    return fresh_df, int(len(results_df) - len(fresh_df))


def _is_latest_coverage_error(exc: Exception) -> bool:
    return "latest-session close coverage" in str(exc).lower()


def _passes_archive_freshness(
    data: pd.DataFrame, tickers: list[str], universe, mode: str, n_setups: int
) -> bool:
    """Run the archive freshness gate; return whether the scan may be archived.

    Returns ``True`` when the data is fresh enough to archive, and ``False`` for
    the single tolerated case — a cache-mode eval that used partial latest-session
    coverage (a legitimate empty/partial day; the dashboard is still refreshed).
    Raises ``StaleMarketDataError`` (stamped with ``n_setups``) on a genuine
    stale-data abort.

    Both the empty-result and non-empty branches route through this so their
    stale-handling logic (the ``mode == "cache" and _is_latest_coverage_error``
    tolerance + the ``n_setups`` stamp) stays in ONE place and can't drift.
    """
    try:
        _assert_fresh_for_archive(data, tickers, universe)
    except StaleMarketDataError as exc:
        # Two tolerated cache-mode shapes, both "refresh the dashboard, skip the
        # archive, exit 0": a partial latest-session coverage day, and a session_lag
        # panel (complete through its own last session, provider has not published the
        # expected one). Neither may archive — that is what returning False means.
        tolerated = (_is_latest_coverage_error(exc)
                     or getattr(exc, "freshness_status", None) == "session_lag")
        if mode == "cache" and tolerated:
            return False
        exc.n_setups = n_setups
        raise
    return True


def _maybe_build_health_board(data, universe):
    """Build the flag-gated health-board section for a NON-equities universe.

    A VISIBLE per-universe branch (never a hidden hook in run_screener): it
    classifies every member of the Sectors+Market / Commodities+ETFs universe into
    a position-in-cycle state off the already-fetched ``data`` panel, then assembles
    the artifact section. Returns ``None`` — so the dashboard write is byte-identical
    to before — when EITHER:

      * the read is off (``HEALTH_BOARD_ENABLED`` is design-default False but ships
        True per an operator flip; read lazily to respect the config-vs-cwd trap), OR
      * this is the equities universe (``universe_type == DEFAULT_UNIVERSE_TYPE``):
        the firing grid is its own read, so the health board is only for the ETF
        universes and us_equities stays untouched even when the flag is ON.

    Any failure logs and yields ``None`` — the passive health read can never abort a
    real scan.
    """
    from core.pipeline.universe import DEFAULT_UNIVERSE_TYPE

    if not getattr(settings, "HEALTH_BOARD_ENABLED", False):
        return None
    if universe.universe_type == DEFAULT_UNIVERSE_TYPE:
        return None
    try:
        from core.pipeline.health_board import classify_universe_members
        from output.dashboard import build_health_payload

        members, unreadable = classify_universe_members(data, universe)
        payload = build_health_payload(members, unreadable, data, universe)
        log.info(
            "health board [%s]: %d classified, %d unreadable",
            universe.key, len(payload["members"]), len(payload["unreadable"]),
        )
        return payload
    except Exception:  # noqa: BLE001 — a passive read must never fail a scan
        log.exception("health-board read failed [%s]", universe.key)
        return None


def _archive_near_misses(near_miss_sink, uni) -> None:
    """Persist the lane sink behind the SAME gate that admitted the fires.
    Called only on freshness-passed paths; every writer bound is printed
    (no silent caps). A None/empty sink is a quiet no-op."""
    if near_miss_sink is None:
        return
    rows = near_miss_sink.get("rows") or []
    stats = near_miss_sink.get("stats") or {}
    from core.archive.near_miss_writer import archive_near_miss_rows
    counters = archive_near_miss_rows(rows, universe_type=uni.universe_type,
                                      enable=True)
    print(f"\nNear-miss lane: {counters['inserted']} new + "
          f"{counters['recurred']} recurring episode(s) archived "
          f"(deferred stats {stats}; writer {counters}).", flush=True)


def run_scan_and_export(mode: str = "download", universe=None) -> ScanExportResult:
    """Run the screener and write every non-broker output artifact.

    ``universe`` selects the market to scan (``None`` = US-Stocks). It threads
    through the screener, the freshness gate, and the dashboard artifact path so
    each universe reads and writes its own files; the US-Stocks default is
    byte-identical to the prior single-universe behavior.
    """
    uni = resolve_universe(universe)
    # The near-miss lane rides the scan only when BOTH the lane flag and live
    # archiving are on — its rows land behind the same freshness gate as the
    # fires (a stale/degraded basis is telemetry noise, skipped and said so).
    near_miss_sink = ({"rows": [], "stats": {}}
                      if settings.ARCHIVE_LIVE_SCANS
                      and settings.NEAR_MISS_LANE_ENABLED else None)
    try:
        results_df, data, tickers, market_context = run_screener(
            mode=mode, universe=uni, near_miss_sink=near_miss_sink)
    except CachedMarketDataError as exc:
        raise StaleMarketDataError(str(exc), n_setups=0) from exc

    # Swallowed-eval-crash count for THIS run, read from its own scan metrics. 0 on
    # a clean scan (the key is only present when non-zero — byte-parity). Threaded
    # onto every ScanExportResult so the primary universe carries its own count out
    # to SCAN_RESULT_JSON for the alert tripwire.
    n_errored = int(
        (market_context.get("_scan_metrics", {}).get("counts", {}) or {}).get(
            "errored_tickers", 0
        )
    )

    # Flag-gated position-in-cycle read for the non-equities universes (None
    # otherwise → the dashboard write is byte-identical). Computed once here and
    # threaded into BOTH generate_dashboard call sites (empty + non-empty), because
    # the ETF universes usually fire zero setups and take the empty branch.
    health_board = _maybe_build_health_board(data, uni)

    # Species-lane + fundamentals counters (None when dark) — threaded onto
    # every ScanExportResult below so SCAN_RESULT_JSON carries them as
    # optional keys.
    pp_counts = ((market_context or {}).get("power_play") or {}).get("counts")
    fund_counts = (market_context or {}).get("fundamentals")

    # ONE scan_date for every store this export writes (the payload's
    # scan_identity and the archive's upsert key), computed once so the two
    # can never straddle midnight into different identities for one scan.
    # Stamped from the panel's own last bar, never the wall clock (EC-37): on
    # this ET+7 box the local-date stamp filed every weekend/post-midnight
    # re-scan of Friday's data under a NEW Saturday/Sunday identity instead of
    # re-upserting Friday's rows (~28% duplicate episode-pairs by 2026-08).
    # Clock fallback only for an empty panel, where there is no artifact to copy.
    scan_date = _last_bar_date(data, tickers) or date.today().strftime("%Y-%m-%d")

    if results_df.empty:
        print("\nNo setups found today. Filters are running tight, wait for the right pitch!")
        # An empty result is only a legitimate "scanned, matched nothing" day when
        # the data is trustworthy. A degraded fetch (thin/shallow panel) can also
        # yield zero setups — writing that empty payload would WIPE the prior day's
        # real setups off the live dashboard while the run still reports ok. Gate the
        # empty branch with the SAME freshness check as the archive path so degraded
        # zeros raise (reported stale) instead of silently clobbering the screen. A
        # genuine zero-setup day on healthy data still writes the valid empty artifact.
        lane_freshness_ok = False
        if settings.ARCHIVE_LIVE_SCANS:
            # Genuine stale data raises (reported stale); a fresh day and the
            # tolerated cache-mode partial-coverage case both fall through to the
            # dashboard refresh below (the empty artifact clears stale names).
            if _passes_archive_freshness(data, tickers, uni, mode, n_setups=0):
                lane_freshness_ok = True
            elif near_miss_sink is not None:
                # Tolerated cache-mode partial coverage: the lane's rows are
                # dropped by the same gate that skipped the archive — said so,
                # never silent (review 2026-07-26 finding 5).
                print(f"Near-miss lane: {len(near_miss_sink.get('rows') or [])} "
                      "row(s) skipped (cache-mode partial coverage).", flush=True)
        # Write an empty artifact so this universe reads as "scanned, matched
        # nothing" rather than "never scanned" — and so an empty day clears any
        # stale setups instead of leaving the previous scan's names on screen. The
        # health board rides this same write (the ETF universes usually land here).
        generate_dashboard(results_df, data, tickers, market_context, universe=uni,
                           health_board=health_board, scan_date=scan_date)
        if lane_freshness_ok:
            # A zero-fire night is prime lane material — the refusal cohort
            # archives on the same freshness verdict as fires would. Ordered
            # AFTER the dashboard write so even an unforeseen lane escape can
            # never cost the empty artifact (review 2026-07-26 finding 5).
            _archive_near_misses(near_miss_sink, uni)
        return ScanExportResult(n_setups=0, n_archived=0, n_errored=n_errored,
                                power_play_counts=pp_counts,
                                fundamentals_counts=fund_counts)

    print_results(results_df)

    output_dir = os.path.join(PROJECT_ROOT, "output", "watchlists")
    os.makedirs(output_dir, exist_ok=True)
    save_csv(results_df, output_dir)
    print_finviz_url(results_df)

    generate_dashboard(results_df, data, tickers, market_context, universe=uni,
                       health_board=health_board, scan_date=scan_date)

    # Persist every setup to setup_archive (idempotent upsert by
    # ticker+scan_date+universe_type). Forward returns are filled in later by
    # core/archive/forward_returns.py. Gated by settings.ARCHIVE_LIVE_SCANS.
    #
    # All universes archive now that universe_type is part of the identity key
    # (Tasks 3/6): each row is stamped with its universe, so an ETF setup coexists
    # with a same-named stock on one date, and the stock-only edge metric filters
    # on universe_type='us_equities'.
    n_archived = 0
    if settings.ARCHIVE_LIVE_SCANS:
        # DOWNLOAD (scheduled accumulation) mode classifies without raising so a
        # CURRENT-session-but-degraded-coverage day archives the per-ticker-fresh
        # subset instead of discarding the whole cohort (the historical permanent-
        # hole bug: a <95%-coverage day silently dropped every fired setup and never
        # re-archived them). Cache mode + the empty-results branch keep the
        # all-or-nothing behavior via the untouched _passes_archive_freshness path.
        if mode != "cache":
            status, msg = _archive_freshness(data, tickers, uni)
            if status == "stale_session":
                log.warning("Aborting archive write: %s", msg)
                raise StaleMarketDataError(msg, n_setups=len(results_df))
            if status == "degraded_coverage":
                fresh_df, n_stale = _fresh_result_subset(results_df, data, tickers, uni)
                if fresh_df.empty:
                    # Session is current but NONE of the fired tickers carry today's
                    # close, so there is nothing per-ticker-fresh to salvage. Do NOT
                    # exit ok/silent here — that would reintroduce the very silent-stall
                    # this effort removes (an 'ok' run with n_setups>0/n_archived=0 fires
                    # no alert). Raise so the run reports stale_data and alerts, exactly
                    # as the pre-partial-archive all-or-nothing gate did for this input.
                    log.warning("Aborting archive write: %s", msg)
                    raise StaleMarketDataError(msg, n_setups=len(results_df))
                n_archived = archive_scan_results(fresh_df, scan_date_str=scan_date,
                                                  enable=True, universe=uni)
                print(f"\nArchived {n_archived} per-ticker-fresh {uni.key} setups to "
                      f"setup_archive; {n_stale} setup(s) on stale tickers skipped "
                      f"(degraded universe coverage; source='screener', "
                      f"universe_type='{uni.universe_type}').", flush=True)
                if near_miss_sink is not None:
                    # Degraded coverage: refusal telemetry on a partial basis
                    # is noise — skipped, and said so (never a silent drop).
                    print(f"Near-miss lane: {len(near_miss_sink.get('rows') or [])} "
                          "row(s) skipped (degraded universe coverage).", flush=True)
                return ScanExportResult(n_setups=len(results_df), n_archived=n_archived,
                                        n_errored=n_errored,
                                power_play_counts=pp_counts,
                                fundamentals_counts=fund_counts)
            # status == "fresh" → archive the whole cohort.
            n_archived = archive_scan_results(results_df, scan_date_str=scan_date,
                                              enable=True, universe=uni)
            print(f"\nArchived {n_archived} live {uni.key} setups to setup_archive "
                  f"(source='screener', universe_type='{uni.universe_type}').")
            _archive_near_misses(near_miss_sink, uni)
            return ScanExportResult(n_setups=len(results_df), n_archived=n_archived,
                                    n_errored=n_errored,
                                power_play_counts=pp_counts,
                                fundamentals_counts=fund_counts)

        # Cache mode: unchanged all-or-nothing gate (tolerates a partial-coverage
        # cached eval by skipping the archive write; genuine staleness raises).
        if not _passes_archive_freshness(data, tickers, uni, mode, n_setups=len(results_df)):
            print(
                "\nCached evaluation used partial latest-session coverage; "
                "dashboard updated, archive write skipped.",
                flush=True,
            )
            if near_miss_sink is not None:
                print(f"Near-miss lane: {len(near_miss_sink.get('rows') or [])} "
                      "row(s) skipped (cache-mode partial coverage).", flush=True)
            return ScanExportResult(n_setups=len(results_df), n_archived=0,
                                    n_errored=n_errored,
                                power_play_counts=pp_counts,
                                fundamentals_counts=fund_counts)
        n_archived = archive_scan_results(results_df, scan_date_str=scan_date,
                                          enable=True, universe=uni)
        print(f"\nArchived {n_archived} live {uni.key} setups to setup_archive "
              f"(source='screener', universe_type='{uni.universe_type}').")
        _archive_near_misses(near_miss_sink, uni)

    return ScanExportResult(n_setups=len(results_df), n_archived=n_archived,
                            n_errored=n_errored,
                                power_play_counts=pp_counts,
                                fundamentals_counts=fund_counts)


def run_all_universe_scans(mode: str = "download") -> dict[str, "ScanExportResult | None"]:
    """Scan every universe sequentially in one process, US-Stocks first.

    US-Stocks runs first so its broad-market context is on disk before the small
    ETF universes (which borrow it). A NON-PRIMARY (ETF) universe's failure is
    ISOLATED — it logs and yields ``None`` without aborting the others. But a
    failure of the PRIMARY (US-Stocks) universe is re-raised AFTER the others run,
    so the scheduled run's exit code / status / alert reflect the primary outcome
    exactly as the prior single-universe path did (a stale/crashed primary must
    not be silently logged as 'ok' with n_setups=0). Runs under whatever lock the
    caller holds; universes are serial, so they don't contend on the pool or rate.
    """
    universes = all_universes()
    primary_key = universes[0].key  # all_universes() is US-Stocks-first by contract
    results: dict[str, ScanExportResult | None] = {}
    primary_error: Exception | None = None
    for uni in universes:
        try:
            results[uni.key] = run_scan_and_export(mode=mode, universe=uni)
        except Exception as exc:  # noqa: BLE001 — isolate ETF universes, capture primary
            results[uni.key] = None
            if isinstance(exc, StaleMarketDataError):
                log.warning("universe scan stale/aborted [%s]: %s", uni.key, exc)
            else:
                log.exception("universe scan failed [%s]", uni.key)
            if uni.key == primary_key:
                primary_error = exc
    if primary_error is not None:
        raise primary_error  # propagate the primary outcome to exit/status/alert
    return results


def refresh_market_data_cache() -> DownloadOnlyResult:
    """Refresh ticker universe + market-data cache without evaluating setups."""
    tickers = get_tickers()
    cache_file, meta_file = _cache_paths()
    # Bind the health checks below to THIS universe's regime index set rather than
    # leaning on build_symbol_scope's global default. This download-only path is
    # us_stocks-only today (the ETF universes refresh through the scheduled
    # run_all_universe_scans), so the value is unchanged — but threading it
    # explicitly mirrors _assert_fresh_for_archive / _read_cached_market_data and
    # closes the latent gap where a future non-equities refresh would otherwise be
    # judged against SPY/QQQ coverage it does not carry.
    index_symbols = list(resolve_universe(None).index_symbols)
    # Hold the per-universe cache lock across the whole read-fetch-write-meta
    # sequence so a CLI download-only run and the scheduler subprocess cannot
    # interleave on the same files (fetch_data re-acquires it re-entrantly).
    with cache_lock(cache_file):
        return _refresh_market_data_cache_locked(
            tickers, cache_file, meta_file, index_symbols
        )


def _clear_absent_session_ledger(meta_file: str) -> None:
    """Forget which sessions were proven absent, so the next fetch may go cold.

    Called ONLY immediately before a run that actually reaches the provider. Clearing
    it at the top of the request instead would spend the operator's override on the
    three branches that return without fetching (already-healthy, repair-not-ready, the
    windowed per-symbol repair) — a click the job itself reports as a no-op would
    silently re-arm the full-universe refetch for the next scheduled run.

    Best-effort: this is housekeeping for a guard that only skips work, so a Windows
    file-replace denial must not abort the operator's refresh and record the job as
    failed (conventions EC-20 / EC-21 — a passenger never owns the paying job's status).
    """
    from core.pipeline.downloads import ABSENT_SESSIONS_KEY  # noqa: PLC0415 — lazy, yfinance-heavy module
    try:
        meta = _read_meta(meta_file)
        dropped = [meta.pop(key, None) for key in (ABSENT_SESSIONS_KEY, 'last_cold_failure')]
        if any(value is not None for value in dropped):
            _write_meta(meta_file, meta)
    except Exception:
        log.warning("Could not clear the absent-session ledger; continuing with the "
                    "refresh.", exc_info=True)


def _refresh_market_data_cache_locked(
    tickers: list[str], cache_file: str, meta_file: str,
    index_symbols: list[str],
) -> DownloadOnlyResult:
    expected = _expected_session_date()
    before_health = _cached_health(cache_file, meta_file, tickers, expected, index_symbols)
    if before_health and before_health["can_archive"] and not before_health.get("weekly_refresh_due"):
        clear_repair_state(meta_file)
        print(f"\nMarket-data cache already healthy: {before_health['diagnosis']}", flush=True)
        return _download_result(tickers, before_health)

    if before_health and not before_health["can_download"] and not before_health["can_archive"]:
        print(f"\nMarket-data repair is not ready: {before_health['diagnosis']}", flush=True)
        return _download_result(tickers, before_health)

    if (before_health
            and before_health["health_state"] == "needs_repair"
            and before_health["can_download"]):
        data = pd.read_parquet(cache_file, engine=settings.PARQUET_ENGINE)
        min_coverage = before_health["coverage"]["archive_target"]
        symbols = before_health["missing_summary"]["eligible_missing_symbols"]
        repaired = repair_latest_session_cache(
            data,
            cache_file,
            meta_file,
            before_health["missing_summary"]["eligible_missing_symbols"],
            pd.Timestamp(expected),
            min_coverage,
            "Manual repair",
        )
        after_health = compute_market_data_health(
            repaired, tickers, expected_session=pd.Timestamp(expected), meta_file=meta_file,
            meta=_read_meta(meta_file), index_symbols=index_symbols,
        )
        if after_health["can_archive"]:
            clear_repair_state(meta_file)
        else:
            record_repair_attempt(meta_file, before_health, after_health)
            after_health = compute_market_data_health(
                repaired, tickers, expected_session=pd.Timestamp(expected), meta_file=meta_file,
                meta=_read_meta(meta_file), index_symbols=index_symbols,
            )
        print(f"\nManual repair checked {len(symbols)} eligible laggard(s).")
        print(after_health["diagnosis"], flush=True)
        return _download_result(tickers, after_health)

    # THE human-override point: this is the one line past which the provider is
    # actually contacted, so the operator's click spends its override here and nowhere
    # earlier. He may know the provider has just published; the ledger must not swallow
    # the very click that is the correct response to the incident.
    _clear_absent_session_ledger(meta_file)
    try:
        data = get_provider().fetch(tickers)
    except Exception as exc:
        state = record_repair_attempt(meta_file, before_health, None, error_text=str(exc))
        msg = f"market-data provider failed: {exc}"
        log.warning("Download-only cache refresh failed: %s", msg)
        raise StaleMarketDataError(
            f"{msg}; retry {state.get('next_retry_at') or 'later'}",
            n_setups=None,
        ) from exc

    after_health = compute_market_data_health(
        data, tickers, expected_session=pd.Timestamp(expected), meta_file=meta_file,
        meta=_read_meta(meta_file), index_symbols=index_symbols,
    )
    if after_health["can_archive"]:
        clear_repair_state(meta_file)
    elif after_health["health_state"] == "session_lag":
        # Do NOT spend the repair budget here. record_repair_attempt's vocabulary is
        # per-symbol sparseness: on an absent session the missing set is the whole
        # eligible universe, so its signature is identical on every attempt and
        # attempt_count escalates to symbol_lagging on the third — which sets
        # can_download=False and makes the Refresh button early-return "repair is not
        # ready" until something unrelated heals the cache. There is no per-symbol
        # laggard to repair when the session itself is absent.
        clear_repair_state(meta_file)
    else:
        record_repair_attempt(meta_file, before_health, after_health)
        after_health = compute_market_data_health(
            data, tickers, expected_session=pd.Timestamp(expected), meta_file=meta_file,
            meta=_read_meta(meta_file), index_symbols=index_symbols,
        )

    # "session_lag" belongs here too: it is READABLE (evaluation may proceed on the
    # cache's own last session) but this job exists to REACH the expected session, so
    # finishing still a session behind is a failed refresh, not a success. Without it
    # the run exits 0 / status "ok" and raises no degraded-fetch alert on a day the
    # cache never advanced — and it composes with the cold-retry cooldown, which can
    # return in seconds.
    if after_health["health_state"] in REFRESH_FAILURE_STATES:
        msg = f"stale market data: {after_health['diagnosis']}"
        log.warning("Download-only cache refresh did not reach current data: %s", msg)
        raise StaleMarketDataError(msg, n_setups=None)

    print(f"\nMarket-data cache health: {after_health['diagnosis']}", flush=True)
    return _download_result(tickers, after_health)


def _cached_health(cache_file: str, meta_file: str, tickers: list[str],
                   expected: str, index_symbols: list[str]) -> dict | None:
    if not os.path.exists(cache_file):
        return None
    try:
        data = pd.read_parquet(cache_file, engine=settings.PARQUET_ENGINE)
    except Exception:
        return None
    return compute_market_data_health(
        data,
        tickers,
        expected_session=pd.Timestamp(expected),
        meta_file=meta_file,
        meta=_read_meta(meta_file),
        index_symbols=index_symbols,
        weekly_refresh_due=_weekly_refresh_due(_read_meta(meta_file)),
    )


def _download_result(tickers: list[str], health: dict) -> DownloadOnlyResult:
    return DownloadOnlyResult(
        n_tickers=len(tickers),
        latest_session=health.get("cache_last_session"),
        expected_session=health.get("expected_session"),
        coverage=health["coverage"]["eligible"]["text"],
        health_state=health["health_state"],
        coverage_detail=health["coverage"],
        ready=bool(health["can_archive"]),
        partial=not bool(health["can_archive"]),
        cooldown_until=health.get("next_retry_at"),
        retry_reason=health.get("retry_reason"),
        help_needed=bool(health.get("help_needed")),
        message=health["diagnosis"],
    )
