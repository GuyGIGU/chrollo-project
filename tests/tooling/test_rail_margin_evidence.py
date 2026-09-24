"""Count-math pins for the rail margin-evidence instrument (Rail Program Task 2).

The campaign's floors are fractions but its evidence is integer bars; these
tests pin the fraction->count translation at the exact boundary values the
protocol doc argues from (docs/rail_program_protocol_2026-07.md), so a silent
off-by-one in ceil/floor can never misstate a margin. Pure math only — no DB,
no fixtures, no engine replay (the instrument's replay path certifies itself
against the election's own trace at run time).
"""
from __future__ import annotations

import pytest

from tools.rail_margin_evidence import (
    DWELL_GRID,
    MID_GRID,
    RESPECT_GRID,
    dwell_margin,
    dwell_needed,
    frac_count,
    mid_allowed,
    mid_margin,
    outside_allowed,
    respect_margin,
    tolerance_allowed,
)

pytestmark = pytest.mark.regression


def test_grids_mirror_the_sealed_protocol():
    """The protocol doc's grids are closed (amendment needs an operator ruling
    in its changelog); the instrument's copies must not drift or grow."""
    assert DWELL_GRID == (0.125, 0.10)
    assert MID_GRID == (0.50, 0.55)
    assert RESPECT_GRID == (0.75,)


def test_egbn_examined_window_counts():
    """EGBN's engine-examined candidate: 3 of 23 closes in the lower third
    (lower_dwell 0.1304). Fails the 0.15 floor by one bar; passes both grid
    values exactly (needs 3)."""
    assert dwell_needed(0.15, 23) == 4
    assert dwell_needed(0.125, 23) == 3
    assert dwell_needed(0.10, 23) == 3


def test_ypf_examined_window_counts():
    """YPF's engine-examined candidate (n=14): lower 2/14 (0.1429) and
    mid 7/14 (0.50). The 0.50 mid cap passes NON-STRICT at exactly 7."""
    assert dwell_needed(0.15, 14) == 3      # 2/14 fails baseline
    assert dwell_needed(0.125, 14) == 2     # 2/14 passes the first grid value
    assert mid_allowed(0.45, 14) == 6       # 7/14 fails baseline
    assert mid_allowed(0.50, 14) == 7       # 7/14 passes at the cap, non-strict


def test_pke_examined_window_counts():
    """PKE's engine-examined candidate: 5 of 22 bars outside (respect 0.7727).
    One bar over at baseline; exactly allowed at 0.75 AND under the one-bar
    tolerance — the two framings the protocol keeps distinct."""
    assert outside_allowed(0.80, 22) == 4       # 5 outside fails baseline
    assert outside_allowed(0.75, 22) == 5       # rate framing converts
    assert tolerance_allowed(0.80, 22) == 5     # tolerance framing converts


def test_exact_integer_boundaries_pass_non_strict():
    """Where floor*n is an exact integer the gate comparisons are non-strict
    (>= / <=): the count formulas must not demand an extra bar."""
    assert dwell_needed(0.15, 20) == 3          # 3/20 == 0.15 passes
    assert outside_allowed(0.80, 20) == 4       # 4/20 outside == 0.80 passes
    assert mid_allowed(0.45, 20) == 9           # 9/20 == 0.45 passes


def test_tolerance_is_exactly_one_bar_of_grace():
    """Protocol L3b is the documented rate plus ONE bar — never two."""
    for n in (10, 20, 22, 40, 60):
        assert tolerance_allowed(0.80, n) == outside_allowed(0.80, n) + 1


def test_frac_count_round_trips_the_gates_4dp_rounding():
    """The eq dict rounds fractions to 4dp; the integer numerator must be
    recoverable exactly for every count at corpus window lengths."""
    for n in range(5, 121):
        for k in range(0, n + 1):
            assert frac_count(round(k / n, 4), n) == k


def test_dwell_margin_binds_on_the_worse_half():
    """The half-dwell gate needs BOTH thirds worked; the margin must report
    the binding (worse) side, and None when dwell was never measured."""
    row = {"n": 20, "low": 5, "up": 2, "mid": 13, "outside": 0}
    assert dwell_margin(row, 0.15) == 2 - 3     # upper third binds
    assert dwell_margin({"n": 20, "low": None, "up": None, "mid": None,
                         "outside": 0}, 0.15) is None
    assert mid_margin(row, 0.45) == 9 - 13
    assert respect_margin({"n": 22, "outside": 5}, 0.80) == -1
    assert respect_margin({"n": 22, "outside": 5}, 0.80, tolerance=True) == 0
