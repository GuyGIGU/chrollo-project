import json
import sys
from datetime import datetime, timedelta, timezone

import pandas as pd

from _paths import REPO_ROOT as ROOT
sys.path.insert(0, str(ROOT))

from core.pipeline.market_data.market_data_health import (
    DEGRADED_COVERAGE_STATES,
    HEALTH_STATES,
    REFRESH_FAILURE_STATES,
    compute_market_data_health,
    record_repair_attempt,
)


def test_health_state_groups_derive_from_the_registry():
    """EC-33: the closed health_state vocabulary lives in ONE tuple; the routing
    groups scan_job consumes are derived members, byte-identical to the hand-typed
    sets they replaced. _state_group raises at import on an unregistered name, and
    compute_market_data_health asserts every emitted state is a registry member."""
    assert DEGRADED_COVERAGE_STATES <= set(HEALTH_STATES)
    assert REFRESH_FAILURE_STATES <= set(HEALTH_STATES)
    assert DEGRADED_COVERAGE_STATES == {"needs_repair", "symbol_lagging", "provider_cooldown"}
    assert REFRESH_FAILURE_STATES == {
        "stale_session", "shallow_history", "regime_mismatch", "session_lag"
    }


def _write_tagged_meta(meta_file, last_full_refresh="recent"):
    """Current-regime meta. An untagged meta ({}) is a LEGACY div-adjusted cache
    and now (correctly) classifies regime_mismatch, so the classifier tests pin
    the tag to exercise the state they actually target.

    `last_full_refresh` defaults to a RECENT stamp because `weekly_refresh_due` is now
    derived from meta rather than defaulting to False — without it every classifier
    test would also be asserting "a weekly cold refetch is overdue", which is a
    different concern. Pass None to exercise the overdue case."""
    from core.pipeline.market_data.downloads import _price_regime

    meta = {"price_series": _price_regime()}
    if last_full_refresh == "recent":
        meta["last_full_refresh"] = datetime.now(timezone.utc).isoformat()
    elif last_full_refresh is not None:
        meta["last_full_refresh"] = last_full_refresh
    meta_file.write_text(json.dumps(meta), encoding="utf-8")


def _panel(symbols, day):
    return pd.concat(
        {
            symbol: pd.DataFrame({"Close": [10.0], "Volume": [1000]}, index=[pd.Timestamp(day)])
            for symbol in symbols
        },
        axis=1,
    )


def _health(missing):
    total = len(missing) + 3
    present = total - len(missing)
    text = f"{present}/{total} ({present / total:.1%})"
    return {
        "can_archive": False,
        "coverage": {
            "eligible": {"ratio": present / total, "text": text},
            "raw": {"ratio": present / total, "text": text},
        },
        "missing_summary": {
            "eligible_missing_symbols": missing,
        },
    }


def test_raw_partial_but_eligible_healthy_is_green(tmp_path, monkeypatch):
    meta_file = tmp_path / "cache_meta.json"
    _write_tagged_meta(meta_file)
    (tmp_path / "ticker_admission.json").write_text(
        json.dumps({
            "YNG": {
                "status": "active_young",
                "next_check": (datetime.now(timezone.utc) + timedelta(days=5)).isoformat(),
            },
        }),
        encoding="utf-8",
    )
    monkeypatch.setattr("core.pipeline.market_data.market_data_health.settings.MARKET_DATA_MIN_LATEST_COVERAGE", 0.95)

    health = compute_market_data_health(
        _panel(["AAA", "SPY", "QQQ"], "2026-06-25"),
        ["AAA", "YNG"],
        expected_session=pd.Timestamp("2026-06-25"),
        meta_file=str(meta_file),
    )

    assert health["health_state"] == "healthy"
    assert health["can_evaluate"] is True
    assert health["can_archive"] is True
    assert health["can_download"] is False
    assert health["coverage"]["raw"]["text"] == "3/4 (75.0%)"
    assert health["coverage"]["eligible"]["text"] == "3/3 (100.0%)"
    assert health["missing_summary"]["skipped_missing_count"] == 1


def test_index_less_universe_is_healthy_on_its_own_coverage(tmp_path, monkeypatch):
    """Fix ②: a universe with no regime index symbols (commodities_etf →
    index_symbols=()) is judged on its OWN panel freshness + coverage, not forced
    through SPY/QQQ. Before the fix, last_reference was always None for such a
    universe so it read as stale_session on every run (un-archivable forever)."""
    meta_file = tmp_path / "cache_meta_commodities_etf.json"
    _write_tagged_meta(meta_file)
    monkeypatch.setattr("core.pipeline.market_data.market_data_health.settings.MARKET_DATA_MIN_LATEST_COVERAGE", 0.95)

    panel = _panel(["GLD", "USO", "UNG"], "2026-06-29")  # ETFs only, no SPY/QQQ
    health = compute_market_data_health(
        panel,
        ["GLD", "USO", "UNG"],
        expected_session=pd.Timestamp("2026-06-29"),
        meta_file=str(meta_file),
        index_symbols=[],  # the commodities_etf regime set
    )

    assert health["health_state"] in {"healthy", "market_wait"}
    assert health["can_evaluate"] is True
    assert health["can_archive"] is True
    assert health["cache_last_session"] == "2026-06-29"


def test_index_less_universe_still_flags_stale_when_behind(tmp_path):
    """The index-less path is no free pass: gated on the panel's own latest
    session, a panel lagging the expected session is still correctly stale."""
    meta_file = tmp_path / "cache_meta_commodities_etf.json"
    _write_tagged_meta(meta_file)
    panel = _panel(["GLD", "USO", "UNG"], "2026-06-20")  # behind expected
    health = compute_market_data_health(
        panel,
        ["GLD", "USO", "UNG"],
        expected_session=pd.Timestamp("2026-06-29"),
        meta_file=str(meta_file),
        index_symbols=[],
    )
    assert health["health_state"] == "stale_session"
    assert health["can_archive"] is False


def _lagging_panel(index_days, ticker_days):
    """Panel where the index symbols and the plain tickers stop on DIFFERENT days,
    so the cache's own last session can be made complete or sparse at will."""
    frames = {}
    for symbol in ("SPY", "QQQ"):
        frames[symbol] = pd.DataFrame(
            {"Close": [10.0] * len(index_days), "Volume": [1000] * len(index_days)},
            index=[pd.Timestamp(d) for d in index_days],
        )
    for symbol in ("AAA", "BBB"):
        frames[symbol] = pd.DataFrame(
            {"Close": [10.0] * len(ticker_days), "Volume": [1000] * len(ticker_days)},
            index=[pd.Timestamp(d) for d in ticker_days],
        )
    return pd.concat(frames, axis=1)


def test_one_session_lag_with_complete_panel_is_readable(tmp_path):
    """Operator ruling 2026-07-27. A cache complete through its OWN last session but
    one completed session behind the expected one is readable — the shape seen when the static
    NYSE rule calendar calls a day a session and the provider has no bar for it
    (measured 2026-07-24). Archiving stays shut."""
    meta_file = tmp_path / "cache_meta.json"
    _write_tagged_meta(meta_file)
    panel = _panel(["AAA", "SPY", "QQQ"], "2026-06-24")
    health = compute_market_data_health(
        panel,
        ["AAA"],
        expected_session=pd.Timestamp("2026-06-25"),
        meta_file=str(meta_file),
    )
    assert health["health_state"] == "session_lag"
    assert health["can_evaluate"] is True
    assert health["can_archive"] is False
    assert health["sessions_behind"] == 1
    assert health["coverage"]["cache_last"]["ratio"] == 1.0


def test_one_session_lag_still_blocks_when_the_cached_session_is_sparse(tmp_path):
    """The tolerance requires completeness through the cache's own last session, so
    it cannot launder a genuinely broken panel: behind AND sparse stays blocked."""
    meta_file = tmp_path / "cache_meta.json"
    _write_tagged_meta(meta_file)
    # SPY/QQQ reach 06-24 (so cache_last_session is 06-24, a 1-session lag) but the
    # evaluated tickers stop a day earlier — 0% coverage on that session.
    panel = _lagging_panel(["2026-06-23", "2026-06-24"], ["2026-06-23"])
    health = compute_market_data_health(
        panel,
        ["AAA", "BBB"],
        expected_session=pd.Timestamp("2026-06-25"),
        meta_file=str(meta_file),
    )
    assert health["health_state"] == "stale_session"
    assert health["can_evaluate"] is False
    assert health["can_archive"] is False


def test_a_half_published_session_is_repaired_not_tolerated(tmp_path):
    """The dangerous shape. If the expected session is published for SOME tickers,
    the panel carries two as-of dates and evaluation would read each ticker at its
    own last bar — a leaderboard mixing sessions. That is a real repair target, so
    it must fall through rather than take the lag tolerance.

    MUTATION-SENSITIVE BY CONSTRUCTION: the index symbols must stop one session SHORT
    while a minority of evaluated tickers already carry the expected session, so the
    lag is genuinely 1 and the expected-coverage condition is the only thing refusing
    it. Built the obvious way (index symbols current), cache_last_session equals the
    expected session, the lag is 0, and the predicate returns False at the lag-range
    check — leaving the condition this test exists to pin completely unexercised."""
    meta_file = tmp_path / "cache_meta.json"
    _write_tagged_meta(meta_file)
    # SPY/QQQ stop at 06-24 -> cache_last_session = 06-24, a 1-session lag.
    # AAA/BBB are complete through 06-24 AND one of them already carries 06-25,
    # so the expected session is 50% published — far above the "essentially
    # unpublished" bar the tolerance requires.
    frames = {}
    for symbol in ("SPY", "QQQ", "AAA"):
        frames[symbol] = pd.DataFrame(
            {"Close": [10.0], "Volume": [1000]}, index=[pd.Timestamp("2026-06-24")]
        )
    frames["BBB"] = pd.DataFrame(
        {"Close": [10.0, 11.0], "Volume": [1000, 1100]},
        index=[pd.Timestamp("2026-06-24"), pd.Timestamp("2026-06-25")],
    )
    health = compute_market_data_health(
        pd.concat(frames, axis=1),
        ["AAA", "BBB"],
        expected_session=pd.Timestamp("2026-06-25"),
        meta_file=str(meta_file),
    )
    from config import settings as _settings
    assert health["sessions_behind"] == 1, "the lag-range check must NOT be what refuses this"
    assert (health["coverage"]["eligible"]["ratio"]
            > _settings.PROVIDER_ABSENT_SESSION_MAX_COVERAGE), (
        "the expected session must be genuinely PART-published — otherwise this panel "
        "is the absent-session shape and the tolerance is right to accept it")
    # Specifically stale_session, not merely "not session_lag": the index symbols also
    # lack the expected session, so it falls through the index guard. Asserting the
    # concrete state means a future reclassification has to be looked at, and unlike a
    # negative assertion it cannot be satisfied by cache_missing or a crash-shaped state.
    assert health["health_state"] == "stale_session"
    assert health["can_evaluate"] is False
    assert health["can_archive"] is False


def test_a_session_proven_absent_does_not_count_against_the_lag_budget(tmp_path):
    """The budget must count sessions the provider COULD have published. A phantom
    session (the calendar says it exists, a full fetch proved the provider has no bar
    for it) otherwise consumes the whole budget on its own — measured, the 2026-07-24
    loss made the tolerance expire at 16:31 ET the very next day and hard-block
    evaluation again, which is precisely what this state exists to prevent."""
    meta_file = tmp_path / "cache_meta.json"
    _write_tagged_meta(meta_file)
    panel = _panel(["AAA", "SPY", "QQQ"], "2026-06-23")

    def _health(meta_extra):
        import json as _json
        meta = _json.loads(meta_file.read_text(encoding="utf-8"))
        meta.update(meta_extra)
        meta_file.write_text(_json.dumps(meta), encoding="utf-8")
        return compute_market_data_health(
            panel, ["AAA"],
            expected_session=pd.Timestamp("2026-06-25"),
            meta_file=str(meta_file),
        )

    # 06-23 -> 06-25 is two sessions: over budget, so hard-blocked.
    assert _health({})["health_state"] == "stale_session"
    # ...but if 06-24 is recorded absent upstream, only 06-25 is genuinely missing.
    tolerated = _health({"absent_sessions": ["2026-06-24"]})
    assert tolerated["sessions_behind"] == 1
    assert tolerated["health_state"] == "session_lag"
    assert tolerated["can_evaluate"] is True
    assert tolerated["can_archive"] is False
    # The discount is still BOUNDED — one forgiven session does not forgive the next.
    assert _health({"absent_sessions": ["2026-06-24"],
                    "__unused": 0})["can_evaluate"] is True
    over_budget = compute_market_data_health(
        panel, ["AAA"], expected_session=pd.Timestamp("2026-06-26"),
        meta_file=str(meta_file),
    )
    assert over_budget["health_state"] == "stale_session"


def test_the_expected_session_itself_is_never_discounted(tmp_path):
    """Endpoint case, and it is load-bearing. `upto` is the session we are waiting FOR,
    so discounting it would cancel the lag to zero on the very day the provider lost
    it — and a zero lag fails the tolerance's `1 <= lag` test, blocking evaluation on
    exactly the incident this state exists to survive."""
    meta_file = tmp_path / "cache_meta.json"
    _write_tagged_meta(meta_file)
    import json as _json
    meta = _json.loads(meta_file.read_text(encoding="utf-8"))
    meta["absent_sessions"] = ["2026-06-25"]          # the EXPECTED session is the absent one
    meta_file.write_text(_json.dumps(meta), encoding="utf-8")

    health = compute_market_data_health(
        _panel(["AAA", "SPY", "QQQ"], "2026-06-24"), ["AAA"],
        expected_session=pd.Timestamp("2026-06-25"), meta_file=str(meta_file),
    )
    assert health["sessions_behind"] == 1, "the expected session must not discount itself"
    assert health["health_state"] == "session_lag"
    assert health["can_evaluate"] is True


def test_lag_tolerance_is_disabled_at_zero(tmp_path, monkeypatch):
    """MARKET_DATA_EVALUATE_MAX_LAG_SESSIONS = 0 restores the prior hard block."""
    monkeypatch.setattr(
        "core.pipeline.market_data.market_data_health.settings.MARKET_DATA_EVALUATE_MAX_LAG_SESSIONS",
        0,
        raising=False,
    )
    meta_file = tmp_path / "cache_meta.json"
    _write_tagged_meta(meta_file)
    panel = _panel(["AAA", "SPY", "QQQ"], "2026-06-24")
    health = compute_market_data_health(
        panel,
        ["AAA"],
        expected_session=pd.Timestamp("2026-06-25"),
        meta_file=str(meta_file),
    )
    assert health["health_state"] == "stale_session"
    assert health["can_evaluate"] is False


def test_default_index_symbols_still_require_spy_qqq(tmp_path):
    """Byte-identity guard: with index_symbols defaulted (None), the US-Stocks
    behavior is unchanged — a panel missing SPY/QQQ on the session is stale."""
    meta_file = tmp_path / "cache_meta.json"
    _write_tagged_meta(meta_file)
    panel = _panel(["AAA", "BBB"], "2026-06-29")  # no SPY/QQQ present
    health = compute_market_data_health(
        panel,
        ["AAA", "BBB"],
        expected_session=pd.Timestamp("2026-06-29"),
        meta_file=str(meta_file),
    )
    assert health["health_state"] == "stale_session"
    assert health["can_archive"] is False


def test_regime_mismatched_meta_reports_rebuild_not_healthy(tmp_path, monkeypatch):
    """P2 #3: after a DATA_DIVIDEND_ADJUSTED flip (or on an untagged legacy meta)
    the panel can look perfectly fresh, but evaluation refuses a wrong-regime
    cache — health must tell the SAME story (rebuild via download), not report
    healthy while eval raises and the download-only repair early-returns."""
    from config import settings

    monkeypatch.setattr(settings, "DATA_DIVIDEND_ADJUSTED", False, raising=False)
    meta_file = tmp_path / "cache_meta.json"
    meta_file.write_text("{}", encoding="utf-8")  # legacy/untagged = div_adjusted

    health = compute_market_data_health(
        _panel(["AAA", "SPY", "QQQ"], "2026-06-25"),  # fresh, full coverage
        ["AAA"],
        expected_session=pd.Timestamp("2026-06-25"),
        meta_file=str(meta_file),
    )

    assert health["health_state"] == "regime_mismatch"
    assert health["can_evaluate"] is False
    assert health["can_archive"] is False
    assert health["can_download"] is True
    assert health["download_label"] == "Rebuild Data"
    assert "price-series regime" in health["diagnosis"]


def _multi_row_panel(symbols, n_rows, deep_symbols, end_day):
    """Panel spanning ``n_rows`` business days. ``deep_symbols`` carry a Close on
    every bar; the rest carry only the last 6 bars (the NaN-wipe corruption shape)."""
    idx = pd.bdate_range(end=pd.Timestamp(end_day), periods=n_rows)
    frames = {}
    for s in symbols:
        close = pd.Series([float("nan")] * n_rows, index=idx)
        if s in deep_symbols:
            close[:] = 10.0
        else:
            close.iloc[-6:] = 10.0
        frames[s] = pd.DataFrame({"Close": close.values, "Volume": [1000] * n_rows}, index=idx)
    return pd.concat(frames, axis=1)


def test_shallow_deep_history_is_not_trusted(tmp_path, monkeypatch):
    """Fix ①: a cache whose latest session is fine but whose deep history is
    NaN-wiped (the exact incident shape) must NOT report can_archive — it is
    shallow_history, which drives a full cold refetch, not a no-op repair."""
    meta_file = tmp_path / "cache_meta.json"
    _write_tagged_meta(meta_file)
    monkeypatch.setattr("core.pipeline.market_data.market_data_health.settings.MARKET_DATA_MIN_LATEST_COVERAGE", 0.95)
    monkeypatch.setattr("core.pipeline.market_data.market_data_health.settings.MARKET_DATA_MIN_HISTORY_BARS", 100)
    monkeypatch.setattr("core.pipeline.market_data.market_data_health.settings.MARKET_DATA_MIN_HISTORY_COVERAGE", 0.5)

    tickers = ["AAA", "BBB", "CCC", "DDD", "EEE", "FFF"]
    panel = _multi_row_panel(tickers + ["SPY", "QQQ"], 150, {"SPY", "QQQ"}, "2026-06-29")
    health = compute_market_data_health(
        panel, tickers, expected_session=pd.Timestamp("2026-06-29"), meta_file=str(meta_file),
    )
    assert health["health_state"] == "shallow_history"
    assert health["can_archive"] is False
    assert health["can_evaluate"] is False
    assert health["can_download"] is True


def test_full_history_panel_stays_healthy(tmp_path, monkeypatch):
    """The depth gate must NOT reject a genuinely healthy full-history cache."""
    meta_file = tmp_path / "cache_meta.json"
    _write_tagged_meta(meta_file)
    monkeypatch.setattr("core.pipeline.market_data.market_data_health.settings.MARKET_DATA_MIN_LATEST_COVERAGE", 0.95)
    monkeypatch.setattr("core.pipeline.market_data.market_data_health.settings.MARKET_DATA_MIN_HISTORY_BARS", 100)

    tickers = ["AAA", "BBB", "CCC"]
    panel = _multi_row_panel(tickers + ["SPY", "QQQ"], 150,
                             set(tickers) | {"SPY", "QQQ"}, "2026-06-29")
    health = compute_market_data_health(
        panel, tickers, expected_session=pd.Timestamp("2026-06-29"), meta_file=str(meta_file),
    )
    assert health["health_state"] == "healthy"
    assert health["can_archive"] is True


def test_short_panel_is_not_flagged_shallow(tmp_path):
    """A short/new cache (fewer rows than the bar floor) can't carry deep symbols
    and must NOT be flagged shallow — the gate only judges long-span panels."""
    from core.pipeline.market_data.downloads import _history_too_shallow

    syms = ["AAA", "BBB", "CCC", "DDD", "SPY", "QQQ"]
    short = _multi_row_panel(syms, 30, {"SPY", "QQQ"}, "2026-06-29")
    assert _history_too_shallow(short, syms) is False  # too short to judge depth
    long_hollow = _multi_row_panel(syms, 150, {"SPY", "QQQ"}, "2026-06-29")  # 2/6 deep
    assert _history_too_shallow(long_hollow, syms) is True
    long_healthy = _multi_row_panel(syms, 150, set(syms), "2026-06-29")
    assert _history_too_shallow(long_healthy, syms) is False


def test_sparse_repair_uses_10_then_20_minute_retry_windows(tmp_path, monkeypatch):
    meta_file = tmp_path / "cache_meta.json"
    meta_file.write_text("{}", encoding="utf-8")
    now = datetime(2026, 6, 25, 20, 0, tzinfo=timezone.utc)
    monkeypatch.setattr("core.pipeline.market_data.market_data_health.settings.MARKET_DATA_REPAIR_FIRST_RETRY_MINUTES", 10)
    monkeypatch.setattr("core.pipeline.market_data.market_data_health.settings.MARKET_DATA_REPAIR_SECOND_RETRY_MINUTES", 20)

    first = record_repair_attempt(
        str(meta_file),
        _health(["BBB"]),
        _health(["BBB"]),
        now_utc=now,
    )
    second = record_repair_attempt(
        str(meta_file),
        _health(["BBB"]),
        _health(["BBB"]),
        now_utc=now + timedelta(minutes=10),
    )

    assert first["next_retry_at"] == (now + timedelta(minutes=10)).isoformat()
    assert first["error_class"] == "sparse_symbols"
    assert second["next_retry_at"] == (now + timedelta(minutes=30)).isoformat()
    assert second["attempt_count"] == 2


def test_rate_limit_repair_uses_retry_after_and_escalates_on_repeat(tmp_path):
    meta_file = tmp_path / "cache_meta.json"
    meta_file.write_text("{}", encoding="utf-8")
    now = datetime(2026, 6, 25, 20, 0, tzinfo=timezone.utc)

    first = record_repair_attempt(
        str(meta_file),
        _health(["BBB"]),
        None,
        error_text="YFRateLimitError: 429 Too Many Requests; Retry-After: 120",
        now_utc=now,
    )
    second = record_repair_attempt(
        str(meta_file),
        _health(["BBB"]),
        None,
        error_text="YFRateLimitError: 429 Too Many Requests",
        now_utc=now + timedelta(seconds=120),
    )

    assert first["error_class"] == "provider_rate_limited"
    assert first["next_retry_at"] == (now + timedelta(seconds=120)).isoformat()
    assert first["help_needed"] is False
    assert second["error_class"] == "provider_rate_limited"
    assert second["next_retry_at"] == (now + timedelta(minutes=22)).isoformat()
    assert second["help_needed"] is True
