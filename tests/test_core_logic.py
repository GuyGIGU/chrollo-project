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
from core.archive.analyze import derive_outcomes, safe_rank_corr, signal_edge
from core.structure.scope import scope_consolidation
from tools.fidelity_harness import summarize_fidelity
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


def test_scope_phase_d_anchors_on_final_third_of_base():
    df = _scope_df(30)
    out = scope_consolidation(
        df, bc_anchor_bar=2, phase_b_start_bar=5, base_len=25,
        is_inner_box=False, lps_offset=1, lps_length=4,
        lps_zone_type="INSIDE", atr_val=1.0,
    )
    # box_start = 30 - 25 = 5; final third = 5 + (2*25)//3 = 5 + 16 = 21.
    assert out["phase_d_start_bar"] == 21
    assert out["phase_d_start_date"] == str(df.index[21])[:10]


def test_scope_inner_box_marks_mini_consolidation_and_d_start():
    df = _scope_df(30)
    out = scope_consolidation(
        df, bc_anchor_bar=2, phase_b_start_bar=5, base_len=10,
        is_inner_box=True, lps_offset=1, lps_length=4,
        lps_zone_type="INSIDE", atr_val=1.0,
    )
    # Inner box: Phase D is the mini-consolidation itself → starts at n-base_len.
    assert out["has_mini_consolidation"] is True
    assert out["phase_d_start_date"] == str(df.index[20])[:10]
    assert out["phase_d_start_bar"] == 20


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


def test_scope_degenerate_order_drops_lead_in_keeps_launchpad():
    df = _scope_df(30)
    # Climax AFTER body start is degenerate → drop A/B rather than invert.
    out = scope_consolidation(
        df, bc_anchor_bar=10, phase_b_start_bar=5, base_len=25,
        is_inner_box=False, lps_offset=1, lps_length=4,
        lps_zone_type="INSIDE", atr_val=1.0,
    )
    assert out["phase_a_start_date"] is None
    assert out["phase_b_start_date"] is None
    assert out["phase_d_start_date"] is not None  # launchpad still placed
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


def test_signal_edge_classifies_harmful_inert_beneficial():
    n = 40
    win = [1.0, 0.0] * (n // 2)                      # alternating outcome
    df = pd.DataFrame({
        "barrier_win": win,
        "score_box_tightness": win,                  # perfectly +assoc → beneficial
        "score_touch_density": [1.0 - w for w in win],  # perfectly -assoc → harmful
        "score_oscillation": list(range(n)),         # monotonic vs alternating → ~0 → inert
    })
    out = signal_edge(df, targets=["barrier_win"], min_n=8)
    assert out["primary_target"] == "barrier_win"
    verdicts = {r["feature"]: r["verdict"] for r in out["rows"]}
    assert verdicts["score_box_tightness"] == "beneficial"
    assert verdicts["score_touch_density"] == "harmful"
    assert verdicts["score_oscillation"] == "inert"
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


def test_durable_win_degrades_to_barrier_win_without_timing_columns():
    # No days_to_* columns (outcomes not backfilled) -> every win counts durable.
    df = pd.DataFrame({"barrier_label": ["win", "loss", "timeout", "win"]})
    out = derive_outcomes(df)
    assert out["durable_win"].tolist() == [1.0, 0.0, 0.0, 1.0]
    assert out["barrier_win"].tolist() == [1.0, 0.0, 0.0, 1.0]
