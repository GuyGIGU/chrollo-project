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

from engine_alpha.structure.indicators import trend_template
from core.archive.analyze import derive_outcomes, safe_rank_corr, signal_edge


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
    from engine_alpha.scoring.scoring import score_setup

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
    from engine_alpha.scoring.scoring import score_setup

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


def test_adr_relative_box_tightness_demotes_flat_low_adr_drift(monkeypatch):
    """With TIGHTNESS_ADR_AWARE on, box tightness is measured in ADR units: the SAME
    absolute box width is a tight coil on a real mover but a wide drift on a flat
    low-ADR name (the GBTG case). With the flag off, ADR is ignored and both score
    the identical absolute tightness (the shadow-preserving default)."""
    from engine_alpha.scoring.scoring import score_setup

    base = pd.DataFrame({"High": [11.0, 11.0], "Low": [10.0, 10.0],
                         "Close": [10.5, 10.5], "Volume": [1.0, 1.0]})
    common = dict(r_touches=4, s_touches=4, res_avg=11.0, sup_avg=10.0, base_df=base,
                  atr_ratio=0.5, tightness_ratio=0.5, vol_contraction=0.5,
                  base_len=40, yearly_return=0.0, traversal_density=0.3)
    # Same 4% absolute box: the mover (5% ADR) is 0.8 ADR wide; the flat drift
    # (0.5% ADR) is 8 ADR wide -> past the 4.5-ADR ceiling.
    mover = dict(box_width=0.04, adr_value=5.0)
    flat = dict(box_width=0.04, adr_value=0.5)

    # Flag OFF: ADR ignored -> identical absolute tightness (byte-preserving default).
    monkeypatch.setattr(settings, "TIGHTNESS_ADR_AWARE", False, raising=False)
    assert (score_setup(**common, **mover)["box_tightness"]
            == score_setup(**common, **flat)["box_tightness"])

    # Flag ON: the flat low-ADR drift collapses to zero; the mover keeps strong tightness.
    monkeypatch.setattr(settings, "TIGHTNESS_ADR_AWARE", True, raising=False)
    monkeypatch.setattr(settings, "MAX_BOX_WIDTH_ADR", 4.5, raising=False)
    on_mover = score_setup(**common, **mover)["box_tightness"]
    on_flat = score_setup(**common, **flat)["box_tightness"]
    assert on_mover > 15.0      # 0.8 ADR wide -> near the 22-pt cap
    assert on_flat == 0.0       # 8 ADR wide (> 4.5) -> zero tightness credit
    assert on_mover > on_flat


def test_traversal_overshoot_exempt_for_tight_box_and_spring():
    """The max_swing_frac overshoot penalty must not fire on a tight box (overshoot
    is inevitable when the box is tiny, e.g. PRA) or a confirmed spring (the undercut
    is a bullish leg, not dead space)."""
    from engine_alpha.scoring.scoring import score_setup

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
    (last_support_time_pos <= LSF_MAX) into dead space (low_position_in_box >= CFP_MIN),
    but spares tight boxes (the EQIX exemption) and is None-safe. Unconditional
    since the 2026-07-18 fold (formerly behind DESCENT_TAIL_GATE_ENABLED)."""
    from engine_alpha.structure import descent_tail_rejects

    monkeypatch.setattr(settings, "DESCENT_TAIL_LSF_MAX", 0.40)
    monkeypatch.setattr(settings, "DESCENT_TAIL_CFP_MIN", 0.20)
    monkeypatch.setattr(settings, "BASE_AGE_DEADSPACE_WIDTH", 0.06)

    # Wide box, support left early into a dead band above it -> a dead tail.
    assert descent_tail_rejects(0.35, 0.30, 0.10) is True
    # Tight box (<= BASE_AGE_DEADSPACE_WIDTH) is EXEMPT (saves EQIX, w 0.038).
    assert descent_tail_rejects(0.35, 0.30, 0.04) is False
    # Support held late (high last_support_time_pos) -> not a dead tail.
    assert descent_tail_rejects(0.80, 0.30, 0.10) is False
    # No dead band under the late coil (low low_position_in_box) -> not a dead tail.
    assert descent_tail_rejects(0.35, 0.10, 0.10) is False
    # None-safe (degenerate measure_equilibrium).
    assert descent_tail_rejects(None, 0.30, 0.10) is False
    assert descent_tail_rejects(0.35, None, 0.10) is False


def test_eval_twins_share_the_folded_core():
    """The live (``_evaluate_ticker``) and seed (``_evaluate_at_date``) paths must BOTH
    route through the SINGLE shared numeric chain (``_run_eval_chain``), so the
    structural logic (LPS selection, descent-tail gate, scorer args) can never silently
    diverge between them. "Replay at T == live at T" is true by construction: both call
    the same chain on a frame; seed only differs by working on a pre-sliced frame and
    re-keying the canonical result through ``seed_row_from_result``. If you re-inline the
    orchestration in one path, fold it back onto ``_run_eval_chain`` instead."""
    import ast
    import inspect
    import textwrap

    from core.archive.seed import _evaluate_at_date
    from engine_alpha import evaluation as evaluation_module
    from engine_alpha.evaluation import (
        _evaluate_ticker,
        _run_eval_chain,
        _run_guarded_chain,
        evaluate_ticker_with_near_miss,
    )

    def called_names(fn):
        tree = ast.parse(textwrap.dedent(inspect.getsource(fn)))
        calls = set()
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            if isinstance(node.func, ast.Name):
                calls.add(node.func.id)
            elif isinstance(node.func, ast.Attribute):
                calls.add(node.func.attr)
        return calls

    # Every entry point delegates to the one shared chain — the live path and
    # its lane-carrying twin through the ONE guarded wrapper (near-miss lane
    # Task 8 fold), the seed path directly.
    assert "_run_guarded_chain" in called_names(_evaluate_ticker)
    assert "_run_guarded_chain" in called_names(evaluate_ticker_with_near_miss)
    assert "_run_eval_chain" in called_names(_run_guarded_chain)
    seed_calls = called_names(_evaluate_at_date)
    assert "_run_eval_chain" in seed_calls, "_evaluate_at_date no longer routes through the shared chain"
    assert "seed_row_from_result" in seed_calls, "_evaluate_at_date must re-key via the adapter"

    # The shared chain routes through the structural helpers (the real anti-drift guard).
    chain_calls = called_names(_run_eval_chain)
    assert "_resolve_structure_context" in chain_calls
    assert "_resolve_lps_context" in chain_calls
    assert "descent_tail_drops" in chain_calls
    assert "_score_eval_context" in chain_calls

    # Deeper folds preserved: the LPS election happens ONCE (in the walk);
    # _resolve_lps_context consumes the elected brick, never re-detects.
    assert "_lps_result_from_brick" in called_names(evaluation_module._resolve_lps_context)
    assert "detect_lps" not in called_names(evaluation_module._resolve_lps_context)
    assert "score_equilibrium_args" in called_names(evaluation_module._score_eval_context)


def test_score_equilibrium_args_maps_measure_facts():
    from engine_alpha.evaluation import score_equilibrium_args

    args = score_equilibrium_args(
        {"n_full_traversals": 3, "n_swings": 6, "max_swing_frac": 1.4},
        {"upper_dwell": 0.3, "lower_dwell": 0.5},
        {"bin_c_present": 1},
    )
    assert args["traversal_density"] == 0.5
    assert args["max_swing_frac"] == 1.4
    assert abs(args["dwell_asymmetry"] - 0.2) < 1e-9
    assert args["has_spring"] is True

    # Degenerate guards: zero swings -> density 0; None max_swing_frac -> 1.0; no spring.
    args2 = score_equilibrium_args(
        {"n_full_traversals": 0, "n_swings": 0, "max_swing_frac": None},
        {"upper_dwell": 0.4, "lower_dwell": 0.4},
        {},
    )
    assert args2["traversal_density"] == 0.0
    assert args2["max_swing_frac"] == 1.0
    assert args2["dwell_asymmetry"] == 0.0
    assert args2["has_spring"] is False


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


# ──────────────────────────────────────────────────────────────────
# Tier boundaries + individual scorer contributions (D7 backfill).
# These pin the score->tier mapping and the breadth / touch-density
# sub-scores against the live settings thresholds, so a calibration
# change shows up as an intentional test edit rather than silent drift.
# ──────────────────────────────────────────────────────────────────
def _score_base():
    return pd.DataFrame({"High": [11.0, 11.0], "Low": [10.0, 10.0],
                         "Close": [10.5, 10.5], "Volume": [1.0, 1.0]})


def _score_common(**overrides):
    common = dict(box_width=0.1, r_touches=0, s_touches=0, res_avg=11.0, sup_avg=10.0,
                  base_df=_score_base(), atr_ratio=0.5, tightness_ratio=0.5,
                  vol_contraction=0.5, base_len=40, yearly_return=0.0)
    common.update(overrides)
    return common


def test_calculate_tier_maps_each_band_at_its_threshold():
    from engine_alpha.scoring.scoring import calculate_tier

    # Exactly at each threshold lands in that tier; one point below drops a band.
    assert calculate_tier(settings.TIER_S) == "S"
    assert calculate_tier(settings.TIER_A) == "A"
    assert calculate_tier(settings.TIER_S - 1) == "A"
    assert calculate_tier(settings.TIER_B) == "B"
    assert calculate_tier(settings.TIER_A - 1) == "B"
    assert calculate_tier(settings.TIER_C) == "C"
    assert calculate_tier(settings.TIER_B - 1) == "C"
    assert calculate_tier(settings.TIER_C - 1) == "D"
    assert calculate_tier(0) == "D"


def test_calculate_tier_width_cap_demotes_wide_s_to_a():
    from engine_alpha.scoring.scoring import calculate_tier

    high = settings.TIER_S + 10
    # A tight enough box keeps S; a box wider than the S cap is demoted to A,
    # however high the score. No width supplied -> cap not applied.
    assert calculate_tier(high, box_width=settings.S_MAX_BOX_WIDTH) == "S"
    assert calculate_tier(high, box_width=settings.S_MAX_BOX_WIDTH + 0.01) == "A"
    assert calculate_tier(high) == "S"


def test_breadth_bonus_ramps_between_zero_and_full_thresholds():
    from engine_alpha.scoring.scoring import score_setup

    # Below the zero point -> no breadth credit; None (no breadth measured) -> 0.
    assert score_setup(**_score_common(breadth_pct=settings.BREADTH_ZERO_PCT))["breadth_bonus"] == 0.0
    assert score_setup(**_score_common(breadth_pct=None))["breadth_bonus"] == 0.0
    # At/above the full point -> the full SCORE_BREADTH_BONUS cap.
    full = score_setup(**_score_common(breadth_pct=settings.BREADTH_FULL_PCT))["breadth_bonus"]
    assert full == round(float(settings.SCORE_BREADTH_BONUS), 2)
    # The midpoint earns roughly half the cap and strictly between the two ends.
    mid_pct = (settings.BREADTH_ZERO_PCT + settings.BREADTH_FULL_PCT) / 2
    mid = score_setup(**_score_common(breadth_pct=mid_pct))["breadth_bonus"]
    assert 0.0 < mid < full
    assert mid == pytest.approx(settings.SCORE_BREADTH_BONUS / 2, abs=0.05)


def test_ramp_zero_divisor_guard_returns_neutral():
    # F5: a degenerate/inverted band (a misconfigured operator knob where CLEAN and
    # MESSY collapse or cross) returns the polarity-safe neutral 0.0 instead of
    # dividing by zero. A normal band (full_at > zero_at) is unaffected — the guard
    # is dead code for every shipped anchor, so no live bonus moves.
    from engine_alpha.scoring.scoring import _ramp
    assert _ramp(0.5, 0.4, 0.4, 1.0) == 0.0      # full_at == zero_at (collapsed)
    assert _ramp(0.5, 0.6, 0.4, 1.0) == 0.0      # full_at < zero_at (inverted)
    assert _ramp(1.0, 0.4, 0.4, 1.0) == 0.0      # value >> band, guard first -> neutral, no crash
    assert _ramp(None, 0.4, 0.4, 1.0) == 0.0     # None + degenerate: guard is BEFORE the None check
    # A well-formed band still ramps exactly as before.
    assert _ramp(0.30, 0.30, 0.60, 1.0) == 0.0   # at zero_at
    assert _ramp(0.60, 0.30, 0.60, 1.0) == 1.0   # at full_at (cap)
    assert _ramp(0.45, 0.30, 0.60, 1.0) == pytest.approx(0.5)   # midpoint


def test_touch_density_awards_bonus_only_when_touch_floors_met():
    from engine_alpha.scoring.scoring import score_setup

    # Sparse touches: base density only, no bonus.
    sparse = score_setup(**_score_common(r_touches=1, s_touches=1))["touch_density"]
    # >= TOUCH_BONUS_INDIVIDUAL on EACH side fires the bonus.
    each = score_setup(**_score_common(r_touches=settings.TOUCH_BONUS_INDIVIDUAL,
                                       s_touches=settings.TOUCH_BONUS_INDIVIDUAL))["touch_density"]
    # >= TOUCH_BONUS_TOTAL overall (lopsided) also fires it.
    total = score_setup(**_score_common(r_touches=settings.TOUCH_BONUS_TOTAL, s_touches=0))["touch_density"]
    # Just under both floors: total = TOTAL-1 and one side under INDIVIDUAL -> no bonus.
    near = score_setup(**_score_common(r_touches=settings.TOUCH_BONUS_TOTAL - 1, s_touches=0))["touch_density"]

    assert each >= sparse + settings.TOUCH_BONUS_POINTS
    assert total >= settings.TOUCH_BONUS_POINTS
    assert near < total
    # The whole term is capped at SCORE_TOUCH_DENSITY (15 base + 10 bonus).
    saturated = score_setup(**_score_common(r_touches=20, s_touches=20))["touch_density"]
    assert saturated == round(float(settings.SCORE_TOUCH_DENSITY), 2)


def test_box_tightness_contribution_is_capped_and_rewards_tighter_boxes():
    from engine_alpha.scoring.scoring import score_setup

    tight = score_setup(**_score_common(box_width=0.02))["box_tightness"]
    wide = score_setup(**_score_common(box_width=settings.MAX_BOX_WIDTH))["box_tightness"]
    assert tight > wide
    assert wide == 0.0  # a box at the absolute width ceiling earns no tightness credit
    assert tight <= round(float(settings.SCORE_BOX_TIGHTNESS), 2)


_CLEAN_TEXTURE = {"median_spread_pct_box": 0.30, "median_spread_atr": 0.65,
                  "tight_bar_pct": 0.80, "p80_spread_atr": 1.0}
_MESSY_TEXTURE = {"median_spread_pct_box": 0.60, "median_spread_atr": 1.40,
                  "tight_bar_pct": 0.25, "p80_spread_atr": 1.6}
_EMPTY_TEXTURE = {"median_spread_atr": None, "p80_spread_atr": None,
                  "median_spread_pct_box": None, "tight_bar_pct": 0.0}


def test_candle_readability_neutral_on_missing_metrics():
    from engine_alpha.scoring.scoring import _candle_readability

    # No dict, and the degenerate-base empty dict (spread ratios None), both -> 1.0
    # so absent texture data never silently demotes a setup.
    assert _candle_readability(None) == 1.0
    assert _candle_readability({}) == 1.0
    assert _candle_readability(_EMPTY_TEXTURE) == 1.0


def test_candle_readability_preserves_clean_discounts_messy():
    from engine_alpha.scoring.scoring import _candle_readability

    clean = _candle_readability(_CLEAN_TEXTURE)
    messy = _candle_readability(_MESSY_TEXTURE)
    assert clean == pytest.approx(1.0)               # quiet bars -> full credit
    assert settings.CANDLE_GRADE_FLOOR <= messy < clean   # choppy bars discounted, bounded by floor
    assert messy == pytest.approx(settings.CANDLE_GRADE_FLOOR)


def test_candle_spread_discounts_messy_preserves_clean():
    # The readability multiplier is unconditional engine behavior (folded
    # 2026-07-18; formerly behind CANDLE_SPREAD_AWARE, live since 2026-07-04).
    from engine_alpha.scoring.scoring import score_setup

    neutral = score_setup(**_score_common())["box_tightness"]                       # None -> neutral
    clean = score_setup(**_score_common(bar_compression=_CLEAN_TEXTURE))["box_tightness"]
    messy = score_setup(**_score_common(bar_compression=_MESSY_TEXTURE))["box_tightness"]
    assert clean == pytest.approx(neutral)            # a clean texture is read as a real coil
    assert messy < neutral                            # a choppy texture is discounted
    assert messy == pytest.approx(neutral * settings.CANDLE_GRADE_FLOOR, rel=0.02)


# --- E3: puzzle-quality graded sub-score (flag-gated) ---------------------------

def _nar(completeness, chronology, upthrust_terminal=False):
    return {"completeness": completeness, "chronology": chronology,
            "upthrust_terminal": upthrust_terminal}


def test_puzzle_quality_neutral_on_missing():
    from engine_alpha.scoring.scoring import _puzzle_quality
    assert _puzzle_quality(None) == 0.0           # a missing narrative passes None
    assert _puzzle_quality({}) == 0.0             # malformed dict -> neutral
    assert _puzzle_quality("nope") == 0.0         # non-dict -> neutral
    assert _puzzle_quality(_nar(0, "absent")) == 0.0   # well-formed empty narrative


def test_puzzle_quality_monotonic_and_bounded():
    from engine_alpha.scoring.scoring import _puzzle_quality
    chronos = ["absent", "partial", "intact"]
    # Bounded [0,1] over the whole completeness x chronology domain.
    for c in range(0, 5):
        for ch in chronos:
            q = _puzzle_quality(_nar(c, ch))
            assert 0.0 <= q <= 1.0
    # Non-decreasing in completeness at fixed chronology.
    for ch in chronos:
        seq = [_puzzle_quality(_nar(c, ch)) for c in range(0, 5)]
        assert seq == sorted(seq) and seq[0] < seq[-1]
    # intact >= partial >= absent at fixed completeness.
    for c in range(0, 5):
        a = _puzzle_quality(_nar(c, "absent"))
        p = _puzzle_quality(_nar(c, "partial"))
        i = _puzzle_quality(_nar(c, "intact"))
        assert a <= p <= i


def test_ta_score_v2_flag_off_leaks_no_v2_keys(monkeypatch):
    """Flag-off tripwire at the SCORER boundary (TA-grade build task 2): with
    TA_SCORE_V2 off, score_setup emits NONE of the reserved v2 vocabulary and
    stays the frozen composite. The key list derives from the ONE settled
    vocabulary (taxonomy.V2_RESULT_KEYS, build task 1) so every key added there
    is guarded here automatically; the anchor assertions pin the core names so
    an emptied or renamed vocabulary can never quietly green this test. The
    wire-boundary twin lives in tests/test_dashboard_wire.py."""
    from engine_alpha.scoring.scoring import score_setup
    from engine_alpha.scoring import taxonomy
    for core in ("ta_grade", "ta_grade_raw", "ta_grade_chapters",
                 "structure_tier", "fired_tags"):
        assert core in taxonomy.V2_RESULT_KEYS, (
            f"core v2 name {core!r} missing from the settled vocabulary")
    monkeypatch.setattr(settings, "TA_SCORE_V2", False)
    out = score_setup(**_score_common())
    for k in taxonomy.V2_RESULT_KEYS:
        assert k not in out, f"v2 key {k!r} leaked from score_setup with the flag off"
    assert "spring" not in out, "the flag-gated spring term leaked with the flag off"


def test_score_setup_emits_no_v2_keys_under_either_flag(monkeypatch):
    """score_setup is v1-only FOREVER: the v2 grade lives in compose_ta_grade,
    called from the shared eval chain where the story scalars exist. Under
    either flag state the scorer's own dict carries no v2 vocabulary."""
    from engine_alpha.scoring.scoring import score_setup
    from engine_alpha.scoring import taxonomy
    for flag in (False, True):
        monkeypatch.setattr(settings, "TA_SCORE_V2", flag)
        out = score_setup(**_score_common())
        for k in (*taxonomy.V2_RESULT_KEYS, "spring", "story_s_tests"):
            assert k not in out, f"{k!r} leaked from score_setup (flag={flag})"


# --- Task 4: the chapter composite (compose_ta_grade) ---------------------------
# compose_ta_grade is flag-ON-only by contract: the eval chain gates the call,
# and the registry loop drops not-emitted (flag-gated) terms — so the battery
# runs with the flag on, exactly as the one production call site does.

@pytest.fixture
def v2_on(monkeypatch):
    monkeypatch.setattr(settings, "TA_SCORE_V2", True)


def _sub(overrides=None):
    """A realistic v1 sub_scores dict (registry keys, values within caps).
    Hand-set so the ta-layer sum is exactly 107.0 (breadth's 6.0 excluded)."""
    base = {"box_tightness": 15.0, "touch_density": 18.0, "traversal_quality": 6.0,
            "atr_squeeze": 4.0, "lps_tightness": 12.0, "vol_contraction": 10.0,
            "base_age": 14.0, "uptrend_bonus": 0.0, "rs_bonus": 0.0,
            "high_proximity": 5.0, "breadth_bonus": 6.0, "contraction": 8.0,
            "ascending_support": 4.0, "adr": 5.0, "puzzle_quality": 6.0}
    base.update(overrides or {})
    return base


def _em(**overrides):
    """A measured story substrate (the archived as-of scalars)."""
    base = {"event_map_completed_s": 3, "event_map_completed_r": 2,
            "event_map_alternations": 2, "event_map_terminal_posture": 1,
            "event_map_terminal_drift": 0, "event_map_episode_nan_bars": 0}
    base.update(overrides)
    return base


def test_compose_grade_chapters_partition_the_one_sum(v2_on):
    """Chapters are a display partition of ONE fixed-divisor affine sum: fixed
    arity in the ruled order, subtotals summing EXACTLY to the pre-warning
    grade, bounded [0,100], breadth (regime) excluded from the sum."""
    from engine_alpha.scoring.scoring import compose_ta_grade
    from engine_alpha.scoring import taxonomy
    grid = [
        compose_ta_grade(_sub()),
        compose_ta_grade(_sub(), event_map=_em()),
        compose_ta_grade(_sub({"box_tightness": 0.0}), has_spring=True),
        compose_ta_grade({}, event_map=None),                     # all-absent row
        compose_ta_grade(_sub({"adr": None}),
                         event_map=_em(event_map_completed_s=0)),
    ]
    cap_sum = taxonomy.structural_cap_sum()
    for out in grid:
        assert 0.0 <= out["ta_grade"] <= 100.0
        assert tuple(out["ta_grade_chapters"]) == taxonomy.CHAPTER_ORDER
        assert sum(out["ta_grade_chapters"].values()) == pytest.approx(
            out["ta_grade_raw"] * 100.0 / cap_sum, abs=1e-9)
    # Hand-computed anchor (Beck P1 — never copied from the implementation):
    # the _sub ta-layer values sum to 107.0; breadth's 6.0 is excluded; story
    # terms absent contribute 0 against the FIXED divisor.
    assert grid[0]["ta_grade_raw"] == pytest.approx(107.0)
    assert grid[0]["ta_grade"] == pytest.approx(107.0 * 100.0 / cap_sum)
    # The all-absent row is a finite geometry-only baseline, not NaN.
    assert grid[3]["ta_grade"] == 0.0 and grid[3]["ta_grade_raw"] == 0.0


def test_compose_grade_absence_is_neutral_against_the_fixed_divisor(v2_on):
    """A row missing an input grades against the SAME denominator as a full
    row — absence is neutral-zero, never a per-row divisor shrink (the
    present-cap denominator is tested-DEAD backend-side)."""
    from engine_alpha.scoring.scoring import compose_ta_grade
    from engine_alpha.scoring import taxonomy
    missing = compose_ta_grade(_sub({"adr": None}))
    zeroed = compose_ta_grade(_sub({"adr": 0.0}))
    assert missing["ta_grade"] == pytest.approx(zeroed["ta_grade"])
    assert missing["ta_grade"] == pytest.approx(
        missing["ta_grade_raw"] * 100.0 / taxonomy.structural_cap_sum())


def test_compose_grade_quarantines_nan_before_summing(v2_on):
    from engine_alpha.scoring.scoring import compose_ta_grade
    out = compose_ta_grade(
        _sub({"lps_tightness": float("nan"), "adr": float("inf")}),
        event_map=_em(event_map_completed_s=float("nan")))
    assert math.isfinite(out["ta_grade"]) and math.isfinite(out["ta_grade_raw"])
    assert all(math.isfinite(v) for v in out["ta_grade_chapters"].values())


def test_compose_grade_warnings_discount_floored_missing_is_exactly_one(v2_on, monkeypatch):
    """Warnings multiply on the bounded 0-100: a firing warning discounts by
    its factor, the product never breaches the floor, a missing warning input
    is factor 1.0 EXACTLY, and chapters stay pre-warning (the discount lives
    on the headline only)."""
    from engine_alpha.scoring.scoring import compose_ta_grade
    clean = compose_ta_grade(_sub(), event_map=_em())          # drift 0 -> none
    assert clean["ta_grade_warnings"] == {}
    monkeypatch.setattr(settings, "TA_WARN_TERMINAL_DRIFT", 0.8)
    warned = compose_ta_grade(_sub(), event_map=_em(event_map_terminal_drift=1))
    assert warned["ta_grade_warnings"] == {"terminal_drift": 0.8}
    assert warned["ta_grade"] == pytest.approx(clean["ta_grade"] * 0.8)
    assert sum(warned["ta_grade_chapters"].values()) == pytest.approx(
        sum(clean["ta_grade_chapters"].values()))
    monkeypatch.setattr(settings, "TA_WARN_TERMINAL_DRIFT", 0.05)
    floored = compose_ta_grade(_sub(), event_map=_em(event_map_terminal_drift=1))
    assert floored["ta_grade"] == pytest.approx(
        clean["ta_grade"] * settings.TA_GRADE_WARNING_FLOOR)
    absent = compose_ta_grade(_sub(), event_map=None)          # missing family
    assert absent["ta_grade_warnings"] == {}


def test_compose_grade_rank_preservation_is_exact_the_affine_identity(v2_on):
    """The normalized ordering equals the raw ordering EXACTLY — a mathematical
    identity of the fixed-divisor affine map; any violation is a bug. (Kept
    strictly apart from the EXPECTED v1→v2 rank movement, which is the task-13
    A/B instrument's artifact, not a test.)"""
    from engine_alpha.scoring.scoring import compose_ta_grade
    a = compose_ta_grade(_sub({"box_tightness": 15.000001}))
    b = compose_ta_grade(_sub({"box_tightness": 15.0}))
    assert a["ta_grade_raw"] > b["ta_grade_raw"]
    assert a["ta_grade"] > b["ta_grade"]        # strictly monotone even at 1e-6


def test_compose_story_terms_distinguish_absent_zero_and_unreadable(v2_on, monkeypatch):
    """Three-state story inputs: absent family = neutral; measured counts =
    evidence that grades; all-zero counts with a high unreadable companion =
    ABSENT (the stance term proves the branch: posture 1 earns nothing when
    the window's zeros are unreadable). Caps monkeypatched non-zero to make
    the states observable — production caps stay 0 until the A/B."""
    from engine_alpha.scoring.scoring import compose_ta_grade
    monkeypatch.setattr(settings, "SCORE_STORY_S_TESTS", 10)
    monkeypatch.setattr(settings, "SCORE_STORY_TERMINAL_POSTURE", 8)
    absent = compose_ta_grade(_sub(), event_map=None)
    measured = compose_ta_grade(_sub(), event_map=_em())
    zeros = dict(event_map_completed_s=0, event_map_completed_r=0,
                 event_map_alternations=0)
    honest_zero = compose_ta_grade(_sub(), event_map=_em(**zeros))
    unreadable = compose_ta_grade(_sub(), event_map=_em(
        **zeros, event_map_episode_nan_bars=settings.STORY_UNREADABLE_NAN_BARS))
    assert measured["story_s_tests"] == pytest.approx(10.0)   # saturates at FULL
    assert absent["story_s_tests"] == 0.0
    assert honest_zero["story_s_tests"] == 0.0                # evidence: reads 0
    assert honest_zero["story_terminal_posture"] == pytest.approx(8.0)
    assert unreadable["story_terminal_posture"] == 0.0        # the whole row is absent
    assert measured["ta_grade"] > absent["ta_grade"]          # the evidence grades


def test_compose_stance_enters_its_own_term_never_the_facts(v2_on, monkeypatch):
    """Right-edge stance (terminal posture) may only move its own finish-term —
    never a completed-event count, never the work chapter."""
    from engine_alpha.scoring.scoring import compose_ta_grade
    monkeypatch.setattr(settings, "SCORE_STORY_TERMINAL_POSTURE", 8)
    up = compose_ta_grade(_sub(), event_map=_em(event_map_terminal_posture=1))
    down = compose_ta_grade(_sub(), event_map=_em(event_map_terminal_posture=0))
    for k in ("story_s_tests", "story_r_rejections", "story_alternations"):
        assert up[k] == down[k]
    assert up["ta_grade_chapters"]["work"] == pytest.approx(
        down["ta_grade_chapters"]["work"])
    assert up["ta_grade_chapters"]["finish"] > down["ta_grade_chapters"]["finish"]


def test_compose_never_reads_the_tape(v2_on):
    """The composite consumes named as-of scalars only — a corrupt tape or
    profile sentence changes nothing (nothing re-derives counts downstream)."""
    from engine_alpha.scoring.scoring import compose_ta_grade
    garbage = _em(event_map_episodes="TOTALLY [ BROKEN", event_map_episode_profile="??")
    assert compose_ta_grade(_sub(), event_map=garbage) == \
        compose_ta_grade(_sub(), event_map=_em())


# --- Task 5: the TA-grade archive family extraction -----------------------------

def test_ta_grade_archive_values_null_through_when_dark():
    """A flag-dark row (no _ta_grade / _puzzle_* fields) archives the whole
    family as NULL — never zero (NULL = not measured, the pre-flip contract)."""
    from engine_alpha.scoring.scoring import ta_grade_archive_values
    out = ta_grade_archive_values((lambda _k: None), prefixed=True)
    assert set(out) == {"ta_grade", "ta_grade_raw", "puzzle_completeness",
                        "puzzle_chronology", "puzzle_upthrust_terminal",
                        "score_spring", "score_story_s_tests",
                        "score_story_r_rejections", "score_story_alternations",
                        "score_story_terminal_posture",
                        "lps_shrink_frac", "lps_window_classification",
                        "story_richness_rate"}
    assert all(v is None for v in out.values())


def test_ta_grade_archive_values_scrubs_and_coerces():
    """EC-2 at the pandas boundary: NaN scrubs to NULL; INTEGER cells land as
    plain ints (bools on the 0/1 convention); floats pass at full precision."""
    from engine_alpha.scoring.scoring import ta_grade_archive_values
    row = {"_ta_grade": 61.5, "_ta_grade_raw": float("nan"),
           "_puzzle_completeness": 3.0, "_puzzle_chronology": "partial",
           "_puzzle_upthrust_terminal": True}
    out = ta_grade_archive_values(row.get, prefixed=True)
    assert out["ta_grade"] == 61.5
    assert out["ta_grade_raw"] is None
    assert out["puzzle_completeness"] == 3
    assert isinstance(out["puzzle_completeness"], int)
    assert out["puzzle_upthrust_terminal"] == 1
    assert out["puzzle_chronology"] == "partial"


def test_ta_grade_archive_values_refuses_illegal_chronology():
    """EC-19/22 adapted for the write producer: every legal chronology value
    passes through; an illegal label fails loudly and never lands."""
    from engine_alpha.scoring.scoring import ta_grade_archive_values
    for legal in ("intact", "partial", "absent"):
        out = ta_grade_archive_values({"puzzle_chronology": legal}.get,
                                      prefixed=False)
        assert out["puzzle_chronology"] == legal
    with pytest.raises(ValueError, match="closed set"):
        ta_grade_archive_values({"puzzle_chronology": "Intact"}.get,
                                prefixed=False)
    # Same discipline for the LPS window classification (task 7).
    for legal in ("rising_march", "turned", "clean_dip", "mixed"):
        out = ta_grade_archive_values(
            {"lps_window_classification": legal}.get, prefixed=False)
        assert out["lps_window_classification"] == legal
    with pytest.raises(ValueError, match="closed"):
        ta_grade_archive_values(
            {"lps_window_classification": "insufficient"}.get, prefixed=False)


def test_compose_spring_term_is_present_mask_neutral(v2_on):
    """The spring term reads its registered cap when present, exactly 0.0 when
    absent — never negative, never demoting. Weight-agnostic: holds at the
    shape-only cap of 0 and any future A/B value."""
    from engine_alpha.scoring.scoring import compose_ta_grade
    sprung = compose_ta_grade(_sub(), has_spring=True)
    flat = compose_ta_grade(_sub(), has_spring=False)
    assert sprung["spring"] == pytest.approx(float(settings.SCORE_SPRING))
    assert flat["spring"] == 0.0
    assert sprung["ta_grade_raw"] - flat["ta_grade_raw"] == pytest.approx(
        float(settings.SCORE_SPRING), abs=1e-9)
    assert sprung["ta_grade"] >= flat["ta_grade"] - 1e-9


def test_taxonomy_emitted_keys_match_score_setup_output():
    """The registry's emitted keys must exactly equal score_setup's sub-score keys
    (default flags) — the score-dict coupling that keeps the taxonomy authoritative."""
    from engine_alpha.scoring.scoring import score_setup
    from engine_alpha.scoring import taxonomy
    out = score_setup(**_score_common())
    assert set(taxonomy.emitted_keys()) == set(out) - {"total"}


def test_puzzle_awards_bonus_and_adds_key():
    # The puzzle term is unconditional engine behavior (folded 2026-07-18;
    # formerly behind PUZZLE_SCORE_ENABLED, live since 2026-07-04).
    from engine_alpha.scoring.scoring import score_setup
    none_on = score_setup(**_score_common(narrative=None))   # no narrative -> 0 bonus
    rich = score_setup(**_score_common(narrative=_nar(4, "intact")))
    poor = score_setup(**_score_common(narrative=_nar(1, "absent")))
    assert none_on["puzzle_quality"] == 0.0 and "puzzle_quality" in rich
    assert rich["puzzle_quality"] == settings.SCORE_PUZZLE_QUALITY   # full puzzle -> the cap
    assert rich["puzzle_quality"] > poor["puzzle_quality"] > 0.0
    # the bonus is exactly the total lift over the no-narrative (0-bonus) baseline.
    assert rich["total"] == pytest.approx(none_on["total"] + rich["puzzle_quality"], abs=0.05)
    assert rich["total"] > poor["total"]


def test_puzzle_term_is_bonus_only_and_capped():
    from engine_alpha.scoring.scoring import score_setup
    off = score_setup(**_score_common(narrative=None))["total"]
    for c in range(0, 5):
        for ch in ("absent", "partial", "intact"):
            r = score_setup(**_score_common(narrative=_nar(c, ch)))
            assert 0.0 <= r["puzzle_quality"] <= settings.SCORE_PUZZLE_QUALITY  # bounded bonus
            assert r["total"] >= off                                           # never demotes


def test_e3_eval_feeds_engine_elected_bricks(monkeypatch):
    # The puzzle is read on the engine's OWN elected PARENT box object (object
    # identity), with the EXACT same df + atr read_structure used — never a
    # reconstruction — AND it REUSES the engine's elected spring/LPS bricks
    # (structure.spring / structure.lps) rather than re-detecting on the parent
    # box. This is the faithfulness fix: on an inner-LPS fire, the puzzle must
    # describe the LPS that actually fired (the inner election), never a fresh
    # parent-box re-detection, and it must never SILENTLY drop the elected LPS.
    from tools.shadow_diff import _load_fixture
    import engine_alpha.evaluation as evaluation

    frames, scalars = _load_fixture()
    spy_6m = float(scalars.get("spy_6m_return", 0.0))

    real_rs, real_nar = evaluation.read_structure, evaluation.assemble_box_narrative
    seen = {}

    def _rs(df, atr, **k):
        s = real_rs(df, atr, **k)
        seen["rs_df"], seen["rs_atr"], seen["structure"] = df, atr, s
        return s

    def _nar_spy(df, box, atr, **kw):
        # Capture the injected kwargs (spring / lps) verbatim so we can prove the
        # call site passed the ELECTED bricks, and capture the returned narrative.
        seen["df"], seen["box"], seen["atr"] = df, box, atr
        seen["spring_arg"], seen["lps_arg"] = kw.get("spring"), kw.get("lps")
        nar = real_nar(df, box, atr, **kw)
        seen["nar"] = nar
        return nar

    monkeypatch.setattr(evaluation, "read_structure", _rs)
    monkeypatch.setattr(evaluation, "assemble_box_narrative", _nar_spy)

    fires = inner_fires = lps_represented = 0
    for ticker in scalars["tickers"]:
        df = frames.get(ticker)
        if df is None:
            continue
        seen.clear()
        if evaluation._evaluate_ticker(ticker, df, spy_6m, None) is None:
            continue
        fires += 1
        s = seen["structure"]
        assert seen["box"] is s.box                 # the exact elected PARENT box, unmodified
        assert seen["df"] is seen["rs_df"]          # same df read_structure used
        assert seen["atr"] == seen["rs_atr"]        # same atr read_structure used
        # The narrative REUSES the engine's elected bricks (object identity) — not
        # a re-detected parent-box LPS. lps is required for a fire; spring may be None.
        assert seen["lps_arg"] is s.lps and s.lps is not None
        assert seen["spring_arg"] is s.spring
        # The elected LPS is NEVER silently dropped: either it lands as the spine
        # LPS piece (so completeness counts it) or the rare gate-drop is flagged.
        nar = seen["nar"]
        if nar["spine"]["lps"] is not None:
            lps_represented += 1
            # bit-for-bit: the spine LPS anchor is the elected low_bar, box-relative.
            exp_anchor = max(0, min(int(s.lps.low_bar) - int(s.box.start_bar),
                                    int(nar["base_n"]) - 1))
            assert nar["spine"]["lps"]["anchor_bar"] == exp_anchor
        else:
            assert nar["lps_pre_v_dropped"] is True   # dropped -> observable, not silent
        if s.inner is not None:                     # inner-LPS fire -> still the PARENT frame
            inner_fires += 1
            assert seen["box"] is not s.inner
    assert fires > 0
    assert lps_represented > 0                       # the elected LPS is normally represented


def test_e3_eval_twins_agree_on_puzzle():
    # Both eval-twins (live + seed) route through the single score_setup call, so
    # they compute the identical puzzle bonus (EC-3 fold).
    from tools.shadow_diff import _load_fixture
    from engine_alpha.evaluation import _evaluate_ticker
    from core.archive.seed import _evaluate_at_date
    from core.archive.result_adapter import seed_row_from_result

    frames, scalars = _load_fixture()
    spy_6m = float(scalars.get("spy_6m_return", 0.0))

    for ticker in scalars["tickers"]:
        df = frames.get(ticker)
        if df is None:
            continue
        live = _evaluate_ticker(ticker, df, spy_6m, None)
        seed = _evaluate_at_date(df, spy_6m)        # already the adapter-stripped shape
        if live is None or seed is None:
            continue
        alive = seed_row_from_result(live)           # adapt live to the same shape
        # Both twins compute the identical puzzle bonus (and the adapter re-keys it).
        assert (alive["sub_scores"].get("puzzle_quality")
                == seed["sub_scores"].get("puzzle_quality"))
        assert alive["puzzle_completeness"] == seed["puzzle_completeness"]
        return
    pytest.skip("no firing ticker in fixture")
