"""Unit pins for ``core.archive.analyze.suggested_weights`` — the pure, advisory
re-weighting table the /calibration panel reads.

``suggested_weights(df, corr_20d, corr_60d, current_weights)`` is dict-in/dict-out:
it never applies a weight. These tests pin the three behaviours that matter:

  (a) ADEQUATE mixed sample (>= EDGE_MIN_N matured pairs AND >= EDGE_MIN_MINORITY
      of the minority outcome class) -> a non-empty table whose ``suggested``
      values re-normalize back to the current total point cap, with the 0.02
      floor keeping a ~0-corr sub-score off zero;
  (b) the ``n_with_60d >= 15`` pivot between the 20d-only and 20d+60d bases;
  (c) an INADEQUATE / winners-only sample -> empty weights + ``insufficient_data``.

The correlations are PASSED IN (``corr_20d`` / ``corr_60d``), so the frame only
drives the adequacy gate and the 60d-count pivot — which is exactly what these
tests exercise. Fully offline; no DB, no cache.
"""
import sys

import pandas as pd
import pytest

from _paths import REPO_ROOT as ROOT
sys.path.insert(0, str(ROOT))

from core.archive import analyze
from core.archive.analyze import EDGE_MIN_MINORITY, EDGE_MIN_N, suggested_weights


def _outcome_frame(n_win: int, n_loss: int, n_with_60d: int = 0) -> pd.DataFrame:
    """Frame the adequacy gate + 60d pivot read.

    ``barrier_label`` drives ``derive_outcomes`` -> a binary ``durable_win``
    (1.0 per win, 0.0 per loss), the primary edge target. ``fwd_return_60d`` gets
    ``n_with_60d`` non-null rows so the ``use_60d`` branch can be toggled.
    """
    labels = ["win"] * n_win + ["loss"] * n_loss
    fwd_60 = [1.0] * n_with_60d + [None] * (len(labels) - n_with_60d)
    return pd.DataFrame({"barrier_label": labels, "fwd_return_60d": fwd_60})


# ── (a) adequate mixed sample ────────────────────────────────────────────────
def test_adequate_sample_renormalizes_to_cap_and_floors_weak_feature():
    # 15 wins / 15 losses = 30 matured pairs (>= EDGE_MIN_N) with 15 of the
    # minority class (>= EDGE_MIN_MINORITY) -> the gate passes.
    df = _outcome_frame(15, 15, n_with_60d=0)
    current = {"a": 10, "b": 6, "c": 4}          # total cap = 20
    corr_20d = {"a": 0.4, "b": 0.2, "c": 0.0}    # c is ~0 corr -> hits the floor
    corr_60d = {"a": 0.9, "b": 0.9, "c": 0.9}    # ignored: no 60d rows -> 20d only

    out = suggested_weights(df, corr_20d, corr_60d, current)

    assert out["basis"] == "20d_only"
    weights = out["weights"]
    assert len(weights) == 3
    assert {w["name"] for w in weights} == {"a", "b", "c"}

    by_name = {w["name"]: w for w in weights}
    # Re-normalized back to the current total cap (20.0), within rounding drift.
    assert sum(w["suggested"] for w in weights) == pytest.approx(20.0, abs=0.2)
    # Exact re-weighting: 20 * |corr|/sum(|corr|) with sum(|corr|) = 0.62.
    assert by_name["a"]["suggested"] == pytest.approx(12.9)
    assert by_name["b"]["suggested"] == pytest.approx(6.5)
    assert by_name["c"]["suggested"] == pytest.approx(0.6)
    # deltas are suggested - current.
    assert by_name["a"]["delta"] == pytest.approx(2.9)
    assert by_name["c"]["delta"] == pytest.approx(-3.4)
    # The 0.02 floor: c's ~0 corr is floored so it keeps a small live weight
    # instead of being zeroed by one noisy archive.
    assert by_name["c"]["avg_abs_corr"] == pytest.approx(0.02)
    assert by_name["c"]["suggested"] > 0.0


# ── (b) the n_with_60d >= 15 basis pivot ─────────────────────────────────────
def test_uses_60d_basis_when_enough_60d_rows():
    # 20 matured 60d rows (>= 15) -> the suggestion blends |20d| and |60d|.
    df = _outcome_frame(15, 15, n_with_60d=20)
    current = {"a": 10, "b": 10}                  # cap = 20
    corr_20d = {"a": 0.4, "b": 0.2}
    corr_60d = {"a": 0.2, "b": 0.6}

    out = suggested_weights(df, corr_20d, corr_60d, current)

    assert out["basis"] == "20d+60d_avg"
    by_name = {w["name"]: w for w in out["weights"]}
    # blended = (|c20| + |c60|) / 2 : a -> (0.4+0.2)/2 = 0.30, b -> (0.2+0.6)/2 = 0.40
    assert by_name["a"]["avg_abs_corr"] == pytest.approx(0.30)
    assert by_name["b"]["avg_abs_corr"] == pytest.approx(0.40)
    # 20 * blended / 0.70
    assert by_name["a"]["suggested"] == pytest.approx(8.6)
    assert by_name["b"]["suggested"] == pytest.approx(11.4)


def test_falls_back_to_20d_only_when_too_few_60d_rows():
    # Same everything, but only 10 matured 60d rows (< 15) -> corr_60d is ignored.
    df = _outcome_frame(15, 15, n_with_60d=10)
    current = {"a": 10, "b": 10}
    corr_20d = {"a": 0.4, "b": 0.2}
    corr_60d = {"a": 0.2, "b": 0.6}               # would flip the ranking if used

    out = suggested_weights(df, corr_20d, corr_60d, current)

    assert out["basis"] == "20d_only"
    by_name = {w["name"]: w for w in out["weights"]}
    # avg_abs_corr is |20d| alone (the 60d values never enter the blend).
    assert by_name["a"]["avg_abs_corr"] == pytest.approx(0.40)
    assert by_name["b"]["avg_abs_corr"] == pytest.approx(0.20)
    # 20 * |c20| / 0.60
    assert by_name["a"]["suggested"] == pytest.approx(13.3)
    assert by_name["b"]["suggested"] == pytest.approx(6.7)


# ── (c) inadequate / winners-only sample ─────────────────────────────────────
def test_winners_only_sample_returns_no_suggestion():
    # 30 wins, 0 losses: enough matured rows, but the minority class is empty, so
    # the binary gate can't tell harmful from good -> withhold the suggestion.
    df = _outcome_frame(30, 0, n_with_60d=0)
    current = {"a": 10, "b": 6, "c": 4}
    corr_20d = {"a": 0.4, "b": 0.2, "c": 0.0}
    corr_60d = {"a": 0.9, "b": 0.9, "c": 0.9}

    out = suggested_weights(df, corr_20d, corr_60d, current)

    assert out == {"weights": [], "basis": "insufficient_data"}


def test_too_few_matured_pairs_returns_no_suggestion():
    # 10 wins / 9 losses = 19 pairs < EDGE_MIN_N, though the minority class (9) is
    # above its floor — so this isolates the pair-count gate, not the minority one.
    assert 19 < EDGE_MIN_N and 9 >= EDGE_MIN_MINORITY  # guard the fixture's intent
    df = _outcome_frame(10, 9, n_with_60d=0)
    current = {"a": 10, "b": 6, "c": 4}
    corr_20d = {"a": 0.4, "b": 0.2, "c": 0.0}
    corr_60d = {"a": 0.9, "b": 0.9, "c": 0.9}

    out = suggested_weights(df, corr_20d, corr_60d, current)

    assert out["weights"] == []
    assert out["basis"] == "insufficient_data"
