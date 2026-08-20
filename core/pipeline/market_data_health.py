"""Market-data cache health, coverage, and repair-state helpers."""
from __future__ import annotations

import hashlib
import os
import re
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime

import pandas as pd

from config import settings
from core.pipeline.cache import _cache_paths, _read_meta, _weekly_refresh_due, _write_meta
from core.pipeline.data_freshness import (
    CloseCoverage,
    close_coverage_on,
    history_too_shallow,
    last_complete_reference_date,
    symbols_missing_closes_on,
    unique_symbols,
)
from core.pipeline.fetch_health import load_quarantine, split_active
from core.pipeline.ticker_admission import load_admission, split_downloadable

REPAIR_STATE_KEY = "repair_state"
PROVIDER_RATE_LIMITED = "provider_rate_limited"
SPARSE_SYMBOLS = "sparse_symbols"
SYMBOL_LAGGING = "symbol_lagging"

# The classifier's CLOSED health_state vocabulary (EC-33). Every consumer routes
# through the derived groups below — never a re-typed subset — so adding a state
# here forces a conscious grouping decision instead of a silent fail-open filter.
HEALTH_STATES = (
    "healthy",
    "market_wait",
    "session_lag",
    "needs_repair",
    "provider_cooldown",
    "symbol_lagging",
    "stale_session",
    "shallow_history",
    "regime_mismatch",
)


def _state_group(*names: str) -> frozenset:
    unregistered = set(names) - set(HEALTH_STATES)
    if unregistered:
        raise ValueError(f"unregistered health_state(s): {sorted(unregistered)}")
    return frozenset(names)


# CURRENT-session coverage shortfalls: per-ticker archivable, so scan_job routes
# them to degraded_coverage instead of aborting the archive outright.
DEGRADED_COVERAGE_STATES = _state_group(
    "needs_repair", "symbol_lagging", "provider_cooldown"
)
# A download-only refresh finishing in one of these never reached usable current
# data, so the job must raise rather than exit "ok" (session_lag included: the
# panel is readable, but this job exists to REACH the expected session).
REFRESH_FAILURE_STATES = _state_group(
    "stale_session", "shallow_history", "regime_mismatch", "session_lag"
)


@dataclass(frozen=True)
class SymbolScope:
    raw_tickers: list[str]
    raw_symbols: list[str]
    eligible_symbols: list[str]
    eligible_tickers: list[str]
    index_symbols: list[str]
    skipped_admission: list[str]
    skipped_quarantined: list[str]
    admission_skip_counts: dict[str, int]


def build_symbol_scope(tickers: list[str], meta_file: str | None = None,
                       index_symbols: list[str] | None = None) -> SymbolScope:
    if meta_file is None:
        _, meta_file = _cache_paths()
    # ``index_symbols`` is the universe's regime set (callers pass the resolved
    # Universe.index_symbols). Default = the US-Stocks global, so an unparameterized
    # call is byte-identical. An index-less universe (commodities_etf → ()) carries
    # no SPY/QQQ, so it must NOT be forced through them (the universe-blind bug).
    if index_symbols is None:
        index_symbols = list(getattr(settings, "INDEX_SYMBOLS", [settings.SPY_SYMBOL]))
    else:
        index_symbols = list(index_symbols)
    raw_tickers = unique_symbols(list(tickers))
    raw_symbols = unique_symbols(raw_tickers + index_symbols)

    quarantine = (
        load_quarantine(_state_path(meta_file, "QUARANTINE_FILENAME", "ticker_quarantine.json"))
        if getattr(settings, "QUARANTINE_ENABLED", True)
        else {}
    )
    active, skipped_quarantined = split_active(
        raw_symbols, quarantine, index_symbols=index_symbols
    )

    admission = (
        load_admission(_state_path(meta_file, "TICKER_ADMISSION_FILENAME", "ticker_admission.json"))
        if getattr(settings, "TICKER_ADMISSION_ENABLED", True)
        else {}
    )
    eligible_symbols, skipped_admission, admission_skip_counts = split_downloadable(
        active, admission, index_symbols=index_symbols
    )
    eligible_tickers = [s for s in eligible_symbols if s not in set(index_symbols)]
    return SymbolScope(
        raw_tickers=raw_tickers,
        raw_symbols=raw_symbols,
        eligible_symbols=eligible_symbols,
        eligible_tickers=eligible_tickers,
        index_symbols=index_symbols,
        skipped_admission=skipped_admission,
        skipped_quarantined=skipped_quarantined,
        admission_skip_counts=admission_skip_counts,
    )


def eligible_tickers_for(tickers: list[str], meta_file: str | None = None,
                         index_symbols: list[str] | None = None) -> list[str]:
    return build_symbol_scope(tickers, meta_file, index_symbols).eligible_tickers


def compute_market_data_health(
    data: pd.DataFrame,
    tickers: list[str],
    *,
    expected_session: pd.Timestamp | None = None,
    meta: dict | None = None,
    meta_file: str | None = None,
    index_symbols: list[str] | None = None,
    now_utc: datetime | None = None,
    closed_reason: str | None = None,
    weekly_refresh_due: bool | None = None,
) -> dict:
    if meta_file is None:
        _, meta_file = _cache_paths()
    if meta is None:
        meta = _read_meta(meta_file)
    if expected_session is None:
        from core.pipeline.market_calendar import latest_completed_session
        expected_session = latest_completed_session()
    expected_session = pd.Timestamp(expected_session).normalize()
    now_utc = _as_utc(now_utc)

    panel = _normalize_index(data)
    scope = build_symbol_scope(tickers, meta_file, index_symbols)
    min_coverage = float(getattr(settings, "MARKET_DATA_MIN_LATEST_COVERAGE", 0.95))

    # DERIVE it rather than echo the parameter. It was published as a fact while five of
    # seven production call sites never computed it, so an `after_health` payload
    # reported "no refresh due" on a day one was overdue — the same silent-default class
    # this key was added to fix. The parameter stays for tests and for a caller that has
    # already computed it.
    if weekly_refresh_due is None:
        weekly_refresh_due = _weekly_refresh_due(meta)

    # Price-regime guard — the SAME test fetch_data / _read_cached_market_data
    # apply. A cache fetched under a different DATA_DIVIDEND_ADJUSTED regime is
    # refused by evaluation and only a full cold refetch may replace it, so
    # health must tell that story too — not report healthy while eval raises
    # and the download-only repair early-returns "already healthy".
    from core.pipeline.downloads import _meta_regime_mismatch, _price_regime  # noqa: PLC0415 — lazy, yfinance-heavy module
    regime_mismatch = _meta_regime_mismatch(meta)
    regime_note = (
        f"Cache price-series regime ({meta.get('price_series', 'div_adjusted')}) "
        f"differs from settings ({_price_regime()}); evaluation refuses this "
        "cache — a full cold refetch must rebuild it."
    ) if regime_mismatch else None

    raw_coverage = close_coverage_on(panel, scope.raw_symbols, expected_session)
    eligible_coverage = close_coverage_on(panel, scope.eligible_symbols, expected_session)
    raw_missing = symbols_missing_closes_on(panel, scope.raw_symbols, expected_session)
    eligible_missing = symbols_missing_closes_on(panel, scope.eligible_symbols, expected_session)
    index_missing = symbols_missing_closes_on(panel, scope.index_symbols, expected_session)
    last_reference = last_complete_reference_date(panel, scope.index_symbols)
    cache_last_session = last_reference
    if cache_last_session is None and panel is not None and not panel.empty:
        cache_last_session = pd.Timestamp(panel.index.max()).normalize()
    if not scope.index_symbols:
        # Index-less universe (e.g. commodities_etf): there is no SPY/QQQ reference
        # bar to anchor on, so freshness is judged purely on the panel's own latest
        # session + eligible coverage. Without this, last_reference is always None
        # and _classify reads the universe as stale_session on EVERY run, making it
        # permanently un-evaluable and un-archivable.
        last_reference = cache_last_session

    repair_state = repair_state_from_meta(meta, now_utc)
    missing_summary = _missing_summary(
        panel, scope, raw_missing, eligible_missing, expected_session
    )
    # Deep-history integrity (the "second half" of the multi-universe cache bug).
    # Only judged when the panel itself spans >= the bar floor — a short/new cache
    # can't carry deep symbols and must NOT be flagged. Below the coverage floor =>
    # the NaN-wipe shape (recent bars, hollow history) => not trustworthy for
    # archive/eval; refresh / fetch_data force a full cold refetch instead.
    min_history_bars = int(getattr(settings, "MARKET_DATA_MIN_HISTORY_BARS", 100))
    min_history_cov = float(getattr(settings, "MARKET_DATA_MIN_HISTORY_COVERAGE", 0.5))
    # Same depth predicate as the downloader (data_freshness.history_too_shallow),
    # just scoped to the eligible symbols. The shared helper already returns
    # "not shallow" for an empty/short panel, so the prior len-guard is folded in.
    history_ok = not history_too_shallow(
        panel, scope.eligible_symbols, min_bars=min_history_bars, min_cov=min_history_cov
    )
    # How complete the cache is through its OWN last session, and how far that sits
    # behind the expected one. Together these separate "incomplete panel" from
    # "complete panel, older session" — see _evaluable_despite_lag.
    cache_last_coverage = None
    lag_sessions = None
    if cache_last_session is not None:
        from core.pipeline.market_calendar import session_gap  # noqa: PLC0415 — lazy, mirrors expected_session above
        from core.pipeline.downloads import absent_sessions  # noqa: PLC0415 — lazy, yfinance-heavy module
        # A session the provider has PROVEN it does not carry is not staleness: the
        # cache is as current as the data that exists. Counting it would let one phantom
        # session consume the entire budget — measured, the 2026-07-24 loss made the
        # tolerance expire at 16:31 ET the very next day and hard-block evaluation again,
        # which is exactly what this state was added to prevent.
        lag_sessions = max(0, session_gap(cache_last_session, expected_session)
                           - _absent_sessions_between(absent_sessions(meta),
                                                      cache_last_session, expected_session))
        # On a current cache this is eligible_coverage by definition, and the per-symbol
        # scan costs ~350 ms on the live 5,500-symbol panel — pay it only when the cache
        # is genuinely behind, which is the only case the value can affect the verdict.
        cache_last_coverage = (
            eligible_coverage
            if pd.Timestamp(cache_last_session).normalize() == expected_session
            else close_coverage_on(panel, scope.eligible_symbols, cache_last_session)
        )

    # Keyword args deliberately: this call reached thirteen positional parameters, three
    # of them session-shaped and two interchangeable Coverage objects, so a mis-ordered
    # insertion would type-check silently and surface only as a wrong health state — in
    # the one function that decides whether the operator may read or archive his data.
    health_state, severity, can_evaluate, can_archive, can_download, help_needed = _classify(
        cache_last_session=cache_last_session,
        last_reference=last_reference,
        expected_session=expected_session,
        index_missing=index_missing,
        eligible_coverage=eligible_coverage,
        min_coverage=min_coverage,
        repair_state=repair_state,
        closed_reason=closed_reason,
        weekly_refresh_due=weekly_refresh_due,
        history_ok=history_ok,
        regime_mismatch=regime_mismatch,
        cache_last_coverage=cache_last_coverage,
        lag_sessions=lag_sessions,
    )
    # Registry tripwire (EC-33): a state _classify emits without joining
    # HEALTH_STATES would silently fail open through every derived-group filter.
    assert health_state in HEALTH_STATES, f"unregistered health_state: {health_state!r}"

    diagnosis = _diagnosis(
        health_state=health_state,
        raw_coverage=raw_coverage,
        eligible_coverage=eligible_coverage,
        min_coverage=min_coverage,
        missing_summary=missing_summary,
        cache_last_session=cache_last_session,
        expected_session=expected_session,
        repair_state=repair_state,
        regime_note=regime_note,
        cache_last_coverage=cache_last_coverage,
        lag_sessions=lag_sessions,
    )
    download_label = _download_label(
        health_state,
        can_download,
        weekly_refresh_due,
        missing_summary["eligible_missing_count"],
        repair_state,
    )

    coverage = {
        "raw": _coverage_payload(raw_coverage),
        "eligible": _coverage_payload(eligible_coverage),
        # How complete the cache is through its OWN last session — the number that
        # tells a one-session lag apart from a dead cache. The three above are all
        # measured on the EXPECTED session, so they all read 0% when the provider
        # has not published it.
        "cache_last": (_coverage_payload(cache_last_coverage)
                       if cache_last_coverage is not None else None),
        "archive_target": min_coverage,
        # Compatibility: previous callers expected coverage.text/ratio.
        **_coverage_payload(eligible_coverage),
    }
    return {
        "health_state": health_state,
        "status": health_state,
        "severity": severity,
        # Consumed by scan_job._refresh_market_data_cache_locked to decide whether an
        # archive-healthy cache still owes a weekly cold refetch. It was passed IN but
        # never returned, so that guard silently read None and always skipped the refresh.
        "weekly_refresh_due": bool(weekly_refresh_due),
        # NOT named session_lag: that is a health_state, and this number is non-zero on
        # other states too, so one word would mean "the tolerance fired" in one place and
        # "how far behind, whatever the state" in another — and a truthiness test on it
        # would report readable-but-behind for a hard-stale cache.
        "sessions_behind": lag_sessions,
        "can_evaluate": can_evaluate,
        "can_archive": can_archive,
        "can_download": can_download,
        "download_label": download_label,
        "message": diagnosis,
        "diagnosis": diagnosis,
        "help_needed": help_needed,
        "expected_session": _date_str(expected_session),
        "cache_last_session": _date_str(cache_last_session),
        "coverage": coverage,
        "missing_summary": missing_summary,
        "next_retry_at": repair_state.get("next_retry_at"),
        "retry_seconds": repair_state.get("retry_seconds", 0),
        "retry_reason": repair_state.get("retry_reason"),
        "repair_state": repair_state,
    }


def record_repair_attempt(
    meta_file: str,
    before_health: dict | None,
    after_health: dict | None,
    *,
    error_text: str | None = None,
    now_utc: datetime | None = None,
) -> dict:
    now_utc = _as_utc(now_utc)
    meta = _read_meta(meta_file)
    previous = meta.get(REPAIR_STATE_KEY) if isinstance(meta.get(REPAIR_STATE_KEY), dict) else {}
    after_missing = _eligible_missing(after_health)
    before_missing = _eligible_missing(before_health)
    signature = missing_signature(after_missing or before_missing)
    previous_same = previous.get("missing_signature") == signature
    attempt_count = int(previous.get("attempt_count", 0)) + 1 if previous_same else 1

    error_class = classify_provider_error(error_text) if error_text else None
    retry_seconds = None
    help_needed = False
    if error_class == PROVIDER_RATE_LIMITED:
        retry_seconds = parse_retry_after_seconds(error_text, now_utc)
        if retry_seconds is None:
            retry_seconds = 20 * 60 if attempt_count > 1 else 15 * 60
        help_needed = attempt_count >= 2
    elif after_health and not after_health.get("can_archive", False):
        if attempt_count == 1:
            retry_seconds = int(getattr(settings, "MARKET_DATA_REPAIR_FIRST_RETRY_MINUTES", 10)) * 60
            error_class = SPARSE_SYMBOLS
        elif attempt_count == 2:
            retry_seconds = int(getattr(settings, "MARKET_DATA_REPAIR_SECOND_RETRY_MINUTES", 20)) * 60
            error_class = SPARSE_SYMBOLS
        else:
            error_class = SYMBOL_LAGGING
            help_needed = True
    else:
        clear_repair_state(meta_file)
        return {}

    next_retry_at = (
        (now_utc + timedelta(seconds=max(0, int(retry_seconds)))).isoformat()
        if retry_seconds is not None
        else None
    )
    state = {
        "last_attempt_at": now_utc.isoformat(),
        "attempt_count": attempt_count,
        "missing_signature": signature,
        "missing_eligible_before": len(before_missing),
        "missing_eligible_after": len(after_missing),
        "returned_count": max(0, len(before_missing) - len(after_missing)),
        "error_class": error_class or SPARSE_SYMBOLS,
        "next_retry_at": next_retry_at,
        "retry_reason": _retry_reason(error_class or SPARSE_SYMBOLS, len(after_missing)),
        "help_needed": help_needed,
    }
    if after_health:
        state["eligible_coverage_after"] = after_health["coverage"]["eligible"]["ratio"]
        state["raw_coverage_after"] = after_health["coverage"]["raw"]["ratio"]
    meta[REPAIR_STATE_KEY] = state
    meta.pop("repair_cooldown_until", None)
    meta.pop("repair_cooldown_reason", None)
    _write_meta(meta_file, meta)
    return repair_state_from_meta(meta, now_utc)


def clear_repair_state(meta_file: str) -> None:
    meta = _read_meta(meta_file)
    changed = False
    for key in (REPAIR_STATE_KEY, "repair_cooldown_until", "repair_cooldown_reason"):
        if key in meta:
            meta.pop(key, None)
            changed = True
    if changed:
        _write_meta(meta_file, meta)


def repair_state_from_meta(meta: dict, now_utc: datetime | None = None) -> dict:
    now_utc = _as_utc(now_utc)
    state = meta.get(REPAIR_STATE_KEY) if isinstance(meta.get(REPAIR_STATE_KEY), dict) else {}
    if not state and meta.get("repair_cooldown_until"):
        state = {
            "next_retry_at": meta.get("repair_cooldown_until"),
            "retry_reason": meta.get("repair_cooldown_reason"),
            "error_class": SPARSE_SYMBOLS,
            "attempt_count": 1,
        }
    next_retry_at = state.get("next_retry_at")
    retry_seconds = _seconds_until(next_retry_at, now_utc)
    out = dict(state)
    out["active"] = retry_seconds > 0
    out["retry_seconds"] = retry_seconds
    out["help_needed"] = bool(out.get("help_needed"))
    return out


def classify_provider_error(text: str | None) -> str | None:
    text = (text or "").lower()
    if "429" in text or "too many requests" in text or "yfratelimiterror" in text:
        return PROVIDER_RATE_LIMITED
    return None


def parse_retry_after_seconds(text: str | None, now_utc: datetime | None = None) -> int | None:
    if not text:
        return None
    now_utc = _as_utc(now_utc)
    match = re.search(r"retry-after\s*[:=]\s*([^\r\n;,]+)", text, re.IGNORECASE)
    if not match:
        return None
    value = match.group(1).strip().strip("'\"")
    if value.isdigit():
        return max(0, int(value))
    try:
        retry_at = parsedate_to_datetime(value)
    except (TypeError, ValueError):
        return None
    retry_at = _as_utc(retry_at)
    return max(0, int((retry_at - now_utc).total_seconds()))


def missing_signature(symbols: list[str]) -> str:
    payload = "\n".join(sorted(unique_symbols(symbols)))
    return hashlib.sha1(payload.encode("utf-8")).hexdigest()


def _absent_sessions_between(known_absent, after, upto) -> int:
    """Count recorded-absent sessions STRICTLY between ``after`` and ``upto``.

    Both endpoints are excluded, and the upper one is load-bearing: ``upto`` is the
    session we are waiting FOR, so discounting it would cancel the lag to zero on the
    very day the provider lost it — and a zero lag fails the tolerance's ``1 <= lag``
    test, blocking evaluation on exactly the incident this state exists to survive.
    Sessions in between are different: they are gaps we have already proven nobody can
    fill, so they are not staleness.

    Malformed entries are skipped rather than raised on — the ledger only ever forgives
    a gap, so a corrupt entry must degrade toward reporting MORE staleness, not less.
    """
    if not known_absent:
        return 0
    after = pd.Timestamp(after).normalize()
    upto = pd.Timestamp(upto).normalize()
    count = 0
    for day in known_absent:
        try:
            stamp = pd.Timestamp(day).normalize()
        except (TypeError, ValueError):
            continue
        if after < stamp < upto:
            count += 1
    return count


def _evaluable_despite_lag(history_ok, cache_last_coverage, expected_coverage,
                           lag_sessions, min_coverage) -> bool:
    """True when the cache is merely BEHIND the expected session, not broken.

    The distinction that matters: "this panel is incomplete" (block) versus "this
    panel is complete, through an older session" (readable). Measured 2026-07-24:
    the static NYSE rule calendar called it a session, Yahoo carried no bar for it
    at all, and since every freshness gate keys on Close a 98%-complete cache read
    as 0% coverage and evaluation was refused outright.

    Four conditions, each load-bearing:

    - the gap is 1..MARKET_DATA_EVALUATE_MAX_LAG_SESSIONS, so a long outage still
      reads as broken;
    - deep history is intact (a NaN-wiped panel is not readable at any lag);
    - the panel is complete through its OWN last session, so a cache that is both
      behind AND sparse still blocks — the tolerance must never launder one;
    - the expected session is essentially UNPUBLISHED. A half-published session is
      the dangerous case: the panel would carry the new session for some tickers
      and not others, and evaluation reads each ticker as-of its own last bar, so
      the result is a leaderboard mixing two dates. That case is a genuine repair
      target (the missing symbols really are fetchable), not a provider outage, so
      it must fall through to needs_repair.

    The unpublished bar is its OWN constant, deliberately not the complement of the
    trust bar: derived that way, lowering the trust bar below 0.5 would silently
    invert this condition and admit a MAJORITY-published session — the exact panel
    the paragraph above says must be refused.

    Callers must keep ``can_archive`` False — this permits READING only.
    """
    max_lag = int(getattr(settings, "MARKET_DATA_EVALUATE_MAX_LAG_SESSIONS", 0))
    if max_lag <= 0 or not history_ok:
        return False
    if lag_sessions is None or not (1 <= int(lag_sessions) <= max_lag):
        return False
    if cache_last_coverage is None or cache_last_coverage.ratio < min_coverage:
        return False
    unpublished_bar = float(
        getattr(settings, "PROVIDER_ABSENT_SESSION_MAX_COVERAGE", 0.02)
    )
    return expected_coverage is not None and expected_coverage.ratio <= unpublished_bar


def _classify(cache_last_session, last_reference, expected_session, index_missing,
              eligible_coverage, min_coverage, repair_state, closed_reason,
              weekly_refresh_due, history_ok=True, regime_mismatch=False,
              cache_last_coverage=None, lag_sessions=None):
    if regime_mismatch:
        # Wrong price-series regime outranks every other read: freshness and
        # coverage are meaningless across regimes, evaluation refuses the panel,
        # and only a full cold refetch (can_download) can fix it.
        return "regime_mismatch", "repair", False, False, True, True
    if last_reference is None or cache_last_session is None:
        return "stale_session", "blocked", False, False, True, True
    if _evaluable_despite_lag(history_ok, cache_last_coverage, eligible_coverage,
                              lag_sessions, min_coverage):
        # Complete through its OWN last session, just behind the expected one —
        # typically a provider that has not published the expected session's close
        # yet. Reading is safe; ARCHIVING is not (an archive row would be stamped
        # with the expected session while carrying the prior session's bars), so
        # can_archive is False here. That is the load-bearing block: scan_job's
        # _archive_freshness date compare reads the FIRST index symbol only, so it
        # is not an independent second gate when the index symbols disagree.
        return "session_lag", "watch", True, False, True, False
    if index_missing:
        return "stale_session", "blocked", False, False, True, True
    if pd.Timestamp(last_reference).normalize() < expected_session:
        return "stale_session", "blocked", False, False, True, True
    if eligible_coverage.ratio >= min_coverage:
        if not history_ok:
            # Latest session is current but most symbols lost their multi-year
            # history (the NaN-wipe shape). Refuse to trust it for archive/eval and
            # force a full cold refetch — never a latest-session-only repair, which
            # would leave the deep history hollow.
            return "shallow_history", "repair", False, False, True, True
        if weekly_refresh_due:
            return "healthy", "watch", True, True, True, False
        if closed_reason in {"weekend", "holiday", "before_open"}:
            return "market_wait", "ok", True, True, False, False
        return "healthy", "ok", True, True, False, False

    error_class = repair_state.get("error_class")
    if error_class == PROVIDER_RATE_LIMITED and repair_state.get("active"):
        return "provider_cooldown", "blocked", False, False, False, repair_state.get("help_needed", False)
    if error_class == SYMBOL_LAGGING:
        return "symbol_lagging", "blocked", False, False, False, True
    if repair_state.get("active"):
        return "needs_repair", "watch", False, False, False, False
    return "needs_repair", "repair", False, False, True, False


def _diagnosis(health_state, raw_coverage, eligible_coverage, min_coverage,
               missing_summary, cache_last_session, expected_session, repair_state,
               regime_note=None, cache_last_coverage=None, lag_sessions=None):
    if health_state == "session_lag":
        session_word = "session" if lag_sessions == 1 else "sessions"
        return (
            f"Cache is complete through {cache_last_session.date()} "
            f"({cache_last_coverage.format() if cache_last_coverage else 'n/a'}) but "
            f"{lag_sessions} {session_word} behind {expected_session.date()}, which has "
            f"{eligible_coverage.format()} closes. Evaluation reads the "
            f"{cache_last_session.date()} panel; archiving stays closed until the "
            "expected session lands."
        )
    if health_state == "regime_mismatch":
        # Coverage numbers are meaningless across price regimes; the note is
        # the whole story.
        return regime_note
    raw_text = raw_coverage.format()
    eligible_text = eligible_coverage.format()
    skipped = missing_summary["skipped_missing_count"]
    eligible_missing = missing_summary["eligible_missing_count"]
    base = f"Eligible coverage {eligible_text}; raw coverage {raw_text}."
    if skipped:
        base += f" {skipped} missing raw symbol(s) are admission/quarantine-skipped."
    if eligible_missing:
        base += f" {eligible_missing} eligible symbol(s) still lag the latest session."
    if health_state == "healthy":
        return f"{base} Archive target {min_coverage:.0%} is met."
    if health_state == "market_wait":
        return f"{base} Market is closed or waiting for the next completed session."
    if health_state == "stale_session":
        return (
            f"Cache reference session is {cache_last_session.date() if cache_last_session is not None else 'missing'}; "
            f"expected {expected_session.date()}."
        )
    if health_state == "shallow_history":
        return (
            f"{base} Cache is current but most symbols are missing their deep "
            f"history (truncated cache); a full cold refetch is required."
        )
    if health_state == "provider_cooldown":
        return f"{base} Provider retry is cooling down: {repair_state.get('retry_reason') or 'rate limited'}."
    if health_state == "symbol_lagging":
        return f"{base} The same symbols stayed stale after bounded repairs; review or wait for the next session."
    return f"{base} Repair eligible missing symbols before archive-quality evaluation."


def _download_label(health_state, can_download, weekly_refresh_due, eligible_missing, repair_state):
    if health_state == "healthy" and weekly_refresh_due:
        return "Refresh Data"
    if health_state in {"healthy", "market_wait"}:
        return "Not needed"
    if health_state == "session_lag":
        # Readable but behind: the download is worth offering (the expected session
        # may land at any time) without implying the cache is broken.
        return "Download New Data"
    if repair_state.get("active") and not can_download:
        return f"Cooldown {_minutes_label(repair_state.get('retry_seconds', 0))}"
    if health_state == "symbol_lagging":
        return "Needs help"
    if health_state == "provider_cooldown":
        return "Provider limited"
    if health_state == "stale_session":
        return "Download New Data"
    if health_state in {"shallow_history", "regime_mismatch"}:
        return "Rebuild Data"
    if health_state == "needs_repair":
        return f"Repair {eligible_missing}" if eligible_missing else "Repair Data"
    return "Download New Data"


def _missing_summary(panel, scope: SymbolScope, raw_missing: list[str],
                     eligible_missing: list[str], expected_session: pd.Timestamp) -> dict:
    skipped = set(scope.skipped_admission) | set(scope.skipped_quarantined)
    skipped_missing = [s for s in raw_missing if s in skipped]
    latest_dates, bar_counts = _latest_close_facts(panel, scope.raw_symbols)
    latest_counts = Counter(latest_dates.get(s, "NO_HISTORY") for s in eligible_missing)
    skipped_status_counts = Counter()
    for status, count in scope.admission_skip_counts.items():
        skipped_status_counts[status] += count
    if scope.skipped_quarantined:
        skipped_status_counts["quarantined"] += len(scope.skipped_quarantined)
    zero_history = [s for s in eligible_missing if bar_counts.get(s, 0) == 0]
    active_stale = [s for s in eligible_missing if bar_counts.get(s, 0) > 0]
    samples = [
        {
            "ticker": symbol,
            "latest": latest_dates.get(symbol),
            "bars": bar_counts.get(symbol, 0),
        }
        for symbol in eligible_missing[:12]
    ]
    return {
        "raw_missing_count": len(raw_missing),
        "eligible_missing_count": len(eligible_missing),
        "skipped_missing_count": len(skipped_missing),
        "skipped_admission_count": len(scope.skipped_admission),
        "skipped_quarantined_count": len(scope.skipped_quarantined),
        "skip_counts": dict(skipped_status_counts),
        "zero_history_count": len(zero_history),
        "active_ready_stale_count": len(active_stale),
        "latest_date_lag": dict(latest_counts),
        "eligible_missing_symbols": eligible_missing,
        "sample_tickers": samples,
        "expected_session": _date_str(expected_session),
    }


def _latest_close_facts(panel: pd.DataFrame, symbols: list[str]) -> tuple[dict[str, str], dict[str, int]]:
    if panel is None or panel.empty or not isinstance(panel.columns, pd.MultiIndex):
        return {}, {}
    try:
        closes = panel.xs("Close", axis=1, level=1)
    except KeyError:
        return {}, {}
    latest: dict[str, str] = {}
    counts: dict[str, int] = {}
    for symbol in symbols:
        if symbol not in closes.columns:
            counts[symbol] = 0
            continue
        series = closes[symbol].dropna()
        counts[symbol] = int(len(series))
        if not series.empty:
            latest[symbol] = pd.Timestamp(series.index.max()).date().isoformat()
    return latest, counts


def _coverage_payload(coverage: CloseCoverage) -> dict:
    return {
        "day": _date_str(coverage.day),
        "present": coverage.present,
        "total": coverage.total,
        "ratio": coverage.ratio,
        "text": coverage.format(),
    }


def _eligible_missing(health: dict | None) -> list[str]:
    if not health:
        return []
    summary = health.get("missing_summary") or {}
    return list(summary.get("eligible_missing_symbols") or [])


def _retry_reason(error_class: str, missing_count: int) -> str:
    if error_class == PROVIDER_RATE_LIMITED:
        return "provider rate limit"
    if error_class == SYMBOL_LAGGING:
        return f"{missing_count} symbol(s) stayed stale after bounded repairs"
    return f"{missing_count} symbol(s) still missing the latest close"


def _state_path(meta_file: str, setting_name: str, default_name: str) -> str:
    return os.path.join(os.path.dirname(meta_file), getattr(settings, setting_name, default_name))


def _normalize_index(data: pd.DataFrame) -> pd.DataFrame:
    if hasattr(data.index, "tz") and data.index.tz is not None:
        data = data.copy()
        data.index = data.index.tz_localize(None)
    return data


def _as_utc(value: datetime | None) -> datetime:
    if value is None:
        return datetime.now(timezone.utc)
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _seconds_until(value, now_utc: datetime) -> int:
    if not value:
        return 0
    try:
        when = datetime.fromisoformat(str(value))
    except ValueError:
        return 0
    when = _as_utc(when)
    return max(0, int((when - now_utc).total_seconds()))


def _minutes_label(seconds: int) -> str:
    return f"{max(1, int((int(seconds) + 59) // 60))}m"


def _date_str(value) -> str | None:
    if value is None:
        return None
    return pd.Timestamp(value).strftime("%Y-%m-%d")
