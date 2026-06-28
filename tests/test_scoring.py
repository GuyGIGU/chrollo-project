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

from core.structure.indicators import trend_template
from core.archive.analyze import derive_outcomes, safe_rank_corr, signal_edge
from tools.fidelity_harness import summarize_fidelity


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


def test_adr_relative_box_tightness_demotes_flat_low_adr_drift(monkeypatch):
    """With TIGHTNESS_ADR_AWARE on, box tightness is measured in ADR units: the SAME
    absolute box width is a tight coil on a real mover but a wide drift on a flat
    low-ADR name (the GBTG case). With the flag off, ADR is ignored and both score
    the identical absolute tightness (the shadow-preserving default)."""
    from core.scoring.scoring import score_setup

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
    from core.pipeline import evaluation as evaluation_module
    from core.pipeline.evaluation import _evaluate_ticker, _run_eval_chain

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

    # Both entry points delegate to the one shared chain.
    assert "_run_eval_chain" in called_names(_evaluate_ticker)
    seed_calls = called_names(_evaluate_at_date)
    assert "_run_eval_chain" in seed_calls, "_evaluate_at_date no longer routes through the shared chain"
    assert "seed_row_from_result" in seed_calls, "_evaluate_at_date must re-key via the adapter"

    # The shared chain routes through the structural helpers (the real anti-drift guard).
    chain_calls = called_names(_run_eval_chain)
    assert "_resolve_structure_context" in chain_calls
    assert "_resolve_lps_context" in chain_calls
    assert "descent_tail_drops" in chain_calls
    assert "_score_eval_context" in chain_calls

    # Deeper folds preserved.
    assert "select_active_lps" in called_names(evaluation_module._resolve_lps_context)
    assert "score_traversal_args" in called_names(evaluation_module._score_eval_context)


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


def test_select_active_lps_prefers_inner_then_parent(monkeypatch, _lps_behavior_frame):
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
