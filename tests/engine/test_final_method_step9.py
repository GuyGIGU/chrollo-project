"""Build step 9 of the final method (docs/final_method_2026-09.md point 5): the box opens on the anchors.

His ruling (Sat 12/09/2026): "No, Box opens on the anchors of each of the Boundary rail (Resistance & Support)". The box
opens on the earlier anchor day and never extends left: under BOX_OPENS_ON_ANCHORS_ENABLED the shared-rail
back-extension (box_primitives.backext_shared_rail) returns the anchor pair's own start. One default-off switch;
flag-off byte-identical (the fleet, junk, marks and reader-pin guards prove that at scale).
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from config import settings
from engine_alpha.freeze.manifest import ENGINE_SETTINGS_KEYS
from engine_alpha.structure import box_primitives, bricks
from engine_alpha.structure.box_primitives import backext_shared_rail

SWITCH = "BOX_OPENS_ON_ANCHORS_ENABLED"
S_VAL, R_VAL = 99.75, 110.25          # the wave's valley low and peak high
ANCHOR_START = 36                     # the elected pair: the valley on day 36, the peak on day 40


def _frame(n=60):
    """Twenty days far above the range, then a triangle wave between 100 and 110 with a valley every 8 days from
    day 20: the elected pair sits on days 36 and 40, and the valley on day 20 touches S with every bar between
    inside the buffered band, so the back-extension walks the start from 36 to 20."""
    t = np.arange(n)
    wave = np.where(((t - 20) % 8) <= 4, 100.0 + 2.5 * ((t - 20) % 8), 110.0 - 2.5 * (((t - 20) % 8) - 4))
    mid = np.where(t < 20, 140.0 - 0.5 * t, wave)
    idx = pd.bdate_range("2026-01-05", periods=n)
    return pd.DataFrame({"Open": mid, "High": mid + 0.25, "Low": mid - 0.25, "Close": mid,
                         "Volume": 1e6}, index=idx)


def test_the_switch_is_dark_and_rides_the_manifest():
    assert getattr(settings, SWITCH) is False
    assert SWITCH in ENGINE_SETTINGS_KEYS


def test_the_fixture_extends_flag_off():
    assert backext_shared_rail(_frame(), R_VAL, S_VAL, ANCHOR_START, 1.0) == 20, \
        "flag-off the start walks left to the day-20 valley on S"


def test_the_box_opens_on_its_anchors_under_the_switch(monkeypatch):
    monkeypatch.setattr(settings, SWITCH, True)
    assert backext_shared_rail(_frame(), R_VAL, S_VAL, ANCHOR_START, 1.0) == ANCHOR_START, \
        "the box opens on the earlier anchor day and never extends left"
    assert backext_shared_rail(_frame(), R_VAL, S_VAL, 0, 1.0) == 0, "a start at the window's first day stays"


def test_both_callers_read_the_one_function():
    # The live walk (bricks.validate_equilibrium) and the diagnostic mirror (phase_b_zigzag) both call THIS
    # function by name, so the switch has one site.
    assert bricks.backext_shared_rail is backext_shared_rail
    assert box_primitives.backext_shared_rail is backext_shared_rail
    import inspect
    assert "backext_shared_rail(" in inspect.getsource(bricks.validate_equilibrium)
    assert "backext_shared_rail(" in inspect.getsource(box_primitives.phase_b_zigzag)


def test_the_switch_is_read_at_call_time(monkeypatch):
    df = _frame()
    assert backext_shared_rail(df, R_VAL, S_VAL, ANCHOR_START, 1.0) == 20
    monkeypatch.setattr(settings, SWITCH, True)
    assert backext_shared_rail(df, R_VAL, S_VAL, ANCHOR_START, 1.0) == ANCHOR_START
    monkeypatch.setattr(settings, SWITCH, False)
    assert backext_shared_rail(df, R_VAL, S_VAL, ANCHOR_START, 1.0) == 20, "never cached"


@pytest.mark.parametrize("start", [28, 36, 44])
def test_every_later_start_keeps_its_own_anchor_under_the_switch(monkeypatch, start):
    monkeypatch.setattr(settings, SWITCH, True)
    assert backext_shared_rail(_frame(), R_VAL, S_VAL, start, 1.0) == start
