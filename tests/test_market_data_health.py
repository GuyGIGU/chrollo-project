import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from core.pipeline.market_data_health import (
    compute_market_data_health,
    record_repair_attempt,
)


def _write_tagged_meta(meta_file):
    """Current-regime meta. An untagged meta ({}) is a LEGACY div-adjusted cache
    and now (correctly) classifies regime_mismatch, so the classifier tests pin
    the tag to exercise the state they actually target."""
    from core.pipeline.downloads import _price_regime

    meta_file.write_text(
        json.dumps({"price_series": _price_regime()}), encoding="utf-8"
    )


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
    monkeypatch.setattr("core.pipeline.market_data_health.settings.MARKET_DATA_MIN_LATEST_COVERAGE", 0.95)

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
    monkeypatch.setattr("core.pipeline.market_data_health.settings.MARKET_DATA_MIN_LATEST_COVERAGE", 0.95)

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
    monkeypatch.setattr("core.pipeline.market_data_health.settings.MARKET_DATA_MIN_LATEST_COVERAGE", 0.95)
    monkeypatch.setattr("core.pipeline.market_data_health.settings.MARKET_DATA_MIN_HISTORY_BARS", 100)
    monkeypatch.setattr("core.pipeline.market_data_health.settings.MARKET_DATA_MIN_HISTORY_COVERAGE", 0.5)

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
    monkeypatch.setattr("core.pipeline.market_data_health.settings.MARKET_DATA_MIN_LATEST_COVERAGE", 0.95)
    monkeypatch.setattr("core.pipeline.market_data_health.settings.MARKET_DATA_MIN_HISTORY_BARS", 100)

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
    from core.pipeline.downloads import _history_too_shallow

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
    monkeypatch.setattr("core.pipeline.market_data_health.settings.MARKET_DATA_REPAIR_FIRST_RETRY_MINUTES", 10)
    monkeypatch.setattr("core.pipeline.market_data_health.settings.MARKET_DATA_REPAIR_SECOND_RETRY_MINUTES", 20)

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
