"""The archive's edge arithmetic (core.archive.analyze): outcome derivation, the rank correlation and the
signal-edge verdicts.

Moved out of tests/scoring/test_scoring.py when the old scorer retired with the old engine (Sat 31/10/2026);
these never read a chart, they read the archive's columns.
"""
import math

import numpy as np
import pandas as pd

from core.archive.analyze import derive_outcomes, safe_rank_corr, signal_edge


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


def test_magnitude_threshold_is_imported_not_redeclared():
    """EC-3: the tail threshold has ONE home. A literal 0.25 here would drift the
    day the edge report's bands move."""
    from core.archive import analyze
    from core.backtest.edge_report import TAIL_MFE_COL, TAIL_THRESHOLDS
    assert analyze.MAGNITUDE_THRESHOLD is TAIL_THRESHOLDS[0]
    assert analyze.TAIL_MFE_COL is TAIL_MFE_COL


def test_derive_outcomes_adds_a_label_free_magnitude_target():
    from core.archive.analyze import MAGNITUDE_TARGET, MAGNITUDE_THRESHOLD
    df = pd.DataFrame({
        "barrier_label": [None, None, "loss", None],   # deliberately unlabelled
        "mfe_20d": [MAGNITUDE_THRESHOLD, MAGNITUDE_THRESHOLD - 1e-9, 0.9, None],
    })
    out = derive_outcomes(df)
    got = out[MAGNITUDE_TARGET].tolist()
    assert got[0] == 1.0          # the threshold is INCLUSIVE
    assert got[1] == 0.0          # just under it, and matured, is a measured miss
    assert got[2] == 1.0          # a row the barrier calls a LOSS still counts here
    assert math.isnan(got[3])     # not matured is unknown, never 0.0
    # The whole point: it needs no label, so it keeps rows barrier_win drops.
    assert out["barrier_win"].isna().sum() == 3 and out[MAGNITUDE_TARGET].notna().sum() == 3


def test_adding_the_magnitude_target_does_not_move_the_primary():
    """Swapping the primary would silently rewrite every standing verdict."""
    from core.archive.analyze import EDGE_TARGETS, MAGNITUDE_TARGET
    assert EDGE_TARGETS[0] == "durable_win"
    assert EDGE_TARGETS[-1] == MAGNITUDE_TARGET
    n = 40
    win = [1.0, 0.0] * (n // 2)
    df = pd.DataFrame({"durable_win": win, MAGNITUDE_TARGET: [1.0 - w for w in win],
                       "score_box_tightness": win})
    out = signal_edge(df)
    assert out["primary_target"] == "durable_win"


def test_signal_edge_flags_a_sign_split_between_the_two_targets():
    """The motivating case: a term the path target calls harmful and the magnitude
    target calls beneficial. Acting on half of that is how rs/uptrend went to zero."""
    from core.archive.analyze import MAGNITUDE_TARGET
    n = 40
    win = [1.0, 0.0] * (n // 2)
    df = pd.DataFrame({
        "durable_win": win,
        MAGNITUDE_TARGET: [1.0 - w for w in win],   # exactly opposite outcome
        "score_rs_bonus": [1.0 - w for w in win],   # harmful vs primary, good vs magnitude
    })
    out = signal_edge(df)
    row = next(r for r in out["rows"] if r["feature"] == "score_rs_bonus")
    assert row["verdict"] == "harmful"
    assert row["magnitude_verdict"] == "beneficial"
    assert row["verdict_disagrees"] is True


def test_signal_edge_flags_clears_the_floor_versus_does_not():
    """score_adr live: inert on the barrier target, beneficial on magnitude. The
    two targets lead to different action, which is what the flag is for."""
    from core.archive.analyze import MAGNITUDE_TARGET
    n = 40
    win = [1.0, 0.0] * (n // 2)
    df = pd.DataFrame({
        "durable_win": win,
        MAGNITUDE_TARGET: win,
        "score_adr": list(range(n)),        # ~0 vs alternating -> inert on primary
        "score_box_tightness": win,         # perfect vs magnitude -> beneficial
    })
    out = signal_edge(df)
    adr = next(r for r in out["rows"] if r["feature"] == "score_adr")
    assert adr["verdict"] == "inert" and adr["magnitude_verdict"] == "inert"
    assert adr["verdict_disagrees"] is False    # agreeing inert is NOT a disagreement


def test_magnitude_is_judged_on_its_own_noise_floor_not_the_primarys():
    """The magnitude target needs no label, so it keeps rows the barrier gate
    drops and its n is LARGER — which means a LOWER noise floor. Judging it on
    the primary's floor would call a real magnitude signal inert purely because
    the barrier target had less data. Constructed so the correlation lands
    BETWEEN the two floors: 0.15 (magnitude, n=60) < rho < 0.2425 (primary, n=20).
    """
    from core.archive.analyze import MAGNITUDE_TARGET
    n_mag, n_pri = 60, 20
    feat = np.arange(n_mag, dtype=float)
    mag = feat + np.random.default_rng(6).normal(0, 45, n_mag)
    primary = [1.0, 0.0] * (n_pri // 2) + [float("nan")] * (n_mag - n_pri)
    df = pd.DataFrame({"durable_win": primary, MAGNITUDE_TARGET: mag,
                       "score_adr": feat})
    out = signal_edge(df)
    assert out["n_primary"] == n_pri
    row = next(r for r in out["rows"] if r["feature"] == "score_adr")
    assert row["magnitude_n"] == n_mag
    # rho sits above the magnitude floor (0.15) and below the primary's (0.2425).
    assert 0.15 < row["magnitude_corr"] < max(0.15, 1.0 / math.sqrt(n_pri - 3))
    assert row["magnitude_verdict"] == "beneficial"


def test_signal_edge_never_flags_absence_of_evidence_as_disagreement():
    """'unknown' means we could not measure, not that the targets conflict."""
    from core.archive.analyze import MAGNITUDE_TARGET
    n = 40
    win = [1.0, 0.0] * (n // 2)
    df = pd.DataFrame({
        "durable_win": win,
        MAGNITUDE_TARGET: [float("nan")] * n,   # nothing matured -> unknown
        "score_touch_density": [1.0 - w for w in win],
    })
    out = signal_edge(df)
    row = next(r for r in out["rows"] if r["feature"] == "score_touch_density")
    assert row["verdict"] == "harmful"
    assert row["magnitude_verdict"] == "unknown"
    assert row["verdict_disagrees"] is False


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
