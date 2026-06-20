import math
import json
from datetime import datetime, timezone
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from fastapi import HTTPException

from config import settings

ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = ROOT / "webapp" / "backend"
sys.path.insert(0, str(ROOT))
sys.path.insert(1, str(BACKEND_DIR))

from core.archive.forward_returns import (
    FORWARD_RETURN_HORIZON_BARS,
    _compute_returns,
    compute_barrier_events,
)
from core.archive.seed_recall import diff_against_baseline as seed_diff_against_baseline
from core.pipeline.cache import _atomic_write_parquet, _write_meta
from core.pipeline.json_safety import to_json_safe
from core.pipeline.market_context import get_market_context
import core.pipeline.downloads as downloads_module
import core.pipeline.market_context as market_context_module
import output.dashboard as dashboard_module
from core.structure.bin_features import measure_bins
from core.structure.indicators import trend_template
from core.structure.metrics import (
    _vol_trend_from_contractions,
    measure_bar_compression,
    measure_contractions,
    measure_equilibrium,
    measure_traversal,
)
from core.structure.box_primitives import (
    _detect_inner_phase_b_start,
    _validate_base_quality,
    detect_inner_root_swing,
    select_phase_b_candidate,
)
from core.structure.lps import detect_lps, detect_lps_tests
from core.structure.segmentation import segment_swings
from core.archive.analyze import derive_outcomes, safe_rank_corr, signal_edge
from core.structure.scope import _resolve_phase_d_start, scope_consolidation
from tools.fidelity_harness import summarize_fidelity
from tools.shadow_diff import canonical_fields
from tools.shadow_diff import diff_against_baseline as shadow_diff_against_baseline
from webapp.backend.routers.market_data import _clean_symbol, _is_number
from webapp.backend.services.portfolio_snapshot import (
    flatten_summary,
    has_portfolio_data,
    with_cached_snapshot,
)


def _contraction_frame(levels, volumes):
    """Build an OHLCV frame from a list of close levels (±0.5 High/Low band)."""
    return pd.DataFrame({
        "High": [c + 0.5 for c in levels],
        "Low": [c - 0.5 for c in levels],
        "Close": list(levels),
        "Volume": list(volumes),
    })


def test_cache_writer_optimizes_market_panel_roundtrip(tmp_path):
    idx = pd.date_range("2026-01-01", periods=3, freq="B")
    fields = ["Open", "High", "Low", "Close", "Adj Close", "Volume"]
    cols = pd.MultiIndex.from_product([["AAA", "BBB"], fields])
    data = pd.DataFrame(index=idx, columns=cols, dtype="float64")

    for ticker in ["AAA", "BBB"]:
        data[(ticker, "Open")] = [10.123456, 10.5, 10.7]
        data[(ticker, "High")] = [10.5, 10.8, 11.0]
        data[(ticker, "Low")] = [9.9, 10.2, 10.4]
        data[(ticker, "Close")] = [10.2, 10.6, 10.9]
        data[(ticker, "Adj Close")] = [10.2, 10.6, 10.9]
        data[(ticker, "Volume")] = [1000, None, 1200]

    path = tmp_path / "market_cache.parquet"
    _atomic_write_parquet(data, str(path))
    out = pd.read_parquet(path)

    assert out[("AAA", "Close")].dtype == "float32"
    assert out[("AAA", "Volume")].dtype == "Int64"
    assert abs(float(out[("AAA", "Close")].iloc[0]) - 10.2) < 1e-5
    assert pd.isna(out[("AAA", "Volume")].iloc[1])


def test_json_safe_handles_scan_payload_scalars():
    payload = {
        "chart_data": {
            "RSVR": {
                "lps_tests": [{
                    "window_range_pct_box": np.float32(0.42),
                    "length": np.int64(3),
                    "valid": np.bool_(True),
                    "missing": pd.NA,
                    "when": pd.Timestamp("2026-06-14"),
                }],
                "bad": np.float64(float("nan")),
                "array": np.array([np.float32(1.2), np.inf]),
            },
        },
        ("tuple", "key"): "ok",
    }

    safe = to_json_safe(payload)

    json.dumps(safe, allow_nan=False)
    test = safe["chart_data"]["RSVR"]["lps_tests"][0]
    assert test["window_range_pct_box"] == pytest.approx(0.42)
    assert test["length"] == 3
    assert test["valid"] is True
    assert test["missing"] is None
    assert test["when"] == "2026-06-14T00:00:00"
    assert safe["chart_data"]["RSVR"]["bad"] is None
    assert safe["chart_data"]["RSVR"]["array"][1] is None
    assert safe["['tuple', 'key']"] == "ok"


def test_dashboard_exports_phase_c_and_d_bar_indices(monkeypatch):
    dates = pd.date_range("2026-01-01", periods=10, freq="B", name="Date")
    data = pd.DataFrame({
        "Open": np.linspace(10, 11, len(dates)),
        "High": np.linspace(10.5, 11.5, len(dates)),
        "Low": np.linspace(9.5, 10.5, len(dates)),
        "Close": np.linspace(10.2, 11.2, len(dates)),
        "Volume": np.linspace(1000, 1100, len(dates)),
    }, index=dates)
    results = pd.DataFrame([{
        "Ticker": "AAA",
        "Tier": "A",
        "Score": 100,
        "Setup": "LPS",
        "Current Price": 11.2,
        "_trigger_price": 11.6,
        "_R": 11.5,
        "_S": 9.5,
        "_base_len": 8,
        "_lps_len": 2,
        "_lps_offset": 0,
        "_r_anchor_bar": 2,
        "_s_anchor_bar": 3,
        "_bin_c_event_bar": 7,
        "_bin_c_recovery_bar": 8,
        "_bin_d_start_bar": 6,
    }])
    monkeypatch.setattr(dashboard_module, "_sector_etf_for_ticker", lambda *_args: None)

    chart = dashboard_module._extract_chart_data(data, results, ["AAA"])["AAA"]

    assert chart["bin_c_event_bar"] == 7
    assert chart["bin_c_recovery_bar"] == 8
    assert chart["bin_d_start_bar"] == 6


def test_meta_writer_sanitizes_scan_context(tmp_path):
    path = tmp_path / "market_context.json"

    _write_meta(str(path), {
        "spy_6m_return": np.float32(0.123),
        "breadth_pct": np.float64(float("nan")),
        "computed_at": pd.Timestamp("2026-06-14T12:00:00"),
    })

    written = json.loads(path.read_text(encoding="utf-8"))
    assert written["spy_6m_return"] == pytest.approx(0.123)
    assert written["breadth_pct"] is None
    assert written["computed_at"] == "2026-06-14T12:00:00"


def test_market_context_computes_regime_state(tmp_path, monkeypatch):
    monkeypatch.setattr(
        market_context_module,
        "_market_context_path",
        lambda: str(tmp_path / "market_context.json"),
    )
    monkeypatch.setattr(market_context_module, "_is_market_hours", lambda: False)

    idx = pd.date_range("2025-01-01", periods=220, freq="B")

    def frame(start, step):
        close = pd.Series([start + step * i for i in range(len(idx))], index=idx)
        return pd.DataFrame({
            "Open": close - 0.1,
            "High": close + 0.2,
            "Low": close - 0.2,
            "Close": close,
            "Volume": [1_000_000 + i for i in range(len(idx))],
        }, index=idx)

    panel = pd.concat(
        {"SPY": frame(100, 0.2), "QQQ": frame(120, 0.3)},
        axis=1,
    )
    ticker_frames = {
        "AAA": frame(20, 0.05),
        "BBB": frame(30, 0.04),
        "CCC": frame(40, 0.03),
    }

    context = get_market_context(panel, ticker_frames)
    regime = context["regime"]

    assert context["spy_6m_return"] > 0
    assert context["breadth_pct"] == 1.0
    assert regime["state"] == "UPTREND"
    assert regime["breadth_50_pct"] == 1.0
    assert regime["breadth_200_pct"] == 1.0
    assert regime["indexes"]["SPY"]["above_sma_50"] is True
    assert regime["indexes"]["QQQ"]["sma_50_rising"] is True


def test_market_context_short_history_stays_neutral(tmp_path, monkeypatch):
    monkeypatch.setattr(
        market_context_module,
        "_market_context_path",
        lambda: str(tmp_path / "market_context.json"),
    )
    monkeypatch.setattr(market_context_module, "_is_market_hours", lambda: False)

    idx = pd.date_range("2026-01-01", periods=100, freq="B")
    close = pd.Series([100 + i for i in range(len(idx))], index=idx)
    frame = pd.DataFrame({
        "Open": close - 0.1,
        "High": close + 0.2,
        "Low": close - 0.2,
        "Close": close,
    }, index=idx)
    panel = pd.concat({"SPY": frame, "QQQ": frame}, axis=1)

    context = get_market_context(panel, {"AAA": frame})

    assert context["regime"]["state"] == "NEUTRAL"
    assert context["regime"]["indexes"]["SPY"]["above_sma_200"] is None


def test_market_context_cache_missing_configured_index_recomputes(tmp_path, monkeypatch):
    context_path = tmp_path / "market_context.json"
    monkeypatch.setattr(market_context_module, "_market_context_path", lambda: str(context_path))
    monkeypatch.setattr(market_context_module, "_is_market_hours", lambda: False)

    idx = pd.date_range("2025-01-01", periods=220, freq="B")
    close = pd.Series([100 + i for i in range(len(idx))], index=idx)
    frame = pd.DataFrame({
        "Open": close - 0.1,
        "High": close + 0.2,
        "Low": close - 0.2,
        "Close": close,
        "Volume": [1_000_000 + i for i in range(len(idx))],
    }, index=idx)
    panel = pd.concat({"SPY": frame, "QQQ": frame}, axis=1)
    context_path.write_text(
        json.dumps({
            "spy_6m_return": 0.1,
            "breadth_pct": 1.0,
            "computed_at": datetime.now(timezone.utc).isoformat(),
            "spy_last_bar_date": idx[-1].strftime("%Y-%m-%d"),
            "index_last_bar_dates": {
                "SPY": idx[-1].strftime("%Y-%m-%d"),
                "QQQ": idx[-1].strftime("%Y-%m-%d"),
            },
            "regime": {
                "state": "UPTREND",
                "indexes": {"SPY": {"close": 100.0}},
            },
        }),
        encoding="utf-8",
    )

    context = get_market_context(panel, {"AAA": frame})

    assert set(context["regime"]["indexes"]) == {"SPY", "QQQ"}


def test_fetch_data_refetches_current_cache_missing_regime_index(tmp_path, monkeypatch):
    cache_file = tmp_path / "market_cache.parquet"
    meta_file = tmp_path / "cache_meta.json"

    today = pd.Timestamp.now().normalize()
    last_bar = today if today.weekday() < 5 else today - pd.tseries.offsets.BDay(1)
    cached_panel = pd.concat(
        {
            "AAA": pd.DataFrame({"Close": [10.0], "Volume": [1000]}, index=[last_bar]),
            "SPY": pd.DataFrame({"Close": [100.0], "Volume": [1000]}, index=[last_bar]),
        },
        axis=1,
    )
    full_panel = pd.concat(
        {
            "AAA": pd.DataFrame({"Close": [10.0], "Volume": [1000]}, index=[last_bar]),
            "SPY": pd.DataFrame({"Close": [100.0], "Volume": [1000]}, index=[last_bar]),
            "QQQ": pd.DataFrame({"Close": [120.0], "Volume": [1000]}, index=[last_bar]),
        },
        axis=1,
    )
    _atomic_write_parquet(cached_panel, str(cache_file))
    meta_file.write_text(
        f'{{"last_full_refresh": "{datetime.now(timezone.utc).isoformat()}"}}',
        encoding="utf-8",
    )

    called = {}
    monkeypatch.setattr(downloads_module, "_cache_paths", lambda: (str(cache_file), str(meta_file)))
    monkeypatch.setattr(downloads_module, "_is_market_hours", lambda: False)
    monkeypatch.setattr(downloads_module.settings, "TTL_FRESH_HOURS_OFFHOURS", 0)
    def fake_full_refetch(symbols):
        called["symbols"] = symbols
        return full_panel

    monkeypatch.setattr(downloads_module, "_full_refetch", fake_full_refetch)

    out = downloads_module.fetch_data(["AAA"])

    assert called["symbols"] == ["AAA", "SPY", "QQQ"]
    assert set(out.columns.get_level_values(0)) == {"AAA", "SPY", "QQQ"}


def test_dashboard_sector_cache_resolves_missing_ticker(tmp_path, monkeypatch):
    cache_path = tmp_path / "sector_etf_cache.json"
    monkeypatch.setattr(dashboard_module, "SECTOR_ETF_CACHE_PATH", str(cache_path))
    monkeypatch.setattr(dashboard_module, "_resolve_sector_etf", lambda ticker: "XLI")

    cache = dashboard_module._load_sector_etf_cache()
    sector = dashboard_module._sector_etf_for_ticker("wcc", cache)
    persisted = json.loads(cache_path.read_text(encoding="utf-8"))

    assert sector == "XLI"
    assert persisted == {"WCC": "XLI"}


# A clean 3-contraction sawtooth: peaks at idx 4/12/18, valleys at idx 8/15/21.
_VCP_LEVELS = [
    10, 12, 14, 16, 30, 22, 18, 14, 6, 12, 16, 20,
    26, 18, 14, 9, 13, 17, 22, 16, 13, 11, 12, 13,
]


def test_vol_trend_from_contractions_scores_drying_up():
    # Lighter each contraction, quietest at the final coil -> full credit.
    assert _vol_trend_from_contractions([1000, 800, 500]) == 1.0
    # Heaviest at the final contraction -> zero.
    assert _vol_trend_from_contractions([500, 800, 1000]) == 0.0
    # A trend needs two points; non-finite values are dropped before scoring.
    assert _vol_trend_from_contractions([1000]) is None
    assert _vol_trend_from_contractions([]) is None
    assert _vol_trend_from_contractions([float("nan"), 900, 700, 500]) == 1.0
    # Flat volume -> every step non-rising (1.0), final-lightest neutral (0.5).
    assert _vol_trend_from_contractions([800, 800, 800]) == 0.75


def test_measure_contractions_volume_does_not_touch_quality():
    n = len(_VCP_LEVELS)
    drying = _contraction_frame(_VCP_LEVELS, [2000 - 60 * i for i in range(n)])
    rising = _contraction_frame(_VCP_LEVELS, [620 + 60 * i for i in range(n)])

    rd = measure_contractions(drying, order=2)
    rr = measure_contractions(rising, order=2)

    # Identical price -> identical contractions and IDENTICAL quality: volume is
    # measured but never folded into the score (the measure-first invariant).
    assert rd["n_contractions"] >= 2
    assert rd["quality"] == rr["quality"]
    # ...but the volume read separates them: drying up ranks far above rising in.
    assert rd["vol_trend"] is not None and rr["vol_trend"] is not None
    assert rd["vol_trend"] > rr["vol_trend"]


def test_measure_contractions_vol_trend_none_without_contractions():
    flat = _contraction_frame([10, 10, 10, 10, 10], [500, 500, 500, 500, 500])
    assert measure_contractions(flat, order=2)["vol_trend"] is None


def test_detect_inner_phase_b_start_finds_recent_climax():
    # 12 bars rising to a clear peak (118), a ~17% drop over 5 bars to the inner
    # AR (~98), then 21 tight bars — a textbook inner climax → reaction → inner range.
    levels = (
        [90, 93, 96, 99, 102, 105, 108, 111, 114, 116, 117, 118]
        + [112, 108, 104, 100, 98]
        + [100, 99, 101, 100, 102, 99, 100, 101, 99, 100, 102,
           100, 99, 101, 100, 99, 100, 101, 99, 100, 101]
    )
    frame = _contraction_frame(levels, [1000] * len(levels))
    off = _detect_inner_phase_b_start(frame)
    assert off is not None
    # Lands after the peak, leaves >= INNER_MIN_DAYS room, and is a real reaction.
    assert 11 < off <= len(frame) - 15
    assert frame['Low'].iloc[off] <= 0.95 * frame['High'].iloc[:off].max()


def test_detect_inner_root_swing_reports_reaction_measurements():
    levels = (
        [90, 93, 96, 99, 102, 105, 108, 111, 114, 116, 117, 118]
        + [112, 108, 104, 100, 98]
        + [100, 99, 101, 100, 102, 99, 100, 101, 99, 100, 102,
           100, 99, 101, 100, 99, 100, 101, 99, 100, 101]
    )
    frame = _contraction_frame(levels, [1000] * len(levels))

    root = detect_inner_root_swing(frame)

    assert root is not None
    assert root["bc_bar"] < root["ar_bar"]
    assert root["ar_bar"] == _detect_inner_phase_b_start(frame)
    assert root["reaction_bars"] == root["ar_bar"] - root["bc_bar"]
    assert root["reaction_pct"] >= settings.AR_MIN_DROP_PCT


def test_detect_inner_phase_b_start_none_when_no_reaction():
    # 40 near-flat bars (~3% wiggle) — no >= 5% reaction, so no inner climax.
    levels = [100 + (1.5 if i % 2 else -1.5) for i in range(40)]
    assert _detect_inner_phase_b_start(_contraction_frame(levels, [1000] * 40)) is None


def test_detect_inner_phase_b_start_none_when_too_short():
    levels = [100, 102, 98, 101, 99, 100, 103, 97, 100, 101]
    assert _detect_inner_phase_b_start(_contraction_frame(levels, [1000] * 10)) is None


def test_lps_trigger_uses_last_lps_bar_high():
    df = pd.DataFrame([
        {"High": 118, "Low": 115, "Close": 116, "Spread": 1, "Volume": 900, "Vol_50": 1000},
        {"High": 117, "Low": 115, "Close": 116, "Spread": 1, "Volume": 900, "Vol_50": 1000},
        {"High": 116, "Low": 115, "Close": 116, "Spread": 1, "Volume": 900, "Vol_50": 1000},
        {"High": 116, "Low": 115, "Close": 116, "Spread": 1, "Volume": 900, "Vol_50": 1000},
        {"High": 110, "Low": 106, "Close": 107, "Spread": 2, "Volume": 500, "Vol_50": 1000},
        {"High": 107, "Low": 103, "Close": 106, "Spread": 1, "Volume": 500, "Vol_50": 1000},
    ])

    result = detect_lps(
        df=df,
        latest=df.iloc[-1],
        sup_avg=100,
        res_avg=110,
        atr_val=2,
        base_range_threshold=8,
        base_len=20,
        swing_complete_idx=2,
    )

    assert result["trigger_price"] == 107


def _lps_behavior_frame(highs, lows, closes=None):
    closes = closes or lows
    return pd.DataFrame([
        {
            "High": high,
            "Low": low,
            "Close": close,
            "Spread": high - low,
            "Volume": 500,
            "Vol_50": 1000,
        }
        for high, low, close in zip(highs, lows, closes)
    ])


def test_lps_accepts_compact_reaction_behavior(monkeypatch):
    monkeypatch.setattr(settings, "LPS_LENGTH_MIN", 4)
    monkeypatch.setattr(settings, "LPS_LENGTH_MAX", 4)
    df = _lps_behavior_frame(
        highs=[108, 107, 106, 105],
        lows=[106, 104, 102, 101],
        closes=[107, 105, 103, 104],
    )

    result = detect_lps(
        df=df,
        latest=df.iloc[-1],
        sup_avg=100,
        res_avg=110,
        atr_val=2,
        base_range_threshold=8,
        base_len=20,
        swing_complete_idx=-1,
    )

    assert result is not None
    assert result["window_range_pct_box"] == 0.7
    assert result["high_descent_frac"] == 1.0


def test_lps_accepts_shallow_pullback_on_tight_clean_coil(monkeypatch):
    # A tight, clean-descent coil (lows AND highs strictly descending) whose
    # first-high -> last-low pullback is only 0.5 profile units. The old 0.65
    # floor rejected these tight VCP pivots purely on pullback magnitude (the
    # BP / NVMI seed misses, both descent_frac 1.0); the shipped 0.40 floor
    # accepts them while the descent / vol / spread / zone gates still apply.
    monkeypatch.setattr(settings, "LPS_LENGTH_MIN", 4)
    monkeypatch.setattr(settings, "LPS_LENGTH_MAX", 4)
    df = _lps_behavior_frame(
        highs=[108, 107, 106, 105],
        lows=[107, 106, 105, 104],
        closes=[107, 106, 105, 104],
    )
    kw = dict(
        latest=df.iloc[-1], sup_avg=100, res_avg=110, atr_val=2,
        base_range_threshold=8, base_len=20, swing_complete_idx=-1,
    )

    # Accepted at the shipped 0.40 floor, with a genuinely shallow (<0.65) pullback.
    monkeypatch.setattr(settings, "LPS_PULLBACK_PROFILE_MIN", 0.40)
    accepted = detect_lps(df=df, **kw)
    assert accepted is not None
    assert 0.40 <= accepted["pullback_profile"] < 0.65
    assert accepted["descent_frac"] == 1.0  # the coil is a clean descent, not chop
    assert accepted["swing_type"] == "clean_downswing"

    # The retired 0.65 floor rejected exactly this coil on pullback magnitude alone.
    monkeypatch.setattr(settings, "LPS_PULLBACK_PROFILE_MIN", 0.65)
    rejected, rejects = detect_lps(df=df, diagnose=True, **kw)
    assert rejected is None
    assert any(str(k).startswith("pullback_profile") for k in rejects)


def test_lps_rejects_window_that_spans_most_of_box(monkeypatch):
    monkeypatch.setattr(settings, "LPS_LENGTH_MIN", 5)
    monkeypatch.setattr(settings, "LPS_LENGTH_MAX", 5)
    df = _lps_behavior_frame(
        highs=[110, 114, 113, 112, 106],
        lows=[105, 104, 103, 102, 101],
        closes=[106, 105, 104, 103, 102],
    )

    result, rejects = detect_lps(
        df=df,
        latest=df.iloc[-1],
        sup_avg=100,
        res_avg=110,
        atr_val=2,
        base_range_threshold=10,
        base_len=20,
        swing_complete_idx=-1,
        diagnose=True,
    )

    assert result is None
    assert rejects["window_box_range"] == 1


def test_lps_accepts_clean_downswing_even_when_window_spans_box(monkeypatch):
    monkeypatch.setattr(settings, "LPS_LENGTH_MIN", 3)
    monkeypatch.setattr(settings, "LPS_LENGTH_MAX", 3)
    df = _lps_behavior_frame(
        highs=[112, 110, 107],
        lows=[108, 105, 102],
        closes=[109, 106, 103],
    )

    result = detect_lps(
        df=df,
        latest=df.iloc[-1],
        sup_avg=100,
        res_avg=110,
        atr_val=2,
        base_range_threshold=4,
        base_len=20,
        swing_complete_idx=-1,
    )

    assert result is not None
    assert result["window_range_pct_box"] > settings.LPS_MAX_WINDOW_BOX_RANGE
    assert result["descent_frac"] == 1.0
    assert result["high_descent_frac"] == 1.0
    assert result["swing_type"] == "clean_downswing"
    assert result["lps_anchor_bar"] == 0
    assert result["lps_low_bar"] == 2
    assert result["lps_swing_depth_box"] == pytest.approx((112 - 102) / (110 - 100))


def test_lps_rising_edge_is_graded_not_hard_rejected(monkeypatch):
    # Reframed 2026-06-19: a rising upper edge is NOT a hard reject. A rising
    # coil ties into ASCENDING SUPPORT (gradual rising buyer pressure), which the
    # engine already rewards via SCORE_ASCENDING_SUPPORT — so the old high_up_march
    # reject double-counted it as a defect. The descent floors are retired to 0;
    # descent_frac / high_descent_frac stay GRADED quality inputs (clean descents
    # still outrank), but no longer gate. This frame (lows cleanly testing the
    # terminal support low, rising upper edge) now elects an LPS.
    monkeypatch.setattr(settings, "LPS_LENGTH_MIN", 5)
    monkeypatch.setattr(settings, "LPS_LENGTH_MAX", 5)
    df = _lps_behavior_frame(
        highs=[104, 105, 106, 107, 108],
        lows=[104, 103, 102, 101, 100],
        closes=[104, 103, 102, 101, 101],
    )

    result = detect_lps(
        df=df,
        latest=df.iloc[-1],
        sup_avg=100,
        res_avg=110,
        atr_val=2,
        base_range_threshold=10,
        base_len=20,
        swing_complete_idx=-1,
    )

    assert result is not None
    # The rising upper edge is recorded as a graded signal (low high_descent_frac),
    # not a rejection; the lows still register a clean descent into support.
    assert result["high_descent_frac"] == 0.0
    assert result["descent_frac"] == 1.0


def test_lps_spread_widening_discounts_quality_not_gate(monkeypatch):
    monkeypatch.setattr(settings, "LPS_LENGTH_MIN", 5)
    monkeypatch.setattr(settings, "LPS_LENGTH_MAX", 5)
    df = _lps_behavior_frame(
        highs=[110.0, 109.0, 108.0, 107.0, 106.0],
        lows=[108.8, 107.6, 106.3, 105.6, 104.2],
        closes=[109.0, 108.0, 107.0, 106.0, 105.0],
    )

    result = detect_lps(
        df=df,
        latest=df.iloc[-1],
        sup_avg=100,
        res_avg=112,
        atr_val=2,
        base_range_threshold=2.0,
        base_len=20,
        swing_complete_idx=-1,
    )

    assert result is not None
    assert result["spread_decline_quality"] < 1.0


def test_lps_scans_last_seven_active_bars(monkeypatch):
    monkeypatch.setattr(settings, "LPS_LENGTH_MIN", 2)
    monkeypatch.setattr(settings, "LPS_LENGTH_MAX", 2)
    df = _lps_behavior_frame(
        highs=[116, 115, 110, 108, 109, 110, 111, 112, 113, 114],
        lows=[114, 113, 105, 102, 103, 104, 105, 106, 107, 108],
        closes=[115, 114, 106, 103, 104, 105, 106, 107, 108, 107],
    )

    result = detect_lps(
        df=df,
        latest=df.iloc[-1],
        sup_avg=100,
        res_avg=115,
        atr_val=2,
        base_range_threshold=8,
        base_len=30,
        swing_complete_idx=-1,
    )

    assert result is not None
    assert result["offset"] == 6
    assert result["start_index"] == 2


def test_lps_rejects_stale_candidate_when_later_lower_low(monkeypatch):
    monkeypatch.setattr(settings, "LPS_LENGTH_MIN", 2)
    monkeypatch.setattr(settings, "LPS_LENGTH_MAX", 2)
    df = _lps_behavior_frame(
        highs=[110, 108, 107, 106, 107, 108],
        lows=[105, 102, 101, 100, 101, 102],
        closes=[106, 103, 102, 101, 102, 103],
    )

    result = detect_lps(
        df=df,
        latest=df.iloc[-1],
        sup_avg=99,
        res_avg=112,
        atr_val=2,
        base_range_threshold=8,
        base_len=20,
        swing_complete_idx=-1,
    )

    assert result is not None
    assert result["start_index"] == 2
    assert result["end_index"] == 4


def test_lps_prefers_full_pullback_into_latest_low(monkeypatch):
    monkeypatch.setattr(settings, "LPS_LENGTH_MIN", 2)
    monkeypatch.setattr(settings, "LPS_LENGTH_MAX", 7)
    df = _lps_behavior_frame(
        highs=[72.89, 72.83, 72.76, 72.29, 72.28, 72.98],
        lows=[71.68, 71.39, 71.04, 70.83, 70.51, 71.41],
        closes=[72.08, 71.41, 71.40, 71.68, 70.91, 72.20],
    )
    df.index = pd.to_datetime([
        "2026-06-02", "2026-06-03", "2026-06-04",
        "2026-06-05", "2026-06-08", "2026-06-09",
    ])
    df["Volume"] = [117000, 105800, 77700, 152700, 76500, 126200]
    df["Vol_50"] = [151010, 148000, 146088, 146834, 144268, 146428]

    result = detect_lps(
        df=df,
        latest=df.iloc[-1],
        sup_avg=65.05789189179512,
        res_avg=74.15060505040422,
        atr_val=2.182,
        base_range_threshold=2.62,
        base_len=73,
        swing_complete_idx=-1,
    )

    assert result is not None
    assert result["start_date"] == "2026-06-02"
    assert result["end_date"] == "2026-06-08"
    assert result["low_index"] == 4


def test_lps_profile_uses_first_high_not_window_high(monkeypatch):
    monkeypatch.setattr(settings, "LPS_LENGTH_MIN", 3)
    monkeypatch.setattr(settings, "LPS_LENGTH_MAX", 3)
    df = _lps_behavior_frame(
        highs=[106, 112, 105],
        lows=[104, 108, 101],
        closes=[105, 109, 104],
    )

    result = detect_lps(
        df=df,
        latest=df.iloc[-1],
        sup_avg=100,
        res_avg=120,
        atr_val=2,
        base_range_threshold=4,
        base_len=20,
        swing_complete_idx=-1,
    )

    assert result is not None
    assert result["first_high"] == 106
    assert result["window_high"] == 112
    assert result["pullback_profile"] == pytest.approx((106 - 101) / 4)


def test_lps_terminal_low_guard_rejects_earlier_lower_low(monkeypatch):
    monkeypatch.setattr(settings, "LPS_LENGTH_MIN", 3)
    monkeypatch.setattr(settings, "LPS_LENGTH_MAX", 3)
    df = _lps_behavior_frame(
        highs=[108, 107, 106],
        lows=[105, 100, 102],
        closes=[106, 101, 105],
    )

    result, rejects = detect_lps(
        df=df,
        latest=df.iloc[-1],
        sup_avg=99,
        res_avg=112,
        atr_val=2,
        base_range_threshold=4,
        base_len=20,
        swing_complete_idx=-1,
        diagnose=True,
    )

    assert result is None
    assert rejects["terminal_low"] == 1


def test_lps_accepts_compact_rising_support_shelf(monkeypatch):
    monkeypatch.setattr(settings, "LPS_LENGTH_MIN", 5)
    monkeypatch.setattr(settings, "LPS_LENGTH_MAX", 5)
    df = _lps_behavior_frame(
        highs=[106.0, 105.0, 105.2, 105.4, 105.6],
        lows=[104.0, 101.0, 102.0, 102.5, 103.0],
        closes=[105.0, 102.0, 103.0, 103.5, 104.5],
    )

    result = detect_lps(
        df=df,
        latest=df.iloc[-1],
        sup_avg=100,
        res_avg=112,
        atr_val=2,
        base_range_threshold=4,
        base_len=20,
        swing_complete_idx=-1,
    )

    assert result is not None
    assert result["low_index"] == 1
    assert result["low"] == 101.0
    assert result["last_low"] == 103.0
    assert result["swing_type"] == "rising_support_shelf"


def test_lps_swing_dates_follow_anchor_and_elected_valley(monkeypatch):
    monkeypatch.setattr(settings, "LPS_LENGTH_MIN", 5)
    monkeypatch.setattr(settings, "LPS_LENGTH_MAX", 5)
    df = _lps_behavior_frame(
        highs=[106.0, 105.0, 105.2, 105.4, 105.6],
        lows=[104.0, 101.0, 102.0, 102.5, 103.0],
        closes=[105.0, 102.0, 103.0, 103.5, 104.5],
    )
    df.index = pd.date_range("2026-01-05", periods=len(df), freq="B")

    result = detect_lps(
        df=df,
        latest=df.iloc[-1],
        sup_avg=100,
        res_avg=112,
        atr_val=2,
        base_range_threshold=4,
        base_len=20,
        swing_complete_idx=-1,
    )

    assert result is not None
    assert result["lps_anchor_date"] == "2026-01-05"
    assert result["lps_low_date"] == "2026-01-06"
    assert result["lps_swing_depth_pct"] == pytest.approx((106 - 101) / 106)
    assert result["lps_swing_depth_atr"] == pytest.approx((106 - 101) / 2)


def test_lps_accepts_shallow_buec_shelf_above_resistance(monkeypatch):
    monkeypatch.setattr(settings, "LPS_LENGTH_MIN", 5)
    monkeypatch.setattr(settings, "LPS_LENGTH_MAX", 5)
    df = _lps_behavior_frame(
        highs=[113.0, 112.2, 111.8, 111.6, 111.3],
        lows=[110.7, 110.4, 110.5, 110.6, 110.5],
        closes=[111.2, 110.8, 110.9, 111.0, 110.8],
    )

    result = detect_lps(
        df=df,
        latest=df.iloc[-1],
        sup_avg=100,
        res_avg=110,
        atr_val=2,
        base_range_threshold=4,
        base_len=20,
        swing_complete_idx=-1,
    )

    assert result is not None
    assert result["zone_type"] == "OVERSHOOT_R"
    assert result["swing_type"] == "buec_shelf"
    assert settings.LPS_PULLBACK_PROFILE_MIN <= result["pullback_profile"] < settings.LPS_PULLBACK_PROFILE_MIN_OVERSHOOT_R


def test_lps_swing_type_labels_undercut_rebound(monkeypatch):
    monkeypatch.setattr(settings, "LPS_LENGTH_MIN", 3)
    monkeypatch.setattr(settings, "LPS_LENGTH_MAX", 3)
    df = _lps_behavior_frame(
        highs=[108, 106, 104],
        lows=[103, 100, 98],
        closes=[104, 101, 100],
    )

    result = detect_lps(
        df=df,
        latest=df.iloc[-1],
        sup_avg=100,
        res_avg=110,
        atr_val=4,
        base_range_threshold=5,
        base_len=20,
        swing_complete_idx=-1,
    )

    assert result is not None
    assert result["setup_type"] == "REBOUND"
    assert result["zone_type"] == "UNDERCUT_S"
    assert result["swing_type"] == "undercut_rebound"


def test_lps_rejects_extended_shallow_overshoot_shelf(monkeypatch):
    monkeypatch.setattr(settings, "LPS_LENGTH_MIN", 5)
    monkeypatch.setattr(settings, "LPS_LENGTH_MAX", 5)
    df = _lps_behavior_frame(
        highs=[114.5, 114.2, 114.1, 114.0, 114.2],
        lows=[110.7, 110.4, 110.5, 110.6, 110.5],
        closes=[113.8, 113.9, 113.8, 113.9, 113.8],
    )

    result, rejects = detect_lps(
        df=df,
        latest=df.iloc[-1],
        sup_avg=100,
        res_avg=110,
        atr_val=2,
        base_range_threshold=8,
        base_len=20,
        swing_complete_idx=-1,
        diagnose=True,
    )

    assert result is None
    assert any(str(k).startswith("pullback_profile") for k in rejects)


def test_lps_wide_profile_gets_more_spread_room_than_tight_profile(monkeypatch):
    monkeypatch.setattr(settings, "LPS_LENGTH_MIN", 2)
    monkeypatch.setattr(settings, "LPS_LENGTH_MAX", 2)
    df = _lps_behavior_frame(
        highs=[108, 106],
        lows=[105, 102],
        closes=[106, 104],
    )

    tight, tight_rejects = detect_lps(
        df=df,
        latest=df.iloc[-1],
        sup_avg=100,
        res_avg=110,
        atr_val=2,
        base_range_threshold=2.4,
        base_len=20,
        swing_complete_idx=-1,
        diagnose=True,
    )
    wide = detect_lps(
        df=df,
        latest=df.iloc[-1],
        sup_avg=100,
        res_avg=110,
        atr_val=2,
        base_range_threshold=4.0,
        base_len=20,
        swing_complete_idx=-1,
    )

    assert tight is None
    assert tight_rejects["spread_profile"] == 1
    assert wide is not None
    assert wide["profile_unit"] == 4.0


def test_lps_spread_can_expand_slightly_but_not_a_lot(monkeypatch):
    monkeypatch.setattr(settings, "LPS_LENGTH_MIN", 2)
    monkeypatch.setattr(settings, "LPS_LENGTH_MAX", 2)
    small = _lps_behavior_frame(
        highs=[108, 106],
        lows=[106, 103],
        closes=[107, 104],
    )
    large = _lps_behavior_frame(
        highs=[108, 106],
        lows=[107, 102.5],
        closes=[107, 104],
    )

    ok = detect_lps(
        df=small,
        latest=small.iloc[-1],
        sup_avg=100,
        res_avg=110,
        atr_val=2,
        base_range_threshold=4.0,
        base_len=20,
        swing_complete_idx=-1,
    )
    bad, rejects = detect_lps(
        df=large,
        latest=large.iloc[-1],
        sup_avg=100,
        res_avg=110,
        atr_val=2,
        base_range_threshold=4.0,
        base_len=20,
        swing_complete_idx=-1,
        diagnose=True,
    )

    assert ok is not None
    assert ok["spread_expansion_profile"] == pytest.approx(0.25)
    assert bad is None
    assert rejects["spread_expansion"] == 1


def test_lps_selector_latest_actionable_beats_older_quality(monkeypatch):
    monkeypatch.setattr(settings, "LPS_LENGTH_MIN", 2)
    monkeypatch.setattr(settings, "LPS_LENGTH_MAX", 2)
    df = _lps_behavior_frame(
        highs=[112, 110, 108, 106],
        lows=[106, 102, 105, 102],
        closes=[107, 103, 106, 104],
    )

    result = detect_lps(
        df=df,
        latest=df.iloc[-1],
        sup_avg=100,
        res_avg=112,
        atr_val=2,
        base_range_threshold=7,
        base_len=20,
        swing_complete_idx=-1,
    )

    assert result is not None
    assert result["start_index"] == 2
    assert result["end_index"] == 4


def test_lps_selector_skips_non_actionable_latest(monkeypatch):
    monkeypatch.setattr(settings, "LPS_LENGTH_MIN", 2)
    monkeypatch.setattr(settings, "LPS_LENGTH_MAX", 2)
    df = _lps_behavior_frame(
        highs=[112, 110, 109, 107],
        lows=[105, 102, 105, 102],
        closes=[106, 103, 106, 107],
    )

    result = detect_lps(
        df=df,
        latest=df.iloc[-1],
        sup_avg=100,
        res_avg=112,
        atr_val=2,
        base_range_threshold=7,
        base_len=20,
        swing_complete_idx=-1,
    )

    assert result is not None
    assert result["start_index"] == 0
    assert result["end_index"] == 2


def test_detect_lps_tests_returns_non_overlapping_support_tests(monkeypatch):
    monkeypatch.setattr(settings, "LPS_LENGTH_MIN", 2)
    monkeypatch.setattr(settings, "LPS_LENGTH_MAX", 2)
    df = _lps_behavior_frame(
        highs=[118, 117, 108, 106, 116, 115, 107, 105],
        lows=[116, 115, 102, 100, 114, 113, 101, 100],
        closes=[117, 116, 104, 103, 115, 114, 103, 103],
    )
    df.index = pd.date_range("2026-01-01", periods=len(df), freq="D")

    tests = detect_lps_tests(
        df=df,
        latest=df.iloc[-1],
        sup_avg=100,
        res_avg=110,
        atr_val=2,
        base_range_threshold=8,
        base_len=20,
        swing_complete_idx=-1,
    )

    assert len(tests) >= 2
    assert all("start_date" in test and "end_date" in test for test in tests)
    spans = {(test["start_index"], test["end_index"]) for test in tests}
    assert len(spans) == len(tests)


def test_measure_bar_compression_reports_base_spread_texture():
    base_df = pd.DataFrame([
        {"High": 102.0, "Low": 100.0, "Spread": 2.0},
        {"High": 103.0, "Low": 102.0, "Spread": 1.0},
        {"High": 104.0, "Low": 101.0, "Spread": 3.0},
        {"High": 105.0, "Low": 103.0, "Spread": 2.0},
        {"High": 106.0, "Low": 105.0, "Spread": 1.0},
    ])

    result = measure_bar_compression(base_df, box_height=10.0, atr_val=2.0)

    assert result["median_spread_atr"] == 1.0
    assert result["p80_spread_atr"] == 1.1
    assert result["median_spread_pct_box"] == 0.2
    assert result["tight_bar_pct"] == 0.8


def _ramp_frame(pivot_prices, bars_per_leg=6):
    """Build a degenerate OHLC frame (High==Low==Close) that linearly ramps
    between the given pivot prices, so the zigzag pivots land predictably."""
    prices = [float(pivot_prices[0])]
    for k in range(1, len(pivot_prices)):
        p0, p1 = float(pivot_prices[k - 1]), float(pivot_prices[k])
        for b in range(1, bars_per_leg + 1):
            prices.append(p0 + (p1 - p0) * b / bars_per_leg)
    return pd.DataFrame({"High": prices, "Low": prices, "Close": prices, "Open": prices})


def test_segment_swings_finds_root_bridge():
    # Up-trend (with small pullbacks) into a climax at 60, then a big counter-
    # burst down to 53 (the AR), then a tight range. The root swing is the
    # 60 -> 53 leg: it terminates the trend and births the range.
    df = _ramp_frame([50, 53, 51.5, 56, 54, 60, 53, 56, 53.5, 56, 53.5])

    res = segment_swings(df, atr_val=1.0)

    assert res["dominant_direction"] == 1
    assert res["n_swings"] == 8

    root = res["root_swing"]
    assert root is not None
    assert root["bc_bar"] == 30           # climax pivot (price 60)
    assert root["ar_bar"] == 36           # first counter-burst valley (price 53)
    assert root["counter_disp_atr"] == 7.0
    # The AR (7 ATR) dwarfs the trend's pullbacks (median 1.75 ATR) -> ~4x burst.
    assert root["counter_burst_ratio"] == 4.0

    # Efficiency is a real ratio in [0, 1]; the AR is the single largest swing.
    assert 0.0 <= res["efficiency"] <= 1.0
    assert max(s["abs_disp_atr"] for s in res["swings"]) == 7.0


def _cand(combined, cand_start, box_width=0.1):
    """Build a Phase-B candidate tuple (only combined [0] and cand_start [9]
    drive selection; the rest are placeholders)."""
    return (combined, 100.0, 90.0, box_width, 5, 5, 0, 10, 5, cand_start)


def test_phase_b_select_best_takes_global_best():
    # A later, tighter (higher-combined) pair vs an earlier, looser one.
    early_loose = _cand(combined=0.50, cand_start=10)
    late_tight = _cand(combined=0.80, cand_start=40)
    chosen = select_phase_b_candidate([early_loose, late_tight], "best")
    assert chosen is late_tight  # best == highest combined, regardless of start


def test_phase_b_select_earliest_prefers_earlier_start():
    # Every candidate has already passed worked-equilibrium validity, so
    # "earliest" takes the earliest start (longest cause) even when a later
    # framing scores higher combined. There is no reach-quality floor anymore:
    # a sparse / dead-space framing can no longer be a valid candidate, so the
    # old "is the early framing good enough?" question is moot.
    early = _cand(combined=0.60, cand_start=10)
    late_tight = _cand(combined=0.80, cand_start=40)
    chosen = select_phase_b_candidate([late_tight, early], "earliest")
    assert chosen is early


def test_phase_b_select_earliest_breaks_ties_by_quality():
    # When two valid framings start on the same bar, the higher-combined one
    # wins the tie (the -x[0] secondary key).
    start_lo = _cand(combined=0.50, cand_start=10)
    start_hi = _cand(combined=0.80, cand_start=10)
    chosen = select_phase_b_candidate([start_lo, start_hi], "earliest")
    assert chosen is start_hi


def test_phase_b_select_earliest_never_empties_pool():
    # A single candidate is always returned (it is, by construction, valid).
    only = _cand(combined=0.30, cand_start=5)
    assert select_phase_b_candidate([only], "earliest") is only


def _osc_frame(closes, band=1.0):
    """OHLC frame with High/Low a fixed band around each close."""
    return pd.DataFrame({
        "High": [c + band for c in closes],
        "Low": [c - band for c in closes],
        "Close": list(closes),
    })


# A triangle wave that traverses the whole [100,110] box: touches both rails
# repeatedly, fills the middle bins, and never huddles mid-box. (3 cycles.)
_WORKED = [101, 103, 105, 107, 109, 107, 105, 103] * 3
# Price lives in the top after a single one-time dip to the low — the dead-space
# pathology the engine used to anchor on (support pinned to a low price never revisits).
_DEAD_SPACE = [100, 102] + [106, 109, 107, 108, 106, 109, 107, 108] * 2 + [106, 109, 107, 108, 106, 109]


def test_measure_equilibrium_worked_range_is_filled_and_two_sided():
    eq = measure_equilibrium(_osc_frame(_WORKED), R=110.0, S=100.0, atr_val=1.0)
    assert eq["r_touches"] >= 3 and eq["s_touches"] >= 3
    assert eq["r_touch_thirds"] >= 2 and eq["s_touch_thirds"] >= 2
    assert eq["lower_dwell"] >= 0.15 and eq["upper_dwell"] >= 0.15
    assert eq["mid_dwell"] <= 0.85
    assert eq["coverage"] >= 0.80


def test_measure_equilibrium_dead_space_starves_the_lower_half():
    eq = measure_equilibrium(_osc_frame(_DEAD_SPACE), R=110.0, S=100.0, atr_val=1.0)
    # Price lives up top after a one-time dip: the lower half is dead (dwell
    # collapses there) while the upper half hogs the action.
    assert eq["lower_dwell"] < 0.15
    assert eq["upper_dwell"] > 0.45


def test_measure_equilibrium_range_occupancy_uses_high_low_not_close():
    frame = pd.DataFrame([
        {"High": 110.0, "Low": 100.0, "Close": 105.0},
        {"High": 110.0, "Low": 100.0, "Close": 105.0},
        {"High": 110.0, "Low": 100.0, "Close": 105.0},
    ])

    eq = measure_equilibrium(frame, R=110.0, S=100.0, atr_val=1.0)

    assert eq["r_touches"] == 3
    assert eq["s_touches"] == 3
    assert eq["lower_dwell"] == 1.0
    assert eq["mid_dwell"] == 1.0
    assert eq["upper_dwell"] == 1.0
    assert eq["coverage"] == 1.0


def test_validate_base_quality_accepts_worked_rejects_dead_space():
    # A genuinely worked range validates; a dead-space range does not.
    _rt, _st, _eq, ok_worked = _validate_base_quality(
        _osc_frame(_WORKED), 110.0, 100.0, 1.0)
    _rt2, _st2, _eq2, ok_dead = _validate_base_quality(
        _osc_frame(_DEAD_SPACE), 110.0, 100.0, 1.0)
    assert ok_worked is True
    assert ok_dead is False


def test_worked_window_end_trims_only_a_held_late_breakout():
    # The SOS -> BUEC rescue: a worked range whose right side has broken out above
    # R and HELD above support is validated over its cause, not the breakout tail.
    from core.structure.box_primitives import _worked_window_end
    R, S, atr = 110.0, 100.0, 1.0          # buffer = BOUNDARY_ATR_BUFFER * atr
    base_h, base_l = [105.0] * 20, [104.0] * 20
    # A sustained breakout above R that holds above S -> trim exactly the tail.
    assert _worked_window_end(base_h + [118.0] * 6, base_l + [115.0] * 6,
                              R, S, atr) == 20
    # An all-in-range window has no breakout tail -> no-op (full length).
    assert _worked_window_end([105.0] * 26, [104.0] * 26, R, S, atr) == 26
    # A 2-bar poke is below SOS_TRIM_MIN_RUN -> not a breakout -> no trim.
    assert _worked_window_end(base_h + [118.0] * 2 + [105.0] * 4,
                              base_l + [115.0] * 2 + [104.0] * 4, R, S, atr) == 26
    # A breakout that loses support afterwards is a breakdown, not SOS -> no trim.
    assert _worked_window_end(base_h + [118.0] * 4 + [105.0] * 2,
                              base_l + [115.0] * 4 + [90.0] * 2, R, S, atr) == 26


def _flat_frame(closes):
    """High == Low == Close, so a swing's amplitude is the raw close move (no
    band inflation) — needed to exercise genuinely sub-threshold reversals."""
    return pd.DataFrame({"High": list(closes), "Low": list(closes), "Close": list(closes)})


def test_measure_traversal_counts_rail_to_rail_swings():
    # The worked triangle wave runs the full box repeatedly: many genuine
    # rail-to-rail traversals and no dead space at either rail.
    t = measure_traversal(_osc_frame(_WORKED), R=110.0, S=100.0, atr_val=1.0)
    assert t["n_full_traversals"] >= 2
    assert t["top_dead_space"] is not None and t["top_dead_space"] < 0.15
    assert t["bottom_dead_space"] is not None and t["bottom_dead_space"] < 0.15


def test_measure_traversal_flags_dead_space_hanging_from_a_rail():
    # Price hangs in the top after one initial dip: only that single trip reaches
    # S, so rail-to-rail traversals collapse and the lower half reads as dead.
    t = measure_traversal(_osc_frame(_DEAD_SPACE), R=110.0, S=100.0, atr_val=1.0)
    assert t["n_full_traversals"] < 2
    assert t["bottom_dead_space"] > 0.30


def test_measure_traversal_absorbs_subthreshold_reversal():
    # A 1.2-wide pullback inside an up-leg of an 11-wide box (min_amp = 0.15*11 =
    # 1.65) must be absorbed: the swing list stays V->P->V (3, via soft endpoints),
    # not split into 5 by the noise pivot, and the leg reads as 2 traversals.
    frame = _flat_frame([100, 110, 108.8, 111, 100])
    t = measure_traversal(frame, R=111.0, S=100.0, atr_val=1.0)
    assert t["n_swings"] == 3
    assert t["n_full_traversals"] == 2


def test_measure_traversal_guards_bad_inputs():
    frame = _osc_frame(_WORKED)
    # Non-positive / NaN ATR and a non-positive box collapse to the empty read.
    assert (measure_traversal(frame, 110.0, 100.0, 0.0)
            == measure_traversal(frame, 110.0, 100.0, -1.0))
    assert measure_traversal(frame, 100.0, 100.0, 1.0)["n_full_traversals"] == 0
    assert measure_traversal(frame, 110.0, 100.0, float("nan"))["n_swings"] == 0
    # Too few bars to form a pivot structure.
    assert measure_traversal(_flat_frame([1, 2]), 2.0, 1.0, 1.0)["n_swings"] == 0


def test_segment_swings_guards_bad_inputs():
    df = _ramp_frame([50, 53, 51.5, 56, 54, 60, 53, 56, 53.5, 56, 53.5])
    # Non-positive / NaN ATR must never divide a displacement.
    assert segment_swings(df, atr_val=0.0) == segment_swings(df, atr_val=-1.0)
    assert segment_swings(df, atr_val=0.0)["root_swing"] is None
    assert segment_swings(df, atr_val=float("nan"))["n_swings"] == 0
    # Too few bars to form a swing structure.
    tiny = pd.DataFrame({"High": [1, 2, 3], "Low": [1, 2, 3],
                         "Close": [1, 2, 3], "Open": [1, 2, 3]})
    assert segment_swings(tiny, atr_val=1.0)["n_swings"] == 0


def test_flatten_summary_sums_numeric_values_and_ignores_unknown_tags():
    summary = {
        "DU1": {
            "NetLiquidation": {"value": "1000.50", "currency": "USD"},
            "AvailableFunds": {"value": "250", "currency": "USD"},
            "Ignored": {"value": "999", "currency": "USD"},
        },
        "DU2": {
            "NetLiquidation": {"value": "99.50", "currency": "USD"},
            "AvailableFunds": {"value": "not-ready", "currency": "USD"},
        },
    }

    flattened = flatten_summary(summary)

    assert flattened["values"]["NetLiquidation"] == 1100
    assert flattened["values"]["AvailableFunds"] == 250
    assert "Ignored" not in flattened["values"]
    assert flattened["currency"]["NetLiquidation"] == "USD"
    assert flattened["raw"] == summary


def test_cached_portfolio_snapshot_preserves_last_known_data():
    current = {
        "connected": False,
        "mode": "paper",
        "stale": True,
        "last_update": 200,
        "account_summary": {"values": {}, "currency": {}, "raw": {}},
        "positions": [],
        "open_orders": [],
        "recent_executions": [],
    }
    cached = {
        "last_update": 100,
        "account_summary": {"values": {"NetLiquidation": 1234}, "currency": {}, "raw": {}},
        "positions": [{"symbol": "AAPL"}],
        "open_orders": [{"symbol": "MSFT"}],
        "recent_executions": [{"symbol": "NVDA"}],
    }

    snapshot = with_cached_snapshot(current, cached)

    assert has_portfolio_data(snapshot)
    assert snapshot["backend_cached"] is True
    assert snapshot["last_update"] == 100
    assert snapshot["positions"] == cached["positions"]


@pytest.mark.parametrize(
    ("raw_symbol", "clean_symbol"),
    [("pep", "PEP"), (" brk.b ", "BRK.B"), ("abc-1", "ABC-1")],
)
def test_clean_symbol_accepts_supported_ticker_shapes(raw_symbol, clean_symbol):
    assert _clean_symbol(raw_symbol) == clean_symbol


@pytest.mark.parametrize("raw_symbol", ["", "../secrets", "AAPL$", "TOO-LONG-SYMBOL-123"])
def test_clean_symbol_rejects_unsafe_values(raw_symbol):
    with pytest.raises(HTTPException):
        _clean_symbol(raw_symbol)


@pytest.mark.parametrize("value", [0, "12.5", 7.0])
def test_is_number_accepts_finite_numeric_values(value):
    assert _is_number(value)


@pytest.mark.parametrize("value", [None, "nope", math.inf, math.nan])
def test_is_number_rejects_non_finite_values(value):
    assert not _is_number(value)


# ──────────────────────────────────────────────────────────────────
# Triple-barrier outcome labelling (core.archive.forward_returns)
# entry=100, s_level=95 → stop=92.15, risk=7.85, 2.5R target=119.625, +15%=115
# ──────────────────────────────────────────────────────────────────
def test_barrier_win_via_2_5r_when_price_jumps_straight_through():
    # Bar 1 high 120 clears BOTH targets on the same bar; 2.5R is the stronger
    # move so it is credited as the winning barrier.
    res = compute_barrier_events(highs=[120, 121], lows=[99, 99], entry=100, s_level=95)
    assert res["barrier_label"] == "win"
    assert res["win_barrier"] == "2.5R"
    assert res["days_to_2_5r"] == 1
    assert res["days_to_15pct"] == 1
    assert res["days_to_stop"] is None


def test_barrier_win_via_15pct_when_it_fires_first():
    # +15% (115) is touched at bar 2; 2.5R (119.625) is never reached.
    res = compute_barrier_events(highs=[110, 116, 117], lows=[99, 99, 99], entry=100, s_level=95)
    assert res["barrier_label"] == "win"
    assert res["win_barrier"] == "15pct"
    assert res["days_to_15pct"] == 2
    assert res["days_to_2_5r"] is None


def test_barrier_loss_when_stop_hit_before_target():
    res = compute_barrier_events(highs=[101, 102, 103], lows=[99, 91, 99], entry=100, s_level=95)
    assert res["barrier_label"] == "loss"
    assert res["days_to_stop"] == 2
    assert res["win_barrier"] is None


def test_barrier_same_bar_tie_resolves_to_loss():
    # Bar 1 touches a target (high 120) AND the stop (low 92) — conservative
    # assumption for a long: the adverse move is taken first.
    res = compute_barrier_events(highs=[120], lows=[92], entry=100, s_level=95)
    assert res["barrier_label"] == "loss"


def test_barrier_timeout_when_neither_barrier_touched():
    res = compute_barrier_events(highs=[101, 102, 103], lows=[99, 98, 97], entry=100, s_level=95)
    assert res["barrier_label"] == "timeout"
    assert res["days_to_2_5r"] is None
    assert res["days_to_15pct"] is None
    assert res["days_to_stop"] is None


def test_barrier_degenerate_stop_above_entry_is_unlabelled():
    # s_level*0.97 sits above entry → risk <= 0 → cannot label.
    res = compute_barrier_events(highs=[130], lows=[80], entry=100, s_level=105)
    assert res["barrier_label"] is None
    assert res["win_barrier"] is None


def test_barrier_horizon_caps_the_race():
    # Stop only touched after the horizon → not seen → timeout, not loss.
    highs = [101] * 5
    lows = [99] * 4 + [80]
    res = compute_barrier_events(highs, lows, entry=100, s_level=95, horizon=4)
    assert res["barrier_label"] == "timeout"
    assert res["days_to_stop"] is None


# ──────────────────────────────────────────────────────────────────
# Forward-return maturity guards (core.archive.forward_returns)
# ──────────────────────────────────────────────────────────────────
def test_compute_returns_caps_trigger_detection_at_60_forward_bars():
    n = FORWARD_RETURN_HORIZON_BARS + 5
    idx = pd.date_range("2026-01-02", periods=n, freq="B")
    highs = [101.0] * FORWARD_RETURN_HORIZON_BARS + [130.0] * 5
    fwd_df = pd.DataFrame({
        "Open": [100.0] * n,
        "High": highs,
        "Low": [99.0] * n,
        "Close": [100.0] * n,
        "Volume": [1000.0] * n,
    }, index=idx)

    res = _compute_returns(
        fwd_df,
        scan_close=100.0,
        trigger_price=120.0,
        s_level=95.0,
        vol_50_at_scan=1000.0,
    )

    assert res["triggered"] == 0
    assert "days_to_trigger" not in res
    assert res["fwd_return_60d"] == 0
    assert res["barrier_label"] == "timeout"


def test_compute_returns_defers_timeout_until_60_bar_window_complete():
    n = 5
    idx = pd.date_range("2026-01-02", periods=n, freq="B")
    fwd_df = pd.DataFrame({
        "Open": [100.0] * n,
        "High": [101.0] * n,
        "Low": [99.0] * n,
        "Close": [100.0] * n,
        "Volume": [1000.0] * n,
    }, index=idx)

    res = _compute_returns(fwd_df, scan_close=100.0, trigger_price=120.0, s_level=95.0)

    assert res["barrier_label"] is None
    assert "fwd_return_20d" not in res
    assert "fwd_return_60d" not in res


# Seed-recall baseline guard (core.archive.seed_recall)
def test_seed_recall_guard_fails_on_new_miss():
    baseline = {"recall": 0.8, "misses": [{"ticker": "AAA", "trigger_date": "2026-01-01"}]}
    current = {"recall": 0.8}
    current_misses = [
        {"ticker": "AAA", "trigger_date": "2026-01-01"},
        {"ticker": "BBB", "trigger_date": "2026-02-02"},  # newly lost winner
    ]
    ok, lines = seed_diff_against_baseline(current, current_misses, baseline)
    assert ok is False
    assert any("BBB" in line for line in lines)


def test_seed_recall_guard_fails_on_recall_regression():
    baseline = {"recall": 0.80, "misses": []}
    ok, _ = seed_diff_against_baseline({"recall": 0.70}, [], baseline)
    assert ok is False


def test_seed_recall_guard_passes_when_winner_recovered():
    # A previously-missed winner now found, recall improved → must pass.
    baseline = {"recall": 0.70, "misses": [{"ticker": "AAA", "trigger_date": "2026-01-01"}]}
    ok, _ = seed_diff_against_baseline({"recall": 0.85}, [], baseline)
    assert ok is True


# ──────────────────────────────────────────────────────────────────
# Shadow-output diff guard (tools.shadow_diff)
# ──────────────────────────────────────────────────────────────────
def test_shadow_canonical_fields_ignores_new_diagnostics():
    # A brand-new diagnostic field must not appear in the canonical projection,
    # so measure-first additions can never trip the guard.
    result = {"Setup": "LPS", "Score": 100.123456789, "Tier": "A",
              "_brand_new_diagnostic": 0.42}
    fields = canonical_fields(result)
    assert "_brand_new_diagnostic" not in fields
    assert fields["Score"] == round(100.123456789, 6)


def test_shadow_guard_fails_on_canonical_field_drift():
    baseline = {"fields": {"AAA": {"Setup": "LPS", "Score": 100.0, "Tier": "A"}},
                "ranking": ["AAA"]}
    current = {"fields": {"AAA": {"Setup": "LPS", "Score": 105.0, "Tier": "A"}},
               "ranking": ["AAA"]}
    ok, lines = shadow_diff_against_baseline(current, baseline)
    assert ok is False
    assert any("AAA.Score" in line for line in lines)


def test_shadow_guard_passes_when_only_a_new_field_added():
    # Identical canonical fields; current carries an extra diagnostic key.
    baseline = {"fields": {"AAA": canonical_fields({"Setup": "LPS", "Score": 100.0, "Tier": "A"})},
                "ranking": ["AAA"]}
    current = {"fields": {"AAA": canonical_fields(
        {"Setup": "LPS", "Score": 100.0, "Tier": "A", "_new_diag": 1.0})},
        "ranking": ["AAA"]}
    ok, _ = shadow_diff_against_baseline(current, baseline)
    assert ok is True


def test_shadow_guard_fails_when_ticker_drops_out():
    baseline = {"fields": {"AAA": {"Setup": "LPS"}, "BBB": {"Setup": "LPS"}},
                "ranking": ["AAA", "BBB"]}
    current = {"fields": {"AAA": {"Setup": "LPS"}}, "ranking": ["AAA"]}
    ok, lines = shadow_diff_against_baseline(current, baseline)
    assert ok is False
    assert any("BBB" in line for line in lines)


# ──────────────────────────────────────────────────────────────────
# Bin features + Minervini trend template (Stage 2A, measure-only)
# ──────────────────────────────────────────────────────────────────
def _flat_ohlc(n, *, high=101.0, low=99.0, close=100.0, volume=1000.0):
    """Uniform OHLC frame; callers mutate specific rows for region tests."""
    return pd.DataFrame([
        {"Open": close, "High": high, "Low": low, "Close": close, "Volume": volume}
        for _ in range(n)
    ])


def test_measure_bins_slices_named_regions_at_lps():
    df = _flat_ohlc(120)
    # LPS = last 5 bars, low pinned at 100 (inside the 99..101 box).
    for i in range(115, 120):
        df.loc[i, "Low"] = 100.0
    bins = measure_bins(
        df, bc_anchor_bar=10, phase_b_start_bar=30, base_len=60,
        is_inner_box=False, lps_offset=0, lps_length=5,
        R=101.0, S=99.0, atr_val=1.0,
    )
    assert bins["bin_a_bars"] == 20          # 30 - 10
    assert bins["bin_b_bars"] == 60          # base_len
    assert bins["bin_lps_bars"] == 5
    assert bins["bin_d_bars"] == 5           # Phase D anchored at the LPS: 120 - 115
    assert bins["bin_d_boundary_source"] == "lps"
    evidence = json.loads(bins["phase_d_evidence_json"])
    assert evidence["selected"]["source"] == "lps"
    assert evidence["selected"]["meta"]["fallback"] is True
    assert abs(bins["lps_position_in_box"] - 0.5) < 1e-9   # (100-99)/(101-99)
    assert bins["bin_b_volume_ratio"] == 1.0               # uniform volume
    # LPS foot sits below the ceiling -> no Last-Supper stretch (< 0).
    assert bins["lps_stretch_box"] < 0
    assert bins["lps_stretch_atr"] == -1.0                 # (100-101)/1


def test_measure_bins_phase_a_can_end_at_root_reaction():
    df = _flat_ohlc(120)
    bins = measure_bins(
        df, bc_anchor_bar=10, phase_b_start_bar=30, phase_a_end_bar=16,
        base_len=60, is_inner_box=False, lps_offset=0, lps_length=5,
        R=101.0, S=99.0, atr_val=1.0,
    )

    assert bins["bin_a_bars"] == 6


def test_measure_bins_inner_box_sets_boundary_source_and_region():
    df = _flat_ohlc(120)
    bins = measure_bins(
        df, bc_anchor_bar=10, phase_b_start_bar=30, base_len=60,
        is_inner_box=True, lps_offset=0, lps_length=5,
        R=101.0, S=99.0, atr_val=1.0,
    )
    assert bins["bin_d_boundary_source"] == "inner_box"
    assert bins["bin_d_bars"] == 60          # Phase D = the inner box (box_start..end)


def test_measure_bins_parent_with_inner_phase_d_keeps_parent_base():
    df = _flat_ohlc(120)
    bins = measure_bins(
        df, bc_anchor_bar=10, phase_b_start_bar=30, base_len=60,
        is_inner_box=False, lps_offset=0, lps_length=5,
        R=101.0, S=99.0, atr_val=1.0, phase_d_start_bar=90,
    )
    assert bins["bin_b_bars"] == 60          # parent remains the base of record
    assert bins["bin_d_boundary_source"] == "inner_box"
    assert bins["bin_d_bars"] == 30          # Phase D spans the nested range


def test_measure_bins_evidence_json_records_selected_source():
    df = _flat_ohlc(120)
    bins = measure_bins(
        df, bc_anchor_bar=10, phase_b_start_bar=30, base_len=60,
        is_inner_box=False, lps_offset=0, lps_length=5,
        R=101.0, S=99.0, atr_val=1.0,
        support_test_start_bar=88,
        sos_reclaim_start_bar=82,
        rising_support_start_bar=84,
        v_tip_bar=86,
    )
    evidence = json.loads(bins["phase_d_evidence_json"])

    assert bins["bin_d_boundary_source"] == "sos_reclaim"
    assert evidence["selected"]["source"] == "sos_reclaim"
    assert {s["source"] for s in evidence["signals"]} >= {"support_tests", "sos_reclaim", "rising_support", "v_tip", "lps"}


def test_measure_bins_v_tip_anchors_phase_d_before_support_cluster():
    df = _flat_ohlc(120)
    bins = measure_bins(
        df, bc_anchor_bar=10, phase_b_start_bar=30, base_len=60,
        is_inner_box=False, lps_offset=0, lps_length=5,
        R=101.0, S=99.0, atr_val=1.0,
        support_test_start_bar=92, v_tip_bar=88,
    )
    assert bins["bin_d_boundary_source"] == "v_tip"
    assert bins["bin_d_bars"] == 32


def test_measure_bins_last_supper_positive_when_lps_above_ceiling():
    df = _flat_ohlc(120)
    df.loc[113, "Low"] = 102.0
    df.loc[113, "Close"] = 102.5
    df.loc[113, "High"] = 103.0
    for i in range(115, 120):
        df.loc[i, "Low"] = 103.0
        df.loc[i, "Close"] = 103.5
        df.loc[i, "High"] = 104.0
    bins = measure_bins(
        df, bc_anchor_bar=10, phase_b_start_bar=30, base_len=60,
        is_inner_box=False, lps_offset=0, lps_length=5,
        R=101.0, S=99.0, atr_val=1.0,
    )
    # LPS formed 2 points above R=101 -> stretched (the Last-Supper risk axis).
    assert bins["lps_stretch_box"] > 0
    assert bins["lps_stretch_atr"] == 2.0     # (103-101)/1
    assert bins["lps_position_in_box"] > 1.0  # above the box ceiling
    assert bins["last_supper_pullback_from_extension_pct"] == 0.0096
    assert bins["last_supper_source_box_age"] == 2
    assert bins["last_supper_reclaim_quality"] == 0.75


def test_measure_bins_lps_stretch_can_use_active_inner_box():
    df = _flat_ohlc(120, high=110.0, low=100.0, close=105.0)
    for i in range(115, 120):
        df.loc[i, "Low"] = 103.0
        df.loc[i, "Close"] = 103.5
        df.loc[i, "High"] = 104.0
    bins = measure_bins(
        df, bc_anchor_bar=10, phase_b_start_bar=30, base_len=60,
        is_inner_box=False, lps_offset=0, lps_length=5,
        R=110.0, S=100.0, atr_val=1.0, lps_R=104.0, lps_S=102.0,
    )
    assert bins["bin_b_bars"] == 60           # parent remains the base of record
    assert bins["lps_position_in_box"] == 0.5 # active inner box: (103-102)/(104-102)
    assert bins["lps_stretch_box"] == -0.5    # active inner R, not parent R
    assert bins["lps_stretch_atr"] == -1.0


def test_measure_bins_no_lps_window_degrades_gracefully():
    df = _flat_ohlc(120)
    bins = measure_bins(
        df, bc_anchor_bar=10, phase_b_start_bar=30, base_len=60,
        is_inner_box=False, lps_offset=200, lps_length=5,   # window falls off the frame
        R=101.0, S=99.0, atr_val=1.0,
    )
    assert bins["bin_lps_bars"] is None
    assert bins["lps_stretch_atr"] is None
    assert bins["bin_d_bars"] is None         # heuristic Phase D keys off the LPS start
    assert bins["bin_b_bars"] == 60           # the base region is still measured


def test_measure_bins_phase_d_support_delta_blank_when_unmeasured():
    # The support-test boundary creates a Phase D slice that is too short to fit
    # swing lows. Its standalone quality is neutral, but the D-vs-B comparison
    # should stay blank instead of pretending "no measurement" is weaker support.
    lead = _ramp_frame([104, 108, 103, 107, 102, 106, 101, 105, 100, 104])
    lead["Volume"] = 1000.0
    d = _ramp_frame([104, 105])
    d["Volume"] = 1000.0
    df = pd.concat([lead, d], ignore_index=True)
    d_start = len(lead)

    bins = measure_bins(
        df, bc_anchor_bar=0, phase_b_start_bar=1, base_len=len(df),
        is_inner_box=False, lps_offset=0, lps_length=2,
        R=108.0, S=100.0, atr_val=1.0, support_test_start_bar=d_start,
    )

    assert bins["bin_d_support_slope_atr"] is None
    assert bins["bin_d_ascending_support_quality"] == 0.0
    assert bins["bin_d_boundary_source"] == "support_tests"
    assert bins["bin_d_vs_b_support_quality_delta"] is None


def test_measure_bins_phase_c_spring_requires_recovery():
    df = _flat_ohlc(120, low=100.0, close=100.2)
    # A clean-V spring: a visible undercut of S (0.8 ATR) that reclaims S by
    # Close on the next bar and holds.
    df.loc[95, "Low"] = 98.2
    df.loc[95, "Close"] = 98.9
    df.loc[96, "Low"] = 99.1
    df.loc[96, "Close"] = 99.2

    bins = measure_bins(
        df, bc_anchor_bar=10, phase_b_start_bar=30, base_len=60,
        is_inner_box=False, lps_offset=0, lps_length=5,
        R=101.0, S=99.0, atr_val=1.0,
    )

    assert bins["bin_c_present"] is True
    assert bins["bin_c_type"] == "SPRING"
    assert bins["bin_c_undercut_atr"] == 0.8
    assert bins["bin_c_recovery_bars"] == 1
    assert bins["bin_c_event_bar"] == 95
    assert bins["bin_c_recovery_bar"] == 96
    # The spring reclaim (96) FLOORS Phase D but does not anchor it; with no
    # richer right-side evidence after it, D opens at the LPS (the gate).
    assert bins["bin_d_start_bar"] == 115
    assert bins["bin_d_boundary_source"] == "lps"
    assert bins["bin_c_time_loc"] == pytest.approx((95 - 60) / 59, abs=0.0001)


def test_measure_bins_phase_c_spring_floors_out_earlier_v_tip():
    df = _flat_ohlc(120, low=100.0, close=100.2)
    df.loc[95, "Low"] = 98.2
    df.loc[95, "Close"] = 98.9
    df.loc[96, "Close"] = 99.2

    bins = measure_bins(
        df, bc_anchor_bar=10, phase_b_start_bar=30, base_len=60,
        is_inner_box=False, lps_offset=0, lps_length=5,
        R=101.0, S=99.0, atr_val=1.0, v_tip_bar=88,
    )

    assert bins["bin_c_type"] == "SPRING"
    # The V-tip at 88 sits BEFORE the spring reclaim (96), so it is floored out
    # (it belonged to Phase C); Phase D falls back to the LPS.
    assert bins["bin_d_start_bar"] == 115
    assert bins["bin_d_boundary_source"] == "lps"


def test_measure_bins_inner_after_spring_recovery_opens_phase_d():
    df = _flat_ohlc(120, low=100.0, close=100.2)
    df.loc[95, "Low"] = 98.2
    df.loc[95, "Close"] = 98.9
    df.loc[96, "Close"] = 99.2

    bins = measure_bins(
        df, bc_anchor_bar=10, phase_b_start_bar=30, base_len=60,
        is_inner_box=False, lps_offset=0, lps_length=5,
        R=101.0, S=99.0, atr_val=1.0, phase_d_start_bar=100,
    )

    assert bins["bin_c_type"] == "SPRING"
    # An inner mini-consolidation at 100 is AFTER the reclaim (96): it is the
    # earliest credible right-side evidence and opens Phase D, ahead of the LPS.
    assert bins["bin_d_start_bar"] == 100
    assert bins["bin_d_boundary_source"] == "inner_box"


def test_measure_bins_phase_c_rejects_shallow_undercut():
    # A barely-below-support poke (0.2 ATR) is a "test at support", not a spring
    # — the undercut floor rejects it even though it reclaims by Close.
    df = _flat_ohlc(120, low=100.0, close=100.2)
    df.loc[95, "Low"] = 98.8
    df.loc[95, "Close"] = 98.9
    df.loc[96, "Close"] = 99.2

    bins = measure_bins(
        df, bc_anchor_bar=10, phase_b_start_bar=30, base_len=60,
        is_inner_box=False, lps_offset=0, lps_length=5,
        R=101.0, S=99.0, atr_val=1.0,
    )

    assert bins["bin_c_present"] is False
    assert bins["bin_c_type"] is None
    assert bins["bin_c_event_bar"] is None
    assert bins["bin_c_recovery_bar"] is None


def test_measure_bins_phase_c_accepts_linger_spring():
    # A choppy multi-bar sojourn below S (not a clean V) that reclaims and holds
    # is a valid spring — the "linger below support then recover" variation.
    df = _flat_ohlc(120, low=100.0, close=100.2)
    df.loc[95, ["Low", "Close"]] = [98.5, 98.7]
    df.loc[96, ["Low", "Close"]] = [98.2, 98.6]   # trough
    df.loc[97, ["Low", "Close"]] = [98.3, 98.4]
    df.loc[98, ["Low", "Close"]] = [98.4, 98.8]
    df.loc[99, ["Low", "Close"]] = [98.9, 99.3]   # reclaim; bars 100+ hold above S

    bins = measure_bins(
        df, bc_anchor_bar=10, phase_b_start_bar=30, base_len=60,
        is_inner_box=False, lps_offset=0, lps_length=5,
        R=101.0, S=99.0, atr_val=1.0,
    )

    assert bins["bin_c_present"] is True
    assert bins["bin_c_type"] == "SPRING"
    assert bins["bin_c_event_bar"] == 96      # the trough, not the first penetration
    assert bins["bin_c_recovery_bar"] == 99
    assert bins["bin_c_recovery_bars"] == 3
    assert bins["bin_c_undercut_atr"] == 0.8


def test_measure_bins_phase_c_rejects_never_reclaimed():
    # A sojourn below S that never closes back above it is a breakdown, not a spring.
    df = _flat_ohlc(120, low=100.0, close=100.2)
    for idx in range(95, 120):
        df.loc[idx, ["Low", "Close"]] = [98.0, 98.3]

    bins = measure_bins(
        df, bc_anchor_bar=10, phase_b_start_bar=30, base_len=60,
        is_inner_box=False, lps_offset=0, lps_length=5,
        R=101.0, S=99.0, atr_val=1.0,
    )

    assert bins["bin_c_present"] is False
    assert bins["bin_c_type"] is None


def test_measure_bins_phase_c_rejects_poke_and_fail():
    # Penetrate + reclaim for ONE bar, then break back below S and stay there:
    # the hold check rejects it (a real spring's reclaim sticks = supply absorbed).
    df = _flat_ohlc(120, low=100.0, close=100.2)
    df.loc[95, ["Low", "Close"]] = [98.5, 98.7]   # penetrate
    df.loc[96, ["Low", "Close"]] = [98.9, 99.3]   # one-bar reclaim
    for idx in range(97, 120):
        df.loc[idx, ["Low", "Close"]] = [98.0, 98.3]  # fails back below S, sustained

    bins = measure_bins(
        df, bc_anchor_bar=10, phase_b_start_bar=30, base_len=60,
        is_inner_box=False, lps_offset=0, lps_length=5,
        R=101.0, S=99.0, atr_val=1.0,
    )

    assert bins["bin_c_present"] is False
    assert bins["bin_c_type"] is None


def test_measure_bins_phase_c_does_not_label_held_test_from_above():
    df = _flat_ohlc(120, low=100.0, close=100.2)
    df.loc[110, "Low"] = 99.2
    df.loc[110, "Close"] = 99.4

    bins = measure_bins(
        df, bc_anchor_bar=10, phase_b_start_bar=30, base_len=60,
        is_inner_box=False, lps_offset=0, lps_length=5,
        R=101.0, S=99.0, atr_val=1.0,
    )

    assert bins["bin_c_present"] is False
    assert bins["bin_c_type"] is None


def test_measure_bins_phase_c_held_test_stays_near_support():
    df = _flat_ohlc(120, high=104.0, low=102.0, close=102.2)

    bins = measure_bins(
        df, bc_anchor_bar=10, phase_b_start_bar=30, base_len=60,
        is_inner_box=False, lps_offset=0, lps_length=5,
        R=104.0, S=100.0, atr_val=1.0,
    )

    assert bins["bin_c_present"] is False
    assert bins["bin_c_type"] is None


def test_measure_bins_phase_c_rejects_too_deep_undercut():
    df = _flat_ohlc(120, low=100.0, close=100.2)
    df.loc[95, "Low"] = 97.4
    df.loc[95, "Close"] = 99.2

    bins = measure_bins(
        df, bc_anchor_bar=10, phase_b_start_bar=30, base_len=60,
        is_inner_box=False, lps_offset=0, lps_length=5,
        R=101.0, S=99.0, atr_val=1.0,
    )

    assert bins["bin_c_present"] is False
    assert bins["bin_c_type"] is None


def test_measure_bins_phase_c_requires_atr_frame():
    df = _flat_ohlc(120, low=100.0, close=100.2)
    df.loc[95, "Low"] = 98.8
    df.loc[95, "Close"] = 99.2

    bins = measure_bins(
        df, bc_anchor_bar=10, phase_b_start_bar=30, base_len=60,
        is_inner_box=False, lps_offset=0, lps_length=5,
        R=101.0, S=99.0, atr_val=None,
    )

    assert bins["bin_c_present"] is False
    assert bins["bin_c_type"] is None


def test_resolve_phase_d_start_matches_scope_rule():
    # Corrected model: the LPS is the GATE / fallback. A spring RECOVERY ends
    # Phase C and only FLOORS the search; Phase D opens at the EARLIEST credible
    # right-side evidence AFTER that floor.
    common = dict(box_start=60, base_len=60, last=119, is_inner_box=False,
                  has_lps_window=True, b=30)
    # No richer evidence -> LPS fallback.
    assert _resolve_phase_d_start(lps_start=115, **common) == 115
    # A spring recovery is NOT itself the Phase-D start: with nothing after it,
    # Phase D still falls back to the LPS (it does not anchor at the reclaim).
    assert _resolve_phase_d_start(lps_start=115, phase_c_recovery_bar=96, **common) == 115
    # Earliest right-side evidence wins regardless of type (v_tip @88 < inner @90
    # < support @92).
    assert _resolve_phase_d_start(lps_start=115, phase_d_start_bar=90,
                                  support_test_start_bar=92, v_tip_bar=88, **common) == 88
    assert _resolve_phase_d_start(lps_start=115, support_test_start_bar=92,
                                  v_tip_bar=88, **common) == 88
    assert _resolve_phase_d_start(lps_start=115, support_test_start_bar=92, **common) == 92
    # The spring reclaim floors it: evidence BEFORE the reclaim is ignored; the
    # earliest evidence AFTER it wins.
    assert _resolve_phase_d_start(lps_start=115, phase_c_recovery_bar=91,
                                  v_tip_bar=88, support_test_start_bar=95,
                                  **common) == 95
    assert _resolve_phase_d_start(lps_start=115, phase_c_recovery_bar=91,
                                  phase_d_start_bar=93, support_test_start_bar=95,
                                  **common) == 93
    # Shakeout case: the LPS pullback can predate the reclaim, but Phase D never
    # opens before it — the LPS fallback clamps UP to the recovery floor, so D
    # lands right at "the recovery after a mean shakeout".
    assert _resolve_phase_d_start(lps_start=90, phase_c_recovery_bar=96, **common) == 96
    # Active inner box implies its box start.
    assert _resolve_phase_d_start(box_start=60, base_len=60, last=119,
                                  is_inner_box=True, has_lps_window=True,
                                  lps_start=115, b=30) == 60
    # Clamp: never cross the body start b.
    assert _resolve_phase_d_start(lps_start=20, **common) == 30
    # No LPS window -> None.
    assert _resolve_phase_d_start(box_start=60, base_len=60, last=119,
                                  is_inner_box=False, has_lps_window=False,
                                  lps_start=0, b=30) is None


def test_resolve_phase_d_boundary_lps_fallback_respects_search_start_floor():
    from core.structure.phase_d import resolve_phase_d_boundary
    # The LPS fallback must not open Phase D before the declared search-start
    # floor (the floor includes search_start_bar, not only the spring reclaim).
    pb = resolve_phase_d_boundary(last=119, has_lps_window=True, lps_start=90,
                                  b=30, search_start_bar=100)
    assert pb.start_bar == 100 and pb.source == "lps"
    # ...but a later LPS still wins on its own bar.
    pb2 = resolve_phase_d_boundary(last=119, has_lps_window=True, lps_start=110,
                                   b=30, search_start_bar=100)
    assert pb2.start_bar == 110 and pb2.source == "lps"


def test_resolve_phase_d_boundary_earliest_evidence_after_floor_wins():
    from core.structure.phase_d import resolve_phase_d_boundary

    pb = resolve_phase_d_boundary(
        last=119,
        has_lps_window=True,
        lps_start=110,
        b=30,
        phase_c_recovery_bar=80,
        support_test_start_bar=78,
        sos_reclaim_start_bar=92,
        rising_support_start_bar=88,
        phase_d_start_bar=90,
        v_tip_bar=86,
    )

    assert pb.start_bar == 86
    assert pb.source == "v_tip"
    assert pb.evidence["floor"] == 80
    assert pb.evidence["selected"]["source"] == "v_tip"


def test_support_test_evidence_starts_classifies_cluster_sos_and_rising_support():
    from core.structure.phase_d import support_test_evidence_starts

    starts = support_test_evidence_starts([
        {"start_index": 20, "end_index": 22, "low": 101.0, "zone_type": "INSIDE"},
        {"start_index": 25, "end_index": 27, "low": 102.0, "zone_type": "OVERSHOOT_R"},
        {"start_index": 29, "end_index": 31, "low": 103.0, "zone_type": "INSIDE"},
    ], box_start=0, base_len=40)

    assert starts == {
        "support_tests": 20,
        "sos_reclaim": 25,
        "rising_support": 20,
    }


def test_trend_template_full_pass_on_clean_uptrend():
    n = 252
    df = pd.DataFrame([
        {"Open": 10 + 0.36 * i, "High": (10 + 0.36 * i) * 1.01,
         "Low": (10 + 0.36 * i) * 0.99, "Close": 10 + 0.36 * i, "Volume": 1000}
        for i in range(n)
    ])
    t = trend_template(df, dist_52w_high_pct=-0.01)
    assert t["stage2_trend_pass"] is True
    assert t["stage2_trend_pass_count"] == 7
    assert t["stage2_ma_stack_pass"] is True
    assert t["stage2_ma200_slope_1m_pct"] > 0
    assert t["stage2_52w_low_pct"] > 0.30


def test_trend_template_insufficient_history_degrades():
    df = pd.DataFrame([
        {"Open": 100, "High": 101, "Low": 99, "Close": 100, "Volume": 1000}
        for _ in range(150)        # < 200 bars
    ])
    t = trend_template(df, dist_52w_high_pct=-0.01)
    assert t["stage2_trend_pass"] is False
    assert t["stage2_trend_pass_count"] == 0
    assert t["stage2_ma200_slope_1m_pct"] is None
    assert t["stage2_ma_stack_pass"] is False


# ──────────────────────────────────────────────────────────────────
# No-opinion invariant: the measurement + scoring engines must never
# depend on the archive/outcome layer (structure measures, scoring
# judges, archive learns — one-way dependency).
# ──────────────────────────────────────────────────────────────────
@pytest.mark.parametrize("engine_dir", ["scoring", "structure"])
def test_engines_do_not_import_archive(engine_dir):
    base = ROOT / "core" / engine_dir
    offenders = []
    for py in base.rglob("*.py"):
        text = py.read_text(encoding="utf-8")
        for line in text.splitlines():
            stripped = line.strip()
            if stripped.startswith(("import ", "from ")) and "core.archive" in stripped:
                offenders.append(f"{py.name}: {stripped}")
    assert not offenders, (
        "core/{} must not import core.archive (scoring/structure judge facts, "
        "they never read outcomes): {}".format(engine_dir, offenders)
    )


# ──────────────────────────────────────────────────────────────────
# Phase-D scoping layer (scope_consolidation): pure descriptive
# measurement — re-expresses the detected box / swing / LPS as the
# right-most launch region. Never gates, never scores.
# ──────────────────────────────────────────────────────────────────
def _scope_df(n=30, low=100.0):
    """A length-n OHLC-ish frame with a DatetimeIndex (Low + High are read)."""
    idx = pd.date_range("2026-01-01", periods=n, freq="D")
    return pd.DataFrame({"Low": [low] * n, "High": [low + 1.0] * n}, index=idx)


def test_scope_outer_box_orders_a_b_d_bands():
    df = _scope_df(30)
    df.iloc[26, df.columns.get_loc("Low")] = 95.0  # min of the LPS window [25:29]
    df.iloc[26, df.columns.get_loc("High")] = 96.0
    out = scope_consolidation(
        df, bc_anchor_bar=2, phase_b_start_bar=5, base_len=25,
        is_inner_box=False, lps_offset=1, lps_length=4,
        lps_zone_type="INSIDE", atr_val=1.0,
    )
    # Outer box: A=climax, B=body start, D=right-most region (>= body start,
    # within the frame — its exact bar is anchored on the swing-high logic).
    assert out["phase_a_start_date"] == str(df.index[2])[:10]
    assert out["phase_b_start_date"] == str(df.index[5])[:10]
    assert out["phase_d_start_bar"] is not None
    assert 5 <= out["phase_d_start_bar"] <= 29
    assert out["phase_c_event_date"] is None
    assert out["has_mini_consolidation"] is False
    # All three regions placed → full confidence (D weighted 0.5).
    assert out["scope_confidence"] == 1.0
    # LPS zone = bounding box of the candidate bars [25:29): low = the dip at
    # bar 26 (95.0), high = the max High across those bars (101.0 default).
    assert out["lps_zone_low"] == 95.0
    assert out["lps_zone_high"] == 101.0
    # Tight in time too: the box spans the exact candidate bars.
    assert out["lps_zone_start_date"] == str(df.index[25])[:10]
    assert out["lps_zone_end_date"] == str(df.index[28])[:10]


def test_scope_phase_a_can_end_before_phase_b_body():
    df = _scope_df(30)
    out = scope_consolidation(
        df, bc_anchor_bar=2, phase_a_end_bar=6, phase_b_start_bar=12,
        base_len=18, is_inner_box=False, lps_offset=1, lps_length=4,
        lps_zone_type="INSIDE", atr_val=1.0,
    )

    assert out["phase_a_start_date"] == str(df.index[2])[:10]
    assert out["phase_a_end_date"] == str(df.index[6])[:10]
    assert out["phase_a_end_bar"] == 6
    assert out["phase_b_start_date"] == str(df.index[12])[:10]


def test_scope_phase_d_anchors_at_lps():
    df = _scope_df(30)
    out = scope_consolidation(
        df, bc_anchor_bar=2, phase_b_start_bar=5, base_len=25,
        is_inner_box=False, lps_offset=1, lps_length=4,
        lps_zone_type="INSIDE", atr_val=1.0,
    )
    # No spring -> Phase D anchors at the LPS: lps_start = 30 - 1 - 4 = 25.
    assert out["phase_d_start_bar"] == 25
    assert out["phase_d_start_date"] == str(df.index[25])[:10]


def test_scope_phase_d_can_use_support_test_cluster_hint():
    df = _scope_df(30)
    out = scope_consolidation(
        df, bc_anchor_bar=2, phase_b_start_bar=5, base_len=25,
        is_inner_box=False, lps_offset=1, lps_length=4,
        lps_zone_type="INSIDE", atr_val=1.0, support_test_start_bar=18,
    )
    assert out["has_mini_consolidation"] is False
    assert out["phase_d_start_bar"] == 18
    assert out["phase_d_start_date"] == str(df.index[18])[:10]


def test_scope_phase_d_can_use_v_tip_boundary():
    df = _scope_df(30)
    out = scope_consolidation(
        df, bc_anchor_bar=2, phase_b_start_bar=5, base_len=25,
        is_inner_box=False, lps_offset=1, lps_length=4,
        lps_zone_type="INSIDE", atr_val=1.0,
        support_test_start_bar=18, v_tip_bar=16,
    )
    assert out["has_mini_consolidation"] is False
    assert out["phase_d_start_bar"] == 16
    assert out["phase_d_start_date"] == str(df.index[16])[:10]


def test_scope_phase_c_recovery_floors_phase_d_search():
    df = _scope_df(30)
    out = scope_consolidation(
        df, bc_anchor_bar=2, phase_b_start_bar=5, base_len=25,
        is_inner_box=False, lps_offset=1, lps_length=4,
        lps_zone_type="INSIDE", atr_val=1.0,
        phase_c_recovery_bar=17, v_tip_bar=16, support_test_start_bar=20,
    )
    # Recovery (17) ends Phase C and FLOORS the search: the V-tip at 16 is before
    # the reclaim (ignored); the support test at 20 is after it and opens Phase D.
    assert out["has_mini_consolidation"] is False
    assert out["phase_d_start_bar"] == 20
    assert out["phase_d_start_date"] == str(df.index[20])[:10]


def test_scope_inner_after_recovery_opens_phase_d():
    df = _scope_df(30)
    out = scope_consolidation(
        df, bc_anchor_bar=2, phase_b_start_bar=5, base_len=25,
        is_inner_box=False, lps_offset=1, lps_length=4,
        lps_zone_type="INSIDE", atr_val=1.0,
        phase_d_start_bar=20, phase_c_recovery_bar=17,
    )
    # An inner mini-consolidation AFTER the reclaim is the right-side contraction
    # that opens Phase D (the LPS stays the gate underneath it).
    assert out["has_mini_consolidation"] is True
    assert out["phase_d_start_bar"] == 20
    assert out["phase_d_start_date"] == str(df.index[20])[:10]


def test_scope_inner_box_marks_mini_consolidation_and_d_start():
    df = _scope_df(30)
    out = scope_consolidation(
        df, bc_anchor_bar=2, phase_b_start_bar=5, base_len=10,
        is_inner_box=True, lps_offset=1, lps_length=4,
        lps_zone_type="INSIDE", atr_val=1.0,
    )
    # Active inner box: Phase D is the mini-consolidation itself -> box start.
    assert out["has_mini_consolidation"] is True
    assert out["phase_d_start_date"] == str(df.index[20])[:10]
    assert out["phase_d_start_bar"] == 20


def test_scope_parent_with_inner_phase_d_uses_explicit_start():
    df = _scope_df(30)
    out = scope_consolidation(
        df, bc_anchor_bar=2, phase_b_start_bar=5, base_len=25,
        is_inner_box=False, lps_offset=1, lps_length=4,
        lps_zone_type="INSIDE", atr_val=1.0, phase_d_start_bar=18,
    )
    assert out["has_mini_consolidation"] is True
    assert out["phase_d_start_bar"] == 18
    assert out["phase_d_start_date"] == str(df.index[18])[:10]
    assert out["phase_b_start_date"] == str(df.index[5])[:10]


def test_scope_spring_emits_phase_c_marker_at_lps_low():
    df = _scope_df(30)
    df.iloc[27, df.columns.get_loc("Low")] = 90.0  # the spring low inside [25:29]
    out = scope_consolidation(
        df, bc_anchor_bar=2, phase_b_start_bar=5, base_len=25,
        is_inner_box=False, lps_offset=1, lps_length=4,
        lps_zone_type="UNDERCUT_S", atr_val=2.0,
    )
    assert out["phase_c_event_date"] == str(df.index[27])[:10]
    # Bounding box: low = the spring dip (90.0), high = max High over [25:29).
    assert out["lps_zone_low"] == 90.0
    assert out["lps_zone_high"] == 101.0


def test_scope_degenerate_order_drops_lead_in_keeps_phase_d():
    df = _scope_df(30)
    # Climax AFTER body start is degenerate → drop A/B rather than invert.
    out = scope_consolidation(
        df, bc_anchor_bar=10, phase_b_start_bar=5, base_len=25,
        is_inner_box=False, lps_offset=1, lps_length=4,
        lps_zone_type="INSIDE", atr_val=1.0,
    )
    assert out["phase_a_start_date"] is None
    assert out["phase_b_start_date"] is None
    assert out["phase_d_start_date"] is not None  # Phase D still placed
    assert out["scope_confidence"] == 0.5         # only D (weighted 0.5)


def test_scope_degrades_when_no_lps_window():
    df = _scope_df(30)
    # offset past the frame → no usable LPS window; outer box → no Phase D.
    out = scope_consolidation(
        df, bc_anchor_bar=2, phase_b_start_bar=5, base_len=25,
        is_inner_box=False, lps_offset=40, lps_length=4,
        lps_zone_type="INSIDE", atr_val=1.0,
    )
    assert out["phase_d_start_date"] is None
    assert out["lps_zone_low"] is None
    assert out["phase_a_start_date"] == str(df.index[2])[:10]
    assert out["scope_confidence"] == 0.5  # A + B placed, D missing


def test_scope_empty_on_no_base():
    df = _scope_df(30)
    out = scope_consolidation(
        df, bc_anchor_bar=2, phase_b_start_bar=5, base_len=0,
        is_inner_box=False, lps_offset=1, lps_length=4,
        lps_zone_type="INSIDE", atr_val=1.0,
    )
    assert out["phase_a_start_date"] is None
    assert out["phase_d_start_date"] is None
    assert out["scope_confidence"] == 0.0


# ──────────────────────────────────────────────────────────────────
# Fidelity harness (summarize_fidelity): pure grading core — turns the
# human's hand-labels into a fidelity score. Unscored rows are ignored.
# ──────────────────────────────────────────────────────────────────
def test_fidelity_all_ok_is_full_score():
    rows = [
        {"ticker": "AAA", "phase_d_verdict": "ok", "lps_zone_verdict": "ok"},
        {"ticker": "BBB", "phase_d_verdict": "OK", "lps_zone_verdict": "ok"},
    ]
    s = summarize_fidelity(rows)
    assert s["n_scored"] == 2
    assert s["phase_d_ok_pct"] == 100.0
    assert s["lps_ok_pct"] == 100.0
    assert s["misreads"] == []


def test_fidelity_counts_misreads_and_ignores_unscored():
    rows = [
        {"ticker": "AAA", "phase_d_verdict": "ok", "lps_zone_verdict": "ok"},
        {"ticker": "BBB", "phase_d_verdict": "early", "lps_zone_verdict": "high"},
        {"ticker": "CCC", "phase_d_verdict": "late", "lps_zone_verdict": "ok"},
        {"ticker": "DDD", "phase_d_verdict": "", "lps_zone_verdict": ""},  # unscored → ignored
    ]
    s = summarize_fidelity(rows)
    assert s["n_total"] == 4
    assert s["n_scored"] == 3
    assert s["phase_d_ok"] == 1 and s["phase_d_early"] == 1 and s["phase_d_late"] == 1
    assert round(s["phase_d_ok_pct"], 1) == 33.3
    assert s["lps_breakdown"]["high"] == 1
    assert {m["ticker"] for m in s["misreads"]} == {"BBB", "CCC"}


def test_fidelity_day_error_median_from_dates():
    rows = [
        {"ticker": "AAA", "phase_d_verdict": "ok", "lps_zone_verdict": "ok",
         "engine_phase_d_date": "2026-06-01", "your_phase_d_date": "2026-06-04"},
        {"ticker": "BBB", "phase_d_verdict": "late", "lps_zone_verdict": "ok",
         "engine_phase_d_date": "2026-06-10", "your_phase_d_date": "2026-06-05"},
    ]
    s = summarize_fidelity(rows)
    # |+3| and |-5| → median 4.0
    assert s["median_day_error"] == 4.0


# ──────────────────────────────────────────────────────────────────
# Signal-edge analysis (analyze.signal_edge): pure Stage-1 classifier —
# flags each sub-score as beneficial / inert / harmful by its rank
# association with outcome. Read-only measurement; changes no weights.
# ──────────────────────────────────────────────────────────────────
def test_derive_outcomes_maps_barrier_label_to_win_binary():
    df = pd.DataFrame({"barrier_label": ["win", "loss", "timeout", None]})
    out = derive_outcomes(df)
    wins = out["barrier_win"].tolist()
    assert wins[0] == 1.0
    assert wins[1] == 0.0 and wins[2] == 0.0  # loss + timeout are non-wins
    assert pd.isna(wins[3])                    # unlabelled stays NaN


def test_safe_rank_corr_is_monotonic_not_linear():
    # A monotonic but non-linear relation → Spearman = 1.0 (Pearson would be <1).
    x = pd.Series([1, 2, 3, 4, 5, 6, 7, 8])
    y = pd.Series([1, 4, 9, 16, 25, 36, 49, 64])
    assert safe_rank_corr(x, y) == 1.0
    assert safe_rank_corr(pd.Series([1, 1, 1, 1]), pd.Series([1, 2, 3, 4])) is None  # no variance


def test_score_traversal_quality_rewards_two_sided_over_dead_space():
    """The traversal-quality term (which replaced the rail-blind oscillation term)
    must rank a genuinely two-sided box above a dead-space one."""
    from core.scoring.scoring import score_setup

    base = pd.DataFrame({"High": [11.0, 11.0], "Low": [10.0, 10.0],
                         "Close": [10.5, 10.5], "Volume": [1.0, 1.0]})
    common = dict(box_width=0.1, r_touches=4, s_touches=4, res_avg=11.0, sup_avg=10.0,
                  base_df=base, atr_ratio=0.5, tightness_ratio=0.5, vol_contraction=0.5,
                  base_len=40, yearly_return=0.0)

    clean = score_setup(**common, traversal_density=0.5, max_swing_frac=1.0, dwell_asymmetry=0.1)
    dead = score_setup(**common, traversal_density=0.1, max_swing_frac=1.5, dwell_asymmetry=0.5)

    assert clean["traversal_quality"] > 8.0        # clean two-sided box, near the 10-pt cap
    assert dead["traversal_quality"] == 0.0         # dead-space reward fully eaten by the dock
    assert clean["traversal_quality"] > dead["traversal_quality"]
    assert clean["total"] > dead["total"]
    assert "oscillation" not in clean  # retired sub-score is fully gone from the payload


def test_base_age_dead_space_dock_spares_tight_boxes():
    """base_age 'cause' credit is docked for WIDE low-density (dead-space) bases,
    but NOT for ultra-tight ones (whose low density is a small-box / spring artifact)."""
    from core.scoring.scoring import score_setup

    base = pd.DataFrame({"High": [11.0, 11.0], "Low": [10.0, 10.0],
                         "Close": [10.5, 10.5], "Volume": [1.0, 1.0]})
    common = dict(r_touches=4, s_touches=4, res_avg=11.0, sup_avg=10.0, base_df=base,
                  atr_ratio=0.5, tightness_ratio=0.5, vol_contraction=0.5,
                  base_len=90, yearly_return=0.0, traversal_density=0.15)

    wide = score_setup(box_width=0.12, **common)    # wide + low density -> docked
    tight = score_setup(box_width=0.02, **common)   # ultra-tight -> exempt (PRA-like)
    clean_wide = score_setup(box_width=0.12, **{**common, "traversal_density": 0.40})

    assert tight["base_age"] > wide["base_age"] * 1.5     # tight keeps full credit
    assert clean_wide["base_age"] == tight["base_age"]    # density past full-credit -> no dock


def test_traversal_overshoot_exempt_for_tight_box_and_spring():
    """The max_swing_frac overshoot penalty must not fire on a tight box (overshoot
    is inevitable when the box is tiny, e.g. PRA) or a confirmed spring (the undercut
    is a bullish leg, not dead space)."""
    from core.scoring.scoring import score_setup

    base = pd.DataFrame({"High": [11.0, 11.0], "Low": [10.0, 10.0],
                         "Close": [10.5, 10.5], "Volume": [1.0, 1.0]})
    common = dict(r_touches=4, s_touches=4, res_avg=11.0, sup_avg=10.0, base_df=base,
                  atr_ratio=0.5, tightness_ratio=0.5, vol_contraction=0.5,
                  base_len=40, yearly_return=0.0, traversal_density=0.3,
                  max_swing_frac=2.5, dwell_asymmetry=0.1)

    wide = score_setup(box_width=0.12, **common)                     # wide, no spring -> overshoot docks
    tight = score_setup(box_width=0.02, **common)                    # tight box -> overshoot exempt
    spring = score_setup(box_width=0.12, has_spring=True, **common)   # spring -> overshoot exempt

    assert tight["traversal_quality"] > wide["traversal_quality"]
    assert spring["traversal_quality"] > wide["traversal_quality"]


def test_descent_tail_gate_is_width_aware_and_guarded(monkeypatch):
    """The descent-tail gate drops a WIDE box whose support was abandoned early
    (last_support_frac <= LSF_MAX) into dead space (coil_floor_pos >= CFP_MIN),
    but spares tight boxes (the EQIX exemption) and is None-safe / flag-guarded."""
    from core.structure import descent_tail_rejects

    monkeypatch.setattr(settings, "DESCENT_TAIL_GATE_ENABLED", True)
    monkeypatch.setattr(settings, "DESCENT_TAIL_LSF_MAX", 0.40)
    monkeypatch.setattr(settings, "DESCENT_TAIL_CFP_MIN", 0.20)
    monkeypatch.setattr(settings, "BASE_AGE_DEADSPACE_WIDTH", 0.06)

    # Wide box, support left early into a dead band above it -> a dead tail.
    assert descent_tail_rejects(0.35, 0.30, 0.10) is True
    # Tight box (<= BASE_AGE_DEADSPACE_WIDTH) is EXEMPT (saves EQIX, w 0.038).
    assert descent_tail_rejects(0.35, 0.30, 0.04) is False
    # Support held late (high last_support_frac) -> not a dead tail.
    assert descent_tail_rejects(0.80, 0.30, 0.10) is False
    # No dead band under the late coil (low coil_floor_pos) -> not a dead tail.
    assert descent_tail_rejects(0.35, 0.10, 0.10) is False
    # None-safe (degenerate measure_traversal).
    assert descent_tail_rejects(None, 0.30, 0.10) is False
    assert descent_tail_rejects(0.35, None, 0.10) is False
    # Flag-guarded.
    monkeypatch.setattr(settings, "DESCENT_TAIL_GATE_ENABLED", False)
    assert descent_tail_rejects(0.35, 0.30, 0.10) is False


def test_eval_twins_share_the_folded_core():
    """The live (``_evaluate_ticker``) and seed (``_evaluate_at_date``) paths must
    BOTH route through the shared eval helpers, so the structural logic (LPS
    selection, descent-tail gate, scorer args) can never silently diverge between
    them — the drift that let the descent-tail gate land in one path only and that
    the seed-recall guard exists to measure. If you re-inline one of these in a
    single path, fold it back into the shared helper instead."""
    import inspect

    from core.archive.seed import _evaluate_at_date
    from core.pipeline.evaluation import _evaluate_ticker

    live_src = inspect.getsource(_evaluate_ticker)
    seed_src = inspect.getsource(_evaluate_at_date)
    for helper in ("select_active_lps", "descent_tail_drops", "score_traversal_args"):
        assert helper in live_src, f"_evaluate_ticker no longer routes through {helper}"
        assert helper in seed_src, f"_evaluate_at_date no longer routes through {helper}"


def test_score_traversal_args_maps_measure_facts():
    from core.pipeline.evaluation import score_traversal_args

    args = score_traversal_args(
        {"n_full_traversals": 3, "n_swings": 6, "max_swing_frac": 1.4},
        {"upper_dwell": 0.3, "lower_dwell": 0.5},
        {"bin_c_present": 1},
    )
    assert args["traversal_density"] == 0.5
    assert args["max_swing_frac"] == 1.4
    assert abs(args["dwell_asymmetry"] - 0.2) < 1e-9
    assert args["has_spring"] is True

    # Degenerate guards: zero swings -> density 0; None max_swing_frac -> 1.0; no spring.
    args2 = score_traversal_args(
        {"n_full_traversals": 0, "n_swings": 0, "max_swing_frac": None},
        {"upper_dwell": 0.4, "lower_dwell": 0.4},
        {},
    )
    assert args2["traversal_density"] == 0.0
    assert args2["max_swing_frac"] == 1.0
    assert args2["dwell_asymmetry"] == 0.0
    assert args2["has_spring"] is False


def test_select_active_lps_prefers_inner_then_parent(monkeypatch):
    """The folded inner-first-then-parent rule: take the inner box's LPS when it
    yields one (closer trigger/stop), else the parent's; lps_context follows."""
    from core.pipeline import evaluation

    df = _lps_behavior_frame(
        highs=[110.0] * 30, lows=[100.0] * 30, closes=[105.0] * 30,
    )
    latest = df.iloc[-1]
    inner = {"base_len": 15, "start_bar": 10, "r_anchor_bar": 12,
             "s_anchor_bar": 11, "S": 101.0, "R": 109.0}
    parent = (90.0, 120.0, 5.0, 30, 5)  # (S, R, range_threshold, base_len, swing)

    def fake(which_for_inner):
        def _f(d, l, S, R, atr, rt, bl, sw):
            hit = S == inner["S"] if which_for_inner else S == parent[0]
            return {"setup_type": "LPS", "_who": "inner" if S == inner["S"] else "parent"} if hit else None
        return _f

    # Inner fires -> inner wins; context switches to the inner rails.
    monkeypatch.setattr(evaluation, "detect_lps", fake(which_for_inner=True))
    res, in_inner, ctx = evaluation.select_active_lps(df, latest, parent, inner, atr=2.0)
    assert in_inner is True and res["_who"] == "inner"
    assert ctx[0] == inner["S"] and ctx[1] == inner["R"]

    # Inner returns None -> fall back to the parent; context stays parent.
    monkeypatch.setattr(evaluation, "detect_lps", fake(which_for_inner=False))
    res2, in_inner2, ctx2 = evaluation.select_active_lps(df, latest, parent, inner, atr=2.0)
    assert in_inner2 is False and res2["_who"] == "parent"
    assert ctx2 == parent

    # No inner box at all -> parent path.
    res3, in_inner3, ctx3 = evaluation.select_active_lps(df, latest, parent, None, atr=2.0)
    assert in_inner3 is False and res3["_who"] == "parent"


def test_signal_edge_classifies_harmful_inert_beneficial():
    n = 40
    win = [1.0, 0.0] * (n // 2)                      # alternating outcome
    df = pd.DataFrame({
        "barrier_win": win,
        "score_box_tightness": win,                  # perfectly +assoc → beneficial
        "score_touch_density": [1.0 - w for w in win],  # perfectly -assoc → harmful
        "score_base_age": list(range(n)),            # monotonic vs alternating → ~0 → inert
    })
    out = signal_edge(df, targets=["barrier_win"], min_n=8)
    assert out["primary_target"] == "barrier_win"
    verdicts = {r["feature"]: r["verdict"] for r in out["rows"]}
    assert verdicts["score_box_tightness"] == "beneficial"
    assert verdicts["score_touch_density"] == "harmful"
    assert verdicts["score_base_age"] == "inert"
    # Most-harmful sorts first.
    assert out["rows"][0]["feature"] == "score_touch_density"


def test_signal_edge_no_outcome_column_returns_no_primary():
    df = pd.DataFrame({"score_box_tightness": [1, 2, 3, 4, 5, 6, 7, 8]})
    out = signal_edge(df)
    assert out["primary_target"] is None
    assert out["rows"] == [] or all(r["verdict"] == "unknown" for r in out["rows"])


def test_durable_vs_cash_grab_win_classification():
    # Four labelled setups. days_to_15pct = first profit-target bar; days_to_stop
    # = first stop touch. cash_grab_max_bars defaults to 5.
    df = pd.DataFrame({
        "barrier_label":  ["win",  "win",  "win",  "loss"],
        "days_to_2_5r":   [None,   None,   None,   None],
        "days_to_15pct":  [3,      4,      10,     None],
        "days_to_stop":   [None,   6,      30,     2],
    })
    out = derive_outcomes(df)
    wq = out["win_quality"].tolist()
    # row0: win, never round-trips      -> durable
    # row1: target bar 4, stop bar 6 -> gap 2 <= 5 -> cash_grab
    # row2: target bar 10, stop bar 30 -> gap 20 > 5 -> durable
    # row3: loss -> not a win -> None
    assert wq[0] == "durable"
    assert wq[1] == "cash_grab"
    assert wq[2] == "durable"
    assert wq[3] is None
    # durable_win binary: durable=1; cash-grab/loss=0; (all labelled here)
    assert out["durable_win"].tolist() == [1.0, 0.0, 1.0, 0.0]
    # breathing-room window recorded for any win that round-trips to the stop,
    # whether fast (cash-grab) or slow (durable): row1 gap=2, row2 gap=20.
    gaps = out["bars_target_to_stop"].tolist()
    assert gaps[1] == 2.0
    assert gaps[2] == 20.0
    assert pd.isna(gaps[0]) and pd.isna(gaps[3])  # no stop touch / not a win


def test_signal_edge_withholds_verdicts_on_winners_only_sample():
    # 30 labelled rows but only 1 loser → binary minority class = 1 < 8 →
    # the tool must refuse to trust verdicts (winners-only mirage guard).
    n = 30
    win = [1.0] * (n - 1) + [0.0]
    df = pd.DataFrame({
        "durable_win": win,
        "score_box_tightness": list(range(n)),
    })
    out = signal_edge(df, targets=["durable_win"], min_n=8)
    assert out["primary_target"] == "durable_win"
    assert out["is_binary"] is True
    assert out["n_minority"] == 1
    assert out["verdicts_trustworthy"] is False


def test_signal_edge_trusts_verdicts_with_balanced_adequate_sample():
    # 40 rows, 20 wins / 20 losses, well above the floors → verdicts trusted.
    n = 40
    win = [1.0, 0.0] * (n // 2)
    df = pd.DataFrame({
        "durable_win": win,
        "score_box_tightness": win,  # perfectly +assoc
    })
    out = signal_edge(df, targets=["durable_win"], min_n=8)
    assert out["n_minority"] == 20
    assert out["verdicts_trustworthy"] is True


def test_durable_win_degrades_to_barrier_win_without_timing_columns():
    # No days_to_* columns (outcomes not backfilled) -> every win counts durable.
    df = pd.DataFrame({"barrier_label": ["win", "loss", "timeout", "win"]})
    out = derive_outcomes(df)
    assert out["durable_win"].tolist() == [1.0, 0.0, 0.0, 1.0]
    assert out["barrier_win"].tolist() == [1.0, 0.0, 0.0, 1.0]
