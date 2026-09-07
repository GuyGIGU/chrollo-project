"""WP-C download-pipeline integrity regressions.

#1 Forming-bar persistence: a period-based fetch during market hours carries the
   current day's PARTIAL bar. Nothing may persist rows newer than the latest
   completed session, or an afternoon 'Refresh Data' click freezes 2pm snapshot
   bars that the evening scan then evaluates and permanently archives.
#2 Split probe: EVERY cached ticker must be checked on the incremental overlap
   (not a 30-ticker sample) — under the as-traded regime a split is the only
   series-shifting corporate action, and an unsampled split carries a fake
   price gap until the next weekly cold refetch.
"""
import json
import os
import sys
import time
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from config import settings
from core.pipeline import cache as cache_module
from core.pipeline import downloads as dl


def _panel(close_by_ticker: dict[str, list], dates) -> pd.DataFrame:
    idx = pd.to_datetime(list(dates))
    return pd.concat(
        {
            ticker: pd.DataFrame(
                {"Close": closes, "Volume": [1000] * len(idx)}, index=idx
            )
            for ticker, closes in close_by_ticker.items()
        },
        axis=1,
    )


def _scope(tmp_path, tickers, index_symbols) -> dl._FetchScope:
    non_index = [t for t in tickers if t not in index_symbols]
    return dl._FetchScope(
        tickers_with_indexes=list(tickers),
        index_symbols=list(index_symbols),
        quarantine_path=str(tmp_path / "ticker_quarantine.json"),
        quarantine={},
        skipped_quarantined=[],
        admission_path=str(tmp_path / "ticker_admission.json"),
        admission={},
        skipped_admission=[],
        admission_skip_counts={},
        requested_non_index=non_index,
    )


# ---- #1 forming-bar cap ----
def test_cold_fetch_never_persists_bars_after_expected_session(tmp_path, monkeypatch):
    # 2pm scenario: the 5y period fetch returns yesterday, the expected session,
    # AND today's forming bar. Neither the persisted parquet nor the returned
    # panel may carry the forming row.
    expected = pd.Timestamp("2026-06-18")
    forming = pd.Timestamp("2026-06-19")
    panel = _panel(
        {"AAA": [10.0, 11.0, 11.4], "SPY": [100.0, 101.0, 101.7]},
        ["2026-06-17", expected, forming],
    )
    monkeypatch.setattr(dl, "_full_refetch", lambda symbols: panel.copy())
    monkeypatch.setattr(dl.settings, "QUARANTINE_ENABLED", False, raising=False)
    monkeypatch.setattr(dl.settings, "TICKER_ADMISSION_ENABLED", False, raising=False)

    cache_file = tmp_path / "cache.parquet"
    meta_file = tmp_path / "cache_meta.json"
    out = dl._cold_fetch(
        str(cache_file), str(meta_file), {}, None,
        _scope(tmp_path, ["AAA", "SPY"], ["SPY"]),
        expected, 0.9, time.time(),
    )

    assert out.index.max() == expected                      # returned panel capped
    persisted = pd.read_parquet(cache_file, engine=settings.PARQUET_ENGINE)
    assert persisted.index.max() == expected                # persisted panel capped
    assert forming not in persisted.index
    meta = json.loads(meta_file.read_text(encoding="utf-8"))
    assert meta["price_series"] == dl._price_regime()       # success path was taken


def test_incremental_recovery_never_merges_forming_bars(tmp_path, monkeypatch):
    # The windowed incremental fetch is capped by its end date, but the
    # per-ticker recovery for new listings is PERIOD-based and can drag today's
    # partial bar into the merged panel.
    d0, expected, forming = (pd.Timestamp("2026-06-17"), pd.Timestamp("2026-06-18"),
                             pd.Timestamp("2026-06-19"))
    cached = _panel({t: [10.0] for t in ["AAA", "SPY", "QQQ"]}, [d0])
    fresh = _panel({t: [11.0] for t in ["AAA", "NEW", "SPY", "QQQ"]}, [expected])

    monkeypatch.setattr(dl, "latest_completed_session", lambda: expected)
    monkeypatch.setattr(dl.settings, "INCREMENTAL_OVERLAP_BDAYS", 1)
    monkeypatch.setattr(dl, "_batched_download", lambda *a, **k: fresh)
    monkeypatch.setattr(dl, "_repair_latest_session", lambda data, *a, **k: data)

    def fake_recover(data, tickers, **kwargs):
        out = data.reindex(data.index.union([forming])).sort_index()
        out.loc[forming, ("NEW", "Close")] = 99.0  # the leaked partial bar
        return out

    monkeypatch.setattr(dl, "_recover_missing_data", fake_recover)

    out = dl._incremental_fetch(
        cached, ["AAA", "NEW", "SPY", "QQQ"], 1, ["SPY", "QQQ"]
    )

    assert out is not None
    assert out.index.max() == expected
    assert forming not in out.index


# ---- #2 exhaustive split probe ----
def test_split_probe_is_exhaustive_over_all_cached_tickers(tmp_path, monkeypatch):
    # 121 tickers, ONE split (2:1 → constant 0.5 ratio). A 30-ticker sample
    # would miss it ~75% of the time; the exhaustive probe must always find it.
    dates = pd.bdate_range("2026-06-08", periods=5)
    clean = {f"T{i:03d}": [10.0, 10.2, 10.1, 10.3, 10.4] for i in range(120)}
    cached = _panel({**clean, "ZSPL": [40.0, 40.4, 40.2, 40.6, 40.8]}, dates)
    fresh = _panel({**clean, "ZSPL": [20.0, 20.2, 20.1, 20.3, 20.4]}, dates)
    monkeypatch.setattr(dl.settings, "SPLIT_PROBE_UNIVERSE_DRIFT_PCT", 0.5)

    force, drifted = dl._detect_splits(
        cached, fresh, list(cached.columns.get_level_values(0).unique())
    )

    assert drifted == ["ZSPL"]
    assert force is False


def test_split_probe_skips_noise_and_thin_overlaps():
    # NOIS drifts on individual bars but not as a constant ratio (no split
    # fingerprint); THIN shares only one usable bar (too little to judge);
    # GONE is absent from the fresh window entirely.
    dates = pd.bdate_range("2026-06-08", periods=5)
    cached = _panel({
        "OKAY": [10.0, 10.0, 10.0, 10.0, 10.0],
        "NOIS": [10.0, 10.0, 10.0, 10.0, 10.0],
        "THIN": [10.0, 10.0, 10.0, 10.0, 10.0],
        "GONE": [10.0, 10.0, 10.0, 10.0, 10.0],
    }, dates)
    fresh = _panel({
        "OKAY": [10.0, 10.0, 10.0, 10.0, 10.0],
        "NOIS": [12.0, 14.0, 13.0, 11.0, 12.5],   # drifted mean but high std
        "THIN": [None, None, None, None, 5.0],    # one shared bar only
    }, dates)

    force, drifted = dl._detect_splits(cached, fresh, ["OKAY", "NOIS", "THIN", "GONE"])

    assert drifted == []
    assert force is False


def test_split_probe_forces_cold_path_on_broad_drift():
    dates = pd.bdate_range("2026-06-08", periods=5)
    closes = [10.0, 10.2, 10.1, 10.3, 10.4]
    tickers = [f"T{i}" for i in range(10)]
    cached = _panel({t: closes for t in tickers}, dates)
    fresh_map = {t: closes for t in tickers[3:]}
    fresh_map.update({t: [c / 2 for c in closes] for t in tickers[:3]})  # 3 splits
    fresh = _panel(fresh_map, dates)

    force, drifted = dl._detect_splits(cached, fresh, tickers)

    assert sorted(drifted) == ["T0", "T1", "T2"]
    assert force is True  # 30% > SPLIT_PROBE_UNIVERSE_DRIFT_PCT


# ---- #4 Windows os.replace vs unlocked readers ----
def test_atomic_write_retries_transient_permission_error(tmp_path, monkeypatch):
    # A concurrent status read holding the target open makes os.replace raise
    # PermissionError on Windows; the write must wait the reader out, not die.
    calls = {"n": 0}
    real_replace = os.replace

    def flaky_replace(src, dst):
        calls["n"] += 1
        if calls["n"] < 3:
            raise PermissionError("target held open by a concurrent reader")
        return real_replace(src, dst)

    monkeypatch.setattr(cache_module.os, "replace", flaky_replace)
    monkeypatch.setattr(cache_module.time, "sleep", lambda s: None)

    meta_file = tmp_path / "cache_meta.json"
    cache_module._write_meta(str(meta_file), {"price_series": "as_traded"})

    assert calls["n"] == 3
    assert json.loads(meta_file.read_text(encoding="utf-8"))["price_series"] == "as_traded"


# ---- #5 index-less universe (commodities_etf declares no regime symbols) ----
def test_cold_fetch_persists_index_less_universe_at_full_coverage(tmp_path, monkeypatch):
    # commodities_etf carries index_symbols=(). "Every named index closed" is vacuously
    # true when nothing is named, but has_all_closes_on keys on total > 0, so the empty
    # list read as MISSING index closes and the cold write was refused on 24 consecutive
    # nights from 2026-08-26 — each one reaching 29/29 (100.0%) coverage. Nothing
    # persisted also means price_series is never stamped, so the regime guard then
    # refused evaluation and archiving on the meta the failure left behind.
    expected = pd.Timestamp("2026-06-18")
    panel = _panel(
        {"GLD": [180.0, 181.0], "SLV": [30.0, 30.4], "USO": [70.0, 70.9]},
        ["2026-06-17", expected],
    )
    monkeypatch.setattr(dl, "_full_refetch", lambda symbols: panel.copy())
    monkeypatch.setattr(dl.settings, "QUARANTINE_ENABLED", False, raising=False)
    monkeypatch.setattr(dl.settings, "TICKER_ADMISSION_ENABLED", False, raising=False)

    cache_file = tmp_path / "cache.parquet"
    meta_file = tmp_path / "cache_meta.json"
    out = dl._cold_fetch(
        str(cache_file), str(meta_file), {}, None,
        _scope(tmp_path, ["GLD", "SLV", "USO"], []),   # <- no regime symbols
        expected, 0.95, time.time(),
    )

    assert not out.empty
    assert cache_file.exists()                              # panel actually persisted
    meta = json.loads(meta_file.read_text(encoding="utf-8"))
    assert meta["price_series"] == dl._price_regime()       # regime stamped -> eval allowed
    assert "last_cold_failure" not in meta                  # success path, not the refusal


def test_cold_fetch_still_refuses_when_a_declared_index_close_is_missing(tmp_path, monkeypatch):
    # The other half of the fix: a universe that DOES declare a regime symbol must still
    # fail when that symbol has no close on the expected session. min_latest_coverage is
    # deliberately slack (0.5) so the whole-universe ratio (4/5 = 80%) passes on its own
    # and the index-close branch is the only thing that can refuse this run.
    expected = pd.Timestamp("2026-06-18")
    panel = _panel(
        {
            "AAA": [10.0, 11.0],
            "BBB": [20.0, 21.0],
            "CCC": [30.0, 31.0],
            "DDD": [40.0, 41.0],
            "SPY": [100.0, float("nan")],   # index missing the expected session's close
        },
        ["2026-06-17", expected],
    )
    monkeypatch.setattr(dl, "_full_refetch", lambda symbols: panel.copy())
    monkeypatch.setattr(dl.settings, "QUARANTINE_ENABLED", False, raising=False)
    monkeypatch.setattr(dl.settings, "TICKER_ADMISSION_ENABLED", False, raising=False)

    cache_file = tmp_path / "cache.parquet"
    meta_file = tmp_path / "cache_meta.json"
    dl._cold_fetch(
        str(cache_file), str(meta_file), {}, None,
        _scope(tmp_path, ["AAA", "BBB", "CCC", "DDD", "SPY"], ["SPY"]),
        expected, 0.5, time.time(),
    )

    assert not cache_file.exists()                          # panel NOT persisted
    meta = json.loads(meta_file.read_text(encoding="utf-8"))
    assert "price_series" not in meta                       # regime never stamped
    assert meta["last_cold_failure"]["kind"] == "coverage"  # refusal recorded
