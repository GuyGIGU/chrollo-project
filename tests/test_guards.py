import math
import json
from datetime import datetime, timezone
import sys
from pathlib import Path
from zoneinfo import ZoneInfo

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
from tools.shadow_diff import canonical_fields
from tools.shadow_diff import diff_against_baseline as shadow_diff_against_baseline


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


# ──────────────────────────────────────────────────────────────────
# Look-ahead bias guard (core.archive.forward_returns): no forward-return /
# MFE / trigger field may read a bar AT or BEFORE the scan timestamp. The
# production slice is ``fwd_df = df[df.index > scan_ts]`` (strictly after the
# scan bar). This pins that boundary: an extreme spike planted on the scan bar
# and on every earlier bar must never leak into any forward outcome.
# ──────────────────────────────────────────────────────────────────
def test_forward_returns_never_read_a_bar_at_or_before_scan():
    scan_pos = 10
    # Enough forward bars (>= 60) that a clean forward tape yields a real
    # "timeout" label rather than the still-maturing None.
    n = scan_pos + FORWARD_RETURN_HORIZON_BARS + 5
    idx = pd.date_range("2026-01-02", periods=n, freq="B")
    scan_ts = idx[scan_pos]

    # Flat tape everywhere EXCEPT a giant spike on the scan bar and all bars
    # before it. If any field read index <= scan_ts, the trigger/MFE would catch
    # the spike; the strict ``> scan_ts`` slice must keep it invisible.
    highs = [9999.0] * (scan_pos + 1) + [101.0] * (n - scan_pos - 1)
    lows = [0.01] * (scan_pos + 1) + [99.0] * (n - scan_pos - 1)
    closes = [9999.0] * (scan_pos + 1) + [100.0] * (n - scan_pos - 1)
    df = pd.DataFrame({
        "Open": closes,
        "High": highs,
        "Low": lows,
        "Close": closes,
        "Volume": [1000.0] * n,
    }, index=idx)

    # The exact production boundary from update_forward_returns().
    fwd_df = df[df.index > scan_ts]
    assert (fwd_df.index > scan_ts).all()
    assert scan_ts not in fwd_df.index

    res = _compute_returns(
        fwd_df, scan_close=100.0, trigger_price=120.0, s_level=95.0, vol_50_at_scan=1000.0,
    )

    # Forward window saw only the flat 101/99 tape: no spike leaked in.
    assert res["fwd_return_20d"] == 0.0          # 100 -> 100 flat
    assert res["mfe_20d"] == pytest.approx(0.01)  # (101 - 100) / 100
    assert res["mae_20d"] == pytest.approx(-0.01)  # (99 - 100) / 100
    assert res["triggered"] == 0                  # 120 trigger never hit by the 101 cap
    assert res["barrier_label"] == "timeout"      # neither target nor stop reached forward


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
