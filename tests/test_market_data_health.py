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
    meta_file.write_text("{}", encoding="utf-8")
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
