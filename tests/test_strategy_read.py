"""Unit battery for the strategy read (Surface the Read Task 13; council
review 2026-08-05 finding 3).

Every expected value is HAND-COMPUTED from the module's stated definition —
depth = (climax high − S) / climax high, floor_above_ar = S >= AR low — so a
flipped sign, a wrong bar index, a reversed comparison, or a hard-coded
constant all go red here (the earlier range assertion −10 < depth < 1 could
not fail any of those)."""
import math
from types import SimpleNamespace

import numpy as np
import pandas as pd

from engine_alpha.structure.context.strategy_read import (
    STRATEGY_COLUMN_SQL,
    strategy_archive_values,
    strategy_read_fields,
)


def _frame(highs, lows):
    return pd.DataFrame({"High": highs, "Low": lows})


def _structure(climax_bar, ar_bar, S):
    return SimpleNamespace(climax_bar=climax_bar, ar_bar=ar_bar, S=S)


def test_normal_correction_exact_positive_depth():
    # Climax high 100 at bar 1; AR low 75 at bar 3; elected floor S = 80.
    # depth = (100 - 80) / 100 = 0.20 exactly; 80 >= 75 -> floor held.
    df = _frame([90, 100, 95, 85, 88], [85, 92, 88, 75, 82])
    out = strategy_read_fields(df, _structure(1, 3, 80.0))
    assert out["_strategy_correction_depth_pct"] == 0.20
    assert out["_strategy_floor_above_ar"] == 1


def test_alb_recovery_shape_exact_negative_depth():
    # The selling-climax recovery: the base floor sits ABOVE the climax bar's
    # high. Climax high 50 at bar 0; S = 79.25.
    # depth = (50 - 79.25) / 50 = -0.585 exactly — SIGNED, never clamped.
    df = _frame([50, 60, 70, 80], [40, 55, 65, 78])
    out = strategy_read_fields(df, _structure(0, 1, 79.25))
    assert out["_strategy_correction_depth_pct"] == -0.585
    assert out["_strategy_floor_above_ar"] == 1   # 79.25 >= 55


def test_floor_undercuts_the_ar_low_reads_zero():
    # AR low 75 at bar 3; floor S = 70 sits BELOW it -> 0.
    df = _frame([90, 100, 95, 85], [85, 92, 88, 75])
    out = strategy_read_fields(df, _structure(1, 3, 70.0))
    assert out["_strategy_floor_above_ar"] == 0
    assert out["_strategy_correction_depth_pct"] == 0.30   # (100-70)/100


def test_nan_at_the_ar_bar_returns_one_honest_null_family():
    """Council F3: floor >= nan is False — unguarded, a NaN AR low archives
    the FABRICATED measured fact 'floor undercut the AR' (0) while depth goes
    NULL. The family is all-or-nothing: NaN anywhere -> empty dict."""
    df = _frame([90, 100, 95, 85], [85, 92, 88, np.nan])
    assert strategy_read_fields(df, _structure(1, 3, 80.0)) == {}


def test_nan_climax_high_returns_empty():
    df = _frame([90, np.nan, 95, 85], [85, 92, 88, 75])
    assert strategy_read_fields(df, _structure(1, 3, 80.0)) == {}


def test_nan_floor_returns_empty():
    df = _frame([90, 100, 95, 85], [85, 92, 88, 75])
    assert strategy_read_fields(df, _structure(1, 3, float("nan"))) == {}


def test_non_positive_climax_high_returns_empty():
    df = _frame([90, -5.0, 95, 85], [85, -9.0, 88, 75])
    assert strategy_read_fields(df, _structure(1, 3, 80.0)) == {}


def test_out_of_range_bar_degrades_empty_and_logs_loudly(caplog):
    """The resolved facts cannot legitimately be absent on a fire — the
    degrade must leave a LOUD trace (EC-20), never a silent NULL that reads
    as 'never measured'."""
    df = _frame([90, 100], [85, 92])
    with caplog.at_level("ERROR", logger="chrollo.strategy_read"):
        out = strategy_read_fields(df, _structure(99, 1, 80.0))
    assert out == {}
    assert any("strategy read failed on a FIRE" in r.message for r in caplog.records)


def test_archive_values_preserve_null_and_coerce_integer():
    # Family contract: NULL survives (both prefixes), INTEGER lands a plain int.
    live = strategy_archive_values(
        {"_strategy_correction_depth_pct": 0.2,
         "_strategy_floor_above_ar": 1.0}.get, prefixed=True)
    assert live == {"strategy_correction_depth_pct": 0.2,
                    "strategy_floor_above_ar": 1}
    assert isinstance(live["strategy_floor_above_ar"], int)
    absent = strategy_archive_values({}.get, prefixed=True)
    assert absent == {c: None for c in STRATEGY_COLUMN_SQL}
    nan_scrub = strategy_archive_values(
        {"_strategy_correction_depth_pct": float("nan"),
         "_strategy_floor_above_ar": None}.get, prefixed=True)
    assert nan_scrub["strategy_correction_depth_pct"] is None


def test_depth_definition_is_the_docstring_formula():
    # Mutation tripwire: pin the formula itself on a second, unrelated frame.
    df = _frame([10, 200, 30], [5, 150, 20])
    out = strategy_read_fields(df, _structure(1, 2, 44.0))
    assert math.isclose(out["_strategy_correction_depth_pct"], (200 - 44) / 200)
    assert out["_strategy_floor_above_ar"] == 1   # 44 >= 20
