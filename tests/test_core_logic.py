import math
import sys
from pathlib import Path

import pandas as pd
import pytest
from fastapi import HTTPException

ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = ROOT / "webapp" / "backend"
sys.path.insert(0, str(ROOT))
sys.path.insert(1, str(BACKEND_DIR))

from core.archive.forward_returns import compute_barrier_events
from core.archive.seed_recall import diff_against_baseline as seed_diff_against_baseline
from core.structure.consolidation import measure_bar_compression
from core.structure.lps import detect_lps
from tools.shadow_diff import canonical_fields
from tools.shadow_diff import diff_against_baseline as shadow_diff_against_baseline
from webapp.backend.routers.market_data import _clean_symbol, _is_number
from webapp.backend.services.portfolio_snapshot import (
    flatten_summary,
    has_portfolio_data,
    with_cached_snapshot,
)


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
        base_range_threshold=10,
        base_len=20,
        swing_complete_idx=2,
    )

    assert result["trigger_price"] == 107


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
# Seed-recall baseline guard (core.archive.seed_recall)
# ──────────────────────────────────────────────────────────────────
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
