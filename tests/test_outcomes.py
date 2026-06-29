"""Tests for core.archive.outcomes — the single source of truth for outcome math.

Covers the window-agnostic ELAPSED-window metric (bug class #1: the fixed-window
"stuck on no mature data" failure) and proves the SINGLE-SOURCE invariant: the
forward-return updater computes its fixed-window numbers via the same module, so
the stored column and the reported edge can never diverge.

Offline / pure: no DB, no network.
"""
from __future__ import annotations

import os
import sys

import numpy as np
import pandas as pd
import pytest

_ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from core.archive import outcomes


# ─────────────────────────────────────────────────────────────────────────────
# Elapsed-window outcome — window-agnostic by construction
# ─────────────────────────────────────────────────────────────────────────────
def test_elapsed_full_window():
    highs = [105, 110, 108]
    lows = [99, 101, 103]
    closes = [104, 109, 107]
    out = outcomes.compute_elapsed_outcome(highs, lows, closes, 100.0,
                                           spy_window_return=0.02)
    assert out["mfe_to_date"] == pytest.approx(0.10)   # max high 110 -> +10%
    assert out["mae_to_date"] == pytest.approx(-0.01)  # min low 99 -> -1%
    assert out["ret_to_date"] == pytest.approx(0.07)   # last close 107 -> +7%
    assert out["bars_to_date"] == 3
    assert out["abnormal_ret_to_date"] == pytest.approx(0.05)  # 0.07 - 0.02


def test_elapsed_partial_window_one_bar():
    """A 1-bar window still produces a read — never gated on a full 20/60."""
    out = outcomes.compute_elapsed_outcome([103], [98], [101], 100.0)
    assert out["mfe_to_date"] == pytest.approx(0.03)
    assert out["mae_to_date"] == pytest.approx(-0.02)
    assert out["ret_to_date"] == pytest.approx(0.01)
    assert out["bars_to_date"] == 1
    assert out["abnormal_ret_to_date"] is None  # no SPY supplied


def test_elapsed_two_bars_below_three():
    """<3 bars is fine — there is no minimum-bar gate."""
    out = outcomes.compute_elapsed_outcome([102, 104], [99, 100], [101, 103], 100.0)
    assert out["bars_to_date"] == 2
    assert out["mfe_to_date"] == pytest.approx(0.04)


def test_elapsed_zero_forward_bars_is_all_none():
    out = outcomes.compute_elapsed_outcome([], [], [], 100.0)
    assert out == {
        "mfe_to_date": None, "mae_to_date": None, "ret_to_date": None,
        "bars_to_date": None, "abnormal_ret_to_date": None,
    }


def test_elapsed_non_positive_scan_close_is_all_none():
    out = outcomes.compute_elapsed_outcome([101], [99], [100], 0.0)
    assert all(v is None for v in out.values())


def test_elapsed_caps_at_horizon():
    """A 200-bar window only measures the first 60 (the archive horizon)."""
    highs = [100 + i for i in range(200)]   # rises forever
    lows = [100 - i for i in range(200)]
    closes = list(highs)
    out = outcomes.compute_elapsed_outcome(highs, lows, closes, 100.0)
    assert out["bars_to_date"] == outcomes.HORIZON_BARS  # 60, not 200
    # max high inside the 60-bar cap is highs[59] = 159 -> +59%
    assert out["mfe_to_date"] == pytest.approx(0.59)


def test_elapsed_holiday_gap_counts_bars_not_days():
    """A market closure means one fewer BAR, not a wrong horizon — the function
    only ever sees the bars it is handed, so a gap is simply a shorter window."""
    # 4 trading bars (a holiday removed what would have been a 5th calendar day).
    out = outcomes.compute_elapsed_outcome(
        [101, 102, 103, 104], [99, 98, 99, 100], [100, 101, 102, 103], 100.0,
    )
    assert out["bars_to_date"] == 4
    assert out["ret_to_date"] == pytest.approx(0.03)


def test_elapsed_abnormal_with_negative_spy():
    """Abnormal return = setup return minus SPY over the same window."""
    out = outcomes.compute_elapsed_outcome([97], [94], [96], 100.0,
                                           spy_window_return=-0.05)
    assert out["ret_to_date"] == pytest.approx(-0.04)
    assert out["abnormal_ret_to_date"] == pytest.approx(0.01)  # -0.04 - (-0.05)


def test_window_return_helper():
    assert outcomes.window_return([102, 105, 110], 100.0) == pytest.approx(0.10)
    assert outcomes.window_return([102, 105, 110], 100.0, bars=1) == pytest.approx(0.02)
    assert outcomes.window_return([], 100.0) is None
    assert outcomes.window_return([110], 0.0) is None


# ─────────────────────────────────────────────────────────────────────────────
# Single source of truth — the updater computes fixed windows via this module
# ─────────────────────────────────────────────────────────────────────────────
def test_forward_returns_uses_outcomes_module_for_barriers():
    """forward_returns re-exports the SAME barrier function (no re-derivation)."""
    from core.archive import forward_returns as fr
    assert fr.compute_barrier_events is outcomes.compute_barrier_events
    assert fr.compute_elapsed_outcome is outcomes.compute_elapsed_outcome
    assert fr.FORWARD_RETURN_HORIZON_BARS == outcomes.HORIZON_BARS


def test_fixed_and_elapsed_agree_at_full_window():
    """At a full 60-bar window the elapsed metric must equal the fixed 60d metric
    (same anchor, same math) — the invariant that proves single-sourcing."""
    from core.archive import forward_returns as fr
    idx = pd.date_range("2026-04-02", periods=60, freq="B")
    rng = np.random.default_rng(11)
    base = 100 + np.cumsum(rng.normal(0.3, 1.5, len(idx)))
    df = pd.DataFrame({
        "Open": base, "High": base * 1.01, "Low": base * 0.985, "Close": base,
        "Volume": rng.integers(1e6, 5e6, len(idx)).astype(float),
    }, index=idx)
    res = fr._compute_returns(df, 100.0, trigger_price=None, s_level=95.0)
    assert res["mfe_to_date"] == pytest.approx(res["mfe_60d"])
    assert res["mae_to_date"] == pytest.approx(res["mae_60d"])
    assert res["ret_to_date"] == pytest.approx(res["fwd_return_60d"])
    assert res["bars_to_date"] == 60


def test_elapsed_present_even_when_fixed_windows_are_not():
    """A 5-bar forward window: the fixed 20d/60d MFE are absent, but the elapsed
    metric is populated — the exact 'never stuck' property the refactor delivers."""
    from core.archive import forward_returns as fr
    idx = pd.date_range("2026-06-23", periods=5, freq="B")
    base = np.array([101.0, 103.0, 102.0, 104.0, 105.0])
    df = pd.DataFrame({
        "Open": base, "High": base * 1.01, "Low": base * 0.99, "Close": base,
        "Volume": [1e6] * 5,
    }, index=idx)
    res = fr._compute_returns(df, 100.0, trigger_price=None, s_level=95.0)
    assert "mfe_20d" not in res and "mfe_60d" not in res  # fixed windows not mature
    assert res["mfe_to_date"] is not None                 # elapsed IS populated
    assert res["bars_to_date"] == 5


# ─────────────────────────────────────────────────────────────────────────────
# Track-B auto-migration adds the elapsed columns (verified on a temp sqlite)
# ─────────────────────────────────────────────────────────────────────────────
def test_ensure_outcome_columns_adds_elapsed_columns(tmp_path):
    """A pre-existing setup_archive WITHOUT the elapsed columns gains them
    idempotently — the Track-B additive migration, verified on a temp DB."""
    import sqlite3

    from sqlalchemy import create_engine, inspect

    from core.archive.forward_returns import _ensure_outcome_columns

    db = os.path.join(str(tmp_path), "legacy.db")
    con = sqlite3.connect(db)
    # An old-schema archive lacking every elapsed column.
    con.execute(
        "CREATE TABLE setup_archive (id INTEGER PRIMARY KEY, ticker TEXT, "
        "scan_date TEXT, setup_type TEXT, tier TEXT, score REAL)"
    )
    con.commit()
    con.close()

    engine = create_engine(f"sqlite:///{db}")
    _ensure_outcome_columns(engine)
    cols = {c["name"] for c in inspect(engine).get_columns("setup_archive")}
    for new in ("mfe_to_date", "mae_to_date", "ret_to_date",
                "bars_to_date", "abnormal_ret_to_date"):
        assert new in cols, f"{new} not added by migration"

    # Idempotent: a second run does not raise (columns already exist).
    _ensure_outcome_columns(engine)
    engine.dispose()


# ─────────────────────────────────────────────────────────────────────────────
# abnormal_ret_to_date baseline aligns to the setup's forward END DATE, not by
# SPY's first-N-bars-by-position (regression for the halted/thin-ticker desync)
# ─────────────────────────────────────────────────────────────────────────────
def test_spy_window_return_aligns_by_date_not_position():
    """The SPY abnormal baseline must end on the setup's last forward DATE.

    When a halted/thin setup has fewer forward bars than SPY over the same span,
    aligning SPY by bar COUNT lands on an earlier calendar date and subtracts the
    wrong market move. Align by date: SPY's last close on/before ``fwd_end_ts``.
    """
    from core.archive import forward_returns as fr

    idx = pd.to_datetime(["2026-03-02", "2026-03-03", "2026-03-04",
                          "2026-03-05", "2026-03-06", "2026-03-09"])
    spy = pd.DataFrame({"Close": [100.0, 101.0, 102.0, 103.0, 104.0, 105.0]}, index=idx)
    scan_ts = pd.Timestamp("2026-03-02")  # base close 100

    # Setup's last forward bar is 2026-03-09 even though it (a halted name) only
    # held 3 bars in between — the baseline must run scan->03-09 = +5%, NOT SPY's
    # positional 3rd bar (03-05 = +3%, the old bug).
    assert fr._spy_window_return(spy, scan_ts, pd.Timestamp("2026-03-09")) == pytest.approx(0.05)
    # An earlier endpoint follows the date too.
    assert fr._spy_window_return(spy, scan_ts, pd.Timestamp("2026-03-04")) == pytest.approx(0.02)
    # Missing endpoint / missing SPY -> None (abnormal stays None, never wrong).
    assert fr._spy_window_return(spy, scan_ts, None) is None
    assert fr._spy_window_return(pd.DataFrame(), scan_ts, pd.Timestamp("2026-03-09")) is None
